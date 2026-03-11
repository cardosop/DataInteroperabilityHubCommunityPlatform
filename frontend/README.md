# Frontend Application

React + TypeScript + Vite frontend for the Data Interoperability Hub platform (Meshant brand by default).

## Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Type check
npm run typecheck

# Lint
npm run lint

# Format code
npm run format

# Run tests
npm test

# Coverage (see docs/TEST_EXECUTION_PLAN.md for improvement plan)
npm run test:coverage

# E2E tests (Playwright, real backend)
# See e2e/README.md for setup. For visible browser and slow motion:
npm run test:e2e:visible   # uses E2E_VISIBLE=1 and --project=visible
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

- `VITE_APP_NAME`: Product brand name (default: Meshant). Used in header, login, landing page.
- `VITE_API_BASE_URL`: Backend API base URL (default: http://localhost:8000/api/v1). When using Traefik as entrypoint, set to the Traefik API base (e.g. https://api.hub.local/api/v1). See `docs/API_GATEWAY_TRAEFIK.md`.
- `VITE_WS_BASE_URL`: WebSocket base URL (default: ws://localhost:8000)
- `VITE_USE_TRAEFIK_ENTRYPOINT`: Set to `true` when the app and API are reached via Traefik (single entrypoint). When true, `VITE_API_BASE_URL` must point at the Traefik API base. Default: unset/false.
- `VITE_ENV`: Environment (development/production)

## Docker

```bash
# Build
docker build -t hub-frontend ./frontend

# Run with docker-compose
docker compose up frontend
```

## Project Structure

- `src/features/`: Feature modules (auth, shell, capabilities)
- `src/shared/`: Shared utilities, components, services
- `src/app/`: App-level configuration (routes, providers)

## Conventions

See `FRONTEND_CONVENTIONS.md` for detailed conventions.
