"""
Django management command to harvest data from CKAN instances.

Usage:
    python manage.py harvest_ckan --instance dados.gov.br --limit 10
    python manage.py harvest_ckan --instance dados.gov.br --limit 50 --organization "some-org"
    python manage.py harvest_ckan --instance dados.gov.br --dry-run
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth import get_user_model

from hub.apps.integrations.models import MarketplaceConnection, MarketplaceSyncJob
from hub.apps.integrations.services import MarketplaceIntegrationService
from hub.apps.integrations.base import MarketplaceType, SyncDirection
from hub.apps.integrations.config.marketplace_instances import get_marketplace_instance_config
from hub.apps.tenants.models import Tenant

User = get_user_model()


class Command(BaseCommand):
    help = 'Harvest data from CKAN instances (e.g., dados.gov.br) into Hub'

    def add_arguments(self, parser):
        parser.add_argument(
            '--instance',
            type=str,
            required=True,
            help='CKAN instance name (e.g., dados.gov.br, demo.ckan.org)',
        )
        parser.add_argument(
            '--tenant',
            type=str,
            help='Tenant slug or ID (defaults to first tenant)',
        )
        parser.add_argument(
            '--user',
            type=str,
            help='User email or ID (defaults to first user)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Maximum number of datasets to harvest (default: 10)',
        )
        parser.add_argument(
            '--organization',
            type=str,
            help='Filter by organization name',
        )
        parser.add_argument(
            '--tags',
            type=str,
            help='Filter by tags (comma-separated)',
        )
        parser.add_argument(
            '--query',
            type=str,
            help='Search query string',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate harvest without creating assets',
        )
        parser.add_argument(
            '--no-resources',
            action='store_true',
            help='Skip downloading resources',
        )
        parser.add_argument(
            '--connection-name',
            type=str,
            help='Custom connection name (defaults to instance name)',
        )

    def handle(self, *args, **options):
        instance_name = options['instance']
        tenant_spec = options.get('tenant')
        user_spec = options.get('user')
        limit = options['limit']
        organization = options.get('organization')
        tags = options.get('tags')
        query = options.get('query')
        dry_run = options['dry_run']
        include_resources = not options['no_resources']
        connection_name = options.get('connection_name') or instance_name

        # Validate instance exists
        instance_config = get_marketplace_instance_config(instance_name)
        if not instance_config:
            raise CommandError(
                f"CKAN instance '{instance_name}' not found. "
                f"Available instances: dados.gov.br, demo.ckan.org, data.gov"
            )

        self.stdout.write(
            self.style.SUCCESS(f"✓ Found CKAN instance: {instance_name}")
        )
        self.stdout.write(f"  Base URL: {instance_config.base_url}")
        self.stdout.write(f"  Country: {instance_config.country or 'N/A'}")
        self.stdout.write(f"  Language: {instance_config.language or 'N/A'}")

        # Get tenant
        tenant = None
        if tenant_spec:
            try:
                if tenant_spec.isdigit() or len(tenant_spec) == 36:  # UUID
                    tenant = Tenant.objects.get(id=tenant_spec)
                else:
                    tenant = Tenant.objects.get(slug=tenant_spec)
            except Tenant.DoesNotExist:
                raise CommandError(f"Tenant '{tenant_spec}' not found")
        else:
            tenant = Tenant.objects.first()
            if not tenant:
                raise CommandError("No tenant found. Please create a tenant first.")

        self.stdout.write(f"✓ Using tenant: {tenant.name} ({tenant.id})")

        # Get user (prefer user from the same tenant)
        user = None
        if user_spec:
            try:
                if user_spec.isdigit() or len(user_spec) == 36:  # UUID
                    user = User.objects.get(id=user_spec)
                else:
                    user = User.objects.get(email=user_spec)
            except User.DoesNotExist:
                raise CommandError(f"User '{user_spec}' not found")
        else:
            # Try to get a user from the same tenant first
            user = User.objects.filter(tenant_id=tenant.id).first()
            if not user:
                # Fall back to superuser or any user
                user = User.objects.filter(is_superuser=True).first()
            if not user:
                user = User.objects.first()
            if not user:
                raise CommandError("No user found. Please create a user first.")

        self.stdout.write(f"✓ Using user: {user.email} ({user.id})")

        # Create or get marketplace connection
        with transaction.atomic():
            connection, created = MarketplaceConnection.objects.get_or_create(
                tenant=tenant,
                marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
                name=connection_name,
                defaults={
                    'config': {
                        'instance_id': instance_name,
                        'api_key': instance_config.get_api_key(),
                    },
                    'is_active': True,
                }
            )

            # Update config if connection already exists
            if not created:
                config = connection.get_config()
                config['instance_id'] = instance_name
                if instance_config.get_api_key():
                    config['api_key'] = instance_config.get_api_key()
                connection.set_config(config)
                connection.is_active = True
                connection.save()

        action = "Created" if created else "Using existing"
        self.stdout.write(
            self.style.SUCCESS(f"✓ {action} connection: {connection.name} ({connection.id})")
        )

        # Build filters
        filters = {}
        if organization:
            filters['organization'] = organization
        if tags:
            filters['tags'] = [tag.strip() for tag in tags.split(',')]
        if query:
            filters['q'] = query

        if filters:
            self.stdout.write(f"  Filters: {filters}")

        # Build options
        options_dict = {
            'limit': limit,
            'create_assets': not dry_run,
            'include_resources': include_resources,
            'dry_run': dry_run,
        }

        if dry_run:
            self.stdout.write(
                self.style.WARNING("⚠ DRY RUN MODE - No assets will be created")
            )

        # Create service instance
        service = MarketplaceIntegrationService(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            request_id=None
        )

        # Test connection first (skip if dry-run and connection fails - allow workflow to handle errors)
        self.stdout.write("\nTesting connection...")
        try:
            from hub.apps.integrations.factory import MarketplaceConnectorFactory
            connector = MarketplaceConnectorFactory.create_connector(
                marketplace_type=MarketplaceType.CKAN_INSTANCE,
                config=connection.get_config()
            )

            if connector.test_connection():
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Connection to {instance_config.base_url} verified")
                )
            else:
                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            f"⚠ Connection test failed, but continuing in dry-run mode. "
                            f"Actual harvest may fail if connection is not available."
                        )
                    )
                else:
                    raise CommandError("Connection test failed")
        except Exception as e:
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠ Connection test failed ({e}), but continuing in dry-run mode. "
                        f"Actual harvest may fail if connection is not available."
                    )
                )
            else:
                raise CommandError(f"Connection test failed: {e}")

        # Create sync job
        self.stdout.write(f"\nStarting harvest (limit: {limit})...")
        try:
            sync_job = service.sync_from_marketplace(
                connection_id=str(connection.id),
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                listing_ids=None,  # Harvest all matching filters
                filters=filters,
                options=options_dict,
                request=None
            )

            self.stdout.write(
                self.style.SUCCESS(f"\n✓ Sync job created successfully!")
            )
            self.stdout.write(f"  Job ID: {sync_job.id}")
            self.stdout.write(f"  Status: {sync_job.status}")
            self.stdout.write(f"  Direction: {sync_job.direction}")
            self.stdout.write(f"  Created at: {sync_job.created_at}")

            if dry_run:
                self.stdout.write(
                    self.style.WARNING("\n⚠ This was a dry run. No assets were created.")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        "\n✓ The sync job will be processed asynchronously."
                    )
                )
                self.stdout.write(
                    f"  Check status: python manage.py shell -c "
                    f"'from hub.apps.integrations.models import MarketplaceSyncJob; "
                    f"job = MarketplaceSyncJob.objects.get(id=\"{sync_job.id}\"); "
                    f"print(f\"Status: {{job.status}}, Synced: {{job.items_synced}}, "
                    f"Failed: {{job.items_failed}}\")'"
                )

        except Exception as e:
            raise CommandError(f"Failed to create sync job: {e}")

