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

## Relationship to the full chart (Phase P.8)

`helm/` is the FULL-mode chart: it adds paid service deployments
(`semantic-service`, `dq-service`, `datacontract-service`,
`compliance-service`, `prefect-*`, fuseki, …) on top of the same core
services this community chart provides. This chart is NOT a trimmed copy —
it is the deliberate OSS deployment surface.

The same asymmetry applies to Compose:
`docker-compose.production.yml` intentionally omits
semantic / dq / datacontract — in production those are Helm-deployed from
the full chart, and Compose is the dev/test/staging path that stops at the
core-plus-fuseki boundary. Do not "complete" the production compose file
with paid services: two deployment sources of truth drift.
