#!/usr/bin/env python3
"""
Comprehensive Documentation Endpoint Audit Script

This script audits all documentation files to extract and map endpoint URLs.
It searches:
- docs/API_*.md files
- docs/api-audit/*.md files
- OpenAPI specifications
- API reference documentation
- Developer guides
- Runbooks

Usage:
    python scripts/audit_documentation_endpoints.py [--output OUTPUT_FILE] [--format json|markdown]
"""

import re
import json
import yaml
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field, asdict
from collections import defaultdict
from datetime import datetime
import urllib.parse


@dataclass
class EndpointReference:
    """Represents an endpoint reference found in documentation"""
    endpoint_path: str
    method: Optional[str] = None
    source_file: str = ""
    source_line: int = 0
    context: str = ""
    documentation_type: str = ""  # api_reference, api_audit, openapi, developer_guide, runbook


@dataclass
class DocumentationMapping:
    """Maps an endpoint to its documentation files"""
    endpoint_path: str
    normalized_path: str
    methods: Set[str] = field(default_factory=set)
    documentation_files: List[str] = field(default_factory=list)
    references: List[EndpointReference] = field(default_factory=list)
    total_references: int = 0


class DocumentationEndpointAuditor:
    """Audits documentation files for endpoint URLs"""

    def __init__(self, base_path: str = ".", docs_dir: Optional[str] = None, runbooks_dir: Optional[str] = None):
        self.base_path = Path(base_path)
        self.docs_dir = Path(docs_dir) if docs_dir else self.base_path / "docs"
        self.runbooks_dir = Path(runbooks_dir) if runbooks_dir else self.base_path / "runbooks"

        # All endpoint references found
        self.endpoint_references: List[EndpointReference] = []

        # Mappings from endpoints to documentation
        self.endpoint_mappings: Dict[str, DocumentationMapping] = {}

        # Patterns for finding endpoints
        self.endpoint_patterns = {
            # REST API endpoints: /api/v1/... or /api/... or full URLs
            'rest': re.compile(
                r'(?:^|\s|`|"|\'|/)((?:https?://[^\s`"\'\)]+)?/api/v\d+/[^\s`"\'\)]+|(?:https?://[^\s`"\'\)]+)?/api/[^\s`"\'\)]+)',
                re.IGNORECASE | re.MULTILINE
            ),
            # GraphQL endpoints
            'graphql': re.compile(
                r'(?:^|\s|`|"|\'|/)(/graphql[^\s`"\'\)]*)',
                re.IGNORECASE | re.MULTILINE
            ),
            # WebSocket endpoints
            'websocket': re.compile(
                r'(?:^|\s|`|"|\'|/)(/ws/[^\s`"\'\)]+|wss?://[^\s`"\'\)]+)',
                re.IGNORECASE | re.MULTILINE
            ),
            # HTTP method + endpoint pattern
            'method_endpoint': re.compile(
                r'(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+(?:`|"|\')?(/api/[^\s`"\'\)]+)',
                re.IGNORECASE | re.MULTILINE
            ),
            # URL patterns in code blocks
            'code_block': re.compile(
                r'```(?:bash|shell|curl|http|json|yaml|python|javascript|typescript)?\n.*?(/api/[^\s`"\'\)]+)',
                re.IGNORECASE | re.MULTILINE | re.DOTALL
            ),
        }

    def audit_all(self):
        """Run comprehensive audit of all documentation"""
        print("🔍 Starting comprehensive documentation endpoint audit...")

        # Extract from all sources
        print("\n📄 Searching API_*.md files...")
        self.endpoint_references.extend(self._extract_from_api_files())

        print("📋 Searching api-audit/*.md files...")
        self.endpoint_references.extend(self._extract_from_api_audit())

        print("📘 Searching OpenAPI specifications...")
        self.endpoint_references.extend(self._extract_from_openapi_specs())

        print("📚 Searching API reference documentation...")
        self.endpoint_references.extend(self._extract_from_api_reference())

        print("👨‍💻 Searching developer guides...")
        self.endpoint_references.extend(self._extract_from_developer_guides())

        print("📖 Searching runbooks...")
        self.endpoint_references.extend(self._extract_from_runbooks())

        # Build mappings
        print("\n🗺️  Building documentation mappings...")
        self._build_mappings()

        print(f"\n✅ Audit complete!")
        print(f"   Found {len(self.endpoint_references)} endpoint references")
        print(f"   Mapped to {len(self.endpoint_mappings)} unique endpoints")

    def _extract_from_api_files(self) -> List[EndpointReference]:
        """Extract endpoints from docs/API_*.md files"""
        references = []

        if not self.docs_dir.exists():
            return references

        api_files = list(self.docs_dir.glob("API_*.md"))

        for api_file in api_files:
            try:
                content = api_file.read_text(encoding='utf-8')
                file_refs = self._extract_endpoints_from_content(
                    content,
                    str(api_file.relative_to(self.base_path)),
                    "api_reference"
                )
                references.extend(file_refs)
                print(f"   ✓ {api_file.name}: {len(file_refs)} endpoints")
            except Exception as e:
                print(f"   ✗ Error processing {api_file}: {e}", file=sys.stderr)

        return references

    def _extract_from_api_audit(self) -> List[EndpointReference]:
        """Extract endpoints from docs/api-audit/*.md files"""
        references = []

        api_audit_dir = self.docs_dir / "api-audit"
        if not api_audit_dir.exists():
            return references

        audit_files = list(api_audit_dir.glob("*.md"))

        for audit_file in audit_files:
            try:
                content = audit_file.read_text(encoding='utf-8')
                file_refs = self._extract_endpoints_from_content(
                    content,
                    str(audit_file.relative_to(self.base_path)),
                    "api_audit"
                )
                references.extend(file_refs)
                print(f"   ✓ {audit_file.name}: {len(file_refs)} endpoints")
            except Exception as e:
                print(f"   ✗ Error processing {audit_file}: {e}", file=sys.stderr)

        return references

    def _extract_from_openapi_specs(self) -> List[EndpointReference]:
        """Extract endpoints from OpenAPI specifications"""
        references = []

        # Search in examples/contracts for OpenAPI specs
        examples_dir = self.base_path / "examples" / "contracts"
        if examples_dir.exists():
            for spec_file in examples_dir.glob("*.yaml"):
                try:
                    with open(spec_file, 'r', encoding='utf-8') as f:
                        spec = yaml.safe_load(f)

                    if spec and 'paths' in spec:
                        for path, methods in spec['paths'].items():
                            if isinstance(methods, dict):
                                for method in methods.keys():
                                    if method.upper() in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']:
                                        ref = EndpointReference(
                                            endpoint_path=path,
                                            method=method.upper(),
                                            source_file=str(spec_file.relative_to(self.base_path)),
                                            documentation_type="openapi"
                                        )
                                        references.append(ref)

                    print(f"   ✓ {spec_file.name}: {len([r for r in references if r.source_file == str(spec_file.relative_to(self.base_path))])} endpoints")
                except Exception as e:
                    print(f"   ✗ Error processing {spec_file}: {e}", file=sys.stderr)

        # Also search docs/api-contracts
        api_contracts_dir = self.docs_dir / "api-contracts"
        if api_contracts_dir.exists():
            for spec_file in api_contracts_dir.rglob("*.yaml"):
                try:
                    with open(spec_file, 'r', encoding='utf-8') as f:
                        spec = yaml.safe_load(f)

                    if spec and 'paths' in spec:
                        for path, methods in spec['paths'].items():
                            if isinstance(methods, dict):
                                for method in methods.keys():
                                    if method.upper() in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']:
                                        ref = EndpointReference(
                                            endpoint_path=path,
                                            method=method.upper(),
                                            source_file=str(spec_file.relative_to(self.base_path)),
                                            documentation_type="openapi"
                                        )
                                        references.append(ref)
                except Exception as e:
                    print(f"   ✗ Error processing {spec_file}: {e}", file=sys.stderr)

        return references

    def _extract_from_api_reference(self) -> List[EndpointReference]:
        """Extract endpoints from API reference documentation"""
        references = []

        if not self.docs_dir.exists():
            return references

        # Search API_REFERENCE.md, API_ENDPOINTS_REFERENCE.md, etc.
        reference_files = [
            self.docs_dir / "API_REFERENCE.md",
            self.docs_dir / "API_ENDPOINTS_REFERENCE.md",
        ]

        for ref_file in reference_files:
            if ref_file.exists():
                try:
                    content = ref_file.read_text(encoding='utf-8')
                    file_refs = self._extract_endpoints_from_content(
                        content,
                        str(ref_file.relative_to(self.base_path)),
                        "api_reference"
                    )
                    references.extend(file_refs)
                    print(f"   ✓ {ref_file.name}: {len(file_refs)} endpoints")
                except Exception as e:
                    print(f"   ✗ Error processing {ref_file}: {e}", file=sys.stderr)

        return references

    def _extract_from_developer_guides(self) -> List[EndpointReference]:
        """Extract endpoints from developer guides"""
        references = []

        if not self.docs_dir.exists():
            return references

        guide_files = [
            self.docs_dir / "DEVELOPER_GUIDE.md",
            self.docs_dir / "DEVELOPMENT_GUIDE.md",
            self.docs_dir / "DEVELOPER_ONBOARDING.md",
        ]

        for guide_file in guide_files:
            if guide_file.exists():
                try:
                    content = guide_file.read_text(encoding='utf-8')
                    file_refs = self._extract_endpoints_from_content(
                        content,
                        str(guide_file.relative_to(self.base_path)),
                        "developer_guide"
                    )
                    references.extend(file_refs)
                    print(f"   ✓ {guide_file.name}: {len(file_refs)} endpoints")
                except Exception as e:
                    print(f"   ✗ Error processing {guide_file}: {e}", file=sys.stderr)

        return references

    def _extract_from_runbooks(self) -> List[EndpointReference]:
        """Extract endpoints from runbooks"""
        references = []

        if not self.runbooks_dir.exists():
            return references

        runbook_files = list(self.runbooks_dir.glob("*.md"))

        for runbook_file in runbook_files:
            try:
                content = runbook_file.read_text(encoding='utf-8')
                file_refs = self._extract_endpoints_from_content(
                    content,
                    str(runbook_file.relative_to(self.base_path)),
                    "runbook"
                )
                references.extend(file_refs)
                print(f"   ✓ {runbook_file.name}: {len(file_refs)} endpoints")
            except Exception as e:
                print(f"   ✗ Error processing {runbook_file}: {e}", file=sys.stderr)

        return references

    def _extract_endpoints_from_content(
        self,
        content: str,
        source_file: str,
        doc_type: str
    ) -> List[EndpointReference]:
        """Extract endpoints from content using multiple patterns"""
        references = []
        lines = content.split('\n')

        # Try method + endpoint pattern first
        for match in self.endpoint_patterns['method_endpoint'].finditer(content):
            endpoint = self._normalize_endpoint_path(match.group(2))
            method = match.group(1).upper()
            line_num = content[:match.start()].count('\n') + 1
            context = self._get_context(lines, line_num)

            ref = EndpointReference(
                endpoint_path=endpoint,
                method=method,
                source_file=source_file,
                source_line=line_num,
                context=context,
                documentation_type=doc_type
            )
            references.append(ref)

        # Try REST endpoint pattern
        for match in self.endpoint_patterns['rest'].finditer(content):
            endpoint_raw = match.group(1)
            endpoint = self._normalize_endpoint_path(endpoint_raw)
            line_num = content[:match.start()].count('\n') + 1
            context = self._get_context(lines, line_num)

            # Skip if already found with method (check normalized path)
            normalized_endpoints_with_methods = [
                self._normalize_endpoint_path(r.endpoint_path)
                for r in references if r.method
            ]
            if endpoint not in normalized_endpoints_with_methods:
                ref = EndpointReference(
                    endpoint_path=endpoint,
                    method=None,
                    source_file=source_file,
                    source_line=line_num,
                    context=context,
                    documentation_type=doc_type
                )
                references.append(ref)

        # Try GraphQL pattern
        for match in self.endpoint_patterns['graphql'].finditer(content):
            endpoint = self._normalize_endpoint_path(match.group(1))
            line_num = content[:match.start()].count('\n') + 1
            context = self._get_context(lines, line_num)

            ref = EndpointReference(
                endpoint_path=endpoint,
                method=None,
                source_file=source_file,
                source_line=line_num,
                context=context,
                documentation_type=doc_type
            )
            references.append(ref)

        # Try WebSocket pattern
        for match in self.endpoint_patterns['websocket'].finditer(content):
            endpoint = self._normalize_endpoint_path(match.group(1))
            line_num = content[:match.start()].count('\n') + 1
            context = self._get_context(lines, line_num)

            ref = EndpointReference(
                endpoint_path=endpoint,
                method=None,
                source_file=source_file,
                source_line=line_num,
                context=context,
                documentation_type=doc_type
            )
            references.append(ref)

        return references

    def _normalize_endpoint_path(self, path: str) -> str:
        """Normalize endpoint path by removing protocol, host, and formatting"""
        # Remove backticks, quotes
        path = path.strip('`"\'')

        # Remove protocol and host
        if '://' in path:
            parsed = urllib.parse.urlparse(path)
            path = parsed.path

        # Ensure starts with /
        if not path.startswith('/'):
            path = '/' + path

        # Preserve trailing slashes for API consistency
        # (Don't remove them - APIs can have trailing slashes)

        return path

    def _get_context(self, lines: List[str], line_num: int, context_lines: int = 2) -> str:
        """Get context around a line"""
        start = max(0, line_num - context_lines - 1)
        end = min(len(lines), line_num + context_lines)
        context = '\n'.join(lines[start:end])
        return context[:200]  # Limit context length

    def _build_mappings(self):
        """Build mappings from endpoints to documentation files"""
        self.endpoint_mappings = {}

        for ref in self.endpoint_references:
            normalized = self._normalize_endpoint_path(ref.endpoint_path)

            if normalized not in self.endpoint_mappings:
                self.endpoint_mappings[normalized] = DocumentationMapping(
                    endpoint_path=ref.endpoint_path,
                    normalized_path=normalized,
                    methods=set(),
                    documentation_files=[],
                    references=[],
                    total_references=0
                )

            mapping = self.endpoint_mappings[normalized]

            if ref.method:
                mapping.methods.add(ref.method)

            if ref.source_file not in mapping.documentation_files:
                mapping.documentation_files.append(ref.source_file)

            mapping.references.append(ref)
            mapping.total_references += 1

    def map_documentation_to_endpoints(self) -> List[DocumentationMapping]:
        """Get all documentation mappings"""
        return list(self.endpoint_mappings.values())

    def verify_all_documentation_found(self) -> Dict[str, Any]:
        """Verify that all documentation was found"""
        total_files = (
            len(list(self.docs_dir.glob("API_*.md"))) +
            len(list((self.docs_dir / "api-audit").glob("*.md"))) if (self.docs_dir / "api-audit").exists() else 0 +
            len(list(self.runbooks_dir.glob("*.md"))) if self.runbooks_dir.exists() else 0
        )

        files_with_endpoints = len(set(ref.source_file for ref in self.endpoint_references))

        return {
            "status": "success" if files_with_endpoints > 0 else "warning",
            "files_checked": total_files,
            "files_with_endpoints": files_with_endpoints,
            "endpoints_found": len(self.endpoint_references),
            "unique_endpoints": len(self.endpoint_mappings)
        }

    def verify_documentation_mapping(self) -> Dict[str, Any]:
        """Verify documentation mapping completeness"""
        endpoints_with_docs = len([m for m in self.endpoint_mappings.values() if len(m.documentation_files) > 0])
        endpoints_with_multiple_docs = len([m for m in self.endpoint_mappings.values() if len(m.documentation_files) > 1])

        return {
            "status": "success" if endpoints_with_docs > 0 else "warning",
            "mappings_verified": len(self.endpoint_mappings),
            "endpoints_with_docs": endpoints_with_docs,
            "endpoints_with_multiple_docs": endpoints_with_multiple_docs,
            "total_references": sum(m.total_references for m in self.endpoint_mappings.values())
        }

    def generate_report(self, output_file: str, format: str = "json"):
        """Generate audit report"""
        mappings = self.map_documentation_to_endpoints()

        # Build summary
        doc_types = defaultdict(int)
        for ref in self.endpoint_references:
            doc_types[ref.documentation_type] += 1

        summary = {
            "generated_at": datetime.now().isoformat(),
            "total_endpoints": len(self.endpoint_mappings),
            "total_references": len(self.endpoint_references),
            "total_documentation_files": len(set(ref.source_file for ref in self.endpoint_references)),
            "documentation_types": dict(doc_types),
            "verification": {
                "documentation_found": self.verify_all_documentation_found(),
                "mapping_completeness": self.verify_documentation_mapping()
            }
        }

        # Build endpoint details
        endpoints = []
        for mapping in sorted(mappings, key=lambda m: m.normalized_path):
            endpoints.append({
                "endpoint_path": mapping.endpoint_path,
                "normalized_path": mapping.normalized_path,
                "methods": sorted(list(mapping.methods)) if mapping.methods else None,
                "documentation_files": mapping.documentation_files,
                "total_references": mapping.total_references,
                "reference_details": [
                    {
                        "source_file": ref.source_file,
                        "source_line": ref.source_line,
                        "method": ref.method,
                        "documentation_type": ref.documentation_type,
                        "context": ref.context[:100] if ref.context else None
                    }
                    for ref in mapping.references[:10]  # Limit to first 10 references
                ]
            })

        # Build documentation mappings
        documentation_mappings = []
        for mapping in sorted(mappings, key=lambda m: m.normalized_path):
            documentation_mappings.append({
                "endpoint": mapping.normalized_path,
                "files": mapping.documentation_files,
                "reference_count": mapping.total_references
            })

        report = {
            "summary": summary,
            "endpoints": endpoints,
            "documentation_mappings": documentation_mappings
        }

        # Write report
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
        else:
            # Markdown format
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("# Documentation Endpoint Audit Report\n\n")
                f.write(f"**Generated:** {summary['generated_at']}\n\n")
                f.write(f"## Summary\n\n")
                f.write(f"- **Total Unique Endpoints:** {summary['total_endpoints']}\n")
                f.write(f"- **Total References:** {summary['total_references']}\n")
                f.write(f"- **Documentation Files:** {summary['total_documentation_files']}\n\n")
                f.write(f"### Documentation Types\n\n")
                for doc_type, count in summary['documentation_types'].items():
                    f.write(f"- **{doc_type}:** {count}\n")
                f.write(f"\n## Endpoints\n\n")
                for endpoint in endpoints:
                    f.write(f"### {endpoint['normalized_path']}\n\n")
                    if endpoint['methods']:
                        f.write(f"**Methods:** {', '.join(endpoint['methods'])}\n\n")
                    f.write(f"**Documentation Files:** {len(endpoint['documentation_files'])}\n\n")
                    for doc_file in endpoint['documentation_files']:
                        f.write(f"- `{doc_file}`\n")
                    f.write(f"\n**Total References:** {endpoint['total_references']}\n\n")
                    f.write("---\n\n")

        print(f"\n📊 Report generated: {output_path}")
        return report


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(
        description="Audit documentation files for endpoint URLs"
    )
    parser.add_argument(
        "--output",
        default="docs/api-audit/documentation-endpoint-audit.json",
        help="Output file path"
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format"
    )
    parser.add_argument(
        "--base-path",
        default=".",
        help="Base path of the project"
    )
    parser.add_argument(
        "--docs-dir",
        help="Documentation directory (default: {base_path}/docs)"
    )
    parser.add_argument(
        "--runbooks-dir",
        help="Runbooks directory (default: {base_path}/runbooks)"
    )

    args = parser.parse_args()

    auditor = DocumentationEndpointAuditor(
        base_path=args.base_path,
        docs_dir=args.docs_dir,
        runbooks_dir=args.runbooks_dir
    )

    auditor.audit_all()
    auditor.generate_report(args.output, format=args.format)

    # Print verification results
    print("\n" + "="*60)
    print("Verification Results")
    print("="*60)

    doc_verification = auditor.verify_all_documentation_found()
    print(f"\n📄 Documentation Found:")
    print(f"   Files checked: {doc_verification['files_checked']}")
    print(f"   Files with endpoints: {doc_verification['files_with_endpoints']}")
    print(f"   Endpoints found: {doc_verification['endpoints_found']}")
    print(f"   Unique endpoints: {doc_verification['unique_endpoints']}")

    mapping_verification = auditor.verify_documentation_mapping()
    print(f"\n🗺️  Mapping Verification:")
    print(f"   Mappings verified: {mapping_verification['mappings_verified']}")
    print(f"   Endpoints with docs: {mapping_verification['endpoints_with_docs']}")
    print(f"   Endpoints with multiple docs: {mapping_verification['endpoints_with_multiple_docs']}")
    print(f"   Total references: {mapping_verification['total_references']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

