# Data Product Owner (DPO)

> Also known as: Data Steward, Domain Data Owner, Data Product Manager

## Who You Are

You are a mid-to-senior professional responsible for publishing datasets as
trusted data products within the Meshant Data Interoperability Hub. Your day
revolves around curating metadata, defining data contracts, ensuring that
every dataset clears its Data Quality (DQ) and compliance gates before it
reaches consumers, and deciding whether a product is published to the
internal catalog or listed on the marketplace for external monetization.

Typical job titles that map to this persona:

- Data Product Owner / Manager
- Data Steward or Data Custodian
- Domain Data Owner
- Head of Data Products

## What You Care About

| Priority | Description |
|----------|-------------|
| Trustworthiness | Every published asset must pass DQ and compliance checks. |
| Discoverability | Rich metadata and clear contracts so consumers find and understand your data. |
| Lifecycle control | Move assets through draft, active, for-sale, deprecated, and archived states. |
| Monetization | Set pricing tiers and visibility rules for marketplace listings. |
| Auditability | Full history of who changed what, when, and why. |

## Your MVP Capabilities

Within the Meshant MVP you can:

1. **Execute three onboarding flows** -- choose the path that fits your
   situation:
   - *Data First* -- upload a file or connect a source, let Meshant infer
     the schema and generate a draft contract.
   - *Contract First* -- define the contract YAML up front, then attach data
     that conforms to it.
   - *Contract Only* -- register a contract without any data (useful for
     pre-publication planning).

2. **Manage the asset lifecycle** -- transition an asset through its states:
   `draft -> active -> for_sale -> deprecated -> archived`.

3. **Review DQ and compliance reports** -- inspect per-column quality scores,
   rule violations, and compliance risk categories before deciding to publish.

4. **Monitor job statuses** -- track ingestion, DQ, and compliance jobs from
   submission through completion or failure.

5. **Publish to marketplace or internal catalog** -- control visibility
   (private, organization, public) and set pricing for external consumers.

6. **Manage data contracts** -- author, validate, version, and attach YAML
   contracts that describe schema, SLAs, and quality expectations.

## Key Journeys

These end-to-end journeys walk you through common workflows step by step:

- [Onboard a New Asset (Data-First Flow)](../../journeys/JOURNEY-DPO-001.md)
- [Publish an Asset to the Marketplace](../../journeys/JOURNEY-DPO-002.md)
- [Manage the Asset Lifecycle](../../journeys/JOURNEY-DPO-003.md)
- [Monitor Asset Quality](../../journeys/JOURNEY-DPO-004.md)
- [Configure Data Contracts](../../journeys/JOURNEY-DPO-005.md)
- [Manage Marketplace Listings](../../journeys/JOURNEY-DPO-006.md)

## Typical Day

1. Check the **Assets** dashboard for any assets stuck in `draft` or with
   failing DQ scores.
2. Review overnight compliance scan results -- address any new PII
   detections or policy violations.
3. Validate an updated data contract submitted by the engineering team.
4. Promote a tested asset from `active` to `for_sale` and configure its
   marketplace listing (pricing, description, sample preview).
5. Archive a deprecated dataset that has been superseded.

## Related Concepts

Dive deeper into the domain objects you work with every day:

- [Assets](../../concepts/assets.md) -- the core publishable unit
- [Contracts](../../concepts/contracts.md) -- schema + SLA + quality rules
- [Data Quality Runs](../../concepts/dq-runs.md) -- automated quality checks
- [Compliance Runs](../../concepts/compliance-runs.md) -- regulatory scans
- [Marketplace Listings](../../concepts/marketplace-listings.md) -- external publication

## Permissions and Roles

The DPO persona maps to the **data_product_owner** role in Meshant RBAC.
This role grants:

- Full CRUD on assets owned by your domain.
- Read access to DQ and compliance run results.
- Write access to marketplace listings for your assets.
- Read-only access to audit events related to your assets.

Your tenant administrator assigns this role. If you need cross-domain access,
request the **data_steward_global** role.

## Get Started

- [5-Minute Quickstart](quickstart.md) -- publish your first asset in under five minutes
- [How-To Guides](how-to/) -- task-oriented recipes for common operations
- [API / CLI / SDK Reference](reference.md) -- every endpoint, command, and class at a glance
