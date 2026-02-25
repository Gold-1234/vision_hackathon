# RANK: 3 - Main orchestrator to initialize GetStream, the AI Agent, and route frames via VideoForwarder.

import asyncio
import os
from dotenv import load_dotenv

# We expect these from vision_agents, adapting based on the PLAN.md
from livekit.plugins import getstream, gemini
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli, llm
from livekit.agents.pipeline import VoicePipelineAgent

# Import our custom components once they are ready
# from processors import ObjectDetectionProcessor, FallDetectionProcessor, ...
# from tools.camera import LocalCameraStream

load_dotenv()

async def entrypoint(ctx: JobContext):
    """
    Main entrypoint for the Vision Agent. 
    Connects to the room, sets up the LLM, and attaches our video processors.
    """
    await ctx.connect(auto_subscribe=AutoSubscribe.VIDEO_ONLY)
    print("Agent connected to the room!")

    # In a full implementation, we'd add the VideoProcessors here.
    # Currently setting up the basic agent structure.
    
    agent = VoicePipelineAgent(
        vad=None, # Video only for now, or add VAD later
        stt=None,
        llm=gemini.LLM(model="gemini-2.5-flash-lite"),
        tts=None,
        instructions="You are a child safety monitoring AI. Alert on dangers. Analyze the provided events.",
    )
    
    agent.start(ctx.room)
    await asyncio.sleep(1)
    print("Safety Monitor is active and listening.")

if __name__ == "__main__":
    # We use livekit cli to start the worker process
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))