from fastapi import FastAPI
from app.core.database import engine
from app.models import Base

app = FastAPI(title="URL Shortener API")

@app.on_event("startup") 
async def init_db():
    """runs this function as soon as the server starts, connects to the database using a context manager
        and creates all the tables defined if they do not exist
    """
    async with engine.begin() as conn: 
        await conn.run_sync(Base.metadata.create_all) # 

@app.get("/health")
async def health_check():
    return {"status": "ok"}