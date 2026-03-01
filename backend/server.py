import asyncio
import logging
import os
import time

from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

from vision_agents.core import Agent, AgentLauncher, Runner, User
from vision_agents.plugins import cartesia, gemini, getstream
from processors.object_detection import ObjectDetectionProcessor
from processors.toddler_processor import ToddlerProcessor
from processors.fall_detection import FallDetectionProcessor
from processors.toddler_danger_guard import ToddlerDangerGuard
from processors.combined_video_publisher import CombinedVideoPublisher
from processors.zone_risk_guard import ZoneRiskGuard
from processors.crying_audio_detector import CryingAudioDetector
from processors.face_recognition import FaceRecognitionProcessor
from processor_registry import set_crying_detector, set_face_recognizer, set_zone_guard
from routes import video_router, audio_router, faces_router, auth_router
from tools.alert_sink import write_alert
from video_stream_registry import set_publisher
from database.db_utils import ensure_default_camera, log_safety_event

load_dotenv()
logging.basicConfig(level=logging.INFO)


async def create_agent(**kwargs) -> Agent:
    _ = kwargs
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-3-flash")
    zone_fps = float(os.getenv("ZONE_RISK_FPS", "5.0"))
    zone_near_threshold_px = float(os.getenv("ZONE_RISK_NEAR_THRESHOLD_PX", "40.0"))
    zone_near_trigger_count = int(os.getenv("ZONE_RISK_NEAR_TRIGGER_COUNT", "3"))
    zone_alert_cooldown_seconds = float(os.getenv("ZONE_RISK_ALERT_COOLDOWN_SECONDS", "20.0"))
    zone_expand_ratio = float(os.getenv("ZONE_RISK_EXPAND_RATIO", "0.1"))
    zone_crossed_display_seconds = float(os.getenv("ZONE_RISK_CROSSED_DISPLAY_SECONDS", "3.0"))
    zone_init_after_frames = int(os.getenv("ZONE_RISK_INIT_AFTER_FRAMES", "0"))
    zone_init_retry_interval_frames = int(os.getenv("ZONE_RISK_INIT_RETRY_INTERVAL_FRAMES", "30"))
    zone_max_init_attempts = int(os.getenv("ZONE_RISK_MAX_INIT_ATTEMPTS", "0"))
    zone_debug_dir = os.getenv("ZONE_RISK_DEBUG_DIR", "data/test_results/zone_risk")
    face_recognition_enabled = os.getenv("FACE_RECOGNITION_ENABLED", "true").lower() == "true"
    face_det_thresh = float(os.getenv("FACE_DET_THRESH", "0.35"))
    face_match_threshold = float(os.getenv("FACE_MATCH_THRESHOLD", "0.35"))

    object_processor = ObjectDetectionProcessor(
        fps=1.0,
        model_path="yolo11m.pt",
        confidence_threshold=0.5,
        danger_confidence_threshold=0.1,
        danger_second_pass_confidence=0.1,
    )
    fall_processor = FallDetectionProcessor(
        fps=1,
        fall_window_size=5,
        required_fall_frames=5,
    )
    toddler_processor = ToddlerProcessor(fps=1) if os.getenv("ROBOFLOW_API_KEY") else None
    object_processor.bind_toddler_processor(toddler_processor)
    fall_processor.bind_toddler_processor(toddler_processor)
    danger_guard = (
        ToddlerDangerGuard(
            toddler_processor=toddler_processor,
            object_processor=object_processor,
            fps=1.0,
            use_temporal_voting=False,
            near_window_size=5,
            trigger_votes=3,
            clear_votes=1,
            moondream_conf_threshold=0.65,
            alert_cooldown_seconds=20.0,
        )
        if toddler_processor is not None
        else None
    )
    zone_guard = (
        ZoneRiskGuard(
            toddler_processor=toddler_processor,
            fps=zone_fps,
            near_threshold_px=zone_near_threshold_px,
            near_trigger_count=zone_near_trigger_count,
            alert_cooldown_seconds=zone_alert_cooldown_seconds,
            zone_expand_ratio=zone_expand_ratio,
            debug_output_dir=zone_debug_dir,
            crossed_display_seconds=zone_crossed_display_seconds,
            init_after_frames=zone_init_after_frames,
            init_retry_interval_frames=zone_init_retry_interval_frames,
            max_init_attempts=zone_max_init_attempts,
        )
        if toddler_processor is not None
        else None
    )
    face_processor = None
    if face_recognition_enabled:
        try:
            face_processor = FaceRecognitionProcessor(
                fps=2.0,
                gallery_dir="data/known_faces",
                det_thresh=face_det_thresh,
                match_threshold=face_match_threshold,
            )
        except Exception as exc:
            logging.warning("FaceRecognitionProcessor disabled: %s", exc)
            face_processor = None
    set_face_recognizer(face_processor)

    
    # Ensure default camera exists in the DB for foreign key constraints
    await ensure_default_camera()
    
    object_processor = ObjectDetectionProcessor(fps=1.0, confidence_threshold=0.5)
    fall_processor = FallDetectionProcessor(fps=2.0)
    toddler_processor = ToddlerProcessor(fps=1) if os.getenv("ROBOFLOW_API_KEY") else None
    
    combined_publisher = CombinedVideoPublisher(
        object_processor=object_processor,
        toddler_processor=toddler_processor,
        fall_processor=fall_processor,
        danger_guard=danger_guard,
        zone_guard=zone_guard,
        face_processor=face_processor,
        fps=10.0,
    )
    set_publisher(combined_publisher)
    set_zone_guard(zone_guard)

    crying_detector = CryingAudioDetector()
    set_crying_detector(crying_detector)

<<<<<<< Updated upstream
    processors: list = []
=======
    # Initialize processor list with all components
    processors: list = [object_processor, fall_processor, crying_detector]
    
>>>>>>> Stashed changes
    if toddler_processor is not None:
        processors.append(toddler_processor)
    if zone_guard is not None:
        processors.append(zone_guard)
    processors.extend([object_processor, fall_processor])
    if danger_guard is not None:
        processors.append(danger_guard)
    if face_processor is not None:
        processors.append(face_processor)
    processors.append(combined_publisher)

    if crying_detector:
        print("initialised crying detector")

    tts_engine = cartesia.TTS() if os.getenv("CARTESIA_API_KEY") else None

    agent = Agent(
        edge=getstream.Edge(),
        agent_user=User(name="Safety Monitor", id="agent"),
        instructions=(
            "You are a child safety monitoring AI. "
            "Alert on dangers and analyze incoming events concisely."
        ),
        llm=gemini.LLM(model=gemini_model),
        tts=tts_engine,
        processors=processors,
    )
    
    # Attach processors to agent for easier access in join_call
    agent._fall_processor = fall_processor
    agent._object_processor = object_processor
    agent._toddler_processor = toddler_processor
    try:
        agent._crying_detector = crying_detector
    except NameError:
        agent._crying_detector = None

    # agent._toddler_processor = toddler_processor
    agent._fall_processor = fall_processor
    agent._danger_guard = danger_guard
    agent._zone_guard = zone_guard
    agent._face_processor = face_processor

    return agent


async def join_call(agent: Agent, call_type: str, call_id: str, **kwargs) -> None:
    _ = kwargs
    face_processor = getattr(agent, "_face_processor", None)
    if face_processor is not None and hasattr(face_processor, "set_active_call_id"):
        try:
            face_processor.set_active_call_id(call_id)
        except Exception:
            pass
    # Stream edge transport relies on agent user initialization before call creation.
    await agent.create_user()
    call = await agent.create_call(call_type, call_id)
    async with agent.join(call):
<<<<<<< Updated upstream
        async def safe_speak(text: str) -> None:
            try:
                await agent.simple_response(text)
            except Exception as exc:
                logging.warning("TTS/LLM speak skipped due to provider/quota error: %s", exc)

        startup_speech_enabled = os.getenv("STARTUP_SPEECH_ENABLED", "false").lower() == "true"
        if startup_speech_enabled:
            await safe_speak("Safety monitoring active.")
        fall_processor = getattr(agent, "_fall_processor", None)
        danger_guard = getattr(agent, "_danger_guard", None)
        zone_guard = getattr(agent, "_zone_guard", None)
        face_processor = getattr(agent, "_face_processor", None)
        # toddler_processor = getattr(agent, "_toddler_processor", None)
        fall_announced = False
        danger_announced = False
        zone_announced = False
        last_danger_speech_ts = 0.0
        last_danger_key = None
        last_zone_speech_ts = 0.0
        last_zone_key = None
        speech_cooldown_seconds = float(os.getenv("DANGER_SPEECH_COOLDOWN_SECONDS", "20.0"))
        zone_speech_cooldown_seconds = float(
            os.getenv("ZONE_SPEECH_COOLDOWN_SECONDS", str(speech_cooldown_seconds))
        )
        unknown_face_announced_ts: float | None = None
        try:
            while True:
                await asyncio.sleep(0.25)
                if fall_processor is not None:
                    fall_now = bool(fall_processor.state().get("fall_present", False))
                    if fall_now and not fall_announced:
                        fall_state = fall_processor.state()
                        fall_det = {}
                        for det in (fall_state.get("detections", []) or []):
                            if det.get("is_falling", False):
                                fall_det = det
                                break
                        write_alert(
                            {
                                "alert_type": "fall_detected",
                                "call_type": call_type,
                                "call_id": call_id,
                                "risk": "fall",
                                "reason": "Fall detected by fall processor.",
                                "confidence": float(fall_det.get("confidence", 0.0) or 0.0),
                                "bbox": fall_det.get("bbox"),
                            }
                        )
                        fall_conf = float(fall_det.get("confidence", 0.0) or 0.0)
                        if fall_conf > 0:
                            await safe_speak(
                                f"Warning. Toddler fall detected. Confidence {fall_conf:.2f}."
                            )
                        else:
                            await safe_speak("Warning. Toddler fall detected.")
                        fall_announced = True
                    elif not fall_now and fall_announced:
                        fall_announced = False

                if danger_guard is not None:
                    danger_state = danger_guard.state()
                    danger_now = bool(danger_state.get("danger_present", False))
                    if danger_now and not danger_announced:
                        alert = danger_state.get("alert") or {}
                        risk = str(alert.get("risk_type") or alert.get("object_label") or "danger")
                        reason = str(alert.get("reason", "")).strip()
                        confidence = float(alert.get("moondream_confidence", 0.0) or 0.0)
                        write_alert(
                            {
                                "alert_type": "danger_object_near_toddler",
                                "call_type": call_type,
                                "call_id": call_id,
                                "risk": risk,
                                "reason": reason or "Dangerous object close to toddler.",
                                "confidence": confidence,
                                "object_label": alert.get("object_label"),
                                "toddler_bbox": alert.get("toddler_bbox"),
                                "object_bbox": alert.get("object_bbox"),
                            }
                        )
                        danger_key = f"{risk}|{alert.get('object_bbox')}|{alert.get('toddler_bbox')}"
                        now_ts = time.time()
                        if (
                            danger_key != last_danger_key
                            or (now_ts - last_danger_speech_ts) >= speech_cooldown_seconds
                        ):
                            msg = f"Warning. {risk} is dangerously close to the toddler."
                            if reason:
                                msg = f"{msg} {reason}"
                            if confidence > 0:
                                msg = f"{msg} Confidence {confidence:.2f}."
                            await safe_speak(msg)
                            last_danger_speech_ts = now_ts
                            last_danger_key = danger_key
                        danger_announced = True
                    elif not danger_now and danger_announced:
                        danger_announced = False
                        last_danger_key = None

                if zone_guard is not None:
                    zone_state = zone_guard.state()
                    zone_now = bool(zone_state.get("alert_active", False))
                    if zone_now and not zone_announced:
                        zone_alert = zone_state.get("alert") or {}
                        zone_bbox = zone_state.get("zone_bbox")
                        baby_point = zone_state.get("baby_point")
                        distance_px = float(zone_state.get("distance_px", 0.0) or 0.0)
                        crossed = bool(zone_alert.get("crossed", False))
                        inside_zone = bool(zone_alert.get("inside_zone", False))
                        write_alert(
                            {
                                "alert_type": "baby_near_stairs_zone",
                                "call_type": call_type,
                                "call_id": call_id,
                                "risk": "stairs",
                                "reason": "Toddler near or inside stairs/drop-off zone.",
                                "distance_px": distance_px,
                                "crossed": crossed,
                                "inside_zone": inside_zone,
                                "zone_bbox": zone_bbox,
                                "baby_point": baby_point,
                            }
                        )
                        zone_key = f"stairs|{zone_bbox}|{baby_point}"
                        now_ts = time.time()
                        if (
                            zone_key != last_zone_key
                            or (now_ts - last_zone_speech_ts) >= zone_speech_cooldown_seconds
                        ):
                            if inside_zone:
                                msg = "Warning. Baby is inside the stairs danger zone."
                            elif crossed:
                                msg = "Warning. Baby crossed into the stairs danger zone."
                            else:
                                msg = "Warning. Baby is too close to stairs."
                            await safe_speak(msg)
                            last_zone_speech_ts = now_ts
                            last_zone_key = zone_key
                        zone_announced = True
                    elif not zone_now and zone_announced:
                        zone_announced = False
                        last_zone_key = None

                if face_processor is not None:
                    face_state = face_processor.state() if hasattr(face_processor, "state") else {}
                    if bool(face_state.get("unknown_detected", False)):
                        now_ts = time.time()
                        if unknown_face_announced_ts is None or (now_ts - unknown_face_announced_ts) >= 10.0:
                            write_alert(
                                {
                                    "alert_type": "unknown_face_detected",
                                    "call_type": call_type,
                                    "call_id": call_id,
                                    "risk": "unknown_person",
                                    "reason": "Unknown face detected while monitoring toddler.",
                                }
                            )
                            await safe_speak("Warning. Unknown person detected near the child.")
                            unknown_face_announced_ts = now_ts

                # Unknown face alerts disabled for this config
=======
        await agent.simple_response("Safety monitoring active.")
        
        fall_processor = getattr(agent, "_fall_processor", None)
        object_processor = getattr(agent, "_object_processor", None)
        toddler_processor = getattr(agent, "_toddler_processor", None)
        crying_detector = getattr(agent, "_crying_detector", None)
        
        fall_announced = False
        last_logged = {
            "fall": 0,
            "object": 0,
            "toddler": 0,
            "crying": 0
        }
        cooldown_sec = 5.0  # Debounce events so we don't spam the database
        
        try:
            while True:
                await asyncio.sleep(0.5)
                current_time = time.time()
                
                # Check Fall
                if fall_processor:
                    fall_state = fall_processor.state()
                    fall_now = bool(fall_state.get("fall_detected", False))
                    if fall_now:
                        if not fall_announced:
                            await agent.simple_response("Fall detected")
                            fall_announced = True
                        
                        if current_time - last_logged["fall"] > cooldown_sec:
                            await log_safety_event(event_type="FallDetected", metadata=fall_state)
                            last_logged["fall"] = current_time
                    elif not fall_now and fall_announced:
                        fall_announced = False
                
                # Check Object
                if object_processor:
                    obj_state = object_processor.state()
                    if obj_state.get("objects"):
                        if current_time - last_logged["object"] > cooldown_sec:
                            await log_safety_event(event_type="ObjectDetected", metadata=obj_state)
                            last_logged["object"] = current_time
                
                # Check Toddler
                if toddler_processor:
                    tod_state = toddler_processor.state()
                    if tod_state.get("toddler_detected", False):
                        if current_time - last_logged["toddler"] > cooldown_sec:
                            await log_safety_event(event_type="ToddlerDetected", metadata=tod_state)
                            last_logged["toddler"] = current_time
                            
                # Check Crying
                if crying_detector:
                    cry_state = crying_detector.state()
                    if cry_state.get("crying_detected", False):
                        if current_time - last_logged["crying"] > cooldown_sec:
                            await log_safety_event(event_type="CryingDetected", metadata=cry_state)
                            last_logged["crying"] = current_time

>>>>>>> Stashed changes
        finally:
            await agent.finish()


from routes.reports import router as reports_router

if __name__ == "__main__":
    runner = Runner(
        AgentLauncher(
            create_agent=create_agent,
            join_call=join_call,
        )
    )
    allow_origins_raw = os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    allow_origins = [origin.strip() for origin in allow_origins_raw.split(",") if origin.strip()]
    runner.fast_api.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    runner.fast_api.include_router(video_router)
    runner.fast_api.include_router(audio_router)
<<<<<<< Updated upstream
    runner.fast_api.include_router(faces_router)
    runner.fast_api.include_router(auth_router)
=======
    runner.fast_api.include_router(reports_router)
>>>>>>> Stashed changes
    runner.cli()
