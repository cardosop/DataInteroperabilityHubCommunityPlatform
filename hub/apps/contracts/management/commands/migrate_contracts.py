"""
Management command to migrate existing contracts to new HubContract version (GAP-10.2.2).

Usage:
    python manage.py migrate_contracts --dry-run
    python manage.py migrate_contracts --batch-size 100
    python manage.py migrate_contracts --target-version 2.0.0
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from hub.apps.contracts.models import Contract
from hub.apps.contracts.migration import (
    get_current_hubcontract_version,
    needs_migration,
    can_migrate,
    migrate_hubcontract
)
from hub.apps.contracts.migration_manager import ContractMigrationManager
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Migrate existing contracts to new HubContract version (GAP-10.2.2)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run migration in dry-run mode (no database changes)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of contracts to process per batch (default: 100)',
        )
        parser.add_argument(
            '--target-version',
            type=str,
            default=None,
            help='Target HubContract version (default: current version)',
        )
        parser.add_argument(
            '--tenant-id',
            type=str,
            default=None,
            help='Migrate contracts for specific tenant only',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force migration even if contract is already at target version',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        target_version = options['target_version'] or get_current_hubcontract_version()
        tenant_id = options.get('tenant_id')
        force = options['force']
        
        self.stdout.write(f"Starting contract migration to version {target_version}")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY-RUN MODE: No database changes will be made"))
        
        # Get contracts that need migration
        queryset = Contract.objects.filter(
            hub_contract_json__isnull=False,
            hub_contract_version__isnull=False
        )
        
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        
        if not force:
            # Filter contracts that need migration
            contracts_to_migrate = []
            for contract in queryset:
                if needs_migration(contract.hub_contract_version) or contract.hub_contract_version != target_version:
                    if can_migrate(contract.hub_contract_version, target_version):
                        contracts_to_migrate.append(contract)
        else:
            contracts_to_migrate = list(queryset)
        
        total_contracts = len(contracts_to_migrate)
        self.stdout.write(f"Found {total_contracts} contracts to migrate")
        
        if total_contracts == 0:
            self.stdout.write(self.style.SUCCESS("No contracts need migration"))
            return
        
        # Process in batches
        migrated_count = 0
        failed_count = 0
        skipped_count = 0
        
        for i in range(0, total_contracts, batch_size):
            batch = contracts_to_migrate[i:i + batch_size]
            self.stdout.write(f"Processing batch {i // batch_size + 1} ({len(batch)} contracts)")
            
            for contract in batch:
                try:
                    if dry_run:
                        # Simulate migration
                        migrated, warnings, errors = migrate_hubcontract(
                            contract.hub_contract_json,
                            contract.hub_contract_version,
                            target_version
                        )
                        if errors:
                            self.stdout.write(
                                self.style.ERROR(
                                    f"  Contract {contract.id}: Migration would fail - {errors}"
                                )
                            )
                            failed_count += 1
                        else:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"  Contract {contract.id}: Would migrate from {contract.hub_contract_version} to {target_version}"
                                )
                            )
                            if warnings:
                                for warning in warnings:
                                    self.stdout.write(f"    Warning: {warning}")
                            migrated_count += 1
                    else:
                        # Perform actual migration
                        migrated, hub_contract, warnings = ContractMigrationManager.migrate_on_write(contract)
                        if migrated:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"  Contract {contract.id}: Migrated from {contract.hub_contract_version} to {target_version}"
                                )
                            )
                            if warnings:
                                for warning in warnings:
                                    self.stdout.write(f"    Warning: {warning}")
                            migrated_count += 1
                        else:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"  Contract {contract.id}: Migration skipped (already at target version or cannot migrate)"
                                )
                            )
                            skipped_count += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f"  Contract {contract.id}: Migration failed - {str(e)}"
                        )
                    )
                    logger.exception(f"Failed to migrate contract {contract.id}")
                    failed_count += 1
        
        # Summary
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("Migration Summary:")
        self.stdout.write(f"  Total contracts: {total_contracts}")
        self.stdout.write(f"  Migrated: {migrated_count}")
        self.stdout.write(f"  Failed: {failed_count}")
        self.stdout.write(f"  Skipped: {skipped_count}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("\nDRY-RUN: No database changes were made"))
        else:
            self.stdout.write(self.style.SUCCESS("\nMigration completed"))

