#!/usr/bin/env python3
"""
Phase 240.5.F.4 — AST lint rule banning raw redacted-key payloads in
DQ Hub-side ``logger.*(..., extra={...})`` calls.

Why an AST check (and not just ruff): ``ruff`` is great at static
shape checks (line length / import order / unused vars) but can't
match the SEMANTIC pattern we need here:

    "any ``logger.*`` call inside ``hub/apps/dq/`` whose ``extra=``
     argument is a dict literal AND that dict's keys include any of
     ``_REDACTED_KEYS``"

That requires walking the AST, identifying ``logger`` attribute calls
(``logger.info / .debug / .warning / .error / .exception / .critical``),
inspecting the ``extra=`` keyword arg as a literal dict, and matching
its keys.  Implemented here as a small pre-commit-friendly script.

Usage::

    python scripts/check_dq_log_extras.py [path...]

Exit code:
* 0 — no offending call sites found.
* 1 — at least one offence; offences are printed to stdout in
       ``file:line: <reason>`` format so editors / CI annotations
       can jump-to-line.

The check ALWAYS allows the safe pattern::

    logger.info("evt", extra=_redact({"details_json": dq_run.details_json}))

It rejects only the unwrapped form::

    logger.info("evt", extra={"details_json": dq_run.details_json})

When run with no arguments, scans the canonical DQ Hub-side file
list per Phase 240.5.F.1:

* ``hub/apps/dq/views.py``
* ``hub/apps/dq/services.py``
* ``hub/apps/dq/service_client.py``
* ``hub/apps/dq/alerting.py``
* ``hub/apps/dq/tasks.py``

Plus the alert-delivery client subtree (extension scope identified
during 240.5.F audit-pass — these files emit ``logger.*(...,
extra={...})`` from the alert delivery hot path orchestrated by
``alerting.py``, so a leak there is morally identical to a leak in
``alerting.py``):

* ``hub/apps/dq/clients/base.py``
* ``hub/apps/dq/clients/email_client.py``
* ``hub/apps/dq/clients/webhook_client.py``
* ``hub/apps/dq/clients/slack_client.py`` (covered if it exists)
* ``hub/apps/dq/clients/pagerduty_client.py`` (covered if it exists)

Run from project root.

Pre-commit + CI integration:
* ``.pre-commit-config.yaml`` adds a ``local`` hook entry pointing here.
* ``.github/workflows/ci.yml`` mirrors the same check (so a pre-commit
  bypass via ``--no-verify`` is still caught at PR review time).
"""
from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


# ---------------------------------------------------------------------------
# Source of truth: the keys we forbid as raw extras.
# Mirror of ``hub.apps.dq.log_helpers._REDACTED_KEYS`` — intentionally
# duplicated here so this script imports nothing from the Hub
# package (keeps the lint rule runnable in pre-commit's lean
# environment without django-stubs etc.).  The parity with the
# Python module is pinned by
# ``hub/apps/dq/tests/test_log_helpers.py::TestLintRuleParity``.
# ---------------------------------------------------------------------------

_FORBIDDEN_KEYS: frozenset[str] = frozenset({
    "row_samples",
    "sample_value",
    "sample_data_json",
    "file_content",
    "body",
    "raw_data",
    "data",
    "details_json",
})

# Names of attributes on `logger` that the rule treats as "log call".
_LOGGER_METHODS: frozenset[str] = frozenset({
    "debug", "info", "warning", "warn", "error",
    "exception", "critical", "fatal", "log",
})

# Default scan paths when invoked with no args.
#
# Layer 1 — the canonical 5 files per Phase 240.5.F.1.
# Layer 2 — the alert-delivery client subtree (extension scope from
#           240.5.F audit pass; same risk surface as ``alerting.py``).
# Files are skipped silently if they don't exist (so a future client
# being deleted doesn't break the lint), but the canonical 5 will
# always be present in any working tree.
_DEFAULT_PATHS: tuple[str, ...] = (
    # Layer 1 — canonical 240.5.F.1 audit list.
    "hub/apps/dq/views.py",
    "hub/apps/dq/services.py",
    "hub/apps/dq/service_client.py",
    "hub/apps/dq/alerting.py",
    "hub/apps/dq/tasks.py",
    # Layer 2 — alert-delivery client subtree (240.5.F audit-pass
    # extension).  Each of these files is invoked from
    # ``alerting.py``'s delivery loop and emits ``logger.*(...,
    # extra={...})`` in failure / retry / circuit-breaker paths;
    # a forbidden key in any of their dicts has the same blast
    # radius as a forbidden key in ``alerting.py`` itself.
    "hub/apps/dq/clients/base.py",
    "hub/apps/dq/clients/email_client.py",
    "hub/apps/dq/clients/webhook_client.py",
    "hub/apps/dq/clients/slack_client.py",
    "hub/apps/dq/clients/pagerduty_client.py",
    # Phase 275.A.5 — warehouse connectivity log helpers.
    # All connector files emit logger.*(..., extra={...}) with
    # potentially sensitive credential/config data that must be
    # redacted via warehouses/log_helpers.redact_extra().
    "hub/apps/warehouses/connectors.py",
    "hub/apps/warehouses/connectors/snowflake.py",
    "hub/apps/warehouses/connectors/bigquery.py",
    "hub/apps/warehouses/connectors/databricks.py",
    "hub/apps/warehouses/connectors/athena.py",
    "hub/apps/warehouses/schema_drift.py",
    "hub/apps/warehouses/cache.py",
)


@dataclass
class Offence:
    file: str
    line: int
    col: int
    method: str
    forbidden_keys: tuple[str, ...]

    def render(self) -> str:
        keys = ", ".join(self.forbidden_keys)
        return (
            f"{self.file}:{self.line}:{self.col}: "
            f"E[DQ-PII-001] logger.{self.method}(..., extra={{...}}) "
            f"contains forbidden key(s) without _redact() wrap: {keys}.  "
            f"Wrap the dict in ``_redact()`` from "
            f"``hub.apps.dq.log_helpers`` before emit."
        )


def _is_logger_call(call: ast.Call) -> str | None:
    """Return the method name (e.g. 'info') if the call looks like
    ``logger.<method>(...)``, else None."""
    func = call.func
    if not isinstance(func, ast.Attribute):
        return None
    if func.attr not in _LOGGER_METHODS:
        return None
    # Match ``logger.<method>`` or ``self.logger.<method>`` or
    # ``cls.logger.<method>``.  Loose: any ``Name`` ending in 'logger'
    # OR any ``Attribute`` whose attr is 'logger'.
    inner = func.value
    if isinstance(inner, ast.Name) and inner.id.endswith("logger"):
        return func.attr
    if isinstance(inner, ast.Attribute) and inner.attr == "logger":
        return func.attr
    return None


def _extra_is_redacted(extra_node: ast.AST) -> bool:
    """True iff ``extra=`` is a call to ``_redact(...)`` (any module-
    qualified or bare form).  Examples that count as redacted:

    * ``extra=_redact({...})``
    * ``extra=log_helpers._redact({...})``
    * ``extra=hub.apps.dq.log_helpers._redact({...})``
    """
    if not isinstance(extra_node, ast.Call):
        return False
    func = extra_node.func
    if isinstance(func, ast.Name) and func.id == "_redact":
        return True
    if isinstance(func, ast.Attribute) and func.attr == "_redact":
        return True
    return False


def _dict_has_forbidden_key(node: ast.AST) -> tuple[str, ...]:
    """Return a sorted tuple of forbidden keys present in a dict literal,
    or empty tuple if not a literal or no forbidden keys."""
    if not isinstance(node, ast.Dict):
        return ()
    found: list[str] = []
    for k in node.keys:
        # Only literal-string keys are checkable; dynamic keys like
        # ``"d_" + suffix`` are ignored (we can't statically resolve
        # them, and forbidding them outright would be too noisy).
        if isinstance(k, ast.Constant) and isinstance(k.value, str):
            if k.value in _FORBIDDEN_KEYS:
                found.append(k.value)
    return tuple(sorted(found))


def scan_file(path: Path) -> List[Offence]:
    """Walk ``path``'s AST, return all unwrapped logger calls whose
    ``extra=`` dict literal contains a forbidden key."""
    src = path.read_text()
    tree = ast.parse(src, filename=str(path))
    offences: list[Offence] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        method = _is_logger_call(node)
        if method is None:
            continue
        # Find ``extra=...`` keyword arg.
        for kw in node.keywords:
            if kw.arg != "extra":
                continue
            value = kw.value
            if _extra_is_redacted(value):
                continue
            keys = _dict_has_forbidden_key(value)
            if keys:
                offences.append(Offence(
                    file=str(path),
                    line=node.lineno,
                    col=node.col_offset,
                    method=method,
                    forbidden_keys=keys,
                ))
    return offences


def main(argv: list[str]) -> int:
    paths: Iterable[str] = argv[1:] or _DEFAULT_PATHS
    all_offences: list[Offence] = []
    for raw in paths:
        p = Path(raw)
        if not p.exists():
            print(f"WARN: skipping {p} (not found)", file=sys.stderr)
            continue
        if p.is_dir():
            for sub in p.rglob("*.py"):
                all_offences.extend(scan_file(sub))
        else:
            all_offences.extend(scan_file(p))

    if all_offences:
        print(
            f"❌ Phase 240.5.F.4 — found {len(all_offences)} unwrapped "
            f"logger ``extra=`` payload(s) carrying forbidden keys:",
            file=sys.stderr,
        )
        for off in all_offences:
            print(off.render())
        return 1

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv))
