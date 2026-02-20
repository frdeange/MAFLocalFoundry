# AGENTS.md — GitHub Copilot Agent Instructions

> This file provides context for GitHub Copilot to work effectively with this codebase.
> Read this file FIRST before making any changes.

## Project Overview

**Travel Planner** — A multi-agent orchestration PoC using **Microsoft Agent Framework (MAF)** with **FoundryLocal** for local GPU-based SLM inference. Three agents collaborate sequentially to produce travel itineraries.

- **Repository**: `frdeange/MAFLocalFoundry`
- **Branch**: `main`
- **Language**: Python 3.13
- **Package Manager**: pip (no pyproject.toml — uses `requirements.txt`)
- **Virtual Environment**: `.localFoundry/` (venv, gitignored)

## Architecture

```
User Query → [Researcher] → [WeatherAnalyst] → [Planner] → Travel Plan
```

### Runtime Components

| Component | Technology | Location | Port |
|-----------|-----------|----------|------|
| Orchestrator | MAF SequentialBuilder | Host process (`main.py`) | — |
| LLM Runtime | FoundryLocal (GPU) | Host process | Auto-assigned |
| MCP Server | FastMCP 3.0 (Streamable HTTP) | Docker container | 8090 |
| Observability | Aspire Dashboard | Docker container | 18888 (UI), 4317→18889 (OTLP gRPC) |

### Key Data Flow

1. `main.py` loads `.env`, initializes FoundryLocal, builds workflow
2. `SequentialBuilder` chains 3 agents with shared `list[Message]` context
3. WeatherAnalyst connects to MCP server via `MCPStreamableHTTPTool`
4. OpenTelemetry traces exported to Aspire Dashboard via OTLP gRPC
5. MCP server also auto-instrumented (FastMCP native OTel spans)

## Project Structure

```
├── main.py                          # Entry point — orchestration
├── docker-compose.yml               # MCP server + Aspire Dashboard
├── requirements.txt                 # Host Python dependencies
├── .env / .env.example              # Configuration
├── AGENTS.md                        # This file
├── README.md                        # User-facing docs
│
├── src/
│   ├── __init__.py
│   ├── config.py                    # Settings from env vars (dataclass)
│   ├── telemetry.py                 # OTel setup, custom spans/metrics
│   ├── agents/
│   │   ├── __init__.py              # Re-exports all agent factories
│   │   ├── researcher.py            # LLM-only: destination research
│   │   ├── weather_analyst.py       # MCP tools: weather, time, restaurants
│   │   └── planner.py               # LLM-only: itinerary synthesis
│   └── workflows/
│       ├── __init__.py              # Re-exports workflow builder
│       └── travel_planner.py        # SequentialBuilder pipeline
│
├── mcp_server/
│   ├── server.py                    # FastMCP tool definitions + /health
│   ├── Dockerfile                   # Python 3.13-slim + OTel auto-instrument
│   └── requirements.txt             # fastmcp, opentelemetry-distro, exporter
│
├── tests/
│   ├── test_architecture.py         # Project structure compliance
│   ├── test_config.py               # Settings defaults and env loading
│   ├── test_mcp_tools.py            # MCP tool unit tests (parametrized)
│   ├── test_telemetry.py            # OTel setup and span helpers
│   ├── test_telemetry_patterns.py   # OTel config validation (Dockerfile, compose)
│   └── test_workflow_patterns.py    # Workflow structure and patterns
│
├── docs/
│   ├── architecture.md              # System architecture diagram
│   ├── telemetry-guide.md           # OTel + Aspire setup guide
│   ├── adding-agents.md             # How to add new agents
│   ├── agent-design-guide.md        # Prompt engineering for SLMs
│   └── creating-workflows.md        # SequentialBuilder usage
│
└── prototypes/                      # Early experiments (not production)
    ├── main.py                      # MCPStdioTool prototype
    ├── main_openai.py               # Direct OpenAI client prototype
    └── mstest.py                    # Basic FoundryLocal test
```

## Code Conventions

### Agent Pattern

Every agent follows the factory function pattern:

```python
# src/agents/{name}.py
from agent_framework import Agent

def create_{name}_agent(client: object) -> Agent:
    return client.as_agent(
        name="AgentName",
        instructions="...",
        tools=[...],  # Only if agent uses tools
    )
```

- Agents with tools return `tuple[Agent, MCPStreamableHTTPTool]`
- Agents without tools return `Agent` directly
- All agents registered in `src/agents/__init__.py`

### MCP Tool Pattern

```python
# mcp_server/server.py
from fastmcp import FastMCP

mcp = FastMCP(name="TravelTools")

@mcp.tool()
def tool_name(param: Annotated[str, "description"]) -> str:
    """Tool docstring becomes MCP description."""
    ...
```

- Tools use `Annotated` for parameter descriptions
- Return type is always `str`
- Custom HTTP routes via `@mcp.custom_route()`

### Configuration

All config via environment variables, loaded from `.env`:

| Variable | Default | Used By |
|----------|---------|---------|
| `FOUNDRY_LOCAL_MODEL_ID` | `Phi-4-mini-instruct-cuda-gpu:5` | Host orchestrator |
| `MCP_SERVER_URL` | `http://localhost:8090/mcp` | Host orchestrator |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | Host orchestrator |
| `OTEL_SERVICE_NAME` | `travel-planner-orchestration` | Host orchestrator |
| `ENABLE_OTEL` | `true` | Host orchestrator |
| `OTEL_SERVICE_NAME` (container) | `travel-mcp-tools` | MCP server container |
| `OTEL_EXPORTER_OTLP_ENDPOINT` (container) | `http://aspire-dashboard:18889` | MCP server container |
| `OTEL_PYTHON_EXCLUDED_URLS` | `health` | MCP server container |

### Telemetry

- Host process: Manual OTel SDK via `agent_framework.observability.configure_otel_providers()`
- MCP server: Auto-instrumented via `opentelemetry-instrument` CLI wrapper in Dockerfile
- FastMCP 3.0 creates native spans: `tools/call {name}` with MCP semantic conventions
- Custom spans: `trace_workflow()`, `trace_agent()` context managers in `src/telemetry.py`
- Custom metrics: `workflow.duration`, `agent.duration`, `mcp.tool_calls`

### Testing

```bash
pytest tests/ -v          # All tests (~61)
pytest tests/ -v -k mcp   # MCP-related only
```

- Tests are **structural/compliance** — they validate code patterns, not runtime behavior
- Tests read source files to check for patterns (imports, config, structure)
- No mocking of LLM calls — agents are tested via architecture compliance
- MCP tool functions are unit-tested directly (imported from `mcp_server.server`)

## Docker Infrastructure

### Start/Stop

```bash
docker compose up -d       # Start MCP server + Aspire Dashboard
docker compose down        # Stop and remove
docker compose build --no-cache mcp-server  # Rebuild after changes
```

### Container Details

**MCP Server** (`travel-mcp-server`):
- Image: Custom from `mcp_server/Dockerfile`
- CMD: `opentelemetry-instrument python server.py`
- Healthcheck: `GET /health` every 10s (excluded from OTel traces)
- Internal telemetry: sends to `http://aspire-dashboard:18889` (container network)

**Aspire Dashboard** (`travel-aspire-dashboard`):
- Image: `mcr.microsoft.com/dotnet/aspire-dashboard:latest`
- Auth: disabled (`DOTNET_DASHBOARD_UNSECURED_ALLOW_ANONYMOUS=true`)
- Port mapping: Host 4317 → Container 18889 (OTLP gRPC)

### Important: After changing `mcp_server/` files

1. `docker compose down`
2. `docker compose build --no-cache mcp-server`
3. `docker compose up -d`

## Key Dependencies

### Host (requirements.txt)

| Package | Purpose |
|---------|---------|
| `agent-framework` | MAF core (git install from microsoft/agent-framework) |
| `agent-framework-foundry-local` | FoundryLocal client |
| `agent-framework-orchestrations` | SequentialBuilder |
| `fastmcp==3.0.0` | MCP client (used by host for MCPStreamableHTTPTool) |
| `opentelemetry-api`, `opentelemetry-sdk` | Telemetry |
| `opentelemetry-exporter-otlp-proto-grpc` | OTLP export |
| `python-dotenv` | .env loading |
| `pytest`, `pytest-asyncio` | Testing |

### MCP Server Container (mcp_server/requirements.txt)

| Package | Purpose |
|---------|---------|
| `fastmcp==3.0.0` | MCP server framework |
| `opentelemetry-distro` | Auto-instrumentation bootstrap |
| `opentelemetry-exporter-otlp` | OTLP export (gRPC + HTTP) |

## Common Tasks

### Add a New MCP Tool

1. Add function in `mcp_server/server.py` with `@mcp.tool()` decorator
2. Add unit tests in `tests/test_mcp_tools.py`
3. Rebuild container: `docker compose down && docker compose build --no-cache mcp-server && docker compose up -d`

### Add a New Agent

1. Create `src/agents/{name}.py` following factory pattern
2. Export from `src/agents/__init__.py`
3. Wire into workflow in `src/workflows/travel_planner.py`
4. Add test in `tests/test_architecture.py`
5. See `docs/adding-agents.md` for full guide

### Add a New Workflow

1. Create `src/workflows/{name}.py`
2. Export from `src/workflows/__init__.py`
3. See `docs/creating-workflows.md` for patterns

### Run End-to-End

```bash
# Prerequisites: Docker running, GPU available, FoundryLocal installed
docker compose up -d
python main.py "Plan a trip to Paris"
# View traces at http://localhost:18888
```

## Important Notes

- **FoundryLocal requires NVIDIA GPU with CUDA** — the orchestrator won't run without it
- **MAF is installed from git** — not from PyPI. Pin to `@main` branch
- **FastMCP 3.0** — uses Streamable HTTP transport (not SSE or stdio for production)
- **The `.env` file is gitignored** — copy from `.env.example` after cloning
- **`prototypes/` directory** — contains early experiments, not part of the production pipeline
- **MCP server has mock data** — weather, restaurants are hardcoded dictionaries (PoC)
- **`load_dotenv()` must be called BEFORE MAF/OTel imports** in `main.py` — order matters

## External Documentation

- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
- [FoundryLocal](https://github.com/microsoft/foundry-local)
- [FastMCP 3.0 Docs](https://gofastmcp.com/) — especially [Telemetry](https://gofastmcp.com/servers/telemetry)
- [Aspire Dashboard](https://learn.microsoft.com/en-us/dotnet/aspire/fundamentals/dashboard/standalone)
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)
