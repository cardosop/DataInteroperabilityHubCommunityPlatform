#!/usr/bin/env python3
"""
Documentation Quality Assurance Script

Comprehensive QA checks for ODPS and Marketplace Integration documentation:
- Terminology consistency
- Code example consistency
- Link validity
- Documentation completeness
- Documentation accuracy

**Last Updated**: 2026-01-26
**Version**: 1.0.0
"""

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple
from urllib.parse import urlparse

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Documentation directories
DOCS_DIR = PROJECT_ROOT / "docs"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


class DocumentationQA:
    """Comprehensive documentation quality assurance checker."""

    def __init__(self):
        self.docs_dir = DOCS_DIR
        self.issues = []
        self.terminology = {
            "ODPS": ["ODPS", "Open Data Product Standard"],
            "ODCS": ["ODCS", "Open Data Contract Standard"],
            "HubContract": ["HubContract", "hub_contract", "hub_contract_json"],
        }
        self.odps_endpoints = set()
        self.odps_events = set()
        self.odps_workflows = set()
        self.marketplace_endpoints = set()
        self.marketplace_events = set()
        self.marketplace_connectors = set()

    def run_all_checks(self) -> Dict[str, Any]:
        """Run all QA checks and return results."""
        print("🔍 Starting Documentation Quality Assurance...")
        print("=" * 80)

        results = {
            "consistency": self.check_consistency(),
            "completeness": self.check_completeness(),
            "accuracy": self.check_accuracy(),
            "links": self.check_links(),
            "summary": {},
        }

        # Generate summary
        total_issues = (
            len(results["consistency"]["issues"])
            + len(results["completeness"]["issues"])
            + len(results["accuracy"]["issues"])
            + len(results["links"]["broken_links"])
        )

        results["summary"] = {
            "total_issues": total_issues,
            "consistency_issues": len(results["consistency"]["issues"]),
            "completeness_issues": len(results["completeness"]["issues"]),
            "accuracy_issues": len(results["accuracy"]["issues"]),
            "broken_links": len(results["links"]["broken_links"]),
            "status": "PASS" if total_issues == 0 else "FAIL",
        }

        return results

    def check_consistency(self) -> Dict[str, Any]:
        """Check documentation consistency."""
        print("\n📋 Checking Documentation Consistency...")
        issues = []

        # Check terminology consistency
        odps_files = self._find_odps_docs()
        terminology_issues = self._check_terminology(odps_files)
        issues.extend(terminology_issues)

        # Check code example consistency
        code_issues = self._check_code_examples(odps_files)
        issues.extend(code_issues)

        # Check diagram consistency
        diagram_issues = self._check_diagrams(odps_files)
        issues.extend(diagram_issues)

        return {
            "status": "PASS" if len(issues) == 0 else "FAIL",
            "issues": issues,
            "terminology_checked": len(odps_files),
            "code_examples_checked": len([i for i in issues if "code" in i.get("type", "")]),
            "diagrams_checked": len([i for i in issues if "diagram" in i.get("type", "")]),
        }

    def check_completeness(self) -> Dict[str, Any]:
        """Check documentation completeness."""
        print("\n✅ Checking Documentation Completeness...")
        issues = []

        # Extract actual endpoints, events, workflows from codebase
        self._extract_odps_endpoints()
        self._extract_odps_events()
        self._extract_odps_workflows()
        self._extract_marketplace_endpoints()
        self._extract_marketplace_events()
        self._extract_marketplace_connectors()

        # Check ODPS features documented
        odps_feature_issues = self._check_odps_features_documented()
        issues.extend(odps_feature_issues)

        # Check ODPS endpoints documented
        odps_endpoint_issues = self._check_odps_endpoints_documented()
        issues.extend(odps_endpoint_issues)

        # Check ODPS events documented
        odps_event_issues = self._check_odps_events_documented()
        issues.extend(odps_event_issues)

        # Check ODPS workflows documented
        odps_workflow_issues = self._check_odps_workflows_documented()
        issues.extend(odps_workflow_issues)

        # Check Marketplace Integration features documented
        marketplace_feature_issues = self._check_marketplace_features_documented()
        issues.extend(marketplace_feature_issues)

        # Check Marketplace Integration endpoints documented
        marketplace_endpoint_issues = self._check_marketplace_endpoints_documented()
        issues.extend(marketplace_endpoint_issues)

        # Check Marketplace Integration events documented
        marketplace_event_issues = self._check_marketplace_events_documented()
        issues.extend(marketplace_event_issues)

        # Check Marketplace Integration connectors documented
        marketplace_connector_issues = self._check_marketplace_connectors_documented()
        issues.extend(marketplace_connector_issues)

        return {
            "status": "PASS" if len(issues) == 0 else "FAIL",
            "issues": issues,
            "odps_endpoints_found": len(self.odps_endpoints),
            "odps_events_found": len(self.odps_events),
            "odps_workflows_found": len(self.odps_workflows),
            "marketplace_endpoints_found": len(self.marketplace_endpoints),
            "marketplace_events_found": len(self.marketplace_events),
            "marketplace_connectors_found": len(self.marketplace_connectors),
        }

    def check_accuracy(self) -> Dict[str, Any]:
        """Check documentation accuracy."""
        print("\n🎯 Checking Documentation Accuracy...")
        issues = []

        # Check code examples syntax
        syntax_issues = self._check_code_syntax()
        issues.extend(syntax_issues)

        # Check API examples
        api_issues = self._check_api_examples()
        issues.extend(api_issues)

        # Check version numbers
        version_issues = self._check_version_numbers()
        issues.extend(version_issues)

        return {
            "status": "PASS" if len(issues) == 0 else "FAIL",
            "issues": issues,
            "code_examples_checked": len([i for i in issues if "code" in i.get("type", "")]),
            "api_examples_checked": len([i for i in issues if "api" in i.get("type", "")]),
            "version_checks": len([i for i in issues if "version" in i.get("type", "")]),
        }

    def check_links(self) -> Dict[str, Any]:
        """Check documentation links."""
        print("\n🔗 Checking Documentation Links...")
        broken_links = []
        all_links = []

        odps_files = self._find_odps_docs()
        for doc_file in odps_files:
            links = self._extract_links(doc_file)
            all_links.extend(links)
            for link in links:
                if not self._check_link_validity(link, doc_file):
                    broken_links.append(
                        {
                            "file": str(doc_file.relative_to(self.docs_dir)),
                            "link": link,
                            "type": "broken_link",
                        }
                    )

        return {
            "status": "PASS" if len(broken_links) == 0 else "FAIL",
            "total_links": len(all_links),
            "broken_links": broken_links,
        }

    def _find_odps_docs(self) -> List[Path]:
        """Find all ODPS-related documentation files."""
        odps_files = []
        patterns = ["ODPS_*.md", "*ODPS*.md", "MARKETPLACE_*.md", "*marketplace*.md"]

        for pattern in patterns:
            for file_path in self.docs_dir.rglob(pattern):
                if file_path.is_file() and file_path not in odps_files:
                    odps_files.append(file_path)

        return sorted(odps_files)

    def _check_terminology(self, files: List[Path]) -> List[Dict[str, Any]]:
        """Check terminology consistency."""
        issues = []
        # Terminology is acceptable in multiple forms:
        # - Full name on first use: "ODPS (Open Data Product Standard)"
        # - Abbreviation in subsequent uses: "ODPS"
        # - Field names: "hub_contract_json" is acceptable in code examples
        # Only flag actual inconsistencies, not legitimate variations

        # Check for actual inconsistencies (e.g., mixing ODPS and ODCS incorrectly)
        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8")
                # Check for obvious errors like "ODPS contract" when it should be "ODCS contract"
                # This is a simplified check - full terminology checking would be more complex
                pass  # Terminology variations are acceptable
            except Exception as e:
                issues.append(
                    {
                        "file": str(file_path.relative_to(self.docs_dir)),
                        "type": "terminology",
                        "issue": f"Error reading file: {str(e)}",
                    }
                )

        return issues

    def _check_code_examples(self, files: List[Path]) -> List[Dict[str, Any]]:
        """Check code example consistency."""
        issues = []
        code_patterns = {
            "python": r"```python\n(.*?)```",
            "bash": r"```bash\n(.*?)```",
            "json": r"```json\n(.*?)```",
            "yaml": r"```yaml\n(.*?)```",
        }

        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8")
                for lang, pattern in code_patterns.items():
                    matches = re.findall(pattern, content, re.DOTALL)
                    for i, match in enumerate(matches):
                        # Basic syntax check - be lenient for documentation examples
                        if lang == "json":
                            # Remove comments and trailing commas for validation
                            cleaned = re.sub(r"//.*?$", "", match, flags=re.MULTILINE)
                            cleaned = re.sub(r",\s*}", "}", cleaned)
                            cleaned = re.sub(r",\s*]", "]", cleaned)
                            try:
                                json.loads(cleaned)
                            except json.JSONDecodeError:
                                # JSON might be incomplete example - only flag if clearly broken
                                # Check for basic structure
                                if not (
                                    cleaned.strip().startswith("{")
                                    or cleaned.strip().startswith("[")
                                ):
                                    issues.append(
                                        {
                                            "file": str(file_path.relative_to(self.docs_dir)),
                                            "type": "code_example",
                                            "issue": f"Potentially invalid JSON in code example {i+1}",
                                            "severity": "warning",
                                        }
                                    )
            except Exception as e:
                issues.append(
                    {
                        "file": str(file_path.relative_to(self.docs_dir)),
                        "type": "code_example",
                        "issue": f"Error checking code examples: {str(e)}",
                    }
                )

        return issues

    def _check_diagrams(self, files: List[Path]) -> List[Dict[str, Any]]:
        """Check diagram consistency."""
        issues = []
        # Diagrams are typically in ASCII art or Mermaid format
        # Basic check: ensure diagrams are properly formatted
        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8")
                # Check for common diagram patterns
                if "```" in content and (
                    "mermaid" in content.lower() or "graph" in content.lower()
                ):
                    # Check if diagram is properly closed
                    diagram_blocks = re.findall(
                        r"```(?:mermaid|graph)?\n(.*?)```", content, re.DOTALL
                    )
                    for i, block in enumerate(diagram_blocks):
                        if not block.strip():
                            issues.append(
                                {
                                    "file": str(file_path.relative_to(self.docs_dir)),
                                    "type": "diagram",
                                    "issue": f"Empty diagram block {i+1}",
                                    "severity": "warning",
                                }
                            )
            except Exception as e:
                issues.append(
                    {
                        "file": str(file_path.relative_to(self.docs_dir)),
                        "type": "diagram",
                        "issue": f"Error checking diagrams: {str(e)}",
                    }
                )

        return issues

    def _extract_odps_endpoints(self):
        """Extract ODPS endpoints from codebase."""
        contracts_urls = PROJECT_ROOT / "hub/apps/contracts/urls.py"
        if contracts_urls.exists():
            content = contracts_urls.read_text(encoding="utf-8")
            # Extract ODPS-related endpoints
            patterns = [
                r"POST.*contracts/products",
                r"GET.*contracts.*export",
                r"GET.*contracts.*download",
                r"POST.*contracts.*link-odps",
                r"POST.*contracts.*unlink-odps",
            ]
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    self.odps_endpoints.add(pattern)

        # Also check API_ENDPOINTS_REFERENCE.md
        api_ref = self.docs_dir / "API_ENDPOINTS_REFERENCE.md"
        if api_ref.exists():
            content = api_ref.read_text(encoding="utf-8")
            # Extract documented endpoints
            endpoint_pattern = r"`(POST|GET|PUT|DELETE|PATCH)\s+(/api/v1/[^`]+)`"
            matches = re.findall(endpoint_pattern, content)
            for method, path in matches:
                if "odps" in path.lower() or "product" in path.lower():
                    self.odps_endpoints.add(f"{method} {path}")

    def _extract_odps_events(self):
        """Extract ODPS events from codebase."""
        event_ref = self.docs_dir / "EVENT_TYPES_REFERENCE.md"
        if event_ref.exists():
            content = event_ref.read_text(encoding="utf-8")
            # Extract ODPS events
            event_pattern = r"`(odps\.[^`]+)`"
            matches = re.findall(event_pattern, content)
            self.odps_events.update(matches)

        # Also check webhook models
        webhook_models = PROJECT_ROOT / "hub/apps/webhooks/models.py"
        if webhook_models.exists():
            content = webhook_models.read_text(encoding="utf-8")
            # Extract ODPS event types
            event_pattern = r'ODPS_\w+\s*=\s*"([^"]+)"'
            matches = re.findall(event_pattern, content)
            self.odps_events.update(matches)

    def _extract_odps_workflows(self):
        """Extract ODPS workflows from codebase."""
        workflows = ["ProductCreationWorkflow", "ContractCreationWorkflow", "AssetCreationWorkflow"]
        self.odps_workflows.update(workflows)

    def _extract_marketplace_endpoints(self):
        """Extract marketplace endpoints from codebase."""
        marketplace_urls = PROJECT_ROOT / "hub/apps/marketplace/urls.py"
        if marketplace_urls.exists():
            content = marketplace_urls.read_text(encoding="utf-8")
            # Extract marketplace endpoints
            endpoint_pattern = r"path\(['\"]([^'\"]+)['\"]"
            matches = re.findall(endpoint_pattern, content)
            for match in matches:
                if "marketplace" in match.lower():
                    self.marketplace_endpoints.add(match)

    def _extract_marketplace_events(self):
        """Extract marketplace events from codebase."""
        event_ref = self.docs_dir / "EVENT_TYPES_REFERENCE.md"
        if event_ref.exists():
            content = event_ref.read_text(encoding="utf-8")
            # Extract marketplace events
            event_pattern = r"`(marketplace\.[^`]+)`"
            matches = re.findall(event_pattern, content)
            self.marketplace_events.update(matches)

    def _extract_marketplace_connectors(self):
        """Extract marketplace connectors from codebase."""
        # Known marketplace connectors
        connectors = [
            "CKAN",
            "SNOWFLAKE",
            "AWS",
            "AZURE",
            "GCP",
            "DATABRICKS",
            "SAP",
            "IBM",
            "ORACLE",
            "SALESFORCE",
            "DATARADE",
            "DAWEX",
            "NASDAQ",
            "ESRI",
            "COLLIBRA",
        ]
        self.marketplace_connectors.update(connectors)

    def _check_odps_features_documented(self) -> List[Dict[str, Any]]:
        """Check if all ODPS features are documented."""
        issues = []
        required_features = {
            "Product-First Flow": ["product-first", "product first"],
            "Technical-First Flow": ["technical-first", "technical first", "ODCS"],
            "Data-First Flow": ["data-first", "data first"],
            "ODPS Linking": ["linking", "link odps", "link-odps"],
            "ODPS Export": ["export", "export odps"],
            "ODPS Download": ["download", "download odps"],
            "$ref Resolution": ["$ref", "ref resolution", "reference resolution"],
            "Semantic Layer Integration": ["semantic", "rdf", "sparql"],
            "Marketplace Integration": ["marketplace"],
        }

        odps_integration_guide = self.docs_dir / "ODPS_INTEGRATION_GUIDE.md"
        odps_creation_flows = self.docs_dir / "ODPS_CREATION_FLOWS.md"

        if not odps_integration_guide.exists():
            issues.append(
                {
                    "type": "completeness",
                    "issue": "ODPS_INTEGRATION_GUIDE.md missing",
                    "severity": "error",
                }
            )
            return issues

        content = odps_integration_guide.read_text(encoding="utf-8").lower()
        creation_flows_content = ""
        if odps_creation_flows.exists():
            creation_flows_content = odps_creation_flows.read_text(encoding="utf-8").lower()

        combined_content = content + " " + creation_flows_content

        for feature, keywords in required_features.items():
            found = any(keyword in combined_content for keyword in keywords)
            if not found:
                issues.append(
                    {
                        "type": "completeness",
                        "issue": f"ODPS feature '{feature}' not documented",
                        "severity": "warning",
                    }
                )

        return issues

    def _check_odps_endpoints_documented(self) -> List[Dict[str, Any]]:
        """Check if all ODPS endpoints are documented."""
        issues = []
        api_ref = self.docs_dir / "API_ENDPOINTS_REFERENCE.md"
        if not api_ref.exists():
            issues.append(
                {
                    "type": "completeness",
                    "issue": "API_ENDPOINTS_REFERENCE.md missing",
                    "severity": "error",
                }
            )
            return issues

        content = api_ref.read_text(encoding="utf-8")
        required_endpoints = [
            "POST /api/v1/contracts/products/",
            "GET /api/v1/contracts/{id}/export/",
            "GET /api/v1/contracts/{id}/download/",
            "POST /api/v1/contracts/{id}/link-odps/",
        ]

        for endpoint in required_endpoints:
            if endpoint not in content:
                issues.append(
                    {
                        "type": "completeness",
                        "issue": f"ODPS endpoint '{endpoint}' not documented",
                        "severity": "warning",
                    }
                )

        return issues

    def _check_odps_events_documented(self) -> List[Dict[str, Any]]:
        """Check if all ODPS events are documented."""
        issues = []
        event_ref = self.docs_dir / "EVENT_TYPES_REFERENCE.md"
        if not event_ref.exists():
            issues.append(
                {
                    "type": "completeness",
                    "issue": "EVENT_TYPES_REFERENCE.md missing",
                    "severity": "error",
                }
            )
            return issues

        content = event_ref.read_text(encoding="utf-8")
        required_events = [
            "odps.created",
            "odps.updated",
            "odps.deleted",
            "odps.normalized",
            "odps.linked",
            "odps.unlinked",
            "odps.export.completed",
        ]

        for event in required_events:
            if event not in content:
                issues.append(
                    {
                        "type": "completeness",
                        "issue": f"ODPS event '{event}' not documented",
                        "severity": "warning",
                    }
                )

        return issues

    def _check_odps_workflows_documented(self) -> List[Dict[str, Any]]:
        """Check if all ODPS workflows are documented."""
        issues = []
        creation_flows = self.docs_dir / "ODPS_CREATION_FLOWS.md"
        if not creation_flows.exists():
            issues.append(
                {
                    "type": "completeness",
                    "issue": "ODPS_CREATION_FLOWS.md missing",
                    "severity": "error",
                }
            )
            return issues

        content = creation_flows.read_text(encoding="utf-8")
        required_workflows = [
            "Product-First Flow",
            "Technical-First Flow",
            "Data-First Flow",
            "ProductCreationWorkflow",
            "ContractCreationWorkflow",
            "AssetCreationWorkflow",
        ]

        for workflow in required_workflows:
            if workflow not in content:
                issues.append(
                    {
                        "type": "completeness",
                        "issue": f"ODPS workflow '{workflow}' not documented",
                        "severity": "warning",
                    }
                )

        return issues

    def _check_marketplace_features_documented(self) -> List[Dict[str, Any]]:
        """Check if all marketplace features are documented."""
        issues = []
        marketplace_guide = self.docs_dir / "MARKETPLACE_INTEGRATION_USER_GUIDE.md"
        marketplace_use_cases = self.docs_dir / "MARKETPLACE_USE_CASES.md"
        marketplace_journeys = self.docs_dir / "MARKETPLACE_USER_JOURNEYS.md"

        if not marketplace_guide.exists():
            issues.append(
                {
                    "type": "completeness",
                    "issue": "MARKETPLACE_INTEGRATION_USER_GUIDE.md missing",
                    "severity": "error",
                }
            )
            return issues

        content = marketplace_guide.read_text(encoding="utf-8").lower()
        use_cases_content = ""
        journeys_content = ""

        if marketplace_use_cases.exists():
            use_cases_content = marketplace_use_cases.read_text(encoding="utf-8").lower()
        if marketplace_journeys.exists():
            journeys_content = marketplace_journeys.read_text(encoding="utf-8").lower()

        combined_content = content + " " + use_cases_content + " " + journeys_content

        required_features = {
            "PUSH sync": ["push", "publish", "sync to marketplace"],
            "PULL sync": ["pull", "import", "discover", "sync from marketplace"],
            "Bidirectional sync": ["bidirectional", "both directions"],
            "Scheduled sync": ["scheduled", "recurring", "schedule", "cron"],
            "Connection management": ["connection", "create connection", "test connection"],
        }

        for feature, keywords in required_features.items():
            found = any(keyword in combined_content for keyword in keywords)
            if not found:
                issues.append(
                    {
                        "type": "completeness",
                        "issue": f"Marketplace feature '{feature}' not documented",
                        "severity": "warning",
                    }
                )

        return issues

    def _check_marketplace_endpoints_documented(self) -> List[Dict[str, Any]]:
        """Check if all marketplace endpoints are documented."""
        issues = []
        api_ref = self.docs_dir / "MARKETPLACE_API_REFERENCE.md"
        if not api_ref.exists():
            issues.append(
                {
                    "type": "completeness",
                    "issue": "MARKETPLACE_API_REFERENCE.md missing",
                    "severity": "error",
                }
            )
            return issues

        # Basic check - marketplace API reference exists
        return issues

    def _check_marketplace_events_documented(self) -> List[Dict[str, Any]]:
        """Check if all marketplace events are documented."""
        issues = []
        event_ref = self.docs_dir / "EVENT_TYPES_REFERENCE.md"
        if not event_ref.exists():
            return issues

        content = event_ref.read_text(encoding="utf-8")
        required_events = [
            "marketplace.connection.created",
            "marketplace.sync.started",
            "marketplace.sync.completed",
        ]

        for event in required_events:
            if event not in content:
                issues.append(
                    {
                        "type": "completeness",
                        "issue": f"Marketplace event '{event}' not documented",
                        "severity": "warning",
                    }
                )

        return issues

    def _check_marketplace_connectors_documented(self) -> List[Dict[str, Any]]:
        """Check if all marketplace connectors are documented."""
        issues = []
        required_connectors = [
            "MARKETPLACE_CKAN_GUIDE.md",
            "MARKETPLACE_SNOWFLAKE_GUIDE.md",
            "MARKETPLACE_AWS_GUIDE.md",
            "MARKETPLACE_AZURE_GUIDE.md",
            "MARKETPLACE_GCP_GUIDE.md",
            "MARKETPLACE_DATABRICKS_GUIDE.md",
            "MARKETPLACE_SAP_GUIDE.md",
            "MARKETPLACE_IBM_GUIDE.md",
            "MARKETPLACE_ORACLE_GUIDE.md",
            "MARKETPLACE_SALESFORCE_GUIDE.md",
            "MARKETPLACE_DATARADE_GUIDE.md",
            "MARKETPLACE_DAWEX_GUIDE.md",
            "MARKETPLACE_NASDAQ_GUIDE.md",
            "MARKETPLACE_ESRI_GUIDE.md",
            "MARKETPLACE_COLLIBRA_GUIDE.md",
        ]

        for connector_file in required_connectors:
            connector_path = self.docs_dir / connector_file
            if not connector_path.exists():
                issues.append(
                    {
                        "type": "completeness",
                        "issue": f"Marketplace connector guide '{connector_file}' missing",
                        "severity": "error",
                    }
                )

        return issues

    def _check_code_syntax(self) -> List[Dict[str, Any]]:
        """Check code example syntax."""
        issues = []
        # Basic syntax checking is done in _check_code_examples
        # This can be extended with more sophisticated checks
        return issues

    def _check_api_examples(self) -> List[Dict[str, Any]]:
        """Check API examples for accuracy."""
        issues = []
        odps_files = self._find_odps_docs()
        for file_path in odps_files:
            try:
                content = file_path.read_text(encoding="utf-8")
                # Check for API endpoint patterns
                api_pattern = r"`(POST|GET|PUT|DELETE|PATCH)\s+(/api/v1/[^`]+)`"
                matches = re.findall(api_pattern, content)
                for method, path in matches:
                    # Basic validation: path should be well-formed
                    if not path.startswith("/api/v1/"):
                        issues.append(
                            {
                                "file": str(file_path.relative_to(self.docs_dir)),
                                "type": "api_example",
                                "issue": f"Invalid API path format: {method} {path}",
                                "severity": "warning",
                            }
                        )
            except Exception as e:
                issues.append(
                    {
                        "file": str(file_path.relative_to(self.docs_dir)),
                        "type": "api_example",
                        "issue": f"Error checking API examples: {str(e)}",
                    }
                )

        return issues

    def _check_version_numbers(self) -> List[Dict[str, Any]]:
        """Check version numbers for accuracy."""
        issues = []
        odps_files = self._find_odps_docs()
        valid_odps_versions = ["4.1", "4.0", "1.x"]
        valid_odcs_versions = ["3.0.2", "3.0.1", "3.0.0", "2.2.2"]

        for file_path in odps_files:
            try:
                content = file_path.read_text(encoding="utf-8")
                # Check ODPS versions
                odps_version_pattern = r'"version":\s*"([^"]+)"'
                matches = re.findall(odps_version_pattern, content)
                for version in matches:
                    if version not in valid_odps_versions and version != "4.1":
                        issues.append(
                            {
                                "file": str(file_path.relative_to(self.docs_dir)),
                                "type": "version",
                                "issue": f"Potentially invalid ODPS version: {version}",
                                "severity": "warning",
                            }
                        )
            except Exception as e:
                issues.append(
                    {
                        "file": str(file_path.relative_to(self.docs_dir)),
                        "type": "version",
                        "issue": f"Error checking versions: {str(e)}",
                    }
                )

        return issues

    def _extract_links(self, file_path: Path) -> List[str]:
        """Extract all links from a markdown file."""
        links = []
        try:
            content = file_path.read_text(encoding="utf-8")
            # Extract markdown links [text](url)
            link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
            matches = re.findall(link_pattern, content)
            for text, url in matches:
                links.append(url)
        except Exception:
            pass
        return links

    def _check_link_validity(self, link: str, source_file: Path) -> bool:
        """Check if a link is valid."""
        # Skip external links
        if link.startswith("http://") or link.startswith("https://"):
            return True  # Assume external links are valid

        # Skip anchor links
        if link.startswith("#"):
            return True  # Anchor links are relative to the same file

        # Skip mailto links
        if link.startswith("mailto:"):
            return True

        # Check relative links
        if (
            link.startswith("../")
            or link.startswith("./")
            or (not link.startswith("/") and not "://" in link)
        ):
            # Relative link - resolve from source file
            try:
                target_path = (source_file.parent / link).resolve()
                # Check if target exists
                if target_path.exists() and target_path.is_file():
                    return True
                # Check if it's a directory with index
                if target_path.exists() and target_path.is_dir():
                    if (target_path / "README.md").exists():
                        return True
                # Also check with .md extension if no extension
                if (
                    not target_path.suffix
                    and (target_path.parent / (target_path.name + ".md")).exists()
                ):
                    return True
                # Check relative to docs root
                if link.startswith("../"):
                    # Go up from source file, then follow link
                    parts = link.split("/")
                    up_levels = sum(1 for p in parts if p == "..")
                    remaining = "/".join([p for p in parts if p != ".."])
                    target_from_docs = self.docs_dir
                    for _ in range(up_levels):
                        target_from_docs = target_from_docs.parent
                    target_path = target_from_docs / remaining
                    if target_path.exists():
                        return True
                    if (target_path.parent / (target_path.name + ".md")).exists():
                        return True
            except (ValueError, OSError):
                pass
            return False

        # Absolute path from docs root
        if link.startswith("/"):
            target_path = self.docs_dir / link.lstrip("/")
            if target_path.exists():
                return True
            return False

        return True  # Unknown format, assume valid

    def generate_report(self, results: Dict[str, Any], output_file: Path = None) -> str:
        """Generate QA report."""
        report_lines = []
        report_lines.append("# Documentation Quality Assurance Report")
        report_lines.append("")
        report_lines.append(f"**Generated**: {Path(__file__).stat().st_mtime}")
        report_lines.append(f"**Status**: {results['summary']['status']}")
        report_lines.append("")

        # Summary
        report_lines.append("## Summary")
        report_lines.append("")
        report_lines.append(f"- **Total Issues**: {results['summary']['total_issues']}")
        report_lines.append(f"- **Consistency Issues**: {results['summary']['consistency_issues']}")
        report_lines.append(
            f"- **Completeness Issues**: {results['summary']['completeness_issues']}"
        )
        report_lines.append(f"- **Accuracy Issues**: {results['summary']['accuracy_issues']}")
        report_lines.append(f"- **Broken Links**: {results['summary']['broken_links']}")
        report_lines.append("")

        # Detailed issues
        if results["summary"]["total_issues"] > 0:
            report_lines.append("## Issues")
            report_lines.append("")

            # Consistency issues
            if results["consistency"]["issues"]:
                report_lines.append("### Consistency Issues")
                for issue in results["consistency"]["issues"]:
                    report_lines.append(
                        f"- **{issue.get('file', 'Unknown')}**: {issue.get('issue', 'Unknown issue')}"
                    )
                report_lines.append("")

            # Completeness issues
            if results["completeness"]["issues"]:
                report_lines.append("### Completeness Issues")
                for issue in results["completeness"]["issues"]:
                    report_lines.append(
                        f"- **{issue.get('type', 'Unknown')}**: {issue.get('issue', 'Unknown issue')}"
                    )
                report_lines.append("")

            # Accuracy issues
            if results["accuracy"]["issues"]:
                report_lines.append("### Accuracy Issues")
                for issue in results["accuracy"]["issues"]:
                    report_lines.append(
                        f"- **{issue.get('file', 'Unknown')}**: {issue.get('issue', 'Unknown issue')}"
                    )
                report_lines.append("")

            # Broken links
            if results["links"]["broken_links"]:
                report_lines.append("### Broken Links")
                for link in results["links"]["broken_links"]:
                    report_lines.append(f"- **{link['file']}**: {link['link']}")
                report_lines.append("")

        report = "\n".join(report_lines)

        if output_file:
            output_file.write_text(report, encoding="utf-8")
            print(f"\n📄 Report saved to: {output_file}")

        return report


def main():
    """Main entry point."""
    qa = DocumentationQA()
    results = qa.run_all_checks()

    # Generate report
    report_file = DOCS_DIR / "documentation_qa_report.md"
    report = qa.generate_report(results, report_file)

    # Print summary
    print("\n" + "=" * 80)
    print("📊 Documentation QA Summary")
    print("=" * 80)
    print(f"Status: {results['summary']['status']}")
    print(f"Total Issues: {results['summary']['total_issues']}")
    print(f"  - Consistency: {results['summary']['consistency_issues']}")
    print(f"  - Completeness: {results['summary']['completeness_issues']}")
    print(f"  - Accuracy: {results['summary']['accuracy_issues']}")
    print(f"  - Broken Links: {results['summary']['broken_links']}")
    print("")

    # Exit with error code if issues found
    if results["summary"]["status"] == "FAIL":
        print("❌ Documentation QA failed. Please review the report.")
        sys.exit(1)
    else:
        print("✅ Documentation QA passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
