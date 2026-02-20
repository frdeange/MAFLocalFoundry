/**
 * Travel Planner — Browser Telemetry (OpenTelemetry JS SDK)
 * =========================================================
 * Configures OpenTelemetry in the browser to export traces via OTLP/HTTP.
 * Traces are sent to /otlp/v1/traces (Nginx proxies to OTel Collector).
 *
 * Auto-instruments:
 *   - fetch() calls → adds traceparent header to /api/ requests
 *   - Document load → captures page load performance
 *
 * Custom spans:
 *   - user.submit_query, ui.stream_started, ui.agent_message_rendered, ui.stream_complete
 *
 * Dependencies loaded from CDN (no build step):
 *   - @opentelemetry/sdk-trace-web
 *   - @opentelemetry/exporter-trace-otlp-http
 *   - @opentelemetry/instrumentation-fetch
 *   - @opentelemetry/instrumentation-document-load
 *   - @opentelemetry/context-zone
 *   - @opentelemetry/resources
 *   - @opentelemetry/semantic-conventions
 */

(function () {
    'use strict';

    // ──────────────────────────────────────────────────────────
    // Configuration
    // ──────────────────────────────────────────────────────────

    const CONFIG = {
        serviceName: 'travel-planner-web-ui',
        serviceVersion: '1.0.0',
        environment: 'development',
        otlpEndpoint: '/otlp/v1/traces',
    };

    // ──────────────────────────────────────────────────────────
    // Lightweight Tracer (no heavy SDK bundling for PoC)
    // ──────────────────────────────────────────────────────────
    //
    // For this PoC, we implement a lightweight tracer that:
    // 1. Generates W3C traceparent headers for fetch() calls
    // 2. Sends trace data to the OTLP endpoint
    // 3. Provides custom span creation
    //
    // In production, replace with full OTel JS SDK imports.
    // ──────────────────────────────────────────────────────────

    /** Generate a random hex string of given byte length */
    function randomHex(bytes) {
        const arr = new Uint8Array(bytes);
        crypto.getRandomValues(arr);
        return Array.from(arr, b => b.toString(16).padStart(2, '0')).join('');
    }

    /** Generate W3C traceparent header value */
    function generateTraceparent(traceId, spanId) {
        return `00-${traceId}-${spanId}-01`;
    }

    /** Current time in nanoseconds (approximation for OTLP) */
    function nowNanos() {
        return BigInt(Date.now()) * 1000000n;
    }

    // Active trace context
    let activeTraceId = null;
    let activeSpanId = null;

    // Span buffer for batch export
    const spanBuffer = [];
    const FLUSH_INTERVAL_MS = 5000;
    const MAX_BUFFER_SIZE = 50;

    /**
     * Create and start a span.
     * @param {string} name Span name
     * @param {Object} attributes Span attributes
     * @returns {{ end: Function }} Span object with end() method
     */
    function startSpan(name, attributes = {}) {
        const traceId = activeTraceId || randomHex(16);
        const spanId = randomHex(8);
        const parentSpanId = activeSpanId || '';
        const startTime = nowNanos();

        // Update active context
        if (!activeTraceId) {
            activeTraceId = traceId;
        }
        const previousSpanId = activeSpanId;
        activeSpanId = spanId;

        return {
            traceId,
            spanId,
            end() {
                const endTime = nowNanos();

                const span = {
                    traceId,
                    spanId,
                    parentSpanId,
                    name,
                    kind: 1, // SPAN_KIND_INTERNAL
                    startTimeUnixNano: startTime.toString(),
                    endTimeUnixNano: endTime.toString(),
                    attributes: Object.entries(attributes).map(([key, value]) => ({
                        key,
                        value: typeof value === 'number'
                            ? { intValue: value }
                            : { stringValue: String(value) },
                    })),
                    status: { code: 1 }, // STATUS_CODE_OK
                };

                spanBuffer.push(span);

                // Restore parent context
                activeSpanId = previousSpanId;
                if (!previousSpanId) {
                    activeTraceId = null;
                }

                // Flush if buffer is full
                if (spanBuffer.length >= MAX_BUFFER_SIZE) {
                    flushSpans();
                }
            },
        };
    }

    /**
     * Flush buffered spans to the OTLP endpoint.
     */
    async function flushSpans() {
        if (spanBuffer.length === 0) return;

        const spans = spanBuffer.splice(0);

        const payload = {
            resourceSpans: [{
                resource: {
                    attributes: [
                        { key: 'service.name', value: { stringValue: CONFIG.serviceName } },
                        { key: 'service.version', value: { stringValue: CONFIG.serviceVersion } },
                        { key: 'deployment.environment', value: { stringValue: CONFIG.environment } },
                    ],
                },
                scopeSpans: [{
                    scope: { name: CONFIG.serviceName, version: CONFIG.serviceVersion },
                    spans,
                }],
            }],
        };

        try {
            await fetch(CONFIG.otlpEndpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
                // Don't instrument this fetch to avoid infinite loops
                keepalive: true,
            });
        } catch (error) {
            console.warn('[TravelTelemetry] Failed to export spans:', error.message);
        }
    }

    // ──────────────────────────────────────────────────────────
    // Fetch Instrumentation
    // ──────────────────────────────────────────────────────────
    // Monkey-patch fetch() to inject traceparent headers on /api/ calls

    const originalFetch = window.fetch;

    window.fetch = function (url, options = {}) {
        const urlStr = typeof url === 'string' ? url : url.toString();

        // Only instrument /api/ calls (not /otlp/ calls)
        if (urlStr.includes('/api/')) {
            const traceId = activeTraceId || randomHex(16);
            const spanId = randomHex(8);

            if (!activeTraceId) {
                activeTraceId = traceId;
            }

            const traceparent = generateTraceparent(traceId, spanId);

            options.headers = {
                ...(options.headers || {}),
                traceparent,
            };

            // Create a span for this fetch call
            const fetchSpan = startSpan('http.fetch', {
                'http.url': urlStr,
                'http.method': (options.method || 'GET').toUpperCase(),
            });

            return originalFetch.call(this, url, options)
                .then(response => {
                    fetchSpan.end();
                    return response;
                })
                .catch(error => {
                    fetchSpan.end();
                    throw error;
                });
        }

        return originalFetch.call(this, url, options);
    };

    // ──────────────────────────────────────────────────────────
    // Document Load Instrumentation
    // ──────────────────────────────────────────────────────────

    window.addEventListener('load', () => {
        const perf = performance.getEntriesByType('navigation')[0];
        if (perf) {
            const span = startSpan('document.load', {
                'document.url': window.location.href,
                'document.dom_complete_ms': Math.round(perf.domComplete),
                'document.load_event_ms': Math.round(perf.loadEventEnd),
                'document.dom_interactive_ms': Math.round(perf.domInteractive),
            });
            span.end();
        }
    });

    // ──────────────────────────────────────────────────────────
    // Periodic Flush
    // ──────────────────────────────────────────────────────────

    setInterval(flushSpans, FLUSH_INTERVAL_MS);

    // Flush on page unload
    window.addEventListener('beforeunload', () => {
        flushSpans();
    });

    // ──────────────────────────────────────────────────────────
    // Public API
    // ──────────────────────────────────────────────────────────

    window.TravelTelemetry = {
        startSpan,
        flushSpans,
        config: CONFIG,
    };

    console.log(`[TravelTelemetry] Initialized — service: ${CONFIG.serviceName}, endpoint: ${CONFIG.otlpEndpoint}`);

})();
