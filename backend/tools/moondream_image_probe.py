import argparse
import base64
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

from dotenv import load_dotenv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send one local image to Moondream and print/save raw results."
    )
    parser.add_argument(
        "--image",
        default="",
        help="Image path. If omitted, uses latest *_marked.jpg from data/test_results/zone_risk.",
    )
    parser.add_argument(
        "--query",
        default=(
            'Identify places in this image a toddler should not go near. '
            'Return JSON only: {"unsafe_places":["stairs","balcony","pool","fireplace","stove","window_edge"]}.'
        ),
        help="Question for /v1/query.",
    )
    parser.add_argument(
        "--detect-object",
        default="",
        help="Optional object for /v1/detect (e.g., stairs). If empty, detect step is skipped.",
    )
    parser.add_argument(
        "--out",
        default="data/test_results/zone_risk/moondream_probe_output.json",
        help="Path to save JSON output.",
    )
    parser.add_argument(
        "--api-base",
        default="https://api.moondream.ai",
        help="Moondream API base URL.",
    )
    return parser.parse_args()


def latest_zone_image(default_dir: Path) -> Path:
    if not default_dir.exists():
        raise FileNotFoundError(f"Zone risk directory not found: {default_dir}")
    marked = sorted(default_dir.glob("*_marked.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
    if marked:
        return marked[0]
    jpgs = sorted(default_dir.glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
    if jpgs:
        return jpgs[0]
    raise FileNotFoundError(f"No JPG images found in: {default_dir}")


def data_url_from_image(image_path: Path) -> str:
    raw = image_path.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def post_json(url: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url=url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Moondream-Auth": api_key,
            "Accept": "*/*",
            "User-Agent": "curl/8.7.1",
        },
    )
    try:
        with request.urlopen(req, timeout=30) as resp:
            txt = resp.read().decode("utf-8", errors="replace")
            return {
                "ok": True,
                "status_code": int(resp.status),
                "response_raw": txt,
            }
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        headers_text = ""
        try:
            headers_text = str(exc.headers)
        except Exception:
            headers_text = "<unavailable>"
        return {
            "ok": False,
            "status_code": int(exc.code),
            "error_type": "http_error",
            "reason": str(getattr(exc, "reason", "")),
            "url": str(url),
            "headers": headers_text,
            "error_detail": detail,
        }
    except Exception as exc:
        return {
            "ok": False,
            "status_code": None,
            "error_type": "request_exception",
            "error_detail": str(exc),
        }


def main() -> None:
    load_dotenv(".env")
    args = parse_args()

    api_key = os.getenv("MOONDREAM_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("MOONDREAM_API_KEY is missing in environment/.env")

    default_zone_dir = Path("data/test_results/zone_risk")
    image_path = Path(args.image) if args.image else latest_zone_image(default_zone_dir)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    image_url = data_url_from_image(image_path)
    base = args.api_base.rstrip("/")

    query_payload = {"image_url": image_url, "question": args.query}
    query_result = post_json(f"{base}/v1/query", api_key, query_payload)

    detect_result = None
    if args.detect_object:
        detect_payload = {"image_url": image_url, "object": args.detect_object}
        detect_result = post_json(f"{base}/v1/detect", api_key, detect_payload)

    output = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "image_path": str(image_path),
        "query": {
            "url": f"{base}/v1/query",
            "question": args.query,
            "result": query_result,
        },
        "detect": {
            "url": f"{base}/v1/detect",
            "object": args.detect_object,
            "result": detect_result,
        }
        if args.detect_object
        else None,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=True, indent=2), encoding="utf-8")

    print("Image:", image_path)
    print("Query status:", query_result.get("status_code"), "ok=", query_result.get("ok"))
    if not query_result.get("ok"):
        print(
            f"[ERROR][QUERY] endpoint={base}/v1/query "
            f"status={query_result.get('status_code')} "
            f"reason={query_result.get('reason')} "
            f"type={query_result.get('error_type')} "
            f"headers={query_result.get('headers')} "
            f"body={query_result.get('error_detail')}"
        )
    else:
        print("Query response:", query_result.get("response_raw"))

    if args.detect_object:
        print("Detect status:", detect_result.get("status_code"), "ok=", detect_result.get("ok"))
        if not detect_result.get("ok"):
            print(
                f"[ERROR][DETECT] endpoint={base}/v1/detect "
                f"status={detect_result.get('status_code')} "
                f"reason={detect_result.get('reason')} "
                f"type={detect_result.get('error_type')} "
                f"headers={detect_result.get('headers')} "
                f"body={detect_result.get('error_detail')}"
            )
        else:
            print("Detect response:", detect_result.get("response_raw"))

    print("Saved:", out_path)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
