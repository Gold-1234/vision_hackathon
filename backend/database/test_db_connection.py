import asyncio
import os
import sys

# Add the parent directory to sys.path so we can import from database
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import AsyncSessionLocal, engine
from database.models import Base
from database.repository import SafetyRepository

async def test_connection():
    print("Testing database connection...")
    try:
        async with AsyncSessionLocal() as session:
            repo = SafetyRepository(session)
            print("Successfully connected to database.")
            
            # Simple check
            print("Database session is active.")
            
    except Exception as e:
        print(f"Error connecting to database: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_connection())
