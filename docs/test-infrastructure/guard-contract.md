# Core/paid import guard contract (GUARD-313.H)

Every allowlisted core-site paid import (see `scripts/core_boundary_allowlist.txt`)
must survive **both** core-only failure modes:

| Mode | Failure |
|---|---|
| Private repo, `HUB_CORE_ONLY=1` | `RuntimeError` — the app is not installed, Django raises at model-class definition |
| Public tree / deployment | `ModuleNotFoundError` — the paid module does not exist on disk |

`scripts/check_core_boundary.py --check-guards` enforces this statically
(AST parent lookup). Sanctioned patterns, **in preference order**:

1. **Hooks inversion** — don't import at all: register a provider in
   `hub.apps.core.commercial_hooks` from the paid app's `AppConfig.ready()`
   and call the hook from core. (Not statically verifiable — the guard
   gate cannot see this pattern, so such sites need no allowlist entry at
   all: the import lives in the paid app.)
2. **Full-mode branch** — the import runs only when core mode is OFF:
   ```python
   from django.conf import settings

   if not settings.HUB_CORE_ONLY:
       from hub.apps.marketplace.models import Listing
   ```
   or `if not is_core_only():` / the `else` branch of a core-mode `if`.
3. **Exception guard** — defensive fallback:
   ```python
   try:
       from hub.apps.semantic.models import Thing
   except (RuntimeError, ModuleNotFoundError):
       Thing = None
   ```
   `except Exception` and bare `except` also satisfy the gate, but prefer
   the explicit pair — `--check-guards --prefer-explicit` reports the
   broad-handler sites non-blockingly so they migrate over time.
   `except ImportError` alone is NOT sufficient (it misses `RuntimeError`);
   `except (ImportError, RuntimeError)` IS sufficient (ImportError covers
   `ModuleNotFoundError`).
4. **Annotated full-mode-only** — only when a caller-chain proof exists:
   ```python
   # core-guard: full-mode-only — called only from <paid-view path> (see <evidence>)
   from hub.apps.marketplace.models import Order
   ```
   The proof must be non-empty; an empty proof fails the gate.

Anything else must sit in `scripts/core_guard_exceptions.txt` — the
**shrinking baseline**. The growth ratchet (`--check-guard-growth`) uses
NET accounting (additions minus removals vs `git HEAD`), so line-shift
churn never blocks CI, but the baseline may never grow.

**313.H.3 closeout (2026-08-20): the baseline is EMPTY and must stay
empty.** All 49 baselined sites were converted to hooks / branches /
try-both. New sites go through the same treatment (hooks inversion first);
a baseline entry is no longer an accepted outcome — the gate hard-fails
on any new unguarded site, which is the intended ratchet end-state.

## Simulating core-only mode in tests

`hub.apps.core.commercial_hooks` ships two test/simulation primitives:

- `reset_hooks()` — clears every registered provider (the exact runtime
  shape of a core-only process: every hook returns its no-op default).
- `hooks_snapshot()` — a context manager that restores the full registry
  (incl. `AppConfig.ready()` registrations) on exit. Tests that simulate
  core-only mode must run `reset_hooks()` INSIDE a `hooks_snapshot()`
  block, otherwise the paid providers stay wiped for every later test
  module in the session.

## Exemptions

- **Test modules** (`test_*.py` / `*_tests.py`): protected by the root
  conftest's collection gate in core mode; the public tree excludes paid
  apps entirely.
- **Paid app directories**: never scanned (their internal paid imports are
  legal), same as GATE-29.

`conftest.py` files are **NOT** exempt — pytest loads them in core runs
regardless of the test-module gate.

## Wiring

- `make boundary-check` / `make publish-check` (last line of defense
  before sync commits)
- Private CI lint (`_reusable.lint.yml`, GATE-29 step)
- Public `ci-core.yml` boundary job
- `scripts/tests/test_publish_tree.py` asserts both files ship in the
  public tree
