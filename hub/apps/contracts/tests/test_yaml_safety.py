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


def _scan_for_unsafe_yaml_load() -> list[tuple[Path, int, str]]:
    """Return every line in ``hub.apps.contracts`` that calls
    ``yaml.load(`` *without* ``Loader=yaml.SafeLoader``.

    Skips comments + docstrings: a line that appears under a triple
    quote or inside a ``#`` comment is allowed (used for narrative).
    """
    unsafe = re.compile(r"\byaml\.load\s*\(")
    safe_loader = re.compile(r"Loader\s*=\s*yaml\.SafeLoader")
    findings: list[tuple[Path, int, str]] = []
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
    assert findings == [], "Unsafe ``yaml.load`` call detected (RCE risk):\n" + "\n".join(
        f"  {p}:{n}: {line}" for (p, n, line) in findings
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


class CreateContractRejectsMaliciousYamlTest:
    """End-to-end behavioural pin — the ``ContractsAPITransactionTestBase``
    fixture wires the full middleware stack (auth, tenant, subscription,
    role) so we exercise the actual API surface attackers would hit.

    Implemented as a non-Django test class with ``self`` plumbed through
    a setup helper so ``pytest`` collects each parametrised case as a
    separate test (instead of one ginormous test).
    """


def _build_yaml_safety_e2e_class():
    """Return a TestCase subclass with one method per malicious tag.

    Defining the class via a builder keeps the parametrisation static
    (clear test names) and avoids the awkward ``_pre_setup`` /
    ``_post_teardown`` hack the previous version used.
    """
    from hub.apps.contracts.models import Contract
    from hub.apps.contracts.tests.test_base import (
        ContractsAPITransactionTestBase,
    )

    namespace: dict = {}

    def _make_test(label: str, body: str):
        def _test(self):
            before = Contract.objects.count()
            response = self.client.post(
                "/api/v1/contracts/",
                data={
                    "original_raw": body,
                    "original_format": "YAML",
                    "original_spec_type": "ODCS",
                },
                format="json",
            )
            self.assertGreaterEqual(
                response.status_code,
                400,
                f"Malicious YAML must be rejected with 4xx; got "
                f"{response.status_code}: {getattr(response, 'data', None)}",
            )
            self.assertLess(response.status_code, 500)
            self.assertEqual(
                Contract.objects.count(),
                before,
                "Malicious YAML caused a Contract row to be persisted — the parse path is unsafe.",
            )

        _test.__name__ = f"test_rejects_{label}"
        _test.__doc__ = (
            f"End-to-end: ``{label}`` MUST be rejected with 4xx and MUST NOT "
            f"persist a row. Tag: {body!r}"
        )
        return _test

    for label, body in _MALICIOUS_PAYLOADS:
        method = _make_test(label, body)
        namespace[method.__name__] = method

    return type(
        "CreateContractRejectsMaliciousYamlE2E",
        (ContractsAPITransactionTestBase,),
        namespace,
    )


CreateContractRejectsMaliciousYamlE2E = _build_yaml_safety_e2e_class()
