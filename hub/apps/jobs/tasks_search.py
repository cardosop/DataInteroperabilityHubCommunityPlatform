"""
Search Job Handlers

Handlers for Search indexing job execution.

SAVING CHECKPOINT: This module contains Search job handlers (< 700 lines per project rule).
"""

import structlog

from .models import Job

logger = structlog.get_logger(__name__)


def _execute_search_index_update_job(job_obj: Job) -> dict:
    """
    Execute SEARCH_INDEX_UPDATE job.

    Updates search index for a specific resource (contract, asset, or dataset).

    Args:
        job_obj: Job instance

    Returns:
        Result dictionary with indexing summary

    Raises:
        ValueError: For validation errors
        Exception: For other errors
    """
    from hub.apps.assets.models import Asset
    from hub.apps.contracts.models import Contract
    from hub.apps.datasets.models import Dataset
    from hub.apps.search.indexing import SearchIndexer

    resource_type = job_obj.resource_type
    resource_id = job_obj.resource_id

    logger.info(
        "Starting search index update",
        job_id=str(job_obj.id),
        resource_type=resource_type,
        resource_id=str(resource_id),
    )

    try:
        # Index based on resource type
        if resource_type == "CONTRACT":
            contract = Contract.objects.get(id=resource_id)
            search_index = SearchIndexer.index_contract(contract)
            indexed_type = "contract"
        elif resource_type == "ASSET":
            asset = Asset.objects.get(id=resource_id)
            search_index = SearchIndexer.index_asset(asset)
            indexed_type = "asset"
        elif resource_type == "DATASET":
            dataset = Dataset.objects.get(id=resource_id)
            search_index = SearchIndexer.index_dataset(dataset)
            indexed_type = "dataset"
        elif resource_type == "VIRTUAL_DATASET":
            from hub.apps.virtualization.models import VirtualDataset

            virtual_dataset = VirtualDataset.objects.get(id=resource_id)
            search_index = SearchIndexer.index_virtual_dataset(virtual_dataset)
            indexed_type = "virtual_dataset"
        else:
            raise ValueError(f"Unknown resource type for indexing: {resource_type}")

        logger.info(
            "Search index update completed",
            job_id=str(job_obj.id),
            resource_type=resource_type,
            resource_id=str(resource_id),
            search_index_id=str(search_index.id),
        )

        return {
            "success": True,
            "indexed_type": indexed_type,
            "search_index_id": str(search_index.id),
            "resource_type": resource_type,
            "resource_id": str(resource_id),
        }

    except Contract.DoesNotExist:
        raise ValueError(f"Contract {resource_id} not found")
    except Asset.DoesNotExist:
        raise ValueError(f"Asset {resource_id} not found")
    except Dataset.DoesNotExist:
        raise ValueError(f"Dataset {resource_id} not found")
    except Exception as e:
        # Check if it's a VirtualDataset.DoesNotExist
        from hub.apps.virtualization.models import VirtualDataset

        if isinstance(e, VirtualDataset.DoesNotExist):
            raise ValueError(f"VirtualDataset {resource_id} not found")
        # Log and re-raise other exceptions
        logger.error(
            "Search index update job failed",
            exc_info=True,
            job_id=str(job_obj.id),
            resource_type=resource_type,
            resource_id=str(resource_id),
            error=str(e),
        )
        raise
