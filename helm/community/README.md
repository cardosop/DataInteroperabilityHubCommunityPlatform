# DataInteroperabilityHub — community chart (core)

Minimal, deployable chart for the **open-source core** (HUB_CORE_ONLY=1):
API + worker + frontend with Postgres, Redis, and MinIO.

## Install

```bash
kubectl create namespace datahub
kubectl -n datahub create secret generic datahub-core-secrets \
  --from-literal=SECRET_KEY="$(openssl rand -base64 48)" \
  --from-literal=JWT_SECRET_KEY="$(openssl rand -base64 48)" \
  --from-literal=POSTGRES_PASSWORD="$(openssl rand -base64 24)" \
  --from-literal=MINIO_ROOT_USER=minio \
  --from-literal=MINIO_ROOT_PASSWORD="$(openssl rand -base64 24)"
helm install datahub-core ./helm/community -n datahub \
  --set ingress.host=datahub.example.com \
  --set images.api=ghcr.io/<org>/DataInteroperabilityHub/api-core:latest \
  --set images.worker=ghcr.io/<org>/DataInteroperabilityHub/worker-core:latest \
  --set images.frontend=ghcr.io/<org>/DataInteroperabilityHub/frontend:latest
```

## Notes

- The paid layer (semantic, marketplace, billing/BaaS, ML/AI, social) is a
  hosted-SaaS capability and is intentionally absent — the API runs
  `HUB_CORE_ONLY=1`.
- Secrets are injected via `secretName` references only; never commit
  values.
- This chart targets the core images published by the public CI
  (`ci-core.yml`, GHCR, built from the public tree).
