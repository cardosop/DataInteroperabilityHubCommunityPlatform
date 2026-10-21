# DataInteroperabilityHub (core)

The open-source core of the Meshant Data Interoperability Hub: a
multi-tenant data platform for governed asset catalogs, data contracts,
data quality, compliance, and cross-tenant data sharing.

Licensed under the **Apache License 2.0** (see [LICENSE](LICENSE)).

## Open-core boundary (please read before contributing)

This repository contains the **core platform only**. The following
capabilities are part of the hosted **Meshant SaaS** and are **not open
to contribution**:

- **Semantic layer** — ontology management, SPARQL, RDF ingestion,
  Linked Data Notifications, GraphQL-LD
- **Marketplace** — listings, orders, entitlements, payments, KYB/KYC,
  trust signals
- **Billing / BaaS / rate limiting** — subscriptions, usage metering,
  API gateway tiers
- **ML/AI and social/community features**

Issues and PRs in these domains will be closed as out of scope. If you
need these capabilities, deploy them via the hosted SaaS or contact
Meshant for enterprise licensing.

## Quickstart (5 minutes)

Prerequisites: Docker + Docker Compose v2.

```bash
git clone https://github.com/<org>/DataInteroperabilityHub.git
cd DataInteroperabilityHub
make quickstart
```

`make quickstart` brings up the core stack (Postgres, Redis, MinIO,
API, worker, frontend), runs migrations, seeds a demo tenant, and opens
the UI at http://localhost:3000.

**First walkthrough** — the flagship loop in one sitting:

1. **Ingest a sample CSV** — `http://localhost:3000/files` → upload
   `examples/sample_orders.csv`.
2. **Create an asset** — `/assets/create` using the uploaded file.
3. **Attach a data contract** — `/contracts/create`, select the asset,
   paste the ODPS JSON from `examples/sample_contract.odps.json`.
4. **Preview the listing** — the marketplace surface is a SaaS feature;
   on the core deployment the route shows the capability notice
   ("SaaS feature — not available in this deployment"). Connect your
   deployment to the hosted Meshant marketplace to publish.

## Development

- Backend tests (core-only): `make test-core`
- Boundary gate (GATE-29): `make boundary-check`
- Full contribution guide: [CONTRIBUTING.md](CONTRIBUTING.md)

## Documentation

Docs build with mkdocs: `mkdocs serve`. Architecture overview in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
