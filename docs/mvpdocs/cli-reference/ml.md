# datahub ml

ML Model Registry management commands for models, inference deployments, training jobs, serving, A/B testing, and plan limits.

## Synopsis

```
datahub ml [OPTIONS] COMMAND [ARGS]...
```

## Subcommands

| Command | Description |
|---------|-------------|
| `ml models list` | List ML models |
| `ml models get <id>` | Get model details |
| `ml models create` | Create a new ML model link |
| `ml models update <id>` | Update ML model |
| `ml models delete <id>` | Delete ML model |
| `ml models versions <id>` | List all versions of a model |
| `ml inference deploy` | Deploy a model for inference |
| `ml inference predict` | Run inference prediction on a deployed model |
| `ml inference list` | List inference deployments |
| `ml inference get <id>` | Get deployment details |
| `ml inference undeploy <id>` | Undeploy a model |
| `ml inference metrics <id>` | Get inference metrics for a deployment |
| `ml training submit` | Submit a training job |
| `ml training list` | List training jobs |
| `ml training get <id>` | Get training job details |
| `ml training cancel <id>` | Cancel a training job |
| `ml training logs <id>` | Get training job logs |
| `ml serving deploy` | Deploy a model for serving as an API endpoint |
| `ml serving predict` | Run inference prediction on a served model |
| `ml serving list` | List model serving deployments |
| `ml serving get <id>` | Get serving deployment details |
| `ml serving undeploy <id>` | Undeploy a model serving deployment |
| `ml serving metrics <id>` | Get quality metrics for a serving deployment |
| `ml ab-test create` | Create an A/B test for model serving |
| `ml ab-test list` | List A/B tests |
| `ml ab-test get <id>` | Get A/B test details |
| `ml deploy <id>` | Deploy an ML model |
| `ml undeploy <id>` | Undeploy an ML model |
| `ml rollback <id>` | Rollback an ML model to a previous version |
| `ml plan show` | Show current ML subscription plan |
| `ml plan limits` | Show ML plan limits |
| `ml marketplace-publish <id>` | Publish an ML model to the marketplace |

## Common Options

| Flag | Description |
|------|-------------|
| `--format json\|table\|yaml` | Output format (default: table) |
| `--tenant <slug>` | Tenant context override |
| `-v, --verbose` | Verbose output |
| `--no-color` | Disable coloured output |
| `--timeout <seconds>` | Request timeout (default: 30) |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |
| 3 | Authentication failure |
| 4 | Resource not found |

## Examples

```bash
# List all models
datahub ml models list

# Deploy a model for inference
datahub ml inference deploy --model-id <id> --instance-type ml.c5.large

# Submit a training job
datahub ml training submit --config training-config.json

# Run batch prediction
datahub ml inference predict --deployment-id <id> --input data.csv

# Create an A/B test
datahub ml ab-test create --name "model-v2-experiment" --variant-a <id> --variant-b <id>

# Check ML plan limits
datahub ml plan limits

# Publish a model to the marketplace
datahub ml marketplace-publish <model-id> --pricing FREE
```

## Related

- API: [`/api/v1/ml/`](../api-reference/ml.md)
