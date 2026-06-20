# User Journey Index

**Last Updated**: 2026-06-17 | **Source**: `docs/PRODUCT_GUIDE.md`, `docs/CRITICAL_UC_JOURNEY_IDS.yaml`, `frontend/e2e/journeys/`  
**YAML Registry**: `docs/CRITICAL_UC_JOURNEY_IDS.yaml`  
**Total journeys**: 149

---

## Table of User Journeys

### Authentication (Persona: Visitor / All)
| ID | Title | Persona(s) | Phase |
|---|---|---|---|
| JOURNEY-AUTH-001 | First-Time Visitor Registers | DC | Phase 11 |
| JOURNEY-AUTH-002 | User Logs In | All | Phase 11 |
| JOURNEY-AUTH-003 | User Resets Password | All | Phase 11 |
| JOURNEY-AUTH-004 | Unauthenticated User Accesses Public Resources | DC (visitor) | Phase 11 |
| JOURNEY-AUTH-005 | Invitation Accept | DC / DE | Phase 11 |
| JOURNEY-AUTH-006 | SSO Login | DE / DEV | Phase 11 |
| JOURNEY-AUTH-007 | Tenant Switch | DE / DC | Phase 11 |

### Data Product Owner (Persona: DPO)
| ID | Title | Persona(s) | Phase |
|---|---|---|---|
| JOURNEY-DPO-001 | Onboard New Asset via Data-First Flow | DPO | Phase 250 |
| JOURNEY-DPO-002 | Publish Asset to Marketplace | DPO | Phase 250 |
| JOURNEY-DPO-003 | Manage Asset Lifecycle | DPO | Phase 250 |
| JOURNEY-DPO-004 | Monitor Asset Quality | DPO | Phase 240 |
| JOURNEY-DPO-005 | Configure Data Contracts | DPO | Phase 227 |
| JOURNEY-DPO-006 | Manage Marketplace Listings | DPO | Phase 231 |
| JOURNEY-DPO-007 | Import Data from External Provider (Federated Import) | DPO | Phase 284 |
| JOURNEY-DPO-008 | Create Transformation Pipeline for Asset | DPO | Phase 115A |
| JOURNEY-DPO-009 | Manage Ratings and Reviews | DPO | Phase 278 |
| JOURNEY-DPO-010 | Configure Usage-Based Pricing | DPO | Phase 231 |
| JOURNEY-DPO-011 | Assign Data Stewards | DPO | Phase 278 |
| JOURNEY-DPO-012 | Join Data Community | DPO | Phase 278 |
| JOURNEY-DPO-013 | Configure Data Mesh Domain | DPO | Phase 284 |
| JOURNEY-DPO-014 | Monitor Reliability Score | DPO | Phase 284 |
| JOURNEY-DPO-015 | Create ODPS Product | DPO | Phase 227 |
| JOURNEY-DPO-016 | Link ODPS to ODCS | DPO | Phase 227 |
| JOURNEY-DPO-017 | Export ODPS Product | DPO | Phase 227 |
| JOURNEY-DPO-018 | Edit Dataset and Link to Asset | DPO | Phase 250 |

### Data Engineer (Persona: DE)
| ID | Title | Persona(s) | Phase |
|---|---|---|---|
| JOURNEY-DE-001 | Programmatic Contract-First Onboarding | DE | Phase 227 |
| JOURNEY-DE-002 | Set Up Scheduled Ingestion | DE | Phase 25 |
| JOURNEY-DE-003 | Configure Data Quality Checks | DE | Phase 240 |
| JOURNEY-DE-004 | Set Up Compliance Scanning | DE | Phase 231 |
| JOURNEY-DE-005 | Upload and Activate Custom Ontology | DE | Phase 284 |
| JOURNEY-DE-006 | Manage LDN Inbox Subscriptions | DE | Phase 284 |
| JOURNEY-DE-007 | Create Transformation Pipeline | DE | Phase 115A |
| JOURNEY-DE-008 | AI Schema Matching Integration | DE | Phase 284 |
| JOURNEY-DE-009 | Configure Data Virtualization | DE | Phase 284 |
| JOURNEY-DE-010 | Configure Data Connector | DE | Phase 234 |
| JOURNEY-DE-011 | Set Up Reverse ETL | DE | Phase 284 |
| JOURNEY-DE-012 | Create Custom Plugin | DE | Phase 278 |
| JOURNEY-DE-013 | Configure Mesh Domain (Engineer) | DE | Phase 284 |
| JOURNEY-DE-014 | Create ODPS Product via API | DE | Phase 227 |
| JOURNEY-DE-015 | Upload File via Files Page | DE | Phase 250 |

### Compliance & Privacy Officer (Persona: CPO)
| ID | Title | Persona(s) | Phase |
|---|---|---|---|
| JOURNEY-CPO-001 | Run Compliance Scan for Asset | CPO | Phase 231 |
| JOURNEY-CPO-002 | Generate Compliance Report | CPO | Phase 231 |
| JOURNEY-CPO-003 | Review Access Request | CPO | Phase 232 |
| JOURNEY-CPO-004 | Review Access Requests (Batch) | CPO | Phase 232 |
| JOURNEY-CPO-005 | Audit Access Logs | CPO | Phase 232 |
| JOURNEY-CPO-006 | Configure Automated Compliance | CPO | Phase 232 |
| JOURNEY-CPO-007 | Execute GDPR Right to be Forgotten | CPO | Phase 232 |
| JOURNEY-CPO-008 | Manage Consent Tracking | CPO | Phase 232 |
| JOURNEY-CPO-009 | Configure Automated Retention | CPO | Phase 232 |
| JOURNEY-CPO-010 | Review AI Auto-Classification Results | CPO | Phase 232 |
| JOURNEY-CPO-011 | Approval Inbox Flow (Unified Governance) | CPO | Phase 278 | (Planned) |
| JOURNEY-CPO-012 | Complete DPIA Assessment Wizard | CPO | Phase 284 | (Planned) |
| JOURNEY-CPO-013 | Generate and Export Record of Processing Activities (RoPA) | CPO | Phase 232 | (Planned) |
| JOURNEY-CPO-014 | Manage Processor Agreement Lifecycle | CPO | Phase 232 | (Planned) |
| JOURNEY-CPO-015 | Submit and Track DSAR Request | CPO | Phase 232 |
| JOURNEY-CPO-016 | Report and Resolve Data Breach | CPO | Phase 284 | (Planned) |

### Data Consumer (Persona: DC)
| ID | Title | Persona(s) | Phase |
|---|---|---|---|
| JOURNEY-DC-001 | Discover and Purchase Asset | DC | Phase 231 |
| JOURNEY-DC-002 | Marketplace Discovery Flow | DC | Phase 278 |
| JOURNEY-DC-003 | Browse Resource Version History | DC | Phase 284 |
| JOURNEY-DC-004 | Search Catalogue with Semantic Facets | DC | Phase 284 |
| JOURNEY-DC-005 | View Entitlements | DC | Phase 231 |
| JOURNEY-DC-006 | Natural Language Search | DC | Phase 284 |
| JOURNEY-DC-007 | Create Transformation Pipeline for Data | DC | Phase 115A |
| JOURNEY-DC-008 | Rate and Review Purchased Asset | DC | Phase 278 |
| JOURNEY-DC-009 | Join Data Community | DC | Phase 278 |
| JOURNEY-DC-010 | Query Virtual Dataset | DC | Phase 284 |
| JOURNEY-DC-011 | Usage-Based Purchase | DC | Phase 231 |
| JOURNEY-DC-012 | Preview Data Before Purchase | DC | Phase 231 |
| JOURNEY-DC-013 | View Asset Recommendations | DC | Phase 284 |
| JOURNEY-DC-014 | Discover ODPS Product (Semantic) | DC | Phase 284 |
| JOURNEY-DC-015 | Purchase ODPS Product | DC | Phase 231 |

### Tenant Admin (Persona: TA)
| ID | Title | Persona(s) | Phase |
|---|---|---|---|
| JOURNEY-TA-001 | Onboard New User | TA | Phase 11 |
| JOURNEY-TA-002 | Manage User Roles | TA | Phase 11 |
| JOURNEY-TA-003 | Monitor Tenant Usage | TA | Phase 234 |
| JOURNEY-TA-004 | Manage Tenant Billing | TA | Phase 234 |
| JOURNEY-TA-005 | Configure Mesh Domains (Admin) | TA | Phase 284 |
| JOURNEY-TA-006 | Advanced Governance Configuration | TA | Phase 232 |
| JOURNEY-TA-007 | Monitor Cost Tracking | TA | Phase 234 |
| JOURNEY-TA-008 | Configure Integration Ecosystem | TA | Phase 234 |
| JOURNEY-TA-SUBSCRIPTION | Manage Subscription | TA | Phase 234 |
| JOURNEY-TA-TENANT-SETTINGS | Configure Tenant Settings | TA | Phase 234 |
| JOURNEY-TA-BILLING-UPGRADE | Upgrade Billing Plan | TA | Phase 234 |

### Platform Admin / Marketplace Admin (Persona: PA / MPA)
| ID | Title | Persona(s) | Phase |
|---|---|---|---|
| JOURNEY-PA-001 | Onboard Marketplace Instance | MPA | Phase 231 |
| JOURNEY-PA-002 | Manage Tenant KYC Status | MPA | Phase 231 | (Frontend spec only) |
| JOURNEY-PA-003 | Configure Platform Settings | MPA | Phase 231 | (Frontend spec only) |
| JOURNEY-PA-004 | Review Platform Analytics | MPA | Phase 231 | (Frontend spec only) |
| JOURNEY-PA-005 | Manage Marketplace Configuration | MPA | Phase 231 | (Frontend spec only) |
| JOURNEY-PA-006 | Monitor Marketplace Health | MPA | Phase 231 | (Frontend spec only) |
| JOURNEY-PA-007 | Manage ODPS Products (Platform) | MPA | Phase 227 | (Frontend spec only) |
| JOURNEY-PA-008 | Configure External Marketplace Connections | MPA | Phase 231 | (Frontend spec only) |
| JOURNEY-PA-009 | Manage Federated Assets | MPA | Phase 284 | (Frontend spec only) |
| JOURNEY-PA-010 | Manage ODPS Products (Platform) | MPA | Phase 227 |
| JOURNEY-PA-015 | Platform Admin Operations | MPA | Phase 231 | (Frontend spec only) |
| JOURNEY-MPA-001 | Process Marketplace Orders | MPA | Phase 231 |
| JOURNEY-MPA-002 | Manage Marketplace Listings (Admin) | MPA | Phase 231 |
| JOURNEY-MPA-003 | Monitor Platform Health | MPA | Phase 231 |
| JOURNEY-MPA-004 | Configure Platform Settings | MPA | Phase 231 |
| JOURNEY-MPA-005 | Connector Marketplace Management | MPA | Phase 231 |
| JOURNEY-MPA-006 | Advanced Marketplace Configuration | MPA | Phase 231 |
| JOURNEY-MPA-007 | Monitor Mesh Topology | MPA | Phase 284 |
| JOURNEY-MPA-008 | Advanced Observability | MPA | Phase 284 |
| JOURNEY-MPA-009 | Plugin Marketplace Management | MPA | Phase 278 |

### External Developer (Persona: DEV)
| ID | Title | Persona(s) | Phase |
|---|---|---|---|
| JOURNEY-DEV-001 | External Developer Marketplace Browsing | DEV | Phase 278 |
| JOURNEY-DEV-002 | Integrate via Python SDK | DEV | Phase 278 |
| JOURNEY-DEV-003 | Integrate via REST API | DEV | Phase 278 |
| JOURNEY-DEV-004 | Set Up Webhooks | DEV | Phase 278 |
| JOURNEY-DEV-005 | Natural Language Search API | DEV | Phase 284 |
| JOURNEY-DEV-006 | Integrate Transformation Pipeline API | DEV | Phase 115A |
| JOURNEY-DEV-007 | Build Custom Connector | DEV | Phase 278 |
| JOURNEY-DEV-008 | Use Plugin System | DEV / DE | Phase 278 |
| JOURNEY-DEV-009 | Integrate with Developer Portal | DEV | Phase 278 |
| JOURNEY-DEV-010 | Query via GraphQL-LD Endpoint | DEV | Phase 284 | (Planned) |

### Auditor (Persona: AUD)
| ID | Title | Persona(s) | Phase |
|---|---|---|---|
| JOURNEY-AUD-001 | Review Audit Logs | AUD | Phase 232 |
| JOURNEY-AUD-002 | Query Audit Events | AUD | Phase 232 |
| JOURNEY-AUD-003 | Export Audit Data | AUD | Phase 232 |
| JOURNEY-AUD-004 | Review Mesh Governance | AUD | Phase 284 |
| JOURNEY-AUD-005 | Audit Transformation Pipelines | AUD | Phase 115A |
| JOURNEY-AUD-006 | Review Social Feature Activity | AUD | Phase 278 |

### Data Scientist (Persona: DS)
| ID | Title | Persona(s) | Phase |
|---|---|---|---|
| JOURNEY-DS-001 | Natural Language Search (Data Scientist) | DS | Phase 284 |
| JOURNEY-DS-002 | AI-Powered Schema Matching | DS | Phase 284 |
| JOURNEY-DS-003 | ML-Based Anomaly Detection | DS | Phase 284 |
| JOURNEY-DS-004 | Tune Recommendation Engine | DS | Phase 284 |
| JOURNEY-DS-005 | Auto-Classification Configuration | DS | Phase 284 |

### Data Analyst (Persona: DA)
| ID | Title | Persona(s) | Phase |
|---|---|---|---|
| JOURNEY-DA-001 | Create Transformation Pipeline (Analyst) | DA | Phase 115A |
| JOURNEY-DA-002 | Wrangle Data | DA | Phase 115A |
| JOURNEY-DA-003 | Query Virtual Dataset (Analyst) | DA | Phase 284 |
| JOURNEY-DA-004 | Execute Federated Query | DA | Phase 284 |

### Community Manager (Persona: CM)
| ID | Title | Persona(s) | Phase |
|---|---|---|---|
| JOURNEY-CM-001 | Manage Data Community | CM | Phase 278 |
| JOURNEY-CM-002 | Moderate Reviews and Ratings | CM | Phase 278 |
| JOURNEY-CM-003 | Assign Data Stewards (Community) | CM | Phase 278 |
| JOURNEY-CM-004 | Manage Activity Feeds | CM | Phase 278 |

### Data Mesh Domain Owner (Persona: DMO)
| ID | Title | Persona(s) | Phase |
|---|---|---|---|
| JOURNEY-DMO-001 | Create Data Mesh Domain | DMO | Phase 284 |
| JOURNEY-DMO-002 | Configure Federated Governance | DMO | Phase 284 |
| JOURNEY-DMO-003 | Manage Domain Topology | DMO | Phase 284 |
| JOURNEY-DMO-004 | Transfer Domain Ownership | DMO | Phase 284 |
| JOURNEY-DMO-005 | Monitor Domain Health | DMO | Phase 284 |

### ODPS (Product-First Data Sharing) (Persona: DPO / DE / DC)
| ID | Title | Persona(s) | Phase |
|---|---|---|---|
| JOURNEY-ODPS-001 | Product-First Flow | DPO | Phase 227 |
| JOURNEY-ODPS-002 | ODPS Linking | DPO | Phase 227 |
| JOURNEY-ODPS-003 | ODPS Export | DPO | Phase 227 |
| JOURNEY-ODPS-004 | ODPS Download | DC | Phase 227 |
| JOURNEY-ODPS-005 | ODPS Pricing Plans | DPO | Phase 227 |

### Marketplace Integration (Persona: DPO / DC)
| ID | Title | Persona(s) | Phase |
|---|---|---|---|
| JOURNEY-MP-001 | Connect to External Marketplace | DPO | Phase 231 |
| JOURNEY-MP-002 | Publish Asset to External Marketplace | DPO | Phase 231 |
| JOURNEY-MP-003 | Import Dataset from External Marketplace | DC | Phase 231 |
| JOURNEY-MP-004 | Sync Assets Bidirectionally | DPO | Phase 231 |
| JOURNEY-MP-005 | Schedule Automatic Sync | DPO | Phase 231 |
| JOURNEY-MP-006 | Manage Marketplace Mappings | DPO | Phase 231 |
| JOURNEY-MP-007 | Monitor Sync Jobs | DPO | Phase 231 |

### Scheduled Operations (Persona: DE)
| ID | Title | Persona(s) | Phase |
|---|---|---|---|
| JOURNEY-INGESTION-001 | Create and Run Scheduled Ingestion | DE | Phase 25 |
| JOURNEY-INGESTION-003 | Edit and Delete Scheduled Ingestion | DE | Phase 25 |
| JOURNEY-EXPORT-001 | Create and Run Scheduled Export | DE | Phase 25 |
| JOURNEY-EXPORT-002 | Monitor and Troubleshoot Export Runs | DE | Phase 25 |

---

## Persona Key

| Abbreviation | Persona |
|---|---|
| DPO | Data Product Owner |
| DE | Data Engineer |
| DC | Data Consumer |
| CPO | Compliance & Privacy Officer |
| MPA | Marketplace Platform Admin |
| PA | Platform Admin |
| TA | Tenant Admin |
| DEV | External Developer |
| AUD | Auditor |
| DS | Data Scientist |
| DA | Data Analyst |
| CM | Community Manager |
| DMO | Data Mesh Domain Owner |
| All | All personas |

---

## Phase Key

Journeys are organized by the phase in which they were first implemented:

| Phase | What Shipped |
|---|---|
| Phase 11 | Auth (login, register, password reset, JWT, invitation, SSO, tenant switch) |
| Phase 25 | Scheduled ingestion & export (Prefect orchestration) |
| Phase 115A | Transformation pipeline (dbt, Prefect, wrangling, preview) |
| Phase 227 | Contract normalization + ODPS (product-first flow, linking, export) |
| Phase 231 | Marketplace listings, compliance runs, entitlements, payments, KYC/KYB |
| Phase 232 | GDPR (DSAR, erasure, consent, retention), DPIA, RoPA, processor agreements, breach |
| Phase 234 | Billing, cost tracking, audit retention, connectors, integration ecosystem |
| Phase 240 | Data quality (DQ runs, anomalies, trends, scorecards) |
| Phase 250 | Asset data-first flow, asset activation, file upload, dataset edit/link |
| Phase 278 | UX activation (tenant pill, sync banner, destructive confirm, inbox, HelpTip, error UX, developer portal, plugins, communities, social features) |
| Phase 284 | GA promotions: federated import, GraphQL-LD, semantic search, custom ontology, LDN, DPIA, breach, versioning, mesh domains, virtualization, AI/ML features |

## Maintenance

When adding a new user journey:
1. Document the journey in `docs/PRODUCT_GUIDE.md` or a dedicated file
2. Add a row to the appropriate persona table above
3. Create a frontend E2E spec at `frontend/e2e/journeys/<persona>/JOURNEY-XXX.spec.ts`
4. Add `@pytest.mark.journey("JOURNEY-XXX")` to at least one backend test method
5. If the journey is critical for CI traceability, add its ID to `docs/CRITICAL_UC_JOURNEY_IDS.yaml`
6. Run `make check-docs-sync` before merge

**Last reviewed**: 2026-06-17 | **Next review**: 2026-09-17
