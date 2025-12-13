FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt requirements-dev.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose health check port
EXPOSE 8088

# Default command: process workflows continuously
# Uses services/workflow-engine/main.py which includes health check HTTP server
# Health check endpoints available at http://localhost:8088/healthz and /ready
# Can be overridden in docker-compose to customize poll interval and batch size
CMD ["python", "services/workflow-engine/main.py", "--poll-interval", "5", "--batch-size", "10"]

