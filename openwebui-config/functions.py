"""
OpenWebUI 自定義函數 - RAG策略切換支援
處理不同RAG+LLM組合的查詢請求
"""

import requests


class RagStrategyHandler:
    def __init__(self):
        self.rag_api_url = "http://host.docker.internal:8002"
        self.ollama_api_url = "http://host.docker.internal:11434"

    def parse_model_id(self, model_id: str) -> tuple:
        """
        解析模型ID，提取基礎模型和RAG策略
        例如: "llama3.1:8b@vector_only" -> ("llama3.1:8b", "vector_only")
        """
        if "@" in model_id:
            base_model, rag_strategy = model_id.split("@", 1)
            return base_model, rag_strategy
        return model_id, "none"

    def query_with_rag(self, query: str, rag_strategy: str, params: dict) -> str:
        """
        使用指定RAG策略查詢
        """
        try:
            if rag_strategy == "none":
                return None  # 不使用RAG，直接用LLM

            # 準備RAG查詢請求
            rag_request = {
                "query": query,
                "strategy": rag_strategy,
                "top_k": params.get("top_k", 5),
                "include_sources": True,
                "timeout": params.get("timeout", 30),
            }

            # 發送RAG查詢
            response = requests.post(f"{self.rag_api_url}/query", json=rag_request, timeout=30)

            if response.status_code == 200:
                rag_result = response.json()

                # 構建增強的提示詞
                context = ""
                if rag_result.get("sources"):
                    context = "\\n\\n相關資料:\\n"
                    for i, source in enumerate(rag_result["sources"][:3], 1):
                        context += f"{i}. {source.get('title', 'Unknown')}: {source.get('content', '')}[:200]...\\n"

                enhanced_prompt = f"""基於以下藝術史知識庫資料回答問題：

{context}

問題：{query}

請基於上述資料提供專業的藝術史解答，如果資料不足，請說明並提供一般性建議。"""

                return enhanced_prompt

        except Exception as e:
            print(f"RAG查詢失敗: {e}")

        return None

    def query_ollama(self, model: str, prompt: str, params: dict) -> str:
        """
        查詢Ollama模型
        """
        try:
            ollama_request = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": params.get("temperature", 0.1),
                    "num_predict": params.get("max_tokens", 2048),
                },
            }

            response = requests.post(
                f"{self.ollama_api_url}/api/generate", json=ollama_request, timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("response", "")

        except Exception as e:
            print(f"Ollama查詢失敗: {e}")

        return "抱歉，查詢處理失敗，請稍後再試。"


# 全域處理器實例
rag_handler = RagStrategyHandler()


def rag_enhanced_query(query: str, model_id: str = "llama3.1:8b@hybrid_balanced", **kwargs) -> str:
    """
    RAG增強查詢主函數
    這是OpenWebUI調用的主要函數
    """
    try:
        # 解析模型ID和RAG策略
        base_model, rag_strategy = rag_handler.parse_model_id(model_id)

        # 準備參數
        params = {
            "temperature": kwargs.get("temperature", 0.1),
            "max_tokens": kwargs.get("max_tokens", 2048),
            "top_k": kwargs.get("top_k", 5),
            "timeout": kwargs.get("timeout", 30),
        }

        # 如果使用RAG，先進行RAG查詢
        enhanced_prompt = query
        if rag_strategy != "none":
            rag_result = rag_handler.query_with_rag(query, rag_strategy, params)
            if rag_result:
                enhanced_prompt = rag_result

        # 查詢LLM
        response = rag_handler.query_ollama(base_model, enhanced_prompt, params)

        # 添加策略標識
        strategy_info = (
            f"\\n\\n---\\n🔧 使用策略: {base_model} + {rag_strategy.replace('_', ' ').title()}"
        )

        return response + strategy_info

    except Exception as e:
        return f"查詢處理失敗: {str(e)}"


# OpenWebUI函數定義
async def main(
    body: dict,
    __user__: dict = None,
    __event_emitter__=None,
) -> str:
    """
    OpenWebUI主要入口函數
    """
    try:
        # 提取參數
        messages = body.get("messages", [])
        model = body.get("model", "llama3.1:8b@hybrid_balanced")

        if not messages:
            return "沒有收到查詢訊息"

        # 獲取最新用戶消息
        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break

        if not user_message:
            return "沒有找到用戶查詢"

        # 處理查詢
        result = rag_enhanced_query(query=user_message, model_id=model, **body)

        return result

    except Exception as e:
        return f"函數執行失敗: {str(e)}"
