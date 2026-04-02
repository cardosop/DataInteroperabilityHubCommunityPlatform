"""
Phase 19.15 Tests — Data Migrations

Covers:
  19.15.1  Migration 0015_normalise_regulation_keys: normalises legacy regulation
           key aliases in Contract.hub_contract_json.privacy_compliance.jurisdictions
           to canonical forms (e.g. "PIPL" → "PIPL_CN").

  19.15.2  Management command migrate_compliance_runs_v2: idempotent backfill of
           cross_border_alert, localisation_alert, and legal_basis_violations on
           ComplianceRun rows that have regulation_mapping_json but null v2 fields.

Design principles:
  - Real database: no mocks or stubs.
  - Functions tested directly (migration function via importlib) so the tests
    remain valid even after the Django migration itself is recorded as applied.
  - All assertions target behaviour, not implementation details.
"""

import importlib.util
import uuid
from io import StringIO
from pathlib import Path

import pytest
from django.apps import apps as django_apps
from django.core.management import call_command
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.contracts.models import Contract, ContractStatus, OriginalFormat, OriginalSpecType
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)

# ---------------------------------------------------------------------------
# Helpers — shared infrastructure
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # .../DataInteroperabilityHub/hub/../../ = project root


def _make_tenant(suffix=None):
    slug = f"t19-15-{uuid.uuid4().hex[:8]}{'-' + suffix if suffix else ''}"
    return Tenant.objects.create(name=f"Tenant {slug}", slug=slug)


def _make_user(tenant):
    email = f"u-{uuid.uuid4().hex[:8]}@phase1915.test"
    user = User.objects.create_user(
        email=email, password="P@ssw0rd!", tenant=tenant, status=UserStatus.ACTIVE
    )
    return user


def _make_asset(tenant, user):
    return Asset.objects.create(
        tenant=tenant,
        key=f"asset-{uuid.uuid4().hex[:8]}",
        name="Test Asset",
        status=AssetStatus.ACTIVE,
        created_by=user,
    )


def _make_job(tenant, asset):
    return Job.objects.create(
        tenant=tenant,
        type=JobType.COMPLIANCE_RUN,
        status=JobStatus.PENDING,
        resource_type="ASSET",
        resource_id=asset.id,
    )


def _make_compliance_run(tenant, asset, job, **overrides):
    """Create a ComplianceRun.  save() calls full_clean() which requires asset/dataset/file."""
    defaults = dict(
        tenant=tenant,
        asset=asset,
        job=job,
        status=ComplianceRunStatus.SUCCEEDED,
    )
    defaults.update(overrides)
    run = ComplianceRun(**defaults)
    # Bypass full_clean for fields set via overrides so we can set arbitrary JSON.
    run.save()
    return run


def _make_contract(tenant, hub_contract_json=None):
    """
    Create a Contract row.  Contract.save() validates hub_contract_json structure,
    so we create with null JSON and then use .update() (bypasses clean()) to inject
    test data with alias regulation keys.
    """
    c = Contract(
        tenant=tenant,
        version=1,
        status=ContractStatus.DRAFT,
        original_spec_type=OriginalSpecType.ODCS,
        original_spec_version="3.0.2",
        original_format=OriginalFormat.JSON,
        original_raw='{"id": "test", "name": "Test"}',
        hub_contract_json=None,
    )
    # Save without calling full_clean (hub_contract_json is null here → passes)
    Contract.objects.bulk_create([c])
    if hub_contract_json is not None:
        # Use queryset update to set arbitrary JSON without model-level validation.
        Contract.objects.filter(id=c.id).update(hub_contract_json=hub_contract_json)
        c.refresh_from_db()
    return c


def _load_migration_function(app_label: str, migration_filename: str, func_name: str):
    """
    Load a RunPython function from a migration file by path (avoids the Python
    identifier restriction for module names that start with a digit).
    """
    migrations_dir = (
        _PROJECT_ROOT / "hub" / "apps" / app_label / "migrations"
    )
    path = migrations_dir / migration_filename
    spec = importlib.util.spec_from_file_location(f"_migration_{app_label}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, func_name)


def _run_normalise_regulation_keys():
    """Call the migration function against the live test database."""
    fn = _load_migration_function(
        "contracts", "0015_normalise_regulation_keys.py", "normalise_regulation_keys"
    )
    fn(django_apps, None)


# ---------------------------------------------------------------------------
# 19.15.1 — Migration 0015: normalise_regulation_keys
# ---------------------------------------------------------------------------


class TestNormaliseRegulationKeysMigration(TestCase):
    """
    Tests for hub/apps/contracts/migrations/0015_normalise_regulation_keys.py

    The migration function is called directly via importlib so these tests work
    regardless of whether the migration has been recorded as applied in the
    test database.
    """

    def setUp(self):
        self.tenant = _make_tenant("mig")

    # --- Core alias normalisation -------------------------------------------

    def test_pipl_normalised_to_pipl_cn(self):
        """'PIPL' → 'PIPL_CN'"""
        c = _make_contract(
            self.tenant,
            hub_contract_json={
                "privacy_compliance": {"jurisdictions": ["PIPL"]}
            },
        )
        _run_normalise_regulation_keys()
        c.refresh_from_db()
        self.assertEqual(
            c.hub_contract_json["privacy_compliance"]["jurisdictions"], ["PIPL_CN"]
        )

    def test_pipl_china_normalised_to_pipl_cn(self):
        """'PIPL_CHINA' → 'PIPL_CN'"""
        c = _make_contract(
            self.tenant,
            hub_contract_json={
                "privacy_compliance": {"jurisdictions": ["PIPL_CHINA"]}
            },
        )
        _run_normalise_regulation_keys()
        c.refresh_from_db()
        self.assertEqual(
            c.hub_contract_json["privacy_compliance"]["jurisdictions"], ["PIPL_CN"]
        )

    def test_ccpa_cpra_underscore_normalised_to_ccpa(self):
        """'CCPA_CPRA' → 'CCPA'"""
        c = _make_contract(
            self.tenant,
            hub_contract_json={
                "privacy_compliance": {"jurisdictions": ["CCPA_CPRA"]}
            },
        )
        _run_normalise_regulation_keys()
        c.refresh_from_db()
        self.assertEqual(
            c.hub_contract_json["privacy_compliance"]["jurisdictions"], ["CCPA"]
        )

    def test_ccpa_cpra_slash_normalised_to_ccpa(self):
        """'CCPA/CPRA' → 'CCPA'"""
        c = _make_contract(
            self.tenant,
            hub_contract_json={
                "privacy_compliance": {"jurisdictions": ["CCPA/CPRA"]}
            },
        )
        _run_normalise_regulation_keys()
        c.refresh_from_db()
        self.assertEqual(
            c.hub_contract_json["privacy_compliance"]["jurisdictions"], ["CCPA"]
        )

    def test_privacy_act_normalised_to_privacy_act_au(self):
        """'PRIVACY_ACT' → 'PRIVACY_ACT_AU'"""
        c = _make_contract(
            self.tenant,
            hub_contract_json={
                "privacy_compliance": {"jurisdictions": ["PRIVACY_ACT"]}
            },
        )
        _run_normalise_regulation_keys()
        c.refresh_from_db()
        self.assertEqual(
            c.hub_contract_json["privacy_compliance"]["jurisdictions"],
            ["PRIVACY_ACT_AU"],
        )

    def test_all_aliases_normalised_in_single_contract(self):
        """All five alias variants in one jurisdictions list → all normalised."""
        c = _make_contract(
            self.tenant,
            hub_contract_json={
                "privacy_compliance": {
                    "jurisdictions": ["PIPL", "PIPL_CHINA", "CCPA_CPRA", "CCPA/CPRA", "PRIVACY_ACT"]
                }
            },
        )
        _run_normalise_regulation_keys()
        c.refresh_from_db()
        result = c.hub_contract_json["privacy_compliance"]["jurisdictions"]
        self.assertIn("PIPL_CN", result)
        self.assertIn("CCPA", result)
        self.assertIn("PRIVACY_ACT_AU", result)
        self.assertNotIn("PIPL", result)
        self.assertNotIn("PIPL_CHINA", result)
        self.assertNotIn("CCPA_CPRA", result)
        self.assertNotIn("CCPA/CPRA", result)
        self.assertNotIn("PRIVACY_ACT", result)

    # --- Canonical keys pass through unchanged ------------------------------

    def test_canonical_gdpr_unchanged(self):
        c = _make_contract(
            self.tenant,
            hub_contract_json={"privacy_compliance": {"jurisdictions": ["GDPR"]}},
        )
        _run_normalise_regulation_keys()
        c.refresh_from_db()
        self.assertEqual(
            c.hub_contract_json["privacy_compliance"]["jurisdictions"], ["GDPR"]
        )

    def test_canonical_pipl_cn_unchanged(self):
        c = _make_contract(
            self.tenant,
            hub_contract_json={"privacy_compliance": {"jurisdictions": ["PIPL_CN"]}},
        )
        _run_normalise_regulation_keys()
        c.refresh_from_db()
        self.assertEqual(
            c.hub_contract_json["privacy_compliance"]["jurisdictions"], ["PIPL_CN"]
        )

    def test_mixed_canonical_and_alias(self):
        """Canonical keys preserved; alias keys normalised."""
        c = _make_contract(
            self.tenant,
            hub_contract_json={
                "privacy_compliance": {"jurisdictions": ["GDPR", "PIPL", "CCPA_CPRA"]}
            },
        )
        _run_normalise_regulation_keys()
        c.refresh_from_db()
        result = c.hub_contract_json["privacy_compliance"]["jurisdictions"]
        self.assertIn("GDPR", result)
        self.assertIn("PIPL_CN", result)
        self.assertIn("CCPA", result)
        self.assertNotIn("PIPL", result)
        self.assertNotIn("CCPA_CPRA", result)

    def test_unknown_key_passed_through_unchanged(self):
        """Keys not in the alias map and not canonical are preserved as-is."""
        c = _make_contract(
            self.tenant,
            hub_contract_json={
                "privacy_compliance": {"jurisdictions": ["MYSTERY_REG_2099"]}
            },
        )
        _run_normalise_regulation_keys()
        c.refresh_from_db()
        self.assertEqual(
            c.hub_contract_json["privacy_compliance"]["jurisdictions"],
            ["MYSTERY_REG_2099"],
        )

    # --- Edge cases: contracts that should NOT be modified ------------------

    def test_contract_with_null_hub_contract_json_not_touched(self):
        """Contracts with null hub_contract_json are skipped entirely."""
        c = _make_contract(self.tenant, hub_contract_json=None)
        _run_normalise_regulation_keys()
        c.refresh_from_db()
        self.assertIsNone(c.hub_contract_json)

    def test_contract_without_privacy_compliance_key_not_modified(self):
        """hub_contract_json lacking privacy_compliance key is untouched."""
        original = {"some_other_key": {"data": "value"}}
        c = _make_contract(self.tenant, hub_contract_json=original)
        _run_normalise_regulation_keys()
        c.refresh_from_db()
        self.assertEqual(c.hub_contract_json, original)

    def test_contract_with_empty_jurisdictions_not_modified(self):
        """An empty jurisdictions list produces no update."""
        original = {"privacy_compliance": {"jurisdictions": []}}
        c = _make_contract(self.tenant, hub_contract_json=original)
        _run_normalise_regulation_keys()
        c.refresh_from_db()
        self.assertEqual(c.hub_contract_json, original)

    def test_contract_with_non_list_jurisdictions_not_modified(self):
        """jurisdictions that is not a list is skipped gracefully."""
        original = {"privacy_compliance": {"jurisdictions": "GDPR"}}  # string, not list
        c = _make_contract(self.tenant, hub_contract_json=original)
        _run_normalise_regulation_keys()
        c.refresh_from_db()
        self.assertEqual(c.hub_contract_json, original)

    def test_contract_with_all_canonical_keys_not_modified(self):
        """
        A contract where all jurisdictions are already canonical should NOT be
        added to the bulk_update batch (idempotency check inside migration).
        """
        original = {"privacy_compliance": {"jurisdictions": ["GDPR", "CCPA", "PIPL_CN"]}}
        c = _make_contract(self.tenant, hub_contract_json=original)
        # Track updated_at to verify no DB write occurred.
        before_updated = Contract.objects.filter(id=c.id).values_list("updated_at", flat=True).first()
        _run_normalise_regulation_keys()
        after_updated = Contract.objects.filter(id=c.id).values_list("updated_at", flat=True).first()
        # updated_at is auto_now — it changes on every save/bulk_update.
        # If no bulk_update happened, it stays the same.
        self.assertEqual(before_updated, after_updated, "Row was needlessly updated")

    # --- Idempotency --------------------------------------------------------

    def test_idempotent_running_twice_produces_same_result(self):
        """Running the migration function twice leaves the data unchanged."""
        c = _make_contract(
            self.tenant,
            hub_contract_json={"privacy_compliance": {"jurisdictions": ["PIPL", "CCPA_CPRA"]}},
        )
        _run_normalise_regulation_keys()
        c.refresh_from_db()
        after_first = c.hub_contract_json.copy()

        _run_normalise_regulation_keys()
        c.refresh_from_db()
        after_second = c.hub_contract_json.copy()

        self.assertEqual(after_first, after_second)

    def test_idempotent_second_run_does_not_update_canonical_contract(self):
        """After first run, canonical contracts are skipped on second run."""
        c = _make_contract(
            self.tenant,
            hub_contract_json={"privacy_compliance": {"jurisdictions": ["PIPL"]}},
        )
        _run_normalise_regulation_keys()
        c.refresh_from_db()
        self.assertEqual(c.hub_contract_json["privacy_compliance"]["jurisdictions"], ["PIPL_CN"])

        # Second run: row is now canonical, must not be rewritten.
        updated_before = Contract.objects.filter(id=c.id).values_list("updated_at", flat=True).first()
        _run_normalise_regulation_keys()
        updated_after = Contract.objects.filter(id=c.id).values_list("updated_at", flat=True).first()
        self.assertEqual(updated_before, updated_after)

    # --- Multiple contracts in one pass -------------------------------------

    def test_multiple_contracts_all_normalised_in_single_pass(self):
        """All contracts with alias keys are normalised in one migration call."""
        c1 = _make_contract(
            self.tenant,
            hub_contract_json={"privacy_compliance": {"jurisdictions": ["PIPL"]}},
        )
        c2 = _make_contract(
            self.tenant,
            hub_contract_json={"privacy_compliance": {"jurisdictions": ["CCPA_CPRA"]}},
        )
        c3 = _make_contract(
            self.tenant,
            hub_contract_json={"privacy_compliance": {"jurisdictions": ["GDPR"]}},  # canonical
        )
        _run_normalise_regulation_keys()
        c1.refresh_from_db()
        c2.refresh_from_db()
        c3.refresh_from_db()
        self.assertEqual(c1.hub_contract_json["privacy_compliance"]["jurisdictions"], ["PIPL_CN"])
        self.assertEqual(c2.hub_contract_json["privacy_compliance"]["jurisdictions"], ["CCPA"])
        self.assertEqual(c3.hub_contract_json["privacy_compliance"]["jurisdictions"], ["GDPR"])

    # --- Alias map consistency check ----------------------------------------

    def test_migration_alias_map_matches_contract_integration_source(self):
        """
        The alias map inlined in the migration must be identical to the live
        REGULATION_KEY_ALIASES in hub.apps.compliance.contract_integration.
        """
        from hub.apps.compliance.contract_integration import REGULATION_KEY_ALIASES as live_map

        migration_mod = _load_migration_function.__module__  # unused, just to ensure path works
        fn = _load_migration_function("contracts", "0015_normalise_regulation_keys.py", "normalise_regulation_keys")
        # The module is loaded; fetch the alias dict from it.
        spec = importlib.util.spec_from_file_location(
            "_mig0015",
            _PROJECT_ROOT / "hub" / "apps" / "contracts" / "migrations" / "0015_normalise_regulation_keys.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        migration_map = mod._REGULATION_KEY_ALIASES

        self.assertEqual(
            migration_map,
            live_map,
            "Migration alias map diverged from contract_integration.REGULATION_KEY_ALIASES",
        )


# ---------------------------------------------------------------------------
# 19.15.2 — Management command: migrate_compliance_runs_v2
# ---------------------------------------------------------------------------


class TestMigrateComplianceRunsV2Command(TestCase):
    """
    Tests for hub/apps/compliance/management/commands/migrate_compliance_runs_v2.py

    Uses Django's call_command() to invoke the command against the real database.
    """

    def setUp(self):
        self.tenant = _make_tenant("cmd")
        self.user = _make_user(self.tenant)
        self.asset = _make_asset(self.tenant, self.user)
        self.job = _make_job(self.tenant, self.asset)

    def _call(self, *args, **kwargs) -> str:
        """Run the management command, return stdout as a string."""
        out = StringIO()
        call_command("migrate_compliance_runs_v2", *args, stdout=out, **kwargs)
        return out.getvalue()

    def _make_run(self, regulation_mapping_json=None, **v2_overrides):
        """
        Create a ComplianceRun with regulation_mapping_json set.
        v2_overrides allows pre-setting cross_border_alert etc. for idempotency tests.
        """
        # Create with save() bypass for regulation_mapping_json
        run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.SUCCEEDED,
        )
        update_fields = {}
        if regulation_mapping_json is not None:
            update_fields["regulation_mapping_json"] = regulation_mapping_json
        update_fields.update(v2_overrides)
        if update_fields:
            ComplianceRun.objects.filter(id=run.id).update(**update_fields)
            run.refresh_from_db()
        return run

    # --- Basic backfill correctness -----------------------------------------

    def test_cross_border_alert_set_when_gdpr_present(self):
        """GDPR in regulation_mapping_json → cross_border_alert.applicable=True."""
        run = self._make_run({"GDPR": {"applied": True}, "schema_version": "2.0"})
        self._call()
        run.refresh_from_db()
        self.assertIsNotNone(run.cross_border_alert)
        self.assertTrue(run.cross_border_alert["applicable"])
        self.assertIn("GDPR", run.cross_border_alert["applicable_regulations"])
        self.assertTrue(run.cross_border_alert["requires_safeguards"])

    def test_cross_border_alert_set_for_all_cross_border_regulations(self):
        """Each of the five cross-border regulation keys triggers the alert."""
        cross_border_keys = ["GDPR", "GDPR_SCHREMS_II", "UK_GDPR", "PIPL_CN", "LGPD"]
        for key in cross_border_keys:
            with self.subTest(regulation=key):
                run = self._make_run({key: {"applied": True}})
                self._call()
                run.refresh_from_db()
                self.assertTrue(
                    run.cross_border_alert["applicable"],
                    f"{key} should trigger cross_border_alert",
                )
                self.assertIn(key, run.cross_border_alert["applicable_regulations"])

    def test_localisation_alert_set_when_pipl_cn_present(self):
        """PIPL_CN in regulation_mapping_json → localisation_alert.applicable=True."""
        run = self._make_run({"PIPL_CN": {"applied": True}})
        self._call()
        run.refresh_from_db()
        self.assertIsNotNone(run.localisation_alert)
        self.assertTrue(run.localisation_alert["applicable"])
        self.assertIn("PIPL_CN", run.localisation_alert["applicable_regulations"])
        self.assertTrue(run.localisation_alert["strict_localisation"])

    def test_localisation_alert_set_for_all_localisation_regulations(self):
        """Each of the three localisation regulation keys triggers the alert."""
        localisation_keys = ["PIPL_CN", "PDPA_SG", "DPDP_IN"]
        for key in localisation_keys:
            with self.subTest(regulation=key):
                run = self._make_run({key: {"applied": True}})
                self._call()
                run.refresh_from_db()
                self.assertTrue(
                    run.localisation_alert["applicable"],
                    f"{key} should trigger localisation_alert",
                )

    def test_both_alerts_applicable_when_both_types_present(self):
        """GDPR (cross-border) + PIPL_CN (localisation) → both alerts applicable."""
        run = self._make_run({"GDPR": {"applied": True}, "PIPL_CN": {"applied": True}})
        self._call()
        run.refresh_from_db()
        self.assertTrue(run.cross_border_alert["applicable"])
        self.assertTrue(run.localisation_alert["applicable"])

    def test_neither_alert_applicable_for_non_alert_regulation(self):
        """HIPAA alone → both alerts have applicable=False."""
        run = self._make_run({"HIPAA": {"applied": True}})
        self._call()
        run.refresh_from_db()
        self.assertFalse(run.cross_border_alert["applicable"])
        self.assertFalse(run.localisation_alert["applicable"])
        self.assertEqual(run.cross_border_alert["applicable_regulations"], [])
        self.assertEqual(run.localisation_alert["applicable_regulations"], [])

    def test_legal_basis_violations_always_empty_list(self):
        """legal_basis_violations is always [] for backfilled rows."""
        run = self._make_run({"GDPR": {"applied": True}})
        self._call()
        run.refresh_from_db()
        self.assertEqual(run.legal_basis_violations, [])

    def test_backfilled_marker_present_in_cross_border_alert(self):
        """Derived cross_border_alert carries 'backfilled': True."""
        run = self._make_run({"GDPR": {"applied": True}})
        self._call()
        run.refresh_from_db()
        self.assertTrue(run.cross_border_alert.get("backfilled"))

    def test_backfilled_marker_present_in_localisation_alert(self):
        """Derived localisation_alert carries 'backfilled': True."""
        run = self._make_run({"PIPL_CN": {"applied": True}})
        self._call()
        run.refresh_from_db()
        self.assertTrue(run.localisation_alert.get("backfilled"))

    # --- Structural key exclusion ------------------------------------------

    def test_structural_keys_excluded_from_regulation_detection(self):
        """
        Keys like 'metering', 'error', 'schema_version', 'regulation_summary',
        'metadata' must NOT be treated as regulation entries.
        """
        run = self._make_run({
            "metering": {"tokens": 100},
            "schema_version": "2.0",
            "regulation_summary": {"total": 0},
            "metadata": {"source": "v1"},
            "error": None,            # non-dict value → also filtered out
        })
        self._call()
        run.refresh_from_db()
        # No actual regulations present → both alerts not applicable
        self.assertFalse(run.cross_border_alert["applicable"])
        self.assertFalse(run.localisation_alert["applicable"])
        self.assertEqual(run.cross_border_alert["applicable_regulations"], [])

    def test_non_dict_values_in_regulation_mapping_not_counted(self):
        """
        Only dict-valued keys (actual regulation entries) count; scalar / None
        values under non-structural keys should also be excluded.
        """
        run = self._make_run({
            "GDPR": "some-string-not-a-dict",   # string value → not a regulation entry
            "LGPD": None,                         # None value → not a regulation entry
        })
        self._call()
        run.refresh_from_db()
        self.assertFalse(run.cross_border_alert["applicable"])

    # --- Rows that should NOT be processed ----------------------------------

    def test_run_with_null_regulation_mapping_json_not_eligible(self):
        """Rows without regulation_mapping_json are not processed."""
        run = self._make_run(regulation_mapping_json=None)
        out = self._call()
        run.refresh_from_db()
        self.assertIsNone(run.cross_border_alert)
        self.assertIsNone(run.localisation_alert)
        self.assertIsNone(run.legal_basis_violations)

    def test_run_where_all_v2_fields_already_populated_is_skipped(self):
        """Rows where all three v2 fields are already set are not touched."""
        existing_alert = {"applicable": False, "applicable_regulations": [], "backfilled": False}
        run = self._make_run(
            regulation_mapping_json={"GDPR": {"applied": True}},
            cross_border_alert=existing_alert,
            localisation_alert=existing_alert,
            legal_basis_violations=["violation_1"],
        )
        out = self._call()
        run.refresh_from_db()
        # Should remain as set (not overwritten with derived backfill)
        self.assertEqual(run.cross_border_alert, existing_alert)
        self.assertEqual(run.legal_basis_violations, ["violation_1"])

    def test_run_with_non_dict_regulation_mapping_json_skipped(self):
        """
        Rows where regulation_mapping_json is a list (unexpected shape) are
        skipped rather than corrupted.
        """
        run = self._make_run(regulation_mapping_json=None)
        # Force a list value directly at the DB layer.
        ComplianceRun.objects.filter(id=run.id).update(regulation_mapping_json=["GDPR", "LGPD"])
        run.refresh_from_db()

        self._call()
        run.refresh_from_db()
        # v2 fields must remain null (skipped, not corrupted)
        self.assertIsNone(run.cross_border_alert)
        self.assertIsNone(run.legal_basis_violations)

    # --- Field-level idempotency (partial population) ----------------------

    def test_already_populated_cross_border_alert_not_overwritten(self):
        """cross_border_alert set before command → must not be overwritten."""
        preset = {"applicable": False, "applicable_regulations": [], "custom": "preserved"}
        run = self._make_run(
            regulation_mapping_json={"GDPR": {"applied": True}},
            cross_border_alert=preset,
        )
        self._call()
        run.refresh_from_db()
        self.assertEqual(run.cross_border_alert, preset)
        # But other null fields should be populated
        self.assertIsNotNone(run.localisation_alert)
        self.assertIsNotNone(run.legal_basis_violations)

    def test_already_populated_legal_basis_violations_not_overwritten(self):
        """legal_basis_violations set before command → must not be overwritten."""
        preset = [{"violation": "existing_violation"}]
        run = self._make_run(
            regulation_mapping_json={"PIPL_CN": {"applied": True}},
            legal_basis_violations=preset,
        )
        self._call()
        run.refresh_from_db()
        self.assertEqual(run.legal_basis_violations, preset)

    # --- --dry-run ----------------------------------------------------------

    def test_dry_run_does_not_modify_database(self):
        """--dry-run outputs what would be changed but commits nothing."""
        run = self._make_run({"GDPR": {"applied": True}})
        out = self._call("--dry-run")
        run.refresh_from_db()
        # All v2 fields must remain null
        self.assertIsNone(run.cross_border_alert)
        self.assertIsNone(run.localisation_alert)
        self.assertIsNone(run.legal_basis_violations)
        self.assertIn("DRY RUN", out)

    def test_dry_run_output_reports_eligible_count(self):
        """--dry-run stdout reports the number of rows found."""
        self._make_run({"GDPR": {"applied": True}})
        self._make_run({"LGPD": {"applied": True}})
        out = self._call("--dry-run")
        # Should mention at least 2 rows (may include other test rows in DB)
        self.assertIn("row(s)", out)

    # --- Full idempotency (two complete runs) -------------------------------

    def test_second_run_finds_zero_eligible_rows(self):
        """
        After the command completes successfully, running it again must find
        zero eligible rows (all v2 fields are now populated).
        """
        self._make_run({"GDPR": {"applied": True}})
        self._call()  # first pass: backfills
        out = self._call()  # second pass: should find 0 eligible
        self.assertIn("Nothing to do", out)

    # --- --batch-size option ------------------------------------------------

    def test_batch_size_option_accepted_and_backfills_correctly(self):
        """--batch-size=1 processes one row at a time; all rows still backfilled."""
        run1 = self._make_run({"GDPR": {"applied": True}})
        run2 = self._make_run({"PIPL_CN": {"applied": True}})
        self._call("--batch-size", "1")
        run1.refresh_from_db()
        run2.refresh_from_db()
        self.assertIsNotNone(run1.cross_border_alert)
        self.assertIsNotNone(run2.localisation_alert)

    def test_batch_size_zero_raises_error(self):
        """--batch-size 0 must raise CommandError (not a valid batch size)."""
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            self._call("--batch-size", "0")

    # --- Applicable_regulations list is sorted ------------------------------

    def test_applicable_regulations_list_is_sorted(self):
        """
        The applicable_regulations list in cross_border_alert should be sorted
        to produce deterministic output.
        """
        run = self._make_run({
            "UK_GDPR": {"applied": True},
            "GDPR": {"applied": True},
            "LGPD": {"applied": True},
        })
        self._call()
        run.refresh_from_db()
        regs = run.cross_border_alert["applicable_regulations"]
        self.assertEqual(regs, sorted(regs))

    # --- Command output messages -------------------------------------------

    def test_output_reports_updated_count(self):
        """Command stdout reports how many rows were updated."""
        self._make_run({"GDPR": {"applied": True}})
        out = self._call()
        self.assertIn("Updated", out)

    def test_output_reports_processed_count(self):
        """Command stdout reports how many rows were processed."""
        self._make_run({"GDPR": {"applied": True}})
        out = self._call()
        self.assertIn("Processed", out)

    # --- _derive_v2_fields unit test (internal helper) ---------------------

    def test_derive_v2_fields_cross_border_and_localisation_overlap(self):
        """
        PIPL_CN is in both _CROSS_BORDER_REGS and _LOCALISATION_REGS —
        it should appear in both alert lists.
        """
        from hub.apps.compliance.management.commands.migrate_compliance_runs_v2 import (
            _derive_v2_fields,
        )

        result = _derive_v2_fields({"PIPL_CN": {"applied": True}})
        self.assertTrue(result["cross_border_alert"]["applicable"])
        self.assertIn("PIPL_CN", result["cross_border_alert"]["applicable_regulations"])
        self.assertTrue(result["localisation_alert"]["applicable"])
        self.assertIn("PIPL_CN", result["localisation_alert"]["applicable_regulations"])

    def test_derive_v2_fields_empty_mapping_returns_false_alerts(self):
        """Empty regulation_mapping_json → both alerts not applicable."""
        from hub.apps.compliance.management.commands.migrate_compliance_runs_v2 import (
            _derive_v2_fields,
        )

        result = _derive_v2_fields({})
        self.assertFalse(result["cross_border_alert"]["applicable"])
        self.assertFalse(result["localisation_alert"]["applicable"])
        self.assertEqual(result["legal_basis_violations"], [])

    def test_derive_v2_fields_only_structural_keys_returns_false_alerts(self):
        """regulation_mapping_json with only structural keys → no alerts applicable."""
        from hub.apps.compliance.management.commands.migrate_compliance_runs_v2 import (
            _derive_v2_fields,
        )

        result = _derive_v2_fields({
            "metering": {"tokens": 50},
            "schema_version": "2.0",
            "regulation_summary": {},
        })
        self.assertFalse(result["cross_border_alert"]["applicable"])
        self.assertFalse(result["localisation_alert"]["applicable"])
