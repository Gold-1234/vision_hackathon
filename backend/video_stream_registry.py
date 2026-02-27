from typing import Optional


_publisher = None


def set_publisher(publisher: object) -> None:
    global _publisher
    _publisher = publisher


def get_publisher() -> Optional[object]:
    return _publisher
