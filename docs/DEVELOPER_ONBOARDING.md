# Developer Onboarding

Welcome to the Data Interoperability Hub team. This guide covers setting up your local development environment.

## Prerequisites
- Python 3.12+
- Node.js 20+
- Docker and Docker Compose
- PostgreSQL 16
- Redis 7

## Setup
1. Clone the repository
2. Copy `.env.example` to `.env.dev` and adjust values
3. Run `make setup` to install Python and Node dependencies
4. Run `docker compose up -d` for infrastructure services
5. Run `make migrate` to apply database migrations
6. Run `make run` to start the development server

## Project structure
See `CLAUDE.md` for architecture overview and `docs/DEVELOPMENT_GUIDE.md` for detailed development practices.
