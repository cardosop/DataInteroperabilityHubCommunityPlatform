"""
Unit tests for ODCSNormalizerV3_1_0.

Tests the version-specific normalizer for ODCS 3.1.0 including:
- Version support checking (exact 3.1.0 and semver 3.1.x)
- team restructure: object {members:[...]} → info.owners + team
- exclusiveMaximum/exclusiveMinimum type change (bool vs numeric)
- slaDefaultElement removal with deprecation warning
- Fallback: unknown 3.x versions now fall back to v3.1.0
- Backward compatibility: v3.0.x array team still works via base
"""

import copy
from unittest import TestCase

from hub.apps.contracts.models import (
    NormalizationStatus,
    OriginalSpecType,
)
from hub.apps.contracts.normalization import (
    NormalizationResult,
    _NORMALIZER_REGISTRY,
    _reset_normalizer_registry,
    get_normalizer,
    register_normalizer,
)
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_2 import (
    ODCSNormalizerV3_0_2,
)
from hub.apps.contracts.normalization.odcs_normalizer_v3_1_0 import (
    ODCSNormalizerV3_1_0,
)


# -- Minimal valid contract fixtures ------------------------------------

def _base_contract_v31(**overrides):
    """Return a minimal valid ODCS v3.1.0 contract dict."""
    c = {
        "apiVersion": "odcs.io/v3.1.0",
        "kind": "DataContract",
        "id": "test-v31",
        "name": "V3.1 Contract",
        "version": "1.0.0",
        "schema": {
            "fields": [
                {"name": "id", "type": "integer", "nullable": False},
                {"name": "value", "type": "string"},
            ],
        },
    }
    c.update(overrides)
    return c


def _base_contract_v302(**overrides):
    """Return a minimal valid ODCS v3.0.2 contract dict."""
    c = {
        "apiVersion": "odcs.io/v3.0.2",
        "kind": "DataContract",
        "id": "test-v302",
        "name": "V3.0.2 Contract",
        "version": "1.0.0",
        "schema": {
            "fields": [
                {"name": "id", "type": "integer", "nullable": False},
            ],
        },
    }
    c.update(overrides)
    return c


# ======================================================================
# 26.1.1 — Structure & version support
# ======================================================================

class ODCSNormalizerV3_1_0StructureTest(TestCase):
    """Basic structure tests."""

    def test_can_instantiate(self):
        normalizer = ODCSNormalizerV3_1_0()
        assert normalizer is not None

    def test_spec_type_is_odcs(self):
        normalizer = ODCSNormalizerV3_1_0()
        assert normalizer.spec_type == OriginalSpecType.ODCS


class ODCSNormalizerV3_1_0SupportsTest(TestCase):
    """Test _supports_version / supports."""

    def setUp(self):
        self.normalizer = ODCSNormalizerV3_1_0()

    def test_supports_exact_3_1_0(self):
        assert self.normalizer.supports(
            OriginalSpecType.ODCS, "3.1.0", {}
        ) is True

    def test_supports_3_1_x_semver(self):
        assert self.normalizer.supports(
            OriginalSpecType.ODCS, "3.1.1", {}
        ) is True
        assert self.normalizer.supports(
            OriginalSpecType.ODCS, "3.1.99", {}
        ) is True

    def test_does_not_support_3_0_2(self):
        assert self.normalizer.supports(
            OriginalSpecType.ODCS, "3.0.2", {}
        ) is False

    def test_does_not_support_4_0_0(self):
        assert self.normalizer.supports(
            OriginalSpecType.ODCS, "4.0.0", {}
        ) is False

    def test_does_not_support_none(self):
        assert self.normalizer.supports(
            OriginalSpecType.ODCS, None, {}
        ) is False

    def test_does_not_support_odps(self):
        assert self.normalizer.supports(
            OriginalSpecType.ODPS, "3.1.0", {}
        ) is False


class ODCSNormalizerV3_1_0NormalizeBasicTest(TestCase):
    """Basic normalization smoke tests."""

    def setUp(self):
        self.normalizer = ODCSNormalizerV3_1_0()

    def test_normalize_returns_result(self):
        result = self.normalizer.normalize(
            _base_contract_v31(), spec_version="3.1.0"
        )
        # NormalizationResult may be loaded via importlib (dual-module)
        # so isinstance can fail; check by attribute instead.
        assert hasattr(result, "hub_contract")
        assert hasattr(result, "status")
        assert hasattr(result, "errors")
        assert hasattr(result, "warnings")
        assert hasattr(result, "spec_type")
        assert hasattr(result, "spec_version")
        assert result.spec_type == OriginalSpecType.ODCS
        assert result.spec_version == "3.1.0"

    def test_normalize_produces_valid_hub_contract(self):
        result = self.normalizer.normalize(
            _base_contract_v31(), spec_version="3.1.0"
        )
        assert result.hub_contract is not None
        assert result.hub_contract["info"]["name"] == "V3.1 Contract"
        assert len(result.hub_contract["schema"]["fields"]) == 2

    def test_normalize_detects_version_from_apiVersion(self):
        result = self.normalizer.normalize(
            _base_contract_v31(), spec_version=None
        )
        assert result.spec_version == "3.1.0"

    def test_normalize_fails_for_unsupported_version(self):
        result = self.normalizer.normalize(
            _base_contract_v31(), spec_version="3.0.2"
        )
        assert result.status == NormalizationStatus.NORMALIZATION_FAILED
        assert any("not support" in e.lower() for e in result.errors)

    def test_normalize_fails_for_non_dict(self):
        result = self.normalizer.normalize("bad", spec_version="3.1.0")
        assert result.status == NormalizationStatus.NORMALIZATION_FAILED


# ======================================================================
# 26.1.2 — team restructure (array → object)
# ======================================================================

class TeamV31ObjectTest(TestCase):
    """Test v3.1.0 team object {members: [...]} handling."""

    def setUp(self):
        self.normalizer = ODCSNormalizerV3_1_0()

    def test_team_object_mapped_to_owners_and_team(self):
        """v3.1.0 team object should populate info.owners and team."""
        contract = _base_contract_v31(team={
            "members": [
                {
                    "name": "Alice",
                    "email": "alice@example.com",
                    "role": "owner",
                    "id": "u-001",
                    "description": "Data steward",
                },
                {
                    "name": "Bob",
                    "email": "bob@example.com",
                    "role": "contributor",
                },
            ]
        })
        result = self.normalizer.normalize(contract, spec_version="3.1.0")
        hc = result.hub_contract
        assert hc is not None

        # info.owners populated
        owners = hc["info"]["owners"]
        assert len(owners) == 2
        assert owners[0]["name"] == "Alice"
        assert owners[0]["email"] == "alice@example.com"
        assert owners[1]["name"] == "Bob"

        # team list populated
        team = hc.get("team")
        assert team is not None
        assert len(team) == 2

    def test_team_object_empty_members_warns(self):
        """team object with empty members should produce a warning."""
        contract = _base_contract_v31(team={"members": []})
        result = self.normalizer.normalize(contract, spec_version="3.1.0")
        # Warning comes from base _normalize_roles_team_pricing
        assert any(
            "no valid" in w.lower() or "members" in w.lower()
            for w in result.warnings
        ), f"Expected team-empty warning, got: {result.warnings}"

    def test_team_object_preserves_extra_fields(self):
        """Extra fields in team members should be preserved."""
        contract = _base_contract_v31(team={
            "members": [
                {
                    "name": "Carol",
                    "email": "carol@example.com",
                    "role": "admin",
                    "department": "engineering",
                }
            ]
        })
        result = self.normalizer.normalize(contract, spec_version="3.1.0")
        hc = result.hub_contract
        assert hc is not None
        team = hc.get("team", [])
        assert len(team) >= 1
        # Extra field should be preserved
        found = [m for m in team if m.get("department") == "engineering"]
        assert len(found) == 1


class TeamV30ArrayCompatTest(TestCase):
    """
    Test that v3.0.x array team still works in all normalizers,
    and that base normalizer handles mixed v3.1.0 team objects.
    """

    def test_v302_normalizer_handles_v31_team_object(self):
        """
        If a v3.0.2 contract somehow has a v3.1.0-style team object,
        the base normalizer should gracefully handle it.
        """
        normalizer = ODCSNormalizerV3_0_2()
        contract = _base_contract_v302(team={
            "members": [
                {"name": "Alice", "email": "a@b.com", "role": "owner"}
            ]
        })
        result = normalizer.normalize(contract, spec_version="3.0.2")
        hc = result.hub_contract
        assert hc is not None
        # Team should be parsed
        team = hc.get("team")
        assert team is not None
        assert len(team) == 1
        # Owners should be populated
        owners = hc.get("info", {}).get("owners", [])
        assert len(owners) == 1
        assert owners[0]["name"] == "Alice"

    def test_v31_normalizer_handles_v30_array_team(self):
        """
        If a v3.1.0 contract has old-style array team,
        the base normalizer handles it (before version-specific hook).
        """
        normalizer = ODCSNormalizerV3_1_0()
        contract = _base_contract_v31(team=[
            {"member": "Alice", "role": "owner"},
        ])
        result = normalizer.normalize(contract, spec_version="3.1.0")
        hc = result.hub_contract
        assert hc is not None
        team = hc.get("team")
        assert team is not None
        assert len(team) == 1


class ParseTeamV31HelperTest(TestCase):
    """Direct unit tests for _parse_team_v31 (inherited from base)."""

    def test_basic_parse(self):
        # _parse_team_v31 is inherited from ODCSNormalizerBase
        result = ODCSNormalizerV3_1_0._parse_team_v31({
            "members": [
                {"name": "A", "email": "a@b.com", "role": "admin"}
            ]
        })
        assert len(result) == 1
        assert result[0]["name"] == "A"
        assert result[0]["member"] == "A"
        assert result[0]["email"] == "a@b.com"
        assert result[0]["role"] == "admin"

    def test_empty_members(self):
        assert ODCSNormalizerV3_1_0._parse_team_v31({"members": []}) == []

    def test_no_members_key(self):
        assert ODCSNormalizerV3_1_0._parse_team_v31({}) == []

    def test_members_not_list(self):
        assert ODCSNormalizerV3_1_0._parse_team_v31(
            {"members": "invalid"}
        ) == []

    def test_skips_non_dict_entries(self):
        result = ODCSNormalizerV3_1_0._parse_team_v31({
            "members": [
                {"name": "A"},
                "bad-entry",
                42,
                {"name": "B"},
            ]
        })
        assert len(result) == 2

    def test_preserves_id_and_description(self):
        result = ODCSNormalizerV3_1_0._parse_team_v31({
            "members": [
                {
                    "name": "X",
                    "id": "u-99",
                    "description": "lead",
                }
            ]
        })
        assert result[0]["id"] == "u-99"
        assert result[0]["description"] == "lead"


# ======================================================================
# 26.1.3 — exclusiveMaximum / exclusiveMinimum type change
# ======================================================================

class ExclusiveBoundsTest(TestCase):
    """Test logicalTypeOptions exclusive bound normalization."""

    def setUp(self):
        self.normalizer = ODCSNormalizerV3_1_0()

    def test_numeric_exclusive_bounds_wrapped(self):
        """Numeric exclusive bounds should be wrapped."""
        contract = _base_contract_v31(schema={
            "fields": [
                {
                    "name": "score",
                    "type": "number",
                    "logicalTypeOptions": {
                        "exclusiveMaximum": 100,
                        "exclusiveMinimum": 0,
                        "scale": 2,
                    },
                },
            ],
        })
        result = self.normalizer.normalize(contract, spec_version="3.1.0")
        hc = result.hub_contract
        assert hc is not None

        # Find the score field in schema or models
        fields = hc.get("schema", {}).get("fields", [])
        score_fields = [f for f in fields if f.get("name") == "score"]
        assert len(score_fields) == 1
        lto = score_fields[0].get("logicalTypeOptions", {})
        assert lto["exclusiveMaximum"] == {
            "value": 100, "type": "numeric_bound"
        }
        assert lto["exclusiveMinimum"] == {
            "value": 0, "type": "numeric_bound"
        }
        # Non-exclusive fields preserved as-is
        assert lto["scale"] == 2

    def test_boolean_exclusive_bounds_kept_as_is(self):
        """Boolean exclusive bounds (v3.0.x compat) should be kept."""
        contract = _base_contract_v31(schema={
            "fields": [
                {
                    "name": "score",
                    "type": "number",
                    "logicalTypeOptions": {
                        "exclusiveMaximum": True,
                        "exclusiveMinimum": False,
                    },
                },
            ],
        })
        result = self.normalizer.normalize(contract, spec_version="3.1.0")
        hc = result.hub_contract
        assert hc is not None

        fields = hc.get("schema", {}).get("fields", [])
        score_fields = [f for f in fields if f.get("name") == "score"]
        assert len(score_fields) == 1
        lto = score_fields[0].get("logicalTypeOptions", {})
        assert lto["exclusiveMaximum"] is True
        assert lto["exclusiveMinimum"] is False

    def test_float_exclusive_bound_wrapped(self):
        """Float exclusive bounds should also be wrapped."""
        contract = _base_contract_v31(schema={
            "fields": [
                {
                    "name": "pct",
                    "type": "number",
                    "logicalTypeOptions": {
                        "exclusiveMaximum": 99.99,
                    },
                },
            ],
        })
        result = self.normalizer.normalize(contract, spec_version="3.1.0")
        hc = result.hub_contract
        fields = hc.get("schema", {}).get("fields", [])
        pct = [f for f in fields if f.get("name") == "pct"][0]
        lto = pct.get("logicalTypeOptions", {})
        assert lto["exclusiveMaximum"] == {
            "value": 99.99, "type": "numeric_bound"
        }

    def test_no_logical_type_options_no_error(self):
        """Fields without logicalTypeOptions should not error."""
        contract = _base_contract_v31()
        result = self.normalizer.normalize(contract, spec_version="3.1.0")
        assert result.hub_contract is not None


class ExclusiveBoundsMigrationGuardTest(TestCase):
    """
    Migration guard: v3.0.x contracts with boolean exclusiveMaximum
    should NOT be re-interpreted as numeric bounds.
    """

    def test_v302_boolean_exclusive_bounds_preserved(self):
        """v3.0.2 normalizer should preserve boolean exclusive bounds."""
        normalizer = ODCSNormalizerV3_0_2()
        contract = _base_contract_v302(schema={
            "fields": [
                {
                    "name": "amount",
                    "type": "number",
                    "exclusiveMaximum": True,
                    "exclusiveMinimum": False,
                },
            ],
        })
        result = normalizer.normalize(contract, spec_version="3.0.2")
        hc = result.hub_contract
        assert hc is not None
        fields = hc.get("schema", {}).get("fields", [])
        amt = [f for f in fields if f.get("name") == "amount"]
        assert len(amt) == 1
        # Should be preserved as boolean, NOT wrapped
        assert amt[0].get("exclusiveMaximum") is True
        assert amt[0].get("exclusiveMinimum") is False


class NormalizeBoundHelperTest(TestCase):
    """Direct tests for _normalize_exclusive_bound."""

    def test_bool_true(self):
        assert ODCSNormalizerV3_1_0._normalize_exclusive_bound(True) is True

    def test_bool_false(self):
        r = ODCSNormalizerV3_1_0._normalize_exclusive_bound(False)
        assert r is False

    def test_int(self):
        assert ODCSNormalizerV3_1_0._normalize_exclusive_bound(42) == {
            "value": 42, "type": "numeric_bound"
        }

    def test_float(self):
        assert ODCSNormalizerV3_1_0._normalize_exclusive_bound(3.14) == {
            "value": 3.14, "type": "numeric_bound"
        }

    def test_string_passthrough(self):
        # Edge case: unknown type returned as-is
        assert ODCSNormalizerV3_1_0._normalize_exclusive_bound("x") == "x"

    def test_none_passthrough(self):
        assert ODCSNormalizerV3_1_0._normalize_exclusive_bound(None) is None


# ======================================================================
# 26.1.4 — slaDefaultElement removal
# ======================================================================

class SlaDefaultElementTest(TestCase):
    """Test that slaDefaultElement is removed in v3.1.0 with warning."""

    def setUp(self):
        self.normalizer = ODCSNormalizerV3_1_0()

    def test_sla_default_element_emits_warning(self):
        """slaDefaultElement in SLA properties should emit a warning."""
        contract = _base_contract_v31(slaProperties=[
            {
                "name": "availability",
                "property": "uptime",
                "target": "99.9",
                "slaDefaultElement": "99.5",
            },
        ])
        result = self.normalizer.normalize(contract, spec_version="3.1.0")
        assert any(
            "slaDefaultElement" in w and "removed" in w.lower()
            for w in result.warnings
        ), f"Expected slaDefaultElement warning, got: {result.warnings}"

    def test_sla_default_element_in_lifecycle_emits_warning(self):
        """slaDefaultElement nested in lifecycle.slaProperties also warns."""
        contract = _base_contract_v31(lifecycle={
            "slaProperties": [
                {
                    "name": "freshness",
                    "slaDefaultElement": "1h",
                },
            ],
        })
        result = self.normalizer.normalize(contract, spec_version="3.1.0")
        assert any(
            "slaDefaultElement" in w for w in result.warnings
        )

    def test_sla_without_default_element_no_warning(self):
        """SLA properties without slaDefaultElement should not warn."""
        contract = _base_contract_v31(slaProperties=[
            {
                "name": "availability",
                "property": "uptime",
                "target": "99.9",
            },
        ])
        result = self.normalizer.normalize(contract, spec_version="3.1.0")
        assert not any(
            "slaDefaultElement" in w for w in result.warnings
        )

    def test_v302_sla_default_element_still_mapped(self):
        """v3.0.2 normalizer should still map slaDefaultElement."""
        normalizer = ODCSNormalizerV3_0_2()
        contract = _base_contract_v302(slaProperties=[
            {
                "name": "availability",
                "slaDefaultElement": "99.5",
            },
        ])
        result = normalizer.normalize(contract, spec_version="3.0.2")
        hc = result.hub_contract
        assert hc is not None
        sls = hc.get("servicelevels", [])
        assert len(sls) >= 1
        # Should be mapped to "element" in v3.0.2
        assert sls[0].get("element") == "99.5"


# ======================================================================
# Fallback: unknown 3.x → v3.1.0
# ======================================================================

class FallbackToV31Test(TestCase):
    """
    Unknown 3.x versions should fall back to v3.1.0 (current latest)
    instead of v3.0.2.
    """

    def setUp(self):
        self._saved_registry = copy.deepcopy(_NORMALIZER_REGISTRY)

    def tearDown(self):
        _reset_normalizer_registry(self._saved_registry)

    def test_unknown_3x_falls_back_to_v31(self):
        """get_normalizer for '3.2.0' should return V3_1_0 normalizer."""
        normalizer = get_normalizer(
            OriginalSpecType.ODCS, "3.2.0", {}
        )
        assert normalizer is not None
        assert isinstance(normalizer, ODCSNormalizerV3_1_0)

    def test_unknown_3x_patch_falls_back_to_v31(self):
        """get_normalizer for '3.99.0' should return V3_1_0."""
        normalizer = get_normalizer(
            OriginalSpecType.ODCS, "3.99.0", {}
        )
        assert normalizer is not None
        assert isinstance(normalizer, ODCSNormalizerV3_1_0)

    def test_exact_3_1_0_returns_v31(self):
        """get_normalizer for '3.1.0' should return V3_1_0."""
        normalizer = get_normalizer(
            OriginalSpecType.ODCS, "3.1.0", {}
        )
        assert normalizer is not None
        assert isinstance(normalizer, ODCSNormalizerV3_1_0)

    def test_exact_3_0_2_still_returns_v302(self):
        """get_normalizer for '3.0.2' should still return V3_0_2."""
        normalizer = get_normalizer(
            OriginalSpecType.ODCS, "3.0.2", {}
        )
        assert normalizer is not None
        assert isinstance(normalizer, ODCSNormalizerV3_0_2)


# ======================================================================
# Review fixes — regression tests for bugs found during code review
# ======================================================================

class RegexAnchorTest(TestCase):
    """Verify $ anchor on _V3_1_PATTERN rejects pre-release suffixes."""

    def setUp(self):
        self.normalizer = ODCSNormalizerV3_1_0()

    def test_rejects_3_1_0_beta(self):
        assert self.normalizer.supports(
            OriginalSpecType.ODCS, "3.1.0beta", {}
        ) is False

    def test_rejects_3_1_0_rc1(self):
        assert self.normalizer.supports(
            OriginalSpecType.ODCS, "3.1.0-rc1", {}
        ) is False

    def test_rejects_3_1_0_with_trailing_text(self):
        assert self.normalizer.supports(
            OriginalSpecType.ODCS, "3.1.0.alpha", {}
        ) is False

    def test_accepts_clean_semver(self):
        assert self.normalizer.supports(
            OriginalSpecType.ODCS, "3.1.2", {}
        ) is True


class SlaDefaultElementStripsElementTest(TestCase):
    """
    Verify that element is REMOVED from mapped service levels when
    sourced from slaDefaultElement (not a real "element" field).
    """

    def setUp(self):
        self.normalizer = ODCSNormalizerV3_1_0()

    def test_element_removed_when_only_sla_default(self):
        """element should be stripped if only slaDefaultElement existed."""
        contract = _base_contract_v31(slaProperties=[
            {
                "name": "availability",
                "property": "uptime",
                "target": "99.9",
                "slaDefaultElement": "99.5",
            },
        ])
        result = self.normalizer.normalize(contract, spec_version="3.1.0")
        hc = result.hub_contract
        assert hc is not None
        sls = hc.get("servicelevels", [])
        assert len(sls) >= 1
        # element should have been stripped
        assert "element" not in sls[0], (
            f"element should be removed but found: {sls[0]}"
        )
        # warning should be emitted
        assert any(
            "slaDefaultElement" in w for w in result.warnings
        )

    def test_element_preserved_when_real_element_exists(self):
        """element should be kept if source had both element and slaDefaultElement."""
        contract = _base_contract_v31(slaProperties=[
            {
                "name": "availability",
                "element": "real-element-value",
                "slaDefaultElement": "deprecated-value",
            },
        ])
        result = self.normalizer.normalize(contract, spec_version="3.1.0")
        hc = result.hub_contract
        assert hc is not None
        sls = hc.get("servicelevels", [])
        assert len(sls) >= 1
        # element should remain because source had a real "element"
        assert sls[0].get("element") == "real-element-value"


class TeamNoDoubleProcessingTest(TestCase):
    """
    Verify that v3.1.0 team object is NOT processed twice (once by
    base, once by version hook).  The version hook must NOT overwrite
    validated team data with raw data.
    """

    def setUp(self):
        self.normalizer = ODCSNormalizerV3_1_0()

    def test_team_processed_by_base_only(self):
        """
        Team validation enrichment (from base) should be present.
        If the v3.1.0 hook overwrote it, the enriched fields
        would be missing.
        """
        contract = _base_contract_v31(team={
            "members": [
                {
                    "name": "Alice",
                    "email": "alice@example.com",
                    "role": "owner",
                },
            ]
        })
        result = self.normalizer.normalize(contract, spec_version="3.1.0")
        hc = result.hub_contract
        assert hc is not None

        # Team should exist and have passed through
        # validate_and_enrich_team (base processing)
        team = hc.get("team")
        assert team is not None
        assert len(team) >= 1

        # info.owners should be populated (base processing)
        owners = hc.get("info", {}).get("owners", [])
        assert len(owners) >= 1
        assert owners[0]["name"] == "Alice"
