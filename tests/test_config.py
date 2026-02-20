"""
Configuration Tests
===================
Tests for the configuration module.
"""

import os

import pytest

from src.config import Settings, get_settings


class TestSettings:
    """Tests for the Settings dataclass."""

    def test_default_values(self) -> None:
        s = Settings()
        assert s.foundry_model_id is not None
        assert s.mcp_server_url is not None
        assert s.otel_endpoint is not None
        assert s.otel_service_name is not None

    def test_mcp_server_url_default(self) -> None:
        s = Settings()
        assert "8090" in s.mcp_server_url

    def test_otel_endpoint_default(self) -> None:
        s = Settings()
        assert "4317" in s.otel_endpoint

    def test_settings_is_frozen(self) -> None:
        s = Settings()
        with pytest.raises(AttributeError):
            s.foundry_model_id = "changed"  # type: ignore[misc]


class TestGetSettings:
    """Tests for the get_settings factory function."""

    def test_returns_settings_instance(self) -> None:
        s = get_settings()
        assert isinstance(s, Settings)

    def test_reads_environment_variable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FOUNDRY_LOCAL_MODEL_ID", "test-model-123")
        s = get_settings()
        assert s.foundry_model_id == "test-model-123"

    def test_reads_mcp_url_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MCP_SERVER_URL", "http://custom:9999/mcp")
        s = get_settings()
        assert s.mcp_server_url == "http://custom:9999/mcp"

    def test_reads_otel_endpoint_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel:5555")
        s = get_settings()
        assert s.otel_endpoint == "http://otel:5555"

    def test_reads_api_host_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("API_HOST", "127.0.0.1")
        s = get_settings()
        assert s.api_host == "127.0.0.1"

    def test_reads_api_port_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("API_PORT", "9000")
        s = get_settings()
        assert s.api_port == 9000


class TestApiSettings:
    """Tests for the API-related settings fields."""

    def test_api_host_default(self) -> None:
        s = Settings()
        assert s.api_host == "0.0.0.0"

    def test_api_port_default(self) -> None:
        s = Settings()
        assert s.api_port == 8000

    def test_api_port_is_int(self) -> None:
        s = Settings()
        assert isinstance(s.api_port, int)
