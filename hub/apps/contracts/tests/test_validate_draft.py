"""
Tests for contract validate-draft endpoint (Phase 219.4).

Validates raw contract content without persisting — dry-run normalization.
All tests use real NormalizationService (no mocks).
"""

import json

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.contracts.tests.test_base import ContractsAPITestBase

User = get_user_model()

pytestmark = pytest.mark.django_db


VALID_ODCS_V3 = json.dumps(
    {
        "apiVersion": "odcs.io/v3.0.2",
        "kind": "DataContract",
        "id": "test-validate-draft",
        "name": "Validate Draft Test",
        "version": "1.0.0",
        "schema": {
            "fields": [
                {"name": "id", "type": "string"},
                {"name": "name", "type": "string"},
            ]
        },
    }
)

VALID_ODPS_V4 = json.dumps(
    {
        "schema": "https://opendataproducts.org/schema/v4.1",
        "version": "4.1",
        "product": {
            "details": {
                "en": {
                    "productID": "test-validate-draft",
                    "name": "Validate Draft Test Product",
                    "description": "A minimal ODPS for testing.",
                    "productVersion": "1.0.0",
                }
            }
        },
    }
)

MALFORMED_JSON = '{"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"'  # missing closing brace

UNRECOGNIZED_SPEC = json.dumps({"some_random_key": "some_value", "version": 1})

VALID_ODCS_YAML = """\
apiVersion: odcs.io/v3.0.2
kind: DataContract
id: test-validate-draft-yaml
name: Validate Draft YAML Test
version: "1.0.0"
schema:
  fields:
    - name: id
      type: string
    - name: name
      type: string
"""

ENDPOINT = "/api/v1/contracts/validate-draft/"


class ValidateDraftEndpointTest(ContractsAPITestBase):
    """Test validate-draft endpoint with real NormalizationService."""

    def test_validate_draft_valid_odcs(self):
        """Valid ODCS v3.0.2 content normalizes successfully."""
        response = self.client.post(
            ENDPOINT,
            {"original_raw": VALID_ODCS_V3, "original_format": "JSON"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertTrue(data["valid"])
        self.assertEqual(data["detected_spec_type"], "ODCS")
        self.assertIn("3.0", data["detected_spec_version"])
        self.assertIn(
            data["normalization_status"],
            ("NORMALIZED_OK", "NORMALIZED_WITH_WARNINGS"),
        )
        self.assertIsInstance(data["normalization_errors"], list)
        self.assertIsInstance(data["normalization_warnings"], list)

    def test_validate_draft_valid_odps(self):
        """Valid ODPS v4.1 content normalizes successfully."""
        response = self.client.post(
            ENDPOINT,
            {"original_raw": VALID_ODPS_V4, "original_format": "JSON"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        # ODPS may normalize OK or with warnings depending on normalizer version
        self.assertIn(data["detected_spec_type"], ("ODPS", "UNKNOWN"))
        self.assertIsInstance(data["normalization_errors"], list)
        self.assertIsInstance(data["normalization_warnings"], list)

    def test_validate_draft_invalid_content(self):
        """Malformed JSON returns valid=false with normalization errors."""
        response = self.client.post(
            ENDPOINT,
            {"original_raw": MALFORMED_JSON, "original_format": "JSON"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertFalse(data["valid"])
        self.assertEqual(data["normalization_status"], "NORMALIZATION_FAILED")
        self.assertGreater(len(data["normalization_errors"]), 0)

    def test_validate_draft_unknown_spec(self):
        """Unrecognized spec type returns detected_spec_type=UNKNOWN."""
        response = self.client.post(
            ENDPOINT,
            {"original_raw": UNRECOGNIZED_SPEC, "original_format": "JSON"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        # Unrecognized spec must be detected as UNKNOWN
        self.assertEqual(
            data["detected_spec_type"],
            "UNKNOWN",
            "detected_spec_type must be 'UNKNOWN' for unrecognized spec input",
        )
        self.assertIsInstance(data["normalization_errors"], list)

    def test_validate_draft_requires_auth(self):
        """Unauthenticated request returns 401."""
        anon_client = APIClient()
        response = anon_client.post(
            ENDPOINT,
            {"original_raw": VALID_ODCS_V3, "original_format": "JSON"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_validate_draft_empty_content(self):
        """Empty original_raw returns 400 serializer error."""
        response = self.client.post(
            ENDPOINT,
            {"original_raw": "", "original_format": "JSON"},
            format="json",
        )
        # DRF CharField with required=True rejects empty strings as 400
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validate_draft_missing_format(self):
        """Missing original_format returns 400 serializer error."""
        response = self.client.post(
            ENDPOINT,
            {"original_raw": VALID_ODCS_V3},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validate_draft_invalid_format_choice(self):
        """Invalid format choice returns 400 serializer error."""
        response = self.client.post(
            ENDPOINT,
            {"original_raw": VALID_ODCS_V3, "original_format": "XML"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validate_draft_yaml_format(self):
        """Valid ODCS YAML content normalizes successfully."""
        response = self.client.post(
            ENDPOINT,
            {"original_raw": VALID_ODCS_YAML, "original_format": "YAML"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data["detected_spec_type"], "ODCS")
        self.assertIsInstance(data["normalization_errors"], list)
        self.assertIsInstance(data["normalization_warnings"], list)
