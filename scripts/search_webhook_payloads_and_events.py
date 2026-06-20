#!/usr/bin/env python3
"""
Comprehensive Webhook Payloads and Event Definitions Search Script

Searches for webhook payload structures, event definitions, and subscription configurations.
This script implements task 9.6.1.2.5 from the ODPS integration tasks.
"""

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class WebhookEndpointReference:
    """Represents a webhook endpoint reference"""

    file_path: str
    line_number: int
    endpoint: str
    method: str
    context: str
    event_type: str | None = None


@dataclass
class WebhookPayloadStructure:
    """Represents a webhook payload structure"""

    file_path: str
    line_number: int
    event_type: str
    payload_fields: list[str]
    payload_example: dict[str, Any] | None = None
    context: str = ""


@dataclass
class WebhookSubscriptionConfig:
    """Represents a webhook subscription configuration"""

    file_path: str
    line_number: int
    event_types: list[str]
    url_pattern: str | None = None
    context: str = ""


class WebhookPayloadsAndEventsSearcher:
    """Searches for webhook payloads and event definitions"""

    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.endpoint_references: list[WebhookEndpointReference] = []
        self.payload_structures: list[WebhookPayloadStructure] = []
        self.subscription_configs: list[WebhookSubscriptionConfig] = []
        self.event_types_found: set[str] = set()

    def should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped"""
        skip_patterns = [
            "__pycache__",
            ".pyc",
            ".pyo",
            ".pyd",
            "node_modules",
            ".git",
            "venv",
            "htmlcov",
            "coverage.xml",
            ".egg-info",
            "migrations",
            "backups",
            "deployment_logs",
        ]
        path_str = str(file_path)
        return any(pattern in path_str for pattern in skip_patterns)

    def search_webhook_endpoint_references(self):
        """Search for webhook endpoint references in the codebase"""
        print("Searching for webhook endpoint references...")

        for py_file in self.root_dir.rglob("*.py"):
            if self.should_skip_file(py_file):
                continue

            try:
                content = py_file.read_text(encoding="utf-8")
                lines = content.split("\n")

                for i, line in enumerate(lines, 1):
                    # Search for webhook URL patterns
                    if re.search(r"/api/v1/webhooks", line, re.IGNORECASE):
                        endpoint_match = re.search(r'["\'](/api/v1/webhooks[^"\']+)["\']', line)
                        if endpoint_match:
                            endpoint = endpoint_match.group(1)
                            method = self._extract_method_from_line(line)

                            # Try to extract event type from context
                            event_type = self._extract_event_type_from_context(lines, i)

                            self.endpoint_references.append(
                                WebhookEndpointReference(
                                    file_path=str(py_file.relative_to(self.root_dir)),
                                    line_number=i,
                                    endpoint=endpoint,
                                    method=method,
                                    event_type=event_type,
                                    context=self._get_context(lines, i),
                                )
                            )

                    # Search for webhook service calls
                    if re.search(r"WebhookDeliveryService|trigger_webhook|deliver_webhook", line):
                        # Look for endpoint references in nearby lines
                        for j in range(max(0, i - 5), min(len(lines), i + 10)):
                            endpoint_match = re.search(
                                r'["\']([^"\']*webhook[^"\']*)["\']', lines[j]
                            )
                            if endpoint_match:
                                endpoint = endpoint_match.group(1)
                                if "/api/" in endpoint or "webhook" in endpoint.lower():
                                    event_type = self._extract_event_type_from_context(lines, j)
                                    self.endpoint_references.append(
                                        WebhookEndpointReference(
                                            file_path=str(py_file.relative_to(self.root_dir)),
                                            line_number=j,
                                            endpoint=endpoint,
                                            method="POST",  # Webhooks are typically POST
                                            event_type=event_type,
                                            context=self._get_context(lines, j),
                                        )
                                    )

            except Exception as e:
                print(f"Error processing {py_file}: {e}")

    def search_payload_structures(self):
        """Search for webhook payload structures"""
        print("Searching for webhook payload structures...")

        for py_file in self.root_dir.rglob("*.py"):
            if self.should_skip_file(py_file):
                continue

            try:
                content = py_file.read_text(encoding="utf-8")
                lines = content.split("\n")

                for i, line in enumerate(lines, 1):
                    # Search for payload definitions
                    if re.search(
                        r'payload\s*=|payload\s*:|"payload"|payload\s*\{', line, re.IGNORECASE
                    ):
                        # Look for event_type in nearby lines
                        event_type = self._extract_event_type_from_context(lines, i)
                        if event_type:
                            # Extract payload fields
                            payload_fields = self._extract_payload_fields(lines, i)
                            payload_example = self._extract_payload_example(lines, i)

                            if payload_fields:
                                self.payload_structures.append(
                                    WebhookPayloadStructure(
                                        file_path=str(py_file.relative_to(self.root_dir)),
                                        line_number=i,
                                        event_type=event_type,
                                        payload_fields=payload_fields,
                                        payload_example=payload_example,
                                        context=self._get_context(lines, i, context_lines=20),
                                    )
                                )
                                self.event_types_found.add(event_type)

            except Exception as e:
                print(f"Error processing {py_file}: {e}")

    def search_subscription_configs(self):
        """Search for webhook subscription configurations"""
        print("Searching for webhook subscription configurations...")

        for py_file in self.root_dir.rglob("*.py"):
            if self.should_skip_file(py_file):
                continue

            try:
                content = py_file.read_text(encoding="utf-8")
                lines = content.split("\n")

                for i, line in enumerate(lines, 1):
                    # Search for event_types assignments
                    if re.search(
                        r'event_types\s*=|event_types\s*:|"event_types"', line, re.IGNORECASE
                    ):
                        event_types = self._extract_event_types_from_line(line, lines, i)
                        if event_types:
                            url_pattern = self._extract_url_pattern_from_context(lines, i)

                            self.subscription_configs.append(
                                WebhookSubscriptionConfig(
                                    file_path=str(py_file.relative_to(self.root_dir)),
                                    line_number=i,
                                    event_types=event_types,
                                    url_pattern=url_pattern,
                                    context=self._get_context(lines, i, context_lines=10),
                                )
                            )

                            for event_type in event_types:
                                self.event_types_found.add(event_type)

            except Exception as e:
                print(f"Error processing {py_file}: {e}")

    def analyze_webhook_models(self):
        """Analyze webhook models for event types and configurations"""
        print("Analyzing webhook models...")

        webhook_models_file = self.root_dir / "hub" / "apps" / "webhooks" / "models.py"
        if not webhook_models_file.exists():
            return

        try:
            content = webhook_models_file.read_text(encoding="utf-8")
            lines = content.split("\n")

            # Extract WebhookEventType enum values - look for pattern: NAME = "value", "Label"
            in_event_type_enum = False
            for i, line in enumerate(lines, 1):
                if "class WebhookEventType" in line:
                    in_event_type_enum = True
                    continue

                if in_event_type_enum:
                    # Stop at next class definition or method definition
                    if line.strip().startswith("class ") and "WebhookEventType" not in line:
                        in_event_type_enum = False
                        break

                    # Extract event type definitions: NAME = "value", "Label"
                    # Pattern: CONTRACT_CREATED = "contract.created", "Contract Created"
                    event_match = re.search(
                        r'(\w+)\s*=\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']', line
                    )
                    if event_match:
                        event_match.group(1)
                        event_value = event_match.group(2)
                        # Only add if it looks like an event type (contains a dot and matches known patterns)
                        if "." in event_value and self._is_valid_event_type(event_value):
                            self.event_types_found.add(event_value)

            # Also extract from get_odps_event_types, get_transformation_event_types, etc.
            for i, line in enumerate(lines, 1):
                if (
                    "get_odps_event_types" in line
                    or "get_transformation_event_types" in line
                    or "get_mesh_event_types" in line
                    or "get_virtualization_event_types" in line
                ):
                    # Look for return statement with list
                    for j in range(i, min(len(lines), i + 30)):
                        if "return" in lines[j]:
                            # Extract event types from return list
                            list_match = re.search(r"\[([^\]]+)\]", lines[j])
                            if list_match:
                                event_list = list_match.group(1)
                                for event_match in re.finditer(r"str\(cls\.(\w+)\)", event_list):
                                    # This is a reference to an enum member, we already extracted it above
                                    pass

        except Exception as e:
            print(f"Error analyzing webhook models: {e}")

    def analyze_webhook_validators(self):
        """Analyze webhook validators for payload structures"""
        print("Analyzing webhook validators...")

        validator_files = [
            self.root_dir / "hub" / "apps" / "webhooks" / "odps_webhook_validators.py",
            self.root_dir / "hub" / "apps" / "webhooks" / "transformation_webhook_validators.py",
        ]

        for validator_file in validator_files:
            if not validator_file.exists():
                continue

            try:
                content = validator_file.read_text(encoding="utf-8")
                lines = content.split("\n")

                # Extract payload validation logic
                for i, line in enumerate(lines, 1):
                    if "required_fields" in line or "payload" in line.lower():
                        # Look for field definitions
                        payload_fields = self._extract_payload_fields(lines, i)
                        if payload_fields:
                            # Try to determine event type from function name or context
                            event_type = self._extract_event_type_from_function_name(lines, i)

                            self.payload_structures.append(
                                WebhookPayloadStructure(
                                    file_path=str(validator_file.relative_to(self.root_dir)),
                                    line_number=i,
                                    event_type=event_type or "unknown",
                                    payload_fields=payload_fields,
                                    context=self._get_context(lines, i, context_lines=30),
                                )
                            )

            except Exception as e:
                print(f"Error analyzing {validator_file}: {e}")

    def _extract_method_from_line(self, line: str) -> str:
        """Extract HTTP method from line"""
        method_match = re.search(r"\.(get|post|put|patch|delete|request)", line, re.IGNORECASE)
        if method_match:
            return method_match.group(1).upper()
        return "POST"  # Default for webhooks

    def _extract_event_type_from_context(self, lines: list[str], line_num: int) -> str | None:
        """Extract event type from context"""
        # Check current line and nearby lines
        for i in range(max(0, line_num - 5), min(len(lines), line_num + 10)):
            line = lines[i]
            # Look for event_type assignments
            event_match = re.search(r'event_type\s*[:=]\s*["\']([^"\']+)["\']', line)
            if event_match:
                return event_match.group(1)

            # Look for event type in function calls
            event_match = re.search(
                r"(odps\.|contract\.|asset\.|pipeline\.|mesh\.|virtualization\.)[\w.]+", line
            )
            if event_match:
                return event_match.group(0)

        return None

    def _extract_event_type_from_function_name(self, lines: list[str], line_num: int) -> str | None:
        """Extract event type from function name"""
        # Look backwards for function definition
        for i in range(max(0, line_num - 20), line_num):
            line = lines[i]
            func_match = re.search(r"def\s+validate_(\w+)_webhook_payload", line)
            if func_match:
                prefix = func_match.group(1)
                # Map prefix to event type pattern
                if prefix == "odps":
                    return "odps.created"  # Default ODPS event
                elif prefix == "transformation":
                    return "pipeline.created"  # Default transformation event
                return None
        return None

    def _extract_payload_fields(self, lines: list[str], line_num: int) -> list[str]:
        """Extract payload field names from context"""
        fields = []

        # Look for field definitions in nearby lines
        for i in range(max(0, line_num - 10), min(len(lines), line_num + 30)):
            line = lines[i]

            # Look for field assignments
            field_match = re.search(r'["\'](\w+)["\']\s*[:=]', line)
            if field_match:
                field_name = field_match.group(1)
                if field_name not in fields and field_name in [
                    "event_type",
                    "resource_type",
                    "resource_id",
                    "timestamp",
                    "data",
                ]:
                    fields.append(field_name)

            # Look for required_fields lists
            if "required_fields" in line:
                list_match = re.search(r"\[([^\]]+)\]", line)
                if list_match:
                    field_list = list_match.group(1)
                    for field in re.findall(r'["\'](\w+)["\']', field_list):
                        if field not in fields:
                            fields.append(field)

        return fields

    def _extract_payload_example(self, lines: list[str], line_num: int) -> dict[str, Any] | None:
        """Extract payload example from context"""
        # Look for dictionary literals
        for i in range(max(0, line_num - 5), min(len(lines), line_num + 20)):
            line = lines[i]
            if "{" in line and "event_type" in line:
                # Try to parse as JSON-like structure
                try:
                    # Simple extraction - look for key-value pairs
                    payload = {}
                    if '"event_type"' in line or "'event_type'" in line:
                        payload["event_type"] = "example"
                    if '"resource_type"' in line or "'resource_type'" in line:
                        payload["resource_type"] = "example"
                    if '"resource_id"' in line or "'resource_id'" in line:
                        payload["resource_id"] = "example"
                    if '"timestamp"' in line or "'timestamp'" in line:
                        payload["timestamp"] = "example"
                    if '"data"' in line or "'data'" in line:
                        payload["data"] = {}
                    return payload if payload else None
                except Exception:
                    pass

        return None

    def _extract_event_types_from_line(
        self, line: str, lines: list[str], line_num: int
    ) -> list[str]:
        """Extract event types from a line"""
        event_types = []

        # Look for list of event types
        list_match = re.search(r"\[([^\]]+)\]", line)
        if list_match:
            event_list = list_match.group(1)
            # Extract string values that look like event types
            for event_match in re.finditer(r'["\']([^"\']+)["\']', event_list):
                event_value = event_match.group(1)
                # Only add if it's a valid event type
                if self._is_valid_event_type(event_value):
                    event_types.append(event_value)

        # Look for multi-line list
        if not event_types:
            for i in range(line_num, min(len(lines), line_num + 10)):
                event_match = re.search(r'["\']([^"\']+)["\']', lines[i])
                if event_match:
                    event_value = event_match.group(1)
                    # Only add if it's a valid event type
                    if self._is_valid_event_type(event_value):
                        if event_value not in event_types:
                            event_types.append(event_value)

        return event_types

    def _extract_url_pattern_from_context(self, lines: list[str], line_num: int) -> str | None:
        """Extract URL pattern from context"""
        for i in range(max(0, line_num - 5), min(len(lines), line_num + 10)):
            line = lines[i]
            url_match = re.search(r'url\s*[:=]\s*["\']([^"\']+)["\']', line)
            if url_match:
                return url_match.group(1)
        return None

    def _is_valid_event_type(self, event_type: str) -> bool:
        """Check if a string is a valid event type"""
        # Valid event types have dots and start with known prefixes
        valid_prefixes = (
            "contract",
            "asset",
            "odps",
            "pipeline",
            "mesh",
            "virtualization",
            "ingestion",
            "quality",
            "compliance",
            "version",
        )

        # Must contain a dot (e.g., "contract.created")
        if "." not in event_type:
            return False

        # Must start with a valid prefix
        if not any(event_type.startswith(prefix) for prefix in valid_prefixes):
            return False

        # Filter out common false positives - check if the string looks like a test name or comment
        invalid_patterns = [
            "/event-types/",
            "test",
            "Test",
            "TEST",
            "example",
            "Example",
            "analyzing",
            "Analyzing",
            "handle",
            "Handle",
            "convert",
            "Convert",
            "message",
            "Message",
            "filtering",
            "Filtering",
            "getting",
            "Getting",
            "listing",
            "Listing",
            "Number of",
            "Event message",
            "Handle list",
            "Handle ping",
            "Handle unsubscribe",
        ]

        # Check if it contains invalid patterns
        event_lower = event_type.lower()
        for pattern in invalid_patterns:
            if pattern.lower() in event_lower:
                # Allow if it's still a valid event type pattern (e.g., "contract.created" contains "create" but is valid)
                if not any(
                    event_lower.startswith(prefix) and "." in event_lower
                    for prefix in valid_prefixes
                ):
                    return False

        # Additional validation: should have format like "prefix.action" or "prefix.category.action"
        parts = event_type.split(".")
        if len(parts) < 2:
            return False

        # First part should be a valid prefix
        if parts[0] not in valid_prefixes:
            return False

        return True

    def _get_context(self, lines: list[str], line_num: int, context_lines: int = 5) -> str:
        """Get context around a line"""
        start = max(0, line_num - context_lines - 1)
        end = min(len(lines), line_num + context_lines)
        context = lines[start:end]
        return "\n".join(context)

    def generate_report(self) -> dict[str, Any]:
        """Generate comprehensive report"""
        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_endpoint_references": len(self.endpoint_references),
                "total_payload_structures": len(self.payload_structures),
                "total_subscription_configs": len(self.subscription_configs),
                "unique_event_types": len(self.event_types_found),
                "event_types": sorted(list(self.event_types_found)),
            },
            "endpoint_references": [asdict(ref) for ref in self.endpoint_references],
            "payload_structures": [asdict(struct) for struct in self.payload_structures],
            "subscription_configs": [asdict(config) for config in self.subscription_configs],
        }

        return report

    def run(self) -> dict[str, Any]:
        """Run the complete search"""
        print("Starting webhook payloads and events search...")
        print(f"Root directory: {self.root_dir}")

        # Step 1: Search for endpoint references
        print("\n=== Step 1: Searching for webhook endpoint references ===")
        self.search_webhook_endpoint_references()
        print(f"Found {len(self.endpoint_references)} endpoint references")

        # Step 2: Search for payload structures
        print("\n=== Step 2: Searching for webhook payload structures ===")
        self.search_payload_structures()
        print(f"Found {len(self.payload_structures)} payload structures")

        # Step 3: Search for subscription configurations
        print("\n=== Step 3: Searching for webhook subscription configurations ===")
        self.search_subscription_configs()
        print(f"Found {len(self.subscription_configs)} subscription configurations")

        # Step 4: Analyze webhook models
        print("\n=== Step 4: Analyzing webhook models ===")
        self.analyze_webhook_models()
        print(f"Found {len(self.event_types_found)} unique event types")

        # Step 5: Analyze webhook validators
        print("\n=== Step 5: Analyzing webhook validators ===")
        self.analyze_webhook_validators()
        print(f"Found {len(self.payload_structures)} total payload structures")

        # Step 6: Generate report
        print("\n=== Step 6: Generating report ===")
        report = self.generate_report()

        return report


def main():
    """Main entry point"""
    import sys

    # Get root directory from command line or use current directory
    if len(sys.argv) > 1:
        root_dir = sys.argv[1]
    else:
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    searcher = WebhookPayloadsAndEventsSearcher(root_dir)
    report = searcher.run()

    # Save report
    output_file = Path(root_dir) / "docs" / "api-audit" / "webhook-payloads-and-events-report.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n=== Report saved to: {output_file} ===")
    print("\nSummary:")
    print(f"  Total endpoint references: {report['summary']['total_endpoint_references']}")
    print(f"  Total payload structures: {report['summary']['total_payload_structures']}")
    print(f"  Total subscription configs: {report['summary']['total_subscription_configs']}")
    print(f"  Unique event types: {report['summary']['unique_event_types']}")
    print("\nEvent types found:")
    for event_type in report["summary"]["event_types"][:20]:  # Show first 20
        print(f"  - {event_type}")
    if len(report["summary"]["event_types"]) > 20:
        print(f"  ... and {len(report['summary']['event_types']) - 20} more")


if __name__ == "__main__":
    main()
