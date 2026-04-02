"""
Attribute-Based Access Control (ABAC)

Policy evaluation engine for fine-grained access control.
"""

from typing import Any, Dict, List, Optional, Tuple

from django.core.cache import cache
from django.utils import timezone

from hub.apps.governance.models import ClassificationCategory, DataClassification

from .models import AccessPolicy, FieldAccessPolicy


class PolicyEvaluationResult:
    """Result of policy evaluation"""

    def __init__(
        self,
        allowed: bool,
        policy: Optional[AccessPolicy] = None,
        field_policies: Optional[List[FieldAccessPolicy]] = None,
        masking_required: bool = False,
    ):
        self.allowed = allowed
        self.policy = policy
        self.field_policies = field_policies or []
        self.masking_required = masking_required


class ABACEngine:
    """
    Attribute-Based Access Control evaluation engine.

    Evaluates access policies based on:
    - User attributes (role, department, clearance level)
    - Resource attributes (classification, owner, tags)
    - Environment attributes (time, location, IP)
    """

    CACHE_TTL = 300  # 5 minutes

    @staticmethod
    def evaluate_access(
        user_id: str,
        tenant_id: str,
        resource_type: str,
        resource_id: str,
        access_type: str = "READ",
        field_name: Optional[str] = None,
        user_attributes: Optional[Dict[str, Any]] = None,
        environment_attributes: Optional[Dict[str, Any]] = None,
    ) -> PolicyEvaluationResult:
        """
        Evaluate access for a user to a resource.

        Args:
            user_id: User UUID
            tenant_id: Tenant UUID
            resource_type: Resource type (ASSET, DATASET, FILE)
            resource_id: Resource UUID
            access_type: Access type (READ, WRITE, DOWNLOAD)
            field_name: Optional field name for field-level access
            user_attributes: Optional user attributes (role, department, etc.)
            environment_attributes: Optional environment attributes (time, IP, etc.)

        Returns:
            PolicyEvaluationResult
        """
        # Get user attributes if not provided
        if not user_attributes:
            user_attributes = ABACEngine._get_user_attributes(user_id)

        # Get resource attributes
        resource_attributes = ABACEngine._get_resource_attributes(
            resource_type, resource_id, tenant_id
        )

        # Get environment attributes if not provided
        if not environment_attributes:
            environment_attributes = ABACEngine._get_environment_attributes()

        # Get applicable policies
        policies = ABACEngine._get_applicable_policies(tenant_id, resource_type, resource_id)

        # Evaluate policies in priority order
        for policy in policies:
            if not policy.enabled:
                continue

            # Evaluate policy conditions
            matches = ABACEngine._evaluate_conditions(
                policy.conditions, user_attributes, resource_attributes, environment_attributes
            )

            if matches:
                # Policy matched, apply effect
                if policy.effect == "DENY":
                    return PolicyEvaluationResult(allowed=False, policy=policy)
                elif policy.effect == "ALLOW":
                    # Check field-level policies if field specified
                    field_policies = []
                    masking_required = False

                    if field_name and resource_type == "DATASET":
                        field_policies, masking_required = ABACEngine._get_field_policies(
                            tenant_id, resource_id, field_name, policy, access_type
                        )
                        # Field-level NONE or write-deny returns ([], True) — deny access
                        if not field_policies and masking_required:
                            return PolicyEvaluationResult(allowed=False, policy=policy)

                    # Audit field masking if applied
                    if masking_required and field_policies:
                        try:
                            from hub.apps.audit.utils import create_audit_event

                            masked_fields = [fp.field_name for fp in field_policies
                                             if fp.masking_strategy and fp.masking_strategy != "NONE"]
                            create_audit_event(
                                resource_type=resource_type,
                                action="FIELD_MASKING_APPLIED",
                                tenant=policy.tenant,
                                resource_id=resource_id,
                                details={
                                    "user_id": user_id,
                                    "masked_fields": masked_fields,
                                    "policy_id": str(policy.id),
                                    "masking_strategies": [
                                        fp.masking_strategy for fp in field_policies
                                        if fp.masking_strategy and fp.masking_strategy != "NONE"
                                    ],
                                },
                            )
                        except Exception:
                            pass  # Don't fail access eval on audit error

                    return PolicyEvaluationResult(
                        allowed=True,
                        policy=policy,
                        field_policies=field_policies,
                        masking_required=masking_required,
                    )

        # Default deny if no policy matches
        return PolicyEvaluationResult(allowed=False)

    @staticmethod
    def _get_user_attributes(user_id: str) -> Dict[str, Any]:
        """Get user attributes"""
        from hub.apps.users.models import User

        try:
            user = User.objects.get(id=user_id)
            # Get user roles
            user_roles = []
            if hasattr(user, "user_roles"):
                user_roles = [ur.role.name for ur in user.user_roles.all()]

            return {
                "user_id": str(user.id),
                "email": user.email,
                "tenant_id": str(user.tenant_id) if user.tenant_id else None,
                "status": user.status.value if hasattr(user.status, "value") else str(user.status),
                "user_roles": user_roles,
                # Add more attributes as needed
            }
        except User.DoesNotExist:
            return {"user_id": user_id, "user_roles": []}

    @staticmethod
    def _get_resource_attributes(
        resource_type: str, resource_id: str, tenant_id: str
    ) -> Dict[str, Any]:
        """Get resource attributes"""
        attributes = {
            "resource_type": resource_type,
            "resource_id": str(resource_id),
            "tenant_id": tenant_id,
        }

        # Get classification
        if resource_type == "DATASET":
            from hub.apps.datasets.models import Dataset

            try:
                dataset = Dataset.objects.get(id=resource_id, tenant_id=tenant_id)
                classifications = DataClassification.objects.filter(
                    tenant_id=tenant_id, dataset=dataset
                )

                # Get highest classification
                if classifications.exists():
                    highest_class = max(
                        classifications,
                        key=lambda c: ABACEngine._get_classification_priority(c.category),
                    )
                    attributes["classification"] = highest_class.category
                    attributes["classification_confidence"] = highest_class.confidence_score
            except Dataset.DoesNotExist:
                pass
        elif resource_type == "ASSET":
            from hub.apps.assets.models import Asset

            try:
                asset = Asset.objects.get(id=resource_id, tenant_id=tenant_id)
                attributes["asset_key"] = asset.key
                attributes["asset_status"] = (
                    asset.status.value if hasattr(asset.status, "value") else str(asset.status)
                )
            except Asset.DoesNotExist:
                pass
        elif resource_type == "VIRTUAL_DATASET":
            # Check if resource_id is a valid UUID (not a placeholder like "tenant:...:virtual_dataset:new")
            import uuid

            from hub.apps.virtualization.models import VirtualDataset

            try:
                # Try to parse as UUID
                uuid.UUID(resource_id)
                # If successful, try to get the virtual dataset
                try:
                    virtual_dataset = VirtualDataset.objects.get(
                        id=resource_id, tenant_id=tenant_id
                    )
                    attributes["virtual_dataset_name"] = virtual_dataset.name
                    attributes["virtual_dataset_status"] = (
                        virtual_dataset.status.value
                        if hasattr(virtual_dataset.status, "value")
                        else str(virtual_dataset.status)
                    )
                    attributes["virtual_dataset_version"] = virtual_dataset.version
                    if virtual_dataset.created_by:
                        attributes["virtual_dataset_owner_id"] = str(virtual_dataset.created_by.id)
                except VirtualDataset.DoesNotExist:
                    pass
            except (ValueError, TypeError):
                # Not a valid UUID, likely a placeholder for new resource creation
                # Set basic attributes for policy evaluation
                attributes["virtual_dataset_name"] = "new_virtual_dataset"
                attributes["virtual_dataset_status"] = "DRAFT"
                pass
        elif resource_type == "FILE":
            import uuid

            from hub.apps.files.models import File

            try:
                # Try to parse as UUID
                uuid.UUID(resource_id)
                # If successful, try to get the file
                try:
                    file_obj = File.objects.get(id=resource_id, tenant_id=tenant_id)
                    attributes["file_name"] = file_obj.name
                    attributes["file_status"] = file_obj.status
                    attributes["file_size"] = file_obj.size
                    attributes["file_content_type"] = file_obj.content_type
                    if file_obj.created_by:
                        attributes["file_owner_id"] = str(file_obj.created_by.id)
                except File.DoesNotExist:
                    pass
            except (ValueError, TypeError):
                # Not a valid UUID, likely a placeholder for new resource creation
                # Set basic attributes for policy evaluation
                attributes["file_name"] = "new_file"
                attributes["file_status"] = "PENDING"
                pass
        elif resource_type == "ML_MODEL":
            from hub.apps.ml.models import MLModel

            try:
                ml_model = MLModel.objects.get(
                    id=resource_id, tenant_id=tenant_id,
                )
                attributes["ml_model_name"] = ml_model.odh_model_name
                attributes["ml_model_type"] = ml_model.model_type
                attributes["ml_model_status"] = ml_model.status
                attributes["ml_model_version"] = (
                    ml_model.odh_model_version
                )
                if ml_model.asset_id:
                    attributes["ml_model_asset_id"] = str(
                        ml_model.asset_id,
                    )
            except MLModel.DoesNotExist:
                pass

        return attributes

    @staticmethod
    def _get_environment_attributes() -> Dict[str, Any]:
        """Get environment attributes"""
        return {
            "timestamp": timezone.now().isoformat(),
            "time_of_day": timezone.now().hour,
            "day_of_week": timezone.now().weekday(),
            # Add more environment attributes as needed
        }

    @staticmethod
    def _get_classification_priority(category: str) -> int:
        """Get classification priority (higher = more sensitive)"""
        priorities = {
            ClassificationCategory.PUBLIC.value: 1,
            ClassificationCategory.INTERNAL.value: 2,
            ClassificationCategory.CONFIDENTIAL.value: 3,
            ClassificationCategory.RESTRICTED.value: 4,
            ClassificationCategory.PII.value: 5,
            ClassificationCategory.PHI.value: 6,
            ClassificationCategory.PCI.value: 6,
            ClassificationCategory.FINANCIAL.value: 4,
            ClassificationCategory.LEGAL.value: 4,
        }
        return priorities.get(category, 2)

    @staticmethod
    def _get_applicable_policies(
        tenant_id: str, resource_type: str, resource_id: str
    ) -> List[AccessPolicy]:
        """Get applicable policies for a resource with caching"""
        cache_key = ABACEngine._get_cache_key(tenant_id, resource_type, resource_id)

        # Try to get from cache, but handle cache failures gracefully
        try:
            cached = cache.get(cache_key)
        except Exception:
            # If cache fails (e.g., Redis unavailable), proceed without cache
            cached = None

        if cached is not None:
            # Return cached policy IDs, then fetch policies
            policy_ids = cached
            policies = list(AccessPolicy.objects.filter(id__in=policy_ids).order_by("priority"))
        else:
            # Build query
            from django.db.models import Q

            queryset = AccessPolicy.objects.filter(tenant_id=tenant_id, enabled=True)

            # Filter by resource
            if resource_type == "ASSET":
                queryset = queryset.filter(Q(asset_id=resource_id) | Q(asset__isnull=True))
            elif resource_type == "DATASET":
                queryset = queryset.filter(Q(dataset_id=resource_id) | Q(dataset__isnull=True))
            elif resource_type == "DATA_MESH_DOMAIN":
                # For data mesh domains, check tenant-wide policies
                # (no specific domain field in AccessPolicy model yet)
                queryset = queryset.filter(Q(asset__isnull=True) & Q(dataset__isnull=True))
            elif resource_type == "VIRTUAL_DATASET":
                # For virtual datasets, check tenant-wide policies
                # (no specific virtual dataset field in AccessPolicy model yet)
                queryset = queryset.filter(Q(asset__isnull=True) & Q(dataset__isnull=True))
            elif resource_type == "FILE":
                # For files, check tenant-wide policies
                # (no specific file field in AccessPolicy model yet)
                queryset = queryset.filter(Q(asset__isnull=True) & Q(dataset__isnull=True))
            elif resource_type == "ML_MODEL":
                # For ML models, check tenant-wide policies
                queryset = queryset.filter(
                    Q(asset__isnull=True) & Q(dataset__isnull=True),
                )

            # Use select_related/prefetch_related to optimize query
            policies = list(queryset.select_related("tenant", "created_by").order_by("priority"))

            # Cache policy IDs with TTL (handle cache failures gracefully)
            try:
                policy_ids = [str(p.id) for p in policies]
                cache.set(cache_key, policy_ids, ABACEngine.CACHE_TTL)
            except Exception:
                # If cache fails, continue without caching
                pass

        return policies

    @staticmethod
    def _evaluate_conditions(
        conditions: Dict[str, Any],
        user_attributes: Dict[str, Any],
        resource_attributes: Dict[str, Any],
        environment_attributes: Dict[str, Any],
    ) -> bool:
        """
        Evaluate policy conditions.

        Conditions structure:
        {
            "user": {"role": "admin", "department": "IT"},
            "resource": {"classification": "PII"},
            "environment": {"time_of_day": {"$gte": 9, "$lte": 17}}
        }
        """
        # Evaluate user conditions
        if "user" in conditions:
            for key, value in conditions["user"].items():
                if key not in user_attributes:
                    return False
                # Handle list values (e.g., user_roles)
                if isinstance(value, list):
                    # Check if any value in the list matches
                    if isinstance(user_attributes[key], list):
                        if not any(v in user_attributes[key] for v in value):
                            return False
                    else:
                        if user_attributes[key] not in value:
                            return False
                elif user_attributes[key] != value:
                    return False

        # Evaluate resource conditions
        if "resource" in conditions:
            for key, value in conditions["resource"].items():
                # Map "type" to "resource_type" for backward compatibility
                attr_key = "resource_type" if key == "type" else key
                if attr_key not in resource_attributes:
                    return False
                if resource_attributes[attr_key] != value:
                    return False

        # Check resource_type condition if specified
        if "resource_type" in conditions:
            if resource_attributes.get("resource_type") != conditions["resource_type"]:
                return False

        # Evaluate environment conditions
        if "environment" in conditions:
            for key, condition in conditions["environment"].items():
                if key not in environment_attributes:
                    return False

                env_value = environment_attributes[key]

                # Support comparison operators
                if isinstance(condition, dict):
                    if "$gte" in condition and env_value < condition["$gte"]:
                        return False
                    if "$lte" in condition and env_value > condition["$lte"]:
                        return False
                    if "$gt" in condition and env_value <= condition["$gt"]:
                        return False
                    if "$lt" in condition and env_value >= condition["$lt"]:
                        return False
                elif env_value != condition:
                    return False

        return True

    @staticmethod
    def _get_field_policies(
        tenant_id: str,
        dataset_id: str,
        field_name: str,
        access_policy: AccessPolicy,
        access_type: str,
    ) -> Tuple[List[FieldAccessPolicy], bool]:
        """Get field-level policies and check if masking is required"""
        field_policies = list(
            FieldAccessPolicy.objects.filter(
                tenant_id=tenant_id,
                dataset_id=dataset_id,
                field_name=field_name,
                access_policy=access_policy,
                enabled=True,
            )
        )

        masking_required = False

        for field_policy in field_policies:
            # Check if access type is allowed
            if access_type == "READ" and field_policy.access_type == "NONE":
                return ([], True)  # Deny access

            if access_type == "WRITE" and field_policy.access_type != "WRITE":
                return ([], True)  # Deny write access

            # Check if masking is required
            if field_policy.masking_strategy and field_policy.masking_strategy != "NONE":
                masking_required = True

        return (field_policies, masking_required)

    @staticmethod
    def invalidate_policy_cache(
        tenant_id: str, resource_type: Optional[str] = None, resource_id: Optional[str] = None
    ):
        """Invalidate policy cache"""
        if resource_type and resource_id:
            cache_key = ABACEngine._get_cache_key(tenant_id, resource_type, resource_id)
            cache.delete(cache_key)
        else:
            # Invalidate all policies for tenant using cache versioning
            # Increment tenant cache version to invalidate all related caches
            version_key = f"abac_cache_version_{tenant_id}"
            current_version = cache.get(version_key, 0)
            cache.set(version_key, current_version + 1, timeout=None)  # Never expire

    @staticmethod
    def _get_cache_key(tenant_id: str, resource_type: str, resource_id: str) -> str:
        """Generate cache key with version"""
        version_key = f"abac_cache_version_{tenant_id}"
        version = cache.get(version_key, 0)
        return f"abac_policies_{tenant_id}_{resource_type}_{resource_id}_v{version}"
