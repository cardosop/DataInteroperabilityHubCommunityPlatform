# Personas

This document describes the core personas for the **Interoperable Data Hub** — a platform for managing data contracts (ODCS/DataContract.com), running data-quality and compliance checks as services, exposing semantics via RDF/ontologies, and enabling a multi-tenant data marketplace where companies and individuals can buy and sell data.

These personas are intended to guide:

- Product decisions
- UX design (UI and APIs/SDKs)
- Architecture (security, multi-tenancy, audit trails, billing, jobs)

---

## Persona 1 – Data Product Owner

**Aliases:** Data Steward, Domain Data Owner, Data Product Manager  
**Typical Role Mapping:** Tenant **Data Provider** (sometimes Tenant Admin)  
**Seniority:** Mid to senior  
**Technical level:** Medium – understands data and schemas; not deeply into infra/CLI

### 1.1 Summary

Owns one or more datasets inside an organization and wants to publish them as **data products** in the hub, either for internal reuse (within the tenant) or for sale in the **marketplace**. Responsible for the meaning, quality, and lifecycle of the asset, but usually collaborates with data engineers for technical implementation.

They work primarily through the **web UI**, relying on the platform to enforce data contract standards, data quality, and compliance gates.

### 1.2 Goals

- Turn internal datasets into **well-described, trustworthy and compliant data products**.
- Publish assets to the **tenant catalog** and optionally to the **cross-tenant marketplace** (“on the shelf”).
- Keep contracts, documentation, and metadata **up to date across versions** (while the platform guarantees they stay `VALID`).
- Be confident that mandatory **data-quality** and **compliance** checks ran, and that everything is backed by audit logs.

### 1.3 Key Responsibilities / Tasks

- Choose the appropriate onboarding flow per dataset:

  1. **Data first**  
     - Upload data file via browser (up to size limits) or via SDK/CLI (for larger files).  
     - Wait for:
       - File format validation.
       - Schema inference and sample extraction.
       - Automatic **Compliance Check** (PII/sensitive data detection; fail-closed gate).  
       - Automatic **DQ Check** (`intake_basic` profile).  
     - If checks **fail**, review reports and decide whether to:
       - Fix data externally and re-upload, or
       - Use scan-only mode (no storage) for risk assessment.  
     - If checks **pass** (or are acceptable `WARN`), open the **data contract editing screen** pre-filled with:
       - Inferred schema and sample.
       - Quality metrics.
       - Compliance summary (overall status, risk level, categories).
     - Edit and refine the contract, then trigger **DataContract CLI validation** until it is `VALID`.

  2. **Contract first**  
     - Upload an existing data contract file (ODCS / DataContract.com).  
     - Run **DataContract CLI** validation via the UI:
       - Resolve `INVALID` or `ERROR` status before proceeding.  
     - Once `VALID` (or policy-allowed `WARNING_ONLY`), upload data file.  
     - Wait for file intake:
       - Format validation.
       - Schema inference.
       - Compliance & quality gates.  
     - Compare inferred schema vs contract schema:
       - Review highlighted differences, adjusting either the data or the contract.  
     - Edit the now-canonicalized **HubContract** via UI, then re-run CLI validation until status is `VALID`.  

  3. **Contract only**  
     - Upload a contract file, run CLI validation, fix until `VALID`.  
     - Store it as a **contract-only asset** in the catalog.  
     - Later, attach data files which must pass compliance + DQ gates before being stored.

- Resolve validation errors reported by **DataContract CLI** in the UI:
  - Understand `validation_status` (`INVALID`, `WARNING_ONLY`).
  - Only mark assets as active when contract status is `VALID`.

- Review **data quality** and **compliance** reports:
  - DQ: `overall_status`, `quality_score`, key checks (null ratio, uniqueness, etc.).
  - Compliance: `overall_status`, `risk_level`, categories (e.g. `PAYMENT_CARD`).
  - Understand that they **cannot override** compliance failures; they must change the data and retry.

- Decide whether an asset:
  - Stays **internal** to the tenant, or  
  - Is published to the **marketplace** with pricing and licensing metadata (subject to tenant KYC status and platform policies).

- Monitor long-running operations (DQ, compliance, validations) via **job status** in the UI (`PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`).

### 1.4 Pain Points

- Confusing error messages from contracts (CLI), DQ, or compliance checks.
- Difficulty reconciling **inferred schema** with contract schema when they diverge.
- Anxiety about legal risk:
  - Wants guarantees that **non-compliant data simply cannot be stored**.
- Managing multiple contract versions and asset states (draft, active, for sale, removed).

### 1.5 Needs from the Platform

- A guided, friendly UI for the **three intake flows**, tightly integrated with:
  - DQ/Compliance gates.
  - Contract validation (CLI).
- Clear, non-technical explanations of:
  - DataContract CLI errors and suggested fixes.
  - DQ/compliance issues, risk levels, and recommended actions.
- Strong guardrails:
  - Cannot proceed if compliance gate fails.
  - Visual indicators for `VALID`, `WARNING_ONLY` contracts and for DQ/compliance status.
- Ability to:
  - Edit contracts in a rich editor backed by the canonical **HubContract** model.
  - See and manage asset status:
    - Quality status, compliance status, **semantic status** (OK or `DEGRADED`), and marketplace status (`draft`, `internal only`, `public`, `removed`).
  - Tag assets with domains, ontology concepts, and legal/usage metadata without dealing directly with RDF/SPARQL.

---

## Persona 2 – Data Engineer / Contract Author

**Aliases:** Analytics Engineer, Platform Engineer, Data Platform Developer  
**Typical Role Mapping:** Tenant **Data Provider**, sometimes **Tenant Admin**  
**Seniority:** Mid to senior  
**Technical level:** High – comfortable with code, CI/CD, CLIs, YAML/JSON, RDF basics

### 2.1 Summary

Technical power user who integrates the hub into data platforms and pipelines. Treats data contracts as code, owns schema evolution, and automates onboarding, quality checks, and compliance checks. Often the first to use the **REST/GraphQL APIs**, **Python/JS SDKs**, and **SPARQL/JSON-LD** endpoints.

### 2.2 Goals

- Manage **data contracts as code** (in Git, with CI/CD).
- Automate ingestion and updates:
  - Data-first, contract-first, and contract-only flows via API/SDK.
- Integrate hub features with existing data stack:
  - Warehouses, lakes, schedulers, orchestration tools.
- Use **scan-only DQ/compliance** on external pipelines (without storing data).

### 2.3 Key Responsibilities / Tasks

- Use **DataContract CLI** (locally and via the platform’s CLI service) to:
  - Validate contracts (`validation_status`: `VALID`, `INVALID`, etc.).
  - Lint and enforce specific versions (ODCS v2.2.2–v3.x, datacontract.com).
  - Convert between supported formats/spec versions.
  - Help define and evolve the canonical **HubContract** mapping in code.

- Use platform **APIs, SDKs, and CLI** to:
  - Register and update contracts programmatically.
  - Upload data files or register datasets by reference (e.g. object store paths).
  - Trigger **DQ** and **Compliance** checks as:
    - Intake gates for hub assets.
    - External scan-only checks in ETL/ELT pipelines.
  - Inspect `Job` entities (status, metrics, error messages).
  - Fetch DQ/compliance results and integrate them into internal observability dashboards.

- Implement CI/CD workflows where:
  - Contract changes trigger automated validation in pipelines **before** deploying to the hub.
  - Data deployments trigger DQ/compliance checks, with fail-closed behavior for non-compliant results.

- Work with the **semantic layer** indirectly:
  - Use URIs/IRIs for contracts, datasets, and fields.
  - Call JSON-LD/REST endpoints to resolve metadata.
  - Use SPARQL or graph queries when integrating with internal knowledge graphs.

### 2.4 Pain Points

- Unstable or poorly versioned APIs (REST/GraphQL) and SDKs.
- Noisy or opaque error responses from:
  - CLI validation service.
  - DQ/compliance APIs.
- Complexity of handling multiple contract standards and versions without clear canonical rules.
- Semantic/RDF APIs that are hard to consume programmatically or poorly documented.

### 2.5 Needs from the Platform

- High-quality **developer experience**:
  - Versioned REST and GraphQL APIs.
  - Strong Python and JS SDKs.
  - Clear examples for all three intake flows via code.
- Stable **HubContract** schemas and documented mapping to ODCS/DataContract.com.
- A consistent **Job model**:
  - Standardized `Job` endpoints, fields, and statuses for DQ, compliance, validation, and semantic mapping.
- Clear semantics around:
  - Sampling vs full-scan for DQ.
  - Heuristic nature and thresholds of compliance checks.
- Semantic APIs that:
  - Make URI structures predictable.
  - Provide JSON-LD representations and an accessible SPARQL endpoint.
- Respect for multi-tenancy:
  - Ability to act as a given tenant via APIs, with least-privilege tokens and clear tenant-scoping rules.

---

## Persona 3 – Compliance & Privacy Officer

**Aliases:** DPO, Privacy Officer, Compliance Manager, Legal Counsel  
**Typical Role Mapping:** Tenant **Auditor / Compliance Officer**  
**Seniority:** Senior  
**Technical level:** Low to medium – understands data categories and regulations; not code

### 3.1 Summary

Responsible for ensuring the tenant’s data use and published assets comply with relevant regulations (GDPR, LGPD, CCPA, HIPAA, SOX, etc.). Does not operate data pipelines but must be able to inspect assets, interpret risk, and work with Data Product Owners to remediate issues.

They rely heavily on **compliance reports**, **audit logs**, and **semantic tagging** (PII, sensitive data types, jurisdictions).

### 3.2 Goals

- Ensure that **all stored datasets** passed the compliance gate:
  - No obviously non-compliant datasets in the hub.
- Maintain strong **auditability**:
  - Who ran checks, when, on what, and what the results were.
- Quickly identify risky datasets:
  - Especially those with personal or special-category data (or borderline cases).

### 3.3 Key Responsibilities / Tasks

- Review results from **Data Compliance Check as a Service**:
  - For each asset:
    - `overall_status` (`PASS`, `FAIL`, `WARN`).
    - `risk_level` (`LOW`, `MEDIUM`, `HIGH`).
    - Detected categories (e.g. `PII_DIRECT_EMAIL`, `PAYMENT_CARD`).
    - Applicable regulations (GDPR, LGPD, etc.).
  - Understand that:
    - The platform **fails closed**: non-compliant data is never stored.
    - Detection is heuristic; they determine if additional controls or contract changes are needed.

- Work with Data Product Owners and Tenant Admins to:
  - Decide which assets can be used for sensitive internal use cases.
  - Approve or veto publishing assets to the external marketplace (business process, not a technical override).

- Use **audit logs** (read-only, tenant-scoped) to:
  - See which jobs (compliance, DQ) were run and how issues were resolved.
  - Prepare documentation for regulators or internal audits.
  - Demonstrate retention and traceability (3-year log preservation).

- Use **semantic search and filters** to:
  - Find all assets that involve certain risk types:
    - PII, health data, financial identifiers, cross-border data.
  - Identify assets with specific contract features:
    - Jurisdiction tags, retention periods, legal bases, or consent requirements.

### 3.4 Pain Points

- Overly technical interfaces (raw JSON, CLI logs, RDF graphs).
- Difficulty tracing the history of a problematic dataset across versions and checks.
- Lack of a catalog-level view of risk and compliance coverage.

### 3.5 Needs from the Platform

- Business-friendly dashboards that show, per asset and per tenant:
  - Compliance status and risk levels.
  - DQ/compliance history and trends.
  - Outstanding issues requiring remediation.
- Ability to:
  - Mark assets with **business-level labels** such as “Approved for internal use”, “Not approved for external sharing”, “Under review” (even though they cannot disable the technical compliance gate).
  - Filter and export **audit trails** by regulation, asset, job type, and date range.
- Semantic views to:
  - Highlight PII/sensitive fields and their use context (e.g. joined with other assets, shared externally).
  - Answer questions like:
    - “All datasets involving EU subjects and health data.”
    - “All assets with retention > 5 years that are published to the marketplace.”

---

## Persona 4 – Data Consumer / Buyer

**Aliases:** Data Scientist, Analyst, Product Manager, Business User, External Buyer  
**Typical Role Mapping:** Tenant **Data Consumer** (internal or external to provider tenant)  
**Seniority:** Junior to senior  
**Technical level:** Variable – from low (business user) to high (data scientist)

### 4.1 Summary

Uses the hub to **discover, evaluate, and acquire** data assets. May be internal to a tenant (reusing internal assets) or external (cross-tenant marketplace buyer). Cares about relevance, quality, and compliance **signals**, but not about the underlying mechanics.

### 4.2 Goals

- Quickly find datasets matching their **business questions** or analysis needs.
- Trust that:
  - Data is compliant (the risky stuff never made it into the platform).
  - Data quality is known and at least measured.
- Purchase or gain access with transparent cost and licensing.

### 4.3 Key Responsibilities / Tasks

- Use tenant catalog and **marketplace UI** to:
  - Search/filter by domain, ontology concept, field names, geography, time coverage.
  - View a friendly, human-readable contract summary:
    - Schema and examples.
    - Usage constraints and license.
    - Contact/owner.

- Evaluate **trust indicators**:
  - DQ results summarized as scores/badges (e.g. “Quality Score: 92/100”).
  - Compliance badges (e.g. “No direct PII stored”, “GDPR considerations documented”).
  - Marketplace reviews or usage metrics (future feature).

- Use ecommerce flows to:
  - Select access type:
    - One-off download.
    - Subscription.
    - Usage-based API access.
  - Complete checkout as an individual or on behalf of their company/tenant.

- After purchase or approval:
  - See assets in an **“Owned Assets”** view.
  - Download data or connect via API/SDK using their tenant’s credentials.
  - Optionally request re-validation or updated versions (subject to license & platform features).

### 4.4 Pain Points

- Dense or confusing legal language in contracts.
- Fear that purchased data is low-quality or outdated despite passing gates.
- Unclear pricing or billing units (e.g. cost per DQ run, per GB, etc.).

### 4.5 Needs from the Platform

- Clear, concise dataset overviews with:
  - Schema + sample rows.
  - Quality & compliance summaries (without overwhelming details).
  - Update frequency and data freshness.
- Simple, transparent pricing and licensing information:
  - Clear units (runs, GB, downloads, seats).
- Straightforward access management:
  - See what assets they have entitlements for.
  - Obtain credentials for API access easily, within tenant limits and rate limits.
- Optional semantic search:
  - Find assets by concept/topic instead of technical table names (e.g. “customer churn”, “card transaction aggregates”).

---

## Persona 5 – Marketplace Operator / Platform Admin

**Aliases:** Platform Owner, Product Manager, Operations Lead, Business Owner  
**Typical Role Mapping:** **Platform-level Admin/Operator** (not tied to a single tenant)  
**Seniority:** Senior  
**Technical level:** Medium – understands KPIs, compliance, and some technical constraints; not necessarily coding

### 5.1 Summary

Runs the overall data hub and marketplace. Responsible for the product strategy, partner relationships, platform-level compliance posture, and profitability. They operate across tenants and need cross-cutting views: usage, quality, compliance, and revenue.

### 5.2 Goals

- Grow both **supply** (data providers) and **demand** (data consumers).
- Maintain platform-wide **trust**:
  - Consistent DQ/compliance gates.
  - Robust audit logs.
  - Region-based data residency.
- Ensure accurate **billing and cost control**, including:
  - DQ/compliance run costs.
  - API usage.
  - Marketplace transactions.

### 5.3 Key Responsibilities / Tasks

- Configure platform-level defaults:
  - Supported ODCS/DataContract versions and CLI versions.
  - Default DQ profile (`intake_basic`) and compliance thresholds (e.g. 1% PII).
  - Per-plan or per-tenant limits and rate limits (e.g. max DQ/compliance runs).

- Oversee **multi-tenancy & KYC** at a high level:
  - Approve tenant onboarding (subject to external KYC/KYB policy).
  - Track tenant KYC status and restrict publishing for non-verified tenants.

- Monitor and manage the **marketplace**:
  - Approve or de-list public assets.
  - Monitor global metrics:
    - Total assets, public assets, active buyers/sellers.
    - DQ and compliance workload and failure rates.
    - Revenue and cost (including infra cost of jobs).

- Ensure the platform is **audit-ready**:
  - Confirm that important actions (uploads, checks, validations, purchases, access) are logged.
  - Work with legal/compliance functions to respond to regulatory inquiries.

### 5.4 Pain Points

- Fragmented view across billing, quality, compliance, and usage.
- Difficulty explaining platform behavior and guarantees to large enterprise clients and regulators.
- Managing fair, clear policies across very diverse tenants and use cases.

### 5.5 Needs from the Platform

- Cross-tenant admin dashboards showing:
  - Revenue, costs, and margins (e.g. DQ/compliance run costs, infrastructure usage).
  - Asset counts, tenant growth, and adoption metrics.
  - Error rates and SLA performance for core services.

- Controls to:
  - Adjust default DQ/compliance policies and thresholds.
  - Configure rate limits and quotas for tenants or plans.
  - Suspend tenants or hide assets when necessary (for policy or security reasons).

- Strong observability and governance integration:
  - Searchable audit logs across tenants (for platform admins only).
  - Ability to export or mirror audit events into external governance tools.

---

## Persona 6 – External Developer / Integrator

**Aliases:** Partner Engineer, Platform Integrator, Solution Architect  
**Typical Role Mapping:** Acts as **Developer** within a tenant or as a partner building atop the hub  
**Seniority:** Mid to senior  
**Technical level:** High – very comfortable with APIs, SDKs, auth, multi-tenant patterns, and semantic tech

### 6.1 Summary

Builds products or internal tools that integrate deeply with the hub: custom portals, data catalogs, internal governance dashboards, data science platforms, etc. Rarely uses the web UI beyond initial testing; lives in code, docs, and API consoles.

### 6.2 Goals

- Embed the hub’s capabilities into other systems:
  - Automated onboarding flows.
  - DQ/compliance checks as embedded services.
  - Semantic discovery capabilities.
- Respect multi-tenancy, security, and rate limits:
  - Correctly act as the right tenant with right roles.
- Expose **semantic views** of assets to other apps using URIs, JSON-LD, and SPARQL.

### 6.3 Key Responsibilities / Tasks

- Implement integrations that:
  - Register data and data contracts via **REST/GraphQL** APIs.
  - Upload files or reference external storage (as supported).
  - Trigger DQ and Compliance checks, then:
    - Poll job endpoints for status.
    - Consume results and integrate into downstream UIs or logs.
  - Manage entitlements and asset visibility for their users.

- Work with the **job/run model**:
  - Use `/jobs/{job_id}` to track long-running operations.
  - Handle `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED` and retries gracefully.

- Use the **semantic layer** to:
  - Resolve URIs into JSON-LD metadata.
  - Call the SPARQL endpoint for concept-based queries (e.g. find all datasets with `ex:PII`).
  - Feed semantic information into internal catalogs or knowledge graphs.

- Use **CLI/SDKs (JS and Python)** to:
  - Prototype and test locally.
  - Package scripts and utilities for internal teams.

### 6.4 Pain Points

- Missing or unclear API reference and lack of end-to-end examples.
- Breaking changes in APIs, schemas, or auth/tenant model.
- Ambiguous rate limits and quotas, making it hard to design robust customer-facing integrations.

### 6.5 Needs from the Platform

- Strong developer tooling:
  - Versioned API docs for REST and GraphQL.
  - Detailed reference for SPARQL endpoint and JSON-LD shapes.
  - Example apps for:
    - Intake flows.
    - DQ/compliance integration.
    - Semantic search.

- Clear and stable **auth and tenant model**:
  - How to represent tenants and roles in tokens/credentials.
  - How to scope all operations correctly to a tenant.

- Transparent limits:
  - Rate limits per API key/tenant.
  - Quotas for DQ/compliance usage.
  - Clear error codes when limits are hit.

- Easy access to **sandbox environments**:
  - Test tenants with fake billing.
  - Safe DQ/compliance tests on synthetic data.

---

## How These Personas Relate to Core Capabilities

- **Data Contract Standards & HubContract / DataContract CLI**
  - Critical for:  
    - **Data Product Owner** (via UI)  
    - **Data Engineer / Contract Author** (via code & CLI)  
    - **External Developer / Integrator** (via APIs/CLI)
  - Platform behavior: only `VALID` contracts become active; `WARNING_ONLY` carries UI warnings.

- **Data Quality as a Service (Great Expectations / Soda)**
  - Visible to:  
    - **Data Product Owner** (intake gate, quality score)  
    - **Data Consumer/Buyer** (trust badges/summaries)  
    - **Compliance Officer** (context for risk evaluation)  
    - **Marketplace Operator** (workload & cost metrics)
  - Automatable by:  
    - **Data Engineer**, **External Developer**.

- **Compliance Check as a Service**
  - Primary concern for:  
    - **Compliance & Privacy Officer**  
    - **Marketplace Operator / Platform Admin**
  - Platform design:  
    - Fail-closed gate at intake (no override).  
    - Scan-only mode for external assets.  
    - Heuristic detection with configurable thresholds and clear risk levels.

- **Semantic/Ontology Layer (URIs, RDF, SPARQL, JSON-LD)**
  - Directly used by:  
    - **External Developer / Integrator**  
    - **Data Engineer** (for integrations)
  - Surfaced indirectly to:  
    - **Data Product Owner**, **Data Consumer**, **Compliance Officer** as better search, semantic filters, and PII/sensitive tags.

- **Multi-Tenancy & Roles**
  - **Tenant Admin** role affects:  
    - Data Product Owners (permissions, thresholds)  
    - Data Engineers (pipeline permissions)  
    - Compliance Officers (read-only access to logs and reports)  
    - Data Consumers (entitlements)
  - **Platform Admin / Marketplace Operator** operates across tenants and defines defaults, limits, and global policies.

- **Ecommerce / Marketplace & Billing**
  - Directly used by:  
    - **Data Consumer/Buyer** (purchase flow)  
    - **Marketplace Operator / Platform Admin** (pricing, revenue, cost tracking)
  - Indirectly used by:  
    - **Data Product Owner** (publishing and pricing assets)  
    - **External Developer** (integrated purchase/access flows)

- **Audit Trails & Job Model**
  - Essential for:  
    - **Compliance & Privacy Officer** (proving checks ran)  
    - **Marketplace Operator / Platform Admin** (governance)  
    - **Data Engineer / External Developer** (debugging and observability)
  - Jobs and audit logs tie together:
    - Each major operation (checks, validations, mappings) is both a `Job` and an `Audit` event.

These personas are **living documents** and should evolve as we validate real users, refine the product, and clarify the boundaries between MVP and future phases.
