"""Automated Merkle integrity verification for CI (277.B.077).

Provides a self-contained smoke test that exercises the full audit
hash-chain + Merkle-snapshot pipeline and fails the build if any
integrity check fails.
"""

from __future__ import annotations

import json
import uuid
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from hub.apps.audit.chain import (
    merkle_root,
    verify_chain_against_snapshots,
    verify_chain_segment,
)
from hub.apps.audit.models import AuditEvent, AuditMerkleSnapshot

# Number of synthetic audit events to create for the CI smoke test.
_CI_SMOKE_TEST_EVENT_COUNT = 10

# Synthetic signing key for CI (64 hex chars = 32 bytes).
# This is ONLY used in CI — production keys come from
# AUDIT_CHAIN_SIGNING_KEYS_JSON environment variable.
_CI_SIGNING_KEY = "0" * 64


def _ensure_signing_keys() -> dict[str, list[str]]:
    """Return a signing-keys dict suitable for CI or production."""
    raw = getattr(settings, "AUDIT_CHAIN_SIGNING_KEYS_JSON", None)
    if raw:
        return raw
    # CI / test fallback: a synthetic key for the smoke-test tenant.
    return {"__default__": [_CI_SIGNING_KEY]}


def _ci_signature_verifier(tenant_id: str | None, root_hex: str, signature_hex: str) -> bool:
    """Verify snapshot signature using the CI signing key or configured keys."""
    import hashlib
    import hmac

    keys = _ensure_signing_keys()
    tenant_key = tenant_id or "__platform__"
    key_ring: list[str] = keys.get(tenant_key) or keys.get("__default__") or [_CI_SIGNING_KEY]

    for key_hex in key_ring:
        try:
            expected = hmac.new(
                bytes.fromhex(key_hex),
                root_hex.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            if hmac.compare_digest(expected, signature_hex):
                return True
        except (ValueError, TypeError):
            continue
    return False


def _sign_root(root_hex: str, key_hex: str = _CI_SIGNING_KEY) -> str:
    """HMAC-SHA256 sign a Merkle root hex string."""
    import hashlib
    import hmac

    return hmac.new(
        bytes.fromhex(key_hex),
        root_hex.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def run_integrity_verification(
    *,
    tenant_id: str | None = None,
    include_snapshots: bool = True,
    create_test_data: bool = False,
) -> dict[str, Any]:
    """Run the full chain + Merkle integrity verification.

    Returns a dict with ``verified``, ``summary``, and detailed results.
    """
    now = timezone.now()

    # ── Resolve tenant ────────────────────────────────────────────────────
    if tenant_id is None:
        # Find a tenant with audit events, or fall back to creating test data
        event = AuditEvent.objects.order_by("created_at").first()
        if event is not None and event.tenant_id:
            tenant_id = str(event.tenant_id)
        else:
            create_test_data = True
            tenant_id = str(uuid.uuid4())

    # ── Create synthetic test data if requested or needed ─────────────────
    if create_test_data:
        _create_ci_smoke_test_events(tenant_id, _CI_SMOKE_TEST_EVENT_COUNT, now)

    # ── Verify chain segment ──────────────────────────────────────────────
    events = list(
        AuditEvent.objects.filter(tenant_id=tenant_id)
        .order_by("chain_sequence")
        .only(
            "id",
            "tenant_id",
            "actor_user_id",
            "resource_type",
            "resource_id",
            "action",
            "result",
            "details_json",
            "full_details_json",
            "chain_sequence",
            "chain_hash",
            "prev_chain_hash",
            "timestamp",
        )
    )

    if not events:
        return {
            "verified": False,
            "error": "No audit events found for chain verification.",
            "tenant_id": tenant_id,
            "checked": 0,
            "mismatches": [],
            "gaps": [],
            "snapshots_checked": 0,
            "snapshot_mismatches": [],
        }

    base_result = verify_chain_segment(events)

    result: dict[str, Any] = {
        "verified": base_result.verified,
        "tenant_id": tenant_id,
        "checked": base_result.checked,
        "mismatches": [m.to_dict() for m in base_result.mismatches],
        "gaps": [list(g) for g in base_result.gaps],
        "snapshots_checked": 0,
        "snapshot_mismatches": [],
    }

    # ── Snapshot cross-check ──────────────────────────────────────────────
    if include_snapshots:
        # Create a snapshot if none exist for this tenant
        existing = AuditMerkleSnapshot.objects.filter(
            tenant_id=tenant_id,
        ).exists()
        if not existing:
            _create_ci_snapshot(tenant_id, events, now)

        snapshots = list(
            AuditMerkleSnapshot.objects.filter(tenant_id=tenant_id).order_by("period_start")
        )
        snapshot_pairs: list[tuple[Any, list[Any]]] = []
        for snap in snapshots:
            window_events = [
                ev for ev in events if snap.period_start <= ev.timestamp < snap.period_end
            ]
            snapshot_pairs.append((snap, window_events))

        augmented = verify_chain_against_snapshots(
            base=base_result,
            snapshot_pairs=snapshot_pairs,
            signature_verifier=_ci_signature_verifier,
        )
        result["verified"] = augmented.verified
        result["snapshots_checked"] = augmented.snapshots_checked
        result["snapshot_mismatches"] = [m.to_dict() for m in augmented.snapshot_mismatches]

    result["summary"] = (
        "PASS"
        if result["verified"]
        else f"FAIL — {len(result['mismatches'])} chain mismatch(es), "
        f"{len(result['snapshot_mismatches'])} snapshot mismatch(es)"
    )
    return result


def _create_ci_smoke_test_events(tenant_id: str, count: int, now) -> None:
    """Create synthetic audit events with proper chain linkage for CI smoke test."""
    for i in range(count):
        AuditEvent.objects.create(
            tenant_id=tenant_id,
            actor_user_id=None,
            resource_type="SYSTEM",
            resource_id=str(uuid.uuid4()),
            action="AUDIT_INTEGRITY_SMOKE_TEST",
            result="SUCCESS",
            details_json={"smoke_test_index": i, "timestamp": now.isoformat()},
            timestamp=now - timedelta(minutes=count - i),
        )


def _create_ci_snapshot(tenant_id: str, events: list[AuditEvent], now) -> None:
    """Create a single Merkle snapshot covering all *events*."""
    if not events:
        return
    period_start = min(ev.timestamp for ev in events)
    period_end = max(ev.timestamp for ev in events) + timedelta(seconds=1)
    leaves = [ev.chain_hash for ev in events if ev.chain_hash]
    root_hex = merkle_root(leaves)
    signature_hex = _sign_root(root_hex)

    AuditMerkleSnapshot.objects.create(
        tenant_id=tenant_id,
        period_start=period_start,
        period_end=period_end,
        event_count=len(events),
        first_chain_sequence=min(ev.chain_sequence for ev in events if ev.chain_sequence),
        last_chain_sequence=max(ev.chain_sequence for ev in events if ev.chain_sequence),
        root_hex=root_hex,
        signature_hex=signature_hex,
        signing_key_index=0,
    )


class Command(BaseCommand):
    help = (
        "Verify audit hash-chain + Merkle snapshot integrity. "
        "Intended for CI automated verification (277.B.077)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-id",
            help="Verify a specific tenant (default: auto-detect or create smoke-test data).",
        )
        parser.add_argument(
            "--create-test-data",
            action="store_true",
            help="Create synthetic audit events + snapshot before verifying (CI smoke test).",
        )
        parser.add_argument(
            "--include-snapshots",
            action="store_true",
            default=True,
            help="Cross-check chain against Merkle snapshots (default: on).",
        )
        parser.add_argument(
            "--no-snapshots",
            action="store_true",
            help="Skip snapshot cross-check (chain-only verification).",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output results as JSON.",
        )
        parser.add_argument(
            "--tamper-test",
            action="store_true",
            help=(
                "Phase 277.B.112 — CI tamper-detection smoke test. "
                "Creates events, tampers one chain_hash, verifies detection, "
                "cleans up. Exit 0 = tamper detected (PASS), "
                "exit 1 = tamper NOT detected (FAIL)."
            ),
        )

    def _run_tamper_test(self) -> bool:
        """Create events, tamper one chain_hash, verify detection.

        Returns True if tampering was detected (PASS), False if it slipped
        through undetected (FAIL — detection regression).
        """
        from hub.apps.audit.models import AuditEvent

        # 1. Create synthetic test data
        self.stdout.write("Creating 10 synthetic events for tamper test...")
        run_integrity_verification(create_test_data=True, include_snapshots=False)

        # 2. Pick the most recent event and tamper its chain_hash
        event = AuditEvent.objects.order_by("-timestamp").first()
        if not event or not event.chain_hash:
            self.stdout.write(
                self.style.ERROR(
                    "No chain_hash found on test event — hash-chain may not be enabled."
                )
            )
            return False

        original_hash = event.chain_hash
        tampered_hash = original_hash[:60] + ("F" if original_hash[60] != "F" else "0") * 4
        AuditEvent.objects.filter(pk=event.pk).update(chain_hash=tampered_hash)
        self.stdout.write(
            f"Tampered event {event.pk}: {original_hash[:16]}... → {tampered_hash[:16]}..."
        )

        # 3. Verify — the tamper MUST be detected
        result = run_integrity_verification(
            tenant_id=str(event.tenant_id) if event.tenant_id else None,
            include_snapshots=False,
            create_test_data=False,
        )

        # 4. Clean up test data
        AuditEvent.all_objects.filter(details_json__icontains="_CI_SMOKE_TEST_EVENT").delete()

        tamper_detected = not result["verified"]
        if tamper_detected:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Tamper DETECTED ({len(result.get('mismatches', []))} mismatches) — "
                    "integrity verification is working."
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    "TAMPER NOT DETECTED! Hash-chain integrity regression — "
                    "a tampered chain_hash passed verification."
                )
            )
        return tamper_detected

    def handle(self, *args, **options):
        if options["tamper_test"]:
            ok = self._run_tamper_test()
            raise SystemExit(0 if ok else 1)

        include_snapshots = options["include_snapshots"] and not options["no_snapshots"]
        result = run_integrity_verification(
            tenant_id=options["tenant_id"],
            include_snapshots=include_snapshots,
            create_test_data=options["create_test_data"],
        )

        if options["json"]:
            self.stdout.write(json.dumps(result, indent=2, default=str))
            if not result["verified"]:
                raise SystemExit(1)
            return

        self.stdout.write(f"Verified: {result['verified']}")
        self.stdout.write(f"Tenant:   {result.get('tenant_id', 'N/A')}")
        self.stdout.write(f"Checked:  {result['checked']} event(s)")
        self.stdout.write(f"Mismatches: {len(result.get('mismatches', []))}")
        self.stdout.write(f"Snapshots checked: {result.get('snapshots_checked', 0)}")
        self.stdout.write(f"Snapshot mismatches: {len(result.get('snapshot_mismatches', []))}")
        self.stdout.write(f"Summary: {result.get('summary', 'UNKNOWN')}")

        if not result["verified"]:
            self.stderr.write(
                self.style.ERROR(
                    f"Audit integrity verification FAILED for tenant {result.get('tenant_id')}"
                )
            )
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS("Audit integrity verification PASSED"))
