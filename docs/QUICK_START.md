# Quick Start Guide

Get the Data Interoperability Hub up and running in minutes.

## Prerequisites

- **Docker** 20.10+ and **Docker Compose** 2.0+
- **Python** 3.12+ (for local development)
- **Git**

## Quick Start (Docker Compose)

### 1. Clone the Repository

```bash
git clone <repository-url>
cd DataInteroperabilityHub
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env.dev

# Edit .env.dev with your settings (optional for development)
```

### 3. Start Services

```bash
# Start all services
docker compose up -d

# Or start only infrastructure services
docker compose up -d postgres redis minio fuseki
```

### 4. Run Migrations

```bash
# Run database migrations
docker compose exec api-service python manage.py migrate

# Create superuser (optional)
docker compose exec api-service python manage.py createsuperuser
```

### 5. Access the Platform

- **API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/api-docs/
- **GraphQL**: http://localhost:8000/graphql
- **Health Check**: http://localhost:8000/health
- **MinIO Console**: http://localhost:9001 (minio/minio123)
- **Grafana**: http://localhost:3000 (admin/admin)
- **Jaeger**: http://localhost:16686
- **Prefect UI**: http://localhost:4201

## Verify Installation

```bash
# Check service health
curl http://localhost:8000/health

# Check API info
curl http://localhost:8000/api/v1/
```

## Create Your First Contract

```bash
# Get authentication token
TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-password"}' \
  | jq -r '.token')

# Create a contract
curl -X POST http://localhost:8000/api/v1/contracts/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My First Contract",
    "spec": {
      "type": "table",
      "data": {
        "s3": {
          "path": "s3://bucket/path/to/data"
        }
      },
      "schema": {
        "fields": [
          {"name": "id", "type": "string"},
          {"name": "value", "type": "number"}
        ]
      }
    }
  }'
```

## Local Development Setup

### 1. Create Virtual Environment

```bash
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 3. Start Infrastructure

```bash
docker compose up -d postgres redis minio fuseki
```

### 4. Configure Django

```bash
# Set environment variables
export DATABASE_URL=postgresql://hub:hub@localhost:5432/hub
export REDIS_URL=redis://localhost:6379/0
export MINIO_ENDPOINT=localhost:9000
export MINIO_ACCESS_KEY=minio
export MINIO_SECRET_KEY=minio123

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

### 5. Run Development Server

```bash
# Run API server
python manage.py runserver

# In another terminal, run worker
python services/worker/main.py job_critical job_default job_low

# In another terminal, run workflow engine
python services/workflow-engine/main.py
```

## Common Commands

```bash
# View logs
docker compose logs -f api-service

# Stop services
docker compose down

# Stop and remove volumes
docker compose down -v

# Restart a service
docker compose restart api-service

# Run tests
docker compose exec api-service python manage.py test

# Access Django shell
docker compose exec api-service python manage.py shell
```

## Next Steps

- Read the [Developer Onboarding Guide](DEVELOPER_ONBOARDING.md)
- Explore the [API Documentation](API_REFERENCE.md)
- Review the [Architecture Documentation](ARCHITECTURE.md)
- Check out the [Testing Guide](TESTING_GUIDE.md)

## Troubleshooting

### Services Won't Start

```bash
# Check service status
docker compose ps

# Check logs
docker compose logs <service-name>

# Check port conflicts
netstat -tulpn | grep -E '8000|5432|6379|9000'
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker compose ps postgres

# Check connection
docker compose exec postgres psql -U hub -d hub -c "SELECT 1;"
```

### Permission Issues

```bash
# Fix file permissions
sudo chown -R $USER:$USER .

# Fix Docker permissions (Linux)
sudo usermod -aG docker $USER
```

## Getting Help

- Check the [Troubleshooting Guide](TROUBLESHOOTING.md)
- Review [API Error Codes](API_ERROR_CODES.md)
- Consult the [Developer Onboarding Guide](DEVELOPER_ONBOARDING.md)

