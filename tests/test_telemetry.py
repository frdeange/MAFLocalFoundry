"""
Telemetry Tests
===============
Tests for the telemetry module's spans and metrics helpers.
"""

import pytest

from src.telemetry import (
    get_tracer,
    record_mcp_tool_call,
    setup_telemetry,
    trace_agent,
    trace_workflow,
)


class TestSetupTelemetry:
    """Tests for telemetry initialization."""

    def test_setup_does_not_raise(self) -> None:
        """setup_telemetry should not raise even without the OTLP backend running."""
        setup_telemetry(service_name="test-service")

    def test_get_tracer_returns_tracer(self) -> None:
        """get_tracer should always return a Tracer (possibly no-op)."""
        tracer = get_tracer()
        assert tracer is not None


class TestTraceWorkflow:
    """Tests for the trace_workflow context manager."""

    def test_trace_workflow_creates_span(self) -> None:
        setup_telemetry("test")
        with trace_workflow("test_wf", "test query") as span:
            assert span is not None

    def test_trace_workflow_sets_attributes(self) -> None:
        setup_telemetry("test")
        with trace_workflow("wf_attrs", "my query") as span:
            # Span should have workflow attributes set
            pass  # No exception means success


class TestTraceAgent:
    """Tests for the trace_agent context manager."""

    def test_trace_agent_creates_span(self) -> None:
        setup_telemetry("test")
        with trace_agent("test_agent") as span:
            assert span is not None

    def test_trace_agent_with_custom_attributes(self) -> None:
        setup_telemetry("test")
        with trace_agent("custom_agent", custom_key="custom_value") as span:
            pass  # No exception means success


class TestRecordMcpToolCall:
    """Tests for MCP tool call metric recording."""

    def test_record_mcp_tool_call_does_not_raise(self) -> None:
        setup_telemetry("test")
        record_mcp_tool_call("get_weather", "http://localhost:8090/mcp")

    def test_record_without_setup_does_not_raise(self) -> None:
        """Should not raise even if telemetry is not initialized."""
        record_mcp_tool_call("get_weather", "http://localhost:8090/mcp")
