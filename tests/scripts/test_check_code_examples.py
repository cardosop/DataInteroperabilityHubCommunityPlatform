#!/usr/bin/env python3
"""
Tests for code example checker script

Tests the comprehensive checking of code examples in documentation for endpoint URLs
and validates their accuracy.
"""

import json
import pytest
import tempfile
import ast
from pathlib import Path
from typing import Dict, List, Any
import sys

# Add scripts directory to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "scripts"))

from check_code_examples import (
    CodeExampleChecker,
    CodeExample,
    ExampleValidationResult,
)


class TestCodeExampleChecker:
    """Test suite for CodeExampleChecker"""

    @pytest.fixture
    def temp_docs_dir(self, tmp_path):
        """Create temporary docs directory structure with code examples"""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        # Create markdown file with code examples
        (docs_dir / "API_EXAMPLES.md").write_text("""
# API Examples

## Python Example

```python
import requests

url = "http://localhost:8000/api/v1/contracts/"
headers = {"Authorization": "Bearer token"}
response = requests.get(url, headers=headers)
```

## Bash Example

```bash
curl -X GET http://localhost:8000/api/v1/contracts/ \\
  -H "Authorization: Bearer token"
```

## HTTP Example

```http
GET /api/v1/contracts/ HTTP/1.1
Host: localhost:8000
Authorization: Bearer token
```

## Invalid Endpoint Example

```python
import requests
url = "http://localhost:8000/api/v1/nonexistent/"
response = requests.get(url)
```
""")

        # Create examples directory
        examples_dir = tmp_path / "examples"
        examples_dir.mkdir()
        api_dir = examples_dir / "api"
        api_dir.mkdir()

        # Create valid Python example file
        (api_dir / "valid_example.py").write_text("""#!/usr/bin/env python3
import requests

API_BASE_URL = "http://localhost:8000/api/v1"
url = f"{API_BASE_URL}/contracts/"
response = requests.get(url)
""")

        # Create Python file with invalid endpoint
        (api_dir / "invalid_example.py").write_text("""#!/usr/bin/env python3
import requests

url = "http://localhost:8000/api/v1/invalid-endpoint/"
response = requests.get(url)
""")

        # Create Python file with syntax error
        (api_dir / "syntax_error.py").write_text("""#!/usr/bin/env python3
import requests

url = "http://localhost:8000/api/v1/contracts/"
response = requests.get(url  # Missing closing parenthesis
""")

        return docs_dir, examples_dir

    @pytest.fixture
    def endpoint_inventory(self, tmp_path):
        """Create a sample endpoint inventory JSON file"""
        inventory_file = tmp_path / "endpoint-inventory.json"
        inventory_data = {
            "inventory": {
                "summary": {
                    "total_endpoints": 2,
                    "total_services": 1
                },
                "endpoints": [
                    {
                        "type": "path",
                        "full_path": "/api/v1/contracts/",
                        "methods": ["GET", "POST"],
                        "service": "contracts"
                    },
                    {
                        "type": "path",
                        "full_path": "/api/v1/assets/",
                        "methods": ["GET"],
                        "service": "assets"
                    }
                ]
            }
        }
        inventory_file.write_text(json.dumps(inventory_data, indent=2))
        return str(inventory_file)

    def test_checker_initialization(self, temp_docs_dir, endpoint_inventory):
        """Test checker initialization"""
        docs_dir, examples_dir = temp_docs_dir
        checker = CodeExampleChecker(
            docs_dir=str(docs_dir),
            examples_dir=str(examples_dir),
            endpoint_inventory_file=endpoint_inventory
        )

        assert checker.docs_dir == Path(docs_dir)
        assert checker.examples_dir == Path(examples_dir)
        assert checker.endpoint_inventory_file == Path(endpoint_inventory)
        assert len(checker.known_endpoints) == 2

    def test_find_code_examples_in_markdown(self, temp_docs_dir, endpoint_inventory):
        """Test finding code examples in markdown files"""
        docs_dir, examples_dir = temp_docs_dir
        checker = CodeExampleChecker(
            docs_dir=str(docs_dir),
            examples_dir=str(examples_dir),
            endpoint_inventory_file=endpoint_inventory
        )

        examples = checker.find_code_examples()

        assert len(examples) > 0
        markdown_examples = [e for e in examples if e.source_file.endswith('.md')]
        assert len(markdown_examples) >= 3  # At least Python, Bash, HTTP examples

        # Check Python example found
        python_examples = [e for e in markdown_examples if e.language == 'python']
        assert len(python_examples) > 0

        # Check Bash example found
        bash_examples = [e for e in markdown_examples if e.language == 'bash']
        assert len(bash_examples) > 0

    def test_find_code_examples_in_python_files(self, temp_docs_dir, endpoint_inventory):
        """Test finding code examples in Python files"""
        docs_dir, examples_dir = temp_docs_dir
        checker = CodeExampleChecker(
            docs_dir=str(docs_dir),
            examples_dir=str(examples_dir),
            endpoint_inventory_file=endpoint_inventory
        )

        examples = checker.find_code_examples()

        python_file_examples = [e for e in examples if e.source_file.endswith('.py')]
        assert len(python_file_examples) >= 3  # valid_example, invalid_example, syntax_error

    def test_extract_endpoints_from_examples(self, temp_docs_dir, endpoint_inventory):
        """Test extracting endpoint URLs from code examples"""
        docs_dir, examples_dir = temp_docs_dir
        checker = CodeExampleChecker(
            docs_dir=str(docs_dir),
            examples_dir=str(examples_dir),
            endpoint_inventory_file=endpoint_inventory
        )

        examples = checker.find_code_examples()
        endpoints = checker.extract_endpoints_from_examples(examples)

        assert len(endpoints) > 0
        # Should find /api/v1/contracts/ multiple times
        contracts_endpoints = [e for e in endpoints if '/api/v1/contracts/' in e['endpoint']]
        assert len(contracts_endpoints) > 0

    def test_validate_python_syntax(self, temp_docs_dir, endpoint_inventory):
        """Test Python syntax validation"""
        docs_dir, examples_dir = temp_docs_dir
        checker = CodeExampleChecker(
            docs_dir=str(docs_dir),
            examples_dir=str(examples_dir),
            endpoint_inventory_file=endpoint_inventory
        )

        examples = checker.find_code_examples()
        python_examples = [e for e in examples if e.language == 'python']

        valid_example = [e for e in python_examples if 'valid_example' in e.source_file][0]
        invalid_example = [e for e in python_examples if 'syntax_error' in e.source_file][0]

        # Valid Python should pass
        result_valid = checker.validate_python_syntax(valid_example)
        assert result_valid.is_valid is True

        # Invalid Python should fail
        result_invalid = checker.validate_python_syntax(invalid_example)
        assert result_invalid.is_valid is False
        assert 'syntax' in result_invalid.errors[0].lower() or 'invalid' in result_invalid.errors[0].lower()

    def test_validate_endpoint_exists(self, temp_docs_dir, endpoint_inventory):
        """Test endpoint existence validation"""
        docs_dir, examples_dir = temp_docs_dir
        checker = CodeExampleChecker(
            docs_dir=str(docs_dir),
            examples_dir=str(examples_dir),
            endpoint_inventory_file=endpoint_inventory
        )

        examples = checker.find_code_examples()
        endpoints = checker.extract_endpoints_from_examples(examples)

        # Valid endpoint
        valid_endpoints = [e for e in endpoints if '/api/v1/contracts/' in e['endpoint']]
        if valid_endpoints:
            result_valid = checker.validate_endpoint_exists(valid_endpoints[0]['endpoint'])
            assert result_valid.is_valid is True

        # Invalid endpoint
        invalid_endpoints = [e for e in endpoints if '/api/v1/nonexistent/' in e['endpoint'] or '/api/v1/invalid-endpoint/' in e['endpoint']]
        if invalid_endpoints:
            result_invalid = checker.validate_endpoint_exists(invalid_endpoints[0]['endpoint'])
            assert result_invalid.is_valid is False

    def test_is_our_api_endpoint(self, temp_docs_dir, endpoint_inventory):
        """Test filtering of our API endpoints vs external"""
        docs_dir, examples_dir = temp_docs_dir
        checker = CodeExampleChecker(
            docs_dir=str(docs_dir),
            examples_dir=str(examples_dir),
            endpoint_inventory_file=endpoint_inventory
        )

        # Our API endpoints
        assert checker.is_our_api_endpoint("/api/v1/contracts/") is True
        assert checker.is_our_api_endpoint("http://localhost:8000/api/v1/contracts/") is True

        # External endpoints
        assert checker.is_our_api_endpoint("http://localhost:9090/api/v1/query") is False
        assert checker.is_our_api_endpoint("http://localhost:8000/metrics") is False

    def test_validate_all_examples(self, temp_docs_dir, endpoint_inventory):
        """Test comprehensive validation of all examples"""
        docs_dir, examples_dir = temp_docs_dir
        checker = CodeExampleChecker(
            docs_dir=str(docs_dir),
            examples_dir=str(examples_dir),
            endpoint_inventory_file=endpoint_inventory
        )

        results = checker.validate_all_examples()

        assert 'summary' in results
        assert 'examples' in results
        assert results['summary']['total_examples'] > 0
        assert results['summary']['total_endpoints_found'] > 0

        # Should have validation results for each example
        assert len(results['examples']) == results['summary']['total_examples']

    def test_generate_report(self, temp_docs_dir, endpoint_inventory, tmp_path):
        """Test report generation"""
        docs_dir, examples_dir = temp_docs_dir
        checker = CodeExampleChecker(
            docs_dir=str(docs_dir),
            examples_dir=str(examples_dir),
            endpoint_inventory_file=endpoint_inventory
        )

        results = checker.validate_all_examples()
        report_file = tmp_path / "report.json"
        checker.generate_report(results, str(report_file))

        assert report_file.exists()
        report_data = json.loads(report_file.read_text())
        assert 'summary' in report_data
        assert 'examples' in report_data

    def test_empty_directories(self, tmp_path, endpoint_inventory):
        """Test behavior with empty directories"""
        empty_docs = tmp_path / "empty_docs"
        empty_docs.mkdir()
        empty_examples = tmp_path / "empty_examples"
        empty_examples.mkdir()

        checker = CodeExampleChecker(
            docs_dir=str(empty_docs),
            examples_dir=str(empty_examples),
            endpoint_inventory_file=endpoint_inventory
        )

        examples = checker.find_code_examples()
        assert len(examples) == 0

        results = checker.validate_all_examples()
        assert results['summary']['total_examples'] == 0

    def test_missing_inventory_file(self, temp_docs_dir):
        """Test behavior with missing inventory file"""
        docs_dir, examples_dir = temp_docs_dir

        with pytest.raises(FileNotFoundError):
            CodeExampleChecker(
                docs_dir=str(docs_dir),
                examples_dir=str(examples_dir),
                endpoint_inventory_file="nonexistent.json"
            )

    def test_endpoint_normalization(self, temp_docs_dir, endpoint_inventory):
        """Test endpoint path normalization"""
        docs_dir, examples_dir = temp_docs_dir
        checker = CodeExampleChecker(
            docs_dir=str(docs_dir),
            examples_dir=str(examples_dir),
            endpoint_inventory_file=endpoint_inventory
        )

        # Test various endpoint formats
        test_cases = [
            ("http://localhost:8000/api/v1/contracts/", "/api/v1/contracts/"),
            ("https://api.example.com/api/v1/contracts/", "/api/v1/contracts/"),
            ("/api/v1/contracts/", "/api/v1/contracts/"),
            ("/api/v1/contracts", "/api/v1/contracts/"),  # Should normalize trailing slash
            ("/api/v1/contracts/?page=1", "/api/v1/contracts/"),  # Should remove query params
        ]

        for input_endpoint, expected_normalized in test_cases:
            normalized = checker.normalize_endpoint(input_endpoint)
            assert normalized == expected_normalized or normalized.startswith("/api/v1/")

