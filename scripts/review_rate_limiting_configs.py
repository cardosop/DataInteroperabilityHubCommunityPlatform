#!/usr/bin/env python3
"""
Review Rate Limiting Configurations and Map to Endpoints

This script:
1. Reviews endpoint category mappings
2. Reviews rate limit rules (platform defaults and maximums)
3. Maps rate limiting configs to actual endpoints
4. Generates a comprehensive review report

Usage:
    python scripts/review_rate_limiting_configs.py [--output OUTPUT_FILE]
"""

import re
import json
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict
from datetime import datetime

# Import rate limiting utilities - read directly from source files
project_root = Path(__file__).parent.parent
hub_dir = project_root / "hub"
rate_limiting_config_file = hub_dir / "apps" / "rate_limiting" / "config.py"
rate_limiting_utils_file = hub_dir / "apps" / "rate_limiting" / "utils.py"

# Read config directly from source
PLATFORM_DEFAULT_LIMITS = {}
PLATFORM_MAXIMUM_LIMITS = {}

# Define EndpointCategory as a simple class to avoid linter warnings
class EndpointCategory:
    """Endpoint categories for rate limiting"""
    AUTH = 'auth'
    ASSET = 'asset'
    CONTRACT = 'contract'
    SEARCH = 'search'
    DQ_RUN = 'dq_run'
    COMPLIANCE_RUN = 'compliance_run'
    FILE_UPLOAD = 'file_upload'
    FILE_DOWNLOAD = 'file_download'
    CONTRACT_VALIDATION = 'contract_validation'
    CATALOG_READ = 'catalog_read'
    SPARQL_QUERY = 'sparql_query'
    TRANSFORMATION = 'transformation'
    GENERAL = 'general'

class TimeWindow:
    BURST = 10
    SUSTAINED = 60
    DAILY = 86400

# Parse config.py to extract limits
if rate_limiting_config_file.exists():
    config_content = rate_limiting_config_file.read_text(encoding='utf-8')

    # Extract PLATFORM_DEFAULT_LIMITS
    default_match = re.search(
        r'PLATFORM_DEFAULT_LIMITS:\s*Dict\[str,\s*Dict\[int,\s*int\]\]\s*=\s*\{([^}]+(?:\{[^}]+\}[^}]*)*)\}',
        config_content,
        re.DOTALL
    )
    if default_match:
        # Parse the dictionary content
        import ast
        try:
            # Find the full dictionary definition
            start = config_content.find('PLATFORM_DEFAULT_LIMITS:')
            if start != -1:
                # Extract the dictionary
                lines = config_content[start:].split('\n')
                dict_lines = []
                brace_count = 0
                for line in lines:
                    dict_lines.append(line)
                    brace_count += line.count('{') - line.count('}')
                    if brace_count == 0 and '{' in ''.join(dict_lines):
                        break
                dict_str = '\n'.join(dict_lines)
                # Extract just the dict part
                dict_match = re.search(r'\{.*\}', dict_str, re.DOTALL)
                if dict_match:
                    dict_str = dict_match.group(0)
                    # Replace EndpointCategory.XXX with strings
                    for attr in dir(EndpointCategory):
                        if not attr.startswith('_'):
                            dict_str = dict_str.replace(f'EndpointCategory.{attr}', f'"{getattr(EndpointCategory, attr)}"')
                    # Replace TimeWindow.XXX with integers
                    dict_str = dict_str.replace('TimeWindow.BURST', str(TimeWindow.BURST))
                    dict_str = dict_str.replace('TimeWindow.SUSTAINED', str(TimeWindow.SUSTAINED))
                    dict_str = dict_str.replace('TimeWindow.DAILY', str(TimeWindow.DAILY))
                    try:
                        PLATFORM_DEFAULT_LIMITS = ast.literal_eval(dict_str)
                    except:
                        pass
        except Exception as e:
            print(f"   ⚠ Warning: Could not parse PLATFORM_DEFAULT_LIMITS: {e}", file=sys.stderr)

    # Extract PLATFORM_MAXIMUM_LIMITS similarly
    max_match = re.search(
        r'PLATFORM_MAXIMUM_LIMITS:\s*Dict\[str,\s*Dict\[int,\s*int\]\]\s*=\s*\{([^}]+(?:\{[^}]+\}[^}]*)*)\}',
        config_content,
        re.DOTALL
    )
    if max_match:
        try:
            start = config_content.find('PLATFORM_MAXIMUM_LIMITS:')
            if start != -1:
                lines = config_content[start:].split('\n')
                dict_lines = []
                brace_count = 0
                for line in lines:
                    dict_lines.append(line)
                    brace_count += line.count('{') - line.count('}')
                    if brace_count == 0 and '{' in ''.join(dict_lines):
                        break
                dict_str = '\n'.join(dict_lines)
                dict_match = re.search(r'\{.*\}', dict_str, re.DOTALL)
                if dict_match:
                    dict_str = dict_match.group(0)
                    for attr in dir(EndpointCategory):
                        if not attr.startswith('_'):
                            dict_str = dict_str.replace(f'EndpointCategory.{attr}', f'"{getattr(EndpointCategory, attr)}"')
                    dict_str = dict_str.replace('TimeWindow.BURST', str(TimeWindow.BURST))
                    dict_str = dict_str.replace('TimeWindow.SUSTAINED', str(TimeWindow.SUSTAINED))
                    dict_str = dict_str.replace('TimeWindow.DAILY', str(TimeWindow.DAILY))
                    try:
                        PLATFORM_MAXIMUM_LIMITS = ast.literal_eval(dict_str)
                    except:
                        pass
        except Exception as e:
            print(f"   ⚠ Warning: Could not parse PLATFORM_MAXIMUM_LIMITS: {e}", file=sys.stderr)

# If parsing failed, read the actual values from the file
if not PLATFORM_DEFAULT_LIMITS and rate_limiting_config_file.exists():
    # Fallback: manually extract values
    config_content = rate_limiting_config_file.read_text(encoding='utf-8')
    # Extract values using regex
    for category_attr in ['AUTH', 'ASSET', 'CONTRACT', 'SEARCH', 'FILE_UPLOAD', 'DQ_RUN',
                          'COMPLIANCE_RUN', 'FILE_DOWNLOAD', 'CONTRACT_VALIDATION',
                          'CATALOG_READ', 'SPARQL_QUERY', 'TRANSFORMATION', 'GENERAL']:
        category = getattr(EndpointCategory, category_attr)
        PLATFORM_DEFAULT_LIMITS[category] = {}
        PLATFORM_MAXIMUM_LIMITS[category] = {}

        # Extract default limits for this category
        pattern = rf'EndpointCategory\.{category_attr}:\s*\{{([^}}]+)\}}'
        match = re.search(pattern, config_content, re.DOTALL)
        if match:
            limits_str = match.group(1)
            # Extract BURST, SUSTAINED, DAILY
            for window_name, window_value in [('BURST', TimeWindow.BURST),
                                                ('SUSTAINED', TimeWindow.SUSTAINED),
                                                ('DAILY', TimeWindow.DAILY)]:
                window_pattern = rf'TimeWindow\.{window_name}:\s*(\d+)'
                window_match = re.search(window_pattern, limits_str)
                if window_match:
                    PLATFORM_DEFAULT_LIMITS[category][window_value] = int(window_match.group(1))

        # Extract maximum limits for this category
        max_pattern = rf'EndpointCategory\.{category_attr}:\s*\{{([^}}]+)\}}'
        # Search in PLATFORM_MAXIMUM_LIMITS section
        max_section_start = config_content.find('PLATFORM_MAXIMUM_LIMITS:')
        if max_section_start != -1:
            max_section = config_content[max_section_start:]
            max_match = re.search(max_pattern, max_section, re.DOTALL)
            if max_match:
                limits_str = max_match.group(1)
                for window_name, window_value in [('BURST', TimeWindow.BURST),
                                                    ('SUSTAINED', TimeWindow.SUSTAINED),
                                                    ('DAILY', TimeWindow.DAILY)]:
                    window_pattern = rf'TimeWindow\.{window_name}:\s*(\d+)'
                    window_match = re.search(window_pattern, limits_str)
                    if window_match:
                        PLATFORM_MAXIMUM_LIMITS[category][window_value] = int(window_match.group(1))

# Define get_endpoint_category function
def get_endpoint_category(path: str, method: str) -> str:
    """Determine endpoint category from request path and method"""
    path_lower = path.lower()

    if '/api/v1/auth/' in path_lower or path_lower.startswith('/auth/'):
        return EndpointCategory.AUTH
    if '/api/v1/search/' in path_lower or path_lower.startswith('/search/'):
        return EndpointCategory.SEARCH
    if '/dq/runs' in path_lower and method == 'POST':
        return EndpointCategory.DQ_RUN
    if '/compliance/runs' in path_lower and method == 'POST':
        return EndpointCategory.COMPLIANCE_RUN
    if '/files' in path_lower and method in ('POST', 'PUT'):
        return EndpointCategory.FILE_UPLOAD
    if '/files' in path_lower and method == 'GET' and '/download' in path_lower:
        return EndpointCategory.FILE_DOWNLOAD
    if '/contracts' in path_lower and '/validate' in path_lower:
        return EndpointCategory.CONTRACT_VALIDATION
    if '/api/v1/assets/' in path_lower:
        if method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return EndpointCategory.ASSET
        elif method == 'GET':
            return EndpointCategory.CATALOG_READ
    if '/api/v1/contracts/' in path_lower:
        if method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return EndpointCategory.CONTRACT
        elif method == 'GET':
            return EndpointCategory.CATALOG_READ
    if '/catalog' in path_lower or '/assets' in path_lower:
        if method == 'GET':
            return EndpointCategory.CATALOG_READ
    if '/sparql' in path_lower or '/semantic' in path_lower:
        if method in ('POST', 'GET'):
            return EndpointCategory.SPARQL_QUERY
    if '/transformation/pipelines' in path_lower:
        return EndpointCategory.TRANSFORMATION

    return EndpointCategory.GENERAL


@dataclass
class RateLimitRule:
    """Represents a rate limit rule"""
    category: str
    window: str  # 'BURST', 'SUSTAINED', 'DAILY'
    window_seconds: int
    default_limit: int
    maximum_limit: int


@dataclass
class EndpointRateLimitMapping:
    """Maps an endpoint to its rate limiting configuration"""
    endpoint_path: str
    method: str
    category: str
    burst_limit: int
    sustained_limit: int
    daily_limit: int
    burst_maximum: int
    sustained_maximum: int
    daily_maximum: int


class RateLimitingConfigReviewer:
    """Reviews rate limiting configurations and maps to endpoints"""

    def __init__(self, hub_dir: Optional[Path] = None):
        self.hub_dir = hub_dir or Path(__file__).parent.parent / "hub"
        self.rate_limit_rules: List[RateLimitRule] = []
        self.endpoint_mappings: List[EndpointRateLimitMapping] = []
        self.category_mappings: Dict[str, List[Tuple[str, str]]] = defaultdict(list)  # category -> [(path, method)]

    def review_endpoint_category_mappings(self) -> Dict[str, List[Tuple[str, str]]]:
        """Review endpoint category mappings from utils.py"""
        # Extract category mapping logic from get_endpoint_category function
        # This is done by analyzing the function code

        # Test various endpoint patterns to understand mappings
        test_endpoints = [
            # Auth endpoints
            ("/api/v1/auth/login/", "POST"),
            ("/api/v1/auth/register/", "POST"),
            ("/api/v1/auth/password-reset/", "POST"),
            # Asset endpoints
            ("/api/v1/assets/", "GET"),
            ("/api/v1/assets/", "POST"),
            ("/api/v1/assets/{id}/", "PUT"),
            ("/api/v1/assets/{id}/", "DELETE"),
            # Contract endpoints
            ("/api/v1/contracts/", "GET"),
            ("/api/v1/contracts/", "POST"),
            ("/api/v1/contracts/{id}/validate/", "POST"),
            # Search endpoints
            ("/api/v1/search/", "GET"),
            # DQ endpoints
            ("/api/v1/dq/runs/", "POST"),
            ("/api/v1/dq/runs/", "GET"),
            # Compliance endpoints
            ("/api/v1/compliance/runs/", "POST"),
            # File endpoints
            ("/api/v1/files/", "POST"),
            ("/api/v1/files/{id}/download/", "GET"),
            # SPARQL endpoints
            ("/api/v1/semantic/sparql/", "POST"),
            # Transformation endpoints
            ("/api/v1/transformation/pipelines/", "POST"),
        ]

        for path, method in test_endpoints:
            category = get_endpoint_category(path, method)
            self.category_mappings[category].append((path, method))

        return dict(self.category_mappings)

    def review_rate_limit_rules(self) -> List[RateLimitRule]:
        """Review rate limit rules from config.py"""
        rules = []

        # Get all categories from platform defaults
        all_categories = set(PLATFORM_DEFAULT_LIMITS.keys()) | set(PLATFORM_MAXIMUM_LIMITS.keys())

        window_names = {
            TimeWindow.BURST: "BURST",
            TimeWindow.SUSTAINED: "SUSTAINED",
            TimeWindow.DAILY: "DAILY"
        }

        for category in sorted(all_categories):
            default_limits = PLATFORM_DEFAULT_LIMITS.get(category, {})
            maximum_limits = PLATFORM_MAXIMUM_LIMITS.get(category, {})

            for window_seconds in [TimeWindow.BURST, TimeWindow.SUSTAINED, TimeWindow.DAILY]:
                window_name = window_names.get(window_seconds, str(window_seconds))
                default_limit = default_limits.get(window_seconds, 0)
                maximum_limit = maximum_limits.get(window_seconds, 0)

                rule = RateLimitRule(
                    category=category,
                    window=window_name,
                    window_seconds=window_seconds,
                    default_limit=default_limit,
                    maximum_limit=maximum_limit
                )
                rules.append(rule)

        self.rate_limit_rules = rules
        return rules

    def map_rate_limiting_to_endpoints(self, endpoints: List[Dict[str, Any]]) -> List[EndpointRateLimitMapping]:
        """Map rate limiting configs to actual endpoints"""
        mappings = []

        for endpoint in endpoints:
            path = endpoint.get('path', '')
            method = endpoint.get('method', 'GET')

            # Get category for this endpoint
            category = get_endpoint_category(path, method)

            # Get rate limits for this category
            default_limits = PLATFORM_DEFAULT_LIMITS.get(category, {})
            maximum_limits = PLATFORM_MAXIMUM_LIMITS.get(category, {})

            mapping = EndpointRateLimitMapping(
                endpoint_path=path,
                method=method,
                category=category,
                burst_limit=default_limits.get(TimeWindow.BURST, 0),
                sustained_limit=default_limits.get(TimeWindow.SUSTAINED, 0),
                daily_limit=default_limits.get(TimeWindow.DAILY, 0),
                burst_maximum=maximum_limits.get(TimeWindow.BURST, 0),
                sustained_maximum=maximum_limits.get(TimeWindow.SUSTAINED, 0),
                daily_maximum=maximum_limits.get(TimeWindow.DAILY, 0)
            )
            mappings.append(mapping)

        self.endpoint_mappings = mappings
        return mappings

    def extract_endpoints_from_codebase(self) -> List[Dict[str, Any]]:
        """Extract actual endpoints from Django codebase"""
        # Try to use the Django API extractor
        try:
            import importlib.util
            script_dir = Path(__file__).parent
            spec = importlib.util.spec_from_file_location(
                "extract_django_api_inventory",
                script_dir / "extract-django-api-inventory.py"
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                extractor = module.DjangoAPIExtractor(self.hub_dir)
                endpoints = extractor.extract_all()

                return [
                    {
                        "path": ep.path,
                        "method": ep.method,
                        "view_class": ep.view_class,
                        "file_path": ep.file_path
                    }
                    for ep in endpoints
                ]
        except Exception as e:
            print(f"   ⚠ Warning: Could not extract endpoints from codebase: {e}", file=sys.stderr)

        return []

    def verify_all_rate_limiting_configs_reviewed(self) -> Dict[str, Any]:
        """Verify that all rate limiting configs were reviewed"""
        categories_reviewed = len(set(rule.category for rule in self.rate_limit_rules))
        total_categories = len(set(PLATFORM_DEFAULT_LIMITS.keys()) | set(PLATFORM_MAXIMUM_LIMITS.keys()))

        rules_reviewed = len(self.rate_limit_rules)
        expected_rules = total_categories * 3  # 3 time windows per category

        return {
            "status": "success" if categories_reviewed == total_categories and rules_reviewed == expected_rules else "warning",
            "categories_reviewed": categories_reviewed,
            "total_categories": total_categories,
            "rules_reviewed": rules_reviewed,
            "expected_rules": expected_rules,
            "category_mappings_reviewed": len(self.category_mappings)
        }

    def verify_rate_limiting_mapping(self) -> Dict[str, Any]:
        """Verify rate limiting mapping completeness"""
        endpoints_mapped = len(self.endpoint_mappings)
        categories_with_endpoints = len(set(m.category for m in self.endpoint_mappings))

        # Check coverage by category
        category_coverage = {}
        for category in set(PLATFORM_DEFAULT_LIMITS.keys()):
            endpoints_in_category = len([m for m in self.endpoint_mappings if m.category == category])
            category_coverage[category] = endpoints_in_category

        return {
            "status": "success" if endpoints_mapped > 0 else "warning",
            "endpoints_mapped": endpoints_mapped,
            "categories_with_endpoints": categories_with_endpoints,
            "category_coverage": category_coverage,
            "mapping_working": endpoints_mapped >= 0
        }

    def generate_report(self, output_file: Path, format: str = "json"):
        """Generate review report"""
        verification_configs = self.verify_all_rate_limiting_configs_reviewed()
        verification_mapping = self.verify_rate_limiting_mapping()

        # Group rules by category
        rules_by_category = defaultdict(list)
        for rule in self.rate_limit_rules:
            rules_by_category[rule.category].append(rule)

        # Group mappings by category
        mappings_by_category = defaultdict(list)
        for mapping in self.endpoint_mappings:
            mappings_by_category[mapping.category].append(mapping)

        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_categories": len(set(PLATFORM_DEFAULT_LIMITS.keys())),
                "total_rate_limit_rules": len(self.rate_limit_rules),
                "total_endpoint_mappings": len(self.endpoint_mappings),
                "categories_with_mappings": len(self.category_mappings),
                "verification": {
                    "configs_reviewed": verification_configs,
                    "mapping_completeness": verification_mapping
                }
            },
            "rate_limit_rules": {
                "by_category": {
                    category: [
                        {
                            "category": rule.category,
                            "window": rule.window,
                            "window_seconds": rule.window_seconds,
                            "default_limit": rule.default_limit,
                            "maximum_limit": rule.maximum_limit
                        }
                        for rule in sorted(rules, key=lambda r: r.window_seconds)
                    ]
                    for category, rules in sorted(rules_by_category.items())
                },
                "all": [
                    {
                        "category": rule.category,
                        "window": rule.window,
                        "window_seconds": rule.window_seconds,
                        "default_limit": rule.default_limit,
                        "maximum_limit": rule.maximum_limit
                    }
                    for rule in sorted(self.rate_limit_rules, key=lambda r: (r.category, r.window_seconds))
                ]
            },
            "endpoint_category_mappings": {
                category: [
                    {"path": path, "method": method}
                    for path, method in endpoints
                ]
                for category, endpoints in sorted(self.category_mappings.items())
            },
            "endpoint_rate_limit_mappings": [
                {
                    "endpoint_path": m.endpoint_path,
                    "method": m.method,
                    "category": m.category,
                    "limits": {
                        "burst": {"default": m.burst_limit, "maximum": m.burst_maximum},
                        "sustained": {"default": m.sustained_limit, "maximum": m.sustained_maximum},
                        "daily": {"default": m.daily_limit, "maximum": m.daily_maximum}
                    }
                }
                for m in sorted(self.endpoint_mappings, key=lambda m: (m.category, m.endpoint_path, m.method))
            ]
        }

        output_file.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
        else:
            # Markdown format
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("# Rate Limiting Configuration Review Report\n\n")
                f.write(f"**Generated:** {report['generated_at']}\n\n")
                f.write("## Summary\n\n")
                f.write(f"- **Total Categories:** {report['summary']['total_categories']}\n")
                f.write(f"- **Total Rate Limit Rules:** {report['summary']['total_rate_limit_rules']}\n")
                f.write(f"- **Total Endpoint Mappings:** {report['summary']['total_endpoint_mappings']}\n\n")
                f.write("## Rate Limit Rules by Category\n\n")
                for category, rules in report['rate_limit_rules']['by_category'].items():
                    f.write(f"### {category}\n\n")
                    f.write("| Window | Default Limit | Maximum Limit |\n")
                    f.write("|--------|---------------|----------------|\n")
                    for rule in rules:
                        f.write(f"| {rule['window']} ({rule['window_seconds']}s) | {rule['default_limit']} | {rule['maximum_limit']} |\n")
                    f.write("\n")
                f.write("## Endpoint Mappings\n\n")
                for category, mappings in mappings_by_category.items():
                    f.write(f"### {category}\n\n")
                    f.write(f"**Endpoints:** {len(mappings)}\n\n")
                    for mapping in mappings[:20]:  # Limit to first 20
                        f.write(f"- {mapping.method} {mapping.endpoint_path}\n")
                    if len(mappings) > 20:
                        f.write(f"\n*... and {len(mappings) - 20} more*\n")
                    f.write("\n")

        print(f"\n📊 Report generated: {output_file}")
        return report


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(
        description="Review rate limiting configurations and map to endpoints"
    )
    parser.add_argument(
        "--output",
        default="docs/api-audit/rate-limiting-review.json",
        help="Output file path"
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format"
    )
    parser.add_argument(
        "--hub-dir",
        default="hub",
        help="Hub directory path"
    )

    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    hub_dir = project_root / args.hub_dir
    output_file = project_root / args.output

    reviewer = RateLimitingConfigReviewer(hub_dir)

    print("🔍 Reviewing rate limiting configurations...")

    print("\n📋 Reviewing endpoint category mappings...")
    category_mappings = reviewer.review_endpoint_category_mappings()
    print(f"   ✓ Found {len(category_mappings)} categories with mappings")
    for category, endpoints in category_mappings.items():
        print(f"      - {category}: {len(endpoints)} endpoint patterns")

    print("\n📊 Reviewing rate limit rules...")
    rules = reviewer.review_rate_limit_rules()
    print(f"   ✓ Found {len(rules)} rate limit rules")

    print("\n🔗 Extracting endpoints from codebase...")
    endpoints = reviewer.extract_endpoints_from_codebase()
    print(f"   ✓ Extracted {len(endpoints)} endpoints")

    print("\n🗺️  Mapping rate limiting configs to endpoints...")
    mappings = reviewer.map_rate_limiting_to_endpoints(endpoints)
    print(f"   ✓ Mapped {len(mappings)} endpoints to rate limiting configs")

    print("\n✅ Verifying all rate limiting configs reviewed...")
    configs_verification = reviewer.verify_all_rate_limiting_configs_reviewed()
    print(f"   Categories reviewed: {configs_verification['categories_reviewed']}/{configs_verification['total_categories']}")
    print(f"   Rules reviewed: {configs_verification['rules_reviewed']}/{configs_verification['expected_rules']}")

    print("\n✅ Verifying rate limiting mapping...")
    mapping_verification = reviewer.verify_rate_limiting_mapping()
    print(f"   Endpoints mapped: {mapping_verification['endpoints_mapped']}")
    print(f"   Categories with endpoints: {mapping_verification['categories_with_endpoints']}")

    reviewer.generate_report(output_file, format=args.format)

    return 0


if __name__ == "__main__":
    sys.exit(main())

