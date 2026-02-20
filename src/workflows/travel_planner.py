"""
Travel Planner Workflow
=======================
Sequential orchestration: Researcher → WeatherAnalyst → Planner.

Uses MAF's SequentialBuilder for high-level workflow construction.
The shared conversation context (list[Message]) flows through each participant,
with each agent appending its response to the chain.

Architecture:
    User Query
        → Researcher (LLM-only: destination research)
        → WeatherAnalyst (MCP tools: weather, time, restaurants)
        → Planner (LLM-only: synthesize into travel plan)
        → Final Output
"""

from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.orchestrations import SequentialBuilder

from ..agents import (
    create_planner_agent,
    create_researcher_agent,
    create_weather_analyst_agent,
)


def build_travel_planner_workflow(
    client: object,
    mcp_server_url: str,
) -> tuple[object, MCPStreamableHTTPTool]:
    """Build the Travel Planner sequential workflow.

    Args:
        client: A FoundryLocalClient for creating agents.
        mcp_server_url: URL of the FastMCP server.

    Returns:
        A tuple of (Workflow, MCPStreamableHTTPTool). The MCP tool must be managed
        as a context manager to keep the connection alive during workflow execution.
    """
    # Create agents
    researcher = create_researcher_agent(client)
    weather_analyst, mcp_tool = create_weather_analyst_agent(client, mcp_server_url)
    planner = create_planner_agent(client)

    # Build sequential workflow: Researcher → WeatherAnalyst → Planner
    # intermediate_outputs=True emits output events after each agent completes,
    # enabling progressive streaming to the UI instead of a single batch at the end.
    workflow = SequentialBuilder(
        participants=[researcher, weather_analyst, planner],
        intermediate_outputs=True,
    ).build()

    return workflow, mcp_tool
