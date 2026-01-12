# Dockerfile for API Gateway Service
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY services/api-gateway/requirements.txt ./api-gateway-requirements.txt
# Also install critical Django dependencies from main requirements.txt
# This ensures all Django apps can be imported
COPY requirements.txt ./main-requirements.txt
RUN pip install --no-cache-dir -r api-gateway-requirements.txt && \
    pip install --no-cache-dir \
        django-rq>=3.2.0 \
        rq>=1.15.0 \
        strawberry-graphql[django]>=0.287.0 \
        cryptography>=41.0.0 \
        PyJWT>=2.8.0 \
        boto3>=1.34.0 \
        django-storages>=1.14.6 \
        python-dateutil>=2.8.2 \
        pytz>=2023.3 \
        pyyaml>=6.0.1 \
        click>=8.0.0

# Copy shared module first
COPY services/shared/ ./shared/

# Copy Django hub directory (needed for ORM access)
COPY hub/ ./hub/

# Copy application code
COPY services/api-gateway/ .

# Expose port
EXPOSE 8088

# Run the service
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8088"]
