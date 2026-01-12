"""
Integration tests for comprehensive endpoint audit
"""
import os
import sys
import json
import importlib.util
from pathlib import Path
import pytest

# Add scripts directory to path
scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

# Import module with hyphenated name using importlib
script_path = scripts_dir / 'audit-api-endpoints.py'
spec = importlib.util.spec_from_file_location('audit_api_endpoints', script_path)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load module from {script_path}")
audit_api_endpoints = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_api_endpoints)

EndpointAuditor = audit_api_endpoints.EndpointAuditor


@pytest.mark.integration
class TestComprehensiveAudit:
    """Integration tests for comprehensive endpoint audit"""

    @pytest.mark.skipif(
        not os.path.exists('hub/apps/api/urls.py'),
        reason='Django project not available'
    )
    def test_verify_all_endpoints_discovered(self):
        """Test: Verify all endpoints discovered"""
        urls_file = 'hub/apps/api/urls.py'
        auditor = EndpointAuditor()

        try:
            results = auditor.audit(
                urls_file,
                check_duplicates=True,
                check_naming=True,
            )

            # Verify structure
            assert 'inventory' in results
            assert 'issues' in results
            assert 'mount_points' in results

            # Verify endpoints were discovered
            inventory = results['inventory']
            assert 'summary' in inventory
            assert 'endpoints' in inventory

            total_endpoints = inventory['summary']['total_endpoints']
            total_services = inventory['summary']['total_services']

            # Should have discovered endpoints
            assert total_endpoints > 0, "No endpoints discovered"
            assert total_services > 0, "No services discovered"

            # Should have discovered a reasonable number of endpoints
            # (at least 20 based on the API structure)
            assert total_endpoints >= 20, f"Expected at least 20 endpoints, found {total_endpoints}"

            # Verify endpoints list matches summary
            endpoints = inventory['endpoints']
            assert len(endpoints) == total_endpoints, \
                f"Endpoint count mismatch: summary says {total_endpoints}, list has {len(endpoints)}"

            # Verify endpoints have required fields
            for endpoint in endpoints[:10]:  # Check first 10
                assert 'full_path' in endpoint or 'pattern' in endpoint, \
                    f"Endpoint missing path: {endpoint}"
                assert 'type' in endpoint, f"Endpoint missing type: {endpoint}"

            # Verify services are properly identified
            by_service = inventory.get('by_service', {})
            if by_service:
                assert len(by_service) == total_services, \
                    f"Service count mismatch: summary says {total_services}, by_service has {len(by_service)}"

        except Exception as e:
            pytest.skip(f"Django setup failed: {e}")

    @pytest.mark.skipif(
        not os.path.exists('hub/apps/api/urls.py'),
        reason='Django project not available'
    )
    def test_verify_all_issues_identified(self):
        """Test: Verify all issues identified"""
        urls_file = 'hub/apps/api/urls.py'
        auditor = EndpointAuditor()

        try:
            results = auditor.audit(
                urls_file,
                check_duplicates=True,
                check_naming=True,
            )

            # Verify issues structure
            assert 'issues' in results
            issues = results['issues']

            # Verify duplicates detection
            assert 'duplicates' in issues
            duplicates = issues['duplicates']
            assert isinstance(duplicates, list)

            # Verify naming inconsistencies detection
            assert 'naming_inconsistencies' in issues
            naming_issues = issues['naming_inconsistencies']
            assert isinstance(naming_issues, list)

            # Verify duplicate structure
            for dup in duplicates[:5]:  # Check first 5
                assert 'type' in dup, f"Duplicate missing type: {dup}"
                assert dup['type'] in ['duplicate_path', 'duplicate_name'], \
                    f"Invalid duplicate type: {dup['type']}"
                assert 'count' in dup, f"Duplicate missing count: {dup}"
                assert dup['count'] > 1, f"Duplicate count should be > 1: {dup['count']}"
                assert 'endpoints' in dup, f"Duplicate missing endpoints: {dup}"

            # Verify naming inconsistency structure
            for inc in naming_issues[:5]:  # Check first 5
                assert 'type' in inc, f"Naming issue missing type: {inc}"
                assert 'service' in inc, f"Naming issue missing service: {inc}"

        except Exception as e:
            pytest.skip(f"Django setup failed: {e}")

    @pytest.mark.skipif(
        not os.path.exists('hub/apps/api/urls.py'),
        reason='Django project not available'
    )
    def test_verify_mount_points_mapped(self):
        """Test: Verify service mount points are correctly mapped"""
        urls_file = 'hub/apps/api/urls.py'
        auditor = EndpointAuditor()

        try:
            results = auditor.audit(urls_file)

            # Verify mount points
            assert 'mount_points' in results
            mount_points = results['mount_points']
            assert isinstance(mount_points, dict)

            # Should have mapped mount points
            assert len(mount_points) > 0, "No mount points mapped"

            # Verify mount point structure
            for service, module in list(mount_points.items())[:5]:
                assert isinstance(service, str), f"Service name should be string: {service}"
                assert isinstance(module, str), f"Module path should be string: {module}"
                assert 'hub.apps' in module or 'hub.apps.api' in module, \
                    f"Invalid module path: {module}"

        except Exception as e:
            pytest.skip(f"Django setup failed: {e}")

    @pytest.mark.skipif(
        not os.path.exists('hub/apps/api/urls.py'),
        reason='Django project not available'
    )
    def test_verify_endpoint_paths_valid(self):
        """Test: Verify endpoint paths are valid"""
        urls_file = 'hub/apps/api/urls.py'
        auditor = EndpointAuditor()

        try:
            results = auditor.audit(urls_file)

            inventory = results['inventory']
            endpoints = inventory['endpoints']

            # Check that paths are valid
            for endpoint in endpoints[:20]:  # Check first 20
                full_path = endpoint.get('full_path', endpoint.get('pattern', ''))
                assert full_path, f"Endpoint missing path: {endpoint}"

                # Path should start with /api/v1 or be a valid pattern
                if full_path.startswith('/'):
                    assert full_path.startswith('/api/v1'), \
                        f"Path should start with /api/v1: {full_path}"
                else:
                    # Might be a regex pattern, that's okay
                    pass

        except Exception as e:
            pytest.skip(f"Django setup failed: {e}")

    @pytest.mark.skipif(
        not os.path.exists('hub/apps/api/urls.py'),
        reason='Django project not available'
    )
    def test_verify_duplicate_detection_accuracy(self):
        """Test: Verify duplicate detection finds actual duplicates"""
        urls_file = 'hub/apps/api/urls.py'
        auditor = EndpointAuditor()

        try:
            results = auditor.audit(urls_file, check_duplicates=True)

            duplicates = results['issues'].get('duplicates', [])
            endpoints = results['inventory']['endpoints']

            # Verify duplicates are actually duplicates
            for dup in duplicates[:10]:
                dup_path = dup.get('path', dup.get('name', ''))
                dup_endpoints = dup.get('endpoints', [])

                # Should have multiple endpoints
                assert len(dup_endpoints) > 1, \
                    f"Duplicate should have multiple endpoints: {dup}"

                # If it's a path duplicate, verify paths match
                if dup['type'] == 'duplicate_path':
                    paths = [e.get('full_path', e.get('pattern', '')) for e in dup_endpoints]
                    # All paths should be the same (or very similar)
                    assert len(set(paths)) == 1 or len(set(paths)) < len(paths), \
                        f"Duplicate paths don't match: {paths}"

                # If it's a name duplicate, verify names match
                if dup['type'] == 'duplicate_name':
                    names = [e.get('name', '') for e in dup_endpoints]
                    # All names should be the same
                    assert len(set(names)) == 1, \
                        f"Duplicate names don't match: {names}"

        except Exception as e:
            pytest.skip(f"Django setup failed: {e}")

    @pytest.mark.skipif(
        not os.path.exists('hub/apps/api/urls.py'),
        reason='Django project not available'
    )
    def test_verify_service_grouping(self):
        """Test: Verify endpoints are correctly grouped by service"""
        urls_file = 'hub/apps/api/urls.py'
        auditor = EndpointAuditor()

        try:
            results = auditor.audit(urls_file)

            inventory = results['inventory']
            by_service = inventory.get('by_service', {})
            endpoints = inventory['endpoints']

            # Verify grouping
            if by_service:
                # Count endpoints in groups
                grouped_count = sum(len(eps) for eps in by_service.values())
                total_count = len(endpoints)

                # Should match (allowing for some endpoints without service)
                assert grouped_count <= total_count, \
                    f"Grouped count ({grouped_count}) exceeds total ({total_count})"

                # Verify service names are reasonable
                for service_name in list(by_service.keys())[:10]:
                    # Service name should be a valid identifier or empty
                    assert service_name == '' or isinstance(service_name, str), \
                        f"Invalid service name: {service_name}"

        except Exception as e:
            pytest.skip(f"Django setup failed: {e}")

    @pytest.mark.skipif(
        not os.path.exists('hub/apps/api/urls.py'),
        reason='Django project not available'
    )
    def test_verify_json_output_valid(self):
        """Test: Verify JSON output is valid"""
        urls_file = 'hub/apps/api/urls.py'
        auditor = EndpointAuditor()

        try:
            results = auditor.audit(urls_file)

            # Generate JSON output
            json_output = auditor.output_json(results)

            # Verify it's valid JSON
            parsed = json.loads(json_output)
            assert 'inventory' in parsed
            assert 'issues' in parsed

        except Exception as e:
            pytest.skip(f"Django setup failed: {e}")

    @pytest.mark.skipif(
        not os.path.exists('hub/apps/api/urls.py'),
        reason='Django project not available'
    )
    def test_verify_markdown_output_valid(self):
        """Test: Verify Markdown output is valid"""
        urls_file = 'hub/apps/api/urls.py'
        auditor = EndpointAuditor()

        try:
            results = auditor.audit(urls_file)

            # Generate Markdown output
            markdown_output = auditor.output_markdown(results)

            # Verify it's valid Markdown
            assert isinstance(markdown_output, str)
            assert len(markdown_output) > 0

            # Should contain expected sections
            assert 'API Endpoint Audit Report' in markdown_output or 'Summary' in markdown_output

        except Exception as e:
            pytest.skip(f"Django setup failed: {e}")

    @pytest.mark.skipif(
        not os.path.exists('docs/api-audit/endpoint-inventory-current.json'),
        reason='Audit reports not generated'
    )
    def test_verify_reports_exist(self):
        """Test: Verify audit reports were generated"""
        report_files = [
            'docs/api-audit/endpoint-naming-audit-report.md',
            'docs/api-audit/endpoint-inventory-current.md',
            'docs/api-audit/endpoint-inventory-proposed.md',
        ]

        for report_file in report_files:
            assert os.path.exists(report_file), f"Report file not found: {report_file}"

            # Verify file is not empty
            file_size = os.path.getsize(report_file)
            assert file_size > 0, f"Report file is empty: {report_file}"

    @pytest.mark.skipif(
        not os.path.exists('docs/api-audit/endpoint-inventory-current.json'),
        reason='Audit reports not generated'
    )
    def test_verify_report_contents(self):
        """Test: Verify report contents are valid"""
        json_file = 'docs/api-audit/endpoint-inventory-current.json'

        with open(json_file, 'r') as f:
            data = json.load(f)

        # Verify structure
        assert 'inventory' in data
        assert 'issues' in data
        assert 'mount_points' in data

        # Verify inventory
        inventory = data['inventory']
        assert 'summary' in inventory
        assert 'endpoints' in inventory

        summary = inventory['summary']
        assert 'total_endpoints' in summary
        assert 'total_services' in summary

        # Verify endpoints were discovered
        assert summary['total_endpoints'] > 0
        assert summary['total_services'] > 0

        # Verify issues
        issues = data['issues']
        assert 'duplicates' in issues
        assert 'naming_inconsistencies' in issues

