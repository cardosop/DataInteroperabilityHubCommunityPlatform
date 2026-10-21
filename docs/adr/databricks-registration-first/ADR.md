# ADR: Databricks Workspace Registration-First Operating Model

**Status**: Accepted
**Date**: 2026-09-13
**Owner**: Platform Engineering
**Phase**: P8 (openspec add-databricks-account-plane)

## Context

The Hub's Databricks control plane (P0–P7) treats workspace registration as the only onboarding path: tenants bring their own (BYO) Databricks workspaces and the Hub registers them with per-tenant credentials. Phase 8 adds the OPTIONAL hub-owned account plane — the Hub can now link a Databricks *account* (the account console, above workspaces), create metastores, and provision workspaces through the account API. That capability introduces a product question the code cannot answer alone: which path is the DEFAULT?

Provisioning through the account API creates real external infrastructure (workspaces bill to the account; mistakes are expensive and legally consequential — the account admin credential is a high-privilege secret). The umbrella roadmap already records the product lean: "Registration-first — tenants register existing workspaces; provisioning is never the default" and "Hub-owned account provisioning as default (rejected — infra-creating path with DPO/Legal signoff; kept as optional P8)". This ADR formalizes that lean as a durable operating-model decision so future contributors cannot silently drift the default.

## Decision

1. **Registration-first is the default operating model.** Tenants onboard by registering existing BYO workspaces (the P0 surface). The Hub never provisions infrastructure by default; nothing in the product onboarding flow suggests otherwise.
2. **Provisioning is the signoff-gated exception.** Workspace/metastore provisioning through the account API requires BOTH:
   - the target tenant's `databricks_workspace_provisioning_enabled` feature flag ON (default-off, the `databricks_control_plane_enabled` flag pattern), AND
   - a COMPLETE DPO/Legal signoff recorded on the account row (`provisioning_signoff_by`, `provisioning_signoff_at`, `provisioning_signoff_evidence_url`).
   Without both, the provisioning endpoint returns HTTP 403 with ZERO network calls — creating external infrastructure is a legal act, not an admin convenience.
3. **Every provisioning operation is audit-trailed** — `DATABRICKS_METASTORE_CREATED` / `DATABRICKS_WORKSPACE_PROVISIONED` (plus `DATABRICKS_ACCOUNT_LINKED` for the link) — best-effort emission that never blocks the operation (the Phase 273 discipline).
4. **The account plane is platform-scoped.** The `DatabricksAccount` platform table carries no tenant FK and no RLS (the documented exemption); access is admin-DB-only (`DATABASES["admin"]`, BYPASSRLS) with PLATFORM_ADMIN RBAC on the API surface. A provisioned workspace attaches to a tenant through the existing workspace registry (the same host validation + SSRF guard as registration — registration-first machinery reused, never bypassed).

## Consequences

- **Positive**: the default path stays the safe one (BYO registration); the infra-creating path is deliberate, reviewable, and reversible; the signoff record makes the legal gate auditable rather than cultural.
- **Negative**: platform admins cannot provision without the flag + signoff — a deliberate friction; the flag/signoff/audit triple must be re-verified by every future account-plane extension.
- **Reversal**: to make provisioning the default, a new ADR superseding this one is required (the index marks the supersession).

## Related

- `openspec/changes/add-databricks-control-plane` (umbrella proposal/design — the BYO + registration-first product decisions)
- `openspec/changes/add-databricks-account-plane/design.md` (D3 — the flag/signoff triple; D6 — the estate summary)
- Journey [JOURNEY-DB-016](../../mvpdocs/journeys/JOURNEY-DB-016.md) — Provision a Workspace from the Account
