"""
Harvest command for dados.gov.br using the workflow system.

This command uses sync_from_marketplace which triggers the marketplace_sync_pull workflow:
1. Creates a sync job
2. Triggers workflow orchestration
3. Uses connector.sync_pull() to discover and map listings
4. Creates federated assets with ODPS/ODCS contracts via workflow tasks
5. Supports scheduled/recurrent delta syncs
6. Provides proper error handling and progress tracking

Usage:
    python manage.py harvest_dados_gov_br_direct --limit 5
    python manage.py harvest_dados_gov_br_direct --limit 100 --skip-resources --skip-semantic
"""

import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from hub.apps.integrations.base import MarketplaceType
from hub.apps.integrations.config.marketplace_instances import get_marketplace_instance_config
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.integrations.models import MarketplaceConnection
from hub.apps.integrations.services import MarketplaceIntegrationService
from hub.apps.tenants.models import Tenant

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Directly harvest data from dados.gov.br and create federated assets"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=5,
            help="Maximum number of datasets to harvest (default: 5)",
        )
        parser.add_argument(
            "--tenant",
            type=str,
            help="Tenant slug or ID (defaults to first tenant)",
        )
        parser.add_argument(
            "--user",
            type=str,
            help="User email or ID (defaults to first user)",
        )
        parser.add_argument(
            "--query",
            type=str,
            help="Search query string",
        )
        parser.add_argument(
            "--skip-resources",
            action="store_true",
            help="Skip resource downloads for faster harvest",
        )
        parser.add_argument(
            "--skip-semantic",
            action="store_true",
            help="Skip semantic mapping for faster harvest",
        )
        parser.add_argument(
            "--download-resources-for-last-n",
            type=int,
            help="Download resources only for the last N assets (e.g., 100). Useful for selective resource downloading.",
        )
        parser.add_argument(
            "--data-strategy",
            type=str,
            choices=["METADATA_ONLY", "DOWNLOAD_SELECTIVE", "DOWNLOAD_ALL"],
            default="METADATA_ONLY",
            help="Data download strategy: METADATA_ONLY (default), DOWNLOAD_SELECTIVE, DOWNLOAD_ALL",
        )
        parser.add_argument(
            "--download-resources",
            type=str,
            help="Comma-separated list of resource IDs to download (only used with DOWNLOAD_SELECTIVE)",
        )
        parser.add_argument(
            "--wait",
            action="store_true",
            help="Wait for workflow to complete (synchronous mode)",
        )

    def handle(self, *args, **options):
        instance_name = "dados.gov.br"
        limit = options["limit"]
        tenant_spec = options.get("tenant")
        user_spec = options.get("user")
        query = options.get("query")
        skip_resources = options.get("skip_resources", False)
        skip_semantic = options.get("skip_semantic", False)
        download_resources_for_last_n = options.get("download_resources_for_last_n")
        data_strategy = options.get("data_strategy", "METADATA_ONLY")
        download_resources_str = options.get("download_resources")
        wait = options.get("wait", False)

        # Parse download_resources if provided
        download_resources = None
        if download_resources_str:
            download_resources = [r.strip() for r in download_resources_str.split(",") if r.strip()]

        # Validate instance exists
        instance_config = get_marketplace_instance_config(instance_name)
        if not instance_config:
            raise CommandError(f"CKAN instance '{instance_name}' not found.")

        self.stdout.write(self.style.SUCCESS(f"✓ Found CKAN instance: {instance_name}"))
        self.stdout.write(f"  Base URL: {instance_config.base_url}")

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
                raise CommandError("No tenant found. Please create a tenant first.")

        self.stdout.write(f"✓ Using tenant: {tenant.name} ({tenant.id})")

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
                raise CommandError("No user found. Please create a user first.")

        self.stdout.write(f"✓ Using user: {user.email} ({user.id})")

        # Create or get marketplace connection
        with transaction.atomic():
            connection, created = MarketplaceConnection.objects.get_or_create(
                tenant=tenant,
                marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
                name=instance_name,
                defaults={
                    "config": {
                        "instance_id": instance_name,
                        "api_key": instance_config.get_api_key(),
                    },
                    "is_active": True,
                },
            )

            if not created:
                config = connection.get_config()
                config["instance_id"] = instance_name
                if instance_config.get_api_key():
                    config["api_key"] = instance_config.get_api_key()
                connection.set_config(config)
                connection.is_active = True
                connection.save()

        action = "Created" if created else "Using existing"
        self.stdout.write(
            self.style.SUCCESS(f"✓ {action} connection: {connection.name} ({connection.id})")
        )

        # Create connector
        connector = MarketplaceConnectorFactory.create_connector(
            marketplace_type=MarketplaceType.CKAN_INSTANCE, config=connection.get_config()
        )

        # Test connection
        self.stdout.write("\nTesting connection...")
        if not connector.test_connection():
            raise CommandError("Connection test failed")
        self.stdout.write(
            self.style.SUCCESS(f"✓ Connection to {instance_config.base_url} verified")
        )

        # Build filters
        filters = {}
        if query:
            filters["q"] = query

        # Build sync options
        sync_options = {
            "limit": limit,
            "include_resources": not skip_resources,
        }
        # Backward compatibility: skip_resources maps to METADATA_ONLY
        if skip_resources and not download_resources_for_last_n:
            sync_options["skip_resource_downloads"] = True
            sync_options["data_strategy"] = "METADATA_ONLY"
        else:
            sync_options["data_strategy"] = data_strategy
        if download_resources_for_last_n:
            sync_options["download_resources_for_last_n"] = download_resources_for_last_n
        if download_resources:
            sync_options["download_resources"] = download_resources
        if skip_semantic:
            sync_options["skip_semantic_mapping"] = True

        # Create service
        service = MarketplaceIntegrationService(
            tenant_id=str(tenant.id), user_id=str(user.id), request_id=None
        )

        # Use sync_from_marketplace to trigger workflow system
        self.stdout.write(f"\n✓ Starting harvest via workflow system (target: {limit} assets)...")
        self.stdout.write("  Using workflow: marketplace_sync_pull")
        self.stdout.write(f"  Filters: {filters}")
        self.stdout.write(f"  Options: {sync_options}\n")

        try:
            sync_job = service.sync_from_marketplace(
                connection_id=str(connection.id),
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                filters=filters if filters else None,
                options=sync_options,
                request=None,
            )

            self.stdout.write(self.style.SUCCESS(f"✓ Created sync job: {sync_job.id}"))
            self.stdout.write(
                f"  Workflow instance: {sync_job.metadata.get('workflow_instance_id', 'N/A')}"
            )
            self.stdout.write(f"  Status: {sync_job.status}")

            if wait:
                # Wait for workflow to complete (synchronous mode)
                self.stdout.write("\n  Waiting for workflow to complete...")
                import time

                from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus

                workflow_instance_id = sync_job.metadata.get("workflow_instance_id")
                if workflow_instance_id:
                    max_wait = 3600  # 1 hour max
                    start_time = time.time()
                    while time.time() - start_time < max_wait:
                        try:
                            workflow_instance = WorkflowInstance.objects.get(
                                id=workflow_instance_id
                            )
                            sync_job.refresh_from_db()

                            if workflow_instance.status in [
                                WorkflowStatus.COMPLETED,
                                WorkflowStatus.FAILED,
                            ]:
                                break

                            # Update progress from workflow
                            if workflow_instance.state_data:
                                progress = workflow_instance.state_data.get(
                                    "progress_percentage", 0
                                )
                                step = workflow_instance.state_data.get("current_step_name", "")
                                self.stdout.write(f"  Progress: {progress}% - {step}")

                            time.sleep(2)
                        except WorkflowInstance.DoesNotExist:
                            break

                # Refresh sync job to get final status
                sync_job.refresh_from_db()

                self.stdout.write(f"\n{'=' * 60}")
                self.stdout.write(self.style.SUCCESS("\n✓ Harvest Summary:"))
                self.stdout.write(f"  Sync job ID: {sync_job.id}")
                self.stdout.write(f"  Status: {sync_job.status}")
                self.stdout.write(f"  Items synced: {sync_job.items_synced or 0}")
                self.stdout.write(f"  Items failed: {sync_job.items_failed or 0}")
                if sync_job.completed_at:
                    self.stdout.write(f"  Completed at: {sync_job.completed_at}")
            else:
                self.stdout.write(f"\n{'=' * 60}")
                self.stdout.write(self.style.SUCCESS("\n✓ Sync job created successfully"))
                self.stdout.write("  The workflow will process in the background")
                self.stdout.write(f"  Monitor progress via: sync job {sync_job.id}")
                self.stdout.write(
                    f"  Or check workflow instance: {sync_job.metadata.get('workflow_instance_id', 'N/A')}"
                )

        except Exception as e:
            raise CommandError(f"Harvest failed: {e}")
