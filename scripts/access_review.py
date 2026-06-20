#!/usr/bin/env python3
"""306.1 — IAM access review: query users, roles, generate evidence JSON."""

import json
import os
from datetime import UTC, datetime

OUTPUT_DIR = "evidence"


def collect_evidence():
    """Simulate IAM access collection. In production, query AWS IAM API."""
    evidence = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": "scripts/access_review.py",
        "type": "iam-access-review",
        "users": [],
        "roles": [],
        "access_entries": [],
    }
    return evidence


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    output = os.path.join(OUTPUT_DIR, f"ACCESS_REVIEW-{date_str}.json")

    evidence = collect_evidence()

    # Diff against previous run
    prev_files = sorted(
        [
            f
            for f in os.listdir(OUTPUT_DIR)
            if f.startswith("ACCESS_REVIEW-") and f != os.path.basename(output)
        ]
    )
    if prev_files:
        prev_path = os.path.join(OUTPUT_DIR, prev_files[-1])
        try:
            with open(prev_path) as f:
                prev = json.load(f)
        except:
            prev = {}
        evidence["diff_from"] = os.path.basename(prev_path)
        evidence["new_users"] = len(evidence["users"]) - len(prev.get("users", []))
        evidence["changed_roles"] = len(evidence["roles"]) - len(prev.get("roles", []))
    else:
        evidence["diff_from"] = "baseline"

    with open(output, "w") as f:
        json.dump(evidence, f, indent=2)
    print(f"Access review: {output}")


if __name__ == "__main__":
    main()
