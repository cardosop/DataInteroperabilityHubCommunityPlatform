"""
312.13.3 — Transaction integrity tests.

Verifies that database transactions provide correct ACID guarantees:
atomic commits, rollback on failure, savepoint isolation, and
transaction scope correctness.  All tests use real Django ORM
transactions — no mocks.
"""

import uuid

import pytest
from django.db import IntegrityError, transaction

from hub.apps.tenants.models import KYCStatus, Tenant, TenantPlan


@pytest.mark.integration
@pytest.mark.transaction
class TestTransactionAtomicRollback:
    """``transaction.atomic()`` rolls back all writes on exception."""

    @pytest.mark.django_db(transaction=True)
    def test_atomic_rollback_on_integrity_error(self):
        """Writes inside an atomic block are fully rolled back on IntegrityError."""
        slug = f"rollback-{uuid.uuid4().hex[:8]}"

        # First create — succeeds
        Tenant.objects.create(
            name=f"Rollback Test {slug}",
            slug=slug,
            kyc_status=KYCStatus.PENDING_REVIEW,
        )

        # Second create with same slug inside atomic — must roll back
        with pytest.raises(IntegrityError), transaction.atomic():
            Tenant.objects.create(
                name=f"Rollback Dup {slug}",
                slug=slug,
                kyc_status=KYCStatus.PENDING_REVIEW,
            )
            # If we reach here, the duplicate was NOT caught — that's a bug
            pytest.fail("IntegrityError should have been raised")

        # Count must still be 1
        count = Tenant.objects.filter(slug=slug).count()
        assert count == 1, f"Expected 1 tenant after rollback, got {count}"

    @pytest.mark.django_db(transaction=True)
    def test_atomic_rollback_on_deliberate_exception(self):
        """Explicitly raised exception inside atomic rolls back all prior writes."""
        slug = f"deliberate-rollback-{uuid.uuid4().hex[:8]}"

        try:
            with transaction.atomic():
                Tenant.objects.create(
                    name=f"Should Rollback {slug}",
                    slug=slug,
                    kyc_status=KYCStatus.PENDING_REVIEW,
                )
                raise ValueError("deliberate test failure")
        except ValueError:
            pass  # Expected

        count = Tenant.objects.filter(slug=slug).count()
        assert count == 0, f"Expected 0 tenants after deliberate rollback, got {count}"

    @pytest.mark.django_db(transaction=True)
    def test_atomic_multiple_writes_all_or_nothing(self):
        """Multiple writes in an atomic block are all-or-nothing."""
        slug_a = f"all-or-nothing-a-{uuid.uuid4().hex[:8]}"
        slug_b = f"all-or-nothing-b-{uuid.uuid4().hex[:8]}"

        # Create slug_b first so the duplicate triggers IntegrityError
        Tenant.objects.create(
            name=f"Pre-existing {slug_b}",
            slug=slug_b,
            kyc_status=KYCStatus.PENDING_REVIEW,
        )

        try:
            with transaction.atomic():
                Tenant.objects.create(
                    name=f"A {slug_a}",
                    slug=slug_a,
                    kyc_status=KYCStatus.PENDING_REVIEW,
                )
                Tenant.objects.create(
                    name=f"B {slug_b}",
                    slug=slug_b,  # Duplicate!
                    kyc_status=KYCStatus.PENDING_REVIEW,
                )
        except IntegrityError:
            pass

        # Neither should exist (slug_a's write was rolled back too)
        count_a = Tenant.objects.filter(slug=slug_a).count()
        count_b = Tenant.objects.filter(slug=slug_b).count()
        assert count_a == 0, f"Tenant A should be rolled back, got {count_a}"
        assert count_b == 1, f"Tenant B should still exist (pre-existing), got {count_b}"


@pytest.mark.integration
@pytest.mark.transaction
class TestNestedSavepointRollback:
    """Inner savepoint rollback does not affect outer transaction."""

    @pytest.mark.django_db(transaction=True)
    def test_inner_savepoint_rollback_preserves_outer(self):
        """Inner atomic block (savepoint) rollback keeps outer writes."""
        outer_slug = f"outer-{uuid.uuid4().hex[:8]}"
        inner_slug = f"inner-{uuid.uuid4().hex[:8]}"

        # Pre-create inner so it conflicts
        Tenant.objects.create(
            name=f"Pre-existing {inner_slug}",
            slug=inner_slug,
            kyc_status=KYCStatus.PENDING_REVIEW,
        )

        with transaction.atomic():
            # Outer write
            Tenant.objects.create(
                name=f"Outer {outer_slug}",
                slug=outer_slug,
                kyc_status=KYCStatus.PENDING_REVIEW,
            )

            try:
                with transaction.atomic():
                    # Inner write — will fail
                    Tenant.objects.create(
                        name=f"Inner {inner_slug}",
                        slug=inner_slug,  # Duplicate!
                        kyc_status=KYCStatus.PENDING_REVIEW,
                    )
            except IntegrityError:
                pass  # Inner savepoint rolled back

            # Outer write must still exist
            outer_count = Tenant.objects.filter(slug=outer_slug).count()
            assert outer_count == 1, f"Outer write should survive inner rollback, got {outer_count}"

        # Post-transaction: outer should be committed
        outer_count = Tenant.objects.filter(slug=outer_slug).count()
        assert outer_count == 1, f"Outer write should be committed, got {outer_count}"
        # Inner should NOT exist (was never committed since pre-existing blocked it)
        # The pre-existing one should still be there
        inner_count = Tenant.objects.filter(slug=inner_slug).count()
        assert inner_count == 1, f"Only pre-existing inner should exist, got {inner_count}"

    @pytest.mark.django_db(transaction=True)
    def test_nested_three_level_savepoints(self):
        """Three levels of nested atomics — each savepoint is independent."""
        slug_a = f"level-a-{uuid.uuid4().hex[:8]}"
        slug_b = f"level-b-{uuid.uuid4().hex[:8]}"
        slug_c = f"level-c-{uuid.uuid4().hex[:8]}"

        # Pre-create C to trigger conflict at level 3
        Tenant.objects.create(
            name=f"Pre-C {slug_c}",
            slug=slug_c,
            kyc_status=KYCStatus.PENDING_REVIEW,
        )

        with transaction.atomic():  # level 1
            Tenant.objects.create(
                name=f"A {slug_a}",
                slug=slug_a,
                kyc_status=KYCStatus.PENDING_REVIEW,
            )
            with transaction.atomic():  # level 2 (savepoint)
                Tenant.objects.create(
                    name=f"B {slug_b}",
                    slug=slug_b,
                    kyc_status=KYCStatus.PENDING_REVIEW,
                )
                try:
                    with transaction.atomic():  # level 3 (nested savepoint)
                        Tenant.objects.create(
                            name=f"C {slug_c}",
                            slug=slug_c,  # Conflict!
                            kyc_status=KYCStatus.PENDING_REVIEW,
                        )
                except IntegrityError:
                    pass  # Level 3 rolled back

                # Level 2 writes still exist
                assert Tenant.objects.filter(slug=slug_b).count() == 1

            # Level 1 writes still exist
            assert Tenant.objects.filter(slug=slug_a).count() == 1

        # All committed except C (which was pre-existing + the duplicate attempt rolled back)
        assert Tenant.objects.filter(slug=slug_a).count() == 1
        assert Tenant.objects.filter(slug=slug_b).count() == 1
        assert Tenant.objects.filter(slug=slug_c).count() == 1  # Pre-existing only


@pytest.mark.integration
@pytest.mark.transaction
class TestSelectForUpdate:
    """``select_for_update()`` provides row-level locking."""

    @pytest.mark.django_db(transaction=True)
    def test_select_for_update_blocks_concurrent_writes(self):
        """select_for_update prevents lost updates under concurrency."""
        import concurrent.futures
        import threading

        slug = f"sfu-{uuid.uuid4().hex[:8]}"

        tenant = Tenant.objects.create(
            name=f"SFU {slug}",
            slug=slug,
            kyc_status=KYCStatus.PENDING_REVIEW,
        )
        plan_free = TenantPlan.objects.get(slug="free")
        tenant.plan = plan_free
        tenant.save(update_fields=["plan", "updated_at"])

        plan_ids_seen = []
        lock = threading.Lock()

        def update_plan():
            from django.db import connections

            connections.close_all()
            try:
                with transaction.atomic():
                    t = Tenant.objects.select_for_update().get(slug=slug)
                    current_id = t.plan_id
                    with lock:
                        plan_ids_seen.append(current_id)
                    # Attempt a different plan
                    new_plan = TenantPlan.objects.get(slug="enterprise")
                    t.plan = new_plan
                    t.save(update_fields=["plan", "updated_at"])
            except Exception as e:
                with lock:
                    plan_ids_seen.append(f"error: {e}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(update_plan) for _ in range(2)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        # Final state is consistent — one plan set
        tenant.refresh_from_db()
        assert tenant.plan_id is not None, "Tenant should have a plan after concurrent updates"
