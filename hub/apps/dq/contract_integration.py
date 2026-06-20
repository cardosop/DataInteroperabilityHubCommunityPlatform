"""
DQ Service Integration with Contract Quality Rules (GAP-8.2.1).

Reads quality rules from HubContract and integrates them with DQ service execution.
"""

import os

# Import DQ profile types - handle import path with hyphen
import sys
from typing import Any

from hub.apps.contracts.models import Contract

dq_service_path = os.path.join(os.path.dirname(__file__), "../../../services/dq-service")
if dq_service_path not in sys.path:
    sys.path.insert(0, dq_service_path)
try:
    from dq_profile import DQCategory, DQCheck, DQSeverity
except ImportError:
    # Fallback: define minimal types
    from enum import Enum

    class DQCategory(Enum):
        COMPLETENESS = "completeness"
        ACCURACY = "accuracy"
        CONSISTENCY = "consistency"
        TIMELINESS = "timeliness"
        VALIDITY = "validity"
        UNIQUENESS = "uniqueness"

    class DQSeverity(Enum):
        ERROR = "ERROR"
        WARNING = "WARNING"
        INFO = "INFO"

    class DQCheck:
        def __init__(
            self,
            check_id,
            name,
            category,
            severity,
            expectation_type,
            params,
            target_level,
            target_column=None,
            target_pattern=None,
        ):
            self.check_id = check_id
            self.name = name
            self.category = category
            self.severity = severity
            self.expectation_type = expectation_type
            self.params = params
            self.target_level = target_level
            self.target_column = target_column
            self.target_pattern = target_pattern


# Import vocabulary mappings - handle import path with hyphen
semantic_service_path = os.path.join(
    os.path.dirname(__file__), "../../../services/semantic-service"
)
if semantic_service_path not in sys.path:
    sys.path.insert(0, semantic_service_path)
try:
    from vocabulary_mappings import get_dqv_dimension
except ImportError:

    def get_dqv_dimension(dimension):
        return None


class ContractQualityRulesExtractor:
    """
    Extracts quality rules from HubContract and converts them to DQ checks.
    """

    @staticmethod
    def extract_quality_rules(contract: Contract) -> dict[str, Any]:
        """
        Extract quality rules from contract's HubContract JSON.

        Args:
            contract: Contract instance

        Returns:
            Dictionary with:
            - rules: List of quality rules
            - default_profile_key: Default profile key if specified
        """
        hub_contract = contract.hub_contract_json or {}
        quality_section = hub_contract.get("quality", {})

        rules = quality_section.get("rules", [])
        default_profile_key = quality_section.get("default_profile_key")

        return {"rules": rules, "default_profile_key": default_profile_key}

    @staticmethod
    def parse_rule_expression(expression: str, field_name: str | None = None) -> dict[str, Any]:
        """
        Parse rule expression (SQL-like or domain-specific) into executable check.

        Supports expressions like:
        - "field_name IS NOT NULL"
        - "field_name > 0"
        - "field_name IN ('value1', 'value2')"
        - "COUNT(*) > 100"

        Args:
            expression: Rule expression string
            field_name: Optional field name (if rule is field-specific)

        Returns:
            Dictionary with parsed check information
        """
        # Store original for value extraction (to preserve case in IN clauses)
        original_expression = expression.strip()
        expression_upper = original_expression.upper()

        # Parse common patterns (use uppercase version for matching)
        if "IS NOT NULL" in expression_upper:
            return {
                "type": "not_null",
                "field": field_name or expression_upper.split("IS NOT NULL")[0].strip(),
                "expression": original_expression,
            }
        elif "IS NULL" in expression_upper:
            return {
                "type": "is_null",
                "field": field_name or expression_upper.split("IS NULL")[0].strip(),
                "expression": original_expression,
            }
        elif ">" in expression_upper:
            parts = expression_upper.split(">")
            if len(parts) == 2:
                field = parts[0].strip()
                threshold = parts[1].strip()
                try:
                    threshold_value = float(threshold)
                    return {
                        "type": "greater_than",
                        "field": field_name or field,
                        "threshold": threshold_value,
                        "expression": original_expression,
                    }
                except ValueError:
                    pass
        elif "<" in expression_upper:
            parts = expression_upper.split("<")
            if len(parts) == 2:
                field = parts[0].strip()
                threshold = parts[1].strip()
                try:
                    threshold_value = float(threshold)
                    return {
                        "type": "less_than",
                        "field": field_name or field,
                        "threshold": threshold_value,
                        "expression": original_expression,
                    }
                except ValueError:
                    pass
        elif "IN (" in expression_upper:
            # Extract values from IN clause - use original expression to preserve case
            in_start = original_expression.upper().find("IN (")
            if in_start >= 0:
                # Find the opening and closing parentheses in original
                in_part_start = in_start + 4
                in_part_end = original_expression.find(")", in_part_start)
                if in_part_end > in_part_start:
                    in_part = original_expression[in_part_start:in_part_end]
                    # Extract values preserving original case
                    values = [v.strip().strip("'\"") for v in in_part.split(",")]
                    return {
                        "type": "in_values",
                        "field": field_name or original_expression[:in_start].strip(),
                        "values": values,
                        "expression": original_expression,
                    }
        elif "COUNT(*)" in expression_upper or "COUNT" in expression_upper:
            # Aggregate checks
            if ">" in expression_upper:
                parts = expression_upper.split(">")
                if len(parts) == 2:
                    try:
                        threshold = float(parts[1].strip())
                        return {
                            "type": "row_count",
                            "threshold": threshold,
                            "operator": "greater_than",
                            "expression": original_expression,
                        }
                    except ValueError:
                        pass

        # Default: custom expression
        return {"type": "custom", "field": field_name, "expression": original_expression}

    @staticmethod
    def convert_rule_to_dq_check(rule: dict[str, Any]) -> DQCheck | None:
        """
        Convert HubContract quality rule to DQCheck.

        Args:
            rule: Quality rule dictionary with rule_id, dimension, expression, severity

        Returns:
            DQCheck instance or None if conversion fails
        """
        rule_id = rule.get("rule_id", "unknown")
        dimension = rule.get("dimension", "validity")
        expression = rule.get("expression", "")
        severity = rule.get("severity", "ERROR")
        field = rule.get("field")  # Optional field name

        # Parse expression
        parsed = ContractQualityRulesExtractor.parse_rule_expression(expression, field)

        # Map dimension to DQV vocabulary and DQCategory
        get_dqv_dimension(dimension) if get_dqv_dimension else None

        # Map dimension string to DQCategory
        dimension_map = {
            "completeness": DQCategory.COMPLETENESS,
            "accuracy": DQCategory.ACCURACY,
            "consistency": DQCategory.CONSISTENCY,
            "timeliness": DQCategory.TIMELINESS,
            "validity": DQCategory.VALIDITY,
            "uniqueness": DQCategory.UNIQUENESS,
        }
        category = dimension_map.get(dimension.lower(), DQCategory.VALIDITY)

        # Map severity string to DQSeverity
        severity_map = {
            "ERROR": DQSeverity.ERROR,
            "WARNING": DQSeverity.WARNING,
            "INFO": DQSeverity.INFO,
        }
        dq_severity = severity_map.get(severity.upper(), DQSeverity.ERROR)

        # Determine expectation type from parsed expression
        check_type_str = parsed.get("type", "custom")
        field_name = parsed.get("field")

        # Map to Great Expectations expectation type
        expectation_type_map = {
            "not_null": "expect_column_values_to_not_be_null",
            "is_null": "expect_column_values_to_be_null",
            "greater_than": "expect_column_values_to_be_between",
            "less_than": "expect_column_values_to_be_between",
            "in_values": "expect_column_values_to_be_in_set",
            "row_count": "expect_table_row_count_to_be_between",
            "custom": "expect_custom_expression_to_be_true",
        }

        expectation_type = expectation_type_map.get(
            check_type_str, "expect_custom_expression_to_be_true"
        )

        # Build params based on check type
        params = {}
        if check_type_str == "greater_than":
            params["min_value"] = parsed.get("threshold")
        elif check_type_str == "less_than":
            params["max_value"] = parsed.get("threshold")
        elif check_type_str == "in_values":
            params["value_set"] = parsed.get("values", [])
        elif check_type_str == "row_count":
            params["min_value"] = parsed.get("threshold", 1)
        elif check_type_str == "custom":
            params["expression"] = expression

        # Create DQCheck
        try:
            dq_check = DQCheck(
                check_id=rule_id,
                name=f"Contract rule: {rule_id}",
                category=category,
                severity=dq_severity,
                expectation_type=expectation_type,
                params=params,
                target_level="COLUMN" if field_name else "DATASET",
                target_column=field_name,
                target_pattern=None,
            )
            return dq_check
        except Exception as e:
            # Log error but don't fail
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to convert rule {rule_id} to DQCheck: {e}")
            return None

    @staticmethod
    def get_contract_quality_checks(contract: Contract) -> list[DQCheck]:
        """
        Get all quality checks from contract's quality rules.

        Args:
            contract: Contract instance

        Returns:
            List of DQCheck instances
        """
        quality_data = ContractQualityRulesExtractor.extract_quality_rules(contract)
        rules = quality_data.get("rules", [])

        checks = []
        for rule in rules:
            dq_check = ContractQualityRulesExtractor.convert_rule_to_dq_check(rule)
            if dq_check:
                checks.append(dq_check)

        return checks

    @staticmethod
    def get_contract_profile_key(contract: Contract, fallback: str = "intake_basic_gx") -> str:
        """
        Get default profile key from contract, with fallback.

        Args:
            contract: Contract instance
            fallback: Fallback profile key if not specified in contract

        Returns:
            Profile key string
        """
        quality_data = ContractQualityRulesExtractor.extract_quality_rules(contract)
        default_profile_key = quality_data.get("default_profile_key")

        if default_profile_key:
            return default_profile_key

        return fallback
