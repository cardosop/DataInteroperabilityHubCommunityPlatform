# How-To: Discover Datasets

This guide covers searching and filtering the Meshant marketplace to find
datasets that match your requirements.


## Search via the Web UI

1. Navigate to **Marketplace** in the left sidebar.
2. Enter keywords in the **search bar** (e.g., "revenue forecast Q4").
3. Use the **filter panel** on the left to narrow results by:
   - **Domain** -- business domain such as `finance`, `healthcare`, or
     `marketing`.
   - **Classification** -- data sensitivity level (`PUBLIC`, `INTERNAL`,
     `CONFIDENTIAL`, `RESTRICTED`).
   - **Quality Status** -- result of the latest DQ check (`PASSED`,
     `WARNING`, `FAILED`).
   - **Compliance Status** -- result of the latest compliance scan
     (`COMPLIANT`, `NON_COMPLIANT`, `PENDING`).
   - **Tags** -- provider-defined labels (e.g., `pii`, `real-time`,
     `aggregated`).
4. Sort results by **relevance**, **date created**, or **date indexed**.
5. Click a listing card to open its detail page.


## Search via the CLI

The `datahub-cli search search` command supports all the same filters:

```bash
datahub-cli search search \
  --query "customer churn" \
  --domain "analytics" \
  --classification "INTERNAL" \
  --quality-status "PASSED" \
  --tags "ml-ready,monthly" \
  --sort-by relevance \
  --sort-order desc \
  --limit 20 \
  --offset 0 \
  --format table
```

### CLI Filter Reference

| Flag | Type | Description |
|------|------|-------------|
| `--query`, `-q` | string (required) | Free-text search query |
| `--type` | enum | `CONTRACT`, `ASSET`, or `DATASET` |
| `--domain` | string | Business domain filter |
| `--classification` | string | Data classification filter |
| `--owner` | string | Filter by owner (provider) ID |
| `--tags` | string | Comma-separated tag filter |
| `--quality-status` | string | DQ status filter |
| `--compliance-status` | string | Compliance status filter |
| `--sort-by` | enum | `relevance`, `created_at`, `indexed_at` |
| `--sort-order` | enum | `asc` or `desc` |
| `--limit` | int | Results per page (default 20, max 100) |
| `--offset` | int | Pagination offset |
| `--format` | enum | `json` or `table` |


## Search via the SDK

```python
from datahub_interoperability import DataHubClient

client = DataHubClient.from_env()
results = client.search.search(
    query="customer churn",
    domain="analytics",
    quality_status="PASSED",
    limit=20,
)

for item in results:
    print(f"{item.id}  {item.name}  [{item.quality_status}]")
```


## Tips for Effective Search

- **Start broad, then filter.** Begin with a short keyword query and
  progressively add filters to narrow results.
- **Use domain filters** when you know the business area. This avoids
  irrelevant matches from other domains.
- **Prefer quality-gated results.** Adding `--quality-status PASSED`
  ensures you only see datasets that have passed automated DQ checks.
- **Check compliance status** for regulated data. Filter by
  `--compliance-status COMPLIANT` when working with PII or healthcare
  data.
- **Bookmark listings** in the web UI for quick access later.


## See Also

- [How-To: Evaluate Data Quality](evaluate-data-quality.md)
- [How-To: Purchase and Access](purchase-and-access.md)
- [Reference: Search API](../reference.md)
