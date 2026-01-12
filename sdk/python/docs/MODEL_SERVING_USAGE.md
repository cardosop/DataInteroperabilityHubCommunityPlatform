# Model Serving SDK Usage Guide

Complete guide for using model serving and A/B testing in the DataHub Python SDK.

## Table of Contents

1. [Overview](#overview)
2. [Model Serving Concepts](#model-serving-concepts)
3. [Model Serving API](#model-serving-api)
4. [A/B Testing API](#ab-testing-api)
5. [Workflow Patterns](#workflow-patterns)
6. [Error Handling](#error-handling)
7. [Troubleshooting](#troubleshooting)

## Overview

The DataHub Python SDK provides comprehensive support for model serving, allowing you to deploy ML models as production-ready API endpoints with contract validation, quality monitoring, and A/B testing capabilities.

### Key Features

- **Model Serving**: Deploy models as API endpoints with custom paths
- **Direct Predictions**: Run predictions using model IDs (no deployment ID needed)
- **Quality Monitoring**: Track accuracy, latency, error rate, and data drift
- **A/B Testing**: Compare model variants with configurable traffic splitting
- **Contract Validation**: Automatic validation of input/output contracts
- **Marketplace Integration**: Serve models through marketplace listings

## Model Serving Concepts

### Serving Deployments

Serving deployments expose ML models as REST API endpoints:
- Models are deployed with optional custom endpoint paths
- Predictions are made directly using model IDs
- Each deployment tracks quality metrics and performance
- Deployments can be monitored, updated, and undeployed

### A/B Testing

A/B testing allows you to compare model performance:
- Split traffic between a base model and variant model
- Traffic split is configurable (e.g., 50:50, 70:30)
- Metrics are tracked separately for each variant
- Results help determine which model performs better

### Quality Metrics

Serving deployments track comprehensive quality metrics:
- **Accuracy**: Model prediction accuracy
- **Latency**: Average response time in milliseconds
- **Error Rate**: Percentage of failed requests
- **Data Drift**: Measure of input data distribution changes
- **Request Counts**: Total, successful, and failed requests

## Model Serving API

### Initialize Model Serving API

The Model Serving API is automatically available through the client:

```python
from datahub_interoperability import DataHubClient, DataHubClientConfig

config = DataHubClientConfig(
    base_url="https://api.hub.example.com/api/v1",
    api_token="your-api-key",
)

async with DataHubClient(config) as client:
    # Model serving API is available at client.model_serving
    serving_api = client.model_serving
```

### Deploy Model as API

Deploy a model as a serving endpoint:

```python
# Basic deployment
serving = await client.model_serving.deploy_model_as_api(
    model_id="123e4567-e89b-12d3-a456-426614174000"
)

# Deploy with custom endpoint path
serving = await client.model_serving.deploy_model_as_api(
    model_id="123e4567-e89b-12d3-a456-426614174000",
    endpoint="/api/v1/models/my-classifier"
)

print(f"Serving ID: {serving['serving_id']}")
print(f"Endpoint: {serving['endpoint']}")
print(f"Status: {serving['status']}")
```

**Returns:**
```python
{
    "serving_id": "789e0123-e89b-12d3-a456-426614174002",
    "model_id": "123e4567-e89b-12d3-a456-426614174000",
    "endpoint": "https://api.hub.example.com/api/v1/models/my-classifier",
    "status": "DEPLOYING",
    "created_at": "2025-01-10T10:00:00Z",
    "updated_at": "2025-01-10T10:00:00Z"
}
```

**Parameters:**
- `model_id` (required): UUID of the ML model to deploy
- `endpoint` (optional): Custom endpoint path (default: auto-generated)

**Raises:**
- `ValidationError`: If model_id is invalid
- `NotFoundError`: If model not found
- `ConflictError`: If model is already deployed
- `ServerError`: If deployment fails

### Run Prediction via API

Run inference prediction on a served model using model ID directly:

```python
# Run prediction
prediction = await client.model_serving.predict_via_api(
    model_id="123e4567-e89b-12d3-a456-426614174000",
    input_data={
        "feature1": 0.5,
        "feature2": 0.8,
        "feature3": 0.3
    }
)

print(f"Prediction: {prediction['output']}")
print(f"Status: {prediction['status']}")
```

**Returns:**
```python
{
    "output": {
        "prediction": 0.95,
        "confidence": 0.87,
        "class": "positive"
    },
    "model_id": "123e4567-e89b-12d3-a456-426614174000",
    "serving_id": "789e0123-e89b-12d3-a456-426614174002",
    "status": "success"
}
```

**Parameters:**
- `model_id` (required): UUID of the ML model
- `input_data` (required): Input data dictionary for prediction

**Raises:**
- `ValidationError`: If parameters are invalid
- `NotFoundError`: If model or deployment not found
- `ServerError`: If prediction fails

### List Deployed Models

List all serving deployments with optional filters:

```python
# List all deployments
deployments = await client.model_serving.list_deployed_models()

# Filter by model ID
deployments = await client.model_serving.list_deployed_models(
    model_id="123e4567-e89b-12d3-a456-426614174000"
)

# Filter by status
deployments = await client.model_serving.list_deployed_models(
    status="READY"
)

# Combine filters with pagination
deployments = await client.model_serving.list_deployed_models(
    model_id="123e4567-e89b-12d3-a456-426614174000",
    status="READY",
    limit=50,
    offset=0
)

for deployment in deployments:
    print(f"Serving ID: {deployment['serving_id']}")
    print(f"Model ID: {deployment['model_id']}")
    print(f"Status: {deployment['status']}")
    print(f"Endpoint: {deployment['endpoint']}")
```

**Returns:**
```python
[
    {
        "serving_id": "789e0123-e89b-12d3-a456-426614174002",
        "model_id": "123e4567-e89b-12d3-a456-426614174000",
        "status": "READY",
        "endpoint": "https://api.hub.example.com/api/v1/models/my-classifier",
        "created_at": "2025-01-10T10:00:00Z",
        "updated_at": "2025-01-10T10:05:00Z"
    },
    ...
]
```

**Parameters:**
- `model_id` (optional): Filter by model ID
- `status` (optional): Filter by deployment status (e.g., "READY", "DEPLOYING", "FAILED")
- `limit` (optional): Maximum number of results to return
- `offset` (optional): Offset for pagination

**Raises:**
- `ValidationError`: If parameters are invalid
- `ServerError`: If API request fails

### Get Serving Details

Get detailed information about a specific serving deployment:

```python
serving_details = await client.model_serving.get_model_serving_details(
    serving_id="789e0123-e89b-12d3-a456-426614174002"
)

print(f"Serving ID: {serving_details['serving_id']}")
print(f"Model ID: {serving_details['model_id']}")
print(f"Status: {serving_details['status']}")
print(f"Endpoint: {serving_details['endpoint']}")
print(f"Replicas: {serving_details.get('replicas', 0)}")
if serving_details.get('metrics'):
    print(f"Metrics: {serving_details['metrics']}")
```

**Returns:**
```python
{
    "serving_id": "789e0123-e89b-12d3-a456-426614174002",
    "model_id": "123e4567-e89b-12d3-a456-426614174000",
    "status": "READY",
    "endpoint": "https://api.hub.example.com/api/v1/models/my-classifier",
    "created_at": "2025-01-10T10:00:00Z",
    "updated_at": "2025-01-10T10:05:00Z",
    "replicas": 3,
    "metrics": {
        "accuracy": 0.95,
        "latency_ms": 45.2,
        "error_rate": 0.5
    }
}
```

**Parameters:**
- `serving_id` (required): UUID of the serving deployment

**Raises:**
- `ValidationError`: If serving_id is invalid
- `NotFoundError`: If serving not found
- `ServerError`: If API request fails

### Undeploy Model

Undeploy a serving deployment:

```python
await client.model_serving.undeploy_model(
    serving_id="789e0123-e89b-12d3-a456-426614174002"
)
```

**Parameters:**
- `serving_id` (required): UUID of the serving deployment to undeploy

**Raises:**
- `ValidationError`: If serving_id is invalid
- `NotFoundError`: If serving not found
- `ServerError`: If undeployment fails

### Get Quality Metrics

Get quality metrics for a serving deployment:

```python
metrics = await client.model_serving.get_model_quality_metrics(
    serving_id="789e0123-e89b-12d3-a456-426614174002"
)

print(f"Total Requests: {metrics['total_requests']}")
print(f"Successful Requests: {metrics['successful_requests']}")
print(f"Failed Requests: {metrics['failed_requests']}")
print(f"Average Latency: {metrics['avg_latency_ms']} ms")
if metrics.get('accuracy') is not None:
    print(f"Accuracy: {metrics['accuracy']}")
if metrics.get('precision') is not None:
    print(f"Precision: {metrics['precision']}")
if metrics.get('recall') is not None:
    print(f"Recall: {metrics['recall']}")
if metrics.get('f1_score') is not None:
    print(f"F1 Score: {metrics['f1_score']}")
```

**Returns:**
```python
{
    "serving_id": "789e0123-e89b-12d3-a456-426614174002",
    "total_requests": 1000,
    "successful_requests": 995,
    "failed_requests": 5,
    "avg_latency_ms": 45.2,
    "accuracy": 0.95,
    "precision": 0.94,
    "recall": 0.96,
    "f1_score": 0.95
}
```

**Parameters:**
- `serving_id` (required): UUID of the serving deployment

**Raises:**
- `ValidationError`: If serving_id is invalid
- `NotFoundError`: If serving not found
- `ServerError`: If API request fails

**Metrics Explained:**
- **total_requests**: Total number of prediction requests
- **successful_requests**: Number of successful predictions
- **failed_requests**: Number of failed predictions
- **avg_latency_ms**: Average response time in milliseconds
- **accuracy**: Model prediction accuracy (0.0 to 1.0)
- **precision**: Precision score (0.0 to 1.0)
- **recall**: Recall score (0.0 to 1.0)
- **f1_score**: F1 score (0.0 to 1.0)

## A/B Testing API

### Create A/B Test

Create an A/B test to compare two model variants:

```python
# Create A/B test with 50:50 traffic split
ab_test = await client.model_serving.create_ab_test(
    model_id="123e4567-e89b-12d3-a456-426614174000",  # Base model
    variant_id="456e7890-e89b-12d3-a456-426614174001",  # Variant model
    traffic_split="50:50"  # 50% to base, 50% to variant
)

# Create A/B test with 70:30 traffic split
ab_test = await client.model_serving.create_ab_test(
    model_id="123e4567-e89b-12d3-a456-426614174000",
    variant_id="456e7890-e89b-12d3-a456-426614174001",
    traffic_split="70:30"  # 70% to base, 30% to variant
)

print(f"A/B Test ID: {ab_test['ab_test_id']}")
print(f"Base Model ID: {ab_test['model_id']}")
print(f"Variant Model ID: {ab_test['variant_id']}")
print(f"Traffic Split: {ab_test['traffic_split']}")
print(f"Status: {ab_test['status']}")
```

**Returns:**
```python
{
    "ab_test_id": "012e3456-e89b-12d3-a456-426614174003",
    "model_id": "123e4567-e89b-12d3-a456-426614174000",
    "variant_id": "456e7890-e89b-12d3-a456-426614174001",
    "traffic_split": "50:50",
    "status": "ACTIVE",
    "created_at": "2025-01-10T10:00:00Z"
}
```

**Parameters:**
- `model_id` (required): UUID of the base model
- `variant_id` (required): UUID of the variant model to compare
- `traffic_split` (required): Traffic split in format "X:Y" where X+Y=100 (e.g., "50:50", "70:30")

**Traffic Split Format:**
- Must be in format "X:Y" where X and Y are integers
- X and Y must sum to 100
- X represents percentage of traffic to base model
- Y represents percentage of traffic to variant model
- Examples: "50:50", "70:30", "90:10", "80:20"

**Raises:**
- `ValidationError`: If parameters are invalid
- `NotFoundError`: If model or variant not found
- `ConflictError`: If A/B test already exists
- `ServerError`: If A/B test creation fails

### List A/B Tests

List all A/B tests with optional filters:

```python
# List all A/B tests
ab_tests = await client.model_serving.list_ab_tests()

# Filter by model ID
ab_tests = await client.model_serving.list_ab_tests(
    model_id="123e4567-e89b-12d3-a456-426614174000"
)

# With pagination
ab_tests = await client.model_serving.list_ab_tests(
    model_id="123e4567-e89b-12d3-a456-426614174000",
    limit=20,
    offset=0
)

for ab_test in ab_tests:
    print(f"A/B Test ID: {ab_test['ab_test_id']}")
    print(f"Base Model ID: {ab_test['model_id']}")
    print(f"Variant Model ID: {ab_test['variant_id']}")
    print(f"Traffic Split: {ab_test['traffic_split']}")
    print(f"Status: {ab_test['status']}")
```

**Returns:**
```python
[
    {
        "ab_test_id": "012e3456-e89b-12d3-a456-426614174003",
        "model_id": "123e4567-e89b-12d3-a456-426614174000",
        "variant_id": "456e7890-e89b-12d3-a456-426614174001",
        "traffic_split": "50:50",
        "status": "ACTIVE",
        "created_at": "2025-01-10T10:00:00Z"
    },
    ...
]
```

**Parameters:**
- `model_id` (optional): Filter by model ID (base or variant)
- `limit` (optional): Maximum number of results to return
- `offset` (optional): Offset for pagination

**Raises:**
- `ValidationError`: If parameters are invalid
- `ServerError`: If API request fails

### Get A/B Test Details

Get detailed information about a specific A/B test including metrics for each variant:

```python
ab_test_details = await client.model_serving.get_ab_test_details(
    ab_test_id="012e3456-e89b-12d3-a456-426614174003"
)

print(f"A/B Test ID: {ab_test_details['ab_test_id']}")
print(f"Base Model ID: {ab_test_details['model_id']}")
print(f"Variant Model ID: {ab_test_details['variant_id']}")
print(f"Traffic Split: {ab_test_details['traffic_split']}")
print(f"Status: {ab_test_details['status']}")

# Access metrics for each variant
metrics = ab_test_details.get('metrics', {})
if 'model' in metrics:
    print(f"\nBase Model Metrics:")
    print(f"  Accuracy: {metrics['model'].get('accuracy')}")
    print(f"  Latency: {metrics['model'].get('avg_latency_ms')} ms")
    print(f"  Error Rate: {metrics['model'].get('error_rate')}%")

if 'variant' in metrics:
    print(f"\nVariant Model Metrics:")
    print(f"  Accuracy: {metrics['variant'].get('accuracy')}")
    print(f"  Latency: {metrics['variant'].get('avg_latency_ms')} ms")
    print(f"  Error Rate: {metrics['variant'].get('error_rate')}%")
```

**Returns:**
```python
{
    "ab_test_id": "012e3456-e89b-12d3-a456-426614174003",
    "model_id": "123e4567-e89b-12d3-a456-426614174000",
    "variant_id": "456e7890-e89b-12d3-a456-426614174001",
    "traffic_split": "50:50",
    "status": "ACTIVE",
    "created_at": "2025-01-10T10:00:00Z",
    "metrics": {
        "model": {
            "total_requests": 500,
            "successful_requests": 495,
            "avg_latency_ms": 45.2,
            "accuracy": 0.95,
            "error_rate": 1.0
        },
        "variant": {
            "total_requests": 500,
            "successful_requests": 498,
            "avg_latency_ms": 42.1,
            "accuracy": 0.97,
            "error_rate": 0.4
        }
    }
}
```

**Parameters:**
- `ab_test_id` (required): UUID of the A/B test

**Raises:**
- `ValidationError`: If ab_test_id is invalid
- `NotFoundError`: If A/B test not found
- `ServerError`: If API request fails

## Workflow Patterns

### Complete Model Serving Workflow

Deploy a model, run predictions, monitor metrics, and undeploy:

```python
import asyncio
from datahub_interoperability import DataHubClient, DataHubClientConfig

async def complete_serving_workflow():
    config = DataHubClientConfig(
        base_url="https://api.hub.example.com/api/v1",
        api_token="your-api-key",
    )

    async with DataHubClient(config) as client:
        model_id = "123e4567-e89b-12d3-a456-426614174000"

        # 1. Deploy model for serving
        serving = await client.model_serving.deploy_model_as_api(
            model_id=model_id,
            endpoint="/api/v1/models/my-classifier"
        )
        serving_id = serving['serving_id']
        print(f"Deployed serving: {serving_id}")

        # 2. Wait for deployment to be ready
        import time
        while True:
            details = await client.model_serving.get_model_serving_details(serving_id)
            if details['status'] == 'READY':
                break
            print(f"Status: {details['status']}, waiting...")
            await asyncio.sleep(5)

        # 3. Run predictions
        prediction = await client.model_serving.predict_via_api(
            model_id=model_id,
            input_data={
                "feature1": 0.5,
                "feature2": 0.8
            }
        )
        print(f"Prediction: {prediction['output']}")

        # 4. Monitor metrics
        metrics = await client.model_serving.get_model_quality_metrics(serving_id)
        print(f"Accuracy: {metrics.get('accuracy')}")
        print(f"Latency: {metrics['avg_latency_ms']} ms")

        # 5. List all deployments
        deployments = await client.model_serving.list_deployed_models(model_id=model_id)
        print(f"Found {len(deployments)} deployments")

        # 6. Undeploy when done
        await client.model_serving.undeploy_model(serving_id)
        print("Undeployed successfully")

asyncio.run(complete_serving_workflow())
```

### A/B Testing Workflow

Create an A/B test, monitor results, and compare performance:

```python
async def ab_testing_workflow():
    config = DataHubClientConfig(
        base_url="https://api.hub.example.com/api/v1",
        api_token="your-api-key",
    )

    async with DataHubClient(config) as client:
        base_model_id = "123e4567-e89b-12d3-a456-426614174000"
        variant_model_id = "456e7890-e89b-12d3-a456-426614174001"

        # 1. Deploy both models
        base_serving = await client.model_serving.deploy_model_as_api(base_model_id)
        variant_serving = await client.model_serving.deploy_model_as_api(variant_model_id)

        # 2. Create A/B test
        ab_test = await client.model_serving.create_ab_test(
            model_id=base_model_id,
            variant_id=variant_model_id,
            traffic_split="50:50"
        )
        ab_test_id = ab_test['ab_test_id']
        print(f"Created A/B test: {ab_test_id}")

        # 3. Monitor A/B test results
        import time
        for i in range(10):  # Monitor for 10 iterations
            details = await client.model_serving.get_ab_test_details(ab_test_id)
            metrics = details.get('metrics', {})

            base_metrics = metrics.get('model', {})
            variant_metrics = metrics.get('variant', {})

            print(f"\nIteration {i+1}:")
            print(f"Base - Accuracy: {base_metrics.get('accuracy')}, Latency: {base_metrics.get('avg_latency_ms')} ms")
            print(f"Variant - Accuracy: {variant_metrics.get('accuracy')}, Latency: {variant_metrics.get('avg_latency_ms')} ms")

            await asyncio.sleep(30)  # Wait 30 seconds between checks

        # 4. Compare results
        final_details = await client.model_serving.get_ab_test_details(ab_test_id)
        final_metrics = final_details.get('metrics', {})

        base_accuracy = final_metrics.get('model', {}).get('accuracy', 0)
        variant_accuracy = final_metrics.get('variant', {}).get('accuracy', 0)

        if variant_accuracy > base_accuracy:
            print(f"\nVariant model performs better ({variant_accuracy} vs {base_accuracy})")
        else:
            print(f"\nBase model performs better ({base_accuracy} vs {variant_accuracy})")

asyncio.run(ab_testing_workflow())
```

### Production Deployment Pattern

Deploy a model with monitoring and quality checks:

```python
async def production_deployment():
    config = DataHubClientConfig(
        base_url="https://api.hub.example.com/api/v1",
        api_token="your-api-key",
    )

    async with DataHubClient(config) as client:
        model_id = "123e4567-e89b-12d3-a456-426614174000"

        # 1. Deploy model
        serving = await client.model_serving.deploy_model_as_api(
            model_id=model_id,
            endpoint="/api/v1/models/production-classifier"
        )
        serving_id = serving['serving_id']

        # 2. Verify deployment
        details = await client.model_serving.get_model_serving_details(serving_id)
        assert details['status'] == 'READY', "Deployment not ready"

        # 3. Run test predictions
        test_inputs = [
            {"feature1": 0.5, "feature2": 0.8},
            {"feature1": 0.3, "feature2": 0.6},
            {"feature1": 0.7, "feature2": 0.9},
        ]

        for test_input in test_inputs:
            prediction = await client.model_serving.predict_via_api(
                model_id=model_id,
                input_data=test_input
            )
            print(f"Test prediction: {prediction['output']}")

        # 4. Monitor quality metrics
        metrics = await client.model_serving.get_model_quality_metrics(serving_id)

        # Check for data drift (should be low)
        data_drift = metrics.get('data_drift', 0)
        if data_drift > 0.1:
            print(f"WARNING: High data drift detected ({data_drift})")
            print("Consider retraining the model")

        # Check error rate
        error_rate = metrics.get('failed_requests', 0) / max(metrics.get('total_requests', 1), 1)
        if error_rate > 0.05:  # 5% error rate threshold
            print(f"WARNING: High error rate ({error_rate:.2%})")

        print("Production deployment verified successfully")
```

### Model Version Comparison Pattern

Compare new model version with existing production model:

```python
async def model_version_comparison():
    config = DataHubClientConfig(
        base_url="https://api.hub.example.com/api/v1",
        api_token="your-api-key",
    )

    async with DataHubClient(config) as client:
        production_model_id = "123e4567-e89b-12d3-a456-426614174000"
        new_model_id = "789e0123-e89b-12d3-a456-426614174002"

        # 1. Deploy new model version
        new_serving = await client.model_serving.deploy_model_as_api(new_model_id)

        # 2. Create A/B test with small traffic to new model
        ab_test = await client.model_serving.create_ab_test(
            model_id=production_model_id,
            variant_id=new_model_id,
            traffic_split="90:10"  # 90% to production, 10% to new
        )
        ab_test_id = ab_test['ab_test_id']

        # 3. Monitor metrics for both models
        import time
        for i in range(20):  # Monitor for 20 iterations
            details = await client.model_serving.get_ab_test_details(ab_test_id)
            metrics = details.get('metrics', {})

            production_metrics = metrics.get('model', {})
            new_metrics = metrics.get('variant', {})

            print(f"\nIteration {i+1}:")
            print(f"Production - Accuracy: {production_metrics.get('accuracy')}, Latency: {production_metrics.get('avg_latency_ms')} ms")
            print(f"New Model - Accuracy: {new_metrics.get('accuracy')}, Latency: {new_metrics.get('avg_latency_ms')} ms")

            await asyncio.sleep(60)  # Wait 1 minute between checks

        # 4. If new model performs better, gradually increase traffic
        # Update A/B test to 70:30, then 50:50, then 0:100
        # Once confident, undeploy old model
        final_details = await client.model_serving.get_ab_test_details(ab_test_id)
        final_metrics = final_details.get('metrics', {})

        production_accuracy = final_metrics.get('model', {}).get('accuracy', 0)
        new_accuracy = final_metrics.get('variant', {}).get('accuracy', 0)

        if new_accuracy > production_accuracy * 1.05:  # 5% improvement threshold
            print(f"\nNew model performs significantly better ({new_accuracy} vs {production_accuracy})")
            print("Consider promoting new model to production")
        else:
            print(f"\nNew model does not show significant improvement")
```

## Error Handling

### Model Serving Error Classes

The SDK provides specialized error classes for model serving operations:

```python
from datahub_interoperability.errors import (
    ModelServingError,
    ModelServingValidationError,
    ModelServingNotFoundError,
    ModelServingDeploymentError,
    ABTestError,
    ValidationError,
    NotFoundError,
    ConflictError,
    ServerError,
)
```

### Common Error Handling Patterns

#### Validation Errors

```python
try:
    serving = await client.model_serving.deploy_model_as_api(
        model_id="invalid-uuid"
    )
except ModelServingValidationError as e:
    print(f"Validation failed: {e.message}")
    print(f"Error code: {e.error_code}")
    print(f"Details: {e.details}")
except ValidationError as e:
    print(f"General validation error: {e.message}")
```

#### Not Found Errors

```python
try:
    details = await client.model_serving.get_model_serving_details("non-existent-id")
except ModelServingNotFoundError as e:
    print(f"Serving not found: {e.message}")
    print(f"Request ID: {e.request_id}")
except NotFoundError as e:
    print(f"Resource not found: {e.message}")
```

#### Deployment Errors

```python
try:
    serving = await client.model_serving.deploy_model_as_api(model_id)
except ModelServingDeploymentError as e:
    print(f"Deployment failed: {e.message}")
    print(f"Error code: {e.error_code}")
    print(f"Details: {e.details}")
except ConflictError as e:
    print(f"Model already deployed: {e.message}")
except ServerError as e:
    print(f"Server error: {e.message}")
    print(f"Error code: {e.error_code}")
```

#### A/B Testing Errors

```python
try:
    ab_test = await client.model_serving.create_ab_test(
        model_id=base_model_id,
        variant_id=variant_model_id,
        traffic_split="60:50"  # Invalid: doesn't sum to 100
    )
except ModelServingValidationError as e:
    print(f"Traffic split validation failed: {e.message}")
    print(f"Expected: {e.details.get('expected')}")
    print(f"Actual: {e.details.get('actual')}")
except ABTestError as e:
    print(f"A/B test error: {e.message}")
    print(f"Error code: {e.error_code}")
```

### Comprehensive Error Handling Example

```python
async def robust_serving_workflow():
    config = DataHubClientConfig(
        base_url="https://api.hub.example.com/api/v1",
        api_token="your-api-key",
    )

    async with DataHubClient(config) as client:
        model_id = "123e4567-e89b-12d3-a456-426614174000"

        try:
            # Deploy model
            serving = await client.model_serving.deploy_model_as_api(model_id)
            serving_id = serving['serving_id']

            # Wait for ready status
            max_wait = 300  # 5 minutes
            wait_time = 0
            while wait_time < max_wait:
                details = await client.model_serving.get_model_serving_details(serving_id)
                if details['status'] == 'READY':
                    break
                elif details['status'] == 'FAILED':
                    raise ModelServingDeploymentError(
                        f"Deployment failed: {details.get('error', 'Unknown error')}"
                    )
                await asyncio.sleep(10)
                wait_time += 10

            # Run prediction
            prediction = await client.model_serving.predict_via_api(
                model_id=model_id,
                input_data={"feature1": 0.5, "feature2": 0.8}
            )
            print(f"Prediction successful: {prediction['output']}")

        except ModelServingValidationError as e:
            print(f"Validation error: {e.message}")
            print(f"Details: {e.details}")
        except ModelServingNotFoundError as e:
            print(f"Not found: {e.message}")
            print(f"Request ID: {e.request_id}")
        except ModelServingDeploymentError as e:
            print(f"Deployment error: {e.message}")
            print(f"Error code: {e.error_code}")
        except ConflictError as e:
            print(f"Conflict: {e.message}")
            # Model may already be deployed, try to get existing deployment
            deployments = await client.model_serving.list_deployed_models(model_id=model_id)
            if deployments:
                print(f"Found existing deployment: {deployments[0]['serving_id']}")
        except ServerError as e:
            print(f"Server error: {e.message}")
            print(f"Error code: {e.error_code}")
            # Retry logic could be added here
        except Exception as e:
            print(f"Unexpected error: {type(e).__name__}: {e}")

asyncio.run(robust_serving_workflow())
```

## Troubleshooting

### Common Issues and Solutions

#### Deployment Stuck in DEPLOYING Status

**Problem:** Deployment remains in DEPLOYING status indefinitely.

**Solutions:**
1. Check API service health
2. Verify model exists and is in correct status
3. Check API logs for errors
4. Retry deployment after a few minutes
5. Check resource availability (CPU, memory)

```python
# Check deployment status
details = await client.model_serving.get_model_serving_details(serving_id)
if details['status'] == 'DEPLOYING':
    # Wait and retry
    await asyncio.sleep(30)
    details = await client.model_serving.get_model_serving_details(serving_id)
```

#### Predictions Return Errors

**Problem:** Predictions fail with validation or server errors.

**Solutions:**
1. Verify serving deployment is READY
2. Check input data format matches model's expected schema
3. Verify input data is valid JSON
4. Check serving metrics for error patterns

```python
# Verify deployment status
details = await client.model_serving.get_model_serving_details(serving_id)
if details['status'] != 'READY':
    raise Exception(f"Deployment not ready: {details['status']}")

# Check metrics for errors
metrics = await client.model_serving.get_model_quality_metrics(serving_id)
error_rate = metrics['failed_requests'] / max(metrics['total_requests'], 1)
if error_rate > 0.1:
    print(f"WARNING: High error rate: {error_rate:.2%}")
```

#### A/B Test Not Splitting Traffic Correctly

**Problem:** A/B test doesn't split traffic as expected.

**Solutions:**
1. Verify traffic split format: Must be "X:Y" where X+Y=100
2. Check A/B test status
3. Verify both models are deployed and READY
4. Check API service logs for routing issues

```python
# Verify A/B test configuration
details = await client.model_serving.get_ab_test_details(ab_test_id)
print(f"Traffic split: {details['traffic_split']}")
print(f"Status: {details['status']}")

# Check metrics for both variants
metrics = details.get('metrics', {})
base_requests = metrics.get('model', {}).get('total_requests', 0)
variant_requests = metrics.get('variant', {}).get('total_requests', 0)
total = base_requests + variant_requests
if total > 0:
    base_percentage = (base_requests / total) * 100
    variant_percentage = (variant_requests / total) * 100
    print(f"Actual split: {base_percentage:.1f}:{variant_percentage:.1f}")
```

#### Metrics Not Updating

**Problem:** Metrics don't update or show stale data.

**Solutions:**
1. Verify serving deployment is receiving requests
2. Check metrics endpoint is accessible
3. Verify API service is collecting metrics
4. Wait a few minutes for metrics to update

```python
# Force metrics refresh by making a request
await client.model_serving.predict_via_api(
    model_id=model_id,
    input_data={"feature1": 0.5}
)

# Wait and check metrics again
await asyncio.sleep(10)
metrics = await client.model_serving.get_model_quality_metrics(serving_id)
```

#### High Data Drift

**Problem:** Data drift metric is high, indicating input distribution has changed.

**Solutions:**
1. Review input data distribution changes
2. Consider retraining the model with new data
3. Update data preprocessing pipeline if needed
4. Monitor drift trends over time

```python
# Monitor data drift
metrics = await client.model_serving.get_model_quality_metrics(serving_id)
data_drift = metrics.get('data_drift', 0)

if data_drift > 0.1:
    print(f"WARNING: High data drift detected ({data_drift})")
    print("Consider retraining the model with recent data")

    # Optionally trigger retraining workflow
    # await client.training.submit_training_job(...)
```

## Additional Resources

- **[ODH Usage Guide](ODH_USAGE.md)** - Complete guide for ML/ODH commands
- **[SDK README](../README.md)** - General SDK documentation
- **[API Documentation](https://api.hub.example.com/docs)** - API reference documentation

## API Reference

### ModelServingAPI Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `deploy_model_as_api()` | Deploy model as API endpoint | `Dict[str, Any]` |
| `predict_via_api()` | Run prediction via API | `Dict[str, Any]` |
| `list_deployed_models()` | List deployed models | `List[Dict[str, Any]]` |
| `get_model_serving_details()` | Get serving details | `Dict[str, Any]` |
| `undeploy_model()` | Undeploy model | `None` |
| `get_model_quality_metrics()` | Get quality metrics | `Dict[str, Any]` |
| `create_ab_test()` | Create A/B test | `Dict[str, Any]` |
| `list_ab_tests()` | List A/B tests | `List[Dict[str, Any]]` |
| `get_ab_test_details()` | Get A/B test details | `Dict[str, Any]` |
