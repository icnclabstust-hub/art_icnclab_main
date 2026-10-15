#!/usr/bin/env python3
"""
統一 RAG 管理器服務 V2
提供多種 RAG 策略的統一接口，支援動態切換 LLM 模型和 RAG 策略
整合 Ollama 模型和 Neo4j/ChromaDB
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import chromadb
import graph_anchor
import httpx
import k_scorer
import uvicorn

# ChromaDB 共用 embedding function（BGE-M3，取代預設的英文為主模型）
from bge_m3_embedding import EMBED_OLLAMA_URL, BGEM3EmbeddingFunction
from citations import build_citations
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from graph_query import DEFAULT_MIN_RELATIVE_SCORE, apply_relative_cutoff, build_lucene_query
from guard_coarse import CoarseResult, check_answer

# 導入多語言查詢翻譯器
from multilingual_query_translator import MultilingualQueryTranslator
from neo4j import GraphDatabase
from pydantic import BaseModel
from redis_cache import RedisQueryCache, connect_redis, is_refusal
from retrieval_fusion import DEFAULT_RRF_K, rrf_fuse

# 導入智能關鍵詞提取器
from smart_keyword_extractor import SmartKeywordExtractor
from streaming import SentenceSplitter, ThinkFilter, ndjson, sentence_hook, with_heartbeat

# 配置日誌
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ==================== 查詢緩存 ====================


class QueryCache:
    """查詢結果緩存 - LRU with TTL"""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        """
        初始化緩存

        Args:
            max_size: 最大緩存條目數
            ttl_seconds: 緩存過期時間（秒）
        """
        self.max_size = max_size
        self.ttl = timedelta(seconds=ttl_seconds)
        self.cache: OrderedDict = OrderedDict()
        self.stats = {"hits": 0, "misses": 0, "evictions": 0, "expirations": 0}

    def _make_key(self, query: str, strategy: str, max_results: int) -> str:
        """生成緩存鍵"""
        # 使用 MD5 hash 來創建唯一的緩存鍵
        content = f"{query}|{strategy}|{max_results}"
        return hashlib.md5(content.encode("utf-8")).hexdigest()  # noqa: S324 -- 僅作快取鍵，非安全用途

    def get(self, query: str, strategy: str, max_results: int) -> list[dict[str, Any]] | None:
        """獲取緩存結果"""
        key = self._make_key(query, strategy, max_results)

        if key in self.cache:
            entry = self.cache[key]
            # 檢查是否過期
            if datetime.now() - entry["timestamp"] < self.ttl:
                # 移到最後（LRU）
                self.cache.move_to_end(key)
                self.stats["hits"] += 1
                logger.info(f"💾 緩存命中: {query[:30]}... | 策略: {strategy}")
                return entry["data"]
            else:
                # 過期，刪除
                del self.cache[key]
                self.stats["expirations"] += 1
                logger.debug(f"⏰ 緩存過期: {query[:30]}...")

        self.stats["misses"] += 1
        return None

    def set(
        self,
        query: str,
        strategy: str,
        max_results: int,
        data: list[dict[str, Any]],
        doc_ids: Any = (),  # 介面同 RedisQueryCache；記憶體版不做來源失效
    ):
        """設置緩存結果"""
        key = self._make_key(query, strategy, max_results)

        # 如果緩存已滿，移除最舊的條目
        if len(self.cache) >= self.max_size and key not in self.cache:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
            self.stats["evictions"] += 1

        # 添加新條目
        self.cache[key] = {"data": data, "timestamp": datetime.now()}

        # 移到最後（LRU）
        self.cache.move_to_end(key)

        logger.debug(f"💾 緩存保存: {query[:30]}... | 策略: {strategy}")

    def clear(self):
        """清空緩存"""
        size = len(self.cache)
        self.cache.clear()
        logger.info(f"🗑️  清空緩存: {size} 個條目")

    def get_stats(self) -> dict[str, Any]:
        """獲取緩存統計信息"""
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0

        return {
            **self.stats,
            "total_requests": total_requests,
            "hit_rate_percent": round(hit_rate, 2),
            "current_size": len(self.cache),
            "max_size": self.max_size,
            "ttl_seconds": int(self.ttl.total_seconds()),
        }


# 創建 FastAPI 應用
app = FastAPI(
    title="Art History RAG Manager V2",
    description="統一 RAG 管理器 - 支援 42 種 RAG+LLM 組合",
    version="2.0.0",
)

# 添加 CORS 中間件（僅信任本機 Open WebUI 來源，不用萬用字元）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== 稽核日誌（Phase 0：唯讀觀察，不影響回應內容） ====================
# 對應設計文件 docs/designs/2026-09-11-target-architecture-consistency-eval-faithfulness.md。
# 目的：先為現行請求量觀察一個穩定的 event_id，供 Phase 2 起 catalog.sync_events／
# Phase 3 起 eval.measurements 建立關聯時使用；本階段不寫入任何資料庫、不改變任何回應內容。
audit_logger = logging.getLogger("rag_audit")


@app.middleware("http")
async def audit_log_middleware(request: Request, call_next):
    """記錄每次請求的 event_id／路徑／耗時，僅供觀察，不影響回應（S-15：不記密碼/個資原文）。"""
    event_id = str(uuid.uuid4())
    started_at = time.monotonic()
    response = await call_next(request)
    duration_ms = round((time.monotonic() - started_at) * 1000, 1)
    audit_logger.info(
        json.dumps(
            {
                "event_id": event_id,
                "path": request.url.path,
                "method": request.method,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
            ensure_ascii=False,
        )
    )
    return response


# ==================== 配置加載 ====================

config_path = Path(__file__).parent / "rag_config.json"
with open(config_path, encoding="utf-8") as f:
    RAG_CONFIG = json.load(f)

# 密碼不放在命令列（同機任何使用者用 ps 都看得到）：由 ENV_FILE 指向的 .env 讀入；
# 已存在的環境變數優先，所以啟動時明確指定的埠、位址不會被 .env 內的舊值蓋掉
if os.getenv("ENV_FILE"):
    load_dotenv(os.environ["ENV_FILE"], override=False)

# 環境變數配置
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# 原生 Neo4j（WSL 直接執行），使用標準埠 bolt:7687 / http:7474。
# 2026-09-20 前曾改用 7688/7475，因 WSL 系統自帶的 neo4j.service 佔用標準埠；
# 該系統服務已停用，標準埠歸本專案。詳見 docs/2026-09-20-port-consolidation.md
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
if not NEO4J_PASSWORD:
    raise RuntimeError(
        "缺少 NEO4J_PASSWORD 環境變數。請以 ENV_FILE=<.env 路徑> 指定密碼檔，例如："
        "ENV_FILE=/mnt/f/.../.env python3 unified_rag_manager_v2.py"
        "（Start-NativeServices.ps1 已內建設定，不需手動處理）"
    )
CHROMADB_HOST = os.getenv("CHROMADB_HOST", "localhost")
CHROMADB_PORT = int(os.getenv("CHROMADB_PORT", "8000"))
CHROMADB_COLLECTION = os.getenv("CHROMADB_COLLECTION", "art_history_bgem3")

# 關閉思考鏈的模型前綴（逗號分隔）。qwen3 系列的 <think> 階段佔生成時間大宗
# （實測同題 19s -> 7s、答案品質相當）；deepseek-r1 的價值就在推理，預設不關。
NO_THINK_MODEL_PREFIXES = [
    p.strip() for p in os.getenv("RAG_NO_THINK_MODELS", "qwen3").split(",") if p.strip()
]


def _no_think(model_id: str) -> bool:
    """此模型是否應關閉思考鏈（Ollama 的 think 參數，不支援的模型會靜默忽略）。"""
    return any(model_id.startswith(pfx) for pfx in NO_THINK_MODEL_PREFIXES)


# Elasticsearch（hybrid_es_rag 策略用：BM25 全文檢索 + 向量 kNN，手動 RRF 融合排序）
# 免費版授權不含 ES 原生 RRF retriever，所以用兩次查詢自己做分數融合
ES_URL = os.getenv("ES_URL", "https://localhost:9200")
ES_USERNAME = os.getenv("ES_USERNAME", "elastic")
ES_PASSWORD = os.getenv("ES_PASSWORD")
ES_INDEX = "art_history_hybrid"

# 系統級三路 RRF（規格 RET-01～07）：model_combination_id 未帶 @策略 時採用 DEFAULT_STRATEGY；
# 各路各取 HYBRID_TOP_K 筆，融合後取請求的 max_results；HYBRID_ROUTES 可逐路關閉（RET-03）
DEFAULT_STRATEGY = "hybrid"
RRF_K = int(os.getenv("RRF_K", str(DEFAULT_RRF_K)))
HYBRID_TOP_K = int(os.getenv("HYBRID_TOP_K", "20"))
HYBRID_ROUTES = [
    r.strip() for r in os.getenv("HYBRID_ROUTES", "vector,fulltext,graph").split(",") if r.strip()
]
# 系統圖譜路：低於該次最高分此比例的全文命中視為弱命中而捨棄
GRAPH_MIN_RELATIVE_SCORE = float(
    os.getenv("GRAPH_MIN_RELATIVE_SCORE", str(DEFAULT_MIN_RELATIVE_SCORE))
)

# 是否記錄使用者提問（規格 BIZ-03：法規告知 P0-2 未完成前維持關閉）
BIZ_LOGGING = os.getenv("BIZ_LOGGING", "false").lower() == "true"

# Phase 4 防護（GRD-06、GRD-08）：shadow＝粗篩只計算並寫入 eval.guard_shadow、不改變回答；
# off＝完全不執行。門檻須先以影子資料＋黃金集校準（GRD-05），故尚無阻擋模式
GUARD_MODE = os.getenv("GUARD_MODE", "shadow").lower()

# 查詢翻譯（設計 docs/designs/2026-10-09-llm-query-translation.md）：llm_hinted＝詞典找出已知術語
# 作為提示，再由 LLM 譯成英文檢索用查詢，生成仍用原問題；dictionary＝原本的詞典替換行為
QUERY_TRANSLATION = os.getenv("QUERY_TRANSLATION", "llm_hinted").lower()
# same＝用本次請求的生成模型翻譯：筆電 GPU 只有 8 GB，翻譯與生成用不同模型時每題都要換模型、
# 冷啟動逾時而退回詞典（spike 2026-10-09 實測）。
# /retrieve 沒有生成模型時用 QUERY_TRANSLATION_DEFAULT_MODEL
QUERY_TRANSLATION_MODEL = os.getenv("QUERY_TRANSLATION_MODEL", "same")
QUERY_TRANSLATION_DEFAULT_MODEL = os.getenv("QUERY_TRANSLATION_DEFAULT_MODEL", "llama3.1:8b")
QUERY_TRANSLATION_TIMEOUT_SEC = float(os.getenv("QUERY_TRANSLATION_TIMEOUT_SEC", "3"))
# Ollama 閒置 5 分鐘即卸載模型，冷啟動載入會超過逾時而退回詞典；延長常駐並在啟動時預熱
QUERY_TRANSLATION_KEEP_ALIVE = os.getenv("QUERY_TRANSLATION_KEEP_ALIVE", "30m")
# 翻譯模型使用的 GPU 層數（Ollama num_gpu）；0＝只用 CPU，與生成模型不搶 8 GB 顯存、換生成模型時
# 不被卸載（第 2 層 A1 方案 1，2026-10-14 實驗）。未設定＝Ollama 預設（現行行為）
# 翻譯可改由另一個 Ollama 提供（例如只用 CPU 的 11435）：GPU Ollama 換載生成模型時會卸載閒置模型，
# 即使翻譯模型只用 CPU 也會被一併卸載（2026-10-14 E13 實測）
QUERY_TRANSLATION_OLLAMA_URL = os.getenv("QUERY_TRANSLATION_OLLAMA_URL", "") or None
# 翻譯長度上限與重複懲罰：1024 是為會先思考的 deepseek-r1 而設；小模型（qwen3:1.7b，思考關閉）
# 偶爾陷入重複迴圈直到上限（10-14 試做 1：T13 39 秒），逾時後 Ollama 仍佔住 CPU 拖慢下一題。
# 試做結果：200＋重複懲罰 1.15 → 30 題全在 3 秒內、術語 0.867～0.872。預設不變
QUERY_TRANSLATION_NUM_PREDICT = int(os.getenv("QUERY_TRANSLATION_NUM_PREDICT", "1024"))
_QT_REPEAT = os.getenv("QUERY_TRANSLATION_REPEAT_PENALTY", "")
QUERY_TRANSLATION_REPEAT_PENALTY = float(_QT_REPEAT) if _QT_REPEAT.strip() else None
_QT_NUM_GPU = os.getenv("QUERY_TRANSLATION_NUM_GPU", "")
QUERY_TRANSLATION_NUM_GPU = int(_QT_NUM_GPU) if _QT_NUM_GPU.strip() else None
QUERY_TRANSLATION_PROMPT = """你是藝術史檢索系統的查詢翻譯器。
把下列中文問題翻成英文，供英文藝術史資料庫檢索。
規則：藝術家用通行英文全名；作品用通行英文標題；藝術史術語用英文學界慣用詞；
問題中已出現的拉丁文、義大利文、德文術語（如 Kunstwollen、colorito、sfumato）原樣保留。
{hint}只輸出英文翻譯，不要解釋。
問題：{query}"""
_translation_cache: dict[tuple[str, str], tuple[str, dict[str, Any]]] = {}
# llama3.1:8b 常不理會「只輸出翻譯」，先加「Here is the translation (of the problem):」之類開場白，
# 這些字會直接進入檢索（spike 實測「林布蘭的肖像畫」命中 5→1）；去掉開場白與外圍引號
_TRANSLATION_PREAMBLE = re.compile(
    r"^\s*(here\s+is|here's|translation)\b[^:：]{0,60}[:：]\s*", re.IGNORECASE
)
_TRANSLATION_CACHE_MAX = 512


def _clean_translation(text: str) -> str:
    """把 LLM 譯文整理成單行檢索字串：去思考段落、開場白、換行與外圍引號。

    deepseek-r1 不理會 think=false，會把 ``<think>…</think>`` 直接寫在回應裡；思考被長度上限
    截斷（沒有結束標記）時整段不可用，回傳空字串讓呼叫端退回詞典。
    """
    text = re.sub(r"<think>.*?</think>", " ", text, flags=re.DOTALL)
    if "<think>" in text:
        return ""
    text = " ".join(text.split())
    text = _TRANSLATION_PREAMBLE.sub("", text)
    return text.strip("\"'「」“” ")


GUARD_HARD_TIMEOUT_SEC = float(os.getenv("GUARD_HARD_TIMEOUT_SEC", "30"))  # GRD-06c 掛住保護

# ==================== 請求/響應模型 ====================


class QueryRequest(BaseModel):
    """查詢請求模型"""

    query: str
    model_combination_id: str
    max_results: int = 5
    include_sources: bool = True
    temperature: float | None = None
    max_tokens: int | None = None
    source_filter: str | None = None  # 限定只檢索 ChromaDB metadata.source 等於此值的文件


class QueryResponse(BaseModel):
    """查詢響應模型"""

    answer: str
    sources: list[dict[str, Any]]
    model_used: str
    rag_strategy: str
    retrieval_time_ms: float
    generation_time_ms: float
    metadata: dict[str, Any]
    # 規格 GEN-02：每個回應必附引用；index 對應提示詞中的「[文檔 N]」
    citations: list[dict[str, Any]] = []


class HealthResponse(BaseModel):
    """健康檢查響應"""

    status: str
    services: dict[str, bool]
    timestamp: str


# ==================== 連接管理器 ====================


class ConnectionManager:
    """管理外部服務連接"""

    def __init__(self):
        self.neo4j_driver = None
        self.chroma_client = None
        self.http_client = httpx.AsyncClient(timeout=900.0)
        # 獨立的 client 給 Elasticsearch 用：ES 走自簽憑證 HTTPS，只有它需要關閉憑證驗證，
        # 不能共用 http_client（那個要保持驗證，給其他 HTTPS 呼叫用）
        self.es_http_client = httpx.AsyncClient(timeout=30.0, verify=False)  # noqa: S501 -- 本機自簽憑證

    async def initialize(self):
        """初始化所有連接"""
        try:
            # Neo4j 連接
            logger.info(f"連接 Neo4j: {NEO4J_URI}")
            self.neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            # 測試連接
            self.neo4j_driver.verify_connectivity()
            logger.info("✅ Neo4j 連接成功")
        except Exception as e:
            logger.error(f"❌ Neo4j 連接失敗: {e}")
            self.neo4j_driver = None

        try:
            # ChromaDB 連接
            logger.info(f"連接 ChromaDB: {CHROMADB_HOST}:{CHROMADB_PORT}")
            self.chroma_client = chromadb.HttpClient(host=CHROMADB_HOST, port=CHROMADB_PORT)
            # 測試連接
            self.chroma_client.heartbeat()
            logger.info("✅ ChromaDB 連接成功")
        except Exception as e:
            logger.error(f"❌ ChromaDB 連接失敗: {e}")
            self.chroma_client = None

        # 測試 Ollama 連接
        try:
            logger.info(f"連接 Ollama: {OLLAMA_BASE_URL}")
            response = await self.http_client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                logger.info("✅ Ollama 連接成功")
            else:
                logger.error(f"❌ Ollama 連接失敗: {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Ollama 連接失敗: {e}")

    async def close(self):
        """關閉所有連接"""
        if self.neo4j_driver:
            self.neo4j_driver.close()
        await self.http_client.aclose()
        await self.es_http_client.aclose()

    def get_health_status(self) -> dict[str, bool]:
        """獲取服務健康狀態"""
        status = {"neo4j": False, "chromadb": False, "ollama": False}

        # 檢查 Neo4j
        if self.neo4j_driver:
            try:
                self.neo4j_driver.verify_connectivity()
                status["neo4j"] = True
            except Exception as e:
                logger.debug(f"Neo4j 健康檢查失敗: {e}")

        # 檢查 ChromaDB
        if self.chroma_client:
            try:
                self.chroma_client.heartbeat()
                status["chromadb"] = True
            except Exception as e:
                logger.debug(f"ChromaDB 健康檢查失敗: {e}")

        return status


# 全局連接管理器
conn_manager = ConnectionManager()

# 全局多語言翻譯器
query_translator = None

# 全局智能關鍵詞提取器
keyword_extractor = None

# 全局查詢緩存
query_cache = None
CACHE_BACKEND = os.getenv("CACHE_BACKEND", "redis").lower()
RAG_CACHE_REDIS_URL = os.getenv("RAG_CACHE_REDIS_URL", "redis://localhost:6379/0")


# Google Books 空殼移出證據（規格 Q11，2026-10-14 實驗開關，預設關閉）：58 筆 googlebooks 全為空殼
# （去書目後 ≤25 字，description 只是出版社名），在 hybrid 前 5 名佔位。設為 googlebooks_ 啟用。
EXCLUDE_EVIDENCE_PREFIXES = tuple(
    p for p in os.getenv("EXCLUDE_EVIDENCE_PREFIXES", "").split(",") if p.strip()
)
_EXCLUDE_MARGIN = 5  # 啟用時多取幾筆，過濾後仍能補滿 max_results


def _evidence_only(sources: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """移除被排除前綴的來源（空殼不作為證據），再截到 limit。"""
    if not EXCLUDE_EVIDENCE_PREFIXES:
        return sources
    kept = [
        d
        for d, c in zip(sources, build_citations(sources), strict=True)
        if not (c.get("external_id") or "").startswith(EXCLUDE_EVIDENCE_PREFIXES)
    ]
    return kept[:limit]


def _source_doc_ids(sources: list[dict[str, Any]]) -> list[str]:
    """快取項用到的來源 doc_id（RET-12 反向索引）。"""
    return [c["doc_id"] for c in build_citations(sources) if c.get("doc_id")]


# ==================== RAG 策略實現 ====================


class RAGStrategy:
    """RAG 策略基類"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    async def retrieve(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """檢索相關文檔"""
        raise NotImplementedError

    async def generate(
        self,
        query: str,
        context: list[dict[str, Any]],
        model_id: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """生成答案"""
        # 構建提示詞
        context_text = self._format_context(context)
        prompt = self._build_prompt(query, context_text)

        # 調用 Ollama
        try:
            payload = {
                "model": model_id,
                "prompt": prompt,
                "stream": False,
                # temperature/num_predict 必須放在 options 裡，放在最外層 Ollama 會直接忽略
                # （忽略 num_predict 代表沒有生成長度上限，曾實際觀測到單次生成失控超過
                # 1萬 token 還沒停，把 Ollama 唯一的處理槽卡死、拖累其他所有請求）
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            }
            if _no_think(model_id):
                # 只在要關閉時才帶 think 鍵；未帶鍵時模型維持各自預設行為
                payload["think"] = False
            response = await conn_manager.http_client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json=payload,
                timeout=900.0,  # 32B/30B 級模型在 Advanced/Graph/Agentic RAG 下常需 5-10 分鐘
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("response", "")
            else:
                error_text = response.text
                logger.error(f"Ollama 生成失敗: {response.status_code}, 詳情: {error_text}")
                return f"抱歉，生成答案時發生錯誤（狀態碼: {response.status_code}）"
        except Exception as e:
            logger.error(f"調用 Ollama 失敗: {e}")
            return f"錯誤: {str(e)}"

    def _format_context(self, context: list[dict[str, Any]]) -> str:
        """格式化上下文"""
        if not context:
            return "沒有找到相關資料。"

        formatted = []
        for i, doc in enumerate(context, 1):
            content = doc.get("content", doc.get("text", ""))
            source = doc.get("source", "未知來源")
            formatted.append(f"[文檔 {i}] 來源: {source}\n{content}")

        return "\n\n".join(formatted)

    def _build_prompt(self, query: str, context: str) -> str:
        """構建提示詞"""
        return f"""你是一位藝術史專家助手。請基於以下參考資料回答用戶的問題。

參考資料：
{context}

用戶問題：{query}

請提供準確、詳細的回答。如果參考資料中沒有相關信息，請誠實說明。
如果問題指定了某個博物館或收藏機構，而參考資料中沒有屬於該機構的作品：只能說「檢索結果中沒有找到」，
不得斷言該機構沒有收藏，也不得把其他機構的作品歸給該機構。
"""


class VectorOnlyRAG(RAGStrategy):
    """純向量檢索 RAG"""

    def __init__(self):
        super().__init__("Vector Only RAG", "使用向量數據庫進行語義檢索")

    async def retrieve(
        self, query: str, max_results: int = 5, source_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """使用 ChromaDB 進行向量檢索"""
        if not conn_manager.chroma_client:
            logger.warning("ChromaDB 未連接，返回空結果")
            return []

        try:
            # 獲取或創建集合（BGE-M3 embedding，取代預設英文為主模型）
            collection = conn_manager.chroma_client.get_or_create_collection(
                name=CHROMADB_COLLECTION, embedding_function=BGEM3EmbeddingFunction()
            )

            # 執行查詢（若指定 source_filter，僅檢索 metadata.source 相符的文件）
            results = collection.query(
                query_texts=[query],
                n_results=max_results,
                where={"source": source_filter} if source_filter else None,
            )

            # 格式化結果
            documents = []
            if results and results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    metadata = dict(results["metadatas"][0][i]) if results["metadatas"] else {}
                    # chunk id 供系統級 RRF 對齊文件（舊資料可能缺 parent_id）
                    metadata.setdefault("chunk_id", results["ids"][0][i])
                    distance = results["distances"][0][i] if results["distances"] else 0

                    documents.append(
                        {
                            "content": doc,
                            "metadata": metadata,
                            "score": 1 - distance,  # 轉換為相似度分數
                            "source": metadata.get("source", "ChromaDB"),
                        }
                    )

            logger.info(f"向量檢索返回 {len(documents)} 個結果")
            return documents

        except Exception as e:
            logger.error(f"向量檢索失敗: {e}")
            return []


class HybridESRAG(RAGStrategy):
    """Hybrid Elasticsearch RAG - BM25 全文檢索 + BGE-M3 向量 kNN，用 RRF 手動融合排序

    背景：純向量檢索（VectorOnlyRAG）對長篇學術問題裡的專有名詞（人名、作品名）
    有時抓不準，BM25 擅長這類精確詞彙比對，兩者互補。
    免費版 ES 授權不含原生 RRF retriever（回傳 403 license 錯誤），
    所以這裡自己對兩份排名結果做 RRF 融合：score = Σ 1/(k + rank)，k=60（業界慣用常數）。
    """

    RRF_K = 60

    def __init__(self):
        super().__init__("Hybrid Elasticsearch RAG", "BM25 全文檢索 + 向量 kNN，RRF 融合排序")

    async def _embed_query(self, query: str) -> list[float] | None:
        # 獨立的嵌入 Ollama 沒啟動時退回主 Ollama（同 bge_m3_embedding）
        urls = [EMBED_OLLAMA_URL] + (
            [OLLAMA_BASE_URL] if EMBED_OLLAMA_URL != OLLAMA_BASE_URL else []
        )
        for url in urls:
            try:
                response = await conn_manager.http_client.post(
                    f"{url}/api/embed",
                    json={"model": "bge-m3:latest", "input": [query]},
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json()["embeddings"][0]
            except Exception as e:
                logger.error(f"Hybrid ES RAG 查詢向量化失敗（{url}）: {e}")
        return None

    async def _es_search(self, body: dict[str, Any]) -> list[dict[str, Any]]:
        response = await conn_manager.es_http_client.post(
            f"{ES_URL}/{ES_INDEX}/_search",
            json=body,
            auth=(ES_USERNAME, ES_PASSWORD),
        )
        response.raise_for_status()
        return response.json()["hits"]["hits"]

    async def retrieve(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        if not ES_PASSWORD:
            logger.warning("ES_PASSWORD 未設定，Hybrid ES RAG 無法使用，返回空結果")
            return []

        candidate_pool = max_results * 4  # 融合前每份排名多抓一些，讓 RRF 有得挑

        query_vector = await self._embed_query(query)
        if query_vector is None:
            return []

        try:
            bm25_hits, knn_hits = [], []
            bm25_body = {
                "query": {"match": {"content": query}},
                "size": candidate_pool,
                "_source": ["content", "source", "title", "artist", "date"],
            }
            knn_body = {
                "knn": {
                    "field": "embedding",
                    "query_vector": query_vector,
                    "k": candidate_pool,
                    "num_candidates": candidate_pool * 4,
                },
                "size": candidate_pool,
                "_source": ["content", "source", "title", "artist", "date"],
            }
            bm25_hits = await self._es_search(bm25_body)
            knn_hits = await self._es_search(knn_body)
        except Exception as e:
            logger.error(f"Hybrid ES RAG 檢索失敗: {e}")
            return []

        # RRF 融合：同一份文件在 BM25/kNN 排名榜的名次分別貢獻 1/(k+rank) 分數，加總排序
        rrf_scores: dict[str, float] = {}
        doc_data: dict[str, Any] = {}
        for hits in (bm25_hits, knn_hits):
            for rank, hit in enumerate(hits):
                doc_id = hit["_id"]
                rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (self.RRF_K + rank + 1)
                doc_data[doc_id] = hit["_source"]

        ranked_ids = sorted(rrf_scores.keys(), key=lambda d: rrf_scores[d], reverse=True)[
            :max_results
        ]

        documents = []
        for doc_id in ranked_ids:
            src = doc_data[doc_id]
            documents.append(
                {
                    "content": src.get("content", ""),
                    "metadata": {
                        "title": src.get("title", ""),
                        "artist": src.get("artist", ""),
                        "date": src.get("date", ""),
                        "source": src.get("source", ""),
                        "chunk_id": doc_id,  # ES _id 即 chunk id，供引用對應 catalog
                    },
                    "score": rrf_scores[doc_id],
                    "source": src.get("source", "Elasticsearch Hybrid"),
                }
            )

        logger.info(f"Hybrid ES RAG 檢索返回 {len(documents)} 個結果（BM25+kNN RRF 融合）")
        return documents


class FulltextESRAG(HybridESRAG):
    """純全文檢索：Elasticsearch BM25（系統級 RRF 的全文路，RET-01 ``fulltext``）"""

    def __init__(self):
        RAGStrategy.__init__(self, "Fulltext ES RAG", "Elasticsearch BM25 全文檢索")

    async def retrieve(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        if not ES_PASSWORD:
            logger.warning("ES_PASSWORD 未設定，全文檢索無法使用，返回空結果")
            return []
        body = {
            "query": {"match": {"content": query}},
            "size": max_results,
            "_source": ["content", "source", "title", "artist", "date", "parent_id"],
        }
        try:
            hits = await self._es_search(body)
        except Exception as e:
            logger.error(f"全文檢索失敗: {e}")
            return []

        documents = []
        for hit in hits:
            src = hit["_source"]
            documents.append(
                {
                    "content": src.get("content", ""),
                    "metadata": {
                        "title": src.get("title", ""),
                        "artist": src.get("artist", ""),
                        "date": src.get("date", ""),
                        "source": src.get("source", ""),
                        "parent_id": src.get("parent_id", ""),
                        "chunk_id": hit["_id"],
                    },
                    "score": hit.get("_score") or 0.0,
                    "source": src.get("source", "Elasticsearch"),
                }
            )
        logger.info(f"全文檢索返回 {len(documents)} 個結果（BM25）")
        return documents


class SystemHybridRAG(RAGStrategy):
    """系統級三路 RRF：向量＋全文＋圖並行檢索後以 RRF 融合（RET-01 ``hybrid``、RET-04～07）

    不做重排（RET-05／06：先取得量測基準）。某一路失敗或未啟用時以其餘路融合，
    ``metadata.fusion.ranks`` 可看出每份文件來自哪幾路。
    """

    def __init__(self, routes: dict[str, RAGStrategy]):
        super().__init__("System Hybrid RAG", "向量＋全文＋圖三路檢索，系統級 RRF 融合")
        self.routes = routes

    async def retrieve(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        enabled = [r for r in HYBRID_ROUTES if r in self.routes]
        results = await asyncio.gather(
            *(
                self.routes[r].retrieve(query, HYBRID_TOP_K, fallback=False)
                if r == "graph" and isinstance(self.routes[r], SystemGraphRAG)
                else self.routes[r].retrieve(query, HYBRID_TOP_K)
                for r in enabled
            ),
            return_exceptions=True,
        )
        ranked: dict[str, list[dict[str, Any]]] = {}
        for route, result in zip(enabled, results, strict=True):
            if isinstance(result, BaseException):
                logger.error(f"三路 RRF 的 {route} 路失敗，略過: {result}")
                continue
            ranked[route] = result

        # 限制條件題（錨點模板 T2：畫家 × 館藏）命中時只採 graph 結果：其他兩路不會套用館藏條件，
        # 融合後會擠掉符合條件的作品（spike 限制條件 F1：graph 0.970、hybrid 0.665，2026-10-11）
        graph_docs = ranked.get("graph") or []
        if graph_docs and all(
            (d.get("metadata") or {}).get("graph_match") == "anchor:T2" for d in graph_docs
        ):
            logger.info(f"三路 RRF：限制條件題由 graph 錨點 T2 直接回傳 {len(graph_docs)} 筆")
            return graph_docs[:max_results]
        fused = rrf_fuse(ranked, k=RRF_K, top_n=max_results)
        counts = "／".join(f"{r} {len(docs)}" for r, docs in ranked.items())
        logger.info(f"三路 RRF 融合返回 {len(fused)} 個結果（各路候選：{counts}）")
        return fused


# Neo4j 節點上僅供資料維護使用的欄位（軟到期／軟刪除時間戳），不放進提供給模型的文字
_GRAPH_INTERNAL_KEYS = frozenset(
    {"valid_from", "valid_to", "is_deleted", "deleted_at", "updated_at"}
)


class GraphOnlyRAG(RAGStrategy):
    """純圖譜檢索 RAG"""

    def __init__(self):
        super().__init__("Graph Only RAG", "使用知識圖譜進行關係推理")

    async def retrieve(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """使用 Neo4j 進行圖譜檢索"""
        if not conn_manager.neo4j_driver:
            logger.warning("Neo4j 未連接，返回空結果")
            return []
        # 方案 A 擴及舊策略（Graph RAG、Advanced、Agentic 皆經此類）：問題中認得出畫家時改用
        # 錨點結果，避免下方 Lucene「~」模糊比對把 Nicolas Poussin 錯配成 Nicolas Castille
        # （2026-10-13 模擬 F4）。認不出畫家時維持原行為——此時沒有可錯配的畫家，不會退步。
        if GRAPH_RETRIEVAL == "anchor" and type(self) is GraphOnlyRAG:
            anchored = await _SYSTEM_ROUTES["graph"]._anchor_retrieve(
                query, max_results, fallback=False
            )
            if anchored:
                return anchored

        try:
            # 查詢改寫/實體正規化：跟 AdvancedGraphRAG 一樣，先用術語詞典把中文人名/作品名
            # （如「達文西」「雅典學院」）轉成圖譜裡實際存的正規英文詞，再抽關鍵詞，
            # 否則中文問題常常抽不出任何英文關鍵詞、退化成整句模糊查詢（幾乎必定查無結果）
            normalized_query = query
            if query_translator:
                try:
                    normalized_query, found_terms = query_translator.translate_terms(query)
                    if found_terms:
                        logger.info(f"🔤 實體正規化: '{query}' -> '{normalized_query}'")
                except Exception as e:
                    logger.warning(f"實體正規化失敗: {e}")

            # 使用智能關鍵詞提取器
            if keyword_extractor:
                search_terms, extraction_info = keyword_extractor.extract_keywords(
                    normalized_query,
                    max_keywords=5,
                    min_word_length=3,  # 提高最小長度以避免 'da' 這樣的詞
                )
                if not search_terms:
                    search_terms = [normalized_query]
            else:
                # 回退到基礎提取
                import re

                keywords = []
                # 不用 \b（中文緊貼英文詞時會漏抓，理由同 smart_keyword_extractor.py）
                english_words = re.findall(r"[a-zA-Z]{3,}", normalized_query)  # 最少3個字母
                stop_words = {
                    "the",
                    "a",
                    "an",
                    "and",
                    "or",
                    "but",
                    "in",
                    "on",
                    "at",
                    "to",
                    "for",
                    "of",
                    "with",
                    "by",
                    "from",
                    "as",
                    "is",
                    "was",
                    "are",
                    "were",
                    "da",
                    "de",
                    "di",
                    "del",
                    "van",
                    "von",
                    "le",
                    "la",
                }
                keywords = [w for w in english_words if w.lower() not in stop_words]
                search_terms = keywords if keywords else [normalized_query]

            logger.info(f"🔍 提取的搜索關鍵詞: {search_terms}")

            with conn_manager.neo4j_driver.session() as session:
                all_documents = []
                seen_titles = set()

                # 對每個關鍵詞分別查詢
                for term in search_terms:
                    # 使用全文索引進行模糊搜索
                    # 添加 ~ 後綴支援模糊匹配（最多2個字符差異）
                    fuzzy_term = f"{term}~" if len(term) >= 4 else term

                    # 1. 搜索藝術家（使用全文索引）
                    artist_query = """
                    CALL db.index.fulltext.queryNodes('artist_name_fulltext', $search_term)
                    YIELD node, score
                    WITH node as artist, score
                    LIMIT $limit
                    OPTIONAL MATCH (artist)-[r:CREATED]->(artwork:Artwork)
                    WHERE r.valid_to IS NULL AND coalesce(artwork.is_deleted, false) = false
                    RETURN artist as n, score,
                           collect({rel: type(r), node: artwork}) as relationships
                    """

                    artist_result = session.run(
                        artist_query, search_term=fuzzy_term, limit=max_results
                    )

                    # 收集藝術家結果
                    for record in artist_result:
                        node = record["n"]
                        score = record["score"]
                        title = node.get("name")

                        # 去重檢查
                        if title and title not in seen_titles:
                            seen_titles.add(title)
                            relationships = record["relationships"]
                            content = self._format_graph_node(node, relationships)

                            # 安全轉換Node為dict
                            metadata = {}
                            for key in node.keys():
                                value = node[key]
                                # 只保留可序列化的類型
                                if isinstance(value, (str, int, float, bool)) or value is None:
                                    metadata[key] = value
                                elif isinstance(value, (list, tuple)):
                                    metadata[key] = str(value)  # 轉換為字符串
                                elif hasattr(value, "isoformat"):
                                    # Neo4j DateTime/Date/Time objects
                                    metadata[key] = value.isoformat()
                                else:
                                    # 其他類型轉為字符串
                                    metadata[key] = str(value)

                            all_documents.append(
                                {
                                    "content": content,
                                    "metadata": metadata,
                                    "score": float(score),  # 使用全文搜索分數
                                    "source": "Neo4j Knowledge Graph (Artist)",
                                }
                            )

                        # 限制總結果數量
                        if len(all_documents) >= max_results:
                            break

                    if len(all_documents) >= max_results:
                        break

                    # 2. 搜索作品標題（使用全文索引）
                    artwork_title_query = """
                    CALL db.index.fulltext.queryNodes('artwork_title_fulltext', $search_term)
                    YIELD node, score
                    WHERE coalesce(node.is_deleted, false) = false
                    WITH node as artwork, score
                    LIMIT $limit
                    OPTIONAL MATCH (artwork)-[r]-(related)
                    WHERE r.valid_to IS NULL AND coalesce(related.is_deleted, false) = false
                    RETURN artwork as n, score,
                           collect({rel: type(r), node: related}) as relationships
                    """

                    artwork_result = session.run(
                        artwork_title_query,
                        search_term=fuzzy_term,
                        limit=max_results - len(all_documents),
                    )

                    # 收集作品結果
                    for record in artwork_result:
                        node = record["n"]
                        score = record["score"]
                        title = node.get("title")

                        # 去重檢查
                        if title and title not in seen_titles:
                            seen_titles.add(title)
                            relationships = record["relationships"]
                            content = self._format_graph_node(node, relationships)

                            # 安全轉換Node為dict
                            metadata = {}
                            for key in node.keys():
                                value = node[key]
                                # 只保留可序列化的類型
                                if isinstance(value, (str, int, float, bool)) or value is None:
                                    metadata[key] = value
                                elif isinstance(value, (list, tuple)):
                                    metadata[key] = str(value)  # 轉換為字符串
                                elif hasattr(value, "isoformat"):
                                    # Neo4j DateTime/Date/Time objects
                                    metadata[key] = value.isoformat()
                                else:
                                    # 其他類型轉為字符串
                                    metadata[key] = str(value)

                            all_documents.append(
                                {
                                    "content": content,
                                    "metadata": metadata,
                                    "score": float(score),  # 使用全文搜索分數
                                    "source": "Neo4j Knowledge Graph (Artwork)",
                                }
                            )

                        # 限制總結果數量
                        if len(all_documents) >= max_results:
                            break

                    if len(all_documents) >= max_results:
                        break

                # 按分數排序結果
                all_documents.sort(key=lambda x: x["score"], reverse=True)

                logger.info(f"圖譜檢索返回 {len(all_documents)} 個結果 (使用全文索引模糊匹配)")
                return all_documents

        except Exception as e:
            logger.error(f"圖譜檢索失敗: {e}")
            return []

    def _extract_entities(self, query: str) -> list[str]:
        """簡單的實體提取（分詞）"""
        # 移除常見停用詞
        stop_words = {
            "的",
            "是",
            "有",
            "在",
            "和",
            "與",
            "或",
            "對",
            "為",
            "了",
            "個",
            "著",
            "嗎",
            "呢",
            "吧",
        }
        words = [w for w in query if len(w) > 1 and w not in stop_words]
        return words[:5]  # 限制最多5個實體

    def _format_graph_node(self, node, relationships) -> str:
        """格式化圖譜節點信息"""
        # 判斷節點類型並獲取名稱
        node_name = node.get("title") or node.get("name", "未知")
        content = f"實體: {node_name}\n"

        # 添加屬性 - 安全處理各種類型；生命週期欄位與舊的單值 source（已由 sources 取代）
        # 不是給模型看的內容，放進去只會增加雜訊，甚至讓過時的來源被當成事實引用
        skip_keys = _GRAPH_INTERNAL_KEYS | ({"source"} if node.get("sources") else set())
        for key, value in node.items():
            if key not in ["name", "title"] and key not in skip_keys and value:
                # 安全序列化value
                if isinstance(value, (list, tuple, dict)):
                    content += f"{key}: {str(value)}\n"
                elif hasattr(value, "isoformat"):
                    content += f"{key}: {value.isoformat()}\n"
                else:
                    content += f"{key}: {value}\n"

        # 添加關係 - 安全處理Node對象
        if relationships:
            content += "\n相關關係:\n"
            for rel in relationships[:5]:  # 限制關係數量
                if rel.get("node"):
                    rel_type = rel.get("rel", "RELATED")
                    # 安全獲取關聯節點名稱
                    related_node = rel["node"]
                    if hasattr(related_node, "get"):
                        rel_node = related_node.get("title") or related_node.get("name", "未知")
                    else:
                        rel_node = str(related_node)
                    content += f"  - {rel_type} -> {rel_node}\n"

        return content


_ARTWORK_BY_TITLE = """
CALL db.index.fulltext.queryNodes('artwork_title_fulltext', $q) YIELD node, score
WHERE coalesce(node.is_deleted, false) = false
RETURN node AS artwork, score ORDER BY score DESC LIMIT $limit
"""

_ARTIST_BY_NAME = """
CALL db.index.fulltext.queryNodes('artist_name_fulltext', $q) YIELD node, score
RETURN elementId(node) AS artist_id, score ORDER BY score DESC LIMIT $limit
"""

_ARTWORKS_OF_ARTISTS = """
UNWIND $artists AS a
MATCH (x:Artist)-[c:CREATED]->(artwork:Artwork)
WHERE elementId(x) = a.artist_id AND c.valid_to IS NULL
  AND coalesce(artwork.is_deleted, false) = false
WITH artwork, max(a.score) AS score
RETURN artwork, score ORDER BY score DESC LIMIT $limit
"""

_ARTWORK_RELATIONSHIPS = """
MATCH (artwork:Artwork) WHERE elementId(artwork) = $artwork_id
OPTIONAL MATCH (artwork)-[r]-(related)
WHERE r.valid_to IS NULL AND coalesce(related.is_deleted, false) = false
RETURN collect({rel: type(r), node: related}) AS relationships
"""


def _node_metadata(node) -> dict[str, Any]:
    """Neo4j 節點屬性轉成可序列化的 metadata。"""
    metadata: dict[str, Any] = {}
    for key, value in node.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            metadata[key] = value
        elif hasattr(value, "isoformat"):
            metadata[key] = value.isoformat()
        else:
            metadata[key] = str(value)
    return metadata


# 圖譜檢索修復方案 A（2026-10-13 老師核可上線）：anchor＝畫家錨點＋模板＋退回（預設）；
# legacy＝舊版關鍵詞模糊比對，僅作回滾（設計
# docs/designs/2026-10-11-graph-retrieval-anchor.md）
GRAPH_RETRIEVAL = os.getenv("GRAPH_RETRIEVAL", "anchor")
# 錨點查無時，非事實題（關係／理論）的退回路由（規格 Q2，2026-10-14 實驗開關）：
# 預設 fulltext（現行行為）；可設 vector 或 hybrid 比較理論題
GRAPH_FALLBACK_NONFACT = os.getenv("GRAPH_FALLBACK_NONFACT", "fulltext")
if GRAPH_FALLBACK_NONFACT not in ("fulltext", "vector", "hybrid"):
    raise ValueError(
        f"GRAPH_FALLBACK_NONFACT 只能是 fulltext／vector／hybrid：{GRAPH_FALLBACK_NONFACT}"
    )
_alias_table = None


def _graph_alias_table():
    global _alias_table
    if _alias_table is None:
        _alias_table = graph_anchor.AliasTable()
    return _alias_table


class SystemGraphRAG(GraphOnlyRAG):
    """系統圖譜路（RET-01 ``graph``）：只回傳 Artwork，讓 RRF 能以文件 id 與另外兩路對齊

    與舊 ``graph_only`` 的差異（2026-10-01，舊策略保留作對照組）：
    1. 先查作品標題，再由藝術家展開其作品；不回傳 Artist 節點本身（沒有文件 id）
    2. 不做模糊比對，多字詞以片語查詢，所有關鍵詞一次查詢
    3. 以相對分數門檻 ``GRAPH_MIN_RELATIVE_SCORE`` 濾掉弱命中
    """

    def __init__(self):
        RAGStrategy.__init__(self, "System Graph RAG", "作品標題＋藝術家展開作品的圖譜檢索")

    def _search_terms(self, query: str) -> list[str]:
        normalized = query
        if query_translator:
            try:
                normalized, _ = query_translator.translate_terms(query)
            except Exception as e:
                logger.warning(f"實體正規化失敗: {e}")
        if keyword_extractor:
            terms, _ = keyword_extractor.extract_keywords(
                normalized, max_keywords=5, min_word_length=3
            )
            if terms:
                return terms
        import re  # noqa: PLC0415 -- 僅關鍵詞抽取器不可用時的後備

        return re.findall(r"[a-zA-Z]{3,}", normalized) or [normalized]

    async def retrieve(
        self, query: str, max_results: int = 5, fallback: bool = True
    ) -> list[dict[str, Any]]:
        if not conn_manager.neo4j_driver:
            logger.warning("Neo4j 未連接，返回空結果")
            return []
        if GRAPH_RETRIEVAL == "anchor":
            return await self._anchor_retrieve(query, max_results, fallback)
        lucene = build_lucene_query(self._search_terms(query))
        if not lucene:
            return []

        try:
            with conn_manager.neo4j_driver.session() as session:
                # 作品保留原始 Record（.data() 會把節點轉成 dict，失去 element_id）
                titled = apply_relative_cutoff(
                    list(session.run(_ARTWORK_BY_TITLE, q=lucene, limit=max_results)),
                    GRAPH_MIN_RELATIVE_SCORE,
                )
                artists = apply_relative_cutoff(
                    session.run(_ARTIST_BY_NAME, q=lucene, limit=max_results).data(),
                    GRAPH_MIN_RELATIVE_SCORE,
                )
                by_artist = (
                    list(session.run(_ARTWORKS_OF_ARTISTS, artists=artists, limit=max_results))
                    if artists
                    else []
                )

                documents: list[dict[str, Any]] = []
                seen: set[str] = set()
                for row, via in [(r, "title") for r in titled] + [(r, "artist") for r in by_artist]:
                    artwork = row["artwork"]
                    key = artwork.get("id") or artwork.get("title")
                    if not key or key in seen:
                        continue
                    seen.add(key)
                    relationships = session.run(
                        _ARTWORK_RELATIONSHIPS, artwork_id=artwork.element_id
                    ).single()["relationships"]
                    metadata = _node_metadata(artwork)
                    metadata["graph_match"] = via
                    documents.append(
                        {
                            "content": self._format_graph_node(artwork, relationships),
                            "metadata": metadata,
                            "score": float(row["score"]),
                            "source": "Neo4j Knowledge Graph (Artwork)",
                        }
                    )
                    if len(documents) >= max_results:
                        break
        except Exception as e:
            logger.error(f"系統圖譜檢索失敗: {e}")
            return []

        logger.info(
            f"系統圖譜檢索返回 {len(documents)} 個結果"
            f"（標題命中 {len(titled)}、藝術家 {len(artists)} 位展開 {len(by_artist)} 件）"
        )
        return documents

    async def _anchor_retrieve(
        self, query: str, max_results: int, fallback: bool
    ) -> list[dict[str, Any]]:
        """方案 A：錨點（M2）→ 模板 T1／T2（M3）→ 查無或 0 列時依題型退回（M4）→ 日誌（M5）。"""
        original = graph_anchor.ORIGINAL_QUERY.get()
        anchor = _graph_alias_table().anchor(original, query)
        template, params = graph_anchor.choose_template(original, query)
        log = {
            "original": original,
            "retrieval_query": query,
            "anchors": anchor.matched,
            "artist_nodes": len(anchor.names),
            "template": template if anchor.hit else None,
            "params": params if anchor.hit else {},
        }
        records: list = []
        if anchor.hit:
            cypher = graph_anchor._T2 if template == "T2" else graph_anchor._T1
            try:
                with conn_manager.neo4j_driver.session() as session:
                    records = list(session.run(cypher, names=anchor.names, **params))
                    ranked = graph_anchor.rank_artworks(records, query, max_results)
                    documents = []
                    for score, row in ranked:
                        artwork = row["artwork"]
                        relationships = session.run(
                            _ARTWORK_RELATIONSHIPS, artwork_id=artwork.element_id
                        ).single()["relationships"]
                        metadata = _node_metadata(artwork)
                        metadata["graph_match"] = f"anchor:{template}"
                        documents.append(
                            {
                                "content": self._format_graph_node(artwork, relationships),
                                "metadata": metadata,
                                "score": float(score),
                                "source": "Neo4j Knowledge Graph (Artwork)",
                            }
                        )
            except Exception as e:
                logger.error(f"錨點圖譜檢索失敗: {e}")
                records, documents = [], []
            log["rows"] = len(records)
            if documents:
                log.update(fallback=None, returned=[d["metadata"].get("id") for d in documents])
                graph_anchor.write_log(log)
                return documents
        else:
            log["rows"] = 0
        route = (
            "vector" if graph_anchor.question_type(original) == "fact" else GRAPH_FALLBACK_NONFACT
        )
        if not fallback:  # 呼叫端自行處理（三路融合已含 vector／fulltext；舊策略走原流程）
            log.update(fallback="none(caller)", returned=[])
            graph_anchor.write_log(log)
            return []
        # hybrid 內部呼叫 graph 時帶 fallback=False，不會遞迴
        documents = await RAG_STRATEGIES[route].retrieve(query, max_results)
        for d in documents:
            d.setdefault("metadata", {})["graph_fallback"] = route
        log.update(
            fallback=route,
            reason="abstain" if not anchor.hit else "zero_rows",
            returned=[(d.get("metadata") or {}).get("id") for d in documents],
        )
        graph_anchor.write_log(log)
        return documents


class AdvancedGraphRAG(RAGStrategy):
    """Advanced Graph RAG - 查詢改寫(術語正規化) + 多跳圖檢索(2-hop) + 子圖重排序"""

    # 作品節點可能延伸出去的關係類型（12類分類體系裡的風格/材質/技法/產地/機構/主題/概念）
    EXTENDED_REL_TYPES = [
        "BELONGS_TO_STYLE",
        "USES_MATERIAL",
        "USES_TECHNIQUE",
        "FROM_PLACE",
        "HELD_BY",
        "DEPICTS_THEME",
        "MENTIONS_CONCEPT",
    ]

    def __init__(self):
        super().__init__("Advanced Graph RAG", "查詢改寫、多跳圖檢索(2-hop)與子圖重排序")

    async def retrieve(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        if not conn_manager.neo4j_driver:
            logger.warning("Neo4j 未連接，返回空結果")
            return []

        # 1. 查詢改寫/實體正規化：用術語詞典把別名/多語言詞轉成圖譜裡的正規英文詞
        normalized_query = query
        if query_translator:
            try:
                normalized_query, found_terms = query_translator.translate_terms(query)
                if found_terms:
                    logger.info(f"🔤 實體正規化: '{query}' -> '{normalized_query}' ({found_terms})")
            except Exception as e:
                logger.warning(f"實體正規化失敗: {e}")

        # 2. 抽取關鍵詞
        if keyword_extractor:
            search_terms, _ = keyword_extractor.extract_keywords(
                normalized_query, max_keywords=5, min_word_length=3
            )
            if not search_terms:
                search_terms = [normalized_query]
        else:
            search_terms = [normalized_query]

        logger.info(f"🔍 Advanced Graph RAG 搜索關鍵詞: {search_terms}")

        candidates: list[dict[str, Any]] = []
        try:
            with conn_manager.neo4j_driver.session() as session:
                for term in search_terms:
                    fuzzy_term = f"{term}~" if len(term) >= 4 else term

                    # 2-hop: Artist -[:CREATED]-> Artwork -[延伸關係]-> 相關實體
                    # (Style/Material/Place/...)
                    artist_query = """
                    CALL db.index.fulltext.queryNodes('artist_name_fulltext', $search_term)
                    YIELD node AS artist, score
                    WITH artist, score LIMIT $limit
                    OPTIONAL MATCH (artist)-[c:CREATED]->(artwork:Artwork)
                    WHERE c.valid_to IS NULL AND coalesce(artwork.is_deleted, false) = false
                    WITH artist, score, collect(DISTINCT artwork) as artworks
                    UNWIND (CASE WHEN size(artworks) = 0 THEN [null] ELSE artworks END) as aw
                    OPTIONAL MATCH (aw)-[r2]->(ext)
                    WHERE aw IS NULL OR (type(r2) IN $ext_types AND r2.valid_to IS NULL)
                    RETURN artist AS n, score, 'Artist' as node_type,
                           collect(DISTINCT CASE WHEN aw IS NOT NULL
                               THEN {rel: 'CREATED', node: aw} END) as hop1,
                           collect(DISTINCT CASE WHEN ext IS NOT NULL
                               THEN {rel: type(r2), node: ext} END) as hop2
                    """
                    result = session.run(
                        artist_query,
                        search_term=fuzzy_term,
                        limit=max_results,
                        ext_types=self.EXTENDED_REL_TYPES,
                    )
                    for record in result:
                        candidates.append(self._build_candidate(record, "Artist"))

                    # 同樣針對作品標題全文索引做 2-hop
                    # （作品 -> 延伸關係 -> 相關實體，以及作品 <- 藝術家）
                    artwork_query = """
                    CALL db.index.fulltext.queryNodes('artwork_title_fulltext', $search_term)
                    YIELD node AS artwork, score
                    WHERE coalesce(artwork.is_deleted, false) = false
                    WITH artwork, score LIMIT $limit
                    OPTIONAL MATCH (artist:Artist)-[c:CREATED]->(artwork)
                    WHERE c.valid_to IS NULL
                    OPTIONAL MATCH (artwork)-[r2]->(ext)
                    WHERE r2 IS NULL OR (type(r2) IN $ext_types AND r2.valid_to IS NULL)
                    RETURN artwork AS n, score, 'Artwork' as node_type,
                           collect(DISTINCT CASE WHEN artist IS NOT NULL
                               THEN {rel: 'CREATED_BY', node: artist} END) as hop1,
                           collect(DISTINCT CASE WHEN ext IS NOT NULL
                               THEN {rel: type(r2), node: ext} END) as hop2
                    """
                    result2 = session.run(
                        artwork_query,
                        search_term=fuzzy_term,
                        limit=max_results,
                        ext_types=self.EXTENDED_REL_TYPES,
                    )
                    for record in result2:
                        candidates.append(self._build_candidate(record, "Artwork"))
        except Exception as e:
            logger.error(f"Advanced Graph RAG 檢索失敗: {e}")
            return []

        # 3. 子圖重排序：分數 = 全文分數 + 2-hop擴展豐富度加成，並依名稱去重
        ranked = self._rerank(candidates, max_results)
        logger.info(f"Advanced Graph RAG 檢索返回 {len(ranked)} 個結果")
        return ranked

    def _build_candidate(self, record, node_type: str) -> dict[str, Any]:
        node = record["n"]
        hop1 = [h for h in record["hop1"] if h and h.get("node") is not None]
        hop2 = [h for h in record["hop2"] if h and h.get("node") is not None]
        name = node.get("title") or node.get("name", "未知")

        content_lines = [f"實體: {name} ({node_type})"]
        if hop1:
            content_lines.append("一跳關係:")
            for h in hop1[:5]:
                related = h["node"]
                related_name = (
                    (related.get("title") or related.get("name", "未知"))
                    if hasattr(related, "get")
                    else str(related)
                )
                content_lines.append(f"  - {h['rel']} -> {related_name}")
        if hop2:
            content_lines.append("二跳擴展(風格/材質/技法/產地/機構/主題/概念):")
            for h in hop2[:8]:
                related = h["node"]
                related_name = (
                    (related.get("name") or related.get("title", "未知"))
                    if hasattr(related, "get")
                    else str(related)
                )
                content_lines.append(f"  - {h['rel']} -> {related_name}")

        return {
            "content": "\n".join(content_lines),
            "metadata": {"name": name, "node_type": node_type},
            "score": float(record["score"]),
            "hop2_richness": len(hop2),
            "source": f"Neo4j Knowledge Graph 2-hop ({node_type})",
        }

    def _rerank(self, candidates: list[dict[str, Any]], max_results: int) -> list[dict[str, Any]]:
        seen = set()
        deduped = []
        for c in candidates:
            key = c["metadata"].get("name")
            if key and key not in seen:
                seen.add(key)
                deduped.append(c)
        # 綜合分數：全文分數 + 2-hop 擴展豐富度加成（每個延伸關係 +0.3 分，最多加3分）
        for c in deduped:
            c["combined_score"] = c["score"] + min(c.get("hop2_richness", 0) * 0.3, 3.0)
        deduped.sort(key=lambda x: x["combined_score"], reverse=True)
        return deduped[:max_results]


class AgenticGraphRAG(RAGStrategy):
    """Agentic Graph RAG - LLM 規劃檢索策略、多輪自我評估、動態調整檢索方向的圖譜檢索"""

    def __init__(self, max_iterations: int = 3, planner_model: str = "qwen3:8b"):
        super().__init__("Agentic Graph RAG", "LLM規劃查詢策略、多輪自我評估、動態調整檢索方向")
        self.max_iterations = max_iterations
        self.planner_model = planner_model
        self._advanced_graph_rag = AdvancedGraphRAG()

    async def retrieve(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        if not conn_manager.neo4j_driver:
            logger.warning("Neo4j 未連接，返回空結果")
            return []

        reasoning_trace: list[str] = []
        collected: list[dict[str, Any]] = []
        seen_names = set()
        current_focus = query

        for i in range(self.max_iterations):
            search_terms = await self._plan_search_terms(query, current_focus, reasoning_trace)
            round_docs: list[dict[str, Any]] = []
            for term in search_terms:
                docs = await self._advanced_graph_rag.retrieve(term, max_results)
                round_docs.extend(docs)

            new_docs = [d for d in round_docs if d["metadata"].get("name") not in seen_names]
            for d in new_docs:
                seen_names.add(d["metadata"].get("name"))
            collected.extend(new_docs)

            sufficient, assessment = await self._assess_sufficiency(query, collected)
            reasoning_trace.append(
                f"第{i + 1}輪：搜尋詞={search_terms} → "
                f"新增{len(new_docs)}筆（累計{len(collected)}筆）→ "
                f"{'足夠' if sufficient else '不足夠'}：{assessment}"
            )

            if sufficient or not new_docs:
                break
            current_focus = assessment

        trace_doc = {
            "content": "\n".join(reasoning_trace),
            "metadata": {"name": "Agent 推理路徑"},
            "score": 0.0,
            "source": "Agentic Graph RAG (推理過程)",
        }

        ranked = sorted(
            collected, key=lambda x: x.get("combined_score", x.get("score", 0)), reverse=True
        )[:max_results]
        logger.info(
            f"Agentic Graph RAG 完成 {len(reasoning_trace)} 輪迭代，返回 {len(ranked)} 個結果"
        )
        return ranked + [trace_doc]

    async def _call_llm(self, prompt: str) -> str | None:
        try:
            response = await conn_manager.http_client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": self.planner_model,
                    "prompt": prompt,
                    "stream": False,
                    # 規劃步驟不需要思考鏈：產出本來就該很短（關鍵詞列表或一句話評估），
                    # 對支援 think 的模型一律關閉；不支援的模型會靜默忽略此鍵
                    "think": False,
                    # 同上，temperature/num_predict 要放進 options 才會生效
                    "options": {"temperature": 0.1, "num_predict": 300},
                },
                timeout=120.0,
            )
            if response.status_code == 200:
                return response.json().get("response", "").strip()
        except Exception as e:
            logger.warning(f"Agent 呼叫 LLM 失敗: {e}")
        return None

    async def _plan_search_terms(
        self, original_query: str, current_focus: str, history: list[str]
    ) -> list[str]:
        import re

        history_text = "\n".join(history) if history else "（第一輪，尚無歷史）"
        prompt = f"""你是一個知識圖譜檢索規劃助手。原始問題：「{original_query}」
目前檢索焦點：「{current_focus}」
先前檢索歷史：
{history_text}

請列出 1-3 個最適合拿去查詢知識圖譜的關鍵詞（人名、作品名、風格、地點等專有名詞），
用逗號分隔，不要任何說明文字，直接輸出關鍵詞列表。"""
        text = await self._call_llm(prompt)
        if text:
            terms = [t.strip() for t in re.split(r"[,，、\n]", text) if t.strip()]
            if terms:
                return terms[:3]
        return [original_query]

    async def _assess_sufficiency(self, query: str, collected: list[dict[str, Any]]):
        if not collected:
            return False, "尚未檢索到任何資料"
        summary = "\n".join(f"- {d['metadata'].get('name', '未知')}" for d in collected[:10])
        prompt = f"""使用者問題：「{query}」
目前已檢索到的實體：
{summary}

這些資料是否足夠回答使用者的問題？只回答「足夠」或「不足夠：<還缺什麼，用一句話簡短說明，做為下一輪搜尋方向>」"""
        text = await self._call_llm(prompt)
        if text:
            if text.startswith("足夠"):
                return True, text
            return False, text
        return True, "評估失敗，預設視為足夠以避免無限迴圈"


class HybridBalancedRAG(RAGStrategy):
    """混合平衡 RAG - 結合向量和圖譜"""

    def __init__(self):
        super().__init__("Hybrid Balanced RAG", "平衡使用向量檢索和圖譜推理")
        self.vector_rag = VectorOnlyRAG()
        self.graph_rag = GraphOnlyRAG()

    async def retrieve(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """混合檢索"""
        # 從兩種策略各取一半
        vector_limit = max_results // 2
        graph_limit = max_results - vector_limit

        # 並行檢索
        vector_docs = await self.vector_rag.retrieve(query, vector_limit)
        graph_docs = await self.graph_rag.retrieve(query, graph_limit)

        # 合並結果
        all_docs = vector_docs + graph_docs

        logger.info(
            f"混合檢索返回 {len(all_docs)} 個結果"
            f"（向量: {len(vector_docs)}, 圖譜: {len(graph_docs)}）"
        )
        return all_docs


class AdvancedRAG(RAGStrategy):
    """高級 RAG - 多級檢索和重排序"""

    def __init__(self):
        super().__init__("Advanced RAG", "多級檢索、結果融合和重排序")
        self.vector_rag = VectorOnlyRAG()
        self.graph_rag = GraphOnlyRAG()

    async def retrieve(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """高級檢索流程"""
        # 第一階段：廣泛檢索
        vector_docs = await self.vector_rag.retrieve(query, max_results * 2)
        graph_docs = await self.graph_rag.retrieve(query, max_results * 2)

        # 第二階段：結果融合和去重
        all_docs = self._merge_and_deduplicate(vector_docs, graph_docs)

        # 第三階段：重排序（基於分數和多樣性）
        ranked_docs = self._rerank(all_docs, query, max_results)

        logger.info(f"高級檢索返回 {len(ranked_docs)} 個結果")
        return ranked_docs

    def _merge_and_deduplicate(self, docs1: list[dict], docs2: list[dict]) -> list[dict]:
        """合並和去重"""
        # 簡單的基於內容的去重
        seen_content = set()
        merged = []

        for doc in docs1 + docs2:
            content_hash = hash(doc["content"][:100])  # 使用前100字符作為特徵
            if content_hash not in seen_content:
                seen_content.add(content_hash)
                merged.append(doc)

        return merged

    def _rerank(self, docs: list[dict], query: str, max_results: int) -> list[dict]:
        """重排序文檔"""
        # 基於分數排序
        sorted_docs = sorted(docs, key=lambda x: x.get("score", 0), reverse=True)
        return sorted_docs[:max_results]


class AgenticRAG(RAGStrategy):
    """智能代理 RAG - 使用代理進行多步推理"""

    def __init__(self):
        super().__init__("Agentic RAG", "使用智能代理進行多步驟推理和檢索")
        self.hybrid_rag = HybridBalancedRAG()

    async def retrieve(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """代理式檢索"""
        # 第一步：分析查詢意圖
        intent = self._analyze_intent(query)

        # 第二步：根據意圖選擇檢索策略
        if intent == "relationship":
            # 關係類查詢，優先使用圖譜
            return await GraphOnlyRAG().retrieve(query, max_results)
        elif intent == "semantic":
            # 語義類查詢，優先使用向量
            return await VectorOnlyRAG().retrieve(query, max_results)
        else:
            # 混合查詢
            return await self.hybrid_rag.retrieve(query, max_results)

    def _analyze_intent(self, query: str) -> str:
        """分析查詢意圖（簡化版）"""
        # 關係關鍵詞
        relationship_keywords = ["關係", "影響", "比較", "差異", "聯繫", "之間"]
        # 語義關鍵詞
        semantic_keywords = ["是什麼", "特點", "描述", "介紹", "說明"]

        query_lower = query.lower()

        if any(kw in query_lower for kw in relationship_keywords):
            return "relationship"
        elif any(kw in query_lower for kw in semantic_keywords):
            return "semantic"
        else:
            return "hybrid"


class SelfRAG(RAGStrategy):
    """自我反思 RAG - 包含自我評估和迭代改進"""

    def __init__(self):
        super().__init__("Self RAG", "自我反思和迭代改進的 RAG")
        self.advanced_rag = AdvancedRAG()

    async def retrieve(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """自我反思式檢索"""
        # 第一次檢索
        docs = await self.advanced_rag.retrieve(query, max_results)

        # 自我評估：檢查結果質量
        quality_score = self._assess_quality(docs, query)

        # 如果質量不足，進行第二次檢索（使用改寫的查詢）
        if quality_score < 0.6:
            logger.info(f"首次檢索質量不足 ({quality_score:.2f})，進行查詢改寫")
            refined_query = self._refine_query(query)
            docs = await self.advanced_rag.retrieve(refined_query, max_results)

        return docs

    def _assess_quality(self, docs: list[dict], query: str) -> float:
        """評估檢索結果質量（簡化版）"""
        if not docs:
            return 0.0

        # 基於文檔數量和平均分數
        avg_score = sum(doc.get("score", 0) for doc in docs) / len(docs)
        coverage = min(len(docs) / 5, 1.0)  # 期望至少5個結果

        return (avg_score + coverage) / 2

    def _refine_query(self, query: str) -> str:
        """改寫查詢（簡化版）"""
        # 實際應用中可以使用 LLM 進行查詢改寫
        return f"{query} 藝術史 相關資料"


class NaiveRAG(RAGStrategy):
    """Naive RAG - 基礎的檢索增強生成，最簡單直接的方法"""

    def __init__(self):
        super().__init__("Naive RAG", "最簡單的檢索+生成方法")
        self.vector_rag = VectorOnlyRAG()

    async def retrieve(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """基礎檢索 - 僅使用向量檢索"""
        # Naive RAG 通常只使用最基礎的向量檢索，不進行任何優化
        docs = await self.vector_rag.retrieve(query, max_results)

        logger.info(f"Naive RAG 檢索返回 {len(docs)} 個結果")
        return docs


# RAG 策略註冊表
_graph_only_strategy = GraphOnlyRAG()
_vector_strategy = VectorOnlyRAG()

# 系統級三路檢索（RET-01）：與下方舊策略並存，舊 id 待黃金集基準比較後再另行移除
# （2026-10-01 使用者選定方案 A，見 docs/decision-log.md）
_SYSTEM_ROUTES: dict[str, RAGStrategy] = {
    "vector": _vector_strategy,
    "fulltext": FulltextESRAG(),
    "graph": SystemGraphRAG(),
}

RAG_STRATEGIES = {
    **_SYSTEM_ROUTES,
    "hybrid": SystemHybridRAG(_SYSTEM_ROUTES),
    "vector_only": VectorOnlyRAG(),
    "hybrid_es_rag": HybridESRAG(),
    "graph_only": _graph_only_strategy,
    "hybrid_balanced": HybridBalancedRAG(),
    "advanced_rag": AdvancedRAG(),
    "agentic_rag": AgenticRAG(),
    "self_rag": SelfRAG(),
    "naive_rag": NaiveRAG(),
    # naive_graph_rag 直接沿用 graph_only 同一個實例：NaiveGraphRAG 原本只是
    # 呼叫 GraphOnlyRAG().retrieve() 不加任何邏輯，是重複的空殼類別，已移除
    "naive_graph_rag": _graph_only_strategy,
    "advanced_graph_rag": AdvancedGraphRAG(),
    "agentic_graph_rag": AgenticGraphRAG(),
}

# ==================== API 端點 ====================


@app.on_event("startup")
async def startup_event():
    """應用啟動時初始化連接"""
    global query_translator, keyword_extractor, query_cache

    logger.info("🚀 RAG 管理器服務 V2 啟動中...")
    await conn_manager.initialize()

    # 初始化多語言翻譯器
    try:
        query_translator = MultilingualQueryTranslator()
        logger.info("✅ 多語言查詢翻譯器已初始化")
        if QUERY_TRANSLATION == "llm_hinted":
            _schedule_translation_warmup()
    except Exception as e:
        logger.warning(f"⚠️ 多語言翻譯器初始化失敗: {e}，將繼續使用原始查詢")
        query_translator = None

    # 初始化智能關鍵詞提取器
    try:
        # 查詢日誌含使用者提問原文，與 biz 紀錄同受 BIZ_LOGGING 管制（規格 BIZ-03，預設關閉）
        keyword_extractor = SmartKeywordExtractor(
            translator=query_translator, log_queries=BIZ_LOGGING
        )
        logger.info("✅ 智能關鍵詞提取器已初始化")
    except Exception as e:
        logger.warning(f"⚠️ 關鍵詞提取器初始化失敗: {e}，將使用基礎提取")
        keyword_extractor = None

    # 初始化查詢緩存：預設 Redis（RET-11，決策 B10 一般鍵值快取）；連不上時退回程序內快取
    cache_size = int(os.getenv("QUERY_CACHE_SIZE", "1000"))
    cache_ttl = int(os.getenv("QUERY_CACHE_TTL", "3600"))
    query_cache = None
    if CACHE_BACKEND == "redis":
        try:
            client = connect_redis(RAG_CACHE_REDIS_URL, os.getenv("REDIS_PASSWORD"))
            query_cache = RedisQueryCache(client, ttl_seconds=cache_ttl)
            logger.info(f"✅ 查詢緩存：Redis {RAG_CACHE_REDIS_URL}（TTL: {cache_ttl}秒）")
        except Exception as e:
            logger.warning(f"⚠️ Redis 快取無法使用（{e}），退回程序內快取")
    if query_cache is None:
        try:
            query_cache = QueryCache(max_size=cache_size, ttl_seconds=cache_ttl)
            logger.info(f"✅ 查詢緩存：程序內 (大小: {cache_size}, TTL: {cache_ttl}秒)")
        except Exception as e:
            logger.warning(f"⚠️ 查詢緩存初始化失敗: {e}")
            query_cache = None

    logger.info("✅ RAG 管理器服務已就緒")


@app.on_event("shutdown")
async def shutdown_event():
    """應用關閉時清理連接"""
    logger.info("🛑 RAG 管理器服務關閉中...")
    await conn_manager.close()
    logger.info("✅ RAG 管理器服務已關閉")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康檢查端點"""
    services = conn_manager.get_health_status()

    # 檢查 Ollama
    try:
        response = await conn_manager.http_client.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)
        services["ollama"] = response.status_code == 200
    except Exception as e:
        logger.debug(f"Ollama 健康檢查失敗: {e}")
        services["ollama"] = False

    # 判斷整體狀態
    all_healthy = all(services.values())
    status = "healthy" if all_healthy else "degraded"

    return HealthResponse(status=status, services=services, timestamp=datetime.now().isoformat())


@app.get("/api/v1/models")
async def list_models():
    """列出所有可用的模型組合"""
    return {
        "models": RAG_CONFIG.get("model_combinations", []),
        "total": len(RAG_CONFIG.get("model_combinations", [])),
    }


@app.get("/api/v1/strategies")
async def list_strategies():
    """列出所有可用的 RAG 策略"""
    strategies = []
    for strategy_id, strategy_config in RAG_CONFIG.get("rag_strategies", {}).items():
        strategies.append(
            {
                "id": strategy_id,
                "name": strategy_config.get("name"),
                "display_name": strategy_config.get("display_name"),
                "description": strategy_config.get("description"),
                "emoji": strategy_config.get("emoji"),
            }
        )
    return {"strategies": strategies, "total": len(strategies)}


@app.get("/api/v1/cache/stats")
async def get_cache_stats():
    """獲取緩存統計信息"""
    if query_cache:
        return query_cache.get_stats()
    else:
        return {"error": "Cache not enabled", "enabled": False}


@app.post("/api/v1/cache/clear")
async def clear_cache():
    """清空緩存"""
    if query_cache:
        query_cache.clear()
        return {"success": True, "message": "Cache cleared successfully"}
    else:
        return {"success": False, "message": "Cache not enabled"}


def _read_open_alerts() -> list[dict[str, Any]]:
    from ingest.alerts import open_alerts  # noqa: PLC0415 -- 延遲載入，DB 問題不影響服務啟動
    from ingest.db import connect  # noqa: PLC0415

    with connect() as conn:
        alerts = open_alerts(conn)
    for alert in alerts:
        alert["delta_pct"] = float(alert["delta_pct"])
    return alerts


@app.get("/api/v1/eval/alerts")
async def list_open_alerts():
    """未處理告警（規格 EVL-12、API §11 ``/eval/alerts``），critical 在前"""
    try:
        alerts = await asyncio.to_thread(_read_open_alerts)
    except Exception as e:
        logger.error(f"讀取告警失敗: {e}")
        raise HTTPException(status_code=503, detail="無法讀取 eval.alerts") from e
    return {"alerts": alerts, "total": len(alerts)}


def _route_for_source_filter(
    rag_strategy: str, strategy: RAGStrategy, source_filter: str | None
) -> tuple[str, RAGStrategy]:
    """只有向量策略支援 source_filter；帶了過濾條件就改走 vector，避免條件被默默忽略。"""
    if source_filter and not isinstance(strategy, VectorOnlyRAG):
        logger.info(f"source_filter={source_filter}：策略 {rag_strategy} 不支援，改走 vector")
        return "vector", RAG_STRATEGIES["vector"]
    return rag_strategy, strategy


def _translation_model(llm_model: str | None) -> str:
    """翻譯用的模型：same 時用生成模型（未知模型改用預設），否則用設定值。"""
    if QUERY_TRANSLATION_MODEL != "same":
        return QUERY_TRANSLATION_MODEL
    known = RAG_CONFIG.get("llm_models", {})
    return llm_model if llm_model in known else QUERY_TRANSLATION_DEFAULT_MODEL


async def _warm_translation_model(model: str | None = None) -> None:
    """請 Ollama 載入翻譯模型並常駐（不生成內容）；失敗只記 log。"""
    model = _translation_model(model)
    try:
        await conn_manager.http_client.post(
            f"{QUERY_TRANSLATION_OLLAMA_URL or OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model,
                "keep_alive": QUERY_TRANSLATION_KEEP_ALIVE,
                # 預熱須與翻譯請求同一 num_gpu，否則先載進 GPU、翻譯時又以 CPU 重新載入
                **(
                    {"options": {"num_gpu": QUERY_TRANSLATION_NUM_GPU}}
                    if QUERY_TRANSLATION_NUM_GPU is not None
                    else {}
                ),
            },
            timeout=120.0,
        )
        logger.info(f"✅ 翻譯模型 {model} 已預熱")
    except Exception as e:
        logger.warning(f"⚠️ 翻譯模型預熱失敗: {e!r}")


def _schedule_translation_warmup(model: str | None = None) -> None:
    task = asyncio.create_task(_warm_translation_model(model))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def translate_for_retrieval(
    query: str, llm_model: str | None = None
) -> tuple[str, dict[str, Any] | None]:
    """產生檢索用查詢；英文問題原樣使用。

    Returns:
        (檢索用查詢, 翻譯資訊)；未翻譯時資訊為 None。``llm_hinted`` 模式下 LLM 失敗或逾時
        退回詞典結果（method=fallback），不影響回答。
    """
    if not query_translator:
        return query, None
    model = _translation_model(llm_model)
    if (model, query) in _translation_cache:
        return _translation_cache[(model, query)]
    start = time.monotonic()
    result = query_translator.translate_query(query)
    if result["detected_language"] == "en":
        return query, None
    dictionary_query = result["translated_query"] if result["found_terms"] else query
    info: dict[str, Any] = {
        "original_query": query,
        "detected_language": result["detected_language"],
        "found_terms": result["found_terms"],
    }
    retrieval_query, method = dictionary_query, "dictionary"
    if QUERY_TRANSLATION == "llm_hinted":
        hint = (
            "已知術語對照（請採用）：" + "；".join(result["found_terms"]) + "\n"
            if result["found_terms"]
            else ""
        )
        try:
            response = await conn_manager.http_client.post(
                f"{QUERY_TRANSLATION_OLLAMA_URL or OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": QUERY_TRANSLATION_PROMPT.format(hint=hint, query=query[:500]),
                    "stream": False,
                    "think": False,
                    # 會先思考的模型（deepseek-r1）思考也算在長度內，300 會被截斷
                    "options": {
                        "temperature": 0,
                        "num_predict": QUERY_TRANSLATION_NUM_PREDICT,
                        **(
                            {"repeat_penalty": QUERY_TRANSLATION_REPEAT_PENALTY}
                            if QUERY_TRANSLATION_REPEAT_PENALTY is not None
                            else {}
                        ),
                        **(
                            {"num_gpu": QUERY_TRANSLATION_NUM_GPU}
                            if QUERY_TRANSLATION_NUM_GPU is not None
                            else {}
                        ),
                    },
                    "keep_alive": QUERY_TRANSLATION_KEEP_ALIVE,
                },
                timeout=QUERY_TRANSLATION_TIMEOUT_SEC,
            )
            response.raise_for_status()
            text = _clean_translation(response.json().get("response", ""))
            if text:
                retrieval_query, method = text, "llm_hinted"
            else:
                method = "fallback"
        except Exception as e:
            logger.warning(f"⚠️ LLM 查詢翻譯失敗，退回詞典: {e!r}")
            method = "fallback"
            _schedule_translation_warmup(model)  # 多半是冷啟動：背景載入模型，下一題就能用
    info.update(
        retrieval_query=retrieval_query,
        method=method,
        model=model,
        ms=round((time.monotonic() - start) * 1000, 1),
    )
    if method != "fallback":  # 暫時性失敗不快取，下次再試 LLM
        if len(_translation_cache) >= _TRANSLATION_CACHE_MAX:
            _translation_cache.pop(next(iter(_translation_cache)))
        _translation_cache[(model, query)] = (retrieval_query, info)
    return retrieval_query, info


@app.post("/api/v1/retrieve")
async def process_retrieve_only(request: QueryRequest):
    """僅檢索、不生成答案 —— 用於事後回填評測用的原文片段（Faithfulness 計算）"""
    rag_strategy = request.model_combination_id.split("@")[-1]
    if "@" not in request.model_combination_id and rag_strategy not in RAG_STRATEGIES:
        rag_strategy = DEFAULT_STRATEGY  # 只給模型名稱時採預設策略（RET-02）
    strategy = RAG_STRATEGIES.get(rag_strategy)
    if not strategy:
        raise HTTPException(status_code=404, detail=f"未找到 RAG 策略: {rag_strategy}")
    rag_strategy, strategy = _route_for_source_filter(rag_strategy, strategy, request.source_filter)

    graph_anchor.ORIGINAL_QUERY.set(request.query)  # 圖譜錨點比對中文別名用
    try:
        query_text, _ = await translate_for_retrieval(
            request.query, request.model_combination_id.split("@")[0]
        )
    except Exception as e:
        logger.warning(f"⚠️ 查詢翻譯失敗: {e}，使用原始查詢")
        query_text = request.query

    fetch = request.max_results + (_EXCLUDE_MARGIN if EXCLUDE_EVIDENCE_PREFIXES else 0)
    if isinstance(strategy, VectorOnlyRAG):
        sources = await strategy.retrieve(query_text, fetch, source_filter=request.source_filter)
    else:
        sources = await strategy.retrieve(query_text, fetch)
    sources = _evidence_only(sources, request.max_results)

    return {"sources": sources, "citations": build_citations(sources)}


async def _run_coarse_guard(
    answer: str, sources: list[dict[str, Any]]
) -> tuple[str, CoarseResult | None, float]:
    """執行同步粗篩，回傳 (gate_status, 結果, 耗時 ms)。

    gate_status 為 ok／hang／crash（GRD-06c／06d）。
    """
    start = time.monotonic()
    texts = [str(doc.get("content", "")) for doc in sources]
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(check_answer, answer, texts), timeout=GUARD_HARD_TIMEOUT_SEC
        )
        status = "ok"
    except TimeoutError:
        logger.error(f"粗篩逾 {GUARD_HARD_TIMEOUT_SEC} 秒未完成（gate_hang）")
        result, status = None, "hang"
    except Exception as e:
        logger.error(f"粗篩失敗（gate_crash）: {e}")
        result, status = None, "crash"
    return status, result, (time.monotonic() - start) * 1000


def _write_guard_shadow(row: dict[str, Any]) -> None:
    """寫入 eval.guard_shadow；失敗只記 log，不影響已送出的回答。"""
    try:
        from guard_store import (
            record_guard_shadow,  # noqa: PLC0415 -- 延遲載入，DB 問題不影響服務啟動
        )
        from ingest.db import connect  # noqa: PLC0415

        with connect() as conn:
            record_guard_shadow(conn, row)
    except Exception as e:
        logger.error(f"影子紀錄寫入失敗: {e}")


# 背景寫入工作的參照，避免 task 被回收
_background_tasks: set[asyncio.Task] = set()


# 生成模型並行預載（串流設計 docs/designs/2026-10-14-streaming-response.md §3.4）：收到請求即請
# GPU Ollama 載入生成模型，與翻譯、檢索同時進行，換載模型時省 1.5～2 秒。預設關閉
GENERATION_PRELOAD = os.getenv("GENERATION_PRELOAD", "0") == "1"


# 換模型時主動卸載（使用者 2026-10-15）：收到請求即查 GPU Ollama 已載入的模型，
# 與本次不同者先卸載（keep_alive=0），再載入本次模型；與翻譯、檢索並行，新模型可完整放進 GPU。
# 只作用於 GPU Ollama（OLLAMA_BASE_URL）。進行中請求是否受影響見 E20 實測。預設關閉
GENERATION_SWITCH_UNLOAD = os.getenv("GENERATION_SWITCH_UNLOAD", "0") == "1"
_switch_lock = asyncio.Lock()


async def _switch_generation_model(model: str) -> None:
    """卸載 GPU Ollama 上其他生成模型，再載入 model；失敗只記 log。"""
    async with _switch_lock:  # 同時多個請求換模型時依序處理，避免互相卸載
        try:
            ps = await conn_manager.http_client.get(f"{OLLAMA_BASE_URL}/api/ps", timeout=5.0)
            loaded = [m.get("name") for m in ps.json().get("models", [])]
            for other in loaded:
                if other and other != model:
                    await conn_manager.http_client.post(
                        f"{OLLAMA_BASE_URL}/api/generate",
                        json={"model": other, "keep_alive": 0},
                        timeout=60.0,
                    )
                    logger.info(f"🔁 換模型：卸載 {other} → 載入 {model}")
        except Exception as e:
            logger.warning(f"⚠️ 卸載其他生成模型失敗: {e!r}")
    await _preload_generation_model(model)


async def _preload_generation_model(model: str) -> None:
    """只載入模型、不生成；失敗只記 log（生成時 Ollama 仍會自行載入）。"""
    try:
        await conn_manager.http_client.post(
            f"{OLLAMA_BASE_URL}/api/generate", json={"model": model}, timeout=120.0
        )
    except Exception as e:
        logger.warning(f"⚠️ 生成模型預載失敗: {e!r}")


# K（檢索信心）評分器（規格 Q9；2026-10-14 試做，預設關閉）：開啟時只把 K 記入 metadata，不改回答
K_SCORER = os.getenv("K_SCORER", "0") == "1"


@dataclass
class _QueryContext:
    """/query 與 /query/stream 共用的生成前狀態。"""

    request: QueryRequest
    start_time: datetime
    llm_model: str
    rag_strategy: str
    strategy: "RAGStrategy"
    translation_info: dict[str, Any] | None
    sources: list[dict[str, Any]]
    cache_hit: bool
    retrieval_time: float
    temperature: float
    max_tokens: int
    answer_cache_key: str
    k_info: dict[str, Any] | None = None


async def _prepare_query(request: QueryRequest) -> _QueryContext:
    """解析模型組合、翻譯、檢索（含快取）、決定生成參數與答案快取鍵。"""
    start_time = datetime.now()

    # 解析模型組合 ID；只給模型名稱（不帶 @策略）時採預設策略（RET-02）
    if "@" not in request.model_combination_id:
        request.model_combination_id = f"{request.model_combination_id}@{DEFAULT_STRATEGY}"
    try:
        llm_model, rag_strategy = request.model_combination_id.split("@")
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=(
                f"無效的模型組合 ID: {request.model_combination_id}，"
                f"格式應為 'llm_model@rag_strategy'"
            ),
        ) from e

    # 獲取 RAG 策略
    strategy = RAG_STRATEGIES.get(rag_strategy)
    if not strategy:
        raise HTTPException(status_code=404, detail=f"未找到 RAG 策略: {rag_strategy}")
    rag_strategy, strategy = _route_for_source_filter(rag_strategy, strategy, request.source_filter)

    if GENERATION_SWITCH_UNLOAD or GENERATION_PRELOAD:
        job = _switch_generation_model if GENERATION_SWITCH_UNLOAD else _preload_generation_model
        task = asyncio.create_task(job(llm_model))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    graph_anchor.ORIGINAL_QUERY.set(request.query)  # 圖譜錨點比對中文別名用
    # 多語言查詢翻譯：llm_hinted 只把譯文用於檢索，生成仍用原問題；dictionary 維持原行為
    # （譯文同時用於檢索與生成）
    try:
        retrieval_query, translation_info = await translate_for_retrieval(request.query, llm_model)
    except Exception as e:
        logger.warning(f"⚠️ 查詢翻譯失敗: {e}，使用原始查詢")
        retrieval_query, translation_info = request.query, None
    if translation_info:
        logger.info(f"🌐 查詢翻譯（{translation_info['method']}）完成，{translation_info['ms']} ms")
        if QUERY_TRANSLATION == "dictionary":
            request.query = retrieval_query

    # 檢索階段
    retrieval_start = datetime.now()
    cache_hit = False

    # source_filter 只有 VectorOnlyRAG 支援，且會影響檢索結果，需併入快取鍵
    cache_strategy_key = (
        f"{rag_strategy}:{request.source_filter}" if request.source_filter else rag_strategy
    )
    if EXCLUDE_EVIDENCE_PREFIXES:  # 開關影響檢索結果，併入快取鍵
        cache_strategy_key += ":ex=" + ",".join(EXCLUDE_EVIDENCE_PREFIXES)
    if GRAPH_FALLBACK_NONFACT != "fulltext":
        cache_strategy_key += ":gf=" + GRAPH_FALLBACK_NONFACT

    async def _retrieve():
        fetch = request.max_results + (_EXCLUDE_MARGIN if EXCLUDE_EVIDENCE_PREFIXES else 0)
        if isinstance(strategy, VectorOnlyRAG):
            docs = await strategy.retrieve(
                retrieval_query, fetch, source_filter=request.source_filter
            )
        else:
            docs = await strategy.retrieve(retrieval_query, fetch)
        return _evidence_only(docs, request.max_results)

    try:
        # 嘗試從緩存獲取
        if query_cache:
            cached_sources = query_cache.get(
                retrieval_query, cache_strategy_key, request.max_results
            )
            if cached_sources is not None:
                sources = cached_sources
                cache_hit = True
            else:
                # 緩存未命中，執行檢索
                sources = await _retrieve()
                # 保存到緩存（空結果不快取，RET-13；記下 doc_id 供來源變動失效，RET-12）
                if sources:
                    query_cache.set(
                        retrieval_query,
                        cache_strategy_key,
                        request.max_results,
                        sources,
                        doc_ids=_source_doc_ids(sources),
                    )
        else:
            # 緩存未啟用
            sources = await _retrieve()

    except Exception as e:
        logger.error(f"檢索失敗: {e}")
        raise HTTPException(status_code=500, detail=f"檢索失敗: {str(e)}") from e

    retrieval_time = (datetime.now() - retrieval_start).total_seconds() * 1000

    k_info = None
    if K_SCORER and sources:
        try:  # CPU 推論放到執行緒，不阻塞事件迴圈；以原問題打分（同 E6 校準方式）
            k_info = await asyncio.to_thread(k_scorer.score_k, request.query, sources)
        except Exception as e:
            logger.warning(f"⚠️ K 評分失敗: {e!r}")

    # 獲取模型參數；如果沒有指定，從配置中獲取默認值
    temperature = request.temperature
    max_tokens = request.max_tokens
    if temperature is None or max_tokens is None:
        for combo in RAG_CONFIG.get("model_combinations", []):
            if combo["id"] == request.model_combination_id:
                if temperature is None:
                    temperature = combo["params"].get("temperature", 0.1)
                if max_tokens is None:
                    max_tokens = combo["params"].get("max_tokens", 2048)
                break

    # 部署層可設全域生成長度上限（RAG_MAX_TOKENS_CAP）：實測回應時間與答案
    # 長度近乎線性（~60 字/s），課堂情境用上限換速度；0 或未設定表示不設限
    cap = int(os.getenv("RAG_MAX_TOKENS_CAP", "0"))
    if cap > 0 and max_tokens:
        max_tokens = min(max_tokens, cap)

    # 答案層快取：原本只快取檢索結果，但檢索僅 ~0.04s、生成要 10s+，
    # 快取蓋在不痛的地方——同題重問照樣付全額生成時間。答案 key 需含
    # 會影響輸出的全部參數（組合、溫度、長度上限、來源過濾）。
    answer_cache_key = (
        f"ans:{request.model_combination_id}:{temperature}:{max_tokens}:"
        f"{request.source_filter or ''}"
    )
    return _QueryContext(
        request=request,
        start_time=start_time,
        llm_model=llm_model,
        rag_strategy=rag_strategy,
        strategy=strategy,
        translation_info=translation_info,
        sources=sources,
        cache_hit=cache_hit,
        retrieval_time=retrieval_time,
        temperature=temperature,
        max_tokens=max_tokens,
        answer_cache_key=answer_cache_key,
        k_info=k_info,
    )


def _cached_answer(ctx: _QueryContext) -> str | None:
    if not query_cache:
        return None
    return query_cache.get(ctx.request.query, ctx.answer_cache_key, ctx.request.max_results)


def _store_answer(ctx: _QueryContext, answer: str) -> None:
    if query_cache and ctx.sources and not is_refusal(answer):  # 拒答不進快取（RET-13）
        query_cache.set(
            ctx.request.query,
            ctx.answer_cache_key,
            ctx.request.max_results,
            answer,
            doc_ids=_source_doc_ids(ctx.sources),
        )


async def _finish_query(
    ctx: _QueryContext, answer: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """生成完成後：守門員影子模式與回應 metadata（兩個端點共用）。"""
    citations = build_citations(ctx.sources)

    # 防護影子模式（GRD-06、GRD-08）：只計算與記錄，回答內容不變
    guard_info = None
    if GUARD_MODE == "shadow":
        gate_status, coarse, guard_ms = await _run_coarse_guard(answer, ctx.sources)
        scores = coarse.summary() if coarse else {}
        guard_info = {"mode": "shadow", "gate_status": gate_status, "guard_ms": guard_ms, **scores}
        task = asyncio.create_task(
            asyncio.to_thread(
                _write_guard_shadow,
                {
                    "route_id": ctx.rag_strategy,
                    "model": ctx.llm_model,
                    "gate_status": gate_status,
                    "guard_ms": round(guard_ms, 3),
                    **scores,
                    "cited_doc_ids": [c["doc_id"] for c in citations if c["doc_id"]],
                    "cache_hit": ctx.cache_hit,
                },
            )
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    total_time = (datetime.now() - ctx.start_time).total_seconds() * 1000

    # 構建響應
    metadata = {
        "total_time_ms": total_time,
        "num_sources": len(ctx.sources),
        "query_length": len(ctx.request.query),
        "answer_length": len(answer),
        "cache_hit": ctx.cache_hit,
    }
    if guard_info:
        metadata["guard"] = guard_info
        metadata["timings"] = {"guard": guard_info["guard_ms"]}  # GRD-06a

    # 如果有翻譯信息，添加到元數據
    if ctx.translation_info:
        metadata["translation"] = ctx.translation_info
    if ctx.k_info:
        metadata["k"] = ctx.k_info

    logger.info(
        f"查詢完成: {ctx.request.query[:50]}... | "
        f"模型: {ctx.llm_model} | 策略: {ctx.rag_strategy} | "
        f"總時間: {total_time:.0f}ms"
    )
    return metadata, citations


# 三層回答（規格 Q8：直接依據／相關資料／無法回答；2026-10-14 試做，預設關閉，需 K_SCORER=1）：
# 每筆來源以 K 校準機率分層；只把「直接依據」交給模型並要求逐句引用，「相關資料」由程式列出、
# 不經模型；沒有直接依據時不呼叫模型。門檻為替代量尺下的暫定值
ANSWER_LAYERS = os.getenv("ANSWER_LAYERS", "0") == "1"
LAYER_DIRECT_MIN = float(os.getenv("LAYER_DIRECT_MIN", "0.7"))
LAYER_RELATED_MIN = float(os.getenv("LAYER_RELATED_MIN", "0.3"))


def _split_layers(ctx: _QueryContext) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """依每筆來源的 K 校準機率分成直接依據與相關資料（分數高者在前）。"""
    scores = (ctx.k_info or {}).get("scores") or []
    ranked = sorted(zip(scores, ctx.sources, strict=False), key=lambda t: -t[0])
    direct = [s for sc, s in ranked if k_scorer.calibrate(sc) >= LAYER_DIRECT_MIN]
    related = [
        s for sc, s in ranked if LAYER_RELATED_MIN <= k_scorer.calibrate(sc) < LAYER_DIRECT_MIN
    ]
    return direct, related


def _related_text(related: list[dict[str, Any]]) -> str:
    lines = []
    for i, s in enumerate(related, 1):
        md = s.get("metadata") or {}
        title = md.get("title") or md.get("name") or "未知"
        lines.append(f"{i}. {title}" + (f"［{md['source']}］" if md.get("source") else ""))
    return "\n".join(lines)


async def _layered_answer(ctx: _QueryContext) -> tuple[str, dict[str, Any]]:
    direct, related = _split_layers(ctx)
    layers = {"direct": len(direct), "related": len(related), "answered": bool(direct)}
    parts = []
    if direct:
        body = await ctx.strategy.generate(
            ctx.request.query
            + "\n（只根據參考資料回答；每句以 [文檔 n] 標注出處；資料沒有的內容不要寫。）",
            direct,
            ctx.llm_model,
            temperature=ctx.temperature,
            max_tokens=ctx.max_tokens,
        )
        parts.append("【直接依據】\n" + body.strip())
    else:
        parts.append("【無法回答】\n館藏中沒有可以直接回答這個問題的資料。")
    if related:
        parts.append("【相關資料】（可能有幫助，但不足以直接回答）\n" + _related_text(related))
    return "\n\n".join(parts), layers


@app.post("/api/v1/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """處理查詢請求"""
    ctx = await _prepare_query(request)

    # 生成階段
    generation_start = datetime.now()
    try:
        answer = None if ANSWER_LAYERS else _cached_answer(ctx)
        layers = None
        if answer is not None:
            ctx.cache_hit = True
        elif ANSWER_LAYERS and ctx.k_info:
            answer, layers = await _layered_answer(ctx)
        else:
            answer = await ctx.strategy.generate(
                ctx.request.query,
                ctx.sources,
                ctx.llm_model,
                temperature=ctx.temperature,
                max_tokens=ctx.max_tokens,
            )
            _store_answer(ctx, answer)
    except Exception as e:
        logger.error(f"生成失敗: {e}")
        raise HTTPException(status_code=500, detail=f"生成失敗: {str(e)}") from e
    generation_time = (datetime.now() - generation_start).total_seconds() * 1000

    metadata, citations = await _finish_query(ctx, answer)
    if layers:
        metadata["layers"] = layers
    return QueryResponse(
        answer=answer,
        sources=ctx.sources if request.include_sources else [],
        model_used=ctx.llm_model,
        rag_strategy=ctx.rag_strategy,
        retrieval_time_ms=ctx.retrieval_time,
        generation_time_ms=generation_time,
        metadata=metadata,
        citations=citations,
    )


async def _stream_generate(ctx: _QueryContext):
    """逐段產生模型輸出 (種類, 文字)：種類 "text"＝回答、"think"＝Ollama thinking 欄位的思考內容
    （gemma4 等）。策略自訂 generate 時退回整段生成（不串流但結果相同）。"""
    strategy = ctx.strategy
    if type(strategy).generate is not RAGStrategy.generate:
        yield (
            "text",
            await strategy.generate(
                ctx.request.query,
                ctx.sources,
                ctx.llm_model,
                temperature=ctx.temperature,
                max_tokens=ctx.max_tokens,
            ),
        )
        return
    prompt = strategy._build_prompt(ctx.request.query, strategy._format_context(ctx.sources))
    payload = {
        "model": ctx.llm_model,
        "prompt": prompt,
        "stream": True,
        "options": {"temperature": ctx.temperature, "num_predict": ctx.max_tokens},
    }
    if _no_think(ctx.llm_model):
        payload["think"] = False
    async with conn_manager.http_client.stream(
        "POST", f"{OLLAMA_BASE_URL}/api/generate", json=payload, timeout=900.0
    ) as response:
        if response.status_code != 200:
            detail = (await response.aread()).decode("utf-8", "replace")[:300]
            raise RuntimeError(f"Ollama 生成失敗: {response.status_code} {detail}")
        async for line in response.aiter_lines():
            if not line.strip():
                continue
            chunk = json.loads(line)
            if chunk.get("thinking"):
                yield "think", chunk["thinking"]
            if chunk.get("response"):
                yield "text", chunk["response"]
            if chunk.get("done"):
                break


@app.post("/api/v1/query/stream")
async def process_query_stream(request: QueryRequest):
    """串流版 /query（NDJSON：meta →（waiting／thinking…）→ delta… → done；錯誤時 error）。

    設計：docs/designs/2026-10-14-streaming-response.md。每句經 sentence_hook 再送出
    （預留守門員攔截 #15、分層回答 #12）；答案快取與守門員影子模式在生成結束後處理。
    """
    ctx = await _prepare_query(request)

    def elapsed_ms() -> float:
        return round((datetime.now() - ctx.start_time).total_seconds() * 1000, 1)

    def checked(sentences: list[str]) -> list[str]:
        return [s for s in (sentence_hook(x, ctx.sources) for x in sentences) if s]

    async def events():
        yield ndjson(
            {
                "type": "meta",
                "model_used": ctx.llm_model,
                "rag_strategy": ctx.rag_strategy,
                "sources": ctx.sources if request.include_sources else [],
                "citations": build_citations(ctx.sources),
                "translation": ctx.translation_info,
                "retrieval_time_ms": ctx.retrieval_time,
                "k": ctx.k_info,
            }
        )
        generation_start = datetime.now()
        first_ms = None
        parts: list[str] = []
        try:
            cached = _cached_answer(ctx)
            if cached is not None:
                ctx.cache_hit = True
                first_ms = elapsed_ms()
                parts.append(cached)
                yield ndjson({"type": "delta", "text": cached})
            else:
                think, splitter = ThinkFilter(), SentenceSplitter()
                last_thinking = 0.0
                async for kind, piece in with_heartbeat(_stream_generate(ctx)):
                    if kind == "waiting":  # 模型載入中、尚無任何輸出
                        yield ndjson({"type": "waiting", "elapsed_ms": elapsed_ms()})
                        continue
                    visible = think.feed(piece) if kind == "text" else ""
                    # 思考中（thinking 欄位或 <think> 段）：每 3 秒最多送一次，讓前端顯示進度
                    if (kind == "think" or think.in_think) and first_ms is None:
                        now = time.monotonic()
                        if now - last_thinking >= 3:
                            last_thinking = now
                            yield ndjson({"type": "thinking", "elapsed_ms": elapsed_ms()})
                    for sentence in checked(splitter.feed(visible)):
                        first_ms = first_ms if first_ms is not None else elapsed_ms()
                        parts.append(sentence)
                        yield ndjson({"type": "delta", "text": sentence})
                tail = splitter.feed(think.finish())
                last = splitter.flush()
                for sentence in checked(tail + ([last] if last else [])):
                    first_ms = first_ms if first_ms is not None else elapsed_ms()
                    parts.append(sentence)
                    yield ndjson({"type": "delta", "text": sentence})
                _store_answer(ctx, "".join(parts))
        except Exception as e:
            logger.error(f"串流生成失敗: {e}")
            yield ndjson({"type": "error", "detail": str(e)})
            return
        answer = "".join(parts)
        generation_time = (datetime.now() - generation_start).total_seconds() * 1000
        metadata, _ = await _finish_query(ctx, answer)
        metadata["first_sentence_ms"] = first_ms
        yield ndjson(
            {
                "type": "done",
                "answer": answer,
                "retrieval_time_ms": ctx.retrieval_time,
                "generation_time_ms": generation_time,
                "metadata": metadata,
            }
        )

    return StreamingResponse(events(), media_type="application/x-ndjson")


@app.get("/")
async def root():
    """根端點"""
    return {
        "service": "Art History RAG Manager V2",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "models": "/api/v1/models",
            "strategies": "/api/v1/strategies",
            "query": "/api/v1/query",
            "cache_stats": "/api/v1/cache/stats",
            "cache_clear": "/api/v1/cache/clear",
        },
    }


# ==================== 主程序 ====================

if __name__ == "__main__":
    port = int(os.getenv("RAG_MANAGER_PORT", "8001"))

    logger.info(f"🚀 啟動 RAG 管理器服務於端口 {port}")
    logger.info(f"   Ollama: {OLLAMA_BASE_URL}")
    logger.info(f"   Neo4j: {NEO4J_URI}")
    logger.info(f"   ChromaDB: {CHROMADB_HOST}:{CHROMADB_PORT}")

    # WSL 內部服務，需綁定所有介面供 Windows 端連線
    # 預設僅綁本機；部署若需跨介面（例如 WSL 對外供 Windows 側存取）以 RAG_BIND_HOST 覆蓋
    host = os.getenv("RAG_BIND_HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=port, log_level="info")
