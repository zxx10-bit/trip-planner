"""HelloAgents智能旅行助手 - 后端应用"""

# ============ 兼容性补丁 ============
# fastmcp 2.14.7 从 mcp.server.auth.provider 导入 IdentityAssertionParams,
# 但 mcp 1.30.0 没有这个类。这个类只在服务端 OAuth 代理模块用到,
# 客户端(MCPClient)完全不需要。注入一个空类让导入通过即可。
try:
    import mcp.server.auth.provider as _auth_provider
    if not hasattr(_auth_provider, "IdentityAssertionParams"):
        class IdentityAssertionParams:
            """兼容性占位类,仅服务端OAuth代理使用,客户端不需要"""
            pass
        _auth_provider.IdentityAssertionParams = IdentityAssertionParams
except Exception:
    pass
# ============ 补丁结束 ============

__version__ = "1.0.0"

