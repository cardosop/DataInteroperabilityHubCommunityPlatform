# Generated manually for Phase 7 — User Profile Edit (useronboardfix)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_create_personal_tenants_for_users_without_tenant'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='avatar_url',
            field=models.URLField(
                blank=True,
                max_length=500,
                null=True,
                help_text='URL to user avatar image (e.g. gravatar, CDN)',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='preferences',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='User preferences (theme, language, notifications, etc.)',
            ),
        ),
    ]
