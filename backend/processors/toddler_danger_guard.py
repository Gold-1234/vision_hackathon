import asyncio
import json
import logging
import os
import time
from collections import deque
from typing import Any, Optional

import aiortc
import av
from vision_agents.core.processors import VideoProcessor
from vision_agents.core.utils.video_forwarder import VideoForwarder

logger = logging.getLogger(__name__)

DEFAULT_DANGEROUS_LABELS = {
    "knife",
    "scissors",
    "fork",
    "wine glass",
    "bottle",
    "microwave",
    "oven",
    "toaster",
    "hair drier",
    "tie"
}


class ToddlerDangerGuard(VideoProcessor):
    """
    Toddler-gated danger detector:
    1) requires toddler presence
    2) checks dangerous objects near toddler
    3) verifies candidate with Moondream API
    """

    name = "toddler_danger_guard"

    def __init__(
        self,
        toddler_processor: Any,
        object_processor: Any,
        fps: float = 1.0,
        use_temporal_voting: bool = True,
        near_window_size: int = 5,
        trigger_votes: int = 3,
        clear_votes: int = 1,
        center_distance_scale: float = 0.8,
        expand_ratio: float = 0.2,
        alert_cooldown_seconds: float = 20.0,
        verify_cooldown_seconds: float = 3.0,
        verify_result_ttl_seconds: float = 8.0,
        moondream_conf_threshold: float = 0.65,
        dangerous_labels: Optional[set[str]] = None,
        moondream_api_url: Optional[str] = None,
        moondream_api_key: Optional[str] = None,
    ) -> None:
        self.toddler_processor = toddler_processor
        self.object_processor = object_processor
        self.fps = max(1.0, float(fps))
        self.use_temporal_voting = bool(use_temporal_voting)

        self.near_window_size = max(1, int(near_window_size))
        self.trigger_votes = max(1, int(trigger_votes))
        self.clear_votes = max(0, int(clear_votes))
        self.trigger_votes = min(self.trigger_votes, self.near_window_size)
        self.clear_votes = min(self.clear_votes, self.near_window_size)

        self.center_distance_scale = max(0.1, float(center_distance_scale))
        self.expand_ratio = max(0.0, float(expand_ratio))
        self.alert_cooldown_seconds = max(0.0, float(alert_cooldown_seconds))
        self.verify_cooldown_seconds = max(0.0, float(verify_cooldown_seconds))
        self.verify_result_ttl_seconds = max(0.0, float(verify_result_ttl_seconds))
        self.moondream_conf_threshold = max(0.0, min(1.0, float(moondream_conf_threshold)))

        self.dangerous_labels = set(dangerous_labels or DEFAULT_DANGEROUS_LABELS)
        self.dangerous_labels = {label.strip().lower() for label in self.dangerous_labels if label.strip()}

        self.moondream_api_url = moondream_api_url or os.getenv("MOONDREAM_API_URL", "").strip() or None
        self.moondream_api_key = moondream_api_key or os.getenv("MOONDREAM_API_KEY", "").strip() or None
        self._moondream_model: Optional[Any] = None
        self._moondream_warned = False

        self._forwarder: Optional[VideoForwarder] = None
        self._owns_forwarder = False
        self._handler_registered = False
        self._processing_lock = asyncio.Lock()

        self._near_window: deque[bool] = deque(maxlen=self.near_window_size)
        self._last_alert_ts = 0.0
        self._last_verify_ts = 0.0
        self._last_log_ts = 0.0
        self._log_interval_seconds = 2.0
        self._frame_number = 0
        self._verify_attempted = False
        self._verify_result = {
            "is_dangerous": False,
            "confidence": 0.0,
            "reason": "not-verified",
            "primary_risk": "unknown",
            "timestamp": 0.0,
        }

        self.danger_present: bool = False
        self.latest_alert: Optional[dict[str, Any]] = None
        self.latest_candidate: Optional[dict[str, Any]] = None

    async def process_video(
        self,
        track: aiortc.VideoStreamTrack,
        participant_id: Optional[str],
        shared_forwarder: Optional[VideoForwarder] = None,
    ) -> None:
        _ = participant_id
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
                fps=self.fps,
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

    @staticmethod
    def _bbox_center(bbox: tuple[int, int, int, int]) -> tuple[float, float]:
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    @staticmethod
    def _bbox_area(bbox: tuple[int, int, int, int]) -> float:
        x1, y1, x2, y2 = bbox
        return max(0.0, float(x2 - x1)) * max(0.0, float(y2 - y1))

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
        union = ToddlerDangerGuard._bbox_area(a) + ToddlerDangerGuard._bbox_area(b) - inter
        if union <= 0:
            return 0.0
        return inter / union

    @staticmethod
    def _expand_bbox(
        bbox: tuple[int, int, int, int],
        frame_w: int,
        frame_h: int,
        ratio: float,
    ) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = bbox
        w = max(1.0, float(x2 - x1))
        h = max(1.0, float(y2 - y1))
        dx = int(round(w * ratio))
        dy = int(round(h * ratio))
        nx1 = max(0, x1 - dx)
        ny1 = max(0, y1 - dy)
        nx2 = min(frame_w - 1, x2 + dx)
        ny2 = min(frame_h - 1, y2 + dy)
        return (nx1, ny1, nx2, ny2)

    @staticmethod
    def _intersects(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        return not (ax2 < bx1 or bx2 < ax1 or ay2 < by1 or by2 < ay1)

    def _is_near(
        self,
        toddler_bbox: tuple[int, int, int, int],
        object_bbox: tuple[int, int, int, int],
        frame_w: int,
        frame_h: int,
    ) -> tuple[bool, float]:
        iou = self._bbox_iou(toddler_bbox, object_bbox)
        if iou > 0:
            return True, 0.0

        toddler_expanded = self._expand_bbox(toddler_bbox, frame_w, frame_h, self.expand_ratio)
        if self._intersects(toddler_expanded, object_bbox):
            return True, 0.0

        tcx, tcy = self._bbox_center(toddler_bbox)
        ocx, ocy = self._bbox_center(object_bbox)
        dx = tcx - ocx
        dy = tcy - ocy
        center_distance = (dx * dx + dy * dy) ** 0.5

        tw = max(1.0, float(toddler_bbox[2] - toddler_bbox[0]))
        th = max(1.0, float(toddler_bbox[3] - toddler_bbox[1]))
        toddler_diag = (tw * tw + th * th) ** 0.5
        near_threshold = self.center_distance_scale * toddler_diag
        return center_distance <= near_threshold, center_distance

    async def _on_frame(self, frame: av.VideoFrame) -> None:
        if self._processing_lock.locked():
            return

        async with self._processing_lock:
            image_bgr = frame.to_ndarray(format="bgr24")
            frame_h, frame_w = image_bgr.shape[:2]
            frame_number = self._frame_number
            self._frame_number += 1

            toddler_state = self.toddler_processor.state() if hasattr(self.toddler_processor, "state") else {}
            object_state = self.object_processor.state() if hasattr(self.object_processor, "state") else {}

            toddler_detections = toddler_state.get("detections", []) or []
            toddler_boxes = [
                det.get("bbox")
                for det in toddler_detections
                if str(det.get("label", "")).strip().lower() == "toddler" and det.get("bbox") is not None
            ]

            object_detections = object_state.get("detections", []) or []
            danger_objects = []
            for det in object_detections:
                label = str(det.get("label", "")).strip().lower()
                bbox = det.get("bbox")
                if label in self.dangerous_labels and bbox is not None:
                    danger_objects.append(det)

            best_candidate: Optional[dict[str, Any]] = None
            for toddler_bbox in toddler_boxes:
                if not isinstance(toddler_bbox, tuple):
                    continue
                for obj in danger_objects:
                    object_bbox = obj.get("bbox")
                    if not isinstance(object_bbox, tuple):
                        continue
                    near, distance_px = self._is_near(toddler_bbox, object_bbox, frame_w, frame_h)
                    if not near:
                        continue
                    candidate = {
                        "frame_number": frame_number,
                        "toddler_bbox": toddler_bbox,
                        "object_bbox": object_bbox,
                        "object_label": str(obj.get("label", "unknown")),
                        "object_confidence": float(obj.get("confidence", 0.0)),
                        "distance_px": float(distance_px),
                    }
                    if best_candidate is None:
                        best_candidate = candidate
                        continue
                    if candidate["distance_px"] < best_candidate["distance_px"]:
                        best_candidate = candidate
                        continue
                    if candidate["object_confidence"] > best_candidate["object_confidence"]:
                        best_candidate = candidate

            near_danger_now = best_candidate is not None and len(toddler_boxes) > 0
            self._near_window.append(near_danger_now)
            votes = sum(1 for item in self._near_window if item)

            if self.use_temporal_voting:
                should_verify = (
                    len(self._near_window) == self.near_window_size
                    and votes >= self.trigger_votes
                    and best_candidate is not None
                )
            else:
                should_verify = best_candidate is not None

            self._verify_attempted = False
            if should_verify and (time.time() - self._last_verify_ts >= self.verify_cooldown_seconds):
                self._verify_attempted = True
                verified = await asyncio.to_thread(self._verify_with_moondream, image_bgr, best_candidate)
                verify_ts = time.time()
                self._last_verify_ts = verify_ts
                self._verify_result = {
                    "is_dangerous": bool(verified.get("is_dangerous", False)),
                    "confidence": float(verified.get("confidence", 0.0) or 0.0),
                    "reason": str(verified.get("reason", "")),
                    "primary_risk": str(
                        verified.get("primary_risk", best_candidate.get("object_label", "unknown"))
                    ),
                    "timestamp": verify_ts,
                }

            now = time.time()
            verify_recent = (
                now - float(self._verify_result.get("timestamp", 0.0) or 0.0) <= self.verify_result_ttl_seconds
            )
            verify_ok = (
                should_verify
                and verify_recent
                and bool(self._verify_result.get("is_dangerous", False))
                and float(self._verify_result.get("confidence", 0.0) or 0.0) >= self.moondream_conf_threshold
            )
            should_alert = (
                verify_ok
                and (now - self._last_alert_ts >= self.alert_cooldown_seconds)
            )

            if should_alert and best_candidate is not None:
                self.danger_present = True
                self._last_alert_ts = now
                self.latest_alert = {
                    **best_candidate,
                    "reason": str(self._verify_result.get("reason", "")),
                    "risk_type": str(self._verify_result.get("primary_risk", best_candidate["object_label"])),
                    "moondream_confidence": float(self._verify_result.get("confidence", 0.0) or 0.0),
                    "timestamp": now,
                }
            elif self.danger_present and votes <= self.clear_votes:
                self.danger_present = False

            self.latest_candidate = best_candidate

            if now - self._last_log_ts >= self._log_interval_seconds:
                logger.info(
                    "danger-guard | toddler=%s danger_objs=%d near=%s votes=%d/%d verify_attempted=%s verify_ok=%s alert=%s",
                    len(toddler_boxes) > 0,
                    len(danger_objects),
                    near_danger_now,
                    votes,
                    self.near_window_size,
                    self._verify_attempted,
                    verify_ok,
                    self.danger_present,
                )
                self._last_log_ts = now

    def _verify_with_moondream(
        self,
        image_bgr: Any,
        candidate: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.moondream_api_key:
            if not self._moondream_warned:
                logger.warning("MOONDREAM_API_KEY not set; skipping Moondream verification.")
                self._moondream_warned = True
            return {
                "is_dangerous": False,
                "confidence": 0.0,
                "reason": "moondream-not-configured",
                "primary_risk": candidate.get("object_label", "unknown"),
            }

        try:
            if self._moondream_model is None:
                import moondream as md  # local import to avoid hard startup dependency

                self._moondream_model = md.vl(api_key=self.moondream_api_key)
        except Exception as exc:
            if not self._moondream_warned:
                logger.exception("Failed to initialize Moondream SDK: %s", exc)
                self._moondream_warned = True
            return {
                "is_dangerous": False,
                "confidence": 0.0,
                "reason": "moondream-init-failed",
                "primary_risk": candidate.get("object_label", "unknown"),
            }

        try:
            import cv2
            from PIL import Image

            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            image_pil = Image.fromarray(image_rgb)
        except Exception as exc:
            logger.exception("Moondream image preparation failed: %s", exc)
            return {
                "is_dangerous": False,
                "confidence": 0.0,
                "reason": "image-prep-error",
                "primary_risk": candidate.get("object_label", "unknown"),
            }

        prompt = (
            "A toddler is near a potentially dangerous object. "
            "Decide whether this scene is dangerous now. "
            "Return only JSON with keys: is_dangerous (bool), confidence (0-1), "
            "reason (string), primary_risk (string). "
            f"Context: toddler_bbox={candidate.get('toddler_bbox')}, "
            f"object_bbox={candidate.get('object_bbox')}, "
            f"object_label={candidate.get('object_label')}, "
            f"object_confidence={candidate.get('object_confidence')}, "
            f"distance_px={candidate.get('distance_px')}."
        )

        try:
            result = self._moondream_model.query(image_pil, prompt)
        except Exception as exc:
            logger.warning("Moondream query failed: %s", exc)
            return {
                "is_dangerous": False,
                "confidence": 0.0,
                "reason": "moondream-query-failed",
                "primary_risk": candidate.get("object_label", "unknown"),
            }

        answer = ""
        if isinstance(result, dict):
            answer = str(result.get("answer", "")).strip()
        elif result is not None:
            answer = str(result).strip()

        if not answer:
            return {
                "is_dangerous": False,
                "confidence": 0.0,
                "reason": "moondream-empty-answer",
                "primary_risk": candidate.get("object_label", "unknown"),
            }

        parsed: Optional[dict[str, Any]] = None
        try:
            parsed = json.loads(answer)
        except json.JSONDecodeError:
            left = answer.find("{")
            right = answer.rfind("}")
            if left != -1 and right != -1 and right > left:
                try:
                    parsed = json.loads(answer[left : right + 1])
                except json.JSONDecodeError:
                    parsed = None

        if isinstance(parsed, dict):
            try:
                conf = float(parsed.get("confidence", 0.0) or 0.0)
            except (TypeError, ValueError):
                conf = 0.0
            return {
                "is_dangerous": bool(parsed.get("is_dangerous", False)),
                "confidence": conf,
                "reason": str(parsed.get("reason", "")),
                "primary_risk": str(parsed.get("primary_risk", candidate.get("object_label", "unknown"))),
            }

        lower = answer.lower()
        inferred_danger = any(token in lower for token in ["danger", "hazard", "unsafe", "risk", "yes"])
        inferred_reason = answer[:240]

        return {
            "is_dangerous": inferred_danger,
            "confidence": 0.5 if inferred_danger else 0.0,
            "reason": inferred_reason,
            "primary_risk": candidate.get("object_label", "unknown"),
        }

    def state(self) -> dict[str, Any]:
        now = time.time()
        verify_recent = (
            now - float(self._verify_result.get("timestamp", 0.0) or 0.0) <= self.verify_result_ttl_seconds
        )
        return {
            "danger_present": self.danger_present,
            "alert": self.latest_alert,
            "candidate": self.latest_candidate,
            "near_votes": sum(1 for item in self._near_window if item),
            "near_window_size": self.near_window_size,
            "verify_attempted": self._verify_attempted,
            "verify_ok": verify_recent
            and bool(self._verify_result.get("is_dangerous", False))
            and float(self._verify_result.get("confidence", 0.0) or 0.0) >= self.moondream_conf_threshold,
            "verify_confidence": float(self._verify_result.get("confidence", 0.0) or 0.0),
            "verify_reason": str(self._verify_result.get("reason", "")),
            "verify_timestamp": float(self._verify_result.get("timestamp", 0.0) or 0.0),
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
