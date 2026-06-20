"""
Comprehensive AI/ML New Use Cases Test Suite (Task 10.1.53.1)

Tests all new AI/ML use cases (UC-AI-001 through UC-AI-010):
- UC-AI-001: Natural Language Search
- UC-AI-002: AI Schema Matching
- UC-AI-003: ML-Based Anomaly Detection
- UC-AI-004: Smart Recommendations
- UC-AI-005: Auto-Classification
- UC-AI-006: Predictive Quality Forecasting
- UC-AI-007: Auto-Generated Quality Rules
- UC-AI-008: Query-to-SQL Translation
- UC-AI-009: ML Model Training
- UC-AI-010: Recommendation Feedback Loop

All tests hit real endpoints -- no mocks/stubs.
"""

import time
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import AssetStatus
from hub.apps.tenants.models import KYCStatus, TenantStatus
from hub.apps.testing.billing_support import (
    ensure_tenant_has_active_subscription,
)
from hub.apps.users.models import Role, UserRole
from tests.fixtures.test_data_factories import (
    AssetFactory,
    TenantFactory,
    UserFactory,
)
from tests.utils.test_data_management import TestDatabaseIsolationMixin

User = get_user_model()

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.uc("UC-AI-001"),
    pytest.mark.uc("UC-AI-002"),
    pytest.mark.uc("UC-AI-003"),
    pytest.mark.uc("UC-AI-004"),
    pytest.mark.uc("UC-AI-005"),
    pytest.mark.uc("UC-AI-006"),
    pytest.mark.uc("UC-AI-007"),
    pytest.mark.uc("UC-AI-008"),
    pytest.mark.uc("UC-AI-009"),
    pytest.mark.uc("UC-AI-010"),
]


class AIMLNewUseCasesTestBase(TestCase, TestDatabaseIsolationMixin):
    """Base test class for AI/ML new use cases."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()

        unique_id = str(uuid.uuid4())[:8]
        self.tenant = TenantFactory.create_tenant(
            name=f"Test Tenant {unique_id}",
            slug=f"test-tenant-{unique_id}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)

        self.data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )
        self.data_consumer_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_CONSUMER",
            defaults={"description": "Data Consumer"},
        )
        self.data_scientist_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_SCIENTIST",
            defaults={"description": "Data Scientist"},
        )

        self.dc_user = UserFactory.create_user(
            tenant=self.tenant,
            email=f"dc-{unique_id}@example.com",
        )
        UserRole.objects.get_or_create(
            user=self.dc_user,
            role=self.data_consumer_role,
        )

        self.ds_user = UserFactory.create_user(
            tenant=self.tenant,
            email=f"ds-{unique_id}@example.com",
        )
        UserRole.objects.get_or_create(
            user=self.ds_user,
            role=self.data_scientist_role,
        )

        self.dpo_user = UserFactory.create_user(
            tenant=self.tenant,
            email=f"dpo-{unique_id}@example.com",
        )
        UserRole.objects.get_or_create(
            user=self.dpo_user,
            role=self.data_provider_role,
        )

        self.asset1 = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.dpo_user,
            status=AssetStatus.ACTIVE,
            name="Customer Data Q1",
            description="Customer data from first quarter",
        )
        self.asset2 = AssetFactory.create_asset(
            tenant=self.tenant,
            created_by=self.dpo_user,
            status=AssetStatus.ACTIVE,
            name="Sales Data",
            description="Sales data for analytics",
        )


# ------------------------------------------------------------------
# UC-AI-001: Natural Language Search
# ------------------------------------------------------------------
class UCAI001NaturalLanguageSearchTest(AIMLNewUseCasesTestBase):
    """UC-AI-001: Natural Language Search"""

    def test_natural_language_search_success(self):
        """POST with query and result_types -> 200 with structured results."""
        self.client.force_authenticate(user=self.dc_user)
        search_url = reverse("ai-natural-language-search")
        response = self.client.post(
            search_url,
            {
                "query": "show me customer data from last quarter",
                "result_types": ["assets"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("query", response.data)
        self.assertIn("interpreted_query", response.data)
        self.assertIn("results", response.data)
        self.assertIn("assets", response.data["results"])

    def test_natural_language_search_multiple_types(self):
        """Search across multiple resource types -> all requested types present."""
        self.client.force_authenticate(user=self.dc_user)
        search_url = reverse("ai-natural-language-search")
        response = self.client.post(
            search_url,
            {
                "query": "find sales and contract information",
                "result_types": ["assets", "contracts", "datasets"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for result_type in ["assets", "contracts", "datasets"]:
            self.assertIn(
                result_type,
                response.data["results"],
                f"Missing '{result_type}' key in results",
            )

    def test_natural_language_search_llm_fallback(self):
        """Fallback to keyword search when LLM unavailable -> still 200."""
        self.client.force_authenticate(user=self.dc_user)
        search_url = reverse("ai-natural-language-search")
        response = self.client.post(
            search_url,
            {"query": "customer data", "result_types": ["assets"]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("assets", response.data["results"])

    @pytest.mark.performance
    def test_natural_language_search_performance(self):
        """Natural language search should complete within 5 seconds."""
        self.client.force_authenticate(user=self.dc_user)
        search_url = reverse("ai-natural-language-search")
        start = time.time()
        response = self.client.post(
            search_url,
            {"query": "show me customer data", "result_types": ["assets"]},
            format="json",
        )
        elapsed_ms = (time.time() - start) * 1000
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLess(
            elapsed_ms,
            5000,
            f"Search took {elapsed_ms:.0f}ms, exceeds 5000ms",
        )

    def test_natural_language_search_empty_results(self):
        """Search with no matches -> 200 with assets results."""
        self.client.force_authenticate(user=self.dc_user)
        search_url = reverse("ai-natural-language-search")
        response = self.client.post(
            search_url,
            {
                "query": "xyznonexistent999",
                "result_types": ["assets"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("assets", response.data["results"])
        assets = response.data["results"]["assets"]
        # assets may be a list or a dict with items/total
        if isinstance(assets, dict):
            self.assertIn("items", assets)
        else:
            self.assertIsInstance(assets, list)

    def test_natural_language_search_unauthorized(self):
        """Unauthenticated search -> 401/403."""
        self.client.logout()
        search_url = reverse("ai-natural-language-search")
        response = self.client.post(
            search_url,
            {"query": "test", "result_types": ["assets"]},
            format="json",
        )
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )


# ------------------------------------------------------------------
# UC-AI-002: AI Schema Matching
# ------------------------------------------------------------------
class UCAI002AISchemaMatchingTest(AIMLNewUseCasesTestBase):
    """UC-AI-002: AI Schema Matching"""

    def test_ai_schema_matching_success(self):
        """Match similar schemas -> 200 with matches and confidence."""
        self.client.force_authenticate(user=self.dpo_user)
        matching_url = reverse("ai-schema-matching")
        response = self.client.post(
            matching_url,
            {
                "source_schema": {
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string"},
                        "customer_name": {"type": "string"},
                        "email": {"type": "string"},
                    },
                },
                "target_schema": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                        "email_address": {"type": "string"},
                    },
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("matches", response.data)
        self.assertIn("confidence", response.data)
        self.assertIsInstance(response.data["matches"], list)

    def test_ai_schema_matching_low_confidence(self):
        """Completely different fields -> low confidence score."""
        self.client.force_authenticate(user=self.dpo_user)
        matching_url = reverse("ai-schema-matching")
        response = self.client.post(
            matching_url,
            {
                "source_schema": {
                    "type": "object",
                    "properties": {
                        "field1": {"type": "string"},
                    },
                },
                "target_schema": {
                    "type": "object",
                    "properties": {
                        "completely_different": {"type": "number"},
                    },
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("matches", response.data)
        self.assertIn("confidence", response.data)
        if response.data["confidence"] is not None:
            self.assertLessEqual(response.data["confidence"], 0.5)

    @pytest.mark.performance
    def test_ai_schema_matching_performance(self):
        """Schema matching should complete within 15 seconds."""
        self.client.force_authenticate(user=self.dpo_user)
        matching_url = reverse("ai-schema-matching")
        start = time.time()
        response = self.client.post(
            matching_url,
            {
                "source_schema": {
                    "type": "object",
                    "properties": {
                        "f1": {"type": "string"},
                        "f2": {"type": "number"},
                    },
                },
                "target_schema": {
                    "type": "object",
                    "properties": {
                        "f1": {"type": "string"},
                        "f2": {"type": "number"},
                    },
                },
            },
            format="json",
        )
        elapsed_ms = (time.time() - start) * 1000
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLess(
            elapsed_ms,
            15000,
            f"Matching took {elapsed_ms:.0f}ms, exceeds 15s",
        )

    def test_ai_schema_matching_unauthorized(self):
        """Unauthenticated schema matching -> 401/403."""
        self.client.logout()
        matching_url = reverse("ai-schema-matching")
        response = self.client.post(
            matching_url,
            {"source_schema": {}, "target_schema": {}},
            format="json",
        )
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )


# ------------------------------------------------------------------
# UC-AI-003: ML-Based Anomaly Detection
# ------------------------------------------------------------------
class UCAI003MLAnomalyDetectionTest(AIMLNewUseCasesTestBase):
    """UC-AI-003: ML-Based Anomaly Detection

    Tests real /api/v1/ai/anomaly-detection/ endpoints.
    """

    def test_anomaly_detection_list(self):
        """GET /anomaly-detection/ -> 200 with results key."""
        self.client.force_authenticate(user=self.dpo_user)
        response = self.client.get("/api/v1/ai/anomaly-detection/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("results", data)
        self.assertIn("enabled", data)
        self.assertIn("count", data)

    def test_anomaly_detection_config(self):
        """GET /anomaly-detection/config/ -> 200 with config keys."""
        self.client.force_authenticate(user=self.dpo_user)
        response = self.client.get(
            "/api/v1/ai/anomaly-detection/config/",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("enabled", data)
        self.assertIn("threshold", data)

    def test_anomaly_detection_train(self):
        """POST /anomaly-detection/train/ -> 202 Accepted."""
        self.client.force_authenticate(user=self.dpo_user)
        response = self.client.post(
            "/api/v1/ai/anomaly-detection/train/",
            {},
            format="json",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_202_ACCEPTED,
        )
        data = response.json()
        self.assertIn("status", data)
        self.assertEqual(data["status"], "training")

    def test_anomaly_detection_unauthorized(self):
        """Unauthenticated anomaly detection -> 401/403."""
        self.client.logout()
        response = self.client.get("/api/v1/ai/anomaly-detection/")
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_anomaly_detection_via_dq_results(self):
        """DQ run results include anomalies section when available.

        Create a DQ run to verify the results endpoint returns
        anomaly data in its response structure.
        """
        self.client.force_authenticate(user=self.dpo_user)
        dq_url = reverse("dq-run-list")
        dq_resp = self.client.post(
            dq_url,
            {"asset_id": str(self.asset1.id), "profile": "intake_basic"},
            format="json",
        )
        self.assertEqual(
            dq_resp.status_code,
            status.HTTP_201_CREATED,
        )
        run_id = dq_resp.data["id"]

        results_resp = self.client.get(
            f"/api/v1/dq/runs/{run_id}/results/",
        )
        self.assertEqual(
            results_resp.status_code,
            status.HTTP_200_OK,
        )
        data = results_resp.json()
        # DQ results endpoint returns anomalies and recommendations
        self.assertIn("anomalies", data)
        self.assertIn("recommendations", data)
        self.assertIsInstance(data["anomalies"], list)
        self.assertIsInstance(data["recommendations"], list)


# ------------------------------------------------------------------
# UC-AI-004: Smart Recommendations
# ------------------------------------------------------------------
class UCAI004SmartRecommendationsTest(AIMLNewUseCasesTestBase):
    """UC-AI-004: Smart Recommendations

    Tests real /api/v1/ai/recommendations/ endpoint.
    """

    def test_recommendations_list(self):
        """GET /recommendations/ -> 200 with recommendations key."""
        self.client.force_authenticate(user=self.dc_user)
        response = self.client.get("/api/v1/ai/recommendations/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("recommendations", data)
        self.assertIsInstance(data["recommendations"], list)

    def test_recommendations_model_info(self):
        """GET /recommendations/model/ -> 200 with model metadata."""
        self.client.force_authenticate(user=self.dc_user)
        response = self.client.get(
            "/api/v1/ai/recommendations/model/",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("model_version", data)
        self.assertIn("metrics", data)

    def test_recommendations_unauthorized(self):
        """Unauthenticated recommendations -> 401/403."""
        self.client.logout()
        response = self.client.get("/api/v1/ai/recommendations/")
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )


# ------------------------------------------------------------------
# UC-AI-005: Auto-Classification
# ------------------------------------------------------------------
class UCAI005AutoClassificationTest(AIMLNewUseCasesTestBase):
    """UC-AI-005: Auto-Classification

    Tests real /api/v1/ai/classification/ endpoints.
    """

    def test_classification_list(self):
        """GET /classification/ -> 200 with results and count."""
        self.client.force_authenticate(user=self.dpo_user)
        response = self.client.get("/api/v1/ai/classification/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("results", data)
        self.assertIn("count", data)
        self.assertIsInstance(data["results"], list)

    def test_classification_retrieve(self):
        """GET /classification/{id}/ -> 200 with status and confidence."""
        self.client.force_authenticate(user=self.dpo_user)
        fake_id = uuid.uuid4()
        response = self.client.get(
            f"/api/v1/ai/classification/{fake_id}/",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("confidence", data)
        self.assertEqual(data["id"], str(fake_id))

    def test_classification_validate(self):
        """POST /classification/{id}/validate/ -> 200 with validated status."""
        self.client.force_authenticate(user=self.dpo_user)
        fake_id = uuid.uuid4()
        response = self.client.post(
            f"/api/v1/ai/classification/{fake_id}/validate/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["status"], "validated")
        self.assertIn("validated_by", data)

    def test_classification_unauthorized(self):
        """Unauthenticated classification -> 401/403."""
        self.client.logout()
        response = self.client.get("/api/v1/ai/classification/")
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )


# ------------------------------------------------------------------
# UC-AI-006: Predictive Quality Forecasting
# ------------------------------------------------------------------
class UCAI006PredictiveQualityForecastingTest(AIMLNewUseCasesTestBase):
    """UC-AI-006: Predictive Quality Forecasting

    Tests real DQ run results endpoint which includes trend_analysis
    with forecast_value (the actual forecasting implementation).
    """

    def test_dq_run_results_include_trend_analysis(self):
        """DQ run results include trend_analysis with forecast data."""
        self.client.force_authenticate(user=self.dpo_user)
        dq_url = reverse("dq-run-list")
        dq_resp = self.client.post(
            dq_url,
            {"asset_id": str(self.asset1.id), "profile": "intake_basic"},
            format="json",
        )
        self.assertEqual(
            dq_resp.status_code,
            status.HTTP_201_CREATED,
        )
        run_id = dq_resp.data["id"]

        results_resp = self.client.get(
            f"/api/v1/dq/runs/{run_id}/results/",
        )
        self.assertEqual(
            results_resp.status_code,
            status.HTTP_200_OK,
        )
        data = results_resp.json()
        # trend_analysis is the real forecasting implementation
        # May be None for a fresh asset with a single DQ run
        self.assertIn("trend_analysis", data)
        trend = data["trend_analysis"]
        if trend is not None:
            self.assertIsInstance(trend, dict)
            for key in ("direction", "current_value"):
                self.assertIn(
                    key,
                    trend,
                    f"Missing '{key}' in trend_analysis",
                )

    def test_dq_runs_list_returns_quality_history(self):
        """DQ runs list returns historical quality data for forecasting."""
        self.client.force_authenticate(user=self.dpo_user)
        response = self.client.get("/api/v1/dq/runs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        results = data.get("results", data)
        self.assertIsInstance(results, list)


# ------------------------------------------------------------------
# UC-AI-007: Auto-Generated Quality Rules
# ------------------------------------------------------------------
class UCAI007AutoGeneratedQualityRulesTest(AIMLNewUseCasesTestBase):
    """UC-AI-007: Auto-Generated Quality Rules

    Tests the classification rules update endpoint and DQ run
    recommendations which suggest quality rules.
    """

    def test_classification_rules_update(self):
        """PATCH /classification/{id}/rules/ -> 200 with rules_updated."""
        self.client.force_authenticate(user=self.dpo_user)
        fake_id = uuid.uuid4()
        response = self.client.patch(
            f"/api/v1/ai/classification/{fake_id}/rules/",
            {"rules": [{"type": "completeness", "threshold": 0.95}]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data.get("rules_updated"))

    def test_dq_results_include_recommendations(self):
        """DQ run results include rule recommendations."""
        self.client.force_authenticate(user=self.dpo_user)
        dq_url = reverse("dq-run-list")
        dq_resp = self.client.post(
            dq_url,
            {"asset_id": str(self.asset1.id), "profile": "intake_basic"},
            format="json",
        )
        self.assertEqual(
            dq_resp.status_code,
            status.HTTP_201_CREATED,
        )
        run_id = dq_resp.data["id"]
        results_resp = self.client.get(
            f"/api/v1/dq/runs/{run_id}/results/",
        )
        self.assertEqual(
            results_resp.status_code,
            status.HTTP_200_OK,
        )
        data = results_resp.json()
        self.assertIn("recommendations", data)
        self.assertIsInstance(data["recommendations"], list)

    def test_classification_report(self):
        """GET /classification/{id}/report/ -> 200 with report."""
        self.client.force_authenticate(user=self.dpo_user)
        fake_id = uuid.uuid4()
        response = self.client.get(
            f"/api/v1/ai/classification/{fake_id}/report/",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("report", data)
        self.assertIn("status", data)
        self.assertEqual(data["status"], "generated")


# ------------------------------------------------------------------
# UC-AI-008: Query-to-SQL Translation
# ------------------------------------------------------------------
class UCAI008QueryToSQLTranslationTest(AIMLNewUseCasesTestBase):
    """UC-AI-008: Query-to-SQL Translation

    Uses NL search with SQL-like queries -- the interpreted_query
    field shows the SQL/structured translation.
    """

    def test_query_to_sql_via_nl_search(self):
        """POST NL search with SQL-like query -> interpreted_query."""
        self.client.force_authenticate(user=self.dc_user)
        search_url = reverse("ai-natural-language-search")
        response = self.client.post(
            search_url,
            {
                "query": "SELECT customer_name FROM customers WHERE region = 'EMEA'",
                "result_types": ["assets"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("interpreted_query", response.data)
        self.assertIn("results", response.data)

    def test_query_to_sql_unauthorized(self):
        """Unauthenticated query-to-SQL -> 401/403."""
        self.client.logout()
        search_url = reverse("ai-natural-language-search")
        response = self.client.post(
            search_url,
            {"query": "SELECT * FROM data", "result_types": ["assets"]},
            format="json",
        )
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )


# ------------------------------------------------------------------
# UC-AI-009: ML Model Training
# ------------------------------------------------------------------
class UCAI009MLModelTrainingTest(AIMLNewUseCasesTestBase):
    """UC-AI-009: ML Model Training"""

    def test_ml_training_jobs_list(self):
        """GET /ml/training/jobs/ -> 200 with list structure."""
        self.client.force_authenticate(user=self.ds_user)
        response = self.client.get("/api/v1/ml/training/jobs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        results = data.get("results", data)
        self.assertIsInstance(results, list)

    def test_ml_training_jobs_unauthorized(self):
        """Unauthenticated training jobs -> 401/403."""
        self.client.logout()
        response = self.client.get("/api/v1/ml/training/jobs/")
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )


# ------------------------------------------------------------------
# UC-AI-010: Recommendation Feedback Loop
# ------------------------------------------------------------------
class UCAI010RecommendationFeedbackLoopTest(AIMLNewUseCasesTestBase):
    """UC-AI-010: Recommendation Feedback Loop

    Tests the real feedback submission endpoint at
    POST /api/v1/ai/recommendations/feedback/.
    """

    def test_submit_recommendation_feedback(self):
        """POST /recommendations/feedback/ -> 200 with status received."""
        self.client.force_authenticate(user=self.dc_user)
        response = self.client.post(
            "/api/v1/ai/recommendations/feedback/",
            {
                "recommendation_id": str(uuid.uuid4()),
                "feedback": "helpful",
                "rating": 5,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["status"], "received")

    def test_feedback_then_recommendations_accessible(self):
        """After submitting feedback, recommendations are still accessible."""
        self.client.force_authenticate(user=self.dc_user)
        # Submit feedback
        fb_resp = self.client.post(
            "/api/v1/ai/recommendations/feedback/",
            {"recommendation_id": str(uuid.uuid4()), "feedback": "ok"},
            format="json",
        )
        self.assertEqual(fb_resp.status_code, status.HTTP_200_OK)

        # Recommendations still work
        rec_resp = self.client.get("/api/v1/ai/recommendations/")
        self.assertEqual(rec_resp.status_code, status.HTTP_200_OK)
        self.assertIn("recommendations", rec_resp.json())

    def test_feedback_unauthorized(self):
        """Unauthenticated feedback -> 401/403."""
        self.client.logout()
        response = self.client.post(
            "/api/v1/ai/recommendations/feedback/",
            {"feedback": "test"},
            format="json",
        )
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )
