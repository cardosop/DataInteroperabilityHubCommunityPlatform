"""Phase 313.1.1 — app membership manifest unit tests.

The manifest is the single source of truth for the OSS/paid split. These
tests encode the invariants the rest of the boundary machinery relies on:

- CORE_APPS and PAID_APPS are disjoint and together cover every hub app
  in INSTALLED_APPS (full mode) — nothing may drift outside the boundary.
- ALL_HUB_APPS preserves the exact pre-split INSTALLED_APPS order so the
  production path (HUB_CORE_ONLY unset) stays byte-for-byte identical.
- is_core_only() parses 1/true/yes case-insensitively.
- Module-name normalisation strips ".apps.XConfig" suffixes so GATE-29 and
  the publish script can match import paths.
"""

import os
from unittest import mock

import pytest

from hub.apps import manifest


def _hub_app_entries(apps):
    return [
        a
        for a in apps
        if a.startswith(("hub.apps", "hub.data_movement"))
    ]


def test_core_and_paid_are_disjoint():
    assert not set(manifest.CORE_APPS) & set(manifest.PAID_APPS)


def test_manifest_covers_all_installed_hub_apps():
    """CORE ∪ PAID == the hub.* set in INSTALLED_APPS (full mode).

    graphql_graphene is conditionally inserted when graphene_django is
    importable (settings), so the comparison accounts for it explicitly.
    """
    from django.conf import settings

    installed = _hub_app_entries(settings.INSTALLED_APPS)
    manifest_all = _hub_app_entries(list(manifest.ALL_HUB_APPS))
    conditional = {"hub.apps.graphql_graphene"}
    assert set(installed) - conditional == set(manifest_all), (
        f"manifest drifted from INSTALLED_APPS:\n"
        f"  installed-only: {sorted(set(installed) - conditional - set(manifest_all))}\n"
        f"  manifest-only: {sorted(set(manifest_all) - set(installed) - conditional)}"
    )
    assert set(manifest_all) == set(manifest.CORE_APPS) | set(manifest.PAID_APPS)


def test_all_hub_apps_preserves_installed_order():
    """The production path depends on exact INSTALLED_APPS ordering.

    The conditionally-inserted graphql_graphene entry is ignored for the
    comparison — everything else must match ALL_HUB_APPS exactly."""
    from django.conf import settings

    installed = _hub_app_entries(settings.INSTALLED_APPS)
    installed = [a for a in installed if a != "hub.apps.graphql_graphene"]
    assert installed == _hub_app_entries(list(manifest.ALL_HUB_APPS))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1", True),
        ("true", True),
        ("TRUE", True),
        ("Yes", True),
        ("0", False),
        ("false", False),
        ("", False),
        (" 1 ", True),
    ],
)
def test_is_core_only_parses_truthy_values(raw, expected):
    with mock.patch.dict(os.environ, {"HUB_CORE_ONLY": raw}, clear=False):
        assert manifest.is_core_only() is expected


def test_is_core_only_defaults_false():
    with mock.patch.dict(os.environ, {}, clear=True):
        assert manifest.is_core_only() is False


def test_module_name_normalisation_strips_app_config_suffix():
    assert manifest.module_name("hub.apps.compliance.apps.ComplianceConfig") == "hub.apps.compliance"
    assert manifest.module_name("hub.apps.marketplace") == "hub.apps.marketplace"


def test_module_name_never_collapses_plain_module_paths():
    """Regression: the split-based normaliser returned 'hub' for every
    plain 'hub.apps.X' path, silently classifying every app as CORE."""
    assert manifest.module_name("hub.apps.semantic") == "hub.apps.semantic"
    assert manifest.module_name("hub.apps.api.analytics") == "hub.apps.api.analytics"
    assert manifest.module_name("hub.data_movement") == "hub.data_movement"


def test_paid_and_core_membership_is_explicit():
    """Locked boundary: semantic is PAID, assets is CORE — the boot filter
    depends on this, so membership drift must fail loudly."""
    paid_modules = {manifest.module_name(e) for e in manifest.PAID_APPS}
    core_modules = {manifest.module_name(e) for e in manifest.CORE_APPS}
    assert "hub.apps.semantic" in paid_modules
    assert "hub.apps.marketplace" in paid_modules
    assert "hub.apps.assets" in core_modules
    assert "hub.apps.assets" not in paid_modules
    assert len(manifest.PAID_APPS) == 10
    assert len(manifest.CORE_APPS) == 42
    assert not paid_modules & core_modules
