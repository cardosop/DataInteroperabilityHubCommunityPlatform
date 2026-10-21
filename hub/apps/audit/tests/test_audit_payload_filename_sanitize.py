"""
Phase 260.2.G — audit ``details_json`` / ``full_details_json`` filename + string sanitization.

Ensures C0 control characters (including CRLF log-injection) cannot survive into persisted
audit payloads when callers embed user-controlled filenames or messages.
"""

from __future__ import annotations

import uuid

import pytest
from django.test import TestCase

from hub.apps.audit.utils import _sanitize, _sanitize_audit_payload_values, create_audit_event
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.integration
class TestSanitizeHelper(TestCase):
    """Unit tests for ``_sanitize`` / tree walker (no mocks)."""

    @pytest.mark.integration
    def test_newline_tab_carriage_return_become_spaces_collapsed(self):
        raw = "report\n\t.csv"
        out = _sanitize(raw)
        self.assertNotIn("\n", out)
        self.assertNotIn("\t", out)
        self.assertEqual(out, "report .csv")

    @pytest.mark.integration
    def test_nul_byte_removed(self):
        self.assertEqual(_sanitize("a\x00b"), "ab")

    @pytest.mark.integration
    def test_crlf_log_injection_sequence_flattened(self):
        raw = "ok.pdf\r\nINFO attacker injected success"
        out = _sanitize(raw)
        self.assertNotIn("\r", out)
        self.assertNotIn("\n", out)

    @pytest.mark.integration
    def test_unicode_line_paragraph_separators_neutralized(self):
        raw = "x\u2028y\u2029z"
        out = _sanitize(raw)
        self.assertNotIn("\u2028", out)
        self.assertNotIn("\u2029", out)
        self.assertEqual(out, "x y z")

    @pytest.mark.integration
    def test_tuple_values_in_detail_tree(self):
        out = _sanitize_audit_payload_values({"t": ("a\n", 99)})
        self.assertEqual(out["t"][0], "a")
        self.assertEqual(out["t"][1], 99)

    @pytest.mark.integration
    def test_low_controls_replaced(self):
        self.assertEqual(_sanitize("x\x01\x02y"), "x y")


@pytest.mark.integration
class TestCreateAuditEventSanitizesPayload(TestCase):
    """Persisted audit rows must not retain injectable control characters in string fields."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Sanitize-{uid}",
            slug=f"sanitize-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"u-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    @pytest.mark.integration
    def test_filename_with_newline_tab_in_details_json(self):
        malicious = "data\nINFO fake\tentry.csv"
        ev = create_audit_event(
            resource_type="FILE",
            action="FILE_UPLOAD_COMPLETED",
            actor_user=self.user,
            tenant=self.tenant,
            resource_id=str(uuid.uuid4()),
            details={"name": malicious, "size": 42},
        )
        ev.refresh_from_db()
        stored = ev.details_json["name"]
        self.assertNotIn("\n", stored)
        self.assertNotIn("\t", stored)

    @pytest.mark.integration
    def test_nested_and_list_strings_sanitized(self):
        payload = {
            "outer": {"inner_name": "in\nner.csv"},
            "paths": ["p\r\nq.txt", "clean.txt"],
        }
        ev = create_audit_event(
            resource_type="FILE",
            action="FILE_TEST",
            actor_user=self.user,
            tenant=self.tenant,
            resource_id=str(uuid.uuid4()),
            details=payload,
        )
        ev.refresh_from_db()
        d = ev.details_json
        self.assertNotIn("\n", d["outer"]["inner_name"])
        self.assertNotIn("\r", d["paths"][0])
        self.assertNotIn("\n", d["paths"][0])
        self.assertEqual(d["paths"][1], "clean.txt")

    @pytest.mark.integration
    def test_dict_key_with_embedded_newline_normalized(self):
        ev = create_audit_event(
            resource_type="FILE",
            action="FILE_TEST",
            actor_user=self.user,
            tenant=self.tenant,
            resource_id=str(uuid.uuid4()),
            details={"report\nname": "value"},
        )
        ev.refresh_from_db()
        self.assertIn("report name", ev.details_json)
        self.assertNotIn("\n", "".join(ev.details_json.keys()))

    @pytest.mark.integration
    def test_resource_activity_sanitizes_dict_keys(self):
        from hub.apps.audit.serializers import sanitize_activity_details

        raw = {"meta\nkey": "v"}
        out = sanitize_activity_details(raw)
        self.assertEqual(list(out.keys()), ["meta key"])

    @pytest.mark.integration
    def test_full_details_json_sanitized(self):
        malicious = "secret\nnote.xls"
        ev = create_audit_event(
            resource_type="FILE",
            action="FILE_TEST",
            actor_user=self.user,
            tenant=self.tenant,
            resource_id=str(uuid.uuid4()),
            details={"k": 1},
            full_details={"filename": malicious},
        )
        ev.refresh_from_db()
        self.assertIsNotNone(ev.full_details_json)
        self.assertNotIn("\n", ev.full_details_json["filename"])


@pytest.mark.integration
class TestSanitizeTreeWalker(TestCase):
    @pytest.mark.integration
    def test_non_string_scalars_passthrough(self):
        self.assertEqual(_sanitize_audit_payload_values(None), None)
        self.assertEqual(_sanitize_audit_payload_values(7), 7)
        self.assertEqual(_sanitize_audit_payload_values(True), True)


@pytest.mark.integration
class TestSanitizeActivityDetailsDefenseInDepth(TestCase):
    """Read-path scrub matches persisted Phase 260.2.G semantics for legacy rows."""

    @pytest.mark.integration
    def test_string_leaves_and_list_elements_scrubbed(self):
        from hub.apps.audit.serializers import sanitize_activity_details

        raw = {"name": "x\ny", "items": ["a\tb", {"k": "p\rq"}]}
        out = sanitize_activity_details(raw)
        self.assertEqual(out["name"], "x y")
        self.assertEqual(out["items"][0], "a b")
        self.assertEqual(out["items"][1]["k"], "p q")

    @pytest.mark.integration
    def test_tuple_strings_scrubbed(self):
        from hub.apps.audit.serializers import sanitize_activity_details

        raw = {"k": ("p\nq",)}
        out = sanitize_activity_details(raw)
        self.assertEqual(out["k"], ("p q",))
