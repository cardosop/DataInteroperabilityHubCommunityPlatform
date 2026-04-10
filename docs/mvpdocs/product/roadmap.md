# Roadmap

Post-MVP roadmap for the Meshant Data Interoperability Hub. Items are
organised by phase (near-term) and then by future track (unscheduled).

---

## Phase 218 -- Terraform Destroy Workflow Parity

Bring Terraform destroy workflows to the same level of automation and
safety as apply workflows. Includes plan-before-destroy gates, manual
approval steps, and state-lock checks in the CI/CD pipeline.

---

## Future Tracks

### BaaS Dedicated Instances

Provision isolated backend instances per tenant with their own compute,
storage, and network boundaries. Includes SDK download portals and
per-key billing.

### Virtualization (ODBC / JDBC)

Expose virtual datasets through ODBC and JDBC drivers so consumers can
query data products from BI tools without downloading files.

### Data Mesh Federation

First-class domain modelling, mesh topology management, and federated
governance policies. Domain owners manage their own catalogs while the
platform enforces cross-domain interoperability rules.

### ML / AI Model Serving

Register, train, and serve ML models on platform data. Covers anomaly
detection, recommendation engines, auto-classification, and inference
endpoints.

### Transformation Pipelines

In-platform ETL/ELT pipelines that read from ingested datasets, apply
user-defined transformations, and write results back as new versioned
datasets.

### Social Features

Ratings, reviews, comments, and communities attached to marketplace
listings. Enables reputation signals and peer feedback for data products.

### Scheduled Ingestion and Export

Periodic, automated data pulls (ingestion) and pushes (export) on
configurable cron schedules with retry and alerting.

### GraphQL API

A GraphQL schema exposing the same capabilities as the REST API, aimed
at frontend and mobile integrations that benefit from flexible queries.

### JavaScript SDK

A first-party JavaScript/TypeScript SDK with the same coverage as the
Python SDK, targeting Node.js and browser environments.

### Plugin Framework

An extension mechanism that lets third-party developers register custom
DQ checks, compliance rules, normalizers, and webhook handlers.

### Multi-Version Documentation

Versioned documentation site (MkDocs) so users can read docs matching
their deployed platform version rather than only the latest.

---

## How Items Move

Features move from this roadmap into a numbered phase when they are
scheduled for implementation. Each phase produces entries in the
[Changelog](changelog.md). The [MVP Features](mvp-features.md) page
marks deferred items that appear here.
