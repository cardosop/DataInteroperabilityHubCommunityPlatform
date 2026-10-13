"""
W1.7 (R2-S12) — the MFA claim-to-reality pins.

The repo shipped a full TOTP library (``hub/apps/auth/mfa.py``), a
tenant ``mfa_required`` flag, and docs claiming MFA — but ZERO code
ever enforced it (no consumer of ``is_mfa_required`` anywhere). The
remediation decision (design.md W1.5's recommendation — remove-claim
now): the dead library is deleted, the misleading tenant flag is
dropped, and the docs state reality — MFA is NOT shipped.

These pins are the contract: the module is gone, the field is gone,
and no shipped doc claims MFA as a present capability.
"""

import importlib.util

import pytest
from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)


class MFARemovedTest(TestCase):
    def test_mfa_module_is_gone(self):
        spec = importlib.util.find_spec("hub.apps.auth.mfa")
        self.assertIsNone(
            spec,
            "hub/apps/auth/mfa.py must be deleted (dead code — zero "
            "consumers; nothing enforced MFA)",
        )

    def test_tenant_mfa_required_field_is_gone(self):
        from django.core.exceptions import FieldDoesNotExist

        from hub.apps.tenants.models import Tenant

        with self.assertRaises(FieldDoesNotExist):
            Tenant._meta.get_field("mfa_required")

    def test_pyotp_is_no_longer_a_dependency(self):
        import tomllib
        from pathlib import Path

        from django.conf import settings

        pyproject = tomllib.loads((Path(settings.BASE_DIR) / "pyproject.toml").read_text())
        dependencies = pyproject.get("project", {}).get("dependencies", [])
        pyotp_entries = [d for d in dependencies if str(d).startswith("pyotp")]
        self.assertEqual(
            pyotp_entries,
            [],
            "pyotp was imported ONLY by the deleted mfa.py — the "
            "dependency must go with the code",
        )


class MFADocClaimTest(TestCase):
    """No shipped doc may claim MFA as a present capability."""

    @staticmethod
    def _repo_doc(relative: str) -> str:
        from pathlib import Path

        from django.conf import settings

        # settings.BASE_DIR is the repo root in BOTH the in-container
        # layout (/app) and the host-side checkout.
        return (Path(settings.BASE_DIR) / relative).read_text()

    def test_security_docs_state_mfa_not_shipped(self):
        # docs/docs/ was the W12.1-deleted duplication — only the
        # canonical tree exists now.
        text = self._repo_doc("docs/SECURITY.md")
        self.assertNotIn("(JWT, OAuth, SSO, MFA)", text)
        self.assertIn("MFA is not", text)

    def test_feature_completeness_does_not_check_mfa(self):
        # docs/docs/ was the W12.1-deleted duplication — only the
        # canonical tree exists now.
        text = self._repo_doc("docs/FEATURE_COMPLETENESS.md")
        self.assertNotIn("Login, MFA, SSO", text)

    def test_testing_guide_does_not_claim_mfa_coverage(self):
        text = self._repo_doc("docs/TESTING_GUIDE.md")
        self.assertNotIn("password reset, MFA)", text)
        self.assertNotIn("**MFA**: Success, failure", text)

    def test_frontend_guide_marks_mfa_screens_not_shipped(self):
        text = self._repo_doc("docs/FRONTEND_GUIDE.md")
        self.assertIn("NOT SHIPPED (W1.7", text)

    def test_incident_response_uses_generic_auth_bypass_example(self):
        # docs/docs/ was the W12.1-deleted duplication — only the
        # canonical tree exists now.
        text = self._repo_doc("docs/INCIDENT_RESPONSE.md")
        self.assertNotIn("MFA bypass", text)
