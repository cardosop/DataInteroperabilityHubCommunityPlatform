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
COPY services/event-bus/requirements.txt ./services/event-bus/

# Install Python dependencies
# First install main project requirements (for Django)
RUN pip install --no-cache-dir -r requirements.txt

# Then install service-specific requirements
RUN pip install --no-cache-dir -r services/event-bus/requirements.txt

# Copy application code
COPY . .

# Expose service port
EXPOSE 8090

# Default command: run FastAPI health service
# Uses uvicorn to serve the FastAPI application
CMD ["uvicorn", "services.event-bus.health:app", "--host", "0.0.0.0", "--port", "8090"]

