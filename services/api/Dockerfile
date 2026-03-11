FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (unixodbc + PostgreSQL ODBC driver for virtualization ODBC sources)
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    unixodbc \
    unixodbc-dev \
    odbc-postgresql \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt requirements-dev.txt ./

# Install Python dependencies (production + development for testing)
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-dev.txt

# Copy application code
COPY . .

# Install CLI and SDK packages for comprehensive testing
RUN cd /app/cli && pip install --no-cache-dir -e . && \
    cd /app/sdk/python && pip install --no-cache-dir -e .

# Expose port
EXPOSE 8000

# Default command (can be overridden in docker-compose)
CMD ["python", "hub/manage.py", "runserver", "0.0.0.0:8000"]

