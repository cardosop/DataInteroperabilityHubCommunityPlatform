"""
Contract Migration Manager

Manages contract migration strategies (ON_WRITE, ON_READ, BACKGROUND).
"""
import logging
from typing import Optional, Dict, Any, Tuple, List
from django.db import transaction
from django.utils import timezone

from .models import Contract
from .migration import (
    migrate_hubcontract,
    get_current_hubcontract_version,
    needs_migration,
    can_migrate,
    MigrationStrategy,
)
from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.audit.utils import create_audit_event

logger = logging.getLogger(__name__)


class ContractMigrationManager:
    """
    Manages contract migration operations.
    """
    
    @staticmethod
    def migrate_on_write(contract: Contract) -> Tuple[bool, Optional[Dict[str, Any]], List[str]]:
        """
        Migrate contract on write (when contract is updated).
        
        Args:
            contract: Contract instance
            
        Returns:
            Tuple of (migrated: bool, migrated_hub_contract: Optional[Dict], warnings: List[str])
        """
        if not contract.hub_contract_json or not contract.hub_contract_version:
            return False, None, []
        
        current_version = get_current_hubcontract_version()
        
        if not needs_migration(contract.hub_contract_version):
            return False, None, []
        
        if not can_migrate(contract.hub_contract_version, current_version):
            logger.warning(
                f"Contract {contract.id} cannot be migrated from {contract.hub_contract_version} to {current_version}"
            )
            return False, None, []
        
        # Store source version before migration
        source_version = contract.hub_contract_version
        
        # Perform migration
        migrated, warnings, errors = migrate_hubcontract(
            contract.hub_contract_json,
            source_version,
            current_version
        )
        
        if errors:
            logger.error(f"Migration failed for contract {contract.id}: {errors}")
            return False, None, warnings
        
        # Update contract
        with transaction.atomic():
            # Store original version in history (if needed)
            # For now, we just update in place
            
            contract.hub_contract_json = migrated
            contract.hub_contract_version = current_version
            contract.save(update_fields=['hub_contract_json', 'hub_contract_version', 'updated_at'])
            
            # Log audit event
            create_audit_event(
                resource_type="CONTRACT",
                action="CONTRACT_MIGRATED",
                actor_user=None,  # System action
                tenant=contract.tenant,
                resource_id=str(contract.id),
                details={
                    'source_version': source_version,
                    'target_version': current_version,
                    'strategy': MigrationStrategy.ON_WRITE,
                    'warnings': warnings,
                },
                request=None
            )
        
        return True, migrated, warnings
    
    @staticmethod
    def migrate_on_read(contract: Contract) -> Tuple[Optional[Dict[str, Any]], List[str]]:
        """
        Migrate contract on read (lazy migration).
        
        This performs in-memory migration without updating the database.
        The migrated contract is returned but not persisted.
        
        Args:
            contract: Contract instance
            
        Returns:
            Tuple of (migrated_hub_contract: Optional[Dict], warnings: List[str])
        """
        if not contract.hub_contract_json or not contract.hub_contract_version:
            return contract.hub_contract_json, []
        
        current_version = get_current_hubcontract_version()
        
        if not needs_migration(contract.hub_contract_version):
            return contract.hub_contract_json, []
        
        if not can_migrate(contract.hub_contract_version, current_version):
            logger.warning(
                f"Contract {contract.id} cannot be migrated from {contract.hub_contract_version} to {current_version}"
            )
            return contract.hub_contract_json, []
        
        # Perform in-memory migration
        migrated, warnings, errors = migrate_hubcontract(
            contract.hub_contract_json,
            contract.hub_contract_version,
            current_version
        )
        
        if errors:
            logger.error(f"Migration failed for contract {contract.id}: {errors}")
            return contract.hub_contract_json, warnings
        
        return migrated, warnings
    
    @staticmethod
    def migrate_background(contract: Contract, user=None) -> Optional[Job]:
        """
        Queue background migration job.
        
        Args:
            contract: Contract instance
            user: User triggering the migration (optional)
            
        Returns:
            Job instance if created, None otherwise
        """
        if not contract.hub_contract_json or not contract.hub_contract_version:
            return None
        
        current_version = get_current_hubcontract_version()
        
        if not needs_migration(contract.hub_contract_version):
            return None
        
        if not can_migrate(contract.hub_contract_version, current_version):
            logger.warning(
                f"Contract {contract.id} cannot be migrated from {contract.hub_contract_version} to {current_version}"
            )
            return None
        
        # Create migration job
        job = Job.objects.create(
            tenant=contract.tenant,
            type=JobType.CONTRACT_MIGRATION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=str(contract.id),
            details_json={
                'source_version': contract.hub_contract_version,
                'target_version': current_version,
                'strategy': MigrationStrategy.BACKGROUND,
            },
            created_by=user,
        )
        
        # Log audit event
        create_audit_event(
            resource_type="CONTRACT",
            action="CONTRACT_MIGRATION_STARTED",
            actor_user=user,
            tenant=contract.tenant,
            resource_id=str(contract.id),
            details={
                'job_id': str(job.id),
                'source_version': contract.hub_contract_version,
                'target_version': current_version,
                'strategy': MigrationStrategy.BACKGROUND,
            },
            request=None
        )
        
        # Queue job for processing
        from hub.apps.jobs.tasks import process_contract_migration_job
        from django_rq import get_queue
        
        queue = get_queue('default')
        queue.enqueue(process_contract_migration_job, job.id)
        
        return job
    
    @staticmethod
    def ensure_migrated(contract: Contract, strategy: str = MigrationStrategy.ON_READ) -> Tuple[Optional[Dict[str, Any]], List[str]]:
        """
        Ensure contract is migrated to current version.
        
        Args:
            contract: Contract instance
            strategy: Migration strategy (ON_READ or ON_WRITE)
            
        Returns:
            Tuple of (migrated_hub_contract: Optional[Dict], warnings: List[str])
        """
        if strategy == MigrationStrategy.ON_WRITE:
            migrated, hub_contract, warnings = ContractMigrationManager.migrate_on_write(contract)
            if migrated:
                # Refresh from DB to get updated version
                contract.refresh_from_db()
                return contract.hub_contract_json, warnings
            return contract.hub_contract_json, warnings
        else:
            # ON_READ (lazy migration)
            return ContractMigrationManager.migrate_on_read(contract)

