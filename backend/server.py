import asyncio
import os

from dotenv import load_dotenv

from vision_agents.core import Agent, AgentLauncher, Runner, User
from vision_agents.plugins import gemini, getstream
from processors.object_detection import ObjectDetectionProcessor
from processors.toddler_processor import ToddlerProcessor
from processors.combined_video_publisher import CombinedVideoPublisher

load_dotenv()


async def create_agent(**kwargs) -> Agent:
    _ = kwargs
    object_processor = ObjectDetectionProcessor(fps=1.0, confidence_threshold=0.5)
    toddler_processor = ToddlerProcessor(fps=1) if os.getenv("ROBOFLOW_API_KEY") else None
    combined_publisher = CombinedVideoPublisher(
        object_processor=object_processor,
        toddler_processor=toddler_processor,
        fps=10.0,
    )

    processors: list = [object_processor]
    if toddler_processor is not None:
        processors.append(toddler_processor)
    processors.append(combined_publisher)


    return Agent(
        edge=getstream.Edge(),
        agent_user=User(name="Safety Monitor", id="agent"),
        instructions=(
            "You are a child safety monitoring AI. "
            "Alert on dangers and analyze incoming events concisely."
        ),
        llm=gemini.LLM(model="gemini-2.5-flash-lite"),
        processors=processors
    )


async def join_call(agent: Agent, call_type: str, call_id: str, **kwargs) -> None:
    _ = kwargs
    call = await agent.create_call(call_type, call_id)
    async with agent.join(call):
        await agent.simple_response("Safety monitoring active.")
        try:
            await asyncio.Event().wait()
        finally:
            await agent.finish()


if __name__ == "__main__":
    Runner(
        AgentLauncher(
            create_agent=create_agent,
            join_call=join_call,
        )
    ).cli()
