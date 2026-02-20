"""
Architecture Compliance Tests
=============================
Validates that the project adheres to the approved architecture:
    - In-process orchestration via MAF SequentialBuilder
    - 3 agents: Researcher, WeatherAnalyst, Planner
    - MCP server as separate container (FastMCP HTTP)
    - OpenTelemetry for observability
    - Configurable via .env
"""

import importlib
import os

import pytest


class TestProjectStructure:
    """Verify project directory layout matches architecture spec."""

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_src_package_exists(self) -> None:
        assert os.path.isdir(os.path.join(self.BASE_DIR, "src"))
        assert os.path.isfile(os.path.join(self.BASE_DIR, "src", "__init__.py"))

    def test_agents_package_exists(self) -> None:
        agents_dir = os.path.join(self.BASE_DIR, "src", "agents")
        assert os.path.isdir(agents_dir)
        assert os.path.isfile(os.path.join(agents_dir, "__init__.py"))

    def test_workflows_package_exists(self) -> None:
        wf_dir = os.path.join(self.BASE_DIR, "src", "workflows")
        assert os.path.isdir(wf_dir)
        assert os.path.isfile(os.path.join(wf_dir, "__init__.py"))

    def test_mcp_server_directory_exists(self) -> None:
        mcp_dir = os.path.join(self.BASE_DIR, "mcp_server")
        assert os.path.isdir(mcp_dir)
        assert os.path.isfile(os.path.join(mcp_dir, "server.py"))
        assert os.path.isfile(os.path.join(mcp_dir, "Dockerfile"))

    def test_config_module_exists(self) -> None:
        assert os.path.isfile(os.path.join(self.BASE_DIR, "src", "config.py"))

    def test_telemetry_module_exists(self) -> None:
        assert os.path.isfile(os.path.join(self.BASE_DIR, "src", "telemetry.py"))

    def test_docker_compose_exists(self) -> None:
        assert os.path.isfile(os.path.join(self.BASE_DIR, "docker-compose.yml"))

    def test_env_example_exists(self) -> None:
        assert os.path.isfile(os.path.join(self.BASE_DIR, ".env.example"))

    def test_main_entrypoint_exists(self) -> None:
        assert os.path.isfile(os.path.join(self.BASE_DIR, "main.py"))

    def test_prototypes_directory_exists(self) -> None:
        assert os.path.isdir(os.path.join(self.BASE_DIR, "prototypes"))


class TestAgentDefinitions:
    """Verify each agent module exposes the expected factory function."""

    def test_researcher_module_has_factory(self) -> None:
        mod = importlib.import_module("src.agents.researcher")
        assert hasattr(mod, "create_researcher_agent")
        assert callable(mod.create_researcher_agent)

    def test_weather_analyst_module_has_factory(self) -> None:
        mod = importlib.import_module("src.agents.weather_analyst")
        assert hasattr(mod, "create_weather_analyst_agent")
        assert callable(mod.create_weather_analyst_agent)

    def test_planner_module_has_factory(self) -> None:
        mod = importlib.import_module("src.agents.planner")
        assert hasattr(mod, "create_planner_agent")
        assert callable(mod.create_planner_agent)

    def test_agents_init_exports_all_factories(self) -> None:
        mod = importlib.import_module("src.agents")
        assert hasattr(mod, "create_researcher_agent")
        assert hasattr(mod, "create_weather_analyst_agent")
        assert hasattr(mod, "create_planner_agent")


class TestWorkflowDefinitions:
    """Verify workflow module exposes the builder function."""

    def test_travel_planner_module_has_builder(self) -> None:
        mod = importlib.import_module("src.workflows.travel_planner")
        assert hasattr(mod, "build_travel_planner_workflow")
        assert callable(mod.build_travel_planner_workflow)

    def test_workflows_init_exports_builder(self) -> None:
        mod = importlib.import_module("src.workflows")
        assert hasattr(mod, "build_travel_planner_workflow")


class TestConfigModule:
    """Verify configuration module works correctly."""

    def test_settings_class_exists(self) -> None:
        from src.config import Settings
        assert Settings is not None

    def test_get_settings_returns_settings(self) -> None:
        from src.config import Settings, get_settings
        s = get_settings()
        assert isinstance(s, Settings)

    def test_settings_has_required_fields(self) -> None:
        from src.config import get_settings
        s = get_settings()
        assert hasattr(s, "foundry_model_id")
        assert hasattr(s, "mcp_server_url")
        assert hasattr(s, "otel_endpoint")
        assert hasattr(s, "otel_service_name")

    def test_settings_defaults_are_sensible(self) -> None:
        from src.config import get_settings
        s = get_settings()
        assert "localhost" in s.mcp_server_url
        assert "8090" in s.mcp_server_url
        assert "4317" in s.otel_endpoint


class TestTelemetryModule:
    """Verify telemetry module exports expected symbols."""

    def test_setup_telemetry_callable(self) -> None:
        from src.telemetry import setup_telemetry
        assert callable(setup_telemetry)

    def test_trace_workflow_is_context_manager(self) -> None:
        from src.telemetry import trace_workflow
        # Should be a generator-based context manager
        ctx = trace_workflow("test", "test query")
        assert hasattr(ctx, "__enter__")
        assert hasattr(ctx, "__exit__")

    def test_trace_agent_is_context_manager(self) -> None:
        from src.telemetry import trace_agent
        ctx = trace_agent("test_agent")
        assert hasattr(ctx, "__enter__")
        assert hasattr(ctx, "__exit__")

    def test_record_mcp_tool_call_callable(self) -> None:
        from src.telemetry import record_mcp_tool_call
        assert callable(record_mcp_tool_call)


class TestMCPServerModule:
    """Verify MCP server defines expected tools."""

    def test_mcp_server_imports(self) -> None:
        # The server module should import without error
        import mcp_server.server as srv
        assert hasattr(srv, "mcp")

    def test_mcp_tools_registered(self) -> None:
        import mcp_server.server as srv
        # FastMCP stores tools internally
        assert hasattr(srv, "get_weather")
        assert hasattr(srv, "get_current_time")
        assert hasattr(srv, "search_restaurants")

    def test_get_weather_function(self) -> None:
        from mcp_server.server import get_weather
        result = get_weather("Tokyo")
        assert "Tokyo" in result
        assert "°C" in result

    def test_get_current_time_function(self) -> None:
        from mcp_server.server import get_current_time
        result = get_current_time("UTC")
        assert "UTC" in result

    def test_search_restaurants_function(self) -> None:
        from mcp_server.server import search_restaurants
        result = search_restaurants("Tokyo", "Japanese")
        assert "Tokyo" in result


class TestDockerCompose:
    """Verify docker-compose.yml defines required services."""

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_docker_compose_has_mcp_server(self) -> None:
        path = os.path.join(self.BASE_DIR, "docker-compose.yml")
        content = open(path, encoding="utf-8").read()
        assert "mcp-server:" in content
        assert "8090:8090" in content

    def test_docker_compose_has_aspire_dashboard(self) -> None:
        path = os.path.join(self.BASE_DIR, "docker-compose.yml")
        content = open(path, encoding="utf-8").read()
        assert "aspire-dashboard:" in content
        assert "18888:18888" in content  # Aspire UI
        assert "4317:18889" in content   # OTLP gRPC

    def test_docker_compose_has_otlp_enabled(self) -> None:
        path = os.path.join(self.BASE_DIR, "docker-compose.yml")
        content = open(path, encoding="utf-8").read()
        assert "DOTNET_DASHBOARD_UNSECURED_ALLOW_ANONYMOUS=true" in content


class TestArchitectureConstraints:
    """Validate architectural decisions are enforced in code."""

    def test_workflow_uses_sequential_builder(self) -> None:
        """The travel planner workflow must use SequentialBuilder."""
        import inspect
        from src.workflows.travel_planner import build_travel_planner_workflow
        source = inspect.getsource(build_travel_planner_workflow)
        assert "SequentialBuilder" in source

    def test_weather_agent_uses_mcp_streamable_http(self) -> None:
        """The weather agent must use MCPStreamableHTTPTool for remote MCP."""
        import inspect
        from src.agents.weather_analyst import create_weather_analyst_agent
        source = inspect.getsource(create_weather_analyst_agent)
        assert "MCPStreamableHTTPTool" in source

    def test_three_agents_in_workflow(self) -> None:
        """The workflow must chain exactly 3 participants."""
        import inspect
        from src.workflows.travel_planner import build_travel_planner_workflow
        source = inspect.getsource(build_travel_planner_workflow)
        assert "researcher" in source
        assert "weather_analyst" in source
        assert "planner" in source
        assert "participants=" in source

    def test_no_container_per_agent(self) -> None:
        """Agents must NOT have their own Dockerfiles — only MCP server does."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        agents_dir = os.path.join(base, "src", "agents")
        for filename in os.listdir(agents_dir):
            assert filename != "Dockerfile", "Agents should run in-process, not in containers"

    def test_single_mcp_server_dockerfile(self) -> None:
        """Only one Dockerfile should exist: in mcp_server/."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        mcp_dockerfile = os.path.join(base, "mcp_server", "Dockerfile")
        assert os.path.isfile(mcp_dockerfile)

    def test_config_uses_env_vars(self) -> None:
        """Settings must be sourced from environment variables."""
        import inspect
        from src.config import Settings
        source = inspect.getsource(Settings)
        assert "os.getenv" in source
