import asyncio
import base64
from datetime import datetime, timezone
import json
import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

import aiortc
import av
from vision_agents.core.processors import VideoProcessor
from vision_agents.core.utils.video_forwarder import VideoForwarder


logger = logging.getLogger(__name__)


class ZoneRiskGuard(VideoProcessor):
    """
    Scene-level risk-zone guard:
    1) On startup, asks Moondream for stairs/drop-off bbox.
    2) Tracks toddler bottom-center point against that zone.
    3) Alerts with hysteresis + cooldown.
    """

    name = "zone_risk_guard"

    def __init__(
        self,
        toddler_processor: Any,
        fps: float = 5.0,
        near_threshold_px: float = 40.0,
        near_trigger_count: int = 3,
        alert_cooldown_seconds: float = 20.0,
        zone_expand_ratio: float = 0.1,
        moondream_api_key: Optional[str] = None,
        debug_output_dir: Optional[str] = None,
        crossed_display_seconds: float = 3.0,
        init_after_frames: int = 0,
        init_retry_interval_frames: int = 30,
        max_init_attempts: int = 0,
    ) -> None:
        self.toddler_processor = toddler_processor
        self.fps = max(1.0, float(fps))
        self.near_threshold_px = max(0.0, float(near_threshold_px))
        self.near_trigger_count = max(1, int(near_trigger_count))
        self.alert_cooldown_seconds = max(0.0, float(alert_cooldown_seconds))
        self.zone_expand_ratio = max(0.0, float(zone_expand_ratio))
        self.crossed_display_seconds = max(0.0, float(crossed_display_seconds))
        self.init_after_frames = max(0, int(init_after_frames))
        self.init_retry_interval_frames = max(1, int(init_retry_interval_frames))
        self.max_init_attempts = max(0, int(max_init_attempts))

        self.moondream_api_key = moondream_api_key or os.getenv("MOONDREAM_API_KEY", "").strip() or None
        self.moondream_api_base = os.getenv("MOONDREAM_API_BASE", "https://api.moondream.ai").strip().rstrip("/")
        self.debug_output_dir = (
            Path(debug_output_dir)
            if debug_output_dir
            else Path(os.getenv("ZONE_RISK_DEBUG_DIR", "data/test_results/zone_risk"))
        )
        self._moondream_model: Optional[Any] = None
        self._moondream_warned = False
        self._moondream_log_path = self.debug_output_dir / "moondream_api_debug.jsonl"

        self._forwarder: Optional[VideoForwarder] = None
        self._owns_forwarder = False
        self._handler_registered = False
        self._processing_lock = asyncio.Lock()

        self._zone_initialized = False
        self._frame_counter = 0
        self._last_init_try_frame = -10**9
        self._init_attempts = 0
        self._last_alert_ts = 0.0
        self._last_cross_ts = 0.0
        self._near_count = 0
        self._prev_inside = False
        self._init_result: dict[str, Any] = {}

        self.stairs_zone: Optional[tuple[int, int, int, int]] = None
        self.stairs_zone_norm: Optional[tuple[float, float, float, float]] = None
        self.stairs_zone_reason: str = ""
        self.latest_baby_point: Optional[tuple[int, int]] = None
        self.latest_distance_px: Optional[float] = None
        self.latest_status: str = "ZONE_NOT_READY"
        self.alert_active: bool = False
        self.latest_alert: Optional[dict[str, Any]] = None

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

    async def _on_frame(self, frame: av.VideoFrame) -> None:
        if self._processing_lock.locked():
            return

        async with self._processing_lock:
            image_bgr = frame.to_ndarray(format="bgr24")
            frame_h, frame_w = image_bgr.shape[:2]
            self._frame_counter += 1

            should_attempt_init = (
                self.stairs_zone is None
                and self._frame_counter > self.init_after_frames
                and (self._frame_counter - self._last_init_try_frame) >= self.init_retry_interval_frames
                and (self.max_init_attempts == 0 or self._init_attempts < self.max_init_attempts)
            )
            if should_attempt_init:
                self._last_init_try_frame = self._frame_counter
                self._init_attempts += 1
                zone, init_result = await asyncio.to_thread(self._detect_stairs_zone, image_bgr, frame_w, frame_h)
                self._init_result = init_result
                if zone is not None:
                    self._zone_initialized = True
                    expanded = self._expand_bbox(zone, frame_w, frame_h, self.zone_expand_ratio)
                    self._set_locked_zone(expanded, frame_w, frame_h)
                    self.stairs_zone_reason = "moondream-detected"
                    logger.info("ZoneRiskGuard initialized stairs zone=%s", self.stairs_zone)
                else:
                    self.stairs_zone_reason = "stairs-not-found"
                    logger.warning(
                        "ZoneRiskGuard could not initialize stairs zone from Moondream "
                        "(attempt %d).",
                        self._init_attempts,
                    )
                self._save_zone_snapshot(image_bgr)
                self._save_init_result()

            self.latest_baby_point = None
            self.latest_distance_px = None

            # Keep locked zone aligned if frame size changes; do not re-detect.
            if self.stairs_zone_norm is not None:
                self.stairs_zone = self._norm_to_bbox(self.stairs_zone_norm, frame_w=frame_w, frame_h=frame_h)

            if self.stairs_zone is None:
                self.latest_status = "ZONE_NOT_READY"
                self._near_count = 0
                self.alert_active = False
                return

            toddler_box = self._get_primary_toddler_bbox()
            if toddler_box is None:
                self.latest_status = "NO_TODDLER"
                self._near_count = max(0, self._near_count - 1)
                if self._near_count == 0:
                    self.alert_active = False
                self._prev_inside = False
                return

            tx1, ty1, tx2, ty2 = toddler_box
            baby_point = ((tx1 + tx2) // 2, ty2)
            self.latest_baby_point = baby_point

            inside = self._point_in_rect(baby_point, self.stairs_zone)
            distance_px = self._point_rect_distance(baby_point, self.stairs_zone)
            self.latest_distance_px = distance_px

            near_now = inside or (distance_px <= self.near_threshold_px)
            crossed_now = (not self._prev_inside) and inside
            self._prev_inside = inside
            if crossed_now:
                self._last_cross_ts = time.time()

            if near_now:
                self._near_count = min(self.near_trigger_count + 2, self._near_count + 1)
            else:
                self._near_count = max(0, self._near_count - 1)

            status = "SAFE"
            if inside:
                status = f"INSIDE_STAIRS_ZONE ({self._near_count}/{self.near_trigger_count})"
            elif near_now:
                status = f"NEAR_STAIRS ({self._near_count}/{self.near_trigger_count})"
            self.latest_status = status

            now = time.time()
            if self._near_count >= self.near_trigger_count:
                self.alert_active = True
                if (now - self._last_alert_ts) >= self.alert_cooldown_seconds:
                    self._last_alert_ts = now
                    self.latest_alert = {
                        "timestamp": now,
                        "reason": "Toddler near stairs/drop-off area.",
                        "crossed": crossed_now,
                        "inside_zone": inside,
                        "distance_px": float(distance_px),
                        "near_count": int(self._near_count),
                        "threshold_count": int(self.near_trigger_count),
                        "baby_point": baby_point,
                        "zone_bbox": self.stairs_zone,
                    }
            elif self._near_count == 0:
                self.alert_active = False

    def _detect_stairs_zone(
        self,
        image_bgr: Any,
        frame_w: int,
        frame_h: int,
    ) -> tuple[Optional[tuple[int, int, int, int]], dict[str, Any]]:
        if not self.moondream_api_key:
            if not self._moondream_warned:
                logger.warning("MOONDREAM_API_KEY not set; zone detection disabled.")
                self._moondream_warned = True
            return None, {"error": "missing_moondream_api_key"}

        try:
            import cv2
            ok, encoded = cv2.imencode(".jpg", image_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if not ok:
                return None
            image_b64 = base64.b64encode(encoded.tobytes()).decode("ascii")
            data_url = f"data:image/jpeg;base64,{image_b64}"
        except Exception as exc:
            logger.exception("Zone image conversion failed: %s", exc)
            return None, {"error": f"image_conversion_failed: {exc}"}

        # Step 1: Query for unsafe place names in the scene.
        question = (
            "Identify places in this image a toddler should not go near. "
            "Return JSON only: "
            '{"unsafe_places":["stairs","balcony","pool","fireplace","stove","window_edge"]}.'
        )
        query_payload = {"image_url": data_url, "question": question}
        query_response = self._moondream_post("/v1/query", query_payload)
        init_result: dict[str, Any] = {
            "query_payload": self._sanitize_payload_for_log(query_payload),
            "query_response": query_response,
            "place_names": [],
            "detect_attempts": [],
            "selected_place": None,
            "selected_bbox": None,
        }
        if query_response is None:
            return None, init_result

        place_names = self._extract_place_names(query_response)
        init_result["place_names"] = place_names
        if not place_names:
            logger.info("ZoneRiskGuard: no unsafe places returned by Moondream query.")
            return None, init_result

        # Prefer stairs-like regions when available.
        stairs_candidates = [name for name in place_names if "stair" in name]
        if stairs_candidates:
            place_names = stairs_candidates

        # Step 2: Detect boundaries for each returned place.
        for place in place_names:
            detect_payload = {"image_url": data_url, "object": place}
            detect_response = self._moondream_post("/v1/detect", detect_payload)
            init_result["detect_attempts"].append(
                {
                    "place": place,
                    "payload": self._sanitize_payload_for_log(detect_payload),
                    "response": detect_response,
                }
            )
            if detect_response is None:
                continue
            bbox = self._extract_detect_bbox(detect_response, frame_w=frame_w, frame_h=frame_h)
            if bbox is not None:
                self.stairs_zone_reason = f"detected:{place}"
                init_result["selected_place"] = place
                init_result["selected_bbox"] = bbox
                return bbox, init_result

        return None, init_result

    def _save_init_result(self) -> None:
        try:
            self.debug_output_dir.mkdir(parents=True, exist_ok=True)
            ts = int(time.time())
            path = self.debug_output_dir / f"zone_init_{ts}_response.json"
            payload = {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "frame_counter": self._frame_counter,
                "init_after_frames": self.init_after_frames,
                "zone_reason": self.stairs_zone_reason,
                "zone_bbox": self.stairs_zone,
                "moondream_init_result": self._init_result,
            }
            path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
            logger.info("ZoneRiskGuard saved init response: %s", path)
        except Exception as exc:
            logger.warning("ZoneRiskGuard failed to save init response: %s", exc)

    def _set_locked_zone(
        self,
        bbox: tuple[int, int, int, int],
        frame_w: int,
        frame_h: int,
    ) -> None:
        self.stairs_zone = bbox
        self.stairs_zone_norm = self._bbox_to_norm(bbox, frame_w=frame_w, frame_h=frame_h)

    @staticmethod
    def _bbox_to_norm(
        bbox: tuple[int, int, int, int],
        frame_w: int,
        frame_h: int,
    ) -> tuple[float, float, float, float]:
        fw = max(1.0, float(frame_w))
        fh = max(1.0, float(frame_h))
        x1, y1, x2, y2 = bbox
        return (
            max(0.0, min(1.0, float(x1) / fw)),
            max(0.0, min(1.0, float(y1) / fh)),
            max(0.0, min(1.0, float(x2) / fw)),
            max(0.0, min(1.0, float(y2) / fh)),
        )

    @staticmethod
    def _norm_to_bbox(
        bbox_norm: tuple[float, float, float, float],
        frame_w: int,
        frame_h: int,
    ) -> tuple[int, int, int, int]:
        x1n, y1n, x2n, y2n = bbox_norm
        x1 = int(round(x1n * frame_w))
        y1 = int(round(y1n * frame_h))
        x2 = int(round(x2n * frame_w))
        y2 = int(round(y2n * frame_h))
        x1 = max(0, min(frame_w - 1, x1))
        y1 = max(0, min(frame_h - 1, y1))
        x2 = max(0, min(frame_w - 1, x2))
        y2 = max(0, min(frame_h - 1, y2))
        if x2 <= x1:
            x2 = min(frame_w - 1, x1 + 1)
        if y2 <= y1:
            y2 = min(frame_h - 1, y1 + 1)
        return (x1, y1, x2, y2)

    def _moondream_post(self, path: str, payload: dict[str, Any]) -> Optional[dict[str, Any]]:
        if not self.moondream_api_key:
            self._append_moondream_log(
                {
                    "path": path,
                    "ok": False,
                    "error": "missing_moondream_api_key",
                }
            )
            return None
        url = f"{self.moondream_api_base}{path}"
        headers = {
            "Content-Type": "application/json",
            "X-Moondream-Auth": self.moondream_api_key,
            "Accept": "*/*",
            "User-Agent": "curl/8.7.1",
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url=url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                parsed = json.loads(raw)
                self._append_moondream_log(
                    {
                        "path": path,
                        "ok": True,
                        "request": self._sanitize_payload_for_log(payload),
                        "response_raw": raw,
                    }
                )
                if isinstance(parsed, dict):
                    return parsed
                self._append_moondream_log(
                    {
                        "path": path,
                        "ok": False,
                        "request": self._sanitize_payload_for_log(payload),
                        "error": "non_dict_json_response",
                        "response_raw": raw,
                    }
                )
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except Exception:
                detail = str(exc)
            headers_text = ""
            try:
                headers_text = str(exc.headers)
            except Exception:
                headers_text = "<unavailable>"
            logger.warning(
                "Moondream HTTP error %s for %s reason=%s headers=%s body=%s",
                exc.code,
                path,
                getattr(exc, "reason", ""),
                headers_text,
                detail,
            )
            print(
                f"[ZoneRiskGuard][ERROR] endpoint={path} status={exc.code} "
                f"reason={getattr(exc, 'reason', '')} headers={headers_text} body={detail}"
            )
            self._append_moondream_log(
                {
                    "path": path,
                    "ok": False,
                    "request": self._sanitize_payload_for_log(payload),
                    "error_type": "http_error",
                    "status_code": int(exc.code),
                    "reason": str(getattr(exc, "reason", "")),
                    "headers": headers_text,
                    "error_detail": detail,
                }
            )
        except Exception as exc:
            logger.warning("Moondream request failed for %s: %s", path, exc)
            print(f"[ZoneRiskGuard] Moondream request failed for {path}: {exc}")
            self._append_moondream_log(
                {
                    "path": path,
                    "ok": False,
                    "request": self._sanitize_payload_for_log(payload),
                    "error_type": "request_exception",
                    "error_detail": str(exc),
                }
            )
        return None

    @staticmethod
    def _sanitize_payload_for_log(payload: dict[str, Any]) -> dict[str, Any]:
        """
        Keep logs readable by stripping huge base64 content.
        """
        out = dict(payload)
        image_url = out.get("image_url")
        if isinstance(image_url, str) and image_url.startswith("data:image"):
            out["image_url"] = f"<data-url length={len(image_url)}>"
        return out

    def _append_moondream_log(self, event: dict[str, Any]) -> None:
        try:
            self.debug_output_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                **event,
            }
            with self._moondream_log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=True) + "\n")
        except Exception as exc:
            logger.warning("ZoneRiskGuard failed to append Moondream log: %s", exc)

    @staticmethod
    def _extract_json_obj(text: str) -> Optional[dict[str, Any]]:
        parsed: Optional[dict[str, Any]] = None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            left = text.find("{")
            right = text.rfind("}")
            if left != -1 and right != -1 and right > left:
                try:
                    parsed = json.loads(text[left : right + 1])
                except json.JSONDecodeError:
                    parsed = None
        return parsed if isinstance(parsed, dict) else None

    def _extract_place_names(self, response: dict[str, Any]) -> list[str]:
        names: list[str] = []
        answer = str(response.get("answer", "")).strip()
        parsed = self._extract_json_obj(answer) if answer else None
        if isinstance(parsed, dict):
            raw_places = parsed.get("unsafe_places")
            if isinstance(raw_places, list):
                for item in raw_places:
                    if item is None:
                        continue
                    label = str(item).strip().lower()
                    if label:
                        names.append(label)

        if not names and answer:
            lower = answer.lower()
            keywords = [
                "stairs",
                "staircase",
                "balcony",
                "edge",
                "drop-off",
                "drop off",
                "fireplace",
                "stove",
                "pool",
            ]
            for key in keywords:
                if key in lower:
                    names.append("stairs" if key in {"staircase"} else key.replace(" ", "_"))

        # Deduplicate while preserving order.
        seen = set()
        out: list[str] = []
        for n in names:
            if n in seen:
                continue
            seen.add(n)
            out.append(n)
        return out

    def _extract_detect_bbox(
        self,
        response: dict[str, Any],
        frame_w: int,
        frame_h: int,
    ) -> Optional[tuple[int, int, int, int]]:
        # Handle common response structures from detect APIs.
        candidates: list[Any] = []
        if isinstance(response.get("objects"), list):
            candidates.extend(response.get("objects") or [])
        if isinstance(response.get("detections"), list):
            candidates.extend(response.get("detections") or [])

        # Some APIs return a plain list in "answer" as JSON string.
        answer = response.get("answer")
        if isinstance(answer, str):
            parsed = self._extract_json_obj(answer)
            if isinstance(parsed, dict):
                if isinstance(parsed.get("objects"), list):
                    candidates.extend(parsed.get("objects") or [])
                if isinstance(parsed.get("detections"), list):
                    candidates.extend(parsed.get("detections") or [])

        best_bbox: Optional[tuple[int, int, int, int]] = None
        best_conf = -1.0
        for item in candidates:
            if not isinstance(item, dict):
                continue
            bbox = (
                item.get("bbox")
                or item.get("box")
                or item.get("bounds")
                or item.get("xyxy")
            )
            if bbox is None:
                x_min = item.get("x_min")
                y_min = item.get("y_min")
                x_max = item.get("x_max")
                y_max = item.get("y_max")
                if None not in (x_min, y_min, x_max, y_max):
                    bbox = [x_min, y_min, x_max, y_max]
            normalized = self._normalize_bbox(bbox, frame_w=frame_w, frame_h=frame_h)
            if normalized is None:
                continue
            try:
                conf = float(item.get("confidence", item.get("score", 0.0)) or 0.0)
            except (TypeError, ValueError):
                conf = 0.0
            if conf >= best_conf:
                best_conf = conf
                best_bbox = normalized
        return best_bbox

    def _save_zone_snapshot(self, image_bgr: Any) -> None:
        """
        Save the startup frame with zone markup for debugging/demo visibility.
        """
        try:
            import cv2

            self.debug_output_dir.mkdir(parents=True, exist_ok=True)
            ts = int(time.time())
            base_name = f"zone_init_{ts}"

            raw_path = self.debug_output_dir / f"{base_name}_raw.jpg"
            marked_path = self.debug_output_dir / f"{base_name}_marked.jpg"

            cv2.imwrite(str(raw_path), image_bgr)

            marked = image_bgr.copy()
            if self.stairs_zone is not None:
                x1, y1, x2, y2 = self.stairs_zone
                cv2.rectangle(marked, (x1, y1), (x2, y2), (0, 0, 255), 3)
                cv2.putText(
                    marked,
                    "STAIRS/DROP-OFF ZONE",
                    (max(0, x1), max(20, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255),
                    2,
                    cv2.LINE_AA,
                )
            else:
                cv2.putText(
                    marked,
                    "ZONE_NOT_FOUND",
                    (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 165, 255),
                    2,
                    cv2.LINE_AA,
                )
            cv2.imwrite(str(marked_path), marked)
            logger.info("ZoneRiskGuard saved zone snapshots: %s, %s", raw_path, marked_path)
        except Exception as exc:
            logger.warning("ZoneRiskGuard failed to save zone snapshot: %s", exc)

    @staticmethod
    def _normalize_bbox(
        bbox: Any,
        frame_w: int,
        frame_h: int,
    ) -> Optional[tuple[int, int, int, int]]:
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            return None
        vals: list[float] = []
        for item in bbox:
            try:
                vals.append(float(item))
            except (TypeError, ValueError):
                return None

        # If values look normalized, scale to pixels.
        if all(0.0 <= v <= 1.0 for v in vals):
            vals[0] *= frame_w
            vals[2] *= frame_w
            vals[1] *= frame_h
            vals[3] *= frame_h

        x1, y1, x2, y2 = [int(round(v)) for v in vals]
        x1 = max(0, min(frame_w - 1, x1))
        y1 = max(0, min(frame_h - 1, y1))
        x2 = max(0, min(frame_w - 1, x2))
        y2 = max(0, min(frame_h - 1, y2))
        if x2 <= x1 or y2 <= y1:
            return None
        return (x1, y1, x2, y2)

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

    def _get_primary_toddler_bbox(self) -> Optional[tuple[int, int, int, int]]:
        if self.toddler_processor is None or not hasattr(self.toddler_processor, "state"):
            return None
        try:
            toddler_state = self.toddler_processor.state() or {}
        except Exception:
            return None

        detections = toddler_state.get("detections", []) or []
        best_bbox: Optional[tuple[int, int, int, int]] = None
        best_area = -1
        for det in detections:
            if str(det.get("label", "")).strip().lower() != "toddler":
                continue
            bbox = det.get("bbox")
            if not isinstance(bbox, tuple) or len(bbox) != 4:
                continue
            x1, y1, x2, y2 = bbox
            area = max(0, x2 - x1) * max(0, y2 - y1)
            if area > best_area:
                best_area = area
                best_bbox = bbox
        return best_bbox

    @staticmethod
    def _point_in_rect(point: tuple[int, int], rect: tuple[int, int, int, int]) -> bool:
        px, py = point
        x1, y1, x2, y2 = rect
        return x1 <= px <= x2 and y1 <= py <= y2

    @staticmethod
    def _point_rect_distance(point: tuple[int, int], rect: tuple[int, int, int, int]) -> float:
        px, py = point
        x1, y1, x2, y2 = rect
        cx = min(max(px, x1), x2)
        cy = min(max(py, y1), y2)
        dx = float(px - cx)
        dy = float(py - cy)
        return (dx * dx + dy * dy) ** 0.5

    def state(self) -> dict[str, Any]:
        return {
            "zone_ready": self.stairs_zone is not None,
            "zone_bbox": self.stairs_zone,
            "zone_locked": self.stairs_zone is not None,
            "zone_reason": self.stairs_zone_reason,
            "init_attempts": self._init_attempts,
            "init_retry_interval_frames": self.init_retry_interval_frames,
            "baby_point": self.latest_baby_point,
            "distance_px": self.latest_distance_px,
            "near_count": self._near_count,
            "near_trigger_count": self.near_trigger_count,
            "status": self.latest_status,
            "crossed_recent": (time.time() - self._last_cross_ts) <= self.crossed_display_seconds,
            "alert_active": self.alert_active,
            "alert": self.latest_alert,
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
