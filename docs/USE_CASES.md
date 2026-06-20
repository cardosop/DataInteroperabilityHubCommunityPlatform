# Use Case Index

**Last Updated**: 2026-06-17 | **Source**: `docs/mvpdocs/use-cases/`, `docs/PRODUCT_GUIDE.md`, `frontend/e2e/use-cases/`  
**YAML Registry**: `docs/CRITICAL_UC_JOURNEY_IDS.yaml`  
**Total use cases**: 95

---

## Table of Use Cases

### Authentication & Access
| ID | Title | Persona(s) | File |
|---|---|---|---|
| UC-AUTH-001 | User Registers | DC | `mvpdocs/use-cases/UC-AUTH-001.md` |
| UC-AUTH-002 | User Logs In | All (DC, DPO, DE, CPO, MPA, DEV) | `mvpdocs/use-cases/UC-AUTH-002.md` |
| UC-AUTH-003 | User Resets Password | All | `mvpdocs/use-cases/UC-AUTH-003.md` |
| UC-AUTH-004 | Unauthenticated Access | DC (visitor) | `mvpdocs/use-cases/UC-AUTH-004.md` |
| UC-AUTH-005 | Invitation Accept | DC / DE | `mvpdocs/use-cases/UC-AUTH-005.md` |
| UC-AUTH-006 | SSO Login | DE / DEV | `mvpdocs/use-cases/UC-AUTH-006.md` |
| UC-AUTH-007 | Tenant Switch | DE / DC | `mvpdocs/use-cases/UC-AUTH-007.md` |

### Asset Management
| ID | Title | Persona(s) | File |
|---|---|---|---|
| UC-AM-001 | Create Asset via Data-First Flow | DPO | `mvpdocs/use-cases/UC-AM-001.md` |
| UC-AM-002 | Publish Asset to Marketplace | DPO | `mvpdocs/use-cases/UC-AM-002.md` |
| UC-DS-EDIT | Edit Dataset and Link to Asset | DPO, DE | `PRODUCT_GUIDE.md` |
| UC-FILE-UPLOAD | Upload File | DPO, DE | `PRODUCT_GUIDE.md` |

### Contract & Community Management
| ID | Title | Persona(s) | File |
|---|---|---|---|
| UC-CM-001 | Manage Data Community | MPA | `mvpdocs/use-cases/UC-CM-001.md` |
| UC-CM-002 | Moderate Reviews and Ratings | MPA | `mvpdocs/use-cases/UC-CM-002.md` |
| UC-CM-003 | Assign Data Steward | MPA / DPO | `mvpdocs/use-cases/UC-CM-003.md` |
| UC-CM-004 | Manage Activity Feed | DPO | `mvpdocs/use-cases/UC-CM-004.md` |

### Data Quality
| ID | Title | Persona(s) | File |
|---|---|---|---|
| UC-DQ-001 | Run Data Quality Check | DPO / DE | `mvpdocs/use-cases/UC-DQ-001.md` |

### Compliance & Governance
| ID | Title | Persona(s) | File |
|---|---|---|---|
| UC-COMP-001 | Run Compliance Scan | CPO / DE | `mvpdocs/use-cases/UC-COMP-001.md` |
| UC-COMP-002 | Report and Manage Data Breach | CPO | `mvpdocs/use-cases/UC-COMP-002.md` |
| UC-COMP-003 | Conduct DPIA Assessment | CPO | `mvpdocs/use-cases/UC-COMP-003.md` |
| UC-COMP-004 | Generate RoPA | CPO | `mvpdocs/use-cases/UC-COMP-004.md` |
| UC-COMP-005 | Manage Processor Agreements | CPO | `mvpdocs/use-cases/UC-COMP-005.md` |
| UC-COMP-006 | Handle DSAR Request | CPO | `mvpdocs/use-cases/UC-COMP-006.md` |
| UC-COMP-007 | Generate Compliance Report | CPO | `PRODUCT_GUIDE.md` |
| UC-COMP-008 | Track Compliance History | CPO | `PRODUCT_GUIDE.md` |
| UC-CPO-009 | Automated Retention Configuration | CPO | `PRODUCT_GUIDE.md` |
| UC-GOV-ADV-001 | Configure Automated Compliance | CPO | `mvpdocs/use-cases/UC-GOV-ADV-001.md` |
| UC-GOV-ADV-002 | GDPR Right to be Forgotten | CPO | `mvpdocs/use-cases/UC-GOV-ADV-002.md` |
| UC-GOV-ADV-003 | Manage Consent Tracking | CPO | `mvpdocs/use-cases/UC-GOV-ADV-003.md` |
| UC-GOV-ADV-004 | Configure Automated Retention | CPO | `mvpdocs/use-cases/UC-GOV-ADV-004.md` |

### Marketplace
| ID | Title | Persona(s) | File |
|---|---|---|---|
| UC-MKT-001 | Browse Marketplace | DC | `PRODUCT_GUIDE.md` |
| UC-MKT-002 | Request/Purchase Asset Access | DC | `PRODUCT_GUIDE.md` |
| UC-MKT-003 | Import Data from External Provider | DPO | `mvpdocs/use-cases/UC-MKT-003.md` |
| UC-MKT-004 | Access Purchased Asset | DC | `PRODUCT_GUIDE.md` |
| UC-MKT-005 | Unpublish Asset from Marketplace | DPO | `PRODUCT_GUIDE.md` |
| UC-MKT-006 | Publish Asset to Marketplace (Legacy) | DPO | `PRODUCT_GUIDE.md` |
| UC-MKT-ADV-001 | Configure Usage-Based Pricing | DPO / MPA | `mvpdocs/use-cases/UC-MKT-ADV-001.md` |
| UC-MKT-ADV-002 | Preview Data Before Purchase | DC | `mvpdocs/use-cases/UC-MKT-ADV-002.md` |
| UC-MKT-ADV-003 | Manage Trust Signals | DPO / MPA | `PRODUCT_GUIDE.md` |
| UC-MKT-ADV-004 | Track Revenue Analytics | DPO / MPA | `PRODUCT_GUIDE.md` |
| UC-MKT-ADV-005 | Configure Data Quality SLAs | DPO / MPA | `PRODUCT_GUIDE.md` |

### Data Consumer & Analyst
| ID | Title | Persona(s) | File |
|---|---|---|---|
| UC-DC-001 | Discover and Purchase Asset | DC | `PRODUCT_GUIDE.md` |
| UC-DC-006 | Natural Language Search | DC | `PRODUCT_GUIDE.md` |
| UC-DC-008 | Rate and Review Asset | DC | `PRODUCT_GUIDE.md` |
| UC-DA-003 | Query Virtual Dataset | DA | `PRODUCT_GUIDE.md` |
| UC-DA-004 | Execute Federated Query | DA | `PRODUCT_GUIDE.md` |

### Billing & Cost
| ID | Title | Persona(s) | File |
|---|---|---|---|
| UC-BILL-002 | Billing Upgrade | MPA | `mvpdocs/use-cases/UC-BILL-002.md` |
| UC-TA-007 | Monitor Cost Tracking | MPA | `mvpdocs/use-cases/UC-TA-007.md` |

### Transformation Pipeline
| ID | Title | Persona(s) | File |
|---|---|---|---|
| UC-TRANS-001 | Create Transformation Pipeline | DE | `PRODUCT_GUIDE.md` |
| UC-TRANS-002 | Execute Transformation Pipeline | DE | `PRODUCT_GUIDE.md` |
| UC-TRANS-003 | Monitor Pipeline Execution | DE | `PRODUCT_GUIDE.md` |
| UC-TRANS-004 | Data Wrangling | DE | `PRODUCT_GUIDE.md` |
| UC-TRANS-005 | Pipeline Versioning | DE | `PRODUCT_GUIDE.md` |
| UC-TRANS-006 | Pipeline Rollback | DE | `PRODUCT_GUIDE.md` |
| UC-TRANS-007 | Transformation Templates | DE | `PRODUCT_GUIDE.md` |
| UC-TRANS-008 | Custom Transformation Functions | DE | `PRODUCT_GUIDE.md` |

### Scheduled Ingestion
| ID | Title | Persona(s) | File |
|---|---|---|---|
| UC-INGEST-001 | Create Scheduled Ingestion | DE | `PRODUCT_GUIDE.md` |
| UC-INGEST-002 | Configure Ingestion Source | DE | `PRODUCT_GUIDE.md` |
| UC-INGEST-003 | Monitor Ingestion Runs | DE | `PRODUCT_GUIDE.md` |
| UC-INGEST-004 | Manual Trigger Ingestion | DE | `PRODUCT_GUIDE.md` |
| UC-INGEST-005 | Manage Dead Letter Queue | DE | `PRODUCT_GUIDE.md` |

### Scheduled Export
| ID | Title | Persona(s) | File |
|---|---|---|---|
| UC-EXPORT-001 | Schedule Recurring Export | DE | `PRODUCT_GUIDE.md` |
| UC-EXPORT-002 | Configure Export Destination | DE | `PRODUCT_GUIDE.md` |
| UC-EXPORT-003 | Monitor Export Runs | DE | `PRODUCT_GUIDE.md` |
| UC-EXPORT-004 | Manual Trigger Export | DE | `PRODUCT_GUIDE.md` |

### Semantic Layer
| ID | Title | Persona(s) | File |
|---|---|---|---|
| UC-SEM-001 | Upload Custom Ontology | DE | `mvpdocs/use-cases/UC-SEM-001.md` |
| UC-SEM-002 | Subscribe to LDN Inbox | DE | `mvpdocs/use-cases/UC-SEM-002.md` |
| UC-SEM-003 | Browse Resource Version History | DC | `mvpdocs/use-cases/UC-SEM-003.md` |
| UC-SEM-004 | Query with Inference Rules | DE | `mvpdocs/use-cases/UC-SEM-004.md` |
| UC-SEM-005 | Execute GraphQL-LD Query | DEV | `mvpdocs/use-cases/UC-SEM-005.md` |
| UC-SEM-006 | Search with Semantic Facets | DC | `mvpdocs/use-cases/UC-SEM-006.md` |

### AI / ML
| ID | Title | Persona(s) | File |
|---|---|---|---|
| UC-AI-001 | Natural Language Search | DC / DS | `PRODUCT_GUIDE.md` |
| UC-AI-002 | AI Schema Matching | DPO / DE / DS | `PRODUCT_GUIDE.md` |
| UC-AI-003 | ML-Based Anomaly Detection | DPO / DS | `PRODUCT_GUIDE.md` |
| UC-AI-004 | Smart Recommendations | DC / DPO | `PRODUCT_GUIDE.md` |
| UC-AI-005 | Auto-Classification | DPO / CPO / DS | `PRODUCT_GUIDE.md` |
| UC-AI-006 | Predictive Quality Forecasting | DPO / DS | `PRODUCT_GUIDE.md` |
| UC-AI-007 | Auto-Generated Quality Rules | DPO / DS | `PRODUCT_GUIDE.md` |
| UC-AI-008 | Query-to-SQL Translation | DC / DS | `PRODUCT_GUIDE.md` |
| UC-AI-009 | ML Model Training | DS | `PRODUCT_GUIDE.md` |
| UC-AI-010 | Recommendation Feedback Loop | DC / DS | `PRODUCT_GUIDE.md` |

### Social Features
| ID | Title | Persona(s) | File |
|---|---|---|---|
| UC-SOCIAL-001 | Rate Asset | DC / DPO | `PRODUCT_GUIDE.md` |
| UC-SOCIAL-002 | Review Asset | DC / DPO | `PRODUCT_GUIDE.md` |
| UC-SOCIAL-003 | Comment on Asset | DC / DPO | `PRODUCT_GUIDE.md` |
| UC-SOCIAL-004 | Join Data Community | DC / DPO / CM | `PRODUCT_GUIDE.md` |
| UC-SOCIAL-005 | Manage Activity Feed | DC / DPO / CM | `PRODUCT_GUIDE.md` |
| UC-SOCIAL-006 | Assign Data Steward (Social) | DPO / CM | `PRODUCT_GUIDE.md` |

### Data Mesh
| ID | Title | Persona(s) | File |
|---|---|---|---|
| UC-MESH-001 | Create Data Mesh Domain | DMO / TA | `PRODUCT_GUIDE.md` |
| UC-MESH-002 | Configure Federated Governance | DMO / CPO | `PRODUCT_GUIDE.md` |
| UC-MESH-003 | Manage Domain Topology | DMO / MPA | `PRODUCT_GUIDE.md` |
| UC-MESH-004 | Assign Domain Ownership | DMO / TA | `PRODUCT_GUIDE.md` |
| UC-MESH-005 | Monitor Mesh Health | DMO / MPA | `PRODUCT_GUIDE.md` |

### Virtualization
| ID | Title | Persona(s) | File |
|---|---|---|---|
| UC-VIRT-001 | Create Virtual Dataset | DE / DA | `PRODUCT_GUIDE.md` |
| UC-VIRT-002 | Execute Federated Query | DA / DE | `PRODUCT_GUIDE.md` |
| UC-VIRT-003 | Manage Federation Topology | DE / PA | `PRODUCT_GUIDE.md` |
| UC-VIRT-004 | Monitor Virtualization Performance | DE / PA | `PRODUCT_GUIDE.md` |

### Advanced Observability
| ID | Title | Persona(s) | File |
|---|---|---|---|
| UC-OBS-ADV-001 | Monitor Reliability Scores | DPO / PA | `PRODUCT_GUIDE.md` |
| UC-OBS-ADV-002 | Track Data Costs | TA / PA | `PRODUCT_GUIDE.md` |
| UC-OBS-ADV-003 | Set Up Predictive Alerts | PA / DPO | `PRODUCT_GUIDE.md` |
| UC-OBS-ADV-004 | Monitor Performance Regressions | PA / DE | `PRODUCT_GUIDE.md` |

### Integration Ecosystem
| ID | Title | Persona(s) | File |
|---|---|---|---|
| UC-INT-001 | Install Pre-built Connector | DE / TA | `PRODUCT_GUIDE.md` |
| UC-INT-002 | Create Custom Connector | DE / DEV | `PRODUCT_GUIDE.md` |
| UC-INT-003 | Integrate BI Tool | DE / TA | `PRODUCT_GUIDE.md` |
| UC-INT-004 | Set Up Reverse ETL | DE | `PRODUCT_GUIDE.md` |
| UC-INT-005 | Integrate CI/CD Pipeline | DE / DEV | `PRODUCT_GUIDE.md` |

### Developer Experience
| ID | Title | Persona(s) | File |
|---|---|---|---|
| UC-DEV-001 | Install Plugin | DEV / DE | `PRODUCT_GUIDE.md` |
| UC-DEV-002 | Create Custom Plugin | DEV / DE | `PRODUCT_GUIDE.md` |
| UC-DEV-003 | Use CLI Tool | DEV / DE | `PRODUCT_GUIDE.md` |
| UC-DEV-007 | Build Custom Connector | DEV | `PRODUCT_GUIDE.md` |
| UC-DEV-008 | Use Plugin System | DEV | `PRODUCT_GUIDE.md` |
| UC-DEV-004 | Access Developer Portal | DEV | `PRODUCT_GUIDE.md` |
| UC-DEV-009 | Integrate with Developer Portal | DEV | `PRODUCT_GUIDE.md` |

### ODPS (Product-First Data Sharing)
| ID | Title | Persona(s) | File |
|---|---|---|---|
| UC-ODPS-001 | Product-First Flow | DPO | `PRODUCT_GUIDE.md` |
| UC-ODPS-002 | ODPS Linking | DPO | `PRODUCT_GUIDE.md` |
| UC-ODPS-003 | ODPS Export | DPO | `PRODUCT_GUIDE.md` |
| UC-ODPS-004 | ODPS Download | DC | `PRODUCT_GUIDE.md` |
| UC-ODPS-005 | ODPS Pricing Plans | DPO | `PRODUCT_GUIDE.md` |
| UC-ODPS-006 | ODPS Access Methods | DPO | `PRODUCT_GUIDE.md` |
| UC-ODPS-007 | ODPS Payment Gateways | DPO | `PRODUCT_GUIDE.md` |
| UC-ODPS-008 | ODPS Product Strategy | DPO | `PRODUCT_GUIDE.md` |
| UC-ODPS-009 | ODPS Multilingual Details | DPO | `PRODUCT_GUIDE.md` |
| UC-ODPS-010 | ODPS $ref Resolution | DE | `PRODUCT_GUIDE.md` |
| UC-ODPS-011 | ODPS Generation | DE | `PRODUCT_GUIDE.md` |
| UC-ODPS-012 | ODPS Unlinking | DPO | `PRODUCT_GUIDE.md` |

### Lineage
| ID | Title | Persona(s) | File |
|---|---|---|---|
| UC-LIN-FIELD-EDIT-001 | Edit Field-Level Lineage | DPO / DE | `PRODUCT_GUIDE.md` |
| UC-MKT-LINEAGE-001 | Marketplace Lineage Visualization | DC | `PRODUCT_GUIDE.md` |
| UC-MKT-LINEAGE-002 | Lineage Impact Analysis | DPO | `PRODUCT_GUIDE.md` |

### Webhooks
| ID | Title | Persona(s) | File |
|---|---|---|---|
| UC-WH-001 | Configure Webhook Endpoint | DEV | `PRODUCT_GUIDE.md` |

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
| DS | Data Scientist |
| DA | Data Analyst |
| CM | Community Manager |
| DMO | Data Mesh Domain Owner |
| All | All personas |

---

## Maintenance

When adding a new use case:
1. Create the use case file in `docs/mvpdocs/use-cases/` with format `UC-{DOMAIN}-{NNN}.md`
2. Add a row to the appropriate domain table above
3. Add `@pytest.mark.uc("UC-XXX")` to at least one backend test method
4. If the use case is critical for CI traceability, add its ID to `docs/CRITICAL_UC_JOURNEY_IDS.yaml`
5. Run `make check-docs-sync` before merge

**Last reviewed**: 2026-06-17 | **Next review**: 2026-09-17
