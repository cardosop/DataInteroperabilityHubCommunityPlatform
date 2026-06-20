#!/usr/bin/env python3
"""
Add batch markers to E2E test files.

Organizes E2E tests into 5 batches for parallel execution.
"""

import re
from pathlib import Path

# Define batch assignments
BATCH_ASSIGNMENTS = {
    # Batch 1: Core API, Contracts, Assets
    "e2e_batch1": [
        "test_rest_api.py",
        "test_api_documentation.py",
        "test_contract_operations.py",
        "test_contract_first_flow.py",
        "test_contract_first_comprehensive.py",
        "test_contract_only_comprehensive.py",
        "test_contract_normalization_enhanced_e2e.py",
        "test_contract_migration.py",
        "test_asset_operations.py",
        "test_dataset_operations.py",
        "test_file_operations.py",
        "test_schema_inference.py",
    ],
    # Batch 2: Worker Service, Jobs, DQ, Compliance
    "e2e_batch2": [
        "test_worker_service_e2e.py",
        "test_worker_service.py",
        "test_job_orchestration.py",
        "test_dq_service.py",
        "test_compliance_service.py",
        "test_audit_logging.py",
        "test_audit_compliance_journeys.py",
    ],
    # Batch 3: Email, Notifications, Rate Limiting
    "e2e_batch3": [
        "test_email_service_e2e.py",
        "test_rate_limiting_e2e.py",
        "test_rate_limiting.py",
        "test_observability.py",
        "test_health_checks.py",
    ],
    # Batch 4: Tenant Config, Personas, CLI
    "e2e_batch4": [
        "test_tenant_config_e2e.py",
        "test_tenant_management.py",
        "test_persona_tenant_admin.py",
        "test_persona_data_provider.py",
        "test_persona_data_consumer.py",
        "test_persona_auditor.py",
        "test_persona_platform_admin.py",
        "test_cli_e2e.py",
        "test_authentication.py",
        "test_user_management.py",
        "test_multi_tenant_isolation.py",
    ],
    # Batch 5: Marketplace, Semantic, Monitoring, Edge Cases
    "e2e_batch5": [
        "test_marketplace_comprehensive.py",
        "test_marketplace_listings.py",
        "test_marketplace_orders.py",
        "test_marketplace_purchase_flow.py",
        "test_entitlements.py",
        "test_semantic_layer.py",
        "test_graphql_api.py",
        "test_monitoring_e2e.py",
        "test_cross_capability_e2e.py",
        "test_complete_user_journeys.py",
        "test_complete_journeys_enhanced.py",
        "test_data_first_flow.py",
        "test_data_first_comprehensive.py",
        "test_error_handling.py",
        "test_custom_actions_error_handling.py",
        "test_sdk_python.py",
    ],
}


def add_batch_marker(file_path, batch_marker):
    """Add batch marker to test file"""
    with open(file_path) as f:
        content = f.read()

    # Check if already has batch marker
    if batch_marker in content:
        return False

    # Find pytestmark line
    pytestmark_pattern = r"(pytestmark\s*=\s*[^\n]+)"
    match = re.search(pytestmark_pattern, content)

    if match:
        # Add batch marker to existing pytestmark
        existing = match.group(1)
        if "[" in existing:
            # Already a list, add to it
            new_marker = existing.replace("]", f", pytest.mark.{batch_marker},]")
        else:
            # Single marker, convert to list
            new_marker = (
                f"pytestmark = [{existing.split('=')[1].strip()}, pytest.mark.{batch_marker}]"
            )
        content = content.replace(existing, new_marker)
    else:
        # Add new pytestmark after imports
        import_end = content.find("\n\n")
        if import_end == -1:
            import_end = content.find("\nclass ")
        if import_end == -1:
            import_end = content.find("\ndef test_")

        if import_end > 0:
            marker_line = f"\npytestmark = pytest.mark.{batch_marker}\n"
            content = content[:import_end] + marker_line + content[import_end:]

    with open(file_path, "w") as f:
        f.write(content)

    return True


def main():
    """Main function"""
    project_root = Path(__file__).parent.parent
    e2e_dir = project_root / "tests" / "e2e"

    if not e2e_dir.exists():
        print(f"E2E directory not found: {e2e_dir}")
        return

    # Process each batch
    for batch_marker, files in BATCH_ASSIGNMENTS.items():
        for filename in files:
            file_path = e2e_dir / filename
            if file_path.exists():
                if add_batch_marker(file_path, batch_marker):
                    print(f"Added {batch_marker} to {filename}")
            else:
                print(f"Warning: {filename} not found")

    print("\nBatch markers added successfully!")
    print("\nTo run a specific batch:")
    print("  pytest tests/e2e/ -m e2e_batch1")
    print("  pytest tests/e2e/ -m e2e_batch2")
    print("  pytest tests/e2e/ -m e2e_batch3")
    print("  pytest tests/e2e/ -m e2e_batch4")
    print("  pytest tests/e2e/ -m e2e_batch5")
    print("\nOr use the script:")
    print("  ./scripts/run_e2e_tests_batch.sh 1")


if __name__ == "__main__":
    main()
