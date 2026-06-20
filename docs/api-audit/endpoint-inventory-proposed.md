# API Endpoint Inventory (Proposed Fixes)

Generated: 2026-06-13T19:42:09.598431

## Summary

- Total Endpoints: 1247
- Duplicates to Fix: 487
- Naming Issues to Fix: 49

## Duplicate Endpoints

- **/api/v1**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **/api/v1/contracts/^(?P<id>[^/.]+)/lineage/visualization/$**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **/api/v1/contracts/^(?P<id>[^/.]+)/export/$**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **/api/v1/contracts/^(?P<id>[^/.]+)/download/$**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **/api/v1/dq**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **/api/v1/dq/<drf_format_suffix:format>**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **/api/v1/marketplace/^listings/(?P<id>[^/.]+)/download/$**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **/api/v1/ml/inference**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **/api/v1/ml/inference/<drf_format_suffix:format>**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **/api/v1/billing**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **/api/v1/billing/<drf_format_suffix:format>**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **api-key-list**: 4 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **api-key-detail**: 4 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **sso-oidc-callback**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **sso-oidc-login-url**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **sso-saml-callback**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **sso-saml-login-url**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **api-root**: 102 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **tenant-config-detail**: 3 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **tenant-list**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **tenant-detail**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **tenant-reactivate**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **tenant-suspend**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **tenant-config-me-config**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **tenant-config-me-feature-flag-history**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **tenant-config-me-feature-flags**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **tenant-config-me-tax-id**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **tenant-config-onboarding**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **tenant-config-seed-sample**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **tenant-config-usage**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate

## Naming Inconsistencies

- **v1**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **auth**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **admin**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **tenants**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **users**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **audit**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **files**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **datasets**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **jobs**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **contracts**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **security**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **assets**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **dq**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **compliance**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **ropa**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **dpia**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **semantic**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **marketplace**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **scheduled-ingestions**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **scheduled-exports**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
