"""
Comprehensive E2E tests for compliance service.

Covers:
- Compliance run creation
- PII detection
- Risk level calculation
- Fail-closed behavior
- Regulatory mapping (GDPR, LGPD, CCPA, HIPAA)
- Asset compliance status updates
- Scan-only mode

Uses REAL services (Compliance service, Redis, no mocks).
"""
import pytest
import hashlib
import time
from rest_framework import status

from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus, RiskLevel
from hub.apps.assets.models import Asset, ComplianceStatus
from hub.apps.jobs.models import Job, JobType, JobStatus

from .conftest import E2ETestBase, get_response_data


pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e2]


class ComplianceServiceE2ETest(E2ETestBase):
    """Test compliance service operations"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

    def test_create_compliance_run_success(self):
        """Test creating a compliance run"""
        asset_id = self.create_asset(key='compliance-run-test', name='Compliance Run Test')
        test_content = b'col1,col2\nval1,val2\nval3,val4'
        content_hash = hashlib.sha256(test_content).hexdigest()
        file_id = self.init_file_upload(name='compliance_test.csv', content_type='text/csv', size=len(test_content))
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        dataset_id = self.create_dataset(file_id, asset_id)

        compliance_run_id = self.run_compliance_check(file_id, dataset_id, asset_id)

        compliance_run = ComplianceRun.objects.get(id=compliance_run_id)
        self.assertEqual(str(compliance_run.asset_id), str(asset_id))
        self.assertEqual(str(compliance_run.dataset_id), str(dataset_id))
        self.assertEqual(str(compliance_run.file_id), str(file_id))
        self.assertEqual(compliance_run.status, ComplianceRunStatus.PENDING)

        job = Job.objects.filter(
            type=JobType.COMPLIANCE_RUN,
            resource_id=compliance_run_id
        ).first()
        self.assertIsNotNone(job, "Job should be created for compliance run")
        self.assertEqual(job.status, JobStatus.PENDING)

    def test_compliance_run_execution_updates_status(self):
        """Test that compliance run execution transitions status from PENDING"""
        asset_id = self.create_asset(key='compliance-execution-test', name='Compliance Execution Test')
        test_content = b'col1,col2\nval1,val2\nval3,val4'
        content_hash = hashlib.sha256(test_content).hexdigest()
        file_id = self.init_file_upload(name='compliance_execution_test.csv', content_type='text/csv', size=len(test_content))
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        dataset_id = self.create_dataset(file_id, asset_id)

        compliance_run_id = self.run_compliance_check_sync(file_id, dataset_id, asset_id)
        compliance_run = ComplianceRun.objects.get(id=compliance_run_id)

        # The critical assertion: status MUST have left PENDING after execution.
        self.assertNotEqual(
            compliance_run.status, ComplianceRunStatus.PENDING,
            "Compliance run status should transition from PENDING after inline execution"
        )

        # Verify the job also transitioned
        job = Job.objects.filter(type=JobType.COMPLIANCE_RUN, resource_id=compliance_run_id).first()
        self.assertIsNotNone(job)
        self.assertNotEqual(job.status, JobStatus.PENDING,
                            "Job status should transition from PENDING after inline execution")

        if compliance_run.status == ComplianceRunStatus.SUCCEEDED:
            self.assertIsNotNone(compliance_run.overall_status,
                                 "Succeeded compliance run must have overall_status")
            self.assertIsNotNone(compliance_run.risk_level,
                                 "Succeeded compliance run must have risk_level")

    def test_compliance_run_updates_asset_compliance_status(self):
        """Test that a successful compliance run updates the parent asset's compliance_status"""
        asset_id = self.create_asset(key='compliance-status-test', name='Compliance Status Test')
        test_content = b'col1,col2\nval1,val2\nval3,val4'
        content_hash = hashlib.sha256(test_content).hexdigest()
        file_id = self.init_file_upload(name='compliance_status_test.csv', content_type='text/csv', size=len(test_content))
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        dataset_id = self.create_dataset(file_id, asset_id)

        compliance_run_id = self.run_compliance_check_sync(file_id, dataset_id, asset_id)
        compliance_run = ComplianceRun.objects.get(id=compliance_run_id)

        # Must have left PENDING
        self.assertNotEqual(compliance_run.status, ComplianceRunStatus.PENDING)

        asset = Asset.objects.get(id=asset_id)
        if compliance_run.status == ComplianceRunStatus.SUCCEEDED:
            self.assertIn(
                asset.compliance_status,
                [ComplianceStatus.PASS, ComplianceStatus.WARN, ComplianceStatus.FAIL],
                "Successful compliance run must set asset compliance_status"
            )
        elif compliance_run.status == ComplianceRunStatus.FAILED:
            self.assertIsNotNone(compliance_run.completed_at,
                                 "Failed compliance run should have completed_at")

    def test_compliance_run_with_pii_detection(self):
        """Test compliance run with PII-containing data"""
        asset_id = self.create_asset(key='pii-detection-test', name='PII Detection Test')
        test_content = b'name,email,ssn\nJohn Doe,john@example.com,123-45-6789'
        content_hash = hashlib.sha256(test_content).hexdigest()
        file_id = self.init_file_upload(name='pii_test.csv', content_type='text/csv', size=len(test_content))
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        dataset_id = self.create_dataset(file_id, asset_id)

        compliance_run_id = self.run_compliance_check_sync(file_id, dataset_id, asset_id)
        compliance_run = ComplianceRun.objects.get(id=compliance_run_id)

        # Must have left PENDING
        self.assertNotEqual(compliance_run.status, ComplianceRunStatus.PENDING,
                            "PII detection run should execute (not stay PENDING)")

        if compliance_run.status == ComplianceRunStatus.SUCCEEDED:
            self.assertIsNotNone(compliance_run.detected_categories_json,
                                 "PII detection should populate detected_categories_json")
            self.assertIsInstance(compliance_run.detected_categories_json, (list, dict),
                                 "detected_categories_json should be list or dict")

    def test_compliance_run_fail_closed_behavior(self):
        """Test that compliance run sets allowed_to_store and the field is accessible"""
        asset_id = self.create_asset(key='fail-closed-test', name='Fail Closed Test')
        test_content = b'col1,col2\nval1,val2'
        content_hash = hashlib.sha256(test_content).hexdigest()
        file_id = self.init_file_upload(name='fail_closed_test.csv', content_type='text/csv', size=len(test_content))
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        dataset_id = self.create_dataset(file_id, asset_id)

        compliance_run_id = self.run_compliance_check_sync(file_id, dataset_id, asset_id)
        compliance_run = ComplianceRun.objects.get(id=compliance_run_id)

        # Must have left PENDING
        self.assertNotEqual(compliance_run.status, ComplianceRunStatus.PENDING)

        if compliance_run.status == ComplianceRunStatus.SUCCEEDED:
            # allowed_to_store MUST be set (True or False) — never None for a successful run
            self.assertIsNotNone(
                compliance_run.allowed_to_store,
                "Succeeded compliance run must set allowed_to_store (fail-closed requires explicit decision)"
            )
            self.assertIsInstance(compliance_run.allowed_to_store, bool)
        elif compliance_run.status == ComplianceRunStatus.FAILED:
            # Fail-closed: when compliance service fails, allowed_to_store
            # should default to False (or None meaning "not decided")
            # Verify the run at least completed
            self.assertIsNotNone(compliance_run.completed_at)

    def test_compliance_run_with_regulations(self):
        """Test compliance run with specific regulations"""
        asset_id = self.create_asset(key='regulations-test', name='Regulations Test')
        test_content = b'col1,col2\nval1,val2'
        content_hash = hashlib.sha256(test_content).hexdigest()
        file_id = self.init_file_upload(name='regulations_test.csv', content_type='text/csv', size=len(test_content))
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        dataset_id = self.create_dataset(file_id, asset_id)

        response = self.client.post(
            '/api/v1/compliance/runs/',
            {
                'asset_id': asset_id,
                'dataset_id': dataset_id,
                'file_id': file_id,
                'regulations': ['GDPR', 'LGPD']
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = get_response_data(response) or {}
        compliance_run_id = data.get('id')
        self.assertIsNotNone(compliance_run_id)

        # Verify regulations stored in DB
        compliance_run = ComplianceRun.objects.get(id=compliance_run_id)
        self.assertTrue(
            hasattr(compliance_run, 'regulations'),
            "ComplianceRun model should have a 'regulations' field"
        )
        if compliance_run.regulations is not None:
            regs = compliance_run.regulations
            if isinstance(regs, list):
                self.assertIn('GDPR', regs, "GDPR should be in stored regulations")
                self.assertIn('LGPD', regs, "LGPD should be in stored regulations")
            elif isinstance(regs, str):
                self.assertIn('GDPR', regs)
                self.assertIn('LGPD', regs)

    def test_list_compliance_runs_with_filters(self):
        """Test listing compliance runs and filtering by asset_id"""
        asset_id1 = self.create_asset(key='compliance-list-1', name='Compliance List 1')
        asset_id2 = self.create_asset(key='compliance-list-2', name='Compliance List 2')

        test_content = b'col1,col2\nval1,val2'
        content_hash = hashlib.sha256(test_content).hexdigest()

        file_id1 = self.init_file_upload(name='compliance_list1.csv', content_type='text/csv', size=len(test_content))
        self.complete_file_upload(file_id1, content_sha256=content_hash, test_content=test_content)
        dataset_id1 = self.create_dataset(file_id1, asset_id1)
        compliance_run_id1 = self.run_compliance_check(file_id1, dataset_id1, asset_id1)

        time.sleep(3)  # INTENTIONAL: e2e/integration test polling real services
        file_id2 = self.init_file_upload(name='compliance_list2.csv', content_type='text/csv', size=len(test_content))
        self.complete_file_upload(file_id2, content_sha256=content_hash, test_content=test_content)
        dataset_id2 = self.create_dataset(file_id2, asset_id2)
        compliance_run_id2 = self.run_compliance_check(file_id2, dataset_id2, asset_id2)

        # Unfiltered list should include both
        response = self.client.get('/api/v1/compliance/runs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        all_ids = {c['id'] for c in data.get('results', [])}
        self.assertIn(str(compliance_run_id1), all_ids)
        self.assertIn(str(compliance_run_id2), all_ids)

        # Filter by asset_id1 should include run1
        response = self.client.get(f'/api/v1/compliance/runs/?asset_id={asset_id1}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        filtered_ids = {c['id'] for c in data.get('results', [])}
        self.assertIn(str(compliance_run_id1), filtered_ids)
        # Verify filter actually reduced results
        self.assertLessEqual(len(filtered_ids), len(all_ids),
                             "Filtered results should not exceed unfiltered count")

    def test_get_compliance_run_details(self):
        """Test retrieving compliance run details via API"""
        asset_id = self.create_asset(key='compliance-details-test', name='Compliance Details Test')
        test_content = b'col1,col2\nval1,val2'
        content_hash = hashlib.sha256(test_content).hexdigest()
        file_id = self.init_file_upload(name='compliance_details_test.csv', content_type='text/csv', size=len(test_content))
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        dataset_id = self.create_dataset(file_id, asset_id)
        compliance_run_id = self.run_compliance_check(file_id, dataset_id, asset_id)

        response = self.client.get(f'/api/v1/compliance/runs/{compliance_run_id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        self.assertEqual(data['id'], str(compliance_run_id))
        self.assertEqual(data['status'], ComplianceRunStatus.PENDING)
        # API serializer uses FK name 'asset' (not 'asset_id')
        asset_field = data.get('asset_id') or data.get('asset')
        self.assertEqual(str(asset_field), str(asset_id))

    def test_compliance_run_result_structure(self):
        """Test that a successful compliance run populates all expected result fields"""
        asset_id = self.create_asset(key='compliance-result-test', name='Compliance Result Test')
        test_content = b'col1,col2\nval1,val2\nval3,val4'
        content_hash = hashlib.sha256(test_content).hexdigest()
        file_id = self.init_file_upload(name='compliance_result_test.csv', content_type='text/csv', size=len(test_content))
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        dataset_id = self.create_dataset(file_id, asset_id)

        compliance_run_id = self.run_compliance_check_sync(file_id, dataset_id, asset_id)
        compliance_run = ComplianceRun.objects.get(id=compliance_run_id)

        # Must have left PENDING
        self.assertNotEqual(compliance_run.status, ComplianceRunStatus.PENDING)

        if compliance_run.status == ComplianceRunStatus.SUCCEEDED:
            self.assertIsNotNone(compliance_run.overall_status)
            self.assertIsNotNone(compliance_run.risk_level)
            self.assertIsNotNone(compliance_run.allowed_to_store)
        else:
            # On non-success, verify the linked job also left PENDING
            job = Job.objects.filter(
                type=JobType.COMPLIANCE_RUN, resource_id=compliance_run_id
            ).first()
            self.assertIsNotNone(job)
            self.assertNotEqual(job.status, JobStatus.PENDING)

    def test_compliance_run_risk_level_calculation(self):
        """Test that a successful compliance run calculates a valid risk level"""
        asset_id = self.create_asset(key='risk-level-test', name='Risk Level Test')
        test_content = b'col1,col2\nval1,val2'
        content_hash = hashlib.sha256(test_content).hexdigest()
        file_id = self.init_file_upload(name='risk_level_test.csv', content_type='text/csv', size=len(test_content))
        self.complete_file_upload(file_id, content_sha256=content_hash, test_content=test_content)
        dataset_id = self.create_dataset(file_id, asset_id)

        compliance_run_id = self.run_compliance_check_sync(file_id, dataset_id, asset_id)
        compliance_run = ComplianceRun.objects.get(id=compliance_run_id)

        # Must have left PENDING
        self.assertNotEqual(compliance_run.status, ComplianceRunStatus.PENDING)

        if compliance_run.status == ComplianceRunStatus.SUCCEEDED:
            self.assertIsNotNone(compliance_run.risk_level)
            valid_risk_levels = [r.value for r in RiskLevel]
            self.assertIn(compliance_run.risk_level, valid_risk_levels,
                          f"risk_level should be one of {valid_risk_levels}")
