"""
Test Factories for All Models

Real factories (not mocks) for creating test data for all models.
These factories create actual model instances with realistic test data.
"""
import uuid
from typing import Dict, Any, List, Optional
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from hub.apps.tenants.models import Tenant, TenantConfig, TenantStatus, KYCStatus
from hub.apps.notifications.models import EmailDelivery, EmailDeliveryStatus, EmailType
from hub.apps.jobs.models import Job, JobType, JobStatus

User = get_user_model()


class TenantFactory:
    """Factory for creating Tenant instances"""
    
    @staticmethod
    def create_tenant(
        name: Optional[str] = None,
        slug: Optional[str] = None,
        status: TenantStatus = TenantStatus.ACTIVE,
        kyc_status: KYCStatus = KYCStatus.UNVERIFIED,
        region: Optional[str] = None,
        **kwargs
    ) -> Tenant:
        """
        Create a Tenant instance.
        
        Args:
            name: Tenant name (default: auto-generated)
            slug: Tenant slug (default: auto-generated from name)
            status: Tenant status (default: ACTIVE)
            kyc_status: KYC status (default: UNVERIFIED)
            region: Cloud region (default: None)
            **kwargs: Additional fields
            
        Returns:
            Tenant instance
        """
        if name is None:
            name = f"Test Tenant {uuid.uuid4().hex[:8]}"
        if slug is None:
            slug = name.lower().replace(" ", "-")[:50]
        
        return Tenant.objects.create(
            name=name,
            slug=slug,
            status=status,
            kyc_status=kyc_status,
            region=region,
            **kwargs
        )


class TenantConfigFactory:
    """Factory for creating TenantConfig instances"""
    
    @staticmethod
    def create_tenant_config(
        tenant: Optional[Tenant] = None,
        default_dq_profile: Optional[str] = None,
        allowed_compliance_regimes: Optional[List[str]] = None,
        default_compliance_regimes: Optional[List[str]] = None,
        data_retention_days: Optional[int] = None,
        rate_limits: Optional[Dict[str, Any]] = None,
        max_file_size_bytes: Optional[int] = None,
        max_job_concurrency: Optional[int] = None,
        max_queued_jobs: Optional[int] = None,
        **kwargs
    ) -> TenantConfig:
        """
        Create a TenantConfig instance.
        
        Args:
            tenant: Tenant instance (required if not provided)
            default_dq_profile: Default DQ profile key
            allowed_compliance_regimes: List of allowed compliance regimes
            default_compliance_regimes: List of default compliance regimes
            data_retention_days: Data retention period in days (90-3650)
            rate_limits: Rate limits JSON structure
            max_file_size_bytes: Maximum file size in bytes
            max_job_concurrency: Maximum concurrent jobs
            max_queued_jobs: Maximum queued jobs
            **kwargs: Additional fields
            
        Returns:
            TenantConfig instance
        """
        if tenant is None:
            tenant = TenantFactory.create_tenant()
        
        if default_dq_profile is None:
            default_dq_profile = "intake_basic_gx"
        
        if allowed_compliance_regimes is None:
            allowed_compliance_regimes = ["GDPR", "LGPD", "CCPA"]
        
        if default_compliance_regimes is None:
            default_compliance_regimes = ["GDPR"]
        
        if data_retention_days is None:
            data_retention_days = 2555  # 7 years
        
        if rate_limits is None:
            rate_limits = {
                "read": {"requests_per_minute": 100, "requests_per_hour": 1000},
                "write": {"requests_per_minute": 50, "requests_per_hour": 500},
                "admin": {"requests_per_minute": 20, "requests_per_hour": 200}
            }
        
        if max_file_size_bytes is None:
            max_file_size_bytes = 10737418240  # 10 GB
        
        if max_job_concurrency is None:
            max_job_concurrency = 5
        
        if max_queued_jobs is None:
            max_queued_jobs = 50
        
        return TenantConfig.objects.create(
            tenant=tenant,
            default_dq_profile=default_dq_profile,
            allowed_compliance_regimes=allowed_compliance_regimes,
            default_compliance_regimes=default_compliance_regimes,
            data_retention_days=data_retention_days,
            rate_limits=rate_limits,
            max_file_size_bytes=max_file_size_bytes,
            max_job_concurrency=max_job_concurrency,
            max_queued_jobs=max_queued_jobs,
            **kwargs
        )
    
    @staticmethod
    def create_tenant_config_with_all_fields(tenant: Optional[Tenant] = None) -> TenantConfig:
        """
        Create a TenantConfig with all fields populated.
        
        This is a convenience method that creates a config with comprehensive test data.
        """
        return TenantConfigFactory.create_tenant_config(tenant=tenant)


class EmailDeliveryFactory:
    """Factory for creating EmailDelivery instances"""
    
    @staticmethod
    def create_email_delivery(
        email_type: EmailType = EmailType.USER_INVITATION,
        to_email: Optional[str] = None,
        subject: Optional[str] = None,
        status: EmailDeliveryStatus = EmailDeliveryStatus.PENDING,
        message_id: Optional[str] = None,
        error_message: Optional[str] = None,
        retry_count: int = 0,
        max_retries: int = 3,
        sent_at: Optional[timezone.datetime] = None,
        delivered_at: Optional[timezone.datetime] = None,
        failed_at: Optional[timezone.datetime] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> EmailDelivery:
        """
        Create an EmailDelivery instance.
        
        Args:
            email_type: Type of email
            to_email: Recipient email address
            subject: Email subject
            status: Delivery status
            message_id: Message ID from email service
            error_message: Error message if failed
            retry_count: Number of retry attempts
            max_retries: Maximum retry attempts
            sent_at: When email was sent
            delivered_at: When email was delivered
            failed_at: When email failed
            metadata_json: Additional metadata
            **kwargs: Additional fields
            
        Returns:
            EmailDelivery instance
        """
        if to_email is None:
            to_email = f"test-{uuid.uuid4().hex[:8]}@example.com"
        
        if subject is None:
            subject = f"Test {email_type.label} Email"
        
        if metadata_json is None:
            metadata_json = {}
        
        return EmailDelivery.objects.create(
            email_type=email_type,
            to_email=to_email,
            subject=subject,
            status=status,
            message_id=message_id,
            error_message=error_message,
            retry_count=retry_count,
            max_retries=max_retries,
            sent_at=sent_at,
            delivered_at=delivered_at,
            failed_at=failed_at,
            metadata_json=metadata_json,
            **kwargs
        )
    
    @staticmethod
    def create_email_delivery_with_all_statuses() -> List[EmailDelivery]:
        """
        Create EmailDelivery instances with all possible statuses.
        
        Returns:
            List of EmailDelivery instances
        """
        emails = []
        for status in EmailDeliveryStatus:
            emails.append(
                EmailDeliveryFactory.create_email_delivery(
                    status=status,
                    to_email=f"test-{status.value}@example.com"
                )
            )
        return emails
    
    @staticmethod
    def create_email_delivery_with_all_types() -> List[EmailDelivery]:
        """
        Create EmailDelivery instances with all possible email types.
        
        Returns:
            List of EmailDelivery instances
        """
        emails = []
        for email_type in EmailType:
            emails.append(
                EmailDeliveryFactory.create_email_delivery(
                    email_type=email_type,
                    to_email=f"test-{email_type.value}@example.com"
                )
            )
        return emails


class JobFactory:
    """Factory for creating Job instances"""
    
    @staticmethod
    def create_job(
        tenant: Optional[Tenant] = None,
        type: JobType = JobType.DQ_RUN,
        status: JobStatus = JobStatus.PENDING,
        resource_type: Optional[str] = None,
        resource_id: Optional[uuid.UUID] = None,
        created_by: Optional[User] = None,
        started_at: Optional[timezone.datetime] = None,
        completed_at: Optional[timezone.datetime] = None,
        error_message: Optional[str] = None,
        result_json: Optional[Dict[str, Any]] = None,
        details_json: Optional[Dict[str, Any]] = None,
        timeout_seconds: Optional[int] = None,
        **kwargs
    ) -> Job:
        """
        Create a Job instance.
        
        Args:
            tenant: Tenant instance (nullable for system jobs)
            type: Job type
            status: Job status
            resource_type: Resource type (e.g., "CONTRACT", "DATASET", "FILE", "ASSET")
            resource_id: Resource ID
            created_by: User who created the job
            started_at: When job started
            completed_at: When job completed
            error_message: Error message if failed
            result_json: Job result data
            details_json: Job details
            timeout_seconds: Job timeout in seconds
            **kwargs: Additional fields
            
        Returns:
            Job instance
        """
        if resource_type is None:
            resource_type = "CONTRACT"
        
        if resource_id is None:
            resource_id = uuid.uuid4()
        
        if result_json is None:
            result_json = {}
        
        if details_json is None:
            details_json = {}
        
        if timeout_seconds is None:
            timeout_seconds = 3600  # 1 hour
        
        return Job.objects.create(
            tenant=tenant,
            type=type,
            status=status,
            resource_type=resource_type,
            resource_id=resource_id,
            created_by=created_by,
            started_at=started_at,
            completed_at=completed_at,
            error_message=error_message,
            result_json=result_json,
            details_json=details_json,
            timeout_seconds=timeout_seconds,
            **kwargs
        )
    
    @staticmethod
    def create_job_with_all_types(tenant: Optional[Tenant] = None, created_by: Optional[User] = None) -> List[Job]:
        """
        Create Job instances with all possible job types.
        
        Args:
            tenant: Tenant instance
            created_by: User who created the jobs
            
        Returns:
            List of Job instances
        """
        jobs = []
        for job_type in JobType:
            jobs.append(
                JobFactory.create_job(
                    tenant=tenant,
                    type=job_type,
                    created_by=created_by,
                    resource_type="CONTRACT",
                    resource_id=uuid.uuid4()
                )
            )
        return jobs
    
    @staticmethod
    def create_job_with_all_statuses(tenant: Optional[Tenant] = None, created_by: Optional[User] = None) -> List[Job]:
        """
        Create Job instances with all possible job statuses.
        
        Args:
            tenant: Tenant instance
            created_by: User who created the jobs
            
        Returns:
            List of Job instances
        """
        jobs = []
        for status in JobStatus:
            jobs.append(
                JobFactory.create_job(
                    tenant=tenant,
                    status=status,
                    created_by=created_by,
                    resource_type="CONTRACT",
                    resource_id=uuid.uuid4()
                )
            )
        return jobs

