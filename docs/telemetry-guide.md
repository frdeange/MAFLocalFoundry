# Telemetry Guide

## Overview

This project uses **OpenTelemetry** for observability, exporting traces, metrics,
and structured logs to the **.NET Aspire Dashboard** via OTLP gRPC.

The Microsoft Agent Framework (MAF) provides built-in instrumentation through
`configure_otel_providers()`, which automatically creates spans for:

- Agent invocations
- LLM model calls
- Tool executions (including MCP)

Custom business spans in `src/telemetry.py` add workflow-level and agent-level
timing, plus MCP tool-call counters.

## Architecture

```
Python Process                          Docker
┌──────────────────────┐     gRPC     ┌──────────────────────┐
│  MAF + OTel SDK      │ ──────────→  │  Aspire Dashboard    │
│                      │   :4317      │  :18888 (UI)         │
│  TracerProvider      │              │  :18889 (OTLP gRPC)  │
│  MeterProvider       │              │  :18890 (OTLP HTTP)  │
│  LoggerProvider      │              └──────────────────────┘
└──────────────────────┘
```

Host port 4317 is mapped to container port 18889 (Aspire's internal gRPC port).

## Setup Checklist

### 1. Install the OTLP Exporter Package

The `opentelemetry-exporter-otlp-proto-grpc` package is an **optional** dependency
of the Agent Framework. Without it, `configure_otel_providers()` silently falls back
to no-op exporters and you will see **no data** in the dashboard.

```bash
pip install opentelemetry-exporter-otlp-proto-grpc
```

This package is listed in `requirements.txt`, so `pip install -r requirements.txt`
will install it. But if you manually install packages, don't skip this one.

### 2. Call `load_dotenv()` Before MAF Imports

`configure_otel_providers()` reads standard OpenTelemetry environment variables
(`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`, etc.) at **import time**.
If `load_dotenv()` hasn't been called yet, those variables won't be set and the
exporter won't know where to send data.

```python
# ✅ Correct — load .env FIRST
from dotenv import load_dotenv
load_dotenv()

from agent_framework.observability import configure_otel_providers

# ❌ Wrong — .env not loaded when MAF reads env vars
from agent_framework.observability import configure_otel_providers
from dotenv import load_dotenv
load_dotenv()  # Too late!
```

### 3. Call `shutdown_telemetry()` Before Process Exit

MAF's `configure_otel_providers()` creates a `BatchSpanProcessor` that buffers
spans and exports them in the background. If your process exits before the buffer
is flushed, **spans are lost**.

Always call `shutdown_telemetry()` (from `src/telemetry.py`) after the workflow
completes:

```python
from src.telemetry import setup_telemetry, shutdown_telemetry

setup_telemetry()
# ... run workflow ...
shutdown_telemetry()  # flushes pending spans/metrics and shuts down providers
```

The function calls `force_flush(timeout_millis=5000)` followed by `shutdown()` on
both the `TracerProvider` and `MeterProvider`.

### 4. Start the Aspire Dashboard

```bash
docker compose up -d
```

Then open [http://localhost:18888](http://localhost:18888) to view:

- **Traces**: All spans from agent invocations, model calls, and custom business spans
- **Metrics**: `workflow.duration`, `agent.duration`, `mcp.tool_calls` histograms/counters
- **Structured Logs**: Python logging output captured by the OTel log bridge

## Environment Variables

| Variable | Value | Purpose |
|----------|-------|---------|
| `ENABLE_OTEL` | `true` | Enables OpenTelemetry in this project |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | OTLP endpoint (all signals) |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `grpc` | Transport protocol |
| `OTEL_SERVICE_NAME` | `travel-planner-orchestration` | Service name in telemetry data |

> **Note**: Use `OTEL_EXPORTER_OTLP_ENDPOINT` (base endpoint) rather than
> signal-specific variables like `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`. The base
> endpoint applies to all three signals (traces, metrics, logs), which is what
> Aspire Dashboard expects.

## Custom Spans and Metrics

### Workflow Span

```python
from src.telemetry import trace_workflow

with trace_workflow("travel_planner", user_query) as span:
    # ... execute workflow ...
    span.set_attribute("custom.key", "value")
```

Automatically records: `workflow.name`, `workflow.input`, `workflow.duration_s`.

### Agent Span

```python
from src.telemetry import trace_agent

with trace_agent("researcher", custom_attr="value") as span:
    # ... invoke agent ...
```

Automatically records: `agent.name`, `agent.duration_s`, plus any custom attributes.

### MCP Tool Call Counter

```python
from src.telemetry import record_mcp_tool_call

record_mcp_tool_call("get_weather", "http://localhost:8090/mcp")
```

Increments the `mcp.tool_calls` counter with `tool.name` and `mcp.server_url` labels.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| No data in Aspire Dashboard | `load_dotenv()` not called before MAF imports | Move `load_dotenv()` to the top of `main.py`, before any `from agent_framework` imports |
| No data in Aspire Dashboard | `opentelemetry-exporter-otlp-proto-grpc` not installed | `pip install opentelemetry-exporter-otlp-proto-grpc` |
| Intermittent missing spans | Process exits before `BatchSpanProcessor` flushes | Call `shutdown_telemetry()` before exit |
| Connection refused on port 4317 | Aspire Dashboard not running | `docker compose up -d` |
| UNIMPLEMENTED errors for metrics/logs | Backend only supports traces (e.g., Jaeger) | Switch to Aspire Dashboard which supports all three signals |

## Why Aspire Dashboard Instead of Jaeger?

Jaeger only supports **traces**. When the Agent Framework exports metrics and logs
alongside traces (all via OTLP), Jaeger returns `UNIMPLEMENTED` errors for those
signals. The Aspire Dashboard accepts **all three OTLP signals** in a single
container, providing a complete observability view without error noise.
