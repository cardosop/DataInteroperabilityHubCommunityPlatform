# AWS Region Outage / Vendor Failure Runbook

## Impact
- S3: file uploads/downloads blocked (use cached data)
- RDS: all application data unavailable (read replica fails over)
- KMS: credential decryption blocked (cached in memory, new decrypts fail)
- EKS: pod scheduling may fail

## Detection
- CloudWatch alarms on service health
- Prometheus: `db_connections_active` gauge drops to 0
- AWS Health Dashboard: https://health.aws.amazon.com

## Fallback
- RDS: Multi-AZ auto-failover to standby replica
- S3: Cross-region replication (CRR) to us-west-2 for critical buckets
- KMS: Multi-region keys (MRK) for credential vault

## Recovery
1. Confirm AWS Health Dashboard shows recovery
2. Verify RDS failover completed
3. Verify S3 CRR sync
4. Verify KMS decrypts working
