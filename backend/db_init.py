import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from database.connection import DATABASE_URL, Base
from database.models import *

async def init_db():
    print(f"Connecting to DB: {DATABASE_URL}")
    print("Creating database tables...")
    
    # Create an isolated engine just for setup
    setup_engine = create_async_engine(DATABASE_URL, echo=True)
    
    try:
        async with setup_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("Database tables created successfully.")
    except Exception as e:
        print(f"Failed to create tables: {e}")
    finally:
        await setup_engine.dispose()

if __name__ == "__main__":
    asyncio.run(init_db())
