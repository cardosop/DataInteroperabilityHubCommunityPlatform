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
        import uuid as _uuid
        from hub.apps.tenants.models import Tenant

        # Ensure unique slug to prevent reuse-db collisions
        if "slug" not in kwargs and "name" in kwargs and kwargs["name"]:
            kwargs.setdefault(
                "slug",
                kwargs["name"].lower().replace(" ", "-")[:50]
                + f"-{_uuid.uuid4().hex[:8]}",
            )
        # Ensure unique name if not provided
        if "name" not in kwargs or kwargs["name"] is None:
            kwargs["name"] = f"Test Tenant {_uuid.uuid4().hex[:8]}"
        if "slug" not in kwargs or kwargs["slug"] is None:
            kwargs["slug"] = kwargs["name"].lower().replace(" ", "-")[:50]

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
        return UserFactory.create_user(email=email, tenant=None, is_platform_admin=True, **kwargs)

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
        import uuid as _uuid
        from hub.apps.assets.models import Asset

        # Ensure unique key per tenant to prevent reuse-db collisions
        if "key" not in kwargs or kwargs["key"] is None:
            kwargs["key"] = f"asset-{_uuid.uuid4().hex[:12]}"
        if "name" not in kwargs or kwargs["name"] is None:
            kwargs["name"] = f"Asset {_uuid.uuid4().hex[:8]}"

        return Asset.objects.create(**kwargs)


class ContractFactory:
    """Factory for ``Contract`` instances.

    Provides sensible defaults for all required fields so callers
    can create a minimal valid contract with ``create_contract(tenant=t)``.
    """

    @staticmethod
    def create_contract(**kwargs):
        from hub.apps.contracts.models import Contract, OriginalFormat, OriginalSpecType

        kwargs.setdefault("original_spec_type", OriginalSpecType.ODCS)
        kwargs.setdefault("original_spec_version", "3.0.2")
        kwargs.setdefault("original_format", OriginalFormat.JSON)
        kwargs.setdefault("original_raw", "{}")
        return Contract.objects.create(**kwargs)


class DatasetFactory:
    """Factory for ``Dataset`` instances.

    Creates a minimal File and attaches it when ``file`` is not provided.
    """

    @staticmethod
    def create_dataset(**kwargs):
        import uuid as _uuid
        from hub.apps.datasets.models import Dataset

        kwargs.setdefault("format", "CSV")
        if "file" not in kwargs:
            from hub.apps.files.models import File
            uid = _uuid.uuid4().hex[:12]
            kwargs["file"] = File.objects.create(
                tenant=kwargs.get("tenant"),
                name=f"dataset-file-{uid}",
                content_type="text/csv",
                size=1024,
                storage_path=f"/test/datasets/{uid}.csv",
            )
        return Dataset.objects.create(**kwargs)


class JobFactory:
    """Factory for ``Job`` instances.

    Provides defaults for ``type``, ``resource_type``, and ``resource_id``
    so callers can create a minimal valid job with ``create_job(tenant=t)``.
    """

    @staticmethod
    def create_job(**kwargs):
        import uuid as _uuid
        from hub.apps.jobs.models import Job, JobType

        kwargs.setdefault("type", JobType.DQ_RUN)
        kwargs.setdefault("resource_type", "CONTRACT")
        kwargs.setdefault("resource_id", _uuid.uuid4())
        return Job.objects.create(**kwargs)

    @staticmethod
    def create_failed_job(**kwargs):
        from hub.apps.jobs.models import Job, JobStatus

        error_message = kwargs.pop("error_message", "Test error message")
        kwargs.setdefault("status", JobStatus.FAILED)
        kwargs.setdefault("result_json", {"error": error_message})
        return Job.objects.create(**kwargs)

    @staticmethod
    def create_completed_job(**kwargs):
        from hub.apps.jobs.models import Job, JobStatus

        kwargs.setdefault("status", JobStatus.COMPLETED)
        kwargs.setdefault("result_json", {"message": "Job completed successfully"})
        return Job.objects.create(**kwargs)


class FileFactory:
    """Factory for ``File`` instances."""

    @staticmethod
    def create_file(**kwargs):
        from hub.apps.files.models import File

        return File.objects.create(**kwargs)


class ListingFactory:
    """Factory for ``Listing`` instances.

    Uses get_or_create semantics on (tenant, asset) to be idempotent
    across --reuse-db runs.
    """

    @staticmethod
    def create_listing(**kwargs):
        from django.db import IntegrityError
        from hub.apps.marketplace.models import Listing

        try:
            return Listing.objects.create(**kwargs)
        except IntegrityError:
            # reuse-db: listing already exists for this (tenant, asset)
            return Listing.objects.get(
                tenant=kwargs["tenant"],
                asset=kwargs.get("asset"),
            )


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
