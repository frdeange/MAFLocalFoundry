"""
Web UI Tests
=============
Structural and compliance tests for the web UI files (web_ui/).
Validates HTML structure, JavaScript patterns, CSS existence,
Nginx configuration, and Dockerfile correctness.
"""

import os

import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_UI_DIR = os.path.join(BASE_DIR, "web_ui")


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _read_file(filename: str) -> str:
    """Read a file from web_ui/ directory."""
    path = os.path.join(WEB_UI_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return f.read()


def _read_index() -> str:
    return _read_file("index.html")


def _read_app_js() -> str:
    return _read_file("app.js")


def _read_telemetry_js() -> str:
    return _read_file("telemetry.js")


def _read_nginx_conf() -> str:
    return _read_file("nginx.conf")


def _read_dockerfile() -> str:
    return _read_file("Dockerfile")


def _read_style_css() -> str:
    return _read_file("style.css")


# ──────────────────────────────────────────────────────────────
# File Existence
# ──────────────────────────────────────────────────────────────

class TestWebUIFileStructure:
    """Verify all required web UI files exist."""

    @pytest.mark.parametrize("filename", [
        "index.html",
        "app.js",
        "telemetry.js",
        "style.css",
        "nginx.conf",
        "Dockerfile",
    ])
    def test_file_exists(self, filename: str) -> None:
        path = os.path.join(WEB_UI_DIR, filename)
        assert os.path.isfile(path), f"web_ui/{filename} must exist"


# ──────────────────────────────────────────────────────────────
# HTML Structure (index.html)
# ──────────────────────────────────────────────────────────────

class TestIndexHtml:
    """Verify HTML structure and required elements."""

    def test_has_doctype(self) -> None:
        html = _read_index()
        assert "<!DOCTYPE html>" in html

    def test_has_lang_attribute(self) -> None:
        html = _read_index()
        assert 'lang="en"' in html

    def test_includes_style_css(self) -> None:
        html = _read_index()
        assert 'href="style.css"' in html

    def test_includes_telemetry_js(self) -> None:
        html = _read_index()
        assert 'src="telemetry.js"' in html

    def test_includes_app_js(self) -> None:
        html = _read_index()
        assert 'src="app.js"' in html

    def test_telemetry_loads_before_app(self) -> None:
        """telemetry.js must load before app.js for TravelTelemetry to be available."""
        html = _read_index()
        telemetry_pos = html.find('src="telemetry.js"')
        app_pos = html.find('src="app.js"')
        assert telemetry_pos != -1, "telemetry.js script tag must exist"
        assert app_pos != -1, "app.js script tag must exist"
        assert telemetry_pos < app_pos, "telemetry.js must load BEFORE app.js"

    def test_has_query_form(self) -> None:
        html = _read_index()
        assert 'id="query-form"' in html

    def test_has_query_input(self) -> None:
        html = _read_index()
        assert 'id="query-input"' in html

    def test_has_messages_container(self) -> None:
        html = _read_index()
        assert 'id="messages"' in html

    def test_has_agent_progress(self) -> None:
        html = _read_index()
        assert 'id="agent-progress"' in html

    def test_has_history_list(self) -> None:
        html = _read_index()
        assert 'id="history-list"' in html

    def test_has_submit_button(self) -> None:
        html = _read_index()
        assert 'id="submit-btn"' in html

    def test_has_sidebar(self) -> None:
        html = _read_index()
        assert 'id="sidebar"' in html

    def test_has_connection_status(self) -> None:
        html = _read_index()
        assert 'id="connection-status"' in html

    def test_has_welcome_message(self) -> None:
        html = _read_index()
        assert "Welcome" in html

    def test_lists_all_three_agents(self) -> None:
        html = _read_index()
        assert "Researcher" in html
        assert "WeatherAnalyst" in html
        assert "Planner" in html


# ──────────────────────────────────────────────────────────────
# Application Logic (app.js)
# ──────────────────────────────────────────────────────────────

class TestAppJs:
    """Verify app.js implements required functionality."""

    def test_defines_api_base(self) -> None:
        js = _read_app_js()
        assert "API_BASE" in js

    def test_defines_history_key(self) -> None:
        js = _read_app_js()
        assert "HISTORY_KEY" in js

    def test_defines_max_history(self) -> None:
        js = _read_app_js()
        assert "MAX_HISTORY" in js

    def test_defines_agent_config(self) -> None:
        js = _read_app_js()
        assert "AGENT_CONFIG" in js

    @pytest.mark.parametrize("agent", ["Researcher", "WeatherAnalyst", "Planner"])
    def test_agent_config_has_all_agents(self, agent: str) -> None:
        js = _read_app_js()
        assert agent in js

    def test_uses_post_method_for_api(self) -> None:
        """SSE via POST-based fetch (not EventSource which only supports GET)."""
        js = _read_app_js()
        assert "method: 'POST'" in js

    def test_sends_json_content_type(self) -> None:
        js = _read_app_js()
        assert "'Content-Type': 'application/json'" in js

    def test_uses_readable_stream(self) -> None:
        js = _read_app_js()
        assert "getReader()" in js

    def test_parses_sse_events(self) -> None:
        js = _read_app_js()
        assert "event:" in js
        assert "data:" in js

    @pytest.mark.parametrize("event_type", [
        "agent_started",
        "agent_completed",
        "message",
        "output",
        "error",
        "done",
        "status",
    ])
    def test_handles_sse_event_type(self, event_type: str) -> None:
        js = _read_app_js()
        assert f"'{event_type}'" in js or f'"{event_type}"' in js, (
            f"app.js must handle SSE event type '{event_type}'"
        )

    def test_uses_localstorage_for_history(self) -> None:
        js = _read_app_js()
        assert "localStorage" in js

    def test_has_save_to_history(self) -> None:
        js = _read_app_js()
        assert "saveToHistory" in js

    def test_has_load_history(self) -> None:
        js = _read_app_js()
        assert "loadHistory" in js

    def test_has_escape_html(self) -> None:
        js = _read_app_js()
        assert "escapeHtml" in js

    def test_has_handle_submit(self) -> None:
        js = _read_app_js()
        assert "handleSubmit" in js

    def test_has_stream_workflow(self) -> None:
        js = _read_app_js()
        assert "streamWorkflow" in js

    def test_has_handle_sse_event(self) -> None:
        js = _read_app_js()
        assert "handleSSEEvent" in js

    def test_integrates_travel_telemetry(self) -> None:
        """app.js must use TravelTelemetry for custom spans."""
        js = _read_app_js()
        assert "TravelTelemetry" in js

    def test_creates_user_submit_span(self) -> None:
        js = _read_app_js()
        assert "user.submit_query" in js

    def test_creates_stream_started_span(self) -> None:
        js = _read_app_js()
        assert "ui.stream_started" in js

    def test_creates_stream_complete_span(self) -> None:
        js = _read_app_js()
        assert "ui.stream_complete" in js

    def test_tracks_completed_agents(self) -> None:
        """app.js must track completedAgents for step progress display."""
        js = _read_app_js()
        assert "completedAgents" in js

    def test_shows_step_progress(self) -> None:
        """showProgress must display step numbers (e.g., step 1/3)."""
        js = _read_app_js()
        assert "step" in js and "total" in js, (
            "showProgress must accept step/total for numbered progress"
        )


# ──────────────────────────────────────────────────────────────
# Browser Telemetry (telemetry.js)
# ──────────────────────────────────────────────────────────────

class TestTelemetryJs:
    """Verify browser telemetry instrumentation."""

    def test_defines_service_name(self) -> None:
        js = _read_telemetry_js()
        assert "travel-planner-web-ui" in js

    def test_defines_otlp_endpoint(self) -> None:
        js = _read_telemetry_js()
        assert "/otlp/v1/traces" in js

    def test_generates_traceparent(self) -> None:
        js = _read_telemetry_js()
        assert "traceparent" in js

    def test_monkey_patches_fetch(self) -> None:
        """Fetch must be instrumented to inject traceparent on /api/ calls."""
        js = _read_telemetry_js()
        assert "window.fetch" in js
        assert "originalFetch" in js

    def test_only_instruments_api_calls(self) -> None:
        """Only /api/ calls should be instrumented (not /otlp/)."""
        js = _read_telemetry_js()
        assert "/api/" in js

    def test_exports_travel_telemetry_global(self) -> None:
        js = _read_telemetry_js()
        assert "TravelTelemetry" in js

    def test_has_start_span_function(self) -> None:
        js = _read_telemetry_js()
        assert "startSpan" in js

    def test_has_flush_spans_function(self) -> None:
        js = _read_telemetry_js()
        assert "flushSpans" in js

    def test_uses_otlp_json_format(self) -> None:
        """Spans must be exported using OTLP JSON (resourceSpans format)."""
        js = _read_telemetry_js()
        assert "resourceSpans" in js

    def test_includes_resource_attributes(self) -> None:
        js = _read_telemetry_js()
        assert "service.name" in js
        assert "service.version" in js

    def test_has_batch_buffer(self) -> None:
        js = _read_telemetry_js()
        assert "spanBuffer" in js

    def test_uses_w3c_trace_format(self) -> None:
        """W3C trace context format: 00-{traceId}-{spanId}-{flags}."""
        js = _read_telemetry_js()
        assert "00-" in js


# ──────────────────────────────────────────────────────────────
# Nginx Configuration
# ──────────────────────────────────────────────────────────────

class TestNginxConf:
    """Verify Nginx is configured for static files, API proxy, and OTLP proxy."""

    def test_listens_on_port_80(self) -> None:
        conf = _read_nginx_conf()
        assert "listen 80" in conf

    def test_serves_static_files(self) -> None:
        conf = _read_nginx_conf()
        assert "/usr/share/nginx/html" in conf

    def test_has_api_proxy(self) -> None:
        conf = _read_nginx_conf()
        assert "location /api/" in conf

    def test_api_proxy_target(self) -> None:
        conf = _read_nginx_conf()
        assert "host.docker.internal:8000" in conf

    def test_api_proxy_disables_buffering(self) -> None:
        """SSE requires proxy_buffering off."""
        conf = _read_nginx_conf()
        assert "proxy_buffering off" in conf

    def test_api_proxy_has_long_timeout(self) -> None:
        """SLM inference can be slow — need long timeouts."""
        conf = _read_nginx_conf()
        assert "proxy_read_timeout" in conf

    def test_has_otlp_proxy(self) -> None:
        conf = _read_nginx_conf()
        assert "location /otlp/" in conf

    def test_otlp_proxy_target(self) -> None:
        conf = _read_nginx_conf()
        assert "otel-collector:4319" in conf


# ──────────────────────────────────────────────────────────────
# Web UI Dockerfile
# ──────────────────────────────────────────────────────────────

class TestWebUIDockerfile:
    """Verify the web UI Dockerfile is correctly structured."""

    def test_uses_nginx_alpine(self) -> None:
        df = _read_dockerfile()
        assert "nginx:alpine" in df

    def test_copies_html(self) -> None:
        df = _read_dockerfile()
        assert "COPY index.html" in df

    def test_copies_app_js(self) -> None:
        df = _read_dockerfile()
        assert "COPY app.js" in df

    def test_copies_telemetry_js(self) -> None:
        df = _read_dockerfile()
        assert "COPY telemetry.js" in df

    def test_copies_style_css(self) -> None:
        df = _read_dockerfile()
        assert "COPY style.css" in df

    def test_copies_nginx_conf(self) -> None:
        df = _read_dockerfile()
        assert "COPY nginx.conf" in df

    def test_removes_default_nginx_content(self) -> None:
        df = _read_dockerfile()
        assert "rm -rf /usr/share/nginx/html" in df


# ──────────────────────────────────────────────────────────────
# Style Sheet
# ──────────────────────────────────────────────────────────────

class TestStyleCss:
    """Verify the CSS file has basic styling patterns."""

    def test_has_content(self) -> None:
        css = _read_style_css()
        assert len(css) > 100, "style.css should have substantial content"

    def test_has_dark_theme_variables(self) -> None:
        """The UI uses a dark theme with CSS custom properties."""
        css = _read_style_css()
        assert "--" in css, "CSS should use custom properties (variables)"

    def test_has_message_entrance_animation(self) -> None:
        """Messages should have an entrance animation for better UX."""
        css = _read_style_css()
        assert "@keyframes" in css, "CSS must define keyframe animations for messages"
        assert "agent-message" in css, "CSS must style agent messages"
