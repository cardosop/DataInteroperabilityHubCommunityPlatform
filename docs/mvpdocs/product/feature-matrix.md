# Feature Matrix

Feature domain mapped against personas and MVP tier. Extracted from the
Product Guide and MVP Scope documents.

## Personas

| Abbreviation | Persona |
|--------------|---------|
| DPO | Data Product Owner |
| DE | Data Engineer / Contract Author |
| CPO | Compliance & Privacy Officer |
| DC | Data Consumer / Buyer |
| MPA | Marketplace Operator / Platform Admin |
| DEV | External Developer / Integrator |

## Cell Values

- **Primary** -- the persona who owns or drives the capability.
- **Use** -- the persona actively uses the capability day to day.
- **Read** -- the persona has read or view access.
- **Admin** -- administrative or oversight access.
- **--** -- not applicable to this persona.

---

## Matrix

| Feature Domain | DPO | DE | CPO | DC | MPA | DEV | MVP Tier |
|----------------|-----|----|-----|----|-----|-----|----------|
| Auth (login, JWT, API keys, SSO) | Use | Use | Use | Use | Admin | Use | Fully included |
| Tenants (multi-tenancy, isolation) | Use | Use | Read | Use | Primary | -- | Fully included |
| Roles and RBAC | Use | Use | Read | Use | Primary | Read | Fully included |
| Assets (3 onboarding flows, catalog) | Primary | Use | Read | Read | Admin | Use | Fully included |
| Contracts (ODCS, HubContract, validation) | Primary | Primary | Read | Read | Admin | Use | Fully included |
| Datasets (CRUD, versioning, time-travel) | Use | Primary | Read | Read | Admin | Use | Fully included |
| Files (multipart upload, hashing) | Use | Primary | -- | Read | Admin | Use | Fully included |
| Data Quality (intake gate, DQ runs) | Use | Use | Primary | Read | Admin | Use | Fully included |
| Compliance (PII detection, scan-only) | Read | Use | Primary | -- | Admin | Use | Fully included |
| Marketplace (listings, preview, trust) | Primary | -- | Read | Primary | Admin | Use | Fully included |
| Orders and Entitlements | Use | -- | -- | Primary | Admin | Use | Fully included |
| Governance (access requests, ABAC) | Use | Use | Primary | Use | Admin | -- | Fully included |
| Retention and Consent | Read | -- | Primary | -- | Admin | -- | Fully included |
| GDPR Rights (export, erasure) | Read | -- | Primary | Use | Admin | -- | Fully included |
| Search (full-text, per-resource) | Use | Use | Use | Primary | Admin | Use | Fully included |
| Audit (event log, CSV/JSON export) | Read | Read | Primary | -- | Admin | Read | Fully included |
| Jobs (status, cancellation) | Use | Primary | Read | Read | Admin | Use | Fully included |
| Semantic Layer (URIs, JSON-LD, RDF, SPARQL) | Use | Primary | Read | Read | Admin | Primary | Partial |
| Webhooks (event subscriptions) | Use | Primary | -- | Use | Admin | Primary | Fully included |
| Billing (plan tiers, metering) | Read | -- | -- | Read | Primary | Read | Fully included |
| Observability (metrics, freshness, lineage) | Use | Primary | Read | Read | Admin | Use | Fully included |
| Versioning (contracts, datasets) | Use | Primary | Read | Read | Admin | Use | Fully included |
| Orchestration (workflows) | Use | Primary | -- | -- | Admin | Use | Fully included |
| KYC (tenant verification) | -- | -- | -- | -- | Primary | -- | Fully included |

---

## Post-MVP Feature Domains

These domains are not delivered in the MVP. No persona has access at launch.

| Feature Domain | Target Personas | Notes |
|----------------|-----------------|-------|
| BaaS (Backend as a Service) | DPO, DEV, MPA | Dedicated instances, SDK portals |
| Virtualization (ODBC/JDBC) | DE, DEV, DC | Virtual dataset query layer |
| Data Mesh (domains, topology) | DPO, DE, MPA | Federated governance |
| ML / AI (models, training, inference) | DE, DEV, MPA | Anomaly detection, recommendations |
| Transformation pipelines | DE, DEV | ETL/ELT within platform |
| Social (ratings, reviews) | DPO, DC | Marketplace social layer |
| Scheduled Ingestion | DE, DPO | Periodic automated data pulls |
| Scheduled Export | DE, DPO | Periodic automated data pushes |

---

## Reading the Matrix

A Data Product Owner (DPO) who needs to understand which capabilities they
own should scan the DPO column for "Primary" entries. A Platform Admin (MPA)
looking for administrative duties should scan for "Admin" entries.

The MVP Tier column indicates whether the feature ships at launch (Fully
included), ships with limited scope (Partial), or is deferred (Post-MVP).
See [MVP Features](mvp-features.md) for detailed per-feature breakdowns.
