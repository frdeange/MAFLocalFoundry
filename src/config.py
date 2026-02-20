"""
Configuration Module
====================
Centralized settings loaded from environment variables and .env file.
Uses python-dotenv for local development and standard os.environ for production.
"""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

# Load .env file (no-op if not present)
load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Immutable application settings resolved from environment variables.

    Attributes:
        foundry_model_id: FoundryLocal model identifier (e.g. "Phi-4-mini-instruct-cuda-gpu:5").
        mcp_server_url: URL of the FastMCP HTTP server (e.g. "http://localhost:8090/mcp").
        otel_endpoint: OTLP gRPC endpoint for telemetry export (e.g. "http://localhost:4317").
        otel_service_name: Service name tag for telemetry spans.
    """

    foundry_model_id: str = field(
        default_factory=lambda: os.getenv("FOUNDRY_LOCAL_MODEL_ID", "Phi-4-mini-instruct-cuda-gpu:5")
    )
    mcp_server_url: str = field(
        default_factory=lambda: os.getenv("MCP_SERVER_URL", "http://localhost:8090/mcp")
    )
    otel_endpoint: str = field(
        default_factory=lambda: os.getenv(
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
            os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
        )
    )
    otel_service_name: str = field(
        default_factory=lambda: os.getenv("OTEL_SERVICE_NAME", "travel-planner-orchestration")
    )


def get_settings() -> Settings:
    """Create and return a Settings instance from current environment."""
    return Settings()
