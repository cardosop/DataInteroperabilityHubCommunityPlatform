"""
Compliance Reporting

Generates compliance reports for GDPR, HIPAA, SOX, LGPD, and CCPA.
"""

from datetime import datetime, timedelta
from typing import Any

from django.utils import timezone

from hub.apps.compliance.models import ComplianceRun, RiskLevel
from hub.apps.governance.models import (
    AccessRequest,
    AccessRequestStatus,
    ClassificationCategory,
    DataClassification,
    RetentionPolicy,
)


class ComplianceReportGenerator:
    """
    Generates compliance reports for various regulations.
    """

    @staticmethod
    def generate_gdpr_report(
        tenant_id: str, start_date: datetime | None = None, end_date: datetime | None = None
    ) -> dict[str, Any]:
        """
        Generate GDPR compliance report.

        Args:
            tenant_id: Tenant UUID
            start_date: Start date for report period (optional)
            end_date: End date for report period (optional)

        Returns:
            GDPR compliance report dictionary
        """
        if not end_date:
            end_date = timezone.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Get compliance runs for GDPR
        compliance_runs = ComplianceRun.objects.filter(
            tenant_id=tenant_id,
            regulations__contains=["GDPR"],
            completed_at__gte=start_date,
            completed_at__lte=end_date,
        )

        # Get data classifications
        pii_classifications = DataClassification.objects.filter(
            tenant_id=tenant_id,
            category__in=[ClassificationCategory.PII.value, ClassificationCategory.PHI.value],
            created_at__gte=start_date,
            created_at__lte=end_date,
        )

        # Get retention policies
        retention_policies = RetentionPolicy.objects.filter(
            tenant_id=tenant_id, created_at__gte=start_date, created_at__lte=end_date
        )

        # Get access requests
        access_requests = AccessRequest.objects.filter(
            tenant_id=tenant_id, created_at__gte=start_date, created_at__lte=end_date
        )

        # Calculate metrics
        total_runs = compliance_runs.count()
        passed_runs = compliance_runs.filter(overall_status="PASS").count()
        failed_runs = compliance_runs.filter(overall_status="FAIL").count()
        warning_runs = compliance_runs.filter(overall_status="WARN").count()

        # Risk level distribution
        risk_distribution = {}
        for risk_level in RiskLevel.choices:
            count = compliance_runs.filter(risk_level=risk_level[0]).count()
            risk_distribution[risk_level[0]] = count

        # PII categories detected
        pii_categories = {}
        for run in compliance_runs:
            categories = run.detected_categories_json or {}
            for category, count in categories.items():
                pii_categories[category] = pii_categories.get(category, 0) + count

        # Data subject rights (access requests)
        access_requests_count = access_requests.count()
        approved_requests = access_requests.filter(
            status=AccessRequestStatus.APPROVED.value
        ).count()
        rejected_requests = access_requests.filter(
            status=AccessRequestStatus.REJECTED.value
        ).count()

        # Retention policies
        retention_policies_count = retention_policies.count()
        legal_hold_count = retention_policies.filter(legal_hold=True).count()

        return {
            "regulation": "GDPR",
            "report_period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "compliance_runs": {
                "total": total_runs,
                "passed": passed_runs,
                "failed": failed_runs,
                "warnings": warning_runs,
                "compliance_rate": (passed_runs / total_runs * 100) if total_runs > 0 else 0,
            },
            "risk_distribution": risk_distribution,
            "pii_detection": {
                "total_classifications": pii_classifications.count(),
                "categories_detected": pii_categories,
                "high_risk_fields": pii_classifications.filter(confidence_score__gte=0.9).count(),
            },
            "data_subject_rights": {
                "access_requests": access_requests_count,
                "approved": approved_requests,
                "rejected": rejected_requests,
                "approval_rate": (approved_requests / access_requests_count * 100)
                if access_requests_count > 0
                else 0,
            },
            "retention_management": {
                "total_policies": retention_policies_count,
                "legal_hold_active": legal_hold_count,
            },
            "generated_at": timezone.now().isoformat(),
        }

    @staticmethod
    def generate_hipaa_report(
        tenant_id: str, start_date: datetime | None = None, end_date: datetime | None = None
    ) -> dict[str, Any]:
        """
        Generate HIPAA compliance report.

        Args:
            tenant_id: Tenant UUID
            start_date: Start date for report period (optional)
            end_date: End date for report period (optional)

        Returns:
            HIPAA compliance report dictionary
        """
        if not end_date:
            end_date = timezone.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Get compliance runs for HIPAA
        compliance_runs = ComplianceRun.objects.filter(
            tenant_id=tenant_id,
            regulations__contains=["HIPAA"],
            completed_at__gte=start_date,
            completed_at__lte=end_date,
        )

        # Get PHI classifications
        phi_classifications = DataClassification.objects.filter(
            tenant_id=tenant_id,
            category=ClassificationCategory.PHI.value,
            created_at__gte=start_date,
            created_at__lte=end_date,
        )

        # Get access requests
        access_requests = AccessRequest.objects.filter(
            tenant_id=tenant_id, created_at__gte=start_date, created_at__lte=end_date
        )

        # Calculate metrics
        total_runs = compliance_runs.count()
        passed_runs = compliance_runs.filter(overall_status="PASS").count()
        failed_runs = compliance_runs.filter(overall_status="FAIL").count()

        # PHI detection
        phi_fields = phi_classifications.count()
        high_confidence_phi = phi_classifications.filter(confidence_score__gte=0.9).count()

        # Access controls
        access_requests_count = access_requests.count()
        approved_requests = access_requests.filter(
            status=AccessRequestStatus.APPROVED.value
        ).count()

        return {
            "regulation": "HIPAA",
            "report_period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "compliance_runs": {
                "total": total_runs,
                "passed": passed_runs,
                "failed": failed_runs,
                "compliance_rate": (passed_runs / total_runs * 100) if total_runs > 0 else 0,
            },
            "phi_detection": {
                "total_fields": phi_fields,
                "high_confidence_detections": high_confidence_phi,
                "detection_rate": (high_confidence_phi / phi_fields * 100) if phi_fields > 0 else 0,
            },
            "access_controls": {
                "total_requests": access_requests_count,
                "approved": approved_requests,
                "approval_rate": (approved_requests / access_requests_count * 100)
                if access_requests_count > 0
                else 0,
            },
            "generated_at": timezone.now().isoformat(),
        }

    @staticmethod
    def generate_sox_report(
        tenant_id: str, start_date: datetime | None = None, end_date: datetime | None = None
    ) -> dict[str, Any]:
        """
        Generate SOX compliance report.

        Args:
            tenant_id: Tenant UUID
            start_date: Start date for report period (optional)
            end_date: End date for report period (optional)

        Returns:
            SOX compliance report dictionary
        """
        if not end_date:
            end_date = timezone.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Get compliance runs for SOX
        compliance_runs = ComplianceRun.objects.filter(
            tenant_id=tenant_id,
            regulations__contains=["SOX"],
            completed_at__gte=start_date,
            completed_at__lte=end_date,
        )

        # Get financial classifications
        financial_classifications = DataClassification.objects.filter(
            tenant_id=tenant_id,
            category=ClassificationCategory.FINANCIAL.value,
            created_at__gte=start_date,
            created_at__lte=end_date,
        )

        # Get access requests
        access_requests = AccessRequest.objects.filter(
            tenant_id=tenant_id, created_at__gte=start_date, created_at__lte=end_date
        )

        # Calculate metrics
        total_runs = compliance_runs.count()
        passed_runs = compliance_runs.filter(overall_status="PASS").count()

        # Financial data
        financial_fields = financial_classifications.count()

        # Access controls
        access_requests_count = access_requests.count()
        approved_requests = access_requests.filter(
            status=AccessRequestStatus.APPROVED.value
        ).count()

        return {
            "regulation": "SOX",
            "report_period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "compliance_runs": {
                "total": total_runs,
                "passed": passed_runs,
                "compliance_rate": (passed_runs / total_runs * 100) if total_runs > 0 else 0,
            },
            "financial_data": {
                "total_fields": financial_fields,
                "classified_fields": financial_fields,
            },
            "access_controls": {
                "total_requests": access_requests_count,
                "approved": approved_requests,
                "approval_rate": (approved_requests / access_requests_count * 100)
                if access_requests_count > 0
                else 0,
            },
            "generated_at": timezone.now().isoformat(),
        }

    @staticmethod
    def generate_lgpd_report(
        tenant_id: str, start_date: datetime | None = None, end_date: datetime | None = None
    ) -> dict[str, Any]:
        """
        Generate LGPD compliance report.

        Args:
            tenant_id: Tenant UUID
            start_date: Start date for report period (optional)
            end_date: End date for report period (optional)

        Returns:
            LGPD compliance report dictionary
        """
        if not end_date:
            end_date = timezone.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Get compliance runs for LGPD
        compliance_runs = ComplianceRun.objects.filter(
            tenant_id=tenant_id,
            regulations__contains=["LGPD"],
            completed_at__gte=start_date,
            completed_at__lte=end_date,
        )

        # Get PII classifications
        pii_classifications = DataClassification.objects.filter(
            tenant_id=tenant_id,
            category=ClassificationCategory.PII.value,
            created_at__gte=start_date,
            created_at__lte=end_date,
        )

        # Get access requests
        access_requests = AccessRequest.objects.filter(
            tenant_id=tenant_id, created_at__gte=start_date, created_at__lte=end_date
        )

        # Calculate metrics
        total_runs = compliance_runs.count()
        passed_runs = compliance_runs.filter(overall_status="PASS").count()

        # PII detection
        pii_fields = pii_classifications.count()

        # Data subject rights
        access_requests_count = access_requests.count()
        approved_requests = access_requests.filter(
            status=AccessRequestStatus.APPROVED.value
        ).count()

        return {
            "regulation": "LGPD",
            "report_period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "compliance_runs": {
                "total": total_runs,
                "passed": passed_runs,
                "compliance_rate": (passed_runs / total_runs * 100) if total_runs > 0 else 0,
            },
            "pii_detection": {"total_fields": pii_fields, "classified_fields": pii_fields},
            "data_subject_rights": {
                "access_requests": access_requests_count,
                "approved": approved_requests,
                "approval_rate": (approved_requests / access_requests_count * 100)
                if access_requests_count > 0
                else 0,
            },
            "generated_at": timezone.now().isoformat(),
        }

    @staticmethod
    def generate_ccpa_report(
        tenant_id: str, start_date: datetime | None = None, end_date: datetime | None = None
    ) -> dict[str, Any]:
        """
        Generate CCPA compliance report.

        Args:
            tenant_id: Tenant UUID
            start_date: Start date for report period (optional)
            end_date: End date for report period (optional)

        Returns:
            CCPA compliance report dictionary
        """
        if not end_date:
            end_date = timezone.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Get compliance runs for CCPA
        compliance_runs = ComplianceRun.objects.filter(
            tenant_id=tenant_id,
            regulations__contains=["CCPA"],
            completed_at__gte=start_date,
            completed_at__lte=end_date,
        )

        # Get PII classifications
        pii_classifications = DataClassification.objects.filter(
            tenant_id=tenant_id,
            category=ClassificationCategory.PII.value,
            created_at__gte=start_date,
            created_at__lte=end_date,
        )

        # Get access requests
        access_requests = AccessRequest.objects.filter(
            tenant_id=tenant_id, created_at__gte=start_date, created_at__lte=end_date
        )

        # Calculate metrics
        total_runs = compliance_runs.count()
        passed_runs = compliance_runs.filter(overall_status="PASS").count()

        # PII detection
        pii_fields = pii_classifications.count()

        # Consumer rights (access requests)
        access_requests_count = access_requests.count()
        approved_requests = access_requests.filter(
            status=AccessRequestStatus.APPROVED.value
        ).count()

        return {
            "regulation": "CCPA",
            "report_period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "compliance_runs": {
                "total": total_runs,
                "passed": passed_runs,
                "compliance_rate": (passed_runs / total_runs * 100) if total_runs > 0 else 0,
            },
            "pii_detection": {"total_fields": pii_fields, "classified_fields": pii_fields},
            "consumer_rights": {
                "access_requests": access_requests_count,
                "approved": approved_requests,
                "approval_rate": (approved_requests / access_requests_count * 100)
                if access_requests_count > 0
                else 0,
            },
            "generated_at": timezone.now().isoformat(),
        }
