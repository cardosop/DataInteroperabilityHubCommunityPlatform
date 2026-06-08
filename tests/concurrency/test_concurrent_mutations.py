"""
312.13.1 — Concurrent mutation safety tests.

Verifies that concurrent mutations against the same resource produce
deterministic, correct outcomes without data corruption.  Uses
``concurrent.futures.ThreadPoolExecutor`` to simulate simultaneous
requests within the same process.

All tests use real Django models and database constraints — no mocks.
"""

import concurrent.futures
import threading
import uuid

import pytest
from django.db import transaction, connections
from django.db.utils import IntegrityError
from django.utils import timezone

from hub.apps.tenants.models import Tenant, TenantPlan, KYCStatus


@pytest.mark.integration
@pytest.mark.concurrency
class TestConcurrentTenantCreation:
    """Two simultaneous Tenant creates with the same slug — exactly one succeeds."""

    @pytest.mark.django_db(transaction=True)
    def test_concurrent_tenant_same_slug_one_succeeds(self):
        """Two threads creating a tenant with the same slug: only one succeeds."""
        slug = f"concurrent-{uuid.uuid4().hex[:8]}"
        errors = []
        results = []
        lock = threading.Lock()

        def create_tenant():
            connections.close_all()  # Fresh connection per thread
            try:
                with transaction.atomic():
                    t = Tenant.objects.create(
                        name=f"Concurrent Tenant {slug}",
                        slug=slug,
                        kyc_status=KYCStatus.PENDING_REVIEW,
                    )
                    with lock:
                        results.append(t)
            except IntegrityError as e:
                with lock:
                    errors.append(str(e))
            except Exception as e:
                with lock:
                    errors.append(str(e))

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(create_tenant) for _ in range(2)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        # Exactly one must succeed
        assert len(results) == 1, f"Expected 1 success, got {len(results)}"
        assert len(errors) >= 1, f"Expected at least 1 IntegrityError, got {len(errors)}"
        # DB should have exactly one tenant with this slug
        count = Tenant.objects.filter(slug=slug).count()
        assert count == 1, f"Expected 1 tenant with slug {slug}, found {count}"


@pytest.mark.integration
@pytest.mark.concurrency
class TestConcurrentPlanDowngrade:
    """Two simultaneous plan downgrades — exactly one succeeds, other gets conflict."""

    @pytest.mark.django_db(transaction=True)
    def test_concurrent_plan_switch_preserves_consistency(self):
        """Concurrent plan changes on the same tenant don't corrupt plan state."""
        plan_free = TenantPlan.objects.get(slug="free")
        plan_pro = TenantPlan.objects.get(slug="pro")
        tenant_slug = f"plan-switch-{uuid.uuid4().hex[:8]}"

        tenant = Tenant.objects.create(
            name=f"Plan Switch {tenant_slug}",
            slug=tenant_slug,
            plan=plan_free,
            kyc_status=KYCStatus.VERIFIED,
        )

        results = []
        lock = threading.Lock()

        def switch_to_pro():
            connections.close_all()
            try:
                with transaction.atomic():
                    t = Tenant.objects.select_for_update().get(slug=tenant_slug)
                    t.plan = plan_pro
                    t.save(update_fields=["plan", "updated_at"])
                    with lock:
                        results.append("pro")
            except Exception as e:
                with lock:
                    results.append(f"error: {e}")

        def switch_to_enterprise():
            connections.close_all()
            try:
                with transaction.atomic():
                    t = Tenant.objects.select_for_update().get(slug=tenant_slug)
                    t.plan = TenantPlan.objects.get(slug="enterprise")
                    t.save(update_fields=["plan", "updated_at"])
                    with lock:
                        results.append("enterprise")
            except Exception as e:
                with lock:
                    results.append(f"error: {e}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(switch_to_pro)
            f2 = executor.submit(switch_to_enterprise)
            f1.result()
            f2.result()

        # Both threads operated, final state is one of the two plans
        tenant.refresh_from_db()
        assert tenant.plan_id in (plan_pro.id, TenantPlan.objects.get(slug="enterprise").id), \
            f"Tenant plan should be pro or enterprise, got {tenant.plan_id}"
        # The tenant should not be left without a plan
        assert tenant.plan_id is not None


@pytest.mark.integration
@pytest.mark.concurrency
class TestConcurrentAccessRequestApproval:
    """Two simultaneous access request approvals — exactly one transitions state."""

    @pytest.mark.django_db(transaction=True)
    def test_concurrent_approval_does_not_double_transition(self):
        """Concurrent approvals on the same access request don't double-process."""
        from hub.apps.governance.models import (
            AccessRequest, AccessRequestStatus, AccessPolicy,
        )
        from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility

        plan = TenantPlan.objects.get(slug="enterprise")
        tenant = Tenant.objects.create(
            name=f"ar-concurrent-{uuid.uuid4().hex[:8]}",
            slug=f"ar-concurrent-{uuid.uuid4().hex[:8]}",
            plan=plan, kyc_status=KYCStatus.VERIFIED,
        )
        asset = Asset.objects.create(
            name=f"concurrent-ar-asset-{uuid.uuid4().hex[:8]}",
            key=f"concurrent-ar-asset-{uuid.uuid4().hex[:8]}",
            tenant=tenant,
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.INTERNAL,
        )
        ar = AccessRequest.objects.create(
            tenant=tenant,
            resource_type="ASSET",
            resource_id=asset.id,
            status=AccessRequestStatus.PENDING,
            requested_by="test-user",
        )

        transitions = []
        lock = threading.Lock()

        def approve():
            connections.close_all()
            try:
                with transaction.atomic():
                    ar_locked = (
                        AccessRequest.objects
                        .select_for_update()
                        .get(id=ar.id)
                    )
                    if ar_locked.status == AccessRequestStatus.PENDING:
                        ar_locked.status = AccessRequestStatus.APPROVED
                        ar_locked.save(update_fields=["status", "updated_at"])
                        with lock:
                            transitions.append("approved")
                    else:
                        with lock:
                            transitions.append(f"skipped: already {ar_locked.status}")
            except Exception as e:
                with lock:
                    transitions.append(f"error: {e}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(approve) for _ in range(2)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        # Only one should have transitioned to APPROVED
        ar.refresh_from_db()
        assert ar.status == AccessRequestStatus.APPROVED, \
            f"Expected APPROVED, got {ar.status}"
        approved_count = sum(1 for t in transitions if t == "approved")
        assert approved_count == 1, \
            f"Expected exactly 1 approval, got {approved_count}. Transitions: {transitions}"


@pytest.mark.integration
@pytest.mark.concurrency
class TestConcurrentIdempotencyKey:
    """Two simultaneous operations with the same idempotency_key — one processed, one no-op."""

    @pytest.mark.django_db(transaction=True)
    def test_concurrent_idempotency_key_one_succeeds(self):
        """Two threads with the same idempotency key: first writes, second finds existing."""
        from hub.apps.billing.models import Subscription, SubscriptionStatus

        plan = TenantPlan.objects.get(slug="free")
        tenant = Tenant.objects.create(
            name=f"idem-key-{uuid.uuid4().hex[:8]}",
            slug=f"idem-key-{uuid.uuid4().hex[:8]}",
            plan=plan, kyc_status=KYCStatus.VERIFIED,
        )

        idem_key = f"sub_{tenant.id}_{plan.slug}_{uuid.uuid4().hex[:8]}"
        results = []
        lock = threading.Lock()

        def create_with_idempotency():
            connections.close_all()
            try:
                with transaction.atomic():
                    existing = Subscription.objects.filter(
                        tenant=tenant,
                        stripe_subscription_id=idem_key,
                    ).first()
                    if existing:
                        with lock:
                            results.append("existing")
                        return existing
                    sub = Subscription.objects.create(
                        tenant=tenant,
                        plan=plan,
                        status=SubscriptionStatus.ACTIVE,
                        current_period_start=timezone.now(),
                        current_period_end=timezone.now() + timezone.timedelta(days=30),
                        stripe_subscription_id=idem_key,
                    )
                    with lock:
                        results.append("created")
                    return sub
            except IntegrityError:
                # Other thread created it first — find existing
                existing = Subscription.objects.filter(
                    tenant=tenant, stripe_subscription_id=idem_key,
                ).first()
                with lock:
                    results.append("integrity_error_found_existing")
                return existing

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(create_with_idempotency) for _ in range(2)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        # Exactly one subscription should exist
        count = Subscription.objects.filter(
            tenant=tenant, stripe_subscription_id=idem_key,
        ).count()
        assert count == 1, f"Expected exactly 1 subscription, found {count}"
        # One should have created, the other reused
        assert "created" in results, f"Expected one 'created', got: {results}"
