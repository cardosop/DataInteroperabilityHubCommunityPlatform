#!/usr/bin/env python
"""
Generate Consumer Impact Analysis Report

This script compiles all consumer references from previous analysis tasks and generates
a comprehensive impact matrix showing which endpoints are consumed by which consumers.

Dependencies:
- reverse_lookup_analysis.json (from task 9.6.1.2.2)
- api-client-usage-report.json (from task 9.6.1.2.3)
- webhook-payloads-and-events-report.json (from task 9.6.1.2.5)
- endpoint-inventory-current.json (from task 9.6.1.1)
- hardcoded-endpoints-impact-matrix.json (from task 9.6.1.2.1)
- openapi-spec-discrepancies.json (from task 9.6.1.2.4)

Usage:
    python scripts/generate_consumer_impact_report.py
"""

import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


class ConsumerImpactAnalyzer:
    """Analyzer for consumer impact analysis"""

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.consumers: dict[str, list[dict]] = defaultdict(list)
        self.endpoint_consumers: dict[str, set[str]] = defaultdict(set)
        self.consumer_types: dict[str, str] = {}
        self.impact_matrix: dict[str, dict[str, Any]] = {}

    def load_analysis_data(self) -> dict[str, Any]:
        """Load all analysis data from previous tasks"""
        data = {}

        # Load reverse lookup analysis
        reverse_lookup_file = self.base_path / "reverse_lookup_analysis.json"
        if reverse_lookup_file.exists():
            try:
                with open(reverse_lookup_file) as f:
                    data["reverse_lookups"] = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load reverse lookup analysis: {e}", file=sys.stderr)

        # Load API client usage report
        api_client_file = self.base_path / "docs" / "api-audit" / "api-client-usage-report.json"
        if api_client_file.exists():
            try:
                with open(api_client_file) as f:
                    data["api_client_usage"] = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load API client usage report: {e}", file=sys.stderr)

        # Load webhook payloads and events report
        webhook_file = (
            self.base_path / "docs" / "api-audit" / "webhook-payloads-and-events-report.json"
        )
        if webhook_file.exists():
            try:
                with open(webhook_file) as f:
                    data["webhook_payloads"] = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load webhook payloads report: {e}", file=sys.stderr)

        # Load endpoint inventory
        endpoint_file = self.base_path / "docs" / "api-audit" / "endpoint-inventory-current.json"
        if endpoint_file.exists():
            try:
                with open(endpoint_file) as f:
                    data["endpoint_inventory"] = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load endpoint inventory: {e}", file=sys.stderr)

        # Load hardcoded endpoints impact matrix
        hardcoded_file = (
            self.base_path / "docs" / "api-audit" / "hardcoded-endpoints-impact-matrix.json"
        )
        if hardcoded_file.exists():
            try:
                with open(hardcoded_file) as f:
                    data["hardcoded_endpoints"] = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load hardcoded endpoints matrix: {e}", file=sys.stderr)

        # Load OpenAPI spec discrepancies
        openapi_file = self.base_path / "docs" / "api-audit" / "openapi-spec-discrepancies.json"
        if openapi_file.exists():
            try:
                with open(openapi_file) as f:
                    data["openapi_discrepancies"] = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load OpenAPI discrepancies: {e}", file=sys.stderr)

        return data

    def normalize_endpoint(self, endpoint: str) -> str | None:
        """Normalize endpoint path for consistent matching"""
        if not endpoint:
            return None

        # Skip invalid endpoints
        if endpoint in ["localhost:8000/api/v1", "api.example.com/api/v1", "/api/v1", "/api/v1/"]:
            return None

        # Skip endpoints that are just base URLs without paths
        if endpoint in [
            "localhost:8000",
            "api.example.com",
            "http://localhost:8000",
            "https://api.example.com",
        ]:
            return None

        # Remove http:// or https:// prefixes
        endpoint = re.sub(r"^https?://", "", endpoint)

        # Skip regex patterns that aren't valid endpoints
        if endpoint.startswith("^") or endpoint.startswith("(?P<") or "regex" in endpoint.lower():
            # Try to extract the base path from regex
            # Pattern: ^api/v1/path/(?P<id>...)
            match = re.match(r"[\^/]*api/v1/([^\(]+)", endpoint)
            if match:
                base_path = match.group(1).rstrip("/")
                endpoint = f"/api/v1/{base_path}/{{id}}/"
            else:
                return None

        # Skip endpoints with invalid characters or patterns
        if any(
            pattern in endpoint for pattern in ["[^", "]*", "webhook[^", "http://localhost:8000"]
        ):
            return None

        # Remove leading/trailing slashes for processing
        endpoint = endpoint.strip("/")

        # Remove query strings and fragments
        if "?" in endpoint:
            endpoint = endpoint.split("?")[0]
        if "#" in endpoint:
            endpoint = endpoint.split("#")[0]

        # If already starts with /api/v1/, return as-is
        if endpoint.startswith("api/v1/"):
            return f"/{endpoint}"

        # If starts with /api/, check if it's /api/v1/
        if endpoint.startswith("api/"):
            # Check if it's already /api/v1/
            if endpoint.startswith("api/v1/"):
                return f"/{endpoint}"
            else:
                # It's /api/ but not /api/v1/, add v1
                return f"/api/v1/{endpoint[4:]}"

        # If starts with /, add /api/v1
        if endpoint.startswith("/"):
            return f"/api/v1{endpoint}"

        # Otherwise, add /api/v1/
        return f"/api/v1/{endpoint}"

    def extract_endpoint_from_url_name(self, url_name: str) -> str | None:
        """Extract endpoint path from Django URL name"""
        # Map common URL name patterns to endpoints
        # This is a simplified mapping - in practice, you'd need to resolve via Django's URL resolver
        if url_name.endswith("-list"):
            resource = url_name.replace("-list", "").replace("-", "/")
            return f"/api/v1/{resource}/"
        elif url_name.endswith("-detail"):
            resource = url_name.replace("-detail", "").replace("-", "/")
            return f"/api/v1/{resource}/{{id}}/"
        elif "-" in url_name:
            parts = url_name.split("-")
            if len(parts) >= 2:
                resource = "/".join(parts[:-1])
                action = parts[-1]
                return f"/api/v1/{resource}/{action}/"
        return None

    def compile_consumer_references(self, data: dict[str, Any]) -> None:
        """Compile all consumer references from analysis data"""

        # 1. Process reverse lookups
        if "reverse_lookups" in data:
            reverse_data = data["reverse_lookups"]
            for reverse_call in reverse_data.get("reverse_calls", []):
                url_name = reverse_call.get("url_name")
                file_path = reverse_call.get("file")
                line = reverse_call.get("line")

                endpoint = self.extract_endpoint_from_url_name(url_name)
                if endpoint:
                    endpoint = self.normalize_endpoint(endpoint)
                    if not endpoint:  # Skip invalid endpoints
                        continue
                    consumer_id = f"reverse_lookup:{file_path}:{line}"
                    self.consumers[consumer_id].append(
                        {
                            "type": "reverse_lookup",
                            "url_name": url_name,
                            "endpoint": endpoint,
                            "file": file_path,
                            "line": line,
                            "code": reverse_call.get("code", ""),
                        }
                    )
                    self.endpoint_consumers[endpoint].add(consumer_id)
                    self.consumer_types[consumer_id] = "reverse_lookup"

        # 2. Process API client usage
        if "api_client_usage" in data:
            api_client_data = data["api_client_usage"]
            for api_call in api_client_data.get("api_calls", []):
                endpoint = api_call.get("endpoint")
                if endpoint:
                    endpoint = self.normalize_endpoint(endpoint)
                    if not endpoint:  # Skip invalid endpoints
                        continue
                    file_path = api_call.get("file_path")
                    line = api_call.get("line_number")
                    method = api_call.get("method", "GET")

                    consumer_id = f"api_client:{file_path}:{line}"
                    self.consumers[consumer_id].append(
                        {
                            "type": "api_client",
                            "endpoint": endpoint,
                            "method": method,
                            "file": file_path,
                            "line": line,
                            "client_type": api_call.get("client_type", "unknown"),
                            "context": api_call.get("context", ""),
                        }
                    )
                    self.endpoint_consumers[endpoint].add(consumer_id)
                    self.consumer_types[consumer_id] = "api_client"

        # 3. Process SDK client usage (from client_usages array)
        if "api_client_usage" in data:
            api_client_data = data["api_client_usage"]
            # SDK usage is in client_usages array - these are SDK API methods
            for client_usage in api_client_data.get("client_usages", []):
                endpoint = client_usage.get("endpoint")
                if endpoint:
                    endpoint = self.normalize_endpoint(endpoint)
                    file_path = client_usage.get("file_path")
                    line = client_usage.get("line_number")
                    client_class = client_usage.get("client_class", "unknown")
                    method_name = client_usage.get("method_name", "unknown")

                    # Check if this is an SDK client (in sdk/python directory)
                    is_sdk = "sdk/python" in file_path or "sdk/" in file_path

                    if is_sdk and endpoint:
                        normalized_endpoint = self.normalize_endpoint(endpoint)
                        if normalized_endpoint:  # Only add if endpoint is valid
                            endpoint = normalized_endpoint
                            consumer_id = f"sdk:{file_path}:{line}"
                            self.consumers[consumer_id].append(
                                {
                                    "type": "sdk",
                                    "endpoint": endpoint,
                                    "file": file_path,
                                    "line": line,
                                    "sdk_module": client_class,
                                    "sdk_method": method_name,
                                }
                            )
                            self.endpoint_consumers[endpoint].add(consumer_id)
                            self.consumer_types[consumer_id] = "sdk"

        # 4. Process webhook endpoint references
        if "webhook_payloads" in data:
            webhook_data = data["webhook_payloads"]
            for endpoint_ref in webhook_data.get("endpoint_references", []):
                endpoint = endpoint_ref.get("endpoint")
                if endpoint:
                    endpoint = self.normalize_endpoint(endpoint)
                    if not endpoint:  # Skip invalid endpoints
                        continue
                    file_path = endpoint_ref.get("file_path")
                    line = endpoint_ref.get("line_number")
                    event_type = endpoint_ref.get("event_type", "")

                    consumer_id = f"webhook:{file_path}:{line}"
                    self.consumers[consumer_id].append(
                        {
                            "type": "webhook",
                            "endpoint": endpoint,
                            "file": file_path,
                            "line": line,
                            "event_type": event_type,
                            "context": endpoint_ref.get("context", ""),
                        }
                    )
                    self.endpoint_consumers[endpoint].add(consumer_id)
                    self.consumer_types[consumer_id] = "webhook"

        # 5. Process hardcoded endpoints
        if "hardcoded_endpoints" in data:
            hardcoded_data = data["hardcoded_endpoints"]

            # Handle different structures
            endpoints_list = []
            if "endpoints" in hardcoded_data:
                endpoints_list = hardcoded_data["endpoints"]
            elif "all_references" in hardcoded_data:
                # Use all_references array
                endpoints_list = hardcoded_data["all_references"]
            elif "impact_matrix" in hardcoded_data:
                # Use impact_matrix array
                for item in hardcoded_data["impact_matrix"]:
                    if "references" in item:
                        endpoints_list.extend(item["references"])

            for endpoint_info in endpoints_list:
                # Handle different field names
                endpoint_raw = endpoint_info.get("endpoint") or endpoint_info.get("endpoint_url")
                if not endpoint_raw:
                    continue

                endpoint = self.normalize_endpoint(endpoint_raw)
                if not endpoint:  # Skip invalid endpoints
                    continue

                file_path = endpoint_info.get("file_path")
                line = endpoint_info.get("line_number")

                consumer_id = f"hardcoded:{file_path}:{line}"
                self.consumers[consumer_id].append(
                    {
                        "type": "hardcoded",
                        "endpoint": endpoint,
                        "file": file_path,
                        "line": line,
                        "context": endpoint_info.get("context", ""),
                    }
                )
                self.endpoint_consumers[endpoint].add(consumer_id)
                self.consumer_types[consumer_id] = "hardcoded"

    def calculate_impact_score(self, endpoint: str) -> dict[str, Any]:
        """Calculate impact score for an endpoint"""
        consumers = self.endpoint_consumers.get(endpoint, set())

        # Count consumers by type (count actual references, not consumer IDs)
        type_counts = defaultdict(int)
        for consumer_id in consumers:
            consumer_type = self.consumer_types.get(consumer_id, "unknown")
            # Count actual references from this consumer
            if consumer_id in self.consumers:
                reference_count = len(self.consumers[consumer_id])
                type_counts[consumer_type] += reference_count
            else:
                type_counts[consumer_type] += 1

        # Calculate impact score based on:
        # - Number of consumer references (not consumer IDs)
        # - Consumer types (SDK = 2.0, webhook = 1.5, api_client = 1.0, reverse_lookup = 0.5)

        type_weights = {
            "sdk": 2.0,
            "webhook": 1.5,
            "api_client": 1.0,
            "reverse_lookup": 0.5,
            "hardcoded": 1.0,
        }

        total_score = 0.0
        for consumer_type, count in type_counts.items():
            weight = type_weights.get(consumer_type, 1.0)
            total_score += count * weight

        # Determine priority
        if total_score >= 50:
            priority = "CRITICAL"
        elif total_score >= 20:
            priority = "HIGH"
        elif total_score >= 10:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        # Count total consumer references (not consumer IDs)
        total_references = sum(type_counts.values())

        return {
            "total_consumers": total_references,  # Total references, not unique consumer IDs
            "type_counts": dict(type_counts),
            "impact_score": total_score,
            "priority": priority,
        }

    def generate_impact_matrix(self) -> None:
        """Generate impact matrix for all endpoints"""
        for endpoint in self.endpoint_consumers.keys():
            impact = self.calculate_impact_score(endpoint)
            consumers = list(self.endpoint_consumers[endpoint])

            self.impact_matrix[endpoint] = {
                "endpoint": endpoint,
                "impact_score": impact["impact_score"],
                "priority": impact["priority"],
                "total_consumers": impact["total_consumers"],
                "consumer_types": impact["type_counts"],
                "consumers": consumers,
            }

    def categorize_by_priority_and_type(self) -> dict[str, dict[str, list[dict]]]:
        """Categorize endpoints by priority and consumer type"""
        categories: dict[str, dict[str, list[dict]]] = {
            "CRITICAL": {},
            "HIGH": {},
            "MEDIUM": {},
            "LOW": {},
        }

        for _endpoint, info in self.impact_matrix.items():
            priority = info["priority"]
            consumer_types = info["consumer_types"]

            # Categorize by primary consumer type
            if consumer_types:
                primary_type = max(consumer_types.items(), key=lambda x: x[1])[0]
            else:
                primary_type = "unknown"

            if primary_type not in categories[priority]:
                categories[priority][primary_type] = []
            categories[priority][primary_type].append(info)

        return categories

    def generate_markdown_report(self) -> str:
        """Generate markdown report"""
        report = []
        report.append("# Consumer Impact Analysis Report")
        report.append("")
        report.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("**Task**: 9.6.1.2.6 - Generate consumer impact report")
        report.append("")
        report.append("---")
        report.append("")
        report.append("## Overview")
        report.append("")
        report.append(
            "This report analyzes all API consumer references across the codebase to identify"
        )
        report.append("which endpoints are consumed by which consumers and assess the impact of")
        report.append("potential API changes.")
        report.append("")

        # Summary statistics
        total_endpoints = len(self.impact_matrix)
        total_consumers = sum(len(consumers) for consumers in self.endpoint_consumers.values())

        priority_counts = defaultdict(int)
        for endpoint, info in self.impact_matrix.items():
            priority_counts[info["priority"]] += 1

        report.append("## Summary Statistics")
        report.append("")
        report.append("| Metric | Count |")
        report.append("|--------|-------|")
        report.append(f"| **Total Endpoints Analyzed** | **{total_endpoints}** |")
        report.append(f"| **Total Consumer References** | **{total_consumers}** |")
        report.append(f"| **CRITICAL Priority Endpoints** | **{priority_counts['CRITICAL']}** |")
        report.append(f"| **HIGH Priority Endpoints** | **{priority_counts['HIGH']}** |")
        report.append(f"| **MEDIUM Priority Endpoints** | **{priority_counts['MEDIUM']}** |")
        report.append(f"| **LOW Priority Endpoints** | **{priority_counts['LOW']}** |")
        report.append("")

        # Consumer type breakdown
        type_totals = defaultdict(int)
        for consumers in self.endpoint_consumers.values():
            for consumer_id in consumers:
                consumer_type = self.consumer_types.get(consumer_id, "unknown")
                type_totals[consumer_type] += 1

        report.append("## Consumer Type Breakdown")
        report.append("")
        report.append("| Consumer Type | Count | Description |")
        report.append("|---------------|-------|-------------|")
        report.append(f"| **SDK** | **{type_totals['sdk']}** | SDK method calls |")
        report.append(
            f"| **Webhook** | **{type_totals['webhook']}** | Webhook endpoint references |"
        )
        report.append(
            f"| **API Client** | **{type_totals['api_client']}** | Direct API client calls |"
        )
        report.append(
            f"| **Reverse Lookup** | **{type_totals['reverse_lookup']}** | Django reverse() calls |"
        )
        report.append(
            f"| **Hardcoded** | **{type_totals['hardcoded']}** | Hardcoded endpoint strings |"
        )
        report.append("")

        # Impact matrix by priority
        categories = self.categorize_by_priority_and_type()

        for priority in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            report.append(f"## {priority} Priority Endpoints")
            report.append("")

            priority_endpoints = categories[priority]
            if not priority_endpoints:
                report.append(f"No {priority} priority endpoints found.")
                report.append("")
                continue

            # Sort endpoints by impact score
            all_endpoints = []
            for endpoints in priority_endpoints.values():
                all_endpoints.extend(endpoints)
            all_endpoints.sort(key=lambda x: x["impact_score"], reverse=True)

            report.append(f"### Top {min(20, len(all_endpoints))} Endpoints by Impact Score")
            report.append("")
            report.append("| Endpoint | Impact Score | Consumers | Consumer Types |")
            report.append("|----------|--------------|-----------|----------------|")

            for endpoint_info in all_endpoints[:20]:
                endpoint = endpoint_info["endpoint"]
                score = endpoint_info["impact_score"]
                consumers = endpoint_info["total_consumers"]
                types_str = ", ".join(
                    [f"{k}:{v}" for k, v in endpoint_info["consumer_types"].items()]
                )

                report.append(f"| `{endpoint}` | {score:.1f} | {consumers} | {types_str} |")

            report.append("")

            # Breakdown by consumer type
            report.append("### Breakdown by Consumer Type")
            report.append("")
            for consumer_type, endpoints in sorted(priority_endpoints.items()):
                if endpoints:
                    report.append(f"#### {consumer_type.upper()} ({len(endpoints)} endpoints)")
                    report.append("")
                    report.append("| Endpoint | Impact Score | Consumers |")
                    report.append("|----------|--------------|-----------|")

                    for endpoint_info in sorted(
                        endpoints, key=lambda x: x["impact_score"], reverse=True
                    )[:10]:
                        endpoint = endpoint_info["endpoint"]
                        score = endpoint_info["impact_score"]
                        consumers = endpoint_info["total_consumers"]
                        report.append(f"| `{endpoint}` | {score:.1f} | {consumers} |")

                    report.append("")

        # Detailed consumer references
        report.append("## Detailed Consumer References")
        report.append("")
        report.append("### By Endpoint")
        report.append("")

        # Sort endpoints by impact score
        sorted_endpoints = sorted(
            self.impact_matrix.items(), key=lambda x: x[1]["impact_score"], reverse=True
        )

        for endpoint, info in sorted_endpoints[:50]:  # Top 50 endpoints
            report.append(f"#### `{endpoint}`")
            report.append("")
            report.append(f"- **Impact Score**: {info['impact_score']:.1f}")
            report.append(f"- **Priority**: {info['priority']}")
            report.append(f"- **Total Consumers**: {info['total_consumers']}")
            report.append(
                f"- **Consumer Types**: {', '.join([f'{k}:{v}' for k, v in info['consumer_types'].items()])}"
            )
            report.append("")
            report.append("**Consumers:**")
            report.append("")

            # Group consumers by type
            consumers_by_type = defaultdict(list)
            for consumer_id in info["consumers"]:
                consumer_type = self.consumer_types.get(consumer_id, "unknown")
                consumers_by_type[consumer_type].extend(self.consumers[consumer_id])

            for consumer_type, consumer_refs in consumers_by_type.items():
                report.append(f"- **{consumer_type.upper()}** ({len(consumer_refs)} references):")
                for ref in consumer_refs[:5]:  # Show first 5 references
                    file_path = ref.get("file", "unknown")
                    line = ref.get("line", "unknown")
                    report.append(f"  - `{file_path}:{line}`")
                if len(consumer_refs) > 5:
                    report.append(f"  - ... and {len(consumer_refs) - 5} more")

            report.append("")

        # Methodology
        report.append("## Methodology")
        report.append("")
        report.append("### Impact Score Calculation")
        report.append("")
        report.append("The impact score is calculated based on:")
        report.append("")
        report.append("1. **Number of consumers**: Each consumer adds to the base score")
        report.append("2. **Consumer type weights**:")
        report.append("   - SDK: 2.0x (external API consumers)")
        report.append("   - Webhook: 1.5x (event-driven integrations)")
        report.append("   - API Client: 1.0x (internal service calls)")
        report.append("   - Reverse Lookup: 0.5x (internal URL references)")
        report.append("   - Hardcoded: 1.0x (direct endpoint strings)")
        report.append("")
        report.append("### Priority Classification")
        report.append("")
        report.append("- **CRITICAL**: Impact score >= 50")
        report.append("- **HIGH**: Impact score >= 20")
        report.append("- **MEDIUM**: Impact score >= 10")
        report.append("- **LOW**: Impact score < 10")
        report.append("")

        # Data Sources
        report.append("## Data Sources")
        report.append("")
        report.append("This report is compiled from the following analysis tasks:")
        report.append("")
        report.append("1. **Task 9.6.1.2.2**: URL reverse lookups (`reverse_lookup_analysis.json`)")
        report.append("2. **Task 9.6.1.2.3**: API client usage (`api-client-usage-report.json`)")
        report.append(
            "3. **Task 9.6.1.2.5**: Webhook payloads and events (`webhook-payloads-and-events-report.json`)"
        )
        report.append(
            "4. **Task 9.6.1.2.1**: Hardcoded endpoints (`hardcoded-endpoints-impact-matrix.json`)"
        )
        report.append("")

        return "\n".join(report)

    def run(self) -> dict[str, Any]:
        """Run complete analysis"""
        print("Loading analysis data...")
        data = self.load_analysis_data()

        print("Compiling consumer references...")
        self.compile_consumer_references(data)

        print("Generating impact matrix...")
        self.generate_impact_matrix()

        print("Generating markdown report...")
        report = self.generate_markdown_report()

        return {
            "summary": {
                "total_endpoints": len(self.impact_matrix),
                "total_consumers": sum(
                    len(consumers) for consumers in self.endpoint_consumers.values()
                ),
                "priority_counts": {
                    priority: sum(
                        1 for info in self.impact_matrix.values() if info["priority"] == priority
                    )
                    for priority in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
                },
            },
            "impact_matrix": self.impact_matrix,
            "consumers": dict(self.consumers),
            "endpoint_consumers": {k: list(v) for k, v in self.endpoint_consumers.items()},
            "report": report,
        }


def main():
    """Main entry point"""
    analyzer = ConsumerImpactAnalyzer(base_path=".")
    result = analyzer.run()

    # Save markdown report
    output_dir = Path("docs/api-audit")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "consumer-impact-analysis.md"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(result["report"])

    print(f"\nReport saved to {output_file}")

    # Save JSON data
    json_file = output_dir / "consumer-impact-analysis.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"Data saved to {json_file}")

    # Print summary
    summary = result["summary"]
    print("\nSummary:")
    print(f"  Total endpoints: {summary['total_endpoints']}")
    print(f"  Total consumers: {summary['total_consumers']}")
    print(f"  CRITICAL: {summary['priority_counts']['CRITICAL']}")
    print(f"  HIGH: {summary['priority_counts']['HIGH']}")
    print(f"  MEDIUM: {summary['priority_counts']['MEDIUM']}")
    print(f"  LOW: {summary['priority_counts']['LOW']}")


if __name__ == "__main__":
    main()
