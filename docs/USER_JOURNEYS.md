# User Journey Index

**Last Updated**: 2026-05-16 | **Source**: `docs/PRODUCT_GUIDE.md`, `docs/CRITICAL_UC_JOURNEY_IDS.yaml`  
**YAML Registry**: `docs/CRITICAL_UC_JOURNEY_IDS.yaml`  
**Total journeys**: 42

---

## Table of User Journeys

| ID | Title | Persona(s) | Phase |
|---|---|---|---|
| JOURNEY-AUTH-001 | First-Time Visitor Registers | DC | Phase 11 |
| JOURNEY-AUTH-002 | User Logs In | All | Phase 11 |
| JOURNEY-AUTH-003 | User Resets Password | All | Phase 11 |
| JOURNEY-AUTH-004 | Unauthenticated User Accesses Public Resources | DC (visitor) | Phase 11 |
| JOURNEY-DPO-001 | Onboard New Asset via Data-First Flow | DPO | Phase 250 |
| JOURNEY-DPO-002 | Publish Asset to Marketplace | DPO | Phase 250 |
| JOURNEY-DPO-003 | Manage Asset Lifecycle | DPO | Phase 250 |
| JOURNEY-DPO-004 | Monitor Asset Quality | DPO | Phase 240 |
| JOURNEY-DPO-005 | Configure Data Contracts | DPO | Phase 227 |
| JOURNEY-DPO-006 | Manage Marketplace Listings | DPO | Phase 231 |
| JOURNEY-DPO-007 | Import Data from External Provider (Federated Import) | DPO | Phase 284 |
| JOURNEY-DE-001 | Programmatic Contract-First Onboarding | DE | Phase 227 |
| JOURNEY-DE-003 | Configure Data Quality Checks | DE | Phase 240 |
| JOURNEY-DE-004 | Set Up Compliance Scanning | DE | Phase 231 |
| JOURNEY-DE-005 | Upload and Activate Custom Ontology | DE | Phase 284 |
| JOURNEY-DE-006 | Manage LDN Inbox Subscriptions | DE | Phase 284 |
| JOURNEY-CPO-001 | Run Compliance Scan for Asset | CPO | Phase 231 |
| JOURNEY-CPO-006 | Configure Automated Compliance | CPO | Phase 232 |
| JOURNEY-CPO-007 | Execute GDPR Right to be Forgotten | CPO | Phase 232 |
| JOURNEY-CPO-008 | Manage Consent Tracking | CPO | Phase 232 |
| JOURNEY-CPO-009 | Configure Automated Retention | CPO | Phase 232 |
| JOURNEY-CPO-010 | Review Retention Reports | CPO | Phase 232 |
| JOURNEY-CPO-011 | Approval Inbox Flow (Unified Governance) | CPO | Phase 278 |
| JOURNEY-CPO-012 | Complete DPIA Assessment Wizard | CPO | Phase 284 |
| JOURNEY-CPO-013 | Generate and Export Record of Processing Activities (RoPA) | CPO | Phase 232 |
| JOURNEY-CPO-014 | Manage Processor Agreement Lifecycle | CPO | Phase 232 |
| JOURNEY-CPO-015 | Submit and Track DSAR Request | CPO | Phase 232 |
| JOURNEY-CPO-016 | Report and Resolve Data Breach | CPO | Phase 284 |
| JOURNEY-DC-001 | Discover and Purchase Asset | DC | Phase 231 |
| JOURNEY-DC-002 | Marketplace Discovery Flow | DC | Phase 278 |
| JOURNEY-DC-003 | Browse Resource Version History | DC | Phase 284 |
| JOURNEY-DC-004 | Search Catalogue with Semantic Facets | DC | Phase 284 |
| JOURNEY-DEV-001 | External Developer Marketplace Browsing | DEV | Phase 278 |
| JOURNEY-DEV-010 | Query via GraphQL-LD Endpoint | DEV | Phase 284 |
| JOURNEY-TA-007 | Monitor Cost Tracking | MPA | Phase 234 |
| JOURNEY-TA-008 | Configure Integration Ecosystem | MPA | Phase 234 |
| JOURNEY-PA-001 | Onboard Marketplace Instance | MPA | Phase 231 |
| JOURNEY-MPA-005 | Marketplace Admin Journey | MPA | Phase 231 |
| JOURNEY-INGESTION-001 | Create and Run Scheduled Ingestion | DE | Phase 25 |
| JOURNEY-INGESTION-003 | Edit and Delete Scheduled Ingestion | DE | Phase 25 |
| JOURNEY-EXPORT-001 | Create and Run Scheduled Export | DE | Phase 25 |
| JOURNEY-EXPORT-002 | Monitor and Troubleshoot Export Runs | DE | Phase 25 |
| JOURNEY-DEV-008 | Use Plugin System | DEV / DE | Phase 278 |
| JOURNEY-DEV-009 | Integrate with Developer Portal | DEV | Phase 278 |

---

## Persona Key

| Abbreviation | Persona |
|---|---|
| DPO | Data Product Owner |
| DE | Data Engineer |
| DC | Data Consumer |
| CPO | Compliance & Privacy Officer |
| MPA | Marketplace Platform Admin |
| DEV | External Developer |
| All | All 6 personas |

---

## Phase Key

Journeys are organized by the phase in which they were first implemented:

| Phase | What Shipped |
|---|---|
| Phase 11 | Auth (login, register, password reset, JWT) |
| Phase 25 | Scheduled ingestion & export (Prefect orchestration) |
| Phase 227 | Contract normalization + structureless migration |
| Phase 231 | Marketplace listings, compliance runs, entitlements |
| Phase 232 | GDPR (DSAR, erasure, consent, retention), DPIA, RoPA |
| Phase 234 | Billing, cost tracking, audit retention |
| Phase 240 | Data quality (DQ runs, anomalies, trends, scorecards) |
| Phase 250 | Asset data-first flow, asset activation |
| Phase 278 | UX activation (tenant pill, sync banner, destructive confirm, inbox, HelpTip, error UX) |
| Phase 284 | GA promotions: federated import, GraphQL-LD, semantic search, custom ontology, LDN, DPIA, breach, versioning |

## Maintenance

When adding a new user journey:
1. Document the journey in `docs/PRODUCT_GUIDE.md` or a dedicated file
2. Add a row to the table above
3. If the journey is critical for CI traceability, add its ID to `docs/CRITICAL_UC_JOURNEY_IDS.yaml`

**Last reviewed**: 2026-05-13 | **Next review**: 2026-08-11
