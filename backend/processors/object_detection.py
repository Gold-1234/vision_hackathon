import asyncio
import os
from typing import Any, Optional

import aiortc
import av
import cv2
import numpy as np
from ultralytics import YOLO
from vision_agents.core.processors import VideoProcessor
from vision_agents.core.utils.video_forwarder import VideoForwarder

from events.detection_events import ObjectDetectedEvent
from .base import draw_bbox, format_yolo_detections

EXCLUDED_YOLO_LABELS = {"person"}
DANGEROUS_YOLO_LABELS = {
    "knife",
    "scissors",
    "fork",
    "bottle",
    "wine glass",
}


class ObjectDetectionProcessor(VideoProcessor):
    """
    YOLO object detection processor (analysis-only).
    """

    name = "object_detection"

    def __init__(
        self,
        fps: float = 1.0,
        model_path: str = "yolo11m.pt",
        confidence_threshold: float = 0.5,
        danger_confidence_threshold: float = 0.1,
        danger_second_pass_confidence: float = 0.1,
        danger_second_pass_scale: float = 1.6,
        danger_second_pass_every_n_frames: Optional[int] = None,
        danger_roi_expand_ratio: float = 0.25,
        danger_hand_roi_ratio: float = 0.35,
        require_toddler_for_processing: bool = True,
    ) -> None:
        self.fps = float(fps)
        self.confidence_threshold = confidence_threshold
        self.danger_confidence_threshold = float(danger_confidence_threshold)
        self.danger_second_pass_confidence = float(danger_second_pass_confidence)
        self.danger_second_pass_scale = max(1.0, float(danger_second_pass_scale))
        self.danger_second_pass_every_n_frames = (
            max(1, int(danger_second_pass_every_n_frames))
            if danger_second_pass_every_n_frames is not None
            else max(1, int(round(max(1.0, self.fps))))
        )
        self.danger_roi_expand_ratio = max(0.0, float(danger_roi_expand_ratio))
        self.danger_hand_roi_ratio = max(0.1, float(danger_hand_roi_ratio))
        self.require_toddler_for_processing = bool(require_toddler_for_processing)
        self.model_path = model_path
        self.toddler_processor: Optional[Any] = None

        print(f"Loading YOLO model from {model_path}...")
        self.model = YOLO(model_path)
        self.device = self._resolve_device()
        try:
            self.model.to(self.device)
        except Exception:
            # Some ultralytics backends may not support .to(); fallback to device arg in inference.
            pass
        print("YOLO model loaded.")

        self.latest_detections: list[dict[str, Any]] = []
        self.latest_dangerous_detections: list[dict[str, Any]] = []
        self.latest_debug: dict[str, Any] = {
            "toddler_present": False,
            "second_pass_ran": False,
            "second_pass_count": 0,
        }
        self.latest_event: Optional[ObjectDetectedEvent] = None

        self._forwarder: Optional[VideoForwarder] = None
        self._owns_forwarder = False
        self._handler_registered = False
        self._processing_lock = asyncio.Lock()
        self._frame_number = 0

    def bind_toddler_processor(self, toddler_processor: Optional[Any]) -> None:
        self.toddler_processor = toddler_processor

    async def process_video(
        self,
        track: aiortc.VideoStreamTrack,
        participant_id: Optional[str],
        shared_forwarder: Optional[VideoForwarder] = None,
    ) -> None:
        _ = participant_id
        # Rebind handler if process_video is called again (e.g., track switch).
        if self._forwarder is not None and self._handler_registered:
            await self._forwarder.remove_frame_handler(self._on_frame)
            if self._owns_forwarder:
                await self._forwarder.stop()
            self._handler_registered = False
            self._owns_forwarder = False

        self._forwarder = shared_forwarder
        if self._forwarder is None:
            self._forwarder = VideoForwarder(
                input_track=track,
                max_buffer=5,
                fps=max(1.0, self.fps),
                name=f"{self.name}_forwarder",
            )
            await self._forwarder.start()
            self._owns_forwarder = True

        self._forwarder.add_frame_handler(
            self._on_frame,
            fps=self.fps,
            name=f"{self.name}_handler",
        )
        self._handler_registered = True

    async def _on_frame(self, frame: av.VideoFrame) -> None:
        # Skip frame if previous inference is still running.
        if self._processing_lock.locked():
            return

        async with self._processing_lock:
            frame_bgr = frame.to_ndarray(format="bgr24")
            frame_number = self._frame_number
            self._frame_number += 1
            detections = await asyncio.to_thread(
                self._detect,
                frame_number,
                frame_bgr,
            )

            self.latest_detections = detections
            self.latest_event = ObjectDetectedEvent(
                frame_number=frame_number,
                objects=detections,
            )

    def _detect(
        self,
        frame_number: int,
        frame_bgr: np.ndarray,
    ) -> list[dict[str, Any]]:
        _ = frame_number
        toddler_boxes = self._get_toddler_boxes()
        self.latest_debug = {
            "toddler_present": bool(toddler_boxes),
            "second_pass_ran": False,
            "second_pass_count": 0,
        }
        if self.require_toddler_for_processing and not toddler_boxes:
            self.latest_dangerous_detections = []
            return []

        base_results = self.model(
            frame_bgr,
            verbose=False,
            conf=self.confidence_threshold,
            device=self.device,
        )
        detections = format_yolo_detections(base_results)
        second_pass_detections = self._danger_second_pass(
            frame_bgr=frame_bgr,
            toddler_boxes=toddler_boxes,
            frame_number=frame_number,
        )
        if second_pass_detections:
            self.latest_debug["second_pass_ran"] = True
            self.latest_debug["second_pass_count"] = len(second_pass_detections)
            detections = self._merge_detections(detections, second_pass_detections)
        filtered = []
        dangerous = []
        for det in detections:
            label = str(det.get("label", "")).strip().lower()
            if label in EXCLUDED_YOLO_LABELS:
                continue
            conf = float(det.get("confidence", 0.0))
            min_conf = self.confidence_threshold
            if label in DANGEROUS_YOLO_LABELS:
                min_conf = min(min_conf, self.danger_confidence_threshold)
            if conf < min_conf:
                continue
            filtered.append(det)
            if label in DANGEROUS_YOLO_LABELS:
                dangerous.append(det)
        self.latest_dangerous_detections = dangerous
        return filtered

    def _get_toddler_boxes(self) -> list[tuple[int, int, int, int]]:
        if self.toddler_processor is None or not hasattr(self.toddler_processor, "state"):
            return []
        try:
            toddler_state = self.toddler_processor.state() or {}
        except Exception:
            return []
        detections = toddler_state.get("detections", []) or []
        boxes: list[tuple[int, int, int, int]] = []
        for det in detections:
            if str(det.get("label", "")).strip().lower() != "toddler":
                continue
            bbox = det.get("bbox")
            if not isinstance(bbox, tuple) or len(bbox) != 4:
                continue
            boxes.append(bbox)
        return boxes

    @staticmethod
    def _clip_bbox(
        bbox: tuple[int, int, int, int],
        frame_w: int,
        frame_h: int,
    ) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = bbox
        nx1 = max(0, min(frame_w - 1, int(x1)))
        ny1 = max(0, min(frame_h - 1, int(y1)))
        nx2 = max(0, min(frame_w - 1, int(x2)))
        ny2 = max(0, min(frame_h - 1, int(y2)))
        if nx2 <= nx1:
            nx2 = min(frame_w - 1, nx1 + 1)
        if ny2 <= ny1:
            ny2 = min(frame_h - 1, ny1 + 1)
        return (nx1, ny1, nx2, ny2)

    def _build_danger_rois(
        self,
        toddler_bbox: tuple[int, int, int, int],
        frame_w: int,
        frame_h: int,
    ) -> list[tuple[int, int, int, int]]:
        x1, y1, x2, y2 = toddler_bbox
        tw = max(1, x2 - x1)
        th = max(1, y2 - y1)

        pad_x = int(round(tw * self.danger_roi_expand_ratio))
        pad_y = int(round(th * self.danger_roi_expand_ratio))
        full_roi = self._clip_bbox((x1 - pad_x, y1 - pad_y, x2 + pad_x, y2 + pad_y), frame_w, frame_h)

        hand_w = int(round(tw * self.danger_hand_roi_ratio))
        hand_h = int(round(th * 0.7))
        hand_top = y1 + int(round(th * 0.15))
        left_hand_roi = self._clip_bbox(
            (x1 - hand_w, hand_top, x1 + int(round(tw * 0.25)), hand_top + hand_h),
            frame_w,
            frame_h,
        )
        right_hand_roi = self._clip_bbox(
            (x2 - int(round(tw * 0.25)), hand_top, x2 + hand_w, hand_top + hand_h),
            frame_w,
            frame_h,
        )
        return [full_roi, left_hand_roi, right_hand_roi]

    def _danger_second_pass(
        self,
        frame_bgr: np.ndarray,
        toddler_boxes: list[tuple[int, int, int, int]],
        frame_number: int,
    ) -> list[dict[str, Any]]:
        """
        Run a danger-specific pass only when toddler is present, every N frames,
        and only in toddler-centric ROIs (including hand-side zones).
        """
        if not toddler_boxes:
            return []
        if frame_number % self.danger_second_pass_every_n_frames != 0:
            return []

        h, w = frame_bgr.shape[:2]
        primary_toddler = max(toddler_boxes, key=lambda b: max(1, b[2] - b[0]) * max(1, b[3] - b[1]))
        rois = self._build_danger_rois(primary_toddler, w, h)

        remapped: list[dict[str, Any]] = []
        for roi in rois:
            rx1, ry1, rx2, ry2 = roi
            crop = frame_bgr[ry1:ry2, rx1:rx2]
            if crop.size == 0:
                continue
            ch, cw = crop.shape[:2]
            if cw < 2 or ch < 2:
                continue

            scaled = crop
            scale_x = 1.0
            scale_y = 1.0
            if self.danger_second_pass_scale > 1.0:
                scaled_w = max(2, int(round(cw * self.danger_second_pass_scale)))
                scaled_h = max(2, int(round(ch * self.danger_second_pass_scale)))
                scaled = cv2.resize(crop, (scaled_w, scaled_h), interpolation=cv2.INTER_LINEAR)
                scale_x = float(cw) / float(scaled_w)
                scale_y = float(ch) / float(scaled_h)

            results = self.model(
                scaled,
                verbose=False,
                conf=min(self.danger_confidence_threshold, self.danger_second_pass_confidence),
                device=self.device,
            )
            dets = format_yolo_detections(results)
            for det in dets:
                label = str(det.get("label", "")).strip().lower()
                if label not in DANGEROUS_YOLO_LABELS:
                    continue
                bbox = det.get("bbox")
                if bbox is None or len(bbox) != 4:
                    continue
                x1, y1, x2, y2 = bbox
                mapped_bbox = self._clip_bbox(
                    (
                        int(round(rx1 + x1 * scale_x)),
                        int(round(ry1 + y1 * scale_y)),
                        int(round(rx1 + x2 * scale_x)),
                        int(round(ry1 + y2 * scale_y)),
                    ),
                    w,
                    h,
                )
                remapped.append(
                    {
                        **det,
                        "bbox": mapped_bbox,
                    }
                )

        if not remapped:
            return []
        return self._merge_detections([], remapped)

    @staticmethod
    def _bbox_iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)
        iw = max(0, ix2 - ix1)
        ih = max(0, iy2 - iy1)
        inter = float(iw * ih)
        if inter <= 0:
            return 0.0
        area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
        area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
        union = float(area_a + area_b - inter)
        if union <= 0:
            return 0.0
        return inter / union

    def _merge_detections(
        self,
        base: list[dict[str, Any]],
        extra: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged = list(base)
        for candidate in extra:
            label = str(candidate.get("label", "")).strip().lower()
            conf = float(candidate.get("confidence", 0.0))
            bbox = candidate.get("bbox")
            if label not in DANGEROUS_YOLO_LABELS or bbox is None:
                continue

            replaced = False
            for idx, existing in enumerate(merged):
                existing_label = str(existing.get("label", "")).strip().lower()
                existing_bbox = existing.get("bbox")
                if existing_label != label or existing_bbox is None:
                    continue
                if self._bbox_iou(existing_bbox, bbox) < 0.5:
                    continue
                existing_conf = float(existing.get("confidence", 0.0))
                if conf > existing_conf:
                    merged[idx] = candidate
                replaced = True
                break

            if not replaced:
                merged.append(candidate)
        return merged

    @staticmethod
    def _resolve_device() -> str:
        env_device = os.getenv("YOLO_DEVICE", "").strip().lower()
        if env_device:
            return env_device
        try:
            import torch

            if torch.backends.mps.is_available():
                return "mps"
        except Exception:
            pass
        return "cpu"

    def process_frame(self, frame_number: int, frame: np.ndarray) -> np.ndarray:
        """
        Backwards-compatible synchronous API used by local_runner.py.
        """
        detections = self._detect(frame_number, frame)
        annotated_frame = frame.copy()
        for det in detections:
            label = f"{det['label']} {det['confidence']:.2f}"
            annotated_frame = draw_bbox(annotated_frame, det["bbox"], label=label)
        self.latest_detections = detections
        self.latest_event = ObjectDetectedEvent(
            frame_number=frame_number,
            objects=detections,
        )
        return annotated_frame

    def state(self) -> dict[str, Any]:
        return {
            "detections": self.latest_detections,
            "dangerous_detections": self.latest_dangerous_detections,
        }

    async def stop_processing(self) -> None:
        if self._forwarder is not None and self._handler_registered:
            await self._forwarder.remove_frame_handler(self._on_frame)
        if self._forwarder is not None and self._owns_forwarder:
            await self._forwarder.stop()
        self._handler_registered = False
        self._forwarder = None
        self._owns_forwarder = False

    async def close(self) -> None:
        await self.stop_processing()
