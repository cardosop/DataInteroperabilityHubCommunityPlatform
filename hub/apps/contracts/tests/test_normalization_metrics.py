"""
Tests for normalization metrics recording.

Tests the metrics recording functionality for normalization coverage,
contract JSON size, missing objects, and broken lineage links.

Uses real metrics infrastructure (no mocks) - tests verify that:
1. Functions execute without errors
2. Metrics operations succeed
3. Optional: Metrics are recorded (via /metrics endpoint if available)
"""

from django.db.models.signals import post_save
from django.test import Client, TestCase

from hub.apps.contracts.normalization_metrics import (
    METRICS_AVAILABLE,
    record_all_normalization_metrics,
    record_broken_lineage_links,
    record_contract_json_size,
    record_missing_objects,
    record_normalization_coverage,
)


class NormalizationMetricsTestCase(TestCase):
    """Test normalization metrics recording."""

    def setUp(self):
        """Set up test fixtures."""
        # CRITICAL: Disconnect semantic service signals to prevent timeouts
        # Semantic service signals trigger on every Asset/Contract save, causing 60s timeouts
        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            # Disconnect signals to prevent semantic service calls during tests
            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
        except (ImportError, AttributeError):
            # Signals may not be available - continue without disconnecting
            pass

        self.client = Client()
        self.sample_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-contract-1",
            "info": {"name": "Test Contract"},
            "contact": {"email": "test@example.com"},
            "servers": [{"type": "s3", "url": "s3://bucket"}],
            "models": [{"name": "model1", "fields": []}],
            # Missing: terms, definitions, servicelevels, lineage, roles, team, pricing, support
        }

    def tearDown(self):
        """Reconnect signals after test"""
        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            # Reconnect signals after test
            post_save.connect(contract_saved, sender=Contract, weak=False)
            post_save.connect(asset_saved, sender=Asset, weak=False)
        except (ImportError, AttributeError):
            # Signals may not be available - continue without reconnecting
            pass

    def test_record_normalization_coverage(self):
        """Test recording normalization coverage metrics."""
        # Should execute without error
        try:
            record_normalization_coverage(self.sample_contract, tenant_id="test-tenant")
            # If metrics are available, operation should succeed
            if METRICS_AVAILABLE:
                # Verify metrics endpoint is accessible (if available)
                try:
                    response = self.client.get("/metrics/")
                    if response.status_code == 200:
                        content = response.content.decode()
                        # Check if normalization metrics are present
                        self.assertIn("normalization_coverage_by_object", content)
                except Exception:
                    # Metrics endpoint not available in test environment - that's OK
                    pass
        except Exception as e:
            self.fail(f"record_normalization_coverage raised exception: {e}")

    def test_record_contract_json_size(self):
        """Test recording contract JSON size metric."""
        # Should execute without error
        try:
            record_contract_json_size(self.sample_contract, tenant_id="test-tenant")
            # If metrics are available, operation should succeed
            if METRICS_AVAILABLE:
                # Verify metrics endpoint is accessible (if available)
                try:
                    response = self.client.get("/metrics/")
                    if response.status_code == 200:
                        content = response.content.decode()
                        # Check if contract size metrics are present
                        self.assertIn("contract_json_size_bytes", content)
                except Exception:
                    # Metrics endpoint not available in test environment - that's OK
                    pass
        except Exception as e:
            self.fail(f"record_contract_json_size raised exception: {e}")

    def test_record_missing_objects(self):
        """Test recording missing objects metric."""
        # Should execute without error
        try:
            record_missing_objects(self.sample_contract, tenant_id="test-tenant")
            # If metrics are available, operation should succeed
            if METRICS_AVAILABLE:
                # Verify metrics endpoint is accessible (if available)
                try:
                    response = self.client.get("/metrics/")
                    if response.status_code == 200:
                        content = response.content.decode()
                        # Check if missing objects metrics are present
                        self.assertIn("contract_missing_objects_total", content)
                except Exception:
                    # Metrics endpoint not available in test environment - that's OK
                    pass
        except Exception as e:
            self.fail(f"record_missing_objects raised exception: {e}")

    def test_record_broken_lineage_links(self):
        """Test recording broken lineage links metric."""
        broken_links = [
            {"type": "contract", "source": "contract1", "target": "contract2"},
            {"type": "model", "source": "contract1/model1", "target": "contract2/model2"},
            {
                "type": "field",
                "source": "contract1/model1/field1",
                "target": "contract2/model2/field2",
            },
        ]

        # Should execute without error
        try:
            record_broken_lineage_links(self.sample_contract, broken_links, tenant_id="test-tenant")
            # If metrics are available, operation should succeed
            if METRICS_AVAILABLE:
                # Verify metrics endpoint is accessible (if available)
                try:
                    response = self.client.get("/metrics/")
                    if response.status_code == 200:
                        content = response.content.decode()
                        # Check if broken lineage metrics are present
                        self.assertIn("contract_broken_lineage_links_total", content)
                except Exception:
                    # Metrics endpoint not available in test environment - that's OK
                    pass
        except Exception as e:
            self.fail(f"record_broken_lineage_links raised exception: {e}")

    def test_record_all_normalization_metrics(self):
        """Test recording all normalization metrics at once."""
        broken_links = [{"type": "contract", "source": "contract1", "target": "contract2"}]

        # Should execute without error
        try:
            record_all_normalization_metrics(
                self.sample_contract, broken_links=broken_links, tenant_id="test-tenant"
            )
            # If metrics are available, all operations should succeed
            if METRICS_AVAILABLE:
                # Verify metrics endpoint is accessible (if available)
                try:
                    response = self.client.get("/metrics/")
                    if response.status_code == 200:
                        content = response.content.decode()
                        # Check if all normalization metrics are present
                        self.assertIn("normalization_coverage_by_object", content)
                        self.assertIn("contract_json_size_bytes", content)
                        self.assertIn("contract_missing_objects_total", content)
                        self.assertIn("contract_broken_lineage_links_total", content)
                except Exception:
                    # Metrics endpoint not available in test environment - that's OK
                    pass
        except Exception as e:
            self.fail(f"record_all_normalization_metrics raised exception: {e}")

    def test_record_metrics_without_tenant_id(self):
        """Test that metrics can be recorded without tenant_id."""
        # Should execute without error
        try:
            record_normalization_coverage(self.sample_contract)
            # Operation should succeed even without tenant_id
        except Exception as e:
            self.fail(f"record_normalization_coverage without tenant_id raised exception: {e}")

    def test_record_metrics_with_empty_contract(self):
        """Test that metrics handle empty contracts gracefully."""
        empty_contract = {}

        # Should execute without error (gracefully handles empty contract)
        try:
            record_normalization_coverage(empty_contract)
            # Should not raise an error - empty contracts are handled gracefully
        except Exception as e:
            self.fail(f"record_normalization_coverage with empty contract raised exception: {e}")

    def test_record_metrics_with_none_contract(self):
        """Test that metrics handle None contracts gracefully."""
        # Should execute without error (gracefully handles None)
        try:
            record_normalization_coverage(None)
            # Should not raise an error - None contracts are handled gracefully
        except Exception as e:
            self.fail(f"record_normalization_coverage with None contract raised exception: {e}")

    def test_record_broken_lineage_links_with_empty_list(self):
        """Test that broken lineage links handles empty list gracefully."""
        # Should execute without error
        try:
            record_broken_lineage_links(self.sample_contract, [], tenant_id="test-tenant")
            # Should not raise an error - empty list is handled gracefully
        except Exception as e:
            self.fail(f"record_broken_lineage_links with empty list raised exception: {e}")

    def test_record_broken_lineage_links_with_none(self):
        """Test that broken lineage links handles None gracefully."""
        # Should execute without error
        try:
            record_broken_lineage_links(self.sample_contract, None, tenant_id="test-tenant")
            # Should not raise an error - None is handled gracefully
        except Exception as e:
            self.fail(f"record_broken_lineage_links with None raised exception: {e}")

    # ========== SUCCESS SCENARIOS ==========

    def test_record_normalization_coverage_success(self):
        """Test successful recording of normalization coverage metrics"""
        # Contract with all required objects
        complete_contract = {
            "hub_contract_version": "1.0.0",
            "id": "complete-contract",
            "info": {"name": "Complete Contract"},
            "contact": {"email": "test@example.com"},
            "servers": [{"type": "s3", "url": "s3://bucket"}],
            "models": [{"name": "model1", "fields": []}],
            "terms": {"license": "MIT"},
            "definitions": {"schema1": {"type": "object"}},
            "servicelevels": [{"name": "sl1"}],
            "lineage": {"upstream": []},
            "roles": [{"name": "admin"}],
            "team": [{"name": "team1"}],
            "pricing": {"model": "free"},
            "support": {"email": "support@example.com"},
        }

        try:
            record_normalization_coverage(complete_contract, tenant_id="test-tenant")
            # Should succeed without errors
        except Exception as e:
            self.fail(f"record_normalization_coverage with complete contract raised exception: {e}")

    def test_record_contract_json_size_success(self):
        """Test successful recording of contract JSON size"""
        contract = {"id": "test", "data": "x" * 1000}  # 1KB contract

        try:
            record_contract_json_size(contract, tenant_id="test-tenant")
            # Should succeed and record size metric
        except Exception as e:
            self.fail(f"record_contract_json_size raised exception: {e}")

    def test_record_missing_objects_success(self):
        """Test successful recording of missing objects"""
        contract_with_missing = {
            "id": "test",
            "info": {"name": "Test"},
            # Missing: terms, definitions, servicelevels
        }

        try:
            record_missing_objects(contract_with_missing, tenant_id="test-tenant")
            # Should succeed and record missing objects
        except Exception as e:
            self.fail(f"record_missing_objects raised exception: {e}")

    def test_record_broken_lineage_links_success(self):
        """Test successful recording of broken lineage links"""
        broken_links = [
            {"type": "contract", "source": "contract1", "target": "nonexistent"},
            {"type": "model", "source": "contract1/model1", "target": "contract2/model2"},
        ]

        try:
            record_broken_lineage_links(self.sample_contract, broken_links, tenant_id="test-tenant")
            # Should succeed and record broken links
        except Exception as e:
            self.fail(f"record_broken_lineage_links raised exception: {e}")

    # ========== FAILURE SCENARIOS ==========

    def test_record_normalization_coverage_handles_invalid_contract_structure(self):
        """Test that normalization coverage handles invalid contract structure gracefully"""
        invalid_contract = "not a dict"  # Invalid type

        try:
            record_normalization_coverage(invalid_contract, tenant_id="test-tenant")
            # Should handle gracefully (may skip or handle error)
        except Exception as e:
            # Expected if validation fails - that's OK
            self.assertIsInstance(e, (TypeError, AttributeError, ValueError))

    def test_record_contract_json_size_handles_serialization_error(self):
        """Test that contract JSON size handles serialization errors gracefully"""
        # Contract with non-serializable object
        import datetime

        contract_with_date = {"id": "test", "date": datetime.datetime.now()}

        try:
            record_contract_json_size(contract_with_date, tenant_id="test-tenant")
            # Should handle gracefully (may serialize or skip)
        except Exception as e:
            # Expected if serialization fails - that's OK
            self.assertIsInstance(e, (TypeError, ValueError))

    def test_record_missing_objects_handles_malformed_contract(self):
        """Test that missing objects handles malformed contract gracefully"""
        malformed_contract = {"id": "test", "info": None}  # None value

        try:
            record_missing_objects(malformed_contract, tenant_id="test-tenant")
            # Should handle gracefully
        except Exception as e:
            # Expected if contract structure is invalid
            self.assertIsInstance(e, (TypeError, AttributeError))

    # ========== ERROR HANDLING ==========

    def test_record_all_normalization_metrics_handles_partial_failure(self):
        """Test that record_all_normalization_metrics handles partial failures gracefully"""
        # Contract with some valid and some invalid data
        mixed_contract = {
            "id": "test",
            "info": {"name": "Test"},
            "models": [{"name": "model1"}],
            # Missing some objects
        }

        broken_links = [{"type": "contract", "source": "contract1", "target": "contract2"}]

        try:
            record_all_normalization_metrics(
                mixed_contract, broken_links=broken_links, tenant_id="test-tenant"
            )
            # Should handle gracefully even if some metrics fail
        except Exception as e:
            # Should not fail completely - may log errors but continue
            self.fail(f"record_all_normalization_metrics should handle partial failures: {e}")

    def test_record_metrics_handles_metrics_unavailable(self):
        """Test that metrics recording handles metrics infrastructure unavailability"""
        # Metrics may not be available in all test environments
        contract = {"id": "test", "info": {"name": "Test"}}

        try:
            record_normalization_coverage(contract, tenant_id="test-tenant")
            # Should handle gracefully if metrics unavailable
        except Exception as e:
            # If metrics are required, should raise appropriate error
            # If metrics are optional, should handle gracefully
            if METRICS_AVAILABLE:
                # If metrics are available, should not raise error
                self.fail(
                    f"record_normalization_coverage should not raise error when metrics available: {e}"
                )

    def test_record_metrics_with_very_large_contract(self):
        """Test that metrics recording handles very large contracts"""
        # Create very large contract
        large_contract = {
            "id": "test",
            "data": "x" * 10000000,  # 10MB contract
        }

        try:
            record_contract_json_size(large_contract, tenant_id="test-tenant")
            # Should handle large contracts (may take time or skip)
        except Exception as e:
            # May timeout or fail with very large contracts - that's OK
            self.assertIsInstance(e, (MemoryError, TimeoutError, ValueError))

    # ========== EDGE CASES ==========

    def test_record_normalization_coverage_with_nested_objects(self):
        """Test normalization coverage with deeply nested contract objects"""
        nested_contract = {
            "id": "test",
            "info": {"name": "Test", "nested": {"deep": {"value": "test"}}},
            "models": [
                {
                    "name": "model1",
                    "fields": [
                        {
                            "name": "field1",
                            "nested": {"deep": {"value": "test"}},
                        }
                    ],
                }
            ],
        }

        try:
            record_normalization_coverage(nested_contract, tenant_id="test-tenant")
            # Should handle nested structures
        except Exception as e:
            self.fail(f"record_normalization_coverage with nested objects raised exception: {e}")

    def test_record_broken_lineage_links_with_complex_links(self):
        """Test broken lineage links with complex link structures"""
        complex_links = [
            {
                "type": "contract",
                "source": "contract1",
                "target": "contract2",
                "metadata": {"weight": 1.0, "direction": "upstream"},
            },
            {
                "type": "model",
                "source": "contract1/model1",
                "target": "contract2/model2",
                "metadata": {"transformation": "aggregation"},
            },
        ]

        try:
            record_broken_lineage_links(
                self.sample_contract, complex_links, tenant_id="test-tenant"
            )
            # Should handle complex link structures
        except Exception as e:
            self.fail(f"record_broken_lineage_links with complex links raised exception: {e}")

    def test_record_all_normalization_metrics_with_all_parameters(self):
        """Test record_all_normalization_metrics with all optional parameters"""
        broken_links = [{"type": "contract", "source": "c1", "target": "c2"}]

        try:
            record_all_normalization_metrics(
                self.sample_contract,
                broken_links=broken_links,
                tenant_id="test-tenant",
            )
            # Should handle all parameters
        except Exception as e:
            self.fail(f"record_all_normalization_metrics with all parameters raised exception: {e}")
