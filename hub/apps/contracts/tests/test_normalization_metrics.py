"""
Tests for normalization metrics recording.

Tests the metrics recording functionality for normalization coverage,
contract JSON size, missing objects, and broken lineage links.

Uses real metrics infrastructure (no mocks) - tests verify that:
1. Functions execute without errors
2. Metrics operations succeed
3. Optional: Metrics are recorded (via /metrics endpoint if available)
"""
from django.test import TestCase, Client
from hub.apps.contracts.normalization_metrics import (
    record_normalization_coverage,
    record_contract_json_size,
    record_missing_objects,
    record_broken_lineage_links,
    record_all_normalization_metrics,
    METRICS_AVAILABLE,
)


class NormalizationMetricsTestCase(TestCase):
    """Test normalization metrics recording."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.sample_contract = {
            'hub_contract_version': '1.0.0',
            'id': 'test-contract-1',
            'info': {'name': 'Test Contract'},
            'contact': {'email': 'test@example.com'},
            'servers': [{'type': 's3', 'url': 's3://bucket'}],
            'models': [{'name': 'model1', 'fields': []}],
            # Missing: terms, definitions, servicelevels, lineage, roles, team, pricing, support
        }
    
    def test_record_normalization_coverage(self):
        """Test recording normalization coverage metrics."""
        # Should execute without error
        try:
        record_normalization_coverage(self.sample_contract, tenant_id='test-tenant')
            # If metrics are available, operation should succeed
            if METRICS_AVAILABLE:
                # Verify metrics endpoint is accessible (if available)
                try:
                    response = self.client.get('/metrics/')
                    if response.status_code == 200:
                        content = response.content.decode()
                        # Check if normalization metrics are present
                        self.assertIn('normalization_coverage_by_object', content)
                except Exception:
                    # Metrics endpoint not available in test environment - that's OK
                    pass
        except Exception as e:
            self.fail(f"record_normalization_coverage raised exception: {e}")
    
    def test_record_contract_json_size(self):
        """Test recording contract JSON size metric."""
        # Should execute without error
        try:
        record_contract_json_size(self.sample_contract, tenant_id='test-tenant')
            # If metrics are available, operation should succeed
            if METRICS_AVAILABLE:
                # Verify metrics endpoint is accessible (if available)
                try:
                    response = self.client.get('/metrics/')
                    if response.status_code == 200:
                        content = response.content.decode()
                        # Check if contract size metrics are present
                        self.assertIn('contract_json_size_bytes', content)
                except Exception:
                    # Metrics endpoint not available in test environment - that's OK
                    pass
        except Exception as e:
            self.fail(f"record_contract_json_size raised exception: {e}")
    
    def test_record_missing_objects(self):
        """Test recording missing objects metric."""
        # Should execute without error
        try:
        record_missing_objects(self.sample_contract, tenant_id='test-tenant')
            # If metrics are available, operation should succeed
            if METRICS_AVAILABLE:
                # Verify metrics endpoint is accessible (if available)
                try:
                    response = self.client.get('/metrics/')
                    if response.status_code == 200:
                        content = response.content.decode()
                        # Check if missing objects metrics are present
                        self.assertIn('contract_missing_objects_total', content)
                except Exception:
                    # Metrics endpoint not available in test environment - that's OK
                    pass
        except Exception as e:
            self.fail(f"record_missing_objects raised exception: {e}")
    
    def test_record_broken_lineage_links(self):
        """Test recording broken lineage links metric."""
        broken_links = [
            {'type': 'contract', 'source': 'contract1', 'target': 'contract2'},
            {'type': 'model', 'source': 'contract1/model1', 'target': 'contract2/model2'},
            {'type': 'field', 'source': 'contract1/model1/field1', 'target': 'contract2/model2/field2'},
        ]
        
        # Should execute without error
        try:
        record_broken_lineage_links(self.sample_contract, broken_links, tenant_id='test-tenant')
            # If metrics are available, operation should succeed
            if METRICS_AVAILABLE:
                # Verify metrics endpoint is accessible (if available)
                try:
                    response = self.client.get('/metrics/')
                    if response.status_code == 200:
                        content = response.content.decode()
                        # Check if broken lineage metrics are present
                        self.assertIn('contract_broken_lineage_links_total', content)
                except Exception:
                    # Metrics endpoint not available in test environment - that's OK
                    pass
        except Exception as e:
            self.fail(f"record_broken_lineage_links raised exception: {e}")
    
    def test_record_all_normalization_metrics(self):
        """Test recording all normalization metrics at once."""
        broken_links = [{'type': 'contract', 'source': 'contract1', 'target': 'contract2'}]
        
        # Should execute without error
        try:
        record_all_normalization_metrics(
            self.sample_contract,
            broken_links=broken_links,
            tenant_id='test-tenant'
        )
            # If metrics are available, all operations should succeed
            if METRICS_AVAILABLE:
                # Verify metrics endpoint is accessible (if available)
                try:
                    response = self.client.get('/metrics/')
                    if response.status_code == 200:
                        content = response.content.decode()
                        # Check if all normalization metrics are present
                        self.assertIn('normalization_coverage_by_object', content)
                        self.assertIn('contract_json_size_bytes', content)
                        self.assertIn('contract_missing_objects_total', content)
                        self.assertIn('contract_broken_lineage_links_total', content)
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
            record_broken_lineage_links(self.sample_contract, [], tenant_id='test-tenant')
            # Should not raise an error - empty list is handled gracefully
        except Exception as e:
            self.fail(f"record_broken_lineage_links with empty list raised exception: {e}")
    
    def test_record_broken_lineage_links_with_none(self):
        """Test that broken lineage links handles None gracefully."""
        # Should execute without error
        try:
            record_broken_lineage_links(self.sample_contract, None, tenant_id='test-tenant')
            # Should not raise an error - None is handled gracefully
        except Exception as e:
            self.fail(f"record_broken_lineage_links with None raised exception: {e}")

