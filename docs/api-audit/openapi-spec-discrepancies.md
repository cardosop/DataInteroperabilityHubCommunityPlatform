# OpenAPI Spec Reference Check

## Summary

- OpenAPI Paths: 251
- Actual Endpoints: 517
- Discrepancies: 626

### Discrepancy Breakdown

- **missing_in_urls**: 132
- **method_mismatch**: 104
- **missing_in_spec**: 390

## Discrepancies

### Method Mismatch

- **OpenAPI**: /api/v1
  - **Actual**: /api/v1
  - **OpenAPI Methods**: GET
  - **Actual Methods**: PUT, DELETE, GET, PATCH, POST, HEAD, TRACE
  - **Details**: Methods differ: OpenAPI has {'GET'}, actual has {'PUT', 'DELETE', 'GET', 'PATCH', 'POST', 'HEAD', 'TRACE'}

- **OpenAPI**: /api/v1/ai/ai/natural-language-search
  - **Actual**: /api/v1/ai/ai/natural-language-search/
  - **OpenAPI Methods**: POST
  - **Actual Methods**: post
  - **Details**: Methods differ: OpenAPI has {'POST'}, actual has {'post'}

- **OpenAPI**: /api/v1/ai/ai/schema-matching
  - **Actual**: /api/v1/ai/ai/schema-matching/
  - **OpenAPI Methods**: POST
  - **Actual Methods**: post
  - **Details**: Methods differ: OpenAPI has {'POST'}, actual has {'post'}

- **OpenAPI**: /api/v1/analytics/api/dashboard
  - **Actual**: /api/v1/analytics/api/dashboard/
  - **OpenAPI Methods**: GET
  - **Actual Methods**: get
  - **Details**: Methods differ: OpenAPI has {'GET'}, actual has {'get'}

- **OpenAPI**: /api/v1/analytics/api/performance
  - **Actual**: /api/v1/analytics/api/performance/
  - **OpenAPI Methods**: GET
  - **Actual Methods**: get
  - **Details**: Methods differ: OpenAPI has {'GET'}, actual has {'get'}

- **OpenAPI**: /api/v1/analytics/api/popular-endpoints
  - **Actual**: /api/v1/analytics/api/popular-endpoints/
  - **OpenAPI Methods**: GET
  - **Actual Methods**: get
  - **Details**: Methods differ: OpenAPI has {'GET'}, actual has {'get'}

- **OpenAPI**: /api/v1/analytics/api/usage-trends
  - **Actual**: /api/v1/analytics/api/usage-trends/
  - **OpenAPI Methods**: GET
  - **Actual Methods**: get
  - **Details**: Methods differ: OpenAPI has {'GET'}, actual has {'get'}

- **OpenAPI**: /api/v1/assets/assets
  - **Actual**: /api/v1/assets/assets/
  - **OpenAPI Methods**: GET, POST
  - **Actual Methods**: get, post
  - **Details**: Methods differ: OpenAPI has {'GET', 'POST'}, actual has {'get', 'post'}

- **OpenAPI**: /api/v1/assets/assets/recommendations
  - **Actual**: /api/v1/assets/assets/recommendations/
  - **OpenAPI Methods**: GET
  - **Actual Methods**: get
  - **Details**: Methods differ: OpenAPI has {'GET'}, actual has {'get'}

- **OpenAPI**: /api/v1/audit/audit-events
  - **Actual**: /api/v1/audit/audit-events/
  - **OpenAPI Methods**: GET
  - **Actual Methods**: get
  - **Details**: Methods differ: OpenAPI has {'GET'}, actual has {'get'}

- **OpenAPI**: /api/v1/audit/audit-events/export
  - **Actual**: /api/v1/audit/audit-events/export/
  - **OpenAPI Methods**: GET
  - **Actual Methods**: get
  - **Details**: Methods differ: OpenAPI has {'GET'}, actual has {'get'}

- **OpenAPI**: /api/v1/auth/api-keys
  - **Actual**: /api/v1/auth/api-keys/
  - **OpenAPI Methods**: GET, POST
  - **Actual Methods**: get, post
  - **Details**: Methods differ: OpenAPI has {'GET', 'POST'}, actual has {'get', 'post'}

- **OpenAPI**: /api/v1/auth/sso/oidc/callback
  - **Actual**: /api/v1/auth/sso/oidc/callback/
  - **OpenAPI Methods**: POST
  - **Actual Methods**: post
  - **Details**: Methods differ: OpenAPI has {'POST'}, actual has {'post'}

- **OpenAPI**: /api/v1/auth/sso/oidc/login-url
  - **Actual**: /api/v1/auth/sso/oidc/login-url/
  - **OpenAPI Methods**: GET
  - **Actual Methods**: get
  - **Details**: Methods differ: OpenAPI has {'GET'}, actual has {'get'}

- **OpenAPI**: /api/v1/auth/sso/saml/callback
  - **Actual**: /api/v1/auth/sso/saml/callback/
  - **OpenAPI Methods**: POST
  - **Actual Methods**: post
  - **Details**: Methods differ: OpenAPI has {'POST'}, actual has {'post'}

- **OpenAPI**: /api/v1/auth/sso/saml/login-url
  - **Actual**: /api/v1/auth/sso/saml/login-url/
  - **OpenAPI Methods**: GET
  - **Actual Methods**: get
  - **Details**: Methods differ: OpenAPI has {'GET'}, actual has {'get'}

- **OpenAPI**: /api/v1/compliance/compliance-runs
  - **Actual**: /api/v1/compliance/compliance-runs/
  - **OpenAPI Methods**: GET, POST
  - **Actual Methods**: get, post
  - **Details**: Methods differ: OpenAPI has {'GET', 'POST'}, actual has {'get', 'post'}

- **OpenAPI**: /api/v1/compliance/runs
  - **Actual**: /api/v1/compliance/runs
  - **OpenAPI Methods**: GET, POST
  - **Actual Methods**: get, post
  - **Details**: Methods differ: OpenAPI has {'GET', 'POST'}, actual has {'get', 'post'}

- **OpenAPI**: /api/v1/compliance/runs/{id}
  - **Actual**: /api/v1/compliance/runs/<{uuid:id}>
  - **OpenAPI Methods**: GET
  - **Actual Methods**: get
  - **Details**: Methods differ: OpenAPI has {'GET'}, actual has {'get'}

- **OpenAPI**: /api/v1/contracts
  - **Actual**: /api/v1/contracts/
  - **OpenAPI Methods**: GET, POST
  - **Actual Methods**: get, post
  - **Details**: Methods differ: OpenAPI has {'GET', 'POST'}, actual has {'get', 'post'}

- **OpenAPI**: /api/v1/contracts/{id}
  - **Actual**: /api/v1/contracts/<{drf_format_suffix:format}>
  - **OpenAPI Methods**: DELETE, GET, PATCH, PUT
  - **Actual Methods**: PUT, DELETE, GET, PATCH, POST, HEAD, TRACE
  - **Details**: Methods differ: OpenAPI has {'DELETE', 'GET', 'PATCH', 'PUT'}, actual has {'PUT', 'DELETE', 'GET', 'PATCH', 'POST', 'HEAD', 'TRACE'}

- **OpenAPI**: /api/v1/contracts/products
  - **Actual**: /api/v1/contracts/products/
  - **OpenAPI Methods**: POST
  - **Actual Methods**: post
  - **Details**: Methods differ: OpenAPI has {'POST'}, actual has {'post'}

- **OpenAPI**: /api/v1/datasets/datasets
  - **Actual**: /api/v1/datasets/datasets/
  - **OpenAPI Methods**: GET, POST
  - **Actual Methods**: get, post
  - **Details**: Methods differ: OpenAPI has {'GET', 'POST'}, actual has {'get', 'post'}

- **OpenAPI**: /api/v1/developer/plugins
  - **Actual**: /api/v1/developer/plugins/
  - **OpenAPI Methods**: GET
  - **Actual Methods**: get
  - **Details**: Methods differ: OpenAPI has {'GET'}, actual has {'get'}

- **OpenAPI**: /api/v1/developer/sdk
  - **Actual**: /api/v1/developer/sdk/
  - **OpenAPI Methods**: GET
  - **Actual Methods**: get
  - **Details**: Methods differ: OpenAPI has {'GET'}, actual has {'get'}

- **OpenAPI**: /api/v1/dq/dq-runs
  - **Actual**: /api/v1/dq/dq-runs/
  - **OpenAPI Methods**: GET, POST
  - **Actual Methods**: get, post
  - **Details**: Methods differ: OpenAPI has {'GET', 'POST'}, actual has {'get', 'post'}

- **OpenAPI**: /api/v1/dq/runs
  - **Actual**: /api/v1/dq/runs/
  - **OpenAPI Methods**: GET, POST
  - **Actual Methods**: get, post
  - **Details**: Methods differ: OpenAPI has {'GET', 'POST'}, actual has {'get', 'post'}

- **OpenAPI**: /api/v1/files/files
  - **Actual**: /api/v1/files/files/
  - **OpenAPI Methods**: GET, POST
  - **Actual Methods**: get, post
  - **Details**: Methods differ: OpenAPI has {'GET', 'POST'}, actual has {'get', 'post'}

- **OpenAPI**: /api/v1/files/files/init
  - **Actual**: /api/v1/files/files/init/
  - **OpenAPI Methods**: POST
  - **Actual Methods**: post
  - **Details**: Methods differ: OpenAPI has {'POST'}, actual has {'post'}

- **OpenAPI**: /api/v1/governance/access-requests
  - **Actual**: /api/v1/governance/access-requests/
  - **OpenAPI Methods**: GET, POST
  - **Actual Methods**: get, post
  - **Details**: Methods differ: OpenAPI has {'GET', 'POST'}, actual has {'get', 'post'}

- **OpenAPI**: /api/v1/governance/access/access-requests
  - **Actual**: /api/v1/governance/access/access-requests/
  - **OpenAPI Methods**: GET, POST
  - **Actual Methods**: get, post
  - **Details**: Methods differ: OpenAPI has {'GET', 'POST'}, actual has {'get', 'post'}

- **OpenAPI**: /api/v1/governance/access/analytics/anomalies
  - **Actual**: /api/v1/governance/access/analytics/anomalies/
  - **OpenAPI Methods**: GET
  - **Actual Methods**: get
  - **Details**: Methods differ: OpenAPI has {'GET'}, actual has {'get'}

- **OpenAPI**: /api/v1/governance/access/analytics/dashboard
  - **Actual**: /api/v1/governance/access/analytics/dashboard/
  - **OpenAPI Methods**: GET
  - **Actual Methods**: get
  - **Details**: Methods differ: OpenAPI has {'GET'}, actual has {'get'}

- **OpenAPI**: /api/v1/governance/access/analytics/patterns
  - **Actual**: /api/v1/governance/access/analytics/patterns/
  - **OpenAPI Methods**: GET
  - **Actual Methods**: get
  - **Details**: Methods differ: OpenAPI has {'GET'}, actual has {'get'}

- **OpenAPI**: /api/v1/governance/access/analytics/security-events
  - **Actual**: /api/v1/governance/access/analytics/security-events/
  - **OpenAPI Methods**: GET
  - **Actual Methods**: get
  - **Details**: Methods differ: OpenAPI has {'GET'}, actual has {'get'}

- **OpenAPI**: /api/v1/governance/access/certifications
  - **Actual**: /api/v1/governance/access/certifications/
  - **OpenAPI Methods**: GET, POST
  - **Actual Methods**: get, post
  - **Details**: Methods differ: OpenAPI has {'GET', 'POST'}, actual has {'get', 'post'}

- **OpenAPI**: /api/v1/governance/access/certifications/expiring
  - **Actual**: /api/v1/governance/access/certifications/expiring/
  - **OpenAPI Methods**: GET
  - **Actual Methods**: get
  - **Details**: Methods differ: OpenAPI has {'GET'}, actual has {'get'}

- **OpenAPI**: /api/v1/governance/access/certifications/initiate-review
  - **Actual**: /api/v1/governance/access/certifications/initiate-review/
  - **OpenAPI Methods**: POST
  - **Actual Methods**: post
  - **Details**: Methods differ: OpenAPI has {'POST'}, actual has {'post'}

- **OpenAPI**: /api/v1/governance/access/certifications/summary
  - **Actual**: /api/v1/governance/access/certifications/summary/
  - **OpenAPI Methods**: GET
  - **Actual Methods**: get
  - **Details**: Methods differ: OpenAPI has {'GET'}, actual has {'get'}

- **OpenAPI**: /api/v1/governance/access/retention-policies
  - **Actual**: /api/v1/governance/access/retention-policies/
  - **OpenAPI Methods**: GET, POST
  - **Actual Methods**: get, post
  - **Details**: Methods differ: OpenAPI has {'GET', 'POST'}, actual has {'get', 'post'}

- **OpenAPI**: /api/v1/governance/analytics/anomalies
  - **Actual**: /api/v1/governance/analytics/anomalies/
  - **OpenAPI Methods**: GET
  - **Actual Methods**: get
  - **Details**: Methods differ: OpenAPI has {'GET'}, actual has {'get'}

- **OpenAPI**: /api/v1/governance/analytics/dashboard
  - **Actual**: /api/v1/governance/analytics/dashboard/
  - **OpenAPI Methods**: GET
  - **Actual Methods**: get
  - **Details**: Methods differ: OpenAPI has {'GET'}, actual has {'get'}

- **OpenAPI**: /api/v1/governance/analytics/patterns
  - **Actual**: /api/v1/governance/analytics/patterns/
  - **OpenAPI Methods**: GET
  - **Actual Methods**: get
  - **Details**: Methods differ: OpenAPI has {'GET'}, actual has {'get'}

- **OpenAPI**: /api/v1/governance/analytics/security-events
  - **Actual**: /api/v1/governance/analytics/security-events/
  - **OpenAPI Methods**: GET
  - **Actual Methods**: get
  - **Details**: Methods differ: OpenAPI has {'GET'}, actual has {'get'}

- **OpenAPI**: /api/v1/governance/certifications
  - **Actual**: /api/v1/governance/certifications/
  - **OpenAPI Methods**: GET, POST
  - **Actual Methods**: get, post
  - **Details**: Methods differ: OpenAPI has {'GET', 'POST'}, actual has {'get', 'post'}

- **OpenAPI**: /api/v1/governance/certifications/expiring
  - **Actual**: /api/v1/governance/certifications/expiring/
  - **OpenAPI Methods**: GET
  - **Actual Methods**: get
  - **Details**: Methods differ: OpenAPI has {'GET'}, actual has {'get'}

- **OpenAPI**: /api/v1/governance/certifications/initiate-review
  - **Actual**: /api/v1/governance/certifications/initiate-review/
  - **OpenAPI Methods**: POST
  - **Actual Methods**: post
  - **Details**: Methods differ: OpenAPI has {'POST'}, actual has {'post'}

- **OpenAPI**: /api/v1/governance/certifications/summary
  - **Actual**: /api/v1/governance/certifications/summary/
  - **OpenAPI Methods**: GET
  - **Actual Methods**: get
  - **Details**: Methods differ: OpenAPI has {'GET'}, actual has {'get'}

- **OpenAPI**: /api/v1/governance/retention-policies
  - **Actual**: /api/v1/governance/retention-policies/
  - **OpenAPI Methods**: GET, POST
  - **Actual Methods**: get, post
  - **Details**: Methods differ: OpenAPI has {'GET', 'POST'}, actual has {'get', 'post'}

- **OpenAPI**: /api/v1/jobs/jobs
  - **Actual**: /api/v1/jobs/jobs/
  - **OpenAPI Methods**: GET, POST
  - **Actual Methods**: get, post
  - **Details**: Methods differ: OpenAPI has {'GET', 'POST'}, actual has {'get', 'post'}

- ... and 54 more discrepancies

### Missing In Spec

- **OpenAPI**: None
  - **Actual**: /api/v1/auth/api-keys\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: get, post
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/auth/api-keys/(?P<{id}>[/.]+)/
  - **Actual Methods**: put, get, patch, delete
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/auth/api-keys/(?P<{id}>[/.]+)\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: put, get, patch, delete
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/auth/sso/oidc/callback\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: post
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/auth/sso/oidc/login-url\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: get
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/auth/sso/saml/callback\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: post
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/auth/sso/saml/login-url\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: get
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/auth
  - **Actual Methods**: PUT, DELETE, GET, PATCH, POST, HEAD, TRACE
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/auth/<{drf_format_suffix:format}>
  - **Actual Methods**: PUT, DELETE, GET, PATCH, POST, HEAD, TRACE
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/tenants/tenants\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: get, post
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/tenants/tenants/(?P<{id}>[/.]+)/
  - **Actual Methods**: put, get, patch, delete
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/tenants/tenants/(?P<{id}>[/.]+)\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: put, get, patch, delete
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/tenants/tenants/(?P<{id}>[/.]+)/reactivate/
  - **Actual Methods**: post
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/tenants/tenants/(?P<{id}>[/.]+)/reactivate\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: post
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/tenants/tenants/(?P<{id}>[/.]+)/suspend/
  - **Actual Methods**: post
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/tenants/tenants/(?P<{id}>[/.]+)/suspend\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: post
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/tenants
  - **Actual Methods**: PUT, DELETE, GET, PATCH, POST, HEAD, TRACE
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/tenants/<{drf_format_suffix:format}>
  - **Actual Methods**: PUT, DELETE, GET, PATCH, POST, HEAD, TRACE
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/users/users\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: get, post
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/users/users/invite\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: post
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/users/users/(?P<{id}>[/.]+)/
  - **Actual Methods**: put, get, patch, delete
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/users/users/(?P<{id}>[/.]+)\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: put, get, patch, delete
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/users/users/(?P<{id}>[/.]+)/roles/
  - **Actual Methods**: post
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/users/users/(?P<{id}>[/.]+)/roles\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: post
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/users/roles\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: get
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/users/roles/(?P<{id}>[/.]+)/
  - **Actual Methods**: get
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/users/roles/(?P<{id}>[/.]+)\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: get
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/users
  - **Actual Methods**: PUT, DELETE, GET, PATCH, POST, HEAD, TRACE
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/users/<{drf_format_suffix:format}>
  - **Actual Methods**: PUT, DELETE, GET, PATCH, POST, HEAD, TRACE
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/audit/audit-events\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: get
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/audit/audit-events/export\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: get
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/audit/audit-events/(?P<{id}>[/.]+)/
  - **Actual Methods**: get
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/audit/audit-events/(?P<{id}>[/.]+)\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: get
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/audit
  - **Actual Methods**: PUT, DELETE, GET, PATCH, POST, HEAD, TRACE
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/audit/<{drf_format_suffix:format}>
  - **Actual Methods**: PUT, DELETE, GET, PATCH, POST, HEAD, TRACE
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/files/files\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: get, post
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/files/files/init\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: post
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/files/files/(?P<{id}>[/.]+)/
  - **Actual Methods**: put, get, patch, delete
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/files/files/(?P<{id}>[/.]+)\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: put, get, patch, delete
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/files/files/(?P<{id}>[/.]+)/complete/
  - **Actual Methods**: post
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/files/files/(?P<{id}>[/.]+)/complete\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: post
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/files/files/(?P<{id}>[/.]+)/download/
  - **Actual Methods**: get
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/files/files/(?P<{id}>[/.]+)/download\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: get
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/files/files/(?P<{id}>[/.]+)/chunks/init/
  - **Actual Methods**: post
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/files/files/(?P<{id}>[/.]+)/chunks/init\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: post
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/files
  - **Actual Methods**: PUT, DELETE, GET, PATCH, POST, HEAD, TRACE
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/files/<{drf_format_suffix:format}>
  - **Actual Methods**: PUT, DELETE, GET, PATCH, POST, HEAD, TRACE
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/datasets/datasets\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: get, post
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/datasets/datasets/(?P<{id}>[/.]+)/
  - **Actual Methods**: put, get, patch, delete
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- **OpenAPI**: None
  - **Actual**: /api/v1/datasets/datasets/(?P<{id}>[/.]+)\.(?P<{format}>[a-z0-9]+)/?
  - **Actual Methods**: put, get, patch, delete
  - **Details**: Path in actual URLs but not found in OpenAPI spec

- ... and 340 more discrepancies

### Missing In Urls

- **OpenAPI**: /api-docs
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api-docs/openapi.json
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/assets/assets/{id}
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/assets/assets/{id}/activate
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/assets/assets/{id}/contracts
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/assets/assets/{id}/datasets
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/assets/assets/{id}/dependencies
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/assets/assets/{id}/health-score
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/assets/assets/{id}/track-download
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/assets/assets/{id}/track-view
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/audit/audit-events/{id}
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/auth/api-keys/{id}
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/compliance/compliance-runs/{id}
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/compliance/compliance-runs/{id}/results
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/contracts/{id}/convert
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/contracts/{id}/download
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/contracts/{id}/export
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/contracts/{id}/fields/{field_name}/lineage
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/contracts/{id}/generate-odps
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/contracts/{id}/impact-analysis
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/contracts/{id}/lineage/contracts
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/contracts/{id}/lineage/full
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/contracts/{id}/lineage/visualization
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/contracts/{id}/link-odps
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/contracts/{id}/links
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/contracts/{id}/lint
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/contracts/{id}/migrate
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/contracts/{id}/models/{model_name}/lineage
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/contracts/{id}/payment-gateways
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/contracts/{id}/product-details
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/contracts/{id}/product-strategy
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/contracts/{id}/unlink-odps
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/contracts/{id}/validate
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/datasets/datasets/{id}
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/datasets/datasets/{id}/versions
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/datasets/datasets/{id}/versions/compare
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/developer/plugins/{id}
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/developer/sdk/{id}
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/dq/dq-runs/{id}
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/dq/dq-runs/{id}/results
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/dq/runs/{id}
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/dq/runs/{id}/results
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/files/files/{id}
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/files/files/{id}/chunks/init
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/files/files/{id}/complete
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/files/files/{id}/download
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/governance/access-requests/{id}
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/governance/access-requests/{id}/approve
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/governance/access-requests/{id}/reject
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- **OpenAPI**: /api/v1/governance/access/access-requests/{id}
  - **Details**: Path in OpenAPI spec but not found in actual URL patterns

- ... and 82 more discrepancies
