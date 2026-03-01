import asyncio
import os
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

from database.models import Base, Users, Camera, SafetyEvent, Alert

# Use same env logic as connection
DB_USER = os.getenv("POSTGRES_USER", "krishna")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "n0password")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "vision_ai")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def seed_data():
    async with engine.begin() as conn:
        # Check connectivity
        await conn.execute(text("SELECT 1"))
        print("Database connection successful!")
        
        # Ensure tables exist
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Check for existing User
        result = await session.execute(text("SELECT id FROM users LIMIT 1"))
        user_id = result.scalar()
        if not user_id:
            user = Users(name="Test User", email="test@example.com", password="password")
            session.add(user)
            await session.commit()
            await session.refresh(user)
            user_id = user.id

        # Check for existing Camera
        result = await session.execute(text("SELECT id FROM cameras LIMIT 1"))
        camera_id = result.scalar()
        if not camera_id:
            camera = Camera(user_id=user_id, name="Living Room Cam", is_active=True)
            session.add(camera)
            await session.commit()
            await session.refresh(camera)
            camera_id = camera.id

        now = datetime.now(timezone.utc)
        
        # Add SafetyEvents and Alerts for the past 10 days
        print("Inserting fake data...")
        import random
        for day in range(10):
            event_date = now - timedelta(days=day)
            
            # 1 to 5 events per day
            for _ in range(random.randint(1, 5)):
                event = SafetyEvent(
                    camera_id=camera_id,
                    event_type=random.choice(["FallDetected", "ToddlerDetected", "CryingDetected"]),
                    confidence=random.uniform(0.6, 0.99),
                    event_metadata={"test": True}
                )
                event.created_at = event_date - timedelta(hours=random.randint(1, 8)) # Spread out in the day
                session.add(event)
            
            # 0 to 2 alerts per day
            for _ in range(random.randint(0, 2)):
                alert = Alert(
                    camera_id=camera_id,
                    alert_type="SafetyAlert",
                    severity=random.choice(["Low", "Medium", "High"]),
                    message="Something happened",
                    alert_metadata={"test": True}
                )
                alert.created_at = event_date - timedelta(hours=random.randint(1, 8))
                session.add(alert)
                
        await session.commit()
        print("Fake data seeded successfully!")

if __name__ == "__main__":
    asyncio.run(seed_data())
