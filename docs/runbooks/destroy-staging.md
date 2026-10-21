# Destroy Staging Infrastructure

Operator runbook for the **Destroy Staging Infrastructure** workflow
(`.github/workflows/terraform-destroy-staging.yml`).

The workflow executes a complete teardown of all staging AWS resources
in three phases. This runbook explains what each phase does, how to
diagnose failures, and how to clean up manually if the workflow
cannot finish on its own.

---

## Prerequisites

- GitHub Actions access to trigger `workflow_dispatch`
- Confirmation input: type **`destroy staging`** exactly
- Required secrets configured in the `staging` environment:
  `AWS_ROLE_STAGING`, `TF_STAGING_DB_PASSWORD`,
  `TF_STAGING_CACHE_AUTH_TOKEN`, `TF_STAGING_QUEUE_AUTH_TOKEN`,
  `TF_STAGING_EVENTS_AUTH_TOKEN`, `TF_STAGING_CHANNELS_AUTH_TOKEN`,
  `TF_STAGING_SES_SENDER_IDENTITY`

## What Is Preserved

The workflow deliberately does **not** destroy:

- **S3 state bucket** (`meshant-tfstate-staging-279554171209`)
- **DynamoDB lock table** (`meshant-tflock-staging`)

These are kept so you can re-create infrastructure without re-running
the Terraform bootstrap workflow.

---

## Phase 1: Pre-Destroy Sweep

### Concurrency and Timeout Guards

- The workflow shares a concurrency group (`terraform-staging-state`)
  with the apply workflow. Only one can run at a time.
- The destroy job has a 90-minute timeout. If it exceeds this, the
  job is cancelled by GitHub Actions.

### Force-Unlock Stale State Lock

Attempts a `terraform plan` with a 5-second lock timeout. If a stale
lock is detected, extracts the lock ID and runs
`terraform force-unlock -force`.

**If this fails:** The lock is held by an active process. Wait for the
other workflow run to finish, or manually unlock:

```bash
cd infrastructure/terraform/environments/staging
terraform force-unlock -force <LOCK_ID>
```

### Helm Release Cleanup

1. **Priority uninstalls:** `external-dns` and `cert-manager` are
   uninstalled first so they release Route 53 records before the bulk
   sweep removes the controllers.
2. **Bulk sweep:** All remaining Helm releases across all namespaces.
3. **LoadBalancer services:** Any non-Helm-managed LB services deleted.
4. **PVC cleanup:** All PersistentVolumeClaims deleted to release EBS.
5. **StorageClass:** `gp3-wfc` removed (Phase 214 leftover).
6. **Stuck namespaces:** Namespaces in `Terminating` state for >60s
   have their finalizers patched out.

**If Helm cleanup fails:** The EKS cluster may already be gone.
The step uses `set +e` and continues regardless.

### Orphaned EBS Volume Sweep

Finds EBS volumes tagged `kubernetes.io/cluster/meshant-staging=owned`.
Waits up to 3 minutes for volumes to reach `available` state (6
attempts x 30s), then deletes with exponential backoff on throttling.

**If volumes stay `in-use`:** They are still attached to an EC2
instance. The EKS destroy in Phase 2 will terminate the instances,
after which the volumes become available and can be deleted manually:

```bash
aws ec2 describe-volumes \
  --filters "Name=tag:kubernetes.io/cluster/meshant-staging,Values=owned" \
  --query 'Volumes[].VolumeId' --output text --region us-east-1

# For each volume:
aws ec2 delete-volume --volume-id vol-XXXX --region us-east-1
```

---

## Phase 2: Terraform Destroy

### Refresh-Only

`terraform apply -refresh-only` reconciles the state file with reality.
If resources were manually deleted since the last apply, this prevents
"resource already deleted" errors during destroy.

### Plan-Destroy Artifact

A `terraform plan -destroy` is captured as a binary plan file and a
human-readable text file. Both are uploaded as artifacts (90-day
retention) and the first 200 lines are surfaced in the job summary.

The VPC ID is captured at this point (`STAGING_VPC_ID`) and exported
to `$GITHUB_ENV` for use in post-destroy sweeps.

### EKS Targeted Destroy

EKS is destroyed first (`-target=module.eks`) because its node groups,
ENIs, and security groups block VPC/subnet deletion. A 90-second wait
follows for AWS to release ENIs.

### VPC Dependency Cleanup

An 8-step cleanup sequence runs after EKS is gone:

| Step | Resource | Why |
|------|----------|-----|
| 1 | VPC endpoints | Their ENIs block subnet deletion |
| 2 | NAT Gateways | Hold EIPs that block IGW detach |
| 3 | ELBs (classic + ALB/NLB) | Hold ENIs in subnets |
| 4 | NAT GW wait | Poll for `deleted` state (not `available`) |
| 5 | Elastic IPs | Disassociate + release |
| 6 | ENIs | Detach (force) + delete |
| 7 | Security Groups | Revoke rules + delete (except default) |
| 8 | DHCP Options | Disassociate + delete |

**If VPC cleanup times out:** NAT Gateways can take up to 5 minutes
to reach `deleted`. The `wait_for_state` helper polls for 3 minutes
(12 x 15s). If it times out, re-run the workflow or clean up manually:

```bash
aws ec2 describe-nat-gateways \
  --filter "Name=vpc-id,Values=$VPC_ID" "Name=state,Values=available" \
  --query 'NatGateways[].NatGatewayId' --output text --region us-east-1
```

### Full Destroy

`terraform destroy` runs against all remaining resources (RDS,
ElastiCache, S3 app buckets, KMS, IAM/IRSA roles, VPC itself).

---

## Phase 3: Post-Destroy Sweep and Verification

### Non-TF-Tracked Resource Sweep

Resources that Terraform does not manage are cleaned up explicitly:

| Gap | Resource | Method |
|-----|----------|--------|
| 1 | ECR pull-through repos | `docker-hub/*`, `ghcr/*` force-deleted |
| 4 | Secrets Manager | `--force-delete-without-recovery`, tag-filtered |
| 5 | CloudWatch log groups | 3 prefixes: eks, rds, elasticache |
| 6 | Route 53 records | Broad sweep, NS/SOA apex protected |
| 13 | ALB target groups | By VPC ID or `k8s-hubstaging*` name |
| 14 | EBS snapshots | Tagged `purpose=phase214-fuseki-pv-migration` |
| 3 | KMS aliases | Warning only (pending deletion window) |

### Verification Gate

12 named checks run and produce a markdown table in the job summary:

| Check | What It Verifies |
|-------|-----------------|
| `ecr_repos` | No pull-through cache repos remain |
| `ebs_volumes` | No staging-tagged EBS volumes |
| `secrets_manager` | No staging-tagged secrets |
| `cwl_log_groups` | No staging log groups |
| `route53_records` | No records (except NS/SOA) |
| `plan_artifact` | Destroy plan file was captured |
| `vpc_endpoints` | No VPC endpoints in staging VPC |
| `nat_gateways` | No active/pending NAT Gateways |
| `elastic_ips` | No VPC Elastic IPs |
| `enis` | No ENIs in staging VPC |
| `alb_target_groups` | No ALB target groups |
| `kms_aliases` | Warning only (D167) |

Any check except `kms_aliases` failing causes the job to exit 1.

---

## KMS Deletion Window

KMS keys created by Terraform have a configurable deletion window
(default 30 days in production, 7 days in staging). After
`terraform destroy`, the key enters `PendingDeletion` state and the
alias remains visible until the window expires.

The `kms_aliases` verification check is **warning-only** (D167)
because there is no way to accelerate the deletion window. The alias
will disappear automatically after the configured period.

**To check status:**

```bash
aws kms describe-key --key-id alias/meshant-staging-main \
  --query 'KeyMetadata.{State:KeyState,Deletion:DeletionDate}' \
  --region us-east-1
```

---

## Re-Bootstrap Instructions

After a successful destroy, to rebuild staging infrastructure:

1. Push any commit to the `staging` branch
2. `terraform.yml` will automatically:
   - Run `terraform init` (state bucket still exists)
   - Run `terraform plan` + `terraform apply`
   - Re-create VPC, EKS, RDS, ElastiCache, S3, KMS, IAM
3. Deploy the application via the deploy workflow

No manual bootstrap step is needed because the S3 state bucket and
DynamoDB lock table are preserved.

---

## Manual Cleanup Procedures

If the workflow fails mid-run and cannot be re-triggered, clean up
resources manually in this order:

1. **Helm releases:** `helm uninstall <release> -n <ns>` for each
2. **EKS node groups:** Terminate via AWS Console or
   `aws eks delete-nodegroup`
3. **EKS cluster:** `aws eks delete-cluster --name meshant-staging`
4. **VPC dependencies:** Follow the 8-step VPC cleanup table above
5. **Terraform destroy:** `cd infrastructure/terraform/environments/staging && terraform destroy`
6. **Post-destroy sweep:** Run each AWS CLI command from the sweep
   step manually
7. **Verify:** Run each verification check manually

---

## Per-Gap Regression Test Recipes

Manual test recipes for verifying each gap fix works. Seed the leak
condition, run the destroy workflow, and confirm the verification step
catches or cleans it. No disposable AWS account is required — all
recipes use the existing staging environment.

### Gap 1: ECR Pull-Through Cache Repos

**Seed:** Create a dummy ECR repo matching the pull-through prefix.

```bash
aws ecr create-repository --repository-name docker-hub/test-leak \
  --region us-east-1
```

**Verify:** Run the destroy workflow. The post-destroy sweep should
delete `docker-hub/test-leak`. The `ecr_repos` verification check
should report `clean`.

### Gap 2: Orphaned EBS Volumes from PVCs

**Seed:** Create a tagged EBS volume simulating a PVC-backed volume.

```bash
aws ec2 create-volume --availability-zone us-east-1a --size 1 \
  --tag-specifications 'ResourceType=volume,Tags=[{Key=kubernetes.io/cluster/meshant-staging,Value=owned}]' \
  --region us-east-1
```

**Verify:** The pre-destroy EBS sweep should wait for `available`
state and delete it. The `ebs_volumes` check should report `clean`.

### Gap 3: KMS Alias Pending Deletion

**Seed:** KMS aliases naturally remain after `terraform destroy`
(pending deletion window). No manual seeding needed.

**Verify:** The `kms_aliases` check should report `pending`
(warning-only, D167), NOT `leftover`. Job should still pass.

### Gap 4: Secrets Manager Staging Secrets

**Seed:** Create a tagged secret.

```bash
aws secretsmanager create-secret --name test-leak-staging \
  --secret-string '{"dummy":"true"}' \
  --tags Key=Environment,Value=staging \
  --region us-east-1
```

**Verify:** The post-destroy sweep should force-delete it. The
`secrets_manager` check should report `clean`.

### Gap 5: CloudWatch Log Groups

**Seed:** Create a log group under one of the staging prefixes.

```bash
aws logs create-log-group \
  --log-group-name /aws/eks/meshant-staging/test-leak \
  --region us-east-1
```

**Verify:** The post-destroy sweep should delete it. The
`cwl_log_groups` check should report `clean`.

### Gap 7: Plan-Destroy Artifact

**Seed:** No seeding needed — the artifact is generated on every run.

**Verify:** After the workflow completes, check the GitHub Actions
artifacts tab. `terraform-destroy-plan-<run_id>` should contain
`destroy.plan` and `destroy_plan.txt`. The `plan_artifact` check
should report `clean`.

### Gap 8: Terraform Refresh

**Seed:** Manually delete a staging resource (e.g. a security group)
via the AWS Console before running the destroy workflow.

**Verify:** The refresh-only step should reconcile the state without
errors. The subsequent destroy should not fail with "resource already
deleted".

### Gap 9: VPC Endpoint Cleanup

**Seed:** Create a VPC endpoint in the staging VPC.

```bash
aws ec2 create-vpc-endpoint --vpc-id $VPC_ID \
  --service-name com.amazonaws.us-east-1.s3 --vpc-endpoint-type Gateway \
  --region us-east-1
```

**Verify:** The VPC cleanup step 1 should delete it before ENI
cleanup. The `vpc_endpoints` check should report `clean`.

### Gap 10: Stale State Lock

**Seed:** Acquire a Terraform state lock from a separate terminal.

```bash
cd infrastructure/terraform/environments/staging
terraform plan -lock=true -lock-timeout=300s \
  -var="db_password=x" -var="cache_auth_token=x" \
  -var="queue_auth_token=x" -var="events_auth_token=x" \
  -var="channels_auth_token=x" -var="ses_sender_identity=x"
```

**Verify:** The force-unlock step should detect and release the lock.
The subsequent init/destroy should proceed without lock errors.

### Gap 11: Verification Hard-Fail

**Seed:** After a destroy completes, manually create a leftover
resource (e.g. the ECR repo from Gap 1).

**Verify:** Re-run only the verification step (or re-trigger the
workflow on an already-destroyed account with the seeded resource).
The job should exit 1 with the `ecr_repos` check showing `leftover`.

### Gap 12: gp3-wfc StorageClass

**Seed:** No seeding needed if the StorageClass exists from Phase 214.

**Verify:** After Helm cleanup, confirm `kubectl get storageclass`
does not list `gp3-wfc`. If the cluster is already gone, this is a
no-op.

### Gap 13: ALB Target Groups

**Seed:** Create a target group in the staging VPC.

```bash
aws elbv2 create-target-group --name k8s-hubstaging-test \
  --protocol HTTP --port 80 --vpc-id $VPC_ID \
  --target-type ip --region us-east-1
```

**Verify:** The post-destroy sweep should delete it. The
`alb_target_groups` check should report `clean`.

### Gap 14: EBS Migration Snapshots

**Seed:** Create a tagged snapshot.

```bash
VOL_ID=$(aws ec2 create-volume --availability-zone us-east-1a \
  --size 1 --region us-east-1 --query 'VolumeId' --output text)
sleep 5
SNAP_ID=$(aws ec2 create-snapshot --volume-id $VOL_ID \
  --tag-specifications 'ResourceType=snapshot,Tags=[{Key=purpose,Value=phase214-fuseki-pv-migration}]' \
  --region us-east-1 --query 'SnapshotId' --output text)
aws ec2 delete-volume --volume-id $VOL_ID --region us-east-1
echo "Seeded snapshot: $SNAP_ID"
```

**Verify:** The post-destroy sweep should delete the snapshot.

### Gap 15: Concurrency + Timeout

**Seed:** Trigger the destroy workflow and immediately trigger the
apply workflow (`terraform.yml`) on the staging branch.

**Verify:** The second workflow should queue (not run in parallel)
due to the shared `terraform-staging-state` concurrency group. Check
the Actions tab — one should show "Queued" or "Waiting".

---

## Related

- Workflow: `.github/workflows/terraform-destroy-staging.yml`
- Apply workflow: `.github/workflows/terraform.yml`
- Terraform modules: `infrastructure/terraform/`
- Phase 218 spec: `openspec/changes/preprod01/specs/staging-destroy-parity/spec.md`
- [Operator Documentation](../mvpdocs/operations/index.md)
