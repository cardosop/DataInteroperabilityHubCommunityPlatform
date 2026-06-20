"""
Test Factories using Factory Boy

Real factories (not mocks) for creating test data using factory-boy.
These factories create actual model instances with realistic test data using Faker.
"""

import uuid
from datetime import timedelta

import factory
from django.contrib.auth import get_user_model
from django.utils import timezone
from factory import fuzzy
from factory.django import DjangoModelFactory
from faker import Faker

from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.notifications.models import EmailDelivery, EmailDeliveryStatus, EmailType
from hub.apps.tenants.models import KYCStatus, Tenant, TenantConfig, TenantStatus

fake = Faker()
User = get_user_model()


class TenantFactory(DjangoModelFactory):
    """Factory for creating Tenant instances using factory-boy"""

    class Meta:
        model = Tenant
        django_get_or_create = ("slug",)

    name = factory.LazyAttribute(lambda obj: f"Test Tenant {fake.company()}")
    slug = factory.LazyAttribute(lambda obj: obj.name.lower().replace(" ", "-")[:50])
    status = TenantStatus.ACTIVE
    kyc_status = KYCStatus.UNVERIFIED
    region = factory.LazyAttribute(lambda obj: fake.country_code())


class TenantConfigFactory(DjangoModelFactory):
    """Factory for creating TenantConfig instances using factory-boy"""

    class Meta:
        model = TenantConfig
        django_get_or_create = ("tenant",)

    tenant = factory.SubFactory(TenantFactory)
    default_dq_profile = "intake_basic_gx"
    allowed_compliance_regimes = factory.LazyFunction(lambda: ["GDPR", "LGPD", "CCPA"])
    default_compliance_regimes = factory.LazyFunction(lambda: ["GDPR"])
    data_retention_days = fuzzy.FuzzyInteger(90, 3650)
    rate_limits = factory.LazyFunction(
        lambda: {
            "read": {"requests_per_minute": 100, "requests_per_hour": 1000},
            "write": {"requests_per_minute": 50, "requests_per_hour": 500},
            "admin": {"requests_per_minute": 20, "requests_per_hour": 200},
        }
    )
    max_file_size_bytes = 10737418240  # 10 GB
    max_job_concurrency = fuzzy.FuzzyInteger(1, 10)
    max_queued_jobs = fuzzy.FuzzyInteger(10, 100)


class UserFactory(DjangoModelFactory):
    """Factory for creating User instances using factory-boy"""

    class Meta:
        model = User
        django_get_or_create = ("email",)

    email = factory.LazyAttribute(lambda obj: fake.email())
    display_name = factory.LazyAttribute(lambda obj: fake.name())
    password = factory.PostGenerationMethodCall("set_password", "testpass123")
    tenant = factory.SubFactory(TenantFactory)
    is_active = True


class EmailDeliveryFactory(DjangoModelFactory):
    """Factory for creating EmailDelivery instances using factory-boy"""

    class Meta:
        model = EmailDelivery

    email_type = EmailType.USER_INVITATION
    to_email = factory.LazyAttribute(lambda obj: fake.email())
    subject = factory.LazyAttribute(lambda obj: f"Test {obj.email_type.label} Email")
    status = EmailDeliveryStatus.PENDING
    retry_count = 0
    max_retries = 3
    metadata_json = factory.LazyFunction(dict)


class JobFactory(DjangoModelFactory):
    """Factory for creating Job instances using factory-boy"""

    class Meta:
        model = Job

    tenant = factory.SubFactory(TenantFactory)
    type = JobType.DQ_RUN
    status = JobStatus.PENDING
    resource_type = "CONTRACT"
    resource_id = factory.LazyFunction(lambda: uuid.uuid4())
    created_by = factory.SubFactory(UserFactory)
    result_json = factory.LazyFunction(dict)
    details_json = factory.LazyFunction(dict)
    timeout_seconds = 3600


# New model factories - these will work when the models are created
# Following the task requirements for new models


class ScheduledIngestionFactory(DjangoModelFactory):
    """Factory for creating ScheduledIngestion instances"""

    class Meta:
        model = None  # Will be set when model exists
        abstract = True

    # Placeholder fields - will be updated when model exists
    name = factory.LazyAttribute(lambda obj: fake.sentence(nb_words=3))
    schedule = factory.LazyAttribute(lambda obj: "0 0 * * *")  # Daily at midnight
    enabled = True
    tenant = factory.SubFactory(TenantFactory)


class ScheduledIngestionRunFactory(DjangoModelFactory):
    """Factory for creating ScheduledIngestionRun instances"""

    class Meta:
        model = None  # Will be set when model exists
        abstract = True

    scheduled_ingestion = factory.SubFactory(ScheduledIngestionFactory)
    status = factory.LazyAttribute(lambda obj: "PENDING")
    started_at = factory.LazyAttribute(lambda obj: timezone.now())
    completed_at = None


class SchemaVersionFactory(DjangoModelFactory):
    """Factory for creating SchemaVersion instances"""

    class Meta:
        model = None  # Will be set when model exists
        abstract = True

    version = factory.LazyAttribute(lambda obj: fake.semver())
    schema_json = factory.LazyFunction(
        lambda: {
            "fields": [
                {"name": "id", "type": "string"},
                {"name": "name", "type": "string"},
                {"name": "created_at", "type": "timestamp"},
            ]
        }
    )
    is_current = True


class DataClassificationFactory(DjangoModelFactory):
    """Factory for creating DataClassification instances"""

    class Meta:
        model = None  # Will be set when model exists
        abstract = True

    classification_level = factory.LazyAttribute(lambda obj: "PUBLIC")
    sensitivity_tags = factory.LazyFunction(lambda: ["PII", "FINANCIAL"])
    compliance_regimes = factory.LazyFunction(lambda: ["GDPR"])


class RetentionPolicyFactory(DjangoModelFactory):
    """Factory for creating RetentionPolicy instances"""

    class Meta:
        model = None  # Will be set when model exists
        abstract = True

    retention_days = fuzzy.FuzzyInteger(30, 2555)
    auto_delete = True
    tenant = factory.SubFactory(TenantFactory)


class AccessRequestFactory(DjangoModelFactory):
    """Factory for creating AccessRequest instances"""

    class Meta:
        model = None  # Will be set when model exists
        abstract = True

    requester = factory.SubFactory(UserFactory)
    tenant = factory.SubFactory(TenantFactory)
    status = factory.LazyAttribute(lambda obj: "PENDING")
    requested_at = factory.LazyAttribute(lambda obj: timezone.now())


class DatasetSnapshotFactory(DjangoModelFactory):
    """Factory for creating DatasetSnapshot instances"""

    class Meta:
        model = None  # Will be set when model exists
        abstract = True

    snapshot_id = factory.LazyFunction(lambda: uuid.uuid4())
    created_at = factory.LazyAttribute(lambda obj: timezone.now())
    metadata_json = factory.LazyFunction(dict)


class SearchIndexFactory(DjangoModelFactory):
    """Factory for creating SearchIndex instances"""

    class Meta:
        model = None  # Will be set when model exists
        abstract = True

    index_name = factory.LazyAttribute(lambda obj: f"idx_{fake.word()}")
    index_type = factory.LazyAttribute(lambda obj: "FULLTEXT")
    enabled = True


class SearchAnalyticsFactory(DjangoModelFactory):
    """Factory for creating SearchAnalytics instances"""

    class Meta:
        model = None  # Will be set when model exists
        abstract = True

    query = factory.LazyAttribute(lambda obj: fake.sentence())
    result_count = fuzzy.FuzzyInteger(0, 1000)
    executed_at = factory.LazyAttribute(lambda obj: timezone.now())


class WebhookFactory(DjangoModelFactory):
    """Factory for creating Webhook instances"""

    class Meta:
        model = None  # Will be set when model exists
        abstract = True

    url = factory.LazyAttribute(lambda obj: fake.url())
    event_type = factory.LazyAttribute(lambda obj: "data.ingested")
    enabled = True
    tenant = factory.SubFactory(TenantFactory)


class WebhookDeliveryFactory(DjangoModelFactory):
    """Factory for creating WebhookDelivery instances"""

    class Meta:
        model = None  # Will be set when model exists
        abstract = True

    webhook = factory.SubFactory(WebhookFactory)
    status = factory.LazyAttribute(lambda obj: "PENDING")
    attempted_at = factory.LazyAttribute(lambda obj: timezone.now())
    response_code = None


class DataObservabilityMetricFactory(DjangoModelFactory):
    """Factory for creating DataObservabilityMetric instances"""

    class Meta:
        model = None  # Will be set when model exists
        abstract = True

    metric_name = factory.LazyAttribute(lambda obj: f"metric_{fake.word()}")
    metric_value = fuzzy.FuzzyFloat(0.0, 100.0)
    recorded_at = factory.LazyAttribute(lambda obj: timezone.now())
    tenant = factory.SubFactory(TenantFactory)


class DataIncidentFactory(DjangoModelFactory):
    """Factory for creating DataIncident instances"""

    class Meta:
        model = None  # Will be set when model exists
        abstract = True

    incident_type = factory.LazyAttribute(lambda obj: "QUALITY_ISSUE")
    severity = factory.LazyAttribute(lambda obj: "MEDIUM")
    status = factory.LazyAttribute(lambda obj: "OPEN")
    detected_at = factory.LazyAttribute(lambda obj: timezone.now())
    tenant = factory.SubFactory(TenantFactory)


class AccessPolicyFactory(DjangoModelFactory):
    """Factory for creating AccessPolicy instances"""

    class Meta:
        model = None  # Will be set when model exists
        abstract = True

    policy_name = factory.LazyAttribute(lambda obj: f"policy_{fake.word()}")
    enabled = True
    tenant = factory.SubFactory(TenantFactory)


class FieldAccessPolicyFactory(DjangoModelFactory):
    """Factory for creating FieldAccessPolicy instances"""

    class Meta:
        model = None  # Will be set when model exists
        abstract = True

    field_name = factory.LazyAttribute(lambda obj: fake.word())
    access_level = factory.LazyAttribute(lambda obj: "READ")
    policy = factory.SubFactory(AccessPolicyFactory)


class AccessLogFactory(DjangoModelFactory):
    """Factory for creating AccessLog instances"""

    class Meta:
        model = None  # Will be set when model exists
        abstract = True

    user = factory.SubFactory(UserFactory)
    action = factory.LazyAttribute(lambda obj: "READ")
    accessed_at = factory.LazyAttribute(lambda obj: timezone.now())
    ip_address = factory.LazyAttribute(lambda obj: fake.ipv4())


class AccessCertificationFactory(DjangoModelFactory):
    """Factory for creating AccessCertification instances"""

    class Meta:
        model = None  # Will be set when model exists
        abstract = True

    user = factory.SubFactory(UserFactory)
    certified_at = factory.LazyAttribute(lambda obj: timezone.now())
    expires_at = factory.LazyAttribute(lambda obj: timezone.now() + timedelta(days=365))
    status = factory.LazyAttribute(lambda obj: "ACTIVE")


class DQAnomalyFactory(DjangoModelFactory):
    """Factory for creating DQAnomaly instances"""

    class Meta:
        model = None  # Will be set when model exists
        abstract = True

    anomaly_type = factory.LazyAttribute(lambda obj: "VALUE_DEVIATION")
    severity = factory.LazyAttribute(lambda obj: "MEDIUM")
    detected_at = factory.LazyAttribute(lambda obj: timezone.now())
    tenant = factory.SubFactory(TenantFactory)


class DQTrendFactory(DjangoModelFactory):
    """Factory for creating DQTrend instances"""

    class Meta:
        model = None  # Will be set when model exists
        abstract = True

    metric_name = factory.LazyAttribute(lambda obj: f"trend_{fake.word()}")
    trend_direction = factory.LazyAttribute(lambda obj: "INCREASING")
    recorded_at = factory.LazyAttribute(lambda obj: timezone.now())
    tenant = factory.SubFactory(TenantFactory)


class DQAlertingRuleFactory(DjangoModelFactory):
    """Factory for creating DQAlertingRule instances"""

    class Meta:
        model = None  # Will be set when model exists
        abstract = True

    rule_name = factory.LazyAttribute(lambda obj: f"rule_{fake.word()}")
    enabled = True
    threshold = fuzzy.FuzzyFloat(0.0, 100.0)
    tenant = factory.SubFactory(TenantFactory)


class IngestionTemplateFactory(DjangoModelFactory):
    """Factory for creating IngestionTemplate instances"""

    class Meta:
        model = None  # Will be set when model exists
        abstract = True

    template_name = factory.LazyAttribute(lambda obj: f"template_{fake.word()}")
    template_config = factory.LazyFunction(
        lambda: {"source_type": "S3", "format": "CSV", "schema_inference": True}
    )
    tenant = factory.SubFactory(TenantFactory)


# Enhanced model factories - for models with additional fields
# These factories extend base factories with new fields


class DatasetFactoryEnhanced(DjangoModelFactory):
    """Enhanced Dataset factory with version history fields"""

    class Meta:
        model = None  # Will be set when model exists
        abstract = True

    tenant = factory.SubFactory(TenantFactory)
    name = factory.LazyAttribute(lambda obj: f"dataset_{fake.word()}")
    version_history = factory.LazyFunction(
        lambda: [
            {
                "version": "1.0.0",
                "created_at": timezone.now().isoformat(),
                "changes": ["Initial version"],
            }
        ]
    )
    current_version = factory.LazyAttribute(lambda obj: "1.0.0")


class AssetFactoryEnhanced(DjangoModelFactory):
    """Enhanced Asset factory with health and popularity fields"""

    class Meta:
        model = None  # Will be set when model exists
        abstract = True

    tenant = factory.SubFactory(TenantFactory)
    name = factory.LazyAttribute(lambda obj: f"asset_{fake.word()}")
    health_score = fuzzy.FuzzyFloat(0.0, 100.0)
    health_status = factory.LazyAttribute(lambda obj: "HEALTHY")
    popularity_score = fuzzy.FuzzyFloat(0.0, 100.0)
    view_count = fuzzy.FuzzyInteger(0, 10000)
    last_accessed_at = factory.LazyAttribute(lambda obj: timezone.now())


class ContractFactoryEnhanced(DjangoModelFactory):
    """Enhanced Contract factory with search vector field"""

    class Meta:
        model = None  # Will be set when model exists
        abstract = True

    tenant = factory.SubFactory(TenantFactory)
    name = factory.LazyAttribute(lambda obj: f"contract_{fake.word()}")
    search_vector = factory.LazyFunction(lambda: fake.text(max_nb_chars=500))
    # Note: In PostgreSQL, search_vector would be a tsvector type
    # This factory provides text that can be converted to tsvector


class ScheduledIngestionFactoryEnhanced(DjangoModelFactory):
    """Enhanced ScheduledIngestion factory with incremental ingestion fields"""

    class Meta:
        model = None  # Will be set when model exists
        abstract = True

    tenant = factory.SubFactory(TenantFactory)
    name = factory.LazyAttribute(lambda obj: f"ingestion_{fake.word()}")
    schedule = factory.LazyAttribute(lambda obj: "0 0 * * *")  # Daily at midnight
    enabled = True
    incremental_enabled = True
    incremental_strategy = factory.LazyAttribute(lambda obj: "TIMESTAMP")
    incremental_field = factory.LazyAttribute(lambda obj: "updated_at")
    last_incremental_value = factory.LazyAttribute(lambda obj: timezone.now().isoformat())
