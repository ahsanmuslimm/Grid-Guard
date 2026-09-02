# GridGuard — Production Dockerfile
# Python 3.11-slim + Node.js 20 (for Arize Phoenix MCP server)
# Deployed to Google Cloud Run — min-instances=1 prevents cold starts

FROM python:3.11-slim

WORKDIR /app

# Install Node.js 20.x for Phoenix MCP (npx) + curl for health checks
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    node --version && npm --version

# Install Python deps separately for layer caching
# requirements-docker.txt contains the Phoenix Cloud client/exporter only.
COPY requirements-docker.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-docker.txt

# Copy source (after deps to maximise cache hits)
COPY . .

# Remove dev/test artifacts that shouldn't ship
RUN rm -rf venv/ .env credentials/ .pytest_cache/ __pycache__/ \
    && find . -name "*.pyc" -delete \
    && find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Cloud Run injects PORT — default 8080
ENV PORT=8080
ENV GRIDGUARD_ENV=production
ENV LOG_LEVEL=INFO
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080

# Health check — Cloud Run waits for this before routing traffic
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -f "http://localhost:${PORT:-8080}/health" || exit 1

# Single uvicorn worker — required for in-process WebSocket state
CMD ["python", "main.py"]
