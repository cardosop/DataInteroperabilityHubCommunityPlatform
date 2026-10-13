"""Phase 1 (openspec add-databricks-uc-read task 1.8) — per-call version pins.

Every Databricks REST read is version-pinned in ONE place
(``api_paths.py``) with a per-call 2.0-vs-2.1 choice documented per
entry; an import-time guard makes drift impossible (an undocumented
entry, a documented version that disagrees with the URL, or an
unversioned path fails LOUD at import — never against a live workspace).
Callers reference operations by name: the inline-URL scan pins that no
production module outside ``api_paths.py`` embeds an ``/api/2.x``
literal. The spec scenario (unknown operation → ValueError at
development time) is pinned directly.
"""

import re
from pathlib import Path

import pytest
from django.test import SimpleTestCase

from hub.apps.databricks_admin import api_paths


class VersionPinGuardTests(SimpleTestCase):
    """The per-call version documentation + the import-time guard."""

    def test_every_map_entry_is_version_pinned_and_documented(self):
        # The REAL map passes the guard (otherwise the module would not
        # have imported at all — this pin keeps the contract explicit).
        api_paths.validate_version_pins()

    def test_uc_reads_are_documented_2_1_and_control_plane_2_0(self):
        # The per-call 2.0-vs-2.1 choice, pinned entry by entry: the UC
        # REST read surface is 2.1 (the maintained read surface — models
        # listing + next_page_token pagination live there); the control
        # plane's stable GA endpoints (probe, token management, SQL
        # statements) stay 2.0; OAuth is oidc/v1.
        uc_reads = (
            "uc.effective_permissions.table",
            "uc.catalogs.list",
            "uc.schemas.list",
            "uc.tables.list",
            "uc.views.list",
            "uc.volumes.list",
            "uc.models.list",
            "uc.external_locations.list",
            "uc.storage_credentials.list",
        )
        for operation in uc_reads:
            assert api_paths.API_PATH_VERSIONS[operation] == "2.1", operation
        for operation in (
            "workspace.list",
            "sql.statements.submit",
            "sql.statements.get",
            "sql.statements.chunk",
            "token_management.create_pat",
            "token_management.delete",
        ):
            assert api_paths.API_PATH_VERSIONS[operation] == "2.0", operation
        assert api_paths.API_PATH_VERSIONS["oidc.token"] == "1"

    def test_guard_rejects_an_undocumented_entry(self):
        with pytest.raises(RuntimeError, match="no documented version"):
            api_paths.validate_version_pins(
                paths={"uc.new.read": "/api/2.1/unity-catalog/new"},
                versions={"uc.other.read": "2.1"},
            )

    def test_guard_rejects_version_drift(self):
        # Documented 2.0 but the URL carries 2.1 — the documentation and
        # the actual pin can never silently diverge.
        with pytest.raises(RuntimeError, match=r"documented as 2\.0"):
            api_paths.validate_version_pins(
                paths={"workspace.list": "/api/2.1/workspace/list"},
                versions={"workspace.list": "2.0"},
            )

    def test_guard_rejects_unversioned_paths(self):
        with pytest.raises(RuntimeError, match="not version-pinned"):
            api_paths.validate_version_pins(
                paths={"uc.catalogs.list": "/api/unity-catalog/catalogs"},
                versions={"uc.catalogs.list": "2.1"},
            )

    def test_unknown_operation_raises_at_development_time(self):
        # The spec scenario (Version-Pinned UC Paths): a caller naming an
        # operation absent from the map fails HERE, never against a live
        # workspace.
        with pytest.raises(ValueError, match="Unknown Databricks API operation"):
            api_paths.path("uc.nonexistent.read")


class NoInlinePathLiteralTests(SimpleTestCase):
    """Callers reference operations by name — never inline URLs.

    The scan covers the WHOLE hub production tree (the 1.8 review fix:
    the first version walked only databricks_admin and silently missed
    the marketplace connector — the only real violator). One enumerated,
    RATCHETED exemption exists: the marketplace connector's own HTTP
    stack (task 1.7 replaces it with the control-plane client + this pin
    map, which is exactly why its literals are pre-registered here) —
    the discovered offenders MUST equal the allowlist, so neither a new
    violator anywhere in hub/ nor a stale allowlist entry can pass.
    """

    # 1.7 debt — ``integrations/connectors/databricks_connector.py``
    # embeds its own transport's inline UC paths. The 1.7 delegation
    # moves them onto ``DatabricksApiClient`` + this pin map; every
    # literal removed there must shrink this set or the ratchet fails.
    ALLOWED_INLINE_PATH_MODULES = frozenset(
        {"apps/integrations/connectors/databricks_connector.py"}
    )

    def test_no_inline_api_path_literals_outside_the_pin_map(self):
        hub_apps_dir = Path(api_paths.__file__).resolve().parent.parent
        offenders: dict[str, list[str]] = {}
        pattern = re.compile(r"""['"]/api/2\.\d/""")
        for module in sorted(hub_apps_dir.rglob("*.py")):
            rel = str(module.relative_to(hub_apps_dir.parent))
            if (
                "/tests/" in f"/{rel}"
                or "/migrations/" in f"/{rel}"
                or rel.endswith("/databricks_admin/api_paths.py")
            ):
                continue
            for lineno, line in enumerate(module.read_text().splitlines(), start=1):
                if pattern.search(line):
                    offenders.setdefault(rel, []).append(f"{lineno}: {line.strip()}")

        # The ratchet: discovered offenders must EXACTLY equal the
        # enumerated debt — nothing more, nothing stale.
        assert set(offenders) == set(self.ALLOWED_INLINE_PATH_MODULES), (
            "version-pinned paths live ONLY in api_paths.py (plus the "
            f"enumerated 1.7 marketplace-connector debt). Offenders: {sorted(offenders)}; "
            f"allowlist: {sorted(self.ALLOWED_INLINE_PATH_MODULES)}"
        )

    def test_the_marketplace_debt_is_real_and_enumerated(self):
        # The allowlist must point at a real file that still embeds the
        # literals — an empty/imaginary allowlist is the ratchet's other
        # failure mode (1.7's DONE will shrink it as the literals die).
        hub_apps_dir = Path(api_paths.__file__).resolve().parent.parent
        for rel in self.ALLOWED_INLINE_PATH_MODULES:
            module = hub_apps_dir.parent / rel
            assert module.is_file(), f"allowlisted module missing: {rel}"
            text = module.read_text()
            assert re.search(r"""['"]/api/2\.\d/""", text), (
                f"allowlisted module no longer embeds inline paths — "
                f"remove {rel} from the 1.7-debt allowlist"
            )
