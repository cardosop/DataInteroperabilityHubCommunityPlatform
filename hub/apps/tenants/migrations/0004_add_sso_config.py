# Generated migration for SSO config

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0003_rename_tenant_configs_tenant_idx_tenant_conf_tenant__37e737_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenantconfig',
            name='sso_config',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='SSO configuration (SAML and OIDC settings)',
                null=True
            ),
        ),
    ]

