"""FastAPI主应用"""

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from ..config import get_settings, validate_config, print_config
from .routes import trip, poi, map as map_routes

# 静态文件目录：一体化部署时由 Docker 注入；本地开发为空，不影响原有行为
STATIC_DIR = os.environ.get("STATIC_DIR", "")

# 获取配置
settings = get_settings()

# 创建FastAPI应用
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="基于HelloAgents框架的智能旅行规划助手API",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(trip.router, prefix="/api")
app.include_router(poi.router, prefix="/api")
app.include_router(map_routes.router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    print("\n" + "="*60)
    print(f"🚀 {settings.app_name} v{settings.app_version}")
    print("="*60)
    
    # 打印配置信息
    print_config()
    
    # 验证配置
    try:
        validate_config()
        print("\n✅ 配置验证通过")
    except ValueError as e:
        print(f"\n❌ 配置验证失败:\n{e}")
        print("\n请检查.env文件并确保所有必要的配置项都已设置")
        raise
    
    print("\n" + "="*60)
    print("📚 API文档: http://localhost:8000/docs")
    print("📖 ReDoc文档: http://localhost:8000/redoc")
    print("="*60 + "\n")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    print("\n" + "="*60)
    print("👋 应用正在关闭...")
    print("="*60 + "\n")


def _serve_index():
    """一体化模式下返回前端 index.html；否则返回 None"""
    if STATIC_DIR and os.path.isfile(os.path.join(STATIC_DIR, "index.html")):
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
    return None


@app.get("/")
async def root():
    """根路径：一体化模式返回前端首页，否则返回 API 信息"""
    index = _serve_index()
    if index is not None:
        return index
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version
    }


# ===== 一体化部署：静态文件托管 + SPA 路由兜底 =====
# 仅当 STATIC_DIR 存在时启用，本地开发完全不受影响
if STATIC_DIR and os.path.isdir(STATIC_DIR):
    _assets_dir = os.path.join(STATIC_DIR, "assets")
    if os.path.isdir(_assets_dir):
        # 托管 Vite 构建产物（带哈希的 js/css/图片等）
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        """SPA 兜底：非 API 路径返回对应静态文件，找不到则返回 index.html"""
        # 放行 API 路径的 404（避免把 API 错误响应当成前端页面）
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        # 1. 先尝试匹配具体静态文件（favicon、图片等）
        candidate = os.path.join(STATIC_DIR, full_path)
        if os.path.isfile(candidate):
            return FileResponse(candidate)
        # 2. 找不到 → 返回 index.html，交给 Vue Router 处理前端路由
        index = _serve_index()
        if index is not None:
            return index
        raise HTTPException(status_code=404, detail="Not Found")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )

