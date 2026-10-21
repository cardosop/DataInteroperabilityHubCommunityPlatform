# Tenant Deletion Coverage

**Total tenant-scoped models**: 32
**Covered by tenant_hard_delete_sweep**: 2
**Gaps**: 30

## Gaps — Models without deletion path

- `assets.Asset` (`assets`)
- `assets.ExternalResourceReference` (`external_resource_references`)
- `audit.AuditEvent` (`audit_events`)
- `audit.AuditEventRetentionPolicy` (`audit_event_retention_policies`)
- `audit.AuditMerkleSnapshot` (`audit_merkle_snapshots`)
- `auth.RefreshToken` (`refresh_tokens`)
- `baas.APIUsage` (`baas_api_usage`)
- `baas.BaaSUsageRecord` (`baas_usage_record`)
- `billing.ConnectAccount` (`connect_accounts`)
- `billing.UsageRecord` (`usage_records`)
- `contracts.SecurityAuditLog` (`security_audit_logs`)
- `databricks_admin.DatabricksAccount` (`databricks_accounts`)
- `databricks_admin.DatabricksCostBudget` (`databricks_cost_budgets`)
- `databricks_admin.DatabricksCredential` (`databricks_credentials`)
- `databricks_admin.DatabricksOBOToken` (`databricks_obo_tokens`)
- `databricks_admin.DatabricksUserBinding` (`databricks_user_bindings`)
- `databricks_admin.DeltaShareRecipient` (`databricks_delta_share_recipients`)
- `databricks_admin.DeltaShareToken` (`databricks_delta_share_tokens`)
- `dpia.Dpia` (`dpia`)
- `marketplace.SavedSearch` (`marketplace_saved_search`)
- `mesh.DataMeshDomain` (`data_mesh_domains`)
- `processor_agreements.AssetProcessorMembership` (`pa_asset_processor`)
- `processor_agreements.Processor` (`pa_processor`)
- `scheduled_ingestion.ScheduledIngestion` (`scheduled_ingestions`)
- `semantic.LdnPartnerKey` (`semantic_ldn_partner_keys`)
- `semantic.LdnTenantSigningKey` (`semantic_ldn_signing_keys`)
- `semantic.SemanticResourceVersion` (`semantic_resource_versions`)
- `semantic.TenantOntology` (`semantic_tenant_ontologies`)
- `tenants.FeatureFlagFlipApproval` (`feature_flag_flip_approvals`)
- `users.UserTenantMembership` (`user_tenant_memberships`)

## Covered Models

- `jobs.Job` (`jobs`)
- `tenants.Tenant` (`tenants`)