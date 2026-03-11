"""
Django management command to PULL a specific listing from demo.ckan.org and create a federated asset.

Creates a known federated asset synchronously (no workflow). Used for tests
and fixtures that need a pre-created federated asset from demo.ckan.org.

Usage:
    python hub/manage.py create_demo_ckan_federated_asset --listing-id annakarenina
    python hub/manage.py create_demo_ckan_federated_asset --listing-id annakarenina --tenant my-tenant
    python hub/manage.py create_demo_ckan_federated_asset --listing-id annakarenina --output-json
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth import get_user_model

from hub.apps.integrations.models import MarketplaceConnection
from hub.apps.integrations.services import MarketplaceIntegrationService
from hub.apps.integrations.base import MarketplaceType
from hub.apps.integrations.config.marketplace_instances import get_marketplace_instance_config
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.tenants.models import Tenant

User = get_user_model()

# Default listing ID from demo.ckan.org (known to exist)
DEFAULT_LISTING_ID = "annakarenina"


class Command(BaseCommand):
    help = (
        "PULL a specific listing from demo.ckan.org and create a federated asset synchronously. "
        "Used for tests and fixtures."

    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--listing-id",
            type=str,
            default=DEFAULT_LISTING_ID,
            help=f"CKAN package ID (default: {DEFAULT_LISTING_ID})",
        )
        parser.add_argument(
            "--tenant",
            type=str,
            help="Tenant slug or ID (defaults to first tenant)",
        )
        parser.add_argument(
            "--user",
            type=str,
            help="User email or ID (defaults to first user in tenant)",
        )
        parser.add_argument(
            "--connection-name",
            type=str,
            default="Demo CKAN E2E Connection",
            help="Marketplace connection name (default: Demo CKAN E2E Connection)",
        )
        parser.add_argument(
            "--output-json",
            action="store_true",
            help="Output asset_id as JSON for scripting",
        )

    def handle(self, *args, **options):
        listing_id = options["listing_id"]
        tenant_spec = options.get("tenant")
        user_spec = options.get("user")
        connection_name = options["connection_name"]
        output_json = options["output_json"]

        if not listing_id or not listing_id.strip():
            raise CommandError("--listing-id cannot be empty")

        # Get instance config (single source of truth for base_url)
        instance_config = get_marketplace_instance_config("demo.ckan.org")
        if not instance_config:
            raise CommandError(
                "demo.ckan.org instance configuration not found. "
                "Ensure hub.apps.integrations.config.marketplace_instances is configured."
            )
        base_url = instance_config.base_url.rstrip("/")

        # Get tenant
        tenant = None
        if tenant_spec:
            try:
                if tenant_spec.isdigit() or len(tenant_spec) == 36:
                    tenant = Tenant.objects.get(id=tenant_spec)
                else:
                    tenant = Tenant.objects.get(slug=tenant_spec)
            except Tenant.DoesNotExist:
                raise CommandError(f"Tenant '{tenant_spec}' not found")
        else:
            tenant = Tenant.objects.first()
            if not tenant:
                raise CommandError("No tenant found. Create a tenant first.")

        # Get user
        user = None
        if user_spec:
            try:
                if user_spec.isdigit() or len(user_spec) == 36:
                    user = User.objects.get(id=user_spec)
                else:
                    user = User.objects.get(email=user_spec)
            except User.DoesNotExist:
                raise CommandError(f"User '{user_spec}' not found")
        else:
            user = User.objects.filter(tenant_id=tenant.id).first()
            if not user:
                user = User.objects.filter(is_superuser=True).first()
            if not user:
                user = User.objects.first()
            if not user:
                raise CommandError("No user found. Create a user first.")

        # Create connector and get listing
        connector = MarketplaceConnectorFactory.create_connector(
            MarketplaceType.CKAN_INSTANCE,
            config={"base_url": base_url},
        )

        try:
            listing = connector.get_listing(listing_id)
        except Exception as e:
            raise CommandError(f"Failed to get listing '{listing_id}' from demo.ckan.org: {e}")

        # Map to hub asset
        mapping = connector.map_to_hub_asset(listing)

        # Create or get connection
        with transaction.atomic():
            connection, created = MarketplaceConnection.objects.get_or_create(
                tenant=tenant,
                name=connection_name,
                marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
                defaults={
                    "config": {"base_url": base_url},
                    "is_active": True,
                },
            )
            if not created:
                connection.set_config({"base_url": base_url})
                connection.is_active = True
                connection.save(update_fields=["config", "is_active"])

        # Create federated asset
        service = MarketplaceIntegrationService(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
        )

        try:
            asset = service.create_federated_asset_with_contracts(
                asset_mapping=mapping,
                connection=connection,
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                data_strategy="METADATA_ONLY",
            )
        except Exception as e:
            raise CommandError(f"Failed to create federated asset: {e}")

        if output_json:
            self.stdout.write(
                '{"asset_id": "%s", "listing_id": "%s", "asset_name": "%s"}' % (
                    str(asset.id),
                    listing_id,
                    (asset.name or "").replace('"', '\\"'),
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS(f"✓ Created federated asset: {asset.name}"))
            self.stdout.write(f"  Asset ID: {asset.id}")
            self.stdout.write(f"  Listing ID: {listing_id}")
            self.stdout.write(f"  Connection: {connection.name} ({connection.id})")
