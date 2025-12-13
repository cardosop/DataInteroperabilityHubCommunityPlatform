# Multi-stage Dockerfile for Search Service
# This service provides full-text search capabilities

# Stage 1: Build stage
FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY services/search-service/requirements.txt .
COPY requirements.txt ./requirements-root.txt

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime stage
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Add local bin to PATH for user-installed packages
ENV PATH=/root/.local/bin:$PATH

# Copy shared module
COPY services/shared/ ./shared/

# Copy application code
COPY services/search-service/ .

# Make sure scripts are executable
RUN chmod +x services/search-service/*.py || true

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Expose port
EXPOSE 8085

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8085/health || exit 1

# Run the service
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8085"]

