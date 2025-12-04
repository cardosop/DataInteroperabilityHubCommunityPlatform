FROM python:3.11-slim

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

# Default command: process all priority queues (job_critical, job_default, job_low)
# Uses services/worker/main.py which includes health check HTTP server
# Can be overridden in docker-compose to process specific queues
# Priority order: job_critical (HIGH) → job_default (NORMAL) → job_low (LOW)
# Health check endpoints available at http://localhost:8080/healthz and /ready
CMD ["python", "services/worker/main.py", "job_critical", "job_default", "job_low"]

