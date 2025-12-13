FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt ./
COPY services/workflow-registry/requirements.txt ./services/workflow-registry/

# Install Python dependencies
# First install main project requirements (for Django)
RUN pip install --no-cache-dir -r requirements.txt

# Then install service-specific requirements
RUN pip install --no-cache-dir -r services/workflow-registry/requirements.txt

# Copy application code
COPY . .

# Expose service port
EXPOSE 8089

# Default command: run FastAPI service
# Uses uvicorn to serve the FastAPI application
CMD ["uvicorn", "services.workflow-registry.main:app", "--host", "0.0.0.0", "--port", "8089"]

