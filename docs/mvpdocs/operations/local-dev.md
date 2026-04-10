# Local Development Setup

This page orients you to existing developer setup documentation.

## Quick Reference

**Primary guide:** [DEVELOPER_GUIDE.md](../../DEVELOPER_GUIDE.md)

### Prerequisites

- Python 3.12+
- Node.js 20+ (for the frontend SPA)
- Docker and Docker Compose (for backing services)
- PostgreSQL 16 client libraries
- Redis 7+

### Setup Overview

1. Clone the repository and create a Python virtual environment.
2. Install backend dependencies with `pip install -r requirements.txt`.
3. Install frontend dependencies with `npm install` inside `frontend/`.
4. Copy `.env.example` to `.env` and fill in local values.
5. Run `docker compose up -d` for PostgreSQL, Redis, and MinIO.
6. Apply migrations with `python manage.py migrate`.
7. Start the backend with `python manage.py runserver`.
8. Start the frontend with `npm run dev` inside `frontend/`.

See the full guide for IDE configuration, service debugging, and testing
setup.

### Common Issues

- **Missing `libpq`**: Install `libpq-dev` (Debian/Ubuntu) or
  `postgresql-devel` (Fedora/RHEL) before installing `psycopg`.
- **Port conflicts**: The default ports are 8000 (API), 3000 (SPA),
  5432 (PostgreSQL), 6379 (Redis), and 9000 (MinIO). Adjust in `.env`
  if they conflict with existing services.
- **Node version mismatch**: Use `nvm use 20` to switch to the correct
  Node.js version.

## Related

- [Configuration Reference](configuration-reference.md) -- env vars for local dev
- [DEVELOPER_GUIDE.md](../../DEVELOPER_GUIDE.md) -- full developer reference
