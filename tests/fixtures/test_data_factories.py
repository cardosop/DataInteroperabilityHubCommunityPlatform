"""

import uuid
Thin factory helpers for test data creation.

These factories wrap Django ORM calls so that test suites can use a
consistent API across the codebase without importing model classes
directly in each setUp method.  Each factory method accepts the same
keyword arguments as the underlying ORM create call.

All Django / app imports are deferred inside the factory methods so
the module can be imported by the test loader before Django's
application registry is populated.
"""
from __future__ import annotations


class TenantFactory:
    """Factory for ``Tenant`` instances."""

    @staticmethod
    def create_tenant(**kwargs):
        from hub.apps.tenants.models import Tenant
        return Tenant.objects.create(**kwargs)


class UserFactory:
    """Factory for ``User`` instances.

    Pass ``password=`` to set a password (delegated to
    ``User.objects.create_user``); if omitted the user is created
    with a default test password.
    """

    @staticmethod
    def create_user(**kwargs):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        password = kwargs.pop("password", "testpass123")
        email = kwargs.pop("email", None)
        if email is None:
            import uuid
            email = f"factory-{uuid.uuid4().hex[:8]}@test.example.com"
        return User.objects.create_user(email=email, password=password, **kwargs)

    @staticmethod
    def create_platform_admin(email=None, **kwargs):
        """Create a platform admin user (tenant=None, is_platform_admin=True)."""
        import uuid as _uuid
        if email is None:
            email = f"admin_{_uuid.uuid4().hex[:8]}@example.com"
        return UserFactory.create_user(
            email=email, tenant=None, is_platform_admin=True, **kwargs
        )

    @staticmethod
    def create_users_for_tenant(tenant, count=3, **kwargs):
        """Create multiple users for a tenant.  Returns a list of User instances."""
        import uuid as _uuid
        users = []
        for _ in range(count):
            email = kwargs.pop("email", None) or f"user-{_uuid.uuid4().hex[:8]}@example.com"
            users.append(UserFactory.create_user(email=email, tenant=tenant, **kwargs))
        return users


class AssetFactory:
    """Factory for ``Asset`` instances."""

    @staticmethod
    def create_asset(**kwargs):
        from hub.apps.assets.models import Asset
        return Asset.objects.create(**kwargs)


class ContractFactory:
    """Factory for ``Contract`` instances."""

    @staticmethod
    def create_contract(**kwargs):
        from hub.apps.contracts.models import Contract
        return Contract.objects.create(**kwargs)


class DatasetFactory:
    """Factory for ``Dataset`` instances."""

    @staticmethod
    def create_dataset(**kwargs):
        from hub.apps.datasets.models import Dataset
        return Dataset.objects.create(**kwargs)


class JobFactory:
    """Factory for ``Job`` instances."""

    @staticmethod
    def create_job(**kwargs):
        from hub.apps.jobs.models import Job
        return Job.objects.create(**kwargs)

    @staticmethod
    def create_failed_job(**kwargs):
        from hub.apps.jobs.models import Job, JobStatus
        error_message = kwargs.pop("error_message", "Test error message")
        kwargs.setdefault("status", JobStatus.FAILED)
        kwargs.setdefault("result", {"error": error_message})
        return Job.objects.create(**kwargs)

    @staticmethod
    def create_completed_job(**kwargs):
        from hub.apps.jobs.models import Job, JobStatus
        kwargs.setdefault("status", JobStatus.COMPLETED)
        kwargs.setdefault("result", {"message": "Job completed successfully"})
        return Job.objects.create(**kwargs)


class FileFactory:
    """Factory for ``File`` instances."""

    @staticmethod
    def create_file(**kwargs):
        from hub.apps.files.models import File
        return File.objects.create(**kwargs)


class ListingFactory:
    """Factory for ``Listing`` instances."""

    @staticmethod
    def create_listing(**kwargs):
        from hub.apps.marketplace.models import Listing
        return Listing.objects.create(**kwargs)


class EmailDeliveryFactory:
    """Factory for ``EmailDelivery`` instances."""

    @staticmethod
    def create_email_delivery(**kwargs):
        from hub.apps.notifications.models import EmailDelivery
        return EmailDelivery.objects.create(**kwargs)


class AssetFactoryEnhanced(AssetFactory):
    """Enhanced ``Asset`` factory — extends ``AssetFactory``.

    Supports additional fields such as ``health_score``, ``popularity_score``,
    ``view_count``, and ``last_accessed_at``.  The base ``create_asset(**kwargs)``
    already forwards every kwarg to ``Asset.objects.create``, so no override is
    necessary unless default values for the enhanced fields are desired.
    """


class DatasetFactoryEnhanced(DatasetFactory):
    """Enhanced ``Dataset`` factory — extends ``DatasetFactory``.

    Supports additional fields such as ``version_history`` and
    ``current_version``.  The base ``create_dataset(**kwargs)`` already forwards
    every kwarg to ``Dataset.objects.create``, so no override is necessary
    unless default values for the enhanced fields are desired.
    """
