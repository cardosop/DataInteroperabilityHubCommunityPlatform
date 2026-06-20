"""
Phase 82.2 — ABAC Engine tests.

Tests policy evaluation, condition matching, caching, field-level access,
and deny-overrides-allow semantics.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase

from hub.apps.governance.abac import ABACEngine, PolicyEvaluationResult

# ── Helpers ──────────────────────────────────────────────────────────


def _mock_policy(
    effect="ALLOW",
    conditions=None,
    enabled=True,
    priority=10,
    asset_id=None,
    dataset_id=None,
):
    """Create a MagicMock that behaves like an AccessPolicy."""
    p = MagicMock()
    p.id = uuid.uuid4()
    p.effect = effect
    p.conditions = conditions or {}
    p.enabled = enabled
    p.priority = priority
    p.asset_id = asset_id
    p.dataset_id = dataset_id
    return p


def _mock_field_policy(
    access_type="READ",
    masking_strategy=None,
    enabled=True,
):
    fp = MagicMock()
    fp.access_type = access_type
    fp.masking_strategy = masking_strategy
    fp.enabled = enabled
    return fp


_USER_ATTRS = {
    "user_id": "u1",
    "user_roles": ["DATA_CONSUMER"],
    "email": "u@test.com",
}
_RES_ATTRS = {
    "resource_type": "ASSET",
    "resource_id": "r1",
    "tenant_id": "t1",
}
_ENV_ATTRS = {
    "timestamp": "2026-03-19T12:00:00",
    "time_of_day": 12,
    "day_of_week": 3,
}


# ── _evaluate_conditions tests ───────────────────────────────────────


class EvaluateConditionsTest(TestCase):
    """Tests for ABACEngine._evaluate_conditions (pure logic, no DB)."""

    def test_empty_conditions_always_match(self):
        assert (
            ABACEngine._evaluate_conditions(
                {},
                _USER_ATTRS,
                _RES_ATTRS,
                _ENV_ATTRS,
            )
            is True
        )

    def test_user_role_match(self):
        conditions = {"user": {"user_roles": ["DATA_CONSUMER"]}}
        assert (
            ABACEngine._evaluate_conditions(
                conditions,
                _USER_ATTRS,
                _RES_ATTRS,
                _ENV_ATTRS,
            )
            is True
        )

    def test_user_role_mismatch(self):
        conditions = {"user": {"user_roles": ["TENANT_ADMIN"]}}
        assert (
            ABACEngine._evaluate_conditions(
                conditions,
                _USER_ATTRS,
                _RES_ATTRS,
                _ENV_ATTRS,
            )
            is False
        )

    def test_resource_type_matching(self):
        conditions = {"resource": {"type": "ASSET"}}
        assert (
            ABACEngine._evaluate_conditions(
                conditions,
                _USER_ATTRS,
                _RES_ATTRS,
                _ENV_ATTRS,
            )
            is True
        )

    def test_resource_type_mismatch(self):
        conditions = {"resource": {"type": "DATASET"}}
        assert (
            ABACEngine._evaluate_conditions(
                conditions,
                _USER_ATTRS,
                _RES_ATTRS,
                _ENV_ATTRS,
            )
            is False
        )

    def test_resource_classification_matching(self):
        res = {**_RES_ATTRS, "classification": "PII"}
        conditions = {"resource": {"classification": "PII"}}
        assert (
            ABACEngine._evaluate_conditions(
                conditions,
                _USER_ATTRS,
                res,
                _ENV_ATTRS,
            )
            is True
        )

    def test_environment_time_range(self):
        conditions = {
            "environment": {
                "time_of_day": {"$gte": 9, "$lte": 17},
            },
        }
        assert (
            ABACEngine._evaluate_conditions(
                conditions,
                _USER_ATTRS,
                _RES_ATTRS,
                _ENV_ATTRS,
            )
            is True
        )

    def test_environment_time_outside_range(self):
        env = {**_ENV_ATTRS, "time_of_day": 3}
        conditions = {
            "environment": {
                "time_of_day": {"$gte": 9, "$lte": 17},
            },
        }
        assert (
            ABACEngine._evaluate_conditions(
                conditions,
                _USER_ATTRS,
                _RES_ATTRS,
                env,
            )
            is False
        )

    def test_missing_user_attribute_returns_false(self):
        conditions = {"user": {"department": "IT"}}
        assert (
            ABACEngine._evaluate_conditions(
                conditions,
                _USER_ATTRS,
                _RES_ATTRS,
                _ENV_ATTRS,
            )
            is False
        )

    def test_resource_type_top_level_condition(self):
        """resource_type at top level (not inside 'resource')."""
        conditions = {"resource_type": "ASSET"}
        assert (
            ABACEngine._evaluate_conditions(
                conditions,
                _USER_ATTRS,
                _RES_ATTRS,
                _ENV_ATTRS,
            )
            is True
        )


# ── evaluate_access tests (with mocked policies) ────────────────────


@pytest.mark.django_db(transaction=True)
class EvaluateAccessTest(TestCase):
    """Tests for ABACEngine.evaluate_access with mocked policy lookups."""

    @patch.object(ABACEngine, "_get_environment_attributes", return_value=_ENV_ATTRS)
    @patch.object(ABACEngine, "_get_resource_attributes", return_value=_RES_ATTRS)
    @patch.object(ABACEngine, "_get_applicable_policies")
    def test_allow_grants_access(self, mock_policies, *_):
        mock_policies.return_value = [
            _mock_policy(effect="ALLOW", conditions={}),
        ]
        result = ABACEngine.evaluate_access(
            "u1",
            "t1",
            "ASSET",
            "r1",
            user_attributes=_USER_ATTRS,
        )
        assert result.allowed is True

    @patch.object(ABACEngine, "_get_environment_attributes", return_value=_ENV_ATTRS)
    @patch.object(ABACEngine, "_get_resource_attributes", return_value=_RES_ATTRS)
    @patch.object(ABACEngine, "_get_applicable_policies")
    def test_deny_blocks_access(self, mock_policies, *_):
        mock_policies.return_value = [
            _mock_policy(effect="DENY", conditions={}),
        ]
        result = ABACEngine.evaluate_access(
            "u1",
            "t1",
            "ASSET",
            "r1",
            user_attributes=_USER_ATTRS,
        )
        assert result.allowed is False

    @patch.object(ABACEngine, "_get_environment_attributes", return_value=_ENV_ATTRS)
    @patch.object(ABACEngine, "_get_resource_attributes", return_value=_RES_ATTRS)
    @patch.object(ABACEngine, "_get_applicable_policies")
    def test_deny_overrides_allow_by_priority(self, mock_policies, *_):
        """DENY at lower priority number (=higher priority) wins."""
        mock_policies.return_value = [
            _mock_policy(effect="DENY", conditions={}, priority=1),
            _mock_policy(effect="ALLOW", conditions={}, priority=10),
        ]
        result = ABACEngine.evaluate_access(
            "u1",
            "t1",
            "ASSET",
            "r1",
            user_attributes=_USER_ATTRS,
        )
        assert result.allowed is False

    @patch.object(ABACEngine, "_get_environment_attributes", return_value=_ENV_ATTRS)
    @patch.object(ABACEngine, "_get_resource_attributes", return_value=_RES_ATTRS)
    @patch.object(ABACEngine, "_get_applicable_policies")
    def test_no_match_defaults_deny(self, mock_policies, *_):
        mock_policies.return_value = []
        result = ABACEngine.evaluate_access(
            "u1",
            "t1",
            "ASSET",
            "r1",
            user_attributes=_USER_ATTRS,
        )
        assert result.allowed is False

    @patch.object(ABACEngine, "_get_environment_attributes", return_value=_ENV_ATTRS)
    @patch.object(ABACEngine, "_get_resource_attributes", return_value=_RES_ATTRS)
    @patch.object(ABACEngine, "_get_applicable_policies")
    def test_disabled_policy_ignored(self, mock_policies, *_):
        mock_policies.return_value = [
            _mock_policy(effect="ALLOW", conditions={}, enabled=False),
        ]
        result = ABACEngine.evaluate_access(
            "u1",
            "t1",
            "ASSET",
            "r1",
            user_attributes=_USER_ATTRS,
        )
        assert result.allowed is False  # Falls through to default deny

    @patch.object(ABACEngine, "_get_environment_attributes", return_value=_ENV_ATTRS)
    @patch.object(ABACEngine, "_get_resource_attributes", return_value=_RES_ATTRS)
    @patch.object(ABACEngine, "_get_applicable_policies")
    def test_condition_mismatch_skips_policy(self, mock_policies, *_):
        """Policy with non-matching conditions is skipped."""
        mock_policies.return_value = [
            _mock_policy(
                effect="ALLOW",
                conditions={"user": {"user_roles": ["TENANT_ADMIN"]}},
            ),
        ]
        result = ABACEngine.evaluate_access(
            "u1",
            "t1",
            "ASSET",
            "r1",
            user_attributes=_USER_ATTRS,
        )
        assert result.allowed is False  # No matching policy → deny

    @patch.object(ABACEngine, "_get_environment_attributes", return_value=_ENV_ATTRS)
    @patch.object(ABACEngine, "_get_resource_attributes", return_value=_RES_ATTRS)
    @patch.object(ABACEngine, "_get_applicable_policies")
    def test_environment_attributes_passed(self, mock_policies, *_):
        """Custom environment attributes are used for evaluation."""
        mock_policies.return_value = [
            _mock_policy(
                effect="ALLOW",
                conditions={
                    "environment": {
                        "time_of_day": {"$gte": 9, "$lte": 17},
                    },
                },
            ),
        ]
        result = ABACEngine.evaluate_access(
            "u1",
            "t1",
            "ASSET",
            "r1",
            user_attributes=_USER_ATTRS,
            environment_attributes=_ENV_ATTRS,
        )
        assert result.allowed is True


# ── Field-level access tests ─────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
class FieldLevelAccessTest(TestCase):
    """Tests for field-level access and masking detection."""

    @patch.object(ABACEngine, "_get_field_policies")
    @patch.object(ABACEngine, "_get_environment_attributes", return_value=_ENV_ATTRS)
    @patch.object(
        ABACEngine,
        "_get_resource_attributes",
        return_value={**_RES_ATTRS, "resource_type": "DATASET"},
    )
    @patch.object(ABACEngine, "_get_applicable_policies")
    def test_field_level_masking_detected(
        self,
        mock_policies,
        _res,
        _env,
        mock_fp,
    ):
        """When field policy has masking, result.masking_required is True."""
        allow_policy = _mock_policy(effect="ALLOW", conditions={})
        mock_policies.return_value = [allow_policy]
        mock_fp.return_value = (
            [_mock_field_policy(masking_strategy="HASH")],
            True,
        )
        result = ABACEngine.evaluate_access(
            "u1",
            "t1",
            "DATASET",
            "r1",
            field_name="ssn",
            user_attributes=_USER_ATTRS,
        )
        assert result.allowed is True
        assert result.masking_required is True

    @patch.object(ABACEngine, "_get_field_policies")
    @patch.object(ABACEngine, "_get_environment_attributes", return_value=_ENV_ATTRS)
    @patch.object(
        ABACEngine,
        "_get_resource_attributes",
        return_value={**_RES_ATTRS, "resource_type": "DATASET"},
    )
    @patch.object(ABACEngine, "_get_applicable_policies")
    def test_field_access_denied_returns_false(
        self,
        mock_policies,
        _res,
        _env,
        mock_fp,
    ):
        """Field policy returning ([], True) denies access."""
        allow_policy = _mock_policy(effect="ALLOW", conditions={})
        mock_policies.return_value = [allow_policy]
        mock_fp.return_value = ([], True)  # Deny
        result = ABACEngine.evaluate_access(
            "u1",
            "t1",
            "DATASET",
            "r1",
            field_name="ssn",
            user_attributes=_USER_ATTRS,
        )
        assert result.allowed is False


# ── Cache behaviour tests ────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
class ABACCacheTest(TestCase):
    """Tests for policy cache population and invalidation."""

    def _create_tenant(self):
        from hub.apps.tenants.models import Tenant

        return Tenant.objects.get_or_create(
            name="abac-cache-test",
            defaults={"slug": "abac-cache-test"},
        )[0]

    @patch("hub.apps.governance.abac.cache")
    def test_cache_populated_after_first_eval(self, mock_cache):
        """After DB lookup, policy IDs are written to cache."""
        mock_cache.get.return_value = None  # Cache miss
        tenant = self._create_tenant()
        ABACEngine._get_applicable_policies(
            str(tenant.id),
            "ASSET",
            str(uuid.uuid4()),
        )
        mock_cache.set.assert_called_once()

    @patch("hub.apps.governance.abac.cache")
    def test_cache_hit_skips_db(self, mock_cache):
        """When cache has policy IDs, DB query still happens
        (to fetch full objects) but cache.set is NOT called."""
        mock_cache.get.side_effect = [
            0,  # version lookup
            ["id1"],  # policy IDs from cache
        ]
        with patch("hub.apps.governance.models.AccessPolicy.objects") as mock_qs:
            mock_qs.filter.return_value.order_by.return_value = []
            ABACEngine._get_applicable_policies("t1", "ASSET", "r1")
        # cache.set should NOT be called when cache hit
        mock_cache.set.assert_not_called()

    def test_invalidate_deletes_scoped_key(self):
        """invalidate_policy_cache with resource deletes scoped key."""
        from django.core.cache import cache

        tenant = self._create_tenant()
        tid = str(tenant.id)
        rid = str(uuid.uuid4())
        key = ABACEngine._get_cache_key(tid, "ASSET", rid)
        cache.set(key, ["policy-1"], 60)
        ABACEngine.invalidate_policy_cache(tid, "ASSET", rid)
        assert cache.get(key) is None

    def test_invalidate_tenant_increments_version(self):
        """invalidate_policy_cache without resource bumps version."""
        from django.core.cache import cache

        tenant = self._create_tenant()
        tid = str(tenant.id)
        version_key = f"abac_cache_version_{tid}"
        cache.set(version_key, 5, timeout=None)
        ABACEngine.invalidate_policy_cache(tid)
        assert cache.get(version_key) == 6


# ── PolicyEvaluationResult tests ─────────────────────────────────────


class PolicyEvaluationResultTest(TestCase):
    """Tests for PolicyEvaluationResult data class."""

    def test_allowed_result(self):
        r = PolicyEvaluationResult(allowed=True)
        assert r.allowed is True
        assert r.policy is None
        assert r.field_policies == []
        assert r.masking_required is False

    def test_denied_result_with_policy(self):
        p = _mock_policy(effect="DENY")
        r = PolicyEvaluationResult(allowed=False, policy=p)
        assert r.allowed is False
        assert r.policy is p
