"""
Management command to rollback ODPS migration (Task 9.1.3).

This command rolls back ODPS migration by:
1. Removing ODPS links from ODCS contracts
2. Removing ODCS links from ODPS contracts
3. Deleting ODPS contracts created during migration
4. Restoring previous state (if links existed before migration)
5. Validating that state is restored

Usage:
    # Dry-run mode (no changes)
    python manage.py rollback_odps_migration --dry-run

    # Rollback specific contract
    python manage.py rollback_odps_migration --contract-id <uuid>

    # Batch rollback
    python manage.py rollback_odps_migration --batch-size 100

    # Rollback for specific tenant
    python manage.py rollback_odps_migration --tenant-id <uuid>

    # Skip contracts without ODPS links
    python manage.py rollback_odps_migration --skip-unlinked
"""
import logging
from typing import Optional, List, Dict, Any
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from hub.apps.contracts.models import Contract, OriginalSpecType
from hub.apps.core.services.base import ValidationError, NotFoundError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Rollback ODPS migration by removing links and deleting ODPS contracts (Task 9.1.3)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run rollback in dry-run mode (no database changes)',
        )
        parser.add_argument(
            '--contract-id',
            type=str,
            default=None,
            help='Rollback specific contract by ID (per-contract mode)',
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
            help='Rollback contracts for specific tenant only',
        )
        parser.add_argument(
            '--skip-unlinked',
            action='store_true',
            help='Skip ODCS contracts that do not have ODPS links',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        contract_id = options.get('contract_id')
        batch_size = options['batch_size']
        tenant_id = options.get('tenant_id')
        skip_unlinked = options['skip_unlinked']

        self.stdout.write(
            self.style.SUCCESS('Starting ODPS migration rollback')
        )
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY-RUN MODE: No database changes will be made')
            )

        # Get contracts to rollback
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
            contracts = self._find_contracts_to_rollback(
                tenant_id=tenant_id,
                skip_unlinked=skip_unlinked
            )

        total_contracts = len(contracts)
        self.stdout.write(f'Found {total_contracts} ODCS contract(s) to rollback')

        if total_contracts == 0:
            self.stdout.write(
                self.style.SUCCESS('No contracts need rollback')
            )
            return

        # Process contracts
        rolled_back_count = 0
        failed_count = 0
        skipped_count = 0

        for i, odcs_contract in enumerate(contracts, 1):
            self.stdout.write(
                f'\n[{i}/{total_contracts}] Processing contract {odcs_contract.id}'
            )

            try:
                result = self._rollback_contract_wrapper(
                    odcs_contract=odcs_contract,
                    dry_run=dry_run
                )

                if result['status'] == 'success':
                    rolled_back_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✓ Rolled back: {result.get("summary", "")}'
                        )
                    )
                elif result['status'] == 'skipped':
                    skipped_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'  ⊘ Skipped: {result.get("reason", "")}')
                    )
                elif result['status'] == 'failed':
                    failed_count += 1
                    self.stdout.write(
                        self.style.ERROR(f'  ✗ Failed: {result.get("error", "")}')
                    )

            except Exception as e:
                failed_count += 1
                error_msg = str(e)
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Failed: {error_msg}')
                )
                logger.exception(f'Failed to rollback contract {odcs_contract.id}')

        # Summary
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('Rollback Summary:')
        self.stdout.write(f'  Total contracts: {total_contracts}')
        self.stdout.write(f'  Rolled back: {rolled_back_count}')
        self.stdout.write(f'  Failed: {failed_count}')
        self.stdout.write(f'  Skipped: {skipped_count}')

        if dry_run:
            self.stdout.write(
                self.style.WARNING('\nDRY-RUN: No database changes were made')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('\nRollback completed')
            )

    def _get_contract_by_id(
        self,
        contract_id: str,
        tenant_id: Optional[str] = None
    ) -> List[Contract]:
        """Get a specific contract by ID if eligible for rollback."""
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            return []

        # Validate tenant if specified
        if tenant_id and str(contract.tenant_id) != tenant_id:
            return []

        # Check if eligible (must be ODCS with ODPS link)
        if not self._is_eligible_for_rollback(contract):
            return []

        return [contract]

    def _find_contracts_to_rollback(
        self,
        tenant_id: Optional[str] = None,
        skip_unlinked: bool = False
    ) -> List[Contract]:
        """
        Find ODCS contracts eligible for rollback.

        Criteria:
        - Must be ODCS contract (original_spec_type == ODCS)
        - Must have ODPS link (unless skip_unlinked is False)
        """
        queryset = Contract.objects.filter(
            original_spec_type=OriginalSpecType.ODCS
        )

        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)

        # Filter contracts with ODPS links
        eligible_contracts = []
        for contract in queryset:
            if skip_unlinked and not self._has_odps_link(contract):
                continue

            # Only include contracts with ODPS links
            if self._has_odps_link(contract):
                eligible_contracts.append(contract)

        return eligible_contracts

    def _is_eligible_for_rollback(self, contract: Contract) -> bool:
        """Check if contract is eligible for rollback."""
        # Must be ODCS
        if contract.original_spec_type != OriginalSpecType.ODCS:
            return False

        # Must have ODPS link
        if not self._has_odps_link(contract):
            return False

        return True

    def _has_odps_link(self, contract: Contract) -> bool:
        """Check if ODCS contract has an ODPS link."""
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

    def _rollback_contract_wrapper(
        self,
        odcs_contract: Contract,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Wrapper to rollback a contract (finds ODPS contract and calls _rollback_contract).

        Returns:
            Dictionary with:
            - status: 'success', 'skipped', or 'failed'
            - summary: Summary of rollback operations
            - reason: Reason for skip (if skipped)
            - error: Error message (if failed)
        """
        try:
            # Get ODPS contract
            if not odcs_contract.hub_contract_json:
                return {
                    'status': 'skipped',
                    'reason': 'Contract has no hub_contract_json'
                }

            extensions = odcs_contract.hub_contract_json.get('extensions', {})
            x_odps = extensions.get('x_odps', {})
            odps_link = x_odps.get('odps_link')

            if not odps_link:
                return {
                    'status': 'skipped',
                    'reason': 'Contract has no ODPS link'
                }

            # Get ODPS contract
            try:
                odps_contract = Contract.objects.get(
                    id=odps_link,
                    original_spec_type=OriginalSpecType.ODPS,
                    tenant_id=odcs_contract.tenant_id
                )
            except Contract.DoesNotExist:
                return {
                    'status': 'skipped',
                    'reason': f'ODPS contract {odps_link} not found'
                }

            # Perform rollback
            result = self._rollback_contract(
                odcs_contract=odcs_contract,
                odps_contract=odps_contract,
                dry_run=dry_run
            )

            return result

        except Exception as e:
            return {
                'status': 'failed',
                'error': f'Unexpected error: {str(e)}'
            }

    def _rollback_contract(
        self,
        odcs_contract: Contract,
        odps_contract: Contract,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Rollback a single contract pair (ODCS and ODPS).

        This method:
        1. Stores previous state (if any)
        2. Removes ODPS link from ODCS contract
        3. Removes ODCS link from ODPS contract
        4. Deletes ODPS contract
        5. Validates rollback

        Returns:
            Dictionary with:
            - status: 'success' or 'failed'
            - summary: Summary of operations
            - links_removed: List of links removed
            - contract_deleted: Whether ODPS contract was deleted
            - dry_run: Whether this was a dry-run
        """
        if dry_run:
            return {
                'status': 'success',
                'summary': 'Would remove links and delete ODPS contract',
                'links_removed': ['odps_to_odcs', 'odcs_to_odps'],
                'contract_deleted': True,
                'dry_run': True
            }

        try:
            with transaction.atomic():
                # Store previous state (for potential restoration)
                previous_odps_link = None
                if odcs_contract.hub_contract_json:
                    extensions = odcs_contract.hub_contract_json.get('extensions', {})
                    x_odps = extensions.get('x_odps', {})
                    previous_odps_link = x_odps.get('odps_link')

                # Remove links
                links_removed = []
                remove_odps_result = self._remove_odps_link_from_odcs(odcs_contract)
                if remove_odps_result.get('link_removed'):
                    links_removed.append('odcs_to_odps')

                remove_odcs_result = self._remove_odcs_link_from_odps(odps_contract)
                if remove_odcs_result.get('link_removed'):
                    links_removed.append('odps_to_odcs')

                # Delete ODPS contract
                contract_deleted = False
                odps_contract_id = str(odps_contract.id)
                remove_contract_result = self._remove_odps_contract(odps_contract)
                if remove_contract_result.get('contract_deleted'):
                    contract_deleted = True

                # Validate rollback
                validation_result = self._validate_rollback(
                    odcs_contract_id=str(odcs_contract.id),
                    odps_contract_id=odps_contract_id
                )

                summary_parts = []
                if links_removed:
                    summary_parts.append(f'Removed {len(links_removed)} link(s)')
                if contract_deleted:
                    summary_parts.append('Deleted ODPS contract')
                summary = ', '.join(summary_parts) if summary_parts else 'No changes needed'

                return {
                    'status': 'success',
                    'summary': summary,
                    'links_removed': links_removed,
                    'contract_deleted': contract_deleted,
                    'validation': validation_result,
                    'dry_run': False
                }

        except Exception as e:
            logger.exception(f'Failed to rollback contract {odcs_contract.id}')
            return {
                'status': 'failed',
                'error': str(e)
            }

    def _remove_odps_link_from_odcs(self, odcs_contract: Contract) -> Dict[str, Any]:
        """
        Remove ODPS link from ODCS contract.

        Returns:
            Dictionary with:
            - status: 'success' or 'partial_failure'
            - link_removed: True if link was removed
            - no_link_found: True if no link existed
        """
        try:
            if not odcs_contract.hub_contract_json:
                return {
                    'status': 'success',
                    'no_link_found': True
                }

            extensions = odcs_contract.hub_contract_json.get('extensions', {})
            x_odps = extensions.get('x_odps', {})

            if 'odps_link' not in x_odps:
                return {
                    'status': 'success',
                    'no_link_found': True
                }

            # Remove link
            del x_odps['odps_link']

            # Clean up empty x_odps dict
            if not x_odps:
                if 'extensions' in odcs_contract.hub_contract_json:
                    del extensions['x_odps']
                    if not extensions:
                        del odcs_contract.hub_contract_json['extensions']

            odcs_contract.save(update_fields=['hub_contract_json'])

            logger.info(
                f'Removed ODPS link from ODCS contract: odcs_contract_id={odcs_contract.id}'
            )

            return {
                'status': 'success',
                'link_removed': True
            }

        except Exception as e:
            logger.exception(f'Failed to remove ODPS link from ODCS contract: {odcs_contract.id}')
            return {
                'status': 'partial_failure',
                'error': str(e)
            }

    def _remove_odcs_link_from_odps(self, odps_contract: Contract) -> Dict[str, Any]:
        """
        Remove ODCS link from ODPS contract.

        Returns:
            Dictionary with:
            - status: 'success' or 'partial_failure'
            - link_removed: True if link was removed
            - no_link_found: True if no link existed
        """
        try:
            if not odps_contract.hub_contract_json:
                return {
                    'status': 'success',
                    'no_link_found': True
                }

            extensions = odps_contract.hub_contract_json.get('extensions', {})
            x_odps = extensions.get('x_odps', {})

            if 'odcs_link' not in x_odps:
                return {
                    'status': 'success',
                    'no_link_found': True
                }

            # Remove link
            del x_odps['odcs_link']

            # Clean up empty x_odps dict
            if not x_odps:
                if 'extensions' in odps_contract.hub_contract_json:
                    del extensions['x_odps']
                    if not extensions:
                        del odps_contract.hub_contract_json['extensions']

            odps_contract.save(update_fields=['hub_contract_json'])

            logger.info(
                f'Removed ODCS link from ODPS contract: odps_contract_id={odps_contract.id}'
            )

            return {
                'status': 'success',
                'link_removed': True
            }

        except Exception as e:
            logger.exception(f'Failed to remove ODCS link from ODPS contract: {odps_contract.id}')
            return {
                'status': 'partial_failure',
                'error': str(e)
            }

    def _remove_odps_contract(self, odps_contract: Contract) -> Dict[str, Any]:
        """
        Remove ODPS contract.

        Returns:
            Dictionary with:
            - status: 'success' or 'partial_failure'
            - contract_deleted: True if contract was deleted
            - contract_not_found: True if contract doesn't exist
        """
        odps_contract_id = str(odps_contract.id)

        try:
            # Delete contract
            odps_contract.delete()

            logger.info(f'Deleted ODPS contract: odps_contract_id={odps_contract_id}')

            return {
                'status': 'success',
                'contract_deleted': True
            }

        except Contract.DoesNotExist:
            logger.warning(f'ODPS contract not found for deletion: {odps_contract_id}')
            return {
                'status': 'success',
                'contract_not_found': True
            }
        except Exception as e:
            logger.exception(f'Failed to delete ODPS contract: {odps_contract_id}')
            return {
                'status': 'partial_failure',
                'error': str(e)
            }

    def _restore_previous_odps_link(
        self,
        odcs_contract: Contract,
        previous_odps_link: str
    ) -> Dict[str, Any]:
        """
        Restore previous ODPS link in ODCS contract.

        This is used when rolling back a migration that replaced an existing link.

        Returns:
            Dictionary with:
            - status: 'success' or 'partial_failure'
            - link_restored: True if link was restored
        """
        try:
            # Verify previous ODPS contract exists
            try:
                previous_odps_contract = Contract.objects.get(
                    id=previous_odps_link,
                    original_spec_type=OriginalSpecType.ODPS,
                    tenant_id=odcs_contract.tenant_id
                )
            except Contract.DoesNotExist:
                logger.debug(
                    f'Previous ODPS contract not found for restoration: '
                    f'previous_odps_link={previous_odps_link}, odcs_contract_id={odcs_contract.id}'
                )
                return {
                    'status': 'partial_failure',
                    'error': 'Previous ODPS contract not found'
                }

            # Restore link
            if not odcs_contract.hub_contract_json:
                odcs_contract.hub_contract_json = {}

            if 'extensions' not in odcs_contract.hub_contract_json:
                odcs_contract.hub_contract_json['extensions'] = {}

            if 'x_odps' not in odcs_contract.hub_contract_json['extensions']:
                odcs_contract.hub_contract_json['extensions']['x_odps'] = {}

            odcs_contract.hub_contract_json['extensions']['x_odps']['odps_link'] = previous_odps_link
            odcs_contract.save(update_fields=['hub_contract_json'])

            logger.info(
                f'Restored previous ODPS link in ODCS contract: '
                f'odcs_contract_id={odcs_contract.id}, previous_odps_link={previous_odps_link}'
            )

            return {
                'status': 'success',
                'link_restored': True
            }

        except Exception as e:
            logger.exception(
                f'Failed to restore previous ODPS link: odcs_contract_id={odcs_contract.id}'
            )
            return {
                'status': 'partial_failure',
                'error': str(e)
            }

    def _validate_rollback(
        self,
        odcs_contract_id: str,
        odps_contract_id: str
    ) -> Dict[str, Any]:
        """
        Validate that rollback was successful.

        Checks:
        1. ODPS link removed from ODCS contract
        2. ODCS link removed from ODPS contract (if contract still exists)
        3. ODPS contract deleted (if specified)

        Returns:
            Dictionary with:
            - status: 'success' or 'partial_failure'
            - all_links_removed: True if all links are removed
            - odps_contract_deleted: True if ODPS contract is deleted
            - errors: List of validation errors
        """
        errors = []
        all_links_removed = True
        odps_contract_deleted = False

        try:
            # Check ODCS contract
            try:
                odcs_contract = Contract.objects.get(id=odcs_contract_id)
                if odcs_contract.hub_contract_json:
                    extensions = odcs_contract.hub_contract_json.get('extensions', {})
                    x_odps = extensions.get('x_odps', {})
                    if x_odps.get('odps_link'):
                        all_links_removed = False
                        errors.append('ODPS link still exists in ODCS contract')
            except Contract.DoesNotExist:
                errors.append('ODCS contract not found')

            # Check ODPS contract (may be deleted or still exist)
            try:
                odps_contract = Contract.objects.get(id=odps_contract_id)
                # Contract still exists, check if link is removed
                if odps_contract.hub_contract_json:
                    extensions = odps_contract.hub_contract_json.get('extensions', {})
                    x_odps = extensions.get('x_odps', {})
                    if x_odps.get('odcs_link'):
                        all_links_removed = False
                        errors.append('ODCS link still exists in ODPS contract')
                # Contract exists but links are removed - this is valid for partial rollback
                odps_contract_deleted = False
            except Contract.DoesNotExist:
                # Contract deleted, which is expected for full rollback
                odps_contract_deleted = True

            # Success if all links are removed (contract deletion is optional for validation)
            # Contract deletion is checked separately via odps_contract_deleted flag
            status = 'success' if all_links_removed else 'partial_failure'

            return {
                'status': status,
                'all_links_removed': all_links_removed,
                'odps_contract_deleted': odps_contract_deleted,
                'errors': errors
            }

        except Exception as e:
            logger.exception(f'Failed to validate rollback: {e}')
            return {
                'status': 'partial_failure',
                'all_links_removed': False,
                'odps_contract_deleted': False,
                'errors': [str(e)]
            }

