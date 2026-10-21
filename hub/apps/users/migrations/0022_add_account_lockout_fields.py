# Generated migration: add progressive account lockout fields (277.B.066)
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0021_enable_rls_user_roles"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="failed_login_count",
            field=models.IntegerField(
                default=0,
                help_text="Consecutive failed login attempts since last successful login",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="locked_until",
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text="Account locked until this time (progressive backoff)",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="lockout_level",
            field=models.IntegerField(
                default=0,
                help_text="Number of consecutive lockout periods triggered; drives progressive window doubling",
            ),
        ),
    ]
