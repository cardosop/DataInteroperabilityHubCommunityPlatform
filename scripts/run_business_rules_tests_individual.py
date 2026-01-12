#!/usr/bin/env python3
"""
Run business rules tests individually to identify specific failures.
"""
import sys
import subprocess
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = PROJECT_ROOT / "venv" / "bin" / "python3"

test_files = [
    "hub/apps/files/tests/test_business_rules.py",
    "hub/apps/scheduled_ingestion/tests/test_business_rules.py",
    "hub/apps/governance/tests/test_business_rules.py",
    "hub/apps/jobs/tests/test_business_rules.py",
    "hub/apps/compliance/tests/test_business_rules.py",
    "hub/apps/dq/tests/test_business_rules.py",
    "hub/apps/search/tests/test_business_rules.py",
    "hub/apps/semantic/tests/test_business_rules.py",
    "hub/apps/orchestration/tests/test_business_rules.py",
    "hub/apps/orchestration/tests/test_business_rules_state_management.py",
    "hub/apps/notifications/tests/test_business_rules.py",
    "hub/apps/webhooks/tests/test_business_rules.py",
    "hub/apps/webhooks/tests/test_business_rules_payload.py",
    "hub/apps/contracts/tests/test_contracts_business_rules.py",
    "hub/apps/contracts/tests/test_odps_business_rules.py",
    "hub/apps/assets/tests/test_business_rules.py",
    "hub/apps/assets/tests/test_business_rules_dataset_attachment.py",
    "hub/apps/datasets/tests/test_business_rules.py",
    "hub/apps/datasets/tests/test_business_rules_access_validation.py",
    "hub/apps/marketplace/tests/test_business_rules.py",
    "hub/apps/marketplace/tests/test_business_rules_pricing_validation.py",
    "hub/apps/transformation/tests/test_business_rules.py",
    "hub/apps/transformation/tests/test_business_rules_registry.py",
    "hub/apps/transformation/tests/test_cross_service_business_rules.py",
    "hub/apps/mesh/tests/test_business_rules.py",
    "hub/apps/mesh/tests/test_data_mesh_business_rules_refactoring.py",
    "hub/apps/mesh/tests/test_policy_topology_business_rules.py",
    "hub/apps/mesh/tests/test_policy_topology_business_rules_refactoring.py",
    "hub/apps/virtualization/tests/test_business_rules.py",
    "hub/apps/virtualization/tests/test_virtualization_business_rules_refactoring.py",
]

env = os.environ.copy()
env["POSTGRES_HOST"] = "localhost"
env["REDIS_HOST"] = "localhost"

results = {"passed": [], "failed": [], "timeout": []}

for test_file in test_files:
    # test_file is already relative to PROJECT_ROOT
    django_path = test_file.replace("/", ".").replace(".py", "")

    print(f"\n{'='*80}")
    print(f"Testing: {django_path}")
    print(f"{'='*80}")

    cmd = [
        str(VENV_PYTHON),
        str(PROJECT_ROOT / "hub" / "manage.py"),
        "test",
        "--verbosity=1",
        "--keepdb",
        django_path,
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout per test file
            env=env,
        )

        if result.returncode == 0:
            print(f"✅ PASSED: {django_path}")
            results["passed"].append(test_file)
        else:
            print(f"❌ FAILED: {django_path}")
            print(result.stdout[-500:] + result.stderr[-500:])
            results["failed"].append(test_file)

    except subprocess.TimeoutExpired:
        print(f"⏱️  TIMEOUT: {django_path}")
        results["timeout"].append(test_file)

print(f"\n{'='*80}")
print("SUMMARY")
print(f"{'='*80}")
print(f"Passed: {len(results['passed'])}/{len(test_files)}")
print(f"Failed: {len(results['failed'])}/{len(test_files)}")
print(f"Timeout: {len(results['timeout'])}/{len(test_files)}")

if results["failed"]:
    print(f"\nFailed tests:")
    for f in results["failed"]:
        print(f"  - {f}")

if results["timeout"]:
    print(f"\nTimeout tests:")
    for f in results["timeout"]:
        print(f"  - {f}")

