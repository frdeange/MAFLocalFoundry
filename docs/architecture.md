# Architecture Overview

## Travel Planner — Multi-Agent Orchestration

### System Context

This project implements a **multi-agent orchestration** proof-of-concept using the
[Microsoft Agent Framework (MAF)](https://github.com/microsoft/agent-framework) with
**FoundryLocal** as the local Small Language Model (SLM) runtime.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Host Machine (GPU)                        │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Python Process (main.py)                 │  │
│  │                                                       │  │
│  │  ┌─────────────┐  SequentialBuilder  ┌────────────┐   │  │
│  │  │ Researcher  │ ──────────────────→ │ Weather    │   │  │
│  │  │ (LLM only)  │                    │ Analyst    │   │  │
│  │  └─────────────┘                    │ (MCP tools)│   │  │
│  │                                     └─────┬──────┘   │  │
│  │                                           │          │  │
│  │                                     ┌─────▼──────┐   │  │
│  │                                     │ Planner    │   │  │
│  │                                     │ (LLM only) │   │  │
│  │                                     └────────────┘   │  │
│  │                                                       │  │
│  │  FoundryLocalClient ←→ FoundryLocal Runtime (GPU)     │  │
│  │  OpenTelemetry SDK  ──→ OTLP Exporter                │  │
│  └───────────────────────────────────────────────────────┘  │
│                           │                     │           │
│                     HTTP  │               gRPC  │           │
│                           ▼                     ▼           │
│  ┌──────────────────────────┐  ┌─────────────────────────┐  │
│  │   Docker: MCP Server     │  │   Docker: Aspire        │  │
│  │   FastMCP (port 8090)    │  │   UI (port 18888)       │  │
│  │   Streamable HTTP        │  │   OTLP gRPC (port 4317) │  │
│  └──────────────────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
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
- **No authentication** (PoC scope)

The Weather Analyst agent connects to the MCP server using MAF's `MCPStreamableHTTPTool`.

#### 3. Observability (Docker Container)

- **Aspire Dashboard**: Collects and visualizes traces, metrics, and structured logs
- **OTLP gRPC**: Host port 4317 → container port 18889
- **OTLP HTTP**: Host port 4318 → container port 18890
- **UI**: Port 18888

The Agent Framework's `configure_otel_providers()` automatically instruments all agent
calls, model invocations, and tool executions. Custom business spans wrap the workflow
and individual agent steps.

> **Important**: See [Telemetry Guide](telemetry-guide.md) for setup requirements and
> common pitfalls when working with OpenTelemetry in this project.

### Data Flow

```
User Query
    │
    ▼
┌──────────────────────────────────────────────────────┐
│  SequentialBuilder Workflow                           │
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
    │
    ▼
Final Travel Plan displayed to user
```

### Project Structure

```
localOrchestration/
├── main.py                      # Entry point
├── docker-compose.yml           # MCP server + Aspire Dashboard
├── requirements.txt             # Python dependencies
├── .env                         # Environment configuration
├── .env.example                 # Template for .env
├── src/
│   ├── __init__.py
│   ├── config.py                # Settings from env vars
│   ├── telemetry.py             # OTel setup + custom spans
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── researcher.py        # Research agent factory
│   │   ├── weather_analyst.py   # Weather agent + MCP tool
│   │   └── planner.py           # Planner agent factory
│   └── workflows/
│       ├── __init__.py
│       └── travel_planner.py    # SequentialBuilder workflow
├── mcp_server/
│   ├── server.py                # FastMCP tool server
│   ├── Dockerfile               # Container image
│   └── requirements.txt         # Server dependencies
├── tests/
│   ├── test_architecture.py     # Compliance tests
│   ├── test_config.py           # Config module tests
│   ├── test_mcp_tools.py        # MCP tool unit tests
│   ├── test_telemetry.py        # Telemetry tests
│   └── test_workflow_patterns.py# Workflow pattern tests
├── docs/
│   ├── architecture.md          # This document
│   ├── adding-agents.md         # How to add new agents
│   ├── creating-workflows.md    # How to create workflows
│   └── agent-design-guide.md    # Agent prompt design
└── prototypes/                  # Original exploration scripts
    ├── main.py
    ├── main_openai.py
    └── mstest.py
```
