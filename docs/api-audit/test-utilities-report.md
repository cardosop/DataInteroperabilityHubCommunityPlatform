# Test Utilities and Helpers Impact Analysis

## Summary

- **Total Utility Modules**: 122
- **Total Helper Functions**: 2075
- **Total Endpoint URLs**: 92
- **Utilities with Endpoint URLs**: 3
- **Unique Endpoint Paths**: 28

### Utilities by Type

- **conftest**: 115
- **helper**: 4
- **utility**: 3

### Helpers by Type

- **fixture**: 708
- **function**: 1367

## Utility Modules

| Path | Type | Functions | Classes | Has Endpoints |
|------|------|----------|--------|---------------|
| tests/utils/test_data_management.py | utility | 15 | 2 | No |
| tests/utils/test_environment_validation.py | utility | 16 | 2 | No |
| tests/utils/tests/test_test_environment_validation.py | utility | 11 | 2 | No |
| tests/conftest.py | conftest | 54 | 0 | No |
| venv/lib/python3.14/site-packages/graphene_django/conftest.py | conftest | 2 | 0 | No |
| venv/lib/python3.14/site-packages/numpy/conftest.py | conftest | 8 | 0 | No |
| venv/lib/python3.14/site-packages/nbconvert/conftest.py | conftest | 0 | 0 | No |
| venv/lib/python3.14/site-packages/pandas/conftest.py | conftest | 118 | 2 | No |
| venv/lib/python3.14/site-packages/scipy/conftest.py | conftest | 9 | 0 | No |
| venv/lib/python3.14/site-packages/jupyterlab/tests/conftest.py | conftest | 1 | 0 | No |
| venv/lib/python3.14/site-packages/jupyter_lsp/tests/conftest.py | conftest | 16 | 3 | No |
| venv/lib/python3.14/site-packages/pandas/tests/util/conftest.py | conftest | 5 | 0 | No |
| venv/lib/python3.14/site-packages/pandas/tests/io/conftest.py | conftest | 15 | 0 | No |
| venv/lib/python3.14/site-packages/pandas/tests/strings/conftest.py | conftest | 1 | 0 | No |
| venv/lib/python3.14/site-packages/pandas/tests/plotting/conftest.py | conftest | 2 | 0 | No |
| venv/lib/python3.14/site-packages/pandas/tests/resample/conftest.py | conftest | 14 | 0 | No |
| venv/lib/python3.14/site-packages/pandas/tests/arithmetic/conftest.py | conftest | 6 | 0 | No |
| venv/lib/python3.14/site-packages/pandas/tests/groupby/conftest.py | conftest | 17 | 0 | No |
| venv/lib/python3.14/site-packages/pandas/tests/frame/conftest.py | conftest | 5 | 0 | No |
| venv/lib/python3.14/site-packages/pandas/tests/indexing/conftest.py | conftest | 16 | 0 | No |
| venv/lib/python3.14/site-packages/pandas/tests/window/conftest.py | conftest | 16 | 0 | No |
| venv/lib/python3.14/site-packages/pandas/tests/indexes/conftest.py | conftest | 3 | 0 | No |
| venv/lib/python3.14/site-packages/pandas/tests/extension/conftest.py | conftest | 21 | 0 | No |
| venv/lib/python3.14/site-packages/pandas/tests/reshape/concat/conftest.py | conftest | 1 | 0 | No |
| venv/lib/python3.14/site-packages/pandas/tests/indexes/multi/conftest.py | conftest | 1 | 0 | No |
| venv/lib/python3.14/site-packages/pandas/tests/arrays/integer/conftest.py | conftest | 4 | 0 | No |
| venv/lib/python3.14/site-packages/pandas/tests/arrays/floating/conftest.py | conftest | 4 | 0 | No |
| venv/lib/python3.14/site-packages/pandas/tests/window/moments/conftest.py | conftest | 7 | 0 | No |
| venv/lib/python3.14/site-packages/pandas/tests/io/parser/conftest.py | conftest | 18 | 6 | No |
| venv/lib/python3.14/site-packages/pandas/tests/io/pytables/conftest.py | conftest | 1 | 0 | No |
| venv/lib/python3.14/site-packages/pandas/tests/io/xml/conftest.py | conftest | 7 | 0 | No |
| venv/lib/python3.14/site-packages/pandas/tests/io/json/conftest.py | conftest | 1 | 0 | No |
| venv/lib/python3.14/site-packages/graphene_django/filter/tests/conftest.py | conftest | 15 | 7 | No |
| venv/lib/python3.14/site-packages/graphene/types/tests/conftest.py | conftest | 1 | 0 | No |
| venv/lib/python3.12/site-packages/graphene_django/conftest.py | conftest | 2 | 0 | No |
| venv/lib/python3.12/site-packages/numpy/conftest.py | conftest | 13 | 0 | No |
| venv/lib/python3.12/site-packages/pandas/conftest.py | conftest | 118 | 2 | No |
| venv/lib/python3.12/site-packages/scipy/conftest.py | conftest | 9 | 0 | No |
| venv/lib/python3.12/site-packages/pandas/tests/util/conftest.py | conftest | 5 | 0 | No |
| venv/lib/python3.12/site-packages/pandas/tests/io/conftest.py | conftest | 15 | 0 | No |
| venv/lib/python3.12/site-packages/pandas/tests/strings/conftest.py | conftest | 1 | 0 | No |
| venv/lib/python3.12/site-packages/pandas/tests/plotting/conftest.py | conftest | 2 | 0 | No |
| venv/lib/python3.12/site-packages/pandas/tests/resample/conftest.py | conftest | 14 | 0 | No |
| venv/lib/python3.12/site-packages/pandas/tests/arithmetic/conftest.py | conftest | 6 | 0 | No |
| venv/lib/python3.12/site-packages/pandas/tests/groupby/conftest.py | conftest | 17 | 0 | No |
| venv/lib/python3.12/site-packages/pandas/tests/frame/conftest.py | conftest | 5 | 0 | No |
| venv/lib/python3.12/site-packages/pandas/tests/indexing/conftest.py | conftest | 16 | 0 | No |
| venv/lib/python3.12/site-packages/pandas/tests/window/conftest.py | conftest | 16 | 0 | No |
| venv/lib/python3.12/site-packages/pandas/tests/indexes/conftest.py | conftest | 3 | 0 | No |
| venv/lib/python3.12/site-packages/pandas/tests/extension/conftest.py | conftest | 21 | 0 | No |
| venv/lib/python3.12/site-packages/pandas/tests/reshape/concat/conftest.py | conftest | 1 | 0 | No |
| venv/lib/python3.12/site-packages/pandas/tests/indexes/multi/conftest.py | conftest | 1 | 0 | No |
| venv/lib/python3.12/site-packages/pandas/tests/arrays/integer/conftest.py | conftest | 4 | 0 | No |
| venv/lib/python3.12/site-packages/pandas/tests/arrays/floating/conftest.py | conftest | 4 | 0 | No |
| venv/lib/python3.12/site-packages/pandas/tests/window/moments/conftest.py | conftest | 7 | 0 | No |
| venv/lib/python3.12/site-packages/pandas/tests/io/parser/conftest.py | conftest | 18 | 6 | No |
| venv/lib/python3.12/site-packages/pandas/tests/io/pytables/conftest.py | conftest | 1 | 0 | No |
| venv/lib/python3.12/site-packages/pandas/tests/io/xml/conftest.py | conftest | 7 | 0 | No |
| venv/lib/python3.12/site-packages/pandas/tests/io/json/conftest.py | conftest | 1 | 0 | No |
| venv/lib/python3.12/site-packages/graphene_django/filter/tests/conftest.py | conftest | 15 | 7 | No |
| venv/lib/python3.12/site-packages/graphene/types/tests/conftest.py | conftest | 1 | 0 | No |
| venv-python312-test/lib/python3.14/site-packages/numpy/conftest.py | conftest | 8 | 0 | No |
| venv-python312-test/lib/python3.14/site-packages/nbconvert/conftest.py | conftest | 0 | 0 | No |
| venv-python312-test/lib/python3.14/site-packages/pandas/conftest.py | conftest | 118 | 2 | No |
| venv-python312-test/lib/python3.14/site-packages/scipy/conftest.py | conftest | 9 | 0 | No |
| venv-python312-test/lib/python3.14/site-packages/jupyterlab/tests/conftest.py | conftest | 1 | 0 | No |
| venv-python312-test/lib/python3.14/site-packages/jupyter_lsp/tests/conftest.py | conftest | 16 | 3 | No |
| venv-python312-test/lib/python3.14/site-packages/pandas/tests/util/conftest.py | conftest | 5 | 0 | No |
| venv-python312-test/lib/python3.14/site-packages/pandas/tests/io/conftest.py | conftest | 15 | 0 | No |
| venv-python312-test/lib/python3.14/site-packages/pandas/tests/strings/conftest.py | conftest | 1 | 0 | No |
| venv-python312-test/lib/python3.14/site-packages/pandas/tests/plotting/conftest.py | conftest | 2 | 0 | No |
| venv-python312-test/lib/python3.14/site-packages/pandas/tests/resample/conftest.py | conftest | 14 | 0 | No |
| venv-python312-test/lib/python3.14/site-packages/pandas/tests/arithmetic/conftest.py | conftest | 6 | 0 | No |
| venv-python312-test/lib/python3.14/site-packages/pandas/tests/groupby/conftest.py | conftest | 17 | 0 | No |
| venv-python312-test/lib/python3.14/site-packages/pandas/tests/frame/conftest.py | conftest | 5 | 0 | No |
| venv-python312-test/lib/python3.14/site-packages/pandas/tests/indexing/conftest.py | conftest | 16 | 0 | No |
| venv-python312-test/lib/python3.14/site-packages/pandas/tests/window/conftest.py | conftest | 16 | 0 | No |
| venv-python312-test/lib/python3.14/site-packages/pandas/tests/indexes/conftest.py | conftest | 3 | 0 | No |
| venv-python312-test/lib/python3.14/site-packages/pandas/tests/extension/conftest.py | conftest | 21 | 0 | No |
| venv-python312-test/lib/python3.14/site-packages/pandas/tests/reshape/concat/conftest.py | conftest | 1 | 0 | No |
| venv-python312-test/lib/python3.14/site-packages/pandas/tests/indexes/multi/conftest.py | conftest | 1 | 0 | No |
| venv-python312-test/lib/python3.14/site-packages/pandas/tests/arrays/integer/conftest.py | conftest | 4 | 0 | No |
| venv-python312-test/lib/python3.14/site-packages/pandas/tests/arrays/floating/conftest.py | conftest | 4 | 0 | No |
| venv-python312-test/lib/python3.14/site-packages/pandas/tests/window/moments/conftest.py | conftest | 7 | 0 | No |
| venv-python312-test/lib/python3.14/site-packages/pandas/tests/io/parser/conftest.py | conftest | 18 | 6 | No |
| venv-python312-test/lib/python3.14/site-packages/pandas/tests/io/pytables/conftest.py | conftest | 1 | 0 | No |
| venv-python312-test/lib/python3.14/site-packages/pandas/tests/io/xml/conftest.py | conftest | 7 | 0 | No |
| venv-python312-test/lib/python3.14/site-packages/pandas/tests/io/json/conftest.py | conftest | 1 | 0 | No |
| tests/e2e/conftest.py | conftest | 44 | 1 | Yes |
| tests/sdk_python/conftest.py | conftest | 9 | 1 | Yes |
| .venv/lib/python3.12/site-packages/numpy/conftest.py | conftest | 13 | 0 | No |
| .venv/lib/python3.12/site-packages/pyarrow/conftest.py | conftest | 9 | 0 | No |
| .venv/lib/python3.12/site-packages/pandas/conftest.py | conftest | 118 | 2 | No |
| .venv/lib/python3.12/site-packages/pandas/tests/util/conftest.py | conftest | 5 | 0 | No |
| .venv/lib/python3.12/site-packages/pandas/tests/io/conftest.py | conftest | 15 | 0 | No |
| .venv/lib/python3.12/site-packages/pandas/tests/strings/conftest.py | conftest | 1 | 0 | No |
| .venv/lib/python3.12/site-packages/pandas/tests/plotting/conftest.py | conftest | 2 | 0 | No |
| .venv/lib/python3.12/site-packages/pandas/tests/resample/conftest.py | conftest | 14 | 0 | No |
| .venv/lib/python3.12/site-packages/pandas/tests/arithmetic/conftest.py | conftest | 6 | 0 | No |
| .venv/lib/python3.12/site-packages/pandas/tests/groupby/conftest.py | conftest | 17 | 0 | No |
| .venv/lib/python3.12/site-packages/pandas/tests/frame/conftest.py | conftest | 5 | 0 | No |
| .venv/lib/python3.12/site-packages/pandas/tests/indexing/conftest.py | conftest | 16 | 0 | No |
| .venv/lib/python3.12/site-packages/pandas/tests/window/conftest.py | conftest | 16 | 0 | No |
| .venv/lib/python3.12/site-packages/pandas/tests/indexes/conftest.py | conftest | 3 | 0 | No |
| .venv/lib/python3.12/site-packages/pandas/tests/extension/conftest.py | conftest | 21 | 0 | No |
| .venv/lib/python3.12/site-packages/pandas/tests/reshape/concat/conftest.py | conftest | 1 | 0 | No |
| .venv/lib/python3.12/site-packages/pandas/tests/indexes/multi/conftest.py | conftest | 1 | 0 | No |
| .venv/lib/python3.12/site-packages/pandas/tests/arrays/integer/conftest.py | conftest | 4 | 0 | No |
| .venv/lib/python3.12/site-packages/pandas/tests/arrays/floating/conftest.py | conftest | 4 | 0 | No |
| .venv/lib/python3.12/site-packages/pandas/tests/window/moments/conftest.py | conftest | 7 | 0 | No |
| .venv/lib/python3.12/site-packages/pandas/tests/io/parser/conftest.py | conftest | 18 | 6 | No |
| .venv/lib/python3.12/site-packages/pandas/tests/io/pytables/conftest.py | conftest | 1 | 0 | No |
| .venv/lib/python3.12/site-packages/pandas/tests/io/xml/conftest.py | conftest | 7 | 0 | No |
| .venv/lib/python3.12/site-packages/pandas/tests/io/json/conftest.py | conftest | 1 | 0 | No |
| .venv/lib/python3.12/site-packages/pyarrow/tests/conftest.py | conftest | 22 | 1 | No |
| .venv/lib/python3.12/site-packages/pyarrow/tests/parquet/conftest.py | conftest | 5 | 0 | No |
| cli/tests/conftest.py | conftest | 8 | 0 | No |
| cli/build/lib/tests/conftest.py | conftest | 8 | 0 | No |
| tests/performance/helpers.py | helper | 6 | 1 | No |
| tests/performance/test_performance_baseline.py | helper | 18 | 5 | Yes |
| tests/integration/test_database_operations_comprehensive.py | helper | 23 | 6 | No |
| tests/regression/test_database_operations.py | helper | 16 | 7 | No |

## Helper Functions

| Name | File | Line | Type |
|------|------|------|------|
| create_user | tests/factories.py | 32 | function |
| create_tenant | tests/factories.py | 72 | function |
| create_tenant_config | tests/factories.py | 121 | function |
| create_tenant_config_with_all_fields | tests/factories.py | 196 | function |
| create_email_delivery | tests/factories.py | 209 | function |
| create_email_delivery_with_all_statuses | tests/factories.py | 271 | function |
| create_email_delivery_with_all_types | tests/factories.py | 289 | function |
| create_job | tests/factories.py | 311 | function |
| create_job_with_all_types | tests/factories.py | 383 | function |
| create_job_with_all_statuses | tests/factories.py | 408 | function |
| create_test_tenant_and_user | tests/validate_odps_integration_guide.py | 116 | function |
| _log_patch | tests/conftest.py | 19 | function |
| _ensure_sync_apps_patched | tests/conftest.py | 30 | function |
| _get_test_env_validator | tests/conftest.py | 843 | function |
| _get_validate_test_env | tests/conftest.py | 848 | function |
| _get_user_model | tests/conftest.py | 855 | function |
| _get_client | tests/conftest.py | 862 | function |
| _get_transaction_test_case | tests/conftest.py | 869 | function |
| _get_settings | tests/conftest.py | 876 | function |
| pytest_configure | tests/conftest.py | 889 | function |
| pytest_sessionstart | tests/conftest.py | 1164 | function |
| django_db_setup_with_migrations | tests/conftest.py | 1290 | fixture |
| api_client | tests/conftest.py | 1307 | fixture |
| test_user | tests/conftest.py | 1314 | fixture |
| authenticated_client | tests/conftest.py | 1323 | fixture |
| _validate_test_environment_config | tests/conftest.py | 1329 | function |
| _validate_service_connectivity | tests/conftest.py | 1381 | function |
| wait_for_service_health | tests/conftest.py | 1416 | function |
| datacontract_service | tests/conftest.py | 1465 | fixture |
| dq_service | tests/conftest.py | 1481 | fixture |
| compliance_service | tests/conftest.py | 1496 | fixture |
| semantic_service | tests/conftest.py | 1512 | fixture |
| all_services | tests/conftest.py | 1527 | fixture |
| check_service_health | tests/conftest.py | 1537 | function |
| test_env_validator | tests/conftest.py | 1556 | fixture |
| validate_test_env | tests/conftest.py | 1566 | fixture |
| validate_database_connectivity | tests/conftest.py | 1587 | fixture |
| validate_redis_connectivity | tests/conftest.py | 1599 | fixture |
| validate_service_connectivity | tests/conftest.py | 1611 | fixture |
| _patched_sync_apps | tests/conftest.py | 42 | function |
| _noop_validate | tests/conftest.py | 149 | function |
| _patched_table_names | tests/conftest.py | 231 | function |
| _patched_call_command | tests/conftest.py | 606 | function |
| _patched_create_test_db | tests/conftest.py | 659 | function |
| _patched_setup_databases | tests/conftest.py | 1043 | function |
| _patched_loader_init | tests/conftest.py | 182 | function |
| _patched_sql_flush | tests/conftest.py | 326 | function |
| _patched_sync_apps | tests/conftest.py | 360 | function |
| _patched_handle | tests/conftest.py | 405 | function |
| _local_patched_call_command | tests/conftest.py | 693 | function |

... and 2025 more helper functions

## Endpoint URLs in Utilities

| Endpoint | File | Line | Function |
|----------|------|------|---------|
| /api/v1/assets/assets/ | tests/e2e/conftest.py | 435 | create_asset |
| /api/v1/assets/assets/ | tests/e2e/conftest.py | 435 | create_asset |
| /api/v1/contracts/contracts/ | tests/e2e/conftest.py | 482 | create_contract |
| /api/v1/contracts/contracts/ | tests/e2e/conftest.py | 482 | create_contract |
| /api/v1/files/files/init/ | tests/e2e/conftest.py | 517 | init_file_upload |
| /api/v1/files/files/init/ | tests/e2e/conftest.py | 517 | init_file_upload |
| /api/v1/files/files/{file_id}/complete/ | tests/e2e/conftest.py | 652 | complete_file_upload |
| /api/v1/files/files/{file_id}/complete/ | tests/e2e/conftest.py | 652 | complete_file_upload |
| /api/v1/files/files/{file_id}/complete/ | tests/e2e/conftest.py | 652 | complete_file_upload |
| /api/v1/datasets/datasets/ | tests/e2e/conftest.py | 667 | create_dataset |
| /api/v1/datasets/datasets/ | tests/e2e/conftest.py | 667 | create_dataset |
| /api/v1/assets/assets/{asset_id}/activate/ | tests/e2e/conftest.py | 849 | activate_asset |
| /api/v1/assets/assets/{asset_id}/activate/ | tests/e2e/conftest.py | 849 | activate_asset |
| /api/v1/assets/assets/{asset_id}/activate/ | tests/e2e/conftest.py | 849 | activate_asset |
| /api/v1/contracts/contracts/{contract_id}/validate/ | tests/e2e/conftest.py | 944 | validate_contract |
| /api/v1/contracts/contracts/{contract_id}/validate/ | tests/e2e/conftest.py | 944 | validate_contract |
| /api/v1/contracts/contracts/{contract_id}/validate/ | tests/e2e/conftest.py | 944 | validate_contract |
| /api/v1/compliance/compliance-runs/ | tests/e2e/conftest.py | 972 | run_compliance_check |
| /api/v1/compliance/compliance-runs/ | tests/e2e/conftest.py | 972 | run_compliance_check |
| /api/v1/dq/dq-runs/ | tests/e2e/conftest.py | 994 | run_dq_check |
| /api/v1/dq/dq-runs/ | tests/e2e/conftest.py | 994 | run_dq_check |
| /api/v1/assets/assets/{asset_id}/ | tests/e2e/conftest.py | 1052 | attach_contract_to_asset |
| /api/v1/assets/assets/{asset_id}/ | tests/e2e/conftest.py | 1052 | attach_contract_to_asset |
| /api/v1/assets/assets/{asset_id}/ | tests/e2e/conftest.py | 1052 | attach_contract_to_asset |
| /api/v1/auth/login/ | tests/sdk_python/conftest.py | 354 | N/A |
| /api/v1/contracts/ | tests/performance/test_performance_baseline.py | 220 | test_contract_list_endpoint_baseline |
| /api/v1/contracts/ | tests/performance/test_performance_baseline.py | 220 | test_contract_list_endpoint_baseline |
| /api/v1/contracts/ | tests/performance/test_performance_baseline.py | 231 | test_contract_filter_endpoint_baseline |
| /api/v1/contracts/ | tests/performance/test_performance_baseline.py | 231 | test_contract_filter_endpoint_baseline |
| /api/v1/assets/ | tests/performance/test_performance_baseline.py | 246 | test_middleware_chain_baseline |
| /api/v1/assets/ | tests/performance/test_performance_baseline.py | 246 | test_middleware_chain_baseline |
| /api/v1/files/{file_id}/download | tests/performance/locust_file_upload_download.py | 103 | test_file_download |
| /api/v1/files/{file_id}/download | tests/performance/locust_file_upload_download.py | 103 | test_file_download |
| /api/v1/files/{file_id}/download | tests/performance/locust_file_upload_download.py | 103 | test_file_download |
| /api/v1/files/{id}/download | tests/performance/locust_file_upload_download.py | 105 | test_file_download |
| /api/v1/files/{id}/download | tests/performance/locust_file_upload_download.py | 105 | test_file_download |
| /api/v1/files/init | tests/performance/locust_file_upload_download.py | 155 | _upload_file |
| /api/v1/files/init | tests/performance/locust_file_upload_download.py | 155 | _upload_file |
| /api/v1/files/init | tests/performance/locust_file_upload_download.py | 158 | _upload_file |
| /api/v1/files/init | tests/performance/locust_file_upload_download.py | 158 | _upload_file |
| /api/v1/files/{file_id}/complete | tests/performance/locust_file_upload_download.py | 237 | _upload_file |
| /api/v1/files/{file_id}/complete | tests/performance/locust_file_upload_download.py | 237 | _upload_file |
| /api/v1/files/{file_id}/complete | tests/performance/locust_file_upload_download.py | 237 | _upload_file |
| /api/v1/files/{id}/complete | tests/performance/locust_file_upload_download.py | 240 | _upload_file |
| /api/v1/files/{id}/complete | tests/performance/locust_file_upload_download.py | 240 | _upload_file |
| /api/v1/assets/assets/ | tests/e2e/conftest.py | 435 | create_asset |
| /api/v1/assets/assets/ | tests/e2e/conftest.py | 435 | create_asset |
| /api/v1/contracts/contracts/ | tests/e2e/conftest.py | 482 | create_contract |
| /api/v1/contracts/contracts/ | tests/e2e/conftest.py | 482 | create_contract |
| /api/v1/files/files/init/ | tests/e2e/conftest.py | 517 | init_file_upload |

... and 42 more endpoint URLs