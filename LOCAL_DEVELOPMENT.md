# Local Development Setup

This guide explains how to run Django locally (outside Docker) while connecting to Docker services.

---

## Current Setup

Your Docker services are running with these names:
- `datamarketplace-postgres-1` (PostgreSQL on localhost:5432)
- `datamarketplace-redis-1` (Redis on localhost:6379)

These are exposed on `localhost`, so Django can connect to them when running locally.

---

## Configuration

### Database Connection

Django settings are configured to use:
- **Host**: `localhost` (when running Django locally)
- **Host**: `postgres` (when running Django inside Docker)

The default is `localhost` for local development.

### Environment Variables

Create a `.env.dev` file (or use the one provided) with:

```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=hub
POSTGRES_USER=hub
POSTGRES_PASSWORD=hub

# Redis
REDIS_URL=redis://localhost:6379/0
```

---

## Running Migrations

```bash
source venv/bin/activate
python hub/manage.py migrate
```

---

## Running Development Server

```bash
source venv/bin/activate
python hub/manage.py runserver
```

---

## Switching Between Local and Docker

### Running Django Locally (Current Setup)
- Use `POSTGRES_HOST=localhost` in `.env.dev`
- Use `REDIS_URL=redis://localhost:6379/0`
- Run: `python hub/manage.py migrate`

### Running Django in Docker
- Use `POSTGRES_HOST=postgres` in `.env.dev` (or docker-compose env)
- Use `REDIS_URL=redis://redis:6379/0`
- Run: `docker-compose exec api-service python manage.py migrate`

---

## Troubleshooting

### "could not translate host name 'postgres'"
- **Cause**: Django is trying to connect to Docker service name but running locally
- **Fix**: Set `POSTGRES_HOST=localhost` in `.env.dev`

### "Connection refused"
- **Cause**: PostgreSQL container not running
- **Fix**: Check with `docker ps | grep postgres`

### "Authentication failed"
- **Cause**: Wrong database credentials
- **Fix**: Check `.env.dev` matches your PostgreSQL container settings

---

## Quick Commands

```bash
# Check Docker services
docker ps | grep -E "postgres|redis"

# Check Django can connect
source venv/bin/activate
python hub/manage.py check --database default

# Run migrations
python hub/manage.py migrate

# Create superuser
python hub/manage.py createsuperuser

# Run server
python hub/manage.py runserver
```

