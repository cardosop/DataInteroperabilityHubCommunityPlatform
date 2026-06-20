"""
Reference Validation Service

Provides UUID-based reference validation and retrieval for cross-app communication.
This service enables decoupling by allowing apps to reference resources in other apps
without direct model imports.
"""

from collections import defaultdict
from typing import Any, TypeVar

from django.db import models

from hub.apps.core.services.base import BaseService, NotFoundError, ValidationError

T = TypeVar("T", bound=models.Model)


class ReferenceService(BaseService):
    """
    Service for validating and retrieving cross-app references.

    This service provides a decoupled way to access resources from other apps
    without direct model imports, enabling better service boundaries.
    """

    service_name = "reference_service"

    # Registry of model classes by app name and model name
    _model_registry: dict[str, dict[str, type[models.Model]]] = {}

    @classmethod
    def register_model(cls, app_name: str, model_name: str, model_class: type[models.Model]):
        """
        Register a model class for reference resolution.

        Args:
            app_name: Django app name (e.g., 'assets')
            model_name: Model class name (e.g., 'Asset')
            model_class: Django model class
        """
        if app_name not in cls._model_registry:
            cls._model_registry[app_name] = {}
        cls._model_registry[app_name][model_name] = model_class

    @classmethod
    def get_model_class(cls, app_name: str, model_name: str) -> type[models.Model] | None:
        """
        Get model class from registry.

        Args:
            app_name: Django app name
            model_name: Model class name

        Returns:
            Model class or None if not registered
        """
        return cls._model_registry.get(app_name, {}).get(model_name)

    def validate_reference(
        self,
        app_name: str,
        model_name: str,
        resource_id: str,
        tenant_id: str | None = None,
        **filters,
    ) -> bool:
        """
        Validate that a reference exists and is accessible.

        Args:
            app_name: Django app name (e.g., 'assets')
            model_name: Model class name (e.g., 'Asset')
            resource_id: Resource UUID
            tenant_id: Optional tenant ID for tenant isolation
            **filters: Additional filters for validation

        Returns:
            True if reference is valid

        Raises:
            NotFoundError: If reference doesn't exist or is not accessible
            ValidationError: If app/model not registered
        """
        model_class = self.get_model_class(app_name, model_name)
        if not model_class:
            raise ValidationError(
                f"Model {app_name}.{model_name} is not registered in ReferenceService",
                details={"app_name": app_name, "model_name": model_name},
            )

        # Build query filters
        query_filters = {"id": resource_id, **filters}
        if tenant_id:
            query_filters["tenant_id"] = tenant_id

        # Check if resource exists
        exists = model_class.objects.filter(**query_filters).exists()
        if not exists:
            raise NotFoundError(f"{model_name}", resource_id)

        return True

    def get_reference(
        self,
        app_name: str,
        model_name: str,
        resource_id: str,
        tenant_id: str | None = None,
        **filters,
    ) -> models.Model:
        """
        Get a resource by reference.

        Args:
            app_name: Django app name (e.g., 'assets')
            model_name: Model class name (e.g., 'Asset')
            resource_id: Resource UUID
            tenant_id: Optional tenant ID for tenant isolation
            **filters: Additional filters

        Returns:
            Model instance

        Raises:
            NotFoundError: If resource doesn't exist
            ValidationError: If app/model not registered
        """
        model_class = self.get_model_class(app_name, model_name)
        if not model_class:
            raise ValidationError(
                f"Model {app_name}.{model_name} is not registered in ReferenceService",
                details={"app_name": app_name, "model_name": model_name},
            )

        # Build query filters
        query_filters = {"id": resource_id, **filters}
        if tenant_id:
            query_filters["tenant_id"] = tenant_id

        try:
            return model_class.objects.get(**query_filters)
        except model_class.DoesNotExist:
            raise NotFoundError(model_name, resource_id)

    def validate_multiple_references(
        self, references: list[dict[str, Any]], tenant_id: str | None = None
    ) -> dict[str, bool]:
        """
        Validate multiple references at once.

        Args:
            references: List of reference dicts with keys: app_name, model_name, resource_id
            tenant_id: Optional tenant ID for tenant isolation

        Returns:
            Dictionary mapping reference_id to validation result

        Raises:
            ValidationError: If any reference is invalid
        """
        results = {}
        for ref in references:
            ref_id = ref.get("resource_id") or ref.get("id")
            try:
                self.validate_reference(
                    app_name=ref["app_name"],
                    model_name=ref["model_name"],
                    resource_id=ref_id,
                    tenant_id=tenant_id,
                    **ref.get("filters", {}),
                )
                results[ref_id] = True
            except NotFoundError:
                results[ref_id] = False

        return results

    def get_multiple_references(
        self, references: list[dict[str, Any]], tenant_id: str | None = None
    ) -> dict[str, models.Model]:
        """
        Get multiple references at once using batch queries.

        Args:
            references: List of reference dicts with keys: app_name, model_name, resource_id
            tenant_id: Optional tenant ID for tenant isolation

        Returns:
            Dictionary mapping resource_id to model instance

        Raises:
            NotFoundError: If any reference doesn't exist
            ValidationError: If app/model not registered
        """
        # Group references by app and model for batch queries
        # Note: References with different filters are grouped separately
        grouped = defaultdict(list)
        for ref in references:
            app_name = ref["app_name"]
            model_name = ref["model_name"]
            ref_id = ref.get("resource_id") or ref.get("id")
            filters = ref.get("filters", {})
            # Create key that includes filters hash for grouping
            filters_key = str(sorted(filters.items())) if filters else ""
            key = f"{app_name}.{model_name}.{filters_key}"
            grouped[key].append({"id": ref_id, "filters": filters})

        results = {}

        # Process each group with batch query
        for key, refs in grouped.items():
            # Extract app_name and model_name from key
            parts = key.split(".", 2)
            app_name = parts[0]
            model_name = parts[1]
            filters = refs[0]["filters"] if refs else {}

            model_class = self.get_model_class(app_name, model_name)

            if not model_class:
                raise ValidationError(
                    f"Model {app_name}.{model_name} is not registered in ReferenceService",
                    details={"app_name": app_name, "model_name": model_name},
                )

            # Collect all IDs for batch query
            resource_ids = [ref["id"] for ref in refs]

            # Build base query
            query_filters = {"id__in": resource_ids}
            if tenant_id:
                query_filters["tenant_id"] = tenant_id

            # Apply additional filters if any
            query_filters.update(filters)

            # Execute batch query
            instances = model_class.objects.filter(**query_filters)

            # Map results by ID
            for instance in instances:
                results[str(instance.id)] = instance

            # Check for missing references
            found_ids = {str(inst.id) for inst in instances}
            for ref in refs:
                if ref["id"] not in found_ids:
                    raise NotFoundError(model_name, ref["id"])

        return results

    def bulk_validate(
        self,
        app_name: str,
        model_name: str,
        resource_ids: list[str],
        tenant_id: str | None = None,
        **filters,
    ) -> dict[str, bool]:
        """
        Bulk validate multiple references of the same type.

        More efficient than validate_multiple_references when all references
        are of the same app/model type.

        Args:
            app_name: Django app name
            model_name: Model class name
            resource_ids: List of resource UUIDs to validate
            tenant_id: Optional tenant ID for tenant isolation
            **filters: Additional filters

        Returns:
            Dictionary mapping resource_id to validation result (True/False)
        """
        model_class = self.get_model_class(app_name, model_name)
        if not model_class:
            raise ValidationError(
                f"Model {app_name}.{model_name} is not registered in ReferenceService",
                details={"app_name": app_name, "model_name": model_name},
            )

        # Build query filters
        query_filters = {"id__in": resource_ids, **filters}
        if tenant_id:
            query_filters["tenant_id"] = tenant_id

        # Execute batch query
        existing_ids = set(
            str(id)
            for id in model_class.objects.filter(**query_filters).values_list("id", flat=True)
        )

        # Build results dictionary
        results = {}
        for resource_id in resource_ids:
            results[resource_id] = resource_id in existing_ids

        return results


# Auto-register common models (lazy registration on first use)
_model_registration_done = False


def _register_common_models():
    """Register common models for reference resolution."""
    global _model_registration_done

    if _model_registration_done:
        return

    from django.apps import apps

    # Only register if Django apps are ready
    try:
        if not apps.ready:
            return
    except:
        return

    try:
        Asset = apps.get_model("assets", "Asset")
        ReferenceService.register_model("assets", "Asset", Asset)
    except (ImportError, LookupError):
        pass

    try:
        File = apps.get_model("files", "File")
        ReferenceService.register_model("files", "File", File)
    except (ImportError, LookupError):
        pass

    try:
        Dataset = apps.get_model("datasets", "Dataset")
        ReferenceService.register_model("datasets", "Dataset", Dataset)
    except (ImportError, LookupError):
        pass

    try:
        Contract = apps.get_model("contracts", "Contract")
        ReferenceService.register_model("contracts", "Contract", Contract)
    except (ImportError, LookupError):
        pass

    try:
        Tenant = apps.get_model("tenants", "Tenant")
        ReferenceService.register_model("tenants", "Tenant", Tenant)
    except (ImportError, LookupError):
        pass

    try:
        Job = apps.get_model("jobs", "Job")
        ReferenceService.register_model("jobs", "Job", Job)
    except (ImportError, LookupError):
        pass

    try:
        Listing = apps.get_model("marketplace", "Listing")
        ReferenceService.register_model("marketplace", "Listing", Listing)
    except (ImportError, LookupError):
        pass

    _model_registration_done = True


# Lazy registration - register models when ReferenceService is first used
# This is done in the get_model_class method to ensure Django is ready
_original_get_model_class = ReferenceService.get_model_class


@classmethod
def get_model_class_with_registration(cls, app_name: str, model_name: str):
    """Get model class with lazy registration."""
    _register_common_models()
    return _original_get_model_class(app_name, model_name)


ReferenceService.get_model_class = get_model_class_with_registration
