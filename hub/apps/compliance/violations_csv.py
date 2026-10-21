"""Streaming CSV for compliance violation rows (Phase 231.8)."""

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING, Any

from hub.apps.core.utils.output_safety import csv_formula_safe

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator


def iter_violation_csv_bytes(violations: Iterable[dict[str, Any]] | None) -> Iterator[bytes]:
    """Yield UTF-8 encoded CSV chunks (header row + one data row per violation).

    W8.3 — the ``column`` cell carries dataset column names (strings
    that originated in a user-uploaded dataset), so every string cell
    is neutralised against CSV formula injection (CWE-1236);
    ``risk_score`` stays numeric.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["column", "pii_type", "risk_score", "severity"])
    yield buf.getvalue().encode("utf-8")
    buf.seek(0)
    buf.truncate(0)
    for v in violations or []:
        writer.writerow(
            [
                csv_formula_safe(v.get("column") or ""),
                csv_formula_safe(v.get("pii_type") or ""),
                "" if v.get("risk_score") is None else v.get("risk_score"),
                csv_formula_safe(v.get("severity") or ""),
            ]
        )
        yield buf.getvalue().encode("utf-8")
        buf.seek(0)
        buf.truncate(0)
