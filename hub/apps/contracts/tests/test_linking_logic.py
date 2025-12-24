"""
Unit tests for Linking Logic (Task 3.4.2)

Tests verify:
1. Validate ODPS → ODCS link (contract must exist)
2. Validate ODCS → ODPS link (ODPS must exist)
3. Maintain referential integrity (bidirectional consistency)
4. Comprehensive validation of all links
"""
import json
from django.test import TestCase
from django.contrib.auth import get_user_model

from hub.apps.contracts.linking_validation import (
    validate_odps_to_odcs_link,
    validate_odcs_to_odps_link,
    validate_referential_integrity,
    validate_all_links,
    LinkingValidationError
)
from hub.apps.contracts.models import Contract, OriginalSpecType, OriginalFormat, ContractStatus, NormalizationStatus
from hub.apps.tenants.models import Tenant
from hub.apps.assets.models import Asset


User = get_user_model()


class ODPSToODCSLinkValidationTest(TestCase):
    """Test ODPS → ODCS link validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )

        # Create ODCS contract
        self.odcs_raw = json.dumps({
            "schema": "https://datacontract.com/schema/v3.0.2",
            "version": "3.0.2",
            "info": {
                "title": "Test ODCS Contract",
                "version": "1.0.0"
            }
        }, indent=2)

        self.odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=self.odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            hub_contract_json={"id": "test-odcs"},
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )

    def test_validate_odps_to_odcs_link_success(self):
        """Test successful validation of ODPS → ODCS link"""
        # Create ODPS contract with valid ODCS link
        odps_raw = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                }
            }
        }, indent=2)

        odps_hub_contract = {
            "id": "test-product",
            "extensions": {
                "x_odps": {
                    "odcs_link": str(self.odcs_contract.id)
                }
            }
        }

        odps_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odps_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            hub_contract_json=odps_hub_contract,
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )

        # Validate link
        linked_odcs = validate_odps_to_odcs_link(odps_contract)

        # Verify linked contract
        self.assertIsNotNone(linked_odcs)
        self.assertEqual(linked_odcs.id, self.odcs_contract.id)
        self.assertEqual(linked_odcs.original_spec_type, OriginalSpecType.ODCS)

    def test_validate_odps_to_odcs_link_no_link(self):
        """Test validation when ODPS has no ODCS link"""
        # Create ODPS contract without ODCS link
        odps_raw = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                }
            }
        }, indent=2)

        odps_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odps_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            hub_contract_json={"id": "test-product"},
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )

        # Validate link (should return None)
        linked_odcs = validate_odps_to_odcs_link(odps_contract)
        self.assertIsNone(linked_odcs)

    def test_validate_odps_to_odcs_link_contract_not_found(self):
        """Test validation fails when linked ODCS contract doesn't exist"""
        # Create ODPS contract with invalid ODCS link
        odps_raw = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                }
            }
        }, indent=2)

        odps_hub_contract = {
            "id": "test-product",
            "extensions": {
                "x_odps": {
                    "odcs_link": "00000000-0000-0000-0000-000000000000"  # Non-existent ID
                }
            }
        }

        odps_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odps_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            hub_contract_json=odps_hub_contract,
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )

        # Validate link (should raise error)
        with self.assertRaises(LinkingValidationError) as context:
            validate_odps_to_odcs_link(odps_contract)

        self.assertEqual(context.exception.error_code, "INVALID_ODCS_LINK")
        self.assertIn("does not exist", context.exception.message)

    def test_validate_odps_to_odcs_link_wrong_type(self):
        """Test validation fails when linked contract is not ODCS"""
        # Create another ODPS contract
        odps_raw = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product-2",
                        "name": "Test Product 2"
                    }
                }
            }
        }, indent=2)

        odps_contract_2 = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odps_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            hub_contract_json={"id": "test-product-2"},
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )

        # Create ODPS contract linking to another ODPS (wrong type)
        odps_hub_contract = {
            "id": "test-product",
            "extensions": {
                "x_odps": {
                    "odcs_link": str(odps_contract_2.id)  # Linking to ODPS, not ODCS
                }
            }
        }

        odps_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odps_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            hub_contract_json=odps_hub_contract,
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )

        # Validate link (should raise error)
        with self.assertRaises(LinkingValidationError) as context:
            validate_odps_to_odcs_link(odps_contract)

        self.assertEqual(context.exception.error_code, "INVALID_ODCS_LINK_TYPE")
        self.assertIn("non-ODCS contract", context.exception.message)


class ODCSToODPSLinkValidationTest(TestCase):
    """Test ODCS → ODPS link validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )

        # Create ODPS contract
        odps_raw = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                }
            }
        }, indent=2)

        self.odps_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odps_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            hub_contract_json={"id": "test-product"},
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )

    def test_validate_odcs_to_odps_link_success(self):
        """Test successful validation of ODCS → ODPS link"""
        # Create ODCS contract with valid ODPS link
        odcs_raw = json.dumps({
            "schema": "https://datacontract.com/schema/v3.0.2",
            "version": "3.0.2",
            "info": {
                "title": "Test ODCS Contract",
                "version": "1.0.0"
            }
        }, indent=2)

        odcs_hub_contract = {
            "id": "test-odcs",
            "extensions": {
                "x_odps": {
                    "odps_link": str(self.odps_contract.id)
                }
            }
        }

        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            hub_contract_json=odcs_hub_contract,
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )

        # Validate link
        linked_odps = validate_odcs_to_odps_link(odcs_contract)

        # Verify linked contract
        self.assertIsNotNone(linked_odps)
        self.assertEqual(linked_odps.id, self.odps_contract.id)
        self.assertEqual(linked_odps.original_spec_type, OriginalSpecType.ODPS)

    def test_validate_odcs_to_odps_link_no_link(self):
        """Test validation when ODCS has no ODPS link"""
        # Create ODCS contract without ODPS link
        odcs_raw = json.dumps({
            "schema": "https://datacontract.com/schema/v3.0.2",
            "version": "3.0.2",
            "info": {
                "title": "Test ODCS Contract",
                "version": "1.0.0"
            }
        }, indent=2)

        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            hub_contract_json={"id": "test-odcs"},
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )

        # Validate link (should return None)
        linked_odps = validate_odcs_to_odps_link(odcs_contract)
        self.assertIsNone(linked_odps)

    def test_validate_odcs_to_odps_link_contract_not_found(self):
        """Test validation fails when linked ODPS contract doesn't exist"""
        # Create ODCS contract with invalid ODPS link
        odcs_raw = json.dumps({
            "schema": "https://datacontract.com/schema/v3.0.2",
            "version": "3.0.2",
            "info": {
                "title": "Test ODCS Contract",
                "version": "1.0.0"
            }
        }, indent=2)

        odcs_hub_contract = {
            "id": "test-odcs",
            "extensions": {
                "x_odps": {
                    "odps_link": "00000000-0000-0000-0000-000000000000"  # Non-existent ID
                }
            }
        }

        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            hub_contract_json=odcs_hub_contract,
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )

        # Validate link (should raise error)
        with self.assertRaises(LinkingValidationError) as context:
            validate_odcs_to_odps_link(odcs_contract)

        self.assertEqual(context.exception.error_code, "INVALID_ODPS_LINK")
        self.assertIn("does not exist", context.exception.message)

    def test_validate_odcs_to_odps_link_wrong_type(self):
        """Test validation fails when linked contract is not ODPS"""
        # Create another ODCS contract
        odcs_raw = json.dumps({
            "schema": "https://datacontract.com/schema/v3.0.2",
            "version": "3.0.2",
            "info": {
                "title": "Test ODCS Contract 2",
                "version": "1.0.0"
            }
        }, indent=2)

        odcs_contract_2 = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            hub_contract_json={"id": "test-odcs-2"},
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )

        # Create ODCS contract linking to another ODCS (wrong type)
        odcs_hub_contract = {
            "id": "test-odcs",
            "extensions": {
                "x_odps": {
                    "odps_link": str(odcs_contract_2.id)  # Linking to ODCS, not ODPS
                }
            }
        }

        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            hub_contract_json=odcs_hub_contract,
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )

        # Validate link (should raise error)
        with self.assertRaises(LinkingValidationError) as context:
            validate_odcs_to_odps_link(odcs_contract)

        self.assertEqual(context.exception.error_code, "INVALID_ODPS_LINK_TYPE")
        self.assertIn("non-ODPS contract", context.exception.message)


class ReferentialIntegrityValidationTest(TestCase):
    """Test referential integrity validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )

    def test_validate_referential_integrity_bidirectional_success(self):
        """Test successful validation of bidirectional links"""
        # Create ODCS contract
        odcs_raw = json.dumps({
            "schema": "https://datacontract.com/schema/v3.0.2",
            "version": "3.0.2",
            "info": {
                "title": "Test ODCS Contract",
                "version": "1.0.0"
            }
        }, indent=2)

        # Create ODPS contract
        odps_raw = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                }
            }
        }, indent=2)

        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            hub_contract_json={"id": "test-odcs"},
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )

        odps_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odps_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            hub_contract_json={"id": "test-product"},
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )

        # Establish bidirectional links
        odcs_contract.hub_contract_json = {
            "id": "test-odcs",
            "extensions": {
                "x_odps": {
                    "odps_link": str(odps_contract.id)
                }
            }
        }
        odcs_contract.save(update_fields=["hub_contract_json"])

        odps_contract.hub_contract_json = {
            "id": "test-product",
            "extensions": {
                "x_odps": {
                    "odcs_link": str(odcs_contract.id)
                }
            }
        }
        odps_contract.save(update_fields=["hub_contract_json"])

        # Validate referential integrity (should not raise)
        validate_referential_integrity(odcs_contract)
        validate_referential_integrity(odps_contract)

    def test_validate_referential_integrity_violation_odps_to_odcs(self):
        """Test validation fails when ODPS links to ODCS but ODCS doesn't link back"""
        # Create ODCS contract
        odcs_raw = json.dumps({
            "schema": "https://datacontract.com/schema/v3.0.2",
            "version": "3.0.2",
            "info": {
                "title": "Test ODCS Contract",
                "version": "1.0.0"
            }
        }, indent=2)

        # Create ODPS contract
        odps_raw = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                }
            }
        }, indent=2)

        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            hub_contract_json={"id": "test-odcs"},
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )

        # Create ODPS contract with link to ODCS, but ODCS doesn't link back
        odps_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odps_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            hub_contract_json={
                "id": "test-product",
                "extensions": {
                    "x_odps": {
                        "odcs_link": str(odcs_contract.id)
                    }
                }
            },
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )

        # Validate referential integrity (should raise error)
        with self.assertRaises(LinkingValidationError) as context:
            validate_referential_integrity(odps_contract)

        self.assertEqual(context.exception.error_code, "REFERENTIAL_INTEGRITY_VIOLATION")
        self.assertIn("does not link back", str(context.exception.context.get("errors", [])))

    def test_validate_referential_integrity_violation_odcs_to_odps(self):
        """Test validation fails when ODCS links to ODPS but ODPS doesn't link back"""
        # Create ODCS contract
        odcs_raw = json.dumps({
            "schema": "https://datacontract.com/schema/v3.0.2",
            "version": "3.0.2",
            "info": {
                "title": "Test ODCS Contract",
                "version": "1.0.0"
            }
        }, indent=2)

        # Create ODPS contract
        odps_raw = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                }
            }
        }, indent=2)

        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            hub_contract_json={
                "id": "test-odcs",
                "extensions": {
                    "x_odps": {
                        "odps_link": "00000000-0000-0000-0000-000000000000"  # Will be updated
                    }
                }
            },
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )

        odps_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odps_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            hub_contract_json={"id": "test-product"},  # No link back
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )

        # Update ODCS to link to ODPS
        odcs_contract.hub_contract_json["extensions"]["x_odps"]["odps_link"] = str(odps_contract.id)
        odcs_contract.save(update_fields=["hub_contract_json"])

        # Validate referential integrity (should raise error)
        with self.assertRaises(LinkingValidationError) as context:
            validate_referential_integrity(odcs_contract)

        self.assertEqual(context.exception.error_code, "REFERENTIAL_INTEGRITY_VIOLATION")
        self.assertIn("does not link back", str(context.exception.context.get("errors", [])))

    def test_validate_referential_integrity_no_links(self):
        """Test validation succeeds when contract has no links"""
        # Create ODCS contract without links
        odcs_raw = json.dumps({
            "schema": "https://datacontract.com/schema/v3.0.2",
            "version": "3.0.2",
            "info": {
                "title": "Test ODCS Contract",
                "version": "1.0.0"
            }
        }, indent=2)

        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            hub_contract_json={"id": "test-odcs"},
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )

        # Validate referential integrity (should not raise)
        validate_referential_integrity(odcs_contract)


class AllLinksValidationTest(TestCase):
    """Test comprehensive validation of all links"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )

    def test_validate_all_links_odps_with_bidirectional_link(self):
        """Test comprehensive validation for ODPS contract with bidirectional link"""
        # Create ODCS contract
        odcs_raw = json.dumps({
            "schema": "https://datacontract.com/schema/v3.0.2",
            "version": "3.0.2",
            "info": {
                "title": "Test ODCS Contract",
                "version": "1.0.0"
            }
        }, indent=2)

        # Create ODPS contract
        odps_raw = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                }
            }
        }, indent=2)

        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            hub_contract_json={"id": "test-odcs"},
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )

        odps_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odps_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            hub_contract_json={
                "id": "test-product",
                "extensions": {
                    "x_odps": {
                        "odcs_link": str(odcs_contract.id)
                    }
                }
            },
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )

        # Establish bidirectional link
        odcs_contract.hub_contract_json = {
            "id": "test-odcs",
            "extensions": {
                "x_odps": {
                    "odps_link": str(odps_contract.id)
                }
            }
        }
        odcs_contract.save(update_fields=["hub_contract_json"])

        # Validate all links
        result = validate_all_links(odps_contract)

        # Verify results
        self.assertIsNotNone(result["odps_to_odcs"])
        self.assertEqual(result["odps_to_odcs"].id, odcs_contract.id)
        self.assertIsNone(result["odcs_to_odps"])  # ODPS doesn't have odcs_to_odps
        self.assertTrue(result["referential_integrity"])

    def test_validate_all_links_odcs_with_bidirectional_link(self):
        """Test comprehensive validation for ODCS contract with bidirectional link"""
        # Create ODCS contract
        odcs_raw = json.dumps({
            "schema": "https://datacontract.com/schema/v3.0.2",
            "version": "3.0.2",
            "info": {
                "title": "Test ODCS Contract",
                "version": "1.0.0"
            }
        }, indent=2)

        # Create ODPS contract
        odps_raw = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                }
            }
        }, indent=2)

        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odcs_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            hub_contract_json={
                "id": "test-odcs",
                "extensions": {
                    "x_odps": {
                        "odps_link": "00000000-0000-0000-0000-000000000000"  # Will be updated
                    }
                }
            },
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )

        odps_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odps_raw,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            hub_contract_json={
                "id": "test-product",
                "extensions": {
                    "x_odps": {
                        "odcs_link": str(odcs_contract.id)
                    }
                }
            },
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user
        )

        # Update ODCS to link to ODPS
        odcs_contract.hub_contract_json["extensions"]["x_odps"]["odps_link"] = str(odps_contract.id)
        odcs_contract.save(update_fields=["hub_contract_json"])

        # Validate all links
        result = validate_all_links(odcs_contract)

        # Verify results
        self.assertIsNone(result["odps_to_odcs"])  # ODCS doesn't have odps_to_odcs
        self.assertIsNotNone(result["odcs_to_odps"])
        self.assertEqual(result["odcs_to_odps"].id, odps_contract.id)
        self.assertTrue(result["referential_integrity"])

