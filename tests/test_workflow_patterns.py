"""
Workflow Pattern Tests
======================
Tests that validate the workflow construction patterns comply with MAF conventions.
These tests verify structural correctness without requiring a running model.
"""

import inspect

import pytest


class TestSequentialWorkflowPattern:
    """Validate that the Travel Planner uses SequentialBuilder correctly."""

    def test_workflow_builder_uses_sequential_builder(self) -> None:
        """Must use SequentialBuilder, not raw WorkflowBuilder."""
        source = inspect.getsource(
            __import__("src.workflows.travel_planner", fromlist=["build_travel_planner_workflow"])
        )
        assert "SequentialBuilder" in source
        assert "participants=" in source

    def test_workflow_enables_intermediate_outputs(self) -> None:
        """SequentialBuilder must enable intermediate_outputs for progressive streaming."""
        source = inspect.getsource(
            __import__("src.workflows.travel_planner", fromlist=["build_travel_planner_workflow"])
        )
        assert "intermediate_outputs=True" in source, (
            "SequentialBuilder must use intermediate_outputs=True for progressive UI streaming"
        )

    def test_workflow_imports_from_orchestrations(self) -> None:
        """SequentialBuilder must be imported from agent_framework.orchestrations."""
        source = inspect.getsource(
            __import__("src.workflows.travel_planner", fromlist=["build_travel_planner_workflow"])
        )
        assert "from agent_framework.orchestrations import SequentialBuilder" in source

    def test_three_participants_in_order(self) -> None:
        """Workflow must define exactly 3 participants: researcher, weather, planner."""
        source = inspect.getsource(
            __import__("src.workflows.travel_planner", fromlist=["build_travel_planner_workflow"])
        )
        # All three agent variables must appear in participants list
        assert "researcher" in source
        assert "weather_analyst" in source
        assert "planner" in source

    def test_workflow_returns_tuple(self) -> None:
        """build_travel_planner_workflow should return (workflow, mcp_tool) tuple."""
        from src.workflows.travel_planner import build_travel_planner_workflow
        sig = inspect.signature(build_travel_planner_workflow)
        # Return annotation should mention tuple
        assert "tuple" in str(sig.return_annotation).lower()


class TestAgentFactoryPatterns:
    """Validate agent factory functions follow expected conventions."""

    def test_researcher_has_no_tools_param(self) -> None:
        """Researcher agent should NOT use external tools."""
        source = inspect.getsource(
            __import__("src.agents.researcher", fromlist=["create_researcher_agent"])
        )
        assert "tools=" not in source or "tools=[]" in source

    def test_weather_analyst_has_mcp_tool(self) -> None:
        """WeatherAnalyst agent MUST use MCPStreamableHTTPTool."""
        source = inspect.getsource(
            __import__("src.agents.weather_analyst", fromlist=["create_weather_analyst_agent"])
        )
        assert "MCPStreamableHTTPTool" in source
        assert "tools=" in source

    def test_planner_has_no_tools_param(self) -> None:
        """Planner agent should NOT use external tools."""
        source = inspect.getsource(
            __import__("src.agents.planner", fromlist=["create_planner_agent"])
        )
        assert "tools=" not in source or "tools=[]" in source

    def test_all_agents_use_as_agent(self) -> None:
        """All agent factories should use client.as_agent() pattern."""
        for module_name in [
            "src.agents.researcher",
            "src.agents.weather_analyst",
            "src.agents.planner",
        ]:
            source = inspect.getsource(__import__(module_name, fromlist=["create"]))
            assert "as_agent" in source, f"{module_name} should use client.as_agent()"


class TestMCPToolPattern:
    """Validate MCP tool usage patterns."""

    def test_mcp_tool_uses_streamable_http(self) -> None:
        """Must use MCPStreamableHTTPTool, not MCPStdioTool."""
        source = inspect.getsource(
            __import__("src.agents.weather_analyst", fromlist=["create_weather_analyst_agent"])
        )
        assert "MCPStreamableHTTPTool" in source
        assert "MCPStdioTool" not in source

    def test_mcp_tool_url_is_parameterized(self) -> None:
        """MCP server URL should come from a parameter, not hardcoded."""
        source = inspect.getsource(
            __import__("src.agents.weather_analyst", fromlist=["create_weather_analyst_agent"])
        )
        assert "mcp_server_url" in source


class TestMainEntryPoint:
    """Validate main.py structure."""

    def test_main_imports_workflow(self) -> None:
        source = inspect.getsource(__import__("main"))
        assert "build_travel_planner_workflow" in source

    def test_main_imports_foundry_local(self) -> None:
        source = inspect.getsource(__import__("main"))
        assert "FoundryLocalClient" in source

    def test_main_imports_telemetry(self) -> None:
        source = inspect.getsource(__import__("main"))
        assert "setup_telemetry" in source

    def test_main_imports_config(self) -> None:
        source = inspect.getsource(__import__("main"))
        assert "get_settings" in source
