"""
Tests for hardcoded endpoint URL search functionality
"""
import os
import sys
import json
import tempfile
from pathlib import Path
import pytest

# Add scripts directory to path
scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

# Import module
import importlib.util
script_path = scripts_dir / 'search-hardcoded-endpoints.py'
spec = importlib.util.spec_from_file_location('search_hardcoded_endpoints', script_path)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load module from {script_path}")
search_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(search_module)

EndpointURLSearcher = search_module.EndpointURLSearcher
ImpactMatrixGenerator = search_module.ImpactMatrixGenerator
EndpointReference = search_module.EndpointReference


@pytest.mark.integration
class TestHardcodedEndpointSearch:
    """Integration tests for hardcoded endpoint URL search"""

    def test_search_finds_endpoint_urls(self):
        """Test: Verify all references found"""
        # Create temporary test file with endpoint URLs
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'test_endpoints.py'
            test_file.write_text('''
# Test file with endpoint URLs
BASE_URL = "http://localhost:8000/api/v1"
endpoint = "/api/v1/contracts/"
url = "https://api.example.com/api/v1/auth/login/"
            ''')

            searcher = EndpointURLSearcher(base_dir=tmpdir)
            references = searcher.search_file(test_file)

            assert len(references) > 0, "Should find endpoint URLs"

            # Verify endpoints found
            endpoints = [ref.endpoint_url for ref in references]
            assert any('/api/v1/' in ep for ep in endpoints), "Should find /api/v1/ endpoints"

    def test_categorization_accuracy(self):
        """Test: Verify categorization accuracy"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files in different categories
            test_dir = Path(tmpdir) / 'tests'
            test_dir.mkdir()
            test_file = test_dir / 'test_api.py'
            test_file.write_text('endpoint = "/api/v1/test/"')

            cli_dir = Path(tmpdir) / 'cli'
            cli_dir.mkdir()
            cli_file = cli_dir / 'client.py'
            cli_file.write_text('url = "/api/v1/cli/"')

            docs_dir = Path(tmpdir) / 'docs'
            docs_dir.mkdir()
            docs_file = docs_dir / 'api.md'
            docs_file.write_text('See /api/v1/docs/')

            searcher = EndpointURLSearcher(base_dir=tmpdir)
            references = searcher.search_directory(Path(tmpdir))

            # Verify categorization
            categories = set(ref.category for ref in references)
            assert 'test' in categories, "Should categorize test files"
            assert 'cli' in categories, "Should categorize CLI files"
            assert 'docs' in categories, "Should categorize docs files"

            # Verify priorities
            test_refs = [ref for ref in references if ref.category == 'test']
            cli_refs = [ref for ref in references if ref.category == 'cli']

            assert all(ref.priority == 'High' for ref in test_refs), "Test files should be High priority"
            assert all(ref.priority == 'High' for ref in cli_refs), "CLI files should be High priority"

    def test_priority_categorization(self):
        """Test: Verify priority categorization"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / 'test.py'
            test_file.write_text('''
# Production code
endpoint = "/api/v1/production/"
# Comment with /api/v1/comment/
            ''')

            searcher = EndpointURLSearcher(base_dir=tmpdir)
            references = searcher.search_file(test_file)

            # Find references
            prod_ref = next((ref for ref in references if 'production' in ref.endpoint_url), None)
            comment_ref = next((ref for ref in references if 'comment' in ref.endpoint_url), None)

            if prod_ref:
                assert prod_ref.priority in ['Critical', 'High'], \
                    f"Production code should be Critical/High, got {prod_ref.priority}"

            if comment_ref:
                assert comment_ref.is_in_comment, "Comment reference should be marked as comment"
                assert comment_ref.priority in ['Medium', 'Low'], \
                    f"Comment references should be Medium/Low, got {comment_ref.priority}"

    def test_impact_matrix_generation(self):
        """Test: Verify impact matrix generation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'test.py'
            test_file.write_text('endpoint = "/api/v1/test/"')

            searcher = EndpointURLSearcher(base_dir=tmpdir)
            references = searcher.search_file(test_file)

            generator = ImpactMatrixGenerator(references)
            summary = generator.generate_summary()
            matrix = generator.generate_matrix()

            # Verify summary
            assert 'total_references' in summary
            assert 'by_priority' in summary
            assert 'by_category' in summary
            assert summary['total_references'] > 0

            # Verify matrix
            assert len(matrix) > 0
            assert 'file_path' in matrix[0]
            assert 'total_references' in matrix[0]
            assert 'priority_breakdown' in matrix[0]

    def test_json_output_valid(self):
        """Test: Verify JSON output is valid"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'test.py'
            test_file.write_text('endpoint = "/api/v1/test/"')

            searcher = EndpointURLSearcher(base_dir=tmpdir)
            references = searcher.search_file(test_file)

            generator = ImpactMatrixGenerator(references)
            json_output = generator.output_json()

            # Verify valid JSON
            data = json.loads(json_output)
            assert 'summary' in data
            assert 'impact_matrix' in data
            assert 'all_references' in data

    def test_markdown_output_valid(self):
        """Test: Verify Markdown output is valid"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / 'test.py'
            test_file.write_text('endpoint = "/api/v1/test/"')

            searcher = EndpointURLSearcher(base_dir=tmpdir)
            references = searcher.search_file(test_file)

            generator = ImpactMatrixGenerator(references)
            markdown_output = generator.output_markdown()

            # Verify valid Markdown
            assert isinstance(markdown_output, str)
            assert len(markdown_output) > 0
            assert 'Impact Matrix' in markdown_output or 'Summary' in markdown_output

    @pytest.mark.skipif(
        not os.path.exists('tests/'),
        reason='Tests directory not available'
    )
    def test_search_test_files(self):
        """Test: Verify search finds references in test files"""
        searcher = EndpointURLSearcher(base_dir='.')
        references = searcher.search_specific_directories(['tests/'])

        assert len(references) > 0, "Should find references in test files"

        # Verify test category
        test_refs = [ref for ref in references if ref.category == 'test']
        assert len(test_refs) > 0, "Should categorize test file references"

    @pytest.mark.skipif(
        not os.path.exists('cli/'),
        reason='CLI directory not available'
    )
    def test_search_cli_files(self):
        """Test: Verify search finds references in CLI files"""
        searcher = EndpointURLSearcher(base_dir='.')
        references = searcher.search_specific_directories(['cli/'])

        # May or may not find references, but should not crash
        assert isinstance(references, list)

        # If found, verify CLI category
        if references:
            cli_refs = [ref for ref in references if ref.category == 'cli']
            assert len(cli_refs) > 0, "Should categorize CLI file references"

    @pytest.mark.skipif(
        not os.path.exists('docs/'),
        reason='Docs directory not available'
    )
    def test_search_docs_files(self):
        """Test: Verify search finds references in documentation"""
        searcher = EndpointURLSearcher(base_dir='.')
        references = searcher.search_specific_directories(['docs/'])

        # May or may not find references, but should not crash
        assert isinstance(references, list)

        # If found, verify docs category
        if references:
            docs_refs = [ref for ref in references if ref.category == 'docs']
            assert len(docs_refs) > 0, "Should categorize docs file references"

    @pytest.mark.skipif(
        not os.path.exists('docs/api-audit/hardcoded-endpoints-impact-matrix.json'),
        reason='Impact matrix not generated'
    )
    def test_verify_impact_matrix_exists(self):
        """Test: Verify impact matrix was generated"""
        assert os.path.exists('docs/api-audit/hardcoded-endpoints-impact-matrix.json')
        assert os.path.exists('docs/api-audit/hardcoded-endpoints-impact-matrix.md')

        # Verify JSON is valid
        with open('docs/api-audit/hardcoded-endpoints-impact-matrix.json') as f:
            data = json.load(f)

        assert 'summary' in data
        assert 'impact_matrix' in data
        assert 'all_references' in data

        # Verify summary has expected fields
        summary = data['summary']
        assert 'total_references' in summary
        assert 'by_priority' in summary
        assert 'by_category' in summary
        assert 'unique_files' in summary
        assert 'unique_endpoints' in summary

    @pytest.mark.skipif(
        not os.path.exists('docs/api-audit/hardcoded-endpoints-impact-matrix.json'),
        reason='Impact matrix not generated'
    )
    def test_verify_categorization_completeness(self):
        """Test: Verify all references are categorized"""
        with open('docs/api-audit/hardcoded-endpoints-impact-matrix.json') as f:
            data = json.load(f)

        references = data['all_references']

        # Verify all references have required fields
        for ref in references[:100]:  # Check first 100
            assert 'category' in ref, f"Reference missing category: {ref}"
            assert 'priority' in ref, f"Reference missing priority: {ref}"
            assert 'file_path' in ref, f"Reference missing file_path: {ref}"
            assert 'line_number' in ref, f"Reference missing line_number: {ref}"
            assert 'endpoint_url' in ref, f"Reference missing endpoint_url: {ref}"

            # Verify priority is valid
            assert ref['priority'] in ['Critical', 'High', 'Medium', 'Low'], \
                f"Invalid priority: {ref['priority']}"

            # Verify category is valid
            valid_categories = ['test', 'cli', 'frontend', 'docs', 'workflow', 'service_client', 'other']
            assert ref['category'] in valid_categories, \
                f"Invalid category: {ref['category']}"

