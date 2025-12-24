"""
ODPS Generator

Generates ODPS (Open Data Product Standard) documents from HubContract format.
Supports ODPS 4.1 generation with comprehensive error handling.

This module provides the reverse operation of ODPS normalization:
- HubContract → ODPS 4.1

Key Features:
- Comprehensive error handling with ODPSExportError
- Field-level error context (field name, expected type, actual type)
- Support for ODPS 4.1 (latest version)
- Graceful handling of missing optional fields
- YAML and JSON output formatting (Task 2.1.8)
"""
import structlog
import re
import json
from typing import Dict, Any, Optional

from hub.apps.contracts.odps_errors import ODPSExportError

logger = structlog.get_logger(__name__)

# Try to import yaml, but make it optional
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    yaml = None


def generate_odps_from_hubcontract(
    hub_contract: Dict[str, Any],
    target_version: str = "4.1",
    original_odcs_contract: Optional[Dict[str, Any]] = None,
    original_odcs_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate ODPS document from HubContract format.

    Maps HubContract fields to ODPS 4.1 structure:
    - hub_contract.id → product.details[lang].productID
    - hub_contract.info.name → product.details[lang].name
    - hub_contract.info.description → product.details[lang].description
    - hub_contract.marketplace.x_odps.pricing_plans → product.marketplace.pricingPlans
    - hub_contract.marketplace.x_odps.access_methods → product.marketplace.accessMethods
    - hub_contract.marketplace.x_odps.payment_gateways → product.marketplace.paymentGateways
    - hub_contract.marketplace.license_summary → license[lang].definition
    - hub_contract.marketplace.restricted_use → license[lang].restrictions
    - hub_contract.marketplace.intended_use → license[lang].rights

    Args:
        hub_contract: HubContract dictionary
        target_version: Target ODPS version (default: "4.1")
        original_odcs_contract: Optional original ODCS contract dictionary to embed inline
            as product.contract.spec (Task 2.1.3)
        original_odcs_url: Optional URL to original ODCS contract to reference
            as product.contract.contractURL (Task 2.1.3)

    Returns:
        ODPS document as dictionary

    Raises:
        ODPSExportError: If generation fails with context including:
            - field_path: Path to the field that caused the error
            - expected: Expected type or value
            - actual: Actual type or value that caused the error

    Note:
        - If both original_odcs_contract and original_odcs_url are provided,
          original_odcs_contract takes precedence (inline embedding)
        - If neither is provided, product.contract section is omitted (optional in ODPS)
    """
    try:
        # Validate input
        if not isinstance(hub_contract, dict):
            raise ODPSExportError(
                message=f"HubContract must be a dictionary, got {type(hub_contract).__name__}",
                error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                context={
                    "field_path": "/",
                    "expected": "dict",
                    "actual": type(hub_contract).__name__,
                },
            )

        # Validate required sections
        if "info" not in hub_contract:
            raise ODPSExportError(
                message="HubContract missing required 'info' section",
                error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                context={
                    "field_path": "/info",
                    "expected": "dict",
                    "actual": None,
                },
            )

        info = hub_contract.get("info")
        if not isinstance(info, dict):
            raise ODPSExportError(
                message=f"HubContract 'info' must be a dictionary, got {type(info).__name__}",
                error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                context={
                    "field_path": "/info",
                    "expected": "dict",
                    "actual": type(info).__name__,
                },
            )

        # Validate required info.name
        if "name" not in info:
            raise ODPSExportError(
                message="HubContract 'info.name' is required",
                error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                context={
                    "field_path": "/info/name",
                    "expected": "str",
                    "actual": None,
                },
            )

        name = info.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ODPSExportError(
                message=f"HubContract 'info.name' must be a non-empty string, got {type(name).__name__}",
                error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                context={
                    "field_path": "/info/name",
                    "expected": "str (non-empty)",
                    "actual": type(name).__name__ if name is not None else None,
                },
            )

        # Get product ID from hub_contract.id
        product_id = hub_contract.get("id", "")
        if not isinstance(product_id, str):
            raise ODPSExportError(
                message=f"HubContract 'id' must be a string, got {type(product_id).__name__}",
                error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                context={
                    "field_path": "/id",
                    "expected": "str",
                    "actual": type(product_id).__name__,
                },
            )

        # Initialize ODPS document structure
        odps_doc = {
            "schema": f"https://opendataproducts.org/schema/v{target_version}",
            "version": target_version,
            "product": {
                "details": {}
            }
        }

        # Map HubContract info to ODPS product.details
        # Use "en" as default language (can be extended to support multiple languages)
        language = "en"

        product_details = {
            "productID": product_id,
            "name": name,
        }

        # Add description if available
        description = info.get("description")
        if description is not None:
            if not isinstance(description, str):
                raise ODPSExportError(
                    message=f"HubContract 'info.description' must be a string, got {type(description).__name__}",
                    error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                    context={
                        "field_path": "/info/description",
                        "expected": "str",
                        "actual": type(description).__name__,
                    },
                )
            product_details["description"] = description

        # Map info.version → product.details.<lang>.productVersion (Task 2.1.2)
        version = info.get("version")
        if version is not None:
            if not isinstance(version, str):
                raise ODPSExportError(
                    message=f"HubContract 'info.version' must be a string, got {type(version).__name__}",
                    error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                    context={
                        "field_path": "/info/version",
                        "expected": "str",
                        "actual": type(version).__name__,
                    },
                )
            product_details["productVersion"] = version

        # Map info.tags[] → product.details.<lang>.tags (Task 2.1.2)
        tags = info.get("tags")
        if tags is not None:
            if not isinstance(tags, list):
                raise ODPSExportError(
                    message=f"HubContract 'info.tags' must be a list, got {type(tags).__name__}",
                    error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                    context={
                        "field_path": "/info/tags",
                        "expected": "list",
                        "actual": type(tags).__name__,
                    },
                )
            # Validate all tags are strings
            valid_tags: list[str] = []
            for i, tag in enumerate(tags):
                if not isinstance(tag, str):
                    raise ODPSExportError(
                        message=f"HubContract 'info.tags[{i}]' must be a string, got {type(tag).__name__}",
                        error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                        context={
                            "field_path": f"/info/tags/{i}",
                            "expected": "str",
                            "actual": type(tag).__name__,
                        },
                    )
                valid_tags.append(tag)
            if valid_tags:
                product_details["tags"] = valid_tags

        odps_doc["product"]["details"][language] = product_details

        # Map info.owners[] → dataHolder.<lang> (Task 2.1.2)
        owners = info.get("owners")
        if owners is not None:
            if not isinstance(owners, list):
                raise ODPSExportError(
                    message=f"HubContract 'info.owners' must be a list, got {type(owners).__name__}",
                    error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                    context={
                        "field_path": "/info/owners",
                        "expected": "list",
                        "actual": type(owners).__name__,
                    },
                )

            # Use first owner for dataHolder (ODPS supports single dataHolder)
            if owners:
                first_owner = owners[0]
                if not isinstance(first_owner, dict):
                    raise ODPSExportError(
                        message=f"HubContract 'info.owners[0]' must be a dictionary, got {type(first_owner).__name__}",
                        error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                        context={
                            "field_path": "/info/owners/0",
                            "expected": "dict",
                            "actual": type(first_owner).__name__,
                        },
                    )

                # Create dataHolder structure
                data_holder = {}
                owner_name = first_owner.get("name")
                owner_email = first_owner.get("email")

                if owner_name is not None:
                    if not isinstance(owner_name, str):
                        raise ODPSExportError(
                            message=f"HubContract 'info.owners[0].name' must be a string, got {type(owner_name).__name__}",
                            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                            context={
                                "field_path": "/info/owners/0/name",
                                "expected": "str",
                                "actual": type(owner_name).__name__,
                            },
                        )
                    data_holder["legalName"] = owner_name

                if owner_email is not None:
                    if not isinstance(owner_email, str):
                        raise ODPSExportError(
                            message=f"HubContract 'info.owners[0].email' must be a string, got {type(owner_email).__name__}",
                            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                            context={
                                "field_path": "/info/owners/0/email",
                                "expected": "str",
                                "actual": type(owner_email).__name__,
                            },
                        )
                    data_holder["email"] = owner_email

                # Only add dataHolder if we have at least one field
                if data_holder:
                    odps_doc["dataHolder"] = {
                        language: data_holder
                    }

        # Map marketplace section if available
        marketplace = hub_contract.get("marketplace")
        if marketplace is not None:
            if not isinstance(marketplace, dict):
                raise ODPSExportError(
                    message=f"HubContract 'marketplace' must be a dictionary, got {type(marketplace).__name__}",
                    error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                    context={
                        "field_path": "/marketplace",
                        "expected": "dict",
                        "actual": type(marketplace).__name__,
                    },
                )

            # Initialize product.marketplace
            if "product" not in odps_doc:
                odps_doc["product"] = {}
            if "marketplace" not in odps_doc["product"]:
                odps_doc["product"]["marketplace"] = {}

            # Map marketplace section (Task 2.1.6)
            # Map marketplace.x_odps.pricing_plans[] → product.marketplace.pricingPlans[]
            # Map marketplace.x_odps.access_methods{} → product.marketplace.accessMethods{}
            # Map marketplace.x_odps.payment_gateways{} → product.marketplace.paymentGateways{}
            x_odps = marketplace.get("x_odps")
            if x_odps is not None and isinstance(x_odps, dict):
                # Map marketplace.x_odps.pricing_plans[] → product.marketplace.pricingPlans[] (Task 2.1.6)
                pricing_plans = x_odps.get("pricing_plans")
                if pricing_plans is not None:
                    if not isinstance(pricing_plans, list):
                        raise ODPSExportError(
                            message=f"HubContract 'marketplace.x_odps.pricing_plans' must be a list, got {type(pricing_plans).__name__}",
                            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                            context={
                                "field_path": "/marketplace/x_odps/pricing_plans",
                                "expected": "list",
                                "actual": type(pricing_plans).__name__,
                            },
                        )
                    odps_doc["product"]["marketplace"]["pricingPlans"] = pricing_plans

                # Map marketplace.x_odps.access_methods{} → product.marketplace.accessMethods{} (Task 2.1.6)
                access_methods = x_odps.get("access_methods")
                if access_methods is not None:
                    if not isinstance(access_methods, dict):
                        raise ODPSExportError(
                            message=f"HubContract 'marketplace.x_odps.access_methods' must be a dictionary, got {type(access_methods).__name__}",
                            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                            context={
                                "field_path": "/marketplace/x_odps/access_methods",
                                "expected": "dict",
                                "actual": type(access_methods).__name__,
                            },
                        )
                    odps_doc["product"]["marketplace"]["accessMethods"] = access_methods

                # Map marketplace.x_odps.payment_gateways{} → product.marketplace.paymentGateways{} (Task 2.1.6, ODPS 4.1+)
                if target_version == "4.1":
                    payment_gateways = x_odps.get("payment_gateways")
                    if payment_gateways is not None:
                        if not isinstance(payment_gateways, dict):
                            raise ODPSExportError(
                                message=f"HubContract 'marketplace.x_odps.payment_gateways' must be a dictionary, got {type(payment_gateways).__name__}",
                                error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                                context={
                                    "field_path": "/marketplace/x_odps/payment_gateways",
                                    "expected": "dict",
                                    "actual": type(payment_gateways).__name__,
                                },
                            )
                        odps_doc["product"]["marketplace"]["paymentGateways"] = payment_gateways

            # Map marketplace.license_summary → license.<lang>.definition (Task 2.1.6)
            # Map marketplace.restricted_use[] → license.<lang>.restrictions (Task 2.1.6)
            # Map marketplace.intended_use[] → license.<lang>.rights[] (Task 2.1.6)
            license_summary = marketplace.get("license_summary")
            restricted_use = marketplace.get("restricted_use")
            intended_use = marketplace.get("intended_use")

            if license_summary is not None or restricted_use is not None or intended_use is not None:
                license_obj = {}

                if license_summary is not None:
                    if not isinstance(license_summary, str):
                        raise ODPSExportError(
                            message=f"HubContract 'marketplace.license_summary' must be a string, got {type(license_summary).__name__}",
                            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                            context={
                                "field_path": "/marketplace/license_summary",
                                "expected": "str",
                                "actual": type(license_summary).__name__,
                            },
                        )
                    license_obj["definition"] = license_summary

                if restricted_use is not None:
                    if not isinstance(restricted_use, list):
                        raise ODPSExportError(
                            message=f"HubContract 'marketplace.restricted_use' must be a list, got {type(restricted_use).__name__}",
                            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                            context={
                                "field_path": "/marketplace/restricted_use",
                                "expected": "list",
                                "actual": type(restricted_use).__name__,
                            },
                        )
                    license_obj["restrictions"] = restricted_use

                if intended_use is not None:
                    if not isinstance(intended_use, list):
                        raise ODPSExportError(
                            message=f"HubContract 'marketplace.intended_use' must be a list, got {type(intended_use).__name__}",
                            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                            context={
                                "field_path": "/marketplace/intended_use",
                                "expected": "list",
                                "actual": type(intended_use).__name__,
                            },
                        )
                    license_obj["rights"] = intended_use

                if license_obj:
                    odps_doc["license"] = {
                        language: license_obj
                    }

        # Map contract section (Task 2.1.3)
        # Generate ODCS from HubContract (if original ODCS available)
        # Embed as product.contract.spec (inline) or reference as product.contract.contractURL
        if original_odcs_contract is not None:
            # Validate original_odcs_contract is a dictionary
            if not isinstance(original_odcs_contract, dict):
                raise ODPSExportError(
                    message=f"original_odcs_contract must be a dictionary, got {type(original_odcs_contract).__name__}",
                    error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                    context={
                        "field_path": "/product/contract/spec",
                        "expected": "dict",
                        "actual": type(original_odcs_contract).__name__,
                    },
                )

            # Embed inline as product.contract.spec
            if "product" not in odps_doc:
                odps_doc["product"] = {}
            odps_doc["product"]["contract"] = {
                "spec": original_odcs_contract
            }

            logger.debug(
                "odps_contract_embedded_inline",
                product_id=product_id,
                message="ODCS contract embedded inline as product.contract.spec"
            )
        elif original_odcs_url is not None:
            # Validate original_odcs_url is a string
            if not isinstance(original_odcs_url, str):
                raise ODPSExportError(
                    message=f"original_odcs_url must be a string, got {type(original_odcs_url).__name__}",
                    error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                    context={
                        "field_path": "/product/contract/contractURL",
                        "expected": "str",
                        "actual": type(original_odcs_url).__name__,
                    },
                )

            # Validate URL format (basic check)
            if not original_odcs_url.strip():
                raise ODPSExportError(
                    message="original_odcs_url must be a non-empty string",
                    error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                    context={
                        "field_path": "/product/contract/contractURL",
                        "expected": "str (non-empty)",
                        "actual": "empty string",
                    },
                )

            # Reference as product.contract.contractURL
            if "product" not in odps_doc:
                odps_doc["product"] = {}
            odps_doc["product"]["contract"] = {
                "contractURL": original_odcs_url
            }

            logger.debug(
                "odps_contract_referenced_url",
                product_id=product_id,
                contract_url=original_odcs_url,
                message="ODCS contract referenced as product.contract.contractURL"
            )
        # If neither is provided, product.contract section is omitted (optional in ODPS)

        # Map quality section (Task 2.1.4)
        quality = hub_contract.get("quality")
        if quality is not None:
            if not isinstance(quality, dict):
                raise ODPSExportError(
                    message=f"HubContract 'quality' must be a dictionary, got {type(quality).__name__}",
                    error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                    context={
                        "field_path": "/quality",
                        "expected": "dict",
                        "actual": type(quality).__name__,
                    },
                )

            # Initialize product.dataQuality
            if "product" not in odps_doc:
                odps_doc["product"] = {}
            odps_doc["product"]["dataQuality"] = {}

            # Map quality.default_profile_key → product.dataQuality.declarative.default
            default_profile_key = quality.get("default_profile_key")
            if default_profile_key is not None:
                if not isinstance(default_profile_key, str):
                    raise ODPSExportError(
                        message=f"HubContract 'quality.default_profile_key' must be a string, got {type(default_profile_key).__name__}",
                        error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                        context={
                            "field_path": "/quality/default_profile_key",
                            "expected": "str",
                            "actual": type(default_profile_key).__name__,
                        },
                    )
                if "declarative" not in odps_doc["product"]["dataQuality"]:
                    odps_doc["product"]["dataQuality"]["declarative"] = {}
                odps_doc["product"]["dataQuality"]["declarative"]["default"] = default_profile_key

            # Map quality.rules[] → product.dataQuality.declarative.dimensions (Task 2.1.4)
            rules = quality.get("rules")
            if rules is not None:
                if not isinstance(rules, list):
                    raise ODPSExportError(
                        message=f"HubContract 'quality.rules' must be a list, got {type(rules).__name__}",
                        error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                        context={
                            "field_path": "/quality/rules",
                            "expected": "list",
                            "actual": type(rules).__name__,
                        },
                    )

                # Group rules by dimension and generate dimensions
                dimensions = {}
                for i, rule in enumerate(rules):
                    if not isinstance(rule, dict):
                        raise ODPSExportError(
                            message=f"HubContract 'quality.rules[{i}]' must be a dictionary, got {type(rule).__name__}",
                            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                            context={
                                "field_path": f"/quality/rules/{i}",
                                "expected": "dict",
                                "actual": type(rule).__name__,
                            },
                        )

                    # Skip rules without dimension field
                    dimension_name = rule.get("dimension")
                    if not dimension_name:
                        continue

                    # If dimension already exists, use first rule (ODPS supports one dimension per name)
                    if dimension_name not in dimensions:
                        dimension_data = _generate_dimension_from_rule(rule)
                        if dimension_data:
                            dimensions[dimension_name] = dimension_data

                if dimensions:
                    if "declarative" not in odps_doc["product"]["dataQuality"]:
                        odps_doc["product"]["dataQuality"]["declarative"] = {}
                    odps_doc["product"]["dataQuality"]["declarative"]["dimensions"] = dimensions

            # Map quality.x_odps.executable[] → product.dataQuality.executable[] (Task 2.1.4)
            x_odps = quality.get("x_odps")
            if x_odps is not None and isinstance(x_odps, dict):
                executable = x_odps.get("executable")
                if executable is not None:
                    if not isinstance(executable, list):
                        raise ODPSExportError(
                            message=f"HubContract 'quality.x_odps.executable' must be a list, got {type(executable).__name__}",
                            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                            context={
                                "field_path": "/quality/x_odps/executable",
                                "expected": "list",
                                "actual": type(executable).__name__,
                            },
                        )
                    odps_doc["product"]["dataQuality"]["executable"] = executable

        # Map lifecycle section (Task 2.1.5)
        # Map lifecycle.slas → product.SLA.declarative[]
        # Map lifecycle.x_odps.sla_dimensions[] → product.SLA.declarative[]
        # Map lifecycle.x_odps.status → product.details.<lang>.status
        lifecycle = hub_contract.get("lifecycle")
        if lifecycle is not None:
            if not isinstance(lifecycle, dict):
                raise ODPSExportError(
                    message=f"HubContract 'lifecycle' must be a dictionary, got {type(lifecycle).__name__}",
                    error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                    context={
                        "field_path": "/lifecycle",
                        "expected": "dict",
                        "actual": type(lifecycle).__name__,
                    },
                )

            # Map lifecycle.x_odps.status → product.details.<lang>.status
            x_odps = lifecycle.get("x_odps")
            if x_odps is not None and isinstance(x_odps, dict):
                status = x_odps.get("status")
                if status is not None:
                    if not isinstance(status, str):
                        raise ODPSExportError(
                            message=f"HubContract 'lifecycle.x_odps.status' must be a string, got {type(status).__name__}",
                            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                            context={
                                "field_path": "/lifecycle/x_odps/status",
                                "expected": "str",
                                "actual": type(status).__name__,
                            },
                        )
                    # Add status to product.details.<lang>
                    if "product" not in odps_doc:
                        odps_doc["product"] = {}
                    if "details" not in odps_doc["product"]:
                        odps_doc["product"]["details"] = {}
                    if language not in odps_doc["product"]["details"]:
                        odps_doc["product"]["details"][language] = {}
                    odps_doc["product"]["details"][language]["status"] = status

            # Map lifecycle.slas and lifecycle.x_odps.sla_dimensions[] → product.SLA.declarative[]
            sla_dimensions = {}

            # First, collect from lifecycle.slas (standard SLA dimensions)
            slas = lifecycle.get("slas")
            if slas is not None:
                if not isinstance(slas, dict):
                    raise ODPSExportError(
                        message=f"HubContract 'lifecycle.slas' must be a dictionary, got {type(slas).__name__}",
                        error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                        context={
                            "field_path": "/lifecycle/slas",
                            "expected": "dict",
                            "actual": type(slas).__name__,
                        },
                    )

                # Map standard SLA dimensions
                for sla_key, sla_value in slas.items():
                    if not isinstance(sla_value, (int, float)):
                        raise ODPSExportError(
                            message=f"HubContract 'lifecycle.slas.{sla_key}' must be a number, got {type(sla_value).__name__}",
                            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                            context={
                                "field_path": f"/lifecycle/slas/{sla_key}",
                                "expected": "number",
                                "actual": type(sla_value).__name__,
                            },
                        )

                    # Map standard SLA keys to ODPS dimension names
                    if sla_key == "availability":
                        dimension_name = "availability"
                    elif sla_key == "latency_ms_p95":
                        dimension_name = "latency"
                    else:
                        # Use the key as-is for other dimensions
                        dimension_name = sla_key

                    # Add to dimensions dict
                    sla_dimensions[dimension_name] = {
                        "target": float(sla_value)
                    }

            # Then, collect from lifecycle.x_odps.sla_dimensions[] (all SLA dimensions with full data)
            if x_odps is not None and isinstance(x_odps, dict):
                x_odps_sla_dimensions = x_odps.get("sla_dimensions")
                if x_odps_sla_dimensions is not None:
                    if not isinstance(x_odps_sla_dimensions, list):
                        raise ODPSExportError(
                            message=f"HubContract 'lifecycle.x_odps.sla_dimensions' must be a list, got {type(x_odps_sla_dimensions).__name__}",
                            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                            context={
                                "field_path": "/lifecycle/x_odps/sla_dimensions",
                                "expected": "list",
                                "actual": type(x_odps_sla_dimensions).__name__,
                            },
                        )

                    # Process each dimension entry
                    for i, dimension_entry in enumerate(x_odps_sla_dimensions):
                        if not isinstance(dimension_entry, dict):
                            raise ODPSExportError(
                                message=f"HubContract 'lifecycle.x_odps.sla_dimensions[{i}]' must be a dictionary, got {type(dimension_entry).__name__}",
                                error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                                context={
                                    "field_path": f"/lifecycle/x_odps/sla_dimensions/{i}",
                                    "expected": "dict",
                                    "actual": type(dimension_entry).__name__,
                                },
                            )

                        dimension_name = dimension_entry.get("name")
                        dimension_data = dimension_entry.get("data")

                        if dimension_name is None:
                            raise ODPSExportError(
                                message=f"HubContract 'lifecycle.x_odps.sla_dimensions[{i}].name' is required",
                                error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                                context={
                                    "field_path": f"/lifecycle/x_odps/sla_dimensions/{i}/name",
                                    "expected": "str",
                                    "actual": None,
                                },
                            )

                        if not isinstance(dimension_name, str):
                            raise ODPSExportError(
                                message=f"HubContract 'lifecycle.x_odps.sla_dimensions[{i}].name' must be a string, got {type(dimension_name).__name__}",
                                error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                                context={
                                    "field_path": f"/lifecycle/x_odps/sla_dimensions/{i}/name",
                                    "expected": "str",
                                    "actual": type(dimension_name).__name__,
                                },
                            )

                        if dimension_data is not None:
                            if not isinstance(dimension_data, dict):
                                raise ODPSExportError(
                                    message=f"HubContract 'lifecycle.x_odps.sla_dimensions[{i}].data' must be a dictionary, got {type(dimension_data).__name__}",
                                    error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                                    context={
                                        "field_path": f"/lifecycle/x_odps/sla_dimensions/{i}/data",
                                        "expected": "dict",
                                        "actual": type(dimension_data).__name__,
                                    },
                                )
                            # Use the full dimension data (overwrites if already in sla_dimensions from lifecycle.slas)
                            sla_dimensions[dimension_name] = dimension_data
                        else:
                            # If no data, create minimal structure with target from lifecycle.slas if available
                            if dimension_name not in sla_dimensions:
                                # Try to get from lifecycle.slas
                                if slas is not None and isinstance(slas, dict):
                                    sla_value = slas.get(dimension_name)
                                    if sla_value is not None:
                                        sla_dimensions[dimension_name] = {
                                            "target": float(sla_value)
                                        }
                                    else:
                                        # Map latency_ms_p95 to latency if needed
                                        if dimension_name == "latency" and "latency_ms_p95" in slas:
                                            sla_dimensions[dimension_name] = {
                                                "target": float(slas["latency_ms_p95"])
                                            }

            # Add product.SLA.declarative if we have any dimensions
            if sla_dimensions:
                if "product" not in odps_doc:
                    odps_doc["product"] = {}
                if "SLA" not in odps_doc["product"]:
                    odps_doc["product"]["SLA"] = {}
                odps_doc["product"]["SLA"]["declarative"] = {
                    "dimensions": sla_dimensions
                }

                logger.debug(
                    "odps_lifecycle_sla_mapped",
                    product_id=product_id,
                    dimension_count=len(sla_dimensions),
                    message="SLA dimensions mapped to product.SLA.declarative"
                )

        # Map product strategy section (Task 2.1.7, ODPS 4.1+ only)
        # Map info.x_odps.product_strategy or extensions.x_odps.product_strategy → productStrategy
        # Generate objectives, KPIs, strategic alignment
        if target_version == "4.1":
            product_strategy = None

            # Check extensions.x_odps.product_strategy first (preferred location)
            extensions = hub_contract.get("extensions")
            if extensions is not None and isinstance(extensions, dict):
                x_odps = extensions.get("x_odps")
                if x_odps is not None and isinstance(x_odps, dict):
                    product_strategy = x_odps.get("product_strategy")

            # Fallback to info.x_odps.product_strategy if not found
            if product_strategy is None:
                info = hub_contract.get("info")
                if info is not None and isinstance(info, dict):
                    x_odps = info.get("x_odps")
                    if x_odps is not None and isinstance(x_odps, dict):
                        product_strategy = x_odps.get("product_strategy")

            if product_strategy is not None:
                if not isinstance(product_strategy, dict):
                    raise ODPSExportError(
                        message=f"HubContract 'product_strategy' must be a dictionary, got {type(product_strategy).__name__}",
                        error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                        context={
                            "field_path": "/product_strategy",
                            "expected": "dict",
                            "actual": type(product_strategy).__name__,
                        },
                    )

                # Build productStrategy object
                odps_product_strategy = {}

                # Map objectives[]
                objectives = product_strategy.get("objectives")
                if objectives is not None:
                    if not isinstance(objectives, list):
                        raise ODPSExportError(
                            message=f"HubContract 'product_strategy.objectives' must be a list, got {type(objectives).__name__}",
                            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                            context={
                                "field_path": "/product_strategy/objectives",
                                "expected": "list",
                                "actual": type(objectives).__name__,
                            },
                        )

                    # Validate all objectives are strings or dicts
                    valid_objectives = []
                    for i, objective in enumerate(objectives):
                        if not isinstance(objective, (str, dict)):
                            raise ODPSExportError(
                                message=f"HubContract 'product_strategy.objectives[{i}]' must be a string or dictionary, got {type(objective).__name__}",
                                error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                                context={
                                    "field_path": f"/product_strategy/objectives/{i}",
                                    "expected": "str or dict",
                                    "actual": type(objective).__name__,
                                },
                            )
                        valid_objectives.append(objective)

                    if valid_objectives:
                        odps_product_strategy["objectives"] = valid_objectives

                # Map strategicAlignment[]
                strategic_alignment = product_strategy.get("strategicAlignment")
                if strategic_alignment is not None:
                    if not isinstance(strategic_alignment, list):
                        raise ODPSExportError(
                            message=f"HubContract 'product_strategy.strategicAlignment' must be a list, got {type(strategic_alignment).__name__}",
                            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                            context={
                                "field_path": "/product_strategy/strategicAlignment",
                                "expected": "list",
                                "actual": type(strategic_alignment).__name__,
                            },
                        )

                    # Validate all strategic alignment items are strings or dicts
                    valid_alignment = []
                    for i, alignment in enumerate(strategic_alignment):
                        if not isinstance(alignment, (str, dict)):
                            raise ODPSExportError(
                                message=f"HubContract 'product_strategy.strategicAlignment[{i}]' must be a string or dictionary, got {type(alignment).__name__}",
                                error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                                context={
                                    "field_path": f"/product_strategy/strategicAlignment/{i}",
                                    "expected": "str or dict",
                                    "actual": type(alignment).__name__,
                                },
                            )
                        valid_alignment.append(alignment)

                    if valid_alignment:
                        odps_product_strategy["strategicAlignment"] = valid_alignment

                # Map productKPIs[]
                product_kpis = product_strategy.get("productKPIs")
                if product_kpis is not None:
                    if not isinstance(product_kpis, list):
                        raise ODPSExportError(
                            message=f"HubContract 'product_strategy.productKPIs' must be a list, got {type(product_kpis).__name__}",
                            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                            context={
                                "field_path": "/product_strategy/productKPIs",
                                "expected": "list",
                                "actual": type(product_kpis).__name__,
                            },
                        )

                    # Validate all KPIs are strings or dicts
                    valid_kpis = []
                    for i, kpi in enumerate(product_kpis):
                        if not isinstance(kpi, (str, dict)):
                            raise ODPSExportError(
                                message=f"HubContract 'product_strategy.productKPIs[{i}]' must be a string or dictionary, got {type(kpi).__name__}",
                                error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                                context={
                                    "field_path": f"/product_strategy/productKPIs/{i}",
                                    "expected": "str or dict",
                                    "actual": type(kpi).__name__,
                                },
                            )
                        valid_kpis.append(kpi)

                    if valid_kpis:
                        odps_product_strategy["productKPIs"] = valid_kpis

                # Add productStrategy to ODPS document if we have at least one field
                if odps_product_strategy:
                    odps_doc["productStrategy"] = odps_product_strategy

                    logger.debug(
                        "odps_product_strategy_mapped",
                        product_id=product_id,
                        has_objectives="objectives" in odps_product_strategy,
                        has_strategic_alignment="strategicAlignment" in odps_product_strategy,
                        has_product_kpis="productKPIs" in odps_product_strategy,
                        message="Product strategy mapped to productStrategy"
                    )

        logger.debug(
            "odps_generation_complete",
            product_id=product_id,
            target_version=target_version,
            has_contract=original_odcs_contract is not None or original_odcs_url is not None,
            has_lifecycle=lifecycle is not None,
            has_product_strategy=target_version == "4.1" and product_strategy is not None if 'product_strategy' in locals() else False,
            message="ODPS document generated successfully"
        )

        return odps_doc

    except ODPSExportError:
        # Re-raise ODPSExportError as-is (already has proper context)
        raise
    except Exception as e:
        # Wrap unexpected errors in ODPSExportError
        raise ODPSExportError(
            message=f"Unexpected error during ODPS generation: {str(e)}",
            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
            context={
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            cause=e,
        ) from e


def _generate_dimension_from_rule(
    rule: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Generate an ODPS declarative dimension from a HubContract quality rule.

    This is the reverse operation of _generate_rule_from_dimension in the normalizer.

    Args:
        rule: Quality rule dictionary with dimension, rule_id, name, etc.

    Returns:
        Dimension data dictionary or None if generation fails
    """
    try:
        dimension_data: Dict[str, Any] = {}

        # Extract rule ID (rule_id or id)
        rule_id = rule.get("rule_id") or rule.get("id") or rule.get("dimension")
        if rule_id:
            dimension_data["ruleID"] = str(rule_id)

        # Extract name
        name = rule.get("name")
        if name:
            dimension_data["name"] = str(name)

        # Parse expression to objectives (reverse of _generate_expression_from_objectives)
        expression = rule.get("expression")
        unit = rule.get("unit")
        if expression:
            objectives = _parse_expression_to_objectives(expression, unit)
            if objectives:
                dimension_data["objectives"] = objectives

        # Extract threshold
        threshold = rule.get("threshold")
        if threshold is not None:
            dimension_data["threshold"] = threshold

        # Extract unit
        if unit:
            dimension_data["unit"] = str(unit)

        # Extract severity
        severity = rule.get("severity")
        if severity:
            dimension_data["severity"] = str(severity)

        # Extract target
        target = rule.get("target")
        if target:
            dimension_data["target"] = str(target)

        # Extract description
        description = rule.get("description")
        if description:
            dimension_data["description"] = str(description)

        # Extract additional fields
        for key in ["operator", "valid_values", "sql_query", "engine", "implementation", "method"]:
            if key in rule:
                dimension_data[key] = rule[key]

        return dimension_data

    except Exception as e:
        logger.warning(
            "failed_to_generate_dimension_from_rule",
            rule=rule,
            error=str(e),
            message="Failed to generate dimension from rule"
        )
        return None


def _parse_expression_to_objectives(
    expression: str,
    unit: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Parse a rule expression back to objectives dictionary.

    This is the reverse operation of _generate_expression_from_objectives in the normalizer.

    Args:
        expression: Expression string (e.g., ">= 0.95 percentage", "== 0.98 percentage")
        unit: Optional unit string (may be in expression or separate)

    Returns:
        Objectives dictionary with min, max, target, or None if parsing fails
    """
    try:
        if not isinstance(expression, str):
            return None

        # Remove unit from expression if present
        expr = expression.strip()
        if unit:
            # Remove unit from end of expression
            unit_suffix = f" {unit}"
            if expr.endswith(unit_suffix):
                expr = expr[:-len(unit_suffix)].strip()

        objectives: Dict[str, Any] = {}

        # Parse patterns like ">= 0.95", "<= 0.99", "== 0.98"
        # Match patterns: >= value, <= value, == value, BETWEEN value1 AND value2
        min_match = re.search(r">=\s*([\d.]+)", expr)
        max_match = re.search(r"<=\s*([\d.]+)", expr)
        target_match = re.search(r"==\s*([\d.]+)", expr)
        between_match = re.search(r"BETWEEN\s+([\d.]+)\s+AND\s+([\d.]+)", expr, re.IGNORECASE)

        if min_match:
            try:
                objectives["min"] = float(min_match.group(1))
            except (ValueError, AttributeError):
                pass

        if max_match:
            try:
                objectives["max"] = float(max_match.group(1))
            except (ValueError, AttributeError):
                pass

        if target_match:
            try:
                objectives["target"] = float(target_match.group(1))
            except (ValueError, AttributeError):
                pass

        if between_match:
            try:
                min_val = float(between_match.group(1))
                max_val = float(between_match.group(2))
                objectives["range"] = [min_val, max_val]
            except (ValueError, AttributeError):
                pass

        # If no objectives found, try to extract numeric value from expression
        if not objectives:
            # Try to find any number in the expression
            number_match = re.search(r"([\d.]+)", expr)
            if number_match:
                try:
                    value = float(number_match.group(1))
                    # Default to target if no operator found
                    objectives["target"] = value
                except (ValueError, AttributeError):
                    pass

        return objectives if objectives else None

    except Exception as e:
        logger.warning(
            "failed_to_parse_expression_to_objectives",
            expression=expression,
            unit=unit,
            error=str(e),
            message="Failed to parse expression to objectives"
        )
        return None


def format_odps_as_json(
    odps_doc: Dict[str, Any],
    indent: int = 2,
    ensure_ascii: bool = False
) -> str:
    """
    Format ODPS document as JSON string (Task 2.1.8).

    Args:
        odps_doc: ODPS document dictionary
        indent: JSON indentation level (default: 2)
        ensure_ascii: If True, escape non-ASCII characters (default: False)

    Returns:
        ODPS document as JSON string

    Raises:
        ODPSExportError: If JSON serialization fails
    """
    try:
        if not isinstance(odps_doc, dict):
            raise ODPSExportError(
                message=f"ODPS document must be a dictionary, got {type(odps_doc).__name__}",
                error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                context={
                    "field_path": "/",
                    "expected": "dict",
                    "actual": type(odps_doc).__name__,
                },
            )

        return json.dumps(odps_doc, indent=indent, ensure_ascii=ensure_ascii)

    except TypeError as e:
        # Handle non-serializable objects
        raise ODPSExportError(
            message=f"Failed to serialize ODPS document to JSON: {str(e)}",
            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
            context={
                "field_path": "/",
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            cause=e,
        ) from e
    except Exception as e:
        # Wrap unexpected errors
        raise ODPSExportError(
            message=f"Unexpected error formatting ODPS document as JSON: {str(e)}",
            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
            context={
                "field_path": "/",
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            cause=e,
        ) from e


def format_odps_as_yaml(
    odps_doc: Dict[str, Any],
    default_flow_style: bool = False,
    allow_unicode: bool = True,
    sort_keys: bool = False
) -> str:
    """
    Format ODPS document as YAML string (Task 2.1.8).

    Args:
        odps_doc: ODPS document dictionary
        default_flow_style: If True, use flow style (default: False, uses block style)
        allow_unicode: If True, allow unicode characters (default: True)
        sort_keys: If True, sort dictionary keys (default: False)

    Returns:
        ODPS document as YAML string

    Raises:
        ODPSExportError: If YAML serialization fails or PyYAML is not available
    """
    if not YAML_AVAILABLE:
        raise ODPSExportError(
            message="PyYAML is not available. Install PyYAML to use YAML output format.",
            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
            context={
                "field_path": "/",
                "expected": "yaml module available",
                "actual": "yaml module not installed",
            },
        )

    try:
        if not isinstance(odps_doc, dict):
            raise ODPSExportError(
                message=f"ODPS document must be a dictionary, got {type(odps_doc).__name__}",
                error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
                context={
                    "field_path": "/",
                    "expected": "dict",
                    "actual": type(odps_doc).__name__,
                },
            )

        return yaml.dump(
            odps_doc,
            default_flow_style=default_flow_style,
            allow_unicode=allow_unicode,
            sort_keys=sort_keys
        )

    except yaml.YAMLError as e:
        # Handle YAML serialization errors
        raise ODPSExportError(
            message=f"Failed to serialize ODPS document to YAML: {str(e)}",
            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
            context={
                "field_path": "/",
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            cause=e,
        ) from e
    except Exception as e:
        # Wrap unexpected errors
        raise ODPSExportError(
            message=f"Unexpected error formatting ODPS document as YAML: {str(e)}",
            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
            context={
                "field_path": "/",
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            cause=e,
        ) from e

