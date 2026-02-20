"""
Travel Planner - Multi-Agent Orchestration
==========================================
Entry point for the Travel Planner PoC using Microsoft Agent Framework (MAF)
with FoundryLocal as the local SLM runtime.

Architecture:
    - In-process orchestration via MAF SequentialBuilder
    - 3 agents: Researcher → WeatherAnalyst → Planner
    - MCP server provides travel tools (weather, time, restaurants)
    - OpenTelemetry traces exported to Jaeger

Usage:
    python main.py
    python main.py "Plan a 3-day trip to Tokyo"
"""

import asyncio
import logging
import sys
from typing import cast

from dotenv import load_dotenv

# Load .env BEFORE any MAF/OTel imports read environment variables
load_dotenv()

from agent_framework import Message
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
logger = logging.getLogger("travel_planner")


# ──────────────────────────────────────────────────────────────
# Default Query
# ──────────────────────────────────────────────────────────────

DEFAULT_QUERY = "Plan a 3-day trip to Tokyo, Japan. I like sushi and temples."


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

async def run_travel_planner(query: str) -> None:
    """Execute the Travel Planner workflow.

    Args:
        query: The user's travel planning request.
    """
    settings = get_settings()

    # ── 1. Setup Telemetry ──────────────────────────────────
    logger.info("Setting up telemetry (OTLP → %s)", settings.otel_endpoint)
    setup_telemetry(service_name=settings.otel_service_name)

    # ── 2. Initialize FoundryLocal Client ───────────────────
    logger.info("Initializing FoundryLocal client with model: %s", settings.foundry_model_id)
    print("\n" + "=" * 70)
    print(" Travel Planner - Multi-Agent Orchestration (MAF + FoundryLocal)")
    print("=" * 70)
    print(f"\n  Model: {settings.foundry_model_id}")
    print(f"  MCP Server: {settings.mcp_server_url}")
    print(f"  Telemetry: {settings.otel_endpoint}")
    print()

    client = FoundryLocalClient(
        model_id=settings.foundry_model_id,
        bootstrap=True,
        prepare_model=True,
    )
    logger.info("FoundryLocal ready — endpoint: %s", client.manager.endpoint)

    # ── 3. Build Workflow ───────────────────────────────────
    logger.info("Building Travel Planner workflow...")
    workflow, mcp_tool = build_travel_planner_workflow(
        client=client,
        mcp_server_url=settings.mcp_server_url,
    )
    logger.info("Workflow built: Researcher → WeatherAnalyst → Planner")

    # ── 4. Execute Workflow ─────────────────────────────────
    print(f"  Query: {query}")
    print("\n" + "-" * 70)

    with trace_workflow("travel_planner", query):
        # Connect MCP tool and run workflow
        async with mcp_tool:
            logger.info("MCP tool connected to %s", settings.mcp_server_url)
            tool_names = [f.name for f in mcp_tool.functions]
            logger.info("MCP tools available: %s", ", ".join(tool_names))

            print("\n  Running workflow (Researcher → WeatherAnalyst → Planner)...")
            print("  This may take a minute with a local SLM...\n")

            # Stream workflow events
            output_data = None
            async for event in workflow.run(query, stream=True):
                if event.type == "status":
                    logger.debug("Workflow status: %s", event.state)
                elif event.type == "executor_invoked":
                    exec_name = getattr(event, "executor_id", "unknown")
                    logger.info("  → Executor invoked: %s", exec_name)
                elif event.type == "executor_completed":
                    exec_name = getattr(event, "executor_id", "unknown")
                    logger.info("  ✓ Executor completed: %s", exec_name)
                elif event.type == "output":
                    output_data = event.data

    # ── 5. Display Results ──────────────────────────────────
    print("-" * 70)
    if output_data:
        messages = cast(list[Message], output_data)
        print("\n  === WORKFLOW RESULTS ===\n")
        for msg in messages:
            role = msg.role.upper()
            author = msg.author_name or role
            if role == "ASSISTANT":
                print(f"\n  ── {author} ──")
                print(f"  {msg.text}")
            elif role == "USER":
                print(f"\n  [User]: {msg.text}")
        print()
    else:
        print("\n  ⚠ No output received from the workflow.\n")

    print("=" * 70)
    print("  ✓ Workflow complete! Check Jaeger UI at http://localhost:16686")
    print("=" * 70)

    # ── 6. Flush telemetry ───────────────────────────────────
    shutdown_telemetry()


def main() -> None:
    """Entry point — parse CLI args and run the workflow."""
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else DEFAULT_QUERY

    try:
        asyncio.run(run_travel_planner(query))
    except ConnectionError as e:
        logger.error("Connection Error: %s", e)
        print("\n  ✘ Could not connect to FoundryLocal. Is the service running?")
        print("    Start it with: foundry service start")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n  Interrupted by user.")
        sys.exit(0)
    except Exception as e:
        logger.exception("Unexpected error")
        print(f"\n  ✘ Error: {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
