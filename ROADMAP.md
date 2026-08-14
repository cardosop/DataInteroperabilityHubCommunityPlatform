# Roadmap

The open-source core is the community surface of the Meshant data
platform. Direction is set by the maintainers with input from the
community; paid-layer domains (semantic, marketplace, billing/BaaS,
ML/AI, social) ship through the hosted SaaS and are listed here for
visibility only.

## Now

- Core-only test stack + CI hardening (GATE-29 boundary, scoped gates)
- Connector contributions (CKAN, dados.gov.br, AWS Data Exchange, …)
- Adopt-a-journey: test coverage for the canonical user journeys

## Next

- Community Helm chart for the core stack
- `requirements-core.txt` lean install profile
- Publish pipeline automation (mirror sync + release tags)

## SaaS-only (not in this repository)

- Hosted marketplace with KYB/KYC + Stripe Connect rails
- Semantic layer operations (Fuseki clusters, federation, LDN)
- Continuous compliance scanning at scale
