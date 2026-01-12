# ODH (Open Data Hub) Usage Guide

This guide provides comprehensive documentation for using ODH (Open Data Hub) functionality in the DataHub Interoperability Python SDK.

## Table of Contents

1. [Introduction](#introduction)
2. [ODH Concepts](#odh-concepts)
3. [Getting Started](#getting-started)
4. [Model Registry](#model-registry)
5. [Training Jobs](#training-jobs)
6. [Inference Deployments](#inference-deployments)
7. [Error Handling](#error-handling)
8. [Best Practices](#best-practices)
9. [Examples](#examples)

## Introduction

The Open Data Hub (ODH) is an open-source project that provides a set of operators for managing ML workloads on Kubernetes. The DataHub SDK provides comprehensive support for managing ML models, training jobs, and inference deployments with ODH integration.

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

## Getting Started

### Installation

```bash
pip install datahub-interoperability
```

### Basic Setup

```python
import asyncio
import os
from datahub_interoperability import DataHubClient, DataHubClientConfig

async def main():
    config = DataHubClientConfig(
        base_url="https://api.hub.example.com/api/v1",
        api_token=os.getenv("DATAHUB_API_TOKEN"),
    )

    async with DataHubClient(config) as client:
        # Access ODH APIs
        odh_api = client.odh
        training_api = client.training
        inference_api = client.inference

        # Use the APIs
        models = await odh_api.list_models()
        print(f"Found {len(models)} models")

if __name__ == "__main__":
    asyncio.run(main())
```

## Model Registry

### List Models

List all ML models with optional filters:

```python
# List all models
models = await client.odh.list_models()

# Filter by asset ID
models = await client.odh.list_models(asset_id="asset-uuid")

# Filter by status
models = await client.odh.list_models(status="TRAINED")

# Combine filters with pagination
models = await client.odh.list_models(
    asset_id="asset-uuid",
    status="DEPLOYED",
    limit=50,
    offset=0,
)

# Iterate through models
for model in models:
    print(f"Model: {model['odh_model_name']} v{model['odh_model_version']}")
    print(f"Status: {model['status']}")
    print(f"Type: {model['model_type']}")
```

**Status Values:**
- `TRAINING` - Model is currently being trained
- `TRAINED` - Model training completed successfully
- `DEPLOYED` - Model is deployed for inference
- `FAILED` - Model training or deployment failed
- `ARCHIVED` - Model is archived

### Get Model Details

Get detailed information about a specific model:

```python
model = await client.odh.get_model(model_id)

print(f"ID: {model['id']}")
print(f"ODH Model ID: {model['odh_model_id']}")
print(f"ODH Model Name: {model['odh_model_name']}")
print(f"ODH Model Version: {model['odh_model_version']}")
print(f"Model Type: {model['model_type']}")
print(f"Status: {model['status']}")
print(f"Asset ID: {model.get('asset_id', 'N/A')}")
print(f"Contract ID: {model.get('contract_id', 'N/A')}")
```

### Create Model

Create a new ML model link:

```python
# Create model with required fields
model = await client.odh.create_model(
    odh_model_id="my-model-123",
    odh_model_version="1.0.0",
    asset_id="asset-uuid",
    model_type="CLASSIFICATION",
)

# Create model linked to asset and contract
model = await client.odh.create_model(
    odh_model_id="my-model-123",
    odh_model_version="1.0.0",
    asset_id="asset-uuid",
    model_type="CLASSIFICATION",
    contract_id="contract-uuid",  # Optional
)

print(f"Created model: {model['id']}")
print(f"Status: {model['status']}")
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

```python
# Update model status
updated = await client.odh.update_model(
    model_id,
    status="DEPLOYED",
)

# Update linked asset
updated = await client.odh.update_model(
    model_id,
    asset_id="new-asset-uuid",
)

# Update multiple fields
updated = await client.odh.update_model(
    model_id,
    asset_id="new-asset-uuid",
    status="TRAINED",
)

print(f"Updated model: {updated['id']}")
print(f"New status: {updated['status']}")
```

**Note:** At least one field (`asset_id`, `contract_id`, or `status`) must be provided.

### Delete Model

Delete a model:

```python
await client.odh.delete_model(model_id)
print("Model deleted successfully")
```

**Warning:** This operation cannot be undone. Ensure the model is not in use before deleting.

### Get Model Versions

List all versions of a model (by ODH Model ID):

```python
versions = await client.odh.get_model_versions(model_id)

print(f"Found {len(versions)} versions")
for version in versions:
    print(f"Version: {version['odh_model_version']}")
    print(f"Status: {version['status']}")
    print(f"Created: {version['created_at']}")
```

### Link Model to Asset

Link a model to a Hub asset:

```python
model = await client.odh.link_model_to_asset(
    model_id="model-uuid",
    asset_id="asset-uuid",
)

print(f"Model linked to asset: {model['asset_id']}")
```

### Link Model to Dataset

Link a model to a dataset with a specific role:

```python
link = await client.odh.link_model_to_dataset(
    model_id="model-uuid",
    dataset_id="dataset-uuid",
    role="TRAINING",  # TRAINING, VALIDATION, or TEST
)

print(f"Model linked to dataset: {link['dataset_id']}")
print(f"Role: {link['role']}")
```

## Training Jobs

### Submit Training Job

Submit a training job to train a model:

```python
# Submit with configuration dictionary
job = await client.training.submit_training_job(
    model_id="model-uuid",
    dataset_id="dataset-uuid",
    config={
        "epochs": 100,
        "batch_size": 32,
        "learning_rate": 0.001,
        "optimizer": "adam",
        "loss": "categorical_crossentropy",
        "metrics": ["accuracy", "precision", "recall"],
        "validation_split": 0.2,
        "early_stopping": {
            "monitor": "val_loss",
            "patience": 10,
        },
    },
)

print(f"Training job submitted: {job['job_id']}")
print(f"Status: {job['status']}")
print(f"Hub Job ID: {job.get('hub_job_id')}")
```

### Get Training Job Details

Get detailed information about a training job:

```python
job = await client.training.get_training_job(job_id)

print(f"Job ID: {job['job_id']}")
print(f"Status: {job['status']}")
print(f"Progress: {job.get('progress', 0):.1%}")
print(f"Model ID: {job['model_id']}")
print(f"Dataset ID: {job['dataset_id']}")

if job.get('metrics'):
    print("Metrics:")
    for key, value in job['metrics'].items():
        print(f"  {key}: {value}")

if job.get('logs_url'):
    print(f"Logs URL: {job['logs_url']}")

if job.get('error'):
    print(f"Error: {job['error']}")
```

### List Training Jobs

List training jobs with optional filters:

```python
# List all training jobs
jobs = await client.training.list_training_jobs()

# Filter by model ID
jobs = await client.training.list_training_jobs(model_id="model-uuid")

# Filter by status
jobs = await client.training.list_training_jobs(status="RUNNING")

# Combine filters with pagination
jobs = await client.training.list_training_jobs(
    model_id="model-uuid",
    status="COMPLETED",
    limit=20,
    offset=0,
)

# Iterate through jobs
for job in jobs:
    print(f"Job: {job['job_id']}")
    print(f"Status: {job['status']}")
    print(f"Progress: {job.get('progress', 0):.1%}")
```

### Cancel Training Job

Cancel a running training job:

```python
await client.training.cancel_training_job(job_id)
print("Training job cancelled successfully")
```

**Note:** Only jobs with status `PENDING` or `RUNNING` can be cancelled.

### Get Training Logs

Retrieve logs from a training job:

```python
logs = await client.training.get_training_logs(job_id)

# Logs may be returned as a string or structured data
if isinstance(logs, str):
    print(logs)
else:
    # Handle structured log format
    for log_entry in logs:
        print(f"[{log_entry['timestamp']}] [{log_entry['level']}] {log_entry['message']}")
```

## Inference Deployments

### Deploy Model

Deploy a trained model for inference:

```python
# Deploy with default configuration
deployment = await client.inference.deploy_model(
    model_id="model-uuid",
)

# Deploy with custom configuration
deployment = await client.inference.deploy_model(
    model_id="model-uuid",
    config={
        "replicas": 3,
        "resources": {
            "requests": {
                "cpu": "500m",
                "memory": "1Gi",
            },
            "limits": {
                "cpu": "2000m",
                "memory": "4Gi",
            },
        },
        "autoscaling": {
            "min_replicas": 2,
            "max_replicas": 10,
            "target_cpu_utilization": 70,
        },
    },
)

print(f"Deployment ID: {deployment['deployment_id']}")
print(f"Status: {deployment['status']}")
print(f"Endpoint: {deployment.get('endpoint', 'N/A')}")
```

### Run Prediction

Run inference prediction on a deployed model:

```python
# Simple prediction
prediction = await client.inference.predict(
    deployment_id="deployment-id",
    input_data={
        "customer_id": "12345",
        "age": 35,
        "purchase_history": [100, 200, 150],
        "last_purchase_days": 7,
    },
)

print(f"Prediction: {prediction['output']}")
print(f"Status: {prediction['status']}")

# Handle structured output
if isinstance(prediction['output'], dict):
    print(f"Class: {prediction['output'].get('class')}")
    print(f"Confidence: {prediction['output'].get('confidence')}")
    print(f"Probabilities: {prediction['output'].get('probabilities')}")
```

### Get Deployment Details

Get detailed information about a deployment:

```python
deployment = await client.inference.get_deployment(deployment_id)

print(f"Deployment ID: {deployment['deployment_id']}")
print(f"Model ID: {deployment['model_id']}")
print(f"Status: {deployment['status']}")
print(f"Replicas: {deployment.get('replicas', 'N/A')}")
print(f"Endpoint: {deployment.get('endpoint', 'N/A')}")

if deployment.get('created_at'):
    print(f"Created: {deployment['created_at']}")
if deployment.get('updated_at'):
    print(f"Updated: {deployment['updated_at']}")
```

### List Deployments

List inference deployments with optional filters:

```python
# List all deployments
deployments = await client.inference.list_deployments()

# Filter by model ID
deployments = await client.inference.list_deployments(model_id="model-uuid")

# Filter by status
deployments = await client.inference.list_deployments(status="DEPLOYED")

# Combine filters with pagination
deployments = await client.inference.list_deployments(
    model_id="model-uuid",
    status="DEPLOYED",
    limit=20,
    offset=0,
)

# Iterate through deployments
for deployment in deployments:
    print(f"Deployment: {deployment['deployment_id']}")
    print(f"Status: {deployment['status']}")
    print(f"Endpoint: {deployment.get('endpoint', 'N/A')}")
```

### Undeploy Model

Undeploy a model (remove deployment):

```python
await client.inference.undeploy_model(deployment_id)
print("Deployment undeployed successfully")
```

**Warning:** This will stop all inference requests for this deployment.

### Get Inference Metrics

Get performance metrics for a deployment:

```python
metrics = await client.inference.get_inference_metrics(deployment_id)

print(f"Total Requests: {metrics.get('total_requests', 0)}")
print(f"Successful Requests: {metrics.get('successful_requests', 0)}")
print(f"Failed Requests: {metrics.get('failed_requests', 0)}")

if metrics.get('error_rate') is not None:
    print(f"Error Rate: {metrics['error_rate']:.2f}%")

if metrics.get('latency_ms') is not None:
    print(f"Average Latency: {metrics['latency_ms']:.2f} ms")

if metrics.get('accuracy') is not None:
    print(f"Accuracy: {metrics['accuracy']:.2f}")

# Additional metrics
if metrics.get('metrics'):
    print("Additional Metrics:")
    for key, value in metrics['metrics'].items():
        print(f"  {key}: {value}")
```

## Error Handling

### ODH Error Classes

The SDK provides specialized ODH error classes:

```python
from datahub_interoperability.errors import (
    ODHMLError,
    ODHMLValidationError,
    ODHMLNotFoundError,
    ODHMLConflictError,
    ValidationError,
    NotFoundError,
    ServerError,
)
```

### Handling Validation Errors

```python
try:
    model = await client.odh.create_model(
        odh_model_id="",  # Invalid: empty string
        odh_model_version="1.0.0",
        asset_id="invalid-uuid",  # Invalid: not a UUID
        model_type="INVALID_TYPE",  # Invalid: not a valid type
    )
except ODHMLValidationError as e:
    print(f"Validation failed: {e.message}")
    print(f"Error code: {e.error_code}")
    print(f"Field path: {e.field_path}")
    print(f"Expected: {e.expected}")
    print(f"Actual: {e.actual}")
except ValidationError as e:
    print(f"General validation error: {e.message}")
    print(f"Details: {e.details}")
```

### Handling Not Found Errors

```python
try:
    model = await client.odh.get_model("non-existent-id")
except ODHMLNotFoundError as e:
    print(f"Model not found: {e.message}")
except NotFoundError as e:
    print(f"Resource not found: {e.message}")
    print(f"Request ID: {e.request_id}")
```

### Handling Conflict Errors

```python
try:
    model = await client.odh.create_model(
        odh_model_id="existing-model-id",
        odh_model_version="1.0.0",
        asset_id="asset-uuid",
        model_type="CLASSIFICATION",
    )
except ODHMLConflictError as e:
    print(f"Conflict: {e.message}")
    print("Model with this ODH Model ID and version already exists")
```

### Handling Server Errors

```python
try:
    models = await client.odh.list_models()
except ServerError as e:
    print(f"Server error: {e.message}")
    print(f"Request ID: {e.request_id}")
    # May be retryable
    if e.is_retryable:
        print("This error may be retryable")
```

### Comprehensive Error Handling Example

```python
async def safe_create_model(client, **kwargs):
    """Safely create a model with comprehensive error handling."""
    try:
        model = await client.odh.create_model(**kwargs)
        return model
    except ODHMLValidationError as e:
        print(f"Validation error: {e.message}")
        print(f"Field: {e.field_path}")
        print(f"Expected: {e.expected}, Actual: {e.actual}")
        raise
    except ODHMLConflictError as e:
        print(f"Conflict: Model already exists")
        # Optionally get existing model
        existing = await client.odh.list_models(
            asset_id=kwargs.get('asset_id')
        )
        return existing[0] if existing else None
    except ODHMLNotFoundError as e:
        print(f"Not found: {e.message}")
        raise
    except ODHMLError as e:
        print(f"ODH error: {e.message}")
        raise
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise
```

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
- Use configuration dictionaries with clear structure
- Document configuration parameters and their effects

### Async/Await Patterns

- Always use `async with` for client context management
- Use `await` for all API calls
- Handle errors appropriately with try/except blocks

### Resource Management

- Clean up unused deployments to free resources
- Archive old model versions instead of deleting
- Monitor resource usage in deployment configurations

### Error Handling

- Always handle specific error types (ODHMLValidationError, etc.)
- Provide meaningful error messages to users
- Log errors for debugging and monitoring

## Examples

### Complete ML Lifecycle

```python
import asyncio
from datahub_interoperability import DataHubClient, DataHubClientConfig

async def complete_ml_lifecycle():
    config = DataHubClientConfig(
        base_url="https://api.hub.example.com/api/v1",
        api_token=os.getenv("DATAHUB_API_TOKEN"),
    )

    async with DataHubClient(config) as client:
        # 1. Register Model
        model = await client.odh.create_model(
            odh_model_id="customer-churn-predictor",
            odh_model_version="1.0.0",
            asset_id="asset-uuid",
            model_type="CLASSIFICATION",
        )
        print(f"Created model: {model['id']}")

        # 2. Train Model
        job = await client.training.submit_training_job(
            model_id=model['id'],
            dataset_id="dataset-uuid",
            config={
                "epochs": 100,
                "batch_size": 32,
                "learning_rate": 0.001,
            },
        )
        print(f"Submitted training job: {job['job_id']}")

        # Monitor training
        while True:
            job = await client.training.get_training_job(job['job_id'])
            print(f"Status: {job['status']}, Progress: {job.get('progress', 0):.1%}")

            if job['status'] in ['COMPLETED', 'FAILED']:
                break

            await asyncio.sleep(10)

        # Update model status
        if job['status'] == 'COMPLETED':
            await client.odh.update_model(model['id'], status="TRAINED")
            print("Model training completed")

        # 3. Deploy Model
        deployment = await client.inference.deploy_model(
            model_id=model['id'],
            config={"replicas": 3},
        )
        print(f"Deployed model: {deployment['deployment_id']}")

        # 4. Run Inference
        prediction = await client.inference.predict(
            deployment_id=deployment['deployment_id'],
            input_data={
                "customer_id": "12345",
                "age": 35,
                "purchase_history": [100, 200, 150],
            },
        )
        print(f"Prediction: {prediction['output']}")

        # 5. Update Model Status
        await client.odh.update_model(model['id'], status="DEPLOYED")
        print("Model lifecycle completed")

if __name__ == "__main__":
    asyncio.run(complete_ml_lifecycle())
```

### Model Versioning

```python
async def model_versioning_example():
    async with DataHubClient(config) as client:
        # Create initial version
        v1 = await client.odh.create_model(
            odh_model_id="my-model",
            odh_model_version="1.0.0",
            asset_id="asset-uuid",
            model_type="CLASSIFICATION",
        )

        # Create new version
        v2 = await client.odh.create_model(
            odh_model_id="my-model",
            odh_model_version="2.0.0",
            asset_id="asset-uuid",
            model_type="CLASSIFICATION",
        )

        # List all versions
        versions = await client.odh.get_model_versions(v1['id'])
        print(f"Found {len(versions)} versions")
        for version in versions:
            print(f"Version {version['odh_model_version']}: {version['status']}")
```

### Error Recovery

```python
async def error_recovery_example():
    async with DataHubClient(config) as client:
        try:
            # Attempt training
            job = await client.training.submit_training_job(
                model_id="model-uuid",
                dataset_id="dataset-uuid",
                config={"epochs": 100},
            )

            # Monitor job
            while True:
                job = await client.training.get_training_job(job['job_id'])
                if job['status'] == 'FAILED':
                    # Get logs for debugging
                    logs = await client.training.get_training_logs(job['job_id'])
                    print(f"Training failed. Logs: {logs}")

                    # Update model status
                    await client.odh.update_model(
                        job['model_id'],
                        status="FAILED",
                    )
                    break
                elif job['status'] == 'COMPLETED':
                    break
                await asyncio.sleep(10)

        except ODHMLValidationError as e:
            print(f"Validation error: {e.message}")
            # Fix and retry
        except ServerError as e:
            print(f"Server error: {e.message}")
            # May be retryable
            if e.is_retryable:
                # Implement retry logic
                pass
```

## Additional Resources

- [ODH Documentation](https://opendatahub.io/)
- [DataHub SDK Main README](../README.md)
- [DataHub API Documentation](https://api-docs.example.com/)
