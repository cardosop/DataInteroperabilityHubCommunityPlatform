# Quick Start Guide

Get up and running in 5 minutes!

## Prerequisites Check

```bash
# Check Python version (need 3.11+)
python3 --version

# Check Docker
docker --version
docker-compose --version
```

## Installation Steps

### 1. Install System Package (One-time)

```bash
sudo apt install -y python3.12-venv python3-full
```

### 2. Create Virtual Environment

```bash
cd /home/ph/Desktop/DataInteroperabilityHub
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install great-expectations soda-core
```

### 4. Start Infrastructure

```bash
make docker-up
# Wait 10-15 seconds for services to start
```

### 5. Initialize Django

```bash
# Run migrations
python hub/manage.py migrate

# Create superuser (optional)
python hub/manage.py createsuperuser
```

### 6. Create MinIO Bucket

```bash
# Access http://localhost:9001
# Login: minio / minio123
# Create bucket: hub-files
```

### 7. Start Development Server

```bash
python hub/manage.py runserver
```

## Verify Everything Works

```bash
# Check health endpoint
curl http://localhost:8000/health/

# Should return:
# {"status":"healthy","database":"connected","redis":"connected"}
```

## Common Commands

```bash
# Activate virtual environment (always do this first)
source venv/bin/activate

# Start services
make docker-up

# Stop services
make docker-down

# Run tests
make test

# Run migrations
make migrate

# View logs
make docker-logs
```

## Troubleshooting

**Can't create venv?**
```bash
sudo apt install -y python3.12-venv python3-full
```

**Database connection error?**
```bash
# Check PostgreSQL is running
docker ps | grep postgres
# Restart if needed
docker-compose restart postgres
```

**Import errors?**
```bash
# Make sure venv is activated
source venv/bin/activate
# Reinstall
pip install -r requirements.txt
```

## Next: Start Building!

Once everything is running, you can begin:
- **Phase 0**: Critical Path Prototypes
- See `openspec/changes/implement-mvp-foundation/tasks.md`

