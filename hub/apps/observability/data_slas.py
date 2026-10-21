"""
Data SLA Service

Manages data SLAs for availability, freshness, and quality, and tracks compliance.
"""

from typing import Any

from django.db.models import Avg, Count, Q
from django.utils import timezone

from hub.apps.assets.models import Asset
from hub.apps.datasets.models import Dataset

from .models import DataSLA, PipelineExecution


class DataSLAMonitor:
    """
    Data SLA monitoring service for tracking compliance.
    """

    @staticmethod
    def create_sla(
        tenant_id: str,
        name: str,
        sla_type: str,
        dataset_id: str | None = None,
        asset_id: str | None = None,
        description: str | None = None,
        availability_target_percent: float | None = None,
        freshness_sla_seconds: int | None = None,
        quality_target_score: float | None = None,
        created_by_id: str | None = None,
    ) -> DataSLA:
        """
        Create a new data SLA.

        Args:
            tenant_id: Tenant UUID
            name: SLA name
            sla_type: Type of SLA (AVAILABILITY, FRESHNESS, QUALITY)
            dataset_id: Optional dataset UUID
            asset_id: Optional asset UUID
            description: Optional description
            availability_target_percent: Availability target (0-100)
            freshness_sla_seconds: Freshness SLA in seconds
            quality_target_score: Quality target (0.0-1.0)
            created_by_id: User UUID who created the SLA

        Returns:
            DataSLA instance
        """
        from django.contrib.auth import get_user_model

        from hub.apps.tenants.models import Tenant

        User = get_user_model()

        tenant = Tenant.objects.get(id=tenant_id)

        if not dataset_id and not asset_id:
            raise ValueError("Either dataset_id or asset_id must be provided")

        dataset = None
        asset = None

        if dataset_id:
            dataset = Dataset.objects.get(id=dataset_id, tenant=tenant)

        if asset_id:
            asset = Asset.objects.get(id=asset_id, tenant=tenant)

        created_by = None
        if created_by_id:
            created_by = User.objects.get(id=created_by_id)

        sla = DataSLA.objects.create(
            tenant=tenant,
            dataset=dataset,
            asset=asset,
            name=name,
            description=description,
            sla_type=sla_type,
            availability_target_percent=availability_target_percent,
            freshness_sla_seconds=freshness_sla_seconds,
            quality_target_score=quality_target_score,
            created_by=created_by,
        )

        return sla

    @staticmethod
    def check_compliance(sla_id: str) -> dict[str, Any]:
        """
        Check SLA compliance and update the SLA record.

        Args:
            sla_id: SLA UUID

        Returns:
            Compliance check result
        """
        sla = DataSLA.objects.get(id=sla_id)

        if not sla.is_active:
            return {
                "sla_id": str(sla.id),
                "is_compliant": None,
                "compliance_percent": None,
                "message": "SLA is not active",
            }

        compliance_percent = None
        is_violated = False

        if sla.sla_type == "AVAILABILITY":
            # Calculate availability based on pipeline executions

            # Get pipeline executions for the resource
            resource_type = "DATASET" if sla.dataset else "ASSET"
            resource_id = str(sla.dataset.id) if sla.dataset else str(sla.asset.id)

            # Get executions from last 30 days
            from datetime import timedelta

            since = timezone.now() - timedelta(days=30)

            executions = PipelineExecution.objects.filter(
                tenant=sla.tenant,
                resource_type=resource_type,
                resource_id=resource_id,
                created_at__gte=since,
            )

            total_executions = executions.count()
            successful_executions = executions.filter(status="COMPLETED").count()

            if total_executions > 0:
                compliance_percent = (successful_executions / total_executions) * 100
                is_violated = compliance_percent < sla.availability_target_percent
            else:
                compliance_percent = 100.0  # No data means no violations
                is_violated = False

        elif sla.sla_type == "FRESHNESS":
            # Check freshness from observability metrics
            resource = sla.dataset or sla.asset

            if resource:
                # Get latest freshness metric
                from .models import DataObservabilityMetric

                latest_metric = (
                    DataObservabilityMetric.objects.filter(
                        tenant=sla.tenant,
                        **({f"{'dataset' if sla.dataset else 'asset'}": resource}),
                    )
                    .order_by("-recorded_at")
                    .first()
                )

                if latest_metric and latest_metric.freshness_age_seconds is not None:
                    if sla.freshness_sla_seconds:
                        compliance_percent = max(
                            0,
                            100
                            - (
                                (latest_metric.freshness_age_seconds / sla.freshness_sla_seconds)
                                * 100
                            ),
                        )
                        is_violated = (
                            latest_metric.freshness_age_seconds > sla.freshness_sla_seconds
                        )
                    else:
                        compliance_percent = 100.0
                        is_violated = False
                else:
                    compliance_percent = 100.0  # No data means no violations
                    is_violated = False
            else:
                compliance_percent = 100.0
                is_violated = False

        elif sla.sla_type == "QUALITY":
            # Check quality from DQ runs
            from hub.apps.dq.models import DQRun, DQRunStatus

            resource = sla.dataset or sla.asset

            if resource:
                # Get latest DQ run
                latest_dq_run = (
                    DQRun.objects.filter(
                        tenant=sla.tenant,
                        asset=resource if sla.asset else None,
                        dataset=resource if sla.dataset else None,
                        status=DQRunStatus.SUCCEEDED,
                    )
                    .order_by("-completed_at")
                    .first()
                )

                if latest_dq_run and latest_dq_run.quality_score is not None:
                    # quality_score is 0-100, convert to 0-1 for comparison
                    quality_score_normalized = latest_dq_run.quality_score / 100.0
                    compliance_percent = latest_dq_run.quality_score
                    is_violated = quality_score_normalized < sla.quality_target_score
                else:
                    compliance_percent = 100.0  # No data means no violations
                    is_violated = False
            else:
                compliance_percent = 100.0
                is_violated = False

        # Update SLA record
        sla.current_compliance_percent = compliance_percent
        sla.last_compliance_check = timezone.now()

        if is_violated and not sla.is_violated:
            # New violation detected
            sla.violation_count += 1

        sla.is_violated = is_violated
        sla.save(
            update_fields=[
                "current_compliance_percent",
                "last_compliance_check",
                "is_violated",
                "violation_count",
                "updated_at",
            ]
        )

        return {
            "sla_id": str(sla.id),
            "is_compliant": not is_violated,
            "compliance_percent": round(compliance_percent, 2)
            if compliance_percent is not None
            else None,
            "is_violated": is_violated,
            "target": (
                sla.availability_target_percent
                if sla.sla_type == "AVAILABILITY"
                else sla.freshness_sla_seconds
                if sla.sla_type == "FRESHNESS"
                else sla.quality_target_score
                if sla.sla_type == "QUALITY"
                else None
            ),
        }

    @staticmethod
    def get_slas_dashboard(
        tenant_id: str,
        sla_type: str | None = None,
        dataset_id: str | None = None,
        asset_id: str | None = None,
        is_active: bool | None = None,
        is_violated: bool | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        Get data SLAs dashboard.

        Args:
            tenant_id: Tenant UUID
            sla_type: Optional SLA type filter
            dataset_id: Optional dataset UUID filter
            asset_id: Optional asset UUID filter
            is_active: Optional active filter
            is_violated: Optional violation filter
            limit: Maximum number of SLAs to return

        Returns:
            Dashboard data dictionary
        """
        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.get(id=tenant_id)

        # Build query
        query = Q(tenant=tenant)

        if sla_type:
            query &= Q(sla_type=sla_type)

        if dataset_id:
            query &= Q(dataset_id=dataset_id)

        if asset_id:
            query &= Q(asset_id=asset_id)

        if is_active is not None:
            query &= Q(is_active=is_active)

        if is_violated is not None:
            query &= Q(is_violated=is_violated)

        # Get SLAs
        slas = DataSLA.objects.filter(query).order_by("-created_at")[:limit]

        # Calculate statistics
        stats_query = DataSLA.objects.filter(tenant=tenant)

        total_slas = stats_query.count()
        active_slas = stats_query.filter(is_active=True).count()
        violated_slas = stats_query.filter(is_violated=True, is_active=True).count()

        # Get SLA type distribution
        sla_types = (
            stats_query.values("sla_type")
            .annotate(
                count=Count("id"),
                violated_count=Count("id", filter=Q(is_violated=True, is_active=True)),
            )
            .order_by("-count")
        )

        # Get average compliance by type
        avg_compliance = (
            stats_query.filter(is_active=True, current_compliance_percent__isnull=False)
            .values("sla_type")
            .annotate(avg_compliance=Avg("current_compliance_percent"))
        )

        return {
            "results": [
                {
                    "id": str(sla.id),
                    "name": sla.name,
                    "description": sla.description,
                    "sla_type": sla.sla_type,
                    "dataset_id": str(sla.dataset.id) if sla.dataset else None,
                    "asset_id": str(sla.asset.id) if sla.asset else None,
                    "availability_target_percent": sla.availability_target_percent,
                    "freshness_sla_seconds": sla.freshness_sla_seconds,
                    "quality_target_score": sla.quality_target_score,
                    "is_active": sla.is_active,
                    "current_compliance_percent": sla.current_compliance_percent,
                    "last_compliance_check": sla.last_compliance_check.isoformat()
                    if sla.last_compliance_check
                    else None,
                    "is_violated": sla.is_violated,
                    "violation_count": sla.violation_count,
                    "created_at": sla.created_at.isoformat(),
                    "updated_at": sla.updated_at.isoformat(),
                }
                for sla in slas
            ],
            "summary": {
                "total_slas": total_slas,
                "active_slas": active_slas,
                "violated_slas": violated_slas,
                "compliance_rate_percent": round(
                    ((active_slas - violated_slas) / active_slas * 100) if active_slas > 0 else 0.0,
                    2,
                ),
                "sla_types": list(sla_types),
                "avg_compliance_by_type": list(avg_compliance),
            },
        }

    @staticmethod
    def check_all_compliance(tenant_id: str, sla_type: str | None = None) -> dict[str, Any]:
        """
        Check compliance for all active SLAs.

        Args:
            tenant_id: Tenant UUID
            sla_type: Optional SLA type filter

        Returns:
            Compliance check results
        """
        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.get(id=tenant_id)

        query = Q(tenant=tenant, is_active=True)

        if sla_type:
            query &= Q(sla_type=sla_type)

        slas = DataSLA.objects.filter(query)

        results = []
        for sla in slas:
            result = DataSLAMonitor.check_compliance(str(sla.id))
            results.append(result)

        return {
            "checked_count": len(results),
            "compliant_count": sum(1 for r in results if r.get("is_compliant")),
            "violated_count": sum(1 for r in results if r.get("is_violated")),
            "results": results,
        }
