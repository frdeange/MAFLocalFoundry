# Travel Planner — Multi-Agent Orchestration PoC

A proof-of-concept multi-agent system using **Microsoft Agent Framework (MAF)**
with **FoundryLocal** for local GPU-based SLM inference.

Three specialized agents collaborate in a sequential pipeline to produce
personalized travel itineraries:

```
User Query → [Researcher] → [WeatherAnalyst] → [Planner] → Travel Plan
```

## Features

- **In-process orchestration** via MAF `SequentialBuilder`
- **FoundryLocal** as local SLM runtime (no API keys required)
- **FastMCP** tool server in Docker container (Streamable HTTP)
- **OpenTelemetry** observability with Aspire Dashboard (traces + metrics + logs)
- **Architecture compliance tests** with pytest
- **Configurable** model and endpoints via `.env`

## Prerequisites

- Python 3.13+
- Docker Desktop (for MCP server and Aspire Dashboard)
- NVIDIA GPU with CUDA support (for FoundryLocal)
- [FoundryLocal](https://github.com/microsoft/foundry-local) installed

## Quick Start

### 1. Clone and Configure

```bash
cp .env.example .env
# Edit .env if you want to change the model or ports
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Start Infrastructure

```bash
docker compose up -d
```

This starts:
- **MCP Server** on port 8090 (travel tools: weather, time, restaurants)
- **Aspire Dashboard** UI on port 18888 (traces + metrics + logs)

### 4. Run the Travel Planner

```bash
# Default query (Tokyo trip)
python main.py

# Custom query
python main.py "Plan a 5-day trip to Barcelona, Spain. I love architecture and tapas."
```

### 5. View Traces

Open [http://localhost:18888](http://localhost:18888) to view traces, metrics,
and structured logs for the `travel-planner-orchestration` service.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `FOUNDRY_LOCAL_MODEL_ID` | `Phi-4-mini-instruct-cuda-gpu:5` | FoundryLocal model |
| `MCP_SERVER_URL` | `http://localhost:8090/mcp` | MCP server endpoint |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | OTLP gRPC endpoint |
| `OTEL_SERVICE_NAME` | `travel-planner-orchestration` | Service name in traces |

## Testing

```bash
# Run all tests
pytest tests/ -v

# Architecture compliance only
pytest tests/test_architecture.py -v

# MCP tool unit tests
pytest tests/test_mcp_tools.py -v
```

## Project Structure

```
├── main.py                      # Entry point
├── docker-compose.yml           # MCP server + Aspire Dashboard
├── .env                         # Configuration
├── src/
│   ├── config.py                # Settings from env vars
│   ├── telemetry.py             # OpenTelemetry setup
│   ├── agents/
│   │   ├── researcher.py        # Destination research
│   │   ├── weather_analyst.py   # Weather + MCP tools
│   │   └── planner.py           # Itinerary synthesis
│   └── workflows/
│       └── travel_planner.py    # Sequential pipeline
├── mcp_server/
│   ├── server.py                # FastMCP tool server
│   └── Dockerfile               # Container image
├── tests/                       # Compliance + unit tests
└── docs/                        # Architecture documentation
```

## Documentation

- [Architecture Overview](docs/architecture.md)
- [Telemetry Guide](docs/telemetry-guide.md)
- [Adding New Agents](docs/adding-agents.md)
- [Creating Workflows](docs/creating-workflows.md)
- [Agent Design Guide](docs/agent-design-guide.md)

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Orchestration | Microsoft Agent Framework (SequentialBuilder) |
| LLM Runtime | FoundryLocal (local GPU inference) |
| Tool Protocol | Model Context Protocol (MCP) via FastMCP |
| Observability | OpenTelemetry + Aspire Dashboard |
| Containers | Docker Compose |
| Language | Python 3.13 |
