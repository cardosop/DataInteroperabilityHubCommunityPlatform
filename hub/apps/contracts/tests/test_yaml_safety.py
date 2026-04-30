"""
Phase 227 Wave 1 (227.L8.4) — YAML deserialisation safety regression.

Pins the invariant that **every** YAML-parsing call site in the
contracts subsystem uses ``yaml.safe_load`` (or equivalent) and refuses
to deserialise Python-object tags (e.g.
``!!python/object/apply:os.system``).

The unsafe ``yaml.load`` constructor would happily instantiate Python
callables from YAML, giving an attacker remote-code-execution by
uploading a malicious contract. This test guards against:

1. **Source-level regressions** — a code-search over the contracts
   package fails the test if any caller uses ``yaml.load(`` without
   the ``Loader=yaml.SafeLoader`` argument.
2. **Behavioural regressions** — a malicious payload submitted via the
   contract-create API is rejected (either by ``yaml.safe_load`` raising
   ``ConstructorError`` or by downstream parse-error handling). No
   ``Contract`` row is persisted.

The test is deliberately a regression suite — it would FAIL if a future
change reintroduces ``yaml.load`` somewhere under
``hub.apps.contracts``.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

import pytest
import yaml


CONTRACTS_PACKAGE = Path(__file__).resolve().parent.parent
# Files that legitimately mention ``yaml.load`` in narrative
# (docstrings, comments) without invoking it. Add new exemptions
# explicitly with the reason in this list.
ALLOWLIST: tuple[str, ...] = (
    # The test file itself naturally references the unsafe call.
    "tests/test_yaml_safety.py",
)


def _scan_for_unsafe_yaml_load() -> List[tuple[Path, int, str]]:
    """Return every line in ``hub.apps.contracts`` that calls
    ``yaml.load(`` *without* ``Loader=yaml.SafeLoader``.

    Skips comments + docstrings: a line that appears under a triple
    quote or inside a ``#`` comment is allowed (used for narrative).
    """
    unsafe = re.compile(r"\byaml\.load\s*\(")
    safe_loader = re.compile(r"Loader\s*=\s*yaml\.SafeLoader")
    findings: List[tuple[Path, int, str]] = []
    for py in CONTRACTS_PACKAGE.rglob("*.py"):
        rel = py.relative_to(CONTRACTS_PACKAGE).as_posix()
        if any(rel.endswith(skip) for skip in ALLOWLIST):
            continue
        try:
            text = py.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_no, raw_line in enumerate(text.splitlines(), start=1):
            stripped = raw_line.lstrip()
            if stripped.startswith("#"):
                continue
            if not unsafe.search(raw_line):
                continue
            # Allow if the same line specifies the safe loader
            # explicitly (defence-in-depth).
            if safe_loader.search(raw_line):
                continue
            findings.append((py, line_no, raw_line.rstrip()))
    return findings


def test_no_unsafe_yaml_load_in_contracts_package():
    """Source-level regression — every YAML load in the contracts
    package MUST use ``yaml.safe_load`` (or an explicit
    ``Loader=yaml.SafeLoader`` argument).
    """
    findings = _scan_for_unsafe_yaml_load()
    assert findings == [], (
        "Unsafe ``yaml.load`` call detected (RCE risk):\n"
        + "\n".join(f"  {p}:{n}: {line}" for (p, n, line) in findings)
    )


# ---------------------------------------------------------------------------
# Behavioural regression — yaml.safe_load rejects Python-object tags
# ---------------------------------------------------------------------------


_MALICIOUS_PAYLOADS: tuple[tuple[str, str], ...] = (
    # The canonical RCE exploit — Python's deprecated yaml.load would
    # call ``os.system('echo pwned')``. ``safe_load`` raises
    # ``ConstructorError``.
    (
        "python_object_apply_os_system",
        "!!python/object/apply:os.system ['echo pwned']",
    ),
    # Older Python tags (yaml ≤3.13 vintage) the safe loader also rejects.
    (
        "python_object_new_subprocess",
        "!!python/object/new:subprocess.Popen [['echo','pwned']]",
    ),
    # Direct module reference.
    (
        "python_module_os",
        "!!python/module:os",
    ),
    # ``!!python/name:`` was a partial bypass in some yaml versions.
    (
        "python_name_os_system",
        "!!python/name:os.system",
    ),
)


@pytest.mark.parametrize(
    "label, body",
    _MALICIOUS_PAYLOADS,
    ids=[label for label, _ in _MALICIOUS_PAYLOADS],
)
def test_safe_load_rejects_python_object_tags(label, body):
    """Direct invocation: ``yaml.safe_load`` MUST raise on every Python-
    object tag — proving the constructor is not registered in the safe
    loader's tag map. Using ``yaml.load(...)`` (the unsafe constructor)
    on the same body would happily execute the call.
    """
    with pytest.raises(yaml.YAMLError):
        yaml.safe_load(body)


@pytest.mark.parametrize(
    "label, body",
    _MALICIOUS_PAYLOADS,
    ids=[label for label, _ in _MALICIOUS_PAYLOADS],
)
def test_create_contract_rejects_python_object_yaml(label, body):
    """End-to-end: posting a malicious YAML contract to the create
    endpoint MUST result in a 4xx (parse / validation rejection) and
    MUST NOT persist a ``Contract`` row. Anything 2xx here would mean
    the request reached the DB after deserialising attacker-controlled
    Python.
    """
    from rest_framework.test import APIClient

    from hub.apps.contracts.models import Contract
    from hub.apps.contracts.tests.test_base import (
        ContractsAPITransactionTestBase,
    )

    # Ad-hoc setup — re-use the existing transaction base class's
    # ``setUp`` to bootstrap an authenticated tenant + role + active
    # subscription middleware prereqs in one shot.
    tc = ContractsAPITransactionTestBase()
    tc._pre_setup()  # type: ignore[attr-defined]
    try:
        tc.setUp()
        before = Contract.objects.count()
        response = tc.client.post(
            "/api/v1/contracts/",
            data={
                "original_raw": body,
                "original_format": "YAML",
                "original_spec_type": "ODCS",
            },
            format="json",
        )
        # 4xx required; 2xx would mean we deserialised attacker Python.
        assert 400 <= response.status_code < 500, (
            f"Malicious YAML must be rejected with 4xx; got {response.status_code}"
            f" body={getattr(response, 'data', None)}"
        )
        # Belt-and-braces: no row persisted.
        assert Contract.objects.count() == before, (
            "Malicious YAML caused a Contract row to be persisted — "
            "the parse path is unsafe."
        )
    finally:
        try:
            tc.tearDown()
        except Exception:
            pass
        try:
            tc._post_teardown()  # type: ignore[attr-defined]
        except Exception:
            pass
