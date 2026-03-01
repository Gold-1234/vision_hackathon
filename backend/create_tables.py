import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from database.connection import Base
from database.models import *

# Connection details
DB_USER = os.getenv("POSTGRES_USER", "krishna")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "n0password")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "vision_ai")

# Async URL matching the main codebase
ASYNC_DB_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

async def setup_db():
    print(f"Connecting to {ASYNC_DB_URL}...")
    engine = create_async_engine(ASYNC_DB_URL, echo=True)
    try:
        async with engine.begin() as conn:
            print("Creating tables in vision_ai database...")
            await conn.run_sync(Base.metadata.create_all)
        print("Tables created successfully!")
    except Exception as e:
        print(f"Failed to create tables: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(setup_db())
