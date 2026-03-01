from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .models import SafetyEvent, Alert

class SafetyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_event(self, event_type: str, confidence: float, meta: dict = None):
        event = SafetyEvent(
            event_type=event_type,
            confidence=confidence,
            metadata=meta
        )
        self.session.add(event)
        await self.session.commit()
        return event

    async def get_recent_events(self, limit: int = 10):
        query = select(SafetyEvent).order_by(SafetyEvent.created_at.desc()).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

class AlertRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_alert(self, alert_type: str, severity: str, message: str, meta: dict = None):
        alert = Alert(
            alert_type=alert_type,
            severity=severity,
            message=message,
            metadata=meta
        )
        self.session.add(alert)
        await self.session.commit()
        return alert

    async def get_recent_alerts(self, limit: int = 10):
        query = select(Alert).order_by(Alert.created_at.desc()).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()
