"""
W1.15 (R2-S9) — every virtual-dataset SPARQL path routes through the
canonical validator.

The pre-fix state: the virtualization app carried THREE ad-hoc SPARQL
validators — ``VirtualizationBusinessRules._validate_sparql_syntax``,
``QueryServiceMixin._validate_query_syntax`` (dataset create/update),
and ``QueryServiceMixin._parse_and_validate_query`` (the execute path)
— none of which evaluated SERVICE against the tenant federation
allowlist (REQ-SEM-FED-001), none of which rejected GRAPH named-graph
reads, and none of which shared the canonical semantics. The workflow's
``_execute_sparql_query`` validated NOTHING before dispatch.

The fix routes all three (plus the workflow execution leg) through the
``commercial_hooks.validate_virtual_dataset_sparql`` seam — the paid
semantic app registers the canonical ``validate_sparql_query`` (tenant-
allowlisted federation + SSRF re-validation); the core-only default
fails closed (SERVICE/GRAPH/update keywords rejected).

Pins (real rules/services/workflow — no mocks):

* SERVICE payloads are rejected on every path (SPARQL_FEDERATION_NOT_ALLOWED);
* GRAPH payloads are rejected on every path (SPARQL_GRAPH_NOT_ALLOWED);
* valid read-only SELECTs still pass on every path (control).
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.core.services.base import ValidationError
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus
from hub.apps.virtualization.business_rules import VirtualizationBusinessRules
from hub.apps.virtualization.models import QueryType
from hub.apps.virtualization.services.query_service import QueryServiceMixin

pytestmark = pytest.mark.django_db(transaction=True)

User = get_user_model()

SERVICE_QUERY = """
PREFIX ex: <http://example.com/>
SELECT * WHERE {
    SERVICE <http://evil.example.com/sparql> { ?s ?p ?o }
}
"""

GRAPH_QUERY = """
PREFIX ex: <http://example.com/>
SELECT * WHERE {
    GRAPH <http://example.com/named-graph> { ?s ?p ?o }
}
"""

VALID_SELECT = """
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
SELECT ?name WHERE { ?person foaf:name ?name }
"""


class VirtualDatasetSparqlValidationW115Test(TestCase):
    """The three-path SPARQL routing pins."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"SPARQL Validation {uid}",
            slug=f"sparql-val-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"sparql-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.service = VirtualizationServiceForTest(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    # ── Path 1: the business-rules validation surface ───────────────────

    def test_business_rules_reject_service(self):
        rules = VirtualizationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        with pytest.raises(ValidationError):
            rules.validate_query_syntax(
                query=SERVICE_QUERY, query_type=QueryType.SPARQL, raise_on_error=True
            )

    def test_business_rules_reject_graph(self):
        rules = VirtualizationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        with pytest.raises(ValidationError):
            rules.validate_query_syntax(
                query=GRAPH_QUERY, query_type=QueryType.SPARQL, raise_on_error=True
            )

    def test_business_rules_accept_valid_select(self):
        rules = VirtualizationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        result = rules.validate_query_syntax(
            query=VALID_SELECT, query_type=QueryType.SPARQL, raise_on_error=False
        )
        self.assertFalse(result.errors)

    # ── Path 2: dataset create/update validation ────────────────────────

    def test_query_syntax_validation_rejects_service(self):
        with pytest.raises(ValidationError):
            self.service._validate_query_syntax(SERVICE_QUERY, QueryType.SPARQL)

    def test_query_syntax_validation_rejects_graph(self):
        with pytest.raises(ValidationError):
            self.service._validate_query_syntax(GRAPH_QUERY, QueryType.SPARQL)

    def test_query_syntax_validation_accepts_valid_select(self):
        self.service._validate_query_syntax(VALID_SELECT, QueryType.SPARQL)

    # ── Path 3: the execute path ────────────────────────────────────────

    def test_execute_path_validation_rejects_service(self):
        with pytest.raises(ValidationError):
            self.service._parse_and_validate_query(SERVICE_QUERY, QueryType.SPARQL)

    def test_execute_path_validation_rejects_graph(self):
        with pytest.raises(ValidationError):
            self.service._parse_and_validate_query(GRAPH_QUERY, QueryType.SPARQL)

    def test_execute_path_validation_accepts_valid_select(self):
        self.service._parse_and_validate_query(VALID_SELECT, QueryType.SPARQL)

    def test_workflow_sparql_execution_rejects_service_before_dispatch(self):
        from hub.apps.orchestration.workflows.virtualization import VirtualizationWorkflow

        with pytest.raises(ValidationError) as ei:
            VirtualizationWorkflow._execute_sparql_query(
                service=self.service, query=SERVICE_QUERY, timeout_seconds=30
            )
        # The canonical rejection code proves the query was rejected
        # BEFORE any semantic-client dispatch (a client failure would
        # carry SPARQL_EXECUTION_FAILED instead).
        self.assertEqual(ei.value.code, "SPARQL_FEDERATION_NOT_ALLOWED")

    def test_workflow_sparql_execution_rejects_graph_before_dispatch(self):
        from hub.apps.orchestration.workflows.virtualization import VirtualizationWorkflow

        with pytest.raises(ValidationError) as ei:
            VirtualizationWorkflow._execute_sparql_query(
                service=self.service, query=GRAPH_QUERY, timeout_seconds=30
            )
        self.assertEqual(ei.value.code, "SPARQL_GRAPH_NOT_ALLOWED")


class VirtualizationServiceForTest(QueryServiceMixin):
    """The real service shape without the publisher init weight — the
    QueryServiceMixin methods under test use only ``tenant_id``."""

    def __init__(self, tenant_id=None, user_id=None):
        self.tenant_id = tenant_id
        self.user_id = user_id
