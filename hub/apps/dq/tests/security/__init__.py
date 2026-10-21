"""
Phase 240.5.E.1 — DQ-app-local security test package.

Lives under ``hub/apps/dq/tests/security/`` (NOT
``tests/security/``) so the DQ feature's IDOR contract sits next
to the code it pins. The ``test-security`` CI job at
``.github/workflows/ci.yml`` collects this directory in addition
to ``tests/security/`` (see Phase 240.5.E.3).
"""
