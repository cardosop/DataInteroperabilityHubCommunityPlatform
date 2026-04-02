"""
Transformation Signals — Phase 115C.1

Signal handlers that trigger event-based transformation pipelines
when dataset versions are created.

Pattern:
  - post_save on Dataset detects new version creation
  - Queries TransformationPipeline for ACTIVE pipelines that
    reference the dataset's asset in their metadata
  - Enqueues pipeline execution via RQ (transaction-safe)
  - Best-effort: failures logged at WARNING, never propagate
"""

import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="datasets.Dataset")
def trigger_transformation_on_dataset_version(
    sender, instance, created, **kwargs,
):
    """
    Trigger event-based transformation pipelines when a new
    dataset version is created.

    Only triggers when:
    - A new Dataset record is created (created=True)
    - The dataset is linked to an asset
    - ACTIVE transformation pipelines reference that asset
      in their metadata.source_asset_id
    """
    if not created:
        return

    try:
        asset_id = getattr(instance, "asset_id", None)
        if not asset_id:
            return

        tenant_id = str(instance.tenant_id) if instance.tenant_id else None
        if not tenant_id:
            return

        dataset_id = str(instance.pk)
        asset_id_str = str(asset_id)

        from hub.apps.transformation.models import (
            PipelineStatus,
            TransformationPipeline,
        )

        # Find ACTIVE pipelines that have this asset as source
        pipelines = TransformationPipeline.objects.filter(
            tenant_id=tenant_id,
            status=PipelineStatus.ACTIVE,
            metadata__source_asset_id=asset_id_str,
        )

        if not pipelines.exists():
            return

        logger.info(
            "transformation_trigger_dataset_version "
            "dataset_id=%s asset_id=%s pipeline_count=%d",
            dataset_id,
            asset_id_str,
            pipelines.count(),
        )

        for pipeline in pipelines:
            _enqueue_pipeline_execution(
                pipeline_id=str(pipeline.id),
                asset_id=asset_id_str,
                tenant_id=tenant_id,
                dataset_id=dataset_id,
            )

    except Exception as exc:
        logger.warning(
            "transformation_trigger_failed "
            "dataset_id=%s error=%s",
            instance.pk,
            exc,
        )


def _enqueue_pipeline_execution(
    pipeline_id: str,
    asset_id: str,
    tenant_id: str,
    dataset_id: str,
) -> None:
    """
    Enqueue a transformation pipeline execution via RQ.

    Uses transaction.on_commit to ensure the task is only enqueued
    after the enclosing transaction commits.
    """
    try:
        from hub.apps.core.events.publisher import EventPublisher

        publisher = EventPublisher(
            service_name="transformation_signals",
            tenant_id=tenant_id,
        )

        def _publish():
            try:
                publisher.publish(
                    event_type="transformation.pipeline.triggered",
                    data={
                        "pipeline_id": pipeline_id,
                        "asset_id": asset_id,
                        "tenant_id": tenant_id,
                        "dataset_id": dataset_id,
                        "trigger": "dataset_version_created",
                    },
                    tags=[
                        "transformation", "pipeline",
                        "triggered", "dataset_version",
                    ],
                    tenant_id=tenant_id,
                )
                logger.info(
                    "transformation_pipeline_triggered "
                    "pipeline_id=%s asset_id=%s dataset_id=%s",
                    pipeline_id,
                    asset_id,
                    dataset_id,
                )
            except Exception as exc:
                logger.warning(
                    "transformation_trigger_publish_failed "
                    "pipeline_id=%s error=%s",
                    pipeline_id,
                    exc,
                )

        transaction.on_commit(_publish)

    except Exception as exc:
        logger.warning(
            "transformation_enqueue_failed "
            "pipeline_id=%s error=%s",
            pipeline_id,
            exc,
        )
