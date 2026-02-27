"""
Files Business Rules

Comprehensive business rules validation for file operations, including:
- File validation
- Tenant and user context validation
- File access and permissions validation
- File upload validation (size, type, name, content)

All validation methods follow engineering best practices:
- No mocks/stubs - use real services and models
- Fix root causes, not symptoms
- Comprehensive error messages with context
- Follow DRY, SOLID, and clean code principles
"""
import logging
import re
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from dataclasses import dataclass
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError

from hub.apps.core.business_rules.base import (
    BusinessRules,
    RuleExecutionContext,
    ValidationResult,
)
from hub.apps.core.business_rules.registry import register_rule
from hub.apps.files.models import File, FileStatus
from hub.apps.users.models import User
from hub.apps.files.validators import validate_file_size as django_validate_file_size, validate_file_type as django_validate_file_type

if TYPE_CHECKING:
    from hub.apps.tenants.models import Tenant

logger = logging.getLogger(__name__)


@dataclass
class FilesRuleExecutionContext(RuleExecutionContext):
    """
    Extended execution context for files business rules.

    Adds file-specific context:
    - file: The file being validated
    - tenant: Optional tenant instance for validation
    - user: Optional user instance for permission validation
    """
    file: Optional[File] = None
    tenant: Optional[Any] = None  # Using Any to avoid circular import
    user: Optional[User] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for caching/logging."""
        base_dict = super().to_dict()
        # Add file-specific fields
        base_dict.update({
            'file_id': str(self.file.id) if self.file else None,
            'file_name': self.file.name if self.file else None,
            'file_status': self.file.status if self.file else None,
        })
        # Add tenant and user IDs from objects if provided (base_dict already has tenant_id/user_id from context)
        if self.tenant:
            base_dict['tenant_id_from_object'] = str(self.tenant.id)
        if self.user:
            base_dict['user_id_from_object'] = str(self.user.id)
        return base_dict


@register_rule(
    rule_name="files_validation",
    description="Validates files, tenant context, and file access permissions",
    tags=["files", "validation", "storage"],
    priority=10
)
class FilesBusinessRules(BusinessRules):
    """
    Business rules validator for file operations.

    Extends BusinessRules base class with file-specific validation:
    - File validation
    - Tenant context consistency
    - User permissions and access validation
    - File status validation
    """

    def get_rule_name(self) -> str:
        """Return the rule name for metrics and logging."""
        return "FilesBusinessRules"

    def validate(
        self,
        context: Optional[RuleExecutionContext] = None,
        *args,
        **kwargs
    ) -> ValidationResult:
        """
        Main validation method required by BusinessRules base class.

        This method orchestrates all file validation checks.
        It can be called with a FilesRuleExecutionContext or a standard
        RuleExecutionContext. If a standard context is provided, it extracts
        file, tenant, and user from kwargs or context.metadata.

        Args:
            context: Optional rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments:
                - file: File instance (optional)
                - tenant: Optional tenant instance
                - user: Optional user instance
                - validation_type: Optional validation type filter
                    ('file', 'tenant_context', 'permissions', 'all')

        Returns:
            ValidationResult with validation status and details
        """
        # Extract file, tenant, and user from context or kwargs
        if isinstance(context, FilesRuleExecutionContext):
            file = context.file
            tenant = context.tenant
            user = context.user
        else:
            # Try to get from kwargs first
            file = kwargs.get('file')
            tenant = kwargs.get('tenant')
            user = kwargs.get('user')

            # If not in kwargs, try to get from context.metadata or context.resource
            if context and hasattr(context, 'metadata') and isinstance(context.metadata, dict):
                file = file or context.metadata.get('file')
                tenant = tenant or context.metadata.get('tenant')
                user = user or context.metadata.get('user')

            # Also check context.resource
            if not file and context and hasattr(context, 'resource'):
                if isinstance(context.resource, File):
                    file = context.resource

        # Determine what to validate based on what's provided
        validation_type = kwargs.get('validation_type', 'all')

        # Initialize result
        result = ValidationResult(is_valid=True)
        result.details['files_validation'] = 'files'

        # Track what was validated
        validated_items = []

        # Validate file if provided
        if file and validation_type in ('file', 'all'):
            file_result = self._validate_file(file, tenant, user)
            result = result.combine(file_result)
            validated_items.append('file')

        # Validate tenant context if provided
        if tenant and validation_type in ('tenant_context', 'all'):
            tenant_result = self._validate_tenant_context(tenant)
            result = result.combine(tenant_result)
            validated_items.append('tenant_context')

        # Validate user permissions if provided
        if user and validation_type in ('permissions', 'all'):
            permissions_result = self._validate_user_permissions(file, tenant, user)
            result = result.combine(permissions_result)
            validated_items.append('permissions')

        # Validate storage quota if tenant provided
        if tenant and validation_type in ('storage_quota', 'all'):
            storage_quota_result = self.validate_storage_quota(
                file=file,
                tenant=tenant,
                file_size=file.size if file else None
            )
            result = result.combine(storage_quota_result)
            validated_items.append('storage_quota')

        # Update result details
        result.details['validated_items'] = validated_items
        result.details['validation_type'] = validation_type

        return result

    def _validate_file(
        self,
        file: File,
        tenant: Optional[Any] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate file structure and properties.

        Args:
            file: File instance to validate
            tenant: Optional tenant instance for cross-validation
            user: Optional user instance for permission validation

        Returns:
            ValidationResult with file validation status
        """
        errors = []
        warnings = []
        details = {
            'file_validation': 'file',
        }

        # Validate file instance
        if not isinstance(file, File):
            errors.append(f"Expected File instance, got {type(file).__name__}")
            details['file_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['file_id'] = str(file.id)
        details['file_name'] = file.name
        details['file_status'] = file.status

        # Validate file name
        if not file.name or not file.name.strip():
            errors.append("File name is required and cannot be empty")
            details['file_name_valid'] = False
        else:
            details['file_name_valid'] = True

        # Validate file size
        if file.size is None or file.size < 0:
            errors.append(f"File size must be non-negative, got: {file.size}")
            details['file_size_valid'] = False
        else:
            details['file_size_valid'] = True
            details['file_size'] = file.size

        # Validate file status
        if file.status not in FileStatus.values:
            errors.append(
                f"Invalid file status '{file.status}'. "
                f"Valid statuses are: {', '.join(FileStatus.values)}"
            )
            details['file_status_valid'] = False
        else:
            details['file_status_valid'] = True

        # Validate content type
        if not file.content_type or not file.content_type.strip():
            warnings.append("File content_type is missing or empty")
            details['content_type_valid'] = False
        else:
            details['content_type_valid'] = True
            details['content_type'] = file.content_type

        # Validate storage path
        if not file.storage_path or not file.storage_path.strip():
            errors.append("File storage_path is required and cannot be empty")
            details['storage_path_valid'] = False
        else:
            details['storage_path_valid'] = True
            details['storage_path'] = file.storage_path

        # Cross-validate with tenant if provided
        if tenant:
            if file.tenant_id != tenant.id:
                errors.append(
                    f"File tenant_id ({file.tenant_id}) does not match "
                    f"provided tenant id ({tenant.id})"
                )
                details['tenant_match'] = False
            else:
                details['tenant_match'] = True

        # Cross-validate with user if provided
        if user:
            if file.created_by_id and file.created_by_id != user.id:
                warnings.append(
                    f"File created_by_id ({file.created_by_id}) does not match "
                    f"provided user id ({user.id})"
                )
                details['user_match'] = False
            else:
                details['user_match'] = True

        details['file_valid'] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_tenant_context(self, tenant: Any) -> ValidationResult:
        """
        Validate tenant context consistency.

        Args:
            tenant: Tenant instance to validate

        Returns:
            ValidationResult indicating if tenant context is valid
        """
        errors = []
        warnings = []
        details = {
            'tenant_validation': 'tenant_context',
        }

        # Validate tenant instance
        if tenant is None:
            errors.append("Tenant instance is required for tenant context validation")
            details['tenant_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Check if tenant has required attributes
        if not hasattr(tenant, 'id'):
            errors.append("Tenant instance must have an 'id' attribute")
            details['tenant_valid'] = False
        else:
            details['tenant_id'] = str(tenant.id)
            details['tenant_valid'] = True

        # Cross-validate with instance tenant_id if available
        if self.tenant_id:
            if str(tenant.id) != self.tenant_id:
                warnings.append(
                    f"Provided tenant id ({tenant.id}) does not match "
                    f"instance tenant_id ({self.tenant_id})"
                )
                details['tenant_id_consistency'] = False
            else:
                details['tenant_id_consistency'] = True

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_user_permissions(
        self,
        file: Optional[File],
        tenant: Optional[Any],
        user: User
    ) -> ValidationResult:
        """
        Validate user permissions for file access.

        This method orchestrates comprehensive access validation:
        - Tenant isolation validation
        - ABAC policy evaluation
        - Access request validation

        Args:
            file: Optional file instance
            tenant: Optional tenant instance
            user: User instance to validate permissions for

        Returns:
            ValidationResult indicating if user has required permissions
        """
        errors = []
        warnings = []
        details = {
            'permissions_validation': 'user_permissions',
        }

        # Validate user instance
        if user is None:
            errors.append("User instance is required for permissions validation")
            details['permissions_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['user_id'] = str(user.id)

        # If no file provided, only validate basic user/tenant consistency
        if not file:
            warnings.append("File not provided - only basic user/tenant validation performed")
            if tenant and self.tenant_id:
                if str(tenant.id) != self.tenant_id:
                    warnings.append(
                        f"Provided tenant id ({tenant.id}) does not match "
                        f"instance tenant_id ({self.tenant_id})"
                    )
            details['permissions_valid'] = True
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Use comprehensive file access validation
        # Default to READ access if not specified
        return self._validate_file_access(file, user, access_type="READ")

    def _validate_file_access(
        self,
        file: File,
        user: User,
        access_type: str = "READ"
    ) -> ValidationResult:
        """
        Validate user access to a file with comprehensive governance checks.

        Integrates with GovernanceService and ABACEngine for comprehensive access control:
        - Checks tenant isolation (same tenant = allowed by default)
        - Checks ABAC policies via ABACEngine
        - Checks approved AccessRequests

        Args:
            file: File instance to validate
            user: User instance for permission validation
            access_type: Access type to validate ("READ" or "WRITE")

        Returns:
            ValidationResult with access validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'user_provided': user is not None,
            'access_type': access_type,
            'read_access_allowed': False,
            'write_access_allowed': False,
            'tenant_isolation_valid': False,
            'abac_policy_checked': False,
            'access_request_checked': False,
        }

        if not user:
            warnings.append("User not provided - permission validation skipped")
            details['read_access_allowed'] = True  # Not an error, just skipped
            details['write_access_allowed'] = False  # Write requires explicit user
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Validate user has tenant
        if not hasattr(user, 'tenant') or not user.tenant:
            errors.append("User must have a tenant for permission validation")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # 1. Validate tenant isolation
        tenant_isolation_result = self._validate_tenant_isolation(file, user)
        if not tenant_isolation_result.is_valid:
            errors.extend(tenant_isolation_result.errors)
            warnings.extend(tenant_isolation_result.warnings)
        details['tenant_isolation_valid'] = tenant_isolation_result.is_valid
        details['tenant_isolation'] = tenant_isolation_result.details

        # If tenant isolation fails, deny access
        if not tenant_isolation_result.is_valid:
            details['read_access_allowed'] = False
            details['write_access_allowed'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # 2. Check ABAC policies via ABACEngine
        abac_result = self._validate_abac_access(file, user, access_type)
        details['abac_policy_checked'] = True
        details['abac_result'] = {
            'allowed': abac_result.allowed if hasattr(abac_result, 'allowed') else False,
            'policy_id': str(abac_result.policy.id) if hasattr(abac_result, 'policy') and abac_result.policy else None,
            'masking_required': abac_result.masking_required if hasattr(abac_result, 'masking_required') else False,
        }

        # Check if same tenant (default allow for same tenant if no explicit policy)
        is_same_tenant = tenant_isolation_result.details.get('same_tenant', False)

        # Always check access requests first (they take precedence)
        access_request_result = self._validate_access_request(file, user, access_type)
        details['access_request_checked'] = True
        details['access_request'] = access_request_result.details

        if access_request_result.is_valid:
            # Access request approved - grant access
            if access_type == "READ":
                details['read_access_allowed'] = True
            else:
                details['write_access_allowed'] = True
            warnings.append(
                f"Access granted via approved access request"
            )
        elif abac_result.allowed:
            # ABAC policy allows access
            if access_type == "READ":
                details['read_access_allowed'] = True
            else:
                details['write_access_allowed'] = True

            if abac_result.masking_required:
                warnings.append(
                    f"Access allowed but data masking is required for file '{file.id}'"
                )
        elif is_same_tenant:
            # Same tenant: default allow if no explicit DENY policy
            # (ABAC defaults to deny if no policy matches, but same tenant should allow)
            if access_type == "READ":
                details['read_access_allowed'] = True
            else:
                details['write_access_allowed'] = True
            warnings.append(
                f"Same-tenant access allowed by default (no explicit ABAC policy found)"
            )
        else:
            # Cross-tenant and no ABAC policy and no access request: deny access
            errors.append(
                f"User '{user.id}' does not have {access_type} access to file '{file.id}'. "
                f"No ABAC policy allows access and no approved access request found."
            )
            if access_type == "READ":
                details['read_access_allowed'] = False
            else:
                details['write_access_allowed'] = False

        # Set overall access_allowed based on requested access_type
        if access_type == "READ":
            details['access_allowed'] = details['read_access_allowed']
        else:
            details['access_allowed'] = details['write_access_allowed']

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_tenant_isolation(
        self,
        file: File,
        user: User
    ) -> ValidationResult:
        """
        Validate tenant isolation for file access.

        Same-tenant access is allowed by default. Cross-tenant access requires
        explicit entitlements (AccessRequests or ABAC policies).

        Args:
            file: File instance to validate
            user: User instance for tenant comparison

        Returns:
            ValidationResult with tenant isolation validation status
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Safely get tenant IDs - handle case where tenant might be None
        try:
            file_tenant_id = str(file.tenant.id) if file.tenant else None
        except AttributeError:
            # Handle case where file.tenant doesn't exist (RelatedObjectDoesNotExist)
            file_tenant_id = None

        try:
            user_tenant_id = str(user.tenant.id) if user.tenant else None
        except AttributeError:
            user_tenant_id = None

        details: Dict[str, Any] = {
            'user_tenant_id': user_tenant_id,
            'file_tenant_id': file_tenant_id,
            'same_tenant': False,
            'cross_tenant': False,
        }

        # Check if file has tenant - handle both None and RelatedObjectDoesNotExist
        try:
            file_has_tenant = file.tenant is not None
        except AttributeError:
            file_has_tenant = False

        if not file_has_tenant:
            errors.append("File must have a tenant for isolation validation")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Check if user has tenant - handle both None and RelatedObjectDoesNotExist
        try:
            user_has_tenant = user.tenant is not None
        except AttributeError:
            user_has_tenant = False

        if not user_has_tenant:
            errors.append("User must have a tenant for isolation validation")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Check if same tenant - use the tenant IDs we already extracted
        if file_tenant_id and user_tenant_id and file_tenant_id == user_tenant_id:
            details['same_tenant'] = True
            details['cross_tenant'] = False
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Cross-tenant access - requires explicit entitlements
        details['same_tenant'] = False
        details['cross_tenant'] = True
        warnings.append(
            f"Cross-tenant access detected: user tenant ({user_tenant_id}) != file tenant ({file_tenant_id}). "
            f"Access requires explicit entitlements (AccessRequest or ABAC policy)."
        )

        # Cross-tenant is not an error by itself - it's validated by ABAC/access requests
        return ValidationResult(
            is_valid=True,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_abac_access(
        self,
        file: File,
        user: User,
        access_type: str
    ) -> Any:
        """
        Validate access using ABAC engine.

        Args:
            file: File instance
            user: User instance
            access_type: Access type ("READ" or "WRITE")

        Returns:
            PolicyEvaluationResult from ABACEngine
        """
        from hub.apps.governance.abac import ABACEngine

        try:
            result = ABACEngine.evaluate_access(
                user_id=str(user.id),
                tenant_id=str(file.tenant.id),
                resource_type="FILE",
                resource_id=str(file.id),
                access_type=access_type
            )
            return result
        except Exception as e:
            logger.warning(
                f"ABAC access evaluation failed for file {file.id}, user {user.id}: {e}",
                exc_info=True
            )
            # On error, deny access (fail-secure)
            from hub.apps.governance.abac import PolicyEvaluationResult
            return PolicyEvaluationResult(allowed=False)

    def _validate_access_request(
        self,
        file: File,
        user: User,
        access_type: str
    ) -> ValidationResult:
        """
        Validate if user has an approved access request for the file.

        Args:
            file: File instance
            user: User instance
            access_type: Access type ("READ" or "WRITE")

        Returns:
            ValidationResult with access request validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'has_approved_request': False,
            'access_request_id': None,
            'access_request_status': None,
        }

        from hub.apps.governance.models import AccessRequest, AccessRequestStatus
        from django.utils import timezone

        # Check for approved access requests
        access_requests = AccessRequest.objects.filter(
            file=file,
            requested_by=user,
            requested_access_type=access_type,
            status=AccessRequestStatus.APPROVED
        ).order_by('-approved_at')

        # Check if any approved request is still valid (not expired)
        valid_request = None
        for request in access_requests:
            # Check expiration if expires_at is set
            if request.expires_at:
                if request.expires_at < timezone.now():
                    continue  # Expired, skip
            valid_request = request
            break

        if valid_request:
            details['has_approved_request'] = True
            details['access_request_id'] = str(valid_request.id)
            details['access_request_status'] = valid_request.status
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # No valid approved request found
        details['has_approved_request'] = False
        return ValidationResult(
            is_valid=False,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_file_read_access(
        self,
        file: File,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate user has READ access to file.

        Args:
            file: File instance
            user: User instance

        Returns:
            ValidationResult with read access validation status
        """
        if not user:
            return ValidationResult(
                is_valid=False,
                errors=["User is required for read access validation"],
                warnings=[],
                details={'read_access_allowed': False}
            )
        return self._validate_file_access(file, user, access_type="READ")

    def validate_file_write_access(
        self,
        file: File,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate user has WRITE access to file.

        Args:
            file: File instance
            user: User instance

        Returns:
            ValidationResult with write access validation status
        """
        if not user:
            return ValidationResult(
                is_valid=False,
                errors=["User is required for write access validation"],
                warnings=[],
                details={'write_access_allowed': False}
            )
        return self._validate_file_access(file, user, access_type="WRITE")

    def validate_file_for_create(
        self,
        tenant: Any,
        name: str,
        size: int,
        content_type: str,
        upload_method: str = "browser",
        user: Optional[User] = None,
    ) -> ValidationResult:
        """
        Validate file creation (init upload): tenant, size, type, name, storage quota.

        Args:
            tenant: Tenant instance
            name: File name
            size: File size in bytes
            content_type: MIME type
            upload_method: "browser" or "sdk"
            user: Optional user for context

        Returns:
            ValidationResult; invalid if size/type/name/quota fail.
        """
        result = ValidationResult(is_valid=True)
        # Upload validation (size, type, name)
        upload_result = self.validate_upload(
            filename=name,
            file_size=size,
            content_type=content_type,
            upload_method=upload_method,
            tenant=tenant,
            user=user,
            validation_type="all",
        )
        result = result.combine(upload_result)
        if not result.is_valid:
            return result
        # Storage quota (tenant + file_size)
        quota_result = self.validate_storage_quota(
            file=None,
            tenant=tenant,
            file_size=size,
        )
        result = result.combine(quota_result)
        return result

    def validate_file_for_update(
        self,
        file: File,
        tenant: Any,
        user: Optional[User] = None,
        new_status: Optional[str] = None,
    ) -> ValidationResult:
        """
        Validate file update (e.g. complete upload): file must be PENDING or UPLOADING
        for status transition to ACTIVE; user must have write access.

        Args:
            file: File instance to update
            tenant: Tenant instance (must match file.tenant)
            user: User performing the update
            new_status: Target status (e.g. ACTIVE for complete_upload)

        Returns:
            ValidationResult; invalid if state or permissions fail.
        """
        errors: List[str] = []
        details: Dict[str, Any] = {'update_validation': 'file_update'}

        if file.tenant_id != tenant.id:
            errors.append(
                f"File tenant_id ({file.tenant_id}) does not match provided tenant ({tenant.id})"
            )
            details['tenant_match'] = False
        else:
            details['tenant_match'] = True

        if new_status == FileStatus.ACTIVE:
            if file.status not in (FileStatus.PENDING, FileStatus.UPLOADING):
                errors.append(
                    f"File is not in a state that allows completion (current: {file.status}). "
                    "Only PENDING or UPLOADING can be completed."
                )
                details['state_allowed'] = False
            else:
                details['state_allowed'] = True

        if errors:
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=[],
                details=details,
            )

        if user:
            write_result = self.validate_file_write_access(file=file, user=user)
            result = ValidationResult(is_valid=True, details=details).combine(write_result)
            return result

        return ValidationResult(is_valid=True, errors=[], warnings=[], details=details)

    def validate_file_for_destroy(
        self,
        file: File,
        tenant: Any,
        user: Optional[User] = None,
    ) -> ValidationResult:
        """
        Validate file deletion: tenant match and user has write access.

        Args:
            file: File instance to delete
            tenant: Tenant instance (must match file.tenant)
            user: User performing the delete

        Returns:
            ValidationResult; invalid if tenant mismatch or no write access.
        """
        errors: List[str] = []
        details: Dict[str, Any] = {'destroy_validation': 'file_destroy'}

        if file.tenant_id != tenant.id:
            errors.append(
                f"File tenant_id ({file.tenant_id}) does not match provided tenant ({tenant.id})"
            )
            details['tenant_match'] = False
        else:
            details['tenant_match'] = True

        if errors:
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=[],
                details=details,
            )

        if user:
            write_result = self.validate_file_write_access(file=file, user=user)
            result = ValidationResult(is_valid=True, details=details).combine(write_result)
            return result

        return ValidationResult(is_valid=True, errors=[], warnings=[], details=details)

    def validate_upload(
        self,
        filename: str,
        file_size: int,
        content_type: Optional[str] = None,
        upload_method: str = "browser",
        tenant: Optional[Any] = None,
        user: Optional[User] = None,
        file_content: Optional[bytes] = None,
        validation_type: str = "all"
    ) -> ValidationResult:
        """
        Validate file upload with comprehensive checks.

        This method orchestrates all file upload validation checks:
        - File size validation (max file size limits, tenant quota)
        - File type validation (allowed file types/extensions)
        - File name validation (valid characters, length limits)
        - File content validation (malware scanning, content type verification)

        Args:
            filename: Original filename
            file_size: File size in bytes
            content_type: Optional MIME type
            upload_method: Upload method ("browser" or "sdk")
            tenant: Optional tenant instance for quota checks
            user: Optional user instance
            file_content: Optional file content bytes for content validation
            validation_type: Validation type filter ('size', 'type', 'name', 'content', 'all')

        Returns:
            ValidationResult with upload validation status
        """
        errors = []
        warnings = []
        details = {
            'upload_validation': 'file_upload',
            'filename': filename,
            'file_size': file_size,
            'content_type': content_type,
            'upload_method': upload_method,
        }

        # Track what was validated
        validated_items = []
        result = ValidationResult(is_valid=True)

        # File size validation
        if validation_type in ('size', 'all'):
            size_result = self._validate_file_size(
                file_size=file_size,
                upload_method=upload_method,
                tenant=tenant
            )
            result = result.combine(size_result)
            errors.extend(size_result.errors)
            warnings.extend(size_result.warnings)
            details.update(size_result.details)
            validated_items.append('size')

        # File type validation
        if validation_type in ('type', 'all'):
            type_result = self._validate_file_type(
                filename=filename,
                content_type=content_type
            )
            result = result.combine(type_result)
            errors.extend(type_result.errors)
            warnings.extend(type_result.warnings)
            details.update(type_result.details)
            validated_items.append('type')

        # File name validation
        if validation_type in ('name', 'all'):
            name_result = self._validate_file_name(filename=filename)
            result = result.combine(name_result)
            errors.extend(name_result.errors)
            warnings.extend(name_result.warnings)
            details.update(name_result.details)
            validated_items.append('name')

        # File content validation
        if validation_type in ('content', 'all') and file_content is not None:
            content_result = self._validate_file_content(
                file_content=file_content,
                filename=filename,
                content_type=content_type,
                tenant=tenant
            )
            result = result.combine(content_result)
            errors.extend(content_result.errors)
            warnings.extend(content_result.warnings)
            details.update(content_result.details)
            validated_items.append('content')
        elif validation_type in ('content', 'all') and file_content is None:
            warnings.append("File content not provided, skipping content validation")
            details['content_validation_skipped'] = True
            details['content_valid'] = None

        # Update result details
        details['validated_items'] = validated_items
        details['upload_valid'] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_file_size(
        self,
        file_size: int,
        upload_method: str = "browser",
        tenant: Optional[Any] = None
    ) -> ValidationResult:
        """
        Validate file size against limits and tenant quota.

        Validates:
        - File size is non-negative
        - File size doesn't exceed platform limits
        - File size doesn't exceed method-specific limits (browser/SDK)
        - File size doesn't exceed tenant-specific limits
        - Tenant quota not exceeded (if tenant provided)

        Args:
            file_size: File size in bytes
            upload_method: Upload method ("browser" or "sdk")
            tenant: Optional tenant instance for quota checks

        Returns:
            ValidationResult with size validation status
        """
        errors = []
        warnings = []
        details = {
            'size_validation': 'file_size',
            'file_size': file_size,
            'upload_method': upload_method,
        }

        # Validate file size is non-negative
        if file_size < 0:
            errors.append(f"File size must be non-negative, got: {file_size}")
            details['size_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Get tenant-specific limit if tenant provided
        tenant_limit = None
        tenant_id = None
        if tenant:
            tenant_id = str(tenant.id)
            try:
                from hub.apps.tenants.services import get_tenant_file_size_limit
                tenant_limit = get_tenant_file_size_limit(tenant_id)
                details['tenant_limit'] = tenant_limit
                details['limit_source'] = 'tenant_configuration'
            except Exception as e:
                logger.warning(f"Failed to get tenant file size limit: {e}")
                warnings.append(f"Could not retrieve tenant file size limit: {str(e)}")
                details['limit_source'] = 'platform_default'

        # Determine effective limit
        if tenant_limit:
            effective_limit = tenant_limit
            limit_source = "tenant configuration"
            details['limit_source'] = 'tenant_configuration'
        else:
            effective_limit = getattr(settings, 'MAX_FILE_SIZE', 10 * 1024 * 1024 * 1024)  # 10GB default
            limit_source = "platform default"
            details['platform_limit'] = effective_limit
            details['limit_source'] = 'platform_default'

        details['effective_limit'] = effective_limit

        # Get method-specific limits
        if upload_method == "browser":
            method_limit = getattr(settings, 'MAX_BROWSER_UPLOAD_SIZE', 100 * 1024 * 1024)  # 100MB default
            limit_name = "browser upload limit"
        elif upload_method == "sdk":
            method_limit = getattr(settings, 'MAX_SDK_UPLOAD_SIZE', 5 * 1024 * 1024 * 1024)  # 5GB default
            limit_name = "SDK upload limit"
        else:
            method_limit = effective_limit
            limit_name = f"file size limit ({limit_source})"

        details['method_limit'] = method_limit
        details['method_limit_name'] = limit_name

        # Use the more restrictive limit
        max_size = min(method_limit, effective_limit)
        details['max_size'] = max_size

        # Check tenant/platform limit (skip for empty files)
        if file_size > 0 and file_size > effective_limit:
            errors.append(
                f"File size ({file_size} bytes) exceeds {limit_source} limit ({effective_limit} bytes)"
            )
            details['size_valid'] = False
        else:
            details['size_valid'] = True

        # Check method-specific limit (skip for empty files)
        if file_size > 0 and file_size > max_size:
            errors.append(
                f"File size ({file_size} bytes) exceeds {limit_name} ({max_size} bytes)"
            )
            details['size_valid'] = False

        # Check tenant quota if tenant provided
        if tenant:
            try:
                quota_result = self._validate_tenant_quota(file_size, tenant)
                if not quota_result.is_valid:
                    errors.extend(quota_result.errors)
                    details['quota_valid'] = False
                else:
                    details['quota_valid'] = True
                    if quota_result.warnings:
                        warnings.extend(quota_result.warnings)
                    details.update(quota_result.details)
            except Exception as e:
                logger.warning(f"Failed to validate tenant quota: {e}")
                warnings.append(f"Could not validate tenant quota: {str(e)}")
                details['quota_check_error'] = str(e)
                details['quota_valid'] = None

        # Use Django validator as additional check (for consistency)
        if tenant_id:
            try:
                django_validate_file_size(file_size, upload_method, tenant_id)
                details['django_validator_passed'] = True
            except DjangoValidationError as e:
                # Django validator should catch the same issues, but if it doesn't, add warning
                if details.get('size_valid', True):
                    warnings.append(f"Django validator check: {str(e)}")
                details['django_validator_passed'] = False

        details['size_validation_complete'] = True

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_storage_quota(
        self,
        file: Optional[File] = None,
        tenant: Optional[Any] = None,
        file_size: Optional[int] = None
    ) -> ValidationResult:
        """
        Comprehensive storage quota validation.

        Orchestrates all storage quota validation checks:
        - Storage quota validation (total storage limit)
        - File count quota validation (max files per tenant)
        - Quota exceeded handling validation

        Args:
            file: Optional File instance (for file count validation)
            tenant: Tenant instance
            file_size: Optional file size in bytes (if file not provided)

        Returns:
            ValidationResult with storage quota validation status and details
        """
        result = ValidationResult(is_valid=True)
        details = {
            'validation_type': 'storage_quota',
            'tenant_id': str(tenant.id) if tenant else None,
        }

        effective_tenant = tenant or (file.tenant if file and file.tenant else None)
        effective_file_size = file_size or (file.size if file else None)

        if not effective_tenant:
            details['storage_quota_validated'] = False
            details['storage_quota_skipped'] = 'No tenant provided'
            result.details.update(details)
            return result

        # Validate storage quota (total storage limit)
        if effective_file_size is not None:
            storage_quota_result = self._validate_storage_quota(
                file_size=effective_file_size,
                tenant=effective_tenant
            )
            result = result.combine(storage_quota_result)
            details['storage_quota_validated'] = True
        else:
            details['storage_quota_validated'] = False
            details['storage_quota_skipped'] = 'No file size provided'

        # Validate file count quota (max files per tenant)
        file_count_result = self._validate_file_count_quota(
            tenant=effective_tenant,
            file=file
        )
        result = result.combine(file_count_result)
        details['file_count_quota_validated'] = True

        # Validate quota exceeded handling
        quota_exceeded_result = self._validate_quota_exceeded_handling(
            tenant=effective_tenant,
            file_size=effective_file_size
        )
        result = result.combine(quota_exceeded_result)
        details['quota_exceeded_handling_validated'] = True

        result.details.update(details)
        result.details['is_valid'] = result.is_valid
        result.details['has_warnings'] = len(result.warnings) > 0

        return result

    def _validate_storage_quota(
        self,
        file_size: int,
        tenant: Any
    ) -> ValidationResult:
        """
        Validate tenant storage quota (total storage limit).

        Integrates with GovernanceService to check storage quota limits.
        Calculates current storage usage and validates against tenant limits.

        Args:
            file_size: File size in bytes to check against quota
            tenant: Tenant instance

        Returns:
            ValidationResult with storage quota validation status
        """
        errors = []
        warnings = []
        details = {
            'quota_validation': 'storage_quota',
            'file_size_bytes': file_size,
        }

        try:
            # Calculate current tenant storage usage (in bytes)
            from django.db import models
            current_usage_bytes = File.objects.filter(
                tenant_id=tenant.id,
                status__in=[FileStatus.ACTIVE, FileStatus.COMPLETED]
            ).aggregate(total_size=models.Sum('size'))['total_size'] or 0

            details['current_usage_bytes'] = current_usage_bytes
            details['new_file_size_bytes'] = file_size
            projected_usage_bytes = current_usage_bytes + file_size
            details['projected_usage_bytes'] = projected_usage_bytes

            # Convert bytes to GB for GovernanceService (1 GB = 1024^3 bytes)
            BYTES_PER_GB = 1024 ** 3
            current_usage_gb = current_usage_bytes / BYTES_PER_GB
            requested_storage_gb = file_size / BYTES_PER_GB
            projected_usage_gb = projected_usage_bytes / BYTES_PER_GB

            details['current_usage_gb'] = current_usage_gb
            details['requested_storage_gb'] = requested_storage_gb
            details['projected_usage_gb'] = projected_usage_gb

            # Build requested quota dictionary for GovernanceService
            requested_quota = {
                "storage_gb": requested_storage_gb
            }

            # Integrate with GovernanceService for quota validation
            try:
                from hub.apps.governance.services import GovernanceService
                from hub.apps.core.services.base import ValidationError

                governance_service = GovernanceService(
                    tenant_id=str(tenant.id),
                    user_id=self.user_id if self.user_id else None
                )

                # Validate resource quota allocation via GovernanceService
                validated_quota = governance_service.validate_resource_quota_allocation(
                    tenant_id=str(tenant.id),
                    requested_quota=requested_quota
                )

                # Enforce tenant-level resource limits
                governance_service.check_tenant_resource_limits(
                    tenant_id=str(tenant.id),
                    requested_quota=validated_quota
                )

                details['governance_service_validation'] = 'passed'
                details['validated_quota'] = validated_quota
                details['storage_quota_valid'] = True

            except ValidationError as e:
                # GovernanceService validation failed - quota exceeded
                error_message = str(e)
                details['governance_service_validation'] = 'failed'
                details['governance_service_error'] = error_message

                # Determine if it's a storage quota issue
                if "storage" in error_message.lower() or "storage_gb" in error_message.lower():
                    errors.append(
                        f"Tenant storage quota exceeded. "
                        f"Current usage: {current_usage_gb:.2f} GB, "
                        f"Requested: {requested_storage_gb:.2f} GB, "
                        f"Projected: {projected_usage_gb:.2f} GB. "
                        f"Error: {error_message}"
                    )
                    details['storage_quota_exceeded'] = True
                    details['storage_quota_valid'] = False
                else:
                    # Other quota issue, but still mark as storage quota validation passed
                    warnings.append(
                        f"GovernanceService validation failed: {error_message}"
                    )
                    details['storage_quota_valid'] = True  # Not a storage quota issue

            except Exception as e:
                logger.warning(
                    f"Failed to validate storage quota via GovernanceService for tenant {tenant.id}: {e}",
                    exc_info=True
                )
                warnings.append(
                    f"Could not validate storage quota via GovernanceService: {str(e)}. "
                    f"Proceeding with basic quota validation."
                )
                details['governance_service_error'] = str(e)
                details['governance_service_validation'] = 'error'
                details['storage_quota_valid'] = None  # Unknown status

        except Exception as e:
            logger.warning(f"Failed to check tenant storage quota: {e}", exc_info=True)
            errors.append(f"Could not check tenant storage quota: {str(e)}")
            details['quota_check_error'] = str(e)
            details['storage_quota_valid'] = False

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_file_count_quota(
        self,
        tenant: Any,
        file: Optional[File] = None
    ) -> ValidationResult:
        """
        Validate tenant file count quota (max files per tenant).

        Checks if adding a new file would exceed the tenant's file count limit.
        Integrates with GovernanceService for quota checks.

        Args:
            tenant: Tenant instance
            file: Optional File instance (if adding a new file)

        Returns:
            ValidationResult with file count quota validation status
        """
        errors = []
        warnings = []
        details = {
            'quota_validation': 'file_count_quota',
        }

        try:
            # Calculate current file count for tenant
            current_file_count = File.objects.filter(
                tenant_id=tenant.id,
                status__in=[FileStatus.ACTIVE, FileStatus.COMPLETED]
            ).count()

            details['current_file_count'] = current_file_count

            # If adding a new file, increment count
            if file:
                projected_file_count = current_file_count + 1
                details['projected_file_count'] = projected_file_count
            else:
                projected_file_count = current_file_count
                details['projected_file_count'] = projected_file_count

            # Build requested quota dictionary for GovernanceService
            # Note: GovernanceService uses storage_gb, but we can use a custom key for file count
            # For now, we'll check file count limits separately
            requested_quota = {
                "file_count": 1 if file else 0  # Requesting to add 1 file if file provided
            }

            # Get file count limit from tenant config or use default
            # Default limit: 10000 files per tenant
            default_file_count_limit = 10000
            file_count_limit = default_file_count_limit

            try:
                # Try to get from tenant config if available
                if hasattr(tenant, 'config') and tenant.config:
                    if hasattr(tenant.config, 'max_files_per_tenant'):
                        file_count_limit = tenant.config.max_files_per_tenant or default_file_count_limit
                    elif isinstance(tenant.config, dict):
                        file_count_limit = tenant.config.get('max_files_per_tenant', default_file_count_limit)
            except Exception as e:
                logger.debug(f"Could not get file count limit from tenant config: {e}")

            details['file_count_limit'] = file_count_limit
            details['file_count_limit_source'] = 'tenant_config' if file_count_limit != default_file_count_limit else 'default'

            # Check if file count would exceed limit
            if projected_file_count > file_count_limit:
                errors.append(
                    f"Tenant file count quota exceeded. "
                    f"Current files: {current_file_count}, "
                    f"Limit: {file_count_limit}, "
                    f"Projected: {projected_file_count}"
                )
                details['file_count_quota_exceeded'] = True
                details['file_count_quota_valid'] = False
            else:
                details['file_count_quota_exceeded'] = False
                details['file_count_quota_valid'] = True

                # Warn if approaching limit (within 10% of limit)
                if file_count_limit > 0:
                    usage_percentage = (projected_file_count / file_count_limit) * 100
                    details['usage_percentage'] = usage_percentage
                    if usage_percentage >= 90:
                        warnings.append(
                            f"Tenant file count is approaching limit. "
                            f"Current: {projected_file_count}/{file_count_limit} ({usage_percentage:.1f}%)"
                        )
                        details['file_count_warning'] = True
                    else:
                        details['file_count_warning'] = False

        except Exception as e:
            logger.warning(f"Failed to check tenant file count quota: {e}", exc_info=True)
            errors.append(f"Could not check tenant file count quota: {str(e)}")
            details['file_count_check_error'] = str(e)
            details['file_count_quota_valid'] = False

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_quota_exceeded_handling(
        self,
        tenant: Any,
        file_size: Optional[int] = None
    ) -> ValidationResult:
        """
        Validate quota exceeded handling.

        Checks if quota is exceeded and validates the handling strategy:
        - Determines which quota type was exceeded (storage or file count)
        - Validates error messages are clear and actionable
        - Ensures proper error propagation

        Args:
            tenant: Tenant instance
            file_size: Optional file size in bytes

        Returns:
            ValidationResult with quota exceeded handling validation status
        """
        errors = []
        warnings = []
        details = {
            'quota_validation': 'quota_exceeded_handling',
        }

        try:
            # Check storage quota status
            storage_exceeded = False
            if file_size is not None:
                storage_result = self._validate_storage_quota(file_size, tenant)
                if not storage_result.is_valid:
                    storage_exceeded = True
                    details['storage_quota_exceeded'] = True
                    details['storage_quota_errors'] = storage_result.errors
                else:
                    details['storage_quota_exceeded'] = False
            else:
                details['storage_quota_exceeded'] = None
                details['storage_quota_check_skipped'] = 'No file size provided'

            # Check file count quota status
            file_count_result = self._validate_file_count_quota(tenant, file=None)
            if not file_count_result.is_valid:
                details['file_count_quota_exceeded'] = True
                details['file_count_quota_errors'] = file_count_result.errors
            else:
                details['file_count_quota_exceeded'] = False

            # Validate error messages are clear and actionable
            if storage_exceeded:
                storage_errors = details.get('storage_quota_errors', [])
                if storage_errors:
                    # Check if error messages contain actionable information
                    error_text = ' '.join(storage_errors).lower()
                    if 'current usage' not in error_text and 'limit' not in error_text:
                        warnings.append(
                            "Storage quota error message may not be clear enough. "
                            "Consider including current usage and limit information."
                        )
                        details['error_message_quality'] = 'needs_improvement'
                    else:
                        details['error_message_quality'] = 'good'

            # Validate proper error propagation
            if storage_exceeded or details.get('file_count_quota_exceeded', False):
                details['quota_exceeded'] = True
                details['quota_exceeded_handling'] = 'errors_returned'
            else:
                details['quota_exceeded'] = False
                details['quota_exceeded_handling'] = 'no_action_needed'

        except Exception as e:
            logger.warning(f"Failed to validate quota exceeded handling: {e}", exc_info=True)
            warnings.append(f"Could not validate quota exceeded handling: {str(e)}")
            details['quota_exceeded_handling_error'] = str(e)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_tenant_quota(
        self,
        file_size: int,
        tenant: Any
    ) -> ValidationResult:
        """
        Legacy method for backward compatibility.

        This method maintains backward compatibility with the old soft quota check
        behavior while also integrating with GovernanceService for hard limits.

        Args:
            file_size: File size in bytes to check against quota
            tenant: Tenant instance

        Returns:
            ValidationResult with quota validation status
        """
        errors = []
        warnings = []
        details = {
            'quota_validation': 'tenant_storage_quota',
        }

        try:
            # Calculate current tenant storage usage
            from django.db import models
            current_usage = File.objects.filter(
                tenant_id=tenant.id,
                status__in=[FileStatus.ACTIVE, FileStatus.COMPLETED]
            ).aggregate(total_size=models.Sum('size'))['total_size'] or 0

            details['current_usage'] = current_usage
            details['new_file_size'] = file_size
            details['projected_usage'] = current_usage + file_size

            # Get tenant quota limit (if configured)
            # For backward compatibility, use file size limit as proxy for soft quota
            try:
                from hub.apps.tenants.services import get_tenant_file_size_limit
                quota_limit = get_tenant_file_size_limit(str(tenant.id))
                # Use quota limit as a soft limit for total storage
                # Allow some headroom (e.g., 90% of limit) - this maintains backward compatibility
                effective_quota = int(quota_limit * 0.9)
                details['quota_limit'] = quota_limit
                details['effective_quota'] = effective_quota

                if current_usage + file_size > effective_quota:
                    warnings.append(
                        f"Tenant storage usage ({current_usage + file_size} bytes) exceeds "
                        f"recommended quota ({effective_quota} bytes). "
                        f"Current usage: {current_usage} bytes, adding: {file_size} bytes"
                    )
                    details['quota_warning'] = True
                else:
                    details['quota_warning'] = False
            except Exception as e:
                logger.debug(f"Could not determine tenant quota limit: {e}")
                details['quota_limit'] = None
                details['quota_check_skipped'] = True

            # Also check with GovernanceService for hard limits (but don't fail on soft limits)
            try:
                storage_result = self._validate_storage_quota(file_size, tenant)
                # If GovernanceService reports hard limit exceeded, add errors
                if not storage_result.is_valid and storage_result.errors:
                    # Check if it's a storage quota error (hard limit)
                    for error in storage_result.errors:
                        if 'storage quota exceeded' in error.lower() or 'storage_gb' in error.lower():
                            errors.append(error)
                            details['hard_quota_exceeded'] = True
                # Merge warnings from GovernanceService
                warnings.extend(storage_result.warnings)
                details.update(storage_result.details)
            except Exception as e:
                logger.debug(f"Could not check hard quota via GovernanceService: {e}")

        except Exception as e:
            logger.warning(f"Failed to check tenant quota: {e}")
            warnings.append(f"Could not check tenant storage quota: {str(e)}")
            details['quota_check_error'] = str(e)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_file_type(
        self,
        filename: str,
        content_type: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate file type against allowed types.

        Validates:
        - File has an extension
        - File extension is in allowed list
        - Content type matches extension (if provided)

        Args:
            filename: Original filename
            content_type: Optional MIME type

        Returns:
            ValidationResult with type validation status
        """
        errors = []
        warnings = []
        details = {
            'type_validation': 'file_type',
            'filename': filename,
            'content_type': content_type,
        }

        # Extract extension
        if '.' not in filename:
            errors.append("File must have an extension")
            details['type_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        extension = filename.rsplit('.', 1)[1].lower()
        details['extension'] = extension

        # Get allowed file types from settings
        allowed_types = [t.lower() for t in getattr(settings, 'ALLOWED_FILE_TYPES', ['csv', 'json', 'parquet', 'txt', 'xlsx', 'xls'])]
        details['allowed_types'] = allowed_types

        # Validate extension is allowed
        if extension not in allowed_types:
            errors.append(
                f"File type '{extension}' is not allowed. "
                f"Allowed types: {', '.join(allowed_types)}"
            )
            details['type_valid'] = False
        else:
            details['type_valid'] = True

        # Validate content type matches extension (if provided)
        if content_type:
            content_type_map = {
                'csv': ['text/csv', 'application/csv', 'text/comma-separated-values'],
                'json': ['application/json', 'text/json'],
                'jsonl': ['application/jsonl', 'application/x-ndjson', 'text/jsonl'],
                'parquet': ['application/parquet', 'application/x-parquet'],
                'txt': ['text/plain'],
                'xlsx': ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
                'xls': ['application/vnd.ms-excel', 'application/excel'],
            }

            expected_types = content_type_map.get(extension, [])
            details['expected_content_types'] = expected_types
            details['provided_content_type'] = content_type

            if expected_types and content_type.lower() not in [t.lower() for t in expected_types]:
                warnings.append(
                    f"Content type '{content_type}' does not match expected types for '{extension}'. "
                    f"Expected: {', '.join(expected_types)}"
                )
                details['content_type_match'] = False
            else:
                details['content_type_match'] = True

        # Use Django validator as additional check
        try:
            django_validate_file_type(filename, content_type)
            details['django_validator_passed'] = True
        except DjangoValidationError as e:
            # Django validator should catch the same issues
            if details.get('type_valid', True):
                warnings.append(f"Django validator check: {str(e)}")
            details['django_validator_passed'] = False

        details['type_validation_complete'] = True

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_file_name(
        self,
        filename: str
    ) -> ValidationResult:
        """
        Validate file name format and constraints.

        Validates:
        - File name is not empty
        - File name length is within limits
        - File name contains only valid characters
        - File name doesn't contain path traversal attempts

        Args:
            filename: Original filename

        Returns:
            ValidationResult with name validation status
        """
        errors = []
        warnings = []
        details = {
            'name_validation': 'file_name',
            'filename': filename,
        }

        # Validate filename is not empty
        if not filename or not filename.strip():
            errors.append("File name cannot be empty")
            details['name_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Check for leading/trailing spaces BEFORE stripping (for warnings)
        if filename != filename.strip():
            warnings.append("File name has leading or trailing spaces")
            details['name_warning'] = True

        filename_clean = filename.strip()
        details['filename_length'] = len(filename_clean)

        # Validate filename length (max 255 characters per Django model)
        max_length = 255
        if len(filename_clean) > max_length:
            errors.append(
                f"File name length ({len(filename_clean)}) exceeds maximum length ({max_length} characters)"
            )
            details['name_valid'] = False
        else:
            details['name_valid'] = True

        # Validate filename doesn't contain path traversal attempts
        dangerous_patterns = ['..', '/', '\\', '\x00']
        for pattern in dangerous_patterns:
            if pattern in filename_clean:
                errors.append(
                    f"File name contains invalid character sequence: '{pattern}'. "
                    "Path traversal attempts are not allowed"
                )
                details['name_valid'] = False
                break

        # Validate filename contains only safe characters
        # Allow: alphanumeric, spaces, dots, hyphens, underscores, parentheses
        safe_pattern = re.compile(r'^[a-zA-Z0-9._\-\s()]+$')
        if not safe_pattern.match(filename_clean):
            # Check if it's just the extension that's problematic
            if '.' in filename_clean:
                name_part = filename_clean.rsplit('.', 1)[0]
                if safe_pattern.match(name_part):
                    # Extension might have special chars, but name is OK
                    details['name_valid'] = True
                else:
                    warnings.append(
                        f"File name contains special characters that may cause issues: '{filename_clean}'"
                    )
                    details['name_warning'] = True
            else:
                warnings.append(
                    f"File name contains special characters that may cause issues: '{filename_clean}'"
                )
                details['name_warning'] = True

        # Validate filename doesn't start or end with dot
        if filename_clean.startswith('.') or filename_clean.endswith('.'):
            warnings.append("File name should not start or end with a dot")
            details['name_warning'] = True

        details['name_validation_complete'] = True

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_file_content(
        self,
        file_content: bytes,
        filename: str,
        content_type: Optional[str] = None,
        tenant: Optional[Any] = None
    ) -> ValidationResult:
        """
        Validate file content (malware scanning, content type verification).

        Validates:
        - File content is not empty (unless expected)
        - Content type matches file content (basic verification)
        - Malware scanning via compliance service (if available)

        Args:
            file_content: File content as bytes
            filename: Original filename
            content_type: Optional MIME type
            tenant: Optional tenant instance

        Returns:
            ValidationResult with content validation status
        """
        errors = []
        warnings = []
        details = {
            'content_validation': 'file_content',
            'filename': filename,
            'content_type': content_type,
            'content_size': len(file_content) if file_content else 0,
        }

        # Validate file content is provided
        if file_content is None:
            errors.append("File content is required for content validation")
            details['content_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Basic content type verification
        if content_type:
            # Check if content matches declared type (basic checks)
            if content_type.startswith('text/') or content_type in ['application/json', 'application/csv']:
                # Try to decode as text to verify
                try:
                    file_content.decode('utf-8')
                    details['content_decodable'] = True
                except UnicodeDecodeError:
                    warnings.append(
                        f"Content type '{content_type}' suggests text content, "
                        "but file content is not valid UTF-8"
                    )
                    details['content_decodable'] = False

        # Malware scanning via compliance service
        try:
            from hub.apps.compliance.service_client import ComplianceServiceClient

            compliance_client = ComplianceServiceClient()

            # Check compliance service health
            is_healthy, service_name = compliance_client.health_check()
            if not is_healthy:
                warnings.append(
                    f"Compliance service ({service_name}) is unavailable, skipping malware scan"
                )
                details['malware_scan_skipped'] = True
                details['malware_scan_status'] = 'service_unavailable'
            else:
                # Extract file format from filename
                if '.' in filename:
                    file_format = filename.rsplit('.', 1)[1].lower()
                else:
                    file_format = 'csv'  # Default

                # Run compliance scan (which includes basic security checks)
                try:
                    scan_result = compliance_client.scan_file(
                        file_content=file_content,
                        file_format=file_format,
                        scan_mode="internal"
                    )

                    details['malware_scan_status'] = 'completed'
                    details['scan_result'] = {
                        'overall_status': scan_result.get('overall_status'),
                        'risk_level': scan_result.get('risk_level'),
                        'allowed_to_store': scan_result.get('allowed_to_store'),
                    }

                    # Check if scan indicates security issues
                    overall_status = scan_result.get('overall_status', 'UNKNOWN')
                    allowed_to_store = scan_result.get('allowed_to_store', None)

                    # UNKNOWN = fallback when service unavailable; treat as warning, not error
                    if overall_status == 'UNKNOWN':
                        warnings.append(
                            f"Malware scan could not be completed (service unavailable). "
                            f"Risk level: {scan_result.get('risk_level', 'UNKNOWN')}"
                        )
                        details['content_valid'] = True
                    elif overall_status == 'FAIL' or allowed_to_store is False:
                        errors.append(
                            f"File content validation failed. "
                            f"Overall status: {overall_status}, "
                            f"Risk level: {scan_result.get('risk_level', 'UNKNOWN')}"
                        )
                        details['content_valid'] = False
                    else:
                        details['content_valid'] = True

                except Exception as e:
                    logger.warning(f"Compliance scan failed: {e}")
                    warnings.append(f"Could not complete malware scan: {str(e)}")
                    details['malware_scan_status'] = 'failed'
                    details['malware_scan_error'] = str(e)
                    # Don't fail validation if scan fails, just warn
                    details['content_valid'] = True

        except ImportError:
            warnings.append("Compliance service client not available, skipping malware scan")
            details['malware_scan_skipped'] = True
            details['malware_scan_status'] = 'client_unavailable'
        except Exception as e:
            logger.warning(f"Failed to initialize compliance client: {e}")
            warnings.append(f"Could not initialize malware scanning: {str(e)}")
            details['malware_scan_skipped'] = True
            details['malware_scan_status'] = 'initialization_failed'

        details['content_validation_complete'] = True

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

