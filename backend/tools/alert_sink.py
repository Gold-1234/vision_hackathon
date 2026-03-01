import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ALERT_SINK_PATH = Path("data/alerts/alerts.jsonl")


def write_alert(event: dict[str, Any], sink_path: Path | str = DEFAULT_ALERT_SINK_PATH) -> None:
    path = Path(sink_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        **event,
    }

    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=True) + "\n")
