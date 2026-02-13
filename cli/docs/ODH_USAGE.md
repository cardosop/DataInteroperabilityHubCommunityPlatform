# ODH (Open Data Hub) CLI Usage Guide

Complete guide for using ML/ODH commands in the DataHub CLI.

## Table of Contents

1. [Overview](#overview)
2. [ODH Concepts](#odh-concepts)
3. [Model Registry](#model-registry)
4. [Training Jobs](#training-jobs)
5. [Inference Deployments](#inference-deployments)
6. [Workflow Patterns](#workflow-patterns)
7. [Error Handling](#error-handling)
8. [Troubleshooting](#troubleshooting)

## Overview

The DataHub CLI provides comprehensive support for ML model management, training, and inference operations with ODH (Open Data Hub) integration. ODH is an open-source project that provides a set of operators for managing ML workloads on Kubernetes.

### Key Features

- **Model Registry**: Register and manage ML models with ODH Model Registry
- **Training**: Submit and monitor training jobs with ODH Training Operator
- **Inference**: Deploy models and run predictions with ODH Inference Scheduler
- **Integration**: Link models to Hub assets and contracts for governance

## ODH Concepts

### Model Registry

The Model Registry stores metadata about ML models, including:
- ODH Model ID and version
- Model type (classification, regression, etc.)
- Status (training, trained, deployed, failed, archived)
- Links to Hub assets and contracts

### Training Jobs

Training jobs are submitted to train ML models:
- Model ID and dataset ID are required
- Training configuration specifies hyperparameters and training settings
- Jobs can be monitored, cancelled, and logs retrieved

### Inference Deployments

Inference deployments make trained models available for predictions:
- Models are deployed with optional configuration
- Predictions are made via deployment endpoints
- Metrics track performance and usage

## Model Registry

### List Models

List all ML models with optional filters:

```bash
# List all models
datahub ml models list

# Filter by asset ID
datahub ml models list --asset-id <asset-id>

# Filter by status
datahub ml models list --status TRAINED

# Combine filters with pagination
datahub ml models list \
  --asset-id <asset-id> \
  --status DEPLOYED \
  --limit 50 \
  --offset 0

# Output in JSON format
datahub ml models list --format json
```

**Status Values:**
- `TRAINING` - Model is currently being trained
- `TRAINED` - Model training completed successfully
- `DEPLOYED` - Model is deployed for inference
- `FAILED` - Model training or deployment failed
- `ARCHIVED` - Model is archived

### Get Model Details

Get detailed information about a specific model:

```bash
# Get model details (table format)
datahub ml models get <model-id>

# Get model details (JSON format)
datahub ml models get <model-id> --format json
```

**Example Output:**
```
ID: 123e4567-e89b-12d3-a456-426614174000
ODH Model ID: my-model-123
ODH Model Name: Customer Churn Predictor
ODH Model Version: 1.0.0
Model Type: CLASSIFICATION
Status: TRAINED
Asset ID: 456e7890-e89b-12d3-a456-426614174001
Contract ID: 789e0123-e89b-12d3-a456-426614174002
Created: 2025-01-15T10:30:00Z
Updated: 2025-01-15T11:45:00Z
```

### Create Model

Create a new ML model link:

```bash
# Create model with required fields
datahub ml models create \
  --odh-model-id <odh-model-id> \
  --odh-model-name "My Model" \
  --odh-model-version "1.0.0" \
  --model-type CLASSIFICATION

# Create model linked to asset
datahub ml models create \
  --odh-model-id <odh-model-id> \
  --odh-model-name "Customer Churn Predictor" \
  --odh-model-version "1.0.0" \
  --model-type CLASSIFICATION \
  --asset-id <asset-id>

# Create model linked to asset and contract
datahub ml models create \
  --odh-model-id <odh-model-id> \
  --odh-model-name "Sales Forecast" \
  --odh-model-version "2.1.0" \
  --model-type REGRESSION \
  --asset-id <asset-id> \
  --contract-id <contract-id>
```

**Model Types:**
- `CLASSIFICATION` - Classification models
- `REGRESSION` - Regression models
- `CLUSTERING` - Clustering models
- `NLP` - Natural Language Processing models
- `COMPUTER_VISION` - Computer Vision models
- `RECOMMENDATION` - Recommendation models
- `TIME_SERIES` - Time Series models
- `ANOMALY_DETECTION` - Anomaly Detection models
- `OTHER` - Other model types

### Update Model

Update an existing model:

```bash
# Update model status
datahub ml models update <model-id> --status DEPLOYED

# Update linked asset
datahub ml models update <model-id> --asset-id <new-asset-id>

# Update linked contract
datahub ml models update <model-id> --contract-id <new-contract-id>

# Update multiple fields
datahub ml models update <model-id> \
  --asset-id <new-asset-id> \
  --status TRAINED
```

**Note:** At least one field (`--asset-id`, `--contract-id`, or `--status`) must be provided.

### Delete Model

Delete a model:

```bash
datahub ml models delete <model-id>
```

**Warning:** This operation cannot be undone. Ensure the model is not in use before deleting.

### List Model Versions

List all versions of a model (by ODH Model ID):

```bash
datahub ml models versions <model-id>
```

**Example Output:**
```
Versions for ODH Model ID: my-model-123
ID                                      Version              Status          Created
---------------------------------------- -------------------- --------------- -----------------------
123e4567-e89b-12d3-a456-426614174000   1.0.0                TRAINED         2025-01-15T10:30:00Z
234e5678-e89b-12d3-a456-426614174001   1.1.0                TRAINED         2025-01-20T14:20:00Z
345e6789-e89b-12d3-a456-426614174002   2.0.0                DEPLOYED        2025-02-01T09:15:00Z
```

## Training Jobs

### Submit Training Job

Submit a training job to train a model:

```bash
# Submit with JSON config string
datahub ml training submit \
  --model-id <model-id> \
  --dataset-id <dataset-id> \
  --config '{"epochs": 100, "batch_size": 32, "learning_rate": 0.001}'

# Submit with config file
datahub ml training submit \
  --model-id <model-id> \
  --dataset-id <dataset-id> \
  --config training-config.json
```

**Example Training Config File** (`training-config.json`):
```json
{
  "epochs": 100,
  "batch_size": 32,
  "learning_rate": 0.001,
  "optimizer": "adam",
  "loss": "categorical_crossentropy",
  "metrics": ["accuracy", "precision", "recall"],
  "validation_split": 0.2,
  "early_stopping": {
    "monitor": "val_loss",
    "patience": 10
  }
}
```

**Example Output:**
```
Training job submitted successfully!
Job ID: training-job-123
Hub Job ID: 123e4567-e89b-12d3-a456-426614174000
Status: PENDING
Model ID: 456e7890-e89b-12d3-a456-426614174001
Dataset ID: 789e0123-e89b-12d3-a456-426614174002
Submitted At: 2025-01-15T10:30:00Z
```

### List Training Jobs

List training jobs with optional filters:

```bash
# List all training jobs
datahub ml training list

# Filter by model ID
datahub ml training list --model-id <model-id>

# Filter by status
datahub ml training list --status RUNNING

# Combine filters with pagination
datahub ml training list \
  --model-id <model-id> \
  --status COMPLETED \
  --limit 20 \
  --offset 0
```

### Get Training Job Details

Get detailed information about a training job:

```bash
datahub ml training get <job-id>
```

**Example Output:**
```
Job ID: training-job-123
Hub Job ID: 123e4567-e89b-12d3-a456-426614174000
Model ID: 456e7890-e89b-12d3-a456-426614174001
Dataset ID: 789e0123-e89b-12d3-a456-426614174002
Status: RUNNING
Progress: 65.5%
Submitted At: 2025-01-15T10:30:00Z
Started At: 2025-01-15T10:31:00Z
Metrics: {
  "loss": 0.234,
  "accuracy": 0.912,
  "val_loss": 0.267,
  "val_accuracy": 0.895
}
Logs URL: https://logs.example.com/training-job-123
```

### Cancel Training Job

Cancel a running training job:

```bash
datahub ml training cancel <job-id>
```

**Note:** Only jobs with status `PENDING` or `RUNNING` can be cancelled.

### Get Training Logs

Retrieve logs from a training job:

```bash
# Get all logs
datahub ml training logs <job-id>

# Get last 100 lines
datahub ml training logs <job-id> --lines 100
```

## Inference Deployments

### Deploy Model

Deploy a trained model for inference:

```bash
# Deploy with default configuration
datahub ml inference deploy --model-id <model-id>

# Deploy with custom configuration
datahub ml inference deploy \
  --model-id <model-id> \
  --config deployment-config.json
```

**Example Deployment Config File** (`deployment-config.json`):
```json
{
  "replicas": 3,
  "resources": {
    "requests": {
      "cpu": "500m",
      "memory": "1Gi"
    },
    "limits": {
      "cpu": "2000m",
      "memory": "4Gi"
    }
  },
  "autoscaling": {
    "min_replicas": 2,
    "max_replicas": 10,
    "target_cpu_utilization": 70
  }
}
```

**Example Output:**
```
Model deployed successfully!
Deployment ID: deployment-123
Model ID: 456e7890-e89b-12d3-a456-426614174001
Status: DEPLOYING
Replicas: 3
Endpoint: https://inference.example.com/deployment-123
```

### Run Prediction

Run inference prediction on a deployed model:

```bash
# Predict with JSON input string
datahub ml inference predict \
  --deployment-id <deployment-id> \
  --input-data '{"feature1": 0.5, "feature2": 0.8}'

# Predict with input file
datahub ml inference predict \
  --deployment-id <deployment-id> \
  --input-data input.json
```

**Example Input File** (`input.json`):
```json
{
  "customer_id": "12345",
  "age": 35,
  "purchase_history": [100, 200, 150],
  "last_purchase_days": 7
}
```

**Example Output:**
```
Prediction completed successfully!
Deployment ID: deployment-123
Status: SUCCESS

Output:
{
  "prediction": 0.87,
  "confidence": 0.92,
  "class": "churn",
  "probabilities": {
    "churn": 0.87,
    "retain": 0.13
  }
}
```

### List Deployments

List inference deployments with optional filters:

```bash
# List all deployments
datahub ml inference list

# Filter by model ID
datahub ml inference list --model-id <model-id>

# Filter by status
datahub ml inference list --status DEPLOYED

# Combine filters with pagination
datahub ml inference list \
  --model-id <model-id> \
  --status DEPLOYED \
  --limit 20 \
  --offset 0
```

### Get Deployment Details

Get detailed information about a deployment:

```bash
datahub ml inference get <deployment-id>
```

**Example Output:**
```
Deployment ID: deployment-123
Model ID: 456e7890-e89b-12d3-a456-426614174001
Status: DEPLOYED
Replicas: 3
Endpoint: https://inference.example.com/deployment-123
Created: 2025-01-15T12:00:00Z
Updated: 2025-01-15T12:05:00Z
```

### Undeploy Model

Undeploy a model (remove deployment):

```bash
datahub ml inference undeploy <deployment-id>
```

**Warning:** This will stop all inference requests for this deployment.

### Get Inference Metrics

Get performance metrics for a deployment:

```bash
# Get all metrics
datahub ml inference metrics <deployment-id>

# Get metrics for time range
datahub ml inference metrics <deployment-id> \
  --start-time "2025-01-15T00:00:00Z" \
  --end-time "2025-01-15T23:59:59Z"
```

**Example Output:**
```
Metrics for Deployment: deployment-123
Total Requests: 15420
Successful Requests: 15230
Failed Requests: 190
Error Rate: 1.23%
Average Latency: 45.67 ms
Accuracy: 0.912
```

## Workflow Patterns

### Complete ML Lifecycle

**1. Register Model**
```bash
# Create model link
datahub ml models create \
  --odh-model-id my-model-123 \
  --odh-model-name "Customer Churn Predictor" \
  --odh-model-version "1.0.0" \
  --model-type CLASSIFICATION \
  --asset-id <asset-id>
```

**2. Train Model**
```bash
# Submit training job
datahub ml training submit \
  --model-id <model-id> \
  --dataset-id <dataset-id> \
  --config training-config.json

# Monitor training
datahub ml training get <job-id>
datahub ml training logs <job-id>

# Update model status after training
datahub ml models update <model-id> --status TRAINED
```

**3. Deploy Model**
```bash
# Deploy for inference
datahub ml inference deploy \
  --model-id <model-id> \
  --config deployment-config.json

# Wait for deployment to be ready
datahub ml inference get <deployment-id>
```

**4. Run Inference**
```bash
# Make predictions
datahub ml inference predict \
  --deployment-id <deployment-id> \
  --input-data input.json

# Monitor metrics
datahub ml inference metrics <deployment-id>
```

**5. Update Model Status**
```bash
# Mark as deployed
datahub ml models update <model-id> --status DEPLOYED
```

### Model Versioning Workflow

**1. Create New Version**
```bash
# Create new version of existing model
datahub ml models create \
  --odh-model-id my-model-123 \
  --odh-model-name "Customer Churn Predictor" \
  --odh-model-version "2.0.0" \
  --model-type CLASSIFICATION \
  --asset-id <asset-id>
```

**2. List All Versions**
```bash
# Get all versions
datahub ml models versions <model-id>
```

**3. Deploy New Version**
```bash
# Deploy new version
datahub ml inference deploy --model-id <new-version-model-id>

# Undeploy old version
datahub ml inference undeploy <old-deployment-id>
```

### Error Recovery Workflow

**1. Handle Training Failure**
```bash
# Check training job status
datahub ml training get <job-id>

# Review logs
datahub ml training logs <job-id>

# Update model status
datahub ml models update <model-id> --status FAILED

# Fix issues and resubmit
datahub ml training submit \
  --model-id <model-id> \
  --dataset-id <dataset-id> \
  --config fixed-training-config.json
```

**2. Handle Deployment Failure**
```bash
# Check deployment status
datahub ml inference get <deployment-id>

# Undeploy failed deployment
datahub ml inference undeploy <deployment-id>

# Update model status
datahub ml models update <model-id> --status TRAINED

# Retry deployment with different config
datahub ml inference deploy \
  --model-id <model-id> \
  --config retry-deployment-config.json
```

## Error Handling

### Common Errors

**Invalid Model ID**
```
Error: model-id must be a valid UUID
```
**Solution:** Ensure the model ID is a valid UUID format.

**Model Not Found**
```
Error: Model with id <model-id> not found
```
**Solution:** Verify the model ID exists using `datahub ml models list`.

**Invalid Model Type**
```
Error: model_type must be one of: CLASSIFICATION, REGRESSION, ...
```
**Solution:** Use a valid model type from the supported list.

**Training Job Failed**
```
Error: Training job failed: <error-message>
```
**Solution:** Check training logs with `datahub ml training logs <job-id>` and fix configuration issues.

**Deployment Failed**
```
Error: Failed to deploy model: <error-message>
```
**Solution:** Verify deployment configuration and model status. Ensure model is in TRAINED status.

### Error Response Format

Errors are returned in a consistent format:

```json
{
  "error": "Error message",
  "error_code": "ERROR_CODE",
  "details": {
    "field": "field_name",
    "expected": "expected_value",
    "actual": "actual_value"
  }
}
```

## Troubleshooting

### Model Not Appearing in List

**Problem:** Model created but not visible in list.

**Solutions:**
1. Check filters: `datahub ml models list` (no filters)
2. Verify model ID: `datahub ml models get <model-id>`
3. Check status filter: Models with certain statuses may be filtered out

### Training Job Stuck

**Problem:** Training job remains in PENDING or RUNNING status.

**Solutions:**
1. Check job details: `datahub ml training get <job-id>`
2. Review logs: `datahub ml training logs <job-id>`
3. Check Hub job status: Use the Hub Job ID to check in the jobs system
4. Cancel and resubmit if necessary: `datahub ml training cancel <job-id>`

### Deployment Not Responding

**Problem:** Deployment exists but predictions fail.

**Solutions:**
1. Check deployment status: `datahub ml inference get <deployment-id>`
2. Verify endpoint: Ensure endpoint URL is accessible
3. Check metrics: `datahub ml inference metrics <deployment-id>`
4. Review deployment configuration: Ensure resources are sufficient

### Model Versions Not Found

**Problem:** `datahub ml models versions` returns no results.

**Solutions:**
1. Verify model has ODH Model ID: `datahub ml models get <model-id>`
2. Check if other versions exist with same ODH Model ID
3. Ensure model was created with proper ODH Model ID

## Best Practices

### Model Naming

- Use descriptive names: "Customer Churn Predictor" vs "Model1"
- Include version in name: "Sales Forecast v2.0"
- Follow consistent naming conventions across your organization

### Status Management

- Update model status promptly after operations complete
- Use status to track model lifecycle: TRAINING → TRAINED → DEPLOYED
- Archive old models instead of deleting them

### Configuration Management

- Store training and deployment configs in version control
- Use config files instead of inline JSON for complex configurations
- Document configuration parameters and their effects

### Monitoring

- Regularly check training job progress during long-running jobs
- Monitor inference metrics to detect performance degradation
- Set up alerts for failed jobs and deployments

### Resource Management

- Clean up unused deployments to free resources
- Archive old model versions instead of deleting
- Monitor resource usage in deployment configurations

## Additional Resources

- **[CLI README](../README.md)** - Complete CLI documentation
- **[ODPS Usage Guide](ODPS_USAGE.md)** - ODPS contract management
- **[Marketplace Usage Guide](MARKETPLACE_USAGE.md)** - Marketplace integration
- **[BaaS Usage Guide](BAAS_USAGE.md)** - BaaS platform commands
- **[Model Serving Usage Guide](MODEL_SERVING_USAGE.md)** - Model serving and A/B testing
- **[API Reference](../../docs/API_REFERENCE.md)** - Complete API documentation
- [ODH Documentation](https://opendatahub.io/) - External ODH documentation
