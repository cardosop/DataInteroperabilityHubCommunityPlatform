"""
Integration Tests for Version Handling
"""

from hub.apps.contracts.normalization import normalize_contract
from hub.apps.contracts.versioning import detect_version, get_default_version


class TestVersionHandlingIntegration:
    """Integration tests for version handling in normalization"""

    def test_normalized_contract_has_version(self):
        """Test that normalized contract has hub_contract_version"""
        odcs_contract = """
        apiVersion: odcs.io/v3.0.2
        kind: DataContract
        id: test-contract
        name: Test Contract
        schema:
          fields:
            - name: field1
              type: string
        """

        hub_contract, _spec_type, _spec_version, _status, _errors, _warnings = normalize_contract(
            odcs_contract, "YAML"
        )

        assert hub_contract is not None
        assert "hub_contract_version" in hub_contract
        assert hub_contract["hub_contract_version"] == get_default_version()

    def test_version_detection_in_normalized_contract(self):
        """Test detecting version from normalized contract"""
        odcs_contract = """
        apiVersion: odcs.io/v3.0.2
        kind: DataContract
        id: test-contract
        name: Test Contract
        schema:
          fields:
            - name: field1
              type: string
        """

        hub_contract, _spec_type, _spec_version, _status, _errors, _warnings = normalize_contract(
            odcs_contract, "YAML"
        )

        detected_version = detect_version(hub_contract)
        assert detected_version == get_default_version()

    def test_all_contracts_use_default_version(self):
        """Test that all contracts use default version during development"""
        contracts = [
            """
            apiVersion: odcs.io/v3.0.2
            kind: DataContract
            id: test1
            name: Test 1
            schema:
              fields:
                - name: field1
                  type: string
            """,
            """
            dataContractSpecification: 1.2.1
            id: test2
            info:
              title: Test 2
            schema:
              type: object
              fields:
                - name: field1
                  type: string
            """,
        ]

        for contract in contracts:
            hub_contract, _, _, _, _, _ = normalize_contract(contract, "YAML")
            if hub_contract:
                assert hub_contract["hub_contract_version"] == get_default_version()
