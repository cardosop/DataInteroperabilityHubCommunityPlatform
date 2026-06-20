#!/usr/bin/env python3
"""
Update API Development Backlog with Detailed Effort Estimates

Reads effort estimates from JSON file and updates the backlog markdown file
with detailed effort breakdowns for each API.
"""

import json
import re
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent


def format_effort_estimate(estimate: dict[str, Any]) -> str:
    """Format effort estimate for markdown."""
    lines = []

    lines.append(
        f"**Total Effort**: {estimate['total_hours']:.1f} hours ({estimate['total_days']:.1f} days)"
    )
    lines.append("")
    lines.append("**Effort Breakdown**:")
    lines.append(
        f"- **Development**: {estimate['development_hours']:.1f} hours ({estimate['development_hours'] / 8:.1f} days)"
    )
    lines.append(f"  - Base effort: {estimate['breakdown']['base_effort']:.1f}h")
    if estimate["breakdown"]["database"] > 0:
        lines.append(f"  - Database: {estimate['breakdown']['database']:.1f}h")
    if estimate["breakdown"]["external_service"] > 0:
        lines.append(f"  - External service: {estimate['breakdown']['external_service']:.1f}h")
    if estimate["breakdown"]["infrastructure"] > 0:
        lines.append(f"  - Infrastructure: {estimate['breakdown']['infrastructure']:.1f}h")
    if estimate["breakdown"]["service_integration"] > 0:
        lines.append(
            f"  - Service integration: {estimate['breakdown']['service_integration']:.1f}h"
        )
    if estimate["breakdown"]["workflow_integration"] > 0:
        lines.append(
            f"  - Workflow integration: {estimate['breakdown']['workflow_integration']:.1f}h"
        )
    lines.append(
        f"- **Testing**: {estimate['testing_hours']:.1f} hours ({estimate['testing_hours'] / 8:.1f} days)"
    )
    lines.append(f"  - Unit tests: {estimate['breakdown']['unit_tests']:.1f}h")
    lines.append(f"  - Integration tests: {estimate['breakdown']['integration_tests']:.1f}h")
    lines.append(f"  - E2E tests: {estimate['breakdown']['e2e_tests']:.1f}h")
    lines.append(
        f"- **Documentation**: {estimate['documentation_hours']:.1f} hours ({estimate['documentation_hours'] / 8:.1f} days)"
    )
    lines.append("  - API documentation: 0.5h (OpenAPI spec exists)")
    lines.append(f"  - Code documentation: {estimate['breakdown'].get('code_doc', 0.5):.1f}h")

    return "\n".join(lines)


def find_endpoint_in_backlog(backlog_content: str, endpoint: str) -> list[tuple[int, str]]:
    """Find endpoint section in backlog."""
    # Normalize endpoint for matching
    re.escape(endpoint.replace("{id}", "{id}"))

    # Try different patterns
    patterns = [
        rf"#### \d+\.\s+{re.escape(endpoint)}",
        rf"#### \d+\.\s+.*{re.escape(endpoint.split('/')[-1])}",
        rf"\*\*.*{re.escape(endpoint.split('/')[-1])}.*\*\*",
    ]

    matches = []
    lines = backlog_content.split("\n")

    for i, line in enumerate(lines):
        for pattern in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                matches.append((i, line))
                break

    return matches


def update_backlog_with_estimates():
    """Update backlog file with detailed effort estimates."""
    # Read estimates
    estimates_file = PROJECT_ROOT / "docs" / "api-audit" / "api-effort-estimates.json"
    with open(estimates_file) as f:
        estimates = json.load(f)

    # Read backlog
    backlog_file = PROJECT_ROOT / "docs" / "api-audit" / "api-development-backlog.md"
    with open(backlog_file, encoding="utf-8") as f:
        backlog_content = f.read()

    # Map estimates to backlog items
    # This is a simplified mapping - in practice, you'd need more sophisticated matching
    endpoint_mapping = {
        "POST /api/v1/auth/register/": "POST /api/v1/auth/register/",
        "GET /api/v1/auth/me/": "GET /api/v1/auth/me/",
        "GET /api/v1/assets/": "GET /api/v1/assets/",
        "POST /api/v1/assets/{id}/activate/": "POST /api/v1/assets/{id}/activate/",
        "GET /api/v1/auth/api-keys/": "GET /api/v1/auth/api-keys/",
        "POST /api/v1/contracts/{id}/validate/": "POST /api/v1/contracts/{id}/validate/",
        "POST /api/v1/assets/ (enhancement)": "POST /api/v1/assets/",
        "POST /api/v1/assets/{id}/activate/ (enhancement)": "POST /api/v1/assets/{id}/activate/",
        "GET /api/v1/marketplace/listings/": "GET /api/v1/marketplace/listings/",
        "GET /api/v1/search/search/": "GET /api/v1/search/search/",
        "GET /api/v1/scheduled-ingestions/{id}/credentials/": "GET /api/v1/scheduled-ingestions/{id}/credentials/",
        "POST /api/v1/scheduled-ingestions/{id}/credentials/test/": "POST /api/v1/scheduled-ingestions/{id}/credentials/test/",
        "GET /api/v1/compliance/compliance-runs/{id}/results/": "GET /api/v1/compliance/compliance-runs/{id}/results/",
        "GET /api/v1/dq/dq-runs/": "GET /api/v1/dq/dq-runs/",
        "GET /api/v1/dq/dq-runs/{id}/results/": "GET /api/v1/dq/dq-runs/{id}/results/",
        "POST /api/v1/ai/natural-language-search/": "POST /api/v1/ai/natural-language-search/",
        "POST /api/v1/ai/schema-matching/": "POST /api/v1/ai/schema-matching/",
        "POST /api/v1/social/ratings/": "POST /api/v1/social/ratings/",
        "POST /api/v1/social/reviews/": "POST /api/v1/social/reviews/",
        "POST /api/v1/social/comments/": "POST /api/v1/social/comments/",
        "POST /api/v1/social/communities/": "POST /api/v1/social/communities/",
        "GET /api/v1/marketplace/listings/{id}/preview/": "GET /api/v1/marketplace/listings/{id}/preview/",
        "GET /api/v1/developer/plugins/": "GET /api/v1/developer/plugins/",
        "GET /api/v1/developer/sdk/": "GET /api/v1/developer/sdk/",
    }

    # Update backlog with estimates
    updated_content = backlog_content
    lines = updated_content.split("\n")
    new_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]
        new_lines.append(line)

        # Look for "Estimated Effort" line
        if re.match(r"\*\*Estimated Effort\*\*:", line):
            # Find the endpoint this belongs to by looking backwards
            endpoint_found = None
            for j in range(max(0, i - 10), i):
                for est_key, backlog_key in endpoint_mapping.items():
                    if backlog_key in lines[j] or est_key.split()[-1].replace("/", "") in lines[j]:
                        endpoint_found = est_key
                        break
                if endpoint_found:
                    break

            if endpoint_found and endpoint_found in estimates:
                # Skip old estimate line
                i += 1
                # Add new detailed estimate
                estimate_text = format_effort_estimate(estimates[endpoint_found])
                new_lines.append(estimate_text)
                continue

        i += 1

    # Write updated backlog
    with open(backlog_file, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines))

    print("✅ Updated backlog with detailed effort estimates")


def main():
    """Main entry point."""
    print("=" * 80)
    print("Update Backlog with Effort Estimates")
    print("=" * 80)

    update_backlog_with_estimates()

    print("\n✅ Backlog updated successfully!")


if __name__ == "__main__":
    main()
