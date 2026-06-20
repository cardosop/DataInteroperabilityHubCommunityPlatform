"""Streaming CSV for compliance violation rows (Phase 231.8)."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Iterator
from typing import Any


def iter_violation_csv_bytes(violations: Iterable[dict[str, Any]] | None) -> Iterator[bytes]:
    """Yield UTF-8 encoded CSV chunks (header row + one data row per violation)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["column", "pii_type", "risk_score", "severity"])
    yield buf.getvalue().encode("utf-8")
    buf.seek(0)
    buf.truncate(0)
    for v in violations or []:
        writer.writerow(
            [
                v.get("column") or "",
                v.get("pii_type") or "",
                "" if v.get("risk_score") is None else v.get("risk_score"),
                v.get("severity") or "",
            ]
        )
        yield buf.getvalue().encode("utf-8")
        buf.seek(0)
        buf.truncate(0)
