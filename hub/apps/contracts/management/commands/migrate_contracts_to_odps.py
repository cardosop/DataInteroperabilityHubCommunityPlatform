"""
Management command to migrate existing ODCS contracts to ODPS (Task 9.1.1).

This command finds ODCS contracts with marketplace metadata and creates
corresponding ODPS contracts, linking them bidirectionally.

Usage:
    # Dry-run mode (no changes)
    python manage.py migrate_contracts_to_odps --dry-run

    # Migrate specific contract
    python manage.py migrate_contracts_to_odps --contract-id <uuid>

    # Batch migration
    python manage.py migrate_contracts_to_odps --batch-size 100

    # Migrate for specific tenant
    python manage.py migrate_contracts_to_odps --tenant-id <uuid>

    # Skip contracts that already have ODPS links
    python manage.py migrate_contracts_to_odps --skip-linked
"""
import json
import logging
from typing import Optional, List, Dict, Any
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.db.models import Q

from hub.apps.contracts.models import Contract, OriginalSpecType
from hub.apps.contracts.services import ContractService, ODPSService
from hub.apps.contracts.odps_generator import generate_odps_from_hubcontract
from hub.apps.contracts.normalization import parse_contract
from hub.apps.contracts.migration_validation import MigrationValidator
from hub.apps.core.services.base import ValidationError, NotFoundError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Migrate existing ODCS contracts to ODPS contracts (Task 9.1.1)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run migration in dry-run mode (no database changes)',
        )
        parser.add_argument(
            '--contract-id',
            type=str,
            default=None,
            help='Migrate specific contract by ID (per-contract mode)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of contracts to process per batch (default: 100)',
        )
        parser.add_argument(
            '--tenant-id',
            type=str,
            default=None,
            help='Migrate contracts for specific tenant only',
        )
        parser.add_argument(
            '--skip-linked',
            action='store_true',
            help='Skip ODCS contracts that already have ODPS links',
        )
        parser.add_argument(
            '--target-odps-version',
            type=str,
            default='4.1',
            help='Target ODPS version for generated contracts (default: 4.1)',
        )
        parser.add_argument(
            '--min-marketplace-fields',
            type=int,
            default=1,
            help='Minimum number of marketplace fields required to migrate (default: 1)',
        )
        parser.add_argument(
            '--validate',
            action='store_true',
            help='Run validation after migration (Task 9.1.2)',
        )
        parser.add_argument(
            '--validation-report-path',
            type=str,
            default=None,
            help='Path to save validation report (JSON format). If not specified, report is printed to stdout.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        contract_id = options.get('contract_id')
        batch_size = options['batch_size']
        tenant_id = options.get('tenant_id')
        skip_linked = options['skip_linked']
        target_odps_version = options['target_odps_version']
        min_marketplace_fields = options['min_marketplace_fields']

        self.stdout.write(
            self.style.SUCCESS(
                f'Starting ODCS to ODPS migration (target version: {target_odps_version})'
            )
        )
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY-RUN MODE: No database changes will be made')
            )

        # Get contracts to migrate
        if contract_id:
            # Per-contract mode
            contracts = self._get_contract_by_id(contract_id, tenant_id)
            if not contracts:
                self.stdout.write(
                    self.style.ERROR(f'Contract {contract_id} not found or not eligible')
                )
                return
        else:
            # Batch mode
            contracts = self._find_eligible_contracts(
                tenant_id=tenant_id,
                skip_linked=skip_linked,
                min_marketplace_fields=min_marketplace_fields
            )

        total_contracts = len(contracts)
        self.stdout.write(f'Found {total_contracts} ODCS contract(s) to migrate')

        if total_contracts == 0:
            self.stdout.write(
                self.style.SUCCESS('No contracts need migration')
            )
            return

        # Process contracts
        migrated_count = 0
        failed_count = 0
        skipped_count = 0

        for i, contract in enumerate(contracts, 1):
            self.stdout.write(
                f'\n[{i}/{total_contracts}] Processing contract {contract.id}'
            )

            try:
                result = self._migrate_contract(
                    contract=contract,
                    target_odps_version=target_odps_version,
                    dry_run=dry_run
                )

                if result['status'] == 'migrated':
                    migrated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✓ Migrated: Created ODPS contract {result.get("odps_contract_id")}'
                        )
                    )
                elif result['status'] == 'skipped':
                    skipped_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'  ⊘ Skipped: {result.get("reason")}')
                    )
                elif result['status'] == 'failed':
                    failed_count += 1
                    self.stdout.write(
                        self.style.ERROR(f'  ✗ Failed: {result.get("error")}')
                    )

            except Exception as e:
                failed_count += 1
                error_msg = str(e)
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Failed: {error_msg}')
                )
                logger.exception(f'Failed to migrate contract {contract.id}')

        # Summary
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('Migration Summary:')
        self.stdout.write(f'  Total contracts: {total_contracts}')
        self.stdout.write(f'  Migrated: {migrated_count}')
        self.stdout.write(f'  Failed: {failed_count}')
        self.stdout.write(f'  Skipped: {skipped_count}')

        if dry_run:
            self.stdout.write(
                self.style.WARNING('\nDRY-RUN: No database changes were made')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('\nMigration completed')
            )

        # Run validation if requested (Task 9.1.2)
        if options.get('validate') and not dry_run:
            self._run_validation(
                tenant_id=tenant_id,
                report_path=options.get('validation_report_path')
            )

    def _get_contract_by_id(
        self,
        contract_id: str,
        tenant_id: Optional[str] = None
    ) -> List[Contract]:
        """Get a specific contract by ID if eligible for migration."""
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            return []

        # Validate tenant if specified
        if tenant_id and str(contract.tenant_id) != tenant_id:
            return []

        # Check if eligible
        if not self._is_eligible_for_migration(contract):
            return []

        return [contract]

    def _find_eligible_contracts(
        self,
        tenant_id: Optional[str] = None,
        skip_linked: bool = False,
        min_marketplace_fields: int = 1
    ) -> List[Contract]:
        """
        Find ODCS contracts eligible for migration to ODPS.

        Criteria:
        - Must be ODCS contract (original_spec_type == ODCS)
        - Must have hub_contract_json
        - Must have marketplace metadata (if min_marketplace_fields > 0)
        - Must not already have ODPS link (if skip_linked is True)
        """
        queryset = Contract.objects.filter(
            original_spec_type=OriginalSpecType.ODCS,
            hub_contract_json__isnull=False
        )

        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)

        # Filter contracts with marketplace metadata
        eligible_contracts = []
        for contract in queryset:
            # Check if already has ODPS link
            if skip_linked and self._has_odps_link(contract):
                continue

            # Check marketplace metadata
            if min_marketplace_fields > 0:
                marketplace_fields = self._count_marketplace_fields(contract)
                if marketplace_fields < min_marketplace_fields:
                    continue

            eligible_contracts.append(contract)

        return eligible_contracts

    def _is_eligible_for_migration(self, contract: Contract) -> bool:
        """Check if contract is eligible for migration."""
        # Must be ODCS
        if contract.original_spec_type != OriginalSpecType.ODCS:
            return False

        # Must have hub_contract_json
        if not contract.hub_contract_json:
            return False

        return True

    def _has_odps_link(self, contract: Contract) -> bool:
        """Check if ODCS contract already has an ODPS link."""
        if not contract.hub_contract_json:
            return False

        extensions = contract.hub_contract_json.get('extensions', {})
        x_odps = extensions.get('x_odps', {})
        odps_link = x_odps.get('odps_link')

        if odps_link:
            # Verify the linked contract exists
            try:
                Contract.objects.get(
                    id=odps_link,
                    original_spec_type=OriginalSpecType.ODPS,
                    tenant_id=contract.tenant_id
                )
                return True
            except Contract.DoesNotExist:
                # Link exists but contract not found, consider as not linked
                return False

        return False

    def _count_marketplace_fields(self, contract: Contract) -> int:
        """Count marketplace fields in HubContract."""
        if not contract.hub_contract_json:
            return 0

        marketplace = contract.hub_contract_json.get('marketplace', {})
        if not isinstance(marketplace, dict):
            return 0

        count = 0

        # Count basic marketplace fields
        if marketplace.get('license_summary'):
            count += 1
        if marketplace.get('intended_use'):
            count += 1
        if marketplace.get('restricted_use'):
            count += 1

        # Count x_odps fields
        x_odps = marketplace.get('x_odps', {})
        if isinstance(x_odps, dict):
            if x_odps.get('pricing_plans'):
                count += 1
            if x_odps.get('access_methods'):
                count += 1
            if x_odps.get('payment_gateways'):
                count += 1

        return count

    def _migrate_contract(
        self,
        contract: Contract,
        target_odps_version: str,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Migrate a single ODCS contract to ODPS.

        Returns:
            Dictionary with:
            - status: 'migrated', 'skipped', or 'failed'
            - odps_contract_id: UUID of created ODPS contract (if migrated)
            - reason: Reason for skip (if skipped)
            - error: Error message (if failed)
        """
        try:
            # Check if already has ODPS link
            if self._has_odps_link(contract):
                return {
                    'status': 'skipped',
                    'reason': 'Contract already has ODPS link'
                }

            # Validate HubContract
            hub_contract = contract.hub_contract_json
            if not hub_contract:
                return {
                    'status': 'failed',
                    'error': 'Contract has no hub_contract_json'
                }

            # Get original ODCS contract for embedding
            # This is required for linking, so we must have it
            original_odcs_contract = None
            if contract.original_raw:
                try:
                    original_odcs_contract = parse_contract(
                        contract.original_raw,
                        contract.original_format
                    )
                    if not isinstance(original_odcs_contract, dict):
                        logger.warning(
                            f'Parsed ODCS contract {contract.id} is not a dict, cannot embed'
                        )
                        original_odcs_contract = None
                except Exception as e:
                    logger.warning(
                        f'Failed to parse original ODCS contract {contract.id}: {e}'
                    )
                    # Cannot continue without original ODCS for linking
                    return {
                        'status': 'failed',
                        'error': f'Failed to parse original ODCS contract: {str(e)}'
                    }
            else:
                # No original_raw, cannot create ODPS with contract section
                return {
                    'status': 'failed',
                    'error': 'Contract has no original_raw, cannot embed ODCS in ODPS'
                }

            # Generate ODPS document from HubContract
            try:
                odps_doc = generate_odps_from_hubcontract(
                    hub_contract=hub_contract,
                    target_version=target_odps_version,
                    original_odcs_contract=original_odcs_contract,
                    original_odcs_url=None
                )
            except Exception as e:
                return {
                    'status': 'failed',
                    'error': f'Failed to generate ODPS: {str(e)}'
                }

            if dry_run:
                # Dry-run: just validate generation
                return {
                    'status': 'migrated',
                    'odps_contract_id': 'DRY-RUN',
                    'reason': 'Dry-run mode - no contract created'
                }

            # Create ODPS contract and link
            with transaction.atomic():
                # Initialize services
                contract_service = ContractService(
                    tenant_id=str(contract.tenant_id),
                    user_id=str(contract.created_by.id) if contract.created_by else None
                )

                # Format ODPS as JSON
                odps_raw = json.dumps(odps_doc, indent=2)

                # Link ODPS to ODCS (this creates the ODPS contract and links it)
                odps_contract = contract_service.link_odps_to_odcs(
                    odcs_contract_id=str(contract.id),
                    odps_raw=odps_raw,
                    odps_format='json',
                    resolve_external_refs=True,
                    tenant_id=str(contract.tenant_id),
                    user_id=str(contract.created_by.id) if contract.created_by else None
                )

                return {
                    'status': 'migrated',
                    'odps_contract_id': str(odps_contract.id)
                }

        except ValidationError as e:
            return {
                'status': 'failed',
                'error': f'Validation error: {str(e)}'
            }
        except NotFoundError as e:
            return {
                'status': 'failed',
                'error': f'Not found error: {str(e)}'
            }
        except Exception as e:
            return {
                'status': 'failed',
                'error': f'Unexpected error: {str(e)}'
            }

    def _run_validation(
        self,
        tenant_id: Optional[str] = None,
        report_path: Optional[str] = None
    ) -> None:
        """
        Run migration validation and generate report (Task 9.1.2).

        Args:
            tenant_id: Optional tenant ID to filter validation
            report_path: Optional path to save JSON report
        """
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('Running Migration Validation...')
        self.stdout.write('=' * 60)

        try:
            validator = MigrationValidator(tenant_id=tenant_id)
            report = validator.validate_migration(include_statistics=True)

            # Print text report
            text_report = validator.generate_report_text(report)
            self.stdout.write(text_report)

            # Save JSON report if path specified
            if report_path:
                json_report = validator.generate_report_json(report)
                with open(report_path, 'w') as f:
                    f.write(json_report)
                self.stdout.write(
                    self.style.SUCCESS(f'\nJSON report saved to: {report_path}')
                )

            # Print summary
            if report.errors > 0:
                self.stdout.write(
                    self.style.ERROR(
                        f'\nValidation completed with {report.errors} error(s) and {report.warnings} warning(s)'
                    )
                )
            elif report.warnings > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f'\nValidation completed with {report.warnings} warning(s)'
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS('\nValidation completed successfully - no issues found')
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\nValidation failed: {str(e)}')
            )
            logger.exception('Migration validation failed')

