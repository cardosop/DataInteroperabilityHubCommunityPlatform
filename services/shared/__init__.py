# Shared modules for all FastAPI microservices.
# auth      — internal API key enforcement (require_internal_key dependency)
# middleware — RequestSizeLimitMiddleware (50 MiB default)
# metrics   — Prometheus counters/histograms shared across services
# tracing   — OpenTelemetry setup helpers
