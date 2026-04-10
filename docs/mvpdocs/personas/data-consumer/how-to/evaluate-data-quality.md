# How-To: Evaluate Data Quality

Before purchasing or subscribing to a dataset, you should understand the
trust indicators Meshant provides. This guide explains how to interpret
quality scores, compliance badges, lineage, and community signals.


## Quality Scores

Every asset in Meshant can be evaluated by automated Data Quality (DQ)
checks. The results appear on the marketplace listing detail page.

### Overall Quality Status

| Status | Meaning |
|--------|---------|
| **PASSED** | All DQ checks passed within configured thresholds. |
| **WARNING** | Some checks passed but one or more fell below warning thresholds. |
| **FAILED** | One or more critical checks failed. |
| **PENDING** | DQ checks have not yet run or are in progress. |

### Individual DQ Dimensions

Meshant evaluates the following quality dimensions (when configured by the
provider):

- **Completeness** -- Percentage of non-null values across required columns.
- **Uniqueness** -- Percentage of distinct values where uniqueness is expected.
- **Validity** -- Percentage of values conforming to format, range, or regex
  rules.
- **Freshness** -- Time since the last data update. Stale data triggers a
  freshness warning.
- **Consistency** -- Cross-column and cross-table referential integrity.

Each dimension displays a numeric score (0--100) and a pass/warn/fail
indicator.

### Viewing DQ Details via CLI

```bash
datahub-cli dq status --asset-id <asset-id> --format table
```

This returns the most recent DQ check results for the asset, broken down
by dimension.


## Compliance Badges

Compliance badges indicate whether an asset has passed automated compliance
scans for specific regulations.

| Badge | Regulation | What It Checks |
|-------|-----------|----------------|
| GDPR | EU General Data Protection Regulation | PII detection, consent tracking, retention policies |
| HIPAA | US Health Insurance Portability and Accountability Act | PHI detection, access controls, audit trail |
| SOC2 | Service Organization Control 2 | Access logging, encryption, change management |

**Badge states:**

- **COMPLIANT** (green) -- The latest scan passed all checks.
- **NON_COMPLIANT** (red) -- The latest scan found violations.
- **PENDING** (gray) -- No scan has been run yet.

Hover over a badge in the web UI to see the scan date and a summary of
findings. For detailed results, ask the Data Product Owner or Compliance
Officer.


## Lineage

The lineage view on a listing detail page shows a directed graph of:

- **Source systems** -- where the data originates.
- **Transformation steps** -- how the data was processed.
- **Downstream consumers** -- who else uses this data.

Lineage helps you assess provenance: is the data sourced from trusted
systems? How many transformation steps exist between raw source and the
published asset?


## Community Ratings and Reviews

Marketplace listings can receive star ratings (1--5) and text reviews from
other Data Consumers. Look for:

- **Average rating** -- displayed on the listing card and detail page.
- **Review count** -- more reviews generally indicate a more established
  dataset.
- **Recent reviews** -- check for recent feedback about data freshness or
  quality issues.


## Combining Signals

No single indicator tells the whole story. A recommended evaluation
checklist:

1. Is the quality status **PASSED**?
2. Are the relevant compliance badges **COMPLIANT**?
3. Is the freshness score within your tolerance (e.g., updated in the
   last 24 hours)?
4. Does the lineage trace back to a trusted source system?
5. Does the schema preview match your expected structure?
6. Are community ratings above 3.5 stars with recent positive reviews?

If any of these checks raise concerns, consider contacting the Data
Product Owner before purchasing.


## See Also

- [How-To: Discover Datasets](discover-datasets.md)
- [How-To: Purchase and Access](purchase-and-access.md)
- [Data Consumer Reference](../reference.md)
