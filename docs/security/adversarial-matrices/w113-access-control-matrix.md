# W11.3 — ASVS V4 Access-Control Regression Matrix

Generated: 2026-10-16T20:15:05.962863+00:00 — from the live URL resolver (the runtime API
inventory; reconciled against `docs/api-audit/current-api-inventory.md`, the
`categorize-api-inventory.py` source, by the generator command).  The single
source of truth is `docs/api-audit/idor-probe-manifest.json` — the probe suite
and the coverage gate both consume it.

## Scope rule

A *tenant-scoped route* is a runtime-resolved route whose view's model has a
`tenant` FK to `tenants.Tenant` AND whose effective permission surface is not
platform-admin-gated.  Platform admins cross tenants by design; those routes
are excluded from the denominator (pinned by `tests/security/test_admin_user_edit_security.py`
and `tests/security/test_privilege_escalation.py`).

## Coverage

- Tenant-scoped route keys: **588**
- Probed (strict cross-tenant contract): **586**
- Allowlisted with written reasons: **2**
- Coverage: **99.66%** (threshold 95.0%)
- Excluded from the denominator: 20 platform-admin,
  63 no-tenant-FK, 257 unresolved
  (function views / GraphQL / SSE — each cited to its owning suite in the dispositions below).

## Strict probe contract (per probe type)

- `object` — cross-tenant retrieve/update/partial_update/destroy by tenant B on tenant
  A's id → **404** (never 403 — an existence leak); own-tenant positive control → 200;
  unauthenticated → 401.
- `list` — tenant B's list → 200 carrying B's own row, never A's.
- `create` — tenant B's POST lands the row in B's tenant (row 8: scopes/roles are not
  decoration); where the write serializer exposes tenant-scoped FK fields, B's POST
  referencing A's ids → **404** (payload-FK probe).
- `payload_fk` — the 404 direction only (service-triggering creates skip the create
  probe — the 404 fires before execution).
- `bulk` — B's bulk action carrying A's ids → **404**.
- `self_route` — B's /me/ mutation is confined to B's tenant (A's row unchanged).
- `nested_list` — B listing via A's parent id → **404**.

All probes run with real auth against the real DB with RLS request-path arming —
no mocks.

## Dispositions

### probe (586)

| Method | Path | View | Model | Type | Synthesis | Role |
|---|---|---|---|---|---|---|
| DELETE | `/api/v1/assets/{id}/` | AssetViewSet | assets.Asset | object | creator:_create_active_asset | - |
| DELETE | `/api/v1/audit/event-retention-policies/{id}/` | AuditEventRetentionPolicyViewSet | audit.AuditEventRetentionPolicy | object | generic | - |
| DELETE | `/api/v1/auth/api-keys/{id}/` | APIKeyViewSet | hub_auth.APIKey | object | generic | - |
| DELETE | `/api/v1/baas/api-keys/{id}/` | APIKeyViewSet | hub_auth.APIKey | object | generic | - |
| DELETE | `/api/v1/breach/template-overrides/{id}/` | BreachTenantTemplateOverrideViewSet | breach.BreachTenantTemplateOverride | object | generic | - |
| DELETE | `/api/v1/compliance/runs/{id}/` | ComplianceRunViewSet | compliance.ComplianceRun | object | creator:_create_compliance_run | - |
| DELETE | `/api/v1/consent/consent-purposes/{id}/` | ConsentPurposeViewSet | consent.ConsentPurpose | object | generic | - |
| DELETE | `/api/v1/contracts/{id}/` | ContractViewSet | contracts.Contract | object | generic | - |
| DELETE | `/api/v1/data-movement/config/{pk}/` | DataMovementConfigViewSet | data_movement.DataMovementConfig | object | generic | - |
| DELETE | `/api/v1/databricks/workspaces/{id}/` | WorkspaceViewSet | databricks_admin.DatabricksWorkspace | object | creator:_create_databricks_workspace | - |
| DELETE | `/api/v1/datasets/{id}/` | DatasetViewSet | datasets.Dataset | object | generic | - |
| DELETE | `/api/v1/dpia/records/{pk}/` | DpiaViewSet | dpia.Dpia | object | generic | - |
| DELETE | `/api/v1/dq/alerting-rules/{id}/` | DQAlertingRuleViewSet | dq.DQAlertingRule | object | creator:_create_dq_alerting_rule | - |
| DELETE | `/api/v1/dq/runs/{id}/` | DQRunViewSet | dq.DQRun | object | creator:_create_dq_run | - |
| DELETE | `/api/v1/files/{id}/` | FileViewSet | files.File | object | creator:_create_file | - |
| DELETE | `/api/v1/governance/access-requests/{id}/` | AccessRequestViewSet | governance.AccessRequest | object | creator:_create_access_request | - |
| DELETE | `/api/v1/governance/access/access-requests/{id}/` | AccessRequestViewSet | governance.AccessRequest | object | creator:_create_access_request | - |
| DELETE | `/api/v1/governance/access/certifications/{id}/` | AccessCertificationViewSet | governance.AccessCertification | object | generic | - |
| DELETE | `/api/v1/governance/access/delegations/{id}/` | DelegationViewSet | governance.ApprovalDelegation | object | generic | - |
| DELETE | `/api/v1/governance/access/retention-policies/{id}/` | RetentionPolicyViewSet | governance.RetentionPolicy | object | creator:_create_retention_policy | - |
| DELETE | `/api/v1/governance/certifications/{id}/` | AccessCertificationViewSet | governance.AccessCertification | object | generic | - |
| DELETE | `/api/v1/governance/delegations/{id}/` | DelegationViewSet | governance.ApprovalDelegation | object | generic | - |
| DELETE | `/api/v1/governance/retention-policies/{id}/` | RetentionPolicyViewSet | governance.RetentionPolicy | object | creator:_create_retention_policy | - |
| DELETE | `/api/v1/integrations/marketplace/connections/{id}/` | MarketplaceConnectionViewSet | integrations.MarketplaceConnection | object | generic | - |
| DELETE | `/api/v1/integrations/marketplace/mappings/{id}/` | MarketplaceMappingViewSet | integrations.MarketplaceMapping | object | generic | - |
| DELETE | `/api/v1/integrations/marketplace/sync/{id}/` | MarketplaceSyncJobViewSet | integrations.MarketplaceSyncJob | object | generic | - |
| DELETE | `/api/v1/jobs/{id}/` | JobViewSet | jobs.Job | object | generic | - |
| DELETE | `/api/v1/marketplace/config/trust-signals/{id}/` | TrustSignalConfigViewSet | marketplace.TrustSignalConfig | object | generic | - |
| DELETE | `/api/v1/marketplace/listings/{id}/` | ListingViewSet | marketplace.Listing | object | creator:_create_published_listing | - |
| DELETE | `/api/v1/marketplace/orders/{id}/` | OrderViewSet | marketplace.Order | object | creator:_create_order | - |
| DELETE | `/api/v1/marketplace/saved-searches/{id}/` | SavedSearchViewSet | marketplace.SavedSearch | object | generic | - |
| DELETE | `/api/v1/mesh/domains/{id}/` | DomainViewSet | mesh.DataMeshDomain | object | generic | - |
| DELETE | `/api/v1/mesh/domains/{id}/policies/{policy_id}/` | DomainViewSet | mesh.DataMeshDomain | object | generic | - |
| DELETE | `/api/v1/ml/inference/ab-tests/{pk}/` | ABTestViewSet | ml.ABTest | object | creator:_create_ab_test | - |
| DELETE | `/api/v1/ml/models/{id}/` | MLModelViewSet | ml.MLModel | object | generic | - |
| DELETE | `/api/v1/processor-agreements/asset-processor-links/{id}/` | AssetProcessorLinkViewSet | processor_agreements.AssetProcessorMembership | object | generic | TENANT_ADMIN |
| DELETE | `/api/v1/processor-agreements/processor-agreements/{id}/` | ProcessorAgreementViewSet | processor_agreements.ProcessorAgreement | object | generic | TENANT_ADMIN |
| DELETE | `/api/v1/processor-agreements/processors/{id}/` | ProcessorViewSet | processor_agreements.Processor | object | generic | TENANT_ADMIN |
| DELETE | `/api/v1/quality/runs/{id}/` | DeprecatedDQRunViewSet | dq.DQRun | object | creator:_create_dq_run | - |
| DELETE | `/api/v1/ropa/generations/{pk}/delete/` | RopaGenerationViewSet | ropa.RopaGeneration | object | generic | - |
| DELETE | `/api/v1/scheduled-exports/{id}/` | ScheduledExportViewSet | scheduled_export.ScheduledExport | object | creator:_create_scheduled_export | - |
| DELETE | `/api/v1/scheduled-ingestions/{id}/` | ScheduledIngestionViewSet | scheduled_ingestion.ScheduledIngestion | object | creator:_create_scheduled_ingestion | - |
| DELETE | `/api/v1/semantic/ldn/subscriptions/{id}/` | LdnSubscriptionViewSet | semantic.LdnSubscription | object | generic | - |
| DELETE | `/api/v1/semantic/ontologies/{id}/` | TenantOntologyViewSet | semantic.TenantOntology | object | generic | - |
| DELETE | `/api/v1/tenants/{tenant_id}/sparql-endpoints/{pk}/` | TenantSparqlEndpointViewSet | semantic.TenantSparqlEndpoint | object | generic | - |
| DELETE | `/api/v1/transformation/pipelines/{id}/` | TransformationPipelineViewSet | transformation.TransformationPipeline | object | creator:_create_transformation_pipeline | - |
| DELETE | `/api/v1/transformation/wrangling/{id}/` | WranglingSessionViewSet | transformation.WranglingSession | object | generic | - |
| DELETE | `/api/v1/users/{id}/` | UserViewSet | users.User | object | generic | - |
| DELETE | `/api/v1/virtualization/datasets/{id}/` | VirtualDatasetViewSet | virtualization.VirtualDataset | object | creator:_create_virtual_dataset | - |
| DELETE | `/api/v1/warehouses/acls/{id}/` | WarehouseConnectionACLViewSet | warehouses.WarehouseConnectionACL | object | generic | - |
| DELETE | `/api/v1/warehouses/connections/{id}/` | WarehouseConnectionViewSet | warehouses.WarehouseConnection | object | generic | - |
| DELETE | `/api/v1/webhooks/webhooks/{id}/` | WebhookViewSet | webhooks.Webhook | object | creator:_create_webhook | - |
| GET | `/api/v1/assets/recommendations/` | AssetViewSet | assets.Asset | list | creator:_create_active_asset | - |
| GET | `/api/v1/assets/workflows/{workflow_instance_id}/status/` | AssetViewSet | assets.Asset | object | creator:_create_active_asset | - |
| GET | `/api/v1/assets/{id}/` | AssetViewSet | assets.Asset | object | creator:_create_active_asset | - |
| GET | `/api/v1/assets/{id}/classification/` | AssetViewSet | assets.Asset | object | creator:_create_active_asset | - |
| GET | `/api/v1/assets/{id}/dependencies/` | AssetViewSet | assets.Asset | object | creator:_create_active_asset | - |
| GET | `/api/v1/assets/{id}/external-resources/` | AssetViewSet | assets.Asset | object | creator:_create_active_asset | - |
| GET | `/api/v1/assets/{id}/health-score/` | AssetViewSet | assets.Asset | object | creator:_create_active_asset | - |
| GET | `/api/v1/audit/audit-events/` | AuditEventViewSet | audit.AuditEvent | list | generic | TENANT_ADMIN |
| GET | `/api/v1/audit/audit-events/export/` | AuditEventViewSet | audit.AuditEvent | list | generic | TENANT_ADMIN |
| GET | `/api/v1/audit/audit-events/resource-activity/` | AuditEventViewSet | audit.AuditEvent | list | generic | TENANT_ADMIN |
| GET | `/api/v1/audit/audit-events/{id}/` | AuditEventViewSet | audit.AuditEvent | object | generic | TENANT_ADMIN |
| GET | `/api/v1/audit/event-retention-policies/` | AuditEventRetentionPolicyViewSet | audit.AuditEventRetentionPolicy | list | generic | - |
| GET | `/api/v1/audit/event-retention-policies/{id}/` | AuditEventRetentionPolicyViewSet | audit.AuditEventRetentionPolicy | object | generic | - |
| GET | `/api/v1/audit/resource-activity/` | ResourceActivityViewSet | audit.AuditEvent | list | generic | - |
| GET | `/api/v1/auth/api-keys/` | APIKeyViewSet | hub_auth.APIKey | list | generic | - |
| GET | `/api/v1/auth/api-keys/{id}/` | APIKeyViewSet | hub_auth.APIKey | object | generic | - |
| GET | `/api/v1/baas/api-keys/` | APIKeyViewSet | hub_auth.APIKey | list | generic | - |
| GET | `/api/v1/baas/api-keys/{id}/` | APIKeyViewSet | hub_auth.APIKey | object | generic | - |
| GET | `/api/v1/baas/api-keys/{id}/quota/` | APIKeyViewSet | hub_auth.APIKey | object | generic | - |
| GET | `/api/v1/baas/billing-reports/` | CustomerBillingReportViewSet | baas.CustomerBillingReport | list | generic | - |
| GET | `/api/v1/baas/billing-reports/{id}/` | CustomerBillingReportViewSet | baas.CustomerBillingReport | object | generic | - |
| GET | `/api/v1/billing/invoices/` | InvoiceViewSet | billing.Invoice | list | generic | - |
| GET | `/api/v1/billing/invoices/{pk}/` | InvoiceViewSet | billing.Invoice | object | generic | - |
| GET | `/api/v1/billing/invoices/{pk}/download/` | InvoiceViewSet | billing.Invoice | object | generic | - |
| GET | `/api/v1/billing/subscription/` | SubscriptionViewSet | billing.Subscription | list | creator:_create_subscription | - |
| GET | `/api/v1/billing/subscription/current/` | SubscriptionViewSet | billing.Subscription | list | creator:_create_subscription | - |
| GET | `/api/v1/billing/subscription/ml/current/` | MLSubscriptionViewSet | billing.Subscription | list | creator:_create_subscription | - |
| GET | `/api/v1/billing/subscription/{pk}/` | SubscriptionViewSet | billing.Subscription | object | creator:_create_subscription | - |
| GET | `/api/v1/breach/incidents/` | BreachIncidentViewSet | breach.BreachIncident | list | generic | - |
| GET | `/api/v1/breach/incidents/{id}/` | BreachIncidentViewSet | breach.BreachIncident | object | generic | - |
| GET | `/api/v1/breach/notifications/` | BreachNotificationViewSet | breach.BreachNotification | list | generic | - |
| GET | `/api/v1/breach/notifications/{id}/` | BreachNotificationViewSet | breach.BreachNotification | object | generic | - |
| GET | `/api/v1/breach/template-overrides/` | BreachTenantTemplateOverrideViewSet | breach.BreachTenantTemplateOverride | list | generic | - |
| GET | `/api/v1/compliance/runs/` | ComplianceRunViewSet | compliance.ComplianceRun | list | creator:_create_compliance_run | - |
| GET | `/api/v1/compliance/runs/{id}/` | ComplianceRunViewSet | compliance.ComplianceRun | object | creator:_create_compliance_run | - |
| GET | `/api/v1/compliance/runs/{id}/export.csv/` | ComplianceRunViewSet | compliance.ComplianceRun | object | creator:_create_compliance_run | - |
| GET | `/api/v1/compliance/runs/{id}/export.json/` | ComplianceRunViewSet | compliance.ComplianceRun | object | creator:_create_compliance_run | - |
| GET | `/api/v1/compliance/runs/{id}/results/` | ComplianceRunViewSet | compliance.ComplianceRun | object | creator:_create_compliance_run | - |
| GET | `/api/v1/consent/consent-purposes/` | ConsentPurposeViewSet | consent.ConsentPurpose | list | generic | - |
| GET | `/api/v1/consent/consent-purposes/{id}/` | ConsentPurposeViewSet | consent.ConsentPurpose | object | generic | - |
| GET | `/api/v1/consent/consent-records/` | ConsentRecordViewSet | consent.ConsentRecord | list | generic | - |
| GET | `/api/v1/consent/consent-records/{id}/` | ConsentRecordViewSet | consent.ConsentRecord | object | generic | - |
| GET | `/api/v1/contracts/products/workflows/{workflow_instance_id}/status/` | ContractViewSet | contracts.Contract | object | generic | - |
| GET | `/api/v1/contracts/schema/json-schema/` | ContractViewSet | contracts.Contract | list | generic | - |
| GET | `/api/v1/contracts/{id}/` | ContractViewSet | contracts.Contract | object | generic | - |
| GET | `/api/v1/contracts/{id}/fields/{field_name}/lineage/` | ContractViewSet | contracts.Contract | object | generic | - |
| GET | `/api/v1/contracts/{id}/impact-analysis/` | ContractViewSet | contracts.Contract | object | generic | - |
| GET | `/api/v1/contracts/{id}/lineage/contracts/` | ContractViewSet | contracts.Contract | object | generic | - |
| GET | `/api/v1/contracts/{id}/lineage/diff/` | ContractViewSet | contracts.Contract | object | generic | - |
| GET | `/api/v1/contracts/{id}/lineage/full/` | ContractViewSet | contracts.Contract | object | generic | - |
| GET | `/api/v1/contracts/{id}/links/` | ContractViewSet | contracts.Contract | object | generic | - |
| GET | `/api/v1/contracts/{id}/models/{model_name}/lineage/` | ContractViewSet | contracts.Contract | object | generic | - |
| GET | `/api/v1/contracts/{id}/payment-gateways/` | ContractViewSet | contracts.Contract | object | generic | - |
| GET | `/api/v1/contracts/{id}/product-details/` | ContractViewSet | contracts.Contract | object | generic | - |
| GET | `/api/v1/contracts/{id}/product-strategy/` | ContractViewSet | contracts.Contract | object | generic | - |
| GET | `/api/v1/data-movement/config/` | DataMovementConfigViewSet | data_movement.DataMovementConfig | list | generic | - |
| GET | `/api/v1/data-movement/config/{pk}/` | DataMovementConfigViewSet | data_movement.DataMovementConfig | object | generic | - |
| GET | `/api/v1/databricks/workspaces/` | WorkspaceViewSet | databricks_admin.DatabricksWorkspace | list | creator:_create_databricks_workspace | - |
| GET | `/api/v1/databricks/workspaces/{id}/` | WorkspaceViewSet | databricks_admin.DatabricksWorkspace | object | creator:_create_databricks_workspace | - |
| GET | `/api/v1/datasets/{id}/` | DatasetViewSet | datasets.Dataset | object | generic | - |
| GET | `/api/v1/datasets/{id}/rows/` | DatasetViewSet | datasets.Dataset | object | generic | - |
| GET | `/api/v1/datasets/{id}/sample/` | DatasetViewSet | datasets.Dataset | object | generic | - |
| GET | `/api/v1/datasets/{id}/schema-evolution/` | DatasetViewSet | datasets.Dataset | object | generic | - |
| GET | `/api/v1/datasets/{id}/versions/` | DatasetViewSet | datasets.Dataset | object | generic | - |
| GET | `/api/v1/datasets/{id}/versions/compare/` | DatasetViewSet | datasets.Dataset | object | generic | - |
| GET | `/api/v1/dpia/records/` | DpiaViewSet | dpia.Dpia | list | generic | - |
| GET | `/api/v1/dpia/records/asset-status/` | DpiaViewSet | dpia.Dpia | list | generic | - |
| GET | `/api/v1/dpia/records/{pk}/` | DpiaViewSet | dpia.Dpia | object | generic | - |
| GET | `/api/v1/dpia/records/{pk}/diff/` | DpiaViewSet | dpia.Dpia | object | generic | - |
| GET | `/api/v1/dq/alerting-rules/` | DQAlertingRuleViewSet | dq.DQAlertingRule | list | creator:_create_dq_alerting_rule | - |
| GET | `/api/v1/dq/alerting-rules/{id}/` | DQAlertingRuleViewSet | dq.DQAlertingRule | object | creator:_create_dq_alerting_rule | - |
| GET | `/api/v1/dq/runs/` | DQRunViewSet | dq.DQRun | list | creator:_create_dq_run | - |
| GET | `/api/v1/dq/runs/{id}/` | DQRunViewSet | dq.DQRun | object | creator:_create_dq_run | - |
| GET | `/api/v1/dq/runs/{id}/results/` | DQRunViewSet | dq.DQRun | object | creator:_create_dq_run | - |
| GET | `/api/v1/dsar/requests/` | DSARRequestViewSet | dsar.DSARRequest | list | generic | - |
| GET | `/api/v1/dsar/requests/{pk}/` | DSARRequestViewSet | dsar.DSARRequest | object | generic | - |
| GET | `/api/v1/files/quota/` | FileViewSet | files.File | list | creator:_create_file | - |
| GET | `/api/v1/files/{id}/` | FileViewSet | files.File | object | creator:_create_file | - |
| GET | `/api/v1/files/{id}/download-payload/` | FileViewSet | files.File | object | creator:_create_file | - |
| GET | `/api/v1/files/{id}/download/` | FileViewSet | files.File | object | creator:_create_file | - |
| GET | `/api/v1/files/{id}/parts/` | FileViewSet | files.File | object | creator:_create_file | - |
| GET | `/api/v1/files/{id}/scan-status/` | FileViewSet | files.File | object | creator:_create_file | - |
| GET | `/api/v1/gdpr/erasure-requests/` | ErasureRequestViewSet | gdpr.ErasureRequest | list | generic | - |
| GET | `/api/v1/gdpr/erasure-requests/{pk}/` | ErasureRequestViewSet | gdpr.ErasureRequest | object | generic | - |
| GET | `/api/v1/gdpr/export-jobs/` | DataExportJobViewSet | gdpr.DataExportJob | list | generic | - |
| GET | `/api/v1/gdpr/export-jobs/{pk}/` | DataExportJobViewSet | gdpr.DataExportJob | object | generic | - |
| GET | `/api/v1/governance/access-requests/` | AccessRequestViewSet | governance.AccessRequest | list | creator:_create_access_request | - |
| GET | `/api/v1/governance/access-requests/pending-count/` | AccessRequestViewSet | governance.AccessRequest | list | creator:_create_access_request | - |
| GET | `/api/v1/governance/access-requests/{id}/` | AccessRequestViewSet | governance.AccessRequest | object | creator:_create_access_request | - |
| GET | `/api/v1/governance/access-requests/{id}/comments/` | AccessRequestViewSet | governance.AccessRequest | object | creator:_create_access_request | - |
| GET | `/api/v1/governance/access/access-requests/` | AccessRequestViewSet | governance.AccessRequest | list | creator:_create_access_request | - |
| GET | `/api/v1/governance/access/access-requests/pending-count/` | AccessRequestViewSet | governance.AccessRequest | list | creator:_create_access_request | - |
| GET | `/api/v1/governance/access/access-requests/{id}/` | AccessRequestViewSet | governance.AccessRequest | object | creator:_create_access_request | - |
| GET | `/api/v1/governance/access/access-requests/{id}/comments/` | AccessRequestViewSet | governance.AccessRequest | object | creator:_create_access_request | - |
| GET | `/api/v1/governance/access/certifications/` | AccessCertificationViewSet | governance.AccessCertification | list | generic | - |
| GET | `/api/v1/governance/access/certifications/expiring/` | AccessCertificationViewSet | governance.AccessCertification | list | generic | - |
| GET | `/api/v1/governance/access/certifications/summary/` | AccessCertificationViewSet | governance.AccessCertification | list | generic | - |
| GET | `/api/v1/governance/access/certifications/{id}/` | AccessCertificationViewSet | governance.AccessCertification | object | generic | - |
| GET | `/api/v1/governance/access/compliance-reports/{id}/` | ComplianceReportViewSet | compliance.ComplianceRun | object | creator:_create_compliance_run | - |
| GET | `/api/v1/governance/access/delegations/` | DelegationViewSet | governance.ApprovalDelegation | list | generic | - |
| GET | `/api/v1/governance/access/retention-policies/` | RetentionPolicyViewSet | governance.RetentionPolicy | list | creator:_create_retention_policy | - |
| GET | `/api/v1/governance/access/retention-policies/dashboard/` | RetentionPolicyViewSet | governance.RetentionPolicy | list | creator:_create_retention_policy | - |
| GET | `/api/v1/governance/access/retention-policies/quarterly-report/` | RetentionPolicyViewSet | governance.RetentionPolicy | list | creator:_create_retention_policy | - |
| GET | `/api/v1/governance/access/retention-policies/{id}/` | RetentionPolicyViewSet | governance.RetentionPolicy | object | creator:_create_retention_policy | - |
| GET | `/api/v1/governance/certifications/` | AccessCertificationViewSet | governance.AccessCertification | list | generic | - |
| GET | `/api/v1/governance/certifications/expiring/` | AccessCertificationViewSet | governance.AccessCertification | list | generic | - |
| GET | `/api/v1/governance/certifications/summary/` | AccessCertificationViewSet | governance.AccessCertification | list | generic | - |
| GET | `/api/v1/governance/certifications/{id}/` | AccessCertificationViewSet | governance.AccessCertification | object | generic | - |
| GET | `/api/v1/governance/compliance-reports/{id}/` | ComplianceReportViewSet | compliance.ComplianceRun | object | creator:_create_compliance_run | - |
| GET | `/api/v1/governance/delegations/` | DelegationViewSet | governance.ApprovalDelegation | list | generic | - |
| GET | `/api/v1/governance/retention-policies/` | RetentionPolicyViewSet | governance.RetentionPolicy | list | creator:_create_retention_policy | - |
| GET | `/api/v1/governance/retention-policies/dashboard/` | RetentionPolicyViewSet | governance.RetentionPolicy | list | creator:_create_retention_policy | - |
| GET | `/api/v1/governance/retention-policies/quarterly-report/` | RetentionPolicyViewSet | governance.RetentionPolicy | list | creator:_create_retention_policy | - |
| GET | `/api/v1/governance/retention-policies/{id}/` | RetentionPolicyViewSet | governance.RetentionPolicy | object | creator:_create_retention_policy | - |
| GET | `/api/v1/integrations/marketplace/connections/` | MarketplaceConnectionViewSet | integrations.MarketplaceConnection | list | generic | - |
| GET | `/api/v1/integrations/marketplace/connections/{id}/` | MarketplaceConnectionViewSet | integrations.MarketplaceConnection | object | generic | - |
| GET | `/api/v1/integrations/marketplace/mappings/` | MarketplaceMappingViewSet | integrations.MarketplaceMapping | list | generic | - |
| GET | `/api/v1/integrations/marketplace/mappings/{id}/` | MarketplaceMappingViewSet | integrations.MarketplaceMapping | object | generic | - |
| GET | `/api/v1/integrations/marketplace/sync/` | MarketplaceSyncJobViewSet | integrations.MarketplaceSyncJob | list | generic | - |
| GET | `/api/v1/integrations/marketplace/sync/{id}/` | MarketplaceSyncJobViewSet | integrations.MarketplaceSyncJob | object | generic | - |
| GET | `/api/v1/jobs/dlq/` | FailedJobDLQViewSet | jobs.FailedJobDLQ | list | generic | - |
| GET | `/api/v1/jobs/dlq/{id}/` | FailedJobDLQViewSet | jobs.FailedJobDLQ | object | generic | - |
| GET | `/api/v1/jobs/{id}/` | JobViewSet | jobs.Job | object | generic | - |
| GET | `/api/v1/marketplace/config/trust-signals/` | TrustSignalConfigViewSet | marketplace.TrustSignalConfig | list | generic | - |
| GET | `/api/v1/marketplace/config/trust-signals/{id}/` | TrustSignalConfigViewSet | marketplace.TrustSignalConfig | object | generic | - |
| GET | `/api/v1/marketplace/entitlements/` | EntitlementViewSet | marketplace.Entitlement | list | generic | - |
| GET | `/api/v1/marketplace/entitlements/{id}/` | EntitlementViewSet | marketplace.Entitlement | object | generic | - |
| GET | `/api/v1/marketplace/listings/` | ListingViewSet | marketplace.Listing | list | creator:_create_published_listing | - |
| GET | `/api/v1/marketplace/listings/search/` | ListingViewSet | marketplace.Listing | list | creator:_create_published_listing | - |
| GET | `/api/v1/marketplace/listings/{id}/` | ListingViewSet | marketplace.Listing | object | creator:_create_published_listing | - |
| GET | `/api/v1/marketplace/listings/{id}/lineage/` | ListingViewSet | marketplace.Listing | object | creator:_create_published_listing | - |
| GET | `/api/v1/marketplace/listings/{id}/preview/` | ListingViewSet | marketplace.Listing | object | creator:_create_published_listing | - |
| GET | `/api/v1/marketplace/orders/` | OrderViewSet | marketplace.Order | list | creator:_create_order | - |
| GET | `/api/v1/marketplace/orders/{id}/` | OrderViewSet | marketplace.Order | object | creator:_create_order | - |
| GET | `/api/v1/marketplace/saved-searches/` | SavedSearchViewSet | marketplace.SavedSearch | list | generic | - |
| GET | `/api/v1/marketplace/saved-searches/{id}/` | SavedSearchViewSet | marketplace.SavedSearch | object | generic | - |
| GET | `/api/v1/mesh/domains/` | DomainViewSet | mesh.DataMeshDomain | list | generic | - |
| GET | `/api/v1/mesh/domains/{id}/` | DomainViewSet | mesh.DataMeshDomain | object | generic | - |
| GET | `/api/v1/mesh/domains/{id}/analytics/` | DomainViewSet | mesh.DataMeshDomain | object | generic | - |
| GET | `/api/v1/mesh/domains/{id}/compliance/reports/` | DomainViewSet | mesh.DataMeshDomain | object | generic | - |
| GET | `/api/v1/mesh/domains/{id}/compliance/reports/{report_id}/` | DomainViewSet | mesh.DataMeshDomain | object | generic | - |
| GET | `/api/v1/mesh/domains/{id}/governance/` | DomainViewSet | mesh.DataMeshDomain | object | generic | - |
| GET | `/api/v1/mesh/domains/{id}/health/` | DomainViewSet | mesh.DataMeshDomain | object | generic | - |
| GET | `/api/v1/mesh/domains/{id}/infrastructure/` | DomainViewSet | mesh.DataMeshDomain | object | generic | - |
| GET | `/api/v1/mesh/domains/{id}/monitoring/` | DomainViewSet | mesh.DataMeshDomain | object | generic | - |
| GET | `/api/v1/mesh/domains/{id}/policies/` | DomainViewSet | mesh.DataMeshDomain | object | generic | - |
| GET | `/api/v1/mesh/domains/{id}/quotas/` | DomainViewSet | mesh.DataMeshDomain | object | generic | - |
| GET | `/api/v1/mesh/domains/{id}/self-serve/` | DomainViewSet | mesh.DataMeshDomain | object | generic | - |
| GET | `/api/v1/ml/inference/ab-tests/` | ABTestViewSet | ml.ABTest | list | creator:_create_ab_test | - |
| GET | `/api/v1/ml/inference/ab-tests/{pk}/` | ABTestViewSet | ml.ABTest | object | creator:_create_ab_test | - |
| GET | `/api/v1/ml/models/` | MLModelViewSet | ml.MLModel | list | generic | - |
| GET | `/api/v1/ml/models/{id}/` | MLModelViewSet | ml.MLModel | object | generic | - |
| GET | `/api/v1/ml/models/{id}/datasets/` | MLModelViewSet | ml.MLModel | object | generic | - |
| GET | `/api/v1/ml/models/{id}/versions/` | MLModelViewSet | ml.MLModel | object | generic | - |
| GET | `/api/v1/notifications/user-notifications/` | UserNotificationViewSet | notifications.UserNotification | list | generic | - |
| GET | `/api/v1/notifications/user-notifications/unread-count/` | UserNotificationViewSet | notifications.UserNotification | list | generic | - |
| GET | `/api/v1/notifications/user-notifications/{id}/` | UserNotificationViewSet | notifications.UserNotification | object | generic | - |
| GET | `/api/v1/processor-agreements/asset-processor-links/` | AssetProcessorLinkViewSet | processor_agreements.AssetProcessorMembership | list | generic | TENANT_ADMIN |
| GET | `/api/v1/processor-agreements/asset-processor-links/{id}/` | AssetProcessorLinkViewSet | processor_agreements.AssetProcessorMembership | object | generic | TENANT_ADMIN |
| GET | `/api/v1/processor-agreements/processor-agreements/` | ProcessorAgreementViewSet | processor_agreements.ProcessorAgreement | list | generic | TENANT_ADMIN |
| GET | `/api/v1/processor-agreements/processor-agreements/{id}/` | ProcessorAgreementViewSet | processor_agreements.ProcessorAgreement | object | generic | TENANT_ADMIN |
| GET | `/api/v1/processor-agreements/processors/` | ProcessorViewSet | processor_agreements.Processor | list | generic | TENANT_ADMIN |
| GET | `/api/v1/processor-agreements/processors/{id}/` | ProcessorViewSet | processor_agreements.Processor | object | generic | TENANT_ADMIN |
| GET | `/api/v1/quality/runs/` | DeprecatedDQRunViewSet | dq.DQRun | list | creator:_create_dq_run | - |
| GET | `/api/v1/quality/runs/{id}/` | DeprecatedDQRunViewSet | dq.DQRun | object | creator:_create_dq_run | - |
| GET | `/api/v1/quality/runs/{id}/results/` | DeprecatedDQRunViewSet | dq.DQRun | object | creator:_create_dq_run | - |
| GET | `/api/v1/ropa/generations/` | RopaGenerationViewSet | ropa.RopaGeneration | list | generic | - |
| GET | `/api/v1/ropa/generations/preview/` | RopaGenerationViewSet | ropa.RopaGeneration | list | generic | - |
| GET | `/api/v1/ropa/generations/{pk}/` | RopaGenerationViewSet | ropa.RopaGeneration | object | generic | - |
| GET | `/api/v1/ropa/generations/{pk}/download/` | RopaGenerationViewSet | ropa.RopaGeneration | object | generic | - |
| GET | `/api/v1/scheduled-exports/runs/` | ScheduledExportRunViewSet | scheduled_export.ScheduledExportRun | list | creator:_create_scheduled_export_run | - |
| GET | `/api/v1/scheduled-exports/runs/{id}/` | ScheduledExportRunViewSet | scheduled_export.ScheduledExportRun | object | creator:_create_scheduled_export_run | - |
| GET | `/api/v1/scheduled-exports/{id}/` | ScheduledExportViewSet | scheduled_export.ScheduledExport | object | creator:_create_scheduled_export | - |
| GET | `/api/v1/scheduled-exports/{id}/runs/` | ScheduledExportViewSet | scheduled_export.ScheduledExport | object | creator:_create_scheduled_export | - |
| GET | `/api/v1/scheduled-ingestions/costs/` | ScheduledIngestionViewSet | scheduled_ingestion.ScheduledIngestion | list | creator:_create_scheduled_ingestion | - |
| GET | `/api/v1/scheduled-ingestions/dashboard/` | ScheduledIngestionViewSet | scheduled_ingestion.ScheduledIngestion | list | creator:_create_scheduled_ingestion | - |
| GET | `/api/v1/scheduled-ingestions/dead-letter-queue/` | ScheduledIngestionViewSet | scheduled_ingestion.ScheduledIngestion | list | creator:_create_scheduled_ingestion | - |
| GET | `/api/v1/scheduled-ingestions/{id}/` | ScheduledIngestionViewSet | scheduled_ingestion.ScheduledIngestion | object | creator:_create_scheduled_ingestion | - |
| GET | `/api/v1/scheduled-ingestions/{id}/credentials/` | ScheduledIngestionViewSet | scheduled_ingestion.ScheduledIngestion | object | creator:_create_scheduled_ingestion | - |
| GET | `/api/v1/scheduled-ingestions/{id}/runs/` | ScheduledIngestionViewSet | scheduled_ingestion.ScheduledIngestion | object | creator:_create_scheduled_ingestion | - |
| GET | `/api/v1/security/incidents/` | SecurityIncidentViewSet | contracts.SecurityIncident | list | generic | - |
| GET | `/api/v1/security/incidents/{id}/` | SecurityIncidentViewSet | contracts.SecurityIncident | object | generic | - |
| GET | `/api/v1/semantic/ldn/subscriptions/` | LdnSubscriptionViewSet | semantic.LdnSubscription | list | generic | - |
| GET | `/api/v1/semantic/ldn/subscriptions/{id}/` | LdnSubscriptionViewSet | semantic.LdnSubscription | object | generic | - |
| GET | `/api/v1/semantic/ontologies/` | TenantOntologyViewSet | semantic.TenantOntology | list | generic | - |
| GET | `/api/v1/semantic/ontologies/{id}/` | TenantOntologyViewSet | semantic.TenantOntology | object | generic | - |
| GET | `/api/v1/semantic/semantic-resources/` | SemanticResourceViewSet | semantic.SemanticResource | list | generic | - |
| GET | `/api/v1/semantic/semantic-resources/{id}/` | SemanticResourceViewSet | semantic.SemanticResource | object | generic | - |
| GET | `/api/v1/social/comments/` | CommentViewSet | social.Comment | list | generic | - |
| GET | `/api/v1/social/comments/{pk}/` | CommentViewSet | social.Comment | object | generic | - |
| GET | `/api/v1/social/communities/` | CommunityViewSet | social.Community | list | generic | - |
| GET | `/api/v1/social/communities/audit/` | CommunityViewSet | social.Community | list | generic | - |
| GET | `/api/v1/social/communities/{pk}/` | CommunityViewSet | social.Community | object | generic | - |
| GET | `/api/v1/social/communities/{pk}/assets/` | CommunityViewSet | social.Community | object | generic | - |
| GET | `/api/v1/social/communities/{pk}/discussions/` | CommunityViewSet | social.Community | object | generic | - |
| GET | `/api/v1/social/communities/{pk}/knowledge-base/` | CommunityViewSet | social.Community | object | generic | - |
| GET | `/api/v1/social/communities/{pk}/members/` | CommunityViewSet | social.Community | object | generic | - |
| GET | `/api/v1/social/ratings/` | RatingViewSet | social.Rating | list | generic | - |
| GET | `/api/v1/social/ratings/audit/` | RatingViewSet | social.Rating | list | generic | - |
| GET | `/api/v1/social/reviews/` | ReviewViewSet | social.Review | list | generic | - |
| GET | `/api/v1/social/reviews/audit/` | ReviewViewSet | social.Review | list | generic | - |
| GET | `/api/v1/social/reviews/pending/` | ReviewViewSet | social.Review | list | generic | - |
| GET | `/api/v1/social/reviews/{pk}/` | ReviewViewSet | social.Review | object | generic | - |
| GET | `/api/v1/tenants/config/me/config/` | RouterTenantConfigViewSet | tenants.TenantConfig | list | creator:_create_tenant_config | - |
| GET | `/api/v1/tenants/config/me/feature-flag-history/` | RouterTenantConfigViewSet | tenants.TenantConfig | list | creator:_create_tenant_config | - |
| GET | `/api/v1/tenants/config/me/feature-flags/` | RouterTenantConfigViewSet | tenants.TenantConfig | list | creator:_create_tenant_config | - |
| GET | `/api/v1/tenants/config/me/tax-id/` | RouterTenantConfigViewSet | tenants.TenantConfig | list | creator:_create_tenant_config | - |
| GET | `/api/v1/tenants/config/me/usage/` | RouterTenantConfigViewSet | tenants.TenantConfig | list | creator:_create_tenant_config | - |
| GET | `/api/v1/tenants/config/{tenant_id}/` | RouterTenantConfigViewSet | tenants.TenantConfig | object | creator:_create_tenant_config | - |
| GET | `/api/v1/tenants/me/config/` | TenantConfigViewSet | tenants.TenantConfig | list | creator:_create_tenant_config | - |
| GET | `/api/v1/tenants/me/feature-flag-history/` | TenantConfigViewSet | tenants.TenantConfig | list | creator:_create_tenant_config | - |
| GET | `/api/v1/tenants/me/feature-flags/` | TenantConfigViewSet | tenants.TenantConfig | list | creator:_create_tenant_config | - |
| GET | `/api/v1/tenants/me/plan/` | TenantConfigViewSet | tenants.TenantConfig | list | creator:_create_tenant_config | - |
| GET | `/api/v1/tenants/me/plan/available-ml-addons/` | TenantConfigViewSet | tenants.TenantConfig | list | creator:_create_tenant_config | - |
| GET | `/api/v1/tenants/me/plan/available-upgrades/` | TenantConfigViewSet | tenants.TenantConfig | list | creator:_create_tenant_config | - |
| GET | `/api/v1/tenants/me/tax-id/` | TenantConfigViewSet | tenants.TenantConfig | list | creator:_create_tenant_config | - |
| GET | `/api/v1/tenants/me/usage/` | TenantConfigViewSet | tenants.TenantConfig | list | creator:_create_tenant_config | - |
| GET | `/api/v1/tenants/{tenant_id}/config/` | TenantConfigViewSet | tenants.TenantConfig | object | creator:_create_tenant_config | - |
| GET | `/api/v1/tenants/{tenant_id}/sparql-endpoints/` | TenantSparqlEndpointViewSet | semantic.TenantSparqlEndpoint | nested_list | generic | - |
| GET | `/api/v1/tenants/{tenant_id}/sparql-endpoints/{pk}/` | TenantSparqlEndpointViewSet | semantic.TenantSparqlEndpoint | object | generic | - |
| GET | `/api/v1/transformation/pipelines/` | TransformationPipelineViewSet | transformation.TransformationPipeline | list | creator:_create_transformation_pipeline | - |
| GET | `/api/v1/transformation/pipelines/{id}/` | TransformationPipelineViewSet | transformation.TransformationPipeline | object | creator:_create_transformation_pipeline | - |
| GET | `/api/v1/transformation/pipelines/{id}/contract-drift/` | TransformationPipelineViewSet | transformation.TransformationPipeline | object | creator:_create_transformation_pipeline | - |
| GET | `/api/v1/transformation/pipelines/{id}/executions/` | TransformationPipelineViewSet | transformation.TransformationPipeline | object | creator:_create_transformation_pipeline | - |
| GET | `/api/v1/transformation/pipelines/{id}/impact-preview/` | TransformationPipelineViewSet | transformation.TransformationPipeline | object | creator:_create_transformation_pipeline | - |
| GET | `/api/v1/transformation/previews/` | PreviewResultViewSet | transformation.PreviewResult | list | creator:_create_preview_result | - |
| GET | `/api/v1/transformation/previews/{preview_id}/` | PreviewResultViewSet | transformation.PreviewResult | object | creator:_create_preview_result | - |
| GET | `/api/v1/transformation/wrangling/` | WranglingSessionViewSet | transformation.WranglingSession | list | generic | - |
| GET | `/api/v1/transformation/wrangling/{id}/` | WranglingSessionViewSet | transformation.WranglingSession | object | generic | - |
| GET | `/api/v1/users/me/erasure-requests/` | ErasureRequestViewSet | gdpr.ErasureRequest | list | generic | - |
| GET | `/api/v1/users/me/erasure-requests/{pk}/` | ErasureRequestViewSet | gdpr.ErasureRequest | object | generic | - |
| GET | `/api/v1/users/me/export-jobs/` | DataExportJobViewSet | gdpr.DataExportJob | list | generic | - |
| GET | `/api/v1/users/me/export-jobs/{pk}/` | DataExportJobViewSet | gdpr.DataExportJob | object | generic | - |
| GET | `/api/v1/users/roles/` | RoleViewSet | users.Role | list | generic | - |
| GET | `/api/v1/users/roles/{id}/` | RoleViewSet | users.Role | object | generic | - |
| GET | `/api/v1/users/{id}/` | UserViewSet | users.User | object | generic | - |
| GET | `/api/v1/virtualization/datasets/` | VirtualDatasetViewSet | virtualization.VirtualDataset | list | creator:_create_virtual_dataset | - |
| GET | `/api/v1/virtualization/datasets/{id}/` | VirtualDatasetViewSet | virtualization.VirtualDataset | object | creator:_create_virtual_dataset | - |
| GET | `/api/v1/virtualization/datasets/{id}/versions/` | VirtualDatasetViewSet | virtualization.VirtualDataset | object | creator:_create_virtual_dataset | - |
| GET | `/api/v1/warehouses/acls/` | WarehouseConnectionACLViewSet | warehouses.WarehouseConnectionACL | list | generic | - |
| GET | `/api/v1/warehouses/acls/{id}/` | WarehouseConnectionACLViewSet | warehouses.WarehouseConnectionACL | object | generic | - |
| GET | `/api/v1/warehouses/connections/` | WarehouseConnectionViewSet | warehouses.WarehouseConnection | list | generic | - |
| GET | `/api/v1/warehouses/connections/residency-mismatches/` | WarehouseConnectionViewSet | warehouses.WarehouseConnection | list | generic | - |
| GET | `/api/v1/warehouses/connections/{id}/` | WarehouseConnectionViewSet | warehouses.WarehouseConnection | object | generic | - |
| GET | `/api/v1/warehouses/connections/{id}/schema/` | WarehouseConnectionViewSet | warehouses.WarehouseConnection | object | generic | - |
| GET | `/api/v1/webhooks/webhooks/` | WebhookViewSet | webhooks.Webhook | list | creator:_create_webhook | - |
| GET | `/api/v1/webhooks/webhooks/event-types/` | WebhookViewSet | webhooks.Webhook | list | creator:_create_webhook | - |
| GET | `/api/v1/webhooks/webhooks/{id}/` | WebhookViewSet | webhooks.Webhook | object | creator:_create_webhook | - |
| GET | `/api/v1/webhooks/webhooks/{id}/deliveries/` | WebhookViewSet | webhooks.Webhook | object | creator:_create_webhook | - |
| PATCH | `/api/v1/assets/{id}/` | AssetViewSet | assets.Asset | object | creator:_create_active_asset | - |
| PATCH | `/api/v1/audit/event-retention-policies/{id}/` | AuditEventRetentionPolicyViewSet | audit.AuditEventRetentionPolicy | object | generic | - |
| PATCH | `/api/v1/auth/api-keys/{id}/` | APIKeyViewSet | hub_auth.APIKey | object | generic | - |
| PATCH | `/api/v1/baas/api-keys/{id}/` | APIKeyViewSet | hub_auth.APIKey | object | generic | - |
| PATCH | `/api/v1/breach/incidents/{id}/` | BreachIncidentViewSet | breach.BreachIncident | object | generic | - |
| PATCH | `/api/v1/breach/incidents/{id}/status/` | BreachIncidentViewSet | breach.BreachIncident | object | generic | - |
| PATCH | `/api/v1/compliance/runs/{id}/` | ComplianceRunViewSet | compliance.ComplianceRun | object | creator:_create_compliance_run | - |
| PATCH | `/api/v1/consent/consent-purposes/{id}/` | ConsentPurposeViewSet | consent.ConsentPurpose | object | generic | - |
| PATCH | `/api/v1/consent/consent-records/{id}/` | ConsentRecordViewSet | consent.ConsentRecord | object | generic | - |
| PATCH | `/api/v1/contracts/{id}/` | ContractViewSet | contracts.Contract | object | generic | - |
| PATCH | `/api/v1/contracts/{id}/lineage/` | ContractViewSet | contracts.Contract | object | generic | - |
| PATCH | `/api/v1/data-movement/config/{pk}/` | DataMovementConfigViewSet | data_movement.DataMovementConfig | object | generic | - |
| PATCH | `/api/v1/databricks/workspaces/{id}/` | WorkspaceViewSet | databricks_admin.DatabricksWorkspace | object | creator:_create_databricks_workspace | - |
| PATCH | `/api/v1/datasets/{id}/` | DatasetViewSet | datasets.Dataset | object | generic | - |
| PATCH | `/api/v1/dpia/records/{pk}/` | DpiaViewSet | dpia.Dpia | object | generic | - |
| PATCH | `/api/v1/dq/alerting-rules/{id}/` | DQAlertingRuleViewSet | dq.DQAlertingRule | object | creator:_create_dq_alerting_rule | - |
| PATCH | `/api/v1/dq/runs/{id}/` | DQRunViewSet | dq.DQRun | object | creator:_create_dq_run | - |
| PATCH | `/api/v1/dsar/requests/{pk}/` | DSARRequestViewSet | dsar.DSARRequest | object | generic | - |
| PATCH | `/api/v1/files/{id}/` | FileViewSet | files.File | object | creator:_create_file | - |
| PATCH | `/api/v1/governance/access-requests/{id}/` | AccessRequestViewSet | governance.AccessRequest | object | creator:_create_access_request | - |
| PATCH | `/api/v1/governance/access/access-requests/{id}/` | AccessRequestViewSet | governance.AccessRequest | object | creator:_create_access_request | - |
| PATCH | `/api/v1/governance/access/certifications/{id}/` | AccessCertificationViewSet | governance.AccessCertification | object | generic | - |
| PATCH | `/api/v1/governance/access/retention-policies/{id}/` | RetentionPolicyViewSet | governance.RetentionPolicy | object | creator:_create_retention_policy | - |
| PATCH | `/api/v1/governance/certifications/{id}/` | AccessCertificationViewSet | governance.AccessCertification | object | generic | - |
| PATCH | `/api/v1/governance/retention-policies/{id}/` | RetentionPolicyViewSet | governance.RetentionPolicy | object | creator:_create_retention_policy | - |
| PATCH | `/api/v1/integrations/marketplace/connections/{id}/` | MarketplaceConnectionViewSet | integrations.MarketplaceConnection | object | generic | - |
| PATCH | `/api/v1/integrations/marketplace/mappings/{id}/` | MarketplaceMappingViewSet | integrations.MarketplaceMapping | object | generic | - |
| PATCH | `/api/v1/integrations/marketplace/sync/{id}/` | MarketplaceSyncJobViewSet | integrations.MarketplaceSyncJob | object | generic | - |
| PATCH | `/api/v1/jobs/{id}/` | JobViewSet | jobs.Job | object | generic | - |
| PATCH | `/api/v1/marketplace/config/trust-signals/{id}/` | TrustSignalConfigViewSet | marketplace.TrustSignalConfig | object | generic | - |
| PATCH | `/api/v1/marketplace/listings/{id}/` | ListingViewSet | marketplace.Listing | object | creator:_create_published_listing | - |
| PATCH | `/api/v1/marketplace/orders/{id}/` | OrderViewSet | marketplace.Order | object | creator:_create_order | - |
| PATCH | `/api/v1/marketplace/saved-searches/{id}/` | SavedSearchViewSet | marketplace.SavedSearch | object | generic | - |
| PATCH | `/api/v1/mesh/domains/{id}/` | DomainViewSet | mesh.DataMeshDomain | object | generic | - |
| PATCH | `/api/v1/mesh/domains/{id}/boundaries/` | DomainViewSet | mesh.DataMeshDomain | object | generic | - |
| PATCH | `/api/v1/mesh/domains/{id}/ownership/` | DomainViewSet | mesh.DataMeshDomain | object | generic | - |
| PATCH | `/api/v1/ml/models/{id}/` | MLModelViewSet | ml.MLModel | object | generic | - |
| PATCH | `/api/v1/processor-agreements/processor-agreements/{id}/` | ProcessorAgreementViewSet | processor_agreements.ProcessorAgreement | object | generic | TENANT_ADMIN |
| PATCH | `/api/v1/processor-agreements/processors/{id}/` | ProcessorViewSet | processor_agreements.Processor | object | generic | TENANT_ADMIN |
| PATCH | `/api/v1/quality/runs/{id}/` | DeprecatedDQRunViewSet | dq.DQRun | object | creator:_create_dq_run | - |
| PATCH | `/api/v1/ropa/generations/{pk}/update/` | RopaGenerationViewSet | ropa.RopaGeneration | object | generic | - |
| PATCH | `/api/v1/scheduled-exports/{id}/` | ScheduledExportViewSet | scheduled_export.ScheduledExport | object | creator:_create_scheduled_export | - |
| PATCH | `/api/v1/scheduled-ingestions/{id}/` | ScheduledIngestionViewSet | scheduled_ingestion.ScheduledIngestion | object | creator:_create_scheduled_ingestion | - |
| PATCH | `/api/v1/semantic/ldn/subscriptions/{id}/` | LdnSubscriptionViewSet | semantic.LdnSubscription | object | generic | - |
| PATCH | `/api/v1/semantic/ontologies/{id}/` | TenantOntologyViewSet | semantic.TenantOntology | object | generic | - |
| PATCH | `/api/v1/social/communities/{pk}/` | CommunityViewSet | social.Community | object | generic | - |
| PATCH | `/api/v1/tenants/config/me/config/` | RouterTenantConfigViewSet | tenants.TenantConfig | self_route | creator:_create_tenant_config | - |
| PATCH | `/api/v1/tenants/config/me/feature-flags/` | RouterTenantConfigViewSet | tenants.TenantConfig | self_route | creator:_create_tenant_config | - |
| PATCH | `/api/v1/tenants/config/{tenant_id}/` | RouterTenantConfigViewSet | tenants.TenantConfig | object | creator:_create_tenant_config | - |
| PATCH | `/api/v1/tenants/me/config/` | TenantConfigViewSet | tenants.TenantConfig | self_route | creator:_create_tenant_config | - |
| PATCH | `/api/v1/tenants/me/feature-flags/` | TenantConfigViewSet | tenants.TenantConfig | self_route | creator:_create_tenant_config | - |
| PATCH | `/api/v1/tenants/{tenant_id}/config/` | TenantConfigViewSet | tenants.TenantConfig | object | creator:_create_tenant_config | - |
| PATCH | `/api/v1/tenants/{tenant_id}/sparql-endpoints/{pk}/` | TenantSparqlEndpointViewSet | semantic.TenantSparqlEndpoint | object | generic | - |
| PATCH | `/api/v1/transformation/pipelines/{id}/` | TransformationPipelineViewSet | transformation.TransformationPipeline | object | creator:_create_transformation_pipeline | - |
| PATCH | `/api/v1/transformation/wrangling/{id}/` | WranglingSessionViewSet | transformation.WranglingSession | object | generic | - |
| PATCH | `/api/v1/users/{id}/` | UserViewSet | users.User | object | generic | - |
| PATCH | `/api/v1/virtualization/datasets/{id}/` | VirtualDatasetViewSet | virtualization.VirtualDataset | object | creator:_create_virtual_dataset | - |
| PATCH | `/api/v1/warehouses/acls/{id}/` | WarehouseConnectionACLViewSet | warehouses.WarehouseConnectionACL | object | generic | - |
| PATCH | `/api/v1/warehouses/connections/{id}/` | WarehouseConnectionViewSet | warehouses.WarehouseConnection | object | generic | - |
| PATCH | `/api/v1/webhooks/webhooks/{id}/` | WebhookViewSet | webhooks.Webhook | object | creator:_create_webhook | - |
| POST | `/api/v1/assets/data-first/` | AssetViewSet | assets.Asset | payload_fk | creator:_create_active_asset | - |
| POST | `/api/v1/assets/{id}/activate/` | AssetViewSet | assets.Asset | object | creator:_create_active_asset | - |
| POST | `/api/v1/assets/{id}/classify/` | AssetViewSet | assets.Asset | object | creator:_create_active_asset | - |
| POST | `/api/v1/assets/{id}/contracts/` | AssetViewSet | assets.Asset | object | creator:_create_active_asset | - |
| POST | `/api/v1/assets/{id}/datasets/` | AssetViewSet | assets.Asset | object | creator:_create_active_asset | - |
| POST | `/api/v1/assets/{id}/ensure-e2e-activation-prerequisites/` | AssetViewSet | assets.Asset | object | creator:_create_active_asset | - |
| POST | `/api/v1/assets/{id}/external-resources/batch-download/` | AssetViewSet | assets.Asset | object | creator:_create_active_asset | - |
| POST | `/api/v1/assets/{id}/external-resources/download/` | AssetViewSet | assets.Asset | object | creator:_create_active_asset | - |
| POST | `/api/v1/assets/{id}/retire/` | AssetViewSet | assets.Asset | object | creator:_create_active_asset | - |
| POST | `/api/v1/assets/{id}/track-download/` | AssetViewSet | assets.Asset | object | creator:_create_active_asset | - |
| POST | `/api/v1/assets/{id}/track-view/` | AssetViewSet | assets.Asset | object | creator:_create_active_asset | - |
| POST | `/api/v1/audit/event-retention-policies/` | AuditEventRetentionPolicyViewSet | audit.AuditEventRetentionPolicy | create | generic | - |
| POST | `/api/v1/auth/api-keys/` | APIKeyViewSet | hub_auth.APIKey | create | generic | - |
| POST | `/api/v1/baas/api-keys/` | APIKeyViewSet | hub_auth.APIKey | create | generic | - |
| POST | `/api/v1/baas/billing-reports/generate/` | CustomerBillingReportViewSet | baas.CustomerBillingReport | create | generic | - |
| POST | `/api/v1/baas/billing-reports/{id}/finalize/` | CustomerBillingReportViewSet | baas.CustomerBillingReport | object | generic | - |
| POST | `/api/v1/baas/billing-reports/{id}/send/` | CustomerBillingReportViewSet | baas.CustomerBillingReport | object | generic | - |
| POST | `/api/v1/baas/billing-reports/{id}/void/` | CustomerBillingReportViewSet | baas.CustomerBillingReport | object | generic | - |
| POST | `/api/v1/billing/subscription/current/change-plan/` | SubscriptionViewSet | billing.Subscription | create | creator:_create_subscription | - |
| POST | `/api/v1/billing/subscription/ml/current/change-plan/` | MLSubscriptionViewSet | billing.Subscription | create | creator:_create_subscription | - |
| POST | `/api/v1/breach/incidents/` | BreachIncidentViewSet | breach.BreachIncident | create | generic | - |
| POST | `/api/v1/breach/notifications/{id}/mark-sent/` | BreachNotificationViewSet | breach.BreachNotification | object | generic | - |
| POST | `/api/v1/breach/template-overrides/upsert/` | BreachTenantTemplateOverrideViewSet | breach.BreachTenantTemplateOverride | create | generic | - |
| POST | `/api/v1/compliance/runs/` | ComplianceRunViewSet | compliance.ComplianceRun | create | creator:_create_compliance_run | - |
| POST | `/api/v1/compliance/runs/warehouse-scan/` | ComplianceRunViewSet | compliance.ComplianceRun | payload_fk | creator:_create_compliance_run | - |
| POST | `/api/v1/compliance/runs/{id}/cancel/` | ComplianceRunViewSet | compliance.ComplianceRun | object | creator:_create_compliance_run | - |
| POST | `/api/v1/compliance/runs/{id}/scan-warehouse/` | ComplianceRunViewSet | compliance.ComplianceRun | object | creator:_create_compliance_run | - |
| POST | `/api/v1/consent/consent-purposes/` | ConsentPurposeViewSet | consent.ConsentPurpose | create | generic | - |
| POST | `/api/v1/consent/consent-records/` | ConsentRecordViewSet | consent.ConsentRecord | create | generic | - |
| POST | `/api/v1/consent/consent-records/{id}/revoke/` | ConsentRecordViewSet | consent.ConsentRecord | object | generic | - |
| POST | `/api/v1/contracts/validate-draft/` | ContractViewSet | contracts.Contract | create | generic | - |
| POST | `/api/v1/contracts/{id}/convert/` | ContractViewSet | contracts.Contract | object | generic | - |
| POST | `/api/v1/contracts/{id}/generate-odps/` | ContractViewSet | contracts.Contract | object | generic | - |
| POST | `/api/v1/contracts/{id}/link-odps/` | ContractViewSet | contracts.Contract | object | generic | - |
| POST | `/api/v1/contracts/{id}/lint/` | ContractViewSet | contracts.Contract | object | generic | - |
| POST | `/api/v1/contracts/{id}/migrate/` | ContractViewSet | contracts.Contract | object | generic | - |
| POST | `/api/v1/contracts/{id}/unlink-odps/` | ContractViewSet | contracts.Contract | object | generic | - |
| POST | `/api/v1/contracts/{id}/validate/` | ContractViewSet | contracts.Contract | object | generic | - |
| POST | `/api/v1/data-movement/config/` | DataMovementConfigViewSet | data_movement.DataMovementConfig | create | generic | - |
| POST | `/api/v1/databricks/workspaces/{id}/test/` | WorkspaceViewSet | databricks_admin.DatabricksWorkspace | object | creator:_create_databricks_workspace | - |
| POST | `/api/v1/datasets/{id}/refresh-from-file/` | DatasetViewSet | datasets.Dataset | object | generic | - |
| POST | `/api/v1/datasets/{id}/refresh/` | DatasetViewSet | datasets.Dataset | object | generic | - |
| POST | `/api/v1/datasets/{id}/retire/` | DatasetViewSet | datasets.Dataset | object | generic | - |
| POST | `/api/v1/datasets/{id}/versions/` | DatasetViewSet | datasets.Dataset | object | generic | - |
| POST | `/api/v1/dpia/records/` | DpiaViewSet | dpia.Dpia | create | generic | - |
| POST | `/api/v1/dpia/records/{pk}/consultation/complete/` | DpiaViewSet | dpia.Dpia | object | generic | - |
| POST | `/api/v1/dpia/records/{pk}/new-version/` | DpiaViewSet | dpia.Dpia | object | generic | - |
| POST | `/api/v1/dpia/records/{pk}/review/` | DpiaViewSet | dpia.Dpia | object | generic | - |
| POST | `/api/v1/dpia/records/{pk}/submit/` | DpiaViewSet | dpia.Dpia | object | generic | - |
| POST | `/api/v1/dq/alerting-rules/` | DQAlertingRuleViewSet | dq.DQAlertingRule | create | creator:_create_dq_alerting_rule | - |
| POST | `/api/v1/dq/runs/` | DQRunViewSet | dq.DQRun | create | creator:_create_dq_run | - |
| POST | `/api/v1/dq/runs/warehouse-run/` | DQRunViewSet | dq.DQRun | payload_fk | creator:_create_dq_run | - |
| POST | `/api/v1/dsar/requests/` | DSARRequestViewSet | dsar.DSARRequest | create | generic | - |
| POST | `/api/v1/dsar/requests/{pk}/issue_download_url/` | DSARRequestViewSet | dsar.DSARRequest | object | generic | - |
| POST | `/api/v1/dsar/requests/{pk}/legal_hold/` | DSARRequestViewSet | dsar.DSARRequest | object | generic | - |
| POST | `/api/v1/dsar/requests/{pk}/materialize_package/` | DSARRequestViewSet | dsar.DSARRequest | object | generic | - |
| POST | `/api/v1/dsar/requests/{pk}/reject/` | DSARRequestViewSet | dsar.DSARRequest | object | generic | - |
| POST | `/api/v1/files/init/` | FileViewSet | files.File | create | creator:_create_file | - |
| POST | `/api/v1/files/{id}/chunks/init/` | FileViewSet | files.File | object | creator:_create_file | - |
| POST | `/api/v1/files/{id}/complete/` | FileViewSet | files.File | object | creator:_create_file | - |
| POST | `/api/v1/files/{id}/download/checksum-mismatch/` | FileViewSet | files.File | object | creator:_create_file | - |
| POST | `/api/v1/files/{id}/rename/` | FileViewSet | files.File | object | creator:_create_file | - |
| POST | `/api/v1/gdpr/erasure-requests/request-erasure/` | ErasureRequestViewSet | gdpr.ErasureRequest | create | generic | - |
| POST | `/api/v1/gdpr/export-jobs/export-data/` | DataExportJobViewSet | gdpr.DataExportJob | create | generic | - |
| POST | `/api/v1/governance/access-requests/` | AccessRequestViewSet | governance.AccessRequest | create | creator:_create_access_request | - |
| POST | `/api/v1/governance/access-requests/bulk-approve/` | AccessRequestViewSet | governance.AccessRequest | bulk | creator:_create_access_request | - |
| POST | `/api/v1/governance/access-requests/bulk-reject/` | AccessRequestViewSet | governance.AccessRequest | bulk | creator:_create_access_request | - |
| POST | `/api/v1/governance/access-requests/{id}/approve/` | AccessRequestViewSet | governance.AccessRequest | object | creator:_create_access_request | - |
| POST | `/api/v1/governance/access-requests/{id}/comments/` | AccessRequestViewSet | governance.AccessRequest | object | creator:_create_access_request | - |
| POST | `/api/v1/governance/access-requests/{id}/reject/` | AccessRequestViewSet | governance.AccessRequest | object | creator:_create_access_request | - |
| POST | `/api/v1/governance/access-requests/{id}/revoke/` | AccessRequestViewSet | governance.AccessRequest | object | creator:_create_access_request | - |
| POST | `/api/v1/governance/access/access-requests/` | AccessRequestViewSet | governance.AccessRequest | create | creator:_create_access_request | - |
| POST | `/api/v1/governance/access/access-requests/bulk-approve/` | AccessRequestViewSet | governance.AccessRequest | bulk | creator:_create_access_request | - |
| POST | `/api/v1/governance/access/access-requests/bulk-reject/` | AccessRequestViewSet | governance.AccessRequest | bulk | creator:_create_access_request | - |
| POST | `/api/v1/governance/access/access-requests/{id}/approve/` | AccessRequestViewSet | governance.AccessRequest | object | creator:_create_access_request | - |
| POST | `/api/v1/governance/access/access-requests/{id}/comments/` | AccessRequestViewSet | governance.AccessRequest | object | creator:_create_access_request | - |
| POST | `/api/v1/governance/access/access-requests/{id}/reject/` | AccessRequestViewSet | governance.AccessRequest | object | creator:_create_access_request | - |
| POST | `/api/v1/governance/access/access-requests/{id}/revoke/` | AccessRequestViewSet | governance.AccessRequest | object | creator:_create_access_request | - |
| POST | `/api/v1/governance/access/certifications/` | AccessCertificationViewSet | governance.AccessCertification | create | generic | - |
| POST | `/api/v1/governance/access/certifications/initiate-review/` | AccessCertificationViewSet | governance.AccessCertification | create | generic | - |
| POST | `/api/v1/governance/access/certifications/{id}/review/` | AccessCertificationViewSet | governance.AccessCertification | object | generic | - |
| POST | `/api/v1/governance/access/compliance-reports/` | ComplianceReportViewSet | compliance.ComplianceRun | create | creator:_create_compliance_run | - |
| POST | `/api/v1/governance/access/delegations/` | DelegationViewSet | governance.ApprovalDelegation | create | generic | - |
| POST | `/api/v1/governance/access/retention-policies/` | RetentionPolicyViewSet | governance.RetentionPolicy | create | creator:_create_retention_policy | - |
| POST | `/api/v1/governance/certifications/` | AccessCertificationViewSet | governance.AccessCertification | create | generic | - |
| POST | `/api/v1/governance/certifications/initiate-review/` | AccessCertificationViewSet | governance.AccessCertification | create | generic | - |
| POST | `/api/v1/governance/certifications/{id}/review/` | AccessCertificationViewSet | governance.AccessCertification | object | generic | - |
| POST | `/api/v1/governance/compliance-reports/` | ComplianceReportViewSet | compliance.ComplianceRun | create | creator:_create_compliance_run | - |
| POST | `/api/v1/governance/delegations/` | DelegationViewSet | governance.ApprovalDelegation | create | generic | - |
| POST | `/api/v1/governance/retention-policies/` | RetentionPolicyViewSet | governance.RetentionPolicy | create | creator:_create_retention_policy | - |
| POST | `/api/v1/integrations/marketplace/connections/` | MarketplaceConnectionViewSet | integrations.MarketplaceConnection | create | generic | - |
| POST | `/api/v1/integrations/marketplace/connections/{id}/test/` | MarketplaceConnectionViewSet | integrations.MarketplaceConnection | object | generic | - |
| POST | `/api/v1/integrations/marketplace/mappings/` | MarketplaceMappingViewSet | integrations.MarketplaceMapping | create | generic | - |
| POST | `/api/v1/integrations/marketplace/sync/` | MarketplaceSyncJobViewSet | integrations.MarketplaceSyncJob | payload_fk | generic | - |
| POST | `/api/v1/integrations/marketplace/sync/{id}/cancel/` | MarketplaceSyncJobViewSet | integrations.MarketplaceSyncJob | object | generic | - |
| POST | `/api/v1/jobs/dlq/{id}/retry/` | FailedJobDLQViewSet | jobs.FailedJobDLQ | object | generic | - |
| POST | `/api/v1/jobs/{id}/cancel/` | JobViewSet | jobs.Job | object | generic | - |
| POST | `/api/v1/marketplace/config/trust-signals/` | TrustSignalConfigViewSet | marketplace.TrustSignalConfig | create | generic | - |
| POST | `/api/v1/marketplace/entitlements/check-access/` | EntitlementViewSet | marketplace.Entitlement | create | generic | - |
| POST | `/api/v1/marketplace/entitlements/{id}/revoke/` | EntitlementViewSet | marketplace.Entitlement | object | generic | - |
| POST | `/api/v1/marketplace/listings/` | ListingViewSet | marketplace.Listing | create | creator:_create_published_listing | - |
| POST | `/api/v1/marketplace/orders/` | OrderViewSet | marketplace.Order | create | creator:_create_order | - |
| POST | `/api/v1/marketplace/orders/purchase/` | OrderViewSet | marketplace.Order | payload_fk | creator:_create_order | - |
| POST | `/api/v1/marketplace/orders/{id}/approve/` | OrderViewSet | marketplace.Order | object | creator:_create_order | - |
| POST | `/api/v1/marketplace/orders/{id}/cancel/` | OrderViewSet | marketplace.Order | object | creator:_create_order | - |
| POST | `/api/v1/marketplace/orders/{id}/confirm-payment/` | OrderViewSet | marketplace.Order | object | creator:_create_order | - |
| POST | `/api/v1/marketplace/orders/{id}/refund/` | OrderViewSet | marketplace.Order | object | creator:_create_order | - |
| POST | `/api/v1/marketplace/orders/{id}/reject/` | OrderViewSet | marketplace.Order | object | creator:_create_order | - |
| POST | `/api/v1/marketplace/saved-searches/` | SavedSearchViewSet | marketplace.SavedSearch | create | generic | - |
| POST | `/api/v1/mesh/domains/` | DomainViewSet | mesh.DataMeshDomain | create | generic | - |
| POST | `/api/v1/mesh/domains/{id}/assets/` | DomainViewSet | mesh.DataMeshDomain | object | generic | - |
| POST | `/api/v1/mesh/domains/{id}/compliance/check/` | DomainViewSet | mesh.DataMeshDomain | object | generic | - |
| POST | `/api/v1/mesh/domains/{id}/deploy/` | DomainViewSet | mesh.DataMeshDomain | object | generic | - |
| POST | `/api/v1/mesh/domains/{id}/governance/` | DomainViewSet | mesh.DataMeshDomain | object | generic | - |
| POST | `/api/v1/mesh/domains/{id}/infrastructure/` | DomainViewSet | mesh.DataMeshDomain | object | generic | - |
| POST | `/api/v1/mesh/domains/{id}/policies/apply/` | DomainViewSet | mesh.DataMeshDomain | object | generic | - |
| POST | `/api/v1/mesh/domains/{id}/quotas/` | DomainViewSet | mesh.DataMeshDomain | object | generic | - |
| POST | `/api/v1/mesh/domains/{id}/self-serve/` | DomainViewSet | mesh.DataMeshDomain | object | generic | - |
| POST | `/api/v1/mesh/domains/{id}/transfer-ownership/` | DomainViewSet | mesh.DataMeshDomain | object | generic | - |
| POST | `/api/v1/ml/inference/ab-tests/` | ABTestViewSet | ml.ABTest | create | creator:_create_ab_test | - |
| POST | `/api/v1/ml/models/` | MLModelViewSet | ml.MLModel | create | generic | - |
| POST | `/api/v1/ml/models/{id}/link-asset/` | MLModelViewSet | ml.MLModel | object | generic | - |
| POST | `/api/v1/ml/models/{id}/link-dataset/` | MLModelViewSet | ml.MLModel | object | generic | - |
| POST | `/api/v1/ml/models/{id}/predict/` | MLModelViewSet | ml.MLModel | object | generic | - |
| POST | `/api/v1/ml/models/{id}/sync-from-odh/` | MLModelViewSet | ml.MLModel | object | generic | - |
| POST | `/api/v1/notifications/user-notifications/read-all/` | UserNotificationViewSet | notifications.UserNotification | create | generic | - |
| POST | `/api/v1/notifications/user-notifications/{id}/read/` | UserNotificationViewSet | notifications.UserNotification | object | generic | - |
| POST | `/api/v1/processor-agreements/asset-processor-links/` | AssetProcessorLinkViewSet | processor_agreements.AssetProcessorMembership | create | generic | TENANT_ADMIN |
| POST | `/api/v1/processor-agreements/processor-agreements/` | ProcessorAgreementViewSet | processor_agreements.ProcessorAgreement | create | generic | TENANT_ADMIN |
| POST | `/api/v1/processor-agreements/processors/` | ProcessorViewSet | processor_agreements.Processor | create | generic | TENANT_ADMIN |
| POST | `/api/v1/quality/runs/` | DeprecatedDQRunViewSet | dq.DQRun | create | creator:_create_dq_run | - |
| POST | `/api/v1/quality/runs/warehouse-run/` | DeprecatedDQRunViewSet | dq.DQRun | payload_fk | creator:_create_dq_run | - |
| POST | `/api/v1/ropa/generate/` | RopaGenerationViewSet | ropa.RopaGeneration | create | generic | - |
| POST | `/api/v1/ropa/generations/generate/` | RopaGenerationViewSet | ropa.RopaGeneration | create | generic | - |
| POST | `/api/v1/scheduled-exports/{id}/sync/` | ScheduledExportViewSet | scheduled_export.ScheduledExport | object | creator:_create_scheduled_export | - |
| POST | `/api/v1/scheduled-exports/{id}/trigger/` | ScheduledExportViewSet | scheduled_export.ScheduledExport | object | creator:_create_scheduled_export | - |
| POST | `/api/v1/scheduled-ingestions/{id}/credentials/test/` | ScheduledIngestionViewSet | scheduled_ingestion.ScheduledIngestion | object | creator:_create_scheduled_ingestion | - |
| POST | `/api/v1/scheduled-ingestions/{id}/dlq/{dlq_item_id}/resolve/` | ScheduledIngestionViewSet | scheduled_ingestion.ScheduledIngestion | object | creator:_create_scheduled_ingestion | - |
| POST | `/api/v1/scheduled-ingestions/{id}/dlq/{dlq_item_id}/retry/` | ScheduledIngestionViewSet | scheduled_ingestion.ScheduledIngestion | object | creator:_create_scheduled_ingestion | - |
| POST | `/api/v1/scheduled-ingestions/{id}/sync/` | ScheduledIngestionViewSet | scheduled_ingestion.ScheduledIngestion | object | creator:_create_scheduled_ingestion | - |
| POST | `/api/v1/scheduled-ingestions/{id}/trigger/` | ScheduledIngestionViewSet | scheduled_ingestion.ScheduledIngestion | object | creator:_create_scheduled_ingestion | - |
| POST | `/api/v1/security/incidents/{id}/resolve/` | SecurityIncidentViewSet | contracts.SecurityIncident | object | generic | - |
| POST | `/api/v1/semantic/ldn/subscriptions/` | LdnSubscriptionViewSet | semantic.LdnSubscription | create | generic | - |
| POST | `/api/v1/semantic/ontologies/` | TenantOntologyViewSet | semantic.TenantOntology | create | generic | - |
| POST | `/api/v1/social/comments/` | CommentViewSet | social.Comment | create | generic | - |
| POST | `/api/v1/social/communities/` | CommunityViewSet | social.Community | create | generic | - |
| POST | `/api/v1/social/communities/{pk}/assets/` | CommunityViewSet | social.Community | object | generic | - |
| POST | `/api/v1/social/communities/{pk}/discussions/` | CommunityViewSet | social.Community | object | generic | - |
| POST | `/api/v1/social/communities/{pk}/join/` | CommunityViewSet | social.Community | object | generic | - |
| POST | `/api/v1/social/ratings/` | RatingViewSet | social.Rating | create | generic | - |
| POST | `/api/v1/social/reviews/` | ReviewViewSet | social.Review | create | generic | - |
| POST | `/api/v1/social/reviews/{pk}/approve/` | ReviewViewSet | social.Review | object | generic | - |
| POST | `/api/v1/social/reviews/{pk}/reject/` | ReviewViewSet | social.Review | object | generic | - |
| POST | `/api/v1/tenants/config/me/seed-sample/` | RouterTenantConfigViewSet | tenants.TenantConfig | self_route | creator:_create_tenant_config | - |
| POST | `/api/v1/tenants/config/me/tax-id/` | RouterTenantConfigViewSet | tenants.TenantConfig | self_route | creator:_create_tenant_config | - |
| POST | `/api/v1/tenants/config/onboarding/` | RouterTenantConfigViewSet | tenants.TenantConfig | create | creator:_create_tenant_config | - |
| POST | `/api/v1/tenants/me/plan/downgrade/` | TenantConfigViewSet | tenants.TenantConfig | self_route | creator:_create_tenant_config | - |
| POST | `/api/v1/tenants/me/plan/upgrade/` | TenantConfigViewSet | tenants.TenantConfig | self_route | creator:_create_tenant_config | - |
| POST | `/api/v1/tenants/me/seed-sample/` | TenantConfigViewSet | tenants.TenantConfig | self_route | creator:_create_tenant_config | - |
| POST | `/api/v1/tenants/me/tax-id/` | TenantConfigViewSet | tenants.TenantConfig | self_route | creator:_create_tenant_config | - |
| POST | `/api/v1/tenants/onboarding/` | TenantConfigViewSet | tenants.TenantConfig | create | creator:_create_tenant_config | - |
| POST | `/api/v1/tenants/{tenant_id}/sparql-endpoints/` | TenantSparqlEndpointViewSet | semantic.TenantSparqlEndpoint | nested_list | generic | - |
| POST | `/api/v1/transformation/pipelines/` | TransformationPipelineViewSet | transformation.TransformationPipeline | create | creator:_create_transformation_pipeline | - |
| POST | `/api/v1/transformation/pipelines/{id}/execute/` | TransformationPipelineViewSet | transformation.TransformationPipeline | object | creator:_create_transformation_pipeline | - |
| POST | `/api/v1/transformation/pipelines/{id}/preview/` | TransformationPipelineViewSet | transformation.TransformationPipeline | object | creator:_create_transformation_pipeline | - |
| POST | `/api/v1/transformation/pipelines/{id}/validate/` | TransformationPipelineViewSet | transformation.TransformationPipeline | object | creator:_create_transformation_pipeline | - |
| POST | `/api/v1/transformation/wrangling/` | WranglingSessionViewSet | transformation.WranglingSession | payload_fk | generic | - |
| POST | `/api/v1/transformation/wrangling/{id}/redo/` | WranglingSessionViewSet | transformation.WranglingSession | object | generic | - |
| POST | `/api/v1/transformation/wrangling/{id}/undo/` | WranglingSessionViewSet | transformation.WranglingSession | object | generic | - |
| POST | `/api/v1/users/invite/` | UserViewSet | users.User | create | generic | - |
| POST | `/api/v1/users/me/erasure-requests/request-erasure/` | ErasureRequestViewSet | gdpr.ErasureRequest | self_route | generic | - |
| POST | `/api/v1/users/me/export-jobs/export-data/` | DataExportJobViewSet | gdpr.DataExportJob | self_route | generic | - |
| POST | `/api/v1/users/{id}/roles/` | UserViewSet | users.User | object | generic | - |
| POST | `/api/v1/virtualization/datasets/` | VirtualDatasetViewSet | virtualization.VirtualDataset | create | creator:_create_virtual_dataset | - |
| POST | `/api/v1/virtualization/datasets/{id}/queries/` | VirtualDatasetViewSet | virtualization.VirtualDataset | object | creator:_create_virtual_dataset | - |
| POST | `/api/v1/virtualization/datasets/{id}/validate/` | VirtualDatasetViewSet | virtualization.VirtualDataset | object | creator:_create_virtual_dataset | - |
| POST | `/api/v1/warehouses/acls/` | WarehouseConnectionACLViewSet | warehouses.WarehouseConnectionACL | create | generic | - |
| POST | `/api/v1/warehouses/connections/` | WarehouseConnectionViewSet | warehouses.WarehouseConnection | create | generic | - |
| POST | `/api/v1/warehouses/connections/{id}/test/` | WarehouseConnectionViewSet | warehouses.WarehouseConnection | object | generic | - |
| POST | `/api/v1/webhooks/webhooks/` | WebhookViewSet | webhooks.Webhook | create | creator:_create_webhook | - |
| POST | `/api/v1/webhooks/webhooks/{id}/rotate_secret/` | WebhookViewSet | webhooks.Webhook | object | creator:_create_webhook | - |
| POST | `/api/v1/webhooks/webhooks/{id}/test/` | WebhookViewSet | webhooks.Webhook | object | creator:_create_webhook | - |
| PUT | `/api/v1/assets/{id}/` | AssetViewSet | assets.Asset | object | creator:_create_active_asset | - |
| PUT | `/api/v1/audit/event-retention-policies/{id}/` | AuditEventRetentionPolicyViewSet | audit.AuditEventRetentionPolicy | object | generic | - |
| PUT | `/api/v1/auth/api-keys/{id}/` | APIKeyViewSet | hub_auth.APIKey | object | generic | - |
| PUT | `/api/v1/baas/api-keys/{id}/` | APIKeyViewSet | hub_auth.APIKey | object | generic | - |
| PUT | `/api/v1/compliance/runs/{id}/` | ComplianceRunViewSet | compliance.ComplianceRun | object | creator:_create_compliance_run | - |
| PUT | `/api/v1/consent/consent-purposes/{id}/` | ConsentPurposeViewSet | consent.ConsentPurpose | object | generic | - |
| PUT | `/api/v1/contracts/{id}/` | ContractViewSet | contracts.Contract | object | generic | - |
| PUT | `/api/v1/data-movement/config/{pk}/` | DataMovementConfigViewSet | data_movement.DataMovementConfig | object | generic | - |
| PUT | `/api/v1/datasets/{id}/` | DatasetViewSet | datasets.Dataset | object | generic | - |
| PUT | `/api/v1/dpia/records/{pk}/` | DpiaViewSet | dpia.Dpia | object | generic | - |
| PUT | `/api/v1/dq/alerting-rules/{id}/` | DQAlertingRuleViewSet | dq.DQAlertingRule | object | creator:_create_dq_alerting_rule | - |
| PUT | `/api/v1/dq/runs/{id}/` | DQRunViewSet | dq.DQRun | object | creator:_create_dq_run | - |
| PUT | `/api/v1/files/{id}/` | FileViewSet | files.File | object | creator:_create_file | - |
| PUT | `/api/v1/governance/access-requests/{id}/` | AccessRequestViewSet | governance.AccessRequest | object | creator:_create_access_request | - |
| PUT | `/api/v1/governance/access/access-requests/{id}/` | AccessRequestViewSet | governance.AccessRequest | object | creator:_create_access_request | - |
| PUT | `/api/v1/governance/access/certifications/{id}/` | AccessCertificationViewSet | governance.AccessCertification | object | generic | - |
| PUT | `/api/v1/governance/access/retention-policies/{id}/` | RetentionPolicyViewSet | governance.RetentionPolicy | object | creator:_create_retention_policy | - |
| PUT | `/api/v1/governance/certifications/{id}/` | AccessCertificationViewSet | governance.AccessCertification | object | generic | - |
| PUT | `/api/v1/governance/retention-policies/{id}/` | RetentionPolicyViewSet | governance.RetentionPolicy | object | creator:_create_retention_policy | - |
| PUT | `/api/v1/integrations/marketplace/connections/{id}/` | MarketplaceConnectionViewSet | integrations.MarketplaceConnection | object | generic | - |
| PUT | `/api/v1/integrations/marketplace/sync/{id}/` | MarketplaceSyncJobViewSet | integrations.MarketplaceSyncJob | object | generic | - |
| PUT | `/api/v1/jobs/{id}/` | JobViewSet | jobs.Job | object | generic | - |
| PUT | `/api/v1/marketplace/config/trust-signals/{id}/` | TrustSignalConfigViewSet | marketplace.TrustSignalConfig | object | generic | - |
| PUT | `/api/v1/marketplace/listings/{id}/` | ListingViewSet | marketplace.Listing | object | creator:_create_published_listing | - |
| PUT | `/api/v1/marketplace/orders/{id}/` | OrderViewSet | marketplace.Order | object | creator:_create_order | - |
| PUT | `/api/v1/marketplace/saved-searches/{id}/` | SavedSearchViewSet | marketplace.SavedSearch | object | generic | - |
| PUT | `/api/v1/mesh/domains/{id}/` | DomainViewSet | mesh.DataMeshDomain | object | generic | - |
| PUT | `/api/v1/ml/models/{id}/` | MLModelViewSet | ml.MLModel | object | generic | - |
| PUT | `/api/v1/processor-agreements/processor-agreements/{id}/` | ProcessorAgreementViewSet | processor_agreements.ProcessorAgreement | object | generic | TENANT_ADMIN |
| PUT | `/api/v1/processor-agreements/processors/{id}/` | ProcessorViewSet | processor_agreements.Processor | object | generic | TENANT_ADMIN |
| PUT | `/api/v1/quality/runs/{id}/` | DeprecatedDQRunViewSet | dq.DQRun | object | creator:_create_dq_run | - |
| PUT | `/api/v1/scheduled-exports/{id}/` | ScheduledExportViewSet | scheduled_export.ScheduledExport | object | creator:_create_scheduled_export | - |
| PUT | `/api/v1/scheduled-ingestions/{id}/` | ScheduledIngestionViewSet | scheduled_ingestion.ScheduledIngestion | object | creator:_create_scheduled_ingestion | - |
| PUT | `/api/v1/semantic/ldn/subscriptions/{id}/` | LdnSubscriptionViewSet | semantic.LdnSubscription | object | generic | - |
| PUT | `/api/v1/semantic/ontologies/{id}/` | TenantOntologyViewSet | semantic.TenantOntology | object | generic | - |
| PUT | `/api/v1/tenants/{tenant_id}/sparql-endpoints/{pk}/` | TenantSparqlEndpointViewSet | semantic.TenantSparqlEndpoint | object | generic | - |
| PUT | `/api/v1/transformation/pipelines/{id}/` | TransformationPipelineViewSet | transformation.TransformationPipeline | object | creator:_create_transformation_pipeline | - |
| PUT | `/api/v1/transformation/wrangling/{id}/` | WranglingSessionViewSet | transformation.WranglingSession | object | generic | - |
| PUT | `/api/v1/users/{id}/` | UserViewSet | users.User | object | generic | - |
| PUT | `/api/v1/virtualization/datasets/{id}/` | VirtualDatasetViewSet | virtualization.VirtualDataset | object | creator:_create_virtual_dataset | - |
| PUT | `/api/v1/warehouses/acls/{id}/` | WarehouseConnectionACLViewSet | warehouses.WarehouseConnectionACL | object | generic | - |
| PUT | `/api/v1/warehouses/connections/{id}/` | WarehouseConnectionViewSet | warehouses.WarehouseConnection | object | generic | - |
| PUT | `/api/v1/webhooks/webhooks/{id}/` | WebhookViewSet | webhooks.Webhook | object | creator:_create_webhook | - |

### allowlist (2)

| Method | Path | Reason |
|---|---|---|
| POST | `/api/v1/contracts/products/` | The create executes the full ODPS product-creation workflow (schema validation chain + external workflow steps) and the payload carries no tenant-scoped FK reference surface, so neither the create half nor the payload-FK direction is probeable in the DB-only security job.  The tenant boundary for contract creation is pinned by the standard contract-create probe (POST /api/v1/contracts/) and the contracts IDOR suites (tests/security/test_idor_contracts.py). |
| POST | `/api/v1/databricks/workspaces/` | The create runs SSRF host validation with live DNS resolution — a synthetic probe hostname can never pass, and the payload carries no tenant-scoped FK reference surface for the payload-FK direction. The workspace object-level IDOR probes (GET/PATCH/DELETE detail routes) stay probed by the matrix. |

### platform_admin (20)

| Method | Path | View | Model |
|---|---|---|---|
| DELETE | `/api/v1/admin/tenants/{tenant_id}/` | AdminTenantDeleteView | - |
| GET | `/api/v1/admin/dashboard/summary/` | AdminDashboardSummaryView | - |
| GET | `/api/v1/admin/health/` | AdminHealthView | - |
| GET | `/api/v1/admin/tenants/{tenant_id}/feature-flags/` | AdminTenantFeatureFlagView | - |
| GET | `/api/v1/admin/tenants/{tenant_id}/onboarding-state/` | AdminTenantOnboardingStateView | - |
| GET | `/api/v1/billing/admin/cost-overview/` | CostOverviewView | - |
| GET | `/api/v1/platform/users/` | PlatformUserViewSet | users.User |
| GET | `/api/v1/platform/users/{id}/` | PlatformUserViewSet | users.User |
| GET | `/api/v1/platform/users/{id}/erasure-requests/` | PlatformUserViewSet | users.User |
| GET | `/api/v1/security/audit-logs/` | SecurityAuditLogViewSet | contracts.SecurityAuditLog |
| GET | `/api/v1/security/audit-logs/{pk}/` | SecurityAuditLogViewSet | contracts.SecurityAuditLog |
| GET | `/api/v1/tenants/{tenant_id}/rate-limits/` | RateLimitConfigView | - |
| PATCH | `/api/v1/tenants/{tenant_id}/rate-limits/` | RateLimitConfigView | - |
| POST | `/api/v1/admin/feature-flag-approvals/{approval_id}/approve/` | FeatureFlagFlipApprovalApproveView | - |
| POST | `/api/v1/admin/impersonate/` | AdminImpersonateStartView | - |
| POST | `/api/v1/admin/tenants/` | AdminTenantCreateView | - |
| POST | `/api/v1/billing/refunds/` | RefundViewSet | - |
| POST | `/api/v1/jobs/dlq/purge_resolved/` | FailedJobDLQViewSet | jobs.FailedJobDLQ |
| POST | `/api/v1/platform/users/{id}/request-erasure/` | PlatformUserViewSet | users.User |
| PUT | `/api/v1/admin/tenants/{tenant_id}/feature-flags/` | AdminTenantFeatureFlagView | - |

### no_tenant_fk (63)

| Method | Path | View | Model |
|---|---|---|---|
| DELETE | `/api/v1/billing/admin/plans/{pk}/` | PlanAdminViewSet | tenants.TenantPlan |
| DELETE | `/api/v1/developer/plugins/{id}/` | PluginViewSet | developer.Plugin |
| DELETE | `/api/v1/lineage/subscriptions/{id}/` | LineageSubscriptionViewSet | contracts.LineageSubscription |
| DELETE | `/api/v1/tenants/{id}/` | TenantViewSet | tenants.Tenant |
| GET | `/api/v1/baas/usage/` | APIUsageViewSet | baas.APIUsage |
| GET | `/api/v1/baas/usage/by-endpoint/` | APIUsageViewSet | baas.APIUsage |
| GET | `/api/v1/baas/usage/by-tenant/` | APIUsageViewSet | baas.APIUsage |
| GET | `/api/v1/baas/usage/stats/` | APIUsageViewSet | baas.APIUsage |
| GET | `/api/v1/baas/usage/{id}/` | APIUsageViewSet | baas.APIUsage |
| GET | `/api/v1/billing/admin/plans/` | PlanAdminViewSet | tenants.TenantPlan |
| GET | `/api/v1/billing/admin/plans/{pk}/` | PlanAdminViewSet | tenants.TenantPlan |
| GET | `/api/v1/billing/plans/` | PlansViewSet | tenants.TenantPlan |
| GET | `/api/v1/billing/plans/{pk}/` | PlansViewSet | tenants.TenantPlan |
| GET | `/api/v1/developer/documentation/` | DocumentationViewSet | developer.SDKDocumentation |
| GET | `/api/v1/developer/plugins/` | PluginViewSet | developer.Plugin |
| GET | `/api/v1/developer/plugins/marketplace/` | PluginViewSet | developer.Plugin |
| GET | `/api/v1/developer/plugins/marketplace/usage/` | PluginViewSet | developer.Plugin |
| GET | `/api/v1/developer/plugins/{id}/` | PluginViewSet | developer.Plugin |
| GET | `/api/v1/developer/sdk/` | SDKDocumentationViewSet | developer.SDKDocumentation |
| GET | `/api/v1/developer/sdk/{id}/` | SDKDocumentationViewSet | developer.SDKDocumentation |
| GET | `/api/v1/events/dlq/` | DLQListView | core.DeadLetterQueue |
| GET | `/api/v1/lineage/subscriptions/{id}/` | LineageSubscriptionViewSet | contracts.LineageSubscription |
| GET | `/api/v1/platform/tenants/` | PlatformTenantViewSet | tenants.Tenant |
| GET | `/api/v1/platform/tenants/usage/` | PlatformTenantViewSet | tenants.Tenant |
| GET | `/api/v1/platform/tenants/{id}/` | PlatformTenantViewSet | tenants.Tenant |
| GET | `/api/v1/scheduled-ingestions/runs/` | ScheduledIngestionRunViewSet | scheduled_ingestion.ScheduledIngestionRun |
| GET | `/api/v1/scheduled-ingestions/runs/{id}/` | ScheduledIngestionRunViewSet | scheduled_ingestion.ScheduledIngestionRun |
| GET | `/api/v1/tenants/{id}/` | TenantViewSet | tenants.Tenant |
| GET | `/api/v1/transformation/executions/` | PipelineExecutionViewSet | transformation.PipelineExecution |
| GET | `/api/v1/transformation/executions/{id}/` | PipelineExecutionViewSet | transformation.PipelineExecution |
| GET | `/api/v1/transformation/executions/{id}/progress/` | PipelineExecutionViewSet | transformation.PipelineExecution |
| GET | `/api/v1/transformation/executions/{id}/result/` | PipelineExecutionViewSet | transformation.PipelineExecution |
| GET | `/api/v1/virtualization/queries/` | QueryExecutionViewSet | virtualization.QueryExecution |
| GET | `/api/v1/virtualization/queries/{id}/` | QueryExecutionViewSet | virtualization.QueryExecution |
| GET | `/api/v1/virtualization/queries/{id}/progress/` | QueryExecutionViewSet | virtualization.QueryExecution |
| GET | `/api/v1/virtualization/queries/{id}/result/` | QueryExecutionViewSet | virtualization.QueryExecution |
| GET | `/api/v1/virtualization/queries/{id}/stream/` | QueryExecutionViewSet | virtualization.QueryExecution |
| GET | `/api/v1/webhooks/webhook-deliveries/` | WebhookDeliveryViewSet | webhooks.WebhookDelivery |
| GET | `/api/v1/webhooks/webhook-deliveries/{id}/` | WebhookDeliveryViewSet | webhooks.WebhookDelivery |
| GET | `/api/v1/workflows/{name}/` | WorkflowDetailView | orchestration.WorkflowDefinition |
| PATCH | `/api/v1/billing/admin/plans/{pk}/` | PlanAdminViewSet | tenants.TenantPlan |
| PATCH | `/api/v1/developer/plugins/{id}/` | PluginViewSet | developer.Plugin |
| PATCH | `/api/v1/lineage/subscriptions/{id}/` | LineageSubscriptionViewSet | contracts.LineageSubscription |
| PATCH | `/api/v1/tenants/{id}/` | TenantViewSet | tenants.Tenant |
| POST | `/api/v1/billing/admin/plans/` | PlanAdminViewSet | tenants.TenantPlan |
| POST | `/api/v1/developer/plugins/` | PluginViewSet | developer.Plugin |
| POST | `/api/v1/developer/plugins/install/` | PluginViewSet | developer.Plugin |
| POST | `/api/v1/developer/plugins/{id}/deploy/` | PluginViewSet | developer.Plugin |
| POST | `/api/v1/developer/plugins/{id}/execute/` | PluginViewSet | developer.Plugin |
| POST | `/api/v1/developer/plugins/{id}/publish/` | PluginViewSet | developer.Plugin |
| POST | `/api/v1/developer/plugins/{id}/test/` | PluginViewSet | developer.Plugin |
| POST | `/api/v1/developer/plugins/{id}/validate/` | PluginViewSet | developer.Plugin |
| POST | `/api/v1/platform/tenants/{id}/resume/` | PlatformTenantViewSet | tenants.Tenant |
| POST | `/api/v1/platform/tenants/{id}/suspend/` | PlatformTenantViewSet | tenants.Tenant |
| POST | `/api/v1/tenants/{id}/reactivate/` | TenantViewSet | tenants.Tenant |
| POST | `/api/v1/tenants/{id}/suspend/` | TenantViewSet | tenants.Tenant |
| POST | `/api/v1/transformation/executions/{id}/cancel/` | PipelineExecutionViewSet | transformation.PipelineExecution |
| POST | `/api/v1/virtualization/queries/{id}/cancel/` | QueryExecutionViewSet | virtualization.QueryExecution |
| POST | `/api/v1/webhooks/webhook-deliveries/{id}/retry/` | WebhookDeliveryViewSet | webhooks.WebhookDelivery |
| PUT | `/api/v1/billing/admin/plans/{pk}/` | PlanAdminViewSet | tenants.TenantPlan |
| PUT | `/api/v1/billing/admin/plans/{pk}/tier-profile/` | PlanAdminViewSet | tenants.TenantPlan |
| PUT | `/api/v1/developer/plugins/{id}/` | PluginViewSet | developer.Plugin |
| PUT | `/api/v1/tenants/{id}/` | TenantViewSet | tenants.Tenant |

### unresolved (257)

| Method | Path | View | Model |
|---|---|---|---|
| DELETE | `/api/v1/databricks/workspaces/{workspace_id}/dlt-pipelines/{pipeline_id}/` | DatabricksDltPipelineViewSet | - |
| DELETE | `/api/v1/databricks/workspaces/{workspace_id}/ml-assets/models/{model_id}/aliases/{alias}/` | DatabricksMlAssetViewSet | - |
| DELETE | `/api/v1/databricks/workspaces/{workspace_id}/ml-assets/serving-endpoints/{name}/` | DatabricksMlAssetViewSet | - |
| DELETE | `/api/v1/databricks/workspaces/{workspace_id}/ml-assets/tables/{table_id}/feature-tag/` | DatabricksMlAssetViewSet | - |
| DELETE | `/api/v1/drafts/delete/` | draft_delete | - |
| DELETE | `/api/v1/lineage/openlineage/keys/{pk}/` | openlineage_keys_detail_view | - |
| DELETE | `/api/v1/ml/inference/deployments/{pk}/` | InferenceViewSet | - |
| GET | `/api/csp-report/` | - | - |
| GET | `/api/v1/admin/connect/review-queue/` | connect_review_queue | - |
| GET | `/api/v1/ai/anomaly-detection/` | AnomalyDetectionViewSet | - |
| GET | `/api/v1/ai/anomaly-detection/config/` | AnomalyDetectionConfigViewSet | - |
| GET | `/api/v1/ai/classification/` | ClassificationViewSet | - |
| GET | `/api/v1/ai/classification/{pk}/` | ClassificationViewSet | - |
| GET | `/api/v1/ai/classification/{pk}/report/` | ClassificationViewSet | - |
| GET | `/api/v1/ai/recommendations/` | RecommendationsViewSet | - |
| GET | `/api/v1/ai/recommendations/model/` | RecommendationsViewSet | - |
| GET | `/api/v1/analytics/api/dashboard/` | APIAnalyticsViewSet | - |
| GET | `/api/v1/analytics/api/performance/` | APIAnalyticsViewSet | - |
| GET | `/api/v1/analytics/api/popular-endpoints/` | APIAnalyticsViewSet | - |
| GET | `/api/v1/analytics/api/usage-trends/` | APIAnalyticsViewSet | - |
| GET | `/api/v1/analytics/costs/` | CostsViewSet | - |
| GET | `/api/v1/analytics/costs/breakdown/` | CostsViewSet | - |
| GET | `/api/v1/analytics/costs/by-asset/` | CostsViewSet | - |
| GET | `/api/v1/analytics/costs/recommendations/` | CostsViewSet | - |
| GET | `/api/v1/analytics/costs/trends/` | CostsViewSet | - |
| GET | `/api/v1/audit/integrity/verify/` | AuditIntegrityVerifyView | - |
| GET | `/api/v1/auth/me/` | me | - |
| GET | `/api/v1/auth/me/tenants/` | me_tenants | - |
| GET | `/api/v1/auth/sessions/` | list_active_sessions | - |
| GET | `/api/v1/auth/sso/oidc/login-url/` | SSOViewSet | - |
| GET | `/api/v1/baas/docs/` | DeveloperDocumentationViewSet | - |
| GET | `/api/v1/baas/docs/openapi.json/` | DeveloperDocumentationViewSet | - |
| GET | `/api/v1/baas/docs/sdks/` | DeveloperDocumentationViewSet | - |
| GET | `/api/v1/baas/docs/sdks/{language}/` | DeveloperDocumentationViewSet | - |
| GET | `/api/v1/billing/connect/payouts/` | connect_payouts | - |
| GET | `/api/v1/billing/connect/status/` | connect_status | - |
| GET | `/api/v1/billing/public-pricing/` | public_pricing | - |
| GET | `/api/v1/billing/webhooks/stripe/` | - | - |
| GET | `/api/v1/breach/dashboard/` | breach_dashboard | - |
| GET | `/api/v1/breach/templates/catalog/` | breach_template_catalog | - |
| GET | `/api/v1/capabilities/` | capabilities_view | - |
| GET | `/api/v1/capabilities/manifest/` | capabilities_manifest_view | - |
| GET | `/api/v1/compliance/webhooks/completed/report/` | ComplianceWebhookReportSummaryView | - |
| GET | `/api/v1/consent/consent-dashboard/` | consent_dashboard | - |
| GET | `/api/v1/contracts/schema-editor/metrics/` | SchemaEditorMetricsView | - |
| GET | `/api/v1/contracts/{id}/download/` | - | - |
| GET | `/api/v1/contracts/{id}/export/` | - | - |
| GET | `/api/v1/contracts/{id}/lineage/visualization/` | - | - |
| GET | `/api/v1/data-movement/internal/config/{direction}/{resource_id}/` | - | - |
| GET | `/api/v1/databricks/budgets/` | BudgetViewSet | - |
| GET | `/api/v1/databricks/delta-sharing/profile/` | DeltaSharingProtocolViewSet | - |
| GET | `/api/v1/databricks/delta-sharing/shares/` | DeltaSharingProtocolViewSet | - |
| GET | `/api/v1/databricks/delta-sharing/shares/{share}/` | DeltaSharingProtocolViewSet | - |
| GET | `/api/v1/databricks/delta-sharing/shares/{share}/schemas/` | DeltaSharingProtocolViewSet | - |
| GET | `/api/v1/databricks/delta-sharing/shares/{share}/schemas/{schema}/tables/` | DeltaSharingProtocolViewSet | - |
| GET | `/api/v1/databricks/delta-sharing/shares/{share}/schemas/{schema}/tables/{table}/` | DeltaSharingProtocolViewSet | - |
| GET | `/api/v1/databricks/delta-sharing/shares/{share}/schemas/{schema}/tables/{table}/metadata/` | DeltaSharingProtocolViewSet | - |
| GET | `/api/v1/databricks/delta-sharing/shares/{share}/schemas/{schema}/tables/{table}/version/` | DeltaSharingProtocolViewSet | - |
| GET | `/api/v1/databricks/estate-summary/` | AccountEstateViewSet | - |
| GET | `/api/v1/databricks/sso/login-url/` | DatabricksSSOViewSet | - |
| GET | `/api/v1/databricks/sso/session/` | DatabricksSSOViewSet | - |
| GET | `/api/v1/databricks/sso/workspaces/` | DatabricksSSOViewSet | - |
| GET | `/api/v1/databricks/uc/changes/pending-approvals/` | UCApprovalInboxViewSet | - |
| GET | `/api/v1/databricks/workspaces/{workspace_id}/credentials/` | CredentialViewSet | - |
| GET | `/api/v1/databricks/workspaces/{workspace_id}/dlt-pipelines/` | DatabricksDltPipelineViewSet | - |
| GET | `/api/v1/databricks/workspaces/{workspace_id}/jobs/` | DatabricksJobViewSet | - |
| GET | `/api/v1/databricks/workspaces/{workspace_id}/jobs/{job_id}/runs/` | DatabricksJobViewSet | - |
| GET | `/api/v1/databricks/workspaces/{workspace_id}/ml-assets/feature-tables/` | DatabricksMlAssetViewSet | - |
| GET | `/api/v1/databricks/workspaces/{workspace_id}/ml-assets/models/` | DatabricksMlAssetViewSet | - |
| GET | `/api/v1/databricks/workspaces/{workspace_id}/ml-assets/serving-endpoints/` | DatabricksMlAssetViewSet | - |
| GET | `/api/v1/databricks/workspaces/{workspace_id}/ml-assets/vector-search-endpoints/` | DatabricksMlAssetViewSet | - |
| GET | `/api/v1/databricks/workspaces/{workspace_id}/sql-warehouses/` | SqlWarehouseViewSet | - |
| GET | `/api/v1/databricks/workspaces/{workspace_id}/uc/catalogs/` | UCBrowseViewSet | - |
| GET | `/api/v1/databricks/workspaces/{workspace_id}/uc/catalogs/{catalog_id}/schemas/` | UCBrowseViewSet | - |
| GET | `/api/v1/databricks/workspaces/{workspace_id}/uc/changes/` | UCChangeRequestViewSet | - |
| GET | `/api/v1/databricks/workspaces/{workspace_id}/uc/changes/{pk}/` | UCChangeRequestViewSet | - |
| GET | `/api/v1/databricks/workspaces/{workspace_id}/uc/changes/{pk}/comments/` | UCChangeRequestViewSet | - |
| GET | `/api/v1/databricks/workspaces/{workspace_id}/uc/changes/{pk}/timeline/` | UCChangeRequestViewSet | - |
| GET | `/api/v1/databricks/workspaces/{workspace_id}/uc/external-locations/` | UCBrowseViewSet | - |
| GET | `/api/v1/databricks/workspaces/{workspace_id}/uc/schemas/{schema_id}/models/` | UCBrowseViewSet | - |
| GET | `/api/v1/databricks/workspaces/{workspace_id}/uc/schemas/{schema_id}/tables/` | UCBrowseViewSet | - |
| GET | `/api/v1/databricks/workspaces/{workspace_id}/uc/schemas/{schema_id}/views/` | UCBrowseViewSet | - |
| GET | `/api/v1/databricks/workspaces/{workspace_id}/uc/schemas/{schema_id}/volumes/` | UCBrowseViewSet | - |
| GET | `/api/v1/databricks/workspaces/{workspace_id}/uc/storage-credentials/` | UCBrowseViewSet | - |
| GET | `/api/v1/databricks/workspaces/{workspace_id}/uc/tables/{table_id}/` | UCBrowseViewSet | - |
| GET | `/api/v1/developer/api-keys/` | APIKeysViewSet | - |
| GET | `/api/v1/developer/portal/` | PortalViewSet | - |
| GET | `/api/v1/dq/quality/anomalies/` | DQQualityViewSet | - |
| GET | `/api/v1/dq/quality/root_cause_analysis/` | DQQualityViewSet | - |
| GET | `/api/v1/dq/quality/scorecards/` | DQQualityViewSet | - |
| GET | `/api/v1/dq/quality/trends/` | DQQualityViewSet | - |
| GET | `/api/v1/governance/access/analytics/anomalies/` | AccessAnalyticsViewSet | - |
| GET | `/api/v1/governance/access/analytics/dashboard/` | AccessAnalyticsViewSet | - |
| GET | `/api/v1/governance/access/analytics/patterns/` | AccessAnalyticsViewSet | - |
| GET | `/api/v1/governance/access/analytics/security-events/` | AccessAnalyticsViewSet | - |
| GET | `/api/v1/governance/analytics/anomalies/` | AccessAnalyticsViewSet | - |
| GET | `/api/v1/governance/analytics/dashboard/` | AccessAnalyticsViewSet | - |
| GET | `/api/v1/governance/analytics/patterns/` | AccessAnalyticsViewSet | - |
| GET | `/api/v1/governance/analytics/security-events/` | AccessAnalyticsViewSet | - |
| GET | `/api/v1/health/business-rules/` | - | - |
| GET | `/api/v1/integrations/federated-import/imports/{job_id}/` | FederatedImportViewSet | - |
| GET | `/api/v1/integrations/federated-import/providers/` | FederatedImportViewSet | - |
| GET | `/api/v1/integrations/marketplace/connectors/` | list_connectors | - |
| GET | `/api/v1/integrations/marketplace/connectors/{connector_type}/` | get_connector_info | - |
| GET | `/api/v1/lineage/openlineage/keys/` | openlineage_keys_collection_view | - |
| GET | `/api/v1/marketplace/listings/{id}/download/` | - | - |
| GET | `/api/v1/marketplace/payment-gateways/list/` | PaymentGatewayViewSet | - |
| GET | `/api/v1/marketplace/payment-gateways/webhook-url/` | PaymentGatewayViewSet | - |
| GET | `/api/v1/marketplace/webhooks/stripe/` | - | - |
| GET | `/api/v1/mesh/governance/` | MeshGovernanceViewSet | - |
| GET | `/api/v1/mesh/governance/compliance/` | MeshGovernanceViewSet | - |
| GET | `/api/v1/mesh/governance/policies/` | MeshGovernanceViewSet | - |
| GET | `/api/v1/mesh/governance/reports/` | MeshGovernanceViewSet | - |
| GET | `/api/v1/mesh/topology/` | TopologyViewSet | - |
| GET | `/api/v1/mesh/topology/health/` | TopologyViewSet | - |
| GET | `/api/v1/mesh/topology/relationships/` | TopologyViewSet | - |
| GET | `/api/v1/mesh/topology/{pk}/` | TopologyViewSet | - |
| GET | `/api/v1/ml/inference/deployments/` | InferenceViewSet | - |
| GET | `/api/v1/ml/inference/deployments/{pk}/` | InferenceViewSet | - |
| GET | `/api/v1/ml/inference/deployments/{pk}/metrics/` | InferenceViewSet | - |
| GET | `/api/v1/ml/training/jobs/` | TrainingJobViewSet | - |
| GET | `/api/v1/ml/training/jobs/{pk}/` | TrainingJobViewSet | - |
| GET | `/api/v1/ml/training/jobs/{pk}/logs/` | TrainingJobViewSet | - |
| GET | `/api/v1/notifications/stream/` | NotificationStreamView | - |
| GET | `/api/v1/notifications/unsubscribe/{token}/` | - | - |
| GET | `/api/v1/observability/freshness/` | ObservabilityViewSet | - |
| GET | `/api/v1/observability/freshness/stale/` | ObservabilityViewSet | - |
| GET | `/api/v1/observability/incidents/` | ObservabilityViewSet | - |
| GET | `/api/v1/observability/lineage/` | ObservabilityViewSet | - |
| GET | `/api/v1/observability/pipelines/` | ObservabilityViewSet | - |
| GET | `/api/v1/observability/schema-drift/` | ObservabilityViewSet | - |
| GET | `/api/v1/observability/slas/` | ObservabilityViewSet | - |
| GET | `/api/v1/observability/volume/` | ObservabilityViewSet | - |
| GET | `/api/v1/openapi.json/` | OpenAPISchemaView | - |
| GET | `/api/v1/openapi.yaml/` | OpenAPIYAMLView | - |
| GET | `/api/v1/public/dsar-requests/status/{reference_token}/` | PublicDsarStatusByTokenView | - |
| GET | `/api/v1/quality/anomalies/` | DeprecatedDQQualityViewSet | - |
| GET | `/api/v1/quality/root-cause-analysis/` | DeprecatedDQQualityViewSet | - |
| GET | `/api/v1/quality/scorecards/` | DeprecatedDQQualityViewSet | - |
| GET | `/api/v1/quality/trends/` | DeprecatedDQQualityViewSet | - |
| GET | `/api/v1/scheduled-exports/internal/config/{scheduled_export_id}/` | InternalConfigView | - |
| GET | `/api/v1/scheduled-ingestions/internal/config/{scheduled_ingestion_id}/` | InternalConfigView | - |
| GET | `/api/v1/scheduled-ingestions/internal/test-data/{filename}/` | InternalTestDataView | - |
| GET | `/api/v1/search/analytics/` | SearchViewSet | - |
| GET | `/api/v1/search/search/` | SearchViewSet | - |
| GET | `/api/v1/search/suggestions/` | SearchViewSet | - |
| GET | `/api/v1/semantic/context.jsonld/` | get_jsonld_context | - |
| GET | `/api/v1/semantic/context/` | get_jsonld_context | - |
| GET | `/api/v1/semantic/graphql/` | SemanticGraphQLView | - |
| GET | `/api/v1/semantic/id/field/{asset_uuid}/{field_name}/` | resolve_field_uri | - |
| GET | `/api/v1/semantic/id/{resource_type}/{resource_id}/` | resolve_uri | - |
| GET | `/api/v1/semantic/ldn/inbox/{tenant_id}/` | ldn_inbox_list | - |
| GET | `/api/v1/semantic/ldn/inbox/{tenant_id}/{inbox_id}/` | ldn_inbox_detail | - |
| GET | `/api/v1/semantic/ontology/` | get_ontology | - |
| GET | `/api/v1/semantic/relationships/{contract_id}/` | contract_relationships | - |
| GET | `/api/v1/semantic/resource/{resource_type}/{resource_id}/` | dereference_resource | - |
| GET | `/api/v1/semantic/resource/{resource_type}/{resource_id}/timemap/` | semantic_timemap | - |
| GET | `/api/v1/semantic/resource/{resource_type}/{resource_id}/version/{snapshot_at}/` | dereference_versioned_resource | - |
| GET | `/api/v1/semantic/sparql/` | sparql_query | - |
| GET | `/api/v1/semantic/sparql/description/` | sparql_service_description | - |
| GET | `/api/v1/social/activity-feeds/` | ActivityFeedViewSet | - |
| GET | `/api/v1/social/audit/reports/` | SocialAuditViewSet | - |
| GET | `/api/v1/versioning/compare/` | VersioningViewSet | - |
| GET | `/api/v1/versioning/versions/` | VersioningViewSet | - |
| GET | `/api/v1/versioning/versions/compare/` | VersioningViewSet | - |
| GET | `/api/v1/versioning/versions/{pk}/` | VersioningViewSet | - |
| GET | `/api/v1/virtualization/topology/` | VirtualizationTopologyViewSet | - |
| GET | `/api/v1/virtualization/topology/{pk}/` | VirtualizationTopologyViewSet | - |
| GET | `/api/v1/warehouses/query/` | LiveQueryViewSet | - |
| PATCH | `/api/v1/ai/classification/{pk}/rules/` | ClassificationViewSet | - |
| PATCH | `/api/v1/auth/me/` | me | - |
| PATCH | `/api/v1/observability/incidents/update/` | ObservabilityViewSet | - |
| PATCH | `/api/v1/scheduled-exports/internal/runs/{pk}/` | InternalRunViewSet | - |
| PATCH | `/api/v1/scheduled-ingestions/internal/runs/{pk}/` | InternalRunViewSet | - |
| POST | `/api/v1/admin/impersonate/exit/` | AdminImpersonateExitView | - |
| POST | `/api/v1/ai/anomaly-detection/train/` | AnomalyDetectionViewSet | - |
| POST | `/api/v1/ai/classification/{pk}/validate/` | ClassificationViewSet | - |
| POST | `/api/v1/ai/natural-language-search/` | AIViewSet | - |
| POST | `/api/v1/ai/recommendations/feedback/` | RecommendationsViewSet | - |
| POST | `/api/v1/ai/schema-matching/` | AIViewSet | - |
| POST | `/api/v1/ai/schema-matching/acceptance-rules/` | AIViewSet | - |
| POST | `/api/v1/auth/accept-invitation/` | accept_invitation | - |
| POST | `/api/v1/auth/login/` | login | - |
| POST | `/api/v1/auth/logout/` | logout | - |
| POST | `/api/v1/auth/password-reset/` | password_reset_request | - |
| POST | `/api/v1/auth/password-reset/confirm/` | password_reset_confirm | - |
| POST | `/api/v1/auth/refresh/` | refresh_token | - |
| POST | `/api/v1/auth/register/` | register | - |
| POST | `/api/v1/auth/resend-verification/` | resend_verification_email | - |
| POST | `/api/v1/auth/sessions/end-all-others/` | end_all_other_sessions | - |
| POST | `/api/v1/auth/sessions/{session_id}/revoke/` | revoke_session | - |
| POST | `/api/v1/auth/sso/oidc/callback/` | SSOViewSet | - |
| POST | `/api/v1/auth/switch-tenant/` | switch_tenant | - |
| POST | `/api/v1/auth/verify-email/` | verify_email | - |
| POST | `/api/v1/billing/connect/onboarding-link/` | connect_onboarding_link | - |
| POST | `/api/v1/contracts/schema-editor/metrics/` | SchemaEditorMetricsLegacyNoSlashView | - |
| POST | `/api/v1/databricks/accounts/` | AccountProvisioningViewSet | - |
| POST | `/api/v1/databricks/accounts/{pk}/metastores/` | AccountProvisioningViewSet | - |
| POST | `/api/v1/databricks/accounts/{pk}/workspaces/` | AccountProvisioningViewSet | - |
| POST | `/api/v1/databricks/delta-sharing/shares/{share}/schemas/{schema}/tables/{table}/query/` | DeltaSharingProtocolViewSet | - |
| POST | `/api/v1/databricks/sso/callback/` | DatabricksSSOViewSet | - |
| POST | `/api/v1/databricks/workspaces/{workspace_id}/credentials/` | CredentialViewSet | - |
| POST | `/api/v1/databricks/workspaces/{workspace_id}/credentials/{pk}/rotate/` | CredentialViewSet | - |
| POST | `/api/v1/databricks/workspaces/{workspace_id}/dlt-pipelines/` | DatabricksDltPipelineViewSet | - |
| POST | `/api/v1/databricks/workspaces/{workspace_id}/dlt-pipelines/{pipeline_id}/start/` | DatabricksDltPipelineViewSet | - |
| POST | `/api/v1/databricks/workspaces/{workspace_id}/dlt-pipelines/{pipeline_id}/stop/` | DatabricksDltPipelineViewSet | - |
| POST | `/api/v1/databricks/workspaces/{workspace_id}/ml-assets/models/` | DatabricksMlAssetViewSet | - |
| POST | `/api/v1/databricks/workspaces/{workspace_id}/ml-assets/models/{model_id}/versions/` | DatabricksMlAssetViewSet | - |
| POST | `/api/v1/databricks/workspaces/{workspace_id}/ml-assets/serving-endpoints/` | DatabricksMlAssetViewSet | - |
| POST | `/api/v1/databricks/workspaces/{workspace_id}/ml-assets/tables/{table_id}/feature-tag/` | DatabricksMlAssetViewSet | - |
| POST | `/api/v1/databricks/workspaces/{workspace_id}/ml-assets/vector-search-endpoints/` | DatabricksMlAssetViewSet | - |
| POST | `/api/v1/databricks/workspaces/{workspace_id}/sql-warehouses/{warehouse_id}/start/` | SqlWarehouseViewSet | - |
| POST | `/api/v1/databricks/workspaces/{workspace_id}/sql-warehouses/{warehouse_id}/stop/` | SqlWarehouseViewSet | - |
| POST | `/api/v1/databricks/workspaces/{workspace_id}/uc/changes/` | UCChangeRequestViewSet | - |
| POST | `/api/v1/databricks/workspaces/{workspace_id}/uc/changes/{pk}/approve/` | UCChangeRequestViewSet | - |
| POST | `/api/v1/databricks/workspaces/{workspace_id}/uc/changes/{pk}/comments/` | UCChangeRequestViewSet | - |
| POST | `/api/v1/databricks/workspaces/{workspace_id}/uc/changes/{pk}/reject/` | UCChangeRequestViewSet | - |
| POST | `/api/v1/databricks/workspaces/{workspace_id}/uc/changes/{pk}/submit/` | UCChangeRequestViewSet | - |
| POST | `/api/v1/developer/api-keys/` | APIKeysViewSet | - |
| POST | `/api/v1/events/dlq/{dlq_id}/resolve/` | DLQResolveView | - |
| POST | `/api/v1/events/dlq/{dlq_id}/retry/` | DLQRetryView | - |
| POST | `/api/v1/events/replay/` | replay_events | - |
| POST | `/api/v1/integrations/federated-import/imports/` | FederatedImportViewSet | - |
| POST | `/api/v1/integrations/federated-import/imports/{job_id}/cancel/` | FederatedImportViewSet | - |
| POST | `/api/v1/lineage/openlineage/events/` | openlineage_events_view | - |
| POST | `/api/v1/lineage/openlineage/keys/` | openlineage_keys_collection_view | - |
| POST | `/api/v1/marketplace/payment-gateways/link-webhook/` | PaymentGatewayViewSet | - |
| POST | `/api/v1/ml/inference/deployments/` | InferenceViewSet | - |
| POST | `/api/v1/ml/inference/deployments/predict/` | InferenceViewSet | - |
| POST | `/api/v1/ml/training/jobs/` | TrainingJobViewSet | - |
| POST | `/api/v1/ml/training/jobs/{pk}/cancel/` | TrainingJobViewSet | - |
| POST | `/api/v1/observability/incidents/` | ObservabilityViewSet | - |
| POST | `/api/v1/observability/metrics/` | ObservabilityViewSet | - |
| POST | `/api/v1/observability/schema-drift/detect/` | ObservabilityViewSet | - |
| POST | `/api/v1/observability/volume/aggregate/` | ObservabilityViewSet | - |
| POST | `/api/v1/public/dsar-requests/` | PublicDsarSubmitView | - |
| POST | `/api/v1/public/dsar-requests/{dsar_id}/verify-otp/` | PublicDsarVerifyOtpView | - |
| POST | `/api/v1/scheduled-exports/internal/process-export/` | InternalProcessExportView | - |
| POST | `/api/v1/scheduled-exports/internal/runs/` | InternalRunViewSet | - |
| POST | `/api/v1/scheduled-exports/internal/runs/{pk}/cancel/` | InternalRunViewSet | - |
| POST | `/api/v1/scheduled-ingestions/internal/jobs/` | InternalCreateJobView | - |
| POST | `/api/v1/scheduled-ingestions/internal/process-file/` | InternalProcessFileView | - |
| POST | `/api/v1/scheduled-ingestions/internal/runs/` | InternalRunViewSet | - |
| POST | `/api/v1/scheduled-ingestions/internal/runs/{pk}/cancel/` | InternalRunViewSet | - |
| POST | `/api/v1/search/rebuild_index/` | SearchViewSet | - |
| POST | `/api/v1/search/track_click/` | SearchViewSet | - |
| POST | `/api/v1/semantic/export/` | rdf_export | - |
| POST | `/api/v1/semantic/graphql/` | SemanticGraphQLView | - |
| POST | `/api/v1/semantic/ldn/inbox/{tenant_id}/` | ldn_inbox_post | - |
| POST | `/api/v1/semantic/rdf/ingest/` | rdf_ingest | - |
| POST | `/api/v1/semantic/sparql/` | sparql_query | - |
| POST | `/api/v1/social/activity-feeds/{pk}/moderate/` | ActivityFeedViewSet | - |
| POST | `/api/v1/tenants/ephemeral/` | ephemeral_tenant | - |
| POST | `/api/v1/workflows/{name}/trigger/` | WorkflowTriggerView | - |
| PUT | `/api/v1/databricks/workspaces/{workspace_id}/dlt-pipelines/{pipeline_id}/` | DatabricksDltPipelineViewSet | - |
| PUT | `/api/v1/databricks/workspaces/{workspace_id}/ml-assets/models/{model_id}/aliases/{alias}/` | DatabricksMlAssetViewSet | - |
| PUT | `/api/v1/drafts/save/` | draft_save | - |
