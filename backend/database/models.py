from datetime import datetime
from typing import Optional, Any
from sqlalchemy import String, Float, JSON, DateTime, Text, func, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .connection import Base

class Users(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    email: Mapped[str] = mapped_column(String(50))
    password: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    toddlers: Mapped[list["Toddler"]] = relationship(back_populates="user")
    cameras: Mapped[list["Camera"]] = relationship(back_populates="user")


class Toddler(Base):
    __tablename__ = "toddlers"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(50))
    age: Mapped[int] = mapped_column(Integer)
    gender: Mapped[str] = mapped_column(String(10))
    cried_count: Mapped[int] = mapped_column(Integer, default=0)
    fallen_count: Mapped[int] = mapped_column(Integer, default=0)
    harm_count: Mapped[int] = mapped_column(Integer, default=0)
    danger_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["Users"] = relationship(back_populates="toddlers")


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(50))
    stream_url: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["Users"] = relationship(back_populates="cameras")
    danger_zones: Mapped[list["DangerZone"]] = relationship(back_populates="camera")
    safety_events: Mapped[list["SafetyEvent"]] = relationship(back_populates="camera")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="camera")


class DangerZone(Base):
    __tablename__ = "danger_zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id"))
    zone_name: Mapped[str] = mapped_column(String(50))
    polygon_coordinates: Mapped[Any] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    camera: Mapped["Camera"] = relationship(back_populates="danger_zones")


class SafetyEvent(Base):
    __tablename__ = "safety_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id"))
    event_type: Mapped[str] = mapped_column(String(50))
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    event_metadata: Mapped[Optional[Any]] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    camera: Mapped["Camera"] = relationship(back_populates="safety_events")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id"))
    alert_type: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(20))
    message: Mapped[Optional[str]] = mapped_column(Text)
    alert_metadata: Mapped[Optional[Any]] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    camera: Mapped["Camera"] = relationship(back_populates="alerts")