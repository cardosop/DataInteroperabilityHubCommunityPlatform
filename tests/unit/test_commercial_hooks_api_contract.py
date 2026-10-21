"""313-H hardening 1.1 — commercial-hooks API contract pin.

``hub.apps.core.commercial_hooks`` is THE paid↔core contract surface: the
paid apps' ``AppConfig.ready()`` registers providers through the setters and
core call sites invoke the getters/callers. A core-side change that renames a
hook, alters its keyword-only arity, or breaks the setter/getter registry-key
pairing silently breaks the PAID deployment — the import-direction gates
cannot see it, because nothing about the *import graph* changed.

This module pins that surface mechanically against the single metadata table
``commercial_hooks.HOOK_API_CONTRACT``, on three independent axes:

1. **Signature** (``inspect``) — every row's ``param_spec`` must match the
   live function exactly, *including parameter kind*: ``f(tenant)`` and
   ``f(*, tenant)`` are different contracts, and swapping them breaks every
   call site while leaving the parameter *names* identical.
2. **Registry pairing** (``ast``) — the setter named by a row must write
   exactly the row's ``_HOOKS`` key, and the getter/caller must read it.
   The index is built *per function*, not by searching the file: a setter
   that writes the WRONG key leaves both key strings present in the source,
   so a module-wide substring search cannot detect a swapped pairing.
3. **Runtime round-trip** — each setter is called with a sentinel and the
   registry is inspected, proving where the value actually lands rather
   than where the source appears to put it.

Plus completeness in both directions: a new public function or a new
``_HOOKS`` key that is not in the table fails the suite, so the contract
cannot be extended silently.

NO MOCKS: the real module, real ``inspect``, real AST, real registry. The
RED checks perform *AST surgery* on a copy of the module and re-exec it —
never string replacement, which can silently no-op or, worse, delete a
``def`` line and quietly graft the orphaned body onto the previous function
(a mutation that "passes" for entirely the wrong reason).
"""

from __future__ import annotations

import ast
import inspect
import types
from pathlib import Path

import pytest

from hub.apps.core import commercial_hooks

_SOURCE = Path(commercial_hooks.__file__).read_text()
_REGISTRY = "_HOOKS"


@pytest.fixture(autouse=True, scope="module")
def _restore_registry_after_module():
    """Contain the runtime round-trip's churn to this module.

    ``contract_violations`` calls the real setters to observe where values
    land; without this fixture a failure between save and restore could
    leave the paid providers registered at ``AppConfig.ready()`` time WIPED
    for every later test module in the session.
    """
    with commercial_hooks.hooks_snapshot():
        yield


# ---------------------------------------------------------------------------
# Canonical signature rendering
# ---------------------------------------------------------------------------
def _param_spec(fn) -> str:
    """Render a function's caller-facing parameter list.

    Reads like the ``def`` line: names in order, ``/`` after positional-only
    params, ``*`` before keyword-only ones, ``**kwargs`` for var-keyword, and
    a trailing ``=`` on any param carrying a default. Annotations are
    deliberately excluded — retyping a hook breaks no call site, whereas kind
    and optionality break all of them.
    """
    parameters = list(inspect.signature(fn).parameters.values())
    kinds = inspect.Parameter
    last_positional_only = max(
        (i for i, p in enumerate(parameters) if p.kind is kinds.POSITIONAL_ONLY),
        default=None,
    )
    parts: list[str] = []
    star_emitted = False
    for i, param in enumerate(parameters):
        if param.kind is kinds.VAR_POSITIONAL:
            parts.append(f"*{param.name}")
            star_emitted = True
        elif param.kind is kinds.VAR_KEYWORD:
            parts.append(f"**{param.name}")
        else:
            if param.kind is kinds.KEYWORD_ONLY and not star_emitted:
                parts.append("*")
                star_emitted = True
            parts.append(param.name + ("=" if param.default is not param.empty else ""))
        if i == last_positional_only:
            parts.append("/")
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Function-scoped registry index (AST)
# ---------------------------------------------------------------------------
def _subscript_key(node: ast.AST) -> str | None:
    """Return the constant key of a ``_HOOKS["..."]`` subscript, else None."""
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == _REGISTRY
        and isinstance(node.slice, ast.Constant)
        and isinstance(node.slice.value, str)
    ):
        return node.slice.value
    return None


def _accessor_key(node: ast.Call) -> str | None:
    """Return the constant key of a ``_HOOKS.get("...")``/``.pop`` call."""
    if (
        isinstance(node.func, ast.Attribute)
        and node.func.attr in {"get", "pop"}
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == _REGISTRY
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ):
        return node.args[0].value
    return None


def _registry_index(tree: ast.Module) -> dict[str, dict[str, set[str]]]:
    """Map each top-level function to the ``_HOOKS`` keys it writes/reads.

    Per-function scoping is the entire point: a swapped pairing (setter A
    writing setter B's key) leaves every key string present in the file, so
    only an index that knows *which function* touched *which key* can catch
    it.
    """
    index: dict[str, dict[str, set[str]]] = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        writes: set[str] = set()
        reads: set[str] = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    key = _subscript_key(target)
                    if key is not None:
                        writes.add(key)
            elif isinstance(child, ast.Call):
                key = _accessor_key(child)
                if key is not None:
                    reads.add(key)
            elif isinstance(child, ast.Subscript) and isinstance(child.ctx, ast.Load):
                key = _subscript_key(child)
                if key is not None:
                    reads.add(key)
        index[node.name] = {"writes": writes, "reads": reads}
    return index


# ---------------------------------------------------------------------------
# The contract validator
# ---------------------------------------------------------------------------
def _signature_and_pairing_violations(table, module, index) -> list[str]:
    violations: list[str] = []
    for name, spec, setter, key in table:
        fn = getattr(module, name, None)
        if not callable(fn):
            violations.append(f"{name}: missing from module")
            continue

        actual = _param_spec(fn)
        if actual != spec:
            violations.append(f"{name}: signature ({actual}) != contract ({spec})")

        if setter is not None and not callable(getattr(module, setter, None)):
            violations.append(f"{name}: paired setter {setter!r} missing from module")

        if key is None:
            continue

        if setter is None:
            # The row IS the setter: it must write exactly this key, and only it.
            writes = index.get(name, {}).get("writes", set())
            if writes != {key}:
                violations.append(
                    f"{name}: writes {sorted(writes) or '<nothing>'} != contract key [{key!r}]"
                )
            continue

        # The row is a getter/caller: it must read the key its setter writes.
        reads = index.get(name, {}).get("reads", set())
        if key not in reads:
            violations.append(
                f"{name}: reads {sorted(reads) or '<nothing>'} — never registry key {key!r}"
            )
        setter_writes = index.get(setter, {}).get("writes", set())
        if setter_writes != {key}:
            violations.append(
                f"{name}: paired setter {setter} writes "
                f"{sorted(setter_writes) or '<nothing>'} != [{key!r}]"
            )
    return violations


def _runtime_roundtrip_violations(table, module) -> list[str]:
    """Call every setter with a sentinel and observe where it actually lands.

    The runtime twin of the AST pairing check — it depends on execution, not
    on how the source reads, so the two axes fail independently.
    """
    registry = getattr(module, _REGISTRY, None)
    if not isinstance(registry, dict):
        return [f"module exposes no {_REGISTRY} dict registry"]

    saved = dict(registry)
    violations: list[str] = []
    try:
        for name, spec, setter, key in table:
            if setter is not None or key is None:
                continue  # setter rows only
            fn = getattr(module, name, None)
            if not callable(fn) or spec == "" or "," in spec or "*" in spec:
                continue  # not a single-positional setter; signature check owns it
            sentinel = object()
            registry.clear()
            try:
                fn(sentinel)
            # Broad by design: ANY failure to register is a contract
            # violation, and it is reported — never swallowed.
            except Exception as exc:
                violations.append(f"{name}: setter raised {type(exc).__name__}: {exc}")
                continue
            if registry.get(key) is not sentinel:
                landed = sorted(k for k, val in registry.items() if val is sentinel)
                violations.append(
                    f"{name}: setter stored under {landed or '<nothing>'} at run "
                    f"time, contract key is {key!r}"
                )
    finally:
        registry.clear()
        registry.update(saved)
    return violations


def _completeness_violations(table, tree, index) -> list[str]:
    violations: list[str] = []

    listed = [row[0] for row in table]
    duplicates = sorted({name for name in listed if listed.count(name) > 1})
    if duplicates:
        violations.append(f"duplicate HOOK_API_CONTRACT rows: {duplicates}")

    defined = {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and not node.name.startswith("_")
    }
    unlisted = sorted(defined - set(listed))
    if unlisted:
        violations.append(f"public functions missing from HOOK_API_CONTRACT: {unlisted}")

    used_keys = {key for access in index.values() for key in access["writes"] | access["reads"]}
    listed_keys = {row[3] for row in table if row[3] is not None}
    unlisted_keys = sorted(used_keys - listed_keys)
    if unlisted_keys:
        violations.append(f"registry keys missing from HOOK_API_CONTRACT: {unlisted_keys}")

    return violations


def contract_violations(table=None, module=None, tree=None) -> list[str]:
    """Validate *table* against *module*/*tree*; return every violation found.

    Defaults to the real module validating its own table. The ``module`` and
    ``tree`` parameters are the RED-check seam: a drifted copy of the module
    is validated by exactly the same code path as the real one.
    """
    module = module if module is not None else commercial_hooks
    table = commercial_hooks.HOOK_API_CONTRACT if table is None else table
    tree = tree if tree is not None else ast.parse(_SOURCE)
    index = _registry_index(tree)
    return [
        *_signature_and_pairing_violations(table, module, index),
        *_runtime_roundtrip_violations(table, module),
        *_completeness_violations(table, tree, index),
    ]


# ---------------------------------------------------------------------------
# AST surgery helpers for the RED checks
# ---------------------------------------------------------------------------
def _func(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name!r} not found in the module AST — update this test")


def _write_key_node(fn_node: ast.FunctionDef) -> ast.Constant:
    """The ``ast.Constant`` holding the key a setter writes."""
    for child in ast.walk(fn_node):
        if isinstance(child, ast.Assign):
            for target in child.targets:
                if _subscript_key(target) is not None:
                    return target.slice
                raise AssertionError(
                    f"{fn_node.name} has no {_REGISTRY}[...] write — update this test"
                )


def _drifted(mutate) -> tuple[ast.Module, types.ModuleType]:
    """Apply *mutate* to a fresh AST of the real module and exec the result.

    AST surgery rather than string replacement: a mutation cannot silently
    no-op, and removing a function removes the whole node instead of orphaning
    its body onto the preceding one.
    """
    tree = ast.parse(_SOURCE)
    mutate(tree)
    ast.fix_missing_locations(tree)
    module = types.ModuleType("drifted_commercial_hooks")
    exec(compile(tree, "<drifted>", "exec"), module.__dict__)
    return tree, module


def _violations_after(mutate) -> list[str]:
    tree, module = _drifted(mutate)
    return contract_violations(table=commercial_hooks.HOOK_API_CONTRACT, module=module, tree=tree)


@pytest.fixture
def signature_drifted_module():
    """The real module with ONE hook signature mutated.

    ``check_entitlement`` loses its ``provider_tenant_id`` keyword — the
    canonical drift class this pin exists to catch: core drops a parameter,
    the paid marketplace still passes it, every cross-tenant entitlement call
    raises ``TypeError`` in production.
    """

    def mutate(tree: ast.Module) -> None:
        fn = _func(tree, "check_entitlement")
        fn.args.kwonlyargs = [a for a in fn.args.kwonlyargs if a.arg != "provider_tenant_id"]
        fn.args.kw_defaults = [None] * len(fn.args.kwonlyargs)

    return _drifted(mutate)


# ---------------------------------------------------------------------------
# GREEN — the contract holds against the module as it stands
# ---------------------------------------------------------------------------
def test_contract_passes_against_the_current_module():
    assert contract_violations() == []


def test_table_covers_every_public_function_and_registry_key():
    """Guards the guard: an empty/short-circuited table must not pass."""
    table = commercial_hooks.HOOK_API_CONTRACT
    assert len(table) >= 55, f"table shrank to {len(table)} rows — hooks removed?"
    tree = ast.parse(_SOURCE)
    assert _completeness_violations(table, tree, _registry_index(tree)) == []


def test_every_setter_row_is_paired_with_at_least_one_reader():
    """A registered provider nothing ever reads is dead weight (or a typo)."""
    table = commercial_hooks.HOOK_API_CONTRACT
    readers_by_key = {row[3] for row in table if row[2] is not None}
    orphans = sorted(
        row[0]
        for row in table
        if row[2] is None and row[3] is not None and row[3] not in readers_by_key
    )
    assert orphans == [], f"setters with no paired reader row: {orphans}"


def test_param_spec_renders_kind_faithfully():
    """The renderer is the contract's measuring stick — pin its behaviour."""

    def sample(a, /, b, *args, c, d=1, **kwargs):
        pass

    assert _param_spec(sample) == "a, /, b, *args, c, d=, **kwargs"
    assert _param_spec(commercial_hooks.check_entitlement) == (
        "*, consumer_tenant_id, asset_id, provider_tenant_id"
    )
    assert _param_spec(commercial_hooks.has_active_billing_setup) == "tenant"


# ---------------------------------------------------------------------------
# RED — each drift class must fail the contract
# ---------------------------------------------------------------------------
def test_red_dropped_keyword_fails_the_contract(signature_drifted_module):
    """The fixture-mutated signature must be rejected."""
    tree, module = signature_drifted_module
    violations = contract_violations(
        table=commercial_hooks.HOOK_API_CONTRACT, module=module, tree=tree
    )
    assert any("check_entitlement" in v and "signature" in v for v in violations), violations
    # Precision: the surgery touched nothing else.
    assert not any("dispatch_tombstone" in v for v in violations), violations


def test_red_positional_param_turned_keyword_only_is_detected():
    """``f(tenant)`` → ``f(*, tenant)`` keeps every name yet breaks every
    positional caller — the drift a name-only check cannot see."""

    def mutate(tree):
        fn = _func(tree, "has_active_billing_setup")
        fn.args.kwonlyargs = fn.args.args
        fn.args.args = []
        fn.args.kw_defaults = [None] * len(fn.args.kwonlyargs)

    violations = _violations_after(mutate)
    assert any("has_active_billing_setup" in v and "(*, tenant)" in v for v in violations), (
        violations
    )


def test_red_keyword_only_param_turned_positional_is_detected():
    """The reverse direction must fail too."""

    def mutate(tree):
        fn = _func(tree, "get_ml_model_attributes")
        fn.args.args = fn.args.kwonlyargs
        fn.args.kwonlyargs = []
        fn.args.kw_defaults = []

    violations = _violations_after(mutate)
    assert any("get_ml_model_attributes" in v and "signature" in v for v in violations), violations


def test_red_setter_gaining_a_parameter_is_detected():
    """Setters are part of the contract: the paid ``ready()`` calls them."""

    def mutate(tree):
        _func(tree, "set_entitlement_provider").args.args.append(ast.arg(arg="priority"))

    violations = _violations_after(mutate)
    assert any("set_entitlement_provider" in v and "priority" in v for v in violations), violations


def test_red_param_gaining_a_default_is_detected():
    """Optionality is contract: a defaulted param silently accepts fewer args."""

    def mutate(tree):
        fn = _func(tree, "filter_api_keys_by_tier")
        fn.args.defaults = [ast.Constant(value=None)]

    violations = _violations_after(mutate)
    assert any("filter_api_keys_by_tier" in v and "tier_name=" in v for v in violations), violations


def test_red_renamed_hook_is_detected():
    def mutate(tree):
        _func(tree, "get_file_asset_id").name = "resolve_file_asset_id"

    violations = _violations_after(mutate)
    assert any("get_file_asset_id" in v and "missing from module" in v for v in violations), (
        violations
    )
    assert any("resolve_file_asset_id" in v for v in violations), violations


def test_red_removed_hook_is_detected_without_collateral_damage():
    """Whole-node removal — the neighbouring function stays intact, so the
    failure is attributable to the deletion and nothing else."""

    def mutate(tree):
        tree.body.remove(_func(tree, "get_file_asset_id"))

    violations = _violations_after(mutate)
    assert any("get_file_asset_id" in v and "missing from module" in v for v in violations), (
        violations
    )
    assert not any("set_file_asset_resolver" in v for v in violations), violations


def test_red_swapped_registry_keys_between_setters_is_detected():
    """The hole a module-wide substring search cannot close.

    Both key strings still appear in the file after the swap, so a
    ``'_HOOKS["k"]' in source`` check is satisfied — while each getter is
    permanently blind to what its own setter stored.
    """

    def mutate(tree):
        left = _write_key_node(_func(tree, "set_stripe_customer_resolver"))
        right = _write_key_node(_func(tree, "set_admin_billing_summary_provider"))
        left.value, right.value = right.value, left.value

    tree, module = _drifted(mutate)
    violations = contract_violations(
        table=commercial_hooks.HOOK_API_CONTRACT, module=module, tree=tree
    )
    assert any("set_stripe_customer_resolver" in v for v in violations), violations
    assert any("set_admin_billing_summary_provider" in v for v in violations), violations

    # Both key strings survive the swap — proving the substring check is blind.
    swapped_source = ast.unparse(tree)
    assert "_HOOKS['stripe_customer_resolver']" in swapped_source
    assert "_HOOKS['admin_billing_summary_provider']" in swapped_source

    # And the swap is a real runtime break, not a cosmetic one.
    sentinel = object()
    module.set_stripe_customer_resolver(lambda tenant: sentinel)
    assert module.get_stripe_customer_id("tenant") is None


def test_red_getter_reading_the_wrong_key_is_detected():
    """Same blindness from the reader side."""

    def mutate(tree):
        fn = _func(tree, "get_subscription_factory")
        for child in ast.walk(fn):
            if isinstance(child, ast.Call) and _accessor_key(child) == "subscription_factory":
                child.args[0].value = "semantic_mapper"
                return
        raise AssertionError("no read site found — update this test")

    violations = _violations_after(mutate)
    assert any(
        "get_subscription_factory" in v and "subscription_factory" in v for v in violations
    ), violations


def test_red_new_hook_without_a_table_row_is_detected():
    """Extending the paid↔core surface must be a deliberate table edit."""

    def mutate(tree):
        tree.body.append(
            ast.parse(
                "def set_new_paid_hook(provider):\n    _HOOKS['new_paid_hook'] = provider\n"
            ).body[0]
        )

    violations = _violations_after(mutate)
    assert any("public functions missing" in v and "set_new_paid_hook" in v for v in violations), (
        violations
    )
    assert any("registry keys missing" in v and "new_paid_hook" in v for v in violations), (
        violations
    )


def test_red_setter_writing_nothing_is_detected():
    """A setter whose body stops registering the provider."""

    def mutate(tree):
        fn = _func(tree, "set_tombstone_provider")
        fn.body = [node for node in fn.body if not isinstance(node, ast.Assign)]
        fn.body.append(ast.Pass())

    violations = _violations_after(mutate)
    assert any("set_tombstone_provider" in v and "<nothing>" in v for v in violations), violations


def test_red_setter_writing_an_extra_key_is_detected():
    """A setter that ALSO registers under a second key.

    Double-registration is how a rename half-lands: the new key works, the
    stale one lingers and shadows a later hook. The contract demands a setter
    write its key and *only* its key, so a subset match is not enough.
    """

    def mutate(tree):
        fn = _func(tree, "set_semantic_mapper")
        fn.body.append(ast.parse("_HOOKS['legacy_semantic_mapper'] = provider").body[0])

    violations = _violations_after(mutate)
    assert any("set_semantic_mapper" in v and "legacy_semantic_mapper" in v for v in violations), (
        violations
    )


def test_red_runtime_only_drift_is_detected():
    """Source says one key, run time uses another.

    The AST axis reads the literal; the round-trip axis observes execution.
    Here the setter writes the contract key *and then* overwrites the
    registry, so only the runtime axis can catch it.
    """

    def mutate(tree):
        fn = _func(tree, "set_order_owner_checker")
        fn.body.append(ast.parse("_HOOKS.clear()").body[0])

    tree, module = _drifted(mutate)
    violations = contract_violations(
        table=commercial_hooks.HOOK_API_CONTRACT, module=module, tree=tree
    )
    assert any("set_order_owner_checker" in v and "run time" in v for v in violations), violations
