"""W4.6 (openspec oss-release-remediation, G1) — the estate's E2E
administration tooling (the P9 nightly sandbox lifecycle + the audit
envelope emitter), moved OUT of ``scripts/databricks_e2e/`` — estate
administration lives WITH the estate (the provider-boundary direction).

The nightly workflow and the local driver shell out by module path
(``python -m hub.apps.databricks_admin.e2e_tooling.sandbox create``);
the ``meshant_e2e_*`` naming convention lives ONLY in ``sandbox.py``.
"""
