# Multi-stage Dockerfile for bot_mt5
# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY bot_mt5/ ./bot_mt5/
COPY tests/ ./tests/

# Create directories for models and logs
RUN mkdir -p /app/models /app/logs

# Environment variables (can be overridden)
ENV PYTHONUNBUFFERED=1 \
    LOG_LEVEL=INFO \
    LOG_FORMAT=json \
    AI_POOL_SIZE=2 \
    AI_TIMEOUT_QUICK=8.0 \
    AI_TIMEOUT_DEEP=30.0 \
    MT5_HOST=0.0.0.0 \
    MT5_PORT=8765 \
    RATE_LIMIT_ENABLED=true \
    RATE_LIMIT_OPM=60 \
    USE_UVLOOP=true

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8765/health || exit 1

# Run as non-root user
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

# Expose port
EXPOSE 8765

# Default command (can be overridden in docker-compose)
CMD ["python3", "-m", "bot_mt5.main"]
