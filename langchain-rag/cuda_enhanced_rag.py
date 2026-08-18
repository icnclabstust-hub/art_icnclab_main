#!/usr/bin/env python3
"""
CUDA加速的藝術史RAG系統
利用GPU加速提升檢索和生成準確性
"""

import json
import logging
import time
import warnings
from dataclasses import dataclass

import numpy as np

warnings.filterwarnings("ignore")


# 檢查CUDA環境
def check_cuda_environment():
    """檢查CUDA環境配置"""
    try:
        import torch

        cuda_available = torch.cuda.is_available()
        if cuda_available:
            device_count = torch.cuda.device_count()
            current_device = torch.cuda.current_device()
            device_name = torch.cuda.get_device_name(current_device)
            memory_total = torch.cuda.get_device_properties(current_device).total_memory / 1e9
            return {
                "cuda_available": True,
                "device_count": device_count,
                "current_device": current_device,
                "device_name": device_name,
                "memory_total_gb": memory_total,
                "torch_version": torch.__version__,
            }
        else:
            return {"cuda_available": False, "message": "CUDA not available"}
    except ImportError:
        return {"cuda_available": False, "message": "PyTorch not installed"}


@dataclass
class CUDARAGConfig:
    """CUDA RAG配置"""

    # GPU配置
    device: str = "auto"  # auto, cuda, cpu
    batch_size: int = 32
    max_length: int = 512

    # 嵌入模型配置
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # 向量數據庫配置
    vector_store_type: str = "faiss"  # faiss, chroma
    index_type: str = "IVF"  # Flat, IVF, HNSW

    # 檢索配置
    top_k: int = 10
    similarity_threshold: float = 0.7

    # 生成模型配置
    generator_model: str = "llama3.1:8b"
    temperature: float = 0.7
    max_new_tokens: int = 1024


class CUDAEmbeddingModel:
    """CUDA加速的嵌入模型"""

    def __init__(self, config: CUDARAGConfig):
        self.config = config
        self.device = self._get_device()
        self.model = None
        self.tokenizer = None

        logging.info(f"🔧 初始化CUDA嵌入模型，設備: {self.device}")

    def _get_device(self) -> str:
        """自動選擇最佳設備"""
        if self.config.device == "auto":
            try:
                import torch

                if torch.cuda.is_available():
                    return f"cuda:{torch.cuda.current_device()}"
                else:
                    return "cpu"
            except ImportError:
                return "cpu"
        return self.config.device

    def load_model(self) -> None:
        """加載嵌入模型到GPU"""
        try:
            from sentence_transformers import SentenceTransformer

            logging.info(f"📥 加載嵌入模型: {self.config.embedding_model}")
            self.model = SentenceTransformer(self.config.embedding_model)

            # 移動到GPU
            if "cuda" in self.device:
                self.model = self.model.to(self.device)
                logging.info(f"✅ 模型已移動到GPU: {self.device}")

        except ImportError as e:
            logging.error(f"❌ 缺少依賴: {e}")
            raise
        except Exception as e:
            logging.error(f"❌ 模型加載失敗: {e}")
            raise

    def encode_batch(self, texts: list[str]) -> np.ndarray:
        """批量編碼文本為向量"""
        if self.model is None:
            self.load_model()

        try:
            # 批量處理
            batch_size = self.config.batch_size
            all_embeddings = []

            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]

                # GPU加速編碼
                start_time = time.time()
                embeddings = self.model.encode(
                    batch, batch_size=len(batch), show_progress_bar=False, convert_to_numpy=True
                )
                encoding_time = time.time() - start_time

                all_embeddings.append(embeddings)
                logging.debug(
                    f"📊 批次 {i // batch_size + 1}: {len(batch)} 文本, {encoding_time:.3f}s"
                )

            result = np.vstack(all_embeddings)
            logging.info(f"✅ 編碼完成: {len(texts)} 文本 -> {result.shape}")
            return result

        except Exception as e:
            logging.error(f"❌ 編碼失敗: {e}")
            raise


class CUDAVectorStore:
    """CUDA加速的向量存儲"""

    def __init__(self, config: CUDARAGConfig):
        self.config = config
        self.embedding_model = CUDAEmbeddingModel(config)
        self.index = None
        self.texts = []
        self.metadata = []

    def create_index(self, dimension: int) -> None:
        """創建FAISS索引"""
        try:
            import faiss

            if self.config.index_type == "Flat":
                # 精確搜索，適合小數據集
                self.index = faiss.IndexFlatIP(dimension)  # 內積相似度
            elif self.config.index_type == "IVF":
                # 倒排文件索引，適合大數據集
                nlist = min(100, max(1, len(self.texts) // 10))  # 聚類數量
                quantizer = faiss.IndexFlatIP(dimension)
                self.index = faiss.IndexIVFFlat(quantizer, dimension, nlist)
            elif self.config.index_type == "HNSW":
                # 分層導航小世界，高效近似搜索
                self.index = faiss.IndexHNSWFlat(dimension, 32)

            # 如果有GPU，移動索引到GPU
            if hasattr(faiss, "StandardGpuResources") and "cuda" in self.embedding_model.device:
                try:
                    res = faiss.StandardGpuResources()
                    self.index = faiss.index_cpu_to_gpu(res, 0, self.index)
                    logging.info("✅ FAISS索引已移動到GPU")
                except Exception as e:
                    logging.warning(f"⚠️ GPU索引創建失敗，使用CPU: {e}")

            logging.info(f"✅ 創建{self.config.index_type}索引，維度: {dimension}")

        except ImportError:
            logging.error("❌ FAISS未安裝，請先安裝: pip install faiss-gpu")
            raise

    def add_documents(self, texts: list[str], metadata: list[dict] = None) -> None:
        """添加文檔到向量存儲"""
        if metadata is None:
            metadata = [{"index": i} for i in range(len(texts))]

        logging.info(f"🔄 處理 {len(texts)} 個文檔...")

        # GPU加速編碼
        start_time = time.time()
        embeddings = self.embedding_model.encode_batch(texts)
        encoding_time = time.time() - start_time

        # 創建索引（如果還沒有）
        if self.index is None:
            self.create_index(embeddings.shape[1])

        # 訓練索引（對於IVF）
        if self.config.index_type == "IVF" and not self.index.is_trained:
            self.index.train(embeddings.astype("float32"))

        # 添加向量
        self.index.add(embeddings.astype("float32"))
        self.texts.extend(texts)
        self.metadata.extend(metadata)

        logging.info(f"✅ 添加完成: {len(texts)} 文檔, 編碼時間: {encoding_time:.2f}s")

    def search(self, query: str, top_k: int = None) -> list[dict]:
        """搜索相似文檔"""
        if top_k is None:
            top_k = self.config.top_k

        # 編碼查詢
        query_embedding = self.embedding_model.encode_batch([query])

        # 搜索
        start_time = time.time()
        scores, indices = self.index.search(query_embedding.astype("float32"), top_k)
        search_time = time.time() - start_time

        # 準備結果
        results = []
        for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
            if idx >= 0 and score >= self.config.similarity_threshold:
                results.append(
                    {
                        "text": self.texts[idx],
                        "score": float(score),
                        "metadata": self.metadata[idx],
                        "rank": i + 1,
                    }
                )

        logging.info(f"🔍 搜索完成: {len(results)} 結果, 搜索時間: {search_time:.3f}s")
        return results

    def save_index(self, filepath: str) -> None:
        """保存索引到文件"""
        try:
            import faiss

            # 如果索引在GPU上，先移回CPU
            if hasattr(self.index, "device") and self.index.device >= 0:
                cpu_index = faiss.index_gpu_to_cpu(self.index)
                faiss.write_index(cpu_index, filepath)
            else:
                faiss.write_index(self.index, filepath)

            # 保存元數據
            metadata_file = filepath.replace(".index", "_metadata.json")
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "texts": self.texts,
                        "metadata": self.metadata,
                        "config": self.config.__dict__,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

            logging.info(f"💾 索引已保存: {filepath}")

        except Exception as e:
            logging.error(f"❌ 索引保存失敗: {e}")


class CUDAEnhancedRAG:
    """CUDA增強的RAG系統"""

    def __init__(self, config: CUDARAGConfig = None):
        self.config = config or CUDARAGConfig()
        self.vector_store = CUDAVectorStore(self.config)
        self.performance_stats = {
            "total_queries": 0,
            "total_search_time": 0,
            "total_generation_time": 0,
            "gpu_utilization": [],
        }

        # 檢查CUDA環境
        self.cuda_info = check_cuda_environment()
        logging.info(f"🔧 CUDA環境: {self.cuda_info}")

    def initialize_from_documents(self, documents: list[dict]) -> None:
        """從文檔初始化RAG系統"""
        logging.info(f"🚀 初始化CUDA RAG系統，文檔數: {len(documents)}")

        # 準備文本和元數據
        texts = []
        metadata = []

        for doc in documents:
            if "content" in doc:
                texts.append(doc["content"])
                metadata.append({k: v for k, v in doc.items() if k != "content"})
            elif "text" in doc:
                texts.append(doc["text"])
                metadata.append({k: v for k, v in doc.items() if k != "text"})

        # 添加到向量存儲
        self.vector_store.add_documents(texts, metadata)

        logging.info("✅ CUDA RAG系統初始化完成")

    def query(self, question: str, top_k: int = None) -> dict:
        """執行RAG查詢"""
        start_time = time.time()

        # 檢索相關文檔
        search_start = time.time()
        results = self.vector_store.search(question, top_k)
        search_time = time.time() - search_start

        # 準備上下文
        context = "\n\n".join([r["text"][:500] for r in results[:5]])

        # 生成回答（這裡使用簡化的模板，實際可以集成LLM）
        generation_start = time.time()
        answer = self._generate_answer(question, context, results)
        generation_time = time.time() - generation_start

        # 更新性能統計
        total_time = time.time() - start_time
        self.performance_stats["total_queries"] += 1
        self.performance_stats["total_search_time"] += search_time
        self.performance_stats["total_generation_time"] += generation_time

        return {
            "question": question,
            "answer": answer,
            "sources": results,
            "performance": {
                "search_time": search_time,
                "generation_time": generation_time,
                "total_time": total_time,
                "cuda_info": self.cuda_info,
            },
        }

    def _generate_answer(self, question: str, context: str, sources: list[dict]) -> str:
        """生成回答（簡化版）"""
        if not sources:
            return "抱歉，我找不到相關的藝術史資料來回答您的問題。"

        # 基於檢索結果的簡單回答生成
        answer = f"根據藝術史資料庫的檢索結果，關於「{question}」：\n\n"

        for i, source in enumerate(sources[:3], 1):
            score = source.get("score", 0)
            text = source.get("text", "")[:200]
            answer += f"{i}. (相似度: {score:.3f}) {text}...\n\n"

        answer += f"以上信息來自 {len(sources)} 個相關文檔，使用CUDA GPU加速檢索。"

        return answer

    def get_performance_summary(self) -> dict:
        """獲取性能總結"""
        stats = self.performance_stats
        if stats["total_queries"] > 0:
            avg_search_time = stats["total_search_time"] / stats["total_queries"]
            avg_generation_time = stats["total_generation_time"] / stats["total_queries"]
        else:
            avg_search_time = avg_generation_time = 0

        return {
            "cuda_available": self.cuda_info.get("cuda_available", False),
            "device_info": self.cuda_info,
            "total_queries": stats["total_queries"],
            "average_search_time": avg_search_time,
            "average_generation_time": avg_generation_time,
            "vector_store_size": len(self.vector_store.texts),
        }


def main():
    """測試CUDA RAG系統"""
    logging.basicConfig(level=logging.INFO)

    print("🚀 CUDA增強藝術史RAG系統測試")
    print("=" * 50)

    # 檢查CUDA環境
    cuda_info = check_cuda_environment()
    print(f"🔧 CUDA環境: {cuda_info}")

    if not cuda_info.get("cuda_available", False):
        print("⚠️ CUDA不可用，將使用CPU模式")

    # 配置
    config = CUDARAGConfig(device="auto", batch_size=16, top_k=5)

    # 創建RAG系統
    rag = CUDAEnhancedRAG(config)

    # 測試文檔
    test_docs = [
        {
            "content": "Leonardo da Vinci created the famous painting Mona Lisa during the Renaissance period.",
            "title": "Mona Lisa",
            "artist": "Leonardo da Vinci",
            "period": "Renaissance",
        },
        {
            "content": "Vincent van Gogh painted The Starry Night in 1889, representing Post-Impressionism.",
            "title": "The Starry Night",
            "artist": "Vincent van Gogh",
            "period": "Post-Impressionism",
        },
    ]

    try:
        # 初始化
        rag.initialize_from_documents(test_docs)

        # 測試查詢
        result = rag.query("告訴我關於文藝復興時期的藝術作品")

        print("\n📋 查詢結果:")
        print(f"問題: {result['question']}")
        print(f"回答: {result['answer']}")
        print(
            f"性能: 搜索 {result['performance']['search_time']:.3f}s, "
            f"生成 {result['performance']['generation_time']:.3f}s"
        )

        # 性能總結
        summary = rag.get_performance_summary()
        print("\n📊 系統性能總結:")
        print(f"CUDA可用: {summary['cuda_available']}")
        print(f"總查詢數: {summary['total_queries']}")
        print(f"向量庫大小: {summary['vector_store_size']}")

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
