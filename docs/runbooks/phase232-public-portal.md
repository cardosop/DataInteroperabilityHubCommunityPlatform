# Runbook — Phase 232 public portal (`/api/v1/public/*`)

## Symptoms

- Grafana **Phase 232 — Public portal** shows rising 5xx or Prometheus alert **Phase232PublicPortal5xxRate**.

## Checklist

1. Confirm API pods healthy and DB migrations applied for `dsar` public ingress.
2. Tail API logs filtered by `/api/v1/public/` for stack traces.
3. Verify hCaptcha / IdP configuration and rate limits on public routes.
4. If object-storage related, confirm presign credentials and Phase 232.8 closeout bucket IAM (IRSA) includes needed ARNs.

## Escalation

- Page compliance-platform on-call; involve security if WAF or abuse suspected.

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
