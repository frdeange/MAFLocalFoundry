# Architecture Overview

## Travel Planner — Multi-Agent Orchestration

### System Context

This project implements a **multi-agent orchestration** proof-of-concept using the
[Microsoft Agent Framework (MAF)](https://github.com/microsoft/agent-framework) with
**FoundryLocal** as the local Small Language Model (SLM) runtime.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Host Machine (GPU)                             │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │           Python Process (api.py / main.py)                     │    │
│  │                                                                 │    │
│  │  ┌─────────────┐  SequentialBuilder  ┌────────────┐             │    │
│  │  │ Researcher  │ ──────────────────→ │ Weather    │             │    │
│  │  │ (LLM only)  │                    │ Analyst    │             │    │
│  │  └─────────────┘                    │ (MCP tools)│             │    │
│  │                                     └─────┬──────┘             │    │
│  │                                           │                    │    │
│  │                                     ┌─────▼──────┐             │    │
│  │                                     │ Planner    │             │    │
│  │                                     │ (LLM only) │             │    │
│  │                                     └────────────┘             │    │
│  │                                                                 │    │
│  │  FastAPI (api.py) ←─── SSE/REST ──── Nginx (web-ui :8080)      │    │
│  │  FoundryLocalClient ←→ FoundryLocal Runtime (GPU)               │    │
│  │  OpenTelemetry SDK  ──→ OTLP Exporter                          │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│         │ HTTP              │ gRPC                                       │
│         ▼                   ▼                                            │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐   │
│  │ Docker:          │  │ Docker:          │  │ Docker:              │   │
│  │ MCP Server       │  │ Aspire Dashboard │  │ OTel Collector       │   │
│  │ FastMCP (:8090)  │  │ UI (:18888)      │  │ OTLP HTTP (:4319)   │   │
│  │ + OTel auto-inst │─→│ OTLP gRPC        │←─│ → gRPC → Aspire     │   │
│  │ Streamable HTTP  │  │ (:18889/:4317)   │  │ CORS for browser    │   │
│  └──────────────────┘  └──────────────────┘  └──────────────────────┘   │
│                                  ▲                     ▲                 │
│  ┌─────────────────────────────┐ │                     │                 │
│  │ Docker: Web UI (Nginx)     │ │                     │                 │
│  │ Static files (:8080)       │──── /otlp/ proxy ─────┘                 │
│  │ /api/ → host:8000 (SSE)   │                                         │
│  │ Browser OTel (telemetry.js)│                                         │
│  └─────────────────────────────┘                                        │
└─────────────────────────────────────────────────────────────────────────┘

> Telemetry flows:
> - Python process (host) → port 4317 → Aspire Dashboard
> - MCP server (Docker) → aspire-dashboard:18889 → Aspire Dashboard
> - Browser (telemetry.js) → /otlp/ → Nginx → OTel Collector → Aspire Dashboard
> All three sources appear in the same Aspire Dashboard, enabling end-to-end
> distributed tracing from browser click to LLM response.
```

### Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Orchestration | In-process (SequentialBuilder) | MAF's native pattern; all agents share the same process and conversation context |
| LLM Runtime | FoundryLocal | Local GPU inference, no API keys, model configured via `.env` |
| Agent-to-Agent | Shared conversation (list[Message]) | SequentialBuilder passes messages down the chain automatically |
| External Tools | FastMCP (Streamable HTTP) | Single MCP server in Docker container, no auth, port 8090 |
| Observability | OpenTelemetry → Aspire Dashboard | Aspire Dashboard (Docker) for traces, metrics, and structured logs |
| Configuration | `.env` + python-dotenv | Environment-based, 12-factor compatible |

### Components

#### 1. Agents (In-Process)

| Agent | Role | Tools |
|-------|------|-------|
| **Researcher** | Gathers destination info (culture, attractions, transport) | None (LLM knowledge) |
| **WeatherAnalyst** | Fetches and analyzes weather, time, dining options | `get_weather`, `get_current_time`, `search_restaurants` via MCP |
| **Planner** | Synthesizes research + weather into a travel itinerary | None (LLM synthesis) |

All agents are created via `FoundryLocalClient.as_agent()` and wired into a
`SequentialBuilder(participants=[researcher, weather_analyst, planner]).build()` workflow.

#### 2. MCP Server (Docker Container)

- **Technology**: FastMCP 3.0, Python 3.13
- **Transport**: Streamable HTTP on port 8090 (`/mcp` endpoint)
- **Tools**: `get_weather`, `get_current_time`, `search_restaurants`
- **Telemetry**: Auto-instrumented via `opentelemetry-instrument` (service: `travel-mcp-tools`)
- **No authentication** (PoC scope)

The Weather Analyst agent connects to the MCP server using MAF's `MCPStreamableHTTPTool`.
FastMCP's native OpenTelemetry instrumentation automatically creates spans for each
`tools/call` operation, following [MCP semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/mcp/).
The MCP server exports telemetry to Aspire Dashboard via the Docker internal network
(`aspire-dashboard:18889`).

#### 3. Web API (Host Process)

- **Technology**: FastAPI + uvicorn + sse-starlette
- **Entry point**: `api.py` (root directory)
- **Port**: 8000 (configurable via `API_HOST`, `API_PORT` env vars)
- **Endpoints**:
  - `POST /api/plan` → SSE stream of workflow events (agent progress, messages, output)
  - `GET /api/health` → Healthcheck
- **Telemetry**: Auto-instrumented via `FastAPIInstrumentor`, plus `trace_workflow` spans
- **Lifecycle**: FoundryLocalClient initialized once at startup (GPU bootstrap), shared across requests

#### 4. Web UI (Docker Container)

- **Technology**: Vanilla JS + CSS (no build step), Nginx Alpine
- **Port**: 8080 (Nginx serves static files)
- **Features**:
  - Real-time SSE streaming with per-agent progress indicators
  - Agent-specific visual styling (Researcher=🔍/blue, WeatherAnalyst=🌤️/orange, Planner=📋/green)
  - Conversation history via `localStorage` (up to 50 entries)
  - Sidebar with history replay
- **Proxy routes**:
  - `/api/` → `host.docker.internal:8000` (FastAPI, SSE-friendly with `proxy_buffering off`)
  - `/otlp/` → `otel-collector:4319` (browser trace export)
- **Telemetry**: `telemetry.js` — lightweight OTel browser instrumentation with W3C `traceparent` propagation

#### 5. Observability (Docker Containers)

**Aspire Dashboard**:
- Collects and visualizes traces, metrics, and structured logs
- OTLP gRPC: Host port 4317 → container port 18889
- OTLP HTTP: Host port 4318 → container port 18890
- UI: Port 18888
- Services reporting: `travel-planner-orchestration`, `travel-mcp-tools`, `travel-planner-web-ui`

**OTel Collector** (Browser Trace Bridge):
- Image: `otel/opentelemetry-collector-contrib:latest`
- Port: 4319 (OTLP/HTTP with CORS)
- Purpose: Bridges browser → Aspire Dashboard (browsers can't use gRPC, Aspire lacks CORS headers)
- Pipeline: OTLP HTTP receiver → batch processor → gRPC exporter to `aspire-dashboard:18889`

The Agent Framework's `configure_otel_providers()` automatically instruments all agent
calls, model invocations, and tool executions. Custom business spans wrap the workflow
and individual agent steps.

The MCP server is independently instrumented using `opentelemetry-instrument` (auto-
instrumentation CLI), which detects Starlette/uvicorn and creates server-side spans
for every tool call. This enables **distributed tracing**: the orchestrator's HTTP
client propagates W3C `traceparent` headers, and the MCP server's instrumented HTTP
stack extracts them, linking MCP tool spans as children of the agent spans.

> **Important**: See [Telemetry Guide](telemetry-guide.md) for setup requirements and
> common pitfalls when working with OpenTelemetry in this project.

### Data Flow

```
                  Web UI (browser :8080)          CLI (main.py)
                       │                               │
                  POST /api/plan (SSE)           Direct workflow call
                       │                               │
                       ▼                               ▼
┌──────────────────────────────────────────────────────┐
│  FastAPI (api.py) / SequentialBuilder Workflow        │
│                                                      │
│  1. Researcher receives user query                   │
│     → Produces: Research Brief (attractions, tips)    │
│                                                      │
│  2. WeatherAnalyst receives conversation so far      │
│     → Calls MCP tools: get_weather, get_current_time │
│     → Produces: Weather Analysis                     │
│                                                      │
│  3. Planner receives full conversation               │
│     → Produces: Complete Travel Itinerary            │
│                                                      │
│  Output: list[Message] with all agent responses       │
└──────────────────────────────────────────────────────┘
    │                                           │
    ▼ (SSE events to browser)                   ▼ (terminal)
Final Travel Plan displayed to user
```

### Project Structure

```
localOrchestration/
├── main.py                      # CLI entry point
├── api.py                       # FastAPI server (Web UI backend)
├── docker-compose.yml           # 4 services: MCP, Aspire, Web UI, OTel Collector
├── requirements.txt             # Python dependencies
├── .env                         # Environment configuration
├── .env.example                 # Template for .env
├── src/
│   ├── __init__.py
│   ├── config.py                # Settings from env vars (incl. api_host, api_port)
│   ├── telemetry.py             # OTel setup + custom spans
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── researcher.py        # Research agent factory
│   │   ├── weather_analyst.py   # Weather agent + MCP tool
│   │   └── planner.py           # Planner agent factory
│   └── workflows/
│       ├── __init__.py
│       └── travel_planner.py    # SequentialBuilder workflow
├── web_ui/
│   ├── Dockerfile               # Nginx Alpine container
│   ├── nginx.conf               # Static + /api/ + /otlp/ proxy
│   ├── index.html               # Chat interface layout
│   ├── app.js                   # SSE streaming, message rendering, history
│   ├── telemetry.js             # Browser OTel (traceparent, OTLP/HTTP export)
│   └── style.css                # Dark theme, agent colors
├── otel-collector/
│   └── otel-collector-config.yaml  # OTLP HTTP→gRPC bridge with CORS
├── mcp_server/
│   ├── server.py                # FastMCP tool server
│   ├── Dockerfile               # Container image
│   └── requirements.txt         # Server dependencies
├── tests/
│   ├── test_api.py              # API structural tests
│   ├── test_architecture.py     # Compliance tests
│   ├── test_config.py           # Config module tests
│   ├── test_docker_integration.py  # Docker compose + OTel collector tests
│   ├── test_mcp_tools.py        # MCP tool unit tests
│   ├── test_telemetry.py        # Telemetry tests
│   ├── test_telemetry_patterns.py  # Telemetry config validation
│   ├── test_web_ui.py           # Web UI structural tests
│   └── test_workflow_patterns.py# Workflow pattern tests
├── docs/
│   ├── architecture.md          # This document
│   ├── adding-agents.md         # How to add new agents
│   ├── creating-workflows.md    # How to create workflows
│   ├── telemetry-guide.md       # OTel + Aspire setup guide
│   └── agent-design-guide.md    # Agent prompt design
└── prototypes/                  # Original exploration scripts
    ├── main.py
    ├── main_openai.py
    └── mstest.py
```
