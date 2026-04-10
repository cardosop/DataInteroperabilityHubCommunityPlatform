# Staging Deploy

This page orients you to the staging deployment process. For full
details, see the primary deployment reference.

## Quick Reference

**Primary guide:** [DEPLOYMENT_AND_OPERATIONS.md](../../DEPLOYMENT_AND_OPERATIONS.md)

## Staging Environment

The staging environment mirrors production and is available at
`meshant-internal.example.com` (API at `meshant-internal.example.com`). It runs
on the same AWS infrastructure stack (EKS, RDS, ElastiCache, S3)
with smaller instance sizes.

### Infrastructure

- **Terraform** provisions the AWS resources (VPC, EKS cluster, RDS,
  ElastiCache, S3 buckets, IAM roles).
- **Helm** deploys the application into the EKS cluster using the
  same chart as production with staging-specific value overrides.
- **GitHub Actions** CI/CD pipeline triggers on pushes to the
  `staging` branch.

### Deployment Flow

1. Push to the `staging` branch.
2. CI runs linting, tests, and builds container images.
3. Images are pushed to ECR with the commit SHA tag.
4. Helm upgrade applies the new image tag to the staging namespace.
5. Post-deploy health checks verify the rollout.

### Key Differences from Production

| Aspect             | Staging              | Production           |
|--------------------|----------------------|----------------------|
| Replicas           | 1-2 per service      | 3+ per service       |
| RDS instance       | db.t3.medium         | db.r6g.xlarge+       |
| ElastiCache        | cache.t3.micro       | cache.r6g.large+     |
| TLS certificate    | staging wildcard      | production wildcard  |
| Feature flags      | All features enabled  | Controlled rollout   |

### Troubleshooting

- **Deploy stuck**: Check the GitHub Actions workflow logs for the
  `staging` branch.
- **Pod crash loops**: Run `kubectl logs -n staging <pod>` and check
  for missing environment variables or failed migrations.

## Related

- [Production Deploy](production-deploy.md) -- production deployment procedures
- [Configuration Reference](configuration-reference.md) -- all env vars and Helm keys
- [DEPLOYMENT_AND_OPERATIONS.md](../../DEPLOYMENT_AND_OPERATIONS.md) -- full reference
