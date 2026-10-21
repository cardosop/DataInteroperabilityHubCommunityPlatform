# Developer Onboarding

Welcome to the Data Interoperability Hub team. This guide covers setting up your local development environment.

## Prerequisites
- Python 3.12+
- Node.js 20+
- Docker and Docker Compose
- PostgreSQL 16
- Redis 7

## Setup (docker-only)
1. Clone the repository
2. `make quickstart` — core-only stack: generates `.env` (random
   per-developer secrets) and boots postgres + redis + minio + api +
   worker + frontend + traefik
3. Full stack (paid layer): `make dev-env` (generates `.env.dev` from the
   template with every placeholder replaced) then
   `docker compose up -d --build`
4. `make migrate` applies database migrations (the dev api runs them
   on boot); `make run` starts the development server

The legacy bare-metal `setup.sh` / `make setup` flow was removed in
W9.2 — bootstrap is docker-only.

## Project structure
See `CLAUDE.md` for architecture overview and `docs/DEVELOPMENT_GUIDE.md` for detailed development practices.
