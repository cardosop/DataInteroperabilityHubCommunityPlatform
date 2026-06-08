# Capacity planning addendum — Files & Datasets (Phase 260.0.25)

Canonical capacity models continue in [mvpdocs/operations/capacity-planning.md](mvpdocs/operations/capacity-planning.md).

## Files + Datasets planes (2026)

**Object storage (S3)**

- Presume **1.2× write amplification** (multipart parts + scan copies + versioned dataset snapshots).
- Budget **P95 upload size × daily upload count × 90 days** for hot storage; lifecycle to IA per Terraform module after 90 days.
- Audit `abort-incomplete-multipart` rules (7 days non-prod / prod per bucket class).

**Metadata + versions**

- Each successful dataset version emits **≥1 audit row** plus OpenSearch index work.
- Model **10 versions / active asset / year** for enterprise tenants; alert when `datasets` cardinality per tenant exceeds SLO (`monitoring/prometheus/alerts/datasets-files.yml`).

**Throughput**

- ClamAV scan path is synchronous with upload completion → size worker pool assuming **≤ 30 Mbps sustained / worker** concurrent streams to clamd (`CLAMAV_TIMEOUT_SECONDS`, `CLAMAV_JOB_TIMEOUT_SECONDS`).

Maintain quarterly review with FinOps tying S3 PUT/GET invoices to Prometheus `datasets_files_*` counters.
