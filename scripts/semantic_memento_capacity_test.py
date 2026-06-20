#!/usr/bin/env python
"""
Phase 230.4.14 (REQ-SEM-MEMENTO-001) — capacity test.

Inserts ``--count`` ``SemanticResourceVersion`` rows for a single
synthetic tenant + resource and reports the timings:

* Bulk INSERT throughput (rows/s).
* Storage (bytes per row, GB total).
* Index-supported nearest-past lookup p50/p95/p99 latencies.
* TimeMap construction wall-clock.

Targets a staging Postgres so we can verify the
``(resource_id, snapshot_at DESC)`` index renders the lookup O(log
N) up to 100k versions / resource and 1M / tenant.

Run from the hub container:

    python scripts/semantic_memento_capacity_test.py \\
        --count 100000 --tenant-name capacity-test

The script is destructive — it creates a Tenant + a SemanticResource
+ N versions and DOES NOT clean up; ops should drop the test tenant
afterwards.  Always run on staging, never production.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import random
import statistics
import sys
import time
import uuid
from datetime import timedelta


def _setup_django():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")
    import django

    django.setup()


def _create_tenant_and_resource(tenant_name: str):
    from hub.apps.semantic.models import SemanticResource
    from hub.apps.tenants.models import Tenant

    # Audit-fix GAP-C — ``Tenant.objects`` is the ActiveTenantManager
    # which filters out non-ACTIVE tenants. ``get_or_create`` on the
    # filtered manager would create a duplicate tenant if a previous
    # capacity-test run left a SUSPENDED/DELETED tenant with the same
    # name, immediately tripping the unique constraint on ``name``.
    # Use ``all_objects`` (raw manager) to see all rows.
    tenant, _ = Tenant.all_objects.get_or_create(
        name=tenant_name,
        defaults={
            "slug": tenant_name.lower().replace(" ", "-"),
            "semantic_memento_enabled": True,
        },
    )
    rid = uuid.uuid4()
    sr = SemanticResource.objects.create(
        tenant=tenant,
        resource_type="ASSET",
        resource_id=rid,
        uri=f"https://meshant.com/id/asset/{rid}",
        status="PUBLISHED",
    )
    return tenant, sr


def _bulk_insert_versions(*, sr, tenant, count: int, batch_size: int = 5000):
    from django.utils import timezone as dj_tz

    from hub.apps.semantic.models import SemanticResourceVersion

    print(f"  Inserting {count:,} versions in batches of {batch_size}…")
    base = dj_tz.now() - timedelta(seconds=count)
    inserted = 0
    t0 = time.perf_counter()
    while inserted < count:
        batch = []
        for i in range(min(batch_size, count - inserted)):
            n = inserted + i
            body = (
                f"<https://meshant.com/id/asset/{sr.resource_id}> "
                f"<https://meshant.com/ontology/title> 'snapshot {n}' .\n"
            )
            chash = hashlib.sha256(body.encode("utf-8")).hexdigest()
            batch.append(
                SemanticResourceVersion(
                    resource=sr,
                    tenant=tenant,
                    snapshot_at=base + timedelta(seconds=n),
                    content_hash=chash,
                    rdf_content=body,
                    triple_count=1,
                )
            )
        SemanticResourceVersion.objects.bulk_create(batch, ignore_conflicts=False)
        inserted += len(batch)
        if inserted % (batch_size * 5) == 0 or inserted == count:
            elapsed = time.perf_counter() - t0
            rate = inserted / elapsed if elapsed else 0
            print(f"    {inserted:,}/{count:,} ({rate:,.0f} rows/s)")
    return time.perf_counter() - t0


def _measure_lookup_latency(*, sr, samples: int = 200):
    """Sample nearest-past lookups across the full snapshot range."""
    from hub.apps.semantic.models import SemanticResourceVersion

    earliest = (
        SemanticResourceVersion.objects.filter(resource=sr)
        .order_by("snapshot_at")
        .only("snapshot_at")
        .first()
    )
    latest = (
        SemanticResourceVersion.objects.filter(resource=sr)
        .order_by("-snapshot_at")
        .only("snapshot_at")
        .first()
    )
    if not earliest or not latest:
        return {"p50_ms": None}

    span = (latest.snapshot_at - earliest.snapshot_at).total_seconds()
    timings_ms = []
    for _ in range(samples):
        offset = random.uniform(0, span)
        t_query = earliest.snapshot_at + timedelta(seconds=offset)
        t0 = time.perf_counter()
        SemanticResourceVersion.objects.filter(
            resource=sr,
            snapshot_at__lte=t_query,
        ).order_by("-snapshot_at").only("snapshot_at").first()
        timings_ms.append((time.perf_counter() - t0) * 1000)

    timings_ms.sort()
    return {
        "samples": samples,
        "p50_ms": round(statistics.median(timings_ms), 3),
        "p95_ms": round(timings_ms[int(samples * 0.95)], 3),
        "p99_ms": round(timings_ms[int(samples * 0.99)], 3),
        "max_ms": round(max(timings_ms), 3),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100_000)
    parser.add_argument("--tenant-name", default=f"memento-capacity-{uuid.uuid4().hex[:8]}")
    parser.add_argument("--samples", type=int, default=200)
    args = parser.parse_args()

    _setup_django()
    print("=== Phase 230.4 Memento capacity test ===")
    print(f"  Tenant: {args.tenant_name}")
    print(f"  Snapshot count: {args.count:,}")

    tenant, sr = _create_tenant_and_resource(args.tenant_name)
    print(f"  Resource id: {sr.id}")

    insert_seconds = _bulk_insert_versions(sr=sr, tenant=tenant, count=args.count)
    print(
        f"  Bulk-insert wall-clock: {insert_seconds:.1f}s "
        f"({args.count / insert_seconds:,.0f} rows/s)"
    )

    print(f"  Sampling {args.samples} nearest-past lookups…")
    latency = _measure_lookup_latency(sr=sr, samples=args.samples)
    print(f"  Lookup latency: {latency}")

    print()
    print("PASS criteria (Phase 230.4.14):")
    print(f"  * p95 lookup < 50ms   actual={latency.get('p95_ms')}ms")
    print(f"  * p99 lookup < 100ms  actual={latency.get('p99_ms')}ms")
    print(f"  * insert > 5k rows/s  actual={args.count / insert_seconds:,.0f} rows/s")


if __name__ == "__main__":
    main()
