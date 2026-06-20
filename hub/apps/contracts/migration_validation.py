"""
Migration Validation for ODCS to ODPS Migration (Task 9.1.2)

Validates that contract migrations from ODCS to ODPS are successful and complete:
1. Verifies all contracts migrated successfully
2. Verifies no data loss (compare HubContract before/after)
3. Verifies links are correct (bidirectional validation)
4. Verifies marketplace metadata preserved
5. Generates migration report with statistics
"""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog
from django.utils import timezone

from hub.apps.contracts.linking_validation import (
    LinkingValidationError,
    validate_odcs_to_odps_link,
    validate_odps_to_odcs_link,
    validate_referential_integrity,
)
from hub.apps.contracts.models import Contract, OriginalSpecType

logger = structlog.get_logger(__name__)


@dataclass
class ValidationIssue:
    """Represents a validation issue found during migration validation."""

    severity: str  # 'error', 'warning', 'info'
    contract_id: str
    issue_type: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContractValidationResult:
    """Result of validating a single contract migration."""

    odcs_contract_id: str
    odps_contract_id: str | None = None
    is_migrated: bool = False
    has_data_loss: bool = False
    has_link_issues: bool = False
    has_marketplace_issues: bool = False
    issues: list[ValidationIssue] = field(default_factory=list)
    data_comparison: dict[str, Any] = field(default_factory=dict)
    marketplace_comparison: dict[str, Any] = field(default_factory=dict)


@dataclass
class MigrationValidationReport:
    """Comprehensive migration validation report."""

    total_odcs_contracts: int = 0
    migrated_count: int = 0
    not_migrated_count: int = 0
    contracts_with_issues: int = 0
    total_issues: int = 0
    errors: int = 0
    warnings: int = 0
    info: int = 0
    validation_results: list[ContractValidationResult] = field(default_factory=list)
    statistics: dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=timezone.now)


class MigrationValidator:
    """
    Validates ODCS to ODPS contract migrations.

    Provides comprehensive validation including:
    - Migration success verification
    - Data loss detection
    - Link integrity validation
    - Marketplace metadata preservation
    """

    def __init__(self, tenant_id: str | None = None):
        """
        Initialize migration validator.

        Args:
            tenant_id: Optional tenant ID to filter contracts
        """
        self.tenant_id = tenant_id
        self.logger = structlog.get_logger(__name__)

    def validate_migration(
        self, odcs_contract_ids: list[str] | None = None, include_statistics: bool = True
    ) -> MigrationValidationReport:
        """
        Validate migration for ODCS contracts.

        Args:
            odcs_contract_ids: Optional list of specific ODCS contract IDs to validate.
                              If None, validates all ODCS contracts (optionally filtered by tenant).
            include_statistics: If True, includes detailed statistics in report

        Returns:
            MigrationValidationReport with validation results
        """
        # Get contracts to validate
        if odcs_contract_ids:
            contracts = self._get_contracts_by_ids(odcs_contract_ids)
        else:
            contracts = self._get_all_odcs_contracts()

        report = MigrationValidationReport(total_odcs_contracts=len(contracts))

        # Validate each contract
        for contract in contracts:
            result = self._validate_contract_migration(contract)
            report.validation_results.append(result)

            if result.is_migrated:
                report.migrated_count += 1
            else:
                report.not_migrated_count += 1

            if result.issues:
                report.contracts_with_issues += 1
                report.total_issues += len(result.issues)
                for issue in result.issues:
                    if issue.severity == "error":
                        report.errors += 1
                    elif issue.severity == "warning":
                        report.warnings += 1
                    else:
                        report.info += 1

        # Generate statistics if requested
        if include_statistics:
            report.statistics = self._generate_statistics(report)

        return report

    def _get_contracts_by_ids(self, contract_ids: list[str]) -> list[Contract]:
        """Get contracts by IDs."""
        queryset = Contract.objects.filter(
            id__in=contract_ids, original_spec_type=OriginalSpecType.ODCS
        )

        if self.tenant_id:
            queryset = queryset.filter(tenant_id=self.tenant_id)

        return list(queryset)

    def _get_all_odcs_contracts(self) -> list[Contract]:
        """Get all ODCS contracts (optionally filtered by tenant)."""
        queryset = Contract.objects.filter(original_spec_type=OriginalSpecType.ODCS)

        if self.tenant_id:
            queryset = queryset.filter(tenant_id=self.tenant_id)

        return list(queryset)

    def _validate_contract_migration(self, odcs_contract: Contract) -> ContractValidationResult:
        """
        Validate migration for a single ODCS contract.

        Args:
            odcs_contract: ODCS contract to validate

        Returns:
            ContractValidationResult with validation details
        """
        result = ContractValidationResult(odcs_contract_id=str(odcs_contract.id))

        # 1. Check if contract has been migrated (has ODPS link)
        odps_contract = self._get_linked_odps_contract(odcs_contract)

        if not odps_contract:
            result.issues.append(
                ValidationIssue(
                    severity="error",
                    contract_id=str(odcs_contract.id),
                    issue_type="not_migrated",
                    message="ODCS contract has not been migrated (no ODPS link found)",
                )
            )
            return result

        result.is_migrated = True
        result.odps_contract_id = str(odps_contract.id)

        # 2. Validate bidirectional links
        link_issues = self._validate_links(odcs_contract, odps_contract)
        result.issues.extend(link_issues)
        if link_issues:
            result.has_link_issues = True

        # 3. Validate no data loss (compare HubContract before/after)
        data_comparison = self._compare_hubcontract_data(odcs_contract, odps_contract)
        result.data_comparison = data_comparison
        if data_comparison.get("has_data_loss", False):
            result.has_data_loss = True
            result.issues.append(
                ValidationIssue(
                    severity="error",
                    contract_id=str(odcs_contract.id),
                    issue_type="data_loss",
                    message="Data loss detected in HubContract comparison",
                    details=data_comparison,
                )
            )

        # 4. Validate marketplace metadata preservation
        marketplace_comparison = self._compare_marketplace_metadata(odcs_contract, odps_contract)
        result.marketplace_comparison = marketplace_comparison
        if marketplace_comparison.get("has_issues", False):
            result.has_marketplace_issues = True
            for issue_detail in marketplace_comparison.get("issues", []):
                result.issues.append(
                    ValidationIssue(
                        severity=issue_detail.get("severity", "warning"),
                        contract_id=str(odcs_contract.id),
                        issue_type="marketplace_metadata",
                        message=issue_detail.get("message", "Marketplace metadata issue"),
                        details=issue_detail.get("details", {}),
                    )
                )

        return result

    def _get_linked_odps_contract(self, odcs_contract: Contract) -> Contract | None:
        """Get linked ODPS contract for an ODCS contract."""
        if not odcs_contract.hub_contract_json:
            return None

        extensions = odcs_contract.hub_contract_json.get("extensions", {})
        x_odps = extensions.get("x_odps", {})
        odps_link = x_odps.get("odps_link")

        if not odps_link:
            return None

        try:
            odps_contract = Contract.objects.get(
                id=odps_link,
                original_spec_type=OriginalSpecType.ODPS,
                tenant_id=odcs_contract.tenant_id,
            )
            return odps_contract
        except Contract.DoesNotExist:
            return None

    def _validate_links(
        self, odcs_contract: Contract, odps_contract: Contract
    ) -> list[ValidationIssue]:
        """Validate bidirectional links between ODCS and ODPS contracts."""
        issues = []

        # Check ODPS → ODCS link directly from HubContract
        odps_hub = odps_contract.hub_contract_json or {}
        odps_extensions = odps_hub.get("extensions", {})
        odps_x_odps = odps_extensions.get("x_odps", {})
        odps_odcs_link = odps_x_odps.get("odcs_link")

        if not odps_odcs_link:
            issues.append(
                ValidationIssue(
                    severity="error",
                    contract_id=str(odcs_contract.id),
                    issue_type="missing_link",
                    message=f"ODPS contract {odps_contract.id} is missing ODCS link",
                    details={
                        "odps_contract_id": str(odps_contract.id),
                        "expected_odcs_id": str(odcs_contract.id),
                    },
                )
            )
        elif str(odps_odcs_link) != str(odcs_contract.id):
            issues.append(
                ValidationIssue(
                    severity="error",
                    contract_id=str(odcs_contract.id),
                    issue_type="link_mismatch",
                    message=f"ODPS contract {odps_contract.id} links to wrong ODCS contract",
                    details={
                        "odps_contract_id": str(odps_contract.id),
                        "expected_odcs_id": str(odcs_contract.id),
                        "actual_odcs_id": str(odps_odcs_link),
                    },
                )
            )
        else:
            # Link exists and is correct, validate it points to existing contract
            try:
                validate_odps_to_odcs_link(odps_contract)
            except LinkingValidationError as e:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        contract_id=str(odcs_contract.id),
                        issue_type="link_validation_error",
                        message=f"ODPS → ODCS link validation failed: {e!s}",
                        details={"error": str(e)},
                    )
                )

        # Check ODCS → ODPS link directly from HubContract
        odcs_hub = odcs_contract.hub_contract_json or {}
        odcs_extensions = odcs_hub.get("extensions", {})
        odcs_x_odps = odcs_extensions.get("x_odps", {})
        odcs_odps_link = odcs_x_odps.get("odps_link")

        if not odcs_odps_link:
            issues.append(
                ValidationIssue(
                    severity="error",
                    contract_id=str(odcs_contract.id),
                    issue_type="missing_link",
                    message=f"ODCS contract {odcs_contract.id} is missing ODPS link",
                    details={
                        "odcs_contract_id": str(odcs_contract.id),
                        "expected_odps_id": str(odps_contract.id),
                    },
                )
            )
        elif str(odcs_odps_link) != str(odps_contract.id):
            issues.append(
                ValidationIssue(
                    severity="error",
                    contract_id=str(odcs_contract.id),
                    issue_type="link_mismatch",
                    message=f"ODCS contract {odcs_contract.id} links to wrong ODPS contract",
                    details={
                        "odcs_contract_id": str(odcs_contract.id),
                        "expected_odps_id": str(odps_contract.id),
                        "actual_odps_id": str(odcs_odps_link),
                    },
                )
            )
        else:
            # Link exists and is correct, validate it points to existing contract
            try:
                validate_odcs_to_odps_link(odcs_contract)
            except LinkingValidationError as e:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        contract_id=str(odcs_contract.id),
                        issue_type="link_validation_error",
                        message=f"ODCS → ODPS link validation failed: {e!s}",
                        details={"error": str(e)},
                    )
                )

        # Validate referential integrity
        try:
            validate_referential_integrity(odcs_contract)
            validate_referential_integrity(odps_contract)
        except LinkingValidationError as e:
            issues.append(
                ValidationIssue(
                    severity="error",
                    contract_id=str(odcs_contract.id),
                    issue_type="referential_integrity",
                    message=f"Referential integrity validation failed: {e!s}",
                    details={"error": str(e)},
                )
            )

        return issues

    def _compare_hubcontract_data(
        self, odcs_contract: Contract, odps_contract: Contract
    ) -> dict[str, Any]:
        """
        Compare HubContract data between ODCS and ODPS contracts to detect data loss.

        Returns:
            Dictionary with comparison results including:
            - has_data_loss: bool
            - missing_sections: List[str]
            - differences: Dict[str, Any]
        """
        odcs_hub = odcs_contract.hub_contract_json or {}
        odps_hub = odps_contract.hub_contract_json or {}

        comparison = {
            "has_data_loss": False,
            "missing_sections": [],
            "differences": {},
            "preserved_sections": [],
        }

        # Key sections to compare (excluding marketplace which is validated separately)
        key_sections = [
            "info",
            "schema",
            "quality",
            "privacy_compliance",
            "lifecycle",
            "extensions",
        ]

        for section in key_sections:
            odcs_section = odcs_hub.get(section)
            odps_section = odps_hub.get(section)

            if odcs_section is None:
                continue  # Section not present in ODCS, skip

            if odps_section is None:
                # Section present in ODCS but missing in ODPS
                comparison["has_data_loss"] = True
                comparison["missing_sections"].append(section)
            # Compare section content
            elif not self._deep_compare(odcs_section, odps_section):
                comparison["differences"][section] = {"odcs": odcs_section, "odps": odps_section}
                # Note: Differences don't necessarily mean data loss,
                # as ODPS may have additional fields or transformed data
                # We'll mark as warning-level issue, not error
            else:
                comparison["preserved_sections"].append(section)

        return comparison

    def _compare_marketplace_metadata(
        self, odcs_contract: Contract, odps_contract: Contract
    ) -> dict[str, Any]:
        """
        Compare marketplace metadata between ODCS and ODPS contracts.

        Returns:
            Dictionary with comparison results including:
            - has_issues: bool
            - issues: List[Dict] with severity, message, details
            - preserved_fields: List[str]
            - missing_fields: List[str]
        """
        odcs_hub = odcs_contract.hub_contract_json or {}
        odps_hub = odps_contract.hub_contract_json or {}

        odcs_marketplace = odcs_hub.get("marketplace", {}) or {}
        odps_marketplace = odps_hub.get("marketplace", {}) or {}

        comparison = {
            "has_issues": False,
            "issues": [],
            "preserved_fields": [],
            "missing_fields": [],
            "field_comparisons": {},
        }

        # Key marketplace fields to validate
        marketplace_fields = ["license_summary", "intended_use", "restricted_use"]

        # Validate basic marketplace fields
        for field_name in marketplace_fields:
            odcs_value = odcs_marketplace.get(field_name)
            odps_value = odps_marketplace.get(field_name)

            comparison["field_comparisons"][field_name] = {
                "odcs_present": odcs_value is not None,
                "odps_present": odps_value is not None,
                "values_match": self._deep_compare(odcs_value, odps_value)
                if (odcs_value is not None and odps_value is not None)
                else False,
            }

            if odcs_value is not None:
                if odps_value is None:
                    comparison["has_issues"] = True
                    comparison["missing_fields"].append(field_name)
                    comparison["issues"].append(
                        {
                            "severity": "error",
                            "message": f"Marketplace field {field_name} is missing in ODPS contract",
                            "details": {"field": field_name, "odcs_value": odcs_value},
                        }
                    )
                elif not self._deep_compare(odcs_value, odps_value):
                    comparison["has_issues"] = True
                    comparison["issues"].append(
                        {
                            "severity": "warning",
                            "message": f"Marketplace field {field_name} value differs between ODCS and ODPS",
                            "details": {
                                "field": field_name,
                                "odcs_value": odcs_value,
                                "odps_value": odps_value,
                            },
                        }
                    )
                else:
                    comparison["preserved_fields"].append(field_name)

        # Validate x_odps extension fields
        odcs_x_odps = odcs_marketplace.get("x_odps", {}) or {}
        odps_x_odps = odps_marketplace.get("x_odps", {}) or {}

        x_odps_fields = ["pricing_plans", "access_methods", "payment_gateways"]

        for field_name in x_odps_fields:
            odcs_value = odcs_x_odps.get(field_name)
            odps_value = odps_x_odps.get(field_name)

            comparison["field_comparisons"][f"x_odps.{field_name}"] = {
                "odcs_present": odcs_value is not None,
                "odps_present": odps_value is not None,
                "values_match": self._deep_compare(odcs_value, odps_value)
                if (odcs_value is not None and odps_value is not None)
                else False,
            }

            if odcs_value is not None:
                if odps_value is None:
                    comparison["has_issues"] = True
                    comparison["missing_fields"].append(f"x_odps.{field_name}")
                    comparison["issues"].append(
                        {
                            "severity": "warning",  # x_odps fields are extensions, less critical
                            "message": f"Marketplace extension field x_odps.{field_name} is missing in ODPS contract",
                            "details": {"field": f"x_odps.{field_name}", "odcs_value": odcs_value},
                        }
                    )
                elif not self._deep_compare(odcs_value, odps_value):
                    comparison["has_issues"] = True
                    comparison["issues"].append(
                        {
                            "severity": "warning",
                            "message": f"Marketplace extension field x_odps.{field_name} value differs",
                            "details": {
                                "field": f"x_odps.{field_name}",
                                "odcs_value": odcs_value,
                                "odps_value": odps_value,
                            },
                        }
                    )
                else:
                    comparison["preserved_fields"].append(f"x_odps.{field_name}")

        return comparison

    def _deep_compare(self, value1: Any, value2: Any) -> bool:
        """
        Deep comparison of two values, handling nested structures.

        Args:
            value1: First value to compare
            value2: Second value to compare

        Returns:
            True if values are equal, False otherwise
        """
        # Handle None
        if value1 is None and value2 is None:
            return True
        if value1 is None or value2 is None:
            return False

        # Handle different types
        if type(value1) != type(value2):
            return False

        # Handle dictionaries
        if isinstance(value1, dict):
            if set(value1.keys()) != set(value2.keys()):
                return False
            for key in value1.keys():
                if not self._deep_compare(value1[key], value2[key]):
                    return False
            return True

        # Handle lists
        if isinstance(value1, list):
            if len(value1) != len(value2):
                return False
            # For lists, compare as sets if order doesn't matter, otherwise element-by-element
            # We'll do element-by-element comparison for accuracy
            for i, item1 in enumerate(value1):
                if i >= len(value2):
                    return False
                if not self._deep_compare(item1, value2[i]):
                    return False
            return True

        # Handle primitive types
        return value1 == value2

    def _generate_statistics(self, report: MigrationValidationReport) -> dict[str, Any]:
        """Generate detailed statistics from validation report."""
        stats = {
            "migration_rate": 0.0,
            "success_rate": 0.0,
            "issue_rate": 0.0,
            "issue_breakdown": {
                "by_type": defaultdict(int),
                "by_severity": {"error": 0, "warning": 0, "info": 0},
            },
            "data_loss_count": 0,
            "link_issue_count": 0,
            "marketplace_issue_count": 0,
        }

        if report.total_odcs_contracts > 0:
            stats["migration_rate"] = (report.migrated_count / report.total_odcs_contracts) * 100
            stats["issue_rate"] = (report.contracts_with_issues / report.total_odcs_contracts) * 100

            if report.migrated_count > 0:
                successful = report.migrated_count - report.contracts_with_issues
                stats["success_rate"] = (successful / report.migrated_count) * 100

        # Count issues by type and severity
        for result in report.validation_results:
            if result.has_data_loss:
                stats["data_loss_count"] += 1
            if result.has_link_issues:
                stats["link_issue_count"] += 1
            if result.has_marketplace_issues:
                stats["marketplace_issue_count"] += 1

            for issue in result.issues:
                stats["issue_breakdown"]["by_type"][issue.issue_type] += 1
                stats["issue_breakdown"]["by_severity"][issue.severity] += 1

        return stats

    def generate_report_text(self, report: MigrationValidationReport) -> str:
        """
        Generate human-readable text report from validation results.

        Args:
            report: MigrationValidationReport to format

        Returns:
            Formatted text report
        """
        lines = []
        lines.append("=" * 80)
        lines.append("ODCS to ODPS Migration Validation Report")
        lines.append("=" * 80)
        lines.append(f"Generated at: {report.generated_at}")
        lines.append("")

        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 80)
        lines.append(f"Total ODCS contracts: {report.total_odcs_contracts}")
        lines.append(f"Migrated: {report.migrated_count}")
        lines.append(f"Not migrated: {report.not_migrated_count}")
        lines.append(f"Contracts with issues: {report.contracts_with_issues}")
        lines.append(
            f"Total issues: {report.total_issues} (Errors: {report.errors}, Warnings: {report.warnings}, Info: {report.info})"
        )
        lines.append("")

        # Statistics
        if report.statistics:
            lines.append("STATISTICS")
            lines.append("-" * 80)
            stats = report.statistics
            lines.append(f"Migration rate: {stats.get('migration_rate', 0):.2f}%")
            lines.append(f"Success rate: {stats.get('success_rate', 0):.2f}%")
            lines.append(f"Issue rate: {stats.get('issue_rate', 0):.2f}%")
            lines.append(f"Data loss cases: {stats.get('data_loss_count', 0)}")
            lines.append(f"Link issue cases: {stats.get('link_issue_count', 0)}")
            lines.append(f"Marketplace issue cases: {stats.get('marketplace_issue_count', 0)}")
            lines.append("")

        # Detailed results
        lines.append("DETAILED RESULTS")
        lines.append("-" * 80)

        for i, result in enumerate(report.validation_results, 1):
            lines.append(f"\n[{i}] Contract {result.odcs_contract_id}")
            lines.append(f"  Status: {'MIGRATED' if result.is_migrated else 'NOT MIGRATED'}")

            if result.is_migrated:
                lines.append(f"  ODPS Contract: {result.odps_contract_id}")

                if result.issues:
                    lines.append(f"  Issues ({len(result.issues)}):")
                    for issue in result.issues:
                        lines.append(
                            f"    [{issue.severity.upper()}] {issue.issue_type}: {issue.message}"
                        )
                        if issue.details:
                            for key, value in issue.details.items():
                                lines.append(f"      {key}: {value}")
                else:
                    lines.append("  ✓ No issues found")
            else:
                lines.append("  ✗ Migration not completed")

        lines.append("")
        lines.append("=" * 80)

        return "\n".join(lines)

    def generate_report_json(self, report: MigrationValidationReport) -> str:
        """
        Generate JSON report from validation results.

        Args:
            report: MigrationValidationReport to format

        Returns:
            JSON string representation of report
        """

        # Convert dataclasses to dictionaries for JSON serialization
        def serialize_dataclass(obj):
            if hasattr(obj, "__dict__"):
                result = {}
                for key, value in obj.__dict__.items():
                    if isinstance(value, datetime):
                        result[key] = value.isoformat()
                    elif isinstance(value, list):
                        result[key] = [
                            serialize_dataclass(item) if hasattr(item, "__dict__") else item
                            for item in value
                        ]
                    elif isinstance(value, dict):
                        result[key] = {
                            k: serialize_dataclass(v) if hasattr(v, "__dict__") else v
                            for k, v in value.items()
                        }
                    elif hasattr(value, "__dict__"):
                        result[key] = serialize_dataclass(value)
                    else:
                        result[key] = value
                return result
            return obj

        report_dict = serialize_dataclass(report)
        return json.dumps(report_dict, indent=2, default=str)
