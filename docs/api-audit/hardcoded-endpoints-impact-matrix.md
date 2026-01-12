# Hardcoded Endpoint URL Impact Matrix

## Summary

- Total References: 167898
- Unique Files: 349
- Unique Endpoints: 2307

### By Priority

- **Critical**: 3
- **High**: 4908
- **Medium**: 162952
- **Low**: 35

### By Category

- **cli**: 113
- **docs**: 162843
- **other**: 5
- **test**: 4937

## Impact Matrix

### cli/README.md

- **Total References**: 4
- **Categories**: cli
- **Priority Breakdown**:
  - High: 4

#### References

- Line 24: `localhost:8000/api/v1` (High)
- Line 32: `localhost:8000/api/v1` (High)
- Line 334: `localhost:8000/api/v1` (High)
- Line 354: `localhost:8000/api/v1` (High)

### cli/build/lib/datahub_cli/commands/assets.py

- **Total References**: 6
- **Categories**: cli
- **Priority Breakdown**:
  - Medium: 6

#### References

- Line 31: `/api/v1/assets/assets/` (Medium)
  - ⚠️ In comment
- Line 82: `/api/v1/assets/assets/{id}/` (Medium)
  - ⚠️ In comment
- Line 125: `/api/v1/assets/assets/` (Medium)
  - ⚠️ In comment
- Line 164: `/api/v1/assets/assets/{id}/` (Medium)
  - ⚠️ In comment
- Line 190: `/api/v1/assets/assets/{id}/` (Medium)
  - ⚠️ In comment
- Line 205: `/api/v1/assets/assets/{id}/activate/` (Medium)
  - ⚠️ In comment

### cli/build/lib/datahub_cli/commands/contracts.py

- **Total References**: 5
- **Categories**: cli
- **Priority Breakdown**:
  - Medium: 5

#### References

- Line 32: `/api/v1/contracts/contracts/` (Medium)
  - ⚠️ In comment
- Line 71: `/api/v1/contracts/contracts/{id}/` (Medium)
  - ⚠️ In comment
- Line 131: `/api/v1/contracts/contracts/` (Medium)
  - ⚠️ In comment
- Line 156: `/api/v1/contracts/contracts/{id}/validate/` (Medium)
  - ⚠️ In comment
- Line 196: `/api/v1/contracts/contracts/{id}/lint/` (Medium)
  - ⚠️ In comment

### cli/build/lib/datahub_cli/commands/files.py

- **Total References**: 6
- **Categories**: cli
- **Priority Breakdown**:
  - Medium: 6

#### References

- Line 30: `/api/v1/files/files/` (Medium)
  - ⚠️ In comment
- Line 83: `/api/v1/files/files/init/` (Medium)
  - ⚠️ In comment
- Line 104: `/api/v1/files/files/{id}/complete/` (Medium)
  - ⚠️ In comment
- Line 128: `/api/v1/files/files/{id}/` (Medium)
  - ⚠️ In comment
- Line 133: `/api/v1/files/files/{id}/download/` (Medium)
  - ⚠️ In comment
- Line 171: `/api/v1/files/files/{id}/` (Medium)
  - ⚠️ In comment

### cli/build/lib/datahub_cli/commands/jobs.py

- **Total References**: 4
- **Categories**: cli
- **Priority Breakdown**:
  - Medium: 4

#### References

- Line 32: `/api/v1/jobs/jobs/` (Medium)
  - ⚠️ In comment
- Line 72: `/api/v1/jobs/jobs/{id}/` (Medium)
  - ⚠️ In comment
- Line 103: `/api/v1/jobs/jobs/{id}/cancel/` (Medium)
  - ⚠️ In comment
- Line 133: `/api/v1/jobs/jobs/{id}/` (Medium)
  - ⚠️ In comment

### cli/build/lib/datahub_cli/config.py

- **Total References**: 1
- **Categories**: cli
- **Priority Breakdown**:
  - High: 1

#### References

- Line 83: `localhost:8000/api/v1` (High)

### cli/datahub_cli/commands/assets.py

- **Total References**: 6
- **Categories**: cli
- **Priority Breakdown**:
  - Medium: 6

#### References

- Line 31: `/api/v1/assets/assets/` (Medium)
  - ⚠️ In comment
- Line 82: `/api/v1/assets/assets/{id}/` (Medium)
  - ⚠️ In comment
- Line 125: `/api/v1/assets/assets/` (Medium)
  - ⚠️ In comment
- Line 164: `/api/v1/assets/assets/{id}/` (Medium)
  - ⚠️ In comment
- Line 190: `/api/v1/assets/assets/{id}/` (Medium)
  - ⚠️ In comment
- Line 205: `/api/v1/assets/assets/{id}/activate/` (Medium)
  - ⚠️ In comment

### cli/datahub_cli/commands/compliance.py

- **Total References**: 3
- **Categories**: cli
- **Priority Breakdown**:
  - Medium: 3

#### References

- Line 54: `/api/v1/compliance/compliance-runs/` (Medium)
  - ⚠️ In comment
- Line 84: `/api/v1/compliance/compliance-runs/{id}/` (Medium)
  - ⚠️ In comment
- Line 157: `/api/v1/compliance/compliance-runs/` (Medium)
  - ⚠️ In comment

### cli/datahub_cli/commands/contracts.py

- **Total References**: 17
- **Categories**: cli
- **Priority Breakdown**:
  - Medium: 17

#### References

- Line 49: `/api/v1/contracts/contracts/` (Medium)
  - ⚠️ In comment
- Line 91: `/api/v1/contracts/contracts/{id}/` (Medium)
  - ⚠️ In comment
- Line 224: `/api/v1/contracts/contracts/` (Medium)
  - ⚠️ In comment
- Line 250: `/api/v1/contracts/contracts/{id}/validate/` (Medium)
  - ⚠️ In comment
- Line 290: `/api/v1/contracts/contracts/{id}/lint/` (Medium)
  - ⚠️ In comment
- Line 373: `/api/v1/contracts/products/` (Medium)
  - ⚠️ In comment
- Line 428: `/api/v1/contracts/{odcs_id}/link-odps/` (Medium)
  - ⚠️ In comment
- Line 511: `/api/v1/contracts/{id}/export/` (Medium)
  - ⚠️ In comment
- Line 644: `/api/v1/contracts/contracts/{id}/` (Medium)
  - ⚠️ In comment
- Line 696: `/api/v1/contracts/contracts/{id}/` (Medium)
  - ⚠️ In comment
- Line 827: `/api/v1/contracts/contracts/{id}/download/` (Medium)
  - ⚠️ In comment
- Line 915: `/api/v1/contracts/{odcs_id}/link-odps/` (Medium)
  - ⚠️ In comment
- Line 956: `/api/v1/contracts/{odcs_id}/unlink-odps/` (Medium)
  - ⚠️ In comment
- Line 990: `/api/v1/contracts/{contract_id}/links/` (Medium)
  - ⚠️ In comment
- Line 1053: `/api/v1/contracts/{contract_id}/payment-gateways/` (Medium)
  - ⚠️ In comment
- Line 1131: `/api/v1/contracts/{contract_id}/product-strategy/` (Medium)
  - ⚠️ In comment
- Line 1292: `/api/v1/contracts/{contract_id}/product-details/?lang={lang}` (Medium)
  - ⚠️ In comment

### cli/datahub_cli/commands/dq.py

- **Total References**: 7
- **Categories**: cli
- **Priority Breakdown**:
  - Medium: 7

#### References

- Line 41: `/api/v1/dq-runs/` (Medium)
  - ⚠️ In comment
- Line 69: `/api/v1/dq-runs/{id}/` (Medium)
  - ⚠️ In comment
- Line 136: `/api/v1/dq-runs/` (Medium)
  - ⚠️ In comment
- Line 186: `/api/v1/dq-runs/{id}/` (Medium)
  - ⚠️ In comment
- Line 231: `/api/v1/dq/scorecards/{asset_id}/` (Medium)
  - ⚠️ In comment
- Line 264: `/api/v1/dq/alerting-rules/` (Medium)
  - ⚠️ In comment
- Line 306: `/api/v1/dq/alerting-rules/` (Medium)
  - ⚠️ In comment

### cli/datahub_cli/commands/files.py

- **Total References**: 6
- **Categories**: cli
- **Priority Breakdown**:
  - Medium: 6

#### References

- Line 30: `/api/v1/files/files/` (Medium)
  - ⚠️ In comment
- Line 83: `/api/v1/files/files/init/` (Medium)
  - ⚠️ In comment
- Line 104: `/api/v1/files/files/{id}/complete/` (Medium)
  - ⚠️ In comment
- Line 128: `/api/v1/files/files/{id}/` (Medium)
  - ⚠️ In comment
- Line 133: `/api/v1/files/files/{id}/download/` (Medium)
  - ⚠️ In comment
- Line 171: `/api/v1/files/files/{id}/` (Medium)
  - ⚠️ In comment

### cli/datahub_cli/commands/governance.py

- **Total References**: 5
- **Categories**: cli
- **Priority Breakdown**:
  - Medium: 5

#### References

- Line 59: `/api/v1/governance/access-requests/` (Medium)
  - ⚠️ In comment
- Line 89: `/api/v1/governance/access-requests/{id}/` (Medium)
  - ⚠️ In comment
- Line 152: `/api/v1/governance/access-requests/` (Medium)
  - ⚠️ In comment
- Line 194: `/api/v1/governance/access-requests/{id}/approve/` (Medium)
  - ⚠️ In comment
- Line 222: `/api/v1/governance/access-requests/{id}/reject/` (Medium)
  - ⚠️ In comment

### cli/datahub_cli/commands/jobs.py

- **Total References**: 4
- **Categories**: cli
- **Priority Breakdown**:
  - Medium: 4

#### References

- Line 32: `/api/v1/jobs/jobs/` (Medium)
  - ⚠️ In comment
- Line 72: `/api/v1/jobs/jobs/{id}/` (Medium)
  - ⚠️ In comment
- Line 103: `/api/v1/jobs/jobs/{id}/cancel/` (Medium)
  - ⚠️ In comment
- Line 133: `/api/v1/jobs/jobs/{id}/` (Medium)
  - ⚠️ In comment

### cli/datahub_cli/commands/mesh.py

- **Total References**: 14
- **Categories**: cli
- **Priority Breakdown**:
  - Medium: 14

#### References

- Line 77: `/api/v1/mesh/domains/` (Medium)
  - ⚠️ In comment
- Line 190: `/api/v1/mesh/domains/` (Medium)
  - ⚠️ In comment
- Line 221: `/api/v1/mesh/domains/{id}/` (Medium)
  - ⚠️ In comment
- Line 314: `/api/v1/mesh/domains/{id}/` (Medium)
  - ⚠️ In comment
- Line 342: `/api/v1/mesh/domains/{id}/` (Medium)
  - ⚠️ In comment
- Line 372: `/api/v1/mesh/topology/` (Medium)
  - ⚠️ In comment
- Line 448: `/api/v1/mesh/topology/{domain_id}/` (Medium)
  - ⚠️ In comment
- Line 546: `/api/v1/mesh/domains/{domain_id}/policies/apply/` (Medium)
  - ⚠️ In comment
- Line 593: `/api/v1/mesh/domains/{domain_id}/policies/` (Medium)
  - ⚠️ In comment
- Line 669: `/api/v1/mesh/domains/{domain_id}/policies/{policy_id}` (Medium)
  - ⚠️ In comment
- Line 707: `/api/v1/mesh/domains/{domain_id}/compliance/check/` (Medium)
  - ⚠️ In comment
- Line 757: `/api/v1/mesh/domains/{domain_id}/compliance/reports/{report_id}/` (Medium)
  - ⚠️ In comment
- Line 761: `/api/v1/mesh/domains/{domain_id}/compliance/reports/` (Medium)
  - ⚠️ In comment
- Line 786: `/api/v1/mesh/domains/{domain_id}/compliance/reports/{report_id}/` (Medium)
  - ⚠️ In comment

### cli/datahub_cli/commands/transformation.py

- **Total References**: 12
- **Categories**: cli
- **Priority Breakdown**:
  - Medium: 12

#### References

- Line 58: `/api/v1/transformation/pipelines/` (Medium)
  - ⚠️ In comment
- Line 170: `/api/v1/transformation/pipelines/` (Medium)
  - ⚠️ In comment
- Line 197: `/api/v1/transformation/pipelines/{id}/` (Medium)
  - ⚠️ In comment
- Line 269: `/api/v1/transformation/pipelines/{id}/` (Medium)
  - ⚠️ In comment
- Line 297: `/api/v1/transformation/pipelines/{id}/` (Medium)
  - ⚠️ In comment
- Line 562: `/api/v1/transformation/pipelines/{id}/preview/` (Medium)
  - ⚠️ In comment
- Line 597: `/api/v1/transformation/previews/{preview_id}/` (Medium)
  - ⚠️ In comment
- Line 658: `/api/v1/transformation/wrangling/` (Medium)
  - ⚠️ In comment
- Line 717: `/api/v1/transformation/wrangling/` (Medium)
  - ⚠️ In comment
- Line 757: `/api/v1/transformation/wrangling/{session_id}/undo/` (Medium)
  - ⚠️ In comment
- Line 783: `/api/v1/transformation/wrangling/{session_id}/redo/` (Medium)
  - ⚠️ In comment
- Line 809: `/api/v1/transformation/wrangling/{session_id}/` (Medium)
  - ⚠️ In comment

### cli/datahub_cli/commands/virtualization.py

- **Total References**: 12
- **Categories**: cli
- **Priority Breakdown**:
  - Medium: 12

#### References

- Line 82: `/api/v1/virtualization/datasets/` (Medium)
  - ⚠️ In comment
- Line 197: `/api/v1/virtualization/datasets/` (Medium)
  - ⚠️ In comment
- Line 225: `/api/v1/virtualization/datasets/{id}/` (Medium)
  - ⚠️ In comment
- Line 308: `/api/v1/virtualization/datasets/{id}/` (Medium)
  - ⚠️ In comment
- Line 337: `/api/v1/virtualization/datasets/{id}/` (Medium)
  - ⚠️ In comment
- Line 397: `/api/v1/virtualization/datasets/{id}/queries/` (Medium)
  - ⚠️ In comment
- Line 443: `/api/v1/virtualization/queries/` (Medium)
  - ⚠️ In comment
- Line 508: `/api/v1/virtualization/queries/{id}/` (Medium)
  - ⚠️ In comment
- Line 543: `/api/v1/virtualization/queries/{id}/cancel/` (Medium)
  - ⚠️ In comment
- Line 588: `/api/v1/virtualization/queries/{id}/result/` (Medium)
  - ⚠️ In comment
- Line 686: `/api/v1/virtualization/topology/` (Medium)
  - ⚠️ In comment
- Line 763: `/api/v1/virtualization/topology/{dataset_id}/` (Medium)
  - ⚠️ In comment

### cli/datahub_cli/config.py

- **Total References**: 1
- **Categories**: cli
- **Priority Breakdown**:
  - High: 1

#### References

- Line 83: `localhost:8000/api/v1` (High)

### cli/tests/README.md

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 48: `localhost:8000/api/v1` (High)

### cli/tests/e2e/test_asset_management_use_cases.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 668: `localhost:8000/api/v1` (High)

### cli/tests/e2e/test_cli_e2e.py

- **Total References**: 5
- **Categories**: test
- **Priority Breakdown**:
  - High: 5

#### References

- Line 149: `localhost:8000/api/v1` (High)
- Line 161: `localhost:8000/api/v1` (High)
- Line 185: `localhost:8000/api/v1` (High)
- Line 213: `localhost:8000/api/v1` (High)
- Line 278: `localhost:8000/api/v1` (High)

### cli/tests/e2e/test_compliance_use_cases.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 28: `localhost:8000/api/v1` (High)

### cli/tests/e2e/test_contract_management_use_cases.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 1242: `localhost:8000/api/v1` (High)

### cli/tests/e2e/test_data_quality_use_cases.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 556: `localhost:8000/api/v1` (High)

### cli/tests/integration/test_commands_integration.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 511: `localhost:8000/api/v1` (High)

### cli/tests/integration/test_commands_real_api.py

- **Total References**: 4
- **Categories**: test
- **Priority Breakdown**:
  - Low: 4

#### References

- Line 102: `/api/v1/assets/assets/` (Low)
  - ⚠️ In comment
- Line 124: `/api/v1/contracts/contracts/` (Low)
  - ⚠️ In comment
- Line 143: `/api/v1/files/files/init/` (Low)
  - ⚠️ In comment
- Line 167: `/api/v1/jobs/jobs/` (Low)
  - ⚠️ In comment

### cli/tests/integration/test_error_handling_integration.py

- **Total References**: 2
- **Categories**: test
- **Priority Breakdown**:
  - High: 2

#### References

- Line 20: `localhost:99999/api/v1` (High)
- Line 174: `localhost:8000/api/v1` (High)

### cli/tests/integration/test_installation_config_auth.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 139: `localhost:8000/api/v1` (High)

### cli/tests/integration/test_mesh_commands_registration.py

- **Total References**: 3
- **Categories**: test
- **Priority Breakdown**:
  - High: 3

#### References

- Line 30: `/api/v1/health/` (High)
- Line 30: `/api/v1/health/` (High)
- Line 30: `localhost:8000/api/v1` (High)

### cli/tests/integration/test_mesh_domains_commands.py

- **Total References**: 11
- **Categories**: test
- **Priority Breakdown**:
  - High: 11

#### References

- Line 33: `/api/v1/` (High)
- Line 33: `localhost:8000/api/v1` (High)
- Line 52: `localhost:8000/api/v1` (High)
- Line 607: `localhost:8000/api/v1` (High)
- Line 788: `localhost:8000/api/v1` (High)
- Line 823: `localhost:8000/api/v1` (High)
- Line 859: `localhost:8000/api/v1` (High)
- Line 903: `localhost:8000/api/v1` (High)
- Line 940: `localhost:8000/api/v1` (High)
- Line 976: `localhost:8000/api/v1` (High)
- Line 1019: `localhost:8000/api/v1` (High)

### cli/tests/integration/test_mesh_policies_commands.py

- **Total References**: 3
- **Categories**: test
- **Priority Breakdown**:
  - High: 3

#### References

- Line 34: `/api/v1/` (High)
- Line 34: `localhost:8000/api/v1` (High)
- Line 53: `localhost:8000/api/v1` (High)

### cli/tests/integration/test_mesh_topology_commands.py

- **Total References**: 3
- **Categories**: test
- **Priority Breakdown**:
  - High: 3

#### References

- Line 33: `/api/v1/` (High)
- Line 33: `localhost:8000/api/v1` (High)
- Line 52: `localhost:8000/api/v1` (High)

### cli/tests/integration/test_odcs_export.py

- **Total References**: 7
- **Categories**: test
- **Priority Breakdown**:
  - High: 6
  - Low: 1

#### References

- Line 30: `/api/v1/` (High)
- Line 30: `localhost:8000/api/v1` (High)
- Line 49: `localhost:8000/api/v1` (High)
- Line 177: `/api/v1/contracts/` (Low)
  - ⚠️ In comment
- Line 178: `/api/v1/contracts/` (High)
- Line 178: `/api/v1/contracts/` (High)
- Line 178: `localhost:8000/api/v1` (High)

### cli/tests/integration/test_odps_cli_workflows.py

- **Total References**: 9
- **Categories**: test
- **Priority Breakdown**:
  - High: 9

#### References

- Line 47: `localhost:8000/api/v1` (High)
- Line 74: `/api/v1/` (High)
- Line 74: `localhost:8000/api/v1` (High)
- Line 152: `/api/v1/assets/assets/` (High)
- Line 152: `/api/v1/assets/assets/` (High)
- Line 152: `localhost:8000/api/v1` (High)
- Line 167: `/api/v1/contracts/` (High)
- Line 167: `/api/v1/contracts/` (High)
- Line 167: `localhost:8000/api/v1` (High)

### cli/tests/integration/test_odps_commands.py

- **Total References**: 3
- **Categories**: test
- **Priority Breakdown**:
  - High: 3

#### References

- Line 33: `/api/v1/` (High)
- Line 33: `localhost:8000/api/v1` (High)
- Line 52: `localhost:8000/api/v1` (High)

### cli/tests/integration/test_odps_info_commands_real_api.py

- **Total References**: 4
- **Categories**: test
- **Priority Breakdown**:
  - High: 4

#### References

- Line 37: `localhost:8000/api/v1` (High)
- Line 60: `/api/v1/` (High)
- Line 60: `localhost:8000/api/v1` (High)
- Line 232: `localhost:8000/api/v1` (High)

### cli/tests/integration/test_output_formatting_integration.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 106: `localhost:8000/api/v1` (High)

### cli/tests/integration/test_payment_gateways_real_api.py

- **Total References**: 3
- **Categories**: test
- **Priority Breakdown**:
  - High: 3

#### References

- Line 32: `/api/v1/` (High)
- Line 32: `localhost:8000/api/v1` (High)
- Line 51: `localhost:8000/api/v1` (High)

### cli/tests/integration/test_product_details_real_api.py

- **Total References**: 3
- **Categories**: test
- **Priority Breakdown**:
  - High: 3

#### References

- Line 32: `/api/v1/` (High)
- Line 32: `localhost:8000/api/v1` (High)
- Line 51: `localhost:8000/api/v1` (High)

### cli/tests/integration/test_product_strategy_real_api.py

- **Total References**: 3
- **Categories**: test
- **Priority Breakdown**:
  - High: 3

#### References

- Line 32: `/api/v1/` (High)
- Line 32: `localhost:8000/api/v1` (High)
- Line 51: `localhost:8000/api/v1` (High)

### cli/tests/integration/test_transformation_commands.py

- **Total References**: 4
- **Categories**: test
- **Priority Breakdown**:
  - High: 4

#### References

- Line 34: `/api/v1/` (High)
- Line 34: `localhost:8000/api/v1` (High)
- Line 52: `localhost:8000/api/v1` (High)
- Line 280: `localhost:8000/api/v1` (High)

### cli/tests/integration/test_virtualization_commands_registration.py

- **Total References**: 3
- **Categories**: test
- **Priority Breakdown**:
  - High: 3

#### References

- Line 30: `/api/v1/health/` (High)
- Line 30: `/api/v1/health/` (High)
- Line 30: `localhost:8000/api/v1` (High)

### cli/tests/integration/test_virtualization_datasets_commands.py

- **Total References**: 4
- **Categories**: test
- **Priority Breakdown**:
  - High: 4

#### References

- Line 35: `/api/v1/` (High)
- Line 35: `localhost:8000/api/v1` (High)
- Line 53: `localhost:8000/api/v1` (High)
- Line 282: `localhost:8000/api/v1` (High)

### cli/tests/integration/test_virtualization_queries_commands.py

- **Total References**: 5
- **Categories**: test
- **Priority Breakdown**:
  - High: 5

#### References

- Line 35: `/api/v1/` (High)
- Line 35: `localhost:8000/api/v1` (High)
- Line 53: `localhost:8000/api/v1` (High)
- Line 267: `localhost:8000/api/v1` (High)
- Line 313: `localhost:8000/api/v1` (High)

### cli/tests/integration/test_virtualization_topology_commands.py

- **Total References**: 6
- **Categories**: test
- **Priority Breakdown**:
  - High: 6

#### References

- Line 34: `/api/v1/` (High)
- Line 34: `/api/v1/` (High)
- Line 34: `localhost:8000/api/v1` (High)
- Line 61: `localhost:8000/api/v1` (High)
- Line 309: `localhost:8000/api/v1` (High)
- Line 319: `localhost:8000/api/v1` (High)

### cli/tests/test_env_config.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 41: `localhost:8001/api/v1` (High)

### cli/tests/unit/test_config.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 41: `localhost:8000/api/v1` (High)

### cli/tests/unit/test_configuration.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 273: `localhost:8000/api/v1` (High)

### docs/API_BEST_PRACTICES.md

- **Total References**: 7
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 7

#### References

- Line 28: `/api/v1/contracts/` (Medium)
- Line 28: `/api/v1/contracts/` (Medium)
- Line 28: `api.example.com/api/v1` (Medium)
- Line 173: `/api/v1/contracts/?page=1&page_size=50` (Medium)
- Line 210: `/api/v1/contracts/?owner_email=user@example.com&tag=production` (Medium)
- Line 218: `/api/v1/contracts/?ordering=-created_at,quality_score` (Medium)
- Line 324: `/api/v1/contracts/` (Medium)

### docs/API_ENDPOINTS_REFERENCE.md

- **Total References**: 84
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 84

#### References

- Line 21: `/api/v1/contracts/` (Medium)
- Line 21: `/api/v1/contracts/` (Medium)
- Line 71: `/api/v1/contracts/{id}/` (Medium)
- Line 71: `/api/v1/contracts/{id}/` (Medium)
- Line 99: `/api/v1/contracts/` (Medium)
- Line 99: `/api/v1/contracts/` (Medium)
- Line 124: `/api/v1/contracts/{id}/` (Medium)
- Line 124: `/api/v1/contracts/{id}/` (Medium)
- Line 146: `/api/v1/contracts/{id}/` (Medium)
- Line 146: `/api/v1/contracts/{id}/` (Medium)
- Line 158: `/api/v1/contracts/products/` (Medium)
- Line 158: `/api/v1/contracts/products/` (Medium)
- Line 207: `/api/v1/contracts/products/` (Medium)
- Line 207: `/api/v1/contracts/products/` (Medium)
- Line 207: `api.example.com/api/v1` (Medium)
- Line 232: `/api/v1/contracts/{id}/export/` (Medium)
- Line 232: `/api/v1/contracts/{id}/export/` (Medium)
- Line 333: `/api/v1/contracts/{id}/export/?format=odps&output_format=json&version=4.1` (Medium)
- Line 333: `/api/v1/contracts/{id}/export/?format=odps&output_format=json&version=4.1` (Medium)
- Line 333: `api.example.com/api/v1` (Medium)
- ... and 64 more references

### docs/API_ERROR_CODES.md

- **Total References**: 6
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 6

#### References

- Line 441: `/api/v1/contracts/` (Medium)
- Line 441: `/api/v1/contracts/` (Medium)
- Line 441: `api.example.com/api/v1` (Medium)
- Line 480: `/api/v1/contracts/` (Medium)
- Line 480: `/api/v1/contracts/` (Medium)
- Line 480: `api.example.com/api/v1` (Medium)

### docs/API_REFERENCE.md

- **Total References**: 74
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 74

#### References

- Line 27: `/api/v1/auth/login/` (Medium)
- Line 27: `/api/v1/auth/login/` (Medium)
- Line 27: `localhost:8000/api/v1` (Medium)
- Line 33: `/api/v1/contracts/` (Medium)
- Line 33: `/api/v1/contracts/` (Medium)
- Line 33: `localhost:8000/api/v1` (Medium)
- Line 40: `/api/v1/contracts/` (Medium)
- Line 40: `/api/v1/contracts/` (Medium)
- Line 40: `localhost:8000/api/v1` (Medium)
- Line 54: `/api/v1/contracts/` (Medium)
- Line 55: `/api/v1/contracts/` (Medium)
- Line 56: `/api/v1/contracts/{id}/` (Medium)
- Line 57: `/api/v1/contracts/{id}/` (Medium)
- Line 58: `/api/v1/contracts/{id}/` (Medium)
- Line 59: `/api/v1/contracts/{id}/validate/` (Medium)
- Line 60: `/api/v1/contracts/{id}/lint/` (Medium)
- Line 61: `/api/v1/contracts/{id}/convert/` (Medium)
- Line 64: `/api/v1/assets/` (Medium)
- Line 65: `/api/v1/assets/` (Medium)
- Line 66: `/api/v1/assets/{id}/` (Medium)
- ... and 54 more references

### docs/API_STANDARDS.md

- **Total References**: 17
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 17

#### References

- Line 66: `/api/v1/resources/?page=2` (Medium)
- Line 66: `/api/v1/resources/?page=2` (Medium)
- Line 166: `/api/v1/resources/?cursor=eyJjcmVhdGVkX2F0IjoiMjAyNS0wMS0xNVQxMDozMDowMFoifQ==&page_size=50` (Medium)
- Line 188: `/api/v1/resources/?page=2&page_size=50` (Medium)
- Line 199: `/api/v1/resources/?page=3` (Medium)
- Line 199: `/api/v1/resources/?page=3` (Medium)
- Line 200: `/api/v1/resources/?page=1` (Medium)
- Line 200: `/api/v1/resources/?page=1` (Medium)
- Line 246: `/api/v1/resources/?status=active` (Medium)
- Line 249: `/api/v1/resources/?name__iexact=test` (Medium)
- Line 252: `/api/v1/resources/?description__contains=data` (Medium)
- Line 255: `/api/v1/resources/?status__in=active,pending` (Medium)
- Line 258: `/api/v1/resources/?created_at__gte=2025-01-01&created_at__lte=2025-01-31` (Medium)
- Line 261: `/api/v1/resources/?deleted_at__isnull=true` (Medium)
- Line 291: `/api/v1/resources/?ordering=name` (Medium)
- Line 294: `/api/v1/resources/?ordering=-created_at` (Medium)
- Line 297: `/api/v1/resources/?ordering=status,-created_at,name` (Medium)

### docs/API_TESTING_GUIDE.md

- **Total References**: 33
- **Categories**: test
- **Priority Breakdown**:
  - High: 33

#### References

- Line 25: `localhost:8000/api/v1` (High)
- Line 46: `/api/v1/auth/login/` (High)
- Line 46: `/api/v1/auth/login/` (High)
- Line 46: `localhost:8000/api/v1` (High)
- Line 53: `/api/v1/contracts/` (High)
- Line 53: `/api/v1/contracts/` (High)
- Line 53: `localhost:8000/api/v1` (High)
- Line 66: `/api/v1/auth/login/` (High)
- Line 96: `/api/v1/auth/refresh/` (High)
- Line 180: `/api/v1/auth/login/` (High)
- Line 180: `/api/v1/auth/login/` (High)
- Line 180: `localhost:8000/api/v1` (High)
- Line 185: `/api/v1/contracts/` (High)
- Line 185: `/api/v1/contracts/` (High)
- Line 185: `localhost:8000/api/v1` (High)
- Line 189: `/api/v1/contracts/` (High)
- Line 189: `/api/v1/contracts/` (High)
- Line 189: `localhost:8000/api/v1` (High)
- Line 205: `localhost:8000/api/v1` (High)
- Line 227: `localhost:8000/api/v1` (High)
- ... and 13 more references

### docs/API_USABILITY.md

- **Total References**: 28
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 28

#### References

- Line 50: `/api/v1/openapi.yaml` (Medium)
- Line 50: `/api/v1/openapi.yaml` (Medium)
- Line 55: `/api/v1/auth/` (Medium)
- Line 55: `/api/v1/auth/` (Medium)
- Line 56: `/api/v1/assets/` (Medium)
- Line 56: `/api/v1/assets/` (Medium)
- Line 57: `/api/v1/contracts/` (Medium)
- Line 57: `/api/v1/contracts/` (Medium)
- Line 58: `/api/v1/datasets/` (Medium)
- Line 58: `/api/v1/datasets/` (Medium)
- Line 59: `/api/v1/jobs/` (Medium)
- Line 59: `/api/v1/jobs/` (Medium)
- Line 69: `/api/v1/openapi.json` (Medium)
- Line 69: `/api/v1/openapi.json` (Medium)
- Line 70: `/api/v1/openapi.yaml` (Medium)
- Line 70: `/api/v1/openapi.yaml` (Medium)
- Line 104: `/api/v1/{resource}/` (Medium)
- Line 104: `/api/v1/{resource}/` (Medium)
- Line 105: `/api/v1/{resource}/{id}/` (Medium)
- Line 105: `/api/v1/{resource}/{id}/` (Medium)
- ... and 8 more references

### docs/API_VERSIONING_POLICY.md

- **Total References**: 12
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 12

#### References

- Line 35: `/api/v1/...` (Medium)
- Line 35: `/api/v1/...` (Medium)
- Line 70: `/api/v1/assets/` (Medium)
- Line 80: `/api/v1/assets/` (Medium)
- Line 115: `/api/v1/new-feature/` (Medium)
- Line 115: `/api/v1/new-feature/` (Medium)
- Line 211: `/api/v1/old-endpoint/` (Medium)
  - ⚠️ Deprecated context
- Line 211: `/api/v1/old-endpoint/` (Medium)
  - ⚠️ Deprecated context
- Line 329: `/api/v1/analytics/` (Medium)
- Line 329: `/api/v1/analytics/` (Medium)
- Line 345: `/api/v1/old-endpoint/` (Medium)
- Line 345: `/api/v1/old-endpoint/` (Medium)

### docs/DOCKER_COMPOSE_DEPLOYMENT.md

- **Total References**: 9
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 9

#### References

- Line 567: `/api/v1/contracts/` (Medium)
- Line 567: `/api/v1/contracts/` (Medium)
- Line 567: `localhost:8000/api/v1` (Medium)
- Line 599: `/api/v1/targets` (Medium)
- Line 599: `/api/v1/targets` (Medium)
- Line 599: `localhost:9090/api/v1` (Medium)
- Line 602: `/api/v1/query?query=up` (Medium)
- Line 602: `/api/v1/query?query=up` (Medium)
- Line 602: `localhost:9090/api/v1` (Medium)

### docs/FEATURES.md

- **Total References**: 45
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 45

#### References

- Line 38: `/api/v1/contracts/` (Medium)
- Line 39: `/api/v1/contracts/` (Medium)
- Line 40: `/api/v1/contracts/{id}/` (Medium)
- Line 41: `/api/v1/contracts/{id}/` (Medium)
- Line 42: `/api/v1/contracts/{id}/` (Medium)
- Line 43: `/api/v1/contracts/{id}/validate/` (Medium)
- Line 44: `/api/v1/contracts/{id}/lint/` (Medium)
- Line 45: `/api/v1/contracts/{id}/convert/` (Medium)
- Line 70: `/api/v1/assets/` (Medium)
- Line 71: `/api/v1/assets/` (Medium)
- Line 72: `/api/v1/assets/{id}/` (Medium)
- Line 73: `/api/v1/assets/{id}/` (Medium)
- Line 74: `/api/v1/assets/{id}/` (Medium)
- Line 75: `/api/v1/assets/{id}/datasets/` (Medium)
- Line 76: `/api/v1/assets/{id}/contracts/` (Medium)
- Line 77: `/api/v1/assets/{id}/activate/` (Medium)
- Line 102: `/api/v1/datasets/` (Medium)
- Line 103: `/api/v1/datasets/` (Medium)
- Line 104: `/api/v1/datasets/{id}/` (Medium)
- Line 105: `/api/v1/datasets/{id}/` (Medium)
- ... and 25 more references

### docs/GRAPHQL_API.md

- **Total References**: 2
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 2

#### References

- Line 1113: `/api/v1/assets/` (Medium)
- Line 1113: `/api/v1/assets/` (Medium)

### docs/MONITORING.md

- **Total References**: 4
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 4

#### References

- Line 54: `/api/v1/query?query=http_requests_total` (Medium)
- Line 54: `/api/v1/query?query=http_requests_total` (Medium)
- Line 54: `localhost:9090/api/v1` (Medium)
- Line 138: `/api/v1/contracts/` (Medium)
  - ⚠️ In comment

### docs/ODPS_INTEGRATION_GUIDE.md

- **Total References**: 51
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 51

#### References

- Line 41: `/api/v1/contracts/products/` (Medium)
- Line 55: `/api/v1/contracts/products/` (Medium)
- Line 55: `/api/v1/contracts/products/` (Medium)
- Line 55: `api.example.com/api/v1` (Medium)
- Line 88: `/api/v1/contracts/` (Medium)
- Line 102: `/api/v1/contracts/` (Medium)
- Line 102: `/api/v1/contracts/` (Medium)
- Line 102: `api.example.com/api/v1` (Medium)
- Line 449: `/api/v1/contracts/{id}/export/` (Medium)
- Line 458: `/api/v1/contracts/{id}/export/?format=odps&output_format=json&version=4.1` (Medium)
- Line 458: `/api/v1/contracts/{id}/export/?format=odps&output_format=json&version=4.1` (Medium)
- Line 458: `api.example.com/api/v1` (Medium)
- Line 484: `/api/v1/contracts/{id}/export/` (Medium)
- Line 493: `/api/v1/contracts/{id}/export/?format=odps&output_format=yaml` (Medium)
- Line 493: `/api/v1/contracts/{id}/export/?format=odps&output_format=yaml` (Medium)
- Line 493: `api.example.com/api/v1` (Medium)
- Line 514: `/api/v1/contracts/{id}/download/` (Medium)
- Line 523: `/api/v1/contracts/{id}/download/?format=odps&output_format=json` (Medium)
- Line 523: `/api/v1/contracts/{id}/download/?format=odps&output_format=json` (Medium)
- Line 523: `api.example.com/api/v1` (Medium)
- ... and 31 more references

### docs/README.md

- **Total References**: 1
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 1

#### References

- Line 123: `localhost:8000/api/v1` (Medium)

### docs/RUNBOOKS.md

- **Total References**: 3
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 3

#### References

- Line 383: `/api/v1/targets` (Medium)
- Line 383: `/api/v1/targets` (Medium)
- Line 383: `localhost:9090/api/v1` (Medium)

### docs/SERVICES_ARCHITECTURE.md

- **Total References**: 25
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 25

#### References

- Line 98: `/api/v1/assets/*` (Medium)
- Line 98: `/api/v1/assets/*` (Medium)
- Line 99: `/api/v1/contracts/*` (Medium)
- Line 99: `/api/v1/contracts/*` (Medium)
- Line 100: `/api/v1/datasets/*` (Medium)
- Line 100: `/api/v1/datasets/*` (Medium)
- Line 101: `/api/v1/files/*` (Medium)
- Line 101: `/api/v1/files/*` (Medium)
- Line 102: `/api/v1/marketplace/*` (Medium)
- Line 102: `/api/v1/marketplace/*` (Medium)
- Line 103: `/api/v1/jobs/*` (Medium)
- Line 103: `/api/v1/jobs/*` (Medium)
- Line 104: `/api/v1/tenants/*` (Medium)
- Line 104: `/api/v1/tenants/*` (Medium)
- Line 105: `/api/v1/users/*` (Medium)
- Line 105: `/api/v1/users/*` (Medium)
- Line 256: `/api/v1/semantic/*` (Medium)
- Line 256: `/api/v1/semantic/*` (Medium)
- Line 257: `/api/v1/semantic/resources/` (Medium)
- Line 258: `/api/v1/semantic/resources/{id}/` (Medium)
- ... and 5 more references

### docs/SERVICES_STARTUP_SUMMARY.md

- **Total References**: 15
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 15

#### References

- Line 79: `/api/v1/docs` (Medium)
- Line 79: `/api/v1/docs` (Medium)
- Line 79: `localhost:8000/api/v1` (Medium)
- Line 80: `/api/v1/health` (Medium)
- Line 80: `/api/v1/health` (Medium)
- Line 80: `localhost:8000/api/v1` (Medium)
- Line 128: `/api/v1/health` (Medium)
- Line 128: `/api/v1/health` (Medium)
- Line 128: `localhost:8000/api/v1` (Medium)
- Line 165: `/api/v1/health` (Medium)
- Line 165: `/api/v1/health` (Medium)
- Line 165: `localhost:8000/api/v1` (Medium)
- Line 183: `/api/v1/docs` (Medium)
- Line 183: `/api/v1/docs` (Medium)
- Line 183: `localhost:8000/api/v1` (Medium)

### docs/SERVICE_DEPLOYMENT_GUIDE.md

- **Total References**: 6
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 6

#### References

- Line 1030: `/api/v1/contracts/123` (Medium)
- Line 1030: `/api/v1/contracts/123` (Medium)
- Line 1033: `/api/v1/contracts` (Medium)
- Line 1033: `/api/v1/contracts` (Medium)
- Line 1198: `/api/v1/contracts/123` (Medium)
- Line 1198: `/api/v1/contracts/123` (Medium)

### docs/SERVICE_STARTUP_GUIDE.md

- **Total References**: 16
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 16

#### References

- Line 69: `/api/v1/` (Medium)
- Line 69: `localhost:8000/api/v1` (Medium)
- Line 70: `/api/v1/docs` (Medium)
- Line 70: `/api/v1/docs` (Medium)
- Line 70: `localhost:8000/api/v1` (Medium)
- Line 243: `/api/v1/health` (Medium)
- Line 243: `/api/v1/health` (Medium)
- Line 243: `localhost:8000/api/v1` (Medium)
- Line 395: `/api/v1/docs` (Medium)
- Line 395: `/api/v1/docs` (Medium)
- Line 395: `localhost:8000/api/v1` (Medium)
- Line 420: `/api/v1/` (Medium)
- Line 420: `localhost:8000/api/v1` (Medium)
- Line 421: `/api/v1/docs` (Medium)
- Line 421: `/api/v1/docs` (Medium)
- Line 421: `localhost:8000/api/v1` (Medium)

### docs/TESTING_GUIDE.md

- **Total References**: 2
- **Categories**: test
- **Priority Breakdown**:
  - High: 2

#### References

- Line 135: `/api/v1/contracts/` (High)
- Line 135: `/api/v1/contracts/` (High)

### docs/TROUBLESHOOTING.md

- **Total References**: 3
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 3

#### References

- Line 206: `/api/v1/auth/me/` (Medium)
- Line 206: `/api/v1/auth/me/` (Medium)
- Line 206: `localhost:8000/api/v1` (Medium)

### docs/UI/ANALYTICS_INTEGRATION.md

- **Total References**: 6
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 6

#### References

- Line 122: `/api/v1/analytics/events/` (Medium)
- Line 122: `/api/v1/analytics/events/` (Medium)
- Line 306: `/api/v1/analytics/identify/` (Medium)
- Line 306: `/api/v1/analytics/identify/` (Medium)
- Line 487: `/api/v1/analytics/web-vitals/` (Medium)
- Line 487: `/api/v1/analytics/web-vitals/` (Medium)

### docs/UI/CONTRACT_EDITOR_SPECIFICATION.md

- **Total References**: 4
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 4

#### References

- Line 540: `/api/v1/contracts/{id}/` (Medium)
- Line 543: `/api/v1/contracts/{id}/` (Medium)
- Line 546: `/api/v1/contracts/{id}/validate/` (Medium)
- Line 552: `/api/v1/datasets/{id}/schema/` (Medium)

### docs/UI/FRONTEND_ARCHITECTURE.md

- **Total References**: 11
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 11

#### References

- Line 362: `/api/v1/assets` (Medium)
- Line 362: `/api/v1/assets` (Medium)
- Line 363: `/api/v1/assets/${id}` (Medium)
- Line 363: `/api/v1/assets/${id}` (Medium)
- Line 364: `/api/v1/assets` (Medium)
- Line 364: `/api/v1/assets` (Medium)
- Line 366: `/api/v1/assets/${id}` (Medium)
- Line 366: `/api/v1/assets/${id}` (Medium)
- Line 367: `/api/v1/assets/${id}` (Medium)
- Line 367: `/api/v1/assets/${id}` (Medium)
- Line 670: `localhost:8000/api/v1` (Medium)

### docs/UI/TESTING_STRATEGY.md

- **Total References**: 20
- **Categories**: test
- **Priority Breakdown**:
  - High: 20

#### References

- Line 165: `/api/v1/assets/assets/` (High)
- Line 165: `/api/v1/assets/assets/` (High)
- Line 305: `/api/v1/assets/assets/` (High)
- Line 305: `/api/v1/assets/assets/` (High)
- Line 330: `/api/v1/assets/assets/` (High)
- Line 330: `/api/v1/assets/assets/` (High)
- Line 364: `/api/v1/assets/assets/` (High)
- Line 364: `/api/v1/assets/assets/` (High)
- Line 488: `/api/v1/auth/login/` (High)
- Line 488: `/api/v1/auth/login/` (High)
- Line 499: `/api/v1/assets/assets/` (High)
- Line 499: `/api/v1/assets/assets/` (High)
- Line 512: `/api/v1/jobs/${jobId}/` (High)
- Line 512: `/api/v1/jobs/${jobId}/` (High)
- Line 691: `/api/v1/assets/assets/` (High)
- Line 691: `/api/v1/assets/assets/` (High)
- Line 747: `/api/v1/assets/assets/` (High)
- Line 747: `/api/v1/assets/assets/` (High)
- Line 754: `/api/v1/assets/assets/` (High)
- Line 754: `/api/v1/assets/assets/` (High)

### docs/UI/UI_SPECIFICATIONS.md

- **Total References**: 1
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 1

#### References

- Line 346: `/api/v1/assets` (Medium)

### docs/WEBHOOK_API.md

- **Total References**: 22
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 22

#### References

- Line 264: `/api/v1/webhooks/` (Medium)
  - ⚠️ In comment
- Line 295: `/api/v1/webhooks/` (Medium)
  - ⚠️ In comment
- Line 319: `/api/v1/webhooks/{id}/` (Medium)
  - ⚠️ In comment
- Line 323: `/api/v1/webhooks/{id}/` (Medium)
  - ⚠️ In comment
- Line 327: `/api/v1/webhooks/{id}/` (Medium)
  - ⚠️ In comment
- Line 331: `/api/v1/webhooks/{id}/test/` (Medium)
  - ⚠️ In comment
- Line 335: `/api/v1/webhooks/{id}/deliveries/` (Medium)
  - ⚠️ In comment
- Line 357: `/api/v1/webhooks/event-types/` (Medium)
  - ⚠️ In comment
- Line 393: `/api/v1/webhook-deliveries/` (Medium)
  - ⚠️ In comment
- Line 397: `/api/v1/webhook-deliveries/{id}/` (Medium)
  - ⚠️ In comment
- Line 401: `/api/v1/webhook-deliveries/{id}/retry/` (Medium)
  - ⚠️ In comment
- Line 645: `/api/v1/webhooks/` (Medium)
- Line 645: `/api/v1/webhooks/` (Medium)
- Line 645: `api.example.com/api/v1` (Medium)
- Line 661: `/api/v1/webhooks/` (Medium)
- Line 661: `/api/v1/webhooks/` (Medium)
- Line 661: `api.example.com/api/v1` (Medium)
- Line 694: `/api/v1/webhooks/` (Medium)
- Line 694: `/api/v1/webhooks/` (Medium)
- Line 694: `api.example.com/api/v1` (Medium)
- ... and 2 more references

### docs/api-audit/CONSOLIDATION_SUMMARY.md

- **Total References**: 4
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 4

#### References

- Line 208: `/api/v1/openapi.json` (Medium)
- Line 208: `/api/v1/openapi.yaml` (Medium)
- Line 208: `/api/v1/openapi.json` (Medium)
- Line 208: `/api/v1/openapi.yaml` (Medium)

### docs/api-audit/ENDPOINT_TESTING_SUMMARY.md

- **Total References**: 2
- **Categories**: test
- **Priority Breakdown**:
  - High: 2

#### References

- Line 154: `/api/v1/assets/` (High)
- Line 154: `/api/v1/assets/` (High)

### docs/api-audit/GAP_ANALYSIS_SUMMARY.md

- **Total References**: 44
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 44

#### References

- Line 33: `/api/v1/auth/register/` (Medium)
- Line 33: `/api/v1/auth/me/` (Medium)
- Line 33: `/api/v1/auth/register/` (Medium)
- Line 33: `/api/v1/auth/me/` (Medium)
- Line 70: `/api/v1/auth/register/` (Medium)
- Line 70: `/api/v1/auth/register/` (Medium)
- Line 80: `/api/v1/auth/me/` (Medium)
- Line 80: `/api/v1/auth/me/` (Medium)
- Line 93: `/api/v1/assets/` (Medium)
- Line 93: `/api/v1/assets/` (Medium)
- Line 94: `/api/v1/assets/{id}/activate/` (Medium)
- Line 94: `/api/v1/assets/{id}/activate/` (Medium)
- Line 95: `/api/v1/auth/api-keys/` (Medium)
- Line 95: `/api/v1/auth/api-keys/` (Medium)
- Line 96: `/api/v1/contracts/{id}/validate/` (Medium)
- Line 96: `/api/v1/contracts/{id}/validate/` (Medium)
- Line 100: `/api/v1/marketplace/listings/` (Medium)
- Line 100: `/api/v1/marketplace/listings/` (Medium)
- Line 101: `/api/v1/search/search/` (Medium)
- Line 101: `/api/v1/search/search/` (Medium)
- ... and 24 more references

### docs/api-audit/GAP_DETAILS_SUMMARY.md

- **Total References**: 112
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 112

#### References

- Line 77: `/api/v1/auth/register/` (Medium)
- Line 77: `/api/v1/auth/register/` (Medium)
- Line 78: `/api/v1/auth/me/` (Medium)
- Line 78: `/api/v1/auth/me/` (Medium)
- Line 79: `/api/v1/auth/api-keys/` (Medium)
- Line 79: `/api/v1/auth/api-keys/` (Medium)
- Line 80: `/api/v1/assets/{id}/activate/` (Medium)
- Line 80: `/api/v1/assets/{id}/activate/` (Medium)
- Line 81: `/api/v1/assets/` (Medium)
- Line 81: `/api/v1/assets/` (Medium)
- Line 82: `/api/v1/marketplace/listings/` (Medium)
- Line 82: `/api/v1/marketplace/listings/` (Medium)
- Line 83: `/api/v1/ai/natural-language-search/` (Medium)
- Line 83: `/api/v1/ai/natural-language-search/` (Medium)
- Line 84: `/api/v1/marketplace/listings/{id}/preview/` (Medium)
- Line 84: `/api/v1/marketplace/listings/{id}/preview/` (Medium)
- Line 85: `/api/v1/compliance/compliance-runs/{id}/results/` (Medium)
- Line 85: `/api/v1/compliance/compliance-runs/{id}/results/` (Medium)
- Line 87: `/api/v1/ai/schema-matching/` (Medium)
- Line 87: `/api/v1/ai/schema-matching/` (Medium)
- ... and 92 more references

### docs/api-audit/analyze-api-dependencies.py

- **Total References**: 116
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 116

#### References

- Line 108: `/api/v1/assets/` (Medium)
- Line 117: `/api/v1/files/upload/` (Medium)
- Line 126: `/api/v1/datasets/` (Medium)
- Line 135: `/api/v1/contracts/` (Medium)
- Line 287: `/api/v1/auth/me/` (Medium)
- Line 288: `/api/v1/auth/login/` (Medium)
- Line 296: `/api/v1/auth/refresh/` (Medium)
- Line 297: `/api/v1/auth/login/` (Medium)
- Line 305: `/api/v1/auth/logout/` (Medium)
- Line 306: `/api/v1/auth/login/` (Medium)
- Line 314: `/api/v1/auth/api-keys/` (Medium)
- Line 315: `/api/v1/auth/login/` (Medium)
- Line 323: `/api/v1/auth/api-keys/` (Medium)
- Line 324: `/api/v1/auth/login/` (Medium)
- Line 333: `/api/v1/assets/{id}/activate/` (Medium)
- Line 334: `/api/v1/assets/` (Medium)
- Line 342: `/api/v1/assets/{id}/activate/` (Medium)
- Line 343: `/api/v1/contracts/` (Medium)
- Line 352: `/api/v1/contracts/{id}/validate/` (Medium)
- Line 353: `/api/v1/contracts/` (Medium)
- ... and 96 more references

### docs/api-audit/api-dependencies.md

- **Total References**: 185
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 185

#### References

- Line 31: `/api/v1/datasets/` (Medium)
- Line 31: `/api/v1/files/upload/` (Medium)
- Line 34: `/api/v1/auth/me/` (Medium)
- Line 34: `/api/v1/auth/login/` (Medium)
- Line 37: `/api/v1/assets/{id}/activate/` (Medium)
- Line 50: `/api/v1/auth/api-keys/` (Medium)
- Line 50: `/api/v1/auth/login/` (Medium)
- Line 51: `/api/v1/auth/me/` (Medium)
- Line 51: `/api/v1/auth/login/` (Medium)
- Line 52: `/api/v1/jobs/{id}/` (Medium)
- Line 52: `/api/v1/jobs/` (Medium)
- Line 53: `/api/v1/contracts/{id}/` (Medium)
- Line 53: `/api/v1/contracts/` (Medium)
- Line 54: `/api/v1/ai/schema-matching/` (Medium)
- Line 54: `/api/v1/datasets/` (Medium)
- Line 55: `/api/v1/assets/{id}/activate/` (Medium)
- Line 55: `/api/v1/contracts/` (Medium)
- Line 56: `/api/v1/assets/{id}/activate/` (Medium)
- Line 56: `/api/v1/assets/` (Medium)
- Line 57: `/api/v1/assets/{id}/activate/` (Medium)
- ... and 165 more references

### docs/api-audit/api-development-backlog.md

- **Total References**: 152
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 152

#### References

- Line 88: `/api/v1/auth/register/` (Medium)
  - ⚠️ In comment
- Line 88: `/api/v1/auth/register/` (Medium)
  - ⚠️ In comment
- Line 192: `/api/v1/auth/me/` (Medium)
  - ⚠️ In comment
- Line 192: `/api/v1/auth/me/` (Medium)
  - ⚠️ In comment
- Line 266: `/api/v1/auth/login/` (Medium)
- Line 269: `/api/v1/auth/login/` (Medium)
- Line 294: `/api/v1/assets/` (Medium)
  - ⚠️ In comment
- Line 294: `/api/v1/assets/` (Medium)
  - ⚠️ In comment
- Line 346: `/api/v1/assets/{id}/activate/` (Medium)
  - ⚠️ In comment
- Line 346: `/api/v1/assets/{id}/activate/` (Medium)
  - ⚠️ In comment
- Line 386: `/api/v1/assets/` (Medium)
- Line 387: `/api/v1/contracts/` (Medium)
- Line 409: `/api/v1/auth/api-keys/` (Medium)
  - ⚠️ In comment
- Line 409: `/api/v1/auth/api-keys/` (Medium)
  - ⚠️ In comment
- Line 453: `/api/v1/contracts/{id}/validate/` (Medium)
  - ⚠️ In comment
- Line 453: `/api/v1/contracts/{id}/validate/` (Medium)
  - ⚠️ In comment
- Line 488: `/api/v1/contracts/` (Medium)
- Line 510: `/api/v1/assets/` (Medium)
  - ⚠️ In comment
- Line 510: `/api/v1/assets/` (Medium)
  - ⚠️ In comment
- Line 551: `/api/v1/assets/{id}/activate/` (Medium)
  - ⚠️ In comment
- ... and 132 more references

### docs/api-audit/api-development-timeline.md

- **Total References**: 97
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 97

#### References

- Line 52: `/api/v1/assets` (Medium)
- Line 52: `/api/v1/assets` (Medium)
- Line 53: `/api/v1/assets/{id}/activate` (Medium)
- Line 53: `/api/v1/assets/{id}/activate` (Medium)
- Line 54: `/api/v1/auth/api-keys` (Medium)
- Line 54: `/api/v1/auth/api-keys` (Medium)
- Line 55: `/api/v1/assets` (Medium)
- Line 55: `/api/v1/assets` (Medium)
- Line 56: `/api/v1/auth/register` (Medium)
- Line 56: `/api/v1/auth/register` (Medium)
- Line 62: `/api/v1/auth/me` (Medium)
- Line 62: `/api/v1/auth/login` (Medium)
- Line 62: `/api/v1/auth/me` (Medium)
- Line 68: `/api/v1/contracts/{id}/validate` (Medium)
- Line 68: `/api/v1/contracts` (Medium)
- Line 68: `/api/v1/contracts/{id}/validate` (Medium)
- Line 82: `/api/v1/marketplace/listings` (Medium)
- Line 82: `/api/v1/marketplace/listings` (Medium)
- Line 83: `/api/v1/search/search` (Medium)
- Line 83: `/api/v1/search/search` (Medium)
- ... and 77 more references

### docs/api-audit/api-effort-estimates-summary.md

- **Total References**: 64
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 64

#### References

- Line 54: `/api/v1/auth/register/` (Medium)
  - ⚠️ In comment
- Line 54: `/api/v1/auth/register/` (Medium)
  - ⚠️ In comment
- Line 77: `/api/v1/auth/me/` (Medium)
  - ⚠️ In comment
- Line 77: `/api/v1/auth/me/` (Medium)
  - ⚠️ In comment
- Line 99: `/api/v1/assets/` (Medium)
  - ⚠️ In comment
- Line 99: `/api/v1/assets/` (Medium)
  - ⚠️ In comment
- Line 121: `/api/v1/assets/{id}/activate/` (Medium)
  - ⚠️ In comment
- Line 121: `/api/v1/assets/{id}/activate/` (Medium)
  - ⚠️ In comment
- Line 148: `/api/v1/auth/api-keys/` (Medium)
  - ⚠️ In comment
- Line 148: `/api/v1/auth/api-keys/` (Medium)
  - ⚠️ In comment
- Line 170: `/api/v1/contracts/{id}/validate/` (Medium)
  - ⚠️ In comment
- Line 170: `/api/v1/contracts/{id}/validate/` (Medium)
  - ⚠️ In comment
- Line 193: `/api/v1/assets/` (Medium)
  - ⚠️ In comment
- Line 193: `/api/v1/assets/` (Medium)
  - ⚠️ In comment
- Line 216: `/api/v1/assets/{id}/activate/` (Medium)
  - ⚠️ In comment
- Line 216: `/api/v1/assets/{id}/activate/` (Medium)
  - ⚠️ In comment
- Line 243: `/api/v1/marketplace/listings/` (Medium)
  - ⚠️ In comment
- Line 243: `/api/v1/marketplace/listings/` (Medium)
  - ⚠️ In comment
- Line 262: `/api/v1/search/search/` (Medium)
  - ⚠️ In comment
- Line 262: `/api/v1/search/search/` (Medium)
  - ⚠️ In comment
- ... and 44 more references

### docs/api-audit/api-effort-estimates.json

- **Total References**: 36
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 36

#### References

- Line 2: `/api/v1/auth/register/` (Medium)
- Line 23: `/api/v1/auth/me/` (Medium)
- Line 44: `/api/v1/assets/` (Medium)
- Line 65: `/api/v1/assets/{id}/activate/` (Medium)
- Line 86: `/api/v1/auth/api-keys/` (Medium)
- Line 107: `/api/v1/contracts/{id}/validate/` (Medium)
- Line 128: `/api/v1/assets/` (Medium)
- Line 149: `/api/v1/assets/{id}/activate/` (Medium)
- Line 170: `/api/v1/marketplace/listings/` (Medium)
- Line 191: `/api/v1/search/search/` (Medium)
- Line 212: `/api/v1/scheduled-ingestions/{id}/credentials/` (Medium)
- Line 233: `/api/v1/scheduled-ingestions/{id}/credentials/test/` (Medium)
- Line 254: `/api/v1/compliance/compliance-runs/{id}/results/` (Medium)
- Line 275: `/api/v1/dq/dq-runs/` (Medium)
- Line 296: `/api/v1/dq/dq-runs/{id}/results/` (Medium)
- Line 317: `/api/v1/marketplace/listings/` (Medium)
- Line 338: `/api/v1/search/search/` (Medium)
- Line 359: `/api/v1/dq/dq-runs/{id}/results/` (Medium)
- Line 380: `/api/v1/ai/natural-language-search/` (Medium)
- Line 401: `/api/v1/ai/schema-matching/` (Medium)
- ... and 16 more references

### docs/api-audit/api-effort-estimation-methodology.md

- **Total References**: 26
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 26

#### References

- Line 26: `/api/v1/assets/` (Medium)
- Line 26: `/api/v1/assets/` (Medium)
- Line 27: `/api/v1/auth/api-keys/` (Medium)
- Line 27: `/api/v1/auth/api-keys/` (Medium)
- Line 36: `/api/v1/auth/me/` (Medium)
- Line 36: `/api/v1/auth/me/` (Medium)
- Line 37: `/api/v1/marketplace/listings/` (Medium)
- Line 37: `/api/v1/marketplace/listings/` (Medium)
- Line 46: `/api/v1/auth/register/` (Medium)
- Line 46: `/api/v1/auth/register/` (Medium)
- Line 47: `/api/v1/scheduled-ingestions/{id}/credentials/test/` (Medium)
- Line 47: `/api/v1/scheduled-ingestions/{id}/credentials/test/` (Medium)
- Line 48: `/api/v1/social/ratings/` (Medium)
- Line 48: `/api/v1/social/ratings/` (Medium)
- Line 57: `/api/v1/assets/{id}/activate/` (Medium)
- Line 57: `/api/v1/assets/{id}/activate/` (Medium)
- Line 58: `/api/v1/ai/natural-language-search/` (Medium)
- Line 58: `/api/v1/ai/natural-language-search/` (Medium)
- Line 59: `/api/v1/ai/schema-matching/` (Medium)
- Line 59: `/api/v1/ai/schema-matching/` (Medium)
- ... and 6 more references

### docs/api-audit/api-performance-requirements.md

- **Total References**: 412
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 412

#### References

- Line 38: `/api/v1/analytics/api/dashboard/` (Medium)
- Line 38: `/api/v1/analytics/api/dashboard/` (Medium)
- Line 39: `/api/v1/analytics/api/performance/` (Medium)
- Line 39: `/api/v1/analytics/api/performance/` (Medium)
- Line 40: `/api/v1/analytics/api/popular-endpoints/` (Medium)
- Line 40: `/api/v1/analytics/api/popular-endpoints/` (Medium)
- Line 41: `/api/v1/analytics/api/usage-trends/` (Medium)
- Line 41: `/api/v1/analytics/api/usage-trends/` (Medium)
- Line 47: `/api/v1/assets/{id}/` (Medium)
- Line 47: `/api/v1/assets/{id}/` (Medium)
- Line 48: `/api/v1/assets/` (Medium)
- Line 48: `/api/v1/assets/` (Medium)
- Line 49: `/api/v1/assets/{id}/` (Medium)
- Line 49: `/api/v1/assets/{id}/` (Medium)
- Line 50: `/api/v1/assets/` (Medium)
- Line 50: `/api/v1/assets/` (Medium)
- Line 51: `/api/v1/assets/{id}/activate/` (Medium)
- Line 51: `/api/v1/assets/{id}/activate/` (Medium)
- Line 52: `/api/v1/assets/{id}/contracts/` (Medium)
- Line 52: `/api/v1/assets/{id}/contracts/` (Medium)
- ... and 392 more references

### docs/api-audit/api-requirements-from-journeys.md

- **Total References**: 135
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 135

#### References

- Line 34: `/api/v1/assets/` (Medium)
- Line 34: `/api/v1/assets/` (Medium)
- Line 35: `/api/v1/ai/schema-matching/` (Medium)
- Line 35: `/api/v1/ai/schema-matching/` (Medium)
- Line 52: `/api/v1/assets/` (Medium)
- Line 87: `/api/v1/files/upload/` (Medium)
- Line 122: `/api/v1/datasets/` (Medium)
- Line 123: `/api/v1/jobs/` (Medium)
- Line 162: `/api/v1/ai/schema-matching/` (Medium)
- Line 163: `/api/v1/ai/schema-matching/{job_id}/` (Medium)
- Line 217: `/api/v1/ai/classification/` (Medium)
- Line 218: `/api/v1/ai/classification/{job_id}/` (Medium)
- Line 267: `/api/v1/compliance/scans/` (Medium)
- Line 268: `/api/v1/compliance/scans/{id}/` (Medium)
- Line 269: `/api/v1/compliance/scans/{id}/report/` (Medium)
- Line 328: `/api/v1/dq/runs/` (Medium)
- Line 329: `/api/v1/dq/runs/{id}/` (Medium)
- Line 330: `/api/v1/dq/runs/{id}/results/` (Medium)
- Line 389: `/api/v1/ai/anomaly-detection/` (Medium)
- Line 390: `/api/v1/ai/anomaly-detection/{job_id}/` (Medium)
- ... and 115 more references

### docs/api-audit/api-requirements-from-use-cases.md

- **Total References**: 90
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 90

#### References

- Line 61: `/api/v1/auth/me/` (Medium)
- Line 62: `/api/v1/tenants/{id}/` (Medium)
- Line 81: `/api/v1/assets/` (Medium)
- Line 82: `/api/v1/assets/onboarding-modes/` (Medium)
- Line 111: `/api/v1/assets/` (Medium)
- Line 151: `/api/v1/files/upload/` (Medium)
- Line 188: `/api/v1/files/{id}/validate/` (Medium)
- Line 216: `/api/v1/datasets/` (Medium)
- Line 217: `/api/v1/jobs/` (Medium)
- Line 218: `/api/v1/jobs/{id}/` (Medium)
- Line 219: `/api/v1/datasets/{id}/schema/` (Medium)
- Line 220: `/api/v1/datasets/{id}/sample/` (Medium)
- Line 284: `/api/v1/ai/schema-matching/` (Medium)
- Line 285: `/api/v1/ai/schema-matching/{job_id}/` (Medium)
- Line 340: `/api/v1/ai/classification/` (Medium)
- Line 341: `/api/v1/ai/classification/{job_id}/` (Medium)
- Line 391: `/api/v1/compliance/scans/` (Medium)
- Line 392: `/api/v1/compliance/scans/{id}/` (Medium)
- Line 393: `/api/v1/compliance/scans/{id}/report/` (Medium)
- Line 443: `/api/v1/compliance/scans/{id}/report/` (Medium)
- ... and 70 more references

### docs/api-audit/api-requirements-matrix-consolidated.md

- **Total References**: 72
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 72

#### References

- Line 113: `/api/v1/auth/login/` (Medium)
- Line 113: `/api/v1/auth/login/` (Medium)
- Line 114: `/api/v1/auth/register/` (Medium)
- Line 114: `/api/v1/auth/register/` (Medium)
- Line 115: `/api/v1/auth/refresh/` (Medium)
- Line 115: `/api/v1/auth/refresh/` (Medium)
- Line 116: `/api/v1/auth/logout/` (Medium)
- Line 116: `/api/v1/auth/logout/` (Medium)
- Line 117: `/api/v1/auth/password-reset/` (Medium)
- Line 117: `/api/v1/auth/password-reset/` (Medium)
- Line 118: `/api/v1/auth/password-reset/confirm/` (Medium)
- Line 118: `/api/v1/auth/password-reset/confirm/` (Medium)
- Line 119: `/api/v1/auth/me/` (Medium)
- Line 119: `/api/v1/auth/me/` (Medium)
- Line 120: `/api/v1/auth/api-keys/` (Medium)
- Line 120: `/api/v1/auth/api-keys/` (Medium)
- Line 121: `/api/v1/auth/api-keys/` (Medium)
- Line 121: `/api/v1/auth/api-keys/` (Medium)
- Line 122: `/api/v1/auth/api-keys/{id}/` (Medium)
- Line 122: `/api/v1/auth/api-keys/{id}/` (Medium)
- ... and 52 more references

### docs/api-audit/api-requirements-matrix.md

- **Total References**: 216
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 216

#### References

- Line 72: `/api/v1/auth/login/` (Medium)
- Line 72: `/api/v1/auth/login/` (Medium)
- Line 73: `/api/v1/auth/register/` (Medium)
- Line 73: `/api/v1/auth/register/` (Medium)
- Line 74: `/api/v1/auth/refresh/` (Medium)
- Line 74: `/api/v1/auth/refresh/` (Medium)
- Line 75: `/api/v1/auth/logout/` (Medium)
- Line 75: `/api/v1/auth/logout/` (Medium)
- Line 76: `/api/v1/auth/password-reset/` (Medium)
- Line 76: `/api/v1/auth/password-reset/` (Medium)
- Line 77: `/api/v1/auth/password-reset/confirm/` (Medium)
- Line 77: `/api/v1/auth/password-reset/confirm/` (Medium)
- Line 78: `/api/v1/auth/me/` (Medium)
- Line 78: `/api/v1/auth/me/` (Medium)
- Line 79: `/api/v1/auth/api-keys/` (Medium)
- Line 79: `/api/v1/auth/api-keys/` (Medium)
- Line 80: `/api/v1/auth/api-keys/` (Medium)
- Line 80: `/api/v1/auth/api-keys/` (Medium)
- Line 81: `/api/v1/auth/api-keys/{id}/` (Medium)
- Line 81: `/api/v1/auth/api-keys/{id}/` (Medium)
- ... and 196 more references

### docs/api-audit/api-testing-plan.md

- **Total References**: 18
- **Categories**: test
- **Priority Breakdown**:
  - High: 1
  - Low: 17

#### References

- Line 354: `/api/v1/auth/register/` (Low)
  - ⚠️ In comment
- Line 406: `/api/v1/auth/me/` (Low)
  - ⚠️ In comment
- Line 448: `/api/v1/search/search/` (Low)
  - ⚠️ In comment
- Line 494: `/api/v1/ai/natural-language-search/` (Low)
  - ⚠️ In comment
- Line 534: `/api/v1/ai/schema-matching/` (Low)
  - ⚠️ In comment
- Line 575: `/api/v1/social/ratings/` (Low)
  - ⚠️ In comment
- Line 614: `/api/v1/social/reviews/` (Low)
  - ⚠️ In comment
- Line 660: `/api/v1/scheduled-ingestions/{id}/credentials/` (Low)
  - ⚠️ In comment
- Line 694: `/api/v1/scheduled-ingestions/{id}/credentials/test/` (Low)
  - ⚠️ In comment
- Line 738: `/api/v1/auth/register/` (Low)
  - ⚠️ In comment
- Line 738: `/api/v1/auth/register/` (Low)
  - ⚠️ In comment
- Line 780: `/api/v1/auth/me/` (Low)
  - ⚠️ In comment
- Line 780: `/api/v1/auth/me/` (Low)
  - ⚠️ In comment
- Line 815: `/api/v1/assets/` (Low)
  - ⚠️ In comment
- Line 815: `/api/v1/assets/` (Low)
  - ⚠️ In comment
- Line 850: `/api/v1/assets/{id}/activate/` (Low)
  - ⚠️ In comment
- Line 850: `/api/v1/assets/{id}/activate/` (Low)
  - ⚠️ In comment
- Line 1030: `/api/v1/assets/` (High)

### docs/api-audit/codebase-endpoints-inventory.md

- **Total References**: 296
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 296

#### References

- Line 23: `/api/v1/api-analytics/api/dashboard/` (Medium)
- Line 23: `/api/v1/api-analytics/api/dashboard/` (Medium)
- Line 24: `/api/v1/api-analytics/api/performance/` (Medium)
- Line 24: `/api/v1/api-analytics/api/performance/` (Medium)
- Line 25: `/api/v1/api-analytics/api/popular-endpoints/` (Medium)
- Line 25: `/api/v1/api-analytics/api/popular-endpoints/` (Medium)
- Line 26: `/api/v1/api-analytics/api/usage-trends/` (Medium)
- Line 26: `/api/v1/api-analytics/api/usage-trends/` (Medium)
- Line 34: `/api/v1/assets/{id}/` (Medium)
- Line 34: `/api/v1/assets/{id}/` (Medium)
- Line 35: `/api/v1/assets/` (Medium)
- Line 35: `/api/v1/assets/` (Medium)
- Line 36: `/api/v1/assets/recommendations/` (Medium)
- Line 36: `/api/v1/assets/recommendations/` (Medium)
- Line 37: `/api/v1/assets/{id}/` (Medium)
- Line 37: `/api/v1/assets/{id}/` (Medium)
- Line 38: `/api/v1/assets/{id}/dependencies/` (Medium)
- Line 38: `/api/v1/assets/{id}/dependencies/` (Medium)
- Line 39: `/api/v1/assets/{id}/health-score/` (Medium)
- Line 39: `/api/v1/assets/{id}/health-score/` (Medium)
- ... and 276 more references

### docs/api-audit/current-api-inventory-categorized.md

- **Total References**: 592
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 592

#### References

- Line 43: `/api/v1/assets/{id}/` (Medium)
- Line 43: `/api/v1/assets/{id}/` (Medium)
- Line 48: `/api/v1/auth/api-keys/{id}/` (Medium)
- Line 48: `/api/v1/auth/api-keys/{id}/` (Medium)
- Line 53: `/api/v1/contracts/{id}/` (Medium)
- Line 53: `/api/v1/contracts/{id}/` (Medium)
- Line 58: `/api/v1/files/{id}/` (Medium)
- Line 58: `/api/v1/files/{id}/` (Medium)
- Line 63: `/api/v1/marketplace/listings/{id}/` (Medium)
- Line 63: `/api/v1/marketplace/listings/{id}/` (Medium)
- Line 68: `/api/v1/tenants/{id}/` (Medium)
- Line 68: `/api/v1/tenants/{id}/` (Medium)
- Line 73: `/api/v1/users/roles/{id}/` (Medium)
- Line 73: `/api/v1/users/roles/{id}/` (Medium)
- Line 78: `/api/v1/users/{id}/` (Medium)
- Line 78: `/api/v1/users/{id}/` (Medium)
- Line 83: `/api/v1/assets/` (Medium)
- Line 83: `/api/v1/assets/` (Medium)
- Line 88: `/api/v1/assets/{id}/` (Medium)
- Line 88: `/api/v1/assets/{id}/` (Medium)
- ... and 572 more references

### docs/api-audit/current-api-inventory.md

- **Total References**: 386
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 386

#### References

- Line 50: `/api/v1/analytics/` (Medium)
- Line 50: `/api/v1/analytics/` (Medium)
- Line 54: `/api/v1/analytics/api/dashboard/` (Medium)
- Line 54: `/api/v1/analytics/api/dashboard/` (Medium)
- Line 55: `/api/v1/analytics/api/performance/` (Medium)
- Line 55: `/api/v1/analytics/api/performance/` (Medium)
- Line 56: `/api/v1/analytics/api/popular-endpoints/` (Medium)
- Line 56: `/api/v1/analytics/api/popular-endpoints/` (Medium)
- Line 57: `/api/v1/analytics/api/usage-trends/` (Medium)
- Line 57: `/api/v1/analytics/api/usage-trends/` (Medium)
- Line 61: `/api/v1/assets/` (Medium)
- Line 61: `/api/v1/assets/` (Medium)
- Line 65: `/api/v1/assets/` (Medium)
- Line 65: `/api/v1/assets/` (Medium)
- Line 66: `/api/v1/assets/` (Medium)
- Line 66: `/api/v1/assets/` (Medium)
- Line 67: `/api/v1/assets/{id}/` (Medium)
- Line 67: `/api/v1/assets/{id}/` (Medium)
- Line 68: `/api/v1/assets/{id}/` (Medium)
- Line 68: `/api/v1/assets/{id}/` (Medium)
- ... and 366 more references

### docs/api-audit/endpoint-inventory-current.json

- **Total References**: 4082
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 4082

#### References

- Line 22: `/api/v1/openapi.json` (Medium)
- Line 22: `/api/v1/openapi.json` (Medium)
- Line 39: `/api/v1/openapi.yaml` (Medium)
- Line 39: `/api/v1/openapi.yaml` (Medium)
- Line 56: `/api/v1/auth/login/` (Medium)
- Line 56: `/api/v1/auth/login/` (Medium)
- Line 67: `/api/v1/auth/register/` (Medium)
- Line 67: `/api/v1/auth/register/` (Medium)
- Line 78: `/api/v1/auth/me/` (Medium)
- Line 78: `/api/v1/auth/me/` (Medium)
- Line 89: `/api/v1/auth/refresh/` (Medium)
- Line 89: `/api/v1/auth/refresh/` (Medium)
- Line 100: `/api/v1/auth/logout/` (Medium)
- Line 100: `/api/v1/auth/logout/` (Medium)
- Line 111: `/api/v1/auth/password-reset/` (Medium)
- Line 111: `/api/v1/auth/password-reset/` (Medium)
- Line 122: `/api/v1/auth/password-reset/confirm/` (Medium)
- Line 122: `/api/v1/auth/password-reset/confirm/` (Medium)
- Line 133: `/api/v1/auth/accept-invitation/` (Medium)
- Line 133: `/api/v1/auth/accept-invitation/` (Medium)
- ... and 4062 more references

### docs/api-audit/endpoint-inventory-current.md

- **Total References**: 515
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 515

#### References

- Line 16: `/api/v1/governance/access/^analytics/anomalies/$` (Medium)
- Line 18: `/api/v1/governance/access/^analytics/anomalies\.(?P<format>[a-z0-9]+` (Medium)
- Line 20: `/api/v1/governance/access/^analytics/dashboard/$` (Medium)
- Line 22: `/api/v1/governance/access/^analytics/dashboard\.(?P<format>[a-z0-9]+` (Medium)
- Line 24: `/api/v1/governance/access/^analytics/patterns/$` (Medium)
- Line 26: `/api/v1/governance/access/^analytics/patterns\.(?P<format>[a-z0-9]+` (Medium)
- Line 28: `/api/v1/governance/access/^analytics/security-events/$` (Medium)
- Line 30: `/api/v1/governance/access/^analytics/security-events\.(?P<format>[a-z0-9]+` (Medium)
- Line 32: `/api/v1/governance/access/^certifications/$` (Medium)
- Line 34: `/api/v1/governance/access/^certifications\.(?P<format>[a-z0-9]+` (Medium)
- Line 36: `/api/v1/governance/access/^certifications/expiring/$` (Medium)
- Line 38: `/api/v1/governance/access/^certifications/expiring\.(?P<format>[a-z0-9]+` (Medium)
- Line 40: `/api/v1/governance/access/^certifications/initiate-review/$` (Medium)
- Line 42: `/api/v1/governance/access/^certifications/initiate-review\.(?P<format>[a-z0-9]+` (Medium)
- Line 44: `/api/v1/governance/access/^certifications/summary/$` (Medium)
- Line 46: `/api/v1/governance/access/^certifications/summary\.(?P<format>[a-z0-9]+` (Medium)
- Line 48: `/api/v1/governance/access/^certifications/(?P<id>[^/.]+` (Medium)
- Line 50: `/api/v1/governance/access/^certifications/(?P<id>[^/.]+` (Medium)
- Line 52: `/api/v1/governance/access/^certifications/(?P<id>[^/.]+` (Medium)
- Line 54: `/api/v1/governance/access/^certifications/(?P<id>[^/.]+` (Medium)
- ... and 495 more references

### docs/api-audit/endpoint-inventory-proposed.json

- **Total References**: 1040
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 1040

#### References

- Line 16: `/api/v1/dq` (Medium)
- Line 16: `/api/v1/dq` (Medium)
- Line 21: `/api/v1/dq/<drf_format_suffix:format>` (Medium)
- Line 21: `/api/v1/dq/<drf_format_suffix:format>` (Medium)
- Line 26: `/api/v1/marketplace/^listings/(?P<id>[^/.]+` (Medium)
- Line 26: `/api/v1/marketplace/^listings/(?P<id>[^/.]+` (Medium)
- Line 31: `/api/v1/^observability/incidents/$` (Medium)
- Line 31: `/api/v1/^observability/incidents/$` (Medium)
- Line 36: `/api/v1/^observability/incidents\\.(?P<format>[a-z0-9]+` (Medium)
- Line 36: `/api/v1/^observability/incidents\\.(?P<format>[a-z0-9]+` (Medium)
- Line 405: `/api/v1/openapi.json` (Medium)
- Line 405: `/api/v1/openapi.json` (Medium)
- Line 422: `/api/v1/openapi.yaml` (Medium)
- Line 422: `/api/v1/openapi.yaml` (Medium)
- Line 439: `/api/v1/metrics/` (Medium)
- Line 439: `/api/v1/metrics/` (Medium)
- Line 450: `/api/v1/^observability/volume/aggregate/$` (Medium)
- Line 450: `/api/v1/^observability/volume/aggregate/$` (Medium)
- Line 461: `/api/v1/^observability/volume/aggregate\\.(?P<format>[a-z0-9]+` (Medium)
- Line 461: `/api/v1/^observability/volume/aggregate\\.(?P<format>[a-z0-9]+` (Medium)
- ... and 1020 more references

### docs/api-audit/endpoint-inventory-proposed.md

- **Total References**: 5
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 5

#### References

- Line 15: `/api/v1/dq**:` (Medium)
- Line 17: `/api/v1/dq/<drf_format_suffix:format>**:` (Medium)
- Line 19: `/api/v1/marketplace/^listings/(?P<id>[^/.]+` (Medium)
- Line 21: `/api/v1/^observability/incidents/$**:` (Medium)
- Line 23: `/api/v1/^observability/incidents\.(?P<format>[a-z0-9]+` (Medium)

### docs/api-audit/endpoint-naming-audit-report.md

- **Total References**: 520
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 520

#### References

- Line 14: `/api/v1/dq` (Medium)
- Line 16: `/api/v1/dq/<drf_format_suffix:format>` (Medium)
- Line 18: `/api/v1/marketplace/^listings/(?P<id>[^/.]+` (Medium)
- Line 20: `/api/v1/^observability/incidents/$` (Medium)
- Line 22: `/api/v1/^observability/incidents\.(?P<format>[a-z0-9]+` (Medium)
- Line 487: `/api/v1/governance/access/^analytics/anomalies/$` (Medium)
- Line 489: `/api/v1/governance/access/^analytics/anomalies\.(?P<format>[a-z0-9]+` (Medium)
- Line 491: `/api/v1/governance/access/^analytics/dashboard/$` (Medium)
- Line 493: `/api/v1/governance/access/^analytics/dashboard\.(?P<format>[a-z0-9]+` (Medium)
- Line 495: `/api/v1/governance/access/^analytics/patterns/$` (Medium)
- Line 497: `/api/v1/governance/access/^analytics/patterns\.(?P<format>[a-z0-9]+` (Medium)
- Line 499: `/api/v1/governance/access/^analytics/security-events/$` (Medium)
- Line 501: `/api/v1/governance/access/^analytics/security-events\.(?P<format>[a-z0-9]+` (Medium)
- Line 503: `/api/v1/governance/access/^certifications/$` (Medium)
- Line 505: `/api/v1/governance/access/^certifications\.(?P<format>[a-z0-9]+` (Medium)
- Line 507: `/api/v1/governance/access/^certifications/expiring/$` (Medium)
- Line 509: `/api/v1/governance/access/^certifications/expiring\.(?P<format>[a-z0-9]+` (Medium)
- Line 511: `/api/v1/governance/access/^certifications/initiate-review/$` (Medium)
- Line 513: `/api/v1/governance/access/^certifications/initiate-review\.(?P<format>[a-z0-9]+` (Medium)
- Line 515: `/api/v1/governance/access/^certifications/summary/$` (Medium)
- ... and 500 more references

### docs/api-audit/endpoint-test-report-template.md

- **Total References**: 18
- **Categories**: test
- **Priority Breakdown**:
  - High: 16
  - Low: 2

#### References

- Line 32: `/api/v1/auth/login/` (High)
- Line 32: `/api/v1/auth/login/` (High)
- Line 33: `/api/v1/assets/` (High)
- Line 33: `/api/v1/assets/` (High)
- Line 47: `/api/v1/example/` (High)
- Line 47: `/api/v1/example/` (High)
- Line 55: `/api/v1/old-endpoint/` (High)
  - ⚠️ Deprecated context
- Line 55: `/api/v1/new-endpoint/` (High)
  - ⚠️ Deprecated context
- Line 55: `/api/v1/old-endpoint/` (High)
  - ⚠️ Deprecated context
- Line 55: `/api/v1/new-endpoint/` (High)
  - ⚠️ Deprecated context
- Line 63: `/api/v1/admin/` (High)
- Line 63: `/api/v1/admin/` (High)
- Line 64: `/api/v1/private/` (High)
- Line 64: `/api/v1/private/` (High)
- Line 70: `/api/v1/auth/login/` (Low)
  - ⚠️ In comment
- Line 70: `/api/v1/auth/login/` (Low)
  - ⚠️ In comment
- Line 86: `/api/v1/slow-endpoint/` (High)
- Line 86: `/api/v1/slow-endpoint/` (High)

### docs/api-audit/error-responses-documentation.md

- **Total References**: 46
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 46

#### References

- Line 466: `/api/v1/auth/register/` (Medium)
- Line 466: `/api/v1/auth/register/` (Medium)
- Line 467: `/api/v1/auth/register/` (Medium)
- Line 467: `/api/v1/auth/register/` (Medium)
- Line 468: `/api/v1/auth/login/` (Medium)
- Line 468: `/api/v1/auth/login/` (Medium)
- Line 469: `/api/v1/auth/login/` (Medium)
- Line 469: `/api/v1/auth/login/` (Medium)
- Line 475: `/api/v1/scheduled-ingestions/{id}/credentials/test/` (Medium)
- Line 475: `/api/v1/scheduled-ingestions/{id}/credentials/test/` (Medium)
- Line 476: `/api/v1/scheduled-ingestions/{id}/credentials/test/` (Medium)
- Line 476: `/api/v1/scheduled-ingestions/{id}/credentials/test/` (Medium)
- Line 477: `/api/v1/scheduled-ingestions/{id}/credentials/` (Medium)
- Line 477: `/api/v1/scheduled-ingestions/{id}/credentials/` (Medium)
- Line 483: `/api/v1/ai/natural-language-search/` (Medium)
- Line 483: `/api/v1/ai/natural-language-search/` (Medium)
- Line 484: `/api/v1/ai/natural-language-search/` (Medium)
- Line 484: `/api/v1/ai/natural-language-search/` (Medium)
- Line 485: `/api/v1/ai/schema-matching/` (Medium)
- Line 485: `/api/v1/ai/schema-matching/` (Medium)
- ... and 26 more references

### docs/api-audit/error-responses-summary.md

- **Total References**: 26
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 26

#### References

- Line 49: `/api/v1/auth/register/` (Medium)
  - ⚠️ In comment
- Line 49: `/api/v1/auth/register/` (Medium)
  - ⚠️ In comment
- Line 55: `/api/v1/auth/me/` (Medium)
  - ⚠️ In comment
- Line 55: `/api/v1/auth/me/` (Medium)
  - ⚠️ In comment
- Line 65: `/api/v1/scheduled-ingestions/{id}/credentials/` (Medium)
  - ⚠️ In comment
- Line 65: `/api/v1/scheduled-ingestions/{id}/credentials/` (Medium)
  - ⚠️ In comment
- Line 73: `/api/v1/scheduled-ingestions/{id}/credentials/test/` (Medium)
  - ⚠️ In comment
- Line 73: `/api/v1/scheduled-ingestions/{id}/credentials/test/` (Medium)
  - ⚠️ In comment
- Line 83: `/api/v1/ai/natural-language-search/` (Medium)
  - ⚠️ In comment
- Line 83: `/api/v1/ai/natural-language-search/` (Medium)
  - ⚠️ In comment
- Line 91: `/api/v1/ai/schema-matching/` (Medium)
  - ⚠️ In comment
- Line 91: `/api/v1/ai/schema-matching/` (Medium)
  - ⚠️ In comment
- Line 100: `/api/v1/social/ratings/` (Medium)
  - ⚠️ In comment
- Line 100: `/api/v1/social/ratings/` (Medium)
  - ⚠️ In comment
- Line 109: `/api/v1/social/reviews/` (Medium)
  - ⚠️ In comment
- Line 109: `/api/v1/social/reviews/` (Medium)
  - ⚠️ In comment
- Line 118: `/api/v1/social/comments/` (Medium)
  - ⚠️ In comment
- Line 118: `/api/v1/social/comments/` (Medium)
  - ⚠️ In comment
- Line 127: `/api/v1/social/communities/` (Medium)
  - ⚠️ In comment
- Line 127: `/api/v1/social/communities/` (Medium)
  - ⚠️ In comment
- ... and 6 more references

### docs/api-audit/extract-endpoints-from-codebase.py

- **Total References**: 7
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 7

#### References

- Line 123: `/api/v1/{base_route}/{route_path}` (Medium)
- Line 123: `/api/v1/{base_route}/{route_path}` (Medium)
- Line 159: `/api/v1/{base_route}{path_template}` (Medium)
- Line 159: `/api/v1/{base_route}{path_template}` (Medium)
- Line 207: `/api/v1/{base_route}{path_template}` (Medium)
- Line 207: `/api/v1/{base_route}{path_template}` (Medium)
- Line 276: `/api/v1/assets/` (Medium)
  - ⚠️ In comment

### docs/api-audit/gap-analysis-script.py

- **Total References**: 9
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 9

#### References

- Line 79: `/api/v1/...` (Medium)
  - ⚠️ In comment
- Line 79: `/api/v1/...` (Medium)
  - ⚠️ In comment
- Line 80: `/api/v1/[^` (Medium)
- Line 82: `/api/v1/...` (Medium)
  - ⚠️ In comment
- Line 82: `/api/v1/...` (Medium)
  - ⚠️ In comment
- Line 83: `/api/v1/[^` (Medium)
- Line 170: `/api/v1/...` (Medium)
  - ⚠️ In comment
- Line 170: `/api/v1/...` (Medium)
  - ⚠️ In comment
- Line 171: `/api/v1/[^` (Medium)

### docs/api-audit/gap-analysis.md

- **Total References**: 52
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 52

#### References

- Line 78: `/api/v1/auth/register/` (Medium)
  - ⚠️ In comment
- Line 78: `/api/v1/auth/register/` (Medium)
  - ⚠️ In comment
- Line 130: `/api/v1/auth/me/` (Medium)
  - ⚠️ In comment
- Line 130: `/api/v1/auth/me/` (Medium)
  - ⚠️ In comment
- Line 182: `/api/v1/assets/` (Medium)
  - ⚠️ In comment
- Line 182: `/api/v1/assets/` (Medium)
  - ⚠️ In comment
- Line 206: `/api/v1/assets/{id}/activate/` (Medium)
  - ⚠️ In comment
- Line 206: `/api/v1/assets/{id}/activate/` (Medium)
  - ⚠️ In comment
- Line 229: `/api/v1/auth/api-keys/` (Medium)
  - ⚠️ In comment
- Line 229: `/api/v1/auth/api-keys/` (Medium)
  - ⚠️ In comment
- Line 250: `/api/v1/contracts/{id}/validate/` (Medium)
  - ⚠️ In comment
- Line 250: `/api/v1/contracts/{id}/validate/` (Medium)
  - ⚠️ In comment
- Line 275: `/api/v1/marketplace/listings/` (Medium)
  - ⚠️ In comment
- Line 275: `/api/v1/marketplace/listings/` (Medium)
  - ⚠️ In comment
- Line 293: `/api/v1/search/search/` (Medium)
  - ⚠️ In comment
- Line 293: `/api/v1/search/search/` (Medium)
  - ⚠️ In comment
- Line 322: `/api/v1/assets/` (Medium)
  - ⚠️ In comment
- Line 322: `/api/v1/assets/` (Medium)
  - ⚠️ In comment
- Line 341: `/api/v1/assets/{id}/activate/` (Medium)
  - ⚠️ In comment
- Line 341: `/api/v1/assets/{id}/activate/` (Medium)
  - ⚠️ In comment
- ... and 32 more references

### docs/api-audit/gap-categorization-by-priority.md

- **Total References**: 190
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 190

#### References

- Line 92: `/api/v1/auth/register/` (Medium)
- Line 92: `/api/v1/auth/register/` (Medium)
- Line 93: `/api/v1/auth/me/` (Medium)
- Line 93: `/api/v1/auth/me/` (Medium)
- Line 97: `/api/v1/auth/register/` (Medium)
  - ⚠️ In comment
- Line 97: `/api/v1/auth/register/` (Medium)
  - ⚠️ In comment
- Line 120: `/api/v1/auth/me/` (Medium)
  - ⚠️ In comment
- Line 120: `/api/v1/auth/me/` (Medium)
  - ⚠️ In comment
- Line 149: `/api/v1/assets/` (Medium)
- Line 149: `/api/v1/assets/` (Medium)
- Line 150: `/api/v1/assets/{id}/activate/` (Medium)
- Line 150: `/api/v1/assets/{id}/activate/` (Medium)
- Line 151: `/api/v1/auth/api-keys/` (Medium)
- Line 151: `/api/v1/auth/api-keys/` (Medium)
- Line 152: `/api/v1/contracts/{id}/validate/` (Medium)
- Line 152: `/api/v1/contracts/{id}/validate/` (Medium)
- Line 156: `/api/v1/assets/` (Medium)
  - ⚠️ In comment
- Line 156: `/api/v1/assets/` (Medium)
  - ⚠️ In comment
- Line 180: `/api/v1/assets/{id}/activate/` (Medium)
  - ⚠️ In comment
- Line 180: `/api/v1/assets/{id}/activate/` (Medium)
  - ⚠️ In comment
- ... and 170 more references

### docs/api-audit/gap-details.md

- **Total References**: 132
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 132

#### References

- Line 57: `/api/v1/auth/register/` (Medium)
  - ⚠️ In comment
- Line 57: `/api/v1/auth/register/` (Medium)
  - ⚠️ In comment
- Line 130: `/api/v1/auth/me/` (Medium)
  - ⚠️ In comment
- Line 130: `/api/v1/auth/me/` (Medium)
  - ⚠️ In comment
- Line 196: `/api/v1/assets/` (Medium)
  - ⚠️ In comment
- Line 196: `/api/v1/assets/` (Medium)
  - ⚠️ In comment
- Line 247: `/api/v1/assets/{id}/activate/` (Medium)
  - ⚠️ In comment
- Line 247: `/api/v1/assets/{id}/activate/` (Medium)
  - ⚠️ In comment
- Line 303: `/api/v1/auth/api-keys/` (Medium)
  - ⚠️ In comment
- Line 303: `/api/v1/auth/api-keys/` (Medium)
  - ⚠️ In comment
- Line 348: `/api/v1/contracts/{id}/validate/` (Medium)
  - ⚠️ In comment
- Line 348: `/api/v1/contracts/{id}/validate/` (Medium)
  - ⚠️ In comment
- Line 401: `/api/v1/assets/` (Medium)
  - ⚠️ In comment
- Line 401: `/api/v1/assets/` (Medium)
  - ⚠️ In comment
- Line 446: `/api/v1/assets/{id}/activate/` (Medium)
  - ⚠️ In comment
- Line 446: `/api/v1/assets/{id}/activate/` (Medium)
  - ⚠️ In comment
- Line 499: `/api/v1/scheduled-ingestions/{id}/credentials/` (Medium)
  - ⚠️ In comment
- Line 499: `/api/v1/scheduled-ingestions/{id}/credentials/` (Medium)
  - ⚠️ In comment
- Line 546: `/api/v1/scheduled-ingestions/{id}/credentials/test/` (Medium)
  - ⚠️ In comment
- Line 546: `/api/v1/scheduled-ingestions/{id}/credentials/test/` (Medium)
  - ⚠️ In comment
- ... and 112 more references

### docs/api-audit/generate-api-timeline.py

- **Total References**: 21
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 21

#### References

- Line 50: `/api/v1/[^` (Medium)
- Line 284: `/api/v1/auth/register/` (Medium)
- Line 285: `/api/v1/auth/login/` (Medium)
- Line 286: `/api/v1/auth/me/` (Medium)
- Line 287: `/api/v1/assets/` (Medium)
- Line 290: `/api/v1/assets/` (Medium)
- Line 291: `/api/v1/contracts/{id}/validate/` (Medium)
- Line 292: `/api/v1/assets/{id}/activate/` (Medium)
- Line 302: `/api/v1/scheduled-ingestions/{id}/credentials/` (Medium)
- Line 303: `/api/v1/scheduled-ingestions/{id}/credentials/test/` (Medium)
- Line 306: `/api/v1/marketplace/listings/` (Medium)
- Line 307: `/api/v1/search/search/` (Medium)
- Line 317: `/api/v1/ai/natural-language-search/` (Medium)
- Line 318: `/api/v1/ai/schema-matching/` (Medium)
- Line 321: `/api/v1/social/ratings/` (Medium)
- Line 322: `/api/v1/social/reviews/` (Medium)
- Line 323: `/api/v1/social/comments/` (Medium)
- Line 324: `/api/v1/social/communities/` (Medium)
- Line 334: `/api/v1/developer/plugins/` (Medium)
- Line 335: `/api/v1/developer/sdk/` (Medium)
- ... and 1 more references

### docs/api-audit/generate-performance-requirements.py

- **Total References**: 2
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 2

#### References

- Line 60: `/api/v1/[^` (Medium)
- Line 100: `/api/v1/[^` (Medium)

### docs/api-audit/hardcoded-endpoints-impact-matrix.json

- **Total References**: 151710
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 151710

#### References

- Line 32: `localhost:8000/api/v1` (Medium)
- Line 40: `localhost:8000/api/v1` (Medium)
  - ⚠️ Deprecated context
- Line 48: `localhost:8000/api/v1` (Medium)
  - ⚠️ Deprecated context
- Line 56: `localhost:8000/api/v1` (Medium)
  - ⚠️ Deprecated context
- Line 76: `/api/v1/assets/assets/` (Medium)
- Line 76: `/api/v1/assets/assets/` (Medium)
- Line 84: `/api/v1/assets/assets/{id}/` (Medium)
  - ⚠️ Deprecated context
- Line 84: `/api/v1/assets/assets/{id}/` (Medium)
  - ⚠️ Deprecated context
- Line 92: `/api/v1/assets/assets/` (Medium)
  - ⚠️ Deprecated context
- Line 92: `/api/v1/assets/assets/` (Medium)
  - ⚠️ Deprecated context
- Line 100: `/api/v1/assets/assets/{id}/` (Medium)
  - ⚠️ Deprecated context
- Line 100: `/api/v1/assets/assets/{id}/` (Medium)
  - ⚠️ Deprecated context
- Line 108: `/api/v1/assets/assets/{id}/` (Medium)
  - ⚠️ Deprecated context
- Line 108: `/api/v1/assets/assets/{id}/` (Medium)
  - ⚠️ Deprecated context
- Line 116: `/api/v1/assets/assets/{id}/activate/` (Medium)
  - ⚠️ Deprecated context
- Line 116: `/api/v1/assets/assets/{id}/activate/` (Medium)
  - ⚠️ Deprecated context
- Line 136: `/api/v1/contracts/contracts/` (Medium)
- Line 136: `/api/v1/contracts/contracts/` (Medium)
- Line 144: `/api/v1/contracts/contracts/{id}/` (Medium)
  - ⚠️ Deprecated context
- Line 144: `/api/v1/contracts/contracts/{id}/` (Medium)
  - ⚠️ Deprecated context
- ... and 151690 more references

### docs/api-audit/integration-requirements-documentation.md

- **Total References**: 62
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 62

#### References

- Line 143: `/api/v1/ai/natural-language-search/` (Medium)
- Line 159: `/api/v1/ai/schema-matching/` (Medium)
- Line 174: `/api/v1/scheduled-ingestions/{id}/credentials/test/` (Medium)
- Line 198: `/api/v1/auth/register/` (Medium)
- Line 214: `/api/v1/auth/register/` (Medium)
- Line 215: `/api/v1/auth/me/` (Medium)
- Line 216: `/api/v1/social/communities/` (Medium)
- Line 229: `/api/v1/auth/register/` (Medium)
- Line 230: `/api/v1/auth/me/` (Medium)
- Line 243: `/api/v1/scheduled-ingestions/{id}/credentials/` (Medium)
- Line 244: `/api/v1/scheduled-ingestions/{id}/credentials/test/` (Medium)
- Line 258: `/api/v1/ai/natural-language-search/` (Medium)
- Line 259: `/api/v1/ai/schema-matching/` (Medium)
- Line 260: `/api/v1/social/ratings/` (Medium)
- Line 261: `/api/v1/social/reviews/` (Medium)
- Line 262: `/api/v1/social/comments/` (Medium)
- Line 263: `/api/v1/marketplace/listings/{id}/preview/` (Medium)
- Line 278: `/api/v1/ai/natural-language-search/` (Medium)
- Line 279: `/api/v1/ai/schema-matching/` (Medium)
- Line 293: `/api/v1/social/ratings/` (Medium)
- ... and 42 more references

### docs/api-audit/integration-requirements-summary.md

- **Total References**: 26
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 26

#### References

- Line 153: `/api/v1/auth/register/` (Medium)
  - ⚠️ In comment
- Line 153: `/api/v1/auth/register/` (Medium)
  - ⚠️ In comment
- Line 174: `/api/v1/auth/me/` (Medium)
  - ⚠️ In comment
- Line 174: `/api/v1/auth/me/` (Medium)
  - ⚠️ In comment
- Line 194: `/api/v1/scheduled-ingestions/{id}/credentials/` (Medium)
  - ⚠️ In comment
- Line 194: `/api/v1/scheduled-ingestions/{id}/credentials/` (Medium)
  - ⚠️ In comment
- Line 210: `/api/v1/scheduled-ingestions/{id}/credentials/test/` (Medium)
  - ⚠️ In comment
- Line 210: `/api/v1/scheduled-ingestions/{id}/credentials/test/` (Medium)
  - ⚠️ In comment
- Line 229: `/api/v1/ai/natural-language-search/` (Medium)
  - ⚠️ In comment
- Line 229: `/api/v1/ai/natural-language-search/` (Medium)
  - ⚠️ In comment
- Line 249: `/api/v1/ai/schema-matching/` (Medium)
  - ⚠️ In comment
- Line 249: `/api/v1/ai/schema-matching/` (Medium)
  - ⚠️ In comment
- Line 271: `/api/v1/social/ratings/` (Medium)
  - ⚠️ In comment
- Line 271: `/api/v1/social/ratings/` (Medium)
  - ⚠️ In comment
- Line 290: `/api/v1/social/reviews/` (Medium)
  - ⚠️ In comment
- Line 290: `/api/v1/social/reviews/` (Medium)
  - ⚠️ In comment
- Line 309: `/api/v1/social/comments/` (Medium)
  - ⚠️ In comment
- Line 309: `/api/v1/social/comments/` (Medium)
  - ⚠️ In comment
- Line 328: `/api/v1/social/communities/` (Medium)
  - ⚠️ In comment
- Line 328: `/api/v1/social/communities/` (Medium)
  - ⚠️ In comment
- ... and 6 more references

### docs/api-audit/integration-test-requirements.md

- **Total References**: 36
- **Categories**: test
- **Priority Breakdown**:
  - High: 36

#### References

- Line 32: `/api/v1/auth/register/` (High)
- Line 33: `/api/v1/auth/login/` (High)
- Line 34: `/api/v1/auth/refresh/` (High)
- Line 35: `/api/v1/auth/me/` (High)
- Line 65: `/api/v1/assets/` (High)
- Line 66: `/api/v1/files/upload/` (High)
- Line 67: `/api/v1/datasets/` (High)
- Line 68: `/api/v1/contracts/` (High)
- Line 69: `/api/v1/contracts/{id}/validate/` (High)
- Line 70: `/api/v1/assets/{id}/activate/` (High)
- Line 107: `/api/v1/contracts/` (High)
- Line 108: `/api/v1/contracts/{id}/validate/` (High)
- Line 109: `/api/v1/contracts/{id}/publish/` (High)
- Line 144: `/api/v1/dq/runs/` (High)
- Line 182: `/api/v1/marketplace/listings/` (High)
- Line 183: `/api/v1/marketplace/listings/{id}/preview/` (High)
- Line 218: `/api/v1/ai/schema-matching/` (High)
- Line 251: `/api/v1/social/ratings/` (High)
- Line 252: `/api/v1/social/reviews/` (High)
- Line 253: `/api/v1/social/comments/` (High)
- ... and 16 more references

### docs/api-audit/journey-api-extraction-script.py

- **Total References**: 76
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 76

#### References

- Line 79: `/api/v1/assets/` (Medium)
- Line 79: `/api/v1/assets/` (Medium)
- Line 87: `/api/v1/assets/{id}/` (Medium)
- Line 87: `/api/v1/assets/{id}/` (Medium)
- Line 93: `/api/v1/assets/{id}/activate/` (Medium)
- Line 93: `/api/v1/assets/{id}/activate/` (Medium)
- Line 101: `/api/v1/files/upload/` (Medium)
- Line 101: `/api/v1/files/upload/` (Medium)
- Line 109: `/api/v1/datasets/` (Medium)
- Line 109: `/api/v1/datasets/` (Medium)
- Line 115: `/api/v1/datasets/{id}/` (Medium)
- Line 115: `/api/v1/datasets/{id}/` (Medium)
- Line 123: `/api/v1/contracts/` (Medium)
- Line 123: `/api/v1/contracts/` (Medium)
- Line 129: `/api/v1/contracts/{id}/validate/` (Medium)
- Line 129: `/api/v1/contracts/{id}/validate/` (Medium)
- Line 137: `/api/v1/ai/schema-matching/` (Medium)
- Line 137: `/api/v1/ai/schema-matching/` (Medium)
- Line 145: `/api/v1/ai/classification/` (Medium)
- Line 145: `/api/v1/ai/classification/` (Medium)
- ... and 56 more references

### docs/api-audit/security-requirements-documentation.md

- **Total References**: 6
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 6

#### References

- Line 60: `/api/v1/auth/me/` (Medium)
- Line 60: `/api/v1/auth/me/` (Medium)
- Line 110: `/api/v1/assets/` (Medium)
- Line 110: `/api/v1/assets/` (Medium)
- Line 114: `/api/v1/assets/` (Medium)
- Line 114: `/api/v1/assets/` (Medium)

### docs/api-audit/update-backlog-with-dependencies.py

- **Total References**: 2
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 2

#### References

- Line 55: `/api/v1/...` (Medium)
  - ⚠️ In comment
- Line 55: `/api/v1/...` (Medium)
  - ⚠️ In comment

### docs/api-contracts/missing/README.md

- **Total References**: 60
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 60

#### References

- Line 27: `/api/v1/auth/register/` (Medium)
- Line 28: `/api/v1/auth/me/` (Medium)
- Line 30: `/api/v1/scheduled-ingestions/{id}/credentials/` (Medium)
- Line 32: `/api/v1/ai/natural-language-search/` (Medium)
- Line 33: `/api/v1/ai/schema-matching/` (Medium)
- Line 35: `/api/v1/social/{ratings,reviews,comments,communities}/` (Medium)
- Line 37: `/api/v1/marketplace/listings/{id}/preview/` (Medium)
- Line 39: `/api/v1/developer/{plugins,sdk}/` (Medium)
- Line 52: `/api/v1/auth/register/` (Medium)
  - ⚠️ In comment
- Line 52: `/api/v1/auth/register/` (Medium)
  - ⚠️ In comment
- Line 74: `/api/v1/auth/me/` (Medium)
  - ⚠️ In comment
- Line 74: `/api/v1/auth/me/` (Medium)
  - ⚠️ In comment
- Line 101: `/api/v1/scheduled-ingestions/{id}/credentials/` (Medium)
  - ⚠️ In comment
- Line 101: `/api/v1/scheduled-ingestions/{id}/credentials/` (Medium)
  - ⚠️ In comment
- Line 123: `/api/v1/scheduled-ingestions/{id}/credentials/test/` (Medium)
  - ⚠️ In comment
- Line 123: `/api/v1/scheduled-ingestions/{id}/credentials/test/` (Medium)
  - ⚠️ In comment
- Line 153: `/api/v1/ai/natural-language-search/` (Medium)
  - ⚠️ In comment
- Line 153: `/api/v1/ai/natural-language-search/` (Medium)
  - ⚠️ In comment
- Line 179: `/api/v1/ai/schema-matching/` (Medium)
  - ⚠️ In comment
- Line 179: `/api/v1/ai/schema-matching/` (Medium)
  - ⚠️ In comment
- ... and 40 more references

### docs/api-contracts/missing/ai-ml/natural-language-search.yaml

- **Total References**: 1
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 1

#### References

- Line 14: `localhost:8000/api/v1` (Medium)

### docs/api-contracts/missing/ai-ml/schema-matching.yaml

- **Total References**: 1
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 1

#### References

- Line 14: `localhost:8000/api/v1` (Medium)

### docs/api-contracts/missing/auth/me.yaml

- **Total References**: 1
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 1

#### References

- Line 14: `localhost:8000/api/v1` (Medium)

### docs/api-contracts/missing/auth/register.yaml

- **Total References**: 1
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 1

#### References

- Line 14: `localhost:8000/api/v1` (Medium)

### docs/api-contracts/missing/credentials/scheduled-ingestion-credentials.yaml

- **Total References**: 1
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 1

#### References

- Line 14: `localhost:8000/api/v1` (Medium)

### docs/api-contracts/missing/developer/plugins-sdk.yaml

- **Total References**: 1
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 1

#### References

- Line 14: `localhost:8000/api/v1` (Medium)

### docs/api-contracts/missing/marketplace-advanced/preview.yaml

- **Total References**: 1
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 1

#### References

- Line 14: `localhost:8000/api/v1` (Medium)

### docs/api-contracts/missing/social/ratings-reviews-comments-communities.yaml

- **Total References**: 1
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 1

#### References

- Line 14: `localhost:8000/api/v1` (Medium)

### docs/deprecated-doc/analysis-docs/CROSS_SERVICE_ACCESS_EXAMPLES.md

- **Total References**: 14
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 14

#### References

- Line 32: `/api/v1/contracts/{contract_id}` (Medium)
  - ⚠️ Deprecated context
- Line 32: `/api/v1/contracts/{contract_id}` (Medium)
  - ⚠️ Deprecated context
- Line 75: `/api/v1/assets/{asset_id}` (Medium)
  - ⚠️ Deprecated context
- Line 75: `/api/v1/assets/{asset_id}` (Medium)
  - ⚠️ Deprecated context
- Line 317: `/api/v1/contracts` (Medium)
  - ⚠️ Deprecated context
- Line 317: `/api/v1/contracts` (Medium)
  - ⚠️ Deprecated context
- Line 324: `/api/v1/assets` (Medium)
  - ⚠️ Deprecated context
- Line 324: `/api/v1/assets` (Medium)
  - ⚠️ Deprecated context
- Line 334: `/api/v1/contracts/{contract[` (Medium)
  - ⚠️ Deprecated context
- Line 334: `/api/v1/contracts/{contract[` (Medium)
  - ⚠️ Deprecated context
- Line 346: `/api/v1/assets/{asset[` (Medium)
  - ⚠️ Deprecated context
- Line 346: `/api/v1/assets/{asset[` (Medium)
  - ⚠️ Deprecated context
- Line 355: `/api/v1/contracts/{contract[` (Medium)
  - ⚠️ Deprecated context
- Line 355: `/api/v1/contracts/{contract[` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/analysis-docs/MICROSERVICES_INFRASTRUCTURE.md

- **Total References**: 27
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 27

#### References

- Line 157: `/api/v1/contracts/*` (Medium)
  - ⚠️ Deprecated context
- Line 157: `/api/v1/contracts/*` (Medium)
  - ⚠️ Deprecated context
- Line 158: `/api/v1/assets/*` (Medium)
  - ⚠️ Deprecated context
- Line 158: `/api/v1/assets/*` (Medium)
  - ⚠️ Deprecated context
- Line 159: `/api/v1/datasets/*` (Medium)
  - ⚠️ Deprecated context
- Line 159: `/api/v1/datasets/*` (Medium)
  - ⚠️ Deprecated context
- Line 532: `/api/v1/contracts` (Medium)
  - ⚠️ Deprecated context
- Line 532: `/api/v1/contracts` (Medium)
  - ⚠️ Deprecated context
- Line 532: `api.example.com/api/v1` (Medium)
  - ⚠️ Deprecated context
- Line 533: `/api/v1/assets` (Medium)
  - ⚠️ Deprecated context
- Line 533: `/api/v1/assets` (Medium)
  - ⚠️ Deprecated context
- Line 533: `api.example.com/api/v1` (Medium)
  - ⚠️ Deprecated context
- Line 534: `/api/v1/datasets` (Medium)
  - ⚠️ Deprecated context
- Line 534: `/api/v1/datasets` (Medium)
  - ⚠️ Deprecated context
- Line 534: `api.example.com/api/v1` (Medium)
  - ⚠️ Deprecated context
- Line 535: `/api/v1/search` (Medium)
  - ⚠️ Deprecated context
- Line 535: `/api/v1/search` (Medium)
  - ⚠️ Deprecated context
- Line 535: `api.example.com/api/v1` (Medium)
  - ⚠️ Deprecated context
- Line 536: `/api/v1/observability` (Medium)
  - ⚠️ Deprecated context
- Line 536: `/api/v1/observability` (Medium)
  - ⚠️ Deprecated context
- ... and 7 more references

### docs/deprecated-doc/analysis-docs/SERVICE_BOUNDARIES_ANALYSIS.md

- **Total References**: 131
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 131

#### References

- Line 481: `/api/v1/contracts` (Medium)
  - ⚠️ Deprecated context
- Line 481: `/api/v1/contracts` (Medium)
  - ⚠️ Deprecated context
- Line 484: `/api/v1/contracts` (Medium)
  - ⚠️ Deprecated context
- Line 485: `/api/v1/contracts/{id}` (Medium)
  - ⚠️ Deprecated context
- Line 486: `/api/v1/contracts` (Medium)
  - ⚠️ Deprecated context
- Line 487: `/api/v1/contracts/{id}` (Medium)
  - ⚠️ Deprecated context
- Line 488: `/api/v1/contracts/{id}` (Medium)
  - ⚠️ Deprecated context
- Line 489: `/api/v1/contracts/{id}/validate` (Medium)
  - ⚠️ Deprecated context
- Line 490: `/api/v1/contracts/{id}/normalize` (Medium)
  - ⚠️ Deprecated context
- Line 491: `/api/v1/contracts/{id}/lineage` (Medium)
  - ⚠️ Deprecated context
- Line 492: `/api/v1/contracts/{id}/impact` (Medium)
  - ⚠️ Deprecated context
- Line 498: `/api/v1/assets` (Medium)
  - ⚠️ Deprecated context
- Line 498: `/api/v1/assets` (Medium)
  - ⚠️ Deprecated context
- Line 501: `/api/v1/assets` (Medium)
  - ⚠️ Deprecated context
- Line 502: `/api/v1/assets/{id}` (Medium)
  - ⚠️ Deprecated context
- Line 503: `/api/v1/assets` (Medium)
  - ⚠️ Deprecated context
- Line 504: `/api/v1/assets/{id}` (Medium)
  - ⚠️ Deprecated context
- Line 505: `/api/v1/assets/{id}` (Medium)
  - ⚠️ Deprecated context
- Line 506: `/api/v1/assets/{id}/activate` (Medium)
  - ⚠️ Deprecated context
- Line 507: `/api/v1/assets/{id}/publish` (Medium)
  - ⚠️ Deprecated context
- ... and 111 more references

### docs/deprecated-doc/analysis-docs/SERVICE_COMMUNICATION_PATTERNS.md

- **Total References**: 28
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 28

#### References

- Line 49: `/api/v1/contracts/123` (Medium)
  - ⚠️ Deprecated context
- Line 49: `/api/v1/contracts/123` (Medium)
  - ⚠️ Deprecated context
- Line 52: `/api/v1/contracts` (Medium)
  - ⚠️ Deprecated context
- Line 52: `/api/v1/contracts` (Medium)
  - ⚠️ Deprecated context
- Line 55: `/api/v1/contracts/123` (Medium)
  - ⚠️ Deprecated context
- Line 55: `/api/v1/contracts/123` (Medium)
  - ⚠️ Deprecated context
- Line 58: `/api/v1/contracts/123` (Medium)
  - ⚠️ Deprecated context
- Line 58: `/api/v1/contracts/123` (Medium)
  - ⚠️ Deprecated context
- Line 91: `/api/v1/assets/123` (Medium)
  - ⚠️ Deprecated context
- Line 91: `/api/v1/assets/123` (Medium)
  - ⚠️ Deprecated context
- Line 94: `/api/v1/assets/123` (Medium)
  - ⚠️ Deprecated context
- Line 94: `/api/v1/assets/123` (Medium)
  - ⚠️ Deprecated context
- Line 97: `/api/v1/assets/123` (Medium)
  - ⚠️ Deprecated context
- Line 97: `/api/v1/assets/123` (Medium)
  - ⚠️ Deprecated context
- Line 238: `/api/v1/resource/123` (Medium)
  - ⚠️ Deprecated context
- Line 238: `/api/v1/resource/123` (Medium)
  - ⚠️ Deprecated context
- Line 265: `/api/v1/resource` (Medium)
  - ⚠️ Deprecated context
- Line 265: `/api/v1/resource` (Medium)
  - ⚠️ Deprecated context
- Line 282: `/api/v1/resource` (Medium)
  - ⚠️ Deprecated context
- Line 282: `/api/v1/resource` (Medium)
  - ⚠️ Deprecated context
- ... and 8 more references

### docs/deprecated-doc/analysis-docs/SERVICE_LAYER_DEPLOYMENT.md

- **Total References**: 10
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 10

#### References

- Line 90: `/api/v1/contracts/123` (Medium)
  - ⚠️ Deprecated context
- Line 90: `/api/v1/contracts/123` (Medium)
  - ⚠️ Deprecated context
- Line 93: `/api/v1/contracts` (Medium)
  - ⚠️ Deprecated context
- Line 93: `/api/v1/contracts` (Medium)
  - ⚠️ Deprecated context
- Line 96: `/api/v1/contracts/123` (Medium)
  - ⚠️ Deprecated context
- Line 96: `/api/v1/contracts/123` (Medium)
  - ⚠️ Deprecated context
- Line 99: `/api/v1/contracts/123` (Medium)
  - ⚠️ Deprecated context
- Line 99: `/api/v1/contracts/123` (Medium)
  - ⚠️ Deprecated context
- Line 112: `/api/v1/assets/123` (Medium)
  - ⚠️ Deprecated context
- Line 112: `/api/v1/assets/123` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/archive/ACCESS_ANALYTICS.md

- **Total References**: 4
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 4

#### References

- Line 145: `/api/v1/access/analytics/dashboard/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 149: `/api/v1/access/analytics/patterns/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 153: `/api/v1/access/analytics/anomalies/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 157: `/api/v1/access/analytics/security-events/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context

### docs/deprecated-doc/archive/ACCESS_CERTIFICATION.md

- **Total References**: 5
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 5

#### References

- Line 138: `/api/v1/access/certifications/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 142: `/api/v1/access/certifications/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 146: `/api/v1/access/certifications/{id}/review/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 150: `/api/v1/access/certifications/expiring/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 154: `/api/v1/access/certifications/summary/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context

### docs/deprecated-doc/archive/API_ANALYTICS.md

- **Total References**: 8
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 8

#### References

- Line 53: `/api/v1/assets/` (Medium)
  - ⚠️ Deprecated context
- Line 53: `/api/v1/assets/` (Medium)
  - ⚠️ Deprecated context
- Line 83: `/api/v1/assets/` (Medium)
  - ⚠️ Deprecated context
- Line 83: `/api/v1/assets/` (Medium)
  - ⚠️ Deprecated context
- Line 214: `/api/v1/analytics/api/dashboard/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 222: `/api/v1/analytics/api/popular-endpoints/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 231: `/api/v1/analytics/api/usage-trends/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 240: `/api/v1/analytics/api/performance/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context

### docs/deprecated-doc/archive/DATA_OBSERVABILITY.md

- **Total References**: 14
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 14

#### References

- Line 245: `/api/v1/observability/freshness` (Medium)
  - ⚠️ Deprecated context
- Line 245: `/api/v1/observability/freshness` (Medium)
  - ⚠️ Deprecated context
- Line 285: `/api/v1/observability/freshness/stale` (Medium)
  - ⚠️ Deprecated context
- Line 285: `/api/v1/observability/freshness/stale` (Medium)
  - ⚠️ Deprecated context
- Line 295: `/api/v1/observability/metrics` (Medium)
  - ⚠️ Deprecated context
- Line 295: `/api/v1/observability/metrics` (Medium)
  - ⚠️ Deprecated context
- Line 318: `/api/v1/observability/volume` (Medium)
  - ⚠️ Deprecated context
- Line 318: `/api/v1/observability/volume` (Medium)
  - ⚠️ Deprecated context
- Line 330: `/api/v1/observability/volume/aggregate` (Medium)
  - ⚠️ Deprecated context
- Line 330: `/api/v1/observability/volume/aggregate` (Medium)
  - ⚠️ Deprecated context
- Line 343: `/api/v1/observability/schema-drift` (Medium)
  - ⚠️ Deprecated context
- Line 343: `/api/v1/observability/schema-drift` (Medium)
  - ⚠️ Deprecated context
- Line 354: `/api/v1/observability/schema-drift/detect` (Medium)
  - ⚠️ Deprecated context
- Line 354: `/api/v1/observability/schema-drift/detect` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/archive/DEPLOYMENT.md

- **Total References**: 8
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 8

#### References

- Line 299: `/api/v1/health/semantic/` (Medium)
  - ⚠️ Deprecated context
- Line 299: `/api/v1/health/semantic/` (Medium)
  - ⚠️ Deprecated context
- Line 300: `/api/v1/health/datacontract/` (Medium)
  - ⚠️ Deprecated context
- Line 300: `/api/v1/health/datacontract/` (Medium)
  - ⚠️ Deprecated context
- Line 301: `/api/v1/health/compliance/` (Medium)
  - ⚠️ Deprecated context
- Line 301: `/api/v1/health/compliance/` (Medium)
  - ⚠️ Deprecated context
- Line 302: `/api/v1/health/dq/` (Medium)
  - ⚠️ Deprecated context
- Line 302: `/api/v1/health/dq/` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/archive/EMAIL_SERVICE.md

- **Total References**: 4
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 4

#### References

- Line 127: `/api/v1/users/invite/` (Medium)
  - ⚠️ Deprecated context
- Line 127: `/api/v1/users/invite/` (Medium)
  - ⚠️ Deprecated context
- Line 131: `/api/v1/auth/password-reset` (Medium)
  - ⚠️ Deprecated context
- Line 131: `/api/v1/auth/password-reset` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/archive/IMPACT_ANALYSIS.md

- **Total References**: 3
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 3

#### References

- Line 75: `/api/v1/contracts/{id}/impact-analysis` (Medium)
  - ⚠️ Deprecated context
- Line 75: `/api/v1/contracts/{id}/impact-analysis` (Medium)
  - ⚠️ Deprecated context
- Line 90: `/api/v1/contracts/{id}/impact-analysis?depth=5&format=json` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/archive/MULTI_LEVEL_LINEAGE.md

- **Total References**: 1
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 1

#### References

- Line 260: `/api/v1/contracts/{id}/` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/archive/OPENAPI_SPEC_GENERATION.md

- **Total References**: 2
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 2

#### References

- Line 135: `/api/v1/openapi.json` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 139: `/api/v1/openapi.yaml` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context

### docs/deprecated-doc/archive/SDK_DOCUMENTATION.md

- **Total References**: 4
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 4

#### References

- Line 89: `/api/v1/auth/refresh/` (Medium)
  - ⚠️ Deprecated context
- Line 89: `/api/v1/auth/refresh/` (Medium)
  - ⚠️ Deprecated context
- Line 481: `/api/v1/auth/refresh/` (Medium)
  - ⚠️ Deprecated context
- Line 481: `/api/v1/auth/refresh/` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/archive/SEARCH.md

- **Total References**: 13
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 13

#### References

- Line 59: `/api/v1/search/search` (Medium)
  - ⚠️ Deprecated context
- Line 59: `/api/v1/search/search` (Medium)
  - ⚠️ Deprecated context
- Line 81: `/api/v1/search/search?q=test&type=ASSET&limit=10&sort_by=relevance&sort_order=desc` (Medium)
  - ⚠️ Deprecated context
- Line 131: `/api/v1/search/suggestions` (Medium)
  - ⚠️ Deprecated context
- Line 131: `/api/v1/search/suggestions` (Medium)
  - ⚠️ Deprecated context
- Line 143: `/api/v1/search/suggestions?q=test&limit=10` (Medium)
  - ⚠️ Deprecated context
- Line 178: `/api/v1/search/analytics` (Medium)
  - ⚠️ Deprecated context
- Line 178: `/api/v1/search/analytics` (Medium)
  - ⚠️ Deprecated context
- Line 196: `/api/v1/search/analytics?start_date=2024-01-01T00:00:00Z&end_date=2024-01-31T23:59:59Z` (Medium)
  - ⚠️ Deprecated context
- Line 229: `/api/v1/search/track_click` (Medium)
  - ⚠️ Deprecated context
- Line 229: `/api/v1/search/track_click` (Medium)
  - ⚠️ Deprecated context
- Line 282: `/api/v1/search/rebuild_index` (Medium)
  - ⚠️ Deprecated context
- Line 282: `/api/v1/search/rebuild_index` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/archive/SSO_INTEGRATION.md

- **Total References**: 12
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 12

#### References

- Line 51: `/api/v1/auth/sso/saml/login-url/` (Medium)
  - ⚠️ Deprecated context
- Line 53: `/api/v1/auth/sso/saml/callback/` (Medium)
  - ⚠️ Deprecated context
- Line 82: `/api/v1/auth/sso/oidc/login-url/` (Medium)
  - ⚠️ Deprecated context
- Line 84: `/api/v1/auth/sso/oidc/callback/` (Medium)
  - ⚠️ Deprecated context
- Line 116: `/api/v1/auth/sso/saml/login-url/?tenant_id=uuid&redirect_uri=https://example.com/callback` (Medium)
  - ⚠️ Deprecated context
- Line 123: `/api/v1/auth/sso/saml/callback/` (Medium)
  - ⚠️ Deprecated context
- Line 143: `/api/v1/auth/sso/oidc/login-url/?tenant_id=uuid&redirect_uri=https://example.com/callback` (Medium)
  - ⚠️ Deprecated context
- Line 150: `/api/v1/auth/sso/oidc/callback/` (Medium)
  - ⚠️ Deprecated context
- Line 201: `/api/v1/auth/sso/saml/login-url/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 205: `/api/v1/auth/sso/saml/callback/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 209: `/api/v1/auth/sso/oidc/login-url/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 213: `/api/v1/auth/sso/oidc/callback/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context

### docs/deprecated-doc/archive/WEBHOOK_SUPPORT.md

- **Total References**: 7
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 7

#### References

- Line 159: `/api/v1/webhooks/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 175: `/api/v1/webhooks/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 179: `/api/v1/webhooks/{id}/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 183: `/api/v1/webhooks/{id}/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 187: `/api/v1/webhooks/{id}/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 191: `/api/v1/webhooks/{id}/test/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 195: `/api/v1/webhooks/{id}/deliveries/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context

### docs/deprecated-doc/deployment-docs/PRODUCTION_DEPLOYMENT.md

- **Total References**: 8
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 8

#### References

- Line 336: `/api/v1/health/semantic/` (Medium)
  - ⚠️ Deprecated context
- Line 336: `/api/v1/health/semantic/` (Medium)
  - ⚠️ Deprecated context
- Line 337: `/api/v1/health/datacontract/` (Medium)
  - ⚠️ Deprecated context
- Line 337: `/api/v1/health/datacontract/` (Medium)
  - ⚠️ Deprecated context
- Line 338: `/api/v1/health/compliance/` (Medium)
  - ⚠️ Deprecated context
- Line 338: `/api/v1/health/compliance/` (Medium)
  - ⚠️ Deprecated context
- Line 339: `/api/v1/health/dq/` (Medium)
  - ⚠️ Deprecated context
- Line 339: `/api/v1/health/dq/` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/deployment-docs/STAGING_DEPLOYMENT.md

- **Total References**: 3
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 3

#### References

- Line 143: `/api/v1/targets` (Medium)
  - ⚠️ Deprecated context
- Line 143: `/api/v1/targets` (Medium)
  - ⚠️ Deprecated context
- Line 143: `localhost:9090/api/v1` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/feature-docs/API_CHANGELOG.md

- **Total References**: 10
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 10

#### References

- Line 70: `/api/v1/contracts/?contact_email=...` (Medium)
  - ⚠️ Deprecated context
- Line 71: `/api/v1/contracts/?contact_name=...` (Medium)
  - ⚠️ Deprecated context
- Line 72: `/api/v1/contracts/?server_type=...` (Medium)
  - ⚠️ Deprecated context
- Line 73: `/api/v1/contracts/?server_url=...` (Medium)
  - ⚠️ Deprecated context
- Line 74: `/api/v1/contracts/?min_availability=...` (Medium)
  - ⚠️ Deprecated context
- Line 75: `/api/v1/contracts/?max_latency_ms=...` (Medium)
  - ⚠️ Deprecated context
- Line 76: `/api/v1/contracts/?model_name=...` (Medium)
  - ⚠️ Deprecated context
- Line 99: `/api/v1/contracts/` (Medium)
  - ⚠️ Deprecated context
- Line 100: `/api/v1/contracts/{id}/` (Medium)
  - ⚠️ Deprecated context
- Line 101: `/api/v1/contracts/{id}/validate/` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/feature-docs/API_CONTRACTS.md

- **Total References**: 17
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 17

#### References

- Line 27: `localhost:8000/api/v1` (Medium)
  - ⚠️ Deprecated context
- Line 41: `/api/v1/openapi.json` (Medium)
  - ⚠️ Deprecated context
- Line 41: `/api/v1/openapi.json` (Medium)
  - ⚠️ Deprecated context
- Line 42: `/api/v1/openapi.yaml` (Medium)
  - ⚠️ Deprecated context
- Line 42: `/api/v1/openapi.yaml` (Medium)
  - ⚠️ Deprecated context
- Line 109: `/api/v1/resource/?page=2` (Medium)
  - ⚠️ Deprecated context
- Line 109: `/api/v1/resource/?page=2` (Medium)
  - ⚠️ Deprecated context
- Line 185: `/api/v1/contracts/` (Medium)
  - ⚠️ Deprecated context
- Line 185: `/api/v1/contracts/` (Medium)
  - ⚠️ Deprecated context
- Line 194: `/api/v1/contracts/` (Medium)
  - ⚠️ Deprecated context
- Line 194: `/api/v1/contracts/` (Medium)
  - ⚠️ Deprecated context
- Line 200: `/api/v1/auth/login/` (Medium)
  - ⚠️ Deprecated context
- Line 249: `/api/v1/contracts/` (Medium)
  - ⚠️ Deprecated context
- Line 277: `/api/v1/contracts/?page=1&page_size=50` (Medium)
  - ⚠️ Deprecated context
- Line 304: `/api/v1/contracts/{id}/` (Medium)
  - ⚠️ Deprecated context
- Line 311: `/api/v1/contracts/{id}/` (Medium)
  - ⚠️ Deprecated context
- Line 323: `/api/v1/contracts/{id}/` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/feature-docs/API_DOCUMENTATION.md

- **Total References**: 24
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 24

#### References

- Line 35: `localhost:8000/api/v1` (Medium)
  - ⚠️ Deprecated context
- Line 50: `/api/v1/auth/login/` (Medium)
  - ⚠️ Deprecated context
- Line 80: `/api/v1/auth/refresh/` (Medium)
  - ⚠️ Deprecated context
- Line 134: `/api/v1/tenants/{tenant_id}/config/` (Medium)
  - ⚠️ Deprecated context
- Line 170: `/api/v1/tenants/{tenant_id}/config/` (Medium)
  - ⚠️ Deprecated context
- Line 415: `/api/v1/contracts/?tag=analytics&tag=sales&ordering=-created_at` (Medium)
  - ⚠️ Deprecated context
- Line 806: `/api/v1/scheduled-ingestions/` (Medium)
  - ⚠️ Deprecated context
- Line 850: `/api/v1/scheduled-ingestions/` (Medium)
  - ⚠️ Deprecated context
- Line 876: `/api/v1/scheduled-ingestions/{id}/` (Medium)
  - ⚠️ Deprecated context
- Line 883: `/api/v1/scheduled-ingestions/{id}/` (Medium)
  - ⚠️ Deprecated context
- Line 899: `/api/v1/scheduled-ingestions/{id}/` (Medium)
  - ⚠️ Deprecated context
- Line 908: `/api/v1/scheduled-ingestions/{id}/runs/` (Medium)
  - ⚠️ Deprecated context
- Line 942: `/api/v1/scheduled-ingestions/{id}/runs/{run_id}/` (Medium)
  - ⚠️ Deprecated context
- Line 949: `/api/v1/scheduled-ingestions/{id}/trigger/` (Medium)
  - ⚠️ Deprecated context
- Line 1052: `/api/v1/assets/?page=2` (Medium)
  - ⚠️ Deprecated context
- Line 1052: `/api/v1/assets/?page=2` (Medium)
  - ⚠️ Deprecated context
- Line 1186: `/api/v1/assets/` (Medium)
  - ⚠️ Deprecated context
- Line 1186: `/api/v1/assets/` (Medium)
  - ⚠️ Deprecated context
- Line 1199: `/api/v1/assets/?status=ACTIVE&domain=marketing` (Medium)
  - ⚠️ Deprecated context
- Line 1199: `/api/v1/assets/?status=ACTIVE&domain=marketing` (Medium)
  - ⚠️ Deprecated context
- ... and 4 more references

### docs/deprecated-doc/feature-docs/API_VERSIONING_STRATEGY.md

- **Total References**: 6
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 6

#### References

- Line 42: `/api/v1/...` (Medium)
  - ⚠️ Deprecated context
- Line 42: `/api/v1/...` (Medium)
  - ⚠️ Deprecated context
- Line 64: `/api/v1/assets/` (Medium)
  - ⚠️ Deprecated context
- Line 72: `/api/v1/assets/` (Medium)
  - ⚠️ Deprecated context
- Line 128: `/api/v1/old-endpoint/` (Medium)
  - ⚠️ Deprecated context
- Line 128: `/api/v1/old-endpoint/` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/feature-docs/ASSET_DEPENDENCIES_GRAPH.md

- **Total References**: 2
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 2

#### References

- Line 117: `/api/v1/assets/assets/{id}/dependencies/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 128: `/api/v1/assets/assets/{id}/dependencies/?direction=both&format=d3` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/feature-docs/ASSET_HEALTH_SCORE.md

- **Total References**: 2
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 2

#### References

- Line 204: `/api/v1/assets/assets/{id}/health-score/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 214: `/api/v1/assets/assets/{id}/health-score/?breakdown=true` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/feature-docs/ASSET_POPULARITY_METRICS.md

- **Total References**: 4
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 4

#### References

- Line 198: `/api/v1/assets/assets/{id}/track-view/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 204: `/api/v1/assets/assets/{id}/track-view/` (Medium)
  - ⚠️ Deprecated context
- Line 214: `/api/v1/assets/assets/{id}/track-download/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 220: `/api/v1/assets/assets/{id}/track-download/` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/feature-docs/ASSET_RECOMMENDATIONS.md

- **Total References**: 2
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 2

#### References

- Line 170: `/api/v1/assets/assets/recommendations/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 184: `/api/v1/assets/assets/recommendations/?user_id=uuid&limit=10` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/feature-docs/DOCUMENTATION_REVIEW_REPORT.md

- **Total References**: 28
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 28

#### References

- Line 83: `/api/v1/auth/*` (Medium)
  - ⚠️ Deprecated context
- Line 83: `/api/v1/auth/*` (Medium)
  - ⚠️ Deprecated context
- Line 84: `/api/v1/tenants/*` (Medium)
  - ⚠️ Deprecated context
- Line 84: `/api/v1/tenants/*` (Medium)
  - ⚠️ Deprecated context
- Line 85: `/api/v1/users/*` (Medium)
  - ⚠️ Deprecated context
- Line 85: `/api/v1/users/*` (Medium)
  - ⚠️ Deprecated context
- Line 86: `/api/v1/files/*` (Medium)
  - ⚠️ Deprecated context
- Line 86: `/api/v1/files/*` (Medium)
  - ⚠️ Deprecated context
- Line 87: `/api/v1/datasets/*` (Medium)
  - ⚠️ Deprecated context
- Line 87: `/api/v1/datasets/*` (Medium)
  - ⚠️ Deprecated context
- Line 88: `/api/v1/assets/*` (Medium)
  - ⚠️ Deprecated context
- Line 88: `/api/v1/assets/*` (Medium)
  - ⚠️ Deprecated context
- Line 89: `/api/v1/contracts/*` (Medium)
  - ⚠️ Deprecated context
- Line 89: `/api/v1/contracts/*` (Medium)
  - ⚠️ Deprecated context
- Line 90: `/api/v1/jobs/*` (Medium)
  - ⚠️ Deprecated context
- Line 90: `/api/v1/jobs/*` (Medium)
  - ⚠️ Deprecated context
- Line 91: `/api/v1/dq/*` (Medium)
  - ⚠️ Deprecated context
- Line 91: `/api/v1/dq/*` (Medium)
  - ⚠️ Deprecated context
- Line 92: `/api/v1/compliance/*` (Medium)
  - ⚠️ Deprecated context
- Line 92: `/api/v1/compliance/*` (Medium)
  - ⚠️ Deprecated context
- ... and 8 more references

### docs/deprecated-doc/feature-docs/FEATURES_AND_FUNCTIONALITIES.md

- **Total References**: 104
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 104

#### References

- Line 93: `/api/v1/tenants/*` (Medium)
  - ⚠️ Deprecated context
- Line 93: `/api/v1/tenants/*` (Medium)
  - ⚠️ Deprecated context
- Line 119: `/api/v1/users/*` (Medium)
  - ⚠️ Deprecated context
- Line 119: `/api/v1/users/*` (Medium)
  - ⚠️ Deprecated context
- Line 145: `/api/v1/auth/*` (Medium)
  - ⚠️ Deprecated context
- Line 145: `/api/v1/auth/*` (Medium)
  - ⚠️ Deprecated context
- Line 170: `/api/v1/roles/*` (Medium)
  - ⚠️ Deprecated context
- Line 170: `/api/v1/roles/*` (Medium)
  - ⚠️ Deprecated context
- Line 195: `/api/v1/audit-events/*` (Medium)
  - ⚠️ Deprecated context
- Line 195: `/api/v1/audit-events/*` (Medium)
  - ⚠️ Deprecated context
- Line 223: `/api/v1/assets/*` (Medium)
  - ⚠️ Deprecated context
- Line 223: `/api/v1/assets/*` (Medium)
  - ⚠️ Deprecated context
- Line 248: `/api/v1/assets/{id}/activate` (Medium)
  - ⚠️ Deprecated context
- Line 248: `/api/v1/assets/{id}/retire` (Medium)
  - ⚠️ Deprecated context
- Line 248: `/api/v1/assets/{id}/activate` (Medium)
  - ⚠️ Deprecated context
- Line 248: `/api/v1/assets/{id}/retire` (Medium)
  - ⚠️ Deprecated context
- Line 274: `/api/v1/datasets/*` (Medium)
  - ⚠️ Deprecated context
- Line 274: `/api/v1/datasets/*` (Medium)
  - ⚠️ Deprecated context
- Line 299: `/api/v1/assets/{id}/contracts/*` (Medium)
  - ⚠️ Deprecated context
- Line 299: `/api/v1/assets/{id}/contracts/*` (Medium)
  - ⚠️ Deprecated context
- ... and 84 more references

### docs/deprecated-doc/feature-docs/MONITORING_OBSERVABILITY.md

- **Total References**: 3
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 3

#### References

- Line 365: `/api/v1/targets` (Medium)
  - ⚠️ Deprecated context
- Line 365: `/api/v1/targets` (Medium)
  - ⚠️ Deprecated context
- Line 365: `localhost:9090/api/v1` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/feature-docs/MONITORING_SCRIPTS.md

- **Total References**: 11
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 11

#### References

- Line 268: `/api/v1/query` (Medium)
  - ⚠️ Deprecated context
- Line 268: `/api/v1/query` (Medium)
  - ⚠️ Deprecated context
- Line 361: `/api/v1/query?query=up` (Medium)
  - ⚠️ Deprecated context
- Line 361: `/api/v1/query?query=up` (Medium)
  - ⚠️ Deprecated context
- Line 361: `localhost:9090/api/v1` (Medium)
  - ⚠️ Deprecated context
- Line 366: `/api/v1/targets` (Medium)
  - ⚠️ Deprecated context
- Line 366: `/api/v1/targets` (Medium)
  - ⚠️ Deprecated context
- Line 366: `localhost:9090/api/v1` (Medium)
  - ⚠️ Deprecated context
- Line 432: `/api/v1/targets` (Medium)
  - ⚠️ Deprecated context
- Line 432: `/api/v1/targets` (Medium)
  - ⚠️ Deprecated context
- Line 432: `localhost:9090/api/v1` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/feature-docs/OBSERVABILITY_DATA_SLAS.md

- **Total References**: 1
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 1

#### References

- Line 67: `/api/v1/observability/slas/` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/feature-docs/OBSERVABILITY_INCIDENT_MANAGEMENT.md

- **Total References**: 3
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 3

#### References

- Line 55: `/api/v1/observability/incidents/` (Medium)
  - ⚠️ Deprecated context
- Line 123: `/api/v1/observability/incidents/` (Medium)
  - ⚠️ Deprecated context
- Line 155: `/api/v1/observability/incidents/update/?incident_id={id}` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/feature-docs/OBSERVABILITY_PIPELINE_MONITORING.md

- **Total References**: 1
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 1

#### References

- Line 46: `/api/v1/observability/pipelines/` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/feature-docs/OPENTELEMETRY_METRICS_DEPLOYMENT.md

- **Total References**: 16
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 16

#### References

- Line 152: `/api/v1/query?query=histogram_quantile(0.95,rate(http_request_duration_seconds_bucket[5m]` (Medium)
  - ⚠️ Deprecated context
- Line 152: `/api/v1/query?query=histogram_quantile(0.95,rate(http_request_duration_seconds_bucket[5m]` (Medium)
  - ⚠️ Deprecated context
- Line 155: `/api/v1/query?query=rate(http_errors_total[5m]` (Medium)
  - ⚠️ Deprecated context
- Line 155: `/api/v1/query?query=rate(http_errors_total[5m]` (Medium)
  - ⚠️ Deprecated context
- Line 172: `/api/v1/targets` (Medium)
  - ⚠️ Deprecated context
- Line 172: `/api/v1/targets` (Medium)
  - ⚠️ Deprecated context
- Line 186: `/api/v1/query?query=http_requests_total` (Medium)
  - ⚠️ Deprecated context
- Line 186: `/api/v1/query?query=http_requests_total` (Medium)
  - ⚠️ Deprecated context
- Line 187: `/api/v1/query?query=jobs_started_total` (Medium)
  - ⚠️ Deprecated context
- Line 187: `/api/v1/query?query=jobs_started_total` (Medium)
  - ⚠️ Deprecated context
- Line 188: `/api/v1/query?query=tenant_running_jobs` (Medium)
  - ⚠️ Deprecated context
- Line 188: `/api/v1/query?query=tenant_running_jobs` (Medium)
  - ⚠️ Deprecated context
- Line 202: `/api/v1/query?query=absent(http_requests_total` (Medium)
  - ⚠️ Deprecated context
- Line 202: `/api/v1/query?query=absent(http_requests_total` (Medium)
  - ⚠️ Deprecated context
- Line 240: `/api/v1/alerts` (Medium)
  - ⚠️ Deprecated context
- Line 240: `/api/v1/alerts` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/feature-docs/SCHEDULED_INGESTION_MONITORING_DLQ_COST.md

- **Total References**: 5
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 5

#### References

- Line 29: `/api/v1/scheduled-ingestions/dashboard/` (Medium)
  - ⚠️ Deprecated context
- Line 157: `/api/v1/scheduled-ingestions/dead-letter-queue/` (Medium)
  - ⚠️ Deprecated context
- Line 203: `/api/v1/scheduled-ingestions/{id}/dlq/{dlq_item_id}/retry/` (Medium)
  - ⚠️ Deprecated context
- Line 216: `/api/v1/scheduled-ingestions/{id}/dlq/{dlq_item_id}/resolve/` (Medium)
  - ⚠️ Deprecated context
- Line 304: `/api/v1/scheduled-ingestions/costs/` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/feature-docs/STAKEHOLDER_NOTIFICATION_DCS_REMOVAL.md

- **Total References**: 1
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 1

#### References

- Line 106: `/api/v1/contracts/{id}/validate/` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/feature-docs/USER_GUIDE.md

- **Total References**: 2
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 2

#### References

- Line 681: `/api/v1/assets/` (Medium)
  - ⚠️ Deprecated context
- Line 681: `/api/v1/assets/` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/feature-docs/USER_GUIDE_CONTRACTS.md

- **Total References**: 19
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 19

#### References

- Line 39: `/api/v1/contracts/` (Medium)
  - ⚠️ Deprecated context
- Line 54: `/api/v1/contracts/` (Medium)
  - ⚠️ Deprecated context
- Line 98: `/api/v1/contracts/` (Medium)
  - ⚠️ Deprecated context
- Line 107: `/api/v1/contracts/{contract_id}/` (Medium)
  - ⚠️ Deprecated context
- Line 131: `/api/v1/contracts/{contract_id}/` (Medium)
  - ⚠️ Deprecated context
- Line 249: `/api/v1/contracts/?contact_email=support@example.com` (Medium)
  - ⚠️ Deprecated context
- Line 255: `/api/v1/contracts/?server_type=s3` (Medium)
  - ⚠️ Deprecated context
- Line 261: `/api/v1/contracts/?model_name=customer` (Medium)
  - ⚠️ Deprecated context
- Line 267: `/api/v1/contracts/?min_availability=99.5` (Medium)
  - ⚠️ Deprecated context
- Line 273: `/api/v1/contracts/?contact_email=support@example.com&server_type=s3&min_availability=99.5` (Medium)
  - ⚠️ Deprecated context
- Line 281: `/api/v1/contracts/?ordering=-created_at` (Medium)
  - ⚠️ Deprecated context
- Line 287: `/api/v1/contracts/?ordering=-created_at,quality_score` (Medium)
  - ⚠️ Deprecated context
- Line 297: `/api/v1/contracts/{contract_id}/lineage/contracts/` (Medium)
  - ⚠️ Deprecated context
- Line 303: `/api/v1/contracts/{contract_id}/models/{model_name}/lineage/` (Medium)
  - ⚠️ Deprecated context
- Line 309: `/api/v1/contracts/{contract_id}/fields/{field_name}/lineage/` (Medium)
  - ⚠️ Deprecated context
- Line 315: `/api/v1/contracts/{contract_id}/lineage/full/` (Medium)
  - ⚠️ Deprecated context
- Line 323: `/api/v1/contracts/{contract_id}/lineage/visualization/?format=json` (Medium)
  - ⚠️ Deprecated context
- Line 329: `/api/v1/contracts/{contract_id}/lineage/visualization/?format=dot` (Medium)
  - ⚠️ Deprecated context
- Line 335: `/api/v1/contracts/{contract_id}/lineage/visualization/?format=mermaid` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/feature-docs/USER_JOURNEYS.md

- **Total References**: 44
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 44

#### References

- Line 100: `/api/v1/assets` (Medium)
  - ⚠️ Deprecated context
- Line 100: `/api/v1/files` (Medium)
  - ⚠️ Deprecated context
- Line 100: `/api/v1/compliance-runs` (Medium)
  - ⚠️ Deprecated context
- Line 100: `/api/v1/dq-runs` (Medium)
  - ⚠️ Deprecated context
- Line 100: `/api/v1/contracts` (Medium)
  - ⚠️ Deprecated context
- Line 100: `/api/v1/assets` (Medium)
  - ⚠️ Deprecated context
- Line 100: `/api/v1/files` (Medium)
  - ⚠️ Deprecated context
- Line 100: `/api/v1/compliance-runs` (Medium)
  - ⚠️ Deprecated context
- Line 100: `/api/v1/dq-runs` (Medium)
  - ⚠️ Deprecated context
- Line 100: `/api/v1/contracts` (Medium)
  - ⚠️ Deprecated context
- Line 154: `/api/v1/assets/{id}/marketplace` (Medium)
  - ⚠️ Deprecated context
- Line 154: `/api/v1/marketplace/listings` (Medium)
  - ⚠️ Deprecated context
- Line 154: `/api/v1/assets/{id}/marketplace` (Medium)
  - ⚠️ Deprecated context
- Line 154: `/api/v1/marketplace/listings` (Medium)
  - ⚠️ Deprecated context
- Line 217: `/api/v1/contracts` (Medium)
  - ⚠️ Deprecated context
- Line 217: `/api/v1/files` (Medium)
  - ⚠️ Deprecated context
- Line 217: `/api/v1/datasets` (Medium)
  - ⚠️ Deprecated context
- Line 217: `/api/v1/jobs` (Medium)
  - ⚠️ Deprecated context
- Line 217: `/api/v1/contracts` (Medium)
  - ⚠️ Deprecated context
- Line 217: `/api/v1/files` (Medium)
  - ⚠️ Deprecated context
- ... and 24 more references

### docs/deprecated-doc/implementation-summaries/DEVELOPER_GUIDE_IMPLEMENTATION_PATTERNS.md

- **Total References**: 7
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 7

#### References

- Line 231: `/api/v1/contracts/` (Medium)
  - ⚠️ Deprecated context
- Line 231: `/api/v1/contracts/` (Medium)
  - ⚠️ Deprecated context
- Line 422: `/api/v1/contracts/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 423: `/api/v1/contracts/{id}/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 424: `/api/v1/contracts/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 425: `/api/v1/contracts/{id}/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context
- Line 426: `/api/v1/contracts/{id}/` (Medium)
  - ⚠️ In comment
  - ⚠️ Deprecated context

### docs/deprecated-doc/implementation-summaries/TEST_ENVIRONMENT_IMPLEMENTATION_SUMMARY.md

- **Total References**: 4
- **Categories**: test
- **Priority Breakdown**:
  - High: 4

#### References

- Line 277: `localhost:8001/api/v1` (High)
  - ⚠️ Deprecated context
- Line 289: `localhost:8001/api/v1` (High)
  - ⚠️ Deprecated context
- Line 369: `localhost:8001/api/v1` (High)
  - ⚠️ Deprecated context
- Line 372: `localhost:8001/api/v1` (High)
  - ⚠️ Deprecated context

### docs/deprecated-doc/migration-strategies/MICROSERVICES_MIGRATION_STRATEGY.md

- **Total References**: 56
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 56

#### References

- Line 96: `/api/v1/search` (Medium)
  - ⚠️ Deprecated context
- Line 96: `/api/v1/search` (Medium)
  - ⚠️ Deprecated context
- Line 121: `/api/v1/search/*` (Medium)
  - ⚠️ Deprecated context
- Line 121: `/api/v1/search/*` (Medium)
  - ⚠️ Deprecated context
- Line 155: `/api/v1/observability/*` (Medium)
  - ⚠️ Deprecated context
- Line 155: `/api/v1/observability/*` (Medium)
  - ⚠️ Deprecated context
- Line 180: `/api/v1/observability/*` (Medium)
  - ⚠️ Deprecated context
- Line 180: `/api/v1/observability/*` (Medium)
  - ⚠️ Deprecated context
- Line 251: `/api/v1/webhooks/*` (Medium)
  - ⚠️ Deprecated context
- Line 251: `/api/v1/webhooks/*` (Medium)
  - ⚠️ Deprecated context
- Line 275: `/api/v1/webhooks/*` (Medium)
  - ⚠️ Deprecated context
- Line 275: `/api/v1/webhooks/*` (Medium)
  - ⚠️ Deprecated context
- Line 309: `/api/v1/semantic/*` (Medium)
  - ⚠️ Deprecated context
- Line 309: `/api/v1/semantic/*` (Medium)
  - ⚠️ Deprecated context
- Line 332: `/api/v1/semantic/*` (Medium)
  - ⚠️ Deprecated context
- Line 332: `/api/v1/semantic/*` (Medium)
  - ⚠️ Deprecated context
- Line 402: `/api/v1/contracts/*` (Medium)
  - ⚠️ Deprecated context
- Line 402: `/api/v1/contracts/*` (Medium)
  - ⚠️ Deprecated context
- Line 433: `/api/v1/contracts/*` (Medium)
  - ⚠️ Deprecated context
- Line 433: `/api/v1/contracts/*` (Medium)
  - ⚠️ Deprecated context
- ... and 36 more references

### docs/deprecated-doc/migration-strategies/MIGRATION_GUIDE_DCS_TO_ODCS.md

- **Total References**: 2
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 2

#### References

- Line 130: `/api/v1/contracts/{id}/validate/` (Medium)
  - ⚠️ Deprecated context
- Line 142: `/api/v1/contracts/{id}/` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/phase-reports/PHASE_16_COMPLETION_REPORT.md

- **Total References**: 2
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 2

#### References

- Line 21: `/api/v1/openapi.yaml` (Medium)
  - ⚠️ Deprecated context
- Line 21: `/api/v1/openapi.yaml` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/phase-reports/PHASE_16_FINAL_SUMMARY.md

- **Total References**: 2
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 2

#### References

- Line 203: `/api/v1/openapi.yaml` (Medium)
  - ⚠️ Deprecated context
- Line 203: `/api/v1/openapi.yaml` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/phase-reports/PHASE_16_IMPLEMENTATION_SUMMARY.md

- **Total References**: 2
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 2

#### References

- Line 182: `/api/v1/openapi.yaml` (Medium)
  - ⚠️ Deprecated context
- Line 182: `/api/v1/openapi.yaml` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/strategy-docs/DATABASE_STRATEGY_SUMMARY.md

- **Total References**: 4
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 4

#### References

- Line 115: `/api/v1/contracts/{contract_id}` (Medium)
  - ⚠️ Deprecated context
- Line 115: `/api/v1/contracts/{contract_id}` (Medium)
  - ⚠️ Deprecated context
- Line 120: `/api/v1/assets/{asset_id}` (Medium)
  - ⚠️ Deprecated context
- Line 120: `/api/v1/assets/{asset_id}` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/strategy-docs/EVENTUAL_CONSISTENCY_PATTERNS.md

- **Total References**: 10
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 10

#### References

- Line 144: `/api/v1/contracts` (Medium)
  - ⚠️ Deprecated context
- Line 144: `/api/v1/contracts` (Medium)
  - ⚠️ Deprecated context
- Line 151: `/api/v1/assets` (Medium)
  - ⚠️ Deprecated context
- Line 151: `/api/v1/assets` (Medium)
  - ⚠️ Deprecated context
- Line 161: `/api/v1/contracts/{contract[` (Medium)
  - ⚠️ Deprecated context
- Line 161: `/api/v1/contracts/{contract[` (Medium)
  - ⚠️ Deprecated context
- Line 172: `/api/v1/assets/{asset[` (Medium)
  - ⚠️ Deprecated context
- Line 172: `/api/v1/assets/{asset[` (Medium)
  - ⚠️ Deprecated context
- Line 178: `/api/v1/contracts/{contract[` (Medium)
  - ⚠️ Deprecated context
- Line 178: `/api/v1/contracts/{contract[` (Medium)
  - ⚠️ Deprecated context

### docs/deprecated-doc/test-docs/TEST_ENVIRONMENT_README.md

- **Total References**: 11
- **Categories**: test
- **Priority Breakdown**:
  - High: 11

#### References

- Line 78: `localhost:8001/api/v1` (High)
  - ⚠️ Deprecated context
- Line 82: `localhost:8001/api/v1` (High)
  - ⚠️ Deprecated context
- Line 252: `localhost:8001/api/v1` (High)
  - ⚠️ Deprecated context
- Line 299: `localhost:8001/api/v1` (High)
  - ⚠️ Deprecated context
- Line 315: `localhost:8001/api/v1` (High)
  - ⚠️ Deprecated context
- Line 323: `localhost:8001/api/v1` (High)
  - ⚠️ Deprecated context
- Line 358: `localhost:8001/api/v1` (High)
  - ⚠️ Deprecated context
- Line 460: `localhost:8001/api/v1` (High)
  - ⚠️ Deprecated context
- Line 475: `localhost:8001/api/v1` (High)
  - ⚠️ Deprecated context
- Line 495: `localhost:8001/api/v1` (High)
  - ⚠️ Deprecated context
- Line 498: `localhost:8001/api/v1` (High)
  - ⚠️ Deprecated context

### docs/deprecated-doc/test-docs/TEST_ENVIRONMENT_SETUP.md

- **Total References**: 6
- **Categories**: test
- **Priority Breakdown**:
  - High: 6

#### References

- Line 698: `localhost:8001/api/v1` (High)
  - ⚠️ Deprecated context
- Line 715: `localhost:8001/api/v1` (High)
  - ⚠️ Deprecated context
- Line 738: `localhost:8001/api/v1` (High)
  - ⚠️ Deprecated context
- Line 757: `localhost:8001/api/v1` (High)
  - ⚠️ Deprecated context
- Line 846: `localhost:8001/api/v1` (High)
  - ⚠️ Deprecated context
- Line 852: `localhost:8001/api/v1` (High)
  - ⚠️ Deprecated context

### docs/deprecated-doc/test-docs/TEST_MAINTENANCE.md

- **Total References**: 4
- **Categories**: test
- **Priority Breakdown**:
  - High: 4

#### References

- Line 372: `/api/v1/tenants/{self.tenant.id}/config` (High)
  - ⚠️ Deprecated context
- Line 372: `/api/v1/tenants/{self.tenant.id}/config` (High)
  - ⚠️ Deprecated context
- Line 377: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
  - ⚠️ Deprecated context
- Line 377: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
  - ⚠️ Deprecated context

### docs/deprecated-doc/test-docs/TEST_USER_GUIDE.md

- **Total References**: 20
- **Categories**: test
- **Priority Breakdown**:
  - High: 20

#### References

- Line 170: `/api/v1/assets/assets/` (High)
  - ⚠️ Deprecated context
- Line 170: `/api/v1/assets/assets/` (High)
  - ⚠️ Deprecated context
- Line 197: `/api/v1/assets/assets/` (High)
  - ⚠️ Deprecated context
- Line 197: `/api/v1/assets/assets/` (High)
  - ⚠️ Deprecated context
- Line 365: `/api/v1/assets/assets/` (High)
  - ⚠️ Deprecated context
- Line 365: `/api/v1/assets/assets/` (High)
  - ⚠️ Deprecated context
- Line 538: `/api/v1/assets/assets/` (High)
  - ⚠️ Deprecated context
- Line 538: `/api/v1/assets/assets/` (High)
  - ⚠️ Deprecated context
- Line 544: `/api/v1/assets/assets/` (High)
  - ⚠️ Deprecated context
- Line 544: `/api/v1/assets/assets/` (High)
  - ⚠️ Deprecated context
- Line 567: `/api/v1/assets/assets/{asset.id}/` (High)
  - ⚠️ Deprecated context
- Line 567: `/api/v1/assets/assets/{asset.id}/` (High)
  - ⚠️ Deprecated context
- Line 579: `/api/v1/assets/assets/` (High)
  - ⚠️ Deprecated context
- Line 579: `/api/v1/assets/assets/` (High)
  - ⚠️ Deprecated context
- Line 622: `/api/v1/assets/assets/` (High)
  - ⚠️ Deprecated context
- Line 622: `/api/v1/assets/assets/` (High)
  - ⚠️ Deprecated context
- Line 637: `/api/v1/assets/assets/` (High)
  - ⚠️ Deprecated context
- Line 637: `/api/v1/assets/assets/` (High)
  - ⚠️ Deprecated context
- Line 649: `/api/v1/assets/assets/` (High)
  - ⚠️ Deprecated context
- Line 649: `/api/v1/assets/assets/` (High)
  - ⚠️ Deprecated context

### docs/implementation/p2-endpoints-implementation-summary.md

- **Total References**: 12
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 12

#### References

- Line 13: `/api/v1/ai/natural-language-search/` (Medium)
  - ⚠️ In comment
- Line 13: `/api/v1/ai/natural-language-search/` (Medium)
  - ⚠️ In comment
- Line 36: `/api/v1/ai/schema-matching/` (Medium)
  - ⚠️ In comment
- Line 36: `/api/v1/ai/schema-matching/` (Medium)
  - ⚠️ In comment
- Line 55: `/api/v1/social/ratings/` (Medium)
  - ⚠️ In comment
- Line 55: `/api/v1/social/ratings/` (Medium)
  - ⚠️ In comment
- Line 72: `/api/v1/social/reviews/` (Medium)
  - ⚠️ In comment
- Line 72: `/api/v1/social/reviews/` (Medium)
  - ⚠️ In comment
- Line 87: `/api/v1/social/comments/` (Medium)
  - ⚠️ In comment
- Line 87: `/api/v1/social/comments/` (Medium)
  - ⚠️ In comment
- Line 103: `/api/v1/social/communities/` (Medium)
  - ⚠️ In comment
- Line 103: `/api/v1/social/communities/` (Medium)
  - ⚠️ In comment

### docs/performance/asset-endpoints-optimization-summary.md

- **Total References**: 18
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 18

#### References

- Line 12: `/api/v1/assets/` (Medium)
- Line 12: `/api/v1/assets/` (Medium)
- Line 13: `/api/v1/assets/{id}/activate/` (Medium)
- Line 13: `/api/v1/assets/{id}/activate/` (Medium)
- Line 27: `/api/v1/assets/` (Medium)
- Line 27: `/api/v1/assets/` (Medium)
- Line 28: `/api/v1/assets/{id}/activate/` (Medium)
- Line 28: `/api/v1/assets/{id}/activate/` (Medium)
- Line 34: `/api/v1/assets/` (Medium)
  - ⚠️ In comment
- Line 34: `/api/v1/assets/` (Medium)
  - ⚠️ In comment
- Line 58: `/api/v1/assets/{id}/activate/` (Medium)
  - ⚠️ In comment
- Line 58: `/api/v1/assets/{id}/activate/` (Medium)
  - ⚠️ In comment
- Line 190: `/api/v1/assets/**` (Medium)
- Line 193: `/api/v1/assets/{id}/activate/**` (Medium)
- Line 241: `/api/v1/assets/` (Medium)
- Line 241: `/api/v1/assets/` (Medium)
- Line 242: `/api/v1/assets/{id}/activate/` (Medium)
- Line 242: `/api/v1/assets/{id}/activate/` (Medium)

### docs/performance/p1-endpoints-optimization-summary.md

- **Total References**: 27
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 27

#### References

- Line 12: `/api/v1/marketplace/listings/` (Medium)
- Line 12: `/api/v1/marketplace/listings/` (Medium)
- Line 13: `/api/v1/search/search/` (Medium)
- Line 13: `/api/v1/search/search/` (Medium)
- Line 14: `/api/v1/dq/dq-runs/{id}/results/` (Medium)
- Line 14: `/api/v1/dq/dq-runs/{id}/results/` (Medium)
- Line 28: `/api/v1/marketplace/listings/` (Medium)
- Line 28: `/api/v1/marketplace/listings/` (Medium)
- Line 29: `/api/v1/search/search/` (Medium)
- Line 29: `/api/v1/search/search/` (Medium)
- Line 30: `/api/v1/dq/dq-runs/{id}/results/` (Medium)
- Line 30: `/api/v1/dq/dq-runs/{id}/results/` (Medium)
- Line 36: `/api/v1/marketplace/listings/` (Medium)
  - ⚠️ In comment
- Line 36: `/api/v1/marketplace/listings/` (Medium)
  - ⚠️ In comment
- Line 58: `/api/v1/search/search/` (Medium)
  - ⚠️ In comment
- Line 58: `/api/v1/search/search/` (Medium)
  - ⚠️ In comment
- Line 83: `/api/v1/dq/dq-runs/{id}/results/` (Medium)
  - ⚠️ In comment
- Line 83: `/api/v1/dq/dq-runs/{id}/results/` (Medium)
  - ⚠️ In comment
- Line 216: `/api/v1/marketplace/listings/**` (Medium)
- Line 219: `/api/v1/search/search/**` (Medium)
- ... and 7 more references

### docs/runbooks/MIGRATION_PHASE_1.md

- **Total References**: 6
- **Categories**: docs
- **Priority Breakdown**:
  - Medium: 6

#### References

- Line 101: `/api/v1/search` (Medium)
- Line 101: `/api/v1/search` (Medium)
- Line 111: `/api/v1/search` (Medium)
- Line 111: `/api/v1/search` (Medium)
- Line 232: `/api/v1/observability` (Medium)
- Line 232: `/api/v1/observability` (Medium)

### hub/apps/orchestration/workflows/tests/test_contract_creation.py

- **Total References**: 6
- **Categories**: test
- **Priority Breakdown**:
  - High: 6

#### References

- Line 827: `/api/v1/contracts/contracts/` (High)
- Line 827: `/api/v1/contracts/contracts/` (High)
- Line 869: `/api/v1/contracts/contracts/` (High)
- Line 869: `/api/v1/contracts/contracts/` (High)
- Line 892: `/api/v1/contracts/contracts/` (High)
- Line 892: `/api/v1/contracts/contracts/` (High)

### sdk/js/node_modules/@nestjs/common/interfaces/version-options.interface.d.ts

- **Total References**: 2
- **Categories**: other
- **Priority Breakdown**:
  - Critical: 2

#### References

- Line 47: `/api/v1/route` (Critical)
- Line 47: `/api/v1/route` (Critical)

### sdk/js/src/__tests__/authentication.test.ts

- **Total References**: 10
- **Categories**: test
- **Priority Breakdown**:
  - High: 10

#### References

- Line 32: `api.example.com/api/v1` (High)
- Line 45: `api.example.com/api/v1` (High)
- Line 59: `api.example.com/api/v1` (High)
- Line 75: `api.example.com/api/v1` (High)
- Line 90: `api.example.com/api/v1` (High)
- Line 141: `api.example.com/api/v1` (High)
- Line 174: `api.example.com/api/v1` (High)
- Line 205: `api.example.com/api/v1` (High)
- Line 239: `api.example.com/api/v1` (High)
- Line 273: `api.example.com/api/v1` (High)

### sdk/js/src/__tests__/client.test.ts

- **Total References**: 2
- **Categories**: test
- **Priority Breakdown**:
  - High: 2

#### References

- Line 27: `api.example.com/api/v1` (High)
- Line 36: `api.example.com/api/v1` (High)

### sdk/js/src/__tests__/contracts-api.test.ts

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 33: `api.example.com/api/v1` (High)

### sdk/js/src/__tests__/e2e.test.ts

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 15: `api.example.com/api/v1` (High)

### sdk/js/src/__tests__/error-handling.test.ts

- **Total References**: 3
- **Categories**: test
- **Priority Breakdown**:
  - High: 3

#### References

- Line 40: `api.example.com/api/v1` (High)
- Line 461: `api.example.com/api/v1` (High)
- Line 573: `api.example.com/api/v1` (High)

### sdk/js/src/__tests__/installation.test.ts

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 96: `api.example.com/api/v1` (High)

### sdk/js/src/__tests__/integration.test.ts

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 32: `api.example.com/api/v1` (High)

### sdk/js/src/__tests__/lineage-api.test.ts

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 31: `api.example.com/api/v1` (High)

### sdk/js/src/__tests__/test-env-config.ts

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 49: `localhost:8001/api/v1` (High)

### sdk/python/datahub_interoperability/contracts.py

- **Total References**: 2
- **Categories**: other
- **Priority Breakdown**:
  - Medium: 2

#### References

- Line 578: `/api/v1/contracts/products/` (Medium)
  - ⚠️ In comment
- Line 587: `/api/v1/contracts/{odcs_id}/link-odps/` (Medium)
  - ⚠️ In comment

### sdk/python/examples/odps_usage.py

- **Total References**: 1
- **Categories**: other
- **Priority Breakdown**:
  - Critical: 1

#### References

- Line 558: `localhost:8000/api/v1` (Critical)

### sdk/python/tests/README_PREVIEW_TESTS.md

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 88: `localhost:8000/api/v1` (High)

### sdk/python/tests/test_client.py

- **Total References**: 2
- **Categories**: test
- **Priority Breakdown**:
  - High: 2

#### References

- Line 20: `api.example.com/api/v1` (High)
- Line 36: `api.example.com/api/v1` (High)

### sdk/python/tests/test_contracts_api.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 27: `api.example.com/api/v1` (High)

### sdk/python/tests/test_integration.py

- **Total References**: 2
- **Categories**: test
- **Priority Breakdown**:
  - High: 2

#### References

- Line 140: `api.example.com/api/v1` (High)
- Line 148: `localhost:8000/api/v1` (High)

### sdk/python/tests/test_lineage_api.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 15: `api.example.com/api/v1` (High)

### sdk/python/tests/test_mesh_api.py

- **Total References**: 2
- **Categories**: test
- **Priority Breakdown**:
  - High: 2

#### References

- Line 143: `api.example.com/api/v1` (High)
- Line 167: `localhost:8000/api/v1` (High)

### sdk/python/tests/test_mesh_compliance_api.py

- **Total References**: 2
- **Categories**: test
- **Priority Breakdown**:
  - High: 2

#### References

- Line 129: `api.example.com/api/v1` (High)
- Line 153: `localhost:8000/api/v1` (High)

### sdk/python/tests/test_mesh_domains_api.py

- **Total References**: 2
- **Categories**: test
- **Priority Breakdown**:
  - High: 2

#### References

- Line 130: `api.example.com/api/v1` (High)
- Line 154: `localhost:8000/api/v1` (High)

### sdk/python/tests/test_mesh_policies_api.py

- **Total References**: 5
- **Categories**: test
- **Priority Breakdown**:
  - High: 5

#### References

- Line 129: `api.example.com/api/v1` (High)
- Line 153: `localhost:8000/api/v1` (High)
- Line 312: `localhost:8000/api/v1` (High)
- Line 383: `localhost:8000/api/v1` (High)
- Line 527: `localhost:8000/api/v1` (High)

### sdk/python/tests/test_mesh_topology_api.py

- **Total References**: 2
- **Categories**: test
- **Priority Breakdown**:
  - High: 2

#### References

- Line 129: `api.example.com/api/v1` (High)
- Line 153: `localhost:8000/api/v1` (High)

### sdk/python/tests/test_odcs_export.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 122: `localhost:8000/api/v1` (High)

### sdk/python/tests/test_odcs_export_integration.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 121: `localhost:8000/api/v1` (High)

### sdk/python/tests/test_odps_filtering_integration.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 57: `localhost:8000/api/v1` (High)

### sdk/python/tests/test_odps_helpers_integration.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 57: `localhost:8000/api/v1` (High)

### sdk/python/tests/test_odps_workflows_integration.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 55: `localhost:8000/api/v1` (High)

### sdk/python/tests/test_scheduled_ingestion_api.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 15: `api.example.com/api/v1` (High)

### sdk/python/tests/test_transformation_api.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 16: `api.example.com/api/v1` (High)

### sdk/python/tests/test_transformation_api_integration.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 447: `localhost:8000/api/v1` (High)

### sdk/python/tests/test_transformation_execution_methods.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 24: `api.example.com/api/v1` (High)

### sdk/python/tests/test_transformation_pipelines_api.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 22: `api.example.com/api/v1` (High)

### sdk/python/tests/test_transformation_preview_integration.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 209: `localhost:8000/api/v1` (High)

### sdk/python/tests/test_transformation_wrangling_integration.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 108: `localhost:8000/api/v1` (High)

### sdk/python/tests/test_virtualization_api.py

- **Total References**: 2
- **Categories**: test
- **Priority Breakdown**:
  - High: 2

#### References

- Line 265: `api.example.com/api/v1` (High)
- Line 290: `localhost:8000/api/v1` (High)

### tests/DPO_TEST_FIXES_SUMMARY.md

- **Total References**: 2
- **Categories**: test
- **Priority Breakdown**:
  - High: 2

#### References

- Line 133: `/api/v1/assets/assets/{asset.id}/` (High)
- Line 133: `/api/v1/assets/assets/{asset.id}/` (High)

### tests/e2e/COVERAGE_ANALYSIS.md

- **Total References**: 22
- **Categories**: test
- **Priority Breakdown**:
  - High: 22

#### References

- Line 37: `/api/v1/assets/{id}/datasets/` (High)
- Line 38: `/api/v1/assets/{id}/contracts/` (High)
- Line 39: `/api/v1/assets/{id}/activate/` (High)
- Line 42: `/api/v1/audit/audit-events/export/` (High)
- Line 45: `/api/v1/contracts/{id}/validate/` (High)
- Line 46: `/api/v1/contracts/{id}/lint/` (High)
- Line 47: `/api/v1/contracts/{id}/convert/` (High)
- Line 48: `/api/v1/contracts/{id}/migrate/` (High)
- Line 51: `/api/v1/users/invite/` (High)
- Line 52: `/api/v1/users/{id}/roles/` (High)
- Line 55: `/api/v1/tenants/{id}/suspend/` (High)
- Line 56: `/api/v1/tenants/{id}/reactivate/` (High)
- Line 59: `/api/v1/files/init/` (High)
- Line 60: `/api/v1/files/{id}/complete/` (High)
- Line 61: `/api/v1/files/{id}/download/` (High)
- Line 62: `/api/v1/files/{id}/chunks/init/` (High)
- Line 65: `/api/v1/jobs/{id}/cancel/` (High)
- Line 68: `/api/v1/marketplace/listings/{id}/publish/` (High)
- Line 69: `/api/v1/marketplace/listings/{id}/unpublish/` (High)
- Line 70: `/api/v1/marketplace/orders/{id}/complete/` (High)
- ... and 2 more references

### tests/e2e/conftest.py

- **Total References**: 20
- **Categories**: test
- **Priority Breakdown**:
  - High: 20

#### References

- Line 435: `/api/v1/assets/assets/` (High)
- Line 435: `/api/v1/assets/assets/` (High)
- Line 482: `/api/v1/contracts/contracts/` (High)
- Line 482: `/api/v1/contracts/contracts/` (High)
- Line 517: `/api/v1/files/files/init/` (High)
- Line 517: `/api/v1/files/files/init/` (High)
- Line 652: `/api/v1/files/files/{file_id}/complete/` (High)
- Line 652: `/api/v1/files/files/{file_id}/complete/` (High)
- Line 667: `/api/v1/datasets/datasets/` (High)
- Line 667: `/api/v1/datasets/datasets/` (High)
- Line 849: `/api/v1/assets/assets/{asset_id}/activate/` (High)
- Line 849: `/api/v1/assets/assets/{asset_id}/activate/` (High)
- Line 944: `/api/v1/contracts/contracts/{contract_id}/validate/` (High)
- Line 944: `/api/v1/contracts/contracts/{contract_id}/validate/` (High)
- Line 972: `/api/v1/compliance/compliance-runs/` (High)
- Line 972: `/api/v1/compliance/compliance-runs/` (High)
- Line 994: `/api/v1/dq/dq-runs/` (High)
- Line 994: `/api/v1/dq/dq-runs/` (High)
- Line 1052: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 1052: `/api/v1/assets/assets/{asset_id}/` (High)

### tests/e2e/test_api_usability_comprehensive.py

- **Total References**: 88
- **Categories**: test
- **Priority Breakdown**:
  - High: 88

#### References

- Line 59: `/api/v1/openapi.json` (High)
- Line 59: `/api/v1/openapi.json` (High)
- Line 81: `/api/v1/openapi.yaml` (High)
- Line 81: `/api/v1/openapi.yaml` (High)
- Line 96: `/api/v1/openapi.json` (High)
- Line 96: `/api/v1/openapi.json` (High)
- Line 103: `/api/v1/auth/` (High)
- Line 103: `/api/v1/auth/` (High)
- Line 104: `/api/v1/assets/` (High)
- Line 104: `/api/v1/assets/` (High)
- Line 105: `/api/v1/contracts/` (High)
- Line 105: `/api/v1/contracts/` (High)
- Line 106: `/api/v1/datasets/` (High)
- Line 106: `/api/v1/datasets/` (High)
- Line 107: `/api/v1/jobs/` (High)
- Line 107: `/api/v1/jobs/` (High)
- Line 124: `/api/v1/openapi.json` (High)
- Line 124: `/api/v1/openapi.json` (High)
- Line 145: `/api/v1/openapi.json` (High)
- Line 145: `/api/v1/openapi.json` (High)
- ... and 68 more references

### tests/e2e/test_asset_operations.py

- **Total References**: 26
- **Categories**: test
- **Priority Breakdown**:
  - High: 26

#### References

- Line 41: `/api/v1/assets/assets/` (High)
- Line 41: `/api/v1/assets/assets/` (High)
- Line 87: `/api/v1/assets/assets/` (High)
- Line 87: `/api/v1/assets/assets/` (High)
- Line 92: `/api/v1/assets/assets/?status={AssetStatus.DRAFT}` (High)
- Line 92: `/api/v1/assets/assets/?status={AssetStatus.DRAFT}` (High)
- Line 103: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 103: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 121: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 121: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 148: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 148: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 228: `/api/v1/assets/assets/{asset_id}/activate/` (High)
- Line 228: `/api/v1/assets/assets/{asset_id}/activate/` (High)
- Line 260: `/api/v1/assets/assets/{asset_id}/activate/` (High)
- Line 260: `/api/v1/assets/assets/{asset_id}/activate/` (High)
- Line 287: `/api/v1/assets/assets/{asset_id}/contracts/` (High)
- Line 287: `/api/v1/assets/assets/{asset_id}/contracts/` (High)
- Line 330: `/api/v1/assets/assets/{asset_id}/activate/` (High)
- Line 330: `/api/v1/assets/assets/{asset_id}/activate/` (High)
- ... and 6 more references

### tests/e2e/test_asset_recommendations_popularity_health_e2e.py

- **Total References**: 12
- **Categories**: test
- **Priority Breakdown**:
  - High: 12

#### References

- Line 93: `/api/v1/assets/assets/recommendations/` (High)
- Line 93: `/api/v1/assets/assets/recommendations/` (High)
- Line 156: `/api/v1/assets/assets/{self.asset.id}/track-view/` (High)
- Line 156: `/api/v1/assets/assets/{self.asset.id}/track-view/` (High)
- Line 167: `/api/v1/assets/assets/{self.asset.id}/track-download/` (High)
- Line 167: `/api/v1/assets/assets/{self.asset.id}/track-download/` (High)
- Line 268: `/api/v1/assets/assets/{self.asset.id}/health-score/` (High)
- Line 268: `/api/v1/assets/assets/{self.asset.id}/health-score/` (High)
- Line 277: `/api/v1/assets/assets/{self.asset.id}/health-score/` (High)
- Line 277: `/api/v1/assets/assets/{self.asset.id}/health-score/` (High)
- Line 287: `/api/v1/assets/assets/{self.asset.id}/health-score/` (High)
- Line 287: `/api/v1/assets/assets/{self.asset.id}/health-score/` (High)

### tests/e2e/test_audit_compliance_journeys.py

- **Total References**: 26
- **Categories**: test
- **Priority Breakdown**:
  - High: 26

#### References

- Line 51: `/api/v1/audit/audit-events/` (High)
- Line 51: `/api/v1/audit/audit-events/` (High)
- Line 62: `/api/v1/audit/audit-events/` (High)
- Line 62: `/api/v1/audit/audit-events/` (High)
- Line 77: `/api/v1/audit/audit-events/` (High)
- Line 77: `/api/v1/audit/audit-events/` (High)
- Line 95: `/api/v1/audit/audit-events/` (High)
- Line 95: `/api/v1/audit/audit-events/` (High)
- Line 112: `/api/v1/audit/audit-events/` (High)
- Line 112: `/api/v1/audit/audit-events/` (High)
- Line 151: `/api/v1/compliance/compliance-runs/{self.compliance_run_id}/` (High)
- Line 151: `/api/v1/compliance/compliance-runs/{self.compliance_run_id}/` (High)
- Line 166: `/api/v1/compliance/compliance-runs/` (High)
- Line 166: `/api/v1/compliance/compliance-runs/` (High)
- Line 198: `/api/v1/compliance/compliance-runs/` (High)
- Line 198: `/api/v1/compliance/compliance-runs/` (High)
- Line 220: `/api/v1/compliance/compliance-runs/{self.compliance_run_id}/` (High)
- Line 220: `/api/v1/compliance/compliance-runs/{self.compliance_run_id}/` (High)
- Line 234: `/api/v1/compliance/compliance-runs/{self.compliance_run_id}/` (High)
- Line 234: `/api/v1/compliance/compliance-runs/{self.compliance_run_id}/` (High)
- ... and 6 more references

### tests/e2e/test_audit_logging.py

- **Total References**: 20
- **Categories**: test
- **Priority Breakdown**:
  - High: 20

#### References

- Line 92: `/api/v1/audit/audit-events/` (High)
- Line 92: `/api/v1/audit/audit-events/` (High)
- Line 97: `/api/v1/audit/audit-events/?action=ASSET_CREATED` (High)
- Line 97: `/api/v1/audit/audit-events/?action=ASSET_CREATED` (High)
- Line 103: `/api/v1/audit/audit-events/?resource_type=ASSET` (High)
- Line 103: `/api/v1/audit/audit-events/?resource_type=ASSET` (High)
- Line 115: `/api/v1/audit/audit-events/export/?format=csv` (High)
- Line 115: `/api/v1/audit/audit-events/export/?format=csv` (High)
- Line 120: `/api/v1/audit/audit-events/export/` (High)
- Line 120: `/api/v1/audit/audit-events/export/` (High)
- Line 127: `/api/v1/audit/audit-events/export/?format=json` (High)
- Line 127: `/api/v1/audit/audit-events/export/?format=json` (High)
- Line 131: `/api/v1/audit/audit-events/export/?format=csv` (High)
- Line 131: `/api/v1/audit/audit-events/export/?format=csv` (High)
- Line 163: `/api/v1/audit/audit-events/?start_time={start_time.isoformat(` (High)
- Line 163: `/api/v1/audit/audit-events/?start_time={start_time.isoformat(` (High)
- Line 194: `/api/v1/audit/audit-events/` (High)
- Line 194: `/api/v1/audit/audit-events/` (High)
- Line 206: `/api/v1/assets/assets/` (High)
- Line 206: `/api/v1/assets/assets/` (High)

### tests/e2e/test_auth_authorization_comprehensive.py

- **Total References**: 148
- **Categories**: test
- **Priority Breakdown**:
  - High: 148

#### References

- Line 63: `/api/v1/auth/api-keys/` (High)
- Line 63: `/api/v1/auth/api-keys/` (High)
- Line 78: `/api/v1/assets/assets/` (High)
- Line 78: `/api/v1/assets/assets/` (High)
- Line 92: `/api/v1/auth/api-keys/` (High)
- Line 92: `/api/v1/auth/api-keys/` (High)
- Line 106: `/api/v1/assets/assets/` (High)
- Line 106: `/api/v1/assets/assets/` (High)
- Line 113: `/api/v1/assets/assets/` (High)
- Line 113: `/api/v1/assets/assets/` (High)
- Line 133: `/api/v1/assets/assets/` (High)
- Line 133: `/api/v1/assets/assets/` (High)
- Line 142: `/api/v1/auth/api-keys/` (High)
- Line 142: `/api/v1/auth/api-keys/` (High)
- Line 150: `/api/v1/auth/api-keys/{api_key_id}/` (High)
- Line 150: `/api/v1/auth/api-keys/{api_key_id}/` (High)
- Line 160: `/api/v1/assets/assets/` (High)
- Line 160: `/api/v1/assets/assets/` (High)
- Line 169: `/api/v1/auth/api-keys/` (High)
- Line 169: `/api/v1/auth/api-keys/` (High)
- ... and 128 more references

### tests/e2e/test_authentication.py

- **Total References**: 38
- **Categories**: test
- **Priority Breakdown**:
  - High: 38

#### References

- Line 55: `/api/v1/auth/login/` (High)
- Line 55: `/api/v1/auth/login/` (High)
- Line 94: `/api/v1/auth/login/` (High)
- Line 94: `/api/v1/auth/login/` (High)
- Line 116: `/api/v1/auth/login/` (High)
- Line 116: `/api/v1/auth/login/` (High)
- Line 144: `/api/v1/auth/login/` (High)
- Line 144: `/api/v1/auth/login/` (High)
- Line 156: `/api/v1/auth/refresh/` (High)
- Line 156: `/api/v1/auth/refresh/` (High)
- Line 175: `/api/v1/auth/refresh/` (High)
- Line 175: `/api/v1/auth/refresh/` (High)
- Line 204: `/api/v1/auth/refresh/` (High)
- Line 204: `/api/v1/auth/refresh/` (High)
- Line 227: `/api/v1/auth/login/` (High)
- Line 227: `/api/v1/auth/login/` (High)
- Line 253: `/api/v1/auth/logout/` (High)
- Line 253: `/api/v1/auth/logout/` (High)
- Line 298: `/api/v1/auth/password-reset/` (High)
- Line 298: `/api/v1/auth/password-reset/` (High)
- ... and 18 more references

### tests/e2e/test_cli_e2e.py

- **Total References**: 2
- **Categories**: test
- **Priority Breakdown**:
  - High: 2

#### References

- Line 102: `localhost:8000/api/v1` (High)
- Line 107: `localhost:8000/api/v1` (High)

### tests/e2e/test_complete_journeys_enhanced.py

- **Total References**: 10
- **Categories**: test
- **Priority Breakdown**:
  - High: 10

#### References

- Line 309: `/api/v1/assets/assets/{asset_id}/activate/` (High)
- Line 309: `/api/v1/assets/assets/{asset_id}/activate/` (High)
- Line 382: `/api/v1/marketplace/listings/` (High)
- Line 382: `/api/v1/marketplace/listings/` (High)
- Line 396: `/api/v1/marketplace/listings/{listing_id}/publish/` (High)
- Line 396: `/api/v1/marketplace/listings/{listing_id}/publish/` (High)
- Line 402: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 402: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 428: `/api/v1/marketplace/orders/` (High)
- Line 428: `/api/v1/marketplace/orders/` (High)

### tests/e2e/test_complete_user_journeys.py

- **Total References**: 34
- **Categories**: test
- **Priority Breakdown**:
  - High: 34

#### References

- Line 110: `/api/v1/assets/assets/` (High)
- Line 110: `/api/v1/assets/assets/` (High)
- Line 122: `/api/v1/files/files/init/` (High)
- Line 122: `/api/v1/files/files/init/` (High)
- Line 149: `/api/v1/files/files/{file_id}/complete/` (High)
- Line 149: `/api/v1/files/files/{file_id}/complete/` (High)
- Line 156: `/api/v1/datasets/datasets/` (High)
- Line 156: `/api/v1/datasets/datasets/` (High)
- Line 164: `/api/v1/compliance/compliance-runs/` (High)
- Line 164: `/api/v1/compliance/compliance-runs/` (High)
- Line 172: `/api/v1/dq/dq-runs/` (High)
- Line 172: `/api/v1/dq/dq-runs/` (High)
- Line 201: `/api/v1/contracts/contracts/` (High)
- Line 201: `/api/v1/contracts/contracts/` (High)
- Line 213: `/api/v1/contracts/contracts/{contract_id}/validate/` (High)
- Line 213: `/api/v1/contracts/contracts/{contract_id}/validate/` (High)
- Line 229: `/api/v1/assets/assets/{asset_id}/datasets/` (High)
- Line 229: `/api/v1/assets/assets/{asset_id}/datasets/` (High)
- Line 235: `/api/v1/assets/assets/{asset_id}/contracts/` (High)
- Line 235: `/api/v1/assets/assets/{asset_id}/contracts/` (High)
- ... and 14 more references

### tests/e2e/test_compliance_service.py

- **Total References**: 8
- **Categories**: test
- **Priority Breakdown**:
  - High: 8

#### References

- Line 184: `/api/v1/compliance/compliance-runs/` (High)
- Line 184: `/api/v1/compliance/compliance-runs/` (High)
- Line 236: `/api/v1/compliance/compliance-runs/` (High)
- Line 236: `/api/v1/compliance/compliance-runs/` (High)
- Line 241: `/api/v1/compliance/compliance-runs/?asset_id={asset_id1}` (High)
- Line 241: `/api/v1/compliance/compliance-runs/?asset_id={asset_id1}` (High)
- Line 256: `/api/v1/compliance/compliance-runs/{compliance_run_id}/` (High)
- Line 256: `/api/v1/compliance/compliance-runs/{compliance_run_id}/` (High)

### tests/e2e/test_contract_first_comprehensive.py

- **Total References**: 2
- **Categories**: test
- **Priority Breakdown**:
  - High: 2

#### References

- Line 239: `/api/v1/contracts/contracts/{contract_id}/validate/` (High)
- Line 239: `/api/v1/contracts/contracts/{contract_id}/validate/` (High)

### tests/e2e/test_contract_first_flow.py

- **Total References**: 24
- **Categories**: test
- **Priority Breakdown**:
  - High: 24

#### References

- Line 110: `/api/v1/assets/assets/` (High)
- Line 110: `/api/v1/assets/assets/` (High)
- Line 122: `/api/v1/contracts/contracts/` (High)
- Line 122: `/api/v1/contracts/contracts/` (High)
- Line 136: `/api/v1/contracts/contracts/{contract_id}/validate/` (High)
- Line 136: `/api/v1/contracts/contracts/{contract_id}/validate/` (High)
- Line 160: `/api/v1/files/files/init/` (High)
- Line 160: `/api/v1/files/files/init/` (High)
- Line 191: `/api/v1/files/files/{file_id}/complete/` (High)
- Line 191: `/api/v1/files/files/{file_id}/complete/` (High)
- Line 199: `/api/v1/datasets/datasets/` (High)
- Line 199: `/api/v1/datasets/datasets/` (High)
- Line 210: `/api/v1/compliance/compliance-runs/` (High)
- Line 210: `/api/v1/compliance/compliance-runs/` (High)
- Line 223: `/api/v1/dq/dq-runs/` (High)
- Line 223: `/api/v1/dq/dq-runs/` (High)
- Line 256: `/api/v1/assets/assets/{asset_id}/datasets/` (High)
- Line 256: `/api/v1/assets/assets/{asset_id}/datasets/` (High)
- Line 262: `/api/v1/assets/assets/{asset_id}/contracts/` (High)
- Line 262: `/api/v1/assets/assets/{asset_id}/contracts/` (High)
- ... and 4 more references

### tests/e2e/test_contract_migration.py

- **Total References**: 20
- **Categories**: test
- **Priority Breakdown**:
  - High: 20

#### References

- Line 44: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 44: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 95: `/api/v1/contracts/contracts/{contract_id}/migrate/` (High)
- Line 95: `/api/v1/contracts/contracts/{contract_id}/migrate/` (High)
- Line 162: `/api/v1/contracts/contracts/{contract_id}/migrate/` (High)
- Line 162: `/api/v1/contracts/contracts/{contract_id}/migrate/` (High)
- Line 228: `/api/v1/contracts/contracts/{contract_id}/migrate/` (High)
- Line 228: `/api/v1/contracts/contracts/{contract_id}/migrate/` (High)
- Line 258: `/api/v1/contracts/contracts/{contract_id}/migrate/` (High)
- Line 258: `/api/v1/contracts/contracts/{contract_id}/migrate/` (High)
- Line 284: `/api/v1/contracts/contracts/{contract_id}/migrate/` (High)
- Line 284: `/api/v1/contracts/contracts/{contract_id}/migrate/` (High)
- Line 337: `/api/v1/contracts/contracts/{contract_id}/migrate/` (High)
- Line 337: `/api/v1/contracts/contracts/{contract_id}/migrate/` (High)
- Line 370: `/api/v1/contracts/contracts/{contract_id}/migrate/` (High)
- Line 370: `/api/v1/contracts/contracts/{contract_id}/migrate/` (High)
- Line 418: `/api/v1/contracts/contracts/{contract_id}/migrate/` (High)
- Line 418: `/api/v1/contracts/contracts/{contract_id}/migrate/` (High)
- Line 483: `/api/v1/contracts/contracts/{contract_id}/migrate/` (High)
- Line 483: `/api/v1/contracts/contracts/{contract_id}/migrate/` (High)

### tests/e2e/test_contract_normalization_enhanced_e2e.py

- **Total References**: 2
- **Categories**: test
- **Priority Breakdown**:
  - High: 2

#### References

- Line 228: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 228: `/api/v1/contracts/contracts/{contract_id}/` (High)

### tests/e2e/test_contract_only_comprehensive.py

- **Total References**: 6
- **Categories**: test
- **Priority Breakdown**:
  - High: 6

#### References

- Line 148: `/api/v1/assets/assets/{asset_id}/activate/` (High)
- Line 148: `/api/v1/assets/assets/{asset_id}/activate/` (High)
- Line 177: `/api/v1/assets/assets/{asset_id}/activate/` (High)
- Line 177: `/api/v1/assets/assets/{asset_id}/activate/` (High)
- Line 201: `/api/v1/assets/assets/{asset_id}/activate/` (High)
- Line 201: `/api/v1/assets/assets/{asset_id}/activate/` (High)

### tests/e2e/test_contract_operations.py

- **Total References**: 22
- **Categories**: test
- **Priority Breakdown**:
  - High: 22

#### References

- Line 149: `/api/v1/contracts/contracts/` (High)
- Line 149: `/api/v1/contracts/contracts/` (High)
- Line 154: `/api/v1/contracts/contracts/?asset_id={asset_id}` (High)
- Line 154: `/api/v1/contracts/contracts/?asset_id={asset_id}` (High)
- Line 168: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 168: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 185: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 185: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 245: `/api/v1/contracts/contracts/{contract_id}/validate/` (High)
- Line 245: `/api/v1/contracts/contracts/{contract_id}/validate/` (High)
- Line 294: `/api/v1/contracts/contracts/{contract_id}/lint/` (High)
- Line 294: `/api/v1/contracts/contracts/{contract_id}/lint/` (High)
- Line 327: `/api/v1/contracts/contracts/{contract_id}/convert/` (High)
- Line 327: `/api/v1/contracts/contracts/{contract_id}/convert/` (High)
- Line 371: `/api/v1/contracts/contracts/{contract_id}/convert/` (High)
- Line 371: `/api/v1/contracts/contracts/{contract_id}/convert/` (High)
- Line 474: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 474: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 519: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 519: `/api/v1/contracts/contracts/{contract_id}/` (High)
- ... and 2 more references

### tests/e2e/test_cross_capability_e2e.py

- **Total References**: 2
- **Categories**: test
- **Priority Breakdown**:
  - High: 2

#### References

- Line 101: `/api/v1/contracts/` (High)
- Line 101: `/api/v1/contracts/` (High)

### tests/e2e/test_custom_actions_error_handling.py

- **Total References**: 35
- **Categories**: test
- **Priority Breakdown**:
  - High: 34
  - Low: 1

#### References

- Line 30: `/api/v1/assets/00000000-0000-0000-0000-000000000000/activate/` (High)
- Line 30: `/api/v1/assets/00000000-0000-0000-0000-000000000000/activate/` (High)
- Line 43: `/api/v1/assets/{asset.id}/activate/` (High)
- Line 43: `/api/v1/assets/{asset.id}/activate/` (High)
- Line 57: `/api/v1/assets/{dataset_id}/datasets/` (High)
- Line 57: `/api/v1/assets/{dataset_id}/datasets/` (High)
- Line 68: `/api/v1/assets/{contract_id}/contracts/` (High)
- Line 68: `/api/v1/assets/{contract_id}/contracts/` (High)
- Line 77: `/api/v1/jobs/00000000-0000-0000-0000-000000000000/cancel/` (High)
- Line 77: `/api/v1/jobs/00000000-0000-0000-0000-000000000000/cancel/` (High)
- Line 94: `/api/v1/jobs/{job.id}/cancel/` (High)
- Line 94: `/api/v1/jobs/{job.id}/cancel/` (High)
- Line 105: `/api/v1/contracts/00000000-0000-0000-0000-000000000000/validate/` (High)
- Line 105: `/api/v1/contracts/00000000-0000-0000-0000-000000000000/validate/` (High)
- Line 111: `/api/v1/contracts/00000000-0000-0000-0000-000000000000/lint/` (High)
- Line 111: `/api/v1/contracts/00000000-0000-0000-0000-000000000000/lint/` (High)
- Line 117: `/api/v1/contracts/00000000-0000-0000-0000-000000000000/convert/` (High)
- Line 117: `/api/v1/contracts/00000000-0000-0000-0000-000000000000/convert/` (High)
- Line 123: `/api/v1/contracts/00000000-0000-0000-0000-000000000000/migrate/` (High)
- Line 123: `/api/v1/contracts/00000000-0000-0000-0000-000000000000/migrate/` (High)
- ... and 15 more references

### tests/e2e/test_data_first_comprehensive.py

- **Total References**: 18
- **Categories**: test
- **Priority Breakdown**:
  - High: 18

#### References

- Line 272: `/api/v1/assets/assets/{asset_id}/activate/` (High)
- Line 272: `/api/v1/assets/assets/{asset_id}/activate/` (High)
- Line 305: `/api/v1/datasets/datasets/` (High)
- Line 305: `/api/v1/datasets/datasets/` (High)
- Line 342: `/api/v1/files/files/init/` (High)
- Line 342: `/api/v1/files/files/init/` (High)
- Line 367: `/api/v1/files/files/init/` (High)
- Line 367: `/api/v1/files/files/init/` (High)
- Line 383: `/api/v1/datasets/datasets/` (High)
- Line 383: `/api/v1/datasets/datasets/` (High)
- Line 500: `/api/v1/compliance/compliance-runs/` (High)
- Line 500: `/api/v1/compliance/compliance-runs/` (High)
- Line 543: `/api/v1/dq/dq-runs/` (High)
- Line 543: `/api/v1/dq/dq-runs/` (High)
- Line 583: `/api/v1/contracts/contracts/{contract_id}/validate/` (High)
- Line 583: `/api/v1/contracts/contracts/{contract_id}/validate/` (High)
- Line 617: `/api/v1/compliance/compliance-runs/` (High)
- Line 617: `/api/v1/compliance/compliance-runs/` (High)

### tests/e2e/test_data_first_flow.py

- **Total References**: 24
- **Categories**: test
- **Priority Breakdown**:
  - High: 24

#### References

- Line 110: `/api/v1/assets/assets/` (High)
- Line 110: `/api/v1/assets/assets/` (High)
- Line 129: `/api/v1/files/files/init/` (High)
- Line 129: `/api/v1/files/files/init/` (High)
- Line 171: `/api/v1/files/files/{file_id}/complete/` (High)
- Line 171: `/api/v1/files/files/{file_id}/complete/` (High)
- Line 182: `/api/v1/datasets/datasets/` (High)
- Line 182: `/api/v1/datasets/datasets/` (High)
- Line 198: `/api/v1/compliance/compliance-runs/` (High)
- Line 198: `/api/v1/compliance/compliance-runs/` (High)
- Line 227: `/api/v1/dq/dq-runs/` (High)
- Line 227: `/api/v1/dq/dq-runs/` (High)
- Line 254: `/api/v1/contracts/contracts/` (High)
- Line 254: `/api/v1/contracts/contracts/` (High)
- Line 268: `/api/v1/contracts/contracts/{contract_id}/validate/` (High)
- Line 268: `/api/v1/contracts/contracts/{contract_id}/validate/` (High)
- Line 286: `/api/v1/contracts/contracts/{contract_id}/normalize/` (High)
- Line 286: `/api/v1/contracts/contracts/{contract_id}/normalize/` (High)
- Line 303: `/api/v1/assets/assets/{asset_id}/datasets/` (High)
- Line 303: `/api/v1/assets/assets/{asset_id}/datasets/` (High)
- ... and 4 more references

### tests/e2e/test_dataset_operations.py

- **Total References**: 8
- **Categories**: test
- **Priority Breakdown**:
  - High: 8

#### References

- Line 91: `/api/v1/datasets/datasets/` (High)
- Line 91: `/api/v1/datasets/datasets/` (High)
- Line 96: `/api/v1/datasets/datasets/?asset_id={asset_id}` (High)
- Line 96: `/api/v1/datasets/datasets/?asset_id={asset_id}` (High)
- Line 111: `/api/v1/datasets/datasets/{dataset_id}/` (High)
- Line 111: `/api/v1/datasets/datasets/{dataset_id}/` (High)
- Line 207: `/api/v1/datasets/datasets/{dataset_id}/` (High)
- Line 207: `/api/v1/datasets/datasets/{dataset_id}/` (High)

### tests/e2e/test_django6_upgrade_critical_workflows.py

- **Total References**: 16
- **Categories**: test
- **Priority Breakdown**:
  - High: 16

#### References

- Line 278: `/api/v1/contracts/` (High)
- Line 278: `/api/v1/contracts/` (High)
- Line 284: `/api/v1/contracts/` (High)
- Line 284: `/api/v1/contracts/` (High)
- Line 290: `/api/v1/contracts/` (High)
- Line 290: `/api/v1/contracts/` (High)
- Line 314: `/api/v1/assets/` (High)
- Line 314: `/api/v1/assets/` (High)
- Line 324: `/api/v1/assets/` (High)
- Line 324: `/api/v1/assets/` (High)
- Line 347: `/api/v1/contracts/` (High)
- Line 347: `/api/v1/contracts/` (High)
- Line 363: `/api/v1/contracts/` (High)
- Line 363: `/api/v1/contracts/` (High)
- Line 402: `/api/v1/contracts/` (High)
- Line 402: `/api/v1/contracts/` (High)

### tests/e2e/test_docker_compose_e2e.py

- **Total References**: 6
- **Categories**: test
- **Priority Breakdown**:
  - High: 6

#### References

- Line 744: `/api/v1/contracts/contracts/` (High)
- Line 744: `/api/v1/contracts/contracts/` (High)
- Line 1015: `/api/v1/contracts/` (High)
- Line 1015: `/api/v1/contracts/` (High)
- Line 1024: `/api/v1/assets/` (High)
- Line 1024: `/api/v1/assets/` (High)

### tests/e2e/test_dq_service.py

- **Total References**: 12
- **Categories**: test
- **Priority Breakdown**:
  - High: 12

#### References

- Line 143: `/api/v1/dq/dq-runs/` (High)
- Line 143: `/api/v1/dq/dq-runs/` (High)
- Line 176: `/api/v1/dq/dq-runs/` (High)
- Line 176: `/api/v1/dq/dq-runs/` (High)
- Line 181: `/api/v1/dq/dq-runs/?asset_id={asset_id1}` (High)
- Line 181: `/api/v1/dq/dq-runs/?asset_id={asset_id1}` (High)
- Line 196: `/api/v1/dq/dq-runs/{dq_run_id}/` (High)
- Line 196: `/api/v1/dq/dq-runs/{dq_run_id}/` (High)
- Line 257: `/api/v1/datasets/datasets/` (High)
- Line 257: `/api/v1/datasets/datasets/` (High)
- Line 285: `/api/v1/dq/dq-runs/` (High)
- Line 285: `/api/v1/dq/dq-runs/` (High)

### tests/e2e/test_entitlements.py

- **Total References**: 18
- **Categories**: test
- **Priority Breakdown**:
  - High: 18

#### References

- Line 68: `/api/v1/marketplace/listings/` (High)
- Line 68: `/api/v1/marketplace/listings/` (High)
- Line 89: `/api/v1/marketplace/listings/{listing_id}/publish/` (High)
- Line 89: `/api/v1/marketplace/listings/{listing_id}/publish/` (High)
- Line 101: `/api/v1/marketplace/orders/` (High)
- Line 101: `/api/v1/marketplace/orders/` (High)
- Line 203: `/api/v1/marketplace/entitlements/{entitlement.id}/revoke/` (High)
- Line 203: `/api/v1/marketplace/entitlements/{entitlement.id}/revoke/` (High)
- Line 266: `/api/v1/marketplace/entitlements/` (High)
- Line 266: `/api/v1/marketplace/entitlements/` (High)
- Line 279: `/api/v1/marketplace/entitlements/?status={EntitlementStatus.ACTIVE}` (High)
- Line 279: `/api/v1/marketplace/entitlements/?status={EntitlementStatus.ACTIVE}` (High)
- Line 320: `/api/v1/marketplace/entitlements/{entitlement.id}/` (High)
- Line 320: `/api/v1/marketplace/entitlements/{entitlement.id}/` (High)
- Line 361: `/api/v1/marketplace/entitlements/check-access/` (High)
- Line 361: `/api/v1/marketplace/entitlements/check-access/` (High)
- Line 416: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 416: `/api/v1/assets/assets/{asset_id}/` (High)

### tests/e2e/test_error_handling.py

- **Total References**: 26
- **Categories**: test
- **Priority Breakdown**:
  - High: 26

#### References

- Line 38: `/api/v1/assets/assets/{fake_id}/` (High)
- Line 38: `/api/v1/assets/assets/{fake_id}/` (High)
- Line 59: `/api/v1/assets/assets/` (High)
- Line 59: `/api/v1/assets/assets/` (High)
- Line 75: `/api/v1/assets/assets/` (High)
- Line 75: `/api/v1/assets/assets/` (High)
- Line 99: `/api/v1/assets/assets/{fake_id}/` (High)
- Line 99: `/api/v1/assets/assets/{fake_id}/` (High)
- Line 127: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 127: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 145: `/api/v1/assets/assets/{fake_id}/` (High)
- Line 145: `/api/v1/assets/assets/{fake_id}/` (High)
- Line 159: `/api/v1/assets/assets/{fake_id}/` (High)
- Line 159: `/api/v1/assets/assets/{fake_id}/` (High)
- Line 175: `/api/v1/assets/assets/{fake_id}/` (High)
- Line 175: `/api/v1/assets/assets/{fake_id}/` (High)
- Line 176: `/api/v1/contracts/contracts/{fake_id}/` (High)
- Line 176: `/api/v1/contracts/contracts/{fake_id}/` (High)
- Line 177: `/api/v1/datasets/datasets/{fake_id}/` (High)
- Line 177: `/api/v1/datasets/datasets/{fake_id}/` (High)
- ... and 6 more references

### tests/e2e/test_error_handling_comprehensive.py

- **Total References**: 50
- **Categories**: test
- **Priority Breakdown**:
  - High: 50

#### References

- Line 46: `/api/v1/assets/assets/{fake_id}/` (High)
- Line 46: `/api/v1/assets/assets/{fake_id}/` (High)
- Line 76: `/api/v1/assets/assets/` (High)
- Line 76: `/api/v1/assets/assets/` (High)
- Line 87: `/api/v1/assets/assets/{fake_id}/` (High)
- Line 87: `/api/v1/assets/assets/{fake_id}/` (High)
- Line 100: `/api/v1/assets/assets/{fake_id}/` (High)
- Line 100: `/api/v1/assets/assets/{fake_id}/` (High)
- Line 127: `/api/v1/assets/assets/` (High)
- Line 127: `/api/v1/assets/assets/` (High)
- Line 162: `/api/v1/assets/assets/{fake_id}/` (High)
- Line 162: `/api/v1/assets/assets/{fake_id}/` (High)
- Line 182: `/api/v1/assets/assets/{fake_id}/` (High)
- Line 182: `/api/v1/assets/assets/{fake_id}/` (High)
- Line 219: `/api/v1/assets/assets/{fake_id}/` (High)
- Line 219: `/api/v1/assets/assets/{fake_id}/` (High)
- Line 220: `/api/v1/contracts/contracts/{fake_id}/` (High)
- Line 220: `/api/v1/contracts/contracts/{fake_id}/` (High)
- Line 221: `/api/v1/datasets/datasets/{fake_id}/` (High)
- Line 221: `/api/v1/datasets/datasets/{fake_id}/` (High)
- ... and 30 more references

### tests/e2e/test_file_operations.py

- **Total References**: 22
- **Categories**: test
- **Priority Breakdown**:
  - High: 22

#### References

- Line 113: `/api/v1/files/files/init/` (High)
- Line 113: `/api/v1/files/files/init/` (High)
- Line 150: `/api/v1/files/files/{file_id}/download/` (High)
- Line 150: `/api/v1/files/files/{file_id}/download/` (High)
- Line 167: `/api/v1/files/files/{fake_file_id}/download/` (High)
- Line 167: `/api/v1/files/files/{fake_file_id}/download/` (High)
- Line 185: `/api/v1/files/files/{file_id}/` (High)
- Line 185: `/api/v1/files/files/{file_id}/` (High)
- Line 189: `/api/v1/files/files/{file_id}/download/` (High)
- Line 189: `/api/v1/files/files/{file_id}/download/` (High)
- Line 207: `/api/v1/files/files/{file_id}/` (High)
- Line 207: `/api/v1/files/files/{file_id}/` (High)
- Line 237: `/api/v1/files/files/{file_id}/complete/` (High)
- Line 237: `/api/v1/files/files/{file_id}/complete/` (High)
- Line 252: `/api/v1/files/files/init/` (High)
- Line 252: `/api/v1/files/files/init/` (High)
- Line 299: `/api/v1/files/files/init/` (High)
- Line 299: `/api/v1/files/files/init/` (High)
- Line 369: `/api/v1/files/files/{file_id}/` (High)
- Line 369: `/api/v1/files/files/{file_id}/` (High)
- ... and 2 more references

### tests/e2e/test_graphql_api.py

- **Total References**: 2
- **Categories**: test
- **Priority Breakdown**:
  - High: 2

#### References

- Line 550: `/api/v1/assets/assets/` (High)
- Line 550: `/api/v1/assets/assets/` (High)

### tests/e2e/test_job_orchestration.py

- **Total References**: 16
- **Categories**: test
- **Priority Breakdown**:
  - High: 16

#### References

- Line 200: `/api/v1/jobs/jobs/{job.id}/cancel/` (High)
- Line 200: `/api/v1/jobs/jobs/{job.id}/cancel/` (High)
- Line 228: `/api/v1/jobs/jobs/{job.id}/cancel/` (High)
- Line 228: `/api/v1/jobs/jobs/{job.id}/cancel/` (High)
- Line 257: `/api/v1/jobs/jobs/{job.id}/cancel/` (High)
- Line 257: `/api/v1/jobs/jobs/{job.id}/cancel/` (High)
- Line 296: `/api/v1/jobs/jobs/` (High)
- Line 296: `/api/v1/jobs/jobs/` (High)
- Line 301: `/api/v1/jobs/jobs/?type={JobType.DQ_RUN}` (High)
- Line 301: `/api/v1/jobs/jobs/?type={JobType.DQ_RUN}` (High)
- Line 307: `/api/v1/jobs/jobs/?status={JobStatus.PENDING}` (High)
- Line 307: `/api/v1/jobs/jobs/?status={JobStatus.PENDING}` (High)
- Line 325: `/api/v1/jobs/jobs/{job.id}/` (High)
- Line 325: `/api/v1/jobs/jobs/{job.id}/` (High)
- Line 425: `/api/v1/jobs/jobs/` (High)
- Line 425: `/api/v1/jobs/jobs/` (High)

### tests/e2e/test_lineage_use_cases_e2e.py

- **Total References**: 20
- **Categories**: test
- **Priority Breakdown**:
  - High: 20

#### References

- Line 741: `/api/v1/contracts/contracts/{self.contract_id}/lineage/contracts/` (High)
- Line 741: `/api/v1/contracts/contracts/{self.contract_id}/lineage/contracts/` (High)
- Line 751: `/api/v1/contracts/contracts/{self.contract_id}/models/APIModel/lineage/` (High)
- Line 751: `/api/v1/contracts/contracts/{self.contract_id}/models/APIModel/lineage/` (High)
- Line 761: `/api/v1/contracts/contracts/{self.contract_id}/fields/api_field/lineage/` (High)
- Line 761: `/api/v1/contracts/contracts/{self.contract_id}/fields/api_field/lineage/` (High)
- Line 770: `/api/v1/contracts/contracts/{self.contract_id}/lineage/full/` (High)
- Line 770: `/api/v1/contracts/contracts/{self.contract_id}/lineage/full/` (High)
- Line 779: `/api/v1/contracts/contracts/{self.contract_id}/lineage/visualization/` (High)
- Line 779: `/api/v1/contracts/contracts/{self.contract_id}/lineage/visualization/` (High)
- Line 790: `/api/v1/contracts/contracts/{self.contract_id}/lineage/visualization/` (High)
- Line 790: `/api/v1/contracts/contracts/{self.contract_id}/lineage/visualization/` (High)
- Line 801: `/api/v1/contracts/contracts/{self.contract_id}/lineage/visualization/` (High)
- Line 801: `/api/v1/contracts/contracts/{self.contract_id}/lineage/visualization/` (High)
- Line 813: `/api/v1/contracts/contracts/{self.contract_id}/impact-analysis/` (High)
- Line 813: `/api/v1/contracts/contracts/{self.contract_id}/impact-analysis/` (High)
- Line 824: `/api/v1/contracts/contracts/{self.contract_id}/impact-analysis/` (High)
- Line 824: `/api/v1/contracts/contracts/{self.contract_id}/impact-analysis/` (High)
- Line 835: `/api/v1/contracts/contracts/{self.contract_id}/impact-analysis/` (High)
- Line 835: `/api/v1/contracts/contracts/{self.contract_id}/impact-analysis/` (High)

### tests/e2e/test_marketplace_comprehensive.py

- **Total References**: 24
- **Categories**: test
- **Priority Breakdown**:
  - High: 24

#### References

- Line 63: `/api/v1/marketplace/listings/` (High)
- Line 63: `/api/v1/marketplace/listings/` (High)
- Line 78: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 78: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 116: `/api/v1/marketplace/listings/` (High)
- Line 116: `/api/v1/marketplace/listings/` (High)
- Line 144: `/api/v1/marketplace/listings/` (High)
- Line 144: `/api/v1/marketplace/listings/` (High)
- Line 224: `/api/v1/marketplace/listings/search/` (High)
- Line 224: `/api/v1/marketplace/listings/search/` (High)
- Line 233: `/api/v1/marketplace/listings/{self.listing.id}/` (High)
- Line 233: `/api/v1/marketplace/listings/{self.listing.id}/` (High)
- Line 242: `/api/v1/marketplace/listings/search/` (High)
- Line 242: `/api/v1/marketplace/listings/search/` (High)
- Line 315: `/api/v1/marketplace/orders/` (High)
- Line 315: `/api/v1/marketplace/orders/` (High)
- Line 341: `/api/v1/marketplace/orders/` (High)
- Line 341: `/api/v1/marketplace/orders/` (High)
- Line 376: `/api/v1/marketplace/orders/` (High)
- Line 376: `/api/v1/marketplace/orders/` (High)
- ... and 4 more references

### tests/e2e/test_marketplace_listings.py

- **Total References**: 44
- **Categories**: test
- **Priority Breakdown**:
  - High: 44

#### References

- Line 58: `/api/v1/marketplace/listings/` (High)
- Line 58: `/api/v1/marketplace/listings/` (High)
- Line 89: `/api/v1/marketplace/listings/` (High)
- Line 89: `/api/v1/marketplace/listings/` (High)
- Line 111: `/api/v1/marketplace/listings/` (High)
- Line 111: `/api/v1/marketplace/listings/` (High)
- Line 140: `/api/v1/marketplace/listings/` (High)
- Line 140: `/api/v1/marketplace/listings/` (High)
- Line 153: `/api/v1/marketplace/listings/{listing_id}/publish/` (High)
- Line 153: `/api/v1/marketplace/listings/{listing_id}/publish/` (High)
- Line 160: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 160: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 197: `/api/v1/marketplace/listings/` (High)
- Line 197: `/api/v1/marketplace/listings/` (High)
- Line 209: `/api/v1/marketplace/listings/{listing_id}/publish/` (High)
- Line 209: `/api/v1/marketplace/listings/{listing_id}/publish/` (High)
- Line 213: `/api/v1/marketplace/listings/{listing_id}/unlist/` (High)
- Line 213: `/api/v1/marketplace/listings/{listing_id}/unlist/` (High)
- Line 220: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 220: `/api/v1/marketplace/listings/{listing_id}/` (High)
- ... and 24 more references

### tests/e2e/test_marketplace_orders.py

- **Total References**: 44
- **Categories**: test
- **Priority Breakdown**:
  - High: 44

#### References

- Line 72: `/api/v1/marketplace/listings/` (High)
- Line 72: `/api/v1/marketplace/listings/` (High)
- Line 84: `/api/v1/marketplace/listings/{listing_id}/publish/` (High)
- Line 84: `/api/v1/marketplace/listings/{listing_id}/publish/` (High)
- Line 88: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 88: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 110: `/api/v1/marketplace/orders/` (High)
- Line 110: `/api/v1/marketplace/orders/` (High)
- Line 135: `/api/v1/marketplace/orders/` (High)
- Line 135: `/api/v1/marketplace/orders/` (High)
- Line 165: `/api/v1/marketplace/orders/` (High)
- Line 165: `/api/v1/marketplace/orders/` (High)
- Line 187: `/api/v1/marketplace/orders/` (High)
- Line 187: `/api/v1/marketplace/orders/` (High)
- Line 225: `/api/v1/marketplace/orders/{order_id}/approve/` (High)
- Line 225: `/api/v1/marketplace/orders/{order_id}/approve/` (High)
- Line 233: `/api/v1/marketplace/orders/{order_id}/` (High)
- Line 233: `/api/v1/marketplace/orders/{order_id}/` (High)
- Line 274: `/api/v1/marketplace/orders/` (High)
- Line 274: `/api/v1/marketplace/orders/` (High)
- ... and 24 more references

### tests/e2e/test_marketplace_purchase_flow.py

- **Total References**: 16
- **Categories**: test
- **Priority Breakdown**:
  - High: 16

#### References

- Line 77: `/api/v1/marketplace/listings/` (High)
- Line 77: `/api/v1/marketplace/listings/` (High)
- Line 92: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 92: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 100: `/api/v1/marketplace/listings/search/` (High)
- Line 100: `/api/v1/marketplace/listings/search/` (High)
- Line 108: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 108: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 114: `/api/v1/marketplace/orders/` (High)
- Line 114: `/api/v1/marketplace/orders/` (High)
- Line 131: `/api/v1/marketplace/orders/{order_id}/approve/` (High)
- Line 131: `/api/v1/marketplace/orders/{order_id}/approve/` (High)
- Line 157: `/api/v1/marketplace/entitlements/` (High)
- Line 157: `/api/v1/marketplace/entitlements/` (High)
- Line 164: `/api/v1/assets/assets/{self.asset.id}/` (High)
- Line 164: `/api/v1/assets/assets/{self.asset.id}/` (High)

### tests/e2e/test_marketplace_use_cases.py

- **Total References**: 58
- **Categories**: test
- **Priority Breakdown**:
  - High: 58

#### References

- Line 70: `/api/v1/marketplace/listings/` (High)
- Line 70: `/api/v1/marketplace/listings/` (High)
- Line 90: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 90: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 106: `/api/v1/marketplace/listings/` (High)
- Line 106: `/api/v1/marketplace/listings/` (High)
- Line 120: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 120: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 130: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 130: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 146: `/api/v1/marketplace/listings/` (High)
- Line 146: `/api/v1/marketplace/listings/` (High)
- Line 160: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 160: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 192: `/api/v1/marketplace/listings/` (High)
- Line 192: `/api/v1/marketplace/listings/` (High)
- Line 207: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 207: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 227: `/api/v1/marketplace/listings/` (High)
- Line 227: `/api/v1/marketplace/listings/` (High)
- ... and 38 more references

### tests/e2e/test_monitoring_e2e.py

- **Total References**: 13
- **Categories**: test
- **Priority Breakdown**:
  - High: 12
  - Low: 1

#### References

- Line 287: `/api/v1/status/config` (Low)
  - ⚠️ In comment
- Line 289: `/api/v1/status/config` (High)
- Line 317: `/api/v1/status/config` (High)
- Line 326: `/api/v1/alerts` (High)
- Line 331: `/api/v1/status/config` (High)
- Line 630: `/api/v1/contracts/123e4567-e89b-12d3-a456-426614174000/` (High)
- Line 630: `/api/v1/contracts/123e4567-e89b-12d3-a456-426614174000/` (High)
- Line 631: `/api/v1/contracts/{id}/` (High)
- Line 631: `/api/v1/contracts/{id}/` (High)
- Line 633: `/api/v1/assets/123/` (High)
- Line 633: `/api/v1/assets/123/` (High)
- Line 634: `/api/v1/assets/{id}/` (High)
- Line 634: `/api/v1/assets/{id}/` (High)

### tests/e2e/test_multi_tenant_isolation.py

- **Total References**: 18
- **Categories**: test
- **Priority Breakdown**:
  - High: 18

#### References

- Line 59: `/api/v1/assets/assets/{asset_id1}/` (High)
- Line 59: `/api/v1/assets/assets/{asset_id1}/` (High)
- Line 69: `/api/v1/assets/assets/{asset_id2}/` (High)
- Line 69: `/api/v1/assets/assets/{asset_id2}/` (High)
- Line 85: `/api/v1/contracts/contracts/{contract_id1}/` (High)
- Line 85: `/api/v1/contracts/contracts/{contract_id1}/` (High)
- Line 104: `/api/v1/datasets/datasets/{dataset_id1}/` (High)
- Line 104: `/api/v1/datasets/datasets/{dataset_id1}/` (High)
- Line 121: `/api/v1/files/files/{file_id1}/` (High)
- Line 121: `/api/v1/files/files/{file_id1}/` (High)
- Line 125: `/api/v1/files/files/{file_id1}/download/` (High)
- Line 125: `/api/v1/files/files/{file_id1}/download/` (High)
- Line 139: `/api/v1/assets/assets/` (High)
- Line 139: `/api/v1/assets/assets/` (High)
- Line 189: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 189: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 221: `/api/v1/assets/assets/?search=Iso` (High)
- Line 221: `/api/v1/assets/assets/?search=Iso` (High)

### tests/e2e/test_performance_comprehensive.py

- **Total References**: 16
- **Categories**: test
- **Priority Breakdown**:
  - High: 16

#### References

- Line 71: `/api/v1/assets/assets/` (High)
- Line 71: `/api/v1/assets/assets/` (High)
- Line 99: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 99: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 135: `/api/v1/contracts/contracts/` (High)
- Line 135: `/api/v1/contracts/contracts/` (High)
- Line 161: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 161: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 194: `/api/v1/jobs/jobs/` (High)
- Line 194: `/api/v1/jobs/jobs/` (High)
- Line 225: `/api/v1/assets/assets/` (High)
- Line 225: `/api/v1/assets/assets/` (High)
- Line 277: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 277: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 326: `/api/v1/assets/assets/` (High)
- Line 326: `/api/v1/assets/assets/` (High)

### tests/e2e/test_persona_aud_comprehensive.py

- **Total References**: 62
- **Categories**: test
- **Priority Breakdown**:
  - High: 62

#### References

- Line 119: `/api/v1/audit/audit-events/` (High)
- Line 119: `/api/v1/audit/audit-events/` (High)
- Line 144: `/api/v1/audit/audit-events/?resource_type=ASSET` (High)
- Line 144: `/api/v1/audit/audit-events/?resource_type=ASSET` (High)
- Line 158: `/api/v1/audit/audit-events/?resource_type=CONTRACT` (High)
- Line 158: `/api/v1/audit/audit-events/?resource_type=CONTRACT` (High)
- Line 176: `/api/v1/audit/audit-events/?action=ASSET_CREATED` (High)
- Line 176: `/api/v1/audit/audit-events/?action=ASSET_CREATED` (High)
- Line 198: `/api/v1/audit/audit-events/?start_date={start_date}&end_date={end_date}` (High)
- Line 198: `/api/v1/audit/audit-events/?start_date={start_date}&end_date={end_date}` (High)
- Line 219: `/api/v1/audit/audit-events/?actor_user_id={self.auditor_user.id}` (High)
- Line 219: `/api/v1/audit/audit-events/?actor_user_id={self.auditor_user.id}` (High)
- Line 238: `/api/v1/audit/audit-events/` (High)
- Line 238: `/api/v1/audit/audit-events/` (High)
- Line 251: `/api/v1/audit/audit-events/{event_id}/` (High)
- Line 251: `/api/v1/audit/audit-events/{event_id}/` (High)
- Line 264: `/api/v1/audit/audit-events/` (High)
- Line 264: `/api/v1/audit/audit-events/` (High)
- Line 278: `/api/v1/audit/audit-events/{event_id}/` (High)
- Line 278: `/api/v1/audit/audit-events/{event_id}/` (High)
- ... and 42 more references

### tests/e2e/test_persona_auditor.py

- **Total References**: 32
- **Categories**: test
- **Priority Breakdown**:
  - High: 32

#### References

- Line 50: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 50: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 60: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 60: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 69: `/api/v1/contracts/contracts/` (High)
- Line 69: `/api/v1/contracts/contracts/` (High)
- Line 83: `/api/v1/contracts/contracts/` (High)
- Line 83: `/api/v1/contracts/contracts/` (High)
- Line 115: `/api/v1/contracts/contracts/{contract.id}/` (High)
- Line 115: `/api/v1/contracts/contracts/{contract.id}/` (High)
- Line 132: `/api/v1/contracts/contracts/{contract.id}/` (High)
- Line 132: `/api/v1/contracts/contracts/{contract.id}/` (High)
- Line 139: `/api/v1/dq/runs/` (High)
- Line 139: `/api/v1/dq/runs/` (High)
- Line 155: `/api/v1/dq/runs/` (High)
- Line 155: `/api/v1/dq/runs/` (High)
- Line 173: `/api/v1/compliance/runs/` (High)
- Line 173: `/api/v1/compliance/runs/` (High)
- Line 189: `/api/v1/compliance/runs/` (High)
- Line 189: `/api/v1/compliance/runs/` (High)
- ... and 12 more references

### tests/e2e/test_persona_cpo_comprehensive.py

- **Total References**: 72
- **Categories**: test
- **Priority Breakdown**:
  - High: 72

#### References

- Line 97: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 97: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 102: `/api/v1/compliance/compliance-runs/{compliance_run_id}/` (High)
- Line 102: `/api/v1/compliance/compliance-runs/{compliance_run_id}/` (High)
- Line 111: `/api/v1/compliance/compliance-runs/` (High)
- Line 111: `/api/v1/compliance/compliance-runs/` (High)
- Line 154: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 154: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 160: `/api/v1/compliance/compliance-runs/` (High)
- Line 160: `/api/v1/compliance/compliance-runs/` (High)
- Line 172: `/api/v1/assets/assets/invalid-uuid/` (High)
- Line 172: `/api/v1/assets/assets/invalid-uuid/` (High)
- Line 177: `/api/v1/compliance/compliance-runs/{fake_id}/` (High)
- Line 177: `/api/v1/compliance/compliance-runs/{fake_id}/` (High)
- Line 344: `/api/v1/governance/access/retention-policies/` (High)
- Line 344: `/api/v1/governance/access/retention-policies/` (High)
- Line 360: `/api/v1/access/retention-policies/` (High)
- Line 360: `/api/v1/access/retention-policies/` (High)
- Line 484: `/api/v1/governance/access/retention-policies/` (High)
- Line 484: `/api/v1/governance/access/retention-policies/` (High)
- ... and 52 more references

### tests/e2e/test_persona_data_consumer.py

- **Total References**: 34
- **Categories**: test
- **Priority Breakdown**:
  - High: 34

#### References

- Line 52: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 52: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 62: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 62: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 73: `/api/v1/contracts/contracts/` (High)
- Line 73: `/api/v1/contracts/contracts/` (High)
- Line 90: `/api/v1/contracts/contracts/` (High)
- Line 90: `/api/v1/contracts/contracts/` (High)
- Line 96: `/api/v1/contracts/contracts/` (High)
- Line 96: `/api/v1/contracts/contracts/` (High)
- Line 125: `/api/v1/contracts/contracts/` (High)
- Line 125: `/api/v1/contracts/contracts/` (High)
- Line 143: `/api/v1/contracts/contracts/` (High)
- Line 143: `/api/v1/contracts/contracts/` (High)
- Line 149: `/api/v1/contracts/contracts/` (High)
- Line 149: `/api/v1/contracts/contracts/` (High)
- Line 150: `/api/v1/dq/runs/` (High)
- Line 150: `/api/v1/dq/runs/` (High)
- Line 151: `/api/v1/compliance/runs/` (High)
- Line 151: `/api/v1/compliance/runs/` (High)
- ... and 14 more references

### tests/e2e/test_persona_data_engineer_comprehensive.py

- **Total References**: 92
- **Categories**: test
- **Priority Breakdown**:
  - High: 92

#### References

- Line 78: `/api/v1/contracts/contracts/` (High)
- Line 78: `/api/v1/contracts/contracts/` (High)
- Line 94: `/api/v1/contracts/contracts/{contract_id}/validate/` (High)
- Line 94: `/api/v1/contracts/contracts/{contract_id}/validate/` (High)
- Line 112: `/api/v1/assets/assets/` (High)
- Line 112: `/api/v1/assets/assets/` (High)
- Line 121: `/api/v1/assets/assets/{asset_id}/contracts/` (High)
- Line 121: `/api/v1/assets/assets/{asset_id}/contracts/` (High)
- Line 137: `/api/v1/datasets/datasets/` (High)
- Line 137: `/api/v1/datasets/datasets/` (High)
- Line 174: `/api/v1/assets/assets/{asset_id}/activate/` (High)
- Line 174: `/api/v1/assets/assets/{asset_id}/activate/` (High)
- Line 208: `/api/v1/contracts/contracts/` (High)
- Line 208: `/api/v1/contracts/contracts/` (High)
- Line 244: `/api/v1/contracts/contracts/` (High)
- Line 244: `/api/v1/contracts/contracts/` (High)
- Line 253: `/api/v1/contracts/contracts/{contract_id}/validate/` (High)
- Line 253: `/api/v1/contracts/contracts/{contract_id}/validate/` (High)
- Line 301: `/api/v1/datasets/datasets/` (High)
- Line 301: `/api/v1/datasets/datasets/` (High)
- ... and 72 more references

### tests/e2e/test_persona_data_provider.py

- **Total References**: 44
- **Categories**: test
- **Priority Breakdown**:
  - High: 44

#### References

- Line 52: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 52: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 62: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 62: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 78: `/api/v1/tenants/tenants/{other_tenant.id}/config/` (High)
- Line 78: `/api/v1/tenants/tenants/{other_tenant.id}/config/` (High)
- Line 92: `/api/v1/contracts/contracts/` (High)
- Line 92: `/api/v1/contracts/contracts/` (High)
- Line 110: `/api/v1/contracts/contracts/` (High)
- Line 110: `/api/v1/contracts/contracts/` (High)
- Line 118: `/api/v1/contracts/contracts/` (High)
- Line 118: `/api/v1/contracts/contracts/` (High)
- Line 130: `/api/v1/contracts/contracts/` (High)
- Line 130: `/api/v1/contracts/contracts/` (High)
- Line 147: `/api/v1/contracts/contracts/` (High)
- Line 147: `/api/v1/contracts/contracts/` (High)
- Line 164: `/api/v1/contracts/contracts/` (High)
- Line 164: `/api/v1/contracts/contracts/` (High)
- Line 207: `/api/v1/contracts/contracts/` (High)
- Line 207: `/api/v1/contracts/contracts/` (High)
- ... and 24 more references

### tests/e2e/test_persona_dc_comprehensive.py

- **Total References**: 54
- **Categories**: test
- **Priority Breakdown**:
  - High: 54

#### References

- Line 117: `/api/v1/marketplace/listings/` (High)
- Line 117: `/api/v1/marketplace/listings/` (High)
- Line 132: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 132: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 143: `/api/v1/marketplace/listings/search/` (High)
- Line 143: `/api/v1/marketplace/listings/search/` (High)
- Line 154: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 154: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 166: `/api/v1/marketplace/orders/` (High)
- Line 166: `/api/v1/marketplace/orders/` (High)
- Line 186: `/api/v1/marketplace/entitlements/{entitlement_id}/` (High)
- Line 186: `/api/v1/marketplace/entitlements/{entitlement_id}/` (High)
- Line 231: `/api/v1/marketplace/listings/` (High)
- Line 231: `/api/v1/marketplace/listings/` (High)
- Line 247: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 247: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 259: `/api/v1/marketplace/orders/` (High)
- Line 259: `/api/v1/marketplace/orders/` (High)
- Line 274: `/api/v1/marketplace/orders/{order_id}/approve/` (High)
- Line 274: `/api/v1/marketplace/orders/{order_id}/approve/` (High)
- ... and 34 more references

### tests/e2e/test_persona_dev_comprehensive.py

- **Total References**: 74
- **Categories**: test
- **Priority Breakdown**:
  - High: 74

#### References

- Line 68: `/api/v1/auth/api-keys/` (High)
- Line 68: `/api/v1/auth/api-keys/` (High)
- Line 88: `/api/v1/assets/assets/` (High)
- Line 88: `/api/v1/assets/assets/` (High)
- Line 96: `/api/v1/assets/assets/` (High)
- Line 96: `/api/v1/assets/assets/` (High)
- Line 139: `/api/v1/contracts/contracts/` (High)
- Line 139: `/api/v1/contracts/contracts/` (High)
- Line 173: `/api/v1/assets/assets/` (High)
- Line 173: `/api/v1/assets/assets/` (High)
- Line 201: `/api/v1/assets/assets/{asset.id}/` (High)
- Line 201: `/api/v1/assets/assets/{asset.id}/` (High)
- Line 229: `/api/v1/assets/assets/` (High)
- Line 229: `/api/v1/assets/assets/` (High)
- Line 238: `/api/v1/assets/assets/` (High)
- Line 238: `/api/v1/assets/assets/` (High)
- Line 281: `/api/v1/assets/assets/` (High)
- Line 281: `/api/v1/assets/assets/` (High)
- Line 327: `/api/v1/contracts/contracts/` (High)
- Line 327: `/api/v1/contracts/contracts/` (High)
- ... and 54 more references

### tests/e2e/test_persona_dpo_comprehensive.py

- **Total References**: 38
- **Categories**: test
- **Priority Breakdown**:
  - High: 38

#### References

- Line 294: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 294: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 313: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 313: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 378: `/api/v1/marketplace/listings/` (High)
- Line 378: `/api/v1/marketplace/listings/` (High)
- Line 395: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 395: `/api/v1/marketplace/listings/{listing_id}/` (High)
- Line 437: `/api/v1/marketplace/listings/` (High)
- Line 437: `/api/v1/marketplace/listings/` (High)
- Line 457: `/api/v1/marketplace/listings/` (High)
- Line 457: `/api/v1/marketplace/listings/` (High)
- Line 475: `/api/v1/marketplace/listings/` (High)
- Line 475: `/api/v1/marketplace/listings/` (High)
- Line 508: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 508: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 552: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 552: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 599: `/api/v1/dq/dq-runs/{dq_run_id}/` (High)
- Line 599: `/api/v1/dq/dq-runs/{dq_run_id}/` (High)
- ... and 18 more references

### tests/e2e/test_persona_pa_comprehensive.py

- **Total References**: 84
- **Categories**: test
- **Priority Breakdown**:
  - High: 84

#### References

- Line 58: `/api/v1/tenants/tenants/` (High)
- Line 58: `/api/v1/tenants/tenants/` (High)
- Line 115: `/api/v1/tenants/tenants/` (High)
- Line 115: `/api/v1/tenants/tenants/` (High)
- Line 128: `/api/v1/tenants/tenants/{tenant_id}/` (High)
- Line 128: `/api/v1/tenants/tenants/{tenant_id}/` (High)
- Line 154: `/api/v1/tenants/tenants/` (High)
- Line 154: `/api/v1/tenants/tenants/` (High)
- Line 174: `/api/v1/tenants/tenants/{tenant.id}/suspend/` (High)
- Line 174: `/api/v1/tenants/tenants/{tenant.id}/suspend/` (High)
- Line 203: `/api/v1/tenants/tenants/{tenant.id}/reactivate/` (High)
- Line 203: `/api/v1/tenants/tenants/{tenant.id}/reactivate/` (High)
- Line 225: `/api/v1/tenants/tenants/` (High)
- Line 225: `/api/v1/tenants/tenants/` (High)
- Line 252: `/api/v1/tenants/tenants/` (High)
- Line 252: `/api/v1/tenants/tenants/` (High)
- Line 337: `/api/v1/marketplace/listings/` (High)
- Line 337: `/api/v1/marketplace/listings/` (High)
- Line 358: `/api/v1/marketplace/listings/{listing.id}/` (High)
- Line 358: `/api/v1/marketplace/listings/{listing.id}/` (High)
- ... and 64 more references

### tests/e2e/test_persona_platform_admin.py

- **Total References**: 46
- **Categories**: test
- **Priority Breakdown**:
  - High: 46

#### References

- Line 52: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 52: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 59: `/api/v1/tenants/tenants/{self.other_tenant.id}/config/` (High)
- Line 59: `/api/v1/tenants/tenants/{self.other_tenant.id}/config/` (High)
- Line 69: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 69: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 82: `/api/v1/tenants/tenants/{self.other_tenant.id}/config/` (High)
- Line 82: `/api/v1/tenants/tenants/{self.other_tenant.id}/config/` (High)
- Line 92: `/api/v1/tenants/tenants/` (High)
- Line 92: `/api/v1/tenants/tenants/` (High)
- Line 110: `/api/v1/tenants/tenants/` (High)
- Line 110: `/api/v1/tenants/tenants/` (High)
- Line 123: `/api/v1/tenants/tenants/{self.tenant.id}/` (High)
- Line 123: `/api/v1/tenants/tenants/{self.tenant.id}/` (High)
- Line 137: `/api/v1/tenants/tenants/{self.tenant.id}/` (High)
- Line 137: `/api/v1/tenants/tenants/{self.tenant.id}/` (High)
- Line 138: `/api/v1/tenants/tenants/{self.other_tenant.id}/` (High)
- Line 138: `/api/v1/tenants/tenants/{self.other_tenant.id}/` (High)
- Line 156: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 156: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- ... and 26 more references

### tests/e2e/test_persona_ta_comprehensive.py

- **Total References**: 84
- **Categories**: test
- **Priority Breakdown**:
  - High: 84

#### References

- Line 76: `/api/v1/users/users/` (High)
- Line 76: `/api/v1/users/users/` (High)
- Line 115: `/api/v1/users/users/` (High)
- Line 115: `/api/v1/users/users/` (High)
- Line 122: `/api/v1/users/users/{user_id}/` (High)
- Line 122: `/api/v1/users/users/{user_id}/` (High)
- Line 133: `/api/v1/users/users/` (High)
- Line 133: `/api/v1/users/users/` (High)
- Line 165: `/api/v1/users/users/invite/` (High)
- Line 165: `/api/v1/users/users/invite/` (High)
- Line 205: `/api/v1/users/users/{user.id}/roles/` (High)
- Line 205: `/api/v1/users/users/{user.id}/roles/` (High)
- Line 242: `/api/v1/users/users/{user.id}/roles/` (High)
- Line 242: `/api/v1/users/users/{user.id}/roles/` (High)
- Line 269: `/api/v1/users/users/{user.id}/` (High)
- Line 269: `/api/v1/users/users/{user.id}/` (High)
- Line 307: `/api/v1/users/users/{user.id}/` (High)
- Line 307: `/api/v1/users/users/{user.id}/` (High)
- Line 339: `/api/v1/users/users/?status=ACTIVE` (High)
- Line 339: `/api/v1/users/users/?status=ACTIVE` (High)
- ... and 64 more references

### tests/e2e/test_persona_tenant_admin.py

- **Total References**: 76
- **Categories**: test
- **Priority Breakdown**:
  - High: 76

#### References

- Line 70: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 70: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 85: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 85: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 96: `/api/v1/tenants/tenants/{self.other_tenant.id}/config/` (High)
- Line 96: `/api/v1/tenants/tenants/{self.other_tenant.id}/config/` (High)
- Line 106: `/api/v1/tenants/tenants/{self.other_tenant.id}/config/` (High)
- Line 106: `/api/v1/tenants/tenants/{self.other_tenant.id}/config/` (High)
- Line 118: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 118: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 135: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 135: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 162: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 162: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 177: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 177: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 190: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 190: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 202: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 202: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- ... and 56 more references

### tests/e2e/test_rate_limiting.py

- **Total References**: 22
- **Categories**: test
- **Priority Breakdown**:
  - High: 22

#### References

- Line 33: `/api/v1/assets/assets/` (High)
- Line 33: `/api/v1/assets/assets/` (High)
- Line 55: `/api/v1/assets/assets/` (High)
- Line 55: `/api/v1/assets/assets/` (High)
- Line 91: `/api/v1/assets/assets/` (High)
- Line 91: `/api/v1/assets/assets/` (High)
- Line 109: `/api/v1/assets/assets/` (High)
- Line 109: `/api/v1/assets/assets/` (High)
- Line 134: `/api/v1/assets/assets/` (High)
- Line 134: `/api/v1/assets/assets/` (High)
- Line 158: `/api/v1/assets/assets/` (High)
- Line 158: `/api/v1/assets/assets/` (High)
- Line 172: `/api/v1/assets/assets/` (High)
- Line 172: `/api/v1/assets/assets/` (High)
- Line 198: `/api/v1/assets/assets/` (High)
- Line 198: `/api/v1/assets/assets/` (High)
- Line 199: `/api/v1/contracts/contracts/` (High)
- Line 199: `/api/v1/contracts/contracts/` (High)
- Line 200: `/api/v1/datasets/datasets/` (High)
- Line 200: `/api/v1/datasets/datasets/` (High)
- ... and 2 more references

### tests/e2e/test_rate_limiting_e2e.py

- **Total References**: 42
- **Categories**: test
- **Priority Breakdown**:
  - High: 42

#### References

- Line 51: `/api/v1/assets/assets/` (High)
- Line 51: `/api/v1/assets/assets/` (High)
- Line 91: `/api/v1/assets/assets/` (High)
- Line 91: `/api/v1/assets/assets/` (High)
- Line 119: `/api/v1/assets/assets/` (High)
- Line 119: `/api/v1/assets/assets/` (High)
- Line 137: `/api/v1/dq/runs/` (High)
- Line 137: `/api/v1/dq/runs/` (High)
- Line 149: `/api/v1/compliance/runs/` (High)
- Line 149: `/api/v1/compliance/runs/` (High)
- Line 161: `/api/v1/files/` (High)
- Line 161: `/api/v1/files/` (High)
- Line 173: `/api/v1/assets/assets/` (High)
- Line 173: `/api/v1/assets/assets/` (High)
- Line 195: `/api/v1/assets/assets/` (High)
- Line 195: `/api/v1/assets/assets/` (High)
- Line 224: `/api/v1/assets/assets/` (High)
- Line 224: `/api/v1/assets/assets/` (High)
- Line 241: `/api/v1/assets/assets/` (High)
- Line 241: `/api/v1/assets/assets/` (High)
- ... and 22 more references

### tests/e2e/test_rest_api.py

- **Total References**: 18
- **Categories**: test
- **Priority Breakdown**:
  - High: 18

#### References

- Line 67: `/api/v1/auth/login/` (High)
- Line 67: `/api/v1/auth/login/` (High)
- Line 68: `/api/v1/assets/assets/` (High)
- Line 68: `/api/v1/assets/assets/` (High)
- Line 69: `/api/v1/contracts/contracts/` (High)
- Line 69: `/api/v1/contracts/contracts/` (High)
- Line 70: `/api/v1/datasets/datasets/` (High)
- Line 70: `/api/v1/datasets/datasets/` (High)
- Line 71: `/api/v1/files/files/` (High)
- Line 71: `/api/v1/files/files/` (High)
- Line 138: `/api/v1/assets/assets/` (High)
- Line 138: `/api/v1/assets/assets/` (High)
- Line 139: `/api/v1/contracts/contracts/` (High)
- Line 139: `/api/v1/contracts/contracts/` (High)
- Line 140: `/api/v1/datasets/datasets/` (High)
- Line 140: `/api/v1/datasets/datasets/` (High)
- Line 141: `/api/v1/files/files/` (High)
- Line 141: `/api/v1/files/files/` (High)

### tests/e2e/test_scheduled_ingestion.py

- **Total References**: 18
- **Categories**: test
- **Priority Breakdown**:
  - High: 18

#### References

- Line 87: `/api/v1/scheduled-ingestions/` (High)
- Line 87: `/api/v1/scheduled-ingestions/` (High)
- Line 110: `/api/v1/scheduled-ingestions/{ingestion_id}/trigger/` (High)
- Line 110: `/api/v1/scheduled-ingestions/{ingestion_id}/trigger/` (High)
- Line 173: `/api/v1/scheduled-ingestions/{ingestion_id}/runs/` (High)
- Line 173: `/api/v1/scheduled-ingestions/{ingestion_id}/runs/` (High)
- Line 188: `/api/v1/scheduled-ingestions/{ingestion_id}/` (High)
- Line 188: `/api/v1/scheduled-ingestions/{ingestion_id}/` (High)
- Line 201: `/api/v1/scheduled-ingestions/{ingestion_id}/` (High)
- Line 201: `/api/v1/scheduled-ingestions/{ingestion_id}/` (High)
- Line 239: `/api/v1/scheduled-ingestions/` (High)
- Line 239: `/api/v1/scheduled-ingestions/` (High)
- Line 257: `/api/v1/scheduled-ingestions/` (High)
- Line 257: `/api/v1/scheduled-ingestions/` (High)
- Line 264: `/api/v1/scheduled-ingestions/` (High)
- Line 264: `/api/v1/scheduled-ingestions/` (High)
- Line 271: `/api/v1/scheduled-ingestions/` (High)
- Line 271: `/api/v1/scheduled-ingestions/` (High)

### tests/e2e/test_scheduled_ingestion_use_cases.py

- **Total References**: 36
- **Categories**: test
- **Priority Breakdown**:
  - High: 36

#### References

- Line 78: `/api/v1/scheduled-ingestions/` (High)
- Line 78: `/api/v1/scheduled-ingestions/` (High)
- Line 129: `/api/v1/scheduled-ingestions/` (High)
- Line 129: `/api/v1/scheduled-ingestions/` (High)
- Line 172: `/api/v1/scheduled-ingestions/` (High)
- Line 172: `/api/v1/scheduled-ingestions/` (High)
- Line 210: `/api/v1/scheduled-ingestions/` (High)
- Line 210: `/api/v1/scheduled-ingestions/` (High)
- Line 263: `/api/v1/scheduled-ingestions/{self.ingestion.id}/trigger/` (High)
- Line 263: `/api/v1/scheduled-ingestions/{self.ingestion.id}/trigger/` (High)
- Line 302: `/api/v1/scheduled-ingestions/{self.ingestion.id}/runs/` (High)
- Line 302: `/api/v1/scheduled-ingestions/{self.ingestion.id}/runs/` (High)
- Line 325: `/api/v1/scheduled-ingestions/runs/{run.id}/` (High)
- Line 325: `/api/v1/scheduled-ingestions/runs/{run.id}/` (High)
- Line 335: `/api/v1/scheduled-ingestions/dashboard/` (High)
- Line 335: `/api/v1/scheduled-ingestions/dashboard/` (High)
- Line 372: `/api/v1/scheduled-ingestions/{self.ingestion.id}/runs/` (High)
- Line 372: `/api/v1/scheduled-ingestions/{self.ingestion.id}/runs/` (High)
- Line 431: `/api/v1/scheduled-ingestions/{self.ingestion.id}/` (High)
- Line 431: `/api/v1/scheduled-ingestions/{self.ingestion.id}/` (High)
- ... and 16 more references

### tests/e2e/test_schema_inference.py

- **Total References**: 2
- **Categories**: test
- **Priority Breakdown**:
  - High: 2

#### References

- Line 265: `/api/v1/datasets/datasets/` (High)
- Line 265: `/api/v1/datasets/datasets/` (High)

### tests/e2e/test_sdk_python.py

- **Total References**: 3
- **Categories**: test
- **Priority Breakdown**:
  - High: 3

#### References

- Line 144: `/api/v1/auth/login/` (High)
- Line 144: `/api/v1/auth/login/` (High)
- Line 256: `/api/v1/auth/login/` (High)

### tests/e2e/test_security_comprehensive.py

- **Total References**: 36
- **Categories**: test
- **Priority Breakdown**:
  - High: 36

#### References

- Line 59: `/api/v1/assets/assets/` (High)
- Line 59: `/api/v1/assets/assets/` (High)
- Line 84: `/api/v1/assets/assets/{malicious_input}/` (High)
- Line 84: `/api/v1/assets/assets/{malicious_input}/` (High)
- Line 105: `/api/v1/assets/assets/` (High)
- Line 105: `/api/v1/assets/assets/` (High)
- Line 149: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 149: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 173: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 173: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 226: `/api/v1/assets/assets/` (High)
- Line 226: `/api/v1/assets/assets/` (High)
- Line 284: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 284: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 301: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 301: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 318: `/api/v1/assets/assets/` (High)
- Line 318: `/api/v1/assets/assets/` (High)
- Line 367: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 367: `/api/v1/assets/assets/{asset_id}/` (High)
- ... and 16 more references

### tests/e2e/test_semantic_layer.py

- **Total References**: 20
- **Categories**: test
- **Priority Breakdown**:
  - High: 20

#### References

- Line 117: `/api/v1/semantic/id/asset/{asset_id}` (High)
- Line 117: `/api/v1/semantic/id/asset/{asset_id}` (High)
- Line 200: `/api/v1/semantic/id/contract/{contract_id}` (High)
- Line 200: `/api/v1/semantic/id/contract/{contract_id}` (High)
- Line 274: `/api/v1/semantic/id/dataset/{dataset_id}` (High)
- Line 274: `/api/v1/semantic/id/dataset/{dataset_id}` (High)
- Line 367: `/api/v1/semantic/id/field/{asset_id}/id` (High)
- Line 367: `/api/v1/semantic/id/field/{asset_id}/id` (High)
- Line 395: `/api/v1/semantic/ontology` (High)
- Line 395: `/api/v1/semantic/ontology` (High)
- Line 416: `/api/v1/semantic/context.jsonld` (High)
- Line 416: `/api/v1/semantic/context.jsonld` (High)
- Line 471: `/api/v1/semantic/sparql` (High)
- Line 471: `/api/v1/semantic/sparql` (High)
- Line 514: `/api/v1/semantic/id/asset/{other_asset_id}` (High)
- Line 514: `/api/v1/semantic/id/asset/{other_asset_id}` (High)
- Line 585: `/api/v1/semantic/ontology` (High)
- Line 585: `/api/v1/semantic/ontology` (High)
- Line 605: `/api/v1/semantic/context.jsonld` (High)
- Line 605: `/api/v1/semantic/context.jsonld` (High)

### tests/e2e/test_tenant_config_e2e.py

- **Total References**: 50
- **Categories**: test
- **Priority Breakdown**:
  - High: 50

#### References

- Line 140: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 140: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 157: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 157: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 172: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 172: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 187: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 187: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 195: `/api/v1/tenants/tenants/{self.tenant2.id}/config/` (High)
- Line 195: `/api/v1/tenants/tenants/{self.tenant2.id}/config/` (High)
- Line 205: `/api/v1/tenants/tenants/{self.tenant2.id}/config/` (High)
- Line 205: `/api/v1/tenants/tenants/{self.tenant2.id}/config/` (High)
- Line 218: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 218: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 222: `/api/v1/tenants/tenants/{self.tenant2.id}/config/` (High)
- Line 222: `/api/v1/tenants/tenants/{self.tenant2.id}/config/` (High)
- Line 232: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 232: `/api/v1/tenants/tenants/{self.tenant.id}/config/` (High)
- Line 240: `/api/v1/tenants/tenants/{self.tenant2.id}/config/` (High)
- Line 240: `/api/v1/tenants/tenants/{self.tenant2.id}/config/` (High)
- ... and 30 more references

### tests/e2e/test_tenant_management.py

- **Total References**: 28
- **Categories**: test
- **Priority Breakdown**:
  - High: 28

#### References

- Line 51: `/api/v1/tenants/tenants/` (High)
- Line 51: `/api/v1/tenants/tenants/` (High)
- Line 92: `/api/v1/tenants/tenants/` (High)
- Line 92: `/api/v1/tenants/tenants/` (High)
- Line 114: `/api/v1/tenants/tenants/{tenant.id}/` (High)
- Line 114: `/api/v1/tenants/tenants/{tenant.id}/` (High)
- Line 132: `/api/v1/tenants/tenants/{tenant.id}/` (High)
- Line 132: `/api/v1/tenants/tenants/{tenant.id}/` (High)
- Line 166: `/api/v1/tenants/tenants/{tenant.id}/suspend/` (High)
- Line 166: `/api/v1/tenants/tenants/{tenant.id}/suspend/` (High)
- Line 199: `/api/v1/tenants/tenants/{tenant.id}/suspend/` (High)
- Line 199: `/api/v1/tenants/tenants/{tenant.id}/suspend/` (High)
- Line 219: `/api/v1/tenants/tenants/{tenant.id}/reactivate/` (High)
- Line 219: `/api/v1/tenants/tenants/{tenant.id}/reactivate/` (High)
- Line 250: `/api/v1/tenants/tenants/{tenant.id}/reactivate/` (High)
- Line 250: `/api/v1/tenants/tenants/{tenant.id}/reactivate/` (High)
- Line 265: `/api/v1/tenants/tenants/{tenant.id}/` (High)
- Line 265: `/api/v1/tenants/tenants/{tenant.id}/` (High)
- Line 347: `/api/v1/assets/assets/` (High)
- Line 347: `/api/v1/assets/assets/` (High)
- ... and 8 more references

### tests/e2e/test_transformation_pipelines.py

- **Total References**: 36
- **Categories**: test
- **Priority Breakdown**:
  - High: 36

#### References

- Line 70: `/api/v1/transformation/pipelines/` (High)
- Line 70: `/api/v1/transformation/pipelines/` (High)
- Line 84: `/api/v1/transformation/pipelines/` (High)
- Line 84: `/api/v1/transformation/pipelines/` (High)
- Line 100: `/api/v1/transformation/pipelines/{pipeline_id}/` (High)
- Line 100: `/api/v1/transformation/pipelines/{pipeline_id}/` (High)
- Line 110: `/api/v1/transformation/pipelines/{pipeline_id}/validate/` (High)
- Line 110: `/api/v1/transformation/pipelines/{pipeline_id}/validate/` (High)
- Line 128: `/api/v1/transformation/pipelines/{pipeline_id}/` (High)
- Line 128: `/api/v1/transformation/pipelines/{pipeline_id}/` (High)
- Line 139: `/api/v1/transformation/pipelines/{pipeline_id}/` (High)
- Line 139: `/api/v1/transformation/pipelines/{pipeline_id}/` (High)
- Line 148: `/api/v1/transformation/pipelines/{pipeline_id}/` (High)
- Line 148: `/api/v1/transformation/pipelines/{pipeline_id}/` (High)
- Line 155: `/api/v1/transformation/pipelines/{pipeline_id}/` (High)
- Line 155: `/api/v1/transformation/pipelines/{pipeline_id}/` (High)
- Line 170: `/api/v1/transformation/pipelines/` (High)
- Line 170: `/api/v1/transformation/pipelines/` (High)
- Line 203: `/api/v1/transformation/pipelines/` (High)
- Line 203: `/api/v1/transformation/pipelines/` (High)
- ... and 16 more references

### tests/e2e/test_user_journeys_comprehensive.py

- **Total References**: 14
- **Categories**: test
- **Priority Breakdown**:
  - High: 14

#### References

- Line 2228: `/api/v1/marketplace/listings/` (High)
- Line 2228: `/api/v1/marketplace/listings/` (High)
- Line 2235: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 2235: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 2243: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 2243: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 2283: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 2283: `/api/v1/assets/assets/{asset_id}/` (High)
- Line 2366: `/api/v1/files/files/{file_id}/download/` (High)
- Line 2366: `/api/v1/files/files/{file_id}/download/` (High)
- Line 2370: `/api/v1/contracts/contracts/{contract_id}/lineage/` (High)
- Line 2370: `/api/v1/contracts/contracts/{contract_id}/lineage/` (High)
- Line 3257: `/api/v1/assets/assets/` (High)
- Line 3257: `/api/v1/assets/assets/` (High)

### tests/e2e/test_user_management.py

- **Total References**: 28
- **Categories**: test
- **Priority Breakdown**:
  - High: 28

#### References

- Line 66: `/api/v1/users/users/` (High)
- Line 66: `/api/v1/users/users/` (High)
- Line 104: `/api/v1/users/users/` (High)
- Line 104: `/api/v1/users/users/` (High)
- Line 139: `/api/v1/users/users/` (High)
- Line 139: `/api/v1/users/users/` (High)
- Line 144: `/api/v1/users/users/?status=ACTIVE` (High)
- Line 144: `/api/v1/users/users/?status=ACTIVE` (High)
- Line 160: `/api/v1/users/users/{test_user.id}/` (High)
- Line 160: `/api/v1/users/users/{test_user.id}/` (High)
- Line 179: `/api/v1/users/users/{test_user.id}/` (High)
- Line 179: `/api/v1/users/users/{test_user.id}/` (High)
- Line 220: `/api/v1/users/users/{test_user.id}/roles/` (High)
- Line 220: `/api/v1/users/users/{test_user.id}/roles/` (High)
- Line 245: `/api/v1/users/users/invite/` (High)
- Line 245: `/api/v1/users/users/invite/` (High)
- Line 280: `/api/v1/users/users/{test_user.id}/` (High)
- Line 280: `/api/v1/users/users/{test_user.id}/` (High)
- Line 315: `/api/v1/users/users/{test_user.id}/` (High)
- Line 315: `/api/v1/users/users/{test_user.id}/` (High)
- ... and 8 more references

### tests/e2e/test_versioning_use_cases.py

- **Total References**: 10
- **Categories**: test
- **Priority Breakdown**:
  - High: 10

#### References

- Line 97: `/api/v1/datasets/datasets/{self.dataset_v1.id}/versions/` (High)
- Line 97: `/api/v1/datasets/datasets/{self.dataset_v1.id}/versions/` (High)
- Line 173: `/api/v1/datasets/datasets/{self.dataset_v1.id}/versions/` (High)
- Line 173: `/api/v1/datasets/datasets/{self.dataset_v1.id}/versions/` (High)
- Line 219: `/api/v1/datasets/datasets/{self.dataset_v1.id}/versions/` (High)
- Line 219: `/api/v1/datasets/datasets/{self.dataset_v1.id}/versions/` (High)
- Line 328: `/api/v1/datasets/datasets/{self.dataset_v2.id}/versions/compare/` (High)
- Line 328: `/api/v1/datasets/datasets/{self.dataset_v2.id}/versions/compare/` (High)
- Line 363: `/api/v1/datasets/datasets/{self.dataset_v2.id}/versions/compare/` (High)
- Line 363: `/api/v1/datasets/datasets/{self.dataset_v2.id}/versions/compare/` (High)

### tests/integration/test_api_edge_cases.py

- **Total References**: 66
- **Categories**: test
- **Priority Breakdown**:
  - High: 66

#### References

- Line 58: `/api/v1/contracts/contracts/{contract.id}/` (High)
- Line 58: `/api/v1/contracts/contracts/{contract.id}/` (High)
- Line 79: `/api/v1/contracts/contracts/{contract.id}/` (High)
- Line 79: `/api/v1/contracts/contracts/{contract.id}/` (High)
- Line 106: `/api/v1/contracts/contracts/{contract.id}/` (High)
- Line 106: `/api/v1/contracts/contracts/{contract.id}/` (High)
- Line 131: `/api/v1/contracts/contracts/{contract.id}/` (High)
- Line 131: `/api/v1/contracts/contracts/{contract.id}/` (High)
- Line 154: `/api/v1/contracts/contracts/{contract.id}/` (High)
- Line 154: `/api/v1/contracts/contracts/{contract.id}/` (High)
- Line 177: `/api/v1/contracts/contracts/{contract.id}/` (High)
- Line 177: `/api/v1/contracts/contracts/{contract.id}/` (High)
- Line 203: `/api/v1/contracts/contracts/{contract.id}/` (High)
- Line 203: `/api/v1/contracts/contracts/{contract.id}/` (High)
- Line 222: `/api/v1/contracts/contracts/` (High)
- Line 222: `/api/v1/contracts/contracts/` (High)
- Line 252: `/api/v1/contracts/contracts/` (High)
- Line 252: `/api/v1/contracts/contracts/` (High)
- Line 279: `/api/v1/contracts/contracts/` (High)
- Line 279: `/api/v1/contracts/contracts/` (High)
- ... and 46 more references

### tests/integration/test_api_endpoints_comprehensive.py

- **Total References**: 40
- **Categories**: test
- **Priority Breakdown**:
  - High: 40

#### References

- Line 51: `/api/v1/assets/` (High)
- Line 51: `/api/v1/assets/` (High)
- Line 57: `/api/v1/assets/` (High)
- Line 57: `/api/v1/assets/` (High)
- Line 69: `/api/v1/contracts/` (High)
- Line 69: `/api/v1/contracts/` (High)
- Line 81: `/api/v1/contracts/` (High)
- Line 81: `/api/v1/contracts/` (High)
- Line 99: `/api/v1/files/` (High)
- Line 99: `/api/v1/files/` (High)
- Line 105: `/api/v1/files/init-upload/` (High)
- Line 105: `/api/v1/files/init-upload/` (High)
- Line 114: `/api/v1/jobs/` (High)
- Line 114: `/api/v1/jobs/` (High)
- Line 127: `/api/v1/jobs/` (High)
- Line 127: `/api/v1/jobs/` (High)
- Line 143: `/api/v1/tenants/` (High)
- Line 143: `/api/v1/tenants/` (High)
- Line 254: `/api/v1/auth/login/` (High)
- Line 254: `/api/v1/auth/login/` (High)
- ... and 20 more references

### tests/integration/test_asset_apis_comprehensive.py

- **Total References**: 298
- **Categories**: test
- **Priority Breakdown**:
  - High: 298

#### References

- Line 5: `/api/v1/assets/` (High)
- Line 6: `/api/v1/assets/` (High)
- Line 7: `/api/v1/assets/{id}/` (High)
- Line 8: `/api/v1/assets/{id}/` (High)
- Line 9: `/api/v1/assets/{id}/activate/` (High)
- Line 10: `/api/v1/assets/{id}/` (High)
- Line 66: `/api/v1/assets/` (High)
- Line 128: `/api/v1/assets/assets/` (High)
- Line 128: `/api/v1/assets/assets/` (High)
- Line 138: `/api/v1/assets/assets/?page=1&page_size=2` (High)
- Line 138: `/api/v1/assets/assets/?page=1&page_size=2` (High)
- Line 148: `/api/v1/assets/assets/?domain=sales` (High)
- Line 148: `/api/v1/assets/assets/?domain=sales` (High)
- Line 158: `/api/v1/assets/assets/?status=ACTIVE` (High)
- Line 158: `/api/v1/assets/assets/?status=ACTIVE` (High)
- Line 170: `/api/v1/assets/assets/?status=ACTIVE&status=DRAFT` (High)
- Line 170: `/api/v1/assets/assets/?status=ACTIVE&status=DRAFT` (High)
- Line 180: `/api/v1/assets/assets/?visibility=PUBLIC` (High)
- Line 180: `/api/v1/assets/assets/?visibility=PUBLIC` (High)
- Line 197: `/api/v1/assets/assets/?ordering=name` (High)
- ... and 278 more references

### tests/integration/test_auth_apis_comprehensive.py

- **Total References**: 175
- **Categories**: test
- **Priority Breakdown**:
  - High: 175

#### References

- Line 45: `/api/v1/auth/register/` (High)
- Line 77: `/api/v1/auth/register/` (High)
- Line 77: `/api/v1/auth/register/` (High)
- Line 100: `/api/v1/auth/register/` (High)
- Line 100: `/api/v1/auth/register/` (High)
- Line 121: `/api/v1/auth/register/` (High)
- Line 121: `/api/v1/auth/register/` (High)
- Line 148: `/api/v1/auth/register/` (High)
- Line 148: `/api/v1/auth/register/` (High)
- Line 163: `/api/v1/auth/register/` (High)
- Line 163: `/api/v1/auth/register/` (High)
- Line 178: `/api/v1/auth/register/` (High)
- Line 178: `/api/v1/auth/register/` (High)
- Line 195: `/api/v1/auth/register/` (High)
- Line 195: `/api/v1/auth/register/` (High)
- Line 217: `/api/v1/auth/register/` (High)
- Line 217: `/api/v1/auth/register/` (High)
- Line 234: `/api/v1/auth/register/` (High)
- Line 234: `/api/v1/auth/register/` (High)
- Line 245: `/api/v1/auth/register/` (High)
- ... and 155 more references

### tests/integration/test_cli_integration.py

- **Total References**: 2
- **Categories**: test
- **Priority Breakdown**:
  - High: 2

#### References

- Line 80: `localhost:8000/api/v1` (High)
- Line 86: `localhost:8000/api/v1` (High)

### tests/integration/test_compliance_apis_comprehensive.py

- **Total References**: 138
- **Categories**: test
- **Priority Breakdown**:
  - High: 138

#### References

- Line 51: `/api/v1/compliance/runs/` (High)
- Line 110: `/api/v1/compliance/runs/` (High)
- Line 110: `/api/v1/compliance/runs/` (High)
- Line 133: `/api/v1/compliance/runs/` (High)
- Line 133: `/api/v1/compliance/runs/` (High)
- Line 153: `/api/v1/compliance/runs/` (High)
- Line 153: `/api/v1/compliance/runs/` (High)
- Line 174: `/api/v1/compliance/runs/` (High)
- Line 174: `/api/v1/compliance/runs/` (High)
- Line 196: `/api/v1/compliance/runs/` (High)
- Line 196: `/api/v1/compliance/runs/` (High)
- Line 211: `/api/v1/compliance/runs/` (High)
- Line 211: `/api/v1/compliance/runs/` (High)
- Line 226: `/api/v1/compliance/runs/` (High)
- Line 226: `/api/v1/compliance/runs/` (High)
- Line 240: `/api/v1/compliance/runs/` (High)
- Line 240: `/api/v1/compliance/runs/` (High)
- Line 258: `/api/v1/compliance/runs/` (High)
- Line 258: `/api/v1/compliance/runs/` (High)
- Line 285: `/api/v1/compliance/runs/` (High)
- ... and 118 more references

### tests/integration/test_contract_apis_comprehensive.py

- **Total References**: 268
- **Categories**: test
- **Priority Breakdown**:
  - High: 268

#### References

- Line 5: `/api/v1/contracts/contracts/` (High)
- Line 10: `/api/v1/contracts/contracts/` (High)
- Line 15: `/api/v1/contracts/contracts/{id}/` (High)
- Line 19: `/api/v1/contracts/contracts/{id}/` (High)
- Line 23: `/api/v1/contracts/contracts/{id}/validate/` (High)
- Line 60: `/api/v1/contracts/contracts/` (High)
- Line 160: `/api/v1/contracts/contracts/` (High)
- Line 160: `/api/v1/contracts/contracts/` (High)
- Line 171: `/api/v1/contracts/contracts/` (High)
- Line 171: `/api/v1/contracts/contracts/` (High)
- Line 182: `/api/v1/contracts/contracts/` (High)
- Line 182: `/api/v1/contracts/contracts/` (High)
- Line 193: `/api/v1/contracts/contracts/` (High)
- Line 193: `/api/v1/contracts/contracts/` (High)
- Line 203: `/api/v1/contracts/contracts/` (High)
- Line 203: `/api/v1/contracts/contracts/` (High)
- Line 212: `/api/v1/contracts/contracts/` (High)
- Line 212: `/api/v1/contracts/contracts/` (High)
- Line 220: `/api/v1/contracts/contracts/` (High)
- Line 220: `/api/v1/contracts/contracts/` (High)
- ... and 248 more references

### tests/integration/test_cross_service_integration_comprehensive.py

- **Total References**: 10
- **Categories**: test
- **Priority Breakdown**:
  - High: 10

#### References

- Line 68: `/api/v1/dq/dq-runs/` (High)
- Line 68: `/api/v1/dq/dq-runs/` (High)
- Line 143: `/api/v1/compliance/compliance-runs/` (High)
- Line 143: `/api/v1/compliance/compliance-runs/` (High)
- Line 216: `/api/v1/semantic/resolve-uri/` (High)
- Line 216: `/api/v1/semantic/resolve-uri/` (High)
- Line 234: `/api/v1/semantic/sparql/` (High)
- Line 234: `/api/v1/semantic/sparql/` (High)
- Line 274: `/api/v1/dq/dq-runs/` (High)
- Line 274: `/api/v1/dq/dq-runs/` (High)

### tests/integration/test_data_engineer_api_endpoints.py

- **Total References**: 36
- **Categories**: test
- **Priority Breakdown**:
  - High: 36

#### References

- Line 75: `/api/v1/contracts/contracts/` (High)
- Line 75: `/api/v1/contracts/contracts/` (High)
- Line 98: `/api/v1/contracts/contracts/{contract.id}/validate/` (High)
- Line 98: `/api/v1/contracts/contracts/{contract.id}/validate/` (High)
- Line 122: `/api/v1/contracts/contracts/{contract.id}/` (High)
- Line 122: `/api/v1/contracts/contracts/{contract.id}/` (High)
- Line 143: `/api/v1/contracts/contracts/` (High)
- Line 143: `/api/v1/contracts/contracts/` (High)
- Line 207: `/api/v1/scheduled-ingestions/` (High)
- Line 207: `/api/v1/scheduled-ingestions/` (High)
- Line 216: `/api/v1/scheduled-ingestions/scheduled-ingestions/` (High)
- Line 216: `/api/v1/scheduled-ingestions/scheduled-ingestions/` (High)
- Line 250: `/api/v1/scheduled-ingestions/{ingestion.id}/` (High)
- Line 250: `/api/v1/scheduled-ingestions/{ingestion.id}/` (High)
- Line 257: `/api/v1/scheduled-ingestions/scheduled-ingestions/{ingestion.id}/` (High)
- Line 257: `/api/v1/scheduled-ingestions/scheduled-ingestions/{ingestion.id}/` (High)
- Line 283: `/api/v1/scheduled-ingestions/` (High)
- Line 283: `/api/v1/scheduled-ingestions/` (High)
- Line 290: `/api/v1/scheduled-ingestions/scheduled-ingestions/` (High)
- Line 290: `/api/v1/scheduled-ingestions/scheduled-ingestions/` (High)
- ... and 16 more references

### tests/integration/test_dataset_apis_comprehensive.py

- **Total References**: 96
- **Categories**: test
- **Priority Breakdown**:
  - High: 96

#### References

- Line 5: `/api/v1/datasets/` (High)
- Line 10: `/api/v1/datasets/` (High)
- Line 15: `/api/v1/datasets/{id}/` (High)
- Line 19: `/api/v1/datasets/{id}/` (High)
- Line 23: `/api/v1/datasets/{id}/` (High)
- Line 58: `/api/v1/datasets/` (High)
- Line 167: `/api/v1/datasets/datasets/` (High)
- Line 167: `/api/v1/datasets/datasets/` (High)
- Line 194: `/api/v1/datasets/datasets/` (High)
- Line 194: `/api/v1/datasets/datasets/` (High)
- Line 223: `/api/v1/datasets/datasets/` (High)
- Line 223: `/api/v1/datasets/datasets/` (High)
- Line 247: `/api/v1/datasets/datasets.json/` (High)
- Line 247: `/api/v1/datasets/datasets.json/` (High)
- Line 272: `/api/v1/datasets/datasets/` (High)
- Line 272: `/api/v1/datasets/datasets/` (High)
- Line 284: `/api/v1/datasets/datasets/` (High)
- Line 284: `/api/v1/datasets/datasets/` (High)
- Line 297: `/api/v1/datasets/datasets/` (High)
- Line 297: `/api/v1/datasets/datasets/` (High)
- ... and 76 more references

### tests/integration/test_dcs_removal_integration.py

- **Total References**: 6
- **Categories**: test
- **Priority Breakdown**:
  - High: 6

#### References

- Line 71: `/api/v1/contracts/contracts/` (High)
- Line 71: `/api/v1/contracts/contracts/` (High)
- Line 127: `/api/v1/contracts/contracts/` (High)
- Line 127: `/api/v1/contracts/contracts/` (High)
- Line 254: `/api/v1/contracts/contracts/` (High)
- Line 254: `/api/v1/contracts/contracts/` (High)

### tests/integration/test_dpo_api_endpoints.py

- **Total References**: 45
- **Categories**: test
- **Priority Breakdown**:
  - High: 45

#### References

- Line 51: `/api/v1/assets/assets/` (High)
- Line 53: `/api/v1/assets/assets/` (High)
- Line 53: `/api/v1/assets/assets/` (High)
- Line 73: `/api/v1/assets/assets/{id}/` (High)
- Line 81: `/api/v1/assets/assets/{asset.id}/` (High)
- Line 81: `/api/v1/assets/assets/{asset.id}/` (High)
- Line 88: `/api/v1/assets/assets/{id}/` (High)
- Line 97: `/api/v1/assets/assets/{asset.id}/` (High)
- Line 97: `/api/v1/assets/assets/{asset.id}/` (High)
- Line 111: `/api/v1/assets/assets/{id}/` (High)
- Line 119: `/api/v1/assets/assets/{asset.id}/` (High)
- Line 119: `/api/v1/assets/assets/{asset.id}/` (High)
- Line 126: `/api/v1/assets/assets/{id}/activate/` (High)
- Line 151: `/api/v1/assets/assets/{asset.id}/activate/` (High)
- Line 151: `/api/v1/assets/assets/{asset.id}/activate/` (High)
- Line 161: `/api/v1/assets/assets/{id}/health-score/` (High)
- Line 172: `/api/v1/assets/assets/{asset.id}/health-score/` (High)
- Line 172: `/api/v1/assets/assets/{asset.id}/health-score/` (High)
- Line 201: `/api/v1/contracts/contracts/{id}/` (High)
- Line 223: `/api/v1/contracts/contracts/{contract.id}/` (High)
- ... and 25 more references

### tests/integration/test_dq_apis_comprehensive.py

- **Total References**: 103
- **Categories**: test
- **Priority Breakdown**:
  - High: 103

#### References

- Line 5: `/api/v1/dq/runs/` (High)
- Line 6: `/api/v1/dq/runs/{id}/` (High)
- Line 7: `/api/v1/dq/scorecards/` (High)
- Line 40: `/api/v1/dq/runs/` (High)
- Line 90: `/api/v1/dq/runs/` (High)
- Line 90: `/api/v1/dq/runs/` (High)
- Line 111: `/api/v1/dq/runs/` (High)
- Line 111: `/api/v1/dq/runs/` (High)
- Line 125: `/api/v1/dq/runs/` (High)
- Line 125: `/api/v1/dq/runs/` (High)
- Line 140: `/api/v1/dq/runs/` (High)
- Line 140: `/api/v1/dq/runs/` (High)
- Line 151: `/api/v1/dq/runs/` (High)
- Line 151: `/api/v1/dq/runs/` (High)
- Line 164: `/api/v1/dq/runs/` (High)
- Line 164: `/api/v1/dq/runs/` (High)
- Line 178: `/api/v1/dq/runs/` (High)
- Line 178: `/api/v1/dq/runs/` (High)
- Line 188: `/api/v1/dq/runs/` (High)
- Line 188: `/api/v1/dq/runs/` (High)
- ... and 83 more references

### tests/integration/test_file_apis_comprehensive.py

- **Total References**: 93
- **Categories**: test
- **Priority Breakdown**:
  - High: 93

#### References

- Line 40: `/api/v1/files/init` (High)
- Line 72: `/api/v1/files/files/init/` (High)
- Line 72: `/api/v1/files/files/init/` (High)
- Line 98: `/api/v1/files/files/init/` (High)
- Line 98: `/api/v1/files/files/init/` (High)
- Line 116: `/api/v1/files/files/init/` (High)
- Line 116: `/api/v1/files/files/init/` (High)
- Line 139: `/api/v1/files/files/init/` (High)
- Line 139: `/api/v1/files/files/init/` (High)
- Line 181: `/api/v1/files/files/init/` (High)
- Line 181: `/api/v1/files/files/init/` (High)
- Line 202: `/api/v1/files/files/init/` (High)
- Line 202: `/api/v1/files/files/init/` (High)
- Line 218: `/api/v1/files/files/init/` (High)
- Line 218: `/api/v1/files/files/init/` (High)
- Line 234: `/api/v1/files/files/init/` (High)
- Line 234: `/api/v1/files/files/init/` (High)
- Line 245: `/api/v1/files/files/init/` (High)
- Line 245: `/api/v1/files/files/init/` (High)
- Line 256: `/api/v1/files/files/init/` (High)
- ... and 73 more references

### tests/integration/test_file_storage_operations_comprehensive.py

- **Total References**: 16
- **Categories**: test
- **Priority Breakdown**:
  - High: 16

#### References

- Line 46: `/api/v1/files/init-upload/` (High)
- Line 46: `/api/v1/files/init-upload/` (High)
- Line 65: `/api/v1/files/init-upload/` (High)
- Line 65: `/api/v1/files/init-upload/` (High)
- Line 106: `/api/v1/files/{self.file_obj.id}/download/` (High)
- Line 106: `/api/v1/files/{self.file_obj.id}/download/` (High)
- Line 113: `/api/v1/files/00000000-0000-0000-0000-000000000000/download/` (High)
- Line 113: `/api/v1/files/00000000-0000-0000-0000-000000000000/download/` (High)
- Line 146: `/api/v1/files/{self.file_obj.id}/` (High)
- Line 146: `/api/v1/files/{self.file_obj.id}/` (High)
- Line 226: `/api/v1/files/init-upload/` (High)
- Line 226: `/api/v1/files/init-upload/` (High)
- Line 248: `/api/v1/files/{file_obj.id}/download/` (High)
- Line 248: `/api/v1/files/{file_obj.id}/download/` (High)
- Line 258: `/api/v1/files/init-upload/` (High)
- Line 258: `/api/v1/files/init-upload/` (High)

### tests/integration/test_job_apis_comprehensive.py

- **Total References**: 73
- **Categories**: test
- **Priority Breakdown**:
  - High: 73

#### References

- Line 38: `/api/v1/jobs/` (High)
- Line 69: `/api/v1/jobs/jobs/` (High)
- Line 69: `/api/v1/jobs/jobs/` (High)
- Line 91: `/api/v1/jobs/jobs/` (High)
- Line 91: `/api/v1/jobs/jobs/` (High)
- Line 112: `/api/v1/jobs/jobs/` (High)
- Line 112: `/api/v1/jobs/jobs/` (High)
- Line 131: `/api/v1/jobs/jobs/?page=1&page_size=10` (High)
- Line 131: `/api/v1/jobs/jobs/?page=1&page_size=10` (High)
- Line 164: `/api/v1/jobs/jobs/?status=PENDING` (High)
- Line 164: `/api/v1/jobs/jobs/?status=PENDING` (High)
- Line 191: `/api/v1/jobs/jobs/?type=DQ_RUN` (High)
- Line 191: `/api/v1/jobs/jobs/?type=DQ_RUN` (High)
- Line 224: `/api/v1/jobs/jobs/?type=DQ_RUN&status=PENDING` (High)
- Line 224: `/api/v1/jobs/jobs/?type=DQ_RUN&status=PENDING` (High)
- Line 259: `/api/v1/jobs/jobs/` (High)
- Line 259: `/api/v1/jobs/jobs/` (High)
- Line 293: `/api/v1/jobs/jobs/?ordering=created_at` (High)
- Line 293: `/api/v1/jobs/jobs/?ordering=created_at` (High)
- Line 316: `/api/v1/jobs/jobs/?status=INVALID_STATUS` (High)
- ... and 53 more references

### tests/integration/test_job_queue_operations_comprehensive.py

- **Total References**: 2
- **Categories**: test
- **Priority Breakdown**:
  - High: 2

#### References

- Line 217: `/api/v1/jobs/{job.id}/cancel/` (High)
- Line 217: `/api/v1/jobs/{job.id}/cancel/` (High)

### tests/integration/test_marketplace_apis_comprehensive.py

- **Total References**: 88
- **Categories**: test
- **Priority Breakdown**:
  - High: 88

#### References

- Line 40: `/api/v1/marketplace/listings/` (High)
- Line 96: `/api/v1/marketplace/listings/` (High)
- Line 96: `/api/v1/marketplace/listings/` (High)
- Line 105: `/api/v1/marketplace/listings/` (High)
- Line 105: `/api/v1/marketplace/listings/` (High)
- Line 121: `/api/v1/marketplace/listings/?page=1&page_size=3` (High)
- Line 121: `/api/v1/marketplace/listings/?page=1&page_size=3` (High)
- Line 132: `/api/v1/marketplace/listings/` (High)
- Line 132: `/api/v1/marketplace/listings/` (High)
- Line 142: `/api/v1/marketplace/listings/?search=Listing` (High)
- Line 142: `/api/v1/marketplace/listings/?search=Listing` (High)
- Line 153: `/api/v1/marketplace/listings/?domain=finance` (High)
- Line 153: `/api/v1/marketplace/listings/?domain=finance` (High)
- Line 164: `/api/v1/marketplace/listings/?sort=recency` (High)
- Line 164: `/api/v1/marketplace/listings/?sort=recency` (High)
- Line 176: `/api/v1/marketplace/listings/?status=INVALID_STATUS` (High)
- Line 176: `/api/v1/marketplace/listings/?status=INVALID_STATUS` (High)
- Line 189: `/api/v1/marketplace/listings/` (High)
- Line 189: `/api/v1/marketplace/listings/` (High)
- Line 212: `/api/v1/marketplace/listings/` (High)
- ... and 68 more references

### tests/integration/test_middleware_integration.py

- **Total References**: 16
- **Categories**: test
- **Priority Breakdown**:
  - High: 16

#### References

- Line 49: `/api/v1/assets/` (High)
- Line 49: `/api/v1/assets/` (High)
- Line 88: `/api/v1/assets/` (High)
- Line 88: `/api/v1/assets/` (High)
- Line 108: `/api/v1/assets/` (High)
- Line 108: `/api/v1/assets/` (High)
- Line 133: `/api/v1/assets/` (High)
- Line 133: `/api/v1/assets/` (High)
- Line 138: `/api/v1/assets/` (High)
- Line 138: `/api/v1/assets/` (High)
- Line 172: `/api/v1/dq/runs/` (High)
- Line 172: `/api/v1/dq/runs/` (High)
- Line 191: `/api/v1/assets/` (High)
- Line 191: `/api/v1/assets/` (High)
- Line 201: `/api/v1/assets/` (High)
- Line 201: `/api/v1/assets/` (High)

### tests/integration/test_odps_cross_integration.py

- **Total References**: 11
- **Categories**: test
- **Priority Breakdown**:
  - High: 11

#### References

- Line 258: `localhost:8000/api/v1` (High)
- Line 342: `/api/v1/contracts/{contract_id}/` (High)
- Line 342: `/api/v1/contracts/{contract_id}/` (High)
- Line 480: `/api/v1/contracts/?asset_id={asset_id}&spec_type=ODPS` (High)
- Line 480: `/api/v1/contracts/?asset_id={asset_id}&spec_type=ODPS` (High)
- Line 512: `/api/v1/contracts/?asset_id={asset_id}&spec_type=ODPS` (High)
- Line 512: `/api/v1/contracts/?asset_id={asset_id}&spec_type=ODPS` (High)
- Line 846: `/api/v1/contracts/?asset_id={asset_id}&spec_type=ODPS` (High)
- Line 846: `/api/v1/contracts/?asset_id={asset_id}&spec_type=ODPS` (High)
- Line 877: `/api/v1/contracts/?asset_id={asset_id}&spec_type=ODPS` (High)
- Line 877: `/api/v1/contracts/?asset_id={asset_id}&spec_type=ODPS` (High)

### tests/integration/test_openapi_completeness.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 35: `/api/v1/openapi.json` (High)

### tests/integration/test_rate_limiting_integration.py

- **Total References**: 12
- **Categories**: test
- **Priority Breakdown**:
  - High: 12

#### References

- Line 48: `/api/v1/dq/runs/` (High)
- Line 48: `/api/v1/dq/runs/` (High)
- Line 114: `/api/v1/dq/runs/` (High)
- Line 114: `/api/v1/dq/runs/` (High)
- Line 205: `/api/v1/dq/runs/` (High)
- Line 205: `/api/v1/dq/runs/` (High)
- Line 300: `/api/v1/dq/runs/` (High)
- Line 300: `/api/v1/dq/runs/` (High)
- Line 441: `/api/v1/dq/runs/` (High)
- Line 441: `/api/v1/dq/runs/` (High)
- Line 464: `/api/v1/dq/runs/` (High)
- Line 464: `/api/v1/dq/runs/` (High)

### tests/integration/test_search_apis_comprehensive.py

- **Total References**: 100
- **Categories**: test
- **Priority Breakdown**:
  - High: 100

#### References

- Line 5: `/api/v1/search/search/` (High)
- Line 42: `/api/v1/search/search/` (High)
- Line 184: `/api/v1/search/search/` (High)
- Line 184: `/api/v1/search/search/` (High)
- Line 196: `/api/v1/search/search/` (High)
- Line 196: `/api/v1/search/search/` (High)
- Line 204: `/api/v1/search/search/` (High)
- Line 204: `/api/v1/search/search/` (High)
- Line 205: `/api/v1/search/search/` (High)
- Line 205: `/api/v1/search/search/` (High)
- Line 214: `/api/v1/search/search/` (High)
- Line 214: `/api/v1/search/search/` (High)
- Line 238: `/api/v1/search/search/` (High)
- Line 238: `/api/v1/search/search/` (High)
- Line 249: `/api/v1/search/search/` (High)
- Line 249: `/api/v1/search/search/` (High)
- Line 262: `/api/v1/search/search/` (High)
- Line 262: `/api/v1/search/search/` (High)
- Line 273: `/api/v1/search/search/` (High)
- Line 273: `/api/v1/search/search/` (High)
- ... and 80 more references

### tests/integration/test_services_django6.py

- **Total References**: 4
- **Categories**: test
- **Priority Breakdown**:
  - High: 4

#### References

- Line 97: `/api/v1/assets/` (High)
- Line 97: `/api/v1/assets/` (High)
- Line 387: `/api/v1/dq/dq-runs/` (High)
- Line 387: `/api/v1/dq/dq-runs/` (High)

### tests/integration/test_tenant_config_api.py

- **Total References**: 42
- **Categories**: test
- **Priority Breakdown**:
  - High: 40
  - Low: 2

#### References

- Line 79: `/api/v1/tenants/{id}/config` (Low)
  - ⚠️ In comment
- Line 84: `/api/v1/tenants/tenants/{self.tenant1.id}/config/` (High)
- Line 84: `/api/v1/tenants/tenants/{self.tenant1.id}/config/` (High)
- Line 95: `/api/v1/tenants/tenants/{self.tenant1.id}/config/` (High)
- Line 95: `/api/v1/tenants/tenants/{self.tenant1.id}/config/` (High)
- Line 103: `/api/v1/tenants/tenants/{self.tenant1.id}/config/` (High)
- Line 103: `/api/v1/tenants/tenants/{self.tenant1.id}/config/` (High)
- Line 118: `/api/v1/tenants/tenants/{self.tenant1.id}/config/` (High)
- Line 118: `/api/v1/tenants/tenants/{self.tenant1.id}/config/` (High)
- Line 129: `/api/v1/tenants/tenants/{fake_tenant_id}/config/` (High)
- Line 129: `/api/v1/tenants/tenants/{fake_tenant_id}/config/` (High)
- Line 137: `/api/v1/tenants/tenants/{self.tenant1.id}/config/` (High)
- Line 137: `/api/v1/tenants/tenants/{self.tenant1.id}/config/` (High)
- Line 145: `/api/v1/tenants/tenants/{self.tenant2.id}/config/` (High)
- Line 145: `/api/v1/tenants/tenants/{self.tenant2.id}/config/` (High)
- Line 151: `/api/v1/tenants/tenants/{self.tenant1.id}/config/` (High)
- Line 151: `/api/v1/tenants/tenants/{self.tenant1.id}/config/` (High)
- Line 155: `/api/v1/tenants/{id}/config` (Low)
  - ⚠️ In comment
- Line 162: `/api/v1/tenants/tenants/{self.tenant1.id}/config/` (High)
- Line 162: `/api/v1/tenants/tenants/{self.tenant1.id}/config/` (High)
- ... and 22 more references

### tests/performance/EXECUTION_REPORT.md

- **Total References**: 5
- **Categories**: test
- **Priority Breakdown**:
  - High: 5

#### References

- Line 30: `/api/v1/auth/login` (High)
- Line 30: `/api/v1/auth/login` (High)
- Line 90: `/api/v1/auth/login` (High)
- Line 90: `/api/v1/auth/login` (High)
- Line 90: `localhost:8000/api/v1` (High)

### tests/performance/locust_api_endpoints_availability.py

- **Total References**: 24
- **Categories**: test
- **Priority Breakdown**:
  - High: 24

#### References

- Line 60: `/api/v1/assets` (High)
- Line 60: `/api/v1/assets` (High)
- Line 67: `/api/v1/assets/{asset_id}` (High)
- Line 67: `/api/v1/assets/{asset_id}` (High)
- Line 74: `/api/v1/contracts` (High)
- Line 74: `/api/v1/contracts` (High)
- Line 81: `/api/v1/contracts/{contract_id}` (High)
- Line 81: `/api/v1/contracts/{contract_id}` (High)
- Line 88: `/api/v1/jobs` (High)
- Line 88: `/api/v1/jobs` (High)
- Line 99: `/api/v1/files` (High)
- Line 99: `/api/v1/files` (High)
- Line 104: `/api/v1/datasets` (High)
- Line 104: `/api/v1/datasets` (High)
- Line 115: `/api/v1/assets` (High)
- Line 115: `/api/v1/assets` (High)
- Line 129: `/api/v1/assets/{asset_id}` (High)
- Line 129: `/api/v1/assets/{asset_id}` (High)
- Line 147: `/api/v1/contracts` (High)
- Line 147: `/api/v1/contracts` (High)
- ... and 4 more references

### tests/performance/locust_database_query_performance.py

- **Total References**: 24
- **Categories**: test
- **Priority Breakdown**:
  - High: 24

#### References

- Line 61: `/api/v1/assets` (High)
- Line 61: `/api/v1/assets` (High)
- Line 64: `/api/v1/assets` (High)
- Line 64: `/api/v1/assets` (High)
- Line 74: `/api/v1/assets/{asset_id}` (High)
- Line 74: `/api/v1/assets/{asset_id}` (High)
- Line 76: `/api/v1/assets/{id}` (High)
- Line 76: `/api/v1/assets/{id}` (High)
- Line 95: `/api/v1/assets` (High)
- Line 95: `/api/v1/assets` (High)
- Line 98: `/api/v1/assets` (High)
- Line 98: `/api/v1/assets` (High)
- Line 110: `/api/v1/jobs` (High)
- Line 110: `/api/v1/jobs` (High)
- Line 113: `/api/v1/jobs` (High)
- Line 113: `/api/v1/jobs` (High)
- Line 126: `/api/v1/assets` (High)
- Line 126: `/api/v1/assets` (High)
- Line 129: `/api/v1/assets` (High)
- Line 129: `/api/v1/assets` (High)
- ... and 4 more references

### tests/performance/locust_endurance_test.py

- **Total References**: 14
- **Categories**: test
- **Priority Breakdown**:
  - High: 14

#### References

- Line 72: `/api/v1/contracts/contracts/` (High)
- Line 72: `/api/v1/contracts/contracts/` (High)
- Line 96: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 96: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 117: `/api/v1/contracts/contracts/` (High)
- Line 117: `/api/v1/contracts/contracts/` (High)
- Line 141: `/api/v1/assets/assets/` (High)
- Line 141: `/api/v1/assets/assets/` (High)
- Line 158: `/api/v1/assets/assets/` (High)
- Line 158: `/api/v1/assets/assets/` (High)
- Line 177: `/api/v1/jobs/jobs/` (High)
- Line 177: `/api/v1/jobs/jobs/` (High)
- Line 217: `/api/v1/observability/metrics/` (High)
- Line 217: `/api/v1/observability/metrics/` (High)

### tests/performance/locust_file_upload_download.py

- **Total References**: 12
- **Categories**: test
- **Priority Breakdown**:
  - High: 12

#### References

- Line 103: `/api/v1/files/{file_id}/download` (High)
- Line 103: `/api/v1/files/{file_id}/download` (High)
- Line 105: `/api/v1/files/{id}/download` (High)
- Line 105: `/api/v1/files/{id}/download` (High)
- Line 155: `/api/v1/files/init` (High)
- Line 155: `/api/v1/files/init` (High)
- Line 158: `/api/v1/files/init` (High)
- Line 158: `/api/v1/files/init` (High)
- Line 237: `/api/v1/files/{file_id}/complete` (High)
- Line 237: `/api/v1/files/{file_id}/complete` (High)
- Line 240: `/api/v1/files/{id}/complete` (High)
- Line 240: `/api/v1/files/{id}/complete` (High)

### tests/performance/locust_job_queue_throughput.py

- **Total References**: 12
- **Categories**: test
- **Priority Breakdown**:
  - High: 12

#### References

- Line 80: `/api/v1/jobs/{job_id}` (High)
- Line 80: `/api/v1/jobs/{job_id}` (High)
- Line 82: `/api/v1/jobs/{id}` (High)
- Line 82: `/api/v1/jobs/{id}` (High)
- Line 129: `/api/v1/jobs` (High)
- Line 129: `/api/v1/jobs` (High)
- Line 132: `/api/v1/jobs` (High)
- Line 132: `/api/v1/jobs` (High)
- Line 209: `/api/v1/assets` (High)
- Line 209: `/api/v1/assets` (High)
- Line 212: `/api/v1/assets` (High)
- Line 212: `/api/v1/assets` (High)

### tests/performance/locust_spike_test.py

- **Total References**: 10
- **Categories**: test
- **Priority Breakdown**:
  - High: 10

#### References

- Line 71: `/api/v1/contracts/contracts/` (High)
- Line 71: `/api/v1/contracts/contracts/` (High)
- Line 96: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 96: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 125: `/api/v1/contracts/contracts/` (High)
- Line 125: `/api/v1/contracts/contracts/` (High)
- Line 152: `/api/v1/contracts/contracts/` (High)
- Line 152: `/api/v1/contracts/contracts/` (High)
- Line 198: `/api/v1/contracts/contracts/` (High)
- Line 198: `/api/v1/contracts/contracts/` (High)

### tests/performance/locust_stress_test.py

- **Total References**: 16
- **Categories**: test
- **Priority Breakdown**:
  - High: 16

#### References

- Line 78: `/api/v1/contracts/contracts/` (High)
- Line 78: `/api/v1/contracts/contracts/` (High)
- Line 107: `/api/v1/contracts/contracts/` (High)
- Line 107: `/api/v1/contracts/contracts/` (High)
- Line 132: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 132: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 156: `/api/v1/assets/assets/` (High)
- Line 156: `/api/v1/assets/assets/` (High)
- Line 179: `/api/v1/assets/assets/` (High)
- Line 179: `/api/v1/assets/assets/` (High)
- Line 205: `/api/v1/contracts/contracts/` (High)
- Line 205: `/api/v1/contracts/contracts/` (High)
- Line 239: `/api/v1/contracts/contracts/` (High)
- Line 239: `/api/v1/contracts/contracts/` (High)
- Line 271: `/api/v1/contracts/contracts/` (High)
- Line 271: `/api/v1/contracts/contracts/` (High)

### tests/performance/test_performance.py

- **Total References**: 6
- **Categories**: test
- **Priority Breakdown**:
  - High: 6

#### References

- Line 67: `/api/v1/contracts/contracts/` (High)
- Line 67: `/api/v1/contracts/contracts/` (High)
- Line 489: `/api/v1/contracts/contracts/{contract.id}/` (High)
- Line 489: `/api/v1/contracts/contracts/{contract.id}/` (High)
- Line 516: `/api/v1/contracts/contracts/` (High)
- Line 516: `/api/v1/contracts/contracts/` (High)

### tests/performance/test_performance_baseline.py

- **Total References**: 6
- **Categories**: test
- **Priority Breakdown**:
  - High: 6

#### References

- Line 220: `/api/v1/contracts/` (High)
- Line 220: `/api/v1/contracts/` (High)
- Line 231: `/api/v1/contracts/` (High)
- Line 231: `/api/v1/contracts/` (High)
- Line 246: `/api/v1/assets/` (High)
- Line 246: `/api/v1/assets/` (High)

### tests/performance/test_performance_django6.py

- **Total References**: 8
- **Categories**: test
- **Priority Breakdown**:
  - High: 8

#### References

- Line 65: `/api/v1/assets/` (High)
- Line 65: `/api/v1/assets/` (High)
- Line 218: `/api/v1/assets/` (High)
- Line 218: `/api/v1/assets/` (High)
- Line 229: `/api/v1/assets/` (High)
- Line 229: `/api/v1/assets/` (High)
- Line 407: `/api/v1/files/files/init/` (High)
- Line 407: `/api/v1/files/files/init/` (High)

### tests/regression/test_api_endpoints.py

- **Total References**: 161
- **Categories**: test
- **Priority Breakdown**:
  - High: 161

#### References

- Line 64: `/api/v1/auth/login/` (High)
- Line 67: `/api/v1/auth/login/` (High)
- Line 67: `/api/v1/auth/login/` (High)
- Line 76: `/api/v1/auth/refresh/` (High)
- Line 79: `/api/v1/auth/login/` (High)
- Line 79: `/api/v1/auth/login/` (High)
- Line 87: `/api/v1/auth/refresh/` (High)
- Line 87: `/api/v1/auth/refresh/` (High)
- Line 95: `/api/v1/auth/logout/` (High)
- Line 96: `/api/v1/auth/logout/` (High)
- Line 96: `/api/v1/auth/logout/` (High)
- Line 100: `/api/v1/auth/api-keys/` (High)
- Line 101: `/api/v1/auth/api-keys/` (High)
- Line 101: `/api/v1/auth/api-keys/` (High)
- Line 110: `/api/v1/auth/api-keys/` (High)
- Line 112: `/api/v1/auth/api-keys/` (High)
- Line 112: `/api/v1/auth/api-keys/` (High)
- Line 124: `/api/v1/auth/api-keys/{id}/` (High)
- Line 125: `/api/v1/auth/api-keys/{self.api_key_obj.id}/` (High)
- Line 125: `/api/v1/auth/api-keys/{self.api_key_obj.id}/` (High)
- ... and 141 more references

### tests/regression/test_auth_authorization.py

- **Total References**: 40
- **Categories**: test
- **Priority Breakdown**:
  - High: 40

#### References

- Line 54: `/api/v1/auth/login/` (High)
- Line 54: `/api/v1/auth/login/` (High)
- Line 66: `/api/v1/auth/login/` (High)
- Line 66: `/api/v1/auth/login/` (High)
- Line 74: `/api/v1/assets/assets/` (High)
- Line 74: `/api/v1/assets/assets/` (High)
- Line 81: `/api/v1/auth/login/` (High)
- Line 81: `/api/v1/auth/login/` (High)
- Line 89: `/api/v1/auth/refresh/` (High)
- Line 89: `/api/v1/auth/refresh/` (High)
- Line 100: `/api/v1/auth/login/` (High)
- Line 100: `/api/v1/auth/login/` (High)
- Line 108: `/api/v1/auth/logout/` (High)
- Line 108: `/api/v1/auth/logout/` (High)
- Line 127: `/api/v1/assets/assets/` (High)
- Line 127: `/api/v1/assets/assets/` (High)
- Line 137: `/api/v1/auth/api-keys/` (High)
- Line 137: `/api/v1/auth/api-keys/` (High)
- Line 159: `/api/v1/auth/api-keys/` (High)
- Line 159: `/api/v1/auth/api-keys/` (High)
- ... and 20 more references

### tests/regression/test_file_storage.py

- **Total References**: 26
- **Categories**: test
- **Priority Breakdown**:
  - High: 26

#### References

- Line 53: `/api/v1/files/files/init/` (High)
- Line 53: `/api/v1/files/files/init/` (High)
- Line 74: `/api/v1/files/files/init/` (High)
- Line 74: `/api/v1/files/files/init/` (High)
- Line 90: `/api/v1/files/files/{file_id}/complete/` (High)
- Line 90: `/api/v1/files/files/{file_id}/complete/` (High)
- Line 103: `/api/v1/files/files/init/` (High)
- Line 103: `/api/v1/files/files/init/` (High)
- Line 119: `/api/v1/files/files/{file_id}/complete/` (High)
- Line 119: `/api/v1/files/files/{file_id}/complete/` (High)
- Line 151: `/api/v1/files/files/{file.id}/download/` (High)
- Line 151: `/api/v1/files/files/{file.id}/download/` (High)
- Line 162: `/api/v1/files/files/{fake_id}/download/` (High)
- Line 162: `/api/v1/files/files/{fake_id}/download/` (High)
- Line 185: `/api/v1/files/files/{file_id}/` (High)
- Line 185: `/api/v1/files/files/{file_id}/` (High)
- Line 238: `/api/v1/files/files/{file.id}/` (High)
- Line 238: `/api/v1/files/files/{file.id}/` (High)
- Line 259: `/api/v1/files/files/{file.id}/` (High)
- Line 259: `/api/v1/files/files/{file.id}/` (High)
- ... and 6 more references

### tests/regression/test_integrations.py

- **Total References**: 40
- **Categories**: test
- **Priority Breakdown**:
  - High: 40

#### References

- Line 75: `/api/v1/dq/dq-runs/` (High)
- Line 75: `/api/v1/dq/dq-runs/` (High)
- Line 88: `/api/v1/dq/dq-runs/{dq_run_id}/` (High)
- Line 88: `/api/v1/dq/dq-runs/{dq_run_id}/` (High)
- Line 113: `/api/v1/dq/dq-runs/{dq_run.id}/` (High)
- Line 113: `/api/v1/dq/dq-runs/{dq_run.id}/` (High)
- Line 154: `/api/v1/dq/dq-runs/` (High)
- Line 154: `/api/v1/dq/dq-runs/` (High)
- Line 165: `/api/v1/compliance/compliance-runs/` (High)
- Line 165: `/api/v1/compliance/compliance-runs/` (High)
- Line 178: `/api/v1/compliance/compliance-runs/{compliance_run_id}/` (High)
- Line 178: `/api/v1/compliance/compliance-runs/{compliance_run_id}/` (High)
- Line 201: `/api/v1/compliance/compliance-runs/{compliance_run.id}/` (High)
- Line 201: `/api/v1/compliance/compliance-runs/{compliance_run.id}/` (High)
- Line 238: `/api/v1/compliance/compliance-runs/` (High)
- Line 238: `/api/v1/compliance/compliance-runs/` (High)
- Line 246: `/api/v1/compliance/compliance-runs/` (High)
- Line 246: `/api/v1/compliance/compliance-runs/` (High)
- Line 257: `/api/v1/compliance/compliance-runs/` (High)
- Line 257: `/api/v1/compliance/compliance-runs/` (High)
- ... and 20 more references

### tests/regression/test_job_queue.py

- **Total References**: 12
- **Categories**: test
- **Priority Breakdown**:
  - High: 12

#### References

- Line 62: `/api/v1/jobs/jobs/` (High)
- Line 62: `/api/v1/jobs/jobs/` (High)
- Line 164: `/api/v1/jobs/jobs/{job.id}/` (High)
- Line 164: `/api/v1/jobs/jobs/{job.id}/` (High)
- Line 197: `/api/v1/jobs/jobs/` (High)
- Line 197: `/api/v1/jobs/jobs/` (High)
- Line 217: `/api/v1/jobs/jobs/{job.id}/cancel/` (High)
- Line 217: `/api/v1/jobs/jobs/{job.id}/cancel/` (High)
- Line 338: `/api/v1/dq/dq-runs/` (High)
- Line 338: `/api/v1/dq/dq-runs/` (High)
- Line 352: `/api/v1/compliance/compliance-runs/` (High)
- Line 352: `/api/v1/compliance/compliance-runs/` (High)

### tests/regression/test_middleware.py

- **Total References**: 26
- **Categories**: test
- **Priority Breakdown**:
  - High: 26

#### References

- Line 59: `/api/v1/assets/assets/` (High)
- Line 59: `/api/v1/assets/assets/` (High)
- Line 76: `/api/v1/assets/assets/` (High)
- Line 76: `/api/v1/assets/assets/` (High)
- Line 86: `/api/v1/assets/assets/` (High)
- Line 86: `/api/v1/assets/assets/` (High)
- Line 122: `/api/v1/assets/assets/` (High)
- Line 122: `/api/v1/assets/assets/` (High)
- Line 144: `/api/v1/assets/assets/` (High)
- Line 144: `/api/v1/assets/assets/` (High)
- Line 153: `/api/v1/assets/assets/` (High)
- Line 153: `/api/v1/assets/assets/` (High)
- Line 175: `/api/v1/assets/assets/` (High)
- Line 175: `/api/v1/assets/assets/` (High)
- Line 190: `/api/v1/assets/assets/` (High)
- Line 190: `/api/v1/assets/assets/` (High)
- Line 205: `/api/v1/assets/assets/` (High)
- Line 205: `/api/v1/assets/assets/` (High)
- Line 225: `/api/v1/assets/assets/` (High)
- Line 225: `/api/v1/assets/assets/` (High)
- ... and 6 more references

### tests/regression/test_tenant_isolation.py

- **Total References**: 39
- **Categories**: test
- **Priority Breakdown**:
  - High: 38
  - Low: 1

#### References

- Line 80: `/api/v1/assets/assets/` (High)
- Line 80: `/api/v1/assets/assets/` (High)
- Line 84: `/api/v1/assets/assets/{asset2.id}/` (High)
- Line 84: `/api/v1/assets/assets/{asset2.id}/` (High)
- Line 89: `/api/v1/assets/assets/` (High)
- Line 89: `/api/v1/assets/assets/` (High)
- Line 93: `/api/v1/assets/assets/{asset1.id}/` (High)
- Line 93: `/api/v1/assets/assets/{asset1.id}/` (High)
- Line 135: `/api/v1/contracts/contracts/` (High)
- Line 135: `/api/v1/contracts/contracts/` (High)
- Line 139: `/api/v1/contracts/contracts/{contract2.id}/` (High)
- Line 139: `/api/v1/contracts/contracts/{contract2.id}/` (High)
- Line 160: `/api/v1/files/files/` (High)
- Line 160: `/api/v1/files/files/` (High)
- Line 164: `/api/v1/files/files/{file2.id}/` (High)
- Line 164: `/api/v1/files/files/{file2.id}/` (High)
- Line 200: `/api/v1/jobs/jobs/` (High)
- Line 200: `/api/v1/jobs/jobs/` (High)
- Line 204: `/api/v1/jobs/jobs/{job2.id}/` (High)
- Line 204: `/api/v1/jobs/jobs/{job2.id}/` (High)
- ... and 19 more references

### tests/regression/test_workflows.py

- **Total References**: 52
- **Categories**: test
- **Priority Breakdown**:
  - High: 52

#### References

- Line 58: `/api/v1/assets/assets/` (High)
- Line 58: `/api/v1/assets/assets/` (High)
- Line 86: `/api/v1/contracts/contracts/` (High)
- Line 86: `/api/v1/contracts/contracts/` (High)
- Line 102: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 102: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 120: `/api/v1/assets/assets/` (High)
- Line 120: `/api/v1/assets/assets/` (High)
- Line 138: `/api/v1/contracts/contracts/` (High)
- Line 138: `/api/v1/contracts/contracts/` (High)
- Line 155: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 155: `/api/v1/contracts/contracts/{contract_id}/` (High)
- Line 168: `/api/v1/assets/assets/` (High)
- Line 168: `/api/v1/assets/assets/` (High)
- Line 181: `/api/v1/files/files/init/` (High)
- Line 181: `/api/v1/files/files/init/` (High)
- Line 198: `/api/v1/files/files/{file_id}/complete/` (High)
- Line 198: `/api/v1/files/files/{file_id}/complete/` (High)
- Line 210: `/api/v1/files/files/{file_id}/` (High)
- Line 210: `/api/v1/files/files/{file_id}/` (High)
- ... and 32 more references

### tests/sdk_python/conftest.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 354: `/api/v1/auth/login/` (High)

### tests/sdk_python/test_env_config.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 45: `localhost:8001/api/v1` (High)

### tests/sdk_python/test_sdk_error_handling.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 104: `/api/v1/auth/login/` (High)

### tests/security/test_security_features.py

- **Total References**: 4
- **Categories**: test
- **Priority Breakdown**:
  - High: 4

#### References

- Line 38: `/api/v1/health/` (High)
- Line 38: `/api/v1/health/` (High)
- Line 43: `/api/v1/assets/` (High)
- Line 43: `/api/v1/assets/` (High)

### tests/smoke/test_api_health.py

- **Total References**: 5
- **Categories**: test
- **Priority Breakdown**:
  - High: 5

#### References

- Line 111: `/api/v1/tenants/` (High)
- Line 121: `/api/v1/auth/login/` (High)
- Line 135: `/api/v1/tenants/` (High)
- Line 143: `/api/v1/assets/` (High)
- Line 151: `/api/v1/contracts/` (High)

### tests/uat/test_api_compatibility_django6.py

- **Total References**: 22
- **Categories**: test
- **Priority Breakdown**:
  - High: 22

#### References

- Line 47: `/api/v1/assets/` (High)
- Line 47: `/api/v1/assets/` (High)
- Line 48: `/api/v1/contracts/` (High)
- Line 48: `/api/v1/contracts/` (High)
- Line 49: `/api/v1/files/` (High)
- Line 49: `/api/v1/files/` (High)
- Line 50: `/api/v1/jobs/` (High)
- Line 50: `/api/v1/jobs/` (High)
- Line 60: `/api/v1/assets/` (High)
- Line 60: `/api/v1/assets/` (High)
- Line 93: `/api/v1/assets/{asset.id}/` (High)
- Line 93: `/api/v1/assets/{asset.id}/` (High)
- Line 104: `/api/v1/assets/00000000-0000-0000-0000-000000000000/` (High)
- Line 104: `/api/v1/assets/00000000-0000-0000-0000-000000000000/` (High)
- Line 132: `/api/v1/assets/` (High)
- Line 132: `/api/v1/assets/` (High)
- Line 145: `/api/v1/assets/` (High)
- Line 145: `/api/v1/assets/` (High)
- Line 192: `/api/v1/nonexistent/` (High)
- Line 192: `/api/v1/nonexistent/` (High)
- ... and 2 more references

### tests/uat/test_no_user_facing_changes_django6.py

- **Total References**: 28
- **Categories**: test
- **Priority Breakdown**:
  - High: 28

#### References

- Line 54: `/api/v1/assets/{self.asset.id}/` (High)
- Line 54: `/api/v1/assets/{self.asset.id}/` (High)
- Line 66: `/api/v1/assets/` (High)
- Line 66: `/api/v1/assets/` (High)
- Line 103: `/api/v1/assets/` (High)
- Line 103: `/api/v1/assets/` (High)
- Line 130: `/api/v1/assets/{asset.id}/` (High)
- Line 130: `/api/v1/assets/{asset.id}/` (High)
- Line 159: `/api/v1/auth/login/` (High)
- Line 159: `/api/v1/auth/login/` (High)
- Line 174: `/api/v1/nonexistent/` (High)
- Line 174: `/api/v1/nonexistent/` (High)
- Line 202: `/api/v1/assets/` (High)
- Line 202: `/api/v1/assets/` (High)
- Line 203: `/api/v1/contracts/` (High)
- Line 203: `/api/v1/contracts/` (High)
- Line 204: `/api/v1/files/` (High)
- Line 204: `/api/v1/files/` (High)
- Line 205: `/api/v1/jobs/` (High)
- Line 205: `/api/v1/jobs/` (High)
- ... and 8 more references

### tests/uat/test_sdk_compatibility_django6.py

- **Total References**: 16
- **Categories**: test
- **Priority Breakdown**:
  - High: 16

#### References

- Line 57: `localhost:8000/api/v1` (High)
- Line 63: `localhost:8000/api/v1` (High)
- Line 188: `/api/v1/assets/` (High)
- Line 188: `/api/v1/assets/` (High)
- Line 189: `/api/v1/contracts/` (High)
- Line 189: `/api/v1/contracts/` (High)
- Line 190: `/api/v1/files/` (High)
- Line 190: `/api/v1/files/` (High)
- Line 202: `/api/v1/auth/login/` (High)
- Line 202: `/api/v1/auth/login/` (High)
- Line 231: `/api/v1/assets/` (High)
- Line 231: `/api/v1/assets/` (High)
- Line 239: `/api/v1/assets/` (High)
- Line 239: `/api/v1/assets/` (High)
- Line 245: `/api/v1/assets/00000000-0000-0000-0000-000000000000/` (High)
- Line 245: `/api/v1/assets/00000000-0000-0000-0000-000000000000/` (High)

### tests/uat/test_user_acceptance_django6.py

- **Total References**: 22
- **Categories**: test
- **Priority Breakdown**:
  - High: 22

#### References

- Line 60: `/api/v1/contracts/` (High)
- Line 60: `/api/v1/contracts/` (High)
- Line 79: `/api/v1/contracts/{contract_id}/` (High)
- Line 79: `/api/v1/contracts/{contract_id}/` (High)
- Line 105: `/api/v1/files/init-upload/` (High)
- Line 105: `/api/v1/files/init-upload/` (High)
- Line 119: `/api/v1/assets/` (High)
- Line 119: `/api/v1/assets/` (High)
- Line 136: `/api/v1/contracts/` (High)
- Line 136: `/api/v1/contracts/` (High)
- Line 178: `/api/v1/dq/dq-runs/` (High)
- Line 178: `/api/v1/dq/dq-runs/` (High)
- Line 218: `/api/v1/compliance/compliance-runs/` (High)
- Line 218: `/api/v1/compliance/compliance-runs/` (High)
- Line 250: `/api/v1/semantic/resolve-uri/` (High)
- Line 250: `/api/v1/semantic/resolve-uri/` (High)
- Line 284: `/api/v1/marketplace/listings/` (High)
- Line 284: `/api/v1/marketplace/listings/` (High)
- Line 309: `/api/v1/assets/` (High)
- Line 309: `/api/v1/assets/` (High)
- ... and 2 more references

### tests/unit/cli/test_config.py

- **Total References**: 1
- **Categories**: test
- **Priority Breakdown**:
  - High: 1

#### References

- Line 79: `localhost:8000/api/v1` (High)

### tests/unit/notifications/test_email_templates.py

- **Total References**: 2
- **Categories**: test
- **Priority Breakdown**:
  - High: 2

#### References

- Line 235: `/api/v1/jobs/job-uuid-789` (High)
- Line 235: `/api/v1/jobs/job-uuid-789` (High)

### tests/unit/rate_limiting/test_middleware.py

- **Total References**: 22
- **Categories**: test
- **Priority Breakdown**:
  - High: 22

#### References

- Line 76: `/api/v1/dq/runs/` (High)
- Line 76: `/api/v1/dq/runs/` (High)
- Line 102: `/api/v1/dq/runs/` (High)
- Line 102: `/api/v1/dq/runs/` (High)
- Line 127: `/api/v1/dq/runs/` (High)
- Line 127: `/api/v1/dq/runs/` (High)
- Line 160: `/api/v1/dq/runs/` (High)
- Line 160: `/api/v1/dq/runs/` (High)
- Line 180: `/api/v1/dq/runs/` (High)
- Line 180: `/api/v1/dq/runs/` (High)
- Line 210: `/api/v1/dq/runs/` (High)
- Line 210: `/api/v1/dq/runs/` (High)
- Line 255: `/api/v1/dq/runs/` (High)
- Line 255: `/api/v1/dq/runs/` (High)
- Line 283: `/api/v1/dq/runs/` (High)
- Line 283: `/api/v1/dq/runs/` (High)
- Line 310: `/api/v1/dq/runs/` (High)
- Line 310: `/api/v1/dq/runs/` (High)
- Line 332: `/api/v1/dq/runs/` (High)
- Line 332: `/api/v1/dq/runs/` (High)
- ... and 2 more references

### tests/unit/rate_limiting/test_rate_limiting_edge_cases.py

- **Total References**: 2
- **Categories**: test
- **Priority Breakdown**:
  - High: 2

#### References

- Line 121: `/api/v1/contracts/contracts/` (High)
- Line 121: `/api/v1/contracts/contracts/` (High)

### tests/unit/test_dpo_workflows.py

- **Total References**: 2
- **Categories**: test
- **Priority Breakdown**:
  - High: 2

#### References

- Line 488: `/api/v1/assets/assets/{self.asset.id}/` (High)
- Line 488: `/api/v1/assets/assets/{self.asset.id}/` (High)

### tests/validate_odps_integration_guide.py

- **Total References**: 8
- **Categories**: test
- **Priority Breakdown**:
  - High: 2
  - Low: 6

#### References

- Line 25: `localhost:8000/api/v1` (High)
- Line 168: `/api/v1/contracts/products/` (Low)
  - ⚠️ In comment
- Line 244: `/api/v1/contracts/` (Low)
  - ⚠️ In comment
- Line 284: `/api/v1/contracts/{id}/export/?format=odps&output_format=json` (Low)
  - ⚠️ In comment
- Line 353: `/api/v1/contracts/{id}/export/?format=odps&output_format=yaml` (Low)
  - ⚠️ In comment
- Line 396: `/api/v1/contracts/{id}/download/?format=odps&output_format=json` (Low)
  - ⚠️ In comment
- Line 450: `/api/v1/contracts/{id}/download/?format=odps&output_format=yaml` (Low)
  - ⚠️ In comment
- Line 571: `localhost:8000/api/v1` (High)
