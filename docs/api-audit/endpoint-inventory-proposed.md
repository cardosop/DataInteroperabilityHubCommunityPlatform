# API Endpoint Inventory (Proposed Fixes)

Generated: 2025-12-28T12:48:38.878404

## Summary

- Total Endpoints: 517
- Duplicates to Fix: 209
- Naming Issues to Fix: 25

## Duplicate Endpoints

- **/api/v1**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **/api/v1/dq**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **/api/v1/dq/<drf_format_suffix:format>**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **/api/v1/marketplace/^listings/(?P<id>[^/.]+)/download/$**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **/api/v1/^observability/incidents/$**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **/api/v1/^observability/incidents\.(?P<format>[a-z0-9]+)/?$**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **api-key-list**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **api-key-detail**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **sso-oidc-callback**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **sso-oidc-login-url**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **sso-saml-callback**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **sso-saml-login-url**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **api-root**: 54 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **tenant-list**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **tenant-detail**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **tenant-reactivate**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **tenant-suspend**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **user-list**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **user-invite**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **user-detail**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **user-manage-roles**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **role-list**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **role-detail**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **audit-event-list**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **audit-event-export**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **audit-event-detail**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **file-list**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **file-init-upload**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **file-detail**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate
- **file-complete-upload**: 2 occurrences
  - Recommendation: Remove duplicate definitions or consolidate

## Naming Inconsistencies

- **v1**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **auth**: inconsistent_name_prefix
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
- **assets**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **dq**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **compliance**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **semantic**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **marketplace**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **scheduled-ingestions**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **search**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **developer**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **webhooks**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **access**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
- **governance**: inconsistent_name_prefix
  - Recommendation: Standardize naming pattern within service
