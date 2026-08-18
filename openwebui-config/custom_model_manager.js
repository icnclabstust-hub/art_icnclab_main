/**
 * OpenWebUI 自定義模型管理器
 * 用於處理RAG+LLM組合模型的顯示和選擇
 */

class CustomModelManager {
    constructor() {
        this.models = [
            {
                id: "llama3.1:8b@vector_only",
                name: "🔍 Llama 3.1 8B + 向量RAG",
                description: "語義相似度檢索，適合內容相似性查詢",
                base_model: "llama3.1:8b",
                rag_strategy: "vector_only",
                owned_by: "custom"
            },
            {
                id: "llama3.1:8b@graph_only",
                name: "🕸️ Llama 3.1 8B + 圖譜RAG",
                description: "知識圖譜推理，適合關係和結構化查詢",
                base_model: "llama3.1:8b",
                rag_strategy: "graph_only",
                owned_by: "custom"
            },
            {
                id: "llama3.1:8b@hybrid_balanced",
                name: "⚖️ Llama 3.1 8B + 混合RAG",
                description: "平衡混合策略，適合大多數查詢（推薦）",
                base_model: "llama3.1:8b",
                rag_strategy: "hybrid_balanced",
                owned_by: "custom"
            },
            {
                id: "llama3.1:8b@adaptive",
                name: "🧠 Llama 3.1 8B + 自適應RAG",
                description: "基於歷史性能自動選擇最佳策略",
                base_model: "llama3.1:8b",
                rag_strategy: "adaptive",
                owned_by: "custom"
            },
            {
                id: "llama3.1:8b@specialized",
                name: "🎯 Llama 3.1 8B + 專門RAG",
                description: "基於查詢類型自動選擇專門策略",
                base_model: "llama3.1:8b",
                rag_strategy: "specialized",
                owned_by: "custom"
            },
            {
                id: "qwen3:4b@vector_only",
                name: "🔍 Qwen3 4B + 向量RAG",
                description: "快速向量檢索，中文表現優秀",
                base_model: "qwen3:4b",
                rag_strategy: "vector_only",
                owned_by: "custom"
            },
            {
                id: "qwen3:4b@hybrid_balanced",
                name: "⚖️ Qwen3 4B + 混合RAG",
                description: "快速混合檢索，適合日常中文問答",
                base_model: "qwen3:4b",
                rag_strategy: "hybrid_balanced",
                owned_by: "custom"
            },
            {
                id: "llama3.1:8b@no_rag",
                name: "💬 Llama 3.1 8B (純模型)",
                description: "不使用RAG，僅基於預訓練知識",
                base_model: "llama3.1:8b",
                rag_strategy: "none",
                owned_by: "custom"
            },
            {
                id: "qwen3:4b@no_rag",
                name: "💬 Qwen3 4B (純模型)",
                description: "不使用RAG，快速基礎對話",
                base_model: "qwen3:4b",
                rag_strategy: "none",
                owned_by: "custom"
            }
        ];

        this.currentModel = "llama3.1:8b@hybrid_balanced";
        this.init();
    }

    init() {
        // 等待頁面加載完成
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.injectModelSelector());
        } else {
            this.injectModelSelector();
        }
    }

    injectModelSelector() {
        // 尋找模型選擇器
        const modelSelector = document.querySelector('[data-testid="model-selector"]') ||
                            document.querySelector('.model-selector') ||
                            document.querySelector('select[name="model"]') ||
                            document.querySelector('#model-select');

        if (modelSelector) {
            this.enhanceModelSelector(modelSelector);
        } else {
            // 如果找不到選擇器，嘗試創建一個
            this.createCustomModelSelector();
        }
    }

    enhanceModelSelector(selector) {
        // 清空現有選項
        selector.innerHTML = '';

        // 添加自定義模型選項
        this.models.forEach(model => {
            const option = document.createElement('option');
            option.value = model.id;
            option.textContent = model.name;
            option.title = model.description;

            if (model.id === this.currentModel) {
                option.selected = true;
            }

            selector.appendChild(option);
        });

        // 添加變更事件監聽
        selector.addEventListener('change', (e) => {
            this.handleModelChange(e.target.value);
        });
    }

    createCustomModelSelector() {
        // 創建自定義模型選擇器
        const container = document.createElement('div');
        container.className = 'custom-model-selector';
        container.innerHTML = `
            <select id="rag-model-selector" class="bg-gray-100 dark:bg-gray-800 rounded-lg px-3 py-2 text-sm">
                ${this.models.map(model => `
                    <option value="${model.id}" ${model.id === this.currentModel ? 'selected' : ''}>
                        ${model.name}
                    </option>
                `).join('')}
            </select>
        `;

        // 找到合適的插入位置
        const header = document.querySelector('header') ||
                      document.querySelector('.header') ||
                      document.querySelector('.navbar') ||
                      document.body.firstElementChild;

        if (header) {
            header.appendChild(container);

            // 添加事件監聽
            const selector = container.querySelector('#rag-model-selector');
            selector.addEventListener('change', (e) => {
                this.handleModelChange(e.target.value);
            });
        }
    }

    handleModelChange(modelId) {
        this.currentModel = modelId;
        const model = this.models.find(m => m.id === modelId);

        if (model) {
            console.log(`已切換到: ${model.name}`);
            console.log(`RAG策略: ${model.rag_strategy}`);
            console.log(`基礎模型: ${model.base_model}`);

            // 儲存選擇到localStorage
            localStorage.setItem('selectedRAGModel', modelId);

            // 觸發自定義事件
            window.dispatchEvent(new CustomEvent('ragModelChanged', {
                detail: { model, modelId }
            }));

            // 顯示通知
            this.showNotification(`已切換到 ${model.name}`);
        }
    }

    showNotification(message) {
        // 創建通知元素
        const notification = document.createElement('div');
        notification.className = 'fixed top-4 right-4 bg-blue-600 text-white px-4 py-2 rounded-lg shadow-lg z-50';
        notification.textContent = message;

        document.body.appendChild(notification);

        // 3秒後自動消失
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }

    getCurrentModel() {
        return this.models.find(m => m.id === this.currentModel);
    }

    getModels() {
        return this.models;
    }
}

// 全域實例化
window.customModelManager = new CustomModelManager();

// 監聽RAG模型變更事件
window.addEventListener('ragModelChanged', (event) => {
    const { model } = event.detail;
    console.log('RAG模型已變更:', model);

    // 更新頁面標題或其他UI元素
    const titleElement = document.querySelector('title');
    if (titleElement) {
        titleElement.textContent = `${model.name} - 藝術史資料庫 AI 助手`;
    }
});

// 頁面載入時恢復上次選擇的模型
document.addEventListener('DOMContentLoaded', () => {
    const savedModel = localStorage.getItem('selectedRAGModel');
    if (savedModel && window.customModelManager) {
        window.customModelManager.currentModel = savedModel;
    }
});

console.log('✅ 自定義RAG+LLM組合選擇器已載入');
console.log('📋 可用模型組合數量:', window.customModelManager?.getModels().length || 0);