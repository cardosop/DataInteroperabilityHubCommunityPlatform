# Marketplace Test Fixtures

Fixtures and documented sample listing IDs for marketplace connector tests.

## Sample Listing IDs (demo.ckan.org)

Known package IDs from https://demo.ckan.org suitable for tests:

| Listing ID | Description |
|------------|-------------|
| `annakarenina` | A Novel By Tolstoy — metadata-rich package, multiple resources (JSON, JPEG, PLAIN TEXT) |
| `warandpeace` | War and Peace — classic dataset |
| `child-gg` | Child dataset — may have CSV resources |
| `my-sample-dataset-001` | Sample dataset |
| `demo-dataset-rust-*` | Demo datasets (IDs may vary) |

Use `annakarenina` as the default for federated asset creation tests.

## Creating a Federated Asset from demo.ckan.org

```bash
# Create federated asset from annakarenina (default)
python hub/manage.py create_demo_ckan_federated_asset

# Create from specific listing
python hub/manage.py create_demo_ckan_federated_asset --listing-id warandpeace

# Output JSON for scripting
python hub/manage.py create_demo_ckan_federated_asset --listing-id annakarenina --output-json
```

## Fixture Usage in Tests

Use `get_or_create_demo_ckan_federated_asset()` from `hub.apps.integrations.tests.utils.marketplace_fixtures`:

```python
from hub.apps.integrations.tests.utils.marketplace_fixtures import get_or_create_demo_ckan_federated_asset

def test_with_federated_asset(self):
    asset, connection = get_or_create_demo_ckan_federated_asset(
        tenant=self.tenant,
        user=self.user,
        listing_id="annakarenina",
    )
    # Use asset in virtualization or marketplace test
```

## sample_listing_ids.json

Documented demo.ckan.org listing IDs. Validated by `test_sample_listing_ids.py`:

```bash
python3 -m unittest tests.fixtures.marketplace.test_sample_listing_ids -v
```

## CKAN API Fixtures

JSON fixtures for CKAN connector unit tests are in `ckan/`:

- `api_responses/` — CKAN API response samples
- `datasets/` — Package metadata samples
- `resources/` — Resource metadata samples

## See Also

- [REAL_MARKETPLACE_E2E.md](../../../docs/runbooks/REAL_MARKETPLACE_E2E.md) — runbook for real E2E tests
- [REAL_VIRTUALIZATION_E2E.md](../../../docs/runbooks/REAL_VIRTUALIZATION_E2E.md) — virtualization federated asset E2E
