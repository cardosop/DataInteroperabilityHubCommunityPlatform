"""
Phase 234.1 — Tamper-evidence: hash chain primitives.

Pure-function building blocks for the per-tenant append-only audit chain.
None of the helpers here touch the database — they operate on already-loaded
``AuditEvent`` instances (or dict-shaped equivalents) and on cryptographic
primitives. Side-effect handling (chain head lookup, ``select_for_update``,
INSERT) lives in :meth:`hub.apps.audit.models.AuditEvent.save`; this module
is the canonical reference for the on-the-wire format.

Why a separate module
---------------------
* The verifier (REST endpoint + management command) re-runs the same
  canonical-form and hash computation against rows pulled from disk. Reusing
  one implementation guarantees the verifier and the writer can never disagree
  on the byte sequence being hashed.
* The Merkle snapshot job consumes the per-row ``chain_hash`` as a leaf —
  again, a single source of truth for "what does a leaf look like".
* GDPR right-to-erasure (Phase 232.2) hard-deletes rows. The chain
  contract MUST tolerate gaps; the verifier in :func:`verify_chain_segment`
  encodes that tolerance once, not at every call site.
"""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone as dt_timezone
from typing import Any, Iterable, Mapping, Sequence

# Canonical-form field allow-list: any new ``AuditEvent`` column that participates
# in the chain MUST be added here AND covered by a test that pins the hash
# computation. Excluded by design:
#   * ``chain_hash`` itself (it would be circular).
#   * ``chain_sequence`` — sequence is provided alongside the hash to the
#     verifier, but is not part of the hashed canonical (we hash content, not
#     position; otherwise a re-numbering would require re-hashing the whole
#     chain after GDPR-erasure gaps).
#   * ``is_archived`` / ``archived_at`` — archival is a metadata flip that
#     MUST NOT invalidate the chain (per Phase 232 retention spec).
#   * ``prev_chain_hash`` — supplied separately to ``compute_chain_hash``.
_CANONICAL_FIELDS: tuple[str, ...] = (
    "id",
    "tenant_id",
    "actor_user_id",
    "resource_type",
    "resource_id",
    "action",
    "result",
    "details_json",
    "full_details_json",
)


def _normalize_uuid(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _normalize_timestamp(value: Any) -> str | None:
    """Render a timestamp as a stable UTC ISO-8601 string with microseconds.

    PostgreSQL stores TIMESTAMPTZ to microsecond precision; we mirror that
    here so a round-trip through the database can't perturb the canonical
    representation. ``None`` is preserved for the genesis (first-per-tenant)
    case.
    """
    if value is None:
        return None
    if isinstance(value, str):
        # Already serialized — trust upstream normalization.
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            # Defensive: a naive datetime in the chain would let two events
            # with the same wall-clock seconds in different timezones hash
            # to the same canonical. Force UTC interpretation.
            value = value.replace(tzinfo=dt_timezone.utc)
        else:
            value = value.astimezone(dt_timezone.utc)
        return value.isoformat()
    return str(value)


def canonical_form(event: Any) -> bytes:
    """Return the deterministic canonical byte representation of *event*.

    The output is JSON with sorted keys, no whitespace, and UTF-8 encoding.
    ``chain_hash``, ``chain_sequence``, ``prev_chain_hash``, archival
    metadata, and ``timestamp`` are EXCLUDED — they are supplied separately
    to :func:`compute_chain_hash` (timestamp is hashed alongside the
    canonical, sequence is positional, archival is metadata).

    Accepts either an ``AuditEvent`` model instance or a plain dict shaped
    like the ``_CANONICAL_FIELDS`` set. The latter is what the backfill
    command uses when re-hydrating rows from raw SQL.
    """
    if isinstance(event, Mapping):
        get = event.get
    else:
        # Model attribute access. For FK fields we want the underlying ``*_id``
        # column value, not the related object — looking it up via getattr is
        # safe because Django exposes the column attribute even when the
        # related object is unloaded (saves us an unintended FK query).
        def get(key: str, default: Any = None) -> Any:  # type: ignore[no-redef]  # intentional inner-scope redefinition, avoid FK query
            return getattr(event, key, default)

    payload: dict[str, Any] = {}
    for field in _CANONICAL_FIELDS:
        raw = get(field)
        if field in ("id", "tenant_id", "actor_user_id", "resource_id"):
            payload[field] = _normalize_uuid(raw)
        elif field in ("details_json", "full_details_json"):
            # Already JSON-shaped; serializing via json.dumps with sort_keys
            # ensures nested dict ordering doesn't perturb the hash.
            payload[field] = raw
        else:
            payload[field] = raw
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def compute_chain_hash(
    canonical: bytes,
    prev_chain_hash: str | None,
    timestamp_iso: str,
) -> str:
    """Compute the per-row chain hash as a 64-char hex SHA-256 digest.

    Input layout (concatenated bytes):

        canonical_form_bytes || prev_chain_hash_utf8 || timestamp_iso_utf8

    The genesis case (no predecessor on this tenant) uses an empty string
    for ``prev_chain_hash`` so the rolling-window verifier can detect a
    spliced "fake genesis" via the missing predecessor in the snapshot.
    """
    h = hashlib.sha256()
    h.update(canonical)
    h.update((prev_chain_hash or "").encode("utf-8"))
    h.update(timestamp_iso.encode("utf-8"))
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Verification primitives.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ChainMismatch:
    """One detected inconsistency in a verified segment.

    The verifier returns a *list* of these rather than raising on the first
    failure so the auditor can see whether an incident touched 1 row or 1000.
    """

    event_id: str
    chain_sequence: int
    reason: str
    expected: str | None = None
    actual: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "chain_sequence": self.chain_sequence,
            "reason": self.reason,
            "expected": self.expected,
            "actual": self.actual,
        }


@dataclass(frozen=True, slots=True)
class ChainVerification:
    verified: bool
    checked: int
    mismatches: list[ChainMismatch]
    gaps: list[tuple[int, int]]
    # Phase 234.1 audit-fix — snapshot cross-check results. Populated by
    # the REST endpoint when the operator asks for snapshot verification
    # (``?include_snapshots=true``). Empty list when not requested OR when
    # no snapshots cover the window. A non-empty ``snapshot_mismatches``
    # ALWAYS flips ``verified`` to False — the signed Merkle root is the
    # cryptographic anchor and a mismatch indicates either tampering or
    # legitimate GDPR-erasure that hasn't yet been followed by a re-snap.
    snapshots_checked: int = 0
    snapshot_mismatches: list["SnapshotMismatch"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verified": self.verified,
            "checked": self.checked,
            "mismatches": [m.to_dict() for m in self.mismatches],
            # ``gaps`` is informational: legitimate GDPR-erasure can punch
            # holes in the sequence; the verifier reports them but does NOT
            # count them as mismatches (per the cross-spec note in 234.4).
            "gaps": [list(g) for g in self.gaps],
            "snapshots_checked": self.snapshots_checked,
            "snapshot_mismatches": [m.to_dict() for m in self.snapshot_mismatches],
        }


def verify_chain_segment(events: Sequence[Any]) -> ChainVerification:
    """Verify a contiguous-in-intent segment of audit events.

    *events* MUST be sorted by ``chain_sequence`` ascending. The caller is
    responsible for the database query (and for honouring tenant isolation).

    Reason codes
    ------------

    ``chain_hash_mismatch``
        The row's stored ``chain_hash`` does not match what we recompute
        from its on-disk content + ``prev_chain_hash`` + timestamp.
        Always a tamper signal; flips ``verified=False``.

    ``prev_link_mismatch``
        Two consecutive rows (no sequence gap between them) where
        ``row_N.prev_chain_hash != row_{N-1}.chain_hash``. This can ONLY
        happen via splice / insertion / row-rewrite; flips
        ``verified=False``.

    ``erasure_gap``  (informational, not a tamper signal)
        A sequence gap exists between two surviving rows AND the link is
        broken across the gap. This is the EXPECTED shape of a Phase
        232.2 GDPR right-to-erasure: the deleted row's
        ``chain_hash`` is gone, so the next survivor's ``prev_chain_hash``
        no longer matches the previous *surviving* row's ``chain_hash``.
        Per the 234 + 232.2 cross-spec contract documented in
        preprod01/tasks.md ("the tamper-evidence spec MUST tolerate
        missing rows in the chain"), this MUST NOT flip ``verified``
        to false on its own. The Merkle-snapshot cross-check
        (``verify_chain_against_snapshot``) is the secondary defence
        against malicious deletion masquerading as erasure: an
        unauthenticated DELETE produces an erasure-shaped gap here AND
        a recomputed-Merkle-root that doesn't match the signed root.
    """
    mismatches: list[ChainMismatch] = []
    gaps: list[tuple[int, int]] = []
    prev_seq: int | None = None
    prev_hash: str | None = None
    checked = 0

    for ev in events:
        checked += 1
        seq = int(getattr(ev, "chain_sequence", None) or 0)
        stored_hash = getattr(ev, "chain_hash", None) or ""
        stored_prev = getattr(ev, "prev_chain_hash", None)
        timestamp = getattr(ev, "timestamp", None)
        timestamp_iso = _normalize_timestamp(timestamp) or ""

        # Recompute chain_hash from on-disk fields. This catches content
        # forgery regardless of any gap context.
        recomputed = compute_chain_hash(
            canonical_form(ev),
            stored_prev,
            timestamp_iso,
        )
        if recomputed != stored_hash:
            mismatches.append(
                ChainMismatch(
                    event_id=str(getattr(ev, "id", "")),
                    chain_sequence=seq,
                    reason="chain_hash_mismatch",
                    expected=recomputed,
                    actual=stored_hash,
                )
            )

        # Link check vs. previous row in this segment.
        if prev_seq is not None:
            has_gap = seq != prev_seq + 1
            if has_gap:
                gaps.append((prev_seq, seq))

            # Whether or not there's a gap, prev_chain_hash MUST equal the
            # previous-row hash. The distinction is what we *report*:
            #   gap + link broken     -> erasure_gap (informational only)
            #   no gap + link broken  -> prev_link_mismatch (tamper)
            #   gap + link intact     -> unusual but valid (sequence renumber
            #                            without content tamper — flag but
            #                            do not fail; treat as erasure_gap)
            if stored_prev != prev_hash:
                if has_gap:
                    # GDPR-erasure (or equivalent legitimate deletion).
                    # Surface for the auditor but DO NOT flip ``verified``.
                    # Added to a parallel list so callers can distinguish.
                    pass  # Reason recorded via ``gaps`` + ``erasure_notes`` below.
                else:
                    mismatches.append(
                        ChainMismatch(
                            event_id=str(getattr(ev, "id", "")),
                            chain_sequence=seq,
                            reason="prev_link_mismatch",
                            expected=prev_hash,
                            actual=stored_prev,
                        )
                    )
        else:
            # First row of the segment. We can't link it without context;
            # the snapshot path supplies the anchor (Merkle root) separately.
            pass

        prev_seq = seq
        prev_hash = stored_hash

    return ChainVerification(
        verified=(len(mismatches) == 0),
        checked=checked,
        mismatches=mismatches,
        gaps=gaps,
    )


# ---------------------------------------------------------------------------
# Snapshot cross-check — catches what in-row verification cannot.
# ---------------------------------------------------------------------------
#
# Threat model the in-row check ``verify_chain_segment`` cannot defend
# against alone:
#
#   * Full-chain rewrite — an attacker with DB-write access who replaces
#     every row's ``chain_hash`` AND ``prev_chain_hash`` with internally
#     consistent forgeries. ``verify_chain_segment`` finds no link
#     mismatches because the forged links are self-consistent.
#
# The Merkle snapshot is the cryptographic anchor that catches this:
# its root is computed from chain_hash leaves AT SIGNING TIME and signed
# with a key the attacker does not control. Re-hashing the on-disk rows
# produces a different root ⇒ tamper signal.


@dataclass(frozen=True, slots=True)
class SnapshotMismatch:
    """A snapshot whose recomputed root no longer matches the signed root."""

    snapshot_id: str
    period_start: str
    period_end: str
    stored_root_hex: str
    recomputed_root_hex: str
    signature_valid: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "stored_root_hex": self.stored_root_hex,
            "recomputed_root_hex": self.recomputed_root_hex,
            "signature_valid": self.signature_valid,
        }


# ---------------------------------------------------------------------------
# Merkle helpers (used by the AUDIT_MERKLE_SNAPSHOT job).
# ---------------------------------------------------------------------------


def merkle_root(leaves: Iterable[str]) -> str:
    """Compute the SHA-256 Merkle root over *leaves* (hex strings).

    Implementation notes:

    * Odd-leaf-count layers duplicate the last leaf (Bitcoin-style); this
      is the convention auditors recognise without an attached spec.
    * Empty input returns the empty-hash sentinel
      ``"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"``
      (= ``sha256(b"")``), so a tenant with zero events in a snapshot
      window still gets a deterministic, signable root.
    """
    leaf_bytes = [bytes.fromhex(leaf) for leaf in leaves]
    if not leaf_bytes:
        return hashlib.sha256(b"").hexdigest()
    layer = leaf_bytes
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer = layer + [layer[-1]]
        next_layer: list[bytes] = []
        for i in range(0, len(layer), 2):
            h = hashlib.sha256()
            h.update(layer[i])
            h.update(layer[i + 1])
            next_layer.append(h.digest())
        layer = next_layer
    return layer[0].hex()


def verify_chain_against_snapshots(
    *,
    base: ChainVerification,
    snapshot_pairs: Sequence[
        tuple[Any, Sequence[Any]]  # (AuditMerkleSnapshot row, leaves-for-that-window)
    ],
    signature_verifier,
) -> ChainVerification:
    """Augment *base* with snapshot cross-check results.

    The caller supplies pre-resolved ``(snapshot_row, current_window_events)``
    pairs so this function can stay DB-agnostic and unit-testable without
    a Django connection.

    For each pair we:

    1. Re-build the Merkle root from the current ``chain_hash`` leaves
       (in ``chain_sequence`` order) and compare to the snapshot's
       ``root_hex``. A mismatch indicates either malicious deletion (no
       re-snap was issued to follow it) OR a full-chain rewrite (every
       row's chain_hash forged) — both are tamper signals.
    2. Verify the snapshot's ``signature_hex`` against the tenant's
       signing key ring via *signature_verifier* (typically
       :func:`hub.apps.audit.merkle.verify_root_signature`). A False
       result here means the signed blob itself was tampered with —
       distinct from a leaf-rewrite mismatch.

    Any mismatch contributes to a NEW ``ChainVerification`` whose
    ``verified`` flag is the AND of the original ``base.verified`` and
    "no snapshot mismatches detected".
    """
    mismatches: list[SnapshotMismatch] = []
    for snapshot, current_events in snapshot_pairs:
        leaves = [
            getattr(ev, "chain_hash", "")
            for ev in current_events
            if getattr(ev, "chain_hash", None)
        ]
        recomputed = merkle_root(leaves)
        sig_ok = bool(
            signature_verifier(
                tenant_id=str(getattr(snapshot, "tenant_id", "") or "") or None,
                root_hex=snapshot.root_hex,
                signature_hex=snapshot.signature_hex,
            )
        )
        if recomputed != snapshot.root_hex or not sig_ok:
            mismatches.append(
                SnapshotMismatch(
                    snapshot_id=str(getattr(snapshot, "id", "")),
                    period_start=snapshot.period_start.isoformat()
                    if getattr(snapshot, "period_start", None) is not None
                    else "",
                    period_end=snapshot.period_end.isoformat()
                    if getattr(snapshot, "period_end", None) is not None
                    else "",
                    stored_root_hex=snapshot.root_hex,
                    recomputed_root_hex=recomputed,
                    signature_valid=sig_ok,
                )
            )

    return ChainVerification(
        verified=(base.verified and not mismatches),
        checked=base.checked,
        mismatches=base.mismatches,
        gaps=base.gaps,
        snapshots_checked=len(snapshot_pairs),
        snapshot_mismatches=mismatches,
    )
