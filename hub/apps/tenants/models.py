"""
Tenant Management Models

Defines Tenant model with status and KYC status enums, and TenantConfig model for per-tenant configuration.
"""

import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone

from hub.apps.compliance.models import RiskLevel
from hub.apps.integrations.encryption import (
    decrypt_json_field,
    encrypt_json_field,
    EncryptionError,
)

# Phase 231.2 — thresholds exclude UNKNOWN (fail-closed sentinel on runs only).
_COMPLIANCE_RISK_THRESHOLD_CHOICES = tuple(
    (value, label) for value, label in RiskLevel.choices if value != RiskLevel.UNKNOWN.value
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


def _default_connect_enabled() -> bool:
    """Phase 271.1.2 — env-aware default for ``Tenant.connect_enabled``.

    Returns:
        True unconditionally for newly-created rows AFTER this
        phase ships — per the spec ``Connect Onboarding Capability
        Gate``: "default False on existing tenants (one-release
        notice window) and True on new tenants created after this
        phase ships".

    Django evaluates ``default=callable`` at INSERT time, so this
    fires for ANY ``Tenant.objects.create(...)`` from now on; the
    migration's ``add_field`` step uses a literal ``False`` to
    backfill existing rows so live prod tenants are NOT
    automatically opted into Connect — they go through the
    30-day notice + opt-out window per D-271.4 + the same
    rollout-discipline shape Phase 250.1.A.8 set for
    ``compliance_fail_closed_enabled``.

    The callable is deliberately env-INDEPENDENT (unlike the
    legal-basis one) — Connect is opt-in everywhere; staging/dev
    pick it up immediately because that's the safe default for
    a fresh tenant; production picks it up the moment the
    migration applies for any post-migration tenant.
    """
    return True


def _default_compliance_legal_basis_strict() -> bool:
    """Phase 270.C.4.1 — env-aware default for
    ``Tenant.compliance_legal_basis_strict``.

    Returns:
        True when ``settings.ENVIRONMENT == "production"`` (new prod
        tenants opt into strict mode automatically — D-270.9), False
        otherwise (staging/dev/test stay lenient for backward-compat
        with existing fixtures + e2e harnesses that don't always pass
        a valid ``legal_basis``).

    Read-at-row-create (Django evaluates ``default=callable`` at
    INSERT time) so a per-environment Helm rollout flips the default
    on the FIRST tenant created post-deploy, NOT retroactively on
    existing rows. Tenants created BEFORE this field landed receive
    ``False`` via the migration's ``add_field`` default; ops can
    flip individual tenants via the tenant-admin API.
    """
    environment = getattr(settings, "ENVIRONMENT", "") or ""
    return environment.lower() == "production"


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
            # Phase 270.A.1 — monthly per-tenant cap on marketplace orders.
            # Counts the consumer-side ``Order`` rows created in the
            # current calendar month (REJECTED + CANCELLED excluded per
            # the matching ``ResourceCounter``). Default plan values
            # are seeded in migration ``0061_phase_270_a_1_order_plan_limit``:
            # FREE=10, PRO=100, ENTERPRISE=null (unlimited).
            "max_marketplace_orders_per_month",
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
    compliance_pro_pack = models.BooleanField(
        default=False,
        help_text=(
            "D232.16 — when True, commercial terms allow Compliance Pro packaging; "
            "individual subsystem flags on Tenant still default off."
        ),
    )
    # Phase 270.C.5.1 — regulations included by default at this
    # plan tier. New tenants subscribing to this plan get this set
    # copied into ``Tenant.licensed_regulation_keys`` at provisioning
    # time; existing tenants are not retroactively re-seeded (the
    # tenant's own set is the source-of-truth at scan-time, not the
    # plan's). Empty list ⇒ no plan-level entitlement; tenants must
    # be explicitly granted regulations via ``licensed_regulation_keys``.
    # Uppercase regulation tokens (e.g. ``["GDPR", "UK_GDPR"]``); see
    # ``services/compliance-service/regulations/__init__.py`` for the
    # canonical catalogue.
    includes_regulations = ArrayField(
        base_field=models.CharField(max_length=64),
        default=list,
        blank=True,
        help_text=(
            "Phase 270.C.5 — uppercase regulation tokens included "
            "with this plan tier (e.g. ``['GDPR', 'PIPL_CN']``). "
            "New tenants subscribing to this plan get this list "
            "copied into ``Tenant.licensed_regulation_keys`` at "
            "provisioning time. Empty list ⇒ no plan-level "
            "entitlement."
        ),
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
    # Phase 260.1.A.2 — grace between API file delete and hard purge.
    file_soft_delete_grace_days = models.PositiveIntegerField(
        default=30,
        validators=[
            MinValueValidator(7),
            MaxValueValidator(365),
        ],
        help_text=(
            "Phase 260.1.A — days after ``File`` enters DELETING before "
            "purge_deleted_files may delete the object from storage and "
            "remove the DB row. Bounds [7, 365]."
        ),
    )
    # Phase 270.B.2.3 — SLA for AccessRequest PENDING state. The
    # ``revoke_expired_access`` daily sweep transitions any
    # AccessRequest that has been ``status=PENDING`` longer than
    # this many days to ``status=EXPIRED`` and emits a
    # ``ACCESS_REQUEST_EXPIRED_BY_SLA`` audit row. Default 14 d
    # gives consumers two work-weeks for the provider's data-owner
    # to decide; bounds [1, 365] — lower bound 1 day so a tenant
    # operating in a regulated regime can opt into same-day SLA
    # enforcement; upper bound 365 days prevents an effectively-
    # never SLA (an indefinitely-pending request is governance debt
    # the provider's tooling should be flagging anyway).
    access_request_pending_sla_days = models.PositiveIntegerField(
        default=14,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(365),
        ],
        help_text=(
            "Phase 270.B.2 — number of days an AccessRequest can "
            "stay in PENDING before the daily ``revoke_expired_access`` "
            "sweep transitions it to EXPIRED. Default 14 d. Bounds [1, 365]."
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
    # ------------------------------------------------------------------
    # Phase 250.1.A.8 — fail-closed-at-intake flags (preprod01)
    # ------------------------------------------------------------------
    # ``compliance_fail_closed_enabled`` governs whether a compliance
    # FAIL/UNKNOWN at intake refuses to persist the Asset row (the
    # 250.1.A workflow re-sequence). Default True for NEW tenants so
    # the platform ships with the safer behaviour; the migration
    # (0034_tenant_fail_closed_flag) backfills FALSE on EXISTING
    # tenants so their workload runs unchanged until the tenant is
    # opted in by ops. Read at workflow-time per request — flipping
    # the flag mid-execution does NOT affect an in-flight workflow,
    # only subsequent intakes.
    compliance_fail_closed_enabled = models.BooleanField(
        default=True,
        help_text=(
            "Phase 250.1.A.8 — when True, a compliance FAIL/UNKNOWN at "
            "intake refuses to persist the Asset row (fail-closed). "
            "Default True for NEW tenants (production-safe); existing "
            "tenants are backfilled to False by migration 0034 to "
            "preserve legacy draft-then-scan behaviour until ops opts "
            "them in."
        ),
    )
    # ``allow_intake_on_compliance_degraded`` is a per-tenant override
    # for the compliance-service-degraded-mode path (D250.9): when the
    # shared circuit breaker for compliance-service is OPEN, intake
    # SHOULD block with 503 + Retry-After. Setting this flag True
    # opts the tenant out of that block — useful for tenants that
    # have explicit BAA carve-outs for delayed compliance scanning.
    # Default False (fail closed) per S-8.
    allow_intake_on_compliance_degraded = models.BooleanField(
        default=False,
        help_text=(
            "Phase 250.1.A.8 / D250.9 — when True, allow asset intake "
            "while the compliance-service circuit breaker is OPEN (the "
            "scan is queued for later). Default False — intake blocks "
            "with 503 + Retry-After until the breaker recovers."
        ),
    )
    # Phase 231.1 — intake compliance gate: auto-enqueue scan on Asset
    # registration and require a succeeded run (allowed_to_store=true)
    # before activation when enabled. Default False preserves behaviour
    # for existing tenants until ops opts in.
    compliance_intake_gate_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Phase 231.1 — when True, creating an Asset auto-enqueues a "
            "compliance intake scan, and activation is blocked until a "
            "SUCCEEDED ComplianceRun exists with allowed_to_store=true."
        ),
    )
    # Phase 232.1 — consent management subsystem (purposes, records, HMAC proofs).
    compliance_consent_enabled = models.BooleanField(
        default=False,
        help_text=(
            "When True, consent APIs, signup/marketplace/webhook gates, and "
            "banner flows apply for this tenant per Phase 232.1."
        ),
    )
    # Phase 232.2 — DSAR workflow (statutory clock, public ingress, fulfilment).
    compliance_dsar_enabled = models.BooleanField(
        default=False,
        help_text=(
            "When True, public DSAR submission, statutory SLA jobs, and handler "
            "queues are active per Phase 232.2."
        ),
    )
    # Phase 232.3 — breach notification workflow (statutory clocks, templates, proofs).
    compliance_breach_enabled = models.BooleanField(
        default=False,
        help_text=(
            "When True, breach incident APIs, supervisory notification drafts, "
            "template overrides, and SLA jobs are enabled per Phase 232.3."
        ),
    )
    # Phase 232.4 — Record of Processing Activities (RoPA) generator.
    compliance_ropa_enabled = models.BooleanField(
        default=False,
        help_text=(
            "When True, RoPA generation APIs and artefacts are enabled for this tenant."
        ),
    )
    # Phase 232.5 — DPIA register & review workflow.
    compliance_dpia_enabled = models.BooleanField(
        default=False,
        help_text=(
            "When True, DPIA APIs, wizard, and DPO review queue are enabled for this tenant."
        ),
    )
    # Phase 232.6 — processor agreement (DPA/BAA/SCC/BCR) inventory + expiry.
    compliance_processor_agreements_enabled = models.BooleanField(
        default=False,
        help_text=(
            "When True, processor registry, agreement records, asset–processor links, "
            "and expiry notification jobs are enabled per this tenant."
        ),
    )
    compliance_retention_enforcer_enabled = models.BooleanField(
        default=False,
        help_text=(
            "When True, the Phase 232.7 retention auto-sweep (tombstone + 90-day grace + hard-delete) "
            "may process TIME_BASED policies for this tenant when the CronJob executes."
        ),
    )
    # Phase 271.1.2 — per-tenant Stripe Connect onboarding gate.
    # When True, this tenant CAN access the Connect onboarding
    # endpoints (POST /api/v1/billing/connect/onboarding-link/,
    # GET /api/v1/billing/connect/status/) AND the KYB gate at
    # listing-publish time WILL enforce a verified ConnectAccount
    # for paid listings. When False, the endpoints return HTTP 501
    # ``connect_not_enabled`` and the KYB gate is bypassed —
    # preserving pre-271 behaviour for any tenant still in the
    # opt-out window.
    #
    # Default semantics (D-271.4 two-level rollback):
    # * Existing tenants — the migration backfills False via a
    #   literal in ``add_field`` so the 30-day notice + opt-out
    #   window per spec is preserved.
    # * New tenants — the env-INDEPENDENT callable default
    #   ``_default_connect_enabled`` returns True so every tenant
    #   created post-migration ships with Connect enabled.
    connect_enabled = models.BooleanField(
        default=_default_connect_enabled,
        help_text=(
            "Phase 271.1.2 — per-tenant Stripe Connect onboarding "
            "gate. False on existing tenants (30-day opt-out "
            "window); True on new tenants. Global override: "
            "settings.STRIPE_CONNECT_ENABLED."
        ),
    )
    # Phase 272.2 — compliance gate on access request approval.
    # When True, approve_access_request queries the latest ComplianceRun
    # and blocks approval when allowed_to_store is not True.
    # Default False for existing tenants (one-release notice window).
    access_request_compliance_gate_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Phase 272.2 — when True, access request approval requires "
            "a successful ComplianceRun with allowed_to_store=True for "
            "the referenced resource."
        ),
    )
    # Phase 274.1 — marketplace publish compliance threshold gate.
    # When True, listing publication requires a successful ComplianceRun
    # whose risk_level does not exceed the tenant's compliance_risk_threshold.
    # Default False for existing tenants (one-release notice window).
    marketplace_publish_compliance_gate_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Phase 274.1 — when True, listing publication is blocked if "
            "the latest ComplianceRun risk_level exceeds "
            "compliance_risk_threshold or allowed_to_store is not True."
        ),
    )
    # Phase 270.C.4.1 — per-tenant compliance legal-basis strict mode.
    # When True, the compliance-service rejects scans missing a valid
    # ``legal_basis`` for GDPR/UK_GDPR/LGPD-applicable data with HTTP
    # 422 ``LEGAL_BASIS_INVALID``; when False (lenient, default for
    # backward-compat), the scan succeeds with an ERROR-severity
    # issue in the report (existing Phase 19.7.1 behaviour). The
    # env-aware default factory ``_default_compliance_legal_basis_strict``
    # returns True for prod tenants + False for staging/dev so new
    # prod tenants opt into strict by default while staging stays
    # lenient — per D-270.9.
    compliance_legal_basis_strict = models.BooleanField(
        default=_default_compliance_legal_basis_strict,
        help_text=(
            "Phase 270.C.4 — when True, compliance scans that are "
            "missing a valid GDPR/UK_GDPR/LGPD legal_basis are "
            "rejected with HTTP 422 LEGAL_BASIS_INVALID. When False "
            "(default in staging/dev), the scan succeeds with an "
            "ERROR-severity issue in the report. Env-aware default: "
            "True in production, False otherwise."
        ),
    )
    # Phase 270.C.5.1 — per-tenant compliance regulation licensing.
    #
    # ``licensed_regulation_keys`` is the authoritative set of
    # regulation keys this tenant is licensed to scan against.
    # When a compliance run requests ``applicable_regulations`` that
    # are NOT in this set, the un-licensed regs surface as a
    # ``REGULATION_NOT_LICENSED`` WARNING on the run's
    # ``metadata_json["license_warnings"]``. When
    # ``strict_license_check`` is True, the run is REJECTED with
    # HTTP 422 ``REGULATION_NOT_LICENSED`` instead.
    #
    # Empty list — the default for existing tenants pre-deploy and
    # the migration backfill — DISABLES the check entirely
    # (backward-compat: existing tenants don't suddenly see
    # warnings on every scan). New tenants get the field seeded
    # from ``tenant.plan.includes_regulations`` at provisioning
    # time; operators can extend the set per-tenant via the
    # tenant-admin API for add-on purchases.
    #
    # Uppercase regulation tokens (e.g. ``["GDPR", "UK_GDPR",
    # "PIPL_CN"]``); see
    # ``services/compliance-service/regulations/__init__.py`` for
    # the canonical catalogue.
    licensed_regulation_keys = ArrayField(
        base_field=models.CharField(max_length=64),
        default=list,
        blank=True,
        help_text=(
            "Phase 270.C.5 — uppercase regulation tokens this "
            "tenant is licensed to scan against (e.g. "
            "``['GDPR', 'PIPL_CN']``). Empty list disables the "
            "check (backward-compat for pre-Phase-270.C.5 "
            "tenants). Out-of-set requests yield "
            "REGULATION_NOT_LICENSED warnings; strict_license_check "
            "elevates the warning to an HTTP 422 rejection."
        ),
    )
    strict_license_check = models.BooleanField(
        default=False,
        help_text=(
            "Phase 270.C.5 — when True, compliance runs that "
            "request regulations NOT in ``licensed_regulation_keys`` "
            "are REJECTED with HTTP 422 REGULATION_NOT_LICENSED. "
            "When False (default), the un-licensed regulations "
            "appear as WARNING entries on the run's "
            "``metadata_json['license_warnings']`` and the scan "
            "proceeds (Phase 19.7.1 lenient semantics)."
        ),
    )
    # Phase 260.2.F — pass-3 B3-5: full audit trail of file metadata reads
    # (GET /files/{id}/). When True, every successful retrieve emits
    # FILE_METADATA_VIEWED; when False (default), sampling is ~10% deterministic.
    compliance_audit_full_sampling = models.BooleanField(
        default=False,
        help_text=(
            "When True, every successful GET /api/v1/files/{id}/ emits FILE_METADATA_VIEWED. "
            "When False, the platform uses a deterministic ~10% sample per (tenant, file, user)."
        ),
    )
    # ------------------------------------------------------------------
    # Phase 250.2.A.1 — auto-activate-on-gate-pass governance flag
    # (closes Gap 2)
    # ------------------------------------------------------------------
    # ``asset_auto_activate_on_gate_pass`` is a tenant-level kill-switch
    # for the Phase 250.1.A.3 / D250.2 default-True auto-activation
    # behaviour. When True (default), the asset-creation workflow flips
    # an Asset from DRAFT to ACTIVE the moment all gates (DQ,
    # compliance, contract validation, structural floor) pass.  When
    # False, the workflow leaves the Asset in DRAFT regardless of the
    # per-call ``auto_activate`` argument — a caller cannot bypass the
    # tenant policy by passing ``auto_activate=True``.  Read at
    # ``execute()`` time and frozen into ``workflow_input`` so a flag
    # flip mid-execution does NOT affect an in-flight workflow (same
    # contract as ``compliance_fail_closed_enabled``).
    #
    # Default True for both new AND existing tenants because the
    # platform Python-level default (Phase 250.1.A.3) is already True;
    # backfilling False would silently regress current customer
    # behaviour.  Tenants who want DRAFT-first reviews opt out
    # explicitly by flipping the flag to False.
    asset_auto_activate_on_gate_pass = models.BooleanField(
        default=True,
        help_text=(
            "Phase 250.2.A.1 — when True (default), the asset-creation "
            "workflow auto-activates an Asset (DRAFT → ACTIVE) once "
            "all gates pass. When False, the workflow leaves the Asset "
            "in DRAFT regardless of the per-call auto_activate "
            "argument; a per-tenant DRAFT-first review queue. The "
            "effective decision is "
            "``per_call_auto_activate AND tenant_flag``."
        ),
    )
    # Phase 250.5.A.2 (D250.3) — federated import is opt-in. Default
    # FALSE on every tenant (including back-filled rows via the
    # 0036_tenant_federated_flag migration) so the deploy doesn't
    # silently enable the federated-asset code path for customers who
    # never asked for it. Tenants that explicitly want federated
    # import flip the flag via the platform-admin tenant management
    # surface; the gate at
    # ``DiscoveryService.create_federated_asset_with_contracts``
    # refuses any call whose effective tenant has the flag False and
    # emits the ``FEDERATED_IMPORT_REJECTED`` audit row.
    federated_import_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Phase 250.5.A.2 (D250.3) — when True, this tenant may "
            "import federated assets from configured marketplace "
            "connections. Default False so existing tenants are "
            "unchanged by the phase deploy; opt-in is required to "
            "activate the federated-import code path."
        ),
    )
    # Phase 250.6.A.1 (D250.17) — per-tenant asset-creation kill switch.
    # Default TRUE on every existing tenant so the deploy doesn't
    # accidentally freeze customer creation flows. New tenants created
    # via the onboarding flow START at False and flip to True when
    # onboarding completes (so a partially-onboarded tenant can't
    # create production assets). Ops uses the flag to FREEZE creation
    # on a tenant under investigation (e.g. compliance breach,
    # billing-dispute hold) without touching code — flipping the flag
    # to False makes ``POST /assets/`` and ``POST /assets/data-first/``
    # return 403 + ``code="ASSET_CREATION_DISABLED"`` BEFORE any
    # serializer / workflow / persistence work begins. The
    # ``/api/v1/capabilities/`` response mirrors this flag as
    # ``asset_creation`` so the SPA can render a "disabled capability"
    # page instead of letting the user fill out a form that will 403.
    asset_creation_enabled = models.BooleanField(
        default=True,
        help_text=(
            "Phase 250.6.A.1 (D250.17) — when True (default), this "
            "tenant may create assets via POST /assets/ and "
            "POST /assets/data-first/. Default TRUE so existing "
            "tenants are unaffected by the kill-switch deploy; ops "
            "flips to False to freeze creation under investigation. "
            "New tenants created via onboarding START at False until "
            "onboarding completes (separate code path)."
        ),
    )
    # Phase 260.3.B — per-tenant kill switches for Dataset and File REST
    # surfaces. Default TRUE so deploys do not regress existing tenants;
    # ops flips to False to return 403 + DATASETS_DISABLED / FILES_DISABLED
    # on all respective endpoints (mirrored in GET /api/v1/capabilities/).
    datasets_enabled = models.BooleanField(
        default=True,
        help_text=(
            "Phase 260.3.B — when True (default), /api/v1/datasets/* is "
            "enabled for this tenant. When False, every datasets endpoint "
            "returns HTTP 403 with code DATASETS_DISABLED."
        ),
    )
    files_enabled = models.BooleanField(
        default=True,
        help_text=(
            "Phase 260.3.B — when True (default), /api/v1/files/* is "
            "enabled for this tenant. When False, every files endpoint "
            "returns HTTP 403 with code FILES_DISABLED."
        ),
    )
    # Phase 260.3.E — when True, GET /datasets/{id}/sample/ applies server-side
    # PII redaction unless an authorised viewer passes include_pii=true (VIEW_PII).
    # DB default False; inserts align via save(); migrations backfill VERIFIED tenants to True.
    redact_sample_pii_in_ui = models.BooleanField(
        default=False,
        help_text=(
            "Phase 260.3.E — sample preview responses replace suspected PII with "
            "[redacted] for users without VIEW_PII (include_pii). Verified tenants "
            "default True on create/migration backfill."
        ),
    )
    # Phase 260.4.A.4 — retention window in days for hard-deletion of
    # RETIRED datasets. The cleanup management command
    # ``cleanup_retired_datasets`` reads this value at run-time, so a
    # tenant can lengthen / shorten the window without a code change
    # (for compliance regimes that mandate either longer or shorter
    # retention).
    dataset_retain_after_retire_days = models.PositiveIntegerField(
        default=90,
        help_text=(
            "Phase 260.4.A.4 — number of days a dataset row is kept "
            "after retirement before the cleanup command hard-deletes "
            "it. Default 90 days; per-tenant override supported."
        ),
    )
    # Phase 233.3 (REQ-WH-RL-001) — per-tenant outbound webhook rate limit.
    #
    # Default 300/minute = sustained ~5 deliveries/sec ceiling per tenant
    # — enough headroom for healthy fan-out (50 active webhooks each
    # firing once per ~10s) without permitting a misconfigured subscriber
    # to cause a thundering herd downstream.
    #
    # Setting this to 0 DISABLES outbound webhook delivery entirely
    # (kill-switch semantics — REQ-WH-RL-001 Scenario 3). The tenant
    # continues to RECEIVE webhook configuration changes via the API,
    # but outbound HTTP attempts are 100% rate-limited until this value
    # is restored.
    webhook_outbound_rate_limit_per_minute = models.PositiveIntegerField(
        default=300,
        help_text=(
            "Phase 233.3 — per-minute cap on outbound webhook deliveries "
            "for this tenant. 0 disables outbound webhooks entirely "
            "(kill-switch). Default 300."
        ),
    )
    # Phase 250.5.F.1 (closes G2-3) — default classification stamped
    # on EVERY federated-import asset's metadata at intake. Production-
    # safe default INTERNAL (NEVER PUBLIC) — federated metadata may
    # carry PII the source tenant hasn't yet classified, so the
    # consumer-side intake must NOT auto-publicise. Tenants can pin
    # to PII / RESTRICTED / CONFIDENTIAL for marketplaces known to
    # carry sensitive payloads.
    federated_import_classification_default = models.CharField(
        max_length=20,
        default="INTERNAL",
        help_text=(
            "Phase 250.5.F.1 — default sensitivity classification "
            "stamped on every imported federated-asset metadata blob "
            "at intake. Values mirror "
            "``governance.ClassificationCategory`` "
            "(PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED / PII / "
            "PHI / PCI / FINANCIAL / LEGAL). Default INTERNAL — "
            "production-safe posture for unknown source-tenant "
            "classification. Tenants flip to PII / RESTRICTED for "
            "marketplaces carrying sensitive payloads."
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
    # Phase 270.D.1 — Stripe Tax billing identity.
    #
    # ``tax_id`` carries the tenant's tax registration number
    # (VAT for EU, EIN/SSN for US, GST for IN/AU/etc.). Stripe is
    # the system-of-record once it validates the value via
    # ``stripe.Customer.create_tax_id``; we keep a local copy so
    # the UI can render it without a Stripe round-trip + so audit
    # rows can carry the value at the time of action.
    #
    # ``tax_id_type`` is the Stripe-vocabulary tax type
    # (``eu_vat``, ``gb_vat``, ``us_ein``, ``br_cnpj``, …).
    #
    # ``tax_id_verified`` flips to True when Stripe's
    # ``customer.tax_id.verified`` webhook fires (270.D.4); flips
    # back to False on ``customer.tax_id.deleted`` or when the
    # tenant submits a new value pending re-verification.
    #
    # ``tax_address`` is a JSONField storing the registered
    # address (country, postal_code, line1, …). Encrypted at rest
    # via the existing AWS KMS pattern (Phase 211, mirrors
    # ``sso_config`` at line 1250+). Read via
    # ``Tenant.get_tax_address()`` which decrypts; write the dict
    # directly + ``save()`` encrypts. Empty / None when the
    # tenant hasn't yet submitted billing-identity details.
    tax_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text=(
            "Phase 270.D — tenant tax registration number "
            "(e.g. ``GB123456789`` for UK VAT, ``BR12345678000199`` "
            "for BR CNPJ). Empty when unset. Verification status "
            "in ``tax_id_verified``."
        ),
    )
    tax_id_type = models.CharField(
        max_length=32,
        blank=True,
        default="",
        help_text=(
            "Phase 270.D — Stripe-vocabulary tax type "
            "(``eu_vat``, ``gb_vat``, ``us_ein``, ``br_cnpj``, "
            "etc.). Empty when ``tax_id`` is unset."
        ),
    )
    tax_id_verified = models.BooleanField(
        default=False,
        help_text=(
            "Phase 270.D — True when Stripe's "
            "``customer.tax_id.verified`` webhook confirmed the "
            "ID. Flips to False on a new submission OR a "
            "``customer.tax_id.deleted`` event."
        ),
    )
    tax_address = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            "Phase 270.D — KMS-encrypted (Phase 211 pattern) "
            "registered tax address: ``{country, postal_code, "
            "line1, line2, city, state}``. Read via "
            "``Tenant.get_tax_address()``; write the plaintext "
            "dict and ``save()`` encrypts. NULL when unset."
        ),
    )
    # Phase 250.6.D.1 (closes G2-1 / P2-1) — onboarding-completion timestamp.
    # NULL when onboarding has not yet completed; set to ``timezone.now()``
    # the moment all three signals (TENANT_ADMIN role granted, KYC
    # submitted, active subscription) are first satisfied. The setter is
    # ``hub.apps.tenants.onboarding.mark_onboarding_complete_if_ready``
    # which is invoked from post_save signals on UserRole / Tenant /
    # Subscription. Field is also DB-indexed to support the
    # ``onboarding_completed_at IS NULL`` filter the capabilities
    # endpoint uses to differentiate ONBOARDING_INCOMPLETE from
    # DISABLED_BY_OPS reasons.
    onboarding_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Phase 250.6.D.1 — timestamp the tenant FIRST satisfied all "
            "three onboarding signals (TENANT_ADMIN role granted, KYC "
            "submitted, active Subscription). NULL = onboarding not yet "
            "complete. One-way ratchet: never cleared once set."
        ),
    )
    deleted_at = models.DateTimeField(
        null=True, blank=True, help_text="Timestamp when tenant was marked for deletion"
    )
    # ----------------------------------------------------------------------
    # Phase 235.3 — tenant deactivate / hard-delete after 90-day grace.
    # ----------------------------------------------------------------------
    # ``scheduled_for_deletion_at`` is the load-bearing field for the
    # 90-day grace contract: ``DELETE /api/v1/admin/tenants/{id}/``
    # stamps it to ``now()`` (alongside the existing Phase 226
    # ``deleted_at`` for soft-delete semantics); the daily
    # ``tenant_hard_delete_sweep`` cron then hard-deletes the row
    # ``90 days`` after this timestamp. Decoupled from ``deleted_at``
    # so an operator could (a) soft-delete with grace via 235.3 and
    # (b) acquire a legal-hold + restore inside the grace window —
    # the ``restore()`` path clears ``deleted_at`` AND
    # ``scheduled_for_deletion_at`` together (the sweep would
    # otherwise still nuke the row a day after restore).
    scheduled_for_deletion_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Phase 235.3 — UTC timestamp when an admin invoked "
            "``DELETE /api/v1/admin/tenants/{id}/``. The daily "
            "``tenant_hard_delete_sweep`` cron hard-deletes rows where "
            "this is older than 90 days AND ``legal_hold=False`` AND "
            "no open DSAR-restriction. NULL on live tenants."
        ),
    )
    legal_hold = models.BooleanField(
        default=False,
        help_text=(
            "Phase 235.3 — when True, blocks both the PLATFORM_ADMIN "
            "soft-delete endpoint (HTTP 422 LEGAL_HOLD_ACTIVE) AND the "
            "daily hard-delete sweep (the sweep skips the tenant and "
            "logs ``legal_hold_active`` in its summary). Flipped on by "
            "legal / compliance ops when discovery is in scope; "
            "flipped off only after the hold is lifted."
        ),
    )
    # ----------------------------------------------------------------------
    # Phase 235.4 — Impersonation opt-in (per tenant)
    # ----------------------------------------------------------------------
    # ``impersonation_allowed`` is the master switch for the
    # PLATFORM_ADMIN impersonation feature on this tenant. Default
    # False: deploys MUST NOT silently grant the support / debug
    # capability — ops flips it per tenant after the customer has
    # explicitly authorised (commonly via a clause in the BAA / DPA).
    # The ``POST /api/v1/admin/impersonate/`` endpoint validates this
    # flag and returns HTTP 403 + ``IMPERSONATION_NOT_ENABLED`` BEFORE
    # any session row is materialised. The SPA hides the
    # ``ImpersonationButton`` when this flag is False (mirrors the
    # backend gate so a misconfigured FE can't trigger the wasteful
    # 403 round-trip).
    impersonation_allowed = models.BooleanField(
        default=False,
        help_text=(
            "Phase 235.4 — when True, PLATFORM_ADMIN may impersonate "
            "users in this tenant via ``POST /api/v1/admin/impersonate/``. "
            "Default False so the deploy does not silently grant the "
            "capability; ops flips per tenant after the customer has "
            "explicitly authorised impersonation (BAA / DPA addendum)."
        ),
    )
    # ``impersonation_default_max_minutes`` is the per-tenant default
    # for the duration cap stamped on a new ``ImpersonationSession``.
    # Hard cap is 240 (4 h) enforced in the endpoint regardless of
    # this value — operators MUST NOT set this above 240. Default 60
    # (one hour) gives most support flows enough headroom without
    # accidentally creating multi-hour live sessions.
    impersonation_default_max_minutes = models.PositiveIntegerField(
        default=60,
        validators=[MinValueValidator(5), MaxValueValidator(240)],
        help_text=(
            "Phase 235.4 — per-tenant default max-minutes for a new "
            "impersonation session. Hard cap is 240; the endpoint "
            "rejects callers that override above the cap with HTTP "
            "400 ``MAX_MINUTES_OUT_OF_RANGE``."
        ),
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

    def save(self, *args, **kwargs):
        """Default Phase 260.3.E sample PII redaction from KYC on tenant creation."""
        if self._state.adding:
            self.redact_sample_pii_in_ui = self.kyc_status == KYCStatus.VERIFIED

        # Phase 270.D.1 — encrypt ``tax_address`` (Tenant-level field;
        # see line 738) on save with the same KMS pattern that
        # ``TenantConfig.sso_config`` uses. ``{"_encrypted": <cipher>}``
        # is the sentinel that distinguishes already-encrypted
        # ciphertext from plaintext input on subsequent saves. The
        # encryption block was historically misplaced on
        # ``TenantConfig.save`` (which has no ``tax_address`` attribute)
        # and 500'd every registration via
        # ``'TenantConfig' object has no attribute 'tax_address'``.
        if (
            isinstance(self.tax_address, dict)
            and self.tax_address
            and not self.tax_address.get("_encrypted")
        ):
            try:
                encrypted = encrypt_json_field(self.tax_address)
                self.tax_address = {"_encrypted": encrypted}
            except EncryptionError as e:
                raise ValidationError(
                    {"tax_address": f"Failed to encrypt: {e}"}
                ) from e

        super().save(*args, **kwargs)

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
        """Restore a soft-deleted tenant.

        Phase 235.3 — also clears ``scheduled_for_deletion_at`` so the
        daily hard-delete sweep doesn't nuke the just-restored tenant
        on its next run. Treat both timestamps as a coupled pair —
        clearing one without the other would leave the sweep with
        stale grace-window state.
        """
        self.status = TenantStatus.ACTIVE
        self.deleted_at = None
        self.scheduled_for_deletion_at = None
        self.save(
            update_fields=[
                "status",
                "deleted_at",
                "scheduled_for_deletion_at",
                "updated_at",
            ]
        )


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

    # Phase 231.2 — Marketplace publish + asset activation gate on latest SUCCEEDED run risk_level.
    compliance_risk_threshold = models.CharField(
        max_length=20,
        choices=_COMPLIANCE_RISK_THRESHOLD_CHOICES,
        default=RiskLevel.HIGH.value,
        help_text=(
            "Maximum acceptable compliance risk level for publishing listings and activating assets; "
            "risk strictly above this threshold blocks publish/activation."
        ),
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

        # ``tax_address`` lives on ``Tenant``, not ``TenantConfig`` —
        # its encryption-on-save is wired into ``Tenant.save`` instead
        # (see above). The misplaced block previously here raised
        # ``'TenantConfig' object has no attribute 'tax_address'`` on
        # every TenantConfig.save() (e.g. registration's
        # ``TenantConfig.objects.create(...)`` after personal-tenant
        # bootstrap), which 500'd ~10 tests per E2E batch.

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

    def get_tax_address(self) -> dict:
        """Phase 270.D.1 — return decrypted tax address.

        Mirrors ``get_sso_config`` semantics: legacy plaintext
        dicts (e.g. seeded via the Django admin / data migration
        BEFORE the encrypt-on-save patch landed) are returned
        as-is; encrypted ``{"_encrypted": <cipher>}`` shapes are
        decrypted. Returns an empty dict when the field is NULL
        / empty so callers can ``dict.get("country")`` without
        defensive None checks.
        """
        if not self.tax_address:
            return {}
        if isinstance(self.tax_address, dict):
            if "_encrypted" in self.tax_address:
                return decrypt_json_field(
                    self.tax_address["_encrypted"]
                )
            return self.tax_address
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


# ---------------------------------------------------------------------------
# Phase 235.1 — Two-person rule on sensitive feature-flag flips
# ---------------------------------------------------------------------------


class FeatureFlagFlipApprovalStatus(models.TextChoices):
    """Lifecycle states for a ``FeatureFlagFlipApproval`` row."""

    PENDING = "PENDING", "Pending"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    EXPIRED = "EXPIRED", "Expired"


class FeatureFlagFlipApproval(models.Model):
    """Phase 235.1 — pending second-person approval for a sensitive flag flip.

    Every flag tagged ``sensitive=True`` in
    :mod:`hub.apps.tenants.feature_flag_registry` REQUIRES a row of
    this class to land BEFORE the flag value actually changes. A
    SECOND ``PLATFORM_ADMIN`` (different from ``requested_by``)
    transitions the row to ``APPROVED`` via the
    ``POST /api/v1/admin/feature-flag-approvals/{id}/approve/``
    endpoint, at which point the matching ``Tenant.<flag>`` value
    flips inside the same atomic transaction.

    Uniqueness contract
    -------------------
    Only ONE ``PENDING`` row per ``(tenant, flag)`` is allowed at a
    time — partial unique constraint (Postgres ``UniqueConstraint``
    with ``condition``). A SECOND request for the same flip BEFORE
    the first is resolved would otherwise create a race between two
    approvers approving distinct rows.

    Audit trail
    -----------
    * Creation emits ``FEATURE_FLAG_FLIP_APPROVAL_REQUESTED`` (in
      :func:`hub.apps.tenants.views.AdminTenantFeatureFlagView`).
    * Approval emits ``FEATURE_FLAG_FLIP_APPROVED`` AND
      ``TENANT_FEATURE_FLAG_CHANGED`` in the same transaction (the
      approval handler is the canonical caller of the flip).
    * ``approval_id`` is included in both events' ``details_json`` so
      an auditor can correlate the two-person-rule transition.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="feature_flag_flip_approvals",
        help_text="Tenant the flag flip targets.",
    )
    flag = models.CharField(
        max_length=128,
        help_text=(
            "Name of the ``Tenant.<flag>_enabled`` BooleanField the request "
            "wants to flip. MUST be a name registered in "
            ":mod:`hub.apps.tenants.feature_flag_registry` with "
            "``sensitive=True``."
        ),
    )
    requested_value = models.BooleanField(
        help_text=(
            "The new value the requester wants the flag to take. Stored "
            "explicitly so an auditor can replay intent even if the live "
            "tenant value drifts between request and approval."
        ),
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="requested_feature_flag_flips",
        help_text="PLATFORM_ADMIN who opened the request.",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="approved_feature_flag_flips",
        null=True,
        blank=True,
        help_text=(
            "Second PLATFORM_ADMIN who approved the request. MUST be "
            "different from ``requested_by`` — the model's "
            ":meth:`mark_approved` enforces this; the API enforces it "
            "again at the permission layer."
        ),
    )
    status = models.CharField(
        max_length=20,
        choices=FeatureFlagFlipApprovalStatus.choices,
        default=FeatureFlagFlipApprovalStatus.PENDING,
    )
    reason = models.TextField(
        help_text=(
            "Free-text justification (min 10 chars enforced at the API "
            "layer). Pinned in the meta-audit so the regulator can read "
            "WHY a sensitive flag was flipped."
        ),
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "feature_flag_flip_approvals"
        ordering = ["-requested_at"]
        constraints = [
            # Only ONE pending row per (tenant, flag) — partial unique
            # index so resolved (approved/rejected/expired) rows can
            # coexist for the same pair (historical record).
            models.UniqueConstraint(
                fields=["tenant", "flag"],
                condition=models.Q(status="PENDING"),
                name="ffa_one_pending_per_tenant_flag",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "flag", "status"]),
            models.Index(fields=["status", "requested_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.tenant_id}:{self.flag}→{self.requested_value} [{self.status}]"

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def mark_approved(self, *, by) -> None:
        """Move the row to ``APPROVED``; the caller MUST persist the flag flip.

        Raises ``ValueError(SELF_APPROVAL_FORBIDDEN)`` if ``by`` is
        the same user as ``requested_by`` — the two-person rule's
        load-bearing invariant. The API layer also enforces this so
        the model guard is defense-in-depth against direct ORM use
        (e.g. a management command or a fixture replay).
        """
        if by is None or getattr(by, "id", None) is None:
            raise ValueError("Approver user is required.")
        if str(by.id) == str(self.requested_by_id):
            raise ValueError(
                "SELF_APPROVAL_FORBIDDEN: the approver must be a different "
                "PLATFORM_ADMIN than the requester (two-person rule)."
            )
        if self.status != FeatureFlagFlipApprovalStatus.PENDING:
            raise ValueError(
                f"Cannot approve a {self.status!s} row; only PENDING is "
                "transitionable to APPROVED."
            )
        self.status = FeatureFlagFlipApprovalStatus.APPROVED
        self.approved_by = by
        self.approved_at = timezone.now()
        self.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])


# ---------------------------------------------------------------------------
# Phase 235.4 — Impersonation session
# ---------------------------------------------------------------------------


class ImpersonationSessionStatus(models.TextChoices):
    """Lifecycle states for an ``ImpersonationSession`` row."""

    ACTIVE = "ACTIVE", "Active"
    ENDED = "ENDED", "Ended"


class ImpersonationSession(models.Model):
    """Phase 235.4 — A live PLATFORM_ADMIN impersonation session.

    The row is the durable record that an operator assumed another
    user's identity for a bounded time window. It is the ONLY surface
    that links a JWT carrying an ``impersonation_session_id`` claim
    back to BOTH the real operator AND the impersonated user — every
    audit event emitted under the impersonation JWT carries this
    session UUID in ``details_json.impersonation_session_id`` so an
    auditor reconstructing intent can join the chain.

    Status contract
    ---------------
    * ``ACTIVE`` — created by the start endpoint; the JWT is valid
      until ``expires_at`` OR the operator clicks Exit (whichever
      arrives first).
    * ``ENDED`` — set by EITHER the exit endpoint (``end_reason =
      manual_exit``) OR the daily expiration sweep (``end_reason =
      expired``). ``ended_at`` is the moment of transition.

    Audit trail
    -----------
    * Start emits ``IMPERSONATION_STARTED`` in BOTH the impersonator's
      home tenant AND the impersonated user's tenant (two rows). The
      target-tenant row is the auditor-facing record; the impersonator-
      tenant row is the security-team record.
    * End emits ``IMPERSONATION_ENDED`` under the impersonated user's
      tenant context with ``end_reason`` in ``details_json``.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    impersonator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="impersonation_sessions_started",
        help_text="The PLATFORM_ADMIN who opened the session.",
    )
    impersonated_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="impersonation_sessions_as_target",
        help_text="The user whose identity is being assumed.",
    )
    impersonator_tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="impersonation_sessions_outbound",
        help_text=(
            "The impersonator's home tenant (typically the PLATFORM_ADMIN's "
            "operator tenant). Stored explicitly so the row survives the "
            "impersonator user being deleted/migrated."
        ),
    )
    impersonated_tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="impersonation_sessions_inbound",
        help_text="The tenant the impersonated user belongs to.",
    )
    status = models.CharField(
        max_length=20,
        choices=ImpersonationSessionStatus.choices,
        default=ImpersonationSessionStatus.ACTIVE,
        db_index=True,
        help_text="ACTIVE or ENDED.",
    )
    max_minutes = models.PositiveIntegerField(
        help_text=(
            "Operator-chosen (or tenant-default) duration cap in minutes. "
            "The hard cap is 240 (enforced at the endpoint); values above "
            "the cap are rejected with HTTP 400 MAX_MINUTES_OUT_OF_RANGE."
        ),
    )
    reason = models.TextField(
        help_text=(
            "Operator justification (min 10 chars enforced at the API "
            "layer). Pinned in the audit trail so an auditor can read "
            "WHY the session was opened."
        ),
    )
    started_at = models.DateTimeField()
    expires_at = models.DateTimeField(db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    end_reason = models.CharField(
        max_length=32,
        default="",
        blank=True,
        help_text="``manual_exit`` (user-driven) or ``expired`` (cron-driven).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "impersonation_sessions"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["impersonator"]),
            models.Index(fields=["impersonated_user"]),
            models.Index(fields=["impersonated_tenant", "status"]),
            models.Index(fields=["status", "expires_at"]),
        ]

    def __str__(self) -> str:
        return (
            f"{self.impersonator_id} → {self.impersonated_user_id} "
            f"[{self.status}, {self.started_at:%Y-%m-%dT%H:%M:%SZ}]"
        )

    def is_active(self) -> bool:
        return self.status == ImpersonationSessionStatus.ACTIVE

    def end(self, *, reason: str) -> None:
        """Transition ACTIVE → ENDED. No-op if already ENDED.

        Caller is expected to emit the matching ``IMPERSONATION_ENDED``
        audit event AFTER this call returns — the model intentionally
        does not emit audits so unit tests can exercise state
        transitions without standing up the audit pipeline.
        """
        if self.status == ImpersonationSessionStatus.ENDED:
            return
        self.status = ImpersonationSessionStatus.ENDED
        self.ended_at = timezone.now()
        self.end_reason = reason
        self.save(
            update_fields=[
                "status",
                "ended_at",
                "end_reason",
                "updated_at",
            ]
        )
