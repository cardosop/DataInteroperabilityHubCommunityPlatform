# Google Cloud Platform Marketplace Integration Guide

## Overview

This guide covers integration with Google Cloud Platform (GCP) Marketplace, a platform for discovering and deploying data products and services on GCP.

## Marketplace Type

- **Type**: `GOOGLE_CLOUD_MARKETPLACE`
- **Supported Operations**: PUSH, PULL
- **Authentication**: GCP Service Account

## Connection Configuration

### Required Configuration Parameters

```json
{
  "project_id": "your-gcp-project-id",
  "service_account_key": {
    "type": "service_account",
    "project_id": "your-gcp-project-id",
    "private_key_id": "key-id",
    "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
    "client_email": "service-account@project.iam.gserviceaccount.com",
    "client_id": "client-id",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token"
  }
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | string | Yes | GCP project ID |
| `service_account_key` | object | Yes | Service account key JSON (can be file path or JSON object) |

### Optional Configuration

```json
{
  "project_id": "your-gcp-project-id",
  "service_account_key": {...},
  "bucket_name": "marketplace-data-bucket",
  "dataset_id": "marketplace_dataset",
  "location": "us-central1"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `bucket_name` | string | No | GCS bucket for storing data files |
| `dataset_id` | string | No | BigQuery dataset ID for tabular data |
| `location` | string | No | GCP region (default: `us-central1`) |

## Creating a GCP Marketplace Connection

### Step 1: Prepare GCP Service Account

1. Create GCP service account in your project
2. Grant necessary roles:
   - `roles/marketplace.publisher` (for PUSH)
   - `roles/storage.objectAdmin` (for Cloud Storage)
   - `roles/bigquery.dataEditor` (for BigQuery)
   - `roles/marketplace.viewer` (for PULL)
3. Create and download service account key (JSON)
4. Enable required APIs:
   - Cloud Marketplace API
   - Cloud Storage API
   - BigQuery API

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "GOOGLE_CLOUD_MARKETPLACE",
  "name": "My GCP Marketplace",
  "config": {
    "project_id": "my-gcp-project",
    "service_account_key": {
      "type": "service_account",
      "project_id": "my-gcp-project",
      "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
      "client_email": "marketplace@my-gcp-project.iam.gserviceaccount.com"
    },
    "bucket_name": "marketplace-data-bucket",
    "dataset_id": "marketplace_dataset"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## GCP Marketplace-Specific Features

### Listing Publishing (PUSH)

When syncing assets to GCP Marketplace:

1. **Listing Creation**: Assets are published as GCP Marketplace listings
2. **Cloud Storage Upload**: Uploads asset resources to GCS buckets
3. **BigQuery Integration**: For tabular data, creates BigQuery tables
4. **Metadata Publishing**: Publishes asset metadata as listing metadata
5. **ODPS Integration**: Uses ODPS contracts for listing descriptions

### Listing Discovery (PULL)

When syncing from GCP Marketplace:

1. **Listing Discovery**: Lists available listings in the marketplace
2. **Deployment**: Deploys selected listings to your project
3. **GCS Access**: Accesses data from Cloud Storage buckets
4. **BigQuery Access**: Accesses data from BigQuery datasets
5. **ODPS Generation**: Generates ODPS contracts from listing metadata

## GCP Marketplace-Specific Limitations

1. **Service Account Requirements**: Requires GCP service account with JSON key
2. **Publisher Account**: PUSH operations require publisher account setup
3. **API Enablement**: Requires Cloud Marketplace API to be enabled
4. **Storage Dependencies**: Data must be stored in Cloud Storage or BigQuery
5. **Region Constraints**: Operations are region-specific
6. **Deployment Model**: PULL operations require listing deployment
7. **BigQuery Schema**: Tabular data requires compatible BigQuery schemas

## Best Practices

1. **Service Account Security**: Use least-privilege IAM roles
2. **Bucket Organization**: Use bucket prefixes for organization
3. **BigQuery Optimization**: Use appropriate partitioning and clustering
4. **Cost Monitoring**: Monitor GCS storage and BigQuery query costs
5. **Listing Certification**: Understand certification requirements
6. **Metadata Quality**: Ensure complete metadata for discoverability
7. **Schema Compatibility**: Verify BigQuery schema compatibility

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid service account"
- **Solution**: Verify service account key JSON is correct and valid

**Issue**: PUSH sync fails with "Publisher account not found"
- **Solution**: Ensure publisher account is set up in GCP Marketplace

**Issue**: GCS upload fails
- **Solution**: Verify bucket exists and service account has storage.objectAdmin role

**Issue**: BigQuery table creation fails
- **Solution**: Check dataset exists and service account has bigquery.dataEditor role

**Issue**: Listing deployment fails
- **Solution**: Verify project has necessary quotas and APIs enabled

## Additional Resources

- [GCP Marketplace Documentation](https://cloud.google.com/marketplace/docs)
- [GCP Marketplace Publisher Guide](https://cloud.google.com/marketplace/docs/partners/)
- [Cloud Storage Documentation](https://cloud.google.com/storage/docs)
- [BigQuery Documentation](https://cloud.google.com/bigquery/docs)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)
