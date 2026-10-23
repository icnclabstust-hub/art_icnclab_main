"""
MCP (Model Context Protocol) 工具集成模塊

這個模塊提供了將MCP工具集成到Agent框架中的完整解決方案，包括：
- MCP工具註冊和發現
- 工具代理和通信
- Agent集成和協調

主要組件：
- mcp_tool_registry: MCP工具註冊表和管理
- mcp_tool_proxy: MCP工具代理和通信接口
- mcp_agent_integration: Agent與MCP工具的集成層

使用方式：
```python
from mcp import get_mcp_registry, get_proxy_manager, get_mcp_integration_manager

# 獲取MCP組件
registry = get_mcp_registry()
proxy_manager = get_proxy_manager()
integration_manager = get_mcp_integration_manager()

# 初始化MCP系統
await integration_manager.initialize_mcp_system()
```
"""

from .mcp_agent_integration import (
    MCPAgentFactory,
    MCPCapableAgent,
    MCPIntegrationManager,
    MCPMasterAgent,
    MCPMultimodalAgent,
    MCPVectorRAGAgent,
    get_mcp_integration_manager,
)
from .mcp_tool_proxy import (
    HTTPToolProxy,
    LLMToolProxy,
    MCPProxyManager,
    MCPToolProxy,
    MultimodalToolProxy,
    ProxyCallType,
    ProxyRequest,
    ProxyResponse,
    VectorDBToolProxy,
    get_proxy_manager,
)
from .mcp_tool_registry import (
    MCPToolInstance,
    MCPToolRegistry,
    MCPToolSpec,
    MCPToolStatus,
    MCPToolType,
    get_mcp_registry,
)

__version__ = "1.0.0"
__author__ = "Art History Database Team"
__description__ = "MCP工具集成模塊 - 為Agent框架提供MCP工具支持"

# 導出主要組件
__all__ = [
    # Registry components
    "MCPToolRegistry",
    "MCPToolSpec",
    "MCPToolInstance",
    "MCPToolType",
    "MCPToolStatus",
    "get_mcp_registry",
    # Proxy components
    "MCPToolProxy",
    "MCPProxyManager",
    "ProxyRequest",
    "ProxyResponse",
    "ProxyCallType",
    "HTTPToolProxy",
    "LLMToolProxy",
    "VectorDBToolProxy",
    "MultimodalToolProxy",
    "get_proxy_manager",
    # Integration components
    "MCPCapableAgent",
    "MCPMasterAgent",
    "MCPVectorRAGAgent",
    "MCPMultimodalAgent",
    "MCPAgentFactory",
    "MCPIntegrationManager",
    "get_mcp_integration_manager",
]
