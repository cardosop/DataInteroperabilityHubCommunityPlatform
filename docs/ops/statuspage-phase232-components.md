# Statuspage components — Phase 232.8.9

Register the following **functional** components (names are suggestions; align with corporate Statuspage naming):

| Component | User-visible scope | Typical dependencies |
| --- | --- | --- |
| **Compliance — Consent Banner** | First-party consent capture script / configuration API | CDN, API `/api/v1/governance/consent-*`, signing keys |
| **Compliance — DSAR Portal** | Public DSAR ingress + mail OTP | API `/api/v1/public/*`, email provider, object storage |
| **Compliance — Breach Portal** | Breach dashboards & statutory notifications | API `/api/v1/governance/breach-*`, email, proof storage bucket |

### Operational guidance

- Tie each component to the Grafana **Phase 232** dashboards and Prometheus `phase232_*` alerts.
- For partial failures (e.g. email only), create **nested components** or **subscriber notice templates** describing DSAR OTP delay vs full breach outage.
