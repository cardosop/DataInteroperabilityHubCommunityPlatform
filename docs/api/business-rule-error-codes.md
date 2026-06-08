# Business Rule Error Codes — Phase 274

| Code | HTTP | Rule | Description |
|---|---|---|---|
| `COMPLIANCE_THRESHOLD_EXCEEDED` | 422 | BR1 | Asset risk_level exceeds tenant threshold |
| `COMPLIANCE_RUN_REQUIRED` | 422 | BR1 | No SUCCEEDED ComplianceRun for asset |
| `COMPLIANCE_SCAN_PENDING` | 409 | BR4 | Compliance scan in progress; Retry-After: 30s |
| `COMPLIANCE_SCAN_FAILED` | 422 | BR4 | Compliance scan completed with failure |
| `COMPLIANCE_NOT_ALLOWED_TO_STORE` | 422 | BR4 | allowed_to_store=False |
| `SEMANTIC_FEATURE_DISABLED` | 403 | BR3 | Tenant flag off for requested action |
| `CONTRACT_STRUCTURELESS_REJECTED` | 422 | BR2 | Contract fails structural floor |
| `ABAC_POLICY_DENIED` | 403 | BR5 | ABAC evaluation returned DENY |
| `NOT_COMMUNITY_MEMBER` | 403 | BR10 | User not a member of target community |
| `UPDATE_TOO_LONG` | 422 | BR10 | Social update exceeds length limit |
| `POST_RATE_LIMITED` | 429 | BR10 | User exceeded social post rate limit |
| `RECIPIENT_INVALID` | 400 | BR9 | Notification recipient inactive or not found |
| `TENANT_MISMATCH` | 400 | BR9 | Cross-tenant notification blocked |
| `TEMPLATE_NOT_FOUND` | 400 | BR9 | Notification template not found |
| `RECIPIENT_RATE_LIMITED` | 429 | BR9 | Recipient notification rate limit hit |
| `SPARQL_SYNTAX_ERROR` | 400 | BR8 | SPARQL query parse failure |
| `SPARQL_SERVICE_URL_NOT_ALLOWED` | 403 | BR8 | Federation SERVICE URL not in allowlist |
| `SPARQL_QUERY_TOO_COMPLEX` | 422 | BR8 | Query parse-tree depth exceeds limit |
| `QUERY_TOO_LONG` | 413 | BR8 | Search/SPARQL query exceeds length limit |
| `COMPENSATION_INCOMPLETE` | 500 | BR15 | Workflow compensation did not complete |
| `CHAIN_EXECUTION_FAILED` | 500 | BR13 | RuleChain execution failed |
