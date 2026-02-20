# ──────────────────────────────────────────────────────────────
# Dockerfile — Travel Planner Web UI
# ──────────────────────────────────────────────────────────────
# Lightweight Nginx container serving static files (HTML, JS, CSS)
# with reverse proxy to FastAPI backend and OTel Collector.
# ──────────────────────────────────────────────────────────────

FROM nginx:alpine

# Remove default Nginx content
RUN rm -rf /usr/share/nginx/html/*

# Copy static files
COPY index.html /usr/share/nginx/html/
COPY style.css /usr/share/nginx/html/
COPY app.js /usr/share/nginx/html/
COPY telemetry.js /usr/share/nginx/html/

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# Healthcheck
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD wget -q --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
