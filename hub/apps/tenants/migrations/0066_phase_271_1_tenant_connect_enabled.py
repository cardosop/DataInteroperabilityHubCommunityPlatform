"""Phase 271.1.2 — ``Tenant.connect_enabled`` per-tenant Stripe Connect gate.

When True, the tenant has access to the Stripe Connect onboarding
endpoints (POST /api/v1/billing/connect/onboarding-link/, GET
/api/v1/billing/connect/status/) AND the KYB gate at listing-
publish time enforces a verified ConnectAccount for paid listings.
When False, the endpoints return HTTP 501 ``connect_not_enabled``
and the KYB gate is bypassed — preserving pre-Phase-271 behaviour.

Backfill semantics
==================
The model field's ``default`` is the callable
``_default_connect_enabled`` which returns True unconditionally
(env-INDEPENDENT — Connect is opt-in everywhere). Django
evaluates ``default=callable`` at INSERT time — i.e. for FUTURE
rows. For the EXISTING tenant rows this migration handles via
``add_field``, the backfill value is **False unconditionally**
(a hard-coded literal in the migration), so live prod tenants
are NOT automatically opted into Connect on deploy day. They go
through the 30-day notice + opt-out window per D-271.4 + the
same rollout-discipline shape Phase 250.1.A.8 set for
``compliance_fail_closed_enabled`` and Phase 270.C.4.1 set for
``compliance_legal_basis_strict``.

This split (literal False for backfill + callable default for new
rows) is deliberate. Flipping every existing prod tenant to
``connect_enabled=True`` on deploy would (a) expose them to the
KYB gate before they've completed Stripe onboarding and (b)
suddenly enable an external dependency (Stripe Connect API) for
tenants who never opted in. The two-stage rollout — migration
ships False, ops/tenant flips True after a 30-day notice — is
the established platform pattern for an external-dependency opt-in.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0065_phase_270_d_1_tenant_tax_identity"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="connect_enabled",
            # Literal False at the migration boundary — see the
            # docstring for the rationale. The model declaration
            # uses a callable default (returns True) for NEW rows.
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Phase 271.1.2 — per-tenant Stripe Connect "
                    "onboarding gate. False on existing tenants "
                    "(30-day opt-out window); True on new tenants. "
                    "Global override: settings.STRIPE_CONNECT_ENABLED."
                ),
            ),
        ),
    ]
