"""
Unit tests for ODPSNormalizerV4_2

Tests verify:
1. Version support detection (supports 4.2, rejects 4.1/4.0/3.x)
2. paymentGateways with currency/provider mapping
3. productStrategy.kpi with target/unit mapping
4. Graceful handling when optional fields are absent
5. Integration with base + v4.1 inheritance
"""

from django.test import TestCase

from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType

_OK_STATUSES = (NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS)
from hub.apps.contracts.normalization.odps_normalizer_v4_2 import ODPSNormalizerV4_2


def _minimal_v42(extra_product=None):
    """Build a minimal valid ODPS 4.2 contract dict."""
    contract = {
        "schema": "https://opendataproducts.org/schema/v4.2",
        "version": "4.2",
        "product": {
            "details": {"en": {"productID": "test-product", "name": "Test Product 4.2"}},
            "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
        },
    }
    if extra_product:
        contract["product"].update(extra_product)
    return contract


class ODPSNormalizerV4_2StructureTest(TestCase):
    """Test structure, inheritance, and version support."""

    def setUp(self):
        self.normalizer = ODPSNormalizerV4_2()

    def test_inherits_from_v4_1(self):
        from hub.apps.contracts.normalization.odps_normalizer_v4_1 import ODPSNormalizerV4_1
        self.assertIsInstance(self.normalizer, ODPSNormalizerV4_1)

    def test_has_spec_type_odps(self):
        self.assertEqual(self.normalizer.spec_type, OriginalSpecType.ODPS)

    def test_supports_version_4_2(self):
        self.assertTrue(self.normalizer._supports_version("4.2"))

    def test_does_not_support_4_1(self):
        self.assertFalse(self.normalizer._supports_version("4.1"))

    def test_does_not_support_4_0(self):
        self.assertFalse(self.normalizer._supports_version("4.0"))

    def test_does_not_support_3_x(self):
        self.assertFalse(self.normalizer._supports_version("3.x"))

    def test_supports_via_public_api(self):
        data = {"schema": "https://opendataproducts.org/schema/v4.2", "version": "4.2"}
        self.assertTrue(self.normalizer.supports(OriginalSpecType.ODPS, "4.2", data))
        self.assertFalse(self.normalizer.supports(OriginalSpecType.ODPS, "4.1", data))


class ODPSNormalizerV4_2BasicTest(TestCase):
    """Test basic normalization."""

    def setUp(self):
        self.normalizer = ODPSNormalizerV4_2()

    def test_normalize_minimal_contract(self):
        result = self.normalizer.normalize(_minimal_v42())
        self.assertIn(result.status, _OK_STATUSES)
        self.assertIsNotNone(result.hub_contract)
        self.assertEqual(result.spec_version, "4.2")

    def test_product_name_mapped(self):
        result = self.normalizer.normalize(_minimal_v42())
        self.assertEqual(result.hub_contract["info"]["name"], "Test Product 4.2")


class ODPSNormalizerV4_2PaymentGatewaysTest(TestCase):
    """Test paymentGateways currency/provider mapping."""

    def setUp(self):
        self.normalizer = ODPSNormalizerV4_2()

    def test_payment_gateways_mapped(self):
        data = _minimal_v42(extra_product={
            "marketplace": {
                "paymentGateways": [
                    {"currency": "USD", "provider": "Stripe", "enabled": True},
                    {"currency": "EUR", "provider": "PayPal"},
                ],
            },
        })
        result = self.normalizer.normalize(data)
        self.assertIn(result.status, _OK_STATUSES)
        gws = result.hub_contract.get("pricing", {}).get("payment_gateways", [])
        self.assertEqual(len(gws), 2)
        self.assertEqual(gws[0]["currency"], "USD")
        self.assertEqual(gws[0]["provider"], "Stripe")
        self.assertTrue(gws[0]["enabled"])
        self.assertEqual(gws[1]["currency"], "EUR")
        self.assertEqual(gws[1]["provider"], "PayPal")

    def test_no_payment_gateways_no_error(self):
        """Absent paymentGateways should not raise."""
        result = self.normalizer.normalize(_minimal_v42())
        self.assertIn(result.status, _OK_STATUSES)
        # pricing may or may not exist, but no KeyError
        self.assertIsNotNone(result.hub_contract)

    def test_empty_payment_gateways_list(self):
        data = _minimal_v42(extra_product={
            "marketplace": {"paymentGateways": []},
        })
        result = self.normalizer.normalize(data)
        self.assertIn(result.status, _OK_STATUSES)


class ODPSNormalizerV4_2ProductStrategyKPITest(TestCase):
    """Test productStrategy.kpi target/unit mapping."""

    def setUp(self):
        self.normalizer = ODPSNormalizerV4_2()

    def test_kpi_target_unit_mapped(self):
        data = _minimal_v42(extra_product={
            "productStrategy": {
                "kpi": [
                    {"name": "DAU", "target": 10000, "unit": "users/day"},
                    {"name": "Latency", "target": 50, "unit": "ms"},
                ],
            },
        })
        result = self.normalizer.normalize(data)
        self.assertIn(result.status, _OK_STATUSES)
        kpis = result.hub_contract.get("strategy", {}).get("kpis", [])
        self.assertEqual(len(kpis), 2)
        self.assertEqual(kpis[0]["target"], 10000)
        self.assertEqual(kpis[0]["unit"], "users/day")
        self.assertEqual(kpis[0]["name"], "DAU")
        self.assertEqual(kpis[1]["target"], 50)
        self.assertEqual(kpis[1]["unit"], "ms")

    def test_no_kpi_no_error(self):
        """Absent productStrategy.kpi should not raise."""
        result = self.normalizer.normalize(_minimal_v42())
        self.assertIn(result.status, _OK_STATUSES)

    def test_empty_kpi_list(self):
        data = _minimal_v42(extra_product={
            "productStrategy": {"kpi": []},
        })
        result = self.normalizer.normalize(data)
        self.assertIn(result.status, _OK_STATUSES)


class ODPSNormalizerV4_2RegistryTest(TestCase):
    """Test that v4.2 normalizer is registered and discoverable."""

    def test_get_normalizer_returns_v4_2(self):
        from hub.apps.contracts.normalization_engine import get_normalizer
        normalizer = get_normalizer("ODPS", "4.2", {})
        self.assertIsNotNone(normalizer, "No normalizer found for ODPS 4.2")
        self.assertIsInstance(normalizer, ODPSNormalizerV4_2)
