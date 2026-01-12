"""
Comprehensive Test Data Factories

Test data factories for all models: User, Tenant, Asset, Contract, Dataset, Job, Marketplace, etc.
These factories create actual model instances with realistic test data (no mocks/stubs).

Features:
- Multi-tenant support
- Realistic test data generation
- Proper relationships between models
- Configurable defaults
"""
import uuid
from typing import Dict, Any, List, Optional
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from hub.apps.tenants.models import Tenant, TenantConfig, TenantStatus, KYCStatus
from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility, DQStatus, ComplianceStatus
from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType, OriginalFormat
from hub.apps.datasets.models import Dataset, DatasetKind
from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.marketplace.models import Listing, ListingStatus, PricingModel
from hub.apps.notifications.models import EmailDelivery, EmailDeliveryStatus, EmailType

# Import existing app-specific factories (imported inside methods to avoid circular imports)
# from hub.apps.assets.tests.factories import AssetFactory
# from hub.apps.files.tests.factories import FileFactory
# from hub.apps.datasets.tests.factories import DatasetFactory
# from hub.apps.contracts.tests.factories import ContractFactoryEnhanced

User = get_user_model()


class UserFactory:
    """Factory for creating User instances"""

    @staticmethod
    def create_user(
        email: Optional[str] = None,
        tenant: Optional[Tenant] = None,
        display_name: Optional[str] = None,
        status: Optional[str] = None,
        is_platform_admin: bool = False,
        **kwargs
    ) -> User:
        """
        Create a User instance.

        Args:
            email: User email (default: auto-generated)
            tenant: Tenant instance (required unless platform admin)
            display_name: User display name (default: auto-generated)
            status: User status (default: ACTIVE)
            is_platform_admin: Whether user is platform admin
            **kwargs: Additional fields

        Returns:
            User instance
        """
        if email is None:
            email = f"user_{uuid.uuid4().hex[:8]}@example.com"

        if tenant is None and not is_platform_admin:
            tenant = TenantFactory.create_tenant()

        if display_name is None:
            display_name = f"Test User {uuid.uuid4().hex[:6]}"

        if status is None:
            from hub.apps.users.models import UserStatus
            status = UserStatus.ACTIVE.value

        return User.objects.create(
            email=email,
            tenant=tenant,
            display_name=display_name,
            status=status,
            is_platform_admin=is_platform_admin,
            **kwargs
        )

    @staticmethod
    def create_platform_admin(email: Optional[str] = None, **kwargs) -> User:
        """Create a platform admin user"""
        if email is None:
            email = f"admin_{uuid.uuid4().hex[:8]}@example.com"
        return UserFactory.create_user(
            email=email,
            tenant=None,
            is_platform_admin=True,
            **kwargs
        )

    @staticmethod
    def create_users_for_tenant(tenant: Tenant, count: int = 3, **kwargs) -> List[User]:
        """Create multiple users for a tenant"""
        users = []
        for i in range(count):
            users.append(UserFactory.create_user(tenant=tenant, **kwargs))
        return users


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
            # Ensure slug is unique
            base_slug = slug
            counter = 1
            while Tenant.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

        return Tenant.objects.create(
            name=name,
            slug=slug,
            status=status,
            kyc_status=kyc_status,
            region=region,
            **kwargs
        )

    @staticmethod
    def create_verified_tenant(**kwargs) -> Tenant:
        """Create a verified tenant"""
        return TenantFactory.create_tenant(
            kyc_status=KYCStatus.VERIFIED,
            **kwargs
        )

    @staticmethod
    def create_tenant_with_config(**kwargs) -> Tenant:
        """Create a tenant with default config"""
        tenant = TenantFactory.create_tenant(**kwargs)
        TenantConfigFactory.create_tenant_config(tenant=tenant)
        return tenant


class TenantConfigFactory:
    """Factory for creating TenantConfig instances"""

    @staticmethod
    def create_tenant_config(
        tenant: Tenant,
        **kwargs
    ) -> TenantConfig:
        """
        Create a TenantConfig instance.

        Args:
            tenant: Tenant instance (required)
            **kwargs: Additional config fields

        Returns:
            TenantConfig instance
        """
        return TenantConfig.objects.create(
            tenant=tenant,
            **kwargs
        )


class AssetFactoryEnhanced:
    """Enhanced factory for creating Asset instances"""

    @staticmethod
    def create_asset(
        tenant: Optional[Tenant] = None,
        created_by: Optional[User] = None,
        key: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        domain: Optional[str] = None,
        status: AssetStatus = AssetStatus.ACTIVE,
        visibility: AssetVisibility = AssetVisibility.INTERNAL,
        dq_status: DQStatus = DQStatus.PASS,
        compliance_status: ComplianceStatus = ComplianceStatus.PASS,
        **kwargs
    ) -> Asset:
        """
        Create an Asset instance.

        Args:
            tenant: Tenant instance (default: auto-created)
            created_by: User who created the asset (default: auto-created)
            key: Asset key (default: auto-generated)
            name: Asset name (default: auto-generated)
            description: Asset description
            domain: Asset domain
            status: Asset status
            visibility: Asset visibility
            dq_status: Data quality status
            compliance_status: Compliance status
            **kwargs: Additional fields

        Returns:
            Asset instance
        """
        if tenant is None:
            tenant = TenantFactory.create_tenant()

        if created_by is None:
            created_by = UserFactory.create_user(tenant=tenant)

        if key is None:
            key = f"asset-{uuid.uuid4().hex[:8]}"

        if name is None:
            name = f"Test Asset {uuid.uuid4().hex[:6]}"

        # Import AssetFactory from app-specific factories
        from hub.apps.assets.tests.factories import AssetFactory as AppAssetFactory

        return AppAssetFactory.create_asset(
            tenant=tenant,
            created_by=created_by,
            key=key,
            name=name,
            description=description,
            domain=domain,
            status=status,
            visibility=visibility,
            dq_status=dq_status,
            compliance_status=compliance_status,
            **kwargs
        )


class ContractFactory:
    """Factory for creating Contract instances"""

    @staticmethod
    def create_contract(
        tenant: Optional[Tenant] = None,
        asset: Optional[Asset] = None,
        created_by: Optional[User] = None,
        original_spec_type: OriginalSpecType = OriginalSpecType.ODCS,
        original_spec_version: str = "3.0.2",
        original_format: OriginalFormat = OriginalFormat.JSON,
        original_raw: Optional[str] = None,
        status: ContractStatus = ContractStatus.ACTIVE,
        version: int = 1,
        **kwargs
    ) -> Contract:
        """
        Create a Contract instance.

        Args:
            tenant: Tenant instance (default: auto-created)
            asset: Asset instance (optional)
            created_by: User who created the contract
            original_spec_type: Original spec type
            original_spec_version: Original spec version
            original_format: Original format
            original_raw: Original contract content
            status: Contract status
            version: Contract version
            **kwargs: Additional fields

        Returns:
            Contract instance
        """
        if tenant is None:
            tenant = TenantFactory.create_tenant()

        if created_by is None:
            created_by = UserFactory.create_user(tenant=tenant)

        if asset is None:
            asset = AssetFactoryEnhanced.create_asset(tenant=tenant, created_by=created_by)

        # Import ContractFactoryEnhanced from app-specific factories
        from hub.apps.contracts.tests.factories import ContractFactoryEnhanced

        # ContractFactoryEnhanced doesn't accept original_raw, so create contract directly
        # if we need original_raw, we'll create it manually
        contract_kwargs = {
            "tenant": tenant,
            "created_by": created_by,
            "asset": asset,
            "version": version,
            "status": status,
            "original_spec_type": original_spec_type,
            "original_spec_version": original_spec_version,
            "original_format": original_format,
        }

        # Remove original_raw from kwargs if present
        kwargs.pop("original_raw", None)
        contract_kwargs.update(kwargs)

        contract = ContractFactoryEnhanced.create_contract(**contract_kwargs)

        # Set original_raw if provided
        if original_raw:
            contract.original_raw = original_raw
            contract.save()

        return contract


class DatasetFactoryEnhanced:
    """Enhanced factory for creating Dataset instances"""

    @staticmethod
    def create_dataset(
        tenant: Optional[Tenant] = None,
        asset: Optional[Asset] = None,
        file: Optional[File] = None,
        kind: DatasetKind = DatasetKind.FILE,
        name: Optional[str] = None,
        **kwargs
    ) -> Dataset:
        """
        Create a Dataset instance.

        Args:
            tenant: Tenant instance (default: auto-created)
            asset: Asset instance (optional)
            file: File instance (required for FILE kind)
            kind: Dataset kind
            name: Dataset name
            **kwargs: Additional fields

        Returns:
            Dataset instance
        """
        if tenant is None:
            tenant = TenantFactory.create_tenant()

        if asset is None:
            created_by = UserFactory.create_user(tenant=tenant)
            asset = AssetFactoryEnhanced.create_asset(tenant=tenant, created_by=created_by)

        if file is None and kind == DatasetKind.FILE:
            file = FileFactoryEnhanced.create_file(tenant=tenant)

        if name is None:
            name = f"Test Dataset {uuid.uuid4().hex[:6]}"

        # Import DatasetFactory from app-specific factories
        from hub.apps.datasets.tests.factories import DatasetFactory as AppDatasetFactory

        return AppDatasetFactory.create_dataset(
            tenant=tenant,
            file=file,
            asset=asset,
            **kwargs
        )


class JobFactoryEnhanced:
    """Enhanced factory for creating Job instances"""

    @staticmethod
    def create_job(
        tenant: Optional[Tenant] = None,
        type: Optional[JobType] = None,
        job_type: Optional[JobType] = None,  # Alias for type for backward compatibility
        status: JobStatus = JobStatus.PENDING,
        resource_type: Optional[str] = None,
        resource_id: Optional[uuid.UUID] = None,
        created_by: Optional[User] = None,
        started_at: Optional[timezone.datetime] = None,
        completed_at: Optional[timezone.datetime] = None,
        error_message: Optional[str] = None,
        result_json: Optional[Dict[str, Any]] = None,
        details_json: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Job:
        """
        Create a Job instance.

        Args:
            tenant: Tenant instance (nullable for system jobs)
            type: Job type (preferred parameter name)
            job_type: Job type (alias for type, for backward compatibility)
            status: Job status
            resource_type: Resource type
            resource_id: Resource ID
            created_by: User who created the job
            started_at: When job started
            completed_at: When job completed
            error_message: Error message if failed
            result_json: Job result data
            details_json: Job details
            **kwargs: Additional fields

        Returns:
            Job instance
        """
        # Handle job_type alias for backward compatibility
        if job_type is not None:
            if type is not None and type != job_type:
                raise ValueError("Cannot specify both 'type' and 'job_type' with different values")
            type = job_type
        elif type is None:
            type = JobType.DQ_RUN  # Default value

        if tenant is None and resource_type:
            tenant = TenantFactory.create_tenant()

        if created_by is None and tenant:
            created_by = UserFactory.create_user(tenant=tenant)

        if resource_type is None:
            resource_type = "CONTRACT"

        if resource_id is None:
            # Create a resource based on resource_type
            if resource_type == "ASSET" and tenant:
                asset = AssetFactoryEnhanced.create_asset(tenant=tenant, created_by=created_by)
                resource_id = asset.id
            elif resource_type == "CONTRACT" and tenant:
                contract = ContractFactory.create_contract(tenant=tenant)
                resource_id = contract.id
            else:
                resource_id = uuid.uuid4()

        if result_json is None:
            result_json = {}

        if details_json is None:
            details_json = {}

        # Set timestamps based on status
        if status == JobStatus.RUNNING and started_at is None:
            started_at = timezone.now()

        if status in [JobStatus.COMPLETED, JobStatus.FAILED] and completed_at is None:
            completed_at = timezone.now()
            if started_at is None:
                started_at = completed_at - timedelta(minutes=5)

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
            **kwargs
        )

    @staticmethod
    def create_completed_job(**kwargs) -> Job:
        """Create a completed job"""
        return JobFactoryEnhanced.create_job(
            status=JobStatus.COMPLETED,
            started_at=timezone.now() - timedelta(minutes=5),
            completed_at=timezone.now(),
            **kwargs
        )

    @staticmethod
    def create_failed_job(error_message: str = "Test error", **kwargs) -> Job:
        """Create a failed job"""
        return JobFactoryEnhanced.create_job(
            status=JobStatus.FAILED,
            started_at=timezone.now() - timedelta(minutes=5),
            completed_at=timezone.now(),
            error_message=error_message,
            **kwargs
        )


class FileFactoryEnhanced:
    """Enhanced factory for creating File instances"""

    @staticmethod
    def create_file(
        tenant: Optional[Tenant] = None,
        name: Optional[str] = None,
        status: FileStatus = FileStatus.ACTIVE,
        **kwargs
    ) -> File:
        """
        Create a File instance.

        Args:
            tenant: Tenant instance (default: auto-created)
            name: File name
            status: File status
            **kwargs: Additional fields

        Returns:
            File instance
        """
        if tenant is None:
            tenant = TenantFactory.create_tenant()

        if name is None:
            name = f"test_file_{uuid.uuid4().hex[:8]}.csv"

        # Import FileFactory from app-specific factories
        from hub.apps.files.tests.factories import FileFactory as AppFileFactory

        return AppFileFactory.create_file(
            tenant=tenant,
            name=name,
            status=status,
            **kwargs
        )


class ListingFactory:
    """Factory for creating Marketplace Listing instances"""

    @staticmethod
    def create_listing(
        tenant: Optional[Tenant] = None,
        asset: Optional[Asset] = None,
        status: ListingStatus = ListingStatus.DRAFT,
        pricing_model: PricingModel = PricingModel.FREE,
        metadata_json: Optional[Dict[str, Any]] = None,
        published_at: Optional[timezone.datetime] = None,
        **kwargs
    ) -> Listing:
        """
        Create a Listing instance.

        Args:
            tenant: Tenant instance (default: auto-created)
            asset: Asset instance (default: auto-created)
            status: Listing status
            pricing_model: Pricing model
            metadata_json: Listing metadata
            published_at: When listing was published
            **kwargs: Additional fields

        Returns:
            Listing instance
        """
        if tenant is None:
            tenant = TenantFactory.create_tenant()

        if asset is None:
            created_by = UserFactory.create_user(tenant=tenant)
            asset = AssetFactoryEnhanced.create_asset(tenant=tenant, created_by=created_by)

        if metadata_json is None:
            metadata_json = {
                "title": f"Test Listing {uuid.uuid4().hex[:6]}",
                "description": "Test marketplace listing",
                "short_description": "Test listing",
                "tags": ["test", "sample"],
                "domain": "test"
            }

        if status == ListingStatus.PUBLISHED and published_at is None:
            published_at = timezone.now()

        return Listing.objects.create(
            tenant=tenant,
            asset=asset,
            status=status,
            pricing_model=pricing_model,
            metadata_json=metadata_json,
            published_at=published_at,
            **kwargs
        )

    @staticmethod
    def create_published_listing(**kwargs) -> Listing:
        """Create a published listing"""
        return ListingFactory.create_listing(
            status=ListingStatus.PUBLISHED,
            published_at=timezone.now(),
            **kwargs
        )


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

        # Set timestamps based on status
        if status == EmailDeliveryStatus.SENT and sent_at is None:
            sent_at = timezone.now()

        if status == EmailDeliveryStatus.DELIVERED and delivered_at is None:
            delivered_at = timezone.now()
            if sent_at is None:
                sent_at = delivered_at - timedelta(seconds=5)

        if status == EmailDeliveryStatus.FAILED and failed_at is None:
            failed_at = timezone.now()

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


# Convenience instances (factories are callable classes)
UserFactory = UserFactory()
TenantFactory = TenantFactory()
TenantConfigFactory = TenantConfigFactory()
AssetFactory = AssetFactoryEnhanced()
ContractFactory = ContractFactory()
DatasetFactory = DatasetFactoryEnhanced()
JobFactory = JobFactoryEnhanced()
FileFactory = FileFactoryEnhanced()
ListingFactory = ListingFactory()
EmailDeliveryFactory = EmailDeliveryFactory()

