"""Phase 90: Backfill NULL expires_at on RefreshToken rows."""
from django.db import migrations


def backfill_expires_at(apps, schema_editor):
    # Use raw SQL since the field may not allow NULL in the current model
    # definition but could have NULL values from earlier schema states.
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE refresh_tokens SET expires_at = created_at + interval '30 days' "
            "WHERE expires_at IS NULL"
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("hub_auth", "0006_refreshtoken_family_loginattempt"),
    ]

    operations = [
        migrations.RunPython(backfill_expires_at, noop),
    ]
