import logging
from sqlalchemy.future import select
from .connection import AsyncSessionLocal
from .models import SafetyEvent, Alert, Camera, Users

logger = logging.getLogger(__name__)

async def ensure_default_camera():
    try:
        async with AsyncSessionLocal() as session:
            # Check if camera 1 exists
            result = await session.execute(select(Camera).filter(Camera.id == 1))
            cam = result.scalar_one_or_none()
            if not cam:
                # Check user 1
                user_result = await session.execute(select(Users).filter(Users.id == 1))
                user = user_result.scalar_one_or_none()
                if not user:
                    user = Users(name="Default User", email="user@example.com", password="password")
                    session.add(user)
                    await session.flush()
                
                cam = Camera(id=1, user_id=user.id, name="Default Camera", stream_url="N/A", is_active=True)
                session.add(cam)
                await session.commit()
            return cam.id
    except Exception as e:
        logger.error(f"Error ensuring default camera: {e}")
        return 1

async def log_safety_event(event_type: str, confidence: float = None, metadata: dict = None):
    try:
        async with AsyncSessionLocal() as session:
            event = SafetyEvent(
                camera_id=1,
                event_type=event_type,
                confidence=confidence,
                event_metadata=metadata
            )
            session.add(event)
            await session.commit()
    except Exception as e:
        logger.error(f"Failed to log safety event: {e}")

async def log_alert(alert_type: str, severity: str, message: str, metadata: dict = None):
    try:
        async with AsyncSessionLocal() as session:
            alert = Alert(
                camera_id=1,
                alert_type=alert_type,
                severity=severity,
                message=message,
                alert_metadata=metadata
            )
            session.add(alert)
            await session.commit()
    except Exception as e:
        logger.error(f"Failed to log alert: {e}")
