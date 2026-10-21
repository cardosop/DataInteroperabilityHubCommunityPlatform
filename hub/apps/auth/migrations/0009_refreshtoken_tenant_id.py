"""
AUTH-007 fix — add ``RefreshToken.tenant_id`` so the JWT minted by the
refresh endpoint carries the same tenant context the refresh token was
originally issued for.

Without this column, ``POST /auth/refresh/`` mints a new access token via
``JWTTokenGenerator.generate_access_token(user)`` which falls back to
``user.tenant.id`` (the user's HOME tenant). After ``POST /auth/switch-tenant/``,
the current access token expires in ~15 min and the refresh transparently
returns the user to the home tenant — silently regressing the security
context and exposing cross-tenant data (the bug AUTH-007 surfaces).

The column is nullable so the migration is non-blocking on existing rows;
``views.refresh_token`` falls back to ``user.tenant.id`` only when the
column is null (existing tokens issued before this migration). New tokens
issued by ``/auth/login/`` and ``/auth/switch-tenant/`` set it explicitly.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # App label is ``hub_auth`` (set by ``hub.apps.auth.apps.AuthConfig.label``
        # to avoid colliding with Django's built-in ``auth`` app).
        ("hub_auth", "0008_customer_billing_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="refreshtoken",
            name="tenant_id",
            field=models.UUIDField(
                null=True,
                blank=True,
                db_index=True,
                help_text=(
                    "Tenant context this refresh token represents. Set by "
                    "/auth/login/ (user's home tenant) and by "
                    "/auth/switch-tenant/ (the switched-to tenant). On "
                    "refresh, the new access token's tenant_id claim is "
                    "derived from this field."
                ),
            ),
        ),
    ]
