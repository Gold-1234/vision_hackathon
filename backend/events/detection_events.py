# RANK: 1 - Define the dataclasses for events (e.g., ObjectDetectedEvent) emitted by processors.

from dataclasses import dataclass, field
from typing import Any

# Since Vision Agents isn't fully installed yet or we don't know the exact class name
# We'll create a base class for events meant to be published to LLM/Subscribers
@dataclass
class VisionEvent:
    name: str
    frame_number: int = 0
    timestamp: float = 0.0

@dataclass
class ObjectDetectedEvent(VisionEvent):
    name: str = "ObjectDetected"
    # list of dicts: {'label': str, 'confidence': float, 'bbox': tuple, 'class_id': int}
    objects: list[dict[str, Any]] = field(default_factory=list)

@dataclass
class FallDetectedEvent(VisionEvent):
    name: str = "FallDetected"
    confidence: float = 0.0
    bbox: tuple[int, int, int, int] = (0, 0, 0, 0)

@dataclass
class FaceRecognizedEvent(VisionEvent):
    name: str = "FaceRecognized"
    person_name: str = "unknown"
    confidence: float = 0.0
    bbox: tuple[int, int, int, int] = (0, 0, 0, 0)

@dataclass
class ToddlerDetectedEvent(VisionEvent):
    name: str = "ToddlerDetected"
    confidence: float = 0.0
    bbox: tuple[int, int, int, int] = (0, 0, 0, 0)

@dataclass
class CryDetectedEvent(VisionEvent):
    name: str = "CryDetected"
    confidence: float = 0.0

@dataclass
class EdgeProximityEvent(VisionEvent):
    name: str = "EdgeProximity"
    child_bbox: tuple[int, int, int, int] = (0, 0, 0, 0)
    edge_location: str = "unknown"
    distance_px: float = 0.0

@dataclass
class DangerZoneViolationEvent(VisionEvent):
    name: str = "DangerZoneViolation"
    zone_id: str = "unknown"
    object_label: str = "person"

@dataclass
class DangerObjectNearbyEvent(VisionEvent):
    name: str = "DangerObjectNearby"
    object_label: str = "unknown"
    child_bbox: tuple[int, int, int, int] = (0, 0, 0, 0)
    distance_px: float = 0.0

