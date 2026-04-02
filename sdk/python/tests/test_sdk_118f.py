"""
Phase 118F — Python SDK New Modules Tests

Tests all new modules are importable with correct class names
and method signatures. Tests error class hierarchy.
"""

import inspect
import pytest


class TestNewModulesImportable:
    """All 15 new modules should be importable."""

    def test_compliance_api(self):
        from datahub_interoperability.compliance import ComplianceAPI
        assert hasattr(ComplianceAPI, "create_run")
        assert hasattr(ComplianceAPI, "poll_async")

    def test_transformation_api(self):
        from datahub_interoperability.transformation import TransformationAPI
        assert hasattr(TransformationAPI, "list_pipelines")
        assert hasattr(TransformationAPI, "execute_pipeline")
        assert hasattr(TransformationAPI, "cancel_execution")

    def test_semantic_api(self):
        from datahub_interoperability.semantic import SemanticAPI
        assert hasattr(SemanticAPI, "sparql_query")
        assert hasattr(SemanticAPI, "shacl_validate")
        assert hasattr(SemanticAPI, "get_ontology")

    def test_datasets_api(self):
        from datahub_interoperability.datasets import DatasetsAPI
        assert hasattr(DatasetsAPI, "list_datasets")
        assert hasattr(DatasetsAPI, "create_dataset")

    def test_assets_api(self):
        from datahub_interoperability.assets import AssetsAPI
        assert hasattr(AssetsAPI, "list_assets")
        assert hasattr(AssetsAPI, "get_health_score")
        assert hasattr(AssetsAPI, "classify_asset")

    def test_files_api(self):
        from datahub_interoperability.files import FilesAPI
        assert hasattr(FilesAPI, "init_upload")
        assert hasattr(FilesAPI, "get_download_url")

    def test_dq_api(self):
        from datahub_interoperability.dq import DQAPI
        assert hasattr(DQAPI, "create_run")
        assert hasattr(DQAPI, "get_scorecard")
        assert hasattr(DQAPI, "get_trends")

    def test_workflows_api(self):
        from datahub_interoperability.workflows import WorkflowsAPI
        assert hasattr(WorkflowsAPI, "list_workflows")
        assert hasattr(WorkflowsAPI, "retry_workflow")

    def test_auth_api(self):
        from datahub_interoperability.auth import AuthAPI
        assert hasattr(AuthAPI, "login")
        assert hasattr(AuthAPI, "get_profile")

    def test_jobs_api(self):
        from datahub_interoperability.jobs import JobsAPI
        assert hasattr(JobsAPI, "list_jobs")
        assert hasattr(JobsAPI, "cancel_job")

    def test_audit_api(self):
        from datahub_interoperability.audit import AuditAPI
        assert hasattr(AuditAPI, "list_events")
        assert hasattr(AuditAPI, "export_events")

    def test_social_api(self):
        from datahub_interoperability.social import SocialAPI
        assert hasattr(SocialAPI, "create_rating")
        assert hasattr(SocialAPI, "list_communities")

    def test_ai_api(self):
        from datahub_interoperability.ai import AIAPI
        assert hasattr(AIAPI, "search")
        assert hasattr(AIAPI, "schema_matching")

    def test_users_api(self):
        from datahub_interoperability.users import UsersAPI
        assert hasattr(UsersAPI, "list_users")
        assert hasattr(UsersAPI, "create_invitation")

    def test_marketplace_listings_api(self):
        from datahub_interoperability.marketplace_listings import MarketplaceListingsAPI
        assert hasattr(MarketplaceListingsAPI, "list_listings")
        assert hasattr(MarketplaceListingsAPI, "approve_order")
        assert hasattr(MarketplaceListingsAPI, "check_access")


class TestExpandedModules:
    """118F.16-19: Expanded methods on existing modules."""

    def test_billing_expanded(self):
        from datahub_interoperability.billing import BillingAPI
        for m in [
            "list_plans", "get_plan", "change_plan",
            "get_ml_subscription", "change_ml_plan",
            "get_plan_limits", "get_usage",
            "process_refund", "trigger_reconciliation",
        ]:
            assert hasattr(BillingAPI, m), f"Missing {m}"

    def test_baas_expanded(self):
        from datahub_interoperability.baas import BaaSAPI
        for m in [
            "list_customers", "get_customer_usage",
            "list_billing_reports", "generate_billing_report",
            "finalize_billing_report", "export_billing_report_pdf",
            "send_billing_report", "rotate_api_key",
            "get_dashboard",
        ]:
            assert hasattr(BaaSAPI, m), f"Missing {m}"

    def test_ml_expanded(self):
        from datahub_interoperability.ml import ODHIntegrationAPI
        for m in [
            "deploy_model", "undeploy_model",
            "deploy_version", "rollback_deployment",
            "publish_to_marketplace",
            "get_ml_plan", "get_ml_plan_limits",
        ]:
            assert hasattr(ODHIntegrationAPI, m), f"Missing {m}"

    def test_governance_expanded(self):
        from datahub_interoperability.governance import GovernanceAPI
        for m in [
            "get_access_request_expiration",
            "set_access_request_expiration",
        ]:
            assert hasattr(GovernanceAPI, m), f"Missing {m}"


class TestNewErrorClasses:
    """118F.20: All 15 new error classes."""

    def test_billing_errors(self):
        from datahub_interoperability.errors import (
            BillingError,
            BillingValidationError,
            DowngradeLimitExceededError,
            DataHubError,
        )
        assert issubclass(BillingError, DataHubError)
        assert issubclass(BillingValidationError, BillingError)
        assert issubclass(DowngradeLimitExceededError, BillingError)

    def test_transformation_errors(self):
        from datahub_interoperability.errors import (
            TransformationError,
            TransformationValidationError,
            DataHubError,
        )
        assert issubclass(TransformationError, DataHubError)
        assert issubclass(TransformationValidationError, TransformationError)

    def test_compliance_errors(self):
        from datahub_interoperability.errors import (
            ComplianceError,
            ComplianceValidationError,
            DataHubError,
        )
        assert issubclass(ComplianceError, DataHubError)
        assert issubclass(ComplianceValidationError, ComplianceError)

    def test_semantic_errors(self):
        from datahub_interoperability.errors import (
            SemanticError, SPARQLError,
            SHACLValidationError, DataHubError,
        )
        assert issubclass(SemanticError, DataHubError)
        assert issubclass(SPARQLError, SemanticError)
        assert issubclass(SHACLValidationError, SemanticError)

    def test_workflow_dlq_errors(self):
        from datahub_interoperability.errors import (
            WorkflowError, DLQError, DataHubError,
        )
        assert issubclass(WorkflowError, DataHubError)
        assert issubclass(DLQError, DataHubError)

    def test_entitlement_error(self):
        from datahub_interoperability.errors import (
            EntitlementRequiredError, ForbiddenError,
        )
        assert issubclass(EntitlementRequiredError, ForbiddenError)
        err = EntitlementRequiredError()
        assert err.code == "ENTITLEMENT_REQUIRED"

    def test_circuit_breaker_error(self):
        from datahub_interoperability.errors import (
            CircuitBreakerOpenError, ServerError,
        )
        assert issubclass(CircuitBreakerOpenError, ServerError)
        err = CircuitBreakerOpenError()
        assert err.http_status == 503

    def test_model_deployment_error(self):
        from datahub_interoperability.errors import (
            ModelDeploymentError, DataHubError,
        )
        assert issubclass(ModelDeploymentError, DataHubError)


class TestClientMountsAllModules:
    """118F.21: Client mounts all new modules."""

    def test_all_modules_on_init(self):
        from datahub_interoperability.client import DataHubClient
        src = inspect.getsource(DataHubClient.__init__)
        for attr in [
            "self.ai", "self.assets", "self.audit",
            "self.auth", "self.compliance",
            "self.datasets", "self.dq", "self.files",
            "self.jobs", "self.marketplace_listings",
            "self.semantic", "self.social",
            "self.transformation", "self.users",
            "self.workflows",
        ]:
            assert attr in src, f"{attr} not mounted"


class TestInitExportsAll:
    """118F.22: __init__ exports all new classes."""

    def test_new_apis_exported(self):
        import datahub_interoperability as dh
        for name in [
            "AIAPI", "AssetsAPI", "AuditAPI", "AuthAPI",
            "DatasetsAPI", "DQAPI", "FilesAPI", "JobsAPI",
            "MarketplaceListingsAPI", "SemanticAPI",
            "SocialAPI", "TransformationAPI", "UsersAPI",
            "WorkflowsAPI",
        ]:
            assert hasattr(dh, name), f"{name} not exported"

    def test_new_errors_exported(self):
        import datahub_interoperability as dh
        for name in [
            "BillingError", "DowngradeLimitExceededError",
            "TransformationError", "ComplianceError",
            "SemanticError", "SPARQLError",
            "SHACLValidationError", "WorkflowError",
            "DLQError", "EntitlementRequiredError",
            "CircuitBreakerOpenError", "ModelDeploymentError",
        ]:
            assert hasattr(dh, name), f"{name} not exported"


class TestMethodsAreAsync:
    """All new API methods should be async."""

    def test_compliance_methods_async(self):
        from datahub_interoperability.compliance import ComplianceAPI
        for name in ["create_run", "list_runs", "get_run", "get_results", "poll_async"]:
            method = getattr(ComplianceAPI, name)
            assert inspect.iscoroutinefunction(method), f"{name} not async"

    def test_transformation_methods_async(self):
        from datahub_interoperability.transformation import TransformationAPI
        for name in ["list_pipelines", "create_pipeline", "execute_pipeline"]:
            method = getattr(TransformationAPI, name)
            assert inspect.iscoroutinefunction(method), f"{name} not async"

    def test_semantic_methods_async(self):
        from datahub_interoperability.semantic import SemanticAPI
        for name in ["sparql_query", "shacl_validate", "get_ontology"]:
            method = getattr(SemanticAPI, name)
            assert inspect.iscoroutinefunction(method), f"{name} not async"
