"""
Linking Validation for ODPS-ODCS Contracts

Validates contract linking operations to ensure:
1. Contract existence
2. Contract compatibility
3. No circular references
"""
import structlog
from typing import Dict, Any, Optional, Set, List
from django.db import transaction

from hub.apps.contracts.models import Contract, OriginalSpecType
from hub.apps.contracts.odps_errors import ODPSLinkingError

logger = structlog.get_logger(__name__)


class LinkingValidationError(ODPSLinkingError):
    """Exception raised when linking validation fails."""
    pass


def validate_contract_exists(contract_id: str, tenant_id: Optional[str] = None) -> Contract:
    """
    Validate that a contract exists and optionally belongs to a tenant.

    Args:
        contract_id: Contract UUID
        tenant_id: Optional tenant ID to verify ownership

    Returns:
        Contract instance

    Raises:
        LinkingValidationError: If contract doesn't exist or doesn't belong to tenant
    """
    try:
        contract = Contract.objects.get(id=contract_id)
    except Contract.DoesNotExist:
        raise LinkingValidationError(
            message=f"Contract not found: {contract_id}",
            error_code="CONTRACT_NOT_FOUND",
            context={"contract_id": contract_id}
        )

    if tenant_id and str(contract.tenant_id) != str(tenant_id):
        raise LinkingValidationError(
            message=f"Contract {contract_id} does not belong to tenant {tenant_id}",
            error_code="TENANT_MISMATCH",
            context={
                "contract_id": contract_id,
                "contract_tenant_id": str(contract.tenant_id),
                "expected_tenant_id": tenant_id
            }
        )

    return contract


def validate_contract_compatibility(
    odps_contract: Contract,
    odcs_contract: Contract
) -> None:
    """
    Validate that ODPS and ODCS contracts are compatible for linking.

    Args:
        odps_contract: ODPS contract instance
        odcs_contract: ODCS contract instance

    Raises:
        LinkingValidationError: If contracts are incompatible
    """
    errors = []

    # Validate spec types
    if odps_contract.original_spec_type != OriginalSpecType.ODPS:
        errors.append(
            f"First contract must be ODPS type, got {odps_contract.original_spec_type}"
        )

    if odcs_contract.original_spec_type != OriginalSpecType.ODCS:
        errors.append(
            f"Second contract must be ODCS type, got {odcs_contract.original_spec_type}"
        )

    # Validate same tenant
    if odps_contract.tenant_id != odcs_contract.tenant_id:
        errors.append(
            f"Contracts must belong to the same tenant. "
            f"ODPS tenant: {odps_contract.tenant_id}, ODCS tenant: {odcs_contract.tenant_id}"
        )

    # Validate contracts have hub_contract_json (required for linking)
    if not odps_contract.hub_contract_json:
        errors.append("ODPS contract must have hub_contract_json for linking")

    if not odcs_contract.hub_contract_json:
        errors.append("ODCS contract must have hub_contract_json for linking")

    # Validate normalization status (should be normalized)
    from hub.apps.contracts.models import NormalizationStatus
    if odps_contract.normalization_status not in [
        NormalizationStatus.NORMALIZED_OK,
        NormalizationStatus.NORMALIZED_WITH_WARNINGS
    ]:
        errors.append(
            f"ODPS contract must be normalized. Current status: {odps_contract.normalization_status}"
        )

    if odcs_contract.normalization_status not in [
        NormalizationStatus.NORMALIZED_OK,
        NormalizationStatus.NORMALIZED_WITH_WARNINGS
    ]:
        errors.append(
            f"ODCS contract must be normalized. Current status: {odcs_contract.normalization_status}"
        )

    if errors:
        raise LinkingValidationError(
            message="Contract compatibility validation failed",
            error_code="INCOMPATIBLE_CONTRACTS",
            context={
                "odps_contract_id": str(odps_contract.id),
                "odcs_contract_id": str(odcs_contract.id),
                "errors": errors
            }
        )


def _get_linked_contract_ids(contract: Contract) -> Set[str]:
    """
    Get all contract IDs linked to the given contract (both ODPS and ODCS links).

    Args:
        contract: Contract instance

    Returns:
        Set of linked contract IDs
    """
    linked_ids = set()

    if not contract.hub_contract_json:
        return linked_ids

    extensions = contract.hub_contract_json.get("extensions", {})
    x_odps = extensions.get("x_odps", {})

    # Get ODCS link (if this is an ODPS contract)
    odcs_link = x_odps.get("odcs_link")
    if odcs_link:
        linked_ids.add(str(odcs_link))

    # Get ODPS link (if this is an ODCS contract)
    odps_link = x_odps.get("odps_link")
    if odps_link:
        linked_ids.add(str(odps_link))

    return linked_ids


def _check_circular_reference(
    start_contract_id: str,
    target_contract_id: str,
    visited: Optional[Set[str]] = None,
    max_depth: int = 10
) -> bool:
    """
    Check if linking would create a circular reference using DFS.

    Args:
        start_contract_id: Starting contract ID
        target_contract_id: Target contract ID to link to
        visited: Set of visited contract IDs (for recursion)
        max_depth: Maximum depth to traverse (prevent infinite loops)

    Returns:
        True if circular reference would be created, False otherwise
    """
    if visited is None:
        visited = set()

    if max_depth <= 0:
        # Reached max depth, assume no cycle (safety check)
        return False

    # If we've already visited this contract, we have a cycle
    if start_contract_id in visited:
        return True

    # Add current contract to visited set
    visited.add(start_contract_id)

    try:
        contract = Contract.objects.get(id=start_contract_id)
        linked_ids = _get_linked_contract_ids(contract)

        # Check if target is already linked (would create direct cycle)
        if target_contract_id in linked_ids:
            return True

        # Recursively check all linked contracts
        for linked_id in linked_ids:
            if _check_circular_reference(linked_id, target_contract_id, visited.copy(), max_depth - 1):
                return True

    except Contract.DoesNotExist:
        # Contract doesn't exist, no cycle possible
        return False

    return False


def validate_no_circular_reference(
    odps_contract_id: str,
    odcs_contract_id: str
) -> None:
    """
    Validate that linking would not create a circular reference.

    Args:
        odps_contract_id: ODPS contract ID
        odcs_contract_id: ODCS contract ID

    Raises:
        LinkingValidationError: If linking would create a circular reference
    """
    # Check if linking ODPS -> ODCS would create a cycle
    if _check_circular_reference(odcs_contract_id, odps_contract_id):
        raise LinkingValidationError(
            message="Linking would create a circular reference",
            error_code="CIRCULAR_REFERENCE",
            context={
                "odps_contract_id": odps_contract_id,
                "odcs_contract_id": odcs_contract_id,
                "description": "Linking ODPS -> ODCS would create a cycle"
            }
        )

    # Check if linking ODCS -> ODPS would create a cycle
    if _check_circular_reference(odps_contract_id, odcs_contract_id):
        raise LinkingValidationError(
            message="Linking would create a circular reference",
            error_code="CIRCULAR_REFERENCE",
            context={
                "odps_contract_id": odps_contract_id,
                "odcs_contract_id": odcs_contract_id,
                "description": "Linking ODCS -> ODPS would create a cycle"
            }
        )


def validate_linking(
    odps_contract_id: str,
    odcs_contract_id: str,
    tenant_id: Optional[str] = None
) -> tuple[Contract, Contract]:
    """
    Comprehensive linking validation.

    Validates:
    1. Both contracts exist
    2. Contracts are compatible
    3. No circular references would be created (unless already correctly linked)

    Args:
        odps_contract_id: ODPS contract UUID
        odcs_contract_id: ODCS contract UUID
        tenant_id: Optional tenant ID for ownership validation

    Returns:
        Tuple of (odps_contract, odcs_contract)

    Raises:
        LinkingValidationError: If validation fails
    """
    # Validate contract existence
    odps_contract = validate_contract_exists(odps_contract_id, tenant_id)
    odcs_contract = validate_contract_exists(odcs_contract_id, tenant_id)

    # Validate compatibility
    validate_contract_compatibility(odps_contract, odcs_contract)

    # Check if contracts are already correctly linked (idempotent behavior)
    odps_already_linked = False
    odcs_already_linked = False

    if odps_contract.hub_contract_json:
        extensions = odps_contract.hub_contract_json.get("extensions", {})
        x_odps = extensions.get("x_odps", {})
        existing_odcs_link = x_odps.get("odcs_link")
        if existing_odcs_link and str(existing_odcs_link) == str(odcs_contract_id):
            odps_already_linked = True

    if odcs_contract.hub_contract_json:
        extensions = odcs_contract.hub_contract_json.get("extensions", {})
        x_odps = extensions.get("x_odps", {})
        existing_odps_link = x_odps.get("odps_link")
        if existing_odps_link and str(existing_odps_link) == str(odps_contract_id):
            odcs_already_linked = True

    # If contracts are already correctly linked bidirectionally, skip circular reference check
    if odps_already_linked and odcs_already_linked:
        logger.info(
            "Contracts already correctly linked, validation passes (idempotent)",
            odps_contract_id=odps_contract_id,
            odcs_contract_id=odcs_contract_id
        )
    else:
        # Validate no circular references (only if not already correctly linked)
        validate_no_circular_reference(odps_contract_id, odcs_contract_id)

    logger.info(
        "Linking validation passed",
        odps_contract_id=odps_contract_id,
        odcs_contract_id=odcs_contract_id,
        tenant_id=tenant_id
    )

    return odps_contract, odcs_contract


def validate_odps_to_odcs_link(odps_contract: Contract) -> Optional[Contract]:
    """
    Validate that ODPS → ODCS link exists and the linked contract exists.

    This function validates that if an ODPS contract has an odcs_link,
    the linked ODCS contract actually exists.

    Args:
        odps_contract: ODPS contract instance

    Returns:
        Linked ODCS contract if link exists, None if no link

    Raises:
        LinkingValidationError: If link exists but linked contract doesn't exist
    """
    if not odps_contract.hub_contract_json:
        return None

    extensions = odps_contract.hub_contract_json.get("extensions", {})
    x_odps = extensions.get("x_odps", {})
    odcs_link = x_odps.get("odcs_link")

    if not odcs_link:
        # No link, nothing to validate
        return None

    # Validate that linked ODCS contract exists
    try:
        odcs_contract = Contract.objects.get(id=odcs_link)
    except Contract.DoesNotExist:
        raise LinkingValidationError(
            message=f"ODPS contract {odps_contract.id} has invalid odcs_link: contract {odcs_link} does not exist",
            error_code="INVALID_ODCS_LINK",
            context={
                "odps_contract_id": str(odps_contract.id),
                "odcs_link": str(odcs_link),
                "description": "ODPS → ODCS link points to non-existent contract"
            }
        )

    # Validate that linked contract is actually ODCS
    if odcs_contract.original_spec_type != OriginalSpecType.ODCS:
        raise LinkingValidationError(
            message=f"ODPS contract {odps_contract.id} links to non-ODCS contract {odcs_link} (type: {odcs_contract.original_spec_type})",
            error_code="INVALID_ODCS_LINK_TYPE",
            context={
                "odps_contract_id": str(odps_contract.id),
                "odcs_link": str(odcs_link),
                "linked_contract_type": odcs_contract.original_spec_type,
                "expected_type": OriginalSpecType.ODCS
            }
        )

    # Validate same tenant
    if odps_contract.tenant_id != odcs_contract.tenant_id:
        raise LinkingValidationError(
            message=f"ODPS contract {odps_contract.id} links to ODCS contract {odcs_link} from different tenant",
            error_code="TENANT_MISMATCH",
            context={
                "odps_contract_id": str(odps_contract.id),
                "odcs_link": str(odcs_link),
                "odps_tenant_id": str(odps_contract.tenant_id),
                "odcs_tenant_id": str(odcs_contract.tenant_id)
            }
        )

    logger.debug(
        "ODPS → ODCS link validated",
        odps_contract_id=str(odps_contract.id),
        odcs_contract_id=str(odcs_contract.id)
    )

    return odcs_contract


def validate_odcs_to_odps_link(odcs_contract: Contract) -> Optional[Contract]:
    """
    Validate that ODCS → ODPS link exists and the linked contract exists.

    This function validates that if an ODCS contract has an odps_link,
    the linked ODPS contract actually exists.

    Args:
        odcs_contract: ODCS contract instance

    Returns:
        Linked ODPS contract if link exists, None if no link

    Raises:
        LinkingValidationError: If link exists but linked contract doesn't exist
    """
    if not odcs_contract.hub_contract_json:
        return None

    extensions = odcs_contract.hub_contract_json.get("extensions", {})
    x_odps = extensions.get("x_odps", {})
    odps_link = x_odps.get("odps_link")

    if not odps_link:
        # No link, nothing to validate
        return None

    # Validate that linked ODPS contract exists
    try:
        odps_contract = Contract.objects.get(id=odps_link)
    except Contract.DoesNotExist:
        raise LinkingValidationError(
            message=f"ODCS contract {odcs_contract.id} has invalid odps_link: contract {odps_link} does not exist",
            error_code="INVALID_ODPS_LINK",
            context={
                "odcs_contract_id": str(odcs_contract.id),
                "odps_link": str(odps_link),
                "description": "ODCS → ODPS link points to non-existent contract"
            }
        )

    # Validate that linked contract is actually ODPS
    if odps_contract.original_spec_type != OriginalSpecType.ODPS:
        raise LinkingValidationError(
            message=f"ODCS contract {odcs_contract.id} links to non-ODPS contract {odps_link} (type: {odps_contract.original_spec_type})",
            error_code="INVALID_ODPS_LINK_TYPE",
            context={
                "odcs_contract_id": str(odcs_contract.id),
                "odps_link": str(odps_link),
                "linked_contract_type": odps_contract.original_spec_type,
                "expected_type": OriginalSpecType.ODPS
            }
        )

    # Validate same tenant
    if odcs_contract.tenant_id != odps_contract.tenant_id:
        raise LinkingValidationError(
            message=f"ODCS contract {odcs_contract.id} links to ODPS contract {odps_link} from different tenant",
            error_code="TENANT_MISMATCH",
            context={
                "odcs_contract_id": str(odcs_contract.id),
                "odps_link": str(odps_link),
                "odcs_tenant_id": str(odcs_contract.tenant_id),
                "odps_tenant_id": str(odps_contract.tenant_id)
            }
        )

    logger.debug(
        "ODCS → ODPS link validated",
        odcs_contract_id=str(odcs_contract.id),
        odps_contract_id=str(odps_contract.id)
    )

    return odps_contract


def validate_referential_integrity(contract: Contract) -> None:
    """
    Validate referential integrity for contract links.

    Ensures that if contract A links to contract B, then contract B links back to contract A.
    This maintains bidirectional consistency.

    Args:
        contract: Contract instance to validate

    Raises:
        LinkingValidationError: If referential integrity is violated
    """
    if not contract.hub_contract_json:
        return

    extensions = contract.hub_contract_json.get("extensions", {})
    x_odps = extensions.get("x_odps", {})
    errors = []

    # Check ODPS → ODCS link integrity
    if contract.original_spec_type == OriginalSpecType.ODPS:
        odcs_link = x_odps.get("odcs_link")
        if odcs_link:
            try:
                odcs_contract = Contract.objects.get(id=odcs_link)
                # Validate that ODCS contract links back to this ODPS contract
                if odcs_contract.hub_contract_json:
                    odcs_extensions = odcs_contract.hub_contract_json.get("extensions", {})
                    odcs_x_odps = odcs_extensions.get("x_odps", {})
                    odcs_odps_link = odcs_x_odps.get("odps_link")
                    if odcs_odps_link != str(contract.id):
                        errors.append(
                            f"ODPS contract {contract.id} links to ODCS {odcs_link}, "
                            f"but ODCS does not link back (expected odps_link={contract.id}, got {odcs_odps_link})"
                        )
            except Contract.DoesNotExist:
                # This will be caught by validate_odps_to_odcs_link, skip here
                pass

    # Check ODCS → ODPS link integrity
    if contract.original_spec_type == OriginalSpecType.ODCS:
        odps_link = x_odps.get("odps_link")
        if odps_link:
            try:
                odps_contract = Contract.objects.get(id=odps_link)
                # Validate that ODPS contract links back to this ODCS contract
                if odps_contract.hub_contract_json:
                    odps_extensions = odps_contract.hub_contract_json.get("extensions", {})
                    odps_x_odps = odps_extensions.get("x_odps", {})
                    odps_odcs_link = odps_x_odps.get("odcs_link")
                    if odps_odcs_link != str(contract.id):
                        errors.append(
                            f"ODCS contract {contract.id} links to ODPS {odps_link}, "
                            f"but ODPS does not link back (expected odcs_link={contract.id}, got {odps_odcs_link})"
                        )
            except Contract.DoesNotExist:
                # This will be caught by validate_odcs_to_odps_link, skip here
                pass

    if errors:
        raise LinkingValidationError(
            message="Referential integrity violation detected",
            error_code="REFERENTIAL_INTEGRITY_VIOLATION",
            context={
                "contract_id": str(contract.id),
                "contract_type": contract.original_spec_type,
                "errors": errors
            }
        )

    logger.debug(
        "Referential integrity validated",
        contract_id=str(contract.id),
        contract_type=contract.original_spec_type
    )


def validate_all_links(contract: Contract) -> Dict[str, Any]:
    """
    Comprehensive validation of all links for a contract.

    Validates:
    1. ODPS → ODCS link (if contract is ODPS)
    2. ODCS → ODPS link (if contract is ODCS)
    3. Referential integrity (bidirectional consistency)

    Args:
        contract: Contract instance to validate

    Returns:
        Dictionary with validation results:
        {
            "odps_to_odcs": Contract or None,
            "odcs_to_odps": Contract or None,
            "referential_integrity": bool
        }

    Raises:
        LinkingValidationError: If any validation fails
    """
    result = {
        "odps_to_odcs": None,
        "odcs_to_odps": None,
        "referential_integrity": True
    }

    # Validate ODPS → ODCS link
    if contract.original_spec_type == OriginalSpecType.ODPS:
        result["odps_to_odcs"] = validate_odps_to_odcs_link(contract)

    # Validate ODCS → ODPS link
    if contract.original_spec_type == OriginalSpecType.ODCS:
        result["odcs_to_odps"] = validate_odcs_to_odps_link(contract)

    # Validate referential integrity
    validate_referential_integrity(contract)

    logger.info(
        "All links validated",
        contract_id=str(contract.id),
        contract_type=contract.original_spec_type,
        has_odps_to_odcs=result["odps_to_odcs"] is not None,
        has_odcs_to_odps=result["odcs_to_odps"] is not None
    )

    return result

