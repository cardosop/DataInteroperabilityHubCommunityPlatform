# Role-Specific Onboarding Paths — Meshant Hub (281.A.10.8)

**Date:** 2026-05-15  
**Target:** New engineers productive in <2 days per role

## Path 1: Frontend Engineer (React/TypeScript)

**Time to first PR:** <4 hours  
**Prerequisites:** Node 20, npm, VS Code with recommended extensions

### Day 1 Morning — Environment
1. Clone repo + `cd frontend && npm ci` (10 min)
2. Open `.devcontainer/devcontainer.json` in VS Code — accept "Reopen in Container" (5 min)
3. Read `frontend/README.md` + `docs/FRONTEND_GUIDE.md` (30 min)
4. Start dev server: `npm run dev` → http://localhost:5173 (5 min)
5. Log in with smoke-test credentials from `docs/MVP_TEST_SECRETS.md`

### Day 1 Afternoon — Codebase Tour
1. **Architecture overview:** `docs/ARCHITECTURE.md` → Frontend section (15 min)
2. **Component library:** Browse `frontend/src/shared/components/` (30 min)
3. **i18n:** Read `frontend/src/shared/i18n/` — 6 locales, `useTranslation()` hook (15 min)
4. **Routing:** Read `frontend/src/app/routes/routes.tsx` (10 min)
5. **State management:** RTK Query patterns in `frontend/src/shared/api/` (15 min)

### Day 2 — First Contribution
1. Pick a `good first issue` from the backlog
2. Create a branch, implement, write tests (story + unit + a11y)
3. Run `npm run lint && npm run typecheck && npm run test`
4. Open PR → CI runs Chromatic + Lighthouse + Playwright E2E

### Key Files Map
```
frontend/src/
├── app/                  # App shell, router, providers
├── features/             # Feature modules (assets, marketplace, governance…)
│   └── <feature>/
│       ├── components/   # Feature-specific components
│       ├── hooks/        # Feature-specific hooks
│       └── api/          # RTK Query endpoints
├── shared/
│   ├── components/       # Reusable UI components (Button, Banner, Dialog…)
│   ├── i18n/             # Translation keys + formatters
│   ├── styles/           # Global CSS + a11y tokens
│   └── telemetry/        # Web vitals + error tracking
└── e2e/                  # Playwright E2E specs
```

---

## Path 2: Backend Engineer (Python/Django)

**Time to first PR:** <6 hours  
**Prerequisites:** Python 3.12, Docker, PostgreSQL client

### Day 1 Morning — Environment
1. Clone repo + `python -m venv .venv && source .venv/bin/activate` (5 min)
2. `pip install -r requirements.txt -r requirements-dev.txt` (10 min)
3. `docker compose up -d postgres redis-cache` — start infra (5 min)
4. `python hub/manage.py migrate` — apply migrations (2 min)
5. `python hub/manage.py runserver` → http://localhost:8000 (2 min)
6. Read `CLAUDE.md` — project contracts and conventions (15 min)

### Day 1 Afternoon — Codebase Tour
1. **Architecture overview:** `docs/ARCHITECTURE.md` → Backend section (15 min)
2. **Django apps:** Browse `hub/apps/` — 41 apps organized by domain (30 min)
3. **API patterns:** Read `docs/API_STANDARDS.md` + `hub/apps/api/standards/` (15 min)
4. **Error handling:** `hub/apps/core/error_handling/` — ErrorResponse + gettext i18n (10 min)
5. **Business rules:** `hub/apps/core/business_rules/` — chain registry pattern (10 min)
6. **RLS policies:** `CLAUDE.md` → Tenant Isolation RLS Contract (5 min)

### Day 2 — First Contribution
1. Pick a `good first issue` from the backlog
2. Create a branch, implement model/view/serializer, write tests
3. Run `pre-commit run --all-files` + `python hub/manage.py test`
4. Open PR → CI runs pytest + lint-rls-policies + architecture-fitness

### Key Files Map
```
hub/
├── apps/
│   ├── core/             # Shared infrastructure (circuit breaker, error handling)
│   ├── api/              # API gateway, versioning, standards, middleware
│   ├── assets/           # Asset CRUD + lifecycle
│   ├── contracts/        # ODPS/ODCS contract management
│   ├── marketplace/      # Marketplace listings, orders, entitlements
│   ├── governance/       # Access policies, approvals, ABAC
│   ├── compliance/       # Compliance scans, frameworks
│   ├── tenants/          # Tenant management, feature flags
│   └── ...               # 33 more domain apps
├── settings.py           # Django settings (2,600+ lines)
└── urls.py               # Root URL configuration
```

---

## Path 3: Full-Stack Engineer

**Time to first PR:** <8 hours  
**Prerequisites:** Both frontend + backend prerequisites

### Day 1
- Follow Frontend Path → Day 1 Morning (2 hours)
- Follow Backend Path → Day 1 Morning (2 hours)

### Day 2
- Read `CLAUDE.md` — full project contracts (30 min)
- Trace 1 critical journey end-to-end: login → asset creation → contract validation → marketplace publish (2 hours)
- First contribution: pick a full-stack issue, implement FE + BE, write E2E spec

---

## Path 4: DevOps / Platform Engineer

**Time to first PR:** <6 hours  
**Prerequisites:** Docker, kubectl, Helm, Terraform, AWS CLI

### Day 1
1. Read `docs/INFRASTRUCTURE_DECISIONS.md` + `docs/DEPLOYMENT_AND_OPERATIONS.md` (30 min)
2. Review Terraform: `infrastructure/terraform/environments/staging/main.tf` (30 min)
3. Review Helm: `helm/templates/` — service deployments (30 min)
4. Review CI/CD: `.github/workflows/deploy.yml` (15 min)
5. Start local infra: `docker compose up -d` (10 min)

### Day 2
1. Read `docs/operations/production-deployment-runbook.md` (30 min)
2. Run `terraform plan` against staging (requires AWS credentials)
3. First contribution: infrastructure change with Terraform plan output in PR

### Key Files Map
```
infrastructure/
├── terraform/
│   ├── modules/          # Reusable modules (eks, rds, vpc, kms…)
│   └── environments/     # staging/ + prod/ root modules
├── traefik/              # API gateway configuration
└── postgres/             # PostgreSQL SSL + PgBouncer setup
helm/
└── templates/            # Kubernetes service deployments
.github/workflows/        # 50+ CI/CD workflows
```

---

## Shared Resources (All Roles)

| Resource | Path | Purpose |
|---|---|---|
| Architecture overview | `docs/ARCHITECTURE.md` | System design + component diagrams |
| Project contracts | `CLAUDE.md` | RLS, ABAC, search throttle, business rules chains |
| ADR index | `docs/adr/index.md` | 34 architecture decisions with summaries |
| API standards | `docs/API_STANDARDS.md` | Endpoint naming, versioning, error codes |
| Runbook library | `docs/runbooks/INDEX.md` | 106 runbooks across 10 categories |
| Devcontainer | `.devcontainer/devcontainer.json` | Pre-configured VS Code environment |

## Onboarding Checklist (All Roles)

- [ ] Read `CLAUDE.md` — project contracts and conventions
- [ ] Set up dev environment (Docker Compose or devcontainer)
- [ ] Run the test suite: `python hub/manage.py test` or `npm run test`
- [ ] Read the ADR index for your domain
- [ ] Make first PR (docs-only or good-first-issue)
- [ ] Pair review with a domain expert
- [ ] Join `#meshant-eng` Slack channel
