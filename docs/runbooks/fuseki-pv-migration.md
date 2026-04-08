# Fuseki PV migration: gp3 (Immediate) → gp3-wfc (WaitForFirstConsumer)

**Purpose:** migrate the existing AZ-pinned `hub-staging-fuseki` PV from the
default `gp3` StorageClass (`volumeBindingMode: Immediate`) to the new
`gp3-wfc` StorageClass (`volumeBindingMode: WaitForFirstConsumer`) introduced
as the root-cause fix for the single-AZ node-group pin in
[`infrastructure/terraform/environments/staging/main.tf:161`](../../infrastructure/terraform/environments/staging/main.tf#L161).

**Audience:** SRE / staging operator.

**Prerequisites:**
- `kubectl` access to the staging cluster (`hub-staging` namespace)
- AWS CLI with permissions on `ec2:CreateSnapshot`, `ec2:DescribeSnapshots`
- The new `gp3-wfc` StorageClass already exists in the cluster (it ships with
  the chart at `helm/templates/storage/gp3-wfc-storageclass.yaml`)
- A maintenance window of ~30 minutes (fuseki will be unavailable during the
  cut-over)

---

## Why this migration is needed

The default `gp3` StorageClass on EKS uses `volumeBindingMode: Immediate`,
which provisions the EBS volume at PVC-creation time in an arbitrary AZ
(typically wherever the CSI controller pod happens to be running). The pod is
then forced to schedule in that same AZ for the lifetime of the volume.

In Phase 214.4 we set the staging node group to `desired_size=1` and
`subnet_ids = [private_subnet_ids[0]]` so the single node would always land
in the same AZ as the legacy pinned PVs. This works but leaves three issues:

1. **AZ pin = no HA at the AZ level** — when we restore multi-replica + the
   cluster autoscaler (Phase 214.4 D128 follow-up), the pin must be removed.
2. **Forced subnet pin couples Terraform infra to a runtime storage detail** —
   leaks an EBS implementation choice into the IaC layer.
3. **Any new EBS PV provisioned via the default SC inherits the same problem.**

The root-cause fix has two parts:

1. **`gp3-wfc` StorageClass** — `WaitForFirstConsumer` defers EBS provisioning
   until the scheduler picks a node, so new PVs land in the same AZ as their
   consumer pod. Future EBS PVs are AZ-mobile by construction.
2. **Migrate the legacy AZ-pinned PVs** (this runbook) — the existing
   `hub-staging-fuseki` PV remains tied to its original AZ until it is
   destroyed and recreated under the new SC.

After both parts are done, the single-AZ node-group pin can be safely removed.

---

## Strategy

We use a snapshot-and-restore approach because TDB2 is a single-writer
filesystem-backed triplestore: hot file copy is unsafe. The procedure is:

1. **Take an EBS snapshot** of the current `hub-staging-fuseki-data-0` volume
   (works in the source AZ; snapshots are AZ-independent).
2. **Scale fuseki to 0** to release the old PVC.
3. **Delete the old PVC** (the underlying EBS volume is preserved by
   `reclaimPolicy: Retain`, but we don't need it after the snapshot).
4. **Create a new PVC** that requests the snapshot as a data source, against
   the `gp3-wfc` StorageClass. Because of WFC, no volume is created yet.
5. **Scale fuseki back to 1.** When the pod is scheduled, the CSI driver
   creates the new EBS volume **from the snapshot** in whichever AZ the node
   landed in.
6. **Verify** the data is intact (SPARQL count of `dcat:Dataset` triples).
7. **Delete the snapshot and the old EBS volume** to stop paying for them.

Total downtime: ~5 minutes (steps 2–5).

---

## Step-by-step

> All commands assume `kubectl config current-context` points at the staging
> cluster and the default namespace is `hub-staging`. If not, prefix every
> `kubectl` command with `-n hub-staging`.

### 1. Pre-flight verification

```bash
# Confirm the new SC exists
kubectl get storageclass gp3-wfc -o jsonpath='{.volumeBindingMode}{"\n"}'
# Expected: WaitForFirstConsumer

# Confirm the current fuseki PVC and PV
kubectl -n hub-staging get pvc -l app.kubernetes.io/component=fuseki
# Expected: fuseki-data-hub-staging-fuseki-0   Bound   pvc-XXXX   10Gi   RWO   gp3
PVC_NAME=$(kubectl -n hub-staging get pvc -l app.kubernetes.io/component=fuseki -o jsonpath='{.items[0].metadata.name}')
PV_NAME=$(kubectl -n hub-staging get pvc "$PVC_NAME" -o jsonpath='{.spec.volumeName}')
EBS_VOLUME_ID=$(kubectl get pv "$PV_NAME" -o jsonpath='{.spec.csi.volumeHandle}')
echo "PVC=$PVC_NAME"
echo "PV=$PV_NAME"
echo "EBS volume ID=$EBS_VOLUME_ID"

# Capture a baseline triple count for post-migration verification
kubectl -n hub-staging port-forward svc/hub-staging-fuseki 3030:3030 &
PF_PID=$!
sleep 3
BASELINE_COUNT=$(curl -s -u admin:"$FUSEKI_ADMIN_PASSWORD" \
  --data-urlencode 'query=SELECT (COUNT(*) AS ?c) WHERE { ?s ?p ?o }' \
  http://localhost:3030/hub/sparql | jq -r '.results.bindings[0].c.value')
echo "Baseline triple count: $BASELINE_COUNT"
kill $PF_PID
```

Record `EBS_VOLUME_ID` and `BASELINE_COUNT` somewhere durable (Slack, ticket,
etc.) — you will compare to them in step 7.

### 2. Take an EBS snapshot

```bash
SNAPSHOT_ID=$(aws ec2 create-snapshot \
  --volume-id "$EBS_VOLUME_ID" \
  --description "fuseki-migration-pre-wfc-$(date -u +%Y%m%dT%H%M%SZ)" \
  --tag-specifications 'ResourceType=snapshot,Tags=[{Key=purpose,Value=phase214-fuseki-pv-migration}]' \
  --query 'SnapshotId' --output text)
echo "Snapshot=$SNAPSHOT_ID"

# Wait for it to complete (1-3 min for 10 GiB)
aws ec2 wait snapshot-completed --snapshot-ids "$SNAPSHOT_ID"
echo "Snapshot complete."
```

### 3. Scale fuseki down

```bash
kubectl -n hub-staging scale statefulset hub-staging-fuseki --replicas=0
kubectl -n hub-staging wait pod -l app.kubernetes.io/component=fuseki \
  --for=delete --timeout=2m
```

### 4. Create the snapshot-data-source PVC

First, a `VolumeSnapshotContent` and `VolumeSnapshot` so Kubernetes knows
about the EBS snapshot:

```bash
cat <<EOF | kubectl apply -f -
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshotContent
metadata:
  name: fuseki-migration-vsc
spec:
  deletionPolicy: Retain
  driver: ebs.csi.aws.com
  source:
    snapshotHandle: $SNAPSHOT_ID
  volumeSnapshotRef:
    name: fuseki-migration-vs
    namespace: hub-staging
  sourceVolumeMode: Filesystem
---
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: fuseki-migration-vs
  namespace: hub-staging
spec:
  source:
    volumeSnapshotContentName: fuseki-migration-vsc
EOF

# Wait for snapshot binding
kubectl -n hub-staging wait volumesnapshot fuseki-migration-vs \
  --for=jsonpath='{.status.readyToUse}'=true --timeout=2m
```

Now delete the old PVC. The PV stays around (`reclaimPolicy: Retain`) but
becomes orphaned; we'll clean it up at the end.

```bash
kubectl -n hub-staging delete pvc "$PVC_NAME"
```

### 5. Recreate the StatefulSet

The StatefulSet will recreate the PVC automatically when it scales back up,
**but** by default it uses `volumeClaimTemplates` (no data source). To force
the new PVC to come from the snapshot, we apply a one-shot
`PersistentVolumeClaim` with the same name *before* scaling up:

```bash
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: $PVC_NAME
  namespace: hub-staging
  labels:
    app.kubernetes.io/component: fuseki
    app.kubernetes.io/instance: hub-staging
    app.kubernetes.io/name: hub
spec:
  accessModes: ["ReadWriteOnce"]
  storageClassName: gp3-wfc
  resources:
    requests:
      storage: 10Gi
  dataSource:
    name: fuseki-migration-vs
    kind: VolumeSnapshot
    apiGroup: snapshot.storage.k8s.io
EOF

# The PVC stays Pending (no consumer yet). Now scale fuseki back up.
kubectl -n hub-staging scale statefulset hub-staging-fuseki --replicas=1
kubectl -n hub-staging wait pod hub-staging-fuseki-0 \
  --for=condition=Ready --timeout=10m
```

The CSI driver provisions a new EBS volume **in whichever AZ the new node
landed in**, restored from the snapshot. The volume is bound to the PVC, the
pod mounts it, and fuseki starts up against the same data set.

### 6. Verify

```bash
# Confirm the new PV is on gp3-wfc and Bound
kubectl -n hub-staging get pvc "$PVC_NAME" -o jsonpath='{.spec.storageClassName} {.status.phase}{"\n"}'
# Expected: gp3-wfc Bound

# Confirm the new PV is in a (potentially different) AZ
NEW_PV=$(kubectl -n hub-staging get pvc "$PVC_NAME" -o jsonpath='{.spec.volumeName}')
kubectl get pv "$NEW_PV" -o jsonpath='{.spec.nodeAffinity.required.nodeSelectorTerms[0].matchExpressions}{"\n"}' | jq

# Re-run the SPARQL count and compare
kubectl -n hub-staging port-forward svc/hub-staging-fuseki 3030:3030 &
PF_PID=$!
sleep 3
NEW_COUNT=$(curl -s -u admin:"$FUSEKI_ADMIN_PASSWORD" \
  --data-urlencode 'query=SELECT (COUNT(*) AS ?c) WHERE { ?s ?p ?o }' \
  http://localhost:3030/hub/sparql | jq -r '.results.bindings[0].c.value')
echo "Baseline:  $BASELINE_COUNT"
echo "Restored:  $NEW_COUNT"
kill $PF_PID
test "$NEW_COUNT" = "$BASELINE_COUNT" && echo "✅ counts match" || echo "❌ counts differ"
```

If the counts match, the migration is complete. If they differ, **STOP** —
do not proceed to cleanup. The old EBS volume and snapshot are still intact;
follow the rollback procedure below.

### 7. Cleanup (only after successful verification)

```bash
# Delete the VolumeSnapshot CRD objects
kubectl -n hub-staging delete volumesnapshot fuseki-migration-vs
kubectl delete volumesnapshotcontent fuseki-migration-vsc

# Delete the EBS snapshot
aws ec2 delete-snapshot --snapshot-id "$SNAPSHOT_ID"

# Delete the orphaned old PV (Retain policy left it Released)
kubectl delete pv "$PV_NAME"

# Delete the underlying old EBS volume (now no longer referenced)
aws ec2 delete-volume --volume-id "$EBS_VOLUME_ID"
```

---

## Rollback

If verification fails or fuseki refuses to start on the new PV:

```bash
# Scale fuseki to 0
kubectl -n hub-staging scale statefulset hub-staging-fuseki --replicas=0
kubectl -n hub-staging wait pod -l app.kubernetes.io/component=fuseki \
  --for=delete --timeout=2m

# Delete the broken new PVC
kubectl -n hub-staging delete pvc "$PVC_NAME"

# Manually re-create a PVC pointing at the original (still-Retained) PV
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: $PVC_NAME
  namespace: hub-staging
spec:
  accessModes: ["ReadWriteOnce"]
  storageClassName: gp3
  resources:
    requests:
      storage: 10Gi
  volumeName: $PV_NAME
EOF

# Patch the old PV's claimRef to bind it to the new PVC
kubectl patch pv "$PV_NAME" --type=json \
  -p='[{"op":"replace","path":"/spec/claimRef","value":{"namespace":"hub-staging","name":"'$PVC_NAME'"}}]'

# Scale fuseki back up
kubectl -n hub-staging scale statefulset hub-staging-fuseki --replicas=1
```

Verify the original triple count is back. Then investigate the failure on the
new PV (most common cause: snapshot was taken while fuseki was actively
writing — re-do the migration during a quiet window).

---

## After this migration succeeds, the next step is

1. Apply the same migration to `hub-staging-clamav-db-0` — **OR** flip
   `clamav.storage.mode` to `emptyDir` in `helm/values.staging.yaml` (already
   done in the Phase 214.4 follow-up commit) and let the next deploy delete
   the old PVC. ClamAV's virus DB is a re-downloadable cache, not state, so
   no snapshot is needed.
2. Remove the single-AZ pin in
   [`infrastructure/terraform/environments/staging/main.tf:161`](../../infrastructure/terraform/environments/staging/main.tf#L161):
   delete the `subnet_ids = [module.vpc.private_subnet_ids[0]]` line.
3. Run `terraform plan` and verify the only diff is the node group's subnet
   set going from `[private_subnet_ids[0]]` → all three private subnets.
4. Apply.
5. Install cluster-autoscaler (Phase 214.4 D128).
6. Restore multi-replica deployments where appropriate.

After step 5, an AZ failure costs you (#nodes ÷ #AZs) capacity instead of
100% of staging.
