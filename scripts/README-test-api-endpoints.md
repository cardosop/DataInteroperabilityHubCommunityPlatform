# API Endpoint Testing Script

## Quick Start

```bash
# Install dependencies
pip install requests

# Run tests (public endpoints only)
python scripts/test-api-endpoints.py

# Run tests with authentication
python scripts/test-api-endpoints.py \
  --username admin@example.com \
  --password your-password
```

## Dependencies

- Python 3.8+
- `requests` library: `pip install requests`

## Features

- ✅ Real HTTP requests (no mocks)
- ✅ JWT authentication support
- ✅ Performance measurement
- ✅ Status classification
- ✅ Error analysis
- ✅ Automatic retries
- ✅ Markdown + JSON reports

## Output

- `docs/api-audit/endpoint-test-report.md` - Human-readable report
- `docs/api-audit/endpoint-test-report.json` - Machine-readable results
- Updates `docs/api-audit/current-api-inventory.md` with test results

## See Also

- `docs/api-audit/ENDPOINT_TESTING_GUIDE.md` - Comprehensive guide
- `docs/api-audit/ENDPOINT_TESTING_SUMMARY.md` - Implementation summary

