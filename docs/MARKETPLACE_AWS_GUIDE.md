# AWS Data Exchange Integration Guide

## Overview

This guide covers integration with AWS Data Exchange, a service that makes it easy to find, subscribe to, and use third-party data in the cloud.

## Marketplace Type

- **Type**: `AWS_DATA_EXCHANGE`
- **Supported Operations**: PUSH, PULL
- **Authentication**: AWS IAM Credentials

## Connection Configuration

### Required Configuration Parameters

```json
{
  "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
  "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
  "aws_region": "us-east-1",
  "data_set_id": "optional-default-dataset-id"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `aws_access_key_id` | string | Yes | AWS access key ID |
| `aws_secret_access_key` | string | Yes | AWS secret access key |
| `aws_region` | string | Yes | AWS region (e.g., `us-east-1`) |
| `data_set_id` | string | No | Default dataset ID for publishing (optional) |

### Optional Configuration

```json
{
  "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
  "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
  "aws_region": "us-east-1",
  "data_set_id": "optional-default-dataset-id",
  "s3_bucket": "my-data-bucket",
  "s3_prefix": "marketplace/",
  "session_token": "optional-session-token"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `s3_bucket` | string | No | S3 bucket for storing data files |
| `s3_prefix` | string | No | S3 prefix for organizing files |
| `session_token` | string | No | AWS session token (for temporary credentials) |

## Creating an AWS Data Exchange Connection

### Step 1: Prepare AWS Account

1. Ensure you have an AWS account with Data Exchange access
2. Create IAM user or role with necessary permissions:
   - `dataexchange:GetDataSet`
   - `dataexchange:ListDataSets`
   - `dataexchange:CreateDataSet`
   - `dataexchange:UpdateDataSet`
   - `dataexchange:CreateRevision`
   - `dataexchange:UpdateRevision`
   - `dataexchange:CreateJob`
   - `dataexchange:GetJob`
   - `s3:GetObject`
   - `s3:PutObject`
   - `s3:ListBucket`
3. Create S3 bucket for storing data files (if not using existing bucket)
4. Configure bucket policies for Data Exchange access

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "AWS_DATA_EXCHANGE",
  "name": "My AWS Data Exchange",
  "config": {
    "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "aws_region": "us-east-1",
    "s3_bucket": "my-data-exchange-bucket",
    "s3_prefix": "marketplace/"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## AWS Data Exchange-Specific Features

### Product Publishing (PUSH)

When syncing assets to AWS Data Exchange:

1. **DataSet Creation**: Assets are published as AWS Data Exchange datasets
2. **Revision Creation**: Each sync creates a new revision
3. **S3 Upload**: Asset resources are uploaded to S3
4. **Export Job**: Creates export job for data delivery
5. **Metadata Publishing**: Asset metadata is published as product metadata

### Product Discovery (PULL)

When syncing from AWS Data Exchange:

1. **Product Discovery**: Lists available products in the marketplace
2. **Subscription**: Subscribes to selected products
3. **Export Job Creation**: Creates export job to get data
4. **S3 Download**: Downloads data from S3 export location
5. **ODPS Generation**: Generates ODPS contracts from product metadata

## AWS Data Exchange-Specific Limitations

1. **Account Requirements**: Requires AWS account with Data Exchange enabled
2. **IAM Permissions**: Requires extensive IAM permissions for Data Exchange and S3
3. **Revision Model**: Each update creates a new revision (immutable)
4. **Export Jobs**: Data access requires export job creation and completion
5. **S3 Dependencies**: All data must be stored in S3
6. **Region Constraints**: Data Exchange operations are region-specific
7. **Subscription Model**: PULL operations require product subscription
8. **Job Status**: Export jobs are asynchronous and may take time to complete

## Best Practices

1. **IAM Roles**: Use IAM roles instead of access keys when possible
2. **S3 Organization**: Use S3 prefixes to organize marketplace data
3. **Revision Management**: Understand that revisions are immutable
4. **Export Job Monitoring**: Monitor export job status before downloading
5. **Cost Optimization**: Be aware of S3 storage and data transfer costs
6. **Error Handling**: Implement retry logic for export job polling
7. **Metadata Quality**: Ensure complete metadata for better product discoverability
8. **Security**: Use least-privilege IAM policies

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid credentials"
- **Solution**: Verify AWS access key ID and secret access key are correct

**Issue**: PUSH sync fails with "Access Denied"
- **Solution**: Ensure IAM user/role has necessary Data Exchange permissions

**Issue**: Export job creation fails
- **Solution**: Verify S3 bucket exists and IAM user has S3 permissions

**Issue**: Export job stuck in "IN_PROGRESS"
- **Solution**: Export jobs can take time; implement polling with appropriate timeout

**Issue**: S3 download fails
- **Solution**: Verify S3 bucket policy allows Data Exchange service access

**Issue**: Revision creation fails
- **Solution**: Ensure dataset exists and you have revision creation permissions

## Additional Resources

- [AWS Data Exchange Documentation](https://docs.aws.amazon.com/data-exchange/)
- [AWS Data Exchange API Reference](https://docs.aws.amazon.com/data-exchange/latest/apireference/)
- [AWS Data Exchange User Guide](https://docs.aws.amazon.com/data-exchange/latest/userguide/)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)
