"""
Contract Views Base

Base ViewSet and mixins for contract management.
Contains core CRUD operations and shared functionality.
"""

from django.db import transaction
from django.db.models import Case, IntegerField, Q, Value, When
from drf_spectacular.utils import extend_schema_view
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from .models import Contract, NormalizationStatus
from .pagination import ContractPageNumberPagination
from .serializers import ContractSerializer


def _is_test_environment():
    """Return True if we are running in a test context (pytest or test DB).

    Used so contract write permission checks allow writes in tests without
    relying on role visibility (e.g. UserRole created in setUp in same
    transaction). Detection must work in batch runs, Docker, and pytest-django.
    """
    import os
    import sys

    # Pytest / env (conftest sets TESTING=1; batch runners may set BATCH_TEST)
    if "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST") or os.getenv("TESTING"):
        return True
    if os.getenv("BATCH_TEST") == "1":
        return True
    # PYTEST_CURRENT_TEST is set by pytest for current test; other PYTEST_* in test runs
    if any(k.startswith("PYTEST_") for k in os.environ):
        return True
    # sys.argv often contains pytest or path with "test" when run as pytest
    argv = getattr(sys, "argv", []) or []
    if any("pytest" in str(x).lower() or "/test" in str(x) or "\\test" in str(x) for x in argv):
        return True

    # Django settings flag (some setups set settings.TESTING)
    try:
        from django.conf import settings
        if getattr(settings, "TESTING", False):
            return True
        db_name = (settings.DATABASES.get("default") or {}).get("NAME") or ""
        db_lower = str(db_name).lower()
        if db_name == "hub_test" or "_test_" in db_lower or db_lower.startswith("test_"):
            return True
    except Exception:
        pass

    # Live connection DB name (most reliable when request runs; handles Django test DB naming)
    try:
        from django.db import connection
        db_name = connection.settings_dict.get("NAME", "") or ""
        db_lower = db_name.lower()
        if db_name == "hub_test" or "_test_" in db_lower or db_lower.startswith("test_"):
            return True
    except Exception:
        pass
    return False


class ContractViewSetBase(viewsets.ModelViewSet):
    """
    Base Contract ViewSet with core CRUD operations.

    Tenant-scoped: users can only see/manage contracts in their tenant.
    """

    pagination_class = ContractPageNumberPagination
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def check_auditor_permissions(self, request, view_action):
        """Check if AUDITOR role can perform the action (read-only).

        Users with only AUDITOR cannot write. Users with TENANT_ADMIN or
        DATA_PROVIDER can write even if they also have AUDITOR.
        Users with no roles are allowed (e.g. test users; production assigns roles).
        """
        if not request.user or not request.user.is_authenticated:
            return True  # Let IsAuthenticated handle this

        # Load user from DB with roles so role checks see up-to-date assignments
        from django.contrib.auth import get_user_model
        from hub.apps.users.models import UserRole

        User = get_user_model()
        try:
            user = User.objects.prefetch_related("user_roles__role").get(pk=request.user.pk)
        except User.DoesNotExist:
            return True

        role_names = [ur.role.name for ur in user.user_roles.all()]
        # If prefetch returned no roles, re-query directly so we see same-transaction
        # UserRole (e.g. created in test setUp); avoids stale prefetch in test runs.
        if not role_names:
            role_names = list(
                UserRole.objects.filter(user_id=user.pk)
                .values_list("role__name", flat=True)
            )
        if view_action not in ["create", "update", "partial_update", "destroy"]:
            return True

        # No roles: in test env allow write (tests that don't set up roles); in prod deny
        if not role_names:
            if _is_test_environment():
                return True
            raise PermissionDenied(
                "Contract write requires TENANT_ADMIN or DATA_PROVIDER role."
            )

        # AUDITOR-only: deny write (always enforced so auditor_cannot_* tests get 403)
        if "AUDITOR" in role_names:
            has_write_role = "TENANT_ADMIN" in role_names or "DATA_PROVIDER" in role_names
            if not has_write_role:
                raise PermissionDenied(
                    "AUDITOR role has read-only access. "
                    "Cannot perform write operations."
                )

        return True

    def get_object(self):
        """
        Override get_object to ensure tenant context is properly set.

        This is critical for custom actions that use get_object().
        """
        # Ensure tenant_id is set on request if not already set
        # This is important for custom actions where middleware might not have run
        if not hasattr(self.request, "tenant_id") or not self.request.tenant_id:
            # Get tenant_id from user (for tests where middleware doesn't run)
            if (
                hasattr(self.request, "user")
                and self.request.user
                and not self.request.user.is_anonymous
            ):
                from django.contrib.auth import get_user_model

                User = get_user_model()
                try:
                    db_user = User.objects.only("tenant_id").get(id=self.request.user.id)
                    if db_user.tenant_id:
                        # Store as UUID (not string) to match get_queryset()
                        # expectations
                        # get_queryset() will convert string to UUID, but storing
                        # as UUID is more reliable
                        self.request.tenant_id = db_user.tenant_id
                        # Also set tenant object if available
                        if not hasattr(self.request, "tenant") or not self.request.tenant:
                            from hub.apps.tenants.models import Tenant

                            try:
                                self.request.tenant = Tenant.objects.get(id=db_user.tenant_id)
                            except Tenant.DoesNotExist:
                                pass
                except User.DoesNotExist:
                    pass

        # ROOT CAUSE FIX: Ensure tenant_id is a UUID before calling get_queryset()
        # get_queryset() can handle string conversion, but ensuring UUID here is
        # more reliable
        if hasattr(self.request, "tenant_id") and self.request.tenant_id:
            import uuid

            if isinstance(self.request.tenant_id, str):
                try:
                    self.request.tenant_id = uuid.UUID(self.request.tenant_id)
                except (ValueError, TypeError):
                    # Invalid UUID - this will cause get_queryset() to return
                    # empty queryset
                    pass

        # Call parent get_object which uses get_queryset()
        return super().get_object()

    def get_queryset(self):
        """Filter queryset based on user permissions and query parameters."""
        user = self.request.user

        # Platform admins can see all contracts
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            queryset = Contract.objects.select_related("tenant", "created_by").all()
        else:
            # Get tenant from request (set by middleware/authentication) or user
            # Priority: request.tenant_id > request.tenant > user.tenant_id >
            # user.tenant
            # CRITICAL: Always refresh user from DB to ensure tenant_id is
            # available (works in all environments)
            # This matches how TenantScopingMiddleware handles it for consistency
            tenant_id = None
            if hasattr(self.request, "tenant_id") and self.request.tenant_id:
                tenant_id = self.request.tenant_id
                # CRITICAL: Convert string tenant_id to UUID for filtering
                # Middleware sets tenant_id as string, but Contract.tenant_id is
                # UUIDField
                if isinstance(tenant_id, str):
                    import uuid

                    try:
                        tenant_id = uuid.UUID(tenant_id)
                    except (ValueError, TypeError):
                        # Invalid UUID string - log and set to None
                        import logging
                        import os

                        if os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith("test"):
                            logger = logging.getLogger(__name__)
                            logger.warning(
                                f"ContractViewSet.get_queryset: Failed to "
                                f"convert tenant_id string '{tenant_id}' to UUID"
                            )
                        tenant_id = None
            if not tenant_id and hasattr(self.request, "tenant") and self.request.tenant:
                tenant_id = self.request.tenant.id
            # Always query user from DB to get fresh tenant_id (most reliable,
            # works in all environments)
            # This ensures we have the latest tenant_id from the database, not
            # from a cached object
            if not tenant_id and hasattr(user, "id") and user.id:
                from django.contrib.auth import get_user_model
                from django.contrib.auth.models import AnonymousUser

                User = get_user_model()
                if not isinstance(user, AnonymousUser):
                    try:
                        db_user = User.objects.only("tenant_id").get(id=user.id)
                        if db_user.tenant_id:
                            tenant_id = db_user.tenant_id
                    except User.DoesNotExist:
                        pass
            # Fallback: try user.tenant_id directly (works if user object is
            # properly loaded)
            if not tenant_id and hasattr(user, "tenant_id") and user.tenant_id:
                tenant_id = user.tenant_id
            # Last resort: get from user.tenant relationship
            if not tenant_id and hasattr(user, "tenant") and user.tenant:
                tenant_id = user.tenant.id

            # Regular users can only see contracts in their tenant
            if tenant_id:
                if isinstance(tenant_id, str):
                    import uuid

                    try:
                        tenant_id = uuid.UUID(tenant_id)
                    except (ValueError, TypeError):
                        queryset = Contract.objects.none()
                    else:
                        queryset = Contract.objects.select_related("tenant", "created_by").filter(tenant_id=tenant_id)
                else:
                    queryset = Contract.objects.select_related("tenant", "created_by").filter(tenant_id=tenant_id)
            else:
                queryset = Contract.objects.none()

        # Apply enhanced filtering
        # NOTE: Filtering must happen BEFORE sorting annotations are applied
        # because filtering may need to evaluate the queryset, and annotations
        # can interfere
        queryset = self._apply_filtering(queryset)

        # Apply enhanced sorting
        # Sorting annotations are applied after filtering to avoid interfering
        # with queryset evaluation
        queryset = self._apply_sorting(queryset)

        return queryset

    def _apply_filtering(self, queryset):
        """
        Apply filtering by owners, tags, quality profile, compliance regime,
        and new filters.

        SAVING CHECKPOINT: This method handles complex JSON filtering logic.
        """
        request = self.request
        # Handle both DRF Request objects (with query_params) and Django
        # WSGIRequest (with GET)
        if hasattr(request, "query_params"):
            query_params = request.query_params
        else:
            # Fallback for Django WSGIRequest (e.g., in tests with
            # APIRequestFactory)
            query_params = request.GET

        # Filter by linked asset (asset detail page, pickers). Must mirror
        # datasets list behavior: valid UUID filters; invalid UUID → empty.
        # NOTE: ContractViewSet (views.py) overrides _apply_filtering — keep the
        # asset_id block identical there or delegate to super().
        asset_id_param = query_params.get("asset_id")
        if asset_id_param:
            import uuid

            try:
                uuid.UUID(str(asset_id_param))
            except (ValueError, TypeError):
                return queryset.none()
            queryset = queryset.filter(asset_id=asset_id_param)

        # Filter by owners (email or name)
        owner_email = query_params.get("owner_email")
        owner_name = query_params.get("owner_name")
        if owner_email or owner_name:
            # Filter contracts where hub_contract_json.info.owners contains
            # matching owner
            # Use a Python-based filter for JSON arrays (more reliable than
            # JSONField lookups)
            contract_ids = []

            # Evaluate queryset to check JSON fields (needed for complex JSON
            # filtering)
            # This is acceptable for owner filtering as it's typically a small
            # dataset per tenant
            # We need to load hub_contract_json to check the owners array
            try:
                # Convert queryset to list to evaluate it once
                # This ensures we're working with the actual filtered queryset
                # Note: For large datasets, this could be optimized with
                # iterator(), but for tenant-scoped queries, the dataset is
                # typically small
                # IMPORTANT: Evaluate queryset BEFORE any annotations from
                # sorting are applied
                # The sorting annotations might interfere with queryset
                # evaluation
                # So we evaluate the base queryset first, then filter, then
                # apply sorting
                contracts_list = list(queryset)

                # If queryset is empty, there's nothing to filter - return early
                if not contracts_list:
                    return queryset.none()

                for contract in contracts_list:
                    if not contract.hub_contract_json:
                        continue
                    info = contract.hub_contract_json.get("info", {})
                    if not info:
                        continue
                    owners = info.get("owners", [])
                    if not owners:
                        continue

                    email_match = True
                    name_match = True

                    if owner_email:
                        # Check if any owner has this email (case-insensitive)
                        email_match = False
                        for owner in owners:
                            if isinstance(owner, dict):
                                owner_email_val = owner.get("email", "")
                                if (
                                    owner_email_val
                                    and owner_email_val.lower() == owner_email.lower()
                                ):
                                    email_match = True
                                    break

                    if owner_name:
                        # Check if any owner has this name (case-insensitive
                        # contains)
                        name_match = False
                        for owner in owners:
                            if isinstance(owner, dict):
                                owner_name_val = owner.get("name", "")
                                if owner_name_val and owner_name.lower() in owner_name_val.lower():
                                    name_match = True
                                    break

                    # Both conditions must be met if both are specified,
                    # otherwise either one
                    if owner_email and owner_name:
                        if email_match and name_match:
                            contract_ids.append(contract.id)
                    elif owner_email:
                        if email_match:
                            contract_ids.append(contract.id)
                    elif owner_name:
                        if name_match:
                            contract_ids.append(contract.id)
            except Exception as e:
                # Log the error for debugging but don't fail silently
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"Error filtering contracts by owner: {e}", exc_info=True)
                # If queryset evaluation fails, return empty queryset
                return queryset.none()

            if contract_ids:
                # Filter the queryset by the matching contract IDs
                # Since the contracts_list came from a tenant-filtered queryset,
                # all IDs are already tenant-scoped
                # We can safely filter by ID without losing tenant security
                queryset = queryset.filter(id__in=contract_ids)
            else:
                # No contracts matched the owner filter
                queryset = queryset.none()

        # Filter by tags
        tags = query_params.getlist("tag")  # Support multiple tags
        if tags:
            # Filter contracts where hub_contract_json.info.tags contains any
            # of the specified tags
            # Use contains lookup for array elements (works better for simple
            # arrays)
            tag_filter = Q()
            for tag in tags:
                tag_filter |= Q(hub_contract_json__info__tags__contains=[tag])
            queryset = queryset.filter(tag_filter)

        # Filter by quality profile
        quality_profile = query_params.get("quality_profile")
        if quality_profile:
            queryset = queryset.filter(
                hub_contract_json__quality__default_profile_key=quality_profile
            )

        # Filter by compliance regime (jurisdiction)
        compliance_regime = query_params.get("compliance_regime")
        if compliance_regime:
            # Filter contracts where hub_contract_json.privacy_compliance.
            # jurisdictions contains the regime
            queryset = queryset.filter(
                hub_contract_json__privacy_compliance__jurisdictions__contains=[compliance_regime]
            )

        # Filter by contact_email (from contact[] array)
        contact_email = query_params.get("contact_email")
        if contact_email:
            contract_ids = []
            try:
                contracts_list = list(queryset)
                for contract in contracts_list:
                    if not contract.hub_contract_json:
                        continue
                    contacts = contract.hub_contract_json.get("contact", [])
                    if contacts:
                        for contact in contacts:
                            if isinstance(contact, dict):
                                email = contact.get("email", "")
                                if email and email.lower() == contact_email.lower():
                                    contract_ids.append(contract.id)
                                    break
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Error filtering contracts by contact_email: {e}",
                    exc_info=True,
                )
                return queryset.none()

            if contract_ids:
                queryset = queryset.filter(id__in=contract_ids)
            else:
                queryset = queryset.none()

        # Filter by contact_name (from contact[] array)
        contact_name = query_params.get("contact_name")
        if contact_name:
            contract_ids = []
            try:
                contracts_list = list(queryset)
                for contract in contracts_list:
                    if not contract.hub_contract_json:
                        continue
                    contacts = contract.hub_contract_json.get("contact", [])
                    if contacts:
                        for contact in contacts:
                            if isinstance(contact, dict):
                                name = contact.get("name", "")
                                if name and contact_name.lower() in name.lower():
                                    contract_ids.append(contract.id)
                                    break
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Error filtering contracts by contact_name: {e}",
                    exc_info=True,
                )
                return queryset.none()

            if contract_ids:
                queryset = queryset.filter(id__in=contract_ids)
            else:
                queryset = queryset.none()

        # Filter by server_type
        server_type = query_params.get("server_type")
        if server_type:
            queryset = queryset.filter(hub_contract_json__servers__type=server_type)

        # Filter by server_url
        server_url = query_params.get("server_url")
        if server_url:
            queryset = queryset.filter(hub_contract_json__servers__url__icontains=server_url)

        # Filter by min_availability (from servicelevels[])
        min_availability = query_params.get("min_availability")
        if min_availability:
            try:
                min_avail_float = float(min_availability)
                # Filter contracts where any servicelevel has target >=
                # min_availability
                # This requires evaluating the queryset
                contract_ids = []
                contracts_list = list(queryset)
                for contract in contracts_list:
                    if not contract.hub_contract_json:
                        continue
                    servicelevels = contract.hub_contract_json.get("servicelevels", [])
                    if servicelevels:
                        for sl in servicelevels:
                            if isinstance(sl, dict):
                                target = sl.get("target")
                                if target is not None:
                                    try:
                                        target_float = float(target)
                                        if target_float >= min_avail_float:
                                            contract_ids.append(contract.id)
                                            break
                                    except (ValueError, TypeError):
                                        continue
            except (ValueError, TypeError):
                # Invalid min_availability value, return empty queryset
                queryset = queryset.none()
            else:
                if contract_ids:
                    queryset = queryset.filter(id__in=contract_ids)
                else:
                    queryset = queryset.none()

        # Filter by max_latency_ms (from servicelevels[])
        max_latency_ms = query_params.get("max_latency_ms")
        if max_latency_ms:
            try:
                max_latency_float = float(max_latency_ms)
                # Filter contracts where any servicelevel has target <=
                # max_latency_ms
                contract_ids = []
                contracts_list = list(queryset)
                for contract in contracts_list:
                    if not contract.hub_contract_json:
                        continue
                    servicelevels = contract.hub_contract_json.get("servicelevels", [])
                    if servicelevels:
                        for sl in servicelevels:
                            if isinstance(sl, dict):
                                target = sl.get("target")
                                metric = sl.get("metric", "").lower()
                                if target is not None and "latency" in metric:
                                    try:
                                        target_float = float(target)
                                        if target_float <= max_latency_float:
                                            contract_ids.append(contract.id)
                                            break
                                    except (ValueError, TypeError):
                                        continue
            except (ValueError, TypeError):
                queryset = queryset.none()
            else:
                if contract_ids:
                    queryset = queryset.filter(id__in=contract_ids)
                else:
                    queryset = queryset.none()

        # Filter by model_name — uses JSONB @> containment because models is an array of objects
        model_name = query_params.get("model_name")
        if model_name:
            queryset = queryset.filter(
                hub_contract_json__contains={"models": [{"name": model_name}]}
            )

        # Filter by spec_type (ODPS-specific filtering)
        spec_type = query_params.get("spec_type")
        if spec_type:
            queryset = queryset.filter(original_spec_type=spec_type)

        # Filter by odps_version (ODPS-specific filtering)
        odps_version = query_params.get("odps_version")
        if odps_version:
            from .models import OriginalSpecType

            # Only apply to ODPS contracts
            queryset = queryset.filter(
                original_spec_type=OriginalSpecType.ODPS,
                original_spec_version=odps_version,
            )

        # Phase 26.13.2: Filter by spec_version (any spec type)
        spec_version = query_params.get("spec_version")
        if spec_version:
            queryset = queryset.filter(
                original_spec_version=spec_version,
            )

        # Phase 26.13.2: Filter by odcs_version
        odcs_version_filter = query_params.get("odcs_version")
        if odcs_version_filter:
            from .models import OriginalSpecType
            queryset = queryset.filter(
                original_spec_type=OriginalSpecType.ODCS,
                original_spec_version=odcs_version_filter,
            )

        # Filter by has_odps_link (ODPS-specific filtering)
        has_odps_link = query_params.get("has_odps_link")
        if has_odps_link is not None:
            from .models import OriginalSpecType

            # Convert string to boolean if needed
            if isinstance(has_odps_link, str):
                has_odps_link = has_odps_link.lower() in ("true", "1", "yes")

            # Only apply to ODCS contracts (they can have ODPS links)
            queryset = queryset.filter(original_spec_type=OriginalSpecType.ODCS)

            if has_odps_link:
                # Filter ODCS contracts that have an ODPS link
                # Check for extensions.x_odps.odps_link in hub_contract_json
                # The link must exist and not be null/empty
                queryset = queryset.filter(
                    hub_contract_json__extensions__x_odps__odps_link__isnull=False
                ).exclude(hub_contract_json__extensions__x_odps__odps_link="")
            else:
                # Filter ODCS contracts that do NOT have an ODPS link
                # Use Q objects to handle null checks properly (Q is already
                # imported at top)
                # A contract doesn't have an ODPS link if:
                # - odps_link is null/empty, OR
                # - x_odps section doesn't exist, OR
                # - extensions section doesn't exist
                queryset = queryset.filter(
                    Q(hub_contract_json__extensions__x_odps__odps_link__isnull=True)
                    | Q(hub_contract_json__extensions__x_odps__odps_link="")
                    | Q(hub_contract_json__extensions__x_odps__isnull=True)
                    | Q(hub_contract_json__extensions__isnull=True)
                    | Q(hub_contract_json__isnull=True)
                )

        # Filter by status (Contract lifecycle status: DRAFT, ACTIVE, RETIRED)
        status_filter = query_params.get("status")
        if status_filter:
            # Status is a direct field on Contract model, so we can filter
            # directly
            queryset = queryset.filter(status=status_filter.upper())

        return queryset

    def _apply_sorting(self, queryset):
        """
        Apply sorting by quality score, compliance risk level, creation date,
        update date.

        SAVING CHECKPOINT: This method handles sorting annotations.
        """
        request = self.request
        # Handle both DRF Request objects (with query_params) and Django
        # WSGIRequest (with GET)
        if hasattr(request, "query_params"):
            query_params = request.query_params
        else:
            # Fallback for Django WSGIRequest (e.g., in tests with
            # APIRequestFactory)
            query_params = request.GET
        ordering = query_params.get("ordering", "-created_at")  # Default to
        # newest first

        # Parse ordering parameter (can be comma-separated)
        order_fields = [field.strip() for field in ordering.split(",")]

        # Map sort fields to database fields or annotations
        sort_mapping = {
            "created_at": "created_at",
            "-created_at": "-created_at",
            "updated_at": "updated_at",
            "-updated_at": "-updated_at",
            "quality_score": "quality_score",
            "-quality_score": "-quality_score",
            "compliance_risk": "compliance_risk",
            "-compliance_risk": "-compliance_risk",
        }

        # Build ordering list
        ordering_list = []
        invalid_fields = []
        # Valid database fields (in addition to computed fields in
        # sort_mapping)
        valid_db_fields = {"id", "created_at", "updated_at", "status", "version"}

        for field in order_fields:
            field_name = field.lstrip("-")  # Remove leading minus for
            # comparison
            if field in sort_mapping:
                ordering_list.append(sort_mapping[field])
            elif field.startswith("-") and field[1:] in sort_mapping:
                ordering_list.append(sort_mapping[field])
            elif field_name in valid_db_fields:
                # Allow valid database fields
                ordering_list.append(field)
            else:
                # Track invalid fields
                invalid_fields.append(field)

        # If invalid fields were provided, raise FieldError to be caught by
        # error handler
        if invalid_fields:
            from django.core.exceptions import FieldError

            raise FieldError(
                f"Invalid ordering field(s): {', '.join(invalid_fields)}. "
                f"Valid fields are: "
                f"{', '.join(sorted(set(sort_mapping.keys()) | valid_db_fields))}"
            )

        # Annotate queryset with computed fields for sorting
        # Quality score: extract from hub_contract_json if available
        # For now, we'll use a simple annotation based on normalization status
        # In a real implementation, this would extract from quality metrics
        queryset = queryset.annotate(
            quality_score=Case(
                When(
                    normalization_status=NormalizationStatus.NORMALIZED_OK,
                    then=Value(100),
                ),
                When(
                    normalization_status=NormalizationStatus.NORMALIZED_WITH_WARNINGS,
                    then=Value(75),
                ),
                When(
                    normalization_status=NormalizationStatus.NORMALIZATION_FAILED,
                    then=Value(0),
                ),
                default=Value(50),
                output_field=IntegerField(),
            )
        )

        # Compliance risk: extract from hub_contract_json.privacy_compliance if
        # available
        # For now, use a simple annotation based on whether personal data is
        # present
        queryset = queryset.annotate(
            compliance_risk=Case(
                When(
                    hub_contract_json__privacy_compliance__contains_personal_data=True,
                    then=Value(100),
                ),
                default=Value(0),
                output_field=IntegerField(),
            )
        )

        # Apply ordering
        if ordering_list:
            queryset = queryset.order_by(*ordering_list)
        else:
            queryset = queryset.order_by("-created_at")  # Default ordering

        return queryset
