"""
Management command for warming cache with frequently accessed resources.

Usage:
    python manage.py warm_cache --tenant-id=<tenant_id>
    python manage.py warm_cache --all-tenants
    python manage.py warm_cache --tenant-id=<tenant_id> --assets-only
    python manage.py warm_cache --tenant-id=<tenant_id> --contracts-only
    python manage.py warm_cache --marketplace-only
"""
import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from hub.apps.core.caching.warming import (
    warm_tenant_cache,
    warm_all_tenants_cache,
    warm_asset_list_cache,
    warm_contract_list_cache,
    warm_marketplace_listings_cache,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Warm cache with frequently accessed resources'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-id',
            type=str,
            help='Tenant UUID to warm cache for'
        )
        parser.add_argument(
            '--all-tenants',
            action='store_true',
            help='Warm cache for all tenants'
        )
        parser.add_argument(
            '--assets-only',
            action='store_true',
            help='Only warm asset list cache'
        )
        parser.add_argument(
            '--contracts-only',
            action='store_true',
            help='Only warm contract list cache'
        )
        parser.add_argument(
            '--marketplace-only',
            action='store_true',
            help='Only warm marketplace listings cache'
        )

    def handle(self, *args, **options):
        tenant_id = options.get('tenant_id')
        all_tenants = options.get('all_tenants', False)
        assets_only = options.get('assets_only', False)
        contracts_only = options.get('contracts_only', False)
        marketplace_only = options.get('marketplace_only', False)

        # Validate arguments
        if not tenant_id and not all_tenants and not marketplace_only:
            raise CommandError(
                'Must specify either --tenant-id, --all-tenants, or --marketplace-only'
            )

        if all_tenants and tenant_id:
            raise CommandError('Cannot specify both --tenant-id and --all-tenants')

        if (assets_only or contracts_only) and marketplace_only:
            raise CommandError(
                'Cannot specify --marketplace-only with --assets-only or --contracts-only'
            )

        # Warm marketplace-only cache (not tenant-specific)
        if marketplace_only:
            self.stdout.write(self.style.SUCCESS('Warming marketplace listings cache...'))
            try:
                count = warm_marketplace_listings_cache()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully warmed {count} marketplace listing cache entries'
                    )
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Failed to warm marketplace cache: {e}')
                )
                logger.error(f"Marketplace cache warming failed: {e}", exc_info=True)
                raise CommandError(f"Marketplace cache warming failed: {e}")
            return

        # Warm cache for all tenants
        if all_tenants:
            self.stdout.write(self.style.SUCCESS('Warming cache for all tenants...'))
            try:
                summary = warm_all_tenants_cache()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Cache warming completed: '
                        f'{summary["successful"]}/{summary["total_tenants"]} tenants successful, '
                        f'{summary["failed"]} failed'
                    )
                )

                # Print detailed results
                if summary['results_by_tenant']:
                    self.stdout.write('\nDetailed results:')
                    for tid, results in summary['results_by_tenant'].items():
                        self.stdout.write(
                            f'  Tenant {tid}: '
                            f'{results["assets"]} assets, '
                            f'{results["contracts"]} contracts, '
                            f'{results["marketplace"]} marketplace'
                        )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Failed to warm cache for all tenants: {e}')
                )
                logger.error(f"Cache warming for all tenants failed: {e}", exc_info=True)
                raise CommandError(f"Cache warming failed: {e}")
            return

        # Warm cache for specific tenant
        if not tenant_id:
            raise CommandError('Must specify --tenant-id when not using --all-tenants or --marketplace-only')

        # Validate tenant exists
        from hub.apps.tenants.models import Tenant
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            raise CommandError(f'Tenant with id {tenant_id} does not exist')

        self.stdout.write(
            self.style.SUCCESS(f'Warming cache for tenant: {tenant.name} ({tenant_id})')
        )

        try:
            if assets_only:
                # Only warm asset cache
                self.stdout.write('Warming asset list cache...')
                count = warm_asset_list_cache(tenant_id)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully warmed {count} asset list cache entries'
                    )
                )
            elif contracts_only:
                # Only warm contract cache
                self.stdout.write('Warming contract list cache...')
                count = warm_contract_list_cache(tenant_id)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully warmed {count} contract list cache entries'
                    )
                )
            else:
                # Warm all caches for tenant
                results = warm_tenant_cache(tenant_id)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Cache warming completed: '
                        f'{results["assets"]} assets, '
                        f'{results["contracts"]} contracts, '
                        f'{results["marketplace"]} marketplace'
                    )
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to warm cache for tenant: {e}')
            )
            logger.error(f"Cache warming for tenant {tenant_id} failed: {e}", exc_info=True)
            raise CommandError(f"Cache warming failed: {e}")

