"""AskKB 企业级 RAG 知识库平台——FastAPI 主入口"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.base import Base
from app.db.session import engine
from app.middleware.trace import TraceMiddleware

# ─── API 路由 ───
from app.api.auth import router as auth_router
from app.api.kb import router as kb_router
from app.api.document import router as document_router
from app.api.qa import router as qa_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时建表、关闭时清理"""
    # 启动
    os.makedirs("data", exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} 启动成功")
    print(f"   环境: {settings.ENVIRONMENT}")
    print(f"   模型: {settings.LLM_MODEL} | Embedding: {settings.EMBEDDING_MODEL} | Rerank: {settings.RERANK_MODEL}")
    print(f"   向量库: {settings.VECTOR_STORE_TYPE}")
    yield
    # 关闭
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="智汇 · 企业级 RAG 知识库平台 | 双通道架构 (employee_kb / cs_agent)",
    lifespan=lifespan,
)

# ─── 中间件 ───
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TraceMiddleware)

# ─── 注册路由 ───
app.include_router(auth_router)
app.include_router(kb_router)
app.include_router(document_router)
app.include_router(qa_router)


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": __import__("datetime").datetime.now().isoformat()}


# ─── 开发启动入口 ───
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
    )