# Brand Name Change Runbook

**When to use:** Changing the product brand name (e.g. from "Meshant" to a custom name) across the platform — UI, emails, OpenAPI, SDKs, and documentation.

**Default brand:** Meshant (Phase 28.7.5)

---

## Overview

The brand name is controlled by a single source of truth per layer:

| Layer | Variable | Default | Where |
|-------|----------|---------|-------|
| **Frontend** | `VITE_APP_NAME` | Meshant | Build-time env (Vite bakes it in) |
| **Backend** | `APP_NAME` | Meshant | Runtime env (Django settings) |

---

## 1. Frontend (UI, document title)

### Local development

Set in `frontend/.env`:

```bash
VITE_APP_NAME=MyBrand
```

### Docker build

Pass as build arg. In `docker-compose.yml`, `docker-compose.dev.yml`, and `docker-compose.test.yml` (frontend / frontend-test):

```yaml
frontend:
  build:
    args:
      VITE_APP_NAME: ${APP_NAME:-Meshant}
```

Set `APP_NAME` when building:

```bash
APP_NAME=MyBrand docker compose build frontend
```

Or in `.env`:

```bash
APP_NAME=MyBrand
```

### Files that use the brand

- `frontend/src/shared/constants/brand.ts` — `APP_NAME = import.meta.env.VITE_APP_NAME ?? 'Meshant'`
- `frontend/index.html` — `<title>Meshant</title>` (fallback; App.tsx sets `document.title = APP_NAME` at runtime)
- Components: Header, LandingPage, LoginPage import `APP_NAME` from `brand.ts`

**No code changes needed** — only env vars.

---

## 2. Backend (emails, OpenAPI, webhooks)

### Environment variables

Set `APP_NAME` in your env file (`.env.dev`, `.env.staging`, `.env.production`). Copy from `.env.example` which includes `APP_NAME=Meshant`:

```bash
APP_NAME=MyBrand
```

### Docker Compose

`docker-compose.yml`, `docker-compose.dev.yml`, `docker-compose.staging.yml` already pass:

```yaml
environment:
  - APP_NAME=${APP_NAME:-Meshant}
```

Set `APP_NAME` in `.env` or export before `docker compose up`.

### Email from names

`SENDGRID_FROM_NAME`, `AWS_SES_FROM_NAME`, `SMTP_FROM_NAME` default to `APP_NAME`. Override if needed:

```bash
APP_NAME=MyBrand
SMTP_FROM_NAME=MyBrand Support  # optional override
```

### Where backend uses APP_NAME

- `hub/settings.py` — `APP_NAME`, FROM_NAME defaults
- `hub/apps/auth/views.py` — welcome email subject
- `hub/apps/notifications/tasks.py` — invitation email subject
- `hub/apps/notifications/templates.py` — injects `app_name` into email templates
- `hub/apps/api/views.py`, `openapi_enhancement.py` — OpenAPI title
- `hub/apps/baas/developer_portal.py` — API docs title/description
- `hub/apps/baas/sdk_generator.py` — SDK docstrings
- `hub/apps/webhooks/service.py` — User-Agent header
- `hub/apps/contracts/impact_notifications.py` — Slack footer

**No code changes needed** — only `APP_NAME` (and optional FROM_NAME overrides).

---

## 3. Design tokens (colors, typography)

Design tokens (Meshant palette, Inter font) are separate from the brand name.

- **Palette**: `frontend/src/index.css`, `frontend/src/shared/design-system/tokens.ts`
- **Typography**: Inter via Google Fonts in `frontend/index.html`

To change colors or fonts, see [DESIGN_SYSTEM.md](../UI/DESIGN_SYSTEM.md) and [MESHANT_DESIGN_SYSTEM_PLAN.md](../../openspec/changes/useronboardfix/MESHANT_DESIGN_SYSTEM_PLAN.md).

### Token extension

1. Add the token in `frontend/src/index.css` under `:root`
2. Add the same token in `frontend/src/shared/design-system/tokens.ts`
3. Run: `npm run test:run -- src/shared/design-system/`
4. Update `docs/UI/DESIGN_SYSTEM.md` token mapping table if needed

---

## 4. Verification checklist

After changing the brand name:

- [ ] **Frontend**: Rebuild (`npm run build` or `docker compose build frontend`). Check Header, LandingPage, LoginPage, document title.
- [ ] **Backend**: Restart API and worker. Check `/api/v1/baas/docs/` (title), welcome/invitation email subjects, webhook User-Agent.
- [ ] **E2E**: Update `frontend/e2e/fixtures/auth.ts` and `frontend/e2e/login-app-shell.spec.ts` if assertions use the brand name. Default E2E expects "Meshant".
- [ ] **Docs**: Update `docs/README.md`, `docs/DEVELOPER_ONBOARDING.md`, `frontend/README.md` if they mention the old name.

---

## 5. Quick reference

| Task | Command / Location |
|------|--------------------|
| Set brand for local frontend | `VITE_APP_NAME=MyBrand` in `frontend/.env` |
| Set brand for Docker | `APP_NAME=MyBrand` in `.env` or `export APP_NAME=MyBrand` |
| Rebuild frontend (Docker) | `APP_NAME=MyBrand docker compose build frontend` |
| Backend env | `APP_NAME=MyBrand` in `.env.dev` / `.env.staging` / `.env.production` |

---

**References:**

- [docs/UI/DESIGN_SYSTEM.md](../UI/DESIGN_SYSTEM.md) — Token mapping, palette
- [MESHANT_DESIGN_SYSTEM_PLAN.md](../../openspec/changes/useronboardfix/MESHANT_DESIGN_SYSTEM_PLAN.md) — Phase 28.7 plan
- `frontend/src/shared/constants/brand.ts` — Frontend APP_NAME source
- `.env.example` — Backend env template (includes APP_NAME)
