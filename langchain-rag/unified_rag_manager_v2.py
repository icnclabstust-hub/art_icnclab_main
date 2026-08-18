#!/usr/bin/env python3
"""
統一 RAG 管理器服務 V2
提供多種 RAG 策略的統一接口，支援動態切換 LLM 模型和 RAG 策略
整合 Ollama 模型和 Neo4j/ChromaDB
"""

import hashlib
import json
import logging
import os
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import chromadb
import httpx
import uvicorn

# ChromaDB 共用 embedding function（BGE-M3，取代預設的英文為主模型）
from bge_m3_embedding import BGEM3EmbeddingFunction
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# 導入多語言查詢翻譯器
from multilingual_query_translator import MultilingualQueryTranslator
from neo4j import GraphDatabase
from pydantic import BaseModel

# 導入智能關鍵詞提取器
from smart_keyword_extractor import SmartKeywordExtractor

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

    def set(self, query: str, strategy: str, max_results: int, data: list[dict[str, Any]]):
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
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== 配置加載 ====================

config_path = Path(__file__).parent / "rag_config.json"
with open(config_path, encoding="utf-8") as f:
    RAG_CONFIG = json.load(f)

# 環境變數配置
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# 原生 Neo4j（WSL 直接執行，非 Docker）；7688 是因為 WSL 環境本身有另一個系統 Neo4j 服務佔用了 7687
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7688")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
if not NEO4J_PASSWORD:
    raise RuntimeError(
        "缺少 NEO4J_PASSWORD 環境變數。請在啟動前設定，例如："
        "NEO4J_PASSWORD=... python3 unified_rag_manager_v2.py"
        "（Start-NativeServices.ps1 已內建設定，不需手動處理）"
    )
CHROMADB_HOST = os.getenv("CHROMADB_HOST", "localhost")
CHROMADB_PORT = int(os.getenv("CHROMADB_PORT", "8001"))
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
                    metadata = results["metadatas"][0][i] if results["metadatas"] else {}
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
        try:
            response = await conn_manager.http_client.post(
                f"{OLLAMA_BASE_URL}/api/embed",
                json={"model": "bge-m3:latest", "input": [query]},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()["embeddings"][0]
        except Exception as e:
            logger.error(f"Hybrid ES RAG 查詢向量化失敗: {e}")
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
                    },
                    "score": rrf_scores[doc_id],
                    "source": src.get("source", "Elasticsearch Hybrid"),
                }
            )

        logger.info(f"Hybrid ES RAG 檢索返回 {len(documents)} 個結果（BM25+kNN RRF 融合）")
        return documents


class GraphOnlyRAG(RAGStrategy):
    """純圖譜檢索 RAG"""

    def __init__(self):
        super().__init__("Graph Only RAG", "使用知識圖譜進行關係推理")

    async def retrieve(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """使用 Neo4j 進行圖譜檢索"""
        if not conn_manager.neo4j_driver:
            logger.warning("Neo4j 未連接，返回空結果")
            return []

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
                    WITH node as artwork, score
                    LIMIT $limit
                    OPTIONAL MATCH (artwork)-[r]-(related)
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

        # 添加屬性 - 安全處理各種類型
        for key, value in node.items():
            if key not in ["name", "title"] and value:
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
                    OPTIONAL MATCH (artist)-[:CREATED]->(artwork:Artwork)
                    WITH artist, score, collect(DISTINCT artwork) as artworks
                    UNWIND (CASE WHEN size(artworks) = 0 THEN [null] ELSE artworks END) as aw
                    OPTIONAL MATCH (aw)-[r2]->(ext)
                    WHERE aw IS NULL OR type(r2) IN $ext_types
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
                    WITH artwork, score LIMIT $limit
                    OPTIONAL MATCH (artist:Artist)-[:CREATED]->(artwork)
                    OPTIONAL MATCH (artwork)-[r2]->(ext)
                    WHERE r2 IS NULL OR type(r2) IN $ext_types
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

RAG_STRATEGIES = {
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
    except Exception as e:
        logger.warning(f"⚠️ 多語言翻譯器初始化失敗: {e}，將繼續使用原始查詢")
        query_translator = None

    # 初始化智能關鍵詞提取器
    try:
        keyword_extractor = SmartKeywordExtractor(translator=query_translator, log_queries=True)
        logger.info("✅ 智能關鍵詞提取器已初始化")
    except Exception as e:
        logger.warning(f"⚠️ 關鍵詞提取器初始化失敗: {e}，將使用基礎提取")
        keyword_extractor = None

    # 初始化查詢緩存
    try:
        cache_size = int(os.getenv("QUERY_CACHE_SIZE", "1000"))
        cache_ttl = int(os.getenv("QUERY_CACHE_TTL", "3600"))
        query_cache = QueryCache(max_size=cache_size, ttl_seconds=cache_ttl)
        logger.info(f"✅ 查詢緩存已初始化 (大小: {cache_size}, TTL: {cache_ttl}秒)")
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


@app.post("/api/v1/retrieve")
async def process_retrieve_only(request: QueryRequest):
    """僅檢索、不生成答案 —— 用於事後回填評測用的原文片段（Faithfulness 計算）"""
    rag_strategy = request.model_combination_id.split("@")[-1]
    strategy = RAG_STRATEGIES.get(rag_strategy)
    if not strategy:
        raise HTTPException(status_code=404, detail=f"未找到 RAG 策略: {rag_strategy}")

    query_text = request.query
    if query_translator:
        try:
            translation_result = query_translator.translate_query(request.query)
            if (
                translation_result["detected_language"] != "en"
                and translation_result["found_terms"]
            ):
                query_text = translation_result["translated_query"]
        except Exception as e:
            logger.warning(f"⚠️ 查詢翻譯失敗: {e}，使用原始查詢")

    if isinstance(strategy, VectorOnlyRAG):
        sources = await strategy.retrieve(
            query_text, request.max_results, source_filter=request.source_filter
        )
    else:
        sources = await strategy.retrieve(query_text, request.max_results)

    return {"sources": sources}


@app.post("/api/v1/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """處理查詢請求"""
    start_time = datetime.now()

    # 解析模型組合 ID
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

    # 多語言查詢翻譯
    original_query = request.query
    translation_info = None

    if query_translator:
        try:
            translation_result = query_translator.translate_query(request.query)
            translated_query = translation_result["translated_query"]

            # 如果檢測到非英文且進行了翻譯，使用翻譯後的查詢
            if (
                translation_result["detected_language"] != "en"
                and translation_result["found_terms"]
            ):
                n_terms = len(translation_result["found_terms"])
                logger.info(
                    f"🌐 查詢翻譯: '{original_query}' -> '{translated_query}' "
                    f"({translation_result['detected_language']}, {n_terms} 個術語)"
                )
                request.query = translated_query
                translation_info = {
                    "original_query": original_query,
                    "translated_query": translated_query,
                    "detected_language": translation_result["detected_language"],
                    "found_terms": translation_result["found_terms"],
                    "translation_method": translation_result["translation_method"],
                }
        except Exception as e:
            logger.warning(f"⚠️ 查詢翻譯失敗: {e}，使用原始查詢")

    # 檢索階段
    retrieval_start = datetime.now()
    cache_hit = False

    # source_filter 只有 VectorOnlyRAG 支援，且會影響檢索結果，需併入快取鍵
    cache_strategy_key = (
        f"{rag_strategy}:{request.source_filter}" if request.source_filter else rag_strategy
    )

    async def _retrieve():
        if isinstance(strategy, VectorOnlyRAG):
            return await strategy.retrieve(
                request.query, request.max_results, source_filter=request.source_filter
            )
        return await strategy.retrieve(request.query, request.max_results)

    try:
        # 嘗試從緩存獲取
        if query_cache:
            cached_sources = query_cache.get(request.query, cache_strategy_key, request.max_results)
            if cached_sources is not None:
                sources = cached_sources
                cache_hit = True
            else:
                # 緩存未命中，執行檢索
                sources = await _retrieve()
                # 保存到緩存
                query_cache.set(request.query, cache_strategy_key, request.max_results, sources)
        else:
            # 緩存未啟用
            sources = await _retrieve()

    except Exception as e:
        logger.error(f"檢索失敗: {e}")
        raise HTTPException(status_code=500, detail=f"檢索失敗: {str(e)}") from e

    retrieval_time = (datetime.now() - retrieval_start).total_seconds() * 1000

    # 生成階段
    generation_start = datetime.now()
    try:
        # 獲取模型參數
        temperature = request.temperature
        max_tokens = request.max_tokens

        # 如果沒有指定，從配置中獲取默認值
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
        cached_answer = (
            query_cache.get(request.query, answer_cache_key, request.max_results)
            if query_cache
            else None
        )
        if cached_answer is not None:
            answer = cached_answer
            cache_hit = True
        else:
            answer = await strategy.generate(
                request.query, sources, llm_model, temperature=temperature, max_tokens=max_tokens
            )
            if query_cache:
                query_cache.set(request.query, answer_cache_key, request.max_results, answer)
    except Exception as e:
        logger.error(f"生成失敗: {e}")
        raise HTTPException(status_code=500, detail=f"生成失敗: {str(e)}") from e
    generation_time = (datetime.now() - generation_start).total_seconds() * 1000

    total_time = (datetime.now() - start_time).total_seconds() * 1000

    # 構建響應
    metadata = {
        "total_time_ms": total_time,
        "num_sources": len(sources),
        "query_length": len(request.query),
        "answer_length": len(answer),
        "cache_hit": cache_hit,
    }

    # 如果有翻譯信息，添加到元數據
    if translation_info:
        metadata["translation"] = translation_info

    response = QueryResponse(
        answer=answer,
        sources=sources if request.include_sources else [],
        model_used=llm_model,
        rag_strategy=rag_strategy,
        retrieval_time_ms=retrieval_time,
        generation_time_ms=generation_time,
        metadata=metadata,
    )

    logger.info(
        f"查詢完成: {request.query[:50]}... | "
        f"模型: {llm_model} | 策略: {rag_strategy} | "
        f"總時間: {total_time:.0f}ms"
    )

    return response


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
    port = int(os.getenv("RAG_MANAGER_PORT", "8007"))

    logger.info(f"🚀 啟動 RAG 管理器服務於端口 {port}")
    logger.info(f"   Ollama: {OLLAMA_BASE_URL}")
    logger.info(f"   Neo4j: {NEO4J_URI}")
    logger.info(f"   ChromaDB: {CHROMADB_HOST}:{CHROMADB_PORT}")

    # WSL 內部服務，需綁定所有介面供 Windows 端連線
    # 預設僅綁本機；部署若需跨介面（例如 WSL 對外供 Windows 側存取）以 RAG_BIND_HOST 覆蓋
    host = os.getenv("RAG_BIND_HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=port, log_level="info")
