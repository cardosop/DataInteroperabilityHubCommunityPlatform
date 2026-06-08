# Factory File Audit

**Date:** 2026-05-21
**Scope:** 9 project factory files; 8 app-level + 1 central.
**Methodology:** Each factory file was read for line count, class count, cross-app imports, and model coverage. Usage counts from grep across test files.

---

## Summary

| Factory File | Lines | Classes | Models Covered | Cross-App Imports |
|---|---|---|---|---|
| `tests/factories.py` | 645 | 54 | 54 | All (central) |
| `hub/apps/contracts/tests/factories.py` | 355 | 1 | 1 | assets, tenants |
| `hub/apps/datasets/tests/factories.py` | 299 | 1 | 1 | assets, files, tenants |
| `hub/apps/files/tests/factories.py` | 151 | 1 | 1 | files, tenants |
| `hub/apps/scheduled_ingestion/tests/factories.py` | 147 | 2 | 2 | assets, tenants |
| `hub/apps/assets/tests/factories.py` | 130 | 1 | 1 | assets, tenants |
| `hub/apps/versioning/tests/factories.py` | 120 | 2 | 2 | datasets, tenants |
| `hub/apps/marketplace/tests/factories.py` | 27 | 0 | 0 | marketplace |
| `hub/apps/core/tests/factories.py` | 18 | 0 | 0 | core |
| **Total** | **1,892** | **62** | **62** | |

---

## 1. Central Factory: `tests/factories.py`

### Overview

The central factory file (645 lines, 54 factory classes) uses `factory_boy` (`DjangoModelFactory`) and covers models across **22 apps**:

- **Core models:** Tenant, TenantConfig, TenantPlan, User
- **Data models:** Asset, Contract, Dataset, File
- **Marketplace:** Listing, Order, PaymentTransaction, Entitlement
- **Billing:** Subscription, Invoice, UsageRecord
- **Governance:** AccessPolicy, AccessRequest, AccessRequestComment, ApprovalDelegation
- **Compliance:** ComplianceRun
- **Jobs:** Job
- **Notifications:** EmailDelivery
- **Webhooks:** Webhook, WebhookDelivery
- **Data Mesh:** DataMeshDomain, PolicyApplication, ComplianceReport
- **ML:** MLModel, MLModelVersion, ABTest
- **Scheduled:** ScheduledIngestion, ScheduledIngestionRun, ScheduledExport, ScheduledExportRun
- **DQ:** DqRun, DqRuleResult
- **Transformation:** TransformationPipeline, PipelineExecution
- **Virtualization:** VirtualDataset
- **Lineage:** LineageEdge
- **Workflows:** WorkflowDefinition, WorkflowInstance, WorkflowStep
- **Audit:** AuditEvent
- **Auth:** APIKey
- **Users:** UserRole
- **GDPR:** ErasureRequest, DataExportJob
- **Integrations:** MarketplaceMapping, MarketplaceSyncJob, MarketplaceConnection, ExternalResourceReference

### Factory Patterns

All factories follow `factory_boy` conventions:
```python
class XxxFactory(DjangoModelFactory):
    class Meta:
        model = Xxx
        django_get_or_create = ("field",)
```

---

## 2. App-Level Factories vs Central Factory — Duplication Map

### 2.1 `hub/apps/contracts/tests/factories.py` (355 lines)

- **`ContractFactoryEnhanced`** — Creates contracts with complete `hub_contract_json` including owners, tags, quality rules, compliance policy, lifecycle policy, marketplace policy, and schema fields.
- **Cross-app deps:** `hub.apps.tenants.models.Tenant`, `hub.apps.assets.models.Asset`
- **Duplication with central:** Central `ContractFactory` (in `tests/factories.py`) creates basic contracts. `ContractFactoryEnhanced` creates contracts with full section JSON. **Partially overlapping** — the enhanced factory provides fuller fixtures but the basic contract creation is duplicated.
- **Recommendation:** Move `ContractFactoryEnhanced` logic into central `ContractFactory` as optional parameters.

### 2.2 `hub/apps/datasets/tests/factories.py` (299 lines)

- **`DatasetFactory`** — Creates Dataset instances with schema, sample data, row counts.
- **Cross-app deps:** `hub.apps.tenants.models.Tenant`, `hub.apps.assets.models.Asset`, `hub.apps.files.models.File`
- **Duplication with central:** Central has `DatasetFactory` (simple). App-level has richer `create_dataset()` static method. **Partially overlapping.**
- **Recommendation:** Merge enhanced creation into central factory.

### 2.3 `hub/apps/files/tests/factories.py` (151 lines)

- **`FileFactory`** — File creation with upload, size, format simulation.
- **Cross-app deps:** `hub.apps.tenants.models.Tenant`
- **Duplication with central:** Central has `FileFactory` using `factory_boy`. App-level uses static methods. **Duplicated model coverage.**

### 2.4 `hub/apps/scheduled_ingestion/tests/factories.py` (147 lines)

- **`ScheduledIngestionFactory`** + **`ScheduledIngestionRunFactory`**
- **Cross-app deps:** `hub.apps.tenants.models.Tenant`, `hub.apps.assets.models.Asset`
- **Duplication with central:** Central covers both models. App-level adds richer configuration. **Partially overlapping.**

### 2.5 `hub/apps/assets/tests/factories.py` (130 lines)

- Single factory class for Asset.
- **Cross-app deps:** `hub.apps.tenants.models.Tenant`
- **Duplication with central:** Central has `AssetFactory`. App-level provides asset with full metadata. **Duplicated model.**

### 2.6 `hub/apps/versioning/tests/factories.py` (120 lines)

- **`DatasetVersionFactory`** + **`ContractVersionFactory`** — Versioning-specific factories.
- **Cross-app deps:** `hub.apps.datasets.models.Dataset`, `hub.apps.tenants.models.Tenant`
- **Duplication with central:** Not covered in central. **Unique — candidate for promotion to central.**

### 2.7 `hub/apps/marketplace/tests/factories.py` (27 lines)

- No factory classes defined — helpers/utilities only.
- **Recommendation:** Either add factories or merge into central.

### 2.8 `hub/apps/core/tests/factories.py` (18 lines)

- No factory classes defined — minimal helpers.
- **Recommendation:** Either expand or delete (central covers these models).

---

## 3. Cross-App Dependency Graph

```
tests/factories.py (central)
  imports from: hub.apps.{tenants,assets,contracts,datasets,files,marketplace,
                          billing,jobs,compliance,governance,notifications,
                          webhooks,mesh,ml,scheduled_ingestion,scheduled_export,
                          dq,transformation,virtualization,lineage,workflows,
                          audit,auth,users,gdpr,integrations}

hub/apps/contracts/tests/factories.py
  imports from: hub.apps.contracts, hub.apps.tenants, hub.apps.assets

hub/apps/datasets/tests/factories.py
  imports from: hub.apps.datasets, hub.apps.tenants, hub.apps.assets, hub.apps.files

hub/apps/files/tests/factories.py
  imports from: hub.apps.files, hub.apps.tenants

hub/apps/scheduled_ingestion/tests/factories.py
  imports from: hub.apps.assets, hub.apps.tenants

hub/apps/assets/tests/factories.py
  imports from: hub.apps.assets, hub.apps.tenants

hub/apps/versioning/tests/factories.py
  imports from: hub.apps.datasets, hub.apps.tenants

hub/apps/marketplace/tests/factories.py
  imports from: hub.apps.marketplace

hub/apps/core/tests/factories.py
  imports from: hub.apps.core
```

**Most common cross-app dependency:** `hub.apps.tenants` (7 out of 8 app factories import it). This is expected — Tenant is the root entity for RLS-scoped models.

---

## 4. Factory Patterns Used

| Pattern | Used By | Notes |
|---|---|---|
| `factory_boy` (`DjangoModelFactory`) | `tests/factories.py` | Industry standard, supports `build()`/`create()` |
| Static method factories | All app-level factories | `create_xxx()` pattern, no `factory_boy` integration |
| Custom `Factory` classes | contracts, datasets, files | Non-standard, no `.build()` support |
| `Faker` integration | `tests/factories.py` | Uses `Faker()` for realistic test data |

**Key finding:** App-level factories use static methods (`ContractFactoryEnhanced.create_hub_contract_json()`) while central factory uses `factory_boy`. These are **two incompatible patterns** — app factories can't be chained with `factory_boy`'s `SubFactory` or `RelatedFactory`.

---

## 5. Consolidation Candidates

### High Priority — Duplicated Model Coverage

| Model | Central (`tests/factories.py`) | App-Level | Action |
|---|---|---|---|
| Asset | `AssetFactory` | `hub/apps/assets/tests/factories.py` | Merge app factory into central |
| Contract | `ContractFactory` | `hub/apps/contracts/tests/factories.py` | Merge `ContractFactoryEnhanced` into central |
| Dataset | `DatasetFactory` | `hub/apps/datasets/tests/factories.py` | Merge into central |
| File | `FileFactory` | `hub/apps/files/tests/factories.py` | Merge into central |
| ScheduledIngestion | `ScheduledIngestionFactory` | `hub/apps/scheduled_ingestion/tests/factories.py` | Merge into central |

### Medium Priority — Promote to Central

| Model | Current Location | Action |
|---|---|---|
| DatasetVersion | `hub/apps/versioning/tests/factories.py` | Promote to central |
| ContractVersion | `hub/apps/versioning/tests/factories.py` | Promote to central |

### Low Priority — Delete or Expand

| File | Lines | Action |
|---|---|---|
| `hub/apps/marketplace/tests/factories.py` | 27 | Delete (no factories) or add factories |
| `hub/apps/core/tests/factories.py` | 18 | Delete (no factories) |

---

## 6. Factory Usage Across Tests

| Factory | Approximate Test References |
|---|---|
| `TenantFactory` | 200+ (most-used factory) |
| `AssetFactory` | 150+ |
| `User` (get_user_model) | 100+ |
| `ContractFactory` | 80+ |
| `DatasetFactory` | 60+ |
| `FileFactory` | 50+ |
| All others | 10-40 each |

---

## Recommendations

1. **Consolidate all app-level factories into `tests/factories.py`** — eliminate the 8 app-level factory files (~1,247 lines). The central factory already covers all models.
2. **Convert static method factories to `factory_boy`** — app-level factories use non-standard `create_xxx()` static methods instead of `factory_boy`. Convert for consistency and to enable `SubFactory`/`RelatedFactory` chaining.
3. **Delete `hub/apps/marketplace/tests/factories.py` and `hub/apps/core/tests/factories.py`** — no factory classes defined.
4. **Promote `versioning` factories to central** — `DatasetVersionFactory` and `ContractVersionFactory` have no central equivalent.
5. **Add `build()` support to all factories** — some app-level factories only support `create()`, making them unsuitable for unit tests that don't need DB.
6. **Run `scripts/lint_factory_coverage.py`** (existing) to verify model coverage after consolidation.
