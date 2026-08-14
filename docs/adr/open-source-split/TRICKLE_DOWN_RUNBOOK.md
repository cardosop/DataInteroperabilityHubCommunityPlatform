# Trickle-Down Runbook — promoting a paid app to core

When a paid-layer capability stabilizes and should become open source,
follow these steps IN ORDER. Each step is independently verifiable;
stop and fix before continuing.

## Prerequisites

- [ ] GATE-29 green: `python scripts/check_core_boundary.py`
- [ ] Both-mode boot green:
      `python hub/manage.py check` and `HUB_CORE_ONLY=1 python hub/manage.py check`

## 1. Move the app in the manifest (single source of truth)

Edit `hub/apps/manifest.py` — remove the app's module from `_PAID_MODULES`.
Everything downstream derives from this: settings filtering, GATE-29,
publish exclusions, CLI core-gates.

```python
# before
"hub.apps.example_paid",
# after — delete the line
```

- [ ] `venv/bin/python -m pytest hub/tests/test_manifest.py` green
      (membership counts are asserted explicitly — update the counts in
      the test if they are hardcoded, never weaken the test)

## 2. Fix residual boundary violations

Run GATE-29. The promoted app's directory is now scanned as CORE, so any
paid imports it makes (or that other core apps make of it) fail loudly:

```bash
python scripts/check_core_boundary.py --list
```

- [ ] Every violation in the promoted app inverted (hook/registry/move)
      or allowlisted with a dated reason
- [ ] Other core apps may now import the promoted app freely — no change
      needed for them

## 3. Move URL mounts into core URLconfs

The promoted app registered its prefixes via `hub.apps.api.paid_urls`
from `AppConfig.ready()`. Move them back:

- [ ] Remove the `register_paid_urlpatterns(...)` call from the app's
      `ready()`
- [ ] Add the `path(...)` entries to `hub/apps/api/urls.py` (or the
      appropriate core URLconf), preserving names and ordering
- [ ] Verify full-mode OpenAPI is unchanged; core-mode OpenAPI now
      INCLUDES the promoted paths

## 4. Remove `paid: true` tagging

- [ ] Remove the promoted IDs from `paid_ids:` in
      `docs/CRITICAL_UC_JOURNEY_IDS.yaml`
- [ ] Verify both gate scopes still pass:
      `python scripts/lint_journey_marker_coverage.py` and `--scope core`

## 5. Regenerate exclusions and publish

```bash
python scripts/generate_publish_excludes.py
PYTHON=venv/bin/python SKIP_PUSH=1 bash scripts/publish_public.sh   # dry-run
PYTHON=venv/bin/python PUBLIC_REPO_DIR=<public-clone> bash scripts/publish_public.sh
```

- [ ] The dry-run tree contains the promoted app's directory
- [ ] The publish run tags a new `vYYYY.MM.DD`

## 6. History note

The promoted app's pre-promotion commits were scrubbed OUT of the public
history by the original filter-repo pass. Its public history starts with
the sync commit from step 5 (by design — see the ADR).

## Rollback

If a promotion causes trouble: re-add the module to `_PAID_MODULES`,
reverse steps 2–4, and republish. Nothing is irreversible.
