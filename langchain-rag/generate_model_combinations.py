#!/usr/bin/env python3
"""
自動生成 RAG+LLM 模型組合
基於已下載的 Ollama 模型和可用的 RAG 策略
"""

import json
from pathlib import Path

# 加載配置
config_path = Path(__file__).parent / "rag_config.json"
with open(config_path, encoding="utf-8") as f:
    config = json.load(f)

# 根據用戶已下載的模型更新配置
available_llms = {
    "llama3.1:8b": {
        "name": "Llama 3.1 8B",
        "display_name": "🦙 Llama 3.1 8B",
        "provider": "ollama",
        "context_length": 131072,
        "temperature_default": 0.1,
        "description": "通用能力強，指令遵循優秀",
    },
    "qwen2.5:7b": {
        "name": "Qwen 2.5 7B",
        "display_name": "🔮 Qwen 2.5 7B",
        "provider": "ollama",
        "context_length": 32768,
        "temperature_default": 0.2,
        "description": "中文優化，平衡性能",
    },
    "qwen3:8b": {
        "name": "Qwen 3 8B",
        "display_name": "🔮 Qwen 3 8B",
        "provider": "ollama",
        "context_length": 32768,
        "temperature_default": 0.2,
        "description": "Qwen 3系列，性能提升",
    },
    "gemma2:2b": {
        "name": "Gemma 2 2B",
        "display_name": "💎 Gemma 2 2B",
        "provider": "ollama",
        "context_length": 8192,
        "temperature_default": 0.3,
        "description": "輕量級模型，快速響應",
    },
    "gemma3:4b": {
        "name": "Gemma 3 4B",
        "display_name": "💎 Gemma 3 4B",
        "provider": "ollama",
        "context_length": 8192,
        "temperature_default": 0.25,
        "description": "Gemma 3系列，平衡性能",
    },
    "deepseek-r1:8b": {
        "name": "DeepSeek-R1 8B",
        "display_name": "🧠 DeepSeek-R1 8B",
        "provider": "ollama",
        "context_length": 32768,
        "temperature_default": 0.15,
        "description": "專注推理，邏輯思維優秀",
    },
    "llama3-graph-rag:latest": {
        "name": "Llama 3 Graph RAG",
        "display_name": "🕸️ Llama 3 Graph RAG",
        "provider": "ollama",
        "context_length": 131072,
        "temperature_default": 0.1,
        "description": "圖譜RAG專用優化模型",
    },
}

# RAG 策略
rag_strategies = {
    "vector_only": {
        "name": "Vector Only RAG",
        "display_name": "🔍 向量RAG",
        "emoji": "🔍",
        "description": "純向量語義檢索",
    },
    "graph_only": {
        "name": "Graph Only RAG",
        "display_name": "🕸️ 圖譜RAG",
        "emoji": "🕸️",
        "description": "知識圖譜檢索",
    },
    "hybrid_balanced": {
        "name": "Hybrid Balanced RAG",
        "display_name": "⚖️ 混合RAG",
        "emoji": "⚖️",
        "description": "向量+圖譜混合",
    },
    "advanced_rag": {
        "name": "Advanced RAG",
        "display_name": "🎯 Advanced RAG",
        "emoji": "🎯",
        "description": "多級檢索重排",
    },
    "agentic_rag": {
        "name": "Agentic RAG",
        "display_name": "🤖 Agentic RAG",
        "emoji": "🤖",
        "description": "智能代理推理",
    },
    "self_rag": {
        "name": "Self RAG",
        "display_name": "🔄 Self RAG",
        "emoji": "🔄",
        "description": "自我反思迭代",
    },
}


# 生成所有組合
def generate_combinations():
    combinations = []

    for llm_id, llm_config in available_llms.items():
        for rag_id, rag_config in rag_strategies.items():
            # 生成組合 ID
            combo_id = f"{llm_id}@{rag_id}"

            # 生成顯示名稱
            llm_name = llm_config["display_name"]
            rag_name = rag_config["display_name"]

            combination = {
                "id": combo_id,
                "name": f"{llm_name} + {rag_name}",
                "display_name": f"{rag_config['emoji']} {llm_config['name']} + {rag_config['name']}",
                "description": f"{llm_config['description']} + {rag_config['description']}",
                "llm_model": llm_id,
                "rag_strategy": rag_id,
                "enabled": True,
                "meta": {"llm": llm_config, "rag": rag_config},
                "params": {
                    "temperature": llm_config["temperature_default"],
                    "max_tokens": min(2048, llm_config["context_length"] // 4),
                    "use_rag": True,
                },
            }

            combinations.append(combination)

    return combinations


# 生成組合
combinations = generate_combinations()

# 更新配置
config["llm_models"] = available_llms
config["rag_strategies"] = rag_strategies
config["model_combinations"] = combinations

# 保存配置
with open(config_path, "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print(f"✅ 已生成 {len(combinations)} 個 RAG+LLM 組合")
print(f"   LLM 模型: {len(available_llms)} 個")
print(f"   RAG 策略: {len(rag_strategies)} 個")
print(f"   總組合: {len(combinations)} 個")
print(f"\n配置已保存到: {config_path}")

# 生成 OpenWebUI 模型配置
openwebui_models = {"models": [], "default": "llama3.1:8b@hybrid_balanced"}

for combo in combinations[:30]:  # 限制前30個組合
    model_config = {
        "id": combo["id"],
        "name": combo["display_name"],
        "description": combo["description"],
        "meta": {
            "base_model": combo["llm_model"],
            "rag_strategy": combo["rag_strategy"],
            "context_length": combo["meta"]["llm"]["context_length"],
            "temperature": combo["params"]["temperature"],
        },
        "params": combo["params"],
    }
    openwebui_models["models"].append(model_config)

# 保存 OpenWebUI 配置
openwebui_config_path = Path(__file__).parent.parent / "openwebui-config" / "models.json"
with open(openwebui_config_path, "w", encoding="utf-8") as f:
    json.dump(openwebui_models, f, indent=2, ensure_ascii=False)

print(f"\n✅ OpenWebUI 配置已保存: {openwebui_config_path}")
print(f"   包含 {len(openwebui_models['models'])} 個模型組合")

# 顯示前 5 個組合示例
print("\n📋 組合示例:")
for i, combo in enumerate(combinations[:5], 1):
    print(f"   {i}. {combo['display_name']}")

print("\n🎉 配置生成完成！")
