# Tenant Cost Allocation

**Version**: 1.0 | **Owner**: Infrastructure Engineering

## AWS Cost Allocation Tags

All AWS resources MUST be tagged with:

| Tag | Value | Example |
|-----|-------|---------|
| `Environment` | `production` / `staging` / `development` | `production` |
| `Tenant` | Tenant slug or UUID | `acme-corp` |
| `Service` | Service name | `api-service` |
| `CostCenter` | Department code | `eng-platform` |
| `ManagedBy` | `terraform` / `manual` | `terraform` |

## Cost Explorer Configuration

1. Enable Cost Explorer in AWS Billing Console
2. Create cost allocation tags for `Tenant` and `Service`
3. Set up monthly reports:
   - Per-tenant cost breakdown
   - Per-service cost breakdown
   - Daily granularity for the current month

## Per-Tenant Cost Report Format

```json
{
  "tenant_id": "uuid",
  "tenant_slug": "acme-corp",
  "period": "2026-05",
  "costs": {
    "compute": {"eks": 120.50, "rds": 45.00},
    "storage": {"s3": 12.30, "ebs": 8.00},
    "network": {"data_transfer": 15.00, "load_balancer": 22.00},
    "services": {"fuseki": 30.00, "compliance": 10.00},
    "total": 262.80
  }
}
```

## Automation

- Cost reports generated monthly via `scripts/tenant_cost_report.py`
- Reports stored in `evidence/cost-reports/YYYY-MM/`
- Alerts if per-tenant cost exceeds 2x baseline
