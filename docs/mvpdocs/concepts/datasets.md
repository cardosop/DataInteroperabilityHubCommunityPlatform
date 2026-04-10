# Datasets

A dataset in Meshant represents a raw or processed data file that has been uploaded to the platform's managed storage. Datasets are the physical layer beneath [assets](assets.md) -- while an asset carries metadata, governance, and quality information, the dataset holds the actual bytes. A single asset may reference multiple datasets (for example, partitioned Parquet files or a set of CSV extracts).

Datasets are immutable once finalized. Uploading a new version of the data creates a new dataset record linked to the same asset, preserving full history for [lineage](lineage.md) tracking and [audit](audit-events.md) purposes.

## Lifecycle

| State | Description |
|---|---|
| `uploading` | The dataset is being transferred to managed storage. For large files, multipart upload is in progress. |
| `processing` | Upload is complete. The platform is computing checksums, inferring schema, and extracting sample rows. |
| `available` | The dataset is ready for use. DQ and compliance runs can be executed against it. |
| `failed` | Upload or processing encountered an error. The partial data is retained for 24 hours to allow retry. |
| `deleted` | Soft-deleted. The physical bytes are purged after the tenant's configured retention period. |

The transition from `uploading` to `processing` is automatic once the last byte is received and the checksum matches. The transition from `processing` to `available` happens when schema inference and sampling complete without error.

Each state transition is tracked as a [job](jobs.md) and emits a webhook event if the tenant has configured [webhooks](webhooks.md) for dataset events.

## Schema Inference

When a dataset enters the `processing` state, the platform automatically infers its schema. The inference engine examines the first 10,000 rows (or the full dataset if smaller) and determines:

| Property | Description |
|---|---|
| Column names | Extracted from headers (CSV), field names (JSON/Avro), or schema metadata (Parquet/ORC). |
| Data types | Inferred from value patterns: integer, float, string, boolean, date, datetime, binary. |
| Nullable | Whether the column contains any null or missing values. |
| Cardinality | Approximate number of distinct values per column. |
| Sample values | Representative values for each column (up to 10 unique samples). |

The inferred schema is stored on the dataset record and compared against the [contract](contracts.md) schema (if one is bound) to detect schema drift. Inference results are available in the dataset detail view and through the preview API.

## Storage and Checksums

Datasets are stored in the tenant's managed storage with the following guarantees:

- **Encryption at rest** -- All dataset bytes are encrypted using AES-256 with tenant-scoped keys.
- **Checksum verification** -- A SHA-256 checksum is computed on upload and verified on every download. Checksum mismatch triggers an alert.
- **Replication** -- Datasets are replicated across availability zones for durability (99.999999999% durability target).
- **Access logging** -- Every read and write operation on the storage layer is logged for [audit](audit-events.md) purposes.

## Relationships

- **Assets** -- Every dataset belongs to an [asset](assets.md). The asset provides the governance wrapper; the dataset provides the data. Multiple datasets can be attached to a single asset (versioned replacements or partitions).
- **Contracts** -- When a dataset becomes `available`, it can be validated against the [contracts](contracts.md) bound to its parent asset. Schema inference results are compared to contract column definitions.
- **Jobs** -- Upload, processing, and deletion operations are managed as [jobs](jobs.md) with progress tracking.
- **Lineage** -- [Lineage](lineage.md) edges are created when a dataset is produced by a transformation or when it serves as input to a downstream pipeline.
- **DQ Runs** -- [DQ runs](dq-runs.md) operate on the dataset's data, applying the quality rules from the associated contract.
- **Compliance Runs** -- [Compliance runs](compliance-runs.md) scan dataset contents for PII and sensitive data categories.
- **Search** -- Dataset metadata (format, size, row count, schema) is indexed for [search](search.md) and filtering.

## MVP Scope

**Available at launch:**

- File upload via API (single-part up to 5 GB, multipart for larger files).
- CLI upload with progress bar and resume support.
- Supported formats: CSV, Parquet, JSON, JSONL, Avro, ORC.
- Automatic schema inference for structured formats.
- Checksum verification (SHA-256) on upload completion.
- Sample row extraction (first 100 rows stored for preview).
- Dataset listing, filtering by format, size, and upload date.

**Post-MVP:**

- Streaming dataset registration (Kafka topic, Kinesis stream).
- Delta Lake and Iceberg table format support.
- In-place registration of external datasets (S3, GCS, Azure Blob) without copying.
- Dataset profiling (statistical summaries, distribution histograms).
- Automatic format conversion on download.

## API Reference

| Operation | API | CLI | SDK |
|---|---|---|---|
| Upload dataset | `POST /api/v1/datasets/upload` | `meshant dataset upload <file>` | `client.datasets.upload(path)` |
| Initiate multipart | `POST /api/v1/datasets/upload/multipart` | `meshant dataset upload --multipart <file>` | `client.datasets.upload_multipart(path)` |
| Get dataset | `GET /api/v1/datasets/{id}` | `meshant dataset get <id>` | `client.datasets.get(id)` |
| List datasets | `GET /api/v1/datasets` | `meshant dataset list` | `client.datasets.list()` |
| Download dataset | `GET /api/v1/datasets/{id}/download` | `meshant dataset download <id>` | `client.datasets.download(id)` |
| Preview rows | `GET /api/v1/datasets/{id}/preview` | `meshant dataset preview <id>` | `client.datasets.preview(id)` |
| Delete dataset | `DELETE /api/v1/datasets/{id}` | `meshant dataset delete <id>` | `client.datasets.delete(id)` |

See the full [API Reference](/docs/mvpdocs/api-reference) and [CLI Reference](/docs/mvpdocs/cli-reference) for upload parameters, chunk sizes, and filtering options.
