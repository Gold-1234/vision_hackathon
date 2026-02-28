import asyncio
import os

from dotenv import load_dotenv

from vision_agents.core import Agent, AgentLauncher, Runner, User
from vision_agents.plugins import cartesia, gemini, getstream
from processors.object_detection import ObjectDetectionProcessor
from processors.toddler_processor import ToddlerProcessor
from processors.fall_detection import FallDetectionProcessor
from processors.combined_video_publisher import CombinedVideoPublisher
from processors.crying_audio_detector import CryingAudioDetector
from processor_registry import set_crying_detector
from routes import video_router, audio_router
from video_stream_registry import set_publisher


load_dotenv()


async def create_agent(**kwargs) -> Agent:
    _ = kwargs
    object_processor = ObjectDetectionProcessor(fps=1.0, confidence_threshold=0.5)
    fall_processor = FallDetectionProcessor(fps=2.0)
    toddler_processor = ToddlerProcessor(fps=1) if os.getenv("ROBOFLOW_API_KEY") else None
    
    combined_publisher = CombinedVideoPublisher(
        object_processor=object_processor,
        toddler_processor=toddler_processor,
        fall_processor=fall_processor,
        fps=10.0,
    )
    set_publisher(combined_publisher)

    processors: list = [object_processor, fall_processor]
    if toddler_processor is not None:
        processors.append(toddler_processor)
    processors.append(combined_publisher)
  
    if(crying_detector):
        print("initialised crying detector")

    tts_engine = cartesia.TTS() if os.getenv("CARTESIA_API_KEY") else None

    agent = Agent(
        edge=getstream.Edge(),
        agent_user=User(name="Safety Monitor", id="agent"),
        instructions=(
            "You are a child safety monitoring AI. "
            "Alert on dangers and analyze incoming events concisely."
        ),
        llm=gemini.LLM(model="gemini-2.5-flash-lite"),
        tts=tts_engine,
        processors=processors
    )

    return agent


async def join_call(agent: Agent, call_type: str, call_id: str, **kwargs) -> None:
    _ = kwargs
    # Stream edge transport relies on agent user initialization before call creation.
    await agent.create_user()
    call = await agent.create_call(call_type, call_id)
    async with agent.join(call):
        await agent.simple_response("Safety monitoring active.")
        fall_processor = getattr(agent, "_fall_processor", None)
        fall_announced = False
        try:
            while True:
                await asyncio.sleep(0.25)
                if fall_processor is None:
                    continue
                fall_now = bool(fall_processor.state().get("fall_detected", False))
                if fall_now and not fall_announced:
                    await agent.simple_response("Fall detected")
                    fall_announced = True
                elif not fall_now and fall_announced:
                    fall_announced = False
        finally:
            await agent.finish()


if __name__ == "__main__":
    runner = Runner(
        AgentLauncher(
            create_agent=create_agent,
            join_call=join_call,
        )
    )
    runner.fast_api.include_router(video_router)
    runner.fast_api.include_router(audio_router)
    runner.cli()
