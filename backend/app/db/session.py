"""数据库引擎与会话管理"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import get_settings

settings = get_settings()

# SQLite 不支持 QueuePool 的 pool_size/max_overflow 参数，按数据库类型区分配置
if settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs = {}
else:
    engine_kwargs = {"pool_size": 20, "max_overflow": 10, "pool_recycle": 3600}

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    **engine_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入：获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()