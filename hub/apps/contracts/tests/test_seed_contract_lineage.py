"""
Tests for the `seed_contract_lineage` management command.

Covers the five invariants from the plan
(.claude/plans/create-a-comprehensive-and-shimmying-aurora.md):

  1. Empty DB → command creates two contracts (Source + Derived).
  2. Re-run is idempotent: no duplicates.
  3. --dry-run writes nothing.
  4. The derived contract's lineage[].(namespace, name) resolves to the
     Source contract via LineageReference.resolve_contract.
  5. The visualization helper (`generate_lineage_json`) returns a real
     cross-contract `contract_dependency` edge between the two seeded
     contracts.

Plus two safety nets:
  6. --cleanup removes both seeded rows.
  7. Missing tenant / owner → CommandError with actionable message.
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from hub.apps.contracts.lineage import LineageReference, generate_lineage_json
from hub.apps.contracts.management.commands.seed_contract_lineage import (
    DEFAULT_NAMESPACE,
    DERIVED_NAME,
    SOURCE_NAME,
)
from hub.apps.contracts.models import Contract
from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.users.models import User


@pytest.mark.django_db(transaction=True)
class SeedContractLineageCommandTest(TestCase):
    """Driven through `call_command` so the tests exercise the same entry
    point operators use. No mocking — real ORM, real Pydantic validation,
    real lineage traversal."""

    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(
            slug="default",
            name="Default Tenant",
            status=TenantStatus.ACTIVE,
        )
        cls.owner = User.objects.create(
            email="e2e_admin@example.com",
            tenant=cls.tenant,
        )

    def _run(self, *args: str) -> str:
        out = StringIO()
        call_command("seed_contract_lineage", *args, stdout=out)
        return out.getvalue()

    # ---------------------------------------------------------- (1) creates

    def test_creates_two_contracts(self):
        self._run()

        contracts = Contract.objects.filter(tenant=self.tenant).order_by("created_at")
        self.assertEqual(contracts.count(), 2)

        names = sorted(
            (c.hub_contract_json or {}).get("info", {}).get("name") for c in contracts
        )
        self.assertEqual(sorted([SOURCE_NAME, DERIVED_NAME]), names)

        for c in contracts:
            self.assertEqual(c.created_by, self.owner)
            self.assertEqual(c.status, "ACTIVE")
            self.assertEqual(c.normalization_status, "NORMALIZED_OK")
            self.assertEqual(c.validation_status, "VALID")

    # -------------------------------------------------- (2) idempotent rerun

    def test_idempotent_on_rerun(self):
        self._run()
        first_count = Contract.objects.filter(tenant=self.tenant).count()
        self.assertEqual(first_count, 2)

        out = self._run()
        self.assertIn("already exist", out)
        self.assertEqual(Contract.objects.filter(tenant=self.tenant).count(), 2)

    # ---------------------------------------------------- (3) dry-run noop

    def test_dry_run_writes_nothing(self):
        out = self._run("--dry-run")
        self.assertIn("DRY-RUN", out)
        self.assertEqual(Contract.objects.filter(tenant=self.tenant).count(), 0)

    # ---------------------------------------------- (4) lineage resolution

    def test_lineage_reference_resolves_to_source(self):
        self._run()

        # Look up the source as the resolver would, given the namespace+name
        # the derived contract's lineage points at.
        ref = LineageReference(namespace=DEFAULT_NAMESPACE, name=SOURCE_NAME)
        resolved = ref.resolve_contract()

        self.assertIsNotNone(
            resolved,
            "LineageReference(namespace, name) for the seed values must resolve "
            "to the Source contract — confirms the matcher reads info.domain + "
            "info.name correctly.",
        )
        self.assertEqual(
            (resolved.hub_contract_json or {}).get("info", {}).get("name"),
            SOURCE_NAME,
        )

    # ----------------------------------- (5) visualization round-trip edge

    def test_visualization_returns_cross_contract_edge(self):
        self._run()

        derived = Contract.objects.get(
            tenant=self.tenant,
            hub_contract_json__info__name=DERIVED_NAME,
        )
        source = Contract.objects.get(
            tenant=self.tenant,
            hub_contract_json__info__name=SOURCE_NAME,
        )

        viz = generate_lineage_json(derived, max_depth=10)

        # Both contracts represented as nodes
        node_ids = {n["id"] for n in viz.get("nodes", [])}
        self.assertIn(str(source.id), node_ids)
        self.assertIn(str(derived.id), node_ids)

        # The cross-contract dependency edge: source -> derived (downstream).
        # Per _process_lineage_for_visualization at lineage.py:758, type is
        # `contract_dependency` and direction is `downstream` for declared
        # references in hub_contract_json.lineage.contracts.
        deps = [
            link
            for link in viz.get("links", [])
            if link.get("type") == "contract_dependency"
            and link.get("source") == str(source.id)
            and link.get("target") == str(derived.id)
        ]
        self.assertEqual(
            len(deps),
            1,
            f"Expected exactly one contract_dependency edge from source "
            f"({source.id}) to derived ({derived.id}); got links: "
            f"{viz.get('links')}",
        )

    # ---------------------------------------------------- (6) cleanup path

    def test_cleanup_removes_seeded_rows(self):
        self._run()
        self.assertEqual(Contract.objects.filter(tenant=self.tenant).count(), 2)

        out = self._run("--cleanup")
        self.assertIn("Deleted contract", out)
        self.assertEqual(Contract.objects.filter(tenant=self.tenant).count(), 0)

    # --------------------------------------- (7) missing-tenant CommandError

    def test_missing_tenant_raises_command_error(self):
        with self.assertRaises(CommandError) as ctx:
            self._run("--tenant-slug", "no-such-tenant")
        self.assertIn("no-such-tenant", str(ctx.exception))

    def test_missing_owner_raises_command_error(self):
        with self.assertRaises(CommandError) as ctx:
            self._run("--owner-email", "no-such-user@example.com")
        self.assertIn("no-such-user@example.com", str(ctx.exception))

    # -------------------------------------------- (extra) force-recreate

    def test_force_recreate_replaces_existing_rows(self):
        self._run()
        first_ids = set(
            Contract.objects.filter(tenant=self.tenant).values_list("id", flat=True)
        )
        self.assertEqual(len(first_ids), 2)

        self._run("--force-recreate")
        second_ids = set(
            Contract.objects.filter(tenant=self.tenant).values_list("id", flat=True)
        )
        self.assertEqual(len(second_ids), 2)
        # Recreate ⇒ new rows ⇒ disjoint id sets.
        self.assertTrue(first_ids.isdisjoint(second_ids))
