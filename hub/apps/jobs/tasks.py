"""
Job Processing Tasks

Worker tasks for processing jobs.

This module imports from split modules:
- tasks_base: Core job processing infrastructure
- tasks_dq: DQ job handlers
- tasks_compliance: Compliance job handlers
- tasks_contract: Contract-related job handlers
- tasks_governance: Governance job handlers
- tasks_search: Search indexing job handlers
- tasks_odps: ODPS-related job handlers
- tasks_virtualization: Virtualization job handlers
- tasks_marketplace: Marketplace sync job handlers

SAVING CHECKPOINT: This module serves as the main entry point and imports
from specialized modules. Each handler module is < 700 lines per project rule.
"""

# Import core infrastructure from tasks_base
from .tasks_base import (
    _execute_job_logic,
    check_job_timeouts,
    process_job,
)

# Re-export job handlers for backward compatibility and testing
# (they are loaded dynamically in _execute_job_logic to avoid circular imports)
from .tasks_compliance import _execute_compliance_run_job
from .tasks_contract import (
    _execute_contract_migration_job,
    _execute_contract_validation_job,
    _execute_semantic_mapping_job,
)
from .tasks_dq import _execute_dq_run_job
from .tasks_odps import (
    _execute_odps_export_job,
    _execute_odps_linking_job,
    _execute_odps_normalization_job,
    _execute_odps_ref_resolution_job,
    _execute_odps_semantic_mapping_job,
)

__all__ = [
    "_execute_compliance_run_job",
    "_execute_contract_migration_job",
    "_execute_contract_validation_job",
    "_execute_dq_run_job",
    "_execute_job_logic",
    "_execute_odps_export_job",
    "_execute_odps_linking_job",
    "_execute_odps_normalization_job",
    "_execute_odps_ref_resolution_job",
    "_execute_odps_semantic_mapping_job",
    "_execute_semantic_mapping_job",
    "check_job_timeouts",
    "process_job",
]
