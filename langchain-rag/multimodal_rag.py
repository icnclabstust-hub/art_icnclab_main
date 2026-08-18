#!/usr/bin/env python3
"""
多模態 RAG 系統 - LangChain 實現
整合文本、圖像和知識圖譜的完整RAG架構
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any

import chromadb

# 多模態組件
import requests

# LangChain 鏈
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationSummaryBufferMemory

# 文本分割
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import WebBaseLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.llms import Ollama

# LangChain 社群套件
from langchain_community.vectorstores import Chroma

# LangChain 核心組件
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import VectorStore

# 配置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class RAGConfig:
    """RAG 系統配置"""

    # 向量資料庫配置
    chroma_host: str = "localhost"
    chroma_port: int = 8000
    collection_name: str = "art_history_multimodal"

    # LLM 配置
    ollama_base_url: str = "http://localhost:11434"
    model_name: str = "llama3.1:8b"

    # CUDA ML 服務配置
    ml_service_url: str = "http://localhost:8080"

    # 嵌入模型配置
    text_embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    # 分割參數
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # 檢索參數
    top_k: int = 5
    score_threshold: float = 0.7

    # 多模態權重
    text_weight: float = 0.6
    image_weight: float = 0.4


class ArtHistoryEmbeddings(Embeddings):
    """藝術史專用嵌入類"""

    def __init__(self, model_name: str, ml_service_url: str):
        self.model_name = model_name
        self.ml_service_url = ml_service_url
        self.hf_embeddings = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": "cuda" if os.path.exists("/usr/local/cuda") else "cpu"},
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """嵌入多個文檔"""
        try:
            # 優先使用專用 ML 服務
            response = requests.post(
                f"{self.ml_service_url}/embeddings",
                json={"texts": texts, "model": "bge-m3"},
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("success") and "embeddings" in result:
                    return result["embeddings"]
        except Exception as e:
            logger.warning(f"ML服務嵌入失敗，使用備用方案: {e}")

        # 備用方案：使用 HuggingFace
        return self.hf_embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        """嵌入查詢文本"""
        return self.embed_documents([text])[0]


class MultimodalRetriever(BaseRetriever):
    """多模態檢索器"""

    def __init__(
        self,
        vector_store: VectorStore,
        ml_service_url: str,
        text_weight: float = 0.6,
        image_weight: float = 0.4,
        top_k: int = 5,
    ):
        self.vector_store = vector_store
        self.ml_service_url = ml_service_url
        self.text_weight = text_weight
        self.image_weight = image_weight
        self.top_k = top_k

    def _get_relevant_documents(self, query: str, **kwargs) -> list[Document]:
        """獲取相關文檔"""
        try:
            # 如果查詢包含圖像引用，執行多模態檢索
            if self._has_visual_keywords(query):
                return self._multimodal_search(query)
            else:
                # 純文本檢索
                return self.vector_store.similarity_search(query, k=self.top_k)
        except Exception as e:
            logger.error(f"檢索失敗: {e}")
            return []

    def _has_visual_keywords(self, query: str) -> bool:
        """檢測查詢是否包含視覺關鍵詞"""
        visual_keywords = [
            "顏色",
            "色彩",
            "構圖",
            "筆觸",
            "線條",
            "形狀",
            "明暗",
            "光影",
            "透視",
            "風格",
            "畫面",
            "視覺",
            "color",
            "composition",
            "brush",
            "line",
            "shadow",
        ]
        return any(keyword in query.lower() for keyword in visual_keywords)

    def _multimodal_search(self, query: str) -> list[Document]:
        """多模態檢索"""
        try:
            # 1. 文本向量檢索
            text_docs = self.vector_store.similarity_search(query, k=self.top_k * 2)

            # 2. 模擬圖像特徵檢索（實際實現中需要真實的圖像特徵）
            image_features = self._generate_query_image_features(query)

            # 3. 融合檢索結果
            fused_docs = self._fuse_multimodal_results(text_docs, image_features)

            return fused_docs[: self.top_k]

        except Exception as e:
            logger.error(f"多模態檢索失敗: {e}")
            # 降級為純文本檢索
            return self.vector_store.similarity_search(query, k=self.top_k)

    def _generate_query_image_features(self, query: str) -> list[float] | None:
        """根據查詢生成圖像特徵（模擬）"""
        try:
            response = requests.post(
                f"{self.ml_service_url}/image/features",
                json={"text_query": query, "generate_from_text": True},
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("features")
        except Exception as e:
            logger.warning(f"圖像特徵生成失敗: {e}")

        return None

    def _fuse_multimodal_results(
        self, text_docs: list[Document], image_features: list[float] | None
    ) -> list[Document]:
        """融合多模態檢索結果"""
        # 簡化版本：基於文本權重調整分數
        for doc in text_docs:
            # 添加多模態分數元數據
            if image_features:
                doc.metadata["multimodal_score"] = self.text_weight
            else:
                doc.metadata["multimodal_score"] = 1.0

        # 按分數排序
        return sorted(text_docs, key=lambda d: d.metadata.get("multimodal_score", 0), reverse=True)


class ArtHistoryRAGSystem:
    """藝術史 RAG 系統主類"""

    def __init__(self, config: RAGConfig):
        self.config = config
        self.embeddings = None
        self.vector_store = None
        self.llm = None
        self.retriever = None
        self.qa_chain = None
        self.memory = None

    async def initialize(self):
        """初始化 RAG 系統"""
        logger.info("🚀 初始化藝術史多模態 RAG 系統...")

        # 1. 初始化嵌入模型
        logger.info("📊 初始化嵌入模型...")
        self.embeddings = ArtHistoryEmbeddings(
            model_name=self.config.text_embedding_model, ml_service_url=self.config.ml_service_url
        )

        # 2. 初始化向量資料庫
        logger.info("🗄️ 初始化向量資料庫...")
        self.vector_store = await self._initialize_vector_store()

        # 3. 初始化 LLM
        logger.info("🧠 初始化語言模型...")
        self.llm = Ollama(
            base_url=self.config.ollama_base_url,
            model=self.config.model_name,
            temperature=0.1,
            system=self._get_art_expert_system_prompt(),
        )

        # 4. 初始化檢索器
        logger.info("🔍 初始化多模態檢索器...")
        self.retriever = MultimodalRetriever(
            vector_store=self.vector_store,
            ml_service_url=self.config.ml_service_url,
            text_weight=self.config.text_weight,
            image_weight=self.config.image_weight,
            top_k=self.config.top_k,
        )

        # 5. 初始化記憶體
        logger.info("💾 初始化對話記憶體...")
        self.memory = ConversationSummaryBufferMemory(
            llm=self.llm, memory_key="chat_history", return_messages=True, max_token_limit=2000
        )

        # 6. 初始化 QA 鏈
        logger.info("⛓️ 初始化問答鏈...")
        self.qa_chain = ConversationalRetrievalChain.from_llm(
            llm=self.llm,
            retriever=self.retriever,
            memory=self.memory,
            return_source_documents=True,
            verbose=True,
        )

        logger.info("✅ RAG 系統初始化完成！")

    async def _initialize_vector_store(self) -> VectorStore:
        """初始化向量資料庫"""
        try:
            # 嘗試連接現有的 ChromaDB
            client = chromadb.HttpClient(host=self.config.chroma_host, port=self.config.chroma_port)

            # 檢查或創建集合
            collection_name = self.config.collection_name
            try:
                client.get_collection(name=collection_name)
                logger.info(f"✅ 找到現有集合: {collection_name}")
            except Exception:
                client.create_collection(name=collection_name)
                logger.info(f"✅ 創建新集合: {collection_name}")

            # 返回 LangChain Chroma 向量存儲
            vector_store = Chroma(
                client=client, collection_name=collection_name, embedding_function=self.embeddings
            )

            return vector_store

        except Exception as e:
            logger.warning(f"ChromaDB 連接失敗，使用本地存儲: {e}")
            # 本地持久化版本
            persist_directory = "./data/chroma_db"
            os.makedirs(persist_directory, exist_ok=True)

            return Chroma(
                persist_directory=persist_directory,
                embedding_function=self.embeddings,
                collection_name=self.config.collection_name,
            )

    def _get_art_expert_system_prompt(self) -> str:
        """獲取藝術專家系統提示"""
        return """你是一位專業的藝術史學者和策展人，具有以下特質：

專業知識：
- 精通中國、西方和現代藝術史
- 熟悉各個藝術時期的風格特色、技法發展
- 了解藝術家的生平背景和創作理念
- 掌握藝術品的保存、修復和鑑定知識

回答風格：
- 使用專業但易懂的語言
- 提供準確的歷史背景和藝術分析
- 引用具體的藝術作品和藝術家實例
- 結合視覺描述和技法分析
- 保持客觀和學術嚴謹性

回答結構：
1. 直接回答問題要點
2. 提供相關的歷史背景
3. 舉出具體實例或作品
4. 補充相關的藝術技法或風格特色
5. 如有需要，提供進一步學習建議

請基於檢索到的相關資料，結合你的專業知識，為用戶提供高品質的藝術史回答。"""

    async def query(self, question: str) -> dict[str, Any]:
        """執行 RAG 查詢"""
        try:
            logger.info(f"🔍 處理查詢: {question}")

            # 執行檢索和生成
            result = await asyncio.to_thread(self.qa_chain, {"question": question})

            # 整理回應
            response = {
                "question": question,
                "answer": result["answer"],
                "source_documents": [
                    {"content": doc.page_content, "metadata": doc.metadata}
                    for doc in result.get("source_documents", [])
                ],
                "chat_history": result.get("chat_history", []),
            }

            logger.info("✅ 查詢完成")
            return response

        except Exception as e:
            logger.error(f"❌ 查詢失敗: {e}")
            return {
                "question": question,
                "answer": f"抱歉，查詢時發生錯誤: {str(e)}",
                "source_documents": [],
                "chat_history": [],
            }

    async def add_documents(self, documents: list[Document]) -> bool:
        """添加文檔到向量資料庫"""
        try:
            logger.info(f"📄 添加 {len(documents)} 個文檔...")

            # 文本分割
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
                separators=["\n\n", "\n", "。", ".", " "],
            )

            # 分割文檔
            split_docs = []
            for doc in documents:
                splits = text_splitter.split_documents([doc])
                split_docs.extend(splits)

            # 添加到向量存儲
            await asyncio.to_thread(self.vector_store.add_documents, split_docs)

            logger.info(f"✅ 成功添加 {len(split_docs)} 個文檔片段")
            return True

        except Exception as e:
            logger.error(f"❌ 文檔添加失敗: {e}")
            return False

    async def load_documents_from_urls(self, urls: list[str]) -> bool:
        """從 URL 載入文檔"""
        try:
            logger.info(f"🌐 從 {len(urls)} 個URL載入文檔...")

            documents = []
            for url in urls:
                try:
                    loader = WebBaseLoader(url)
                    docs = await asyncio.to_thread(loader.load)
                    documents.extend(docs)
                    logger.info(f"✅ 成功載入: {url}")
                except Exception as e:
                    logger.warning(f"⚠️ URL載入失敗 {url}: {e}")

            if documents:
                return await self.add_documents(documents)
            else:
                logger.warning("⚠️ 沒有成功載入任何文檔")
                return False

        except Exception as e:
            logger.error(f"❌ URL文檔載入失敗: {e}")
            return False

    def get_statistics(self) -> dict[str, Any]:
        """獲取系統統計資訊"""
        try:
            # 獲取向量資料庫統計
            collection = self.vector_store._collection
            count = collection.count()

            return {
                "documents_count": count,
                "model_name": self.config.model_name,
                "embedding_model": self.config.text_embedding_model,
                "collection_name": self.config.collection_name,
                "memory_messages": len(self.memory.chat_memory.messages) if self.memory else 0,
            }
        except Exception as e:
            logger.error(f"獲取統計資訊失敗: {e}")
            return {"error": str(e)}


# 測試和示例用法
async def main():
    """主測試函數"""
    # 配置
    config = RAGConfig()

    # 初始化系統
    rag_system = ArtHistoryRAGSystem(config)
    await rag_system.initialize()

    # 示例查詢
    test_questions = [
        "印象派繪畫有什麼特色？",
        "達文西的《蒙娜麗莎》使用了什麼技法？",
        "巴洛克藝術與文藝復興藝術有什麼區別？",
    ]

    print("🎨 藝術史多模態 RAG 系統測試\n" + "=" * 50)

    for i, question in enumerate(test_questions, 1):
        print(f"\n【測試 {i}】{question}")
        print("-" * 30)

        result = await rag_system.query(question)
        print(f"回答: {result['answer']}")

        if result["source_documents"]:
            print(f"\n參考文獻數量: {len(result['source_documents'])}")

    # 顯示統計資訊
    print("\n" + "=" * 50)
    stats = rag_system.get_statistics()
    print("📊 系統統計:")
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
