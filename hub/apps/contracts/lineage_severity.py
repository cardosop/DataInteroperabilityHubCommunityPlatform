"""
Phase 228.F3.7 — Severity classifier (REQ-LIN-F3-004).

Pure-function classifier that takes a lineage diff + a contract
diff and returns the severity of the change for downstream
notification routing.

The classifier is **deterministic and side-effect free** — same
input always produces the same output, no DB / Redis / clock /
random.  Side-effecting work (looking up subscribers, walking
downstream edges) belongs in the dispatcher (REQ-LIN-F3-005),
NOT here.

Mapping (per the spec):

* ``CRITICAL`` — breaking schema change downstream: a field that
  another contract depends on was removed.
* ``HIGH`` — transformation_ref change OR a derivation edge added
  / removed.
* ``MEDIUM`` — cosmetic edit: only ``job_ref`` or other metadata
  changed.
* ``LOW`` — reference-only edges added / removed, or no change.

When multiple categories apply, the highest wins
(``CRITICAL > HIGH > MEDIUM > LOW``) — the classifier returns the
worst-case severity so subscribers gated at any threshold see the
notification once.

Why dataclasses for the inputs?  The dispatcher computes diffs by
walking the LineageEdge index + the ``hub_contract_json`` JSON.
Dataclasses give us a typed boundary between that computation and
the classifier so the classifier stays pure-function testable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple


class Severity(str, Enum):
    """Severity tiers for lineage-impact notifications."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

    def numeric(self) -> int:
        """Numeric ordering — higher means worse.

        Used by the dispatcher's severity gate
        (``classify(...).numeric() >= subscription.severity_threshold.numeric()``).
        """
        return _SEVERITY_RANK[self]


_SEVERITY_RANK: Dict[Severity, int] = {
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


@dataclass(frozen=True)
class LineageEdgeDelta:
    """An edge that exists in both before and after but with
    field-level changes (e.g. transformation_ref or job_ref edited)."""

    before: dict
    after: dict
    fields_changed: List[str]


@dataclass(frozen=True)
class LineageDiff:
    """The result of diffing two lineage states.

    Attributes
    ----------
    added
        Edges present only in the new state.
    removed
        Edges present only in the old state.
    modified
        Edges present in both with at least one field changed.
    downstream_field_dependencies
        Map ``(model, field) -> [contract_id_of_dependent, ...]``
        — populated by the dispatcher when it walks the downstream
        ``LineageEdge`` graph.  Used to decide whether a removed
        field is a CRITICAL break.
    """

    added: List[dict] = field(default_factory=list)
    removed: List[dict] = field(default_factory=list)
    modified: List[LineageEdgeDelta] = field(default_factory=list)
    downstream_field_dependencies: Dict[Tuple[str, str], List[str]] = field(
        default_factory=dict,
    )


@dataclass(frozen=True)
class ContractDiff:
    """Subset of the contract's schema diff relevant to severity.

    Attributes
    ----------
    removed_fields
        ``[(model, field), ...]`` — fields present in the old
        ``hub_contract_json`` but not the new one.
    added_fields
        ``[(model, field), ...]`` — newly declared fields.
    modified_fields
        ``[(model, field), ...]`` — fields where ``data_type``
        changed.
    """

    removed_fields: List[Tuple[str, str]] = field(default_factory=list)
    added_fields: List[Tuple[str, str]] = field(default_factory=list)
    modified_fields: List[Tuple[str, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------


def classify(
    diff: LineageDiff,
    contract_diff: ContractDiff,
) -> Severity:
    """Return the severity tier for a lineage / contract diff.

    See module docstring for the mapping rules.  The function is
    pure — no I/O, no clock, no randomness — so callers can rely
    on memoised results across retries.

    Phase 228.F3.MetaDoD audit (REQ-LIN-F3-004 spec scenario
    "Removed derivation edge classified CRITICAL") — a removed
    derivation edge IS a breaking change in itself: the downstream
    contract was deriving values from this edge and now isn't, so
    consumers see different data even if no field was removed.
    Classified CRITICAL.  Added derivation edges remain HIGH (new
    derivation is interesting but not breaking).
    """
    # CRITICAL — (a) removed field a downstream contract depends on,
    # OR (b) removed derivation edge.
    if _is_breaking_field_removal(contract_diff, diff):
        return Severity.CRITICAL
    if _has_derivation_edge_removed(diff):
        return Severity.CRITICAL

    # HIGH — transformation_ref change OR new derivation edge.
    if _has_transformation_change(diff) or _has_derivation_edge_added(diff):
        return Severity.HIGH

    # MEDIUM — cosmetic field-level edge edit (job_ref etc).
    if _has_only_metadata_changes(diff):
        return Severity.MEDIUM

    # LOW — reference-only churn (or no change).
    return Severity.LOW


def _is_breaking_field_removal(
    contract_diff: ContractDiff, diff: LineageDiff,
) -> bool:
    """A removed field counts as CRITICAL only when at least one
    downstream contract depends on it (i.e. the field shows up in
    ``downstream_field_dependencies``)."""
    if not contract_diff.removed_fields:
        return False
    for removed in contract_diff.removed_fields:
        dependents = diff.downstream_field_dependencies.get(removed, [])
        if dependents:
            return True
    return False


def _has_transformation_change(diff: LineageDiff) -> bool:
    """True if any modified edge changed its ``transformation_ref``."""
    return any(
        "transformation_ref" in delta.fields_changed
        for delta in diff.modified
    )


_DERIVATION_TYPES = {"derivation", "transformation"}


def _has_derivation_edge_added(diff: LineageDiff) -> bool:
    """True if any newly-added edge has ``edge_type='derivation'``
    (or ``transformation``, treated as a synonym for the F3 v1 mapping).

    Added derivation is HIGH per the spec mapping — interesting but
    not breaking.
    """
    return any(
        edge.get("edge_type") in _DERIVATION_TYPES for edge in diff.added
    )


def _has_derivation_edge_removed(diff: LineageDiff) -> bool:
    """True if any removed edge has ``edge_type='derivation'``.

    Removed derivation is CRITICAL per REQ-LIN-F3-004 spec scenario
    "Removed derivation edge classified CRITICAL" — the downstream
    contract was deriving values from this edge and now isn't, so
    consumers see different data even if no field was removed.
    """
    return any(
        edge.get("edge_type") in _DERIVATION_TYPES for edge in diff.removed
    )


def _has_only_metadata_changes(diff: LineageDiff) -> bool:
    """True if at least one modified edge has fields_changed but
    none of those fields are transformation_ref (those are HIGH).

    Examples: job_ref edits, edge metadata cleanup.  The classifier
    treats these as cosmetic.
    """
    for delta in diff.modified:
        if delta.fields_changed and (
            "transformation_ref" not in delta.fields_changed
        ):
            return True
    return False


__all__ = [
    "ContractDiff",
    "LineageDiff",
    "LineageEdgeDelta",
    "Severity",
    "classify",
]
