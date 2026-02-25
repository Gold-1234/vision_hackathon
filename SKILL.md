---
name: Agent
description: Documentation and capabilities reference for Agent
metadata:
    mintlify-proj: agent
    version: "1.0"
---

## Capabilities

Vision Agents enables building intelligent, real-time voice and video AI applications with minimal latency. Agents can conduct natural conversations, process video with computer vision, understand visual content, execute functions, access knowledge bases, and integrate with phone networks. The framework is provider-agnostic, supporting 25+ AI integrations (OpenAI, Gemini, Deepgram, ElevenLabs, NVIDIA, and more) that can be swapped with a single line of code.

## Skills

### Voice Agent Development
- Build voice agents using realtime models (OpenAI Realtime, Gemini Live) for native speech-to-speech with sub-50ms latency
- Create custom voice pipelines combining separate STT, LLM, and TTS providers
- Configure turn detection for natural conversation flow with automatic interruption handling
- Register Python functions for the agent to call during conversations
- Support for phone integration via Twilio for inbound and outbound calls

### Video Agent Development
- Stream video directly to realtime vision models (OpenAI, Gemini, Qwen) with configurable FPS
- Use Vision Language Models (VLMs) for video understanding and analysis with frame buffering
- Build custom video processors for computer vision tasks (object detection, pose estimation, segmentation)
- Chain multiple processors for complex analysis pipelines
- Publish transformed video back to calls with custom processing

### LLM Integration
- Support for 15+ LLM providers: OpenAI, Gemini, Anthropic, xAI, OpenRouter, HuggingFace, Mistral, and more
- Function calling with automatic tool execution and multi-round tool calling
- Chat completions API support for open-source models (Qwen, Deepseek, Mistral)
- VLM support for visual reasoning (NVIDIA Cosmos, HuggingFace, Moondream)
- Streaming responses and token counting

### Speech Services
- STT providers: Deepgram, Fast-Whisper, Fish, Wizper
- TTS providers: ElevenLabs, Cartesia, Deepgram, Pocket, AWS Polly
- Turn detection: Deepgram (built-in), Smart Turn, Vogent
- Voice activity detection (VAD) for conversation management

### Function Calling & External Tools
- Register Python functions with `@llm.register_function()` decorator
- Connect to MCP (Model Context Protocol) servers for external tool access
- Support for local MCP servers (stdio) and remote servers (HTTP)
- Automatic tool discovery and registration with LLMs
- Tool execution events for monitoring and logging

### Retrieval-Augmented Generation (RAG)
- Gemini File Search for automatic document chunking and embedding
- TurboPuffer integration for hybrid search (vector + BM25)
- Content deduplication via SHA-256 hashing
- Concurrent batch uploads for knowledge base population
- Register search functions for agent access to knowledge bases

### Event System
- Subscribe to 20+ event types: participant joins/leaves, transcriptions, LLM responses, turn detection, tool execution
- Component-specific events from STT, TTS, LLM, turn detection, and processors
- Error events with recovery information
- Custom event emission from video processors
- Event filtering and multi-event handlers

### Video Processing
- YOLO pose detection for fitness, sports, and physical therapy applications
- HeyGen avatar integration for lip-synced AI presenters
- Custom processor development by extending `VideoProcessor` base class
- Frame handler registration at independent FPS rates
- Video track publishing with `QueuedVideoTrack`

### Conversation Management
- Persistent conversations via Stream Chat (default)
- In-memory conversations for development and testing
- Custom conversation storage by implementing `Conversation` interface
- Message history with role, timestamp, and user tracking
- Context maintenance across sessions

### Server & Deployment
- HTTP server mode for production deployments with session management
- Console mode for development and testing
- API endpoints for session creation, monitoring, and metrics
- Health checks (`/health`, `/ready`) for Kubernetes probes
- CORS configuration and authentication/permission callbacks
- Session limits: max concurrent sessions, per-call limits, duration limits, idle timeouts
- Docker support with CPU and GPU Dockerfiles
- Horizontal scaling with sticky sessions

### Monitoring & Telemetry
- Prometheus metrics export for production monitoring
- Per-session metrics: LLM latency, token counts, STT/TTS latency
- Real-time performance metrics via `/sessions/{id}/metrics` endpoint
- Event-based telemetry for all components
- Configurable logging levels for agents and HTTP server

### Agent Configuration
- Modular architecture with independent component configuration
- System instructions for agent behavior customization
- Optional video/audio track overrides for testing with local files
- Processor chaining for multi-stage analysis
- MCP server attachment for tool access

## Workflows

### Building a Voice Agent
1. Create agent factory function with `create_agent()` returning configured `Agent` instance
2. Choose mode: realtime (OpenAI/Gemini) or custom pipeline (STT + LLM + TTS)
3. Configure LLM with model selection and system instructions
4. Add STT and TTS providers (skip for realtime mode)
5. Register functions with `@llm.register_function()` decorator
6. Define `join_call()` to handle agent joining calls
7. Use `Runner` and `AgentLauncher` for console or server mode
8. Call `agent.simple_response()` to send text to LLM for processing
9. Subscribe to events for custom behavior (greetings, logging, etc.)

### Building a Video Agent
1. Create agent with video-capable LLM (realtime or VLM)
2. Set FPS parameter for frame sampling rate
3. Add video processors for computer vision tasks
4. Configure frame buffer size for VLMs (e.g., 10 seconds)
5. Optionally add STT/TTS for voice interaction
6. Subscribe to video processor events for custom handling
7. Use `VideoProcessorPublisher` to publish transformed video
8. Deploy with video track handling enabled

### Implementing Phone Integration
1. Set up Twilio account with phone number
2. Configure ngrok for local development webhooks
3. Create webhook endpoint at `/twilio/voice` for inbound calls
4. Validate Twilio signature with `verify_twilio_signature` dependency
5. Create call registry entry with `call_registry.create()`
6. Return TwiML with media stream URL for bidirectional audio
7. For outbound: use Twilio REST API with `create_media_stream_twiml()`
8. Attach phone audio to Stream call with `attach_phone_to_call()`

### Adding RAG to Agents
1. Choose RAG provider: Gemini File Search (simple) or TurboPuffer (advanced)
2. For Gemini: create `GeminiFilesearchRAG` store and populate with `add_directory()`
3. For TurboPuffer: initialize with chunk size/overlap and add documents
4. Register search function with `@llm.register_function()`
5. Agent calls search function when relevant to conversation
6. Results automatically included in LLM context

### Deploying to Production
1. Create Dockerfile (CPU or GPU variant)
2. Set environment variables for all API keys
3. Build for Linux: `docker buildx build --platform linux/amd64`
4. Configure health check endpoints in Kubernetes
5. Set session limits in `AgentLauncher` for resource management
6. Deploy multiple replicas behind load balancer
7. Enable Prometheus metrics export
8. Set up monitoring for latency and error rates

### Handling Interruptions
1. For realtime APIs: interruption handling is automatic (no configuration needed)
2. For custom pipelines: add turn detection plugin (Smart Turn, Vogent, or Deepgram)
3. Subscribe to `TurnStartedEvent` for custom logging/analytics
4. Adjust sensitivity with `buffer_in_seconds` and `confidence_threshold`
5. Agent automatically stops TTS and flushes audio on interruption
6. Keep responses concise to minimize interruption likelihood

## Integration

Vision Agents integrates with:

**LLM Providers**: OpenAI, Google Gemini, Anthropic Claude, xAI Grok, OpenRouter, HuggingFace, Mistral, Qwen, AWS Bedrock

**Realtime APIs**: OpenAI (WebRTC), Gemini (WebSocket), Qwen, AWS Nova

**Speech Services**: Deepgram (STT/TTS/VAD), ElevenLabs (TTS), Cartesia (TTS), AWS Polly (TTS), Fast-Whisper (STT), Fish (STT), Wizper (STT), Pocket (TTS)

**Vision Models**: NVIDIA Cosmos, HuggingFace VLMs, Moondream, Roboflow, Ultralytics YOLO

**External Tools**: MCP servers (local and remote), Twilio (phone), Stream Chat (persistence), TurboPuffer (vector search), HeyGen (avatars)

**Transport**: Stream's edge network (default, low-latency), custom transports supported

**Deployment**: Docker, Kubernetes, FastAPI, Prometheus

## Context

**Architecture**: Modular design with independent components (LLM, STT, TTS, VAD, processors) orchestrated by the `Agent` class. Event-driven system for loose coupling.

**Latency**: Optimized for sub-50ms latency with Stream's global edge network. Realtime APIs provide the lowest latency for voice interactions.

**Provider Agnostic**: "Bring Your Own Key" (BOYK) model—use your own API keys for all providers. Most offer free tiers for development.

**Two Modes**: Realtime models (native speech-to-speech, built-in interruption handling) vs. custom pipelines (full control over STT/LLM/TTS selection).

**Video Processing**: Frames are distributed to processors at independent FPS rates via shared `VideoForwarder`. Processors can analyze, transform, or publish video.

**Function Calling**: Automatic conversion of registered functions to provider-specific formats. Multi-round tool calling supported for complex tasks.

**Conversation Context**: Messages automatically stored in Stream Chat (persistent) or in-memory. Context maintained across sessions for coherent multi-turn interactions.

**Production Ready**: HTTP server with session management, health checks, metrics, CORS, authentication, and resource limits. Docker deployment with CPU/GPU variants. Horizontal scaling support.

**Type Safety**: Rich typing throughout for better IDE support and error detection.

**Extensibility**: Custom processors, conversation storage, LLM providers, and MCP servers can be implemented by extending base classes.

---

> For additional documentation and navigation, see: https://visionagents.ai/llms.txt