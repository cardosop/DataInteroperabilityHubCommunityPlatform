"""Phase 9 (openspec add-databricks-live-ci-sandbox task 9.2) — the
Databricks E2E nightly sandbox helpers.

The `.github/workflows/databricks-e2e-nightly.yml` workflow shells out to
this package for the two guarded surfaces: the hard-budget pre-flight
(``budget.py`` — pure arithmetic, refused runs never create anything) and
the sandbox lifecycle (``sandbox.py`` — the ``meshant_e2e_*`` naming
convention and the idempotent auto-destroy sweep). Both scripts use the
PRODUCTION ``DatabricksAccountClient``; credentials come from the
environment (workflow secrets via the OIDC posture), never the repo.
"""
