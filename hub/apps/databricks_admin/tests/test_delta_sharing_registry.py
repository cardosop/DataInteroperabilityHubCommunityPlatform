"""Phase 5 (openspec add-delta-sharing-server task 5.2) — the Delta
Sharing recipient/token registry: models + RLS + the API-key store token
hashing + per-recipient-token throttling.

No mocks: real Postgres rows (tenant/recipient/token), RLS policy scans
(pg_policies) + runtime enforcement through the 1.12 ``hub_rls_probe``
role, the REAL sha256 hash helper, and the REAL DRF throttle against the
real cache with per-token keys. The ONE concession to speed is the
throttle bucket pin: the instance's ``num_requests``/``duration`` are
re-configured after ``__init__`` (3 per 60s instead of the production
30/minute) so the boundary pin runs in 4 requests — DRF computes those
attributes from the frozen-at-import ``THROTTLE_RATES``, so instance
re-configuration is the honest way to exercise the bucket logic fast;
the production rate itself is pinned separately.
"""

import uuid

import pytest
from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests.test_uc_browse import _setup_tenant

pytestmark = pytest.mark.django_db(transaction=True)


def _hex64() -> str:
    return "ab" * 32


def _issue_token(recipient, *, share="share", schema=None, table=None, tenant=None):
    """Issue a real token row through the production issue() path."""
    from hub.apps.databricks_admin.models import DeltaShareToken

    return DeltaShareToken.issue(
        recipient=recipient,
        tenant=tenant or recipient.tenant,
        share_name=share,
        schema_name=schema,
        table_name=table,
    )


class TestDeltaShareRecipientModel(TestCase):
    """The recipient registry row: identity, uniqueness, cascade."""

    def setUp(self):
        require_dns()
        self.tenant, self.admin = _setup_tenant()
        self.suffix = uuid.uuid4().hex[:8]

    def _mk(self, **overrides):
        from hub.apps.databricks_admin.models import DeltaShareRecipient

        kwargs = {
            "tenant": self.tenant,
            "name": f"recipient-{self.suffix}",
            "created_by": self.admin,
        }
        kwargs.update(overrides)
        return DeltaShareRecipient.objects.create(**kwargs)

    def test_recipient_carries_the_tenant_scope_and_table_name(self):
        from hub.apps.databricks_admin.models import DeltaShareRecipient

        recipient = self._mk()
        assert str(recipient.tenant_id) == str(self.tenant.id)
        assert DeltaShareRecipient._meta.db_table == "databricks_delta_share_recipients"
        assert recipient.created_by_id == self.admin.id

    def test_blank_name_is_refused(self):
        from django.core.exceptions import ValidationError

        from hub.apps.databricks_admin.models import DeltaShareRecipient

        recipient = DeltaShareRecipient(tenant=self.tenant, name="   ")
        with pytest.raises(ValidationError):
            recipient.full_clean()

    def test_tenant_name_pair_is_unique(self):
        from django.core.exceptions import ValidationError

        from hub.apps.databricks_admin.models import DeltaShareRecipient

        self._mk()
        duplicate = DeltaShareRecipient(tenant=self.tenant, name=f"recipient-{self.suffix}")
        with pytest.raises(ValidationError) as exc_info:
            duplicate.full_clean()
        message = str(exc_info.value)
        assert "__all__" in message
        assert "already exists" in message

    def test_deleting_a_recipient_cascades_to_its_tokens(self):
        from hub.apps.databricks_admin.models import DeltaShareToken

        recipient = self._mk()
        recipient_id = recipient.id
        _issue_token(recipient)
        assert DeltaShareToken.objects.filter(recipient_id=recipient_id).count() == 1
        recipient.delete()
        assert DeltaShareToken.objects.filter(recipient_id=recipient_id).count() == 0


class TestDeltaShareTokenModel(TestCase):
    """The token row: shape guards, the tenant/recipient consistency
    contract, and uniqueness."""

    def setUp(self):
        require_dns()
        self.tenant, self.admin = _setup_tenant()
        from hub.apps.databricks_admin.models import DeltaShareRecipient

        self.recipient = DeltaShareRecipient.objects.create(
            tenant=self.tenant,
            name=f"recipient-{uuid.uuid4().hex[:8]}",
            created_by=self.admin,
        )

    def _unsaved(self, **overrides):
        from hub.apps.databricks_admin.models import DeltaShareToken

        kwargs = {
            "tenant": self.tenant,
            "recipient": self.recipient,
            "token_hash": _hex64(),
            "token_prefix": "ab12cd34",
            "share_name": f"share-{uuid.uuid4().hex[:6]}",
            "created_by": self.admin,
        }
        kwargs.update(overrides)
        return DeltaShareToken(**kwargs)

    def _mk(self, **overrides):
        token = self._unsaved(**overrides)
        token.save()
        return token

    def test_token_carries_the_scope_triple_and_table_name(self):
        from hub.apps.databricks_admin.models import DeltaShareToken

        token = self._mk(schema_name="sales", table_name="orders")
        assert DeltaShareToken._meta.db_table == "databricks_delta_share_tokens"
        assert token.share_name.startswith("share-")
        assert token.schema_name == "sales"
        assert token.table_name == "orders"

    def test_non_hex_token_hash_is_refused(self):
        from django.core.exceptions import ValidationError

        token = self._unsaved(token_hash="z" * 64)
        with pytest.raises(ValidationError) as exc_info:
            token.full_clean()
        assert "token_hash" in str(exc_info.value)

    def test_wrong_length_token_prefix_is_refused(self):
        from django.core.exceptions import ValidationError

        token = self._unsaved(token_prefix="short")
        with pytest.raises(ValidationError) as exc_info:
            token.full_clean()
        assert "token_prefix" in str(exc_info.value)

    def test_blank_share_name_is_refused(self):
        from django.core.exceptions import ValidationError

        token = self._unsaved(share_name="  ")
        with pytest.raises(ValidationError) as exc_info:
            token.full_clean()
        assert "share_name" in str(exc_info.value)

    def test_table_scope_requires_a_schema_scope(self):
        from django.core.exceptions import ValidationError

        token = self._unsaved(schema_name=None, table_name="orders")
        with pytest.raises(ValidationError) as exc_info:
            token.full_clean()
        assert "schema_name" in str(exc_info.value)

    def test_token_tenant_must_match_the_recipients_tenant(self):
        from django.core.exceptions import ValidationError

        from hub.apps.tenants.models import Tenant

        other = Tenant.objects.create(
            name=f"other-{uuid.uuid4().hex[:8]}",
            slug=f"other-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
        )
        token = self._unsaved(tenant=other)
        with pytest.raises(ValidationError) as exc_info:
            token.full_clean()
        assert "recipient" in str(exc_info.value)

    def test_token_hash_is_unique(self):
        from django.core.exceptions import ValidationError

        self._mk()
        duplicate = self._unsaved()
        with pytest.raises(ValidationError) as exc_info:
            duplicate.full_clean()
        assert "token_hash" in str(exc_info.value), "the duplicate hash must be refused"


class TestDeltaShareTokenIssuance(TestCase):
    """The API-key store pattern: the plaintext is shown ONCE, the row
    stores only the hash — verified by a raw column scan, not by
    trusting the ORM's own save path."""

    def setUp(self):
        require_dns()
        self.tenant, self.admin = _setup_tenant()
        from hub.apps.databricks_admin.models import DeltaShareRecipient

        self.recipient = DeltaShareRecipient.objects.create(
            tenant=self.tenant,
            name=f"recipient-{uuid.uuid4().hex[:8]}",
            created_by=self.admin,
        )

    def test_issue_returns_the_plaintext_once_and_stores_only_the_hash(self):
        from django.db import connection

        from hub.apps.auth.utils import sha256_hex

        token, plaintext = _issue_token(self.recipient, schema="sales", table="orders")
        assert plaintext, "the plaintext must be returned exactly once"
        assert token.token_hash == sha256_hex(plaintext)
        assert token.token_prefix == plaintext[:8]
        assert token.schema_name == "sales"
        assert token.table_name == "orders"

        # The raw row must NOT carry the plaintext in any column — the
        # sha256 hex alphabet has no '_'/'-', so substring leaks too.
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM databricks_delta_share_tokens WHERE id = %s",
                [str(token.id)],
            )
            columns = [col.name for col in cursor.description]
            row = cursor.fetchone()
        for name, value in zip(columns, row, strict=True):
            text = str(value)
            assert plaintext not in text, f"the plaintext token leaked into column {name}: {text!r}"

    def test_each_issue_produces_a_distinct_plaintext_and_hash(self):
        first, p1 = _issue_token(self.recipient)
        second, p2 = _issue_token(self.recipient)
        assert p1 != p2
        assert first.token_hash != second.token_hash

    def test_resolve_finds_the_row_by_plaintext(self):
        from hub.apps.databricks_admin.models import DeltaShareToken

        token, plaintext = _issue_token(self.recipient)
        resolved = DeltaShareToken.resolve(plaintext)
        assert resolved is not None
        assert resolved.id == token.id

    def test_resolve_returns_none_for_an_unknown_token(self):
        from hub.apps.databricks_admin.models import DeltaShareToken

        assert DeltaShareToken.resolve(f"unknown-{uuid.uuid4().hex}") is None


class TestDeltaShareRegistryRLS(TestCase):
    """The direct-FK policies FILTER at runtime (the 1.12 probe), not
    just exist in pg_policies."""

    def setUp(self):
        require_dns()
        self.tenant_a, self.admin = _setup_tenant()
        from hub.apps.databricks_admin.models import DeltaShareRecipient
        from hub.apps.tenants.models import Tenant

        self.tenant_b = Tenant.objects.create(
            name=f"tenant-b-{uuid.uuid4().hex[:8]}",
            slug=f"tenant-b-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
        )
        self.recipient = DeltaShareRecipient.objects.create(
            tenant=self.tenant_a,
            name=f"recipient-{uuid.uuid4().hex[:8]}",
            created_by=self.admin,
        )
        _issue_token(self.recipient)

    def _probe_role(self):
        from hub.apps.databricks_admin.tests.test_uc_rls_isolation import (
            _connection_bypasses_rls,
            _ensure_rls_probe_role,
        )

        if _connection_bypasses_rls():
            _ensure_rls_probe_role()
            return "hub_rls_probe"
        return None

    def test_both_tables_ship_a_paired_policy(self):
        from django.db import connection

        for table, policy in (
            (
                "databricks_delta_share_recipients",
                "databricks_delta_share_recipients_tenant_isolation",
            ),
            ("databricks_delta_share_tokens", "databricks_delta_share_tokens_tenant_isolation"),
        ):
            with connection.cursor() as cursor:
                cursor.execute("SELECT policyname FROM pg_policies WHERE tablename = %s", [table])
                names = {row[0] for row in cursor.fetchall()}
            assert policy in names, f"{table} must ship the paired RLS policy"

    def test_foreign_tenants_see_zero_rows_on_both_tables(self):
        from hub.apps.databricks_admin.tests.test_uc_rls_isolation import _visible_count_as

        probe = self._probe_role()
        assert _visible_count_as(probe, self.tenant_a.id, "databricks_delta_share_recipients") == 1
        assert _visible_count_as(probe, self.tenant_b.id, "databricks_delta_share_recipients") == 0
        assert _visible_count_as(probe, self.tenant_a.id, "databricks_delta_share_tokens") == 1
        assert _visible_count_as(probe, self.tenant_b.id, "databricks_delta_share_tokens") == 0

    def test_no_tenant_context_hides_everything(self):
        from django.db import connection

        probe = self._probe_role()
        with connection.cursor() as cursor:
            try:
                if probe:
                    cursor.execute(f"SET ROLE {probe}")
                for table in (
                    "databricks_delta_share_recipients",
                    "databricks_delta_share_tokens",
                ):
                    cursor.execute(f"SELECT count(*) FROM {table}")
                    assert cursor.fetchone()[0] == 0, (
                        f"without a tenant context the {table} policy must hide everything"
                    )
            finally:
                if probe:
                    cursor.execute("RESET ROLE")


class TestDeltaShareTokenThrottle(TestCase):
    """Per-recipient-token throttling: tenant-scoped cache keys, one
    bucket per token, one tenant's exhaustion never touching another's."""

    def setUp(self):
        require_dns()
        self.tenant_a, self.admin = _setup_tenant()
        from hub.apps.databricks_admin.models import DeltaShareRecipient
        from hub.apps.tenants.models import Tenant

        self.tenant_b = Tenant.objects.create(
            name=f"tenant-b-{uuid.uuid4().hex[:8]}",
            slug=f"tenant-b-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
        )
        self.recipient_a = DeltaShareRecipient.objects.create(
            tenant=self.tenant_a,
            name=f"recipient-a-{uuid.uuid4().hex[:8]}",
            created_by=self.admin,
        )
        self.recipient_b = DeltaShareRecipient.objects.create(
            tenant=self.tenant_b,
            name=f"recipient-b-{uuid.uuid4().hex[:8]}",
        )
        self.token_a, self.plaintext_a = _issue_token(self.recipient_a)
        self.token_b, self.plaintext_b = _issue_token(self.recipient_b)

    def _request(self, plaintext):
        return APIRequestFactory().get(
            "/api/v1/databricks/delta-sharing/shares",
            HTTP_AUTHORIZATION=f"Bearer {plaintext}",
        )

    def _throttle(self):
        from hub.apps.databricks_admin.throttles import DeltaShareTokenRateThrottle

        throttle = DeltaShareTokenRateThrottle()
        # The bucket pin runs the boundary in 4 requests: the production
        # rate (30/minute) is frozen into DRF's THROTTLE_RATES at import
        # time, so the instance is re-configured after __init__.
        throttle.num_requests = 3
        throttle.duration = 60
        return throttle

    def test_the_scope_and_settings_rate_are_registered(self):
        from hub.apps.databricks_admin.throttles import DeltaShareTokenRateThrottle

        assert DeltaShareTokenRateThrottle.scope == "delta_share_recipients"
        assert (
            settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["delta_share_recipients"]
            == "30/minute"
        )

    def test_the_cache_key_is_tenant_scoped_and_per_token(self):
        from hub.apps.databricks_admin.throttles import DeltaShareTokenRateThrottle

        key = DeltaShareTokenRateThrottle().get_cache_key(
            self._request(self.plaintext_a),
            None,
        )
        assert key is not None
        assert key.startswith("throttle_delta_share_recipients_")
        assert str(self.tenant_a.id) in key, "the key must carry the tenant id (Phase 273)"
        assert self.token_a.token_hash in key, "the key must be per recipient token"
        assert self.token_b.token_hash not in key

    def test_the_fourth_request_in_a_minute_is_throttled(self):
        from hub.apps.audit.models import AuditEvent

        before = set(AuditEvent.objects.values_list("id", flat=True))
        throttle = self._throttle()
        request = self._request(self.plaintext_a)
        for _ in range(3):
            assert throttle.allow_request(request, None) is True
        assert throttle.allow_request(request, None) is False, (
            "the 4th request must exhaust the 3/min bucket"
        )
        # The 429 emission (the DRF 3.16 failure branch, the Phase 273
        # contract): exactly ONE rate-limit row for the throttled token,
        # tenant-attributed (the before-set delta — the 4.4 row-set
        # convention, immune to the shared DB's leaked rows).
        emitted = AuditEvent.objects.filter(action="DELTA_SHARE_RATE_LIMIT_EXCEEDED").exclude(
            id__in=before
        )
        assert emitted.count() == 1
        assert str(emitted.first().tenant_id) == str(self.tenant_a.id)
        # The token prefix is PII-shaped — the audit redactor scrubs it
        # (the emission carries it; the stored row redacts it, verified).
        assert emitted.first().details_json.get("token_prefix") == "[REDACTED]"

    def test_tenant_as_exhaustion_never_touches_tenant_b(self):
        throttle_a, throttle_b = self._throttle(), self._throttle()
        request_a = self._request(self.plaintext_a)
        request_b = self._request(self.plaintext_b)
        for _ in range(3):
            throttle_a.allow_request(request_a, None)
        assert throttle_a.allow_request(request_a, None) is False
        assert throttle_b.allow_request(request_b, None) is True, (
            "tenant A's exhausted token bucket must never affect tenant B's quota"
        )

    def test_two_tokens_of_one_tenant_get_independent_buckets(self):
        from hub.apps.databricks_admin.models import DeltaShareToken

        _, other_plaintext = _issue_token(self.recipient_a)
        assert DeltaShareToken.resolve(other_plaintext) is not None
        throttle_1, throttle_2 = self._throttle(), self._throttle()
        request_1 = self._request(self.plaintext_a)
        request_2 = self._request(other_plaintext)
        for _ in range(3):
            throttle_1.allow_request(request_1, None)
        assert throttle_1.allow_request(request_1, None) is False
        assert throttle_2.allow_request(request_2, None) is True, (
            "an exhausted token must not throttle the recipient's other tokens"
        )

    def test_an_unknown_or_missing_token_is_not_throttled_here(self):
        from hub.apps.databricks_admin.throttles import DeltaShareTokenRateThrottle

        throttle = DeltaShareTokenRateThrottle()
        assert throttle.get_cache_key(self._request(f"bogus-{uuid.uuid4().hex}"), None) is None
        assert throttle.get_cache_key(APIRequestFactory().get("/"), None) is None, (
            "a request without a bearer token gets no throttle bucket (the auth layer owns the 401)"
        )
