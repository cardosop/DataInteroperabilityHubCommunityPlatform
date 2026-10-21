# CI/CD Pipeline (MVP)

**CI/CD Platform**: GitHub Actions (see `Technology_Stack_Decisions.md` for details)

This document describes the **continuous integration and delivery (CI/CD)**
pipeline for the Interoperable Data Hub MVP.

It focuses on:

- Build process and artifacts.
- Test execution order.
- Deployment strategy (dev → staging → prod).
- Rollback procedures.

It complements:

- `Testing_Strategy.md`
- `Deployment_Architecture.md`
- `System_Architecture.md`
- `Technical_Design_Document.md`

---

## 1. Pipeline Overview

The pipeline is organized around three main flows:

1. **Pull Request (PR) / Feature Branch** – fast feedback for developers.
2. **Main Branch** – building and validating deployable artifacts.
3. **Environment Deployments** – promoting artifacts to **dev**, **staging**,
   and **production** with checks in between.

High-level stages:

1. **Code & Spec validation** (lint, formatting, OpenAPI checks).
2. **Unit & component tests**.
3. **Integration & API tests**.
4. **Security checks** (SAST, dependency/image scanning).
5. **Build & publish artifacts** (Docker images, SDKs).
6. **Deploy** to target environment (dev/staging/prod).
7. **Post-deploy** smoke/E2E tests and monitoring.

---

## 2. Build Process

### 2.1 Source Layout & Services

Each service (API, domain services, workers, UI) lives in its own directory,
with a `Dockerfile` that supports **multi-stage builds** (build → runtime).

Example layout:

- `services/api/`
- `services/asset/`
- `services/contract/`
- `services/ingestion/`
- `services/dq/`
- `services/compliance/`
- `services/semantic/`
- `services/marketplace/`
- `services/worker/`
- `web-ui/`
- `infra/` (infra-as-code, Helm charts, Compose files, etc.)

### 2.2 Docker Image Build

For each service:

- CI builds a Docker image on **main** (and optionally on PRs for smoke):
  - Tag pattern: `service-name:<git-sha>` and `service-name:<semver>`
    (where applicable).
- Build steps:
  1. Install dependencies.
  2. Run compile/type-check (TypeScript, Python type-check, etc.) if applicable.
  3. Copy application code and configuration templates.
  4. Produce minimal runtime image (no dev tooling).

Artifacts:

- One image per service pushed to the container registry.
- Optional: versioned Helm chart or deployment manifest referencing image tags.

### 2.3 SDK & Spec Artifacts

From `API_Spec_v1.md` / OpenAPI spec:

- Generate and publish SDKs (for main branch only), e.g.:
  - `hub-api-client-js` (npm),
  - `hub-api-client-python` (PyPI).
- Artifacts tagged in lockstep with the API version (e.g. `1.0.0`, `1.1.0`).

Spec artifacts:

- Bundled OpenAPI YAML/JSON for external docs.
- Human-readable API docs (Redoc/Swagger UI) built and deployed to a docs site.

---

## 3. Test Execution Order

The pipeline is designed to **run cheap tests first** and only run heavier tests
when earlier stages pass.

### 3.1 Pull Request Pipeline

Triggered for every PR / feature branch.

Recommended order:

1. **Static checks**
   - Linting (ESLint, flake8, etc.).
   - Formatting (Prettier, Black) – either enforced or checked.
   - Type-checking if applicable (TypeScript, mypy).

2. **OpenAPI & contract checks**
   - OpenAPI lint + validation (see `API_Contract_First_Workflow.md`).
   - Backward-compatibility check for API changes.
   - Schema/contract validations for HubContract changes (if automated).

3. **Unit tests**
   - Backend unit tests (pytest/jest, etc.).
   - Front-end unit/component tests (jest + Testing Library).

4. **Targeted integration tests (fast subset)**
   - For critical flows affected by the PR (e.g. contract validation, basic DQ).

5. **Security checks (PR level)**
   - Lightweight SAST (fast rules).
   - Dependency scanning for changed modules.
   - Secrets scanning on diff (optional but recommended).

Output:

- PR is mergeable only if all of the above pass.
- Full integration & E2E tests are run on **main** to keep PR feedback quick.

### 3.2 Main Branch Pipeline

Triggered on merge to `main`.

Order:

1. **Repeat PR validations**
   - Static checks, unit tests, OpenAPI lint/compatibility, security checks.

2. **Full integration/API tests**
   - Bring up a full stack (or subset) using Docker Compose or ephemeral env.
   - Run integration suites defined in `Testing_Strategy.md`:
     - contract CRUD + validation,
     - ingestion → DQ → compliance orchestration,
     - job lifecycle checks,
     - marketplace flows.

3. **E2E smoke tests (optional on main)**
   - Short UI + API flows (login, simple asset onboarding, simple DQ run).

4. **Security tests (deeper)**
   - More complete SAST ruleset.
   - Full dependency + container image scan.
   - Fail on unapproved HIGH/CRITICAL issues.

5. **Build & publish artifacts**
   - Docker images for all services.
   - OpenAPI bundles + docs.
   - SDKs (if version bump / release tag is present).

### 3.3 Environment-Specific Tests

**Dev environment**

- Automatic deploy on **main** green build.
- Run minimal smoke tests post-deploy (API health, database connectivity).

**Staging environment**

- Deploy artifacts promoted from main.
- Run **full integration tests** + **E2E UI tests** against staging:
  - ingestion, DQ, compliance, marketplace, semantic queries.
- Optional: performance smoke tests (small scale).

**Production environment**

- Deployment is triggered **manually** or via an approval gate after staging
  tests pass.
- Run **post-deploy smoke tests** only (quick sanity checks).
- Rely on monitoring/alerts for ongoing health.

---

## 4. Deployment Strategy

### 4.1 Environments

Baseline environments:

- **Local** – developer machines (Docker Compose).
- **Dev** – shared dev cluster; frequent deploys from main.
- **Staging** – production-like; used for pre-release validation.
- **Production** – tenant-facing environment.

### 4.2 Deployment Approach

Assuming a container orchestrator (e.g. Kubernetes / ECS):

- Use **immutable Docker images** tagged by Git SHA.
- Use **declarative manifests** (Helm/compose/k8s manifests) stored in repo.

Deployment patterns (MVP recommendation):

- **Dev**: rolling updates are acceptable.
- **Staging**: rolling updates with the ability to quickly roll back to a
  previous image tag.
- **Production**:
  - Prefer **blue/green** or **rolling with small batches**:
    - deploy new version to a subset of instances,
    - run smoke tests,
    - gradually shift traffic (when supported by infra).

Each deployment includes:

1. Update manifests to reference the new image tags.
2. Apply manifests to the target environment.
3. Wait for pods/tasks to pass readiness and liveness checks.
4. Run environment-specific smoke tests.

### 4.3 Database Migrations

- DB schema changes are applied via a migration tool (Flyway, Alembic, etc.).
- For production:
  - Migrations must be **backward compatible** with the previous app version
    where possible (expand/contract pattern).
  - Destructive changes (column drops, type changes) require:
    - a multi-step deploy (add new schema, backfill, switch, drop),
    - or careful downtime planning (only if absolutely necessary).

Migrations are applied:

- In **staging** before running tests.
- In **production** as part of the deploy pipeline, with clear logging and
  monitoring around migration time.

---

## 5. Rollback Procedures

### 5.1 Application Rollback

In case of a failed deployment (errors, health checks failing, severe regressions):

1. **Detect**
   - Automated alerts fire due to:
     - failing health checks,
     - elevated error rates,
     - failing post-deploy smoke tests.

2. **Rollback action**
   - Re-deploy the **previous known-good image tags** for the affected services.
   - Redeploy manifests pinned to the previous release version.

3. **Validate**
   - Re-run smoke tests.
   - Monitor error rates and key business KPIs (ingestion success, DQ/compliance
     completion rates).

### 5.2 Database Rollback

Rolling back database schema is inherently more risky.

Principles:

- Prefer **backward-compatible migrations** so that rolling back the app
  version does not require rolling back the DB schema.
- Avoid destructive changes in a single step; instead:
  - add new columns/tables,
  - backfill,
  - switch app to new schema,
  - drop old columns in a later release once no code depends on them.

If a migration causes issues:

- Short-term mitigation:
  - hotfix migrations (e.g. adding missing defaults/indexes),
  - temporary feature flags to disable the problematic feature.
- Full schema rollback is a **last resort** and must be planned and tested
  carefully in non-prod environments.

### 5.3 Configuration Rollback

- Config changes (feature flags, environment variables, config maps) are
  versioned alongside application code when possible.
- To roll back a bad config change:
  - revert the config change in version control,
  - redeploy or reload configuration in the target environment.
- For dynamic config/feature-flag services:
  - flip flags back to their previous state,
  - ensure these changes are captured in audit logs.

### 5.4 Documentation & Runbooks

- For each environment, maintain a short **runbook** describing:
  - how to trigger a rollback,
  - where to find the last known-good release,
  - how to verify that rollback succeeded,
  - communication steps (who to notify).

Runbooks should be discoverable (e.g. linked from the CI/CD pipeline UI or ops
wiki) and tested occasionally (game days).

---

## 6. Summary

- CI runs fast feedback loops on PRs with static checks, unit tests, and light
  integration/security checks.
- Main branch builds fully tested artifacts (images, SDKs, docs) and pushes them
  to registries.
- Deployments follow a promotion flow from dev → staging → production with
  environment-specific tests.
- Rollback strategies prioritize:
  - application-level rollbacks using immutable images,
  - backward-compatible migrations to avoid DB rollback where possible,
  - well-documented procedures for config and emergency fixes.
