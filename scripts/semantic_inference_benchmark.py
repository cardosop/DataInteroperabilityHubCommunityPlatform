#!/usr/bin/env python
"""
Phase 230.7.6 (REQ-SEM-INFERENCE-001) — inference latency benchmark.

Drives the same SPARQL query against ``/api/v1/semantic/sparql`` with the
tenant's ``semantic_inference_enabled`` flag flipped on then off, captures
per-request latency from the response timing, and reports p50/p95/p99.

Used by the nightly ``.github/workflows/semantic-inference-benchmark.yml``
to assert the spec's p99 < 2s budget and a sane on/off ratio. Standalone
runnable for ops investigations.

Exit codes:
    0 — all gates passed.
    1 — login / API error (infra problem, not a real regression).
    2 — p99 exceeded the hard budget (real regression).
    3 — on/off ratio exceeded the budget (reasoner regression).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time

import requests

# Spec scenario — superclass closure against the hub ontology. Picked so
# inference-on returns at least one binding (DataAsset is a subClassOf
# DataResource per the Meshant ontology) while inference-off returns
# zero, exercising the reasoner path even when the tenant graph is small.
SPEC_QUERY = (
    "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> "
    "PREFIX meshant: <https://meshant.com/ontology/> "
    "SELECT (COUNT(?a) AS ?n) WHERE { ?a a meshant:DataResource } LIMIT 1"
)


def _login(api_url: str, email: str, password: str) -> tuple[str, str]:
    """Returns (auth_token, tenant_id). Auth is OIDC password-grant
    against the hub /auth/login endpoint."""
    resp = requests.post(
        f"{api_url}/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"login failed: HTTP {resp.status_code} — {resp.text[:300]}")
        sys.exit(1)
    body = resp.json()
    token = body.get("access_token") or body.get("token")
    tenant_id = body.get("tenant_id") or body.get("user", {}).get("tenant_id")
    if not token or not tenant_id:
        print(f"login response missing token/tenant: {body}")
        sys.exit(1)
    return token, tenant_id


def _set_inference_flag(api_url: str, token: str, tenant_id: str, enabled: bool) -> None:
    """Flip ``Tenant.semantic_inference_enabled`` via the admin API.

    The endpoint is ``PATCH /tenants/{id}/`` with a partial body. Falls
    back to a noisy log if the endpoint isn't available — the bench
    still runs but the on/off comparison is meaningless without the
    flip. The runbook calls this out.
    """
    resp = requests.patch(
        f"{api_url}/tenants/{tenant_id}/",
        json={"semantic_inference_enabled": enabled},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if resp.status_code not in (200, 202, 204):
        print(
            f"WARN: could not flip inference flag (HTTP {resp.status_code}); "
            f"the on/off comparison may be invalid. Body: {resp.text[:200]}"
        )


def _bench_one(api_url: str, token: str, samples: int) -> dict[str, float]:
    """Run ``samples`` queries and return percentile-summarised latency."""
    timings_ms: list[float] = []
    endpoint_seen = ""
    for _ in range(samples):
        t0 = time.perf_counter()
        resp = requests.post(
            f"{api_url}/semantic/sparql",
            json={"query": SPEC_QUERY, "format": "json", "timeout": 10},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        if resp.status_code == 200:
            timings_ms.append(elapsed_ms)
            endpoint_seen = resp.headers.get("X-Fuseki-Endpoint", endpoint_seen)
        else:
            print(f"WARN: HTTP {resp.status_code} during sample; skipping")
    if not timings_ms:
        print("ERROR: zero successful samples")
        sys.exit(1)
    timings_ms.sort()
    return {
        "samples": len(timings_ms),
        "p50_ms": round(statistics.median(timings_ms), 1),
        "p95_ms": round(timings_ms[int(len(timings_ms) * 0.95)], 1),
        "p99_ms": round(timings_ms[int(len(timings_ms) * 0.99)], 1)
        if len(timings_ms) >= 100
        else round(max(timings_ms), 1),
        "max_ms": round(max(timings_ms), 1),
        "endpoint_seen": endpoint_seen,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--samples", type=int, default=50)
    parser.add_argument("--p99-budget-ms", type=int, default=2000)
    parser.add_argument("--warn-budget-ms", type=int, default=1500)
    parser.add_argument("--ratio-budget", type=float, default=5.0)
    parser.add_argument("--output", default="-")
    args = parser.parse_args()

    print("=== Phase 230.7 inference benchmark ===")
    print(f"  API: {args.api_url}")
    print(f"  Samples / mode: {args.samples}")

    token, tenant_id = _login(args.api_url, args.email, args.password)
    print(f"  Tenant: {tenant_id}")

    print()
    print("→ inference=False")
    _set_inference_flag(args.api_url, token, tenant_id, enabled=False)
    time.sleep(1)  # let any in-flight queries settle
    off = _bench_one(args.api_url, token, args.samples)
    print(f"  {off}")

    print()
    print("→ inference=True")
    _set_inference_flag(args.api_url, token, tenant_id, enabled=True)
    time.sleep(1)
    on = _bench_one(args.api_url, token, args.samples)
    print(f"  {on}")

    # Restore the flag to whatever it was before. We default to False
    # (the safer default) because we don't snapshot the prior value.
    _set_inference_flag(args.api_url, token, tenant_id, enabled=False)

    ratio = on["p95_ms"] / off["p95_ms"] if off["p95_ms"] > 0 else float("inf")

    summary = {
        "off": off,
        "on": on,
        "ratio_p95": round(ratio, 2),
        "p99_budget_ms": args.p99_budget_ms,
        "ratio_budget": args.ratio_budget,
    }

    if args.output == "-":
        print(json.dumps(summary, indent=2))
    else:
        with open(args.output, "w") as fh:
            json.dump(summary, fh, indent=2)

    print()
    print("=== Gate evaluation ===")
    print(f"  p99 (on)            = {on['p99_ms']:.1f} ms  (budget {args.p99_budget_ms} ms)")
    print(f"  ratio p95 on/off    = {ratio:.2f}x  (budget {args.ratio_budget}x)")
    print(f"  endpoint label (on) = {on['endpoint_seen']!r}  (expected 'dataset/inferred')")

    if on["p99_ms"] > args.p99_budget_ms:
        print("FAIL: p99 budget exceeded")
        return 2
    if ratio > args.ratio_budget:
        print("FAIL: on/off latency ratio exceeded")
        return 3
    if on["p99_ms"] > args.warn_budget_ms:
        print("WARN: p99 above early-warning threshold")
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
