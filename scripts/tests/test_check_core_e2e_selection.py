"""check_core_e2e_selection.py tests — synthetic fixtures, no mocks."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from check_core_e2e_selection import collect_violations

GATING_TS = """
export const PAID_ROUTE_CAPABILITIES: Readonly<Record<string, string>> = {
  '/marketplace': 'marketplace',
  '/integrations': 'integrations.marketplace',
  '/settings/subscription': 'billing',
};
"""


def _write_tree(root: Path, *, entries: str, specs: dict[str, str]) -> None:
    (root / "frontend" / "e2e").mkdir(parents=True)
    (root / "frontend" / "e2e" / "core-only.txt").write_text(entries)
    (root / "frontend" / "src" / "app" / "routes").mkdir(parents=True)
    (root / "frontend" / "src" / "app" / "routes" / "paidRouteGating.ts").write_text(GATING_TS)
    for rel, content in specs.items():
        path = root / "frontend" / "e2e" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


class TestSelectionValidity:
    def test_entry_matching_no_spec_is_flagged(self, tmp_path):
        _write_tree(
            tmp_path,
            entries="Feature: Assets\nGhost Entry\n",
            specs={"assets.spec.ts": "test('Feature: Assets page', () => {})\n"},
        )
        violations = collect_violations(tmp_path)
        assert any("Ghost Entry" in v and "matches NO spec" in v for v in violations)

    def test_valid_entries_are_clean(self, tmp_path):
        _write_tree(
            tmp_path,
            entries="Feature: Assets\n",
            specs={"assets.spec.ts": "test('Feature: Assets page', () => {})\n"},
        )
        assert collect_violations(tmp_path) == []

    def test_comments_and_blanks_are_ignored(self, tmp_path):
        _write_tree(
            tmp_path,
            entries="# comment\n\nFeature: Assets\n",
            specs={"assets.spec.ts": "test('Feature: Assets page', () => {})\n"},
        )
        assert collect_violations(tmp_path) == []


class TestPaidExclusion:
    def test_entry_matching_paid_spec_is_flagged(self, tmp_path):
        """A paid journey leaking into the core selection must fail."""
        _write_tree(
            tmp_path,
            entries="Marketplace checkout\n",
            specs={
                "marketplace.spec.ts": "test('Marketplace checkout flow', () => {})\n",
            },
        )
        violations = collect_violations(tmp_path)
        assert any("PAID-surface" in v for v in violations)

    def test_core_entries_do_not_leak(self, tmp_path):
        _write_tree(
            tmp_path,
            entries="Feature: Assets\n",
            specs={
                "assets.spec.ts": "test('Feature: Assets page', () => {})\n",
                "marketplace.spec.ts": "test('Marketplace checkout flow', () => {})\n",
            },
        )
        assert collect_violations(tmp_path) == []

    def test_core_integrations_spec_is_not_flagged(self, tmp_path):
        """The regression the real scan caught: a CORE integrations spec
        (Jobs/Scheduled/Webhooks) must NOT be flagged as paid even though
        its title contains "Integrations" — the paid signal for the
        ``/integrations`` prefix is "marketplace", not "integrations"."""
        _write_tree(
            tmp_path,
            entries="Scheduled Ingestion\nWebhooks\n",
            specs={
                "integrations.spec.ts": (
                    "test('Integrations, Jobs, Scheduled Ingestion, Webhooks routes', () => {})\n"
                ),
            },
        )
        assert collect_violations(tmp_path) == []

    def test_new_paid_prefix_extends_the_check(self, tmp_path):
        """A NEW paid route prefix in PAID_ROUTE_CAPABILITIES must
        automatically extend the paid-surface terms."""
        _write_tree(
            tmp_path,
            entries="Teams dashboard\n",
            specs={"teams.spec.ts": "test('Teams dashboard', () => {})\n"},
        )
        gating = tmp_path / "frontend" / "src" / "app" / "routes" / "paidRouteGating.ts"
        gating.write_text(
            GATING_TS.replace(
                "'/settings/subscription': 'billing',", "  '/teams': 'billing.teams',"
            )
        )
        violations = collect_violations(tmp_path)
        assert any("PAID-surface" in v for v in violations)
