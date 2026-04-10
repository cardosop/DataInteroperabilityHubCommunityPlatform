# Changelog

Release notes for the Meshant Data Interoperability Hub, organised by
implementation phase.

---

## Phase 218 -- Terraform Destroy Workflow Parity

**Date**: 2026-04-09 (in progress)

Aligns Terraform destroy workflows with the safety and automation level
of apply workflows.

**Key deliverables**

- Plan-before-destroy gate in CI/CD pipeline.
- Manual approval step for production destroy operations.
- State-lock validation before any destroy plan is executed.
- Parity between `staging` and `production` destroy workflows.

---

## Phase 217 -- MVP Documentation Audit, Overlay and Gap Fill

**Date**: 2026-04-01

Comprehensive documentation audit ensuring every MVP feature has a
concept page, API reference entry, use-case page, and persona how-to
guide.

**Key deliverables**

- Product documentation site (`docs/mvpdocs/`) with persona-driven
  navigation (DPO, DE, CPO, DC, MPA, DEV).
- Concept pages for all 16 MVP domains (assets, contracts, datasets,
  DQ runs, compliance runs, marketplace listings, governance, billing,
  jobs, search, webhooks, semantic resources, versioning, orchestration,
  tenants, users and roles).
- Use-case and journey pages promoted from internal planning docs.
- API audit consolidated report (`_audit/api-audit-consolidated.md`).
- Stakeholder product pages (this section): MVP Features, Feature
  Matrix, Roadmap, Changelog, Pricing and Quotas.

---

## Phase 216 -- CLI/SDK MVP Coverage Parity

**Date**: 2026-03-22

Brought the CLI and Python SDK test infrastructure to full parity with
the MVP API surface.

**Key deliverables**

- Integration and end-to-end test suites for all MVP CLI commands.
- SDK method coverage for contracts, assets, datasets, DQ, compliance,
  marketplace, governance, jobs, search, audit, and webhooks.
- MVP-gated feature awareness: CLI commands for post-MVP features
  (BaaS, Virtualization, Mesh, ML, Transformation, Social, Scheduled
  Ingestion, Scheduled Export) return clear "not available in current
  plan" messages instead of cryptic errors.
- Test infrastructure: `conftest.py` fixtures, `pytest.ini` markers,
  and CI workflow updates for reliable parallel test execution.

---

## Phase 215 -- CLI and SDK MVP-Gated Feature Awareness

**Date**: 2026-03-15

Added explicit MVP-gating to the CLI and SDK so that post-MVP feature
commands fail gracefully.

**Key deliverables**

- `odps_errors.py` error module for structured error responses.
- CLI commands for eight post-MVP feature areas (BaaS, Virtualization,
  Mesh, ML, Transformation, Social, Scheduled Ingestion, Scheduled
  Export) wired to return `MVP_NOT_AVAILABLE` status.
- API client updates to propagate MVP-tier information from the server.
- `.env.test.example` and CI workflow adjustments for gated-feature
  test paths.

---

## Earlier Phases

Phases prior to 215 are documented in the internal engineering log.
Contact the platform team for historical release details.
