# Glossary

Canonical definitions of terms used throughout the Meshant platform. Each entry
includes a brief definition and a link to the relevant concept page where
applicable.

---

## A

**API Key** -- A long-lived credential used for service-to-service
authentication, scoped to a single tenant and a defined set of permissions.
API keys can be created, rotated, and revoked through the CLI or API.
[Full reference](../concepts/users-and-roles.md)

**Asset** -- A data product managed by the platform: a file, dataset, or
collection with metadata, quality scores, and compliance status. Assets are the
foundational entity in Meshant and belong to exactly one tenant.
[Full reference](../concepts/assets.md)

**Audit Event** -- An immutable record of a significant action performed on the
platform, capturing who performed the action, what changed, when it occurred,
and which resource was affected. Audit events are retained for a minimum of
three years. [Full reference](../concepts/audit-events.md)

## B

**Billing** -- The subsystem that tracks resource usage, subscription tiers
(Free, Professional, Enterprise), and payment status for each tenant.
[Full reference](../concepts/billing.md)

## C

**Compliance Run** -- An automated evaluation of one or more assets against the
regulatory rule sets (GDPR, HIPAA, SOX, LGPD, CCPA) configured for the
tenant. Compliance runs produce pass/fail results and are recorded in the audit
trail. [Full reference](../concepts/compliance-runs.md)

**Consent** -- A record of a data subject's permission for specific processing
activities, including the scope, timestamp, and method of collection. Consent
can be withdrawn at any time, triggering a review of affected assets.
[Full reference](../compliance/gdpr-rights.md)

**Contract (Data Contract)** -- A formal specification of the schema, quality
expectations, and SLA that an asset must satisfy. Contracts are versioned and
enforced through data quality runs. [Full reference](../concepts/contracts.md)

## D

**Data Quality Run** -- An automated evaluation of an asset against the quality
rules defined in its data contract, checking for schema conformance, null
rates, uniqueness, and custom validation rules.
[Full reference](../concepts/dq-runs.md)

**Dataset** -- A structured tabular asset (as opposed to an unstructured file).
Datasets carry schema information, row counts, and column-level statistics.
[Full reference](../concepts/datasets.md)

## E

**Entitlement** -- A permission grant that controls whether a user or tenant
may access a specific marketplace listing or asset. Entitlements are created
when an order is fulfilled.

## F

**File** -- An unstructured asset such as a CSV, Parquet, JSON, or binary file
uploaded to the platform. Files are stored in the tenant's configured storage
region. [Full reference](../concepts/assets.md)

## G

**Governance Policy** -- A tenant-level rule that defines how data must be
handled, covering retention periods, access restrictions, masking requirements,
and compliance obligations. [Full reference](../concepts/governance.md)

## J

**Job** -- A unit of background work executed by the platform, such as an
ingestion, transformation, export, or compliance scan. Jobs have lifecycle
states (pending, running, succeeded, failed) and are tracked in the audit
trail. [Full reference](../concepts/jobs.md)

**Journey** -- A guided, multi-step workflow that walks a user through a
business process end-to-end, such as onboarding a new data source or
publishing an asset to the marketplace.

## L

**Lineage** -- A directed graph capturing the upstream and downstream
relationships between assets, showing how data flows through
transformations, enrichments, and aggregations.
[Full reference](../concepts/lineage.md)

**Listing (Marketplace)** -- A published entry in the Meshant marketplace that
makes an asset discoverable and requestable by users in other tenants.
Listings include descriptions, pricing tiers, sample data, and usage terms.
[Full reference](../concepts/marketplace-listings.md)

## M

**MVP** -- Minimum Viable Product. The initial release scope of the Meshant
platform, encompassing core asset management, compliance, marketplace, and
governance capabilities. Features explicitly marked as "post-MVP" are planned
but not included in the first release.

## O

**Orchestration** -- The subsystem responsible for scheduling and coordinating
multi-step data pipelines, including ingestion, transformation, quality checks,
and export jobs. [Full reference](../concepts/orchestration.md)

**Order** -- A request by a consumer to access a marketplace listing. Orders
go through an approval workflow and, once fulfilled, create entitlements for
the requesting user or tenant.

## P

**Persona** -- A named user archetype (e.g. Data Producer, Data Consumer, Data
Steward, Platform Admin) that defines the typical goals, permissions, and
workflows for a category of users.
[Full reference](../personas/_persona-overview.md)

**Post-MVP** -- Features and capabilities that are planned for future releases
beyond the initial MVP launch. Post-MVP items are tracked on the product
roadmap.

## R

**Retention Policy** -- A governance rule that specifies how long data and
audit records must be retained before they may be archived or deleted.
Retention periods can only be extended, never shortened.
[Full reference](../concepts/governance.md)

## S

**Search** -- The full-text and faceted search subsystem that allows users to
discover assets, datasets, and marketplace listings by keyword, tag, domain,
quality score, and compliance status.
[Full reference](../concepts/search.md)

**Semantic Resource** -- A metadata entity that represents a business concept
(e.g. "Customer", "Transaction") independently of any specific physical
dataset, enabling concept-level discovery and mapping.
[Full reference](../concepts/semantic-resources.md)

## T

**Tenant** -- An isolated organizational unit within the platform. Each tenant
has its own users, assets, compliance configuration, billing, and storage
region. Cross-tenant access is denied by default.
[Full reference](../concepts/tenants.md)

## U

**Use Case** -- A documented end-to-end workflow that combines multiple
platform capabilities to solve a specific business problem, identified by
a code such as UC-GOV-ADV-002.
[Full reference](../use-cases/)

**User** -- An authenticated individual who interacts with the platform.
Users belong to one or more tenants and are assigned roles (viewer, editor,
admin, superadmin) that govern their permissions.
[Full reference](../concepts/users-and-roles.md)

## V

**Versioning** -- The mechanism by which assets, data contracts, and schemas
maintain a history of changes. Each version is immutable once published, and
previous versions remain accessible for auditing and rollback.
[Full reference](../concepts/versioning.md)

## W

**Webhook** -- A user-configured HTTP callback that the platform invokes when
specific events occur (e.g. asset published, compliance run failed). Webhooks
enable integration with external systems and notification pipelines.
[Full reference](../concepts/webhooks.md)
