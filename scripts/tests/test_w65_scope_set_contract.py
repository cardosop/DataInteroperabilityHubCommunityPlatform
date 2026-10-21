"""W6.5 (oss-release-remediation, S1) — JWT scope-set contract pins.

The W7.5 `ENFORCE_JWT_SCOPES` flip 403s clients whose scope vocabulary
drifted from the backend's.  These pins assert that every client copy of
the scope vocabulary — sdk/python, sdk/js, cli — is EXACTLY the
backend's expected scope set (``hub.apps.auth.scopes.ROLE_SCOPE_MAP`` /
``ALL_SCOPES``), by importing the real modules (no mocks, no copies of
the data).  A scope change on either side flips this suite RED until
both sides land in the same change — that is the contract.

TDD contract, no mocks: the backend module is Django-free on purpose
(see hub/apps/auth/scopes.py) so this file can import it in the CI
no-django lint job.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SDK_PY = REPO_ROOT / "sdk" / "python"
SDK_JS = REPO_ROOT / "sdk" / "js"
CLI = REPO_ROOT / "cli"

for _path in (str(REPO_ROOT), str(SDK_PY), str(CLI)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from datahub_cli import scopes as cli_scopes
from datahub_interoperability import scopes as py_sdk_scopes

from hub.apps.auth import scopes as backend_scopes

# ── sdk/js/src/scopes.ts parser ─────────────────────────────────────────
# The TS module is written in a STRICT, parser-friendly shape (a change
# that breaks the shape flips this suite RED — the shape is part of the
# contract): `export const X = 'value';`,
# `export const Y: readonly string[] = [ ... ];` (one string per line)
# and `export const Z: Record<string, readonly string[]> = { ROLE: [ ... ] };`
# with UPPERCASE role keys ending the line with a bare `:`.
_TS_CONST = re.compile(
    r"export const (?P<name>\w+)(?:: [^=]+)? = (?P<value>\[[^\]]*\]|'[^']*');",
    re.DOTALL,
)
_TS_STRINGS = re.compile(r"'([^']+)'")
_TS_ROLE_KEY = re.compile(r"^\s*([A-Z_][A-Z0-9_]*):\s*\[\s*$")


def _parse_ts_scopes_module() -> dict[str, object]:
    text = (SDK_JS / "src" / "scopes.ts").read_text(encoding="utf-8")
    extracted: dict[str, object] = {}
    for match in _TS_CONST.finditer(text):
        name = match.group("name")
        value = match.group("value").strip()
        if value.startswith("'"):
            extracted[name] = value.strip("'")
        elif value.startswith("["):
            extracted[name] = frozenset(_TS_STRINGS.findall(value))
    # The ROLE_SCOPES object: uppercase keys, one scope string per line.
    role_body = re.search(
        r"export const ROLE_SCOPES:[^{]*\{(?P<body>.*?)\n\};", text, re.DOTALL
    )
    if role_body is None:
        raise AssertionError("sdk/js scopes.ts: ROLE_SCOPES block not in the pinned shape")
    roles: dict[str, frozenset[str]] = {}
    current: str | None = None
    for line in role_body.group("body").splitlines():
        key_match = _TS_ROLE_KEY.match(line)
        if key_match:
            current = key_match.group(1)
            roles[current] = frozenset()
        elif current is not None:
            roles[current] = roles[current] | frozenset(_TS_STRINGS.findall(line))
    extracted["ROLE_SCOPES"] = roles
    return extracted


@pytest.fixture(scope="module")
def ts_scopes() -> dict[str, object]:
    return _parse_ts_scopes_module()


def _client_pairs(ts_scopes):
    """(name, role_map, all_scopes) for every client copy."""
    return [
        ("sdk/python", py_sdk_scopes.ROLE_SCOPES, py_sdk_scopes.ALL_SCOPES),
        ("cli", cli_scopes.ROLE_SCOPES, cli_scopes.ALL_SCOPES),
        ("sdk/js", ts_scopes["ROLE_SCOPES"], ts_scopes["ALL_SCOPES"]),
    ]


def test_backend_vocabulary_is_well_formed():
    """Every concrete scope follows the domain:action shape and the
    wildcard is the only non-concrete entry."""
    for scope in backend_scopes.ALL_SCOPES:
        assert re.fullmatch(r"[a-z_]+:(read|write|view_pii)", scope), scope
    assert backend_scopes.WILDCARD_SCOPE == "*"
    # The worker-internal scope is never part of the client vocabulary.
    assert backend_scopes.SCOPE_SCHEDULED_INGESTION_INTERNAL not in backend_scopes.ALL_SCOPES


def test_every_client_all_scopes_matches_the_backend(ts_scopes):
    """sdk/python + cli + sdk/js carry EXACTLY the backend's scope set."""
    for name, _role_map, all_scopes in _client_pairs(ts_scopes):
        assert all_scopes == backend_scopes.ALL_SCOPES, (
            f"{name} ALL_SCOPES drifted from the backend: "
            f"missing={sorted(backend_scopes.ALL_SCOPES - all_scopes)} "
            f"extra={sorted(all_scopes - backend_scopes.ALL_SCOPES)}"
        )


def test_every_client_role_map_matches_the_backend(ts_scopes):
    """Every client role→scopes map equals ROLE_SCOPE_MAP, including the
    PLATFORM_ADMIN wildcard entry."""
    for name, role_map, _all_scopes in _client_pairs(ts_scopes):
        assert role_map == backend_scopes.ROLE_SCOPE_MAP, (
            f"{name} ROLE_SCOPES drifted from the backend: "
            f"roles_missing={sorted(set(backend_scopes.ROLE_SCOPE_MAP) - set(role_map))} "
            f"roles_extra={sorted(set(role_map) - set(backend_scopes.ROLE_SCOPE_MAP))}"
        )


def test_every_client_rejects_the_internal_scope(ts_scopes):
    """The worker-internal scope must never pass client validation in
    any client (it is unmintable via the public API — R2-B2).  The JS
    validator behaviour is pinned by sdk/js scopes.test.ts; this file
    pins the JS data shape only."""
    internal = backend_scopes.SCOPE_SCHEDULED_INGESTION_INTERNAL
    assert internal in py_sdk_scopes.validate_scopes([internal])
    assert internal in cli_scopes.validate_scopes([internal])
    assert ts_scopes["SCOPE_SCHEDULED_INGESTION_INTERNAL"] == internal
    assert internal not in ts_scopes["ALL_SCOPES"]


def test_client_validators_flag_unknown_scopes_only():
    """validate_scopes returns exactly the scopes outside the
    vocabulary (the wildcard is mintable — role-gated server-side)."""
    assert py_sdk_scopes.validate_scopes(["assets:read"]) == []
    assert py_sdk_scopes.validate_scopes(["nope:nope"]) == ["nope:nope"]
    assert py_sdk_scopes.validate_scopes(["*"]) == []
    assert py_sdk_scopes.validate_scopes(["assets:read", "nope:nope"]) == ["nope:nope"]

    assert cli_scopes.validate_scopes(["assets:read"]) == []
    assert cli_scopes.validate_scopes(["nope:nope"]) == ["nope:nope"]


def test_role_scope_helper_matches_backend_union():
    """scope_set_for_role / effective_scopes_for_roles agree with the
    backend's own union helper for every role."""
    for role, expected in backend_scopes.ROLE_SCOPE_MAP.items():
        assert py_sdk_scopes.scope_set_for_role(role) == expected
        assert cli_scopes.scope_set_for_role(role) == expected
        assert backend_scopes.effective_scopes_for_roles([role]) == expected


def test_drift_pin_a_mutated_client_copy_flips_red(ts_scopes):
    """Falsifiability: a client copy missing ONE scope must fail the
    parity check — a green contract test that never bites detects
    nothing."""
    mutated = set(py_sdk_scopes.ALL_SCOPES)
    mutated.discard(next(iter(mutated)))
    with pytest.raises(AssertionError):
        assert mutated == backend_scopes.ALL_SCOPES

    mutated_roles = dict(py_sdk_scopes.ROLE_SCOPES)
    mutated_roles["AUDITOR"] = frozenset({"audit:read"})
    with pytest.raises(AssertionError):
        assert mutated_roles == backend_scopes.ROLE_SCOPE_MAP

    mutated_ts = dict(ts_scopes)
    mutated_ts["ALL_SCOPES"] = frozenset()
    with pytest.raises(AssertionError):
        assert mutated_ts["ALL_SCOPES"] == backend_scopes.ALL_SCOPES
