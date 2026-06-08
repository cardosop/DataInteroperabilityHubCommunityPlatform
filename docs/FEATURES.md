# Meshant Feature Index

**Date:** 2026-05-16
**Scope:** All 27 per-tenant feature flags (26 GA + 1 CANARY)
**Audit:** Phase 285.3.3 — cross-referenced with USE_CASES.md, USER_JOURNEYS.md, PRODUCT_GUIDE.md, runbooks

## Persona Key

| Alias | Persona | Primary Goal | Technical Level |
|-------|---------|-------------|-----------------|
| **DPO** | Data Protection Officer | Ensure data protection, privacy, and regulatory compliance | Low–Medium |
| **DE** | Data Engineer | Build and maintain data pipelines and quality | High |
| **CPO** | Chief Product Officer | Product strategy, cost oversight, marketplace health | Medium |
| **DC** | Data Consumer | Discover, access, and use data products | Variable |
| **MPA** | Marketplace & Platform Admin | Manage tenants, billing, platform ops | Medium |
| **DEV** | External Developer | Integrate via API, CLI, or SDK | High |

## Stage Key

| Stage | Meaning |
|-------|---------|
| **GA** | Generally Available — production-ready, scored on 13-gate rubric |
| **CANARY** | Canary — released to friendly tenants for soak |
| **DRAFT** | Draft — code path exists, not yet released to tenants |
| **DEPRECATED** | Deprecated — marked for removal |
| **RETIRED** | Retired — code path and flag removed |

## Feature Table

### Data Quality

| Feature | Flag | Stage | Default New | Personas | Journeys | Runbook |
|---------|------|-------|-------------|----------|----------|---------|
| Data Quality | `data_quality_enabled` | GA | True | DE, DPO, CPO | JOURNEY-DPO-004, JOURNEY-DE-003 | [data-quality.md](runbooks/data-quality.md) |
| Advanced Data Quality | `data_quality_advanced_enabled` | GA | True | DE, CPO | JOURNEY-DPO-004 | [data-quality.md](runbooks/data-quality.md) |

### Asset Creation

| Feature | Flag | Stage | Default New | Personas | Journeys | Runbook |
|---------|------|-------|-------------|----------|----------|---------|
| Asset Creation | `asset_creation_enabled` | GA | True | DE, DPO, CPO | JOURNEY-DPO-001, JOURNEY-DE-001 | [asset-creation.md](runbooks/asset-creation.md) |
| Fail-Closed Compliance Gate | `compliance_fail_closed_enabled` | GA (sensitive) | True | DPO, CPO, MPA | JOURNEY-DPO-001 | [RB-COMP-001-compliance-fail-closed.md](runbooks/RB-COMP-001-compliance-fail-closed.md) |
| Asset Auto-Activate on Gate Pass | `asset_auto_activate_on_gate_pass` | GA | True | DE, DPO | JOURNEY-DPO-001 | [asset-creation.md](runbooks/asset-creation.md) |
| Compliance Intake Gate | `compliance_intake_gate_enabled` | GA (sensitive) | False | DPO, CPO, MPA | JOURNEY-DPO-001, JOURNEY-CPO-001 | [compliance-intake-gate.md](runbooks/compliance-intake-gate.md) |
| Allow Intake on Compliance Degraded | `allow_intake_on_compliance_degraded` | CANARY (sensitive) | False | MPA | — | [compliance-intake-gate.md](runbooks/compliance-intake-gate.md) |

### Data Plane

| Feature | Flag | Stage | Default New | Personas | Journeys | Runbook |
|---------|------|-------|-------------|----------|----------|---------|
| Datasets | `datasets_enabled` | GA | True | DE, DC, DEV | JOURNEY-DE-001 | [datasets-files-dr.md](runbooks/datasets-files-dr.md) |
| Files | `files_enabled` | GA | True | DE, DC, DEV | JOURNEY-DPO-001 | [datasets-files-dr.md](runbooks/datasets-files-dr.md) |

### Compliance — Privacy Programme

| Feature | Flag | Stage | Default New | Personas | Journeys | Runbook |
|---------|------|-------|-------------|----------|----------|---------|
| Consent Management | `compliance_consent_enabled` | GA | True | DPO, CPO, DC | JOURNEY-CPO-008, JOURNEY-DPO-008 | [RB-COMP-002-consent.md](runbooks/RB-COMP-002-consent.md) |
| DSAR (Data Subject Access Requests) | `compliance_dsar_enabled` | GA | True | DPO, CPO, DC | JOURNEY-CPO-007, JOURNEY-DPO-007 | [phase232-dsar.md](runbooks/phase232-dsar.md) |
| Breach Notification | `compliance_breach_enabled` | GA | True | DPO, CPO, MPA | JOURNEY-CPO-011 | [RB-COMP-004-breach.md](runbooks/RB-COMP-004-breach.md) |
| RoPA (Record of Processing Activities) | `compliance_ropa_enabled` | GA | True | DPO, CPO | JOURNEY-CPO-001 | [phase232-ropa.md](runbooks/phase232-ropa.md) |
| DPIA (Data Protection Impact Assessment) | `compliance_dpia_enabled` | GA | False | DPO, CPO | JOURNEY-CPO-012 | [RB-COMP-005-dpia.md](runbooks/RB-COMP-005-dpia.md) |
| Processor Agreements | `compliance_processor_agreements_enabled` | GA | False | DPO, CPO, MPA | — | [phase232-compliance-programme.md](runbooks/phase232-compliance-programme.md) |
| Retention Enforcer | `compliance_retention_enforcer_enabled` | GA | False | DPO, CPO | JOURNEY-CPO-009, JOURNEY-CPO-010, JOURNEY-DPO-009, JOURNEY-DPO-010 | [file-retention.md](runbooks/file-retention.md) |
| Audit Full Sampling | `compliance_audit_full_sampling` | GA (sensitive) | False | DPO, MPA | — | RB-FLAG-003 (created, needs operational content) |

### Semantic / Knowledge Graph

| Feature | Flag | Stage | Default New | Personas | Journeys | Runbook |
|---------|------|-------|-------------|----------|----------|---------|
| Memento (Versioned Snapshots) | `semantic_memento_enabled` | GA | False | DE, DEV | — | [semantic-memento.md](runbooks/semantic-memento.md) |
| OWL/RDFS Inference | `semantic_inference_enabled` | GA | False | DE, DEV | — | [semantic-inference.md](runbooks/semantic-inference.md) |
| Custom Ontologies | `semantic_custom_ontology_enabled` | GA | False | DE, DEV | — | [semantic-ontology.md](runbooks/semantic-ontology.md) |
| Linked Data Notifications (LDN) | `semantic_ldn_enabled` | GA | False | DE, DEV | — | [semantic-ldn.md](runbooks/semantic-ldn.md) |
| Semantic Search | `semantic_search_enabled` | GA | False | DC, DE, DEV | JOURNEY-DC-002 | — (no dedicated runbook) |
| GraphQL-LD | `semantic_graphql_ld_enabled` | GA | False | DE, DEV | — | [RB-SEM-001-graphql-ld.md](runbooks/RB-SEM-001-graphql-ld.md) |

### Marketplace & Catalogue

| Feature | Flag | Stage | Default New | Personas | Journeys | Runbook |
|---------|------|-------|-------------|----------|----------|---------|
| Trust Signals | `trust_signals_enabled` | GA | True | DC, CPO, MPA | JOURNEY-DC-002 | RB-FLAG-001 (created, needs operational content) |
| Federated Import | `federated_import_enabled` | GA | False | DE, MPA | — | [RB-COMP-006-federated-import.md](runbooks/RB-COMP-006-federated-import.md) |

### Platform Operations

| Feature | Flag | Stage | Default New | Personas | Journeys | Runbook |
|---------|------|-------|-------------|----------|----------|---------|
| Versioning | `versioning_enabled` | GA | True | DE, DEV, MPA | — | [dataset-version-compare-failure.md](runbooks/dataset-version-compare-failure.md) (partial; RB-FLAG-008 created) |
| Workflows | `workflows_enabled` | GA | True | DE, DEV | JOURNEY-DE-016, JOURNEY-INGESTION-001, JOURNEY-EXPORT-001 | [workflow-dr.md](runbooks/workflow-dr.md), [workflow-stuck.md](runbooks/workflow-stuck.md) (RB-FLAG-002 created) |

## Feature Count by Stage

| Stage | Count | Flags |
|-------|-------|-------|
| GA (default-on for new tenants) | 14 | data_quality, data_quality_advanced, asset_creation, compliance_fail_closed, asset_auto_activate, datasets, files, compliance_consent, compliance_dsar, compliance_breach, compliance_ropa, trust_signals, versioning, workflows |
| GA (opt-in for new tenants) | 12 | compliance_intake_gate, compliance_dpia, compliance_processor_agreements, compliance_retention_enforcer, compliance_audit_full_sampling, semantic_memento, semantic_inference, semantic_custom_ontology, semantic_ldn, semantic_search, semantic_graphql_ld, federated_import |
| CANARY | 1 | allow_intake_on_compliance_degraded |
| **Total** | **27** | |

## Feature Count by Persona

| Persona | Feature Count | Primary Features |
|---------|---------------|-----------------|
| **DPO** (Data Protection Officer) | 17 | All compliance/privacy flags, DQ, asset creation, datasets, files |
| **DE** (Data Engineer) | 18 | Asset creation, DQ, data plane, semantic, versioning, workflows, federated import |
| **CPO** (Chief Product Officer) | 14 | All compliance flags, DQ, marketplace, trust signals |
| **DC** (Data Consumer) | 8 | Datasets, files, marketplace, trust signals, consent, DSAR, semantic search |
| **MPA** (Marketplace & Platform Admin) | 12 | Fail-closed, intake gate, federated import, breach, processor agreements, audit, versioning |
| **DEV** (External Developer) | 13 | Datasets, files, semantic (all 6), versioning, workflows |

## Sensitive Flags (Two-Person Rule, Phase 235.1)

These flags require two PLATFORM_ADMIN approvals to flip:

| Flag | Blast Radius |
|------|-------------|
| `compliance_fail_closed_enabled` | Disabling masks fail-closed rejection posture — non-compliant assets can enter catalogue |
| `compliance_intake_gate_enabled` | Disabling skips intake compliance scan — assets activate without gate clearance |
| `compliance_audit_full_sampling` | Flipping to sampled mode hides per-read forensics |
| `allow_intake_on_compliance_degraded` | Emergency override — allows intake when compliance circuit is OPEN |

## Cross-References

- **USE_CASES.md** — Functional use cases organised by persona and domain
- **USER_JOURNEYS.md** — Step-by-step journey specifications with acceptance criteria
- **CRITICAL_UC_JOURNEY_IDS.yaml** — Machine-readable critical journey ID registry
- **PRODUCT_GUIDE.md** — Product architecture, feature descriptions, configuration
- **FRONTEND_GUIDE.md** — Frontend architecture, component catalogue, design system
- **[runbooks/](runbooks/)** — Operational runbooks with triage matrices and escalation paths
- **[runbooks/INDEX.md](runbooks/INDEX.md)** — Runbook index by category
- **[ga-readiness-audit-2026-05.md](ga-readiness-audit-2026-05.md)** — 13-gate unified GA readiness audit with per-flag scores
- **[mvpdocs/concepts/governance.md](mvpdocs/concepts/governance.md)** — Governance ABAC + multi-step approval architecture
- **[mvpdocs/personas/_persona-overview.md](mvpdocs/personas/_persona-overview.md)** — Detailed persona profiles and documentation

## Maintenance

- **Owner:** Platform Engineering
- **Update triggers:** After any flag stage promotion, new flag addition, or feature retirement
- **Sync with:** `hub/apps/tenants/feature_flag_registry.py` (canonical flag source), `CLAUDE.md` (flag counts)
