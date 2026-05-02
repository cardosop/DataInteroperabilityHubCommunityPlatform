"""
Tenant Management Models

Defines Tenant model with status and KYC status enums, and TenantConfig model for per-tenant configuration.
"""

import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone

from hub.apps.integrations.encryption import (
    decrypt_json_field,
    encrypt_json_field,
    EncryptionError,
)


class ActiveTenantManager(models.Manager):
    """Default manager that excludes soft-deleted tenants."""

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


def default_empty_list():
    """Return a new empty list. Used as default for JSONField to avoid mutable default argument."""
    return []


def default_empty_dict():
    """Return a new empty dict. Used as default for JSONField to avoid mutable default argument."""
    return {}


class TenantStatus(models.TextChoices):
    """Tenant status enumeration"""

    ACTIVE = "ACTIVE", "Active"
    SUSPENDED = "SUSPENDED", "Suspended"
    DELETED = "DELETED", "Deleted"


class KYCStatus(models.TextChoices):
    """KYC status enumeration"""

    UNVERIFIED = "UNVERIFIED", "Unverified"
    PENDING_REVIEW = "PENDING_REVIEW", "Pending review"
    VERIFIED = "VERIFIED", "Verified"


class PlanTier(models.TextChoices):
    """Plan tier enumeration"""

    FREE = "FREE", "Free"
    PRO = "PRO", "Pro"
    ENTERPRISE = "ENTERPRISE", "Enterprise"


class PlanCategory(models.TextChoices):
    """Plan category enumeration — separates base platform from ML/AI packages."""

    BASE = "BASE", "Base Platform"
    ML_AI = "ML_AI", "ML / AI"


class TenantPlan(models.Model):
    """
    Tenant Plan model representing subscription plans with limits.

    Plans define resource limits (max_assets, max_api_calls_per_month, etc.)
    that are enforced per tenant. Each plan belongs to a category (BASE or ML_AI)
    so tenants can subscribe to platform and ML packages independently.
    """

    # Canonical set of recognised limit keys. Serializers and admin
    # validation use this to reject unknown keys in limits_json.
    KNOWN_LIMIT_KEYS = frozenset(
        {
            # ── Base platform limits ──
            "max_assets",
            "max_datasets",
            "max_contracts",
            "max_webhooks",
            "max_mesh_domains",
            "max_users",
            "max_marketplace_listings",
            "max_marketplace_connections",
            "max_virtual_datasets",
            "max_scheduled_ingestions",
            "max_scheduled_exports",
            "max_scheduled_runs_per_month",
            "max_export_runs_per_month",
            "max_api_calls_per_month",
            "max_compliance_runs_per_month",
            "max_dq_runs_per_month",
            # Phase 240.3.B.2 — daily cap on advanced-quality endpoints
            # (anomalies / trends / scorecards / root-cause-analysis).
            # Counter source: AuditEvent rows with action=DQ_QUALITY_QUERY
            # filtered to the current UTC day.  Plan default omits the
            # key entirely (treated as unlimited); operators flip it on
            # for tenants whose query volume needs throttling beyond
            # the per-endpoint per-minute throttle.
            "max_quality_queries_per_day",
            "max_access_requests_per_month",
            "max_storage_gb",
            # ── ML / AI limits (Phase 114A) ──
            "max_ml_models",
            "max_ml_training_jobs_per_month",
            "max_ml_inference_requests_per_month",
            "max_ml_deployed_models",
            "max_ml_storage_gb",
            # ── Transformation limits (Phase 115A) ──
            "max_transformation_pipelines",
            "max_transformation_runs_per_month",
            # ── ODPS limits (Phase 117A) ──
            "max_odps_documents",
        }
    )

    ML_LIMIT_KEYS = frozenset(
        {
            "max_ml_models",
            "max_ml_training_jobs_per_month",
            "max_ml_inference_requests_per_month",
            "max_ml_deployed_models",
            "max_ml_storage_gb",
        }
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=255, unique=True, help_text="Plan name (e.g., 'Free Plan', 'Pro Plan')"
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        help_text="URL-safe plan identifier (e.g., 'free', 'pro', 'enterprise')",
    )
    tier = models.CharField(
        max_length=20, choices=PlanTier.choices, help_text="Plan tier: FREE, PRO, or ENTERPRISE"
    )
    category = models.CharField(
        max_length=20,
        choices=PlanCategory.choices,
        default=PlanCategory.BASE,
        help_text="Plan category: BASE (platform) or ML_AI (ML/AI package)",
    )
    order = models.IntegerField(
        default=0,
        help_text="Tier ordering for upgrade/downgrade validation (FREE=0, PRO=1, ENTERPRISE=2)",
    )
    limits_json = models.JSONField(
        default=default_empty_dict,
        help_text="Plan limits as JSON (e.g., {'max_assets': 10, 'max_api_calls_per_month': 10000})",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this plan is currently active and available for subscription",
    )
    price_amount_cents = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Price amount in cents (e.g., 2999 = $29.99). 0 for free plans.",
    )
    price_currency = models.CharField(
        max_length=3,
        default="usd",
        help_text="ISO 4217 currency code (e.g., 'usd', 'eur', 'brl')",
    )
    billing_interval = models.CharField(
        max_length=10,
        choices=[("month", "Monthly"), ("year", "Yearly")],
        default="month",
        help_text="Billing interval for recurring subscriptions",
    )
    stripe_product_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        unique=True,
        help_text="Stripe Product ID (prod_...)",
    )
    stripe_price_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        unique=True,
        help_text="Stripe Price ID (price_...)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenant_plans"
        ordering = ["order", "name"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["tier"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["order"]),
            models.Index(fields=["category"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.slug})"

    def get_limit(self, limit_key: str, default=None):
        """
        Get a specific limit value from limits_json.

        Args:
            limit_key: Key in limits_json (e.g., 'max_assets')
            default: Default value if limit_key not found

        Returns:
            Limit value or default
        """
        return self.limits_json.get(limit_key, default)


class Tenant(models.Model):
    """
    Tenant model representing an organization or individual user.

    Each tenant is isolated from others with row-level security.
    """

    objects = ActiveTenantManager()
    all_objects = models.Manager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=255, unique=True, help_text="Tenant name (unique per environment)"
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        validators=[
            RegexValidator(
                regex=r"^[a-z0-9-]+$",
                message="Slug must contain only lowercase letters, numbers, and hyphens.",
            )
        ],
        help_text="URL-safe tenant identifier",
    )
    status = models.CharField(
        max_length=20,
        choices=TenantStatus.choices,
        default=TenantStatus.ACTIVE,
        help_text="Tenant status: ACTIVE, SUSPENDED, or DELETED",
    )
    kyc_status = models.CharField(
        max_length=20,
        choices=KYCStatus.choices,
        default=KYCStatus.UNVERIFIED,
        help_text="KYC verification status: UNVERIFIED, PENDING_REVIEW (submission with provider), or VERIFIED",
    )
    region = models.CharField(
        max_length=100, null=True, blank=True, help_text="Cloud region (e.g., us-east-1, eu-west-1)"
    )
    # Phase 228 X (REQ-LIN-X-004 / 228.X.4.1) — data residency.
    # When set, lineage cross-region access for THIS tenant is gated
    # by an explicit consent flag on the inbound request; missing
    # consent + cross-region request → HTTP 403 with code
    # ``DATA_RESIDENCY_BLOCK``. NULL = "no residency rule" (legacy).
    data_residency_region = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Phase 228 X (REQ-LIN-X-004) — ISO region the tenant's "
            "data MUST stay in (e.g. eu-west-1). Cross-region lineage "
            "access requires explicit consent header per F1 contract. "
            "NULL = legacy tenant with no residency rule."
        ),
    )
    # Phase 228 X (REQ-LIN-X-005 / 228.X.5.1) — PII redaction.
    # Patterns matched against ``LineageEdge.source_field`` /
    # ``target_field`` when serializing for cross-tenant viewers.
    # Stored as JSON list of regex patterns; never applied for
    # own-tenant viewers.
    lineage_redact_field_patterns = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Phase 228 X (REQ-LIN-X-005) — JSON list of regex patterns. "
            "When the field name on a LineageEdge matches any pattern "
            "AND the request's tenant_id != edge.tenant_id, the field "
            "name is replaced with '[REDACTED]' in the API response. "
            "Empty list = no redaction (legacy)."
        ),
    )
    # Phase 230.4 (REQ-SEM-MEMENTO-001) — per-tenant Memento (RFC 7089)
    # versioned-retrieval toggle.  When BOTH this flag AND the global
    # ``settings.SEMANTIC_MEMENTO_ENABLED`` are True, semantic-resource
    # updates produce ``SemanticResourceVersion`` snapshots and the
    # dereference endpoint honours the ``Accept-Datetime`` request
    # header.  Default False — feature is rolled-out per tenant.
    semantic_memento_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Phase 230.4 (REQ-SEM-MEMENTO-001) — when True, semantic "
            "resource updates produce versioned snapshots and the "
            "dereference endpoint honours Accept-Datetime. Gated by "
            "the global SEMANTIC_MEMENTO_ENABLED setting in addition."
        ),
    )
    # Phase 230.7 (REQ-SEM-INFERENCE-001) — per-tenant OWL/RDFS reasoning
    # toggle.  When True, SPARQL execution routes to the Fuseki
    # ``dataset/inferred`` endpoint that overlays an OWL Mini reasoner
    # (or RDFSExptRuleReasoner) on the SAME TDB2 store.  When False,
    # queries route to the plain ``dataset`` endpoint.  Toggle changes
    # take effect immediately for new queries — no Fuseki restart.
    # Read at SPARQL-run time per query, NOT cached on the client side.
    semantic_inference_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Phase 230.7 (REQ-SEM-INFERENCE-001) — when True, SPARQL "
            "queries see superclass / subproperty / inverseOf "
            "inferences materialised by the Fuseki reasoner. Expect "
            "2-5x query latency vs. the plain dataset endpoint."
        ),
    )
    # Phase 230.10 (REQ-SEM-ONTO-002) — per-tenant capability gate for
    # custom-ontology registration. Default False — feature is sold
    # as a paid add-on; flipping the flag unlocks the upload/manage
    # surface for the tenant's TENANT_ADMINs. The viewset returns 403
    # when this is False regardless of user role, so a forgotten flag
    # cannot grant access through role drift alone.
    semantic_custom_ontology_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Phase 230.10 (REQ-SEM-ONTO-002) — when True, "
            "TENANT_ADMINs may upload and manage custom ontologies "
            "via /api/v1/semantic/ontologies/. When False the "
            "endpoint returns 403 regardless of role."
        ),
    )
    # Phase 230.12 (REQ-SEM-LDN-001) — per-tenant capability gate for
    # the W3C Linked Data Notifications inbox + outbound delivery.
    # When False the inbox POST returns 401 (signature verification
    # always fails because there are no allow-listed keys to check
    # against) and the outbound signal handler short-circuits.
    # Default False — the feature is sold as a paid add-on AND
    # carries security review obligations (signed-HTTP-request
    # surface; threat-model + legal sign-off per D230.11).
    semantic_ldn_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Phase 230.12 (REQ-SEM-LDN-001) — when True, the tenant's "
            "LDN inbox accepts signed RDF notifications from "
            "allow-listed partners and the platform fires outbound "
            "notifications on resource updates. Default False."
        ),
    )
    # Phase 230.11 (REQ-SEM-SEARCH-EXPAND-001) — per-tenant gate for
    # ontology-aware query expansion in the search endpoint.  When
    # False the ``?semantic=true`` flag on /api/search/ is a no-op
    # (legacy behaviour preserved per the spec scenario "Toggle off
    # reproduces today's behaviour").  When True the endpoint walks
    # the tenant's active TenantOntology rows + the Meshant base
    # ontology for skos:altLabel / skos:related / owl:equivalentClass
    # / rdfs:subClassOf bridges (depth ≤ 2).
    semantic_search_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Phase 230.11 (REQ-SEM-SEARCH-EXPAND-001) — when True, "
            "search requests with ?semantic=true expand the user's "
            "query via tenant ontology relations. When False the "
            "?semantic flag is a no-op (existing search semantics "
            "preserved)."
        ),
    )
    # Phase 230.13 (REQ-SEM-GQL-002) — per-tenant gate for the
    # GraphQL-LD endpoint at POST /api/v1/semantic/graphql.  When
    # False the endpoint returns 403 regardless of role.  Default
    # False because the feature carries DoS surface area (depth /
    # complexity / timeout caps notwithstanding) and is sold as a
    # paid add-on per the proposal.
    semantic_graphql_ld_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Phase 230.13 (REQ-SEM-GQL-002) — when True, "
            "/api/v1/semantic/graphql accepts GraphQL-LD queries "
            "from this tenant's authenticated users (subject to "
            "the depth/complexity/timeout/throttle caps).  When "
            "False the endpoint returns 403."
        ),
    )
    # Phase 240.4.B.1 — per-tenant Data Quality kill-switch.
    #
    # ``data_quality_enabled`` is the BASE flag — when False, ALL DQ
    # API endpoints (DQRunViewSet, DQAlertingRuleViewSet,
    # DQQualityViewSet) return HTTP 403 + ``error_code:
    # DATA_QUALITY_DISABLED`` regardless of role.  Default True for
    # backward compatibility with existing tenants per D240.18 — the
    # flag is purely a kill-switch for incident response, not a
    # paywall surface.  Setting it to False instantly disables the
    # entire DQ feature for the tenant; a stuck DQ run continues to
    # execute (the worker has no flag to consult), but no NEW runs
    # can be created and no read endpoints are accessible.
    data_quality_enabled = models.BooleanField(
        default=True,
        help_text=(
            "Phase 240.4.B.1 — kill-switch for the entire DQ feature. "
            "Default True (existing tenants keep current behaviour); "
            "flip to False to instantly disable all DQ API access for "
            "incident response / cost containment."
        ),
    )
    # ``data_quality_advanced_enabled`` ADDITIONALLY gates the Phase
    # 240.3.B advanced quality endpoints (anomalies / trends /
    # scorecards / root-cause-analysis).  Default False per D240.18 —
    # advanced endpoints are compute-heavy (per-action throttle scopes
    # of 60/30/30/5 per minute) and need staged per-tenant rollout
    # after 14d production stability of 240.3.B.  The base flag must
    # ALSO be True for the advanced surface to work — i.e. the gate
    # is conjunctive ``data_quality_enabled AND
    # data_quality_advanced_enabled``.
    data_quality_advanced_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Phase 240.4.B.1 — gate for advanced DQ endpoints "
            "(anomalies / trends / scorecards / "
            "root-cause-analysis). Default False; flip to True "
            "per-tenant after the basic DQ feature is stable. "
            "Conjunctive with data_quality_enabled — the base "
            "flag must ALSO be True."
        ),
    )
    # Phase 240.1.C.2 — per-tenant DQ-run retention. The
    # ``purge_dq_runs`` management command soft-deletes ``DQRun``
    # rows older than this many days; soft-deleted rows are then
    # hard-deleted after a fixed 30-day grace window. Default 90 d
    # matches the platform-wide retention SLA; bounds [7, 365] per
    # D240.7 (lower = compliance shouldn't allow stripping audit
    # trails too aggressively; upper = storage/cost guard).
    dq_run_retention_days = models.PositiveIntegerField(
        default=90,
        validators=[
            MinValueValidator(7),
            MaxValueValidator(365),
        ],
        help_text=(
            "Phase 240.1.C — number of days to retain DQRun rows "
            "for this tenant before soft-delete (purge_dq_runs). "
            "Bounds: [7, 365] per D240.7."
        ),
    )
    # Phase 240.3.D.2 — per-tenant DQ input thresholds (D240.15).
    #
    # ``dq_input_max_bytes``: NULL → use platform default
    # (``DQ_INPUT_TOO_LARGE_BYTES`` env var on dq-service, currently
    # 500 MiB). When set, the api-service forwards as
    # ``X-Tenant-Threshold-Bytes`` to dq-service /run and that becomes
    # the 413 trip-wire for the upload size. Bounds [10 MiB, 5 GiB]:
    # lower keeps tenants from accidentally setting a value smaller
    # than a single sample CSV; upper keeps a misconfigured tenant
    # from saturating the dq-service worker memory.
    #
    # ``dq_sampling_threshold_rows``: NULL → platform default
    # (``DQ_SAMPLING_THRESHOLD_ROWS``, currently 1 M). When the
    # parsed DataFrame has > threshold rows, the dq-service samples
    # deterministically via ``hashlib.sha256(row_pk).hexdigest()``
    # modulo bucket selection (D240.15). Bounds [10 000, 100 000 000]:
    # lower keeps the deterministic sampler from being a no-op on
    # trivial inputs; upper keeps it from never firing on legitimately
    # large datasets.
    dq_input_max_bytes = models.BigIntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(10 * 1024 * 1024),         # 10 MiB
            MaxValueValidator(5 * 1024 * 1024 * 1024),   # 5 GiB
        ],
        help_text=(
            "Phase 240.3.D — per-tenant DQ input upload cap (bytes). "
            "NULL = use platform default (DQ_INPUT_TOO_LARGE_BYTES). "
            "Bounds: [10 MiB, 5 GiB] per D240.15."
        ),
    )
    dq_sampling_threshold_rows = models.BigIntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(10_000),
            MaxValueValidator(100_000_000),
        ],
        help_text=(
            "Phase 240.3.D — per-tenant DQ sampling threshold (rows). "
            "NULL = use platform default (DQ_SAMPLING_THRESHOLD_ROWS). "
            "Bounds: [10 000, 100 000 000] per D240.15."
        ),
    )
    plan = models.ForeignKey(
        "tenants.TenantPlan",
        on_delete=models.SET_NULL,
        related_name="tenants",
        null=True,
        blank=True,
        help_text="Subscription plan for this tenant",
    )
    ml_plan = models.ForeignKey(
        "tenants.TenantPlan",
        on_delete=models.SET_NULL,
        related_name="ml_tenants",
        null=True,
        blank=True,
        help_text="ML/AI package plan for this tenant",
    )
    kyc_verified_at = models.DateTimeField(
        null=True, blank=True, help_text="Timestamp when KYC was last verified"
    )
    kyc_expires_at = models.DateTimeField(
        null=True, blank=True, help_text="Timestamp when KYC verification expires"
    )
    deleted_at = models.DateTimeField(
        null=True, blank=True, help_text="Timestamp when tenant was marked for deletion"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenants"
        ordering = ["name"]
        default_manager_name = "all_objects"
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["status"]),
            models.Index(fields=["kyc_status"]),
            models.Index(fields=["region"]),
            models.Index(fields=["plan"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.slug})"

    def is_active(self) -> bool:
        """Check if tenant is active"""
        return self.status == TenantStatus.ACTIVE

    def is_suspended(self) -> bool:
        """Check if tenant is suspended"""
        return self.status == TenantStatus.SUSPENDED

    def is_deleted(self) -> bool:
        """Check if tenant is deleted"""
        return self.status == TenantStatus.DELETED

    def can_publish_to_marketplace(self) -> bool:
        """Check if tenant can publish to marketplace (requires valid KYC)"""
        if self.kyc_status != KYCStatus.VERIFIED or not self.is_active():
            return False
        if self.kyc_expires_at and self.kyc_expires_at < timezone.now():
            return False
        return True

    def suspend(self):
        """Suspend the tenant (read-only mode)"""
        if self.status == TenantStatus.DELETED:
            raise ValueError("Cannot suspend a deleted tenant")
        self.status = TenantStatus.SUSPENDED
        self.save(update_fields=["status", "updated_at"])

    def reactivate(self):
        """Reactivate a suspended tenant"""
        if self.status != TenantStatus.SUSPENDED:
            raise ValueError("Can only reactivate suspended tenants")
        self.status = TenantStatus.ACTIVE
        self.save(update_fields=["status", "updated_at"])

    def soft_delete(self):
        """Mark tenant for deletion (soft delete)"""
        self.status = TenantStatus.DELETED
        self.deleted_at = timezone.now()
        self.save(update_fields=["status", "deleted_at", "updated_at"])

    def restore(self):
        """Restore a soft-deleted tenant."""
        self.status = TenantStatus.ACTIVE
        self.deleted_at = None
        self.save(update_fields=["status", "deleted_at", "updated_at"])


class TenantConfig(models.Model):
    """
    Tenant Configuration model storing per-tenant configuration settings.

    Includes DQ profiles, compliance regimes, data retention, rate limits,
    file size limits, and job concurrency limits.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name="config",
        help_text="Tenant this configuration belongs to",
    )

    # DQ Profile Configuration
    default_dq_profile = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Default DQ profile key (e.g., intake_basic_gx, intake_basic_soda)",
    )

    # Compliance Configuration
    allowed_compliance_regimes = models.JSONField(
        default=default_empty_list,
        blank=True,
        help_text="List of compliance regimes available to this tenant (e.g., ['GDPR', 'LGPD', 'CCPA'])",
    )
    default_compliance_regimes = models.JSONField(
        default=default_empty_list,
        blank=True,
        help_text="Default compliance regimes applied to intake flows (subset of allowed_compliance_regimes)",
    )

    # Data Retention
    data_retention_days = models.IntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(90, message="Data retention must be at least 90 days"),
            MaxValueValidator(3650, message="Data retention cannot exceed 3650 days (10 years)"),
        ],
        help_text="Data retention period in days (90-3650)",
    )

    # Rate Limits (JSON structure)
    # API Gateway uses key "api_gateway_requests_per_hour" (int, requests per hour).
    rate_limits = models.JSONField(
        default=default_empty_dict,
        null=True,
        blank=True,
        help_text="Per-endpoint category rate limits (JSON). API Gateway: api_gateway_requests_per_hour (int).",
    )

    # File Size Limits
    max_file_size_bytes = models.BigIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Maximum file size for uploads in bytes",
    )

    # Job Concurrency Limits
    max_job_concurrency = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Maximum concurrent running jobs for this tenant",
    )
    max_queued_jobs = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Maximum queued jobs for this tenant",
    )

    # SSO Configuration (JSON structure)
    sso_config = models.JSONField(
        default=default_empty_dict,
        null=True,
        blank=True,
        help_text="SSO configuration (SAML and OIDC settings)",
    )

    # ODPS $ref Resolver Configuration (JSON structure)
    # Overrides global ODPS refs configuration for this tenant
    # Structure:
    # {
    #   "url_allowlist": ["https://*.example.com", "https://schemas.trusted.com"],
    #   "url_denylist": ["http://*", "https://*.malicious.com"]
    # }
    odps_refs_config = models.JSONField(
        default=default_empty_dict,
        null=True,
        blank=True,
        help_text="ODPS $ref resolver configuration (URL allowlist/denylist overrides)",
    )

    # Trust Signals (Phase 11)
    # When True, tenant can use trust signals (badges, quality SLAs) in marketplace listings.
    trust_signals_enabled = models.BooleanField(
        default=True,
        null=True,
        blank=True,
        help_text="Enable trust signals (badges, quality SLAs) for marketplace listings",
    )

    # Versioning (Phase 12)
    # When True, tenant can use dataset versioning (semantic versions, version history).
    versioning_enabled = models.BooleanField(
        default=True,
        null=True,
        blank=True,
        help_text="Enable dataset versioning (semantic versions, version history) for this tenant",
    )

    # Workflows (Phase 14)
    # When True, tenant can create and run workflows (orchestration).
    workflows_enabled = models.BooleanField(
        default=True,
        null=True,
        blank=True,
        help_text="Enable workflow orchestration for this tenant",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenant_configs"
        ordering = ["tenant"]
        indexes = [
            models.Index(fields=["tenant"]),
        ]

    def __str__(self):
        return f"Config for {self.tenant.name}"

    def clean(self):
        """Validate model-level constraints"""
        super().clean()

        # Validate default_compliance_regimes is subset of allowed_compliance_regimes
        if self.default_compliance_regimes and self.allowed_compliance_regimes:
            default_set = set(self.default_compliance_regimes)
            allowed_set = set(self.allowed_compliance_regimes)
            if not default_set.issubset(allowed_set):
                raise ValidationError(
                    {
                        "default_compliance_regimes": "Default compliance regimes must be a subset of allowed compliance regimes."
                    }
                )

    def save(self, *args, **kwargs):
        """Override save to run clean validation and encrypt sso_config."""
        self.full_clean()

        # Encrypt sso_config if plaintext dict (not already encrypted)
        if (
            isinstance(self.sso_config, dict)
            and self.sso_config
            and not self.sso_config.get("_encrypted")
        ):
            try:
                encrypted = encrypt_json_field(self.sso_config)
                self.sso_config = {"_encrypted": encrypted}
            except EncryptionError as e:
                raise ValidationError(
                    {"sso_config": f"Failed to encrypt: {e}"}
                ) from e

        super().save(*args, **kwargs)

    def get_sso_config(self) -> dict:
        """
        Get decrypted SSO configuration.

        Returns:
            Decrypted SSO config dictionary.
            Legacy plaintext dicts (pre-migration) returned as-is.
        """
        if not self.sso_config:
            return {}
        if isinstance(self.sso_config, dict):
            if "_encrypted" in self.sso_config:
                return decrypt_json_field(
                    self.sso_config["_encrypted"]
                )
            return self.sso_config
        return {}


class TenantUsageSummary(models.Model):
    """
    Tenant Usage Summary model for aggregating per-tenant usage metrics.

    Stores aggregated usage data for billing and admin purposes.
    Can be recalculated periodically or on-demand.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="usage_summaries",
        help_text="Tenant this usage summary belongs to",
    )
    period_start = models.DateTimeField(
        help_text="Start of the usage period (typically start of month)"
    )
    period_end = models.DateTimeField(help_text="End of the usage period (typically end of month)")

    # Usage metrics
    api_calls_count = models.BigIntegerField(default=0, help_text="Total API calls in period")
    asset_count = models.IntegerField(default=0, help_text="Total assets (current count)")
    dataset_count = models.IntegerField(default=0, help_text="Total datasets (current count)")
    scheduled_ingestion_runs_count = models.IntegerField(
        default=0, help_text="Total scheduled ingestion runs in period"
    )
    scheduled_export_runs_count = models.IntegerField(
        default=0, help_text="Total scheduled export runs in period"
    )
    storage_bytes = models.BigIntegerField(default=0, help_text="Total storage used in bytes")

    # Cost metrics (optional, for billing)
    ingestion_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total cost for scheduled ingestion runs in period",
    )

    # Metadata
    calculated_at = models.DateTimeField(
        auto_now=True, help_text="When this summary was last calculated"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenant_usage_summaries"
        ordering = ["-period_start"]
        indexes = [
            models.Index(fields=["tenant", "period_start"]),
            models.Index(fields=["tenant", "period_end"]),
            models.Index(fields=["period_start", "period_end"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "period_start", "period_end"],
                name="unique_tenant_period_usage_summary",
            )
        ]

    def __str__(self):
        return f"Usage summary for {self.tenant.name} ({self.period_start} to {self.period_end})"

    def get_storage_gb(self) -> float:
        """Get storage in GB"""
        return self.storage_bytes / (1024**3)
