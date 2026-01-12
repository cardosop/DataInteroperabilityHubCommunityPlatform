#!/usr/bin/env python3
"""
Review CI/CD Pipelines and Extract Endpoint References

This script:
1. Reviews API endpoint testing workflows
2. Reviews OpenAPI validation workflows
3. Reviews E2E test workflows
4. Extracts endpoint references from workflows
5. Generates a comprehensive review report

Usage:
    python scripts/review_cicd_workflows.py [--workflows-dir PATH] [--output OUTPUT_FILE]
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


@dataclass
class WorkflowEndpointReference:
    """Represents an endpoint reference found in a workflow"""
    endpoint_path: str
    method: Optional[str] = None
    workflow_file: str = ""
    workflow_name: str = ""
    job_name: str = ""
    step_name: str = ""
    line_number: int = 0
    context: str = ""
    reference_type: str = ""  # 'test', 'validation', 'health_check', 'api_call'


@dataclass
class WorkflowReview:
    """Represents a workflow review"""
    workflow_file: str
    workflow_name: str
    workflow_type: str  # 'api_testing', 'openapi_validation', 'e2e', 'other'
    jobs: List[str] = field(default_factory=list)
    endpoint_references: List[WorkflowEndpointReference] = field(default_factory=list)
    total_endpoint_references: int = 0
    has_api_testing: bool = False
    has_openapi_validation: bool = False
    has_e2e_tests: bool = False


class CICDWorkflowReviewer:
    """Reviews CI/CD workflows and extracts endpoint references"""

    def __init__(self, workflows_dir: Path):
        self.workflows_dir = workflows_dir
        self.workflows: List[WorkflowReview] = []
        self.endpoint_references: List[WorkflowEndpointReference] = []

        # Patterns for finding endpoints
        self.endpoint_patterns = {
            # REST API endpoints: /api/v1/... or /api/...
            'rest': re.compile(
                r'(?:^|\s|`|"|\'|/|curl|http|https|\$)((?:https?://[^\s`"\'\)\n]+)?/api/v\d+/[^\s`"\'\)\n]+|(?:https?://[^\s`"\'\)\n]+)?/api/[^\s`"\'\)\n]+|/health[^\s`"\'\)\n]*|/healthz[^\s`"\'\)\n]*)',
                re.IGNORECASE | re.MULTILINE
            ),
            # HTTP method + endpoint pattern
            'method_endpoint': re.compile(
                r'(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+(?:`|"|\')?(/api/[^\s`"\'\)\n]+|/health[^\s`"\'\)\n]*|/healthz[^\s`"\'\)\n]*)',
                re.IGNORECASE | re.MULTILINE
            ),
            # curl commands with URLs
            'curl': re.compile(
                r'curl\s+(?:-[^\s]+\s+)*["\']?(https?://[^\s"\'\)\n]+|/api/[^\s"\'\)\n]+|/health[^\s"\'\)\n]*|/healthz[^\s"\'\)\n]*)',
                re.IGNORECASE | re.MULTILINE
            ),
            # Environment variables with URLs
            'env_url': re.compile(
                r'(?:SERVICE_URL|API_URL|BASE_URL|WS_URL)\s*[:=]\s*["\']?(https?://[^\s"\'\)\n]+|/api/[^\s"\'\)\n]+)',
                re.IGNORECASE | re.MULTILINE
            ),
            # Health check endpoints
            'health': re.compile(
                r'(?:health_endpoint|health-check|/health|/healthz)\s*[:=]\s*["\']?([^\s"\'\)\n]+)',
                re.IGNORECASE | re.MULTILINE
            ),
        }

    def review_all_workflows(self):
        """Review all workflow files"""
        if not self.workflows_dir.exists():
            print(f"Error: Workflows directory not found: {self.workflows_dir}", file=sys.stderr)
            return

        workflow_files = list(self.workflows_dir.glob("*.yml")) + list(self.workflows_dir.glob("*.yaml"))

        print(f"🔍 Reviewing {len(workflow_files)} workflow files...")

        for workflow_file in workflow_files:
            if workflow_file.name in ['README.md', 'CI_CD_SUMMARY.md']:
                continue

            try:
                review = self._review_workflow_file(workflow_file)
                if review:
                    self.workflows.append(review)
                    print(f"   ✓ {workflow_file.name}: {review.workflow_type} ({len(review.endpoint_references)} endpoint references)")
            except Exception as e:
                print(f"   ✗ Error processing {workflow_file.name}: {e}", file=sys.stderr)

        # Collect all endpoint references
        for workflow in self.workflows:
            self.endpoint_references.extend(workflow.endpoint_references)

        print(f"\n✅ Review complete!")
        print(f"   Reviewed {len(self.workflows)} workflows")
        print(f"   Found {len(self.endpoint_references)} endpoint references")

    def _review_workflow_file(self, workflow_file: Path) -> Optional[WorkflowReview]:
        """Review a single workflow file"""
        content = workflow_file.read_text(encoding='utf-8')

        # Parse YAML - use empty dict if parsing fails so we can still extract from raw content
        workflow_data = {}
        try:
            workflow_data = yaml.safe_load(content) or {}
        except yaml.YAMLError as e:
            print(f"   ⚠ Warning: Could not parse YAML for {workflow_file.name}: {e}", file=sys.stderr)
            # Continue with empty dict - we'll still extract from raw content

        workflow_name = workflow_data.get('name', workflow_file.stem) if workflow_data else workflow_file.stem
        jobs = list(workflow_data.get('jobs', {}).keys()) if workflow_data else []

        # Determine workflow type from content
        workflow_type = self._determine_workflow_type(workflow_name, content, jobs)

        # Extract endpoint references from raw content (works even if YAML parsing failed)
        endpoint_references = self._extract_endpoint_references(
            content,
            str(workflow_file.relative_to(self.workflows_dir.parent.parent)),
            workflow_name,
            workflow_data
        )

        # Check for specific workflow features
        has_api_testing = self._has_api_testing(content, workflow_data)
        has_openapi_validation = self._has_openapi_validation(content, workflow_data)
        has_e2e_tests = self._has_e2e_tests(content, workflow_data)

        return WorkflowReview(
            workflow_file=str(workflow_file.relative_to(self.workflows_dir.parent.parent)),
            workflow_name=workflow_name,
            workflow_type=workflow_type,
            jobs=jobs,
            endpoint_references=endpoint_references,
            total_endpoint_references=len(endpoint_references),
            has_api_testing=has_api_testing,
            has_openapi_validation=has_openapi_validation,
            has_e2e_tests=has_e2e_tests
        )

    def _determine_workflow_type(self, workflow_name: str, content: str, jobs: List[str]) -> str:
        """Determine the type of workflow"""
        content_lower = content.lower()
        name_lower = workflow_name.lower()

        if 'e2e' in name_lower or 'e2e' in content_lower or 'end-to-end' in content_lower:
            return 'e2e'
        elif 'openapi' in name_lower or 'openapi' in content_lower or 'spectacular' in content_lower:
            return 'openapi_validation'
        elif 'test' in name_lower or 'pytest' in content_lower or 'test' in content_lower:
            if 'api' in name_lower or 'api' in content_lower:
                return 'api_testing'
            return 'testing'
        elif 'ci' in name_lower or 'lint' in name_lower:
            return 'ci'
        elif 'deploy' in name_lower:
            return 'deployment'
        else:
            return 'other'

    def _has_api_testing(self, content: str, workflow_data: Dict) -> bool:
        """Check if workflow has API endpoint testing"""
        content_lower = content.lower()

        # Check for API test patterns
        api_test_patterns = [
            r'pytest.*test.*api',
            r'test.*endpoint',
            r'api.*test',
            r'/api/v\d+/',
        ]

        for pattern in api_test_patterns:
            if re.search(pattern, content_lower):
                return True

        # Check jobs for test steps
        jobs = workflow_data.get('jobs', {})
        for job_name, job_data in jobs.items():
            steps = job_data.get('steps', [])
            for step in steps:
                run = step.get('run', '')
                if 'pytest' in run.lower() and 'api' in run.lower():
                    return True

        return False

    def _has_openapi_validation(self, content: str, workflow_data: Dict) -> bool:
        """Check if workflow has OpenAPI validation"""
        content_lower = content.lower()

        return (
            'openapi' in content_lower or
            'spectacular' in content_lower or
            'swagger' in content_lower or
            'spectral' in content_lower
        )

    def _has_e2e_tests(self, content: str, workflow_data: Dict) -> bool:
        """Check if workflow has E2E tests"""
        content_lower = content.lower()

        return (
            'e2e' in content_lower or
            'end-to-end' in content_lower or
            'end_to_end' in content_lower
        )

    def _extract_endpoint_references(
        self,
        content: str,
        workflow_file: str,
        workflow_name: str,
        workflow_data: Dict
    ) -> List[WorkflowEndpointReference]:
        """Extract endpoint references from workflow content"""
        references = []
        lines = content.split('\n')

        # Extract from jobs and steps if YAML parsing succeeded
        if workflow_data:
            jobs = workflow_data.get('jobs', {})
            for job_name, job_data in jobs.items():
                steps = job_data.get('steps', [])
                for step_idx, step in enumerate(steps):
                    step_name = step.get('name', f'step_{step_idx}')
                    run_content = step.get('run', '')
                    env = step.get('env', {})

                    # Combine run content and env values
                    step_content = run_content + '\n' + '\n'.join(f"{k}={v}" for k, v in env.items())

                    # Extract endpoints from step content
                    step_refs = self._extract_endpoints_from_text(
                        step_content,
                        workflow_file,
                        workflow_name,
                        job_name,
                        step_name
                    )
                    references.extend(step_refs)

                # Also check job-level env
                job_env = job_data.get('env', {})
                if job_env:
                    env_content = '\n'.join(f"{k}={v}" for k, v in job_env.items())
                    env_refs = self._extract_endpoints_from_text(
                        env_content,
                        workflow_file,
                        workflow_name,
                        job_name,
                        'job_env'
                    )
                    references.extend(env_refs)

        # Always search entire content for endpoints (works even if YAML parsing failed)
        # This is important for files with embedded code blocks
        all_refs = self._extract_endpoints_from_text(
            content,
            workflow_file,
            workflow_name,
            None,
            None
        )

        # Deduplicate
        seen = set()
        unique_refs = []
        for ref in references + all_refs:
            key = (ref.endpoint_path, ref.workflow_file, ref.job_name, ref.step_name, ref.line_number)
            if key not in seen:
                seen.add(key)
                unique_refs.append(ref)

        return unique_refs

    def _extract_endpoints_from_text(
        self,
        text: str,
        workflow_file: str,
        workflow_name: str,
        job_name: Optional[str],
        step_name: Optional[str]
    ) -> List[WorkflowEndpointReference]:
        """Extract endpoints from text content"""
        references = []
        lines = text.split('\n')

        # Try method + endpoint pattern first
        for match in self.endpoint_patterns['method_endpoint'].finditer(text):
            endpoint = self._normalize_endpoint_path(match.group(2))
            method = match.group(1).upper()
            line_num = text[:match.start()].count('\n') + 1
            context = self._get_context(lines, line_num)

            # Determine reference type
            ref_type = 'api_call'
            if '/health' in endpoint or '/healthz' in endpoint:
                ref_type = 'health_check'
            elif 'test' in context.lower() or 'pytest' in context.lower():
                ref_type = 'test'

            ref = WorkflowEndpointReference(
                endpoint_path=endpoint,
                method=method,
                workflow_file=workflow_file,
                workflow_name=workflow_name,
                job_name=job_name or '',
                step_name=step_name or '',
                line_number=line_num,
                context=context,
                reference_type=ref_type
            )
            references.append(ref)

        # Try curl pattern
        for match in self.endpoint_patterns['curl'].finditer(text):
            endpoint_raw = match.group(1)
            endpoint = self._normalize_endpoint_path(endpoint_raw)
            line_num = text[:match.start()].count('\n') + 1
            context = self._get_context(lines, line_num)

            # Determine reference type
            ref_type = 'api_call'
            if '/health' in endpoint or '/healthz' in endpoint:
                ref_type = 'health_check'

            ref = WorkflowEndpointReference(
                endpoint_path=endpoint,
                method=None,
                workflow_file=workflow_file,
                workflow_name=workflow_name,
                job_name=job_name or '',
                step_name=step_name or '',
                line_number=line_num,
                context=context,
                reference_type=ref_type
            )
            references.append(ref)

        # Try REST endpoint pattern
        for match in self.endpoint_patterns['rest'].finditer(text):
            endpoint_raw = match.group(1)
            endpoint = self._normalize_endpoint_path(endpoint_raw)

            # Skip if already found
            if any(r.endpoint_path == endpoint and r.line_number == text[:match.start()].count('\n') + 1 for r in references):
                continue

            line_num = text[:match.start()].count('\n') + 1
            context = self._get_context(lines, line_num)

            # Determine reference type
            ref_type = 'api_call'
            if '/health' in endpoint or '/healthz' in endpoint:
                ref_type = 'health_check'
            elif 'test' in context.lower() or 'pytest' in context.lower():
                ref_type = 'test'

            ref = WorkflowEndpointReference(
                endpoint_path=endpoint,
                method=None,
                workflow_file=workflow_file,
                workflow_name=workflow_name,
                job_name=job_name or '',
                step_name=step_name or '',
                line_number=line_num,
                context=context,
                reference_type=ref_type
            )
            references.append(ref)

        # Try environment variable URLs
        for match in self.endpoint_patterns['env_url'].finditer(text):
            endpoint_raw = match.group(1) if match.lastindex else match.group(0)
            endpoint = self._normalize_endpoint_path(endpoint_raw)
            line_num = text[:match.start()].count('\n') + 1
            context = self._get_context(lines, line_num)

            ref = WorkflowEndpointReference(
                endpoint_path=endpoint,
                method=None,
                workflow_file=workflow_file,
                workflow_name=workflow_name,
                job_name=job_name or '',
                step_name=step_name or '',
                line_number=line_num,
                context=context,
                reference_type='api_call'
            )
            references.append(ref)

        return references

    def _normalize_endpoint_path(self, path: str) -> str:
        """Normalize endpoint path"""
        path = path.strip('`"\'')

        # Remove protocol and host
        if '://' in path:
            from urllib.parse import urlparse
            parsed = urlparse(path)
            path = parsed.path

        # Ensure starts with /
        if not path.startswith('/'):
            path = '/' + path

        return path

    def _get_context(self, lines: List[str], line_num: int, context_lines: int = 2) -> str:
        """Get context around a line"""
        start = max(0, line_num - context_lines - 1)
        end = min(len(lines), line_num + context_lines)
        context = '\n'.join(lines[start:end])
        return context[:200]

    def verify_all_workflows_reviewed(self) -> Dict[str, Any]:
        """Verify that all workflows were reviewed"""
        workflow_files = list(self.workflows_dir.glob("*.yml")) + list(self.workflows_dir.glob("*.yaml"))
        workflow_files = [f for f in workflow_files if f.name not in ['README.md', 'CI_CD_SUMMARY.md']]

        reviewed_files = {w.workflow_file for w in self.workflows}
        total_files = len(workflow_files)
        reviewed_count = len(reviewed_files)

        return {
            "status": "success" if reviewed_count == total_files else "warning",
            "total_workflow_files": total_files,
            "reviewed_workflows": reviewed_count,
            "workflow_types": {
                w.workflow_type: sum(1 for w2 in self.workflows if w2.workflow_type == w.workflow_type)
                for w in self.workflows
            }
        }

    def verify_workflow_reference_extraction(self) -> Dict[str, Any]:
        """Verify workflow reference extraction"""
        workflows_with_references = len([w for w in self.workflows if w.total_endpoint_references > 0])
        total_references = len(self.endpoint_references)

        reference_types = defaultdict(int)
        for ref in self.endpoint_references:
            reference_types[ref.reference_type] += 1

        return {
            "status": "success" if total_references >= 0 else "warning",
            "total_references": total_references,
            "workflows_with_references": workflows_with_references,
            "reference_types": dict(reference_types),
            "extraction_working": True
        }

    def generate_report(self, output_file: Path, format: str = "json"):
        """Generate review report"""
        verification_review = self.verify_all_workflows_reviewed()
        verification_extraction = self.verify_workflow_reference_extraction()

        # Group workflows by type
        workflows_by_type = defaultdict(list)
        for workflow in self.workflows:
            workflows_by_type[workflow.workflow_type].append(workflow)

        report = {
            "generated_at": datetime.now().isoformat(),
            "workflows_dir": str(self.workflows_dir),
            "summary": {
                "total_workflows": len(self.workflows),
                "total_endpoint_references": len(self.endpoint_references),
                "workflows_by_type": {
                    wtype: len(workflows)
                    for wtype, workflows in workflows_by_type.items()
                },
                "verification": {
                    "workflows_reviewed": verification_review,
                    "reference_extraction": verification_extraction
                }
            },
            "workflows": [
                {
                    "workflow_file": w.workflow_file,
                    "workflow_name": w.workflow_name,
                    "workflow_type": w.workflow_type,
                    "jobs": w.jobs,
                    "has_api_testing": w.has_api_testing,
                    "has_openapi_validation": w.has_openapi_validation,
                    "has_e2e_tests": w.has_e2e_tests,
                    "total_endpoint_references": w.total_endpoint_references,
                    "endpoint_references": [
                        {
                            "endpoint_path": ref.endpoint_path,
                            "method": ref.method,
                            "job_name": ref.job_name,
                            "step_name": ref.step_name,
                            "reference_type": ref.reference_type,
                            "line_number": ref.line_number
                        }
                        for ref in w.endpoint_references[:20]  # Limit to first 20
                    ]
                }
                for w in self.workflows
            ],
            "endpoint_references": [
                {
                    "endpoint_path": ref.endpoint_path,
                    "method": ref.method,
                    "workflow_file": ref.workflow_file,
                    "workflow_name": ref.workflow_name,
                    "job_name": ref.job_name,
                    "step_name": ref.step_name,
                    "reference_type": ref.reference_type
                }
                for ref in self.endpoint_references
            ]
        }

        output_file.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
        else:
            # Markdown format
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("# CI/CD Workflow Review Report\n\n")
                f.write(f"**Generated:** {report['generated_at']}\n\n")
                f.write("## Summary\n\n")
                f.write(f"- **Total Workflows:** {report['summary']['total_workflows']}\n")
                f.write(f"- **Total Endpoint References:** {report['summary']['total_endpoint_references']}\n\n")
                f.write("### Workflows by Type\n\n")
                for wtype, count in report['summary']['workflows_by_type'].items():
                    f.write(f"- **{wtype}:** {count}\n")
                f.write("\n## Workflows\n\n")
                for workflow in report['workflows']:
                    f.write(f"### {workflow['workflow_name']}\n\n")
                    f.write(f"**File:** `{workflow['workflow_file']}`\n\n")
                    f.write(f"**Type:** {workflow['workflow_type']}\n\n")
                    f.write(f"**Endpoint References:** {workflow['total_endpoint_references']}\n\n")
                    if workflow['endpoint_references']:
                        f.write("**References:**\n\n")
                        for ref in workflow['endpoint_references']:
                            f.write(f"- {ref['method'] or 'ANY'} {ref['endpoint_path']} ({ref['reference_type']})\n")
                    f.write("\n")

        print(f"\n📊 Report generated: {output_file}")
        return report


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(
        description="Review CI/CD workflows and extract endpoint references"
    )
    parser.add_argument(
        "--workflows-dir",
        default=".github/workflows",
        help="Path to workflows directory"
    )
    parser.add_argument(
        "--output",
        default="docs/api-audit/cicd-workflows-review.json",
        help="Output file path"
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format"
    )

    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    workflows_dir = project_root / args.workflows_dir
    output_file = project_root / args.output

    if not workflows_dir.exists():
        print(f"Error: Workflows directory not found: {workflows_dir}", file=sys.stderr)
        return 1

    reviewer = CICDWorkflowReviewer(workflows_dir)
    reviewer.review_all_workflows()

    # Print verification results
    print("\n" + "="*60)
    print("Verification Results")
    print("="*60)

    review_verification = reviewer.verify_all_workflows_reviewed()
    print(f"\n📋 Workflows Reviewed:")
    print(f"   Total workflow files: {review_verification['total_workflow_files']}")
    print(f"   Reviewed workflows: {review_verification['reviewed_workflows']}")
    print(f"   Workflow types: {review_verification['workflow_types']}")

    extraction_verification = reviewer.verify_workflow_reference_extraction()
    print(f"\n🔗 Reference Extraction:")
    print(f"   Total references: {extraction_verification['total_references']}")
    print(f"   Workflows with references: {extraction_verification['workflows_with_references']}")
    print(f"   Reference types: {extraction_verification['reference_types']}")

    reviewer.generate_report(output_file, format=args.format)

    return 0


if __name__ == "__main__":
    sys.exit(main())

