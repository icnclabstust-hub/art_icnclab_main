#!/usr/bin/env python3
"""
向量RAG Agent
實現基於向量相似度的檢索增強生成
"""

from datetime import datetime
from typing import Any

import numpy as np
import requests

from agents.rag.base_rag_agent import AgentCapability, BaseRAGAgent


class VectorRAGAgent(BaseRAGAgent):
    """
    向量RAG Agent
    使用語義向量檢索 + LLM生成的經典RAG流程
    """

    def __init__(self):
        super().__init__(
            agent_id="vector_rag_agent",
            name="向量RAG實驗Agent",
            rag_framework="vector_rag",
            description="基於向量相似度的檢索增強生成實驗",
        )

        # 向量資料庫配置
        self.vector_db_config = {
            "qdrant": {
                "url": "http://localhost:6333",
                "collection": "art_collection",
                "vector_size": 384,
            },
            "chromadb": {
                "url": "http://localhost:8000",
                "collection": "art_collection",
                "api_version": "v1",
            },
        }

        # LLM配置
        self.llm_config = {
            "openai": {"model": "gpt-3.5-turbo", "max_tokens": 1000, "temperature": 0.1},
            "ollama": {
                "base_url": "http://localhost:11435",
                "model": "llama2:7b",
                "max_tokens": 1000,
            },
        }

        # 當前使用的服務
        self.current_vector_db = "qdrant"
        self.current_llm = "ollama"  # 使用本地LLM避免API依賴

    async def _initialize_rag_components(self):
        """初始化向量RAG組件"""
        try:
            # 初始化向量資料庫連接
            await self._initialize_vector_stores()

            # 初始化LLM客戶端
            await self._initialize_llm_clients()

            # 載入embedding模型
            await self._initialize_embedders()

            self.logger.info("向量RAG組件初始化完成")

        except Exception as e:
            self.logger.error(f"組件初始化失敗: {e}")
            raise

    async def _initialize_vector_stores(self):
        """初始化向量資料庫"""
        # Qdrant連接
        try:
            qdrant_url = self.vector_db_config["qdrant"]["url"]
            response = requests.get(f"{qdrant_url}/collections", timeout=5)
            if response.status_code == 200:
                self.vector_stores["qdrant"] = {"url": qdrant_url, "status": "connected"}
                self.logger.info("Qdrant連接成功")
            else:
                self.logger.warning(f"Qdrant連接失敗: {response.status_code}")
        except Exception as e:
            self.logger.warning(f"Qdrant連接錯誤: {e}")

        # ChromaDB連接測試
        try:
            chromadb_url = self.vector_db_config["chromadb"]["url"]
            response = requests.get(f"{chromadb_url}/api/v1/heartbeat", timeout=5)
            if response.status_code == 200:
                self.vector_stores["chromadb"] = {"url": chromadb_url, "status": "connected"}
                self.logger.info("ChromaDB連接成功")
        except Exception as e:
            self.logger.warning(f"ChromaDB連接錯誤: {e}")

    async def _initialize_llm_clients(self):
        """初始化LLM客戶端"""
        # Ollama客戶端測試
        try:
            ollama_url = self.llm_config["ollama"]["base_url"]
            response = requests.get(f"{ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                self.llm_clients["ollama"] = {"base_url": ollama_url, "status": "connected"}
                self.logger.info("Ollama連接成功")
        except Exception as e:
            self.logger.warning(f"Ollama連接錯誤: {e}")

    async def _initialize_embedders(self):
        """初始化embedding模型"""
        # 這裡可以初始化本地embedding模型
        # 為了示例，我們使用模擬embedding
        self.embedders["default"] = {
            "model": "sentence-transformers/all-MiniLM-L6-v2",
            "dimension": 384,
            "status": "ready",
        }

    async def _register_capabilities(self) -> list[AgentCapability]:
        """註冊向量RAG特定能力"""
        base_capabilities = await super()._register_capabilities()

        vector_capabilities = [
            AgentCapability(
                name="semantic_similarity_search",
                description="基於語義相似度的文檔搜索",
                input_types=["query_vector", "similarity_threshold"],
                output_types=["ranked_documents"],
                resource_requirements={"cpu": 1, "memory": "512MB"},
                estimated_time=3.0,
            ),
            AgentCapability(
                name="vector_indexing",
                description="文檔向量化和索引構建",
                input_types=["documents"],
                output_types=["vector_index"],
                resource_requirements={"cpu": 2, "memory": "2GB"},
                estimated_time=30.0,
            ),
            AgentCapability(
                name="embedding_generation",
                description="文本向量化",
                input_types=["text"],
                output_types=["embedding_vector"],
                resource_requirements={"cpu": 1, "memory": "1GB"},
                estimated_time=1.0,
            ),
        ]

        return base_capabilities + vector_capabilities

    async def retrieve_documents(self, query: str, config: dict[str, Any]) -> list[dict[str, Any]]:
        """基於向量相似度檢索文檔"""
        try:
            # 生成查詢向量
            query_vector = await self._generate_embedding(query)

            # 從向量資料庫檢索
            retrieved_docs = await self._vector_search(
                query_vector,
                config.get("max_retrieved_docs", 5),
                config.get("similarity_threshold", 0.7),
            )

            self.logger.debug(f"檢索到 {len(retrieved_docs)} 個文檔")
            return retrieved_docs

        except Exception as e:
            self.logger.error(f"文檔檢索失敗: {e}")
            return []

    async def generate_answer(
        self, query: str, retrieved_docs: list[dict[str, Any]], config: dict[str, Any]
    ) -> str:
        """基於檢索文檔生成答案"""
        if not retrieved_docs:
            return "抱歉，未能找到相關信息。"

        try:
            # 構建上下文
            context = self._build_context(retrieved_docs)

            # 構建prompt
            prompt = self._build_prompt(query, context)

            # 調用LLM生成答案
            answer = await self._call_llm(prompt, config)

            return answer

        except Exception as e:
            self.logger.error(f"答案生成失敗: {e}")
            return "答案生成過程中出現錯誤。"

    async def _generate_embedding(self, text: str) -> list[float]:
        """生成文本embedding"""
        # 為示例目的，使用模擬embedding
        # 實際實現中會調用真實的embedding模型
        import hashlib
        import random

        # 基於文本內容生成確定性的模擬向量
        text_hash = hashlib.md5(text.encode()).hexdigest()
        random.seed(text_hash)

        # 生成384維度的模擬向量
        vector = [random.uniform(-1, 1) for _ in range(384)]

        # 標準化
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = [v / norm for v in vector]

        return vector

    async def _vector_search(
        self, query_vector: list[float], top_k: int, threshold: float
    ) -> list[dict[str, Any]]:
        """向量相似度搜索"""
        if "qdrant" in self.vector_stores and self.current_vector_db == "qdrant":
            return await self._qdrant_search(query_vector, top_k, threshold)
        elif "chromadb" in self.vector_stores and self.current_vector_db == "chromadb":
            return await self._chromadb_search(query_vector, top_k, threshold)
        else:
            # 返回模擬搜索結果
            return await self._mock_search(query_vector, top_k)

    async def _qdrant_search(
        self, query_vector: list[float], top_k: int, threshold: float
    ) -> list[dict[str, Any]]:
        """Qdrant向量搜索"""
        try:
            qdrant_url = self.vector_stores["qdrant"]["url"]
            collection = self.vector_db_config["qdrant"]["collection"]

            search_payload = {"vector": query_vector, "limit": top_k, "score_threshold": threshold}

            response = requests.post(
                f"{qdrant_url}/collections/{collection}/points/search",
                json=search_payload,
                timeout=10,
            )

            if response.status_code == 200:
                results = response.json()
                documents = []

                for hit in results.get("result", []):
                    doc = {
                        "id": hit.get("id"),
                        "score": hit.get("score", 0),
                        "content": hit.get("payload", {}).get("content", ""),
                        "metadata": hit.get("payload", {}),
                        "source": "qdrant",
                    }
                    documents.append(doc)

                return documents

        except Exception as e:
            self.logger.error(f"Qdrant搜索失敗: {e}")

        # 失敗時返回模擬結果
        return await self._mock_search(query_vector, top_k)

    async def _chromadb_search(
        self, query_vector: list[float], top_k: int, threshold: float
    ) -> list[dict[str, Any]]:
        """ChromaDB向量搜索"""
        # ChromaDB搜索實現
        # 這裡實現ChromaDB的具體搜索邏輯
        return await self._mock_search(query_vector, top_k)

    async def _mock_search(self, query_vector: list[float], top_k: int) -> list[dict[str, Any]]:
        """模擬搜索結果"""
        mock_documents = [
            {
                "id": "doc_001",
                "score": 0.95,
                "content": "蒙娜麗莎是達文西創作的著名肖像畫，以神秘微笑聞名於世。這幅畫展現了文藝復興時期的藝術技巧和人文精神。",
                "metadata": {
                    "title": "蒙娜麗莎",
                    "artist": "達文西",
                    "period": "文藝復興",
                    "year": 1503,
                },
                "source": "mock",
            },
            {
                "id": "doc_002",
                "score": 0.87,
                "content": "星夜是梵高的代表作品，以旋渦狀的筆觸描繪夜空，體現了後印象派的藝術風格和畫家的情感表達。",
                "metadata": {"title": "星夜", "artist": "梵高", "period": "後印象派", "year": 1889},
                "source": "mock",
            },
            {
                "id": "doc_003",
                "score": 0.82,
                "content": "羅浮宮是世界上最著名的藝術博物館之一，收藏了包括蒙娜麗莎在內的眾多藝術珍品。",
                "metadata": {
                    "title": "羅浮宮藏品",
                    "type": "museum_collection",
                    "location": "巴黎",
                },
                "source": "mock",
            },
        ]

        # 根據top_k返回相應數量的結果
        return mock_documents[: min(top_k, len(mock_documents))]

    def _build_context(self, retrieved_docs: list[dict[str, Any]]) -> str:
        """構建檢索文檔的上下文"""
        context_parts = []

        for i, doc in enumerate(retrieved_docs, 1):
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})

            # 添加元數據信息
            metadata_str = ""
            if metadata:
                metadata_parts = []
                for key, value in metadata.items():
                    if key != "content":
                        metadata_parts.append(f"{key}: {value}")
                if metadata_parts:
                    metadata_str = f" ({', '.join(metadata_parts)})"

            context_parts.append(f"文檔 {i}{metadata_str}:\n{content}")

        return "\n\n".join(context_parts)

    def _build_prompt(self, query: str, context: str) -> str:
        """構建LLM prompt"""
        prompt = f"""基於以下藝術史相關文檔信息，回答用戶問題。請提供準確、詳細的答案。

相關文檔:
{context}

用戶問題: {query}

請基於以上文檔信息回答問題。如果文檔中沒有足夠信息，請說明並提供你所知道的相關信息。

回答:"""

        return prompt

    async def _call_llm(self, prompt: str, config: dict[str, Any]) -> str:
        """調用LLM生成答案"""
        if "ollama" in self.llm_clients and self.current_llm == "ollama":
            return await self._call_ollama(prompt, config)
        else:
            # 返回模擬回答
            return await self._mock_llm_response(prompt)

    async def _call_ollama(self, prompt: str, config: dict[str, Any]) -> str:
        """調用Ollama生成答案"""
        try:
            ollama_url = self.llm_clients["ollama"]["base_url"]
            model = self.llm_config["ollama"]["model"]

            payload = {
                "model": model,
                "prompt": prompt,
                "options": {
                    "num_predict": config.get("max_tokens", 1000),
                    "temperature": config.get("temperature", 0.1),
                },
                "stream": False,
            }

            response = requests.post(f"{ollama_url}/api/generate", json=payload, timeout=30)

            if response.status_code == 200:
                result = response.json()
                return result.get("response", "無法生成回答")

        except Exception as e:
            self.logger.error(f"Ollama調用失敗: {e}")

        # 失敗時返回模擬回答
        return await self._mock_llm_response(prompt)

    async def _mock_llm_response(self, prompt: str) -> str:
        """模擬LLM回答"""
        # 簡單的關鍵詞匹配回答
        if "蒙娜麗莎" in prompt or "達文西" in prompt:
            return "蒙娜麗莎是達文西創作的世界著名肖像畫，創作於1503-1519年間。這幅畫以其神秘的微笑和精湛的繪畫技巧聞名於世，現收藏在法國羅浮宮博物館。"

        elif "星夜" in prompt or "梵高" in prompt:
            return "星夜是荷蘭後印象派畫家梵高於1889年創作的油畫作品。畫作以旋渦狀的筆觸描繪夜空，展現了畫家獨特的藝術風格和內心的情感世界。"

        elif "羅浮宮" in prompt:
            return "羅浮宮是位於法國巴黎的世界著名藝術博物館，收藏了大量珍貴的藝術作品，包括蒙娜麗莎、維納斯雕像等世界級藝術珍品。"

        elif "印象派" in prompt:
            return "印象派是19世紀後期興起的藝術流派，強調光線和色彩的表現，代表畫家包括莫奈、雷諾瓦、德加等。"

        else:
            return "基於提供的文檔信息，我可以為您提供相關的藝術史知識。請提供更具體的問題以獲得更準確的回答。"

    async def process_batch_queries(
        self, queries: list[str], config: dict[str, Any] = None
    ) -> dict[str, Any]:
        """批量處理查詢"""
        results = []
        start_time = datetime.now()

        for i, query in enumerate(queries):
            try:
                result = await self.process_single_query(query, config)
                results.append(result)

                # 進度報告
                progress = ((i + 1) / len(queries)) * 100
                self.logger.info(f"批量查詢進度: {progress:.1f}%")

            except Exception as e:
                self.logger.error(f"批量查詢中的查詢失敗: {e}")
                results.append({"query": query, "error": str(e), "success": False})

        total_time = (datetime.now() - start_time).total_seconds()

        return {
            "total_queries": len(queries),
            "successful_queries": sum(1 for r in results if r.get("success", False)),
            "failed_queries": sum(1 for r in results if not r.get("success", False)),
            "total_time": total_time,
            "avg_time_per_query": total_time / len(queries) if queries else 0,
            "results": results,
        }

    def switch_vector_db(self, db_name: str):
        """切換向量資料庫"""
        if db_name in self.vector_stores:
            self.current_vector_db = db_name
            self.logger.info(f"切換到向量資料庫: {db_name}")
        else:
            raise ValueError(f"向量資料庫 {db_name} 未配置")

    def switch_llm(self, llm_name: str):
        """切換LLM"""
        if llm_name in ["ollama", "openai"]:
            self.current_llm = llm_name
            self.logger.info(f"切換到LLM: {llm_name}")
        else:
            raise ValueError(f"LLM {llm_name} 不支持")

    def get_current_configuration(self) -> dict[str, Any]:
        """獲取當前配置"""
        return {
            "vector_db": self.current_vector_db,
            "llm": self.current_llm,
            "vector_db_config": self.vector_db_config.get(self.current_vector_db, {}),
            "llm_config": self.llm_config.get(self.current_llm, {}),
            "available_vector_stores": list(self.vector_stores.keys()),
            "available_llms": list(self.llm_clients.keys()),
        }
