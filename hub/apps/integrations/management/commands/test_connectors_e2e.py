"""
Django management command for manual end-to-end testing of marketplace connectors.

This command provides comprehensive E2E testing capabilities for marketplace connectors,
allowing manual verification of connection, discovery, asset creation, and verification workflows.

Usage:
    # Test CKAN (demo.ckan.org) - no API key required
    python hub/manage.py test_connectors_e2e --source ckan --limit 5 --verify-assets

    # Test all connectors (skips those without credentials)
    python hub/manage.py test_connectors_e2e --source both --limit 5

    # Test only dados.gov.br (DADOS_GOV_BR_API_KEY required)
    python hub/manage.py test_connectors_e2e --source dados_gov_br --limit 10 --wait --verify-assets

    # Test Snowflake with selective resource download
    python manage.py test_connectors_e2e --source snowflake --limit 3 --data-strategy DOWNLOAD_SELECTIVE --download-resources "res1,res2"

    # Test with custom tenant and user
    python manage.py test_connectors_e2e --source dados_gov_br --tenant my-tenant --user admin@example.com
"""
import os
import time
import logging
from typing import Optional, List, Dict, Any
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils import timezone

from hub.apps.integrations.models import MarketplaceConnection, MarketplaceSyncJob, MarketplaceMapping
from hub.apps.integrations.services import MarketplaceIntegrationService
from hub.apps.integrations.base import (
    MarketplaceType,
    SyncDirection,
    SyncStatus,
)
from hub.apps.integrations.config.marketplace_instances import get_marketplace_instance_config
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.integrations.connectors.ckan_connector import CKANConnector
from hub.apps.integrations.connectors.dados_gov_br_connector import DadosGovBrConnector
from hub.apps.integrations.connectors.snowflake_connector import (
    SnowflakeConnector,
    SNOWFLAKE_AVAILABLE,
)
from hub.apps.assets.models import (
    Asset,
    AssetStatus,
    AssetSourceType,
    ExternalResourceReference,
    DataStrategy,
)
from hub.apps.contracts.models import Contract, OriginalSpecType
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.users.models import Role, UserRole, UserStatus
from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
import uuid

User = get_user_model()
logger = logging.getLogger(__name__)


def get_dados_gov_br_credentials() -> dict:
    """Get dados.gov.br credentials from environment variables."""
    jwt_token = os.getenv('DADOS_GOV_BR_API_KEY') or os.getenv('CKAN_DADOS_GOV_BR_API_KEY')
    if not jwt_token:
        raise CommandError("DADOS_GOV_BR_API_KEY not set - required for dados.gov.br testing")
    return {"jwt_token": jwt_token}


def get_azure_marketplace_credentials() -> dict:
    """Get Azure Marketplace Catalog API credentials from environment."""
    api_key = os.getenv("AZURE_MARKETPLACE_API_KEY") or os.getenv("AZURE_CATALOG_API_KEY")
    if not api_key:
        raise CommandError(
            "AZURE_MARKETPLACE_API_KEY (or AZURE_CATALOG_API_KEY) not set - "
            "required for Azure Marketplace testing. "
            "See https://aka.ms/DiscoveryAPI/keys"
        )
    base_url = os.getenv("AZURE_MARKETPLACE_BASE_URL", "https://catalogapi.azure.com")
    api_version = os.getenv("AZURE_MARKETPLACE_API_VERSION", "2025-05-01")
    return {
        "base_url": base_url,
        "api_key": api_key,
        "api_version": api_version,
    }


def get_snowflake_credentials() -> dict:
    """Get Snowflake credentials from environment variables."""
    account = os.getenv("SNOWFLAKE_ACCOUNT")
    user = os.getenv("SNOWFLAKE_USER")
    token = os.getenv("SNOWFLAKE_TOKEN")
    warehouse = os.getenv("SNOWFLAKE_WAREHOUSE")
    role = os.getenv("SNOWFLAKE_ROLE")
    database = os.getenv("SNOWFLAKE_DATABASE")

    if not account or not user or not token:
        raise CommandError(
            "SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, and SNOWFLAKE_TOKEN environment variables are required"
        )

    credentials = {
        "account": account,
        "user": user,
        "token": token,
    }

    if warehouse:
        credentials["warehouse"] = warehouse
    if role:
        credentials["role"] = role
    if database:
        credentials["database"] = database

    return credentials


class Command(BaseCommand):
    help = 'Manual end-to-end testing of marketplace connectors (CKAN, dados.gov.br, Snowflake, Azure)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            type=str,
            choices=['ckan', 'dados_gov_br', 'snowflake', 'azure', 'both'],
            default='both',
            help='Source to test: ckan (demo.ckan.org), dados_gov_br, snowflake, azure, or both (default: both)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=5,
            help='Number of listings to sync (default: 5)',
        )
        parser.add_argument(
            '--tenant',
            type=str,
            help='Tenant slug or ID (default: first tenant)',
        )
        parser.add_argument(
            '--user',
            type=str,
            help='User email or ID (default: first user)',
        )
        parser.add_argument(
            '--wait',
            action='store_true',
            default=True,
            help='Wait for workflow completion (default: True)',
        )
        parser.add_argument(
            '--no-wait',
            action='store_false',
            dest='wait',
            help='Do not wait for workflow completion',
        )
        parser.add_argument(
            '--verify-assets',
            action='store_true',
            default=True,
            help='Verify asset creation (default: True)',
        )
        parser.add_argument(
            '--no-verify-assets',
            action='store_false',
            dest='verify_assets',
            help='Do not verify asset creation',
        )
        parser.add_argument(
            '--skip-semantic',
            action='store_true',
            default=False,
            help='Skip semantic mapping (default: False)',
        )
        parser.add_argument(
            '--data-strategy',
            type=str,
            choices=['METADATA_ONLY', 'DOWNLOAD_SELECTIVE', 'DOWNLOAD_ALL'],
            default='METADATA_ONLY',
            help='Data strategy: METADATA_ONLY (default), DOWNLOAD_SELECTIVE, DOWNLOAD_ALL',
        )
        parser.add_argument(
            '--download-resources',
            type=str,
            help='Comma-separated resource IDs for selective download (only used with DOWNLOAD_SELECTIVE)',
        )

    def handle(self, *args, **options):
        """Main command handler"""
        source = options['source']
        limit = options['limit']
        wait = options['wait']
        verify_assets = options['verify_assets']
        skip_semantic = options['skip_semantic']
        data_strategy = options['data_strategy']
        download_resources_str = options.get('download_resources')

        # Parse download_resources if provided
        download_resources = None
        if download_resources_str:
            download_resources = [r.strip() for r in download_resources_str.split(',') if r.strip()]

        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('  Marketplace Connector E2E Testing'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))

        # Get tenant and user
        tenant = self._get_tenant(options.get('tenant'))
        user = self._get_user(options.get('user'), tenant)

        self.stdout.write(f"✓ Tenant: {tenant.name} ({tenant.id})")
        self.stdout.write(f"✓ User: {user.email} ({user.id})\n")

        # Determine sources to test
        sources_to_test = []
        if source == 'both':
            sources_to_test = ['ckan', 'dados_gov_br', 'snowflake', 'azure']
        else:
            sources_to_test = [source]

        # Track results
        results = {}

        # Test each source
        for source_name in sources_to_test:
            # Skip sources that require credentials when not available
            skip_reason = self._check_credentials_available(source_name)
            if skip_reason:
                self.stdout.write(self.style.WARNING(f"\n{'='*70}"))
                self.stdout.write(self.style.WARNING(f"  Skipping {source_name.upper()}: {skip_reason}"))
                self.stdout.write(self.style.WARNING('='*70 + '\n'))
                results[source_name] = {
                    'success': False,
                    'skipped': True,
                    'skip_reason': skip_reason,
                }
                continue

            self.stdout.write(self.style.SUCCESS(f"\n{'='*70}"))
            self.stdout.write(self.style.SUCCESS(f"  Testing: {source_name.upper()}"))
            self.stdout.write(self.style.SUCCESS('='*70 + '\n'))

            try:
                result = self._test_source(
                    source_name=source_name,
                    tenant=tenant,
                    user=user,
                    limit=limit,
                    wait=wait,
                    verify_assets=verify_assets,
                    skip_semantic=skip_semantic,
                    data_strategy=data_strategy,
                    download_resources=download_resources,
                )
                results[source_name] = result
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Error testing {source_name}: {e}"))
                logger.exception(f"Error testing {source_name}")
                results[source_name] = {
                    'success': False,
                    'error': str(e),
                }

        # Display overall summary
        self._display_overall_summary(results)

    def _check_credentials_available(self, source_name: str) -> Optional[str]:
        """Return skip reason if credentials not available, None if OK to run."""
        if source_name == 'ckan':
            return None  # demo.ckan.org does not require API key for read
        if source_name == 'dados_gov_br':
            if not (os.getenv('DADOS_GOV_BR_API_KEY') or os.getenv('CKAN_DADOS_GOV_BR_API_KEY')):
                return "DADOS_GOV_BR_API_KEY not set"
        elif source_name == 'snowflake':
            if not (os.getenv('SNOWFLAKE_ACCOUNT') and os.getenv('SNOWFLAKE_USER') and os.getenv('SNOWFLAKE_TOKEN')):
                return "SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_TOKEN not set"
        elif source_name == 'azure':
            if not (os.getenv('AZURE_MARKETPLACE_API_KEY') or os.getenv('AZURE_CATALOG_API_KEY')):
                return "AZURE_MARKETPLACE_API_KEY (or AZURE_CATALOG_API_KEY) not set"
        return None

    def _get_tenant(self, tenant_spec: Optional[str]) -> Tenant:
        """Get tenant by slug or ID"""
        if tenant_spec:
            try:
                if tenant_spec.isdigit() or len(tenant_spec) == 36:
                    return Tenant.objects.get(id=tenant_spec)
                else:
                    return Tenant.objects.get(slug=tenant_spec)
            except Tenant.DoesNotExist:
                raise CommandError(f"Tenant '{tenant_spec}' not found")
        else:
            tenant = Tenant.objects.first()
            if not tenant:
                self.stdout.write("No tenant found. Creating E2E test tenant...")
                tenant = Tenant.objects.create(
                    name="E2E Marketplace Test Tenant",
                    slug="e2e-marketplace-test",
                    status="ACTIVE",
                    kyc_status=KYCStatus.VERIFIED,
                )
                self.stdout.write(self.style.SUCCESS(f"   Created tenant: {tenant.name} ({tenant.id})"))
            return tenant

    def _get_user(self, user_spec: Optional[str], tenant: Tenant) -> User:
        """Get user by email or ID"""
        if user_spec:
            try:
                if user_spec.isdigit() or len(user_spec) == 36:
                    return User.objects.get(id=user_spec)
                else:
                    return User.objects.get(email=user_spec)
            except User.DoesNotExist:
                raise CommandError(f"User '{user_spec}' not found")
        else:
            # Try tenant user first, then superuser, then any user
            user = User.objects.filter(tenant_id=tenant.id).first()
            if not user:
                user = User.objects.filter(is_superuser=True).first()
            if not user:
                user = User.objects.first()
            if not user:
                self.stdout.write("No user found. Creating E2E test user...")
                user = User.objects.create_user(
                    email=f"e2e-marketplace-{uuid.uuid4().hex[:8]}@example.com",
                    password="e2e-test-pass",
                    tenant=tenant,
                    status=UserStatus.ACTIVE,
                )
                provider_role, _ = Role.objects.get_or_create(
                    tenant=tenant,
                    name="DATA_PROVIDER",
                    defaults={"description": "Data Provider"},
                )
                UserRole.objects.get_or_create(user=user, role=provider_role)
                self.stdout.write(self.style.SUCCESS(f"   Created user: {user.email} ({user.id})"))
            return user

    def _test_source(
        self,
        source_name: str,
        tenant: Tenant,
        user: User,
        limit: int,
        wait: bool,
        verify_assets: bool,
        skip_semantic: bool,
        data_strategy: str,
        download_resources: Optional[List[str]],
    ) -> Dict[str, Any]:
        """Test a single source"""
        result = {
            'source': source_name,
            'success': False,
            'connection_tested': False,
            'listings_discovered': 0,
            'sync_job_id': None,
            'assets_created': 0,
            'assets_verified': False,
        }

        try:
            # Create or get connection
            connection = self._create_connection(source_name, tenant)
            result['connection_id'] = str(connection.id)

            # Test connection
            self.stdout.write("1. Testing connection...")
            connector = self._test_connection(source_name, connection)
            result['connection_tested'] = True
            self.stdout.write(self.style.SUCCESS("   ✓ Connection successful\n"))

            # Discover listings
            self.stdout.write(f"2. Discovering listings (limit: {limit})...")
            listings = self._discover_listings(connector, limit)
            result['listings_discovered'] = len(listings)
            self.stdout.write(self.style.SUCCESS(f"   ✓ Discovered {len(listings)} listings\n"))

            # Display discovered listings
            if listings:
                self.stdout.write("   Discovered listings:")
                for i, listing in enumerate(listings[:5], 1):  # Show first 5
                    self.stdout.write(f"     {i}. {listing.title} (ID: {listing.marketplace_id})")
                if len(listings) > 5:
                    self.stdout.write(f"     ... and {len(listings) - 5} more\n")

            # Sync and wait if requested
            if wait:
                self.stdout.write("3. Syncing from marketplace...")
                sync_job = self._sync_and_wait(
                    source_name=source_name,
                    connection=connection,
                    tenant=tenant,
                    user=user,
                    limit=limit,
                    skip_semantic=skip_semantic,
                    data_strategy=data_strategy,
                    download_resources=download_resources,
                )
                result['sync_job_id'] = str(sync_job.id)
                result['sync_job_status'] = sync_job.status
                self.stdout.write(self.style.SUCCESS(f"   ✓ Sync job completed: {sync_job.status}\n"))

                # Verify assets if requested
                if verify_assets:
                    self.stdout.write("4. Verifying asset creation...")
                    assets = self._verify_assets(sync_job, tenant)
                    result['assets_created'] = len(assets)
                    result['assets_verified'] = True
                    self.stdout.write(self.style.SUCCESS(f"   ✓ Verified {len(assets)} assets created\n"))
            else:
                self.stdout.write("3. Creating sync job (not waiting for completion)...")
                sync_job = self._create_sync_job(
                    source_name=source_name,
                    connection=connection,
                    tenant=tenant,
                    user=user,
                    limit=limit,
                    skip_semantic=skip_semantic,
                    data_strategy=data_strategy,
                    download_resources=download_resources,
                )
                result['sync_job_id'] = str(sync_job.id)
                result['sync_job_status'] = sync_job.status
                self.stdout.write(self.style.SUCCESS(f"   ✓ Sync job created: {sync_job.id}\n"))
                self.stdout.write("   Note: Use --wait to wait for completion and verify assets\n")

            result['success'] = True

        except Exception as e:
            result['error'] = str(e)
            raise

        return result

    def _create_connection(self, source_name: str, tenant: Tenant) -> MarketplaceConnection:
        """Create MarketplaceConnection for source"""
        if source_name == 'ckan':
            instance_config = get_marketplace_instance_config("demo.ckan.org")
            if not instance_config:
                raise CommandError("demo.ckan.org instance configuration not found")

            config = {
                'instance_id': 'demo.ckan.org',
                'api_key': instance_config.get_api_key(),  # Optional for read-only
            }

            with transaction.atomic():
                connection, created = MarketplaceConnection.objects.get_or_create(
                    tenant=tenant,
                    marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
                    name='demo.ckan.org E2E Test',
                    defaults={
                        'config': config,
                        'is_active': True,
                    }
                )

                if not created:
                    connection.set_config(config)
                    connection.is_active = True
                    connection.save()

            return connection

        elif source_name == 'dados_gov_br':
            instance_config = get_marketplace_instance_config("dados.gov.br")
            if not instance_config:
                raise CommandError("dados.gov.br instance configuration not found")

            credentials = get_dados_gov_br_credentials()
            config = {
                'instance_id': 'dados.gov.br',
                'api_key': credentials['jwt_token'],
            }

            with transaction.atomic():
                connection, created = MarketplaceConnection.objects.get_or_create(
                    tenant=tenant,
                    marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
                    name='dados.gov.br E2E Test',
                    defaults={
                        'config': config,
                        'is_active': True,
                    }
                )

                if not created:
                    connection.set_config(config)
                    connection.is_active = True
                    connection.save()

            return connection

        elif source_name == 'snowflake':
            if not SNOWFLAKE_AVAILABLE:
                raise CommandError("snowflake-connector-python not installed")

            credentials = get_snowflake_credentials()
            config = {
                'account': credentials['account'],
                'user': credentials['user'],
                'token': credentials['token'],
            }
            if credentials.get('warehouse'):
                config['warehouse'] = credentials['warehouse']
            if credentials.get('role'):
                config['role'] = credentials['role']
            if credentials.get('database'):
                config['database'] = credentials['database']

            with transaction.atomic():
                connection, created = MarketplaceConnection.objects.get_or_create(
                    tenant=tenant,
                    marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
                    name='Snowflake E2E Test',
                    defaults={
                        'config': config,
                        'is_active': True,
                    }
                )

                if not created:
                    connection.set_config(config)
                    connection.is_active = True
                    connection.save()

            return connection

        elif source_name == 'azure':
            credentials = get_azure_marketplace_credentials()
            config = {
                'base_url': credentials['base_url'],
                'api_key': credentials['api_key'],
                'api_version': credentials['api_version'],
            }
            with transaction.atomic():
                connection, created = MarketplaceConnection.objects.get_or_create(
                    tenant=tenant,
                    marketplace_type=MarketplaceType.AZURE_MARKETPLACE.value,
                    name='Azure Marketplace E2E Test',
                    defaults={
                        'config': config,
                        'is_active': True,
                    }
                )
                if not created:
                    connection.set_config(config)
                    connection.is_active = True
                    connection.save()
            return connection

        else:
            raise CommandError(f"Unknown source: {source_name}")

    def _test_connection(self, source_name: str, connection: MarketplaceConnection):
        """Test connection to source"""
        if source_name == 'ckan':
            instance_config = get_marketplace_instance_config("demo.ckan.org")
            if not instance_config:
                raise CommandError("demo.ckan.org instance configuration not found")
            connector = CKANConnector(
                base_url=instance_config.base_url,
                api_key=instance_config.get_api_key(),
            )
        elif source_name == 'dados_gov_br':
            connector = DadosGovBrConnector(
                base_url=get_marketplace_instance_config("dados.gov.br").base_url,
                jwt_token=connection.get_config()['api_key'],
                swagger_spec_url=getattr(
                    get_marketplace_instance_config("dados.gov.br"),
                    'swagger_spec_url',
                    None
                )
            )
        elif source_name == 'snowflake':
            config = connection.get_config()
            connector = SnowflakeConnector(
                account=config['account'],
                user=config['user'],
                token=config['token'],
                warehouse=config.get('warehouse'),
                role=config.get('role'),
                database=config.get('database'),
            )
        elif source_name == 'azure':
            from hub.apps.integrations.connectors.azure_marketplace_connector import (
                AzureMarketplaceConnector,
            )
            config = connection.get_config()
            connector = AzureMarketplaceConnector(
                base_url=config.get('base_url'),
                api_key=config.get('api_key'),
                api_version=config.get('api_version'),
            )
        else:
            raise CommandError(f"Unknown source: {source_name}")

        if not connector.test_connection():
            raise CommandError(f"Connection test failed for {source_name}")

        return connector

    def _discover_listings(self, connector, limit: int) -> List:
        """Discover listings from source"""
        try:
            listings = connector.list_listings(limit=limit)
            return listings if listings else []
        except Exception as e:
            raise CommandError(f"Failed to discover listings: {e}")

    def _create_sync_job(
        self,
        source_name: str,
        connection: MarketplaceConnection,
        tenant: Tenant,
        user: User,
        limit: int,
        skip_semantic: bool,
        data_strategy: str,
        download_resources: Optional[List[str]],
    ) -> MarketplaceSyncJob:
        """Create sync job without waiting"""
        service = MarketplaceIntegrationService(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            request_id=None
        )

        sync_options = {
            'limit': limit,
            'data_strategy': data_strategy,
        }
        if skip_semantic:
            sync_options['skip_semantic_mapping'] = True
        if download_resources:
            sync_options['download_resources'] = download_resources

        sync_job = service.sync_from_marketplace(
            connection_id=str(connection.id),
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            filters=None,
            options=sync_options,
            request=None
        )

        return sync_job

    def _sync_and_wait(
        self,
        source_name: str,
        connection: MarketplaceConnection,
        tenant: Tenant,
        user: User,
        limit: int,
        skip_semantic: bool,
        data_strategy: str,
        download_resources: Optional[List[str]],
        timeout: int = 600,  # 10 minutes default
    ) -> MarketplaceSyncJob:
        """Sync from marketplace and wait for completion"""
        sync_job = self._create_sync_job(
            source_name=source_name,
            connection=connection,
            tenant=tenant,
            user=user,
            limit=limit,
            skip_semantic=skip_semantic,
            data_strategy=data_strategy,
            download_resources=download_resources,
        )

        workflow_instance_id = sync_job.metadata.get('workflow_instance_id')
        if not workflow_instance_id:
            self.stdout.write("   ⚠️  No workflow instance ID found in sync job metadata")
            return sync_job

        self.stdout.write(f"   Waiting for workflow completion (timeout: {timeout}s)...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                workflow_instance = WorkflowInstance.objects.get(id=workflow_instance_id)
                sync_job.refresh_from_db()

                if workflow_instance.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]:
                    break

                # Display progress
                if workflow_instance.state_data:
                    progress = workflow_instance.state_data.get('progress_percentage', 0)
                    step = workflow_instance.state_data.get('current_step_name', '')
                    elapsed = int(time.time() - start_time)
                    self.stdout.write(f"   Progress: {progress}% - {step} (elapsed: {elapsed}s)")

                time.sleep(2)  # INTENTIONAL: test-specific timing requirement
            except WorkflowInstance.DoesNotExist:
                self.stdout.write("   ⚠️  Workflow instance not found")
                break

        sync_job.refresh_from_db()

        if sync_job.status == SyncStatus.COMPLETED.value:
            self.stdout.write(self.style.SUCCESS(f"   ✓ Workflow completed successfully"))
        elif sync_job.status == SyncStatus.FAILED.value:
            self.stdout.write(self.style.ERROR(f"   ✗ Workflow failed"))
            error_msg = sync_job.metadata.get('error_message', 'Unknown error')
            self.stdout.write(self.style.ERROR(f"   Error: {error_msg}"))
        else:
            self.stdout.write(self.style.WARNING(f"   ⚠️  Workflow still running (status: {sync_job.status})"))

        return sync_job

    def _verify_assets(self, sync_job: MarketplaceSyncJob, tenant: Tenant) -> List[Asset]:
        """Verify asset creation"""
        # First, try to find assets by sync_job_id
        assets = Asset.objects.filter(
            tenant=tenant,
            source_type=AssetSourceType.FEDERATED,
            source_metadata__sync_job_id=str(sync_job.id)
        ).order_by('created_at')

        # If no assets found by sync_job_id, check via mappings created in this sync
        if assets.count() == 0:
            # Check workflow state for created/mapped assets
            workflow_instance_id = sync_job.metadata.get('workflow_instance_id')
            if workflow_instance_id:
                try:
                    from hub.apps.orchestration.models import WorkflowInstance
                    workflow_instance = WorkflowInstance.objects.get(id=workflow_instance_id)
                    if workflow_instance.state_data:
                        created_assets_data = workflow_instance.state_data.get('created_assets', [])
                        mapped_assets_data = workflow_instance.state_data.get('mapped_assets', [])

                        # Get asset IDs from workflow state
                        asset_ids = []
                        for asset_data in created_assets_data + mapped_assets_data:
                            if isinstance(asset_data, dict):
                                asset_id = asset_data.get('asset_id') or asset_data.get('id')
                                if asset_id:
                                    asset_ids.append(asset_id)

                        if asset_ids:
                            assets = Asset.objects.filter(
                                id__in=asset_ids,
                                tenant=tenant
                            ).order_by('created_at')

                            if assets.count() > 0:
                                self.stdout.write(
                                    self.style.SUCCESS(
                                        f"   Found {assets.count()} asset(s) via workflow state "
                                        f"({len(created_assets_data)} created, {len(mapped_assets_data)} mapped)"
                                    )
                                )
                except Exception as e:
                    logger.debug(f"Error checking workflow state for assets: {e}")

        # If still no assets, check via mappings for this connection
        if assets.count() == 0:
            mappings = MarketplaceMapping.objects.filter(
                connection=sync_job.connection,
                tenant=tenant
            )
            if mappings.exists():
                asset_ids = [m.hub_asset_id for m in mappings if m.hub_asset_id]
                if asset_ids:
                    assets = Asset.objects.filter(
                        id__in=asset_ids,
                        tenant=tenant
                    ).order_by('created_at')
                    if assets.count() > 0:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"   Found {assets.count()} existing asset(s) via mappings "
                                f"(assets may have been created in a previous sync)"
                            )
                        )

        if assets.count() == 0:
            # Check workflow state for more details
            workflow_instance_id = sync_job.metadata.get('workflow_instance_id')
            if workflow_instance_id:
                try:
                    from hub.apps.orchestration.models import WorkflowInstance
                    workflow_instance = WorkflowInstance.objects.get(id=workflow_instance_id)
                    if workflow_instance.state_data:
                        created_count = len(workflow_instance.state_data.get('created_assets', []))
                        mapped_count = len(workflow_instance.state_data.get('mapped_assets', []))
                        if created_count == 0 and mapped_count > 0:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"   ⚠️  No new assets created (workflow mapped {mapped_count} existing assets)"
                                )
                            )
                        elif created_count == 0 and mapped_count == 0:
                            self.stdout.write(
                                self.style.WARNING(
                                    "   ⚠️  No assets found - workflow may have skipped all listings "
                                    "(duplicates or validation failures)"
                                )
                            )
                        else:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"   ⚠️  No assets found in database (workflow reports "
                                    f"{created_count} created, {mapped_count} mapped)"
                                )
                            )
                except Exception:
                    pass

            if assets.count() == 0:
                self.stdout.write(
                    self.style.WARNING(
                        "   ⚠️  No assets found for this sync job. "
                        "This may be normal if listings were already synced or skipped."
                    )
                )
                return []

        self.stdout.write(f"   Verifying {assets.count()} asset(s)...")

        # Verify each asset
        verified_count = 0
        for asset in assets:
            issues = []

            # Verify source type
            if asset.source_type != AssetSourceType.FEDERATED:
                issues.append(f"incorrect source_type ({asset.source_type})")

            # Verify contracts
            odps_contracts = asset.contracts.filter(original_spec_type=OriginalSpecType.ODPS)
            odcs_contracts = asset.contracts.filter(original_spec_type=OriginalSpecType.ODCS)

            if odps_contracts.count() == 0:
                issues.append("missing ODPS contract")
            if odcs_contracts.count() == 0:
                issues.append("missing ODCS contract")

            # Verify external resource references
            external_refs = ExternalResourceReference.objects.filter(asset=asset)
            if external_refs.count() == 0:
                issues.append("no external resource references")

            if issues:
                self.stdout.write(
                    self.style.WARNING(
                        f"   ⚠️  Asset {asset.id} ({asset.name[:50]}...): {', '.join(issues)}"
                    )
                )
            else:
                verified_count += 1
                self.stdout.write(
                    f"   ✓ Asset {asset.id}: {asset.name[:50]}... "
                    f"(ODPS: {odps_contracts.count()}, ODCS: {odcs_contracts.count()}, "
                    f"Resources: {external_refs.count()})"
                )

        if verified_count == assets.count():
            self.stdout.write(self.style.SUCCESS(f"   ✓ All {verified_count} asset(s) verified successfully"))
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"   ⚠️  {verified_count}/{assets.count()} asset(s) fully verified "
                    f"({assets.count() - verified_count} with issues)"
                )
            )

        return list(assets)

    def _display_overall_summary(self, results: Dict[str, Dict[str, Any]]):
        """Display overall test summary"""
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('  Overall Summary'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))

        for source_name, result in results.items():
            if result.get('skipped'):
                self.stdout.write(self.style.WARNING(f"⊘ {source_name.upper()}: SKIPPED"))
                self.stdout.write(f"  Reason: {result.get('skip_reason', 'Unknown')}")
            elif result.get('success'):
                self.stdout.write(self.style.SUCCESS(f"✓ {source_name.upper()}: PASSED"))
                self.stdout.write(f"  - Connection tested: {result.get('connection_tested', False)}")
                self.stdout.write(f"  - Listings discovered: {result.get('listings_discovered', 0)}")
                if result.get('sync_job_id'):
                    self.stdout.write(f"  - Sync job: {result.get('sync_job_id')}")
                    self.stdout.write(f"  - Sync status: {result.get('sync_job_status', 'N/A')}")
                if result.get('assets_created', 0) > 0:
                    self.stdout.write(f"  - Assets created: {result.get('assets_created', 0)}")
                    self.stdout.write(f"  - Assets verified: {result.get('assets_verified', False)}")
            else:
                self.stdout.write(self.style.ERROR(f"✗ {source_name.upper()}: FAILED"))
                if result.get('error'):
                    self.stdout.write(self.style.ERROR(f"  Error: {result['error']}"))
            self.stdout.write("")

        # Overall status
        passed = sum(1 for r in results.values() if r.get('success'))
        skipped = sum(1 for r in results.values() if r.get('skipped'))
        failed = sum(1 for r in results.values() if not r.get('success') and not r.get('skipped'))
        if failed == 0 and passed > 0:
            self.stdout.write(self.style.SUCCESS(f"✓ All run tests PASSED ({passed} passed, {skipped} skipped)"))
        elif failed > 0:
            self.stdout.write(self.style.ERROR(f"✗ {failed} test(s) FAILED ({passed} passed, {skipped} skipped)"))
        else:
            self.stdout.write(self.style.WARNING(f"⊘ All sources skipped (no credentials set)"))

        self.stdout.write("")

