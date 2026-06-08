"""Phase 270.C.5.1 — tenant license validation for compliance regulations.

Adds three fields in a single migration so the ``Tenant`` and
``TenantPlan`` changes land atomically (a partial schema state
would mean ``Tenant.licensed_regulation_keys`` exists but the
plan-side seed source ``TenantPlan.includes_regulations`` doesn't,
or vice versa).

* ``TenantPlan.includes_regulations`` — ArrayField of CharField.
  The plan-level default set of licensed regulations. New tenants
  subscribing to this plan get this list copied into
  ``licensed_regulation_keys`` at provisioning time. Pre-existing
  plans get the empty default; ops populates per-tier via the
  Django admin or a follow-up data migration.

* ``Tenant.licensed_regulation_keys`` — ArrayField of CharField.
  The per-tenant authoritative set. Empty list ⇒ check disabled
  (backward-compat for pre-Phase-270.C.5 tenants — the migration's
  empty default means no existing scan starts emitting warnings on
  deploy).

* ``Tenant.strict_license_check`` — BooleanField, default False.
  When True, un-licensed regulations cause an HTTP 422 rejection
  rather than a warning. Default False preserves the lenient
  Phase 19.7.1 semantics for existing tenants; operators opt in
  per-tenant after coordinating with their compliance team.

Why all three fields in one migration
=====================================
The semantic contract is a TRIANGLE: plan defines the default
set, tenant carries the live set, strict flag controls the
enforcement severity. Splitting into three migrations would mean
a deploy could land partial state (e.g. tenant field exists, plan
field doesn't) and the service-layer license check would have to
defensively guard against the missing field. One migration ⇒ one
post-deploy schema state ⇒ simpler service-layer code.
"""
import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0063_phase_270_c_4_compliance_legal_basis_strict"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenantplan",
            name="includes_regulations",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(max_length=64),
                blank=True,
                default=list,
                help_text=(
                    "Phase 270.C.5 — uppercase regulation tokens "
                    "included with this plan tier (e.g. "
                    "``['GDPR', 'PIPL_CN']``). New tenants "
                    "subscribing to this plan get this list "
                    "copied into ``Tenant.licensed_regulation_keys`` "
                    "at provisioning time. Empty list ⇒ no "
                    "plan-level entitlement."
                ),
                size=None,
            ),
        ),
        migrations.AddField(
            model_name="tenant",
            name="licensed_regulation_keys",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(max_length=64),
                blank=True,
                default=list,
                help_text=(
                    "Phase 270.C.5 — uppercase regulation tokens "
                    "this tenant is licensed to scan against "
                    "(e.g. ``['GDPR', 'PIPL_CN']``). Empty list "
                    "disables the check (backward-compat for "
                    "pre-Phase-270.C.5 tenants). Out-of-set "
                    "requests yield REGULATION_NOT_LICENSED "
                    "warnings; strict_license_check elevates the "
                    "warning to an HTTP 422 rejection."
                ),
                size=None,
            ),
        ),
        migrations.AddField(
            model_name="tenant",
            name="strict_license_check",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Phase 270.C.5 — when True, compliance runs "
                    "that request regulations NOT in "
                    "``licensed_regulation_keys`` are REJECTED "
                    "with HTTP 422 REGULATION_NOT_LICENSED. When "
                    "False (default), the un-licensed regulations "
                    "appear as WARNING entries on the run's "
                    "``metadata_json['license_warnings']`` and the "
                    "scan proceeds (Phase 19.7.1 lenient semantics)."
                ),
            ),
        ),
    ]
