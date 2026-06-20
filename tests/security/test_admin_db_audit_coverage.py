"""
Phase 277.B.019 — Cross-tenant admin DB audit-event coverage conformance.

Verifies every management command using DATABASES["admin"] / .using("admin")
emits at least one create_audit_event call with proper justification.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)

_HUB_APPS = Path(__file__).resolve().parents[2] / "hub" / "apps"


def _find_admin_db_commands() -> list[Path]:
    """Return management commands that use DATABASES['admin'] or .using('admin')."""
    cmds = []
    mgmt_dir = _HUB_APPS
    for root, _dirs, files in os.walk(mgmt_dir):
        if root.endswith("/management/commands") or "management/commands" in root:
            for f in files:
                if f.endswith(".py") and f != "__init__.py":
                    path = Path(root) / f
                    with open(path) as fh:
                        source = fh.read()
                    if 'DATABASES["admin"]' in source or '.using("admin")' in source:
                        cmds.append(path)
    return sorted(cmds)


def _has_audit_event(source: str) -> bool:
    """True if the source file calls create_audit_event."""
    return "create_audit_event" in source


class TestAdminDBAuditCoverage(TestCase):
    """Phase 277.B.019 — every admin-DB management command must emit audit events."""

    def test_all_admin_db_commands_have_audit_coverage(self):
        """Every command using DATABASES["admin"] must call create_audit_event."""
        uncovered = []
        for cmd_path in _find_admin_db_commands():
            with open(cmd_path) as f:
                source = f.read()
            if not _has_audit_event(source):
                uncovered.append(str(cmd_path))

        if uncovered:
            msg = (
                f"Found {len(uncovered)} admin-DB command(s) without audit coverage. "
                f"Every DATABASES['admin'] / .using('admin') call MUST emit an "
                f"audit event with actor=PLATFORM_ADMIN + justification.\n"
                + "\n".join(f"  - {u}" for u in uncovered)
            )
            pytest.fail(msg)

    def test_known_commands_covered(self):
        """revoke_expired_access and archive_old_audit_events both have audit."""
        cmds = [p.name for p in _find_admin_db_commands()]
        assert "revoke_expired_access.py" in cmds
        assert "archive_old_audit_events.py" in cmds
        # Both should pass the audit check.
        for p in _find_admin_db_commands():
            with open(p) as f:
                assert _has_audit_event(f.read()), f"{p.name} lacks audit coverage"
