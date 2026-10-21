"""Phase 270.C.4.1 — Tenant.compliance_legal_basis_strict.

Per-tenant flag controlling whether the compliance-service rejects
scans missing a valid GDPR/UK_GDPR/LGPD ``legal_basis`` with HTTP
422 ``LEGAL_BASIS_INVALID`` (strict mode, True) OR returns the
existing ERROR-severity issue in the report and a 200 (lenient,
False — backward-compat with Phase 19.7.1 behaviour).

Backfill semantics
==================
The model field's ``default`` is the callable
``_default_compliance_legal_basis_strict`` which returns True in
production and False in staging/dev. Django evaluates ``default=
callable`` at INSERT time — i.e. for FUTURE rows. For the
EXISTING tenant rows this migration handles via ``add_field``, the
backfill value is False unconditionally (a hard-coded literal in
the migration), so live prod tenants are NOT automatically opted
into strict mode by this deploy. Ops flips per tenant via the
tenant-admin API after coordinating with the tenant's data-owner
about CONSENT / legitimate-interest documentation; new prod
tenants created AFTER this migration get the env-aware default.

This split (literal False for backfill + callable default for new
rows) is deliberate per D-270.9 — flipping every existing prod
tenant to strict mode on deploy would break ANY in-flight scan
that's currently using the lenient path's "WARN + 200" semantics.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0062_phase_270_b_2_access_request_pending_sla_days"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="compliance_legal_basis_strict",
            # Migration-side default is the literal False — see the
            # docstring for the rationale. The model declaration uses
            # a callable default (env-aware) for NEW rows.
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Phase 270.C.4 — when True, compliance scans "
                    "that are missing a valid GDPR/UK_GDPR/LGPD "
                    "legal_basis are rejected with HTTP 422 "
                    "LEGAL_BASIS_INVALID. When False (default in "
                    "staging/dev), the scan succeeds with an "
                    "ERROR-severity issue in the report. Env-aware "
                    "default: True in production, False otherwise."
                ),
            ),
        ),
    ]
