"""P7 (openspec add-databricks-cost-guardrails task 7.8) — the
property-style pins for the rolling-window arithmetic (the child's
"window arithmetic is pure" contract): invariants over interleaved
record/prune sequences, not single examples.

Every pin runs against the REAL Redis (the shared test cache db 13) —
the arithmetic properties hold for ANY sequence of recordings, the
tenant isolation holds under interleaved multi-tenant writes, and the
TTL discipline holds after every operation.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = pytest.mark.django_db(transaction=True)

_WINDOW = 3600


from hub.apps.databricks_admin.tests._fixtures import redis_13_client

redis_13 = pytest.fixture(autouse=True)(redis_13_client)


def _mk_tenant():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"prop-{uid}",
        slug=f"prop-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


_SEQUENCES = [
    [(Decimal("1"), 1_800_000_000), (Decimal("2"), 1_800_000_100)],
    [(Decimal("5"), 1_700_000_000), (Decimal("3"), 1_800_000_000)],
    [(Decimal("1"), 1_800_000_000), (Decimal("1"), 1_800_000_100), (Decimal("1"), 1_799_999_900)],
    [(Decimal("9"), 1_799_999_999)],
]


class TestWindowArithmeticProperties:
    @pytest.mark.parametrize("sequence", _SEQUENCES)
    def test_the_sum_equals_the_live_entries_for_any_sequence(self, redis_13, sequence):
        from hub.apps.databricks_admin.budget_window import record_units, window_sum

        tenant = _mk_tenant()
        for units, when in sequence:
            record_units(redis_13, str(tenant.id), units=units, now=when)

        last_when = max(when for _units, when in sequence)
        expected = sum(units for units, when in sequence if last_when - when < _WINDOW)
        assert window_sum(redis_13, str(tenant.id), now=last_when) == expected.quantize(
            Decimal("0.000001")
        ), "the sum is always exactly the live entries, never the dead ones"

    def test_zero_units_never_change_the_sum(self, redis_13):
        from hub.apps.databricks_admin.budget_window import record_units, window_sum

        tenant = _mk_tenant()
        record_units(redis_13, str(tenant.id), units=Decimal("3"), now=1_800_000_000)
        before = window_sum(redis_13, str(tenant.id), now=1_800_000_000)
        record_units(redis_13, str(tenant.id), units=Decimal("0"), now=1_800_000_100)
        assert window_sum(redis_13, str(tenant.id), now=1_800_000_100) == before

    def test_the_ttl_stays_within_the_window_after_every_operation(self, redis_13):
        from hub.apps.databricks_admin.budget_window import record_units, window_key, window_sum

        tenant = _mk_tenant()
        record_units(redis_13, str(tenant.id), units=Decimal("1"), now=1_800_000_000)
        window_sum(redis_13, str(tenant.id), now=1_800_000_001)
        ttl = redis_13.ttl(window_key(str(tenant.id)))
        assert 0 < ttl <= _WINDOW, "the key TTL never exceeds the window length"

    def test_interleaved_tenants_keep_exact_per_tenant_sums(self, redis_13):
        from hub.apps.databricks_admin.budget_window import record_units, window_sum

        tenant_a = _mk_tenant()
        tenant_b = _mk_tenant()
        for units, when in [
            (Decimal("2"), 1_800_000_000),
            (Decimal("4"), 1_800_000_010),
            (Decimal("8"), 1_800_000_020),
        ]:
            record_units(redis_13, str(tenant_a.id), units=units, now=when)
            record_units(redis_13, str(tenant_b.id), units=units * 3, now=when)

        assert window_sum(redis_13, str(tenant_a.id), now=1_800_000_030) == Decimal("14.000000")
        assert window_sum(redis_13, str(tenant_b.id), now=1_800_000_030) == Decimal("42.000000"), (
            "interleaved writes never bleed across tenants"
        )
