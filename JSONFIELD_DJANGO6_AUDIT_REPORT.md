================================================================================
JSONField Django 6 Compatibility Audit Report
================================================================================

Total JSONField declarations found: 26

================================================================================
JSONField Declarations by File
================================================================================


File: hub/apps/audit/models.py
  Total JSONFields: 1
    - AuditEvent.details_json (line 61)
      → Consider adding db_index=True for GIN index support (Django 6)

File: hub/apps/auth/models.py
  Total JSONFields: 1
    - APIKey.scopes (line 44)
      → Consider adding db_index=True for GIN index support (Django 6)

File: hub/apps/compliance/models.py
  Total JSONFields: 4
    - ComplianceRun.regulations (line 71)
      → Consider adding db_index=True for GIN index support (Django 6)
    - ComplianceRun.detected_categories_json (line 100)
      → Consider adding db_index=True for GIN index support (Django 6)
    - ComplianceRun.column_findings_json (line 105)
      → Consider adding db_index=True for GIN index support (Django 6)
    - ComplianceRun.regulation_mapping_json (line 110)
      → Consider adding db_index=True for GIN index support (Django 6)

File: hub/apps/contracts/models.py
  Total JSONFields: 5
    - Contract.hub_contract_json (line 105)
      → Consider adding db_index=True for GIN index support (Django 6)
    - Contract.normalization_errors (line 118)
      → Consider adding db_index=True for GIN index support (Django 6)
    - Contract.normalization_warnings (line 124)
      → Consider adding db_index=True for GIN index support (Django 6)
    - Contract.validation_errors (line 139)
      → Consider adding db_index=True for GIN index support (Django 6)
    - Contract.validation_warnings (line 145)
      → Consider adding db_index=True for GIN index support (Django 6)

File: hub/apps/datasets/models.py
  Total JSONFields: 2
    - Dataset.schema_json (line 48)
      → Consider adding db_index=True for GIN index support (Django 6)
    - Dataset.sample_data_json (line 53)
      → Consider adding db_index=True for GIN index support (Django 6)

File: hub/apps/dq/models.py
  Total JSONFields: 2
    - DQRun.checks_json (line 94)
      → Consider adding db_index=True for GIN index support (Django 6)
    - DQRun.details_json (line 99)
      → Consider adding db_index=True for GIN index support (Django 6)

File: hub/apps/files/models.py
  Total JSONFields: 1
    - File.metadata_json (line 65)
      → Consider adding db_index=True for GIN index support (Django 6)

File: hub/apps/jobs/models.py
  Total JSONFields: 2
    - Job.result_json (line 86)
      → Consider adding db_index=True for GIN index support (Django 6)
    - Job.details_json (line 92)
      → Consider adding db_index=True for GIN index support (Django 6)

File: hub/apps/marketplace/models.py
  Total JSONFields: 3
    - Listing.metadata_json (line 60)
      → Consider adding db_index=True for GIN index support (Django 6)
    - Order.metadata_json (line 226)
      → Consider adding db_index=True for GIN index support (Django 6)
    - Entitlement.metadata_json (line 389)
      → Consider adding db_index=True for GIN index support (Django 6)

File: hub/apps/notifications/models.py
  Total JSONFields: 1
    - EmailDelivery.metadata_json (line 98)
      → Consider adding db_index=True for GIN index support (Django 6)

File: hub/apps/semantic/models.py
  Total JSONFields: 1
    - SemanticResource.metadata_json (line 71)
      → Consider adding db_index=True for GIN index support (Django 6)

File: hub/apps/tenants/models.py
  Total JSONFields: 3
    - TenantConfig.allowed_compliance_regimes (line 155)
      → Consider adding db_index=True for GIN index support (Django 6)
    - TenantConfig.default_compliance_regimes (line 160)
      → Consider adding db_index=True for GIN index support (Django 6)
    - TenantConfig.rate_limits (line 178)
      → Consider adding db_index=True for GIN index support (Django 6)

================================================================================
Statistics
================================================================================

Files with JSONField: 12
Total JSONField declarations: 26

================================================================================
Django 6 Optimization Recommendations
================================================================================

1. Consider adding db_index=True for frequently queried JSONFields
2. Review default values - use callable defaults for mutable types
3. Use JSONField(db_index=True) for GIN indexes on PostgreSQL
4. Leverage Django 6's improved JSONField query syntax
5. Review encoder/decoder usage - Django 6 has better defaults