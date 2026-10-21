"""Output-safety primitives (W8.3).

Defence-in-depth helpers for application-generated downloads:
- CSV formula-injection neutralisation (CWE-1236): spreadsheet apps
  evaluate cells whose first character is ``= + - @ <tab> <CR>`` as
  formulas; a value exported verbatim from user-controlled data
  (asset names, column names, emails) can execute commands when the
  CSV is opened.
- HTML escaping for generated documents (the RoPA PDF) lives at the
  call sites via :func:`html.escape` — the standard-library encoder is
  the canonical implementation, no wrapper needed.

Scope note (recorded decision): raw-data exports (dataset downloads,
warehouse staging files) are deliberately NOT routed through these
helpers — those bytes are the customer's data and mutating them would
corrupt fidelity. These helpers are for application-generated *report*
cells, where each cell is a displayed attribute and the consumer is a
spreadsheet application.
"""

from __future__ import annotations

from typing import Any

# First characters spreadsheet applications treat as formula starts
# (OWASP CSV Injection / CWE-1236). Tab and carriage return are
# included per OWASP: Excel/LibreOffice also interpret them as formula
# starters in imported cells.
CSV_FORMULA_TRIGGERS: tuple[str, ...] = ("=", "+", "-", "@", "\t", "\r")

# Prefix that forces spreadsheet apps to treat the cell as text.
CSV_FORMULA_GUARD = "'"


def csv_formula_safe(value: Any) -> Any:
    """Return *value* neutralised against CSV formula injection.

    Strings whose first character is a formula trigger are prefixed
    with a single quote (the spreadsheet text marker), so opening the
    CSV in Excel / LibreOffice / Sheets can never execute them.
    Numbers, booleans, ``None`` and other non-string values pass
    through untouched — numeric columns must stay numeric.
    """
    if isinstance(value, str) and value.startswith(CSV_FORMULA_TRIGGERS):
        return CSV_FORMULA_GUARD + value
    return value
