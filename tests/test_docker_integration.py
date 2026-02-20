"""
Docker Integration Tests
=========================
Structural tests for docker-compose.yml and related container configuration.
Validates service definitions, ports, dependencies, volumes,
and OTel Collector configuration.
"""

import os

import pytest
import yaml

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _read_compose() -> str:
    """Read docker-compose.yml as raw text."""
    path = os.path.join(BASE_DIR, "docker-compose.yml")
    with open(path, encoding="utf-8") as f:
        return f.read()


def _parse_compose() -> dict:
    """Parse docker-compose.yml into a Python dict."""
    path = os.path.join(BASE_DIR, "docker-compose.yml")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _read_otel_collector_config() -> str:
    """Read OTel Collector config as raw text."""
    path = os.path.join(BASE_DIR, "otel-collector", "otel-collector-config.yaml")
    with open(path, encoding="utf-8") as f:
        return f.read()


def _parse_otel_collector_config() -> dict:
    """Parse OTel Collector config into a Python dict."""
    path = os.path.join(BASE_DIR, "otel-collector", "otel-collector-config.yaml")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ──────────────────────────────────────────────────────────────
# File Existence
# ──────────────────────────────────────────────────────────────

class TestDockerFilesExist:
    """Verify Docker-related files exist."""

    def test_compose_file_exists(self) -> None:
        assert os.path.isfile(os.path.join(BASE_DIR, "docker-compose.yml"))

    def test_otel_collector_dir_exists(self) -> None:
        assert os.path.isdir(os.path.join(BASE_DIR, "otel-collector"))

    def test_otel_collector_config_exists(self) -> None:
        assert os.path.isfile(
            os.path.join(BASE_DIR, "otel-collector", "otel-collector-config.yaml")
        )

    def test_web_ui_dockerfile_exists(self) -> None:
        assert os.path.isfile(os.path.join(BASE_DIR, "web_ui", "Dockerfile"))

    def test_mcp_server_dockerfile_exists(self) -> None:
        assert os.path.isfile(os.path.join(BASE_DIR, "mcp_server", "Dockerfile"))


# ──────────────────────────────────────────────────────────────
# Service Definitions
# ──────────────────────────────────────────────────────────────

class TestComposeServices:
    """Verify docker-compose.yml defines all required services."""

    @pytest.mark.parametrize("service_name", [
        "mcp-server",
        "aspire-dashboard",
        "web-ui",
        "otel-collector",
    ])
    def test_service_defined(self, service_name: str) -> None:
        compose = _parse_compose()
        services = compose.get("services", {})
        assert service_name in services, (
            f"Service '{service_name}' must be defined in docker-compose.yml"
        )

    def test_total_service_count(self) -> None:
        compose = _parse_compose()
        services = compose.get("services", {})
        assert len(services) == 4, "docker-compose.yml must define exactly 4 services"


# ──────────────────────────────────────────────────────────────
# MCP Server Service
# ──────────────────────────────────────────────────────────────

class TestMCPServerService:
    """Verify mcp-server service configuration."""

    def test_builds_from_mcp_server_dir(self) -> None:
        compose = _parse_compose()
        svc = compose["services"]["mcp-server"]
        build = svc.get("build", {})
        assert "mcp_server" in str(build.get("context", ""))

    def test_publishes_port_8090(self) -> None:
        compose = _parse_compose()
        svc = compose["services"]["mcp-server"]
        ports = [str(p) for p in svc.get("ports", [])]
        assert any("8090" in p for p in ports)

    def test_has_otel_environment(self) -> None:
        compose = _parse_compose()
        svc = compose["services"]["mcp-server"]
        env = svc.get("environment", [])
        env_str = str(env)
        assert "OTEL_SERVICE_NAME" in env_str

    def test_depends_on_aspire(self) -> None:
        compose = _parse_compose()
        svc = compose["services"]["mcp-server"]
        depends = svc.get("depends_on", [])
        assert "aspire-dashboard" in depends

    def test_has_healthcheck(self) -> None:
        compose = _parse_compose()
        svc = compose["services"]["mcp-server"]
        assert "healthcheck" in svc


# ──────────────────────────────────────────────────────────────
# Aspire Dashboard Service
# ──────────────────────────────────────────────────────────────

class TestAspireDashboardService:
    """Verify aspire-dashboard service configuration."""

    def test_uses_aspire_image(self) -> None:
        compose = _parse_compose()
        svc = compose["services"]["aspire-dashboard"]
        image = svc.get("image", "")
        assert "aspire-dashboard" in image

    def test_publishes_ui_port(self) -> None:
        compose = _parse_compose()
        svc = compose["services"]["aspire-dashboard"]
        ports = [str(p) for p in svc.get("ports", [])]
        assert any("18888" in p for p in ports)

    def test_publishes_otlp_grpc_port(self) -> None:
        compose = _parse_compose()
        svc = compose["services"]["aspire-dashboard"]
        ports = [str(p) for p in svc.get("ports", [])]
        assert any("4317" in p for p in ports)

    def test_anonymous_auth_enabled(self) -> None:
        compose = _parse_compose()
        svc = compose["services"]["aspire-dashboard"]
        env = svc.get("environment", [])
        env_str = str(env)
        assert "UNSECURED_ALLOW_ANONYMOUS" in env_str


# ──────────────────────────────────────────────────────────────
# Web UI Service
# ──────────────────────────────────────────────────────────────

class TestWebUIService:
    """Verify web-ui service configuration."""

    def test_builds_from_web_ui_dir(self) -> None:
        compose = _parse_compose()
        svc = compose["services"]["web-ui"]
        build = svc.get("build", {})
        assert "web_ui" in str(build.get("context", ""))

    def test_publishes_port_8080(self) -> None:
        compose = _parse_compose()
        svc = compose["services"]["web-ui"]
        ports = [str(p) for p in svc.get("ports", [])]
        assert any("8080" in p for p in ports)

    def test_has_extra_hosts(self) -> None:
        """web-ui needs host.docker.internal to reach FastAPI on the host."""
        compose = _parse_compose()
        svc = compose["services"]["web-ui"]
        extra_hosts = svc.get("extra_hosts", [])
        assert any("host.docker.internal" in str(h) for h in extra_hosts)

    def test_depends_on_mcp_server(self) -> None:
        compose = _parse_compose()
        svc = compose["services"]["web-ui"]
        depends = svc.get("depends_on", [])
        assert "mcp-server" in depends

    def test_depends_on_otel_collector(self) -> None:
        compose = _parse_compose()
        svc = compose["services"]["web-ui"]
        depends = svc.get("depends_on", [])
        assert "otel-collector" in depends

    def test_has_healthcheck(self) -> None:
        compose = _parse_compose()
        svc = compose["services"]["web-ui"]
        assert "healthcheck" in svc


# ──────────────────────────────────────────────────────────────
# OTel Collector Service
# ──────────────────────────────────────────────────────────────

class TestOtelCollectorService:
    """Verify otel-collector service configuration."""

    def test_uses_contrib_image(self) -> None:
        compose = _parse_compose()
        svc = compose["services"]["otel-collector"]
        image = svc.get("image", "")
        assert "opentelemetry-collector-contrib" in image

    def test_publishes_port_4319(self) -> None:
        compose = _parse_compose()
        svc = compose["services"]["otel-collector"]
        ports = [str(p) for p in svc.get("ports", [])]
        assert any("4319" in p for p in ports)

    def test_mounts_config_volume(self) -> None:
        compose = _parse_compose()
        svc = compose["services"]["otel-collector"]
        volumes = [str(v) for v in svc.get("volumes", [])]
        assert any("otel-collector-config.yaml" in v for v in volumes)

    def test_depends_on_aspire(self) -> None:
        compose = _parse_compose()
        svc = compose["services"]["otel-collector"]
        depends = svc.get("depends_on", [])
        assert "aspire-dashboard" in depends


# ──────────────────────────────────────────────────────────────
# OTel Collector Configuration
# ──────────────────────────────────────────────────────────────

class TestOtelCollectorConfig:
    """Verify OTel Collector pipeline configuration."""

    def test_has_otlp_receiver(self) -> None:
        config = _parse_otel_collector_config()
        receivers = config.get("receivers", {})
        assert "otlp" in receivers

    def test_otlp_receiver_uses_http(self) -> None:
        config = _parse_otel_collector_config()
        otlp = config["receivers"]["otlp"]
        protocols = otlp.get("protocols", {})
        assert "http" in protocols

    def test_otlp_receiver_listens_on_4319(self) -> None:
        config_text = _read_otel_collector_config()
        assert "4319" in config_text

    def test_otlp_receiver_has_cors(self) -> None:
        """Browser OTLP calls need CORS headers."""
        config = _parse_otel_collector_config()
        http_config = config["receivers"]["otlp"]["protocols"]["http"]
        cors = http_config.get("cors", {})
        assert cors, "CORS must be configured for HTTP receiver"
        allowed = cors.get("allowed_origins", [])
        assert len(allowed) > 0, "At least one CORS origin must be allowed"

    def test_has_aspire_exporter(self) -> None:
        config = _parse_otel_collector_config()
        exporters = config.get("exporters", {})
        assert "otlp/aspire" in exporters

    def test_aspire_exporter_targets_aspire_dashboard(self) -> None:
        config = _parse_otel_collector_config()
        aspire_exporter = config["exporters"]["otlp/aspire"]
        endpoint = aspire_exporter.get("endpoint", "")
        assert "aspire-dashboard" in endpoint

    def test_has_batch_processor(self) -> None:
        config = _parse_otel_collector_config()
        processors = config.get("processors", {})
        assert "batch" in processors

    def test_traces_pipeline_defined(self) -> None:
        config = _parse_otel_collector_config()
        pipelines = config.get("service", {}).get("pipelines", {})
        assert "traces" in pipelines

    def test_traces_pipeline_uses_otlp_receiver(self) -> None:
        config = _parse_otel_collector_config()
        traces = config["service"]["pipelines"]["traces"]
        receivers = traces.get("receivers", [])
        assert "otlp" in receivers

    def test_traces_pipeline_uses_aspire_exporter(self) -> None:
        config = _parse_otel_collector_config()
        traces = config["service"]["pipelines"]["traces"]
        exporters = traces.get("exporters", [])
        assert "otlp/aspire" in exporters

    def test_traces_pipeline_uses_batch_processor(self) -> None:
        config = _parse_otel_collector_config()
        traces = config["service"]["pipelines"]["traces"]
        processors = traces.get("processors", [])
        assert "batch" in processors


# ──────────────────────────────────────────────────────────────
# Port Mapping Consistency
# ──────────────────────────────────────────────────────────────

class TestPortConsistency:
    """Cross-check that ports in docker-compose match what consumers expect."""

    def test_nginx_api_proxy_matches_compose_implied_host_port(self) -> None:
        """Nginx proxies to host:8000, which is where `python api.py` runs."""
        nginx = os.path.join(BASE_DIR, "web_ui", "nginx.conf")
        with open(nginx, encoding="utf-8") as f:
            nginx_text = f.read()
        assert "host.docker.internal:8000" in nginx_text

    def test_nginx_otlp_proxy_matches_collector_port(self) -> None:
        """Nginx proxies /otlp/ to otel-collector:4319."""
        nginx = os.path.join(BASE_DIR, "web_ui", "nginx.conf")
        with open(nginx, encoding="utf-8") as f:
            nginx_text = f.read()
        assert "otel-collector:4319" in nginx_text

    def test_collector_exports_to_aspire_grpc_port(self) -> None:
        """Collector sends gRPC to aspire-dashboard:18889."""
        config_text = _read_otel_collector_config()
        assert "aspire-dashboard:18889" in config_text
