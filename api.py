"""
Travel Planner API Server
=========================
FastAPI wrapper that exposes the MAF Travel Planner workflow as a REST + SSE API.

Endpoints:
    - POST /api/plan  → SSE stream of workflow events (agents running, messages, output)
    - GET  /api/health → Healthcheck

The FoundryLocalClient is initialized once at startup (GPU bootstrap is expensive).
The MCPStreamableHTTPTool is opened per-request to keep the connection lifecycle clean.

Usage:
    python api.py
    uvicorn api:app --host 0.0.0.0 --port 8000
"""

import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, cast

from dotenv import load_dotenv

# Load .env BEFORE any MAF/OTel imports read environment variables
load_dotenv()

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agent_framework import AgentExecutorResponse, Message
from agent_framework_foundry_local import FoundryLocalClient

from src.config import get_settings
from src.telemetry import setup_telemetry, shutdown_telemetry, trace_workflow
from src.workflows.travel_planner import build_travel_planner_workflow

# ──────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("travel_planner.api")


# ──────────────────────────────────────────────────────────────
# Request/Response Models
# ──────────────────────────────────────────────────────────────

class PlanRequest(BaseModel):
    """Request body for the /api/plan endpoint."""
    query: str


# ──────────────────────────────────────────────────────────────
# Application State
# ──────────────────────────────────────────────────────────────

# Holds the shared FoundryLocalClient and settings across requests.
# Initialized during lifespan startup.
_app_state: dict = {}


# ──────────────────────────────────────────────────────────────
# Lifespan
# ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: initialize GPU client and telemetry at startup,
    clean up on shutdown."""
    settings = get_settings()

    # ── Startup ─────────────────────────────────────────────
    logger.info("Setting up telemetry (OTLP → %s)", settings.otel_endpoint)
    setup_telemetry(service_name=settings.otel_service_name)

    logger.info("Initializing FoundryLocal client with model: %s", settings.foundry_model_id)
    client = FoundryLocalClient(
        model_id=settings.foundry_model_id,
        bootstrap=True,
        prepare_model=True,
    )
    logger.info("FoundryLocal ready — endpoint: %s", client.manager.endpoint)

    _app_state["client"] = client
    _app_state["settings"] = settings

    logger.info("API server ready — FoundryLocal + Telemetry initialized")

    yield

    # ── Shutdown ────────────────────────────────────────────
    logger.info("Shutting down telemetry...")
    shutdown_telemetry()
    _app_state.clear()


# ──────────────────────────────────────────────────────────────
# FastAPI App
# ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Travel Planner API",
    description="Multi-agent travel planner powered by MAF + FoundryLocal",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: allow the web-ui container and local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Auto-instrument FastAPI with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)


# ──────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health() -> dict:
    """Healthcheck endpoint."""
    return {
        "status": "healthy",
        "service": "travel-planner-api",
        "model": _app_state.get("settings", {}).foundry_model_id
        if _app_state.get("settings")
        else "not initialized",
    }


@app.post("/api/plan")
async def plan_trip(request: PlanRequest) -> EventSourceResponse:
    """Execute the Travel Planner workflow and stream events via SSE.

    The SSE stream emits the following event types:
        - agent_started:  An agent has begun processing
        - agent_completed: An agent has finished processing
        - message:        An agent's response message
        - output:         Final workflow output (complete itinerary)
        - error:          Error during workflow execution
        - done:           Stream complete signal
    """
    if not request.query.strip():
        raise HTTPException(status_code=422, detail="Query must not be empty")

    client = _app_state.get("client")
    settings = _app_state.get("settings")

    if not client or not settings:
        raise HTTPException(status_code=503, detail="Service not ready — client not initialized")

    async def event_generator() -> AsyncGenerator[dict, None]:
        """Generate SSE events from the workflow execution."""
        try:
            # Build workflow per-request (agents are lightweight, MCP tool needs fresh connection)
            workflow, mcp_tool = build_travel_planner_workflow(
                client=client,
                mcp_server_url=settings.mcp_server_url,
            )

            yield {
                "event": "status",
                "data": json.dumps({"message": "Workflow built — starting execution"}),
            }

            # Track messages already sent to avoid duplicates
            # (intermediate_outputs=True emits cumulative output after each agent)
            sent_message_count = 0

            with trace_workflow("travel_planner", request.query):
                async with mcp_tool:
                    tool_names = [f.name for f in mcp_tool.functions]
                    logger.info("MCP tools available: %s", ", ".join(tool_names))

                    yield {
                        "event": "status",
                        "data": json.dumps({
                            "message": "MCP connected",
                            "tools": tool_names,
                        }),
                    }

                    # Stream workflow events
                    start_time = time.perf_counter()
                    current_agent = None
                    async for event in workflow.run(request.query, stream=True):
                        if event.type == "status":
                            yield {
                                "event": "status",
                                "data": json.dumps({"state": str(event.state)}),
                            }
                        elif event.type == "executor_invoked":
                            exec_name = getattr(event, "executor_id", "unknown")
                            logger.info("Agent started: %s", exec_name)
                            current_agent = exec_name
                            yield {
                                "event": "agent_started",
                                "data": json.dumps({"agent": exec_name}),
                            }
                        elif event.type == "executor_completed":
                            exec_name = getattr(event, "executor_id", "unknown")
                            logger.info("Agent completed: %s", exec_name)
                            yield {
                                "event": "agent_completed",
                                "data": json.dumps({"agent": exec_name}),
                            }
                        elif event.type == "output":
                            # With intermediate_outputs=True, intermediate events carry
                            # AgentExecutorResponse (with .full_conversation), while the
                            # final event carries list[Message]. Extract new messages only.
                            output_data = event.data
                            if output_data:
                                messages: list[Message]
                                if isinstance(output_data, AgentExecutorResponse):
                                    messages = output_data.full_conversation or []
                                elif isinstance(output_data, list):
                                    messages = cast(list[Message], output_data)
                                else:
                                    logger.warning("Unexpected output type: %s", type(output_data).__name__)
                                    continue

                                new_messages = [
                                    m for m in messages[sent_message_count:]
                                    if m.role.upper() == "ASSISTANT"
                                ]
                                for msg in new_messages:
                                    yield {
                                        "event": "message",
                                        "data": json.dumps({
                                            "role": msg.role,
                                            "author": msg.author_name or "Assistant",
                                            "text": msg.text,
                                        }),
                                    }
                                sent_message_count = len(messages)

                    # Send final output summary after stream ends
                    duration = round(time.perf_counter() - start_time, 2)
                    yield {
                        "event": "output",
                        "data": json.dumps({
                            "message": "Workflow complete",
                            "duration_seconds": duration,
                            "agent_count": sent_message_count,
                        }),
                    }

            # Signal stream end
            yield {
                "event": "done",
                "data": json.dumps({"message": "Stream complete"}),
            }

        except Exception as e:
            logger.exception("Error during workflow execution")
            yield {
                "event": "error",
                "data": json.dumps({
                    "error": str(e),
                    "type": type(e).__name__,
                }),
            }

    return EventSourceResponse(event_generator())


# ──────────────────────────────────────────────────────────────
# Entry Point
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    settings = get_settings()

    print("\n" + "=" * 70)
    print(" Travel Planner API — FastAPI + MAF + FoundryLocal")
    print("=" * 70)
    print(f"\n  API:       http://{settings.api_host}:{settings.api_port}")
    print(f"  Health:    http://{settings.api_host}:{settings.api_port}/api/health")
    print(f"  Model:     {settings.foundry_model_id}")
    print(f"  MCP:       {settings.mcp_server_url}")
    print(f"  Telemetry: {settings.otel_endpoint}")
    print(f"  Aspire UI: http://localhost:18888")
    print("=" * 70 + "\n")

    uvicorn.run(
        "api:app",
        host=settings.api_host,
        port=settings.api_port,
        log_level="info",
    )
