"""
Telemetry Pattern Tests
=======================
Validates that the project follows the required telemetry patterns
to ensure reliable OpenTelemetry data export.

These tests catch the most common telemetry setup mistakes:
1. Missing load_dotenv() before MAF imports in main.py
2. Missing shutdown_telemetry() call before process exit
3. Missing OTLP exporter package in requirements
4. Correct Aspire Dashboard configuration in docker-compose
5. MCP server auto-instrumentation and OTLP export config
"""

import ast
import os
import re

import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestLoadDotenvPattern:
    """Ensure load_dotenv() is called before any MAF/OTel imports in main.py.

    Why: configure_otel_providers() reads OTEL_* env vars at import time.
    If load_dotenv() hasn't been called, the exporter won't know where
    to send data (the endpoint defaults to None and no data is exported).
    """

    def _read_main(self) -> str:
        path = os.path.join(BASE_DIR, "main.py")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_load_dotenv_is_called(self) -> None:
        """main.py must call load_dotenv()."""
        source = self._read_main()
        assert "load_dotenv()" in source, (
            "main.py must call load_dotenv() to load .env variables"
        )

    def test_load_dotenv_before_maf_imports(self) -> None:
        """load_dotenv() must appear before any 'from agent_framework' import."""
        source = self._read_main()
        dotenv_pos = source.find("load_dotenv()")
        maf_pos = source.find("from agent_framework")
        assert dotenv_pos != -1, "load_dotenv() not found in main.py"
        assert maf_pos != -1, "agent_framework import not found in main.py"
        assert dotenv_pos < maf_pos, (
            "load_dotenv() must be called BEFORE any agent_framework imports. "
            f"Found load_dotenv() at position {dotenv_pos}, "
            f"but agent_framework import at {maf_pos}"
        )

    def test_load_dotenv_before_otel_imports(self) -> None:
        """load_dotenv() must appear before any telemetry setup import."""
        source = self._read_main()
        dotenv_pos = source.find("load_dotenv()")
        telemetry_pos = source.find("from src.telemetry")
        assert dotenv_pos != -1, "load_dotenv() not found in main.py"
        assert telemetry_pos != -1, "src.telemetry import not found in main.py"
        assert dotenv_pos < telemetry_pos, (
            "load_dotenv() must be called BEFORE importing src.telemetry"
        )


class TestShutdownTelemetryPattern:
    """Ensure shutdown_telemetry() is properly defined and called.

    Why: MAF's BatchSpanProcessor buffers spans and exports them in the
    background. If the process exits without flushing, spans are lost.
    """

    def test_shutdown_telemetry_is_importable(self) -> None:
        """shutdown_telemetry must be importable from src.telemetry."""
        from src.telemetry import shutdown_telemetry
        assert callable(shutdown_telemetry)

    def test_shutdown_telemetry_has_force_flush(self) -> None:
        """shutdown_telemetry must call force_flush to export buffered spans."""
        import inspect
        from src.telemetry import shutdown_telemetry
        source = inspect.getsource(shutdown_telemetry)
        assert "force_flush" in source, (
            "shutdown_telemetry() must call force_flush() on providers"
        )

    def test_shutdown_telemetry_has_shutdown(self) -> None:
        """shutdown_telemetry must call shutdown() on providers."""
        import inspect
        from src.telemetry import shutdown_telemetry
        source = inspect.getsource(shutdown_telemetry)
        assert ".shutdown()" in source, (
            "shutdown_telemetry() must call shutdown() on providers"
        )

    def test_main_calls_shutdown_telemetry(self) -> None:
        """main.py must call shutdown_telemetry() to flush during exit."""
        path = os.path.join(BASE_DIR, "main.py")
        with open(path, encoding="utf-8") as f:
            source = f.read()
        assert "shutdown_telemetry()" in source, (
            "main.py must call shutdown_telemetry() before process exit"
        )

    def test_main_imports_shutdown_telemetry(self) -> None:
        """main.py must import shutdown_telemetry from src.telemetry."""
        path = os.path.join(BASE_DIR, "main.py")
        with open(path, encoding="utf-8") as f:
            source = f.read()
        assert "shutdown_telemetry" in source
        # Verify it's imported, not just mentioned in a comment
        tree = ast.parse(source)
        imported = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "telemetry" in node.module:
                    for alias in node.names:
                        if alias.name == "shutdown_telemetry":
                            imported = True
        assert imported, (
            "shutdown_telemetry must be imported from src.telemetry in main.py"
        )


class TestOtlpExporterPackage:
    """Ensure the OTLP exporter package is in requirements.txt.

    Why: opentelemetry-exporter-otlp-proto-grpc is an OPTIONAL dependency
    of the Agent Framework. Without it, configure_otel_providers() silently
    creates no-op exporters and no data reaches the backend.
    """

    def test_otlp_grpc_exporter_in_requirements(self) -> None:
        """requirements.txt must include the OTLP gRPC exporter."""
        path = os.path.join(BASE_DIR, "requirements.txt")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "opentelemetry-exporter-otlp-proto-grpc" in content, (
            "requirements.txt must include opentelemetry-exporter-otlp-proto-grpc. "
            "Without it, MAF's configure_otel_providers() creates no-op exporters."
        )


class TestAspireDashboardConfig:
    """Ensure docker-compose.yml configures Aspire Dashboard correctly.

    Why: Aspire Dashboard uses non-standard internal ports (18889 for gRPC,
    18890 for HTTP). The host ports 4317/4318 must map to those internal ports.
    """

    def _read_compose(self) -> str:
        path = os.path.join(BASE_DIR, "docker-compose.yml")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_aspire_dashboard_service_exists(self) -> None:
        content = self._read_compose()
        assert "aspire-dashboard:" in content

    def test_aspire_ui_port(self) -> None:
        """Aspire UI must be accessible on port 18888."""
        content = self._read_compose()
        assert "18888:18888" in content, "Aspire UI port mapping is missing"

    def test_aspire_otlp_grpc_port(self) -> None:
        """Host port 4317 must map to Aspire's internal gRPC port 18889."""
        content = self._read_compose()
        assert "4317:18889" in content, (
            "OTLP gRPC port must map host 4317 → container 18889"
        )

    def test_aspire_anonymous_access(self) -> None:
        """Aspire must allow anonymous access in dev mode."""
        content = self._read_compose()
        assert "DOTNET_DASHBOARD_UNSECURED_ALLOW_ANONYMOUS=true" in content


class TestEnvConfiguration:
    """Ensure .env.example has the required OTEL variables."""

    def _read_env_example(self) -> str:
        path = os.path.join(BASE_DIR, ".env.example")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_otel_endpoint_configured(self) -> None:
        """Must use OTEL_EXPORTER_OTLP_ENDPOINT (base, not signal-specific)."""
        content = self._read_env_example()
        assert "OTEL_EXPORTER_OTLP_ENDPOINT" in content

    def test_otel_protocol_configured(self) -> None:
        """Must specify gRPC protocol for Aspire Dashboard."""
        content = self._read_env_example()
        assert "OTEL_EXPORTER_OTLP_PROTOCOL" in content

    def test_otel_service_name_configured(self) -> None:
        """Must set a service name for telemetry identification."""
        content = self._read_env_example()
        assert "OTEL_SERVICE_NAME" in content


class TestMcpServerTelemetryConfig:
    """Ensure the MCP server container is instrumented with OpenTelemetry.

    Why: FastMCP has native OTel API instrumentation, but without the SDK and
    exporter installed + the opentelemetry-instrument CLI wrapper, all spans
    are no-ops. The MCP server must also export to Aspire Dashboard via the
    Docker internal network (not localhost).
    """

    def _read_mcp_requirements(self) -> str:
        path = os.path.join(BASE_DIR, "mcp_server", "requirements.txt")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def _read_mcp_dockerfile(self) -> str:
        path = os.path.join(BASE_DIR, "mcp_server", "Dockerfile")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def _read_compose(self) -> str:
        path = os.path.join(BASE_DIR, "docker-compose.yml")
        with open(path, encoding="utf-8") as f:
            return f.read()

    # ── MCP requirements.txt ──────────────────────────────────

    def test_otel_distro_in_mcp_requirements(self) -> None:
        """MCP server must include opentelemetry-distro for auto-instrumentation."""
        content = self._read_mcp_requirements()
        assert "opentelemetry-distro" in content, (
            "mcp_server/requirements.txt must include opentelemetry-distro"
        )

    def test_otel_exporter_in_mcp_requirements(self) -> None:
        """MCP server must include opentelemetry-exporter-otlp for export."""
        content = self._read_mcp_requirements()
        assert "opentelemetry-exporter-otlp" in content, (
            "mcp_server/requirements.txt must include opentelemetry-exporter-otlp"
        )

    # ── MCP Dockerfile ────────────────────────────────────────

    def test_dockerfile_runs_bootstrap(self) -> None:
        """Dockerfile must run opentelemetry-bootstrap to install instrumentations."""
        content = self._read_mcp_dockerfile()
        assert "opentelemetry-bootstrap" in content, (
            "Dockerfile must run 'opentelemetry-bootstrap -a install' "
            "to auto-detect and install instrumentations (Starlette, uvicorn)"
        )

    def test_dockerfile_uses_otel_instrument_cmd(self) -> None:
        """Dockerfile CMD must use opentelemetry-instrument wrapper."""
        content = self._read_mcp_dockerfile()
        assert "opentelemetry-instrument" in content, (
            "Dockerfile CMD must use 'opentelemetry-instrument' to enable "
            "auto-instrumentation at runtime"
        )

    # ── docker-compose.yml MCP service OTEL config ────────────

    def test_mcp_service_has_otel_service_name(self) -> None:
        """MCP server must have OTEL_SERVICE_NAME set in docker-compose."""
        content = self._read_compose()
        assert "OTEL_SERVICE_NAME=travel-mcp-tools" in content, (
            "docker-compose.yml must set OTEL_SERVICE_NAME for the MCP server"
        )

    def test_mcp_service_has_otel_endpoint(self) -> None:
        """MCP server must export to Aspire via Docker internal network."""
        content = self._read_compose()
        assert "aspire-dashboard:18889" in content, (
            "MCP server's OTEL_EXPORTER_OTLP_ENDPOINT must point to "
            "aspire-dashboard:18889 (Docker internal network)"
        )

    def test_mcp_service_depends_on_aspire(self) -> None:
        """MCP server must depend on aspire-dashboard to ensure start order."""
        content = self._read_compose()
        assert "depends_on" in content, (
            "MCP server should depend on aspire-dashboard in docker-compose"
        )


# ──────────────────────────────────────────────────────────────
# API Telemetry Patterns (api.py)
# ──────────────────────────────────────────────────────────────

class TestApiTelemetryPatterns:
    """Validate that the FastAPI wrapper follows telemetry best practices.

    Why: The API layer must be auto-instrumented with OpenTelemetry so that
    HTTP spans appear in the Aspire Dashboard alongside workflow spans.
    """

    def _read_api(self) -> str:
        path = os.path.join(BASE_DIR, "api.py")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def _read_requirements(self) -> str:
        path = os.path.join(BASE_DIR, "requirements.txt")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_fastapi_instrumentation_in_requirements(self) -> None:
        """requirements.txt must include opentelemetry-instrumentation-fastapi."""
        content = self._read_requirements()
        assert "opentelemetry-instrumentation-fastapi" in content, (
            "requirements.txt must include opentelemetry-instrumentation-fastapi "
            "for automatic HTTP span creation"
        )

    def test_api_imports_fastapi_instrumentor(self) -> None:
        """api.py must import FastAPIInstrumentor."""
        source = self._read_api()
        assert "FastAPIInstrumentor" in source

    def test_api_instruments_app(self) -> None:
        """api.py must call FastAPIInstrumentor.instrument_app(app)."""
        source = self._read_api()
        assert "FastAPIInstrumentor.instrument_app(app)" in source

    def test_api_calls_setup_telemetry(self) -> None:
        """api.py must call setup_telemetry during startup."""
        source = self._read_api()
        assert "setup_telemetry(" in source

    def test_api_calls_shutdown_telemetry(self) -> None:
        """api.py must call shutdown_telemetry during shutdown."""
        source = self._read_api()
        assert "shutdown_telemetry()" in source

    def test_api_load_dotenv_before_otel(self) -> None:
        """load_dotenv() must be called before OTel imports in api.py."""
        source = self._read_api()
        dotenv_pos = source.find("load_dotenv()")
        otel_pos = source.find("opentelemetry")
        assert dotenv_pos != -1, "load_dotenv() not found in api.py"
        assert otel_pos != -1, "OpenTelemetry imports not found in api.py"
        assert dotenv_pos < otel_pos, (
            "load_dotenv() must appear BEFORE OpenTelemetry imports in api.py"
        )

    def test_api_uses_trace_workflow(self) -> None:
        """api.py must use trace_workflow context manager for request tracing."""
        source = self._read_api()
        assert "trace_workflow" in source


# ──────────────────────────────────────────────────────────────
# Browser Telemetry Patterns (web_ui/telemetry.js)
# ──────────────────────────────────────────────────────────────

class TestBrowserTelemetryPatterns:
    """Validate browser-side OpenTelemetry instrumentation.

    Why: End-to-end distributed tracing requires the browser to generate
    trace IDs and propagate them to the backend via W3C traceparent headers.
    Traces are exported via OTLP/HTTP to the OTel Collector.
    """

    def _read_telemetry_js(self) -> str:
        path = os.path.join(BASE_DIR, "web_ui", "telemetry.js")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_browser_service_name(self) -> None:
        """Browser telemetry must identify itself with a service name."""
        source = self._read_telemetry_js()
        assert "travel-planner-web-ui" in source

    def test_browser_otlp_endpoint(self) -> None:
        """Traces must be sent to /otlp/v1/traces (Nginx proxy)."""
        source = self._read_telemetry_js()
        assert "/otlp/v1/traces" in source

    def test_browser_traceparent_propagation(self) -> None:
        """Fetch calls to /api/ must include traceparent header."""
        source = self._read_telemetry_js()
        assert "traceparent" in source

    def test_browser_only_instruments_api_calls(self) -> None:
        """Traceparent must NOT be added to /otlp/ calls (avoids loops)."""
        source = self._read_telemetry_js()
        assert "/api/" in source

    def test_browser_otlp_json_format(self) -> None:
        """Spans must be exported using OTLP JSON (resourceSpans)."""
        source = self._read_telemetry_js()
        assert "resourceSpans" in source

    def test_browser_batch_export(self) -> None:
        """Spans should be batched before export."""
        source = self._read_telemetry_js()
        assert "spanBuffer" in source or "FLUSH_INTERVAL" in source


# ──────────────────────────────────────────────────────────────
# OTel Collector Telemetry Bridge
# ──────────────────────────────────────────────────────────────

class TestOtelCollectorBridge:
    """Validate the OTel Collector is configured as a CORS bridge.

    Why: Browsers cannot send gRPC and Aspire Dashboard doesn't serve
    CORS headers. The Collector accepts OTLP/HTTP with CORS, then
    forwards via gRPC to Aspire Dashboard.
    """

    def _read_collector_config(self) -> str:
        path = os.path.join(BASE_DIR, "otel-collector", "otel-collector-config.yaml")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def _read_compose(self) -> str:
        path = os.path.join(BASE_DIR, "docker-compose.yml")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_collector_in_compose(self) -> None:
        """docker-compose.yml must include otel-collector service."""
        content = self._read_compose()
        assert "otel-collector:" in content

    def test_collector_cors_enabled(self) -> None:
        """Collector must have CORS configured for browser access."""
        config = self._read_collector_config()
        assert "cors" in config
        assert "allowed_origins" in config

    def test_collector_exports_to_aspire(self) -> None:
        """Collector must forward traces to Aspire Dashboard."""
        config = self._read_collector_config()
        assert "aspire-dashboard" in config

    def test_collector_traces_pipeline(self) -> None:
        """Collector must have a traces pipeline defined."""
        config = self._read_collector_config()
        assert "traces:" in config

    def test_nginx_proxies_otlp_to_collector(self) -> None:
        """Nginx must proxy /otlp/ requests to the Collector."""
        path = os.path.join(BASE_DIR, "web_ui", "nginx.conf")
        with open(path, encoding="utf-8") as f:
            nginx = f.read()
        assert "otel-collector" in nginx
        assert "/otlp/" in nginx
