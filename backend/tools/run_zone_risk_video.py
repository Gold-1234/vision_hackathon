import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

import av
import cv2
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from processors.toddler_processor import ALLOWED_CLASSES, TODDLER_MIN_CONFIDENCE, ToddlerProcessor
from processors.zone_risk_guard import ZoneRiskGuard


def _detect_toddler_sync(processor: ToddlerProcessor, frame_bgr: Any) -> list[dict[str, Any]]:
    result = processor.model.predict(
        frame_bgr,
        confidence=processor._rf_confidence,
        overlap=processor._rf_overlap,
    )
    result_json = result.json()
    predictions = result_json.get("predictions", []) if isinstance(result_json, dict) else []
    if not isinstance(predictions, list):
        predictions = []

    detections: list[dict[str, Any]] = []
    for pred in predictions:
        if not isinstance(pred, dict):
            continue
        class_name = str(pred.get("class", "Unknown")).strip() or "Unknown"
        class_lower = class_name.lower()
        confidence = processor._safe_float(pred.get("confidence"))
        if class_lower not in ALLOWED_CLASSES:
            continue
        min_conf = processor.conf_threshold
        if class_lower == "toddler":
            min_conf = max(min_conf, TODDLER_MIN_CONFIDENCE)
        if confidence is None or confidence < min_conf:
            continue
        bbox = processor._prediction_to_bbox(pred)
        if bbox is None:
            continue
        detections.append(
            {
                "label": class_name,
                "confidence": confidence,
                "bbox": bbox,
            }
        )
    return detections


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run zone risk guard on a local video file.")
    parser.add_argument("--input", required=True, help="Path to input video file.")
    parser.add_argument("--output", required=True, help="Path to output annotated video.")
    parser.add_argument("--process-fps", type=float, default=2.0, help="Inference FPS for toddler/zone processing.")
    parser.add_argument("--display", action="store_true", help="Show live preview window while processing.")
    parser.add_argument(
        "--debug-log",
        default="",
        help="Optional CSV path to write per-inference zone ticks.",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = _parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input video not found: {input_path}")

    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open input video: {input_path}")

    src_fps = cap.get(cv2.CAP_PROP_FPS)
    if src_fps <= 0:
        src_fps = 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        src_fps,
        (width, height),
    )

    process_fps = max(0.1, float(args.process_fps))
    process_every_n = max(1, int(round(src_fps / process_fps)))

    toddler_processor = ToddlerProcessor(fps=max(1, int(round(process_fps))))
    zone_guard = ZoneRiskGuard(
        toddler_processor=toddler_processor,
        fps=process_fps,
        near_threshold_px=40.0,
        near_trigger_count=3,
        alert_cooldown_seconds=20.0,
        zone_expand_ratio=0.1,
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    debug_fh = None
    if args.debug_log:
        debug_path = Path(args.debug_log)
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        debug_fh = debug_path.open("w", encoding="utf-8")
        debug_fh.write(
            "frame,time_sec,toddler_present,zone_ready,near_count,near_trigger_count,distance_px,status,alert_active,inside_zone,crossed\n"
        )

    frame_idx = 0
    last_alert_ts = 0.0
    print(
        f"Processing '{input_path}' @ source_fps={src_fps:.2f}, "
        f"inference_fps={process_fps:.2f}, every_n_frames={process_every_n}"
    )

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            if frame_idx % process_every_n == 0:
                toddler_detections = _detect_toddler_sync(toddler_processor, frame)
                toddler_processor.last_predictions = toddler_detections
                toddler_processor.toddler_present = any(
                    str(det.get("label", "")).strip().lower() == "toddler"
                    for det in toddler_detections
                )

                av_frame = av.VideoFrame.from_ndarray(frame, format="bgr24")
                loop.run_until_complete(zone_guard._on_frame(av_frame))
                zone_state = zone_guard.state()

                alert = zone_state.get("alert") or {}
                alert_ts = float(alert.get("timestamp", 0.0) or 0.0)
                if alert_ts > 0 and alert_ts != last_alert_ts:
                    print(
                        f"[ZONE ALERT] t={(frame_idx / src_fps):.2f}s "
                        f"status={zone_state.get('status')} "
                        f"inside={alert.get('inside_zone')} crossed={alert.get('crossed')} "
                        f"dist={alert.get('distance_px')}"
                    )
                    last_alert_ts = alert_ts

                if debug_fh is not None:
                    distance_px = zone_state.get("distance_px")
                    distance_text = "" if distance_px is None else f"{float(distance_px):.3f}"
                    status = str(zone_state.get("status", "")).replace(",", ";").replace("\n", " ").strip()
                    debug_fh.write(
                        f"{frame_idx},{(frame_idx / src_fps):.3f},"
                        f"{int(bool(toddler_processor.toddler_present))},"
                        f"{int(bool(zone_state.get('zone_ready', False)))},"
                        f"{int(zone_state.get('near_count', 0) or 0)},"
                        f"{int(zone_state.get('near_trigger_count', 0) or 0)},"
                        f"{distance_text},"
                        f"{status},"
                        f"{int(bool(zone_state.get('alert_active', False)))},"
                        f"{int(bool(alert.get('inside_zone', False)))},"
                        f"{int(bool(alert.get('crossed', False)))}\n"
                    )

            annotated = frame.copy()
            zone_state = zone_guard.state()
            zone_bbox = zone_state.get("zone_bbox")
            baby_point = zone_state.get("baby_point")
            status = str(zone_state.get("status", "ZONE_NOT_READY"))
            alert_active = bool(zone_state.get("alert_active", False))
            near_count = int(zone_state.get("near_count", 0) or 0)
            near_trigger = int(zone_state.get("near_trigger_count", 0) or 0)

            if isinstance(zone_bbox, tuple) and len(zone_bbox) == 4:
                x1, y1, x2, y2 = [int(v) for v in zone_bbox]
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255) if alert_active else (0, 200, 255), 3)
                cv2.putText(
                    annotated,
                    "STAIRS ZONE",
                    (max(0, x1), max(20, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255) if alert_active else (0, 200, 255),
                    2,
                    cv2.LINE_AA,
                )

            if isinstance(baby_point, tuple) and len(baby_point) == 2:
                bx, by = int(baby_point[0]), int(baby_point[1])
                cv2.circle(annotated, (bx, by), 6, (255, 255, 0), -1)
                cv2.circle(annotated, (bx, by), 9, (0, 0, 0), 2)

            status_text = status if near_trigger <= 0 else f"{status} ({near_count}/{near_trigger})"
            cv2.putText(
                annotated,
                status_text,
                (20, 36),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 0, 255) if alert_active else (0, 200, 255),
                2,
                cv2.LINE_AA,
            )

            writer.write(annotated)
            if args.display:
                cv2.imshow("Zone Risk", annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            frame_idx += 1
    finally:
        cap.release()
        writer.release()
        if debug_fh is not None:
            debug_fh.close()
        loop.close()
        if args.display:
            cv2.destroyAllWindows()

    print(f"Saved output video: {output_path}")
    print(f"Zone snapshots folder: {zone_guard.debug_output_dir}")
    if args.debug_log:
        print(f"Saved debug log: {args.debug_log}")


if __name__ == "__main__":
    main()
