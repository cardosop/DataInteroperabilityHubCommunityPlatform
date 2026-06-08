# Use Case Index

**Last Updated**: 2026-05-17 | **Source**: `docs/mvpdocs/use-cases/`, `docs/PRODUCT_GUIDE.md`  
**YAML Registry**: `docs/CRITICAL_UC_JOURNEY_IDS.yaml`  
**Total use cases**: 47

---

## Table of Use Cases

| ID | Title | Persona(s) | File |
|---|---|---|---|
| UC-AUTH-001 | User Registers | DC | `mvpdocs/use-cases/UC-AUTH-001.md` |
| UC-AUTH-002 | User Logs In | All (DC, DPO, DE, CPO, MPA, DEV) | `mvpdocs/use-cases/UC-AUTH-002.md` |
| UC-AUTH-003 | User Resets Password | All | `mvpdocs/use-cases/UC-AUTH-003.md` |
| UC-AUTH-004 | Unauthenticated Access | DC (visitor) | `mvpdocs/use-cases/UC-AUTH-004.md` |
| UC-AUTH-005 | Invitation Accept | DC / DE | `mvpdocs/use-cases/UC-AUTH-005.md` |
| UC-AUTH-006 | SSO Login | DE / DEV | `mvpdocs/use-cases/UC-AUTH-006.md` |
| UC-AUTH-007 | Tenant Switch | DE / DC | `mvpdocs/use-cases/UC-AUTH-007.md` |
| UC-AM-001 | Create Asset via Data-First Flow | DPO | `mvpdocs/use-cases/UC-AM-001.md` |
| UC-AM-002 | Publish Asset to Marketplace | DPO | `mvpdocs/use-cases/UC-AM-002.md` |
| UC-CM-001 | Manage Data Community | MPA | `mvpdocs/use-cases/UC-CM-001.md` |
| UC-CM-002 | Moderate Reviews and Ratings | MPA | `mvpdocs/use-cases/UC-CM-002.md` |
| UC-CM-003 | Assign Data Steward | MPA / DPO | `mvpdocs/use-cases/UC-CM-003.md` |
| UC-CM-004 | Manage Activity Feed | DPO | `mvpdocs/use-cases/UC-CM-004.md` |
| UC-COMP-001 | Run Compliance Scan | CPO / DE | `mvpdocs/use-cases/UC-COMP-001.md` |
| UC-COMP-002 | Report and Manage Data Breach | CPO | `mvpdocs/use-cases/UC-COMP-002.md` |
| UC-COMP-003 | Conduct DPIA Assessment | CPO | `mvpdocs/use-cases/UC-COMP-003.md` |
| UC-COMP-004 | Generate RoPA | CPO | `mvpdocs/use-cases/UC-COMP-004.md` |
| UC-COMP-005 | Manage Processor Agreements | CPO | `mvpdocs/use-cases/UC-COMP-005.md` |
| UC-COMP-006 | Handle DSAR Request | CPO | `mvpdocs/use-cases/UC-COMP-006.md` |
| UC-DQ-001 | Run Data Quality Check | DPO / DE | `mvpdocs/use-cases/UC-DQ-001.md` |
| UC-BILL-002 | Billing Upgrade | MPA | `mvpdocs/use-cases/UC-BILL-002.md` |
| UC-TA-007 | Monitor Cost Tracking | MPA | `mvpdocs/use-cases/UC-TA-007.md` |
| UC-GOV-ADV-001 | Configure Automated Compliance | CPO | `mvpdocs/use-cases/UC-GOV-ADV-001.md` |
| UC-GOV-ADV-002 | GDPR Right to be Forgotten | CPO | `mvpdocs/use-cases/UC-GOV-ADV-002.md` |
| UC-GOV-ADV-003 | Manage Consent Tracking | CPO | `mvpdocs/use-cases/UC-GOV-ADV-003.md` |
| UC-GOV-ADV-004 | Configure Automated Retention | CPO | `mvpdocs/use-cases/UC-GOV-ADV-004.md` |
| UC-MKT-ADV-001 | Configure Usage-Based Pricing | DPO / MPA | `mvpdocs/use-cases/UC-MKT-ADV-001.md` |
| UC-MKT-ADV-002 | Preview Data Before Purchase | DC | `mvpdocs/use-cases/UC-MKT-ADV-002.md` |
| UC-TRANS-001 | Create Transformation Pipeline | DE | `PRODUCT_GUIDE.md` |
| UC-TRANS-002 | Execute Transformation Pipeline | DE | `PRODUCT_GUIDE.md` |
| UC-TRANS-003 | Monitor Pipeline Execution | DE | `PRODUCT_GUIDE.md` |
| UC-INGEST-001 | Create Scheduled Ingestion | DE | `PRODUCT_GUIDE.md` |
| UC-INGEST-002 | Configure Ingestion Source | DE | `PRODUCT_GUIDE.md` |
| UC-INGEST-003 | Monitor Ingestion Runs | DE | `PRODUCT_GUIDE.md` |
| UC-EXPORT-001 | Schedule Recurring Export | DE | `PRODUCT_GUIDE.md` |
| UC-EXPORT-002 | Configure Export Destination | DE | `PRODUCT_GUIDE.md` |
| UC-EXPORT-003 | Monitor Export Runs | DE | `PRODUCT_GUIDE.md` |
| UC-SEM-001 | Upload Custom Ontology | DE | `mvpdocs/use-cases/UC-SEM-001.md` |
| UC-SEM-002 | Subscribe to LDN Inbox | DE | `mvpdocs/use-cases/UC-SEM-002.md` |
| UC-SEM-003 | Browse Resource Version History | DC | `mvpdocs/use-cases/UC-SEM-003.md` |
| UC-SEM-004 | Query with Inference Rules | DE | `mvpdocs/use-cases/UC-SEM-004.md` |
| UC-SEM-005 | Execute GraphQL-LD Query | DEV | `mvpdocs/use-cases/UC-SEM-005.md` |
| UC-SEM-006 | Search with Semantic Facets | DC | `mvpdocs/use-cases/UC-SEM-006.md` |
| UC-MKT-003 | Import Data from External Provider | DPO | `mvpdocs/use-cases/UC-MKT-003.md` |
| UC-DEV-001 | Install Plugin | DEV / DE | `PRODUCT_GUIDE.md` |
| UC-DEV-002 | Create Custom Plugin | DEV / DE | `PRODUCT_GUIDE.md` |
| UC-DEV-009 | Integrate with Developer Portal | DEV | `PRODUCT_GUIDE.md` |

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

## Maintenance

When adding a new use case:
1. Create the use case file in `docs/mvpdocs/use-cases/` with format `UC-{DOMAIN}-{NNN}.md`
2. Add a row to the table above
3. If the use case is critical for CI traceability, add its ID to `docs/CRITICAL_UC_JOURNEY_IDS.yaml`

**Last reviewed**: 2026-05-13 | **Next review**: 2026-08-11
