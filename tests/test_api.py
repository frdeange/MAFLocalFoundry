"""
API Tests
=========
Structural and compliance tests for the FastAPI wrapper (api.py).
Validates imports, endpoints, middleware, telemetry instrumentation,
and request/response models — without requiring a GPU or live FoundryLocal.
"""

import ast
import os

import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _read_api() -> str:
    """Read api.py source code."""
    path = os.path.join(BASE_DIR, "api.py")
    with open(path, encoding="utf-8") as f:
        return f.read()


def _read_requirements() -> str:
    """Read requirements.txt."""
    path = os.path.join(BASE_DIR, "requirements.txt")
    with open(path, encoding="utf-8") as f:
        return f.read()


def _parse_api_ast() -> ast.Module:
    """Parse api.py into an AST tree."""
    return ast.parse(_read_api(), filename="api.py")


# ──────────────────────────────────────────────────────────────
# File Existence
# ──────────────────────────────────────────────────────────────

class TestApiFileExists:
    """Verify api.py exists in the project root."""

    def test_api_file_exists(self) -> None:
        path = os.path.join(BASE_DIR, "api.py")
        assert os.path.isfile(path), "api.py must exist in the project root"


# ──────────────────────────────────────────────────────────────
# Import Verification
# ──────────────────────────────────────────────────────────────

class TestApiImports:
    """Verify that api.py imports the required frameworks and modules."""

    def test_imports_fastapi(self) -> None:
        source = _read_api()
        assert "from fastapi import" in source or "import fastapi" in source

    def test_imports_cors_middleware(self) -> None:
        source = _read_api()
        assert "CORSMiddleware" in source

    def test_imports_sse(self) -> None:
        source = _read_api()
        assert "EventSourceResponse" in source

    def test_imports_opentelemetry_fastapi(self) -> None:
        source = _read_api()
        assert "FastAPIInstrumentor" in source

    def test_imports_pydantic_basemodel(self) -> None:
        source = _read_api()
        assert "BaseModel" in source

    def test_imports_uvicorn(self) -> None:
        source = _read_api()
        assert "import uvicorn" in source

    def test_imports_dotenv_before_maf(self) -> None:
        """load_dotenv() must be called before MAF/OTel imports."""
        source = _read_api()
        dotenv_pos = source.find("load_dotenv()")
        maf_pos = source.find("from agent_framework")
        assert dotenv_pos != -1, "load_dotenv() must be called in api.py"
        assert maf_pos != -1, "MAF imports must exist in api.py"
        assert dotenv_pos < maf_pos, "load_dotenv() must appear BEFORE MAF imports"

    def test_imports_foundry_local_client(self) -> None:
        source = _read_api()
        assert "FoundryLocalClient" in source

    def test_imports_project_modules(self) -> None:
        """Verify api.py imports from src.config, src.telemetry, src.workflows."""
        source = _read_api()
        assert "from src.config import" in source
        assert "from src.telemetry import" in source
        assert "from src.workflows.travel_planner import" in source


# ──────────────────────────────────────────────────────────────
# Endpoint Definitions
# ──────────────────────────────────────────────────────────────

class TestApiEndpoints:
    """Verify that api.py defines the expected REST endpoints."""

    def test_health_endpoint_defined(self) -> None:
        source = _read_api()
        assert '@app.get("/api/health")' in source

    def test_plan_endpoint_defined(self) -> None:
        source = _read_api()
        assert '@app.post("/api/plan")' in source

    def test_health_endpoint_function_exists(self) -> None:
        source = _read_api()
        assert "async def health" in source

    def test_plan_endpoint_function_exists(self) -> None:
        source = _read_api()
        assert "async def plan_trip" in source


# ──────────────────────────────────────────────────────────────
# Request/Response Models
# ──────────────────────────────────────────────────────────────

class TestApiModels:
    """Verify request/response model definitions in api.py."""

    def test_plan_request_model_defined(self) -> None:
        source = _read_api()
        assert "class PlanRequest" in source

    def test_plan_request_has_query_field(self) -> None:
        source = _read_api()
        assert "query: str" in source


# ──────────────────────────────────────────────────────────────
# CORS Configuration
# ──────────────────────────────────────────────────────────────

class TestApiCORS:
    """Verify CORS middleware is properly configured."""

    def test_cors_middleware_added(self) -> None:
        source = _read_api()
        assert "app.add_middleware" in source
        assert "CORSMiddleware" in source

    def test_cors_allows_web_ui_origin(self) -> None:
        """CORS must allow the web-ui container at :8080."""
        source = _read_api()
        assert "localhost:8080" in source


# ──────────────────────────────────────────────────────────────
# SSE Event Types
# ──────────────────────────────────────────────────────────────

class TestApiSSEEvents:
    """Verify the SSE stream emits expected event types."""

    @pytest.mark.parametrize("event_type", [
        "agent_started",
        "agent_completed",
        "message",
        "output",
        "error",
        "done",
        "status",
    ])
    def test_sse_event_type_emitted(self, event_type: str) -> None:
        source = _read_api()
        assert f'"event": "{event_type}"' in source, (
            f"SSE event type '{event_type}' must be emitted in api.py"
        )


# ──────────────────────────────────────────────────────────────
# Telemetry Integration
# ──────────────────────────────────────────────────────────────

class TestApiTelemetry:
    """Verify OpenTelemetry integration in api.py."""

    def test_fastapi_instrumentor_called(self) -> None:
        source = _read_api()
        assert "FastAPIInstrumentor.instrument_app(app)" in source

    def test_setup_telemetry_in_lifespan(self) -> None:
        source = _read_api()
        assert "setup_telemetry" in source

    def test_shutdown_telemetry_in_lifespan(self) -> None:
        source = _read_api()
        assert "shutdown_telemetry" in source

    def test_trace_workflow_used(self) -> None:
        source = _read_api()
        assert "trace_workflow" in source


# ──────────────────────────────────────────────────────────────
# Lifespan Pattern
# ──────────────────────────────────────────────────────────────

class TestApiLifespan:
    """Verify the lifespan context manager pattern."""

    def test_lifespan_is_async_context_manager(self) -> None:
        source = _read_api()
        assert "asynccontextmanager" in source
        assert "async def lifespan" in source

    def test_lifespan_initializes_foundry_client(self) -> None:
        source = _read_api()
        assert "FoundryLocalClient(" in source

    def test_lifespan_bound_to_app(self) -> None:
        source = _read_api()
        assert "lifespan=lifespan" in source


# ──────────────────────────────────────────────────────────────
# Workflow Integration
# ──────────────────────────────────────────────────────────────

class TestApiWorkflowIntegration:
    """Verify that api.py invokes the workflow correctly."""

    def test_builds_workflow_per_request(self) -> None:
        source = _read_api()
        assert "build_travel_planner_workflow" in source

    def test_uses_streaming_mode(self) -> None:
        source = _read_api()
        assert "stream=True" in source

    def test_uses_mcp_tool_async_context(self) -> None:
        source = _read_api()
        assert "async with mcp_tool" in source

    def test_tracks_sent_messages_for_incremental_streaming(self) -> None:
        """API must track sent_message_count to avoid duplicate messages with intermediate_outputs."""
        source = _read_api()
        assert "sent_message_count" in source, (
            "api.py must track sent_message_count for incremental streaming"
        )


# ──────────────────────────────────────────────────────────────
# Dependencies in requirements.txt
# ──────────────────────────────────────────────────────────────

class TestApiDependencies:
    """Verify that api.py dependencies are declared in requirements.txt."""

    @pytest.mark.parametrize("package", [
        "fastapi",
        "uvicorn",
        "sse-starlette",
        "opentelemetry-instrumentation-fastapi",
    ])
    def test_dependency_in_requirements(self, package: str) -> None:
        requirements = _read_requirements()
        assert package in requirements, (
            f"Package '{package}' must be listed in requirements.txt"
        )


# ──────────────────────────────────────────────────────────────
# Entry Point
# ──────────────────────────────────────────────────────────────

class TestApiEntryPoint:
    """Verify api.py can be executed directly."""

    def test_has_main_guard(self) -> None:
        source = _read_api()
        assert 'if __name__ == "__main__"' in source

    def test_main_runs_uvicorn(self) -> None:
        source = _read_api()
        assert "uvicorn.run(" in source


# ──────────────────────────────────────────────────────────────
# Config Integration
# ──────────────────────────────────────────────────────────────

class TestApiConfigIntegration:
    """Verify api.py uses Settings from src.config."""

    def test_uses_get_settings(self) -> None:
        source = _read_api()
        assert "get_settings()" in source

    def test_uses_api_host_setting(self) -> None:
        source = _read_api()
        assert "api_host" in source

    def test_uses_api_port_setting(self) -> None:
        source = _read_api()
        assert "api_port" in source
