"""
Telemetry Module
================
Configures OpenTelemetry tracing via the Agent Framework's built-in provider,
and exposes helpers for custom business-level spans and metrics.

Exports traces to Jaeger via OTLP gRPC (port 4317).
"""

import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Generator

from opentelemetry import metrics, trace

logger = logging.getLogger(__name__)

# Module-level tracer and meter (initialized after setup)
_tracer: trace.Tracer | None = None
_meter: metrics.Meter | None = None

# Custom metrics
_workflow_duration: metrics.Histogram | None = None
_agent_duration: metrics.Histogram | None = None
_mcp_tool_calls: metrics.Counter | None = None


def setup_telemetry(service_name: str = "travel-planner-orchestration") -> None:
    """Initialize OpenTelemetry using Agent Framework's built-in configuration.

    This configures:
    - Traces exported to OTLP endpoint (reads OTEL_EXPORTER_OTLP_ENDPOINT env var)
    - Console span exporter for local debugging
    - Custom business metrics (workflow duration, agent duration, MCP tool calls)

    Args:
        service_name: The service name to use for telemetry spans.
    """
    global _tracer, _meter, _workflow_duration, _agent_duration, _mcp_tool_calls

    try:
        from agent_framework.observability import configure_otel_providers

        configure_otel_providers(
            enable_sensitive_data=True,
        )
        logger.info("OpenTelemetry configured via Agent Framework (OTLP → %s)", 
                     os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", 
                               os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "not set")))
    except Exception as e:
        logger.warning("Failed to configure Agent Framework OTel providers: %s", e)
        logger.info("Telemetry will be limited to custom spans only")

    # Set up custom tracer and meter for business events
    _tracer = trace.get_tracer(service_name, "1.0.0")
    _meter = metrics.get_meter(service_name, "1.0.0")

    # Custom metrics
    _workflow_duration = _meter.create_histogram(
        name="workflow.duration",
        description="Total workflow execution time in seconds",
        unit="s",
    )
    _agent_duration = _meter.create_histogram(
        name="agent.duration",
        description="Individual agent execution time in seconds",
        unit="s",
    )
    _mcp_tool_calls = _meter.create_counter(
        name="mcp.tool_calls",
        description="Number of MCP tool invocations",
        unit="1",
    )


def get_tracer() -> trace.Tracer:
    """Get the configured tracer, or a no-op tracer if not initialized."""
    return _tracer or trace.get_tracer("travel-planner-fallback")


@contextmanager
def trace_workflow(workflow_name: str, query: str) -> Generator[trace.Span, None, None]:
    """Context manager that creates a span for the entire workflow execution.

    Args:
        workflow_name: Name of the workflow being executed.
        query: The user query that initiated the workflow.

    Yields:
        The active span for additional attribute setting.
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(
        f"workflow.{workflow_name}",
        attributes={
            "workflow.name": workflow_name,
            "workflow.input": query,
        },
    ) as span:
        start = time.perf_counter()
        try:
            yield span
        finally:
            duration = time.perf_counter() - start
            span.set_attribute("workflow.duration_s", round(duration, 3))
            if _workflow_duration:
                _workflow_duration.record(duration, {"workflow.name": workflow_name})


@contextmanager
def trace_agent(agent_name: str, **attributes: Any) -> Generator[trace.Span, None, None]:
    """Context manager that creates a span for an individual agent invocation.

    Args:
        agent_name: Name of the agent being invoked.
        **attributes: Additional span attributes.

    Yields:
        The active span.
    """
    tracer = get_tracer()
    span_attrs: dict[str, Any] = {"agent.name": agent_name}
    span_attrs.update(attributes)

    with tracer.start_as_current_span(
        f"agent.{agent_name}",
        attributes=span_attrs,
    ) as span:
        start = time.perf_counter()
        try:
            yield span
        finally:
            duration = time.perf_counter() - start
            span.set_attribute("agent.duration_s", round(duration, 3))
            if _agent_duration:
                _agent_duration.record(duration, {"agent.name": agent_name})


def record_mcp_tool_call(tool_name: str, server_url: str) -> None:
    """Record an MCP tool invocation metric.

    Args:
        tool_name: Name of the MCP tool called.
        server_url: URL of the MCP server.
    """
    if _mcp_tool_calls:
        _mcp_tool_calls.add(1, {"tool.name": tool_name, "mcp.server_url": server_url})


def shutdown_telemetry() -> None:
    """Flush all pending spans/metrics and shut down providers.

    Must be called before process exit to ensure all telemetry
    data is exported to the backend (e.g., Jaeger).
    BatchSpanProcessor buffers data and may lose it on abrupt exit.
    """
    tracer_provider = trace.get_tracer_provider()
    if hasattr(tracer_provider, "force_flush"):
        tracer_provider.force_flush(timeout_millis=5000)  # type: ignore[attr-defined]
        logger.info("Telemetry spans flushed")
    if hasattr(tracer_provider, "shutdown"):
        tracer_provider.shutdown()  # type: ignore[attr-defined]

    meter_provider = metrics.get_meter_provider()
    if hasattr(meter_provider, "force_flush"):
        meter_provider.force_flush(timeout_millis=5000)  # type: ignore[attr-defined]
    if hasattr(meter_provider, "shutdown"):
        meter_provider.shutdown()  # type: ignore[attr-defined]
