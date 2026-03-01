import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

import av
import cv2
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from processors.base import draw_bbox
from processors.fall_detection import FallDetectionProcessor
from processors.object_detection import ObjectDetectionProcessor
from processors.toddler_danger_guard import ToddlerDangerGuard
from processors.toddler_processor import ALLOWED_CLASSES, TODDLER_MIN_CONFIDENCE, ToddlerProcessor


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


def _draw_detections(frame_bgr: Any, detections: list[dict[str, Any]], color: tuple[int, int, int]) -> Any:
    out = frame_bgr
    for det in detections:
        bbox = det.get("bbox")
        if bbox is None:
            continue
        label = str(det.get("label", "object"))
        conf = det.get("confidence")
        text = f"{label} {float(conf):.2f}" if isinstance(conf, (int, float)) else label
        out = draw_bbox(out, bbox, label=text, color=color)
    return out


def _detect_fall_sync(processor: FallDetectionProcessor, frame_bgr: Any) -> tuple[list[dict[str, Any]], float, tuple[int, int, int, int]]:
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
    fall_detected = False
    highest_conf_fall = 0.0
    fall_bbox = (0, 0, 0, 0)

    for pred in predictions:
        if not isinstance(pred, dict):
            continue
        class_name = str(pred.get("class", "Unknown")).strip() or "Unknown"
        confidence = processor._safe_float(pred.get("confidence"))
        if confidence is None or confidence < processor.conf_threshold:
            continue
        bbox = processor._prediction_to_bbox(pred)
        if bbox is None:
            continue

        normalized_class = class_name.strip().lower().replace("_", "-").replace(" ", "-")
        is_falling = normalized_class in {"fall-detected", "fall"}
        if is_falling:
            fall_detected = True
            if confidence > highest_conf_fall:
                highest_conf_fall = confidence
                fall_bbox = bbox

        detections.append(
            {
                "label": class_name,
                "confidence": confidence,
                "bbox": bbox,
                "is_falling": is_falling,
            }
        )

    processor.latest_detections = detections
    processor._fall_window.append(fall_detected)
    fall_votes = sum(1 for item in processor._fall_window if item)
    processor.fall_present = (
        len(processor._fall_window) == processor.fall_window_size
        and fall_votes >= processor.required_fall_frames
    )
    return detections, highest_conf_fall, fall_bbox


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run toddler danger guard on a local video file.")
    parser.add_argument("--input", required=True, help="Path to input video file.")
    parser.add_argument("--output", default="danger_guard_output.mp4", help="Path to output annotated video.")
    parser.add_argument("--process-fps", type=float, default=1.0, help="Inference FPS for toddler/object/danger logic.")
    parser.add_argument("--object-conf", type=float, default=0.5, help="Object detector confidence threshold.")
    parser.add_argument(
        "--model-path",
        default="",
        help="Optional YOLO model path for object detection (default: backend/yolo11m.pt).",
    )
    parser.add_argument(
        "--disable-second-pass",
        action="store_true",
        help="Disable danger second-pass inference and use only primary object inference.",
    )
    parser.add_argument("--fall-conf", type=float, default=0.7, help="Fall detector confidence threshold.")
    parser.add_argument("--display", action="store_true", help="Show live preview window while processing.")
    parser.add_argument(
        "--danger-labels",
        default="knife,scissors,fork,wine glass,bottle",
        help="Comma-separated dangerous object labels.",
    )
    parser.add_argument(
        "--debug-log",
        default="",
        help="Optional CSV path to write per-inference debug ticks.",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = _parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input video not found: {input_path}")

    api_key = os.getenv("ROBOFLOW_API_KEY")
    if not api_key:
        raise RuntimeError("ROBOFLOW_API_KEY is required for toddler detection.")

    root = Path(__file__).resolve().parents[1]
    yolo_model_path = Path(args.model_path) if args.model_path else (root / "yolo11m.pt")
    if not yolo_model_path.exists():
        raise FileNotFoundError(f"YOLO model not found: {yolo_model_path}")

    second_pass_scale = 1.0 if args.disable_second_pass else 1.6
    object_processor = ObjectDetectionProcessor(
        fps=float(args.process_fps),
        confidence_threshold=float(args.object_conf),
        model_path=str(yolo_model_path),
        danger_second_pass_scale=second_pass_scale,
    )
    fall_processor = FallDetectionProcessor(
        fps=max(1, int(args.process_fps)),
        conf_threshold=float(args.fall_conf),
        fall_window_size=2,
        required_fall_frames=2,
    )
    toddler_processor = ToddlerProcessor(fps=max(1, int(args.process_fps)))
    object_processor.bind_toddler_processor(toddler_processor)
    fall_processor.bind_toddler_processor(toddler_processor)

    danger_labels = {
        item.strip().lower()
        for item in str(args.danger_labels).split(",")
        if item.strip()
    }
    danger_guard = ToddlerDangerGuard(
        toddler_processor=toddler_processor,
        object_processor=object_processor,
        fps=float(args.process_fps),
        near_window_size=5,
        trigger_votes=3,
        clear_votes=1,
        moondream_conf_threshold=0.65,
        alert_cooldown_seconds=20.0,
        dangerous_labels=danger_labels,
    )

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

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    frame_idx = 0
    last_alert_ts = 0.0
    last_fall_alert_frame = -1
    debug_log_fh = None
    if args.debug_log:
        debug_path = Path(args.debug_log)
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        debug_log_fh = debug_path.open("w", encoding="utf-8")
        debug_log_fh.write(
            "frame,time_sec,toddler_present,second_pass_ran,knife_detected_raw,near_candidate,votes,verify_attempted,verify_ok,verify_confidence,verify_reason,alert_state\n"
        )
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

                if toddler_processor.toddler_present:
                    object_detections = object_processor._detect(frame_idx, frame)
                    object_processor.latest_detections = object_detections

                    _, fall_confidence, _ = _detect_fall_sync(fall_processor, frame)
                    if fall_processor.fall_present and frame_idx != last_fall_alert_frame:
                        video_sec = frame_idx / src_fps
                        print(f"[FALL] t={video_sec:.2f}s conf={fall_confidence:.2f}")
                        last_fall_alert_frame = frame_idx
                else:
                    object_processor.latest_detections = []
                    object_processor.latest_dangerous_detections = []
                    fall_processor.latest_detections = []
                    fall_processor.fall_present = False
                    fall_processor.latest_event = None
                    fall_processor._fall_window.clear()

                av_frame = av.VideoFrame.from_ndarray(frame, format="bgr24")
                loop.run_until_complete(danger_guard._on_frame(av_frame))

                state = danger_guard.state()
                alert = state.get("alert") or {}
                alert_ts = float(alert.get("timestamp", 0.0) or 0.0)
                if alert_ts > 0 and alert_ts != last_alert_ts:
                    video_sec = frame_idx / src_fps
                    risk = str(alert.get("risk_type") or alert.get("object_label") or "danger")
                    reason = str(alert.get("reason", "")).strip()
                    print(f"[ALERT] t={video_sec:.2f}s risk={risk} reason={reason}")
                    last_alert_ts = alert_ts

                if debug_log_fh is not None:
                    obj_debug = getattr(object_processor, "latest_debug", {}) or {}
                    knife_detected_raw = any(
                        str(det.get("label", "")).strip().lower() == "knife"
                        for det in (object_processor.latest_dangerous_detections or [])
                    )
                    near_candidate = state.get("candidate") is not None
                    votes = int(state.get("near_votes", 0) or 0)
                    verify_attempted = bool(state.get("verify_attempted", False))
                    verify_ok = bool(state.get("verify_ok", False))
                    verify_conf = float(state.get("verify_confidence", 0.0) or 0.0)
                    verify_reason = str(state.get("verify_reason", "")).replace(",", ";").replace("\n", " ").strip()
                    alert_state = bool(state.get("danger_present", False))
                    debug_log_fh.write(
                        f"{frame_idx},{(frame_idx / src_fps):.3f},"
                        f"{int(bool(toddler_processor.toddler_present))},"
                        f"{int(bool(obj_debug.get('second_pass_ran', False)))},"
                        f"{int(bool(knife_detected_raw))},"
                        f"{int(bool(near_candidate))},"
                        f"{votes},"
                        f"{int(verify_attempted)},"
                        f"{int(verify_ok)},"
                        f"{verify_conf:.3f},"
                        f"{verify_reason},"
                        f"{int(alert_state)}\n"
                    )

            annotated = frame.copy()
            annotated = _draw_detections(annotated, object_processor.latest_detections, color=(0, 255, 0))
            annotated = _draw_detections(annotated, toddler_processor.last_predictions, color=(0, 165, 255))
            if fall_processor.fall_present:
                for det in fall_processor.latest_detections:
                    if det.get("is_falling", False):
                        annotated = draw_bbox(
                            annotated,
                            det.get("bbox", (0, 0, 0, 0)),
                            label="FALL DETECTED!",
                            color=(0, 0, 255),
                            thickness=3,
                        )

            state = danger_guard.state()
            if state.get("danger_present"):
                alert = state.get("alert") or {}
                toddler_bbox = alert.get("toddler_bbox")
                object_bbox = alert.get("object_bbox")
                object_label = str(alert.get("object_label", "danger"))
                reason = str(alert.get("reason", "")).strip()
                if toddler_bbox is not None:
                    annotated = draw_bbox(
                        annotated,
                        toddler_bbox,
                        label="TODDLER AT RISK",
                        color=(0, 0, 255),
                        thickness=3,
                    )
                if object_bbox is not None:
                    label = f"DANGER: {object_label}"
                    if reason:
                        label = f"{label} | {reason}"
                    annotated = draw_bbox(
                        annotated,
                        object_bbox,
                        label=label,
                        color=(0, 0, 255),
                        thickness=3,
                    )

            writer.write(annotated)
            if args.display:
                cv2.imshow("Toddler Danger Guard", annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            frame_idx += 1
    finally:
        cap.release()
        writer.release()
        if debug_log_fh is not None:
            debug_log_fh.close()
        if args.display:
            cv2.destroyAllWindows()
        loop.close()

    print(f"Done. Annotated output saved to: {output_path}")


if __name__ == "__main__":
    main()
