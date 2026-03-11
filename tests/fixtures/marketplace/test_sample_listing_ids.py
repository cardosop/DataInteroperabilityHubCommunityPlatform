"""
Test sample_listing_ids.json fixture.

Validates the documented demo.ckan.org listing IDs are loadable and have
the expected structure for Phase 23 marketplace fixtures.
"""
import json
import unittest
from pathlib import Path

# Path to sample_listing_ids.json (same directory as this test)
FIXTURES_DIR = Path(__file__).parent
SAMPLE_LISTING_IDS_PATH = FIXTURES_DIR / "sample_listing_ids.json"


class TestSampleListingIds(unittest.TestCase):
    """Validate sample_listing_ids.json structure and content."""

    def test_sample_listing_ids_file_exists(self):
        """sample_listing_ids.json must exist."""
        self.assertTrue(
            SAMPLE_LISTING_IDS_PATH.exists(),
            f"sample_listing_ids.json not found at {SAMPLE_LISTING_IDS_PATH}",
        )

    def test_sample_listing_ids_valid_json(self):
        """sample_listing_ids.json must be valid JSON."""
        with open(SAMPLE_LISTING_IDS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data, dict)

    def test_sample_listing_ids_has_demo_ckan(self):
        """sample_listing_ids.json must have demo.ckan.org section."""
        with open(SAMPLE_LISTING_IDS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("demo.ckan.org", data)
        demo = data["demo.ckan.org"]
        self.assertIsInstance(demo, dict)

    def test_sample_listing_ids_has_default(self):
        """sample_listing_ids.json must have default listing ID."""
        with open(SAMPLE_LISTING_IDS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        demo = data["demo.ckan.org"]
        self.assertIn("default", demo)
        self.assertEqual(demo["default"], "annakarenina")

    def test_sample_listing_ids_has_listings_array(self):
        """sample_listing_ids.json must have listings array."""
        with open(SAMPLE_LISTING_IDS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        demo = data["demo.ckan.org"]
        self.assertIn("listings", demo)
        self.assertIsInstance(demo["listings"], list)
        self.assertGreater(len(demo["listings"]), 0)

    def test_sample_listing_ids_default_in_listings(self):
        """Default listing (annakarenina) must be in listings array."""
        with open(SAMPLE_LISTING_IDS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        demo = data["demo.ckan.org"]
        listing_ids = [e["id"] for e in demo["listings"] if "id" in e]
        self.assertIn("annakarenina", listing_ids)

    def test_sample_listing_ids_each_has_id_and_description(self):
        """Each listing entry must have id and description."""
        with open(SAMPLE_LISTING_IDS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for entry in data["demo.ckan.org"]["listings"]:
            self.assertIn("id", entry, f"Listing entry missing 'id': {entry}")
            self.assertIn("description", entry, f"Listing entry missing 'description': {entry}")
            self.assertIsInstance(entry["id"], str)
            self.assertIsInstance(entry["description"], str)


if __name__ == "__main__":
    unittest.main()
