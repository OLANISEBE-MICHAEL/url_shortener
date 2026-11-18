from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings

# creating the database engine

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True # seeing the raw sql in the terminal 
)

# creating the session maker - isolation per user
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# dependency to get a DB session for a route
async def get_db():
    async with SessionLocal() as session:
        yield session