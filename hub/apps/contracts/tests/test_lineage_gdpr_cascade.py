"""
Phase 228 X (228.X.3 + 228.X.3.4 / REQ-LIN-X-003) — GDPR cascade tests.

Pins the contract for the two operator-driven cascades:

* ``delete_lineage_edges_for_tenant <tenant-id>`` — purges every
  ``LineageEdge`` row for the tenant + every ``LineageEdgeArchive``
  row + every S3 archive blob whose object key prefix matches the
  tenant. Idempotent: a re-run finds nothing.
* ``delete_lineage_edges_for_user <user-id>`` — the spec is narrower
  here: lineage edges aren't user-scoped (they're tenant-scoped)
  but audit rows + ``created_by_run`` markers MAY carry user
  identifiers. We purge those + scrub user-id from any audit rows
  related to lineage emission.

The cascade is destructive; tests use real DB rows + a patched S3
helper at the boundary (``_s3_delete_objects``) so the rest of the
pipeline runs end-to-end.

Spec mandates:

  1. Tenant cascade includes archive-tier rows + S3 archive blobs.
  2. User cascade scrubs user identifiers from lineage audit rows
     (the lineage data itself is tenant-scoped — not deleted).
  3. Both commands are idempotent (re-running on an already-purged
     subject is a no-op + exits 0).
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command
from django.test import TransactionTestCase
from django.utils import timezone


def _create_tenant(prefix: str = "GDPR"):
    from hub.apps.tenants.models import Tenant
    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"{prefix} Co {suffix}", slug=f"{prefix.lower()}-co-{suffix}",
    )


def _create_contract(tenant):
    from hub.apps.contracts.models import Contract
    return Contract.objects.create(
        tenant=tenant, version=1,
        original_spec_type="ODCS", original_spec_version="3.0.2",
        original_format="YAML",
        original_raw=(
            "kind: DataContract\napiVersion: v3.0.2\nid: c\nname: c\n"
            "version: 1.0.0\nstatus: active\n"
        ),
        hub_contract_json={
            "models": [{"name": "m", "fields": [{"name": "id", "type": "string"}]}],
            "schema": {"fields": []},
        },
        normalization_status="NORMALIZED_OK",
        validation_status="VALID",
        status="ACTIVE",
    )


def _create_user_for_tenant(tenant):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create(
        email=f"gdpr-{uuid.uuid4().hex[:6]}@x", tenant=tenant,
    )


def _seed_lineage_state(tenant, *, with_archive=True):
    """Create open + closed LineageEdge rows AND a LineageEdgeArchive
    row that's been exported to S3. Returns the relevant pks."""
    from hub.apps.contracts.models import LineageEdge, LineageEdgeArchive

    src = _create_contract(tenant)
    tgt = _create_contract(tenant)
    open_edge = LineageEdge.objects.create(
        tenant=tenant, source_contract=src, target_contract=tgt,
        edge_type="reference",
    )
    closed_edge = LineageEdge.objects.create(
        tenant=tenant, source_contract=src, target_contract=tgt,
        edge_type="derivation",
    )
    LineageEdge.objects.filter(pk=closed_edge.pk).update(
        valid_to=timezone.now() - timedelta(days=10),
    )

    archive_row = None
    if with_archive:
        archive_row = LineageEdgeArchive.objects.create(
            tenant=tenant,
            original_edge_id=uuid.uuid4(),
            edge_type="reference",
            valid_from=timezone.now() - timedelta(days=400),
            valid_to=timezone.now() - timedelta(days=300),
            exported_to_s3_at=timezone.now() - timedelta(days=200),
            s3_uri="s3://meshant-test-lineage-archive/2024/01/abc.jsonl.gz",
        )

    return {
        "open_edge_id": open_edge.id,
        "closed_edge_id": closed_edge.id,
        "archive_id": archive_row.id if archive_row else None,
        "archive_s3_uri": archive_row.s3_uri if archive_row else None,
    }


@pytest.mark.django_db(transaction=True)
class TestDeleteLineageEdgesForTenant(TransactionTestCase):
    """REQ-LIN-X-003 / 228.X.3.1 — tenant cascade purges every tier."""

    def test_purges_open_and_closed_lineage_edges(self):
        from hub.apps.contracts.models import LineageEdge

        tenant = _create_tenant()
        seed = _seed_lineage_state(tenant)
        # Sibling tenant — its rows MUST survive.
        other = _create_tenant(prefix="GDPR2")
        sibling_seed = _seed_lineage_state(other)

        with mock.patch(
            "hub.apps.contracts.management.commands.delete_lineage_edges_for_tenant._s3_delete_objects"
        ) as s3_del:
            s3_del.return_value = 1
            call_command(
                "delete_lineage_edges_for_tenant",
                f"--tenant={tenant.id}",
                stdout=StringIO(),
            )

        # Target tenant's rows are gone.
        assert not LineageEdge.objects.filter(pk=seed["open_edge_id"]).exists()
        assert not LineageEdge.objects.filter(pk=seed["closed_edge_id"]).exists()
        # Sibling tenant's rows survive.
        assert LineageEdge.objects.filter(pk=sibling_seed["open_edge_id"]).exists()
        assert LineageEdge.objects.filter(pk=sibling_seed["closed_edge_id"]).exists()

    def test_purges_archive_rows_and_s3_blobs(self):
        from hub.apps.contracts.models import LineageEdgeArchive

        tenant = _create_tenant()
        seed = _seed_lineage_state(tenant)

        with mock.patch(
            "hub.apps.contracts.management.commands.delete_lineage_edges_for_tenant._s3_delete_objects"
        ) as s3_del:
            s3_del.return_value = 1
            call_command(
                "delete_lineage_edges_for_tenant",
                f"--tenant={tenant.id}",
                stdout=StringIO(),
            )
            # S3 helper called with the URI the archive row carried.
            calls = [c.kwargs.get("uris") or c.args for c in s3_del.call_args_list]
            assert any(
                seed["archive_s3_uri"] in (uris if isinstance(uris, list) else uris[0])
                for uris in calls
            ), f"S3 delete must be called with the archive URI; got {calls}"

        assert not LineageEdgeArchive.objects.filter(pk=seed["archive_id"]).exists()

    def test_idempotent_rerun(self):
        tenant = _create_tenant()
        _seed_lineage_state(tenant)

        with mock.patch(
            "hub.apps.contracts.management.commands.delete_lineage_edges_for_tenant._s3_delete_objects"
        ) as s3_del:
            s3_del.return_value = 1
            for _ in range(2):
                call_command(
                    "delete_lineage_edges_for_tenant",
                    f"--tenant={tenant.id}",
                    stdout=StringIO(),
                )
        # Second call finds nothing → exit 0.

    def test_unknown_tenant_raises_command_error(self):
        from django.core.management.base import CommandError

        with pytest.raises(CommandError):
            call_command(
                "delete_lineage_edges_for_tenant",
                f"--tenant={uuid.uuid4()}",
                stdout=StringIO(),
            )


@pytest.mark.django_db(transaction=True)
class TestDeleteLineageEdgesForUser(TransactionTestCase):
    """REQ-LIN-X-003 / 228.X.3.2 — user cascade scrubs user
    identifiers from lineage audit rows. The lineage data itself is
    tenant-scoped (NOT deleted by user cascade) — purging it would
    over-delete other users' data in the same tenant."""

    def test_scrubs_user_id_from_lineage_audit_rows(self):
        from hub.apps.audit.models import AuditEvent

        tenant = _create_tenant()
        user = _create_user_for_tenant(tenant)
        # Fabricate an audit row tied to the user.
        AuditEvent.objects.create(
            tenant=tenant,
            actor_user=user,
            resource_type="LINEAGE",
            action="LINEAGE_VIEWED",
            resource_id=str(uuid.uuid4()),
            details={"contract_id": "abc"},
        )

        call_command(
            "delete_lineage_edges_for_user",
            f"--user={user.id}",
            stdout=StringIO(),
        )

        # The audit row survives but actor_user is NULL (scrubbed)
        # so GDPR cascade severs the personal-data link without
        # losing the audit trail.
        scrubbed = AuditEvent.objects.filter(
            tenant=tenant, action="LINEAGE_VIEWED",
        ).first()
        assert scrubbed is not None
        assert scrubbed.actor_user_id is None

    def test_does_not_purge_tenant_lineage_edges(self):
        """Spec — user cascade MUST NOT purge tenant-scoped lineage
        data; only the user's identifying markers."""
        from hub.apps.contracts.models import LineageEdge

        tenant = _create_tenant()
        user = _create_user_for_tenant(tenant)
        seed = _seed_lineage_state(tenant)

        call_command(
            "delete_lineage_edges_for_user",
            f"--user={user.id}",
            stdout=StringIO(),
        )

        # All edges still exist.
        assert LineageEdge.objects.filter(pk=seed["open_edge_id"]).exists()
        assert LineageEdge.objects.filter(pk=seed["closed_edge_id"]).exists()
