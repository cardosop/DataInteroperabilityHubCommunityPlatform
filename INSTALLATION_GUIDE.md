# Installation Guide

This guide walks you through installing all external dependencies and setting up the Django project.

## Prerequisites

- Python 3.11+ installed
- Docker and Docker Compose installed
- sudo access (for installing system packages)

## Step 1: Install System Dependencies

```bash
# Install Python venv package
sudo apt install -y python3.12-venv python3-full

# Verify installation
python3 --version  # Should show 3.12.x
```

## Step 2: Create Virtual Environment

```bash
cd /home/ph/Desktop/DataInteroperabilityHub

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Verify activation (prompt should show (venv))
which python  # Should point to venv/bin/python
```

## Step 3: Install Python Dependencies

```bash
# Make sure venv is activated
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install production dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt

# Install external DQ/compliance libraries
pip install great-expectations soda-core
```

## Step 4: Verify External Dependencies

```bash
# Verify Great Expectations
python -c "import great_expectations as gx; print(f'Great Expectations {gx.__version__}')"

# Verify Soda
python -c "import soda; print('Soda installed successfully')"

# Verify Django
python -c "import django; print(f'Django {django.__version__}')"
```

## Step 5: Install DataContract CLI

### Option 1: Docker (Recommended for MVP)

The DataContract CLI will be wrapped in a Docker container service. No local installation needed.

### Option 2: npm (if you want to test locally)

```bash
# Install Node.js 22.x if not already installed
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install DataContract CLI
npm install -g @datacontract/cli

# Verify installation
datacontract --version
```

### Option 3: Python Package

```bash
source venv/bin/activate
pip install datacontract

# Verify installation
datacontract --version
```

## Step 6: Start Infrastructure Services

```bash
# Start all services (PostgreSQL, Redis, MinIO, Fuseki)
make docker-up

# Or manually
docker-compose up -d postgres redis minio fuseki

# Check status
make docker-ps

# View logs if needed
make docker-logs
```

## Step 7: Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env.dev

# Edit .env.dev with your configuration
# Most defaults should work for local development
```

## Step 8: Initialize Django Project

The Django project structure has been created. Now initialize the database:

```bash
# Make sure venv is activated
source venv/bin/activate

# Run migrations
python hub/manage.py migrate

# Create superuser
python hub/manage.py createsuperuser
```

## Step 9: Create MinIO Bucket

```bash
# Access MinIO console at http://localhost:9001
# Login: minio / minio123
# Create bucket: hub-files

# Or use Python script
python << EOF
import boto3
s3 = boto3.client(
    's3',
    endpoint_url='http://localhost:9000',
    aws_access_key_id='minio',
    aws_secret_access_key='minio123'
)
s3.create_bucket(Bucket='hub-files')
print("Bucket created successfully")
EOF
```

## Step 10: Verify Installation

```bash
# Run verification script
make verify-deps

# Or manually check:
# - PostgreSQL: docker ps | grep postgres
# - Redis: docker ps | grep redis
# - MinIO: docker ps | grep minio
# - Fuseki: docker ps | grep fuseki
# - Python packages: pip list | grep -E "django|great-expectations|soda"
```

## Step 11: Run Development Server

```bash
# Make sure venv is activated
source venv/bin/activate

# Run Django development server
python hub/manage.py runserver

# Or use make command
make runserver
```

The API should be available at http://localhost:8000

## Troubleshooting

### Virtual Environment Issues

```bash
# If venv creation fails
sudo apt install -y python3.12-venv python3-full
python3 -m venv venv --clear
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker ps | grep postgres

# Check connection
docker exec -it hub-postgres psql -U hub -d hub -c "SELECT version();"
```

### Redis Connection Issues

```bash
# Check Redis is running
docker ps | grep redis

# Test connection
docker exec -it hub-redis redis-cli ping
```

### MinIO Connection Issues

```bash
# Check MinIO is running
docker ps | grep minio

# Access console at http://localhost:9001
# Login: minio / minio123
```

### Import Errors

```bash
# Make sure venv is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
pip install great-expectations soda-core
```

## Next Steps

After successful installation:

1. ✅ All dependencies installed
2. ✅ Infrastructure services running
3. ✅ Django project configured
4. ✅ Database initialized

You're ready to start **Phase 0: Critical Path Prototypes**!

See `openspec/changes/implement-mvp-foundation/tasks.md` for implementation tasks.

