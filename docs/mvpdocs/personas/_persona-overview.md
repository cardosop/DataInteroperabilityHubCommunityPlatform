# Persona Overview

Meshant serves six product-canonical personas.  Each persona has a
dedicated quickstart, how-to guides, and reference links.

| Alias | Persona | Primary Goal | Technical Level |
|-------|---------|-------------|-----------------|
| DPO | [Data Product Owner](data-product-owner/) | Publish, govern, and monetize data products | Medium |
| DE | [Data Engineer](data-engineer/) | Build and maintain data pipelines and quality | High |
| CPO | [Compliance & Privacy Officer](compliance-privacy-officer/) | Ensure regulatory compliance | Low-Medium |
| DC | [Data Consumer](data-consumer/) | Discover, access, and use data products | Variable |
| MPA | [Marketplace & Platform Admin](marketplace-platform-admin/) | Manage tenants, billing, platform ops | Medium |
| DEV | [External Developer](external-developer/) | Integrate via API, CLI, or SDK | High |

---

## Data Product Owner (DPO)

**Also known as:** Data Steward, Domain Data Owner, Data Product Manager

Mid to senior professional responsible for publishing datasets as
trusted data products to the tenant catalog or marketplace.  Maintains
contracts and metadata with guaranteed VALID status and ensures DQ and
compliance gates pass before storage.

**MVP capabilities:** Three onboarding flows (Data First, Contract
First, Contract Only), asset lifecycle management (draft to published),
DQ and compliance report review, marketplace publishing.

**Key journeys:**
[Onboard Asset](../journeys/JOURNEY-DPO-001.md) |
[Publish to Marketplace](../journeys/JOURNEY-DPO-002.md) |
[Manage Lifecycle](../journeys/JOURNEY-DPO-003.md) |
[Monitor Quality](../journeys/JOURNEY-DPO-004.md) |
[Configure Contracts](../journeys/JOURNEY-DPO-005.md) |
[Manage Listings](../journeys/JOURNEY-DPO-006.md)

**Post-MVP:** Transformation pipelines, scheduled ingestion/export,
advanced lineage visualization.

-> [Full DPO documentation](data-product-owner/)

---

## Data Engineer (DE)

**Also known as:** Analytics Engineer, Platform Engineer, Data Platform
Developer

Mid to senior technical professional who manages contracts as code
(Git + CI/CD), automates intake flows via API/SDK, and integrates
DQ/compliance checks into existing data stacks.

**MVP capabilities:** DataContract CLI validation and linting, REST and
Python SDK integration, programmatic DQ/compliance triggers, SPARQL
and JSON-LD metadata resolution, CI/CD pipeline integration.

**Key journeys:**
[Contract-First Onboarding](../journeys/JOURNEY-DE-001.md) |
[Configure DQ Checks](../journeys/JOURNEY-DE-003.md) |
[Set Up Compliance Scanning](../journeys/JOURNEY-DE-004.md)

**Post-MVP:** Transformation pipeline authoring, scheduled
ingestion/export automation, advanced semantic queries.

-> [Full DE documentation](data-engineer/)

---

## Compliance & Privacy Officer (CPO)

**Also known as:** DPO (data protection context), Privacy Officer,
Compliance Manager, Legal Counsel

Senior professional ensuring all stored datasets pass compliance gates.
Maintains auditability and quickly identifies risky datasets containing
PII, sensitive data, or special categories.

**MVP capabilities:** Compliance scan execution and review, risk level
assessment, PII category detection (PII_DIRECT_EMAIL, PAYMENT_CARD,
etc.), audit log navigation with 3-year retention, GDPR rights
management (access, erasure, portability).

**Key journeys:**
[Run Compliance Scan](../journeys/JOURNEY-CPO-001.md) |
[Configure Automated Compliance](../journeys/JOURNEY-CPO-006.md) |
[Execute GDPR Erasure](../journeys/JOURNEY-CPO-007.md) |
[Manage Consent](../journeys/JOURNEY-CPO-008.md) |
[Configure Retention](../journeys/JOURNEY-CPO-009.md) |
[Review Retention Reports](../journeys/JOURNEY-CPO-010.md)

**Post-MVP:** Cross-tenant compliance dashboards, automated regulatory
reporting, advanced risk trend analysis.

-> [Full CPO documentation](compliance-privacy-officer/)

---

## Data Consumer (DC)

**Also known as:** Data Scientist, Analyst, Product Manager, Business
User, External Buyer

Junior to senior professional who discovers and evaluates datasets for
business needs.  Trusts data quality and compliance badges and
completes purchase flows with transparent pricing and licensing.

**MVP capabilities:** Full-text and semantic search, faceted filtering,
trust indicator evaluation (quality scores, compliance badges),
ecommerce checkout (one-off, subscription, usage-based), purchased
asset access (download and API).

**Key journeys:**
[Discover and Purchase Asset](../journeys/JOURNEY-DC-001.md)

**Post-MVP:** Collaborative workspaces, data previews with sampling,
custom alerting on asset updates.

-> [Full DC documentation](data-consumer/)

---

## Marketplace & Platform Admin (MPA)

**Also known as:** Platform Owner, Operations Lead, Business Owner

Senior professional responsible for growing marketplace supply
(providers) and demand (consumers), maintaining platform-wide trust
via consistent DQ/compliance gates, and ensuring accurate billing.

**MVP capabilities:** Cross-tenant admin dashboard, tenant KYC
onboarding and approval, platform default configuration (ODCS versions,
DQ profiles, compliance thresholds, rate limits), marketplace oversight
(approve/de-list assets), global metrics monitoring, revenue and SLA
tracking.

**Key journeys:**
[Onboard Marketplace Instance](../journeys/JOURNEY-PA-001.md) |
[Admin Operations](../journeys/JOURNEY-MPA-005.md) |
[Monitor Costs](../journeys/JOURNEY-TA-007.md) |
[Configure Integrations](../journeys/JOURNEY-TA-008.md)

**Post-MVP:** Advanced analytics dashboards, automated tenant
provisioning, white-label customization.

-> [Full MPA documentation](marketplace-platform-admin/)

---

## External Developer (DEV)

**Also known as:** Partner Engineer, Platform Integrator, Solution
Architect

Mid to senior technical professional who embeds hub capabilities in
external systems (custom portals, data catalogs, dashboards) while
respecting multi-tenancy, security, and rate limits.

**MVP capabilities:** REST API and Python SDK integration, webhook
event subscriptions, JSON-LD metadata resolution, SPARQL endpoint
access, multi-tenant credential management, rate limit and quota
awareness, MVP-gated feature detection via `MVPGatedFeatureError`.

**Key journeys:**
[API Integration](../journeys/JOURNEY-DE-001.md)

**Post-MVP:** GraphQL API, JavaScript SDK, plugin framework,
white-label embedding toolkit.

-> [Full DEV documentation](external-developer/)

---

## How Personas Map to Platform Capabilities

| Capability | DPO | DE | CPO | DC | MPA | DEV |
|-----------|-----|-----|-----|-----|-----|-----|
| Asset Management | Primary | Create | Review | Browse | Oversee | API |
| Data Contracts | Author | Code | Audit | Read | Configure | API |
| Data Quality | Review | Trigger | Audit | Trust | Configure | API |
| Compliance | Review | Trigger | Primary | Trust | Configure | API |
| Marketplace | Publish | -- | -- | Purchase | Manage | API |
| Billing | -- | -- | -- | Pay | Manage | API |
| Semantic Layer | Browse | Query | Search | Search | -- | API |
| Audit Trail | View own | View own | Primary | -- | Full | API |

## Cross-Phase Persona Reconciliation

The 6 product-canonical personas listed here are used in all
user-facing documentation (D155).  The 13 frontend personas from
Phase 216 D145 (used for e2e test parametrization) map to these 6 via
`docs/mvpdocs/_meta/persona-mapping.yaml` (D163).
