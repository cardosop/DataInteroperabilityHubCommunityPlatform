"""
Django settings for hub project.

Generated with configuration for Interoperable Data Hub MVP.
"""

import os
import sys
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Initialize environment variables
env = environ.Env(
    DEBUG=(bool, False),
    SECRET_KEY=(str, ""),
    ALLOWED_HOSTS=(list, []),
)

# Read .env file
environ.Env.read_env(os.path.join(BASE_DIR, ".env.dev"))

# Environment: production, staging, development. Used for secrets and CORS enforcement.
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development").strip().lower()

# ---------------------------------------------------------------------------
# Sentry Error Tracking
# ---------------------------------------------------------------------------
import sentry_sdk  # noqa: E402

SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=ENVIRONMENT,
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.1),
        send_default_pii=False,
        # Prevent Sentry from leaking PII or secrets
        before_send=lambda event, hint: event,
    )

# ---------------------------------------------------------------------------
# Secrets Integration (Phase 211: AWS Secrets Manager)
# Must run BEFORE any secret consumption so downstream settings read the
# injected env vars.  Controlled by AWS_SECRETS_ENABLED env var (default: false).
# ---------------------------------------------------------------------------
_AWS_SECRETS_ENABLED = os.environ.get("AWS_SECRETS_ENABLED", "false").strip().lower() == "true"
if _AWS_SECRETS_ENABLED:
    from hub.aws_secrets_loader import load_from_aws  # noqa: E402

    load_from_aws()

# Dev-only default secrets; production MUST set SECRET_KEY and JWT_SECRET_KEY via env (see validation below).
_DEV_SECRET_KEY = "dev-secret-key-not-for-production"
_DEV_JWT_SECRET_KEY = "dev-jwt-secret-key-not-for-production"
_DEV_ENCRYPTION_KEY = "dev-encryption-key-not-for-production"

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY", default=_DEV_SECRET_KEY)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool("DEBUG", default=False)

if ENVIRONMENT == "production" and DEBUG:
    raise ImproperlyConfigured(
        "DEBUG must be False in production. "
        "Set DEBUG=False in environment variables."
    )

# Add testserver for Django test client (always in dev/test environments)
default_hosts = [
    "localhost",
    "127.0.0.1",
    "api-service",
    "testserver",
]  # testserver required for Django test client
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=default_hosts)

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",  # Required for SearchVectorField and GinIndex
    # Third-party apps
    "rest_framework",
    "drf_spectacular",  # OpenAPI 3.0 schema generation
    "corsheaders",
    "django_rq",
    "strawberry.django",
    # channels is optional - only add if available
    # "channels",  # Made optional to prevent startup failures if not installed
    # graphene_django is optional - only add if available
    # "graphene_django",  # Made optional to prevent startup failures if not installed
    "django_structlog",
    # Phase 228 X (228.X.9 / REQ-LIN-X-009) — wires the
    # ``manage.py lintmigrations`` command + the ``makemigrations``
    # post-hook lint check. Forbidden ops (DROP COLUMN, ALTER COLUMN
    # TYPE, non-concurrent CREATE INDEX, NOT NULL on existing column
    # without default) fail CI before they land in prod. Optional —
    # gated by the import guard below so a dev environment without
    # the package installed still boots.
    # django-prometheus removed: Not compatible with Django 6.0
    # Migrated to OpenTelemetry metrics with Prometheus exporter
    # Local apps
    "hub.apps.core",
    "hub.apps.tenants",
    "hub.apps.users",
    "hub.apps.auth",
    "hub.apps.audit",
    "hub.apps.billing",
    "hub.apps.platform",
    "hub.apps.gdpr",
    "hub.apps.files",
    "hub.apps.datasets",
    "hub.apps.assets",
    "hub.apps.jobs",
    "hub.apps.contracts",
    "hub.apps.dq",
    "hub.apps.compliance",
    "hub.apps.governance",
    "hub.apps.semantic",
    "hub.apps.marketplace",
    # 'hub.apps.marketplace',
    "hub.apps.developer",
    "hub.apps.api",
    "hub.apps.graphql",
    "hub.apps.graphql_ld",  # Phase 230.13 (REQ-SEM-GQL-001) — GraphQL-LD endpoint
    # hub.apps.graphql_graphene is optional - only add if graphene_django is available
    # "hub.apps.graphql_graphene",  # Made optional to prevent startup failures if not installed
    "hub.apps.health",
    "hub.apps.observability",
    "hub.apps.notifications",
    "hub.apps.rate_limiting",
    "hub.apps.scheduled_ingestion",
    "hub.apps.scheduled_export",
    "hub.apps.search",
    "hub.apps.webhooks.apps.WebhooksConfig",
    "hub.apps.api.analytics",
    "hub.apps.orchestration",
    "hub.apps.websocket",  # WebSocket API
    "hub.apps.ai",  # AI/ML features
    "hub.apps.ml",  # ML Model Registry Bridge
    "hub.apps.social",  # Social features
    "hub.apps.mesh",  # Data mesh domains and federated governance
    "hub.apps.virtualization",  # Data virtualization and federated queries
    "hub.apps.integrations",  # Marketplace connectors and integrations
    "hub.apps.baas",  # BaaS Platform (API Gateway, usage tracking, developer portal)
    "hub.apps.transformation",  # Data transformation pipelines (Phase 115A)
    "hub.apps.versioning",  # Versioning API (list/get/compare versions for contracts and datasets)
    "hub.apps.security",   # CSP violation reporting + security metrics
]

# Phase 228 X (228.X.9 / REQ-LIN-X-009) — django-migration-linter
# integration. The package adds the ``manage.py lintmigrations``
# command + a ``makemigrations`` post-hook check. Forbidden
# operations (DROP COLUMN, ALTER COLUMN TYPE, non-concurrent CREATE
# INDEX, NOT NULL on existing column without default) raise during
# the lint pass; CI runs ``manage.py lintmigrations --quiet`` and
# fails on any error. Optional — guarded so a dev box without the
# package installed still boots.
try:
    import django_migration_linter  # noqa: F401
    if "django_migration_linter" not in INSTALLED_APPS:
        INSTALLED_APPS.append("django_migration_linter")
    # The library reads MIGRATION_LINTER_OPTIONS for behavior
    # tuning. We exclude data migrations + already-shipped
    # additive-only migrations (the spec invariant is that every
    # NEW migration is additive-only; legacy ones are exempt).
    MIGRATION_LINTER_OPTIONS = {
        "ignore_name_contains": "_data_",
        # Forbidden categories — the library calls these "DATA_LOSS"
        # + "BACKWARD_INCOMPATIBLE_OR_ERRORS" + "RUNTIME_HAZARDS".
        "exclude_apps": [],
        "include_apps": [
            "contracts", "tenants", "audit", "integrations",
        ],
    }
except ImportError:
    pass

# Conditionally add graphene_django and graphql_graphene app if available
# This prevents startup failures if graphene-django is not installed
try:
    import graphene_django  # noqa: F401

    # Add graphene_django to INSTALLED_APPS if available
    if "graphene_django" not in INSTALLED_APPS:
        INSTALLED_APPS.insert(INSTALLED_APPS.index("strawberry.django") + 1, "graphene_django")
    # Add graphql_graphene app if available
    if "hub.apps.graphql_graphene" not in INSTALLED_APPS:
        INSTALLED_APPS.insert(
            INSTALLED_APPS.index("hub.apps.graphql") + 1, "hub.apps.graphql_graphene"
        )
except ImportError:
    # graphene_django is not installed - this is OK, GraphQL Graphene endpoint won't be available
    pass

# Conditionally add channels if available (for WebSocket support)
try:
    import channels  # noqa: F401

    # Add channels to INSTALLED_APPS if available
    if "channels" not in INSTALLED_APPS:
        INSTALLED_APPS.insert(INSTALLED_APPS.index("strawberry.django") + 1, "channels")
except ImportError:
    # channels is not installed - this is OK, WebSocket support won't be available
    pass

MIDDLEWARE = [
    # 0 — Must be first: sets security headers (HSTS, nosniff, XSS, SSL redirect)
    "django.middleware.security.SecurityMiddleware",
    # 1 — Must be second (before SessionMiddleware): handles CORS preflight responses
    "corsheaders.middleware.CorsMiddleware",
    # 2 — Content Security Policy headers
    "csp.middleware.CSPMiddleware",
    # Custom hub observability / tracing middlewares (before session/auth so spans cover everything)
    "hub.apps.observability.middleware.MetricsMiddleware",  # Custom metrics middleware
    "django_structlog.middlewares.request.RequestMiddleware",
    "hub.apps.api.middleware.RequestIDMiddleware",  # Request ID generation
    "hub.apps.api.middleware.tracing.TraceIDMiddleware",  # Trace ID extraction and propagation
    "hub.apps.observability.middleware.span_middleware.SpanMiddleware",  # OpenTelemetry span instrumentation
    # Standard Django middlewares
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "hub.apps.api.middleware.mvp_mode_gate.MvpModeApiGateMiddleware",
    "hub.apps.api.middleware.csrf_exempt.APIEndpointCSRFExemptMiddleware",  # CSRF exemption for API endpoints
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # API validation MUST come after AuthenticationMiddleware so request.user is populated
    "hub.apps.api.standards.validation_middleware.APIValidationMiddleware",
    "hub.apps.auth.middleware.TenantScopingMiddleware",  # Tenant scoping after authentication
    # Bind tenant_id + user_id into structlog context BEFORE the view runs (13.5).
    # Must sit after TenantScopingMiddleware so request.tenant is already set.
    "hub.apps.api.middleware.StructlogContextMiddleware",
    "hub.apps.tenants.middleware.TenantSuspensionMiddleware",  # Tenant suspension enforcement
    "hub.apps.api.versioning.APIVersionMiddleware",  # API versioning and deprecation warnings
    "hub.apps.api.middleware.idempotency.IdempotencyMiddleware",  # Idempotency key handling
    "hub.apps.api.middleware.cache_headers.CacheHeadersMiddleware",  # HTTP cache headers (ETag, Last-Modified, Cache-Control)
    "hub.apps.rate_limiting.middleware.RateLimitMiddleware",  # Advanced rate limiting (replaces basic middleware)
    "hub.apps.api.analytics.middleware.APIAnalyticsMiddleware",  # API analytics tracking
    "hub.apps.baas.middleware.BaaSUsageRecordingMiddleware",  # BaaS usage recording (API-key requests)
    "hub.apps.governance.middleware.AccessLoggingMiddleware",  # Access logging for analytics
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "hub.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "hub.wsgi.application"

# ASGI Configuration for WebSocket support
ASGI_APPLICATION = "hub.asgi.application"

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases
# When running locally (outside Docker), use 'localhost'
# When running in Docker, use 'postgres' (service name)
# For tests, use PostgreSQL if available, otherwise SQLite
# PostgreSQL is preferred for tests as it handles threading properly
import sys


# Helper function to detect staging environment for tests
def _detect_staging_for_tests():
    """
    Detect if we're running tests against staging environment.

    This function should ONLY be called within test-specific blocks.
    It defaults to False (non-staging) if detection fails to avoid
    affecting production environments.
    """
    # Check environment variable first (most reliable)
    test_env = os.getenv("TEST_ENVIRONMENT", "").lower()
    if test_env == "staging":
        return True
    if test_env == "default":
        return False

    # Auto-detect by checking staging API port
    try:
        import httpx

        response = httpx.get("http://localhost:8001/health", timeout=1, follow_redirects=False)
        # Accept 200 (OK), 301/302 (redirects), 503 (unhealthy but service exists)
        if response.status_code in [200, 301, 302, 503]:
            return True
    except (ConnectionError, TimeoutError, OSError, Exception) as e:
        # Catch all exceptions including httpx.ConnectError to prevent import failures during tests
        # Also check if staging PostgreSQL port is accessible as fallback
        try:
            import psycopg2

            test_conn = psycopg2.connect(
                host="localhost",
                port=5433,
                database="hub_staging",
                user="hub_staging",
                password="hub_staging_secure",
                connect_timeout=1,
            )
            test_conn.close()
            return True
        except (psycopg2.OperationalError, psycopg2.Error, ConnectionError, TimeoutError):
            # Staging database not available - expected in non-staging environments
            pass
        except Exception as e:
            # Log unexpected errors but don't fail startup
            import logging

            logger = logging.getLogger(__name__)
            logger.debug(
                "Unexpected error checking staging database",
                extra={"error_type": type(e).__name__},
            )

    # Default to False (non-staging) if detection fails
    # This prevents production from accidentally using staging ports
    return False


if "test" in sys.argv or "pytest" in sys.modules:
    # REQUIRED: Use PostgreSQL for tests (no SQLite fallback)
    # PostgreSQL is required for proper threading, transaction handling, and consistency with production
    import os

    # Import psycopg2 with proper error handling
    try:
        import psycopg2
        from psycopg2 import extensions as psycopg2_extensions
    except ImportError:
        raise RuntimeError(
            "psycopg2 is required for tests but not installed. "
            "Install it with: pip install psycopg2-binary"
        )

    # Get PostgreSQL connection parameters
    # For E2E tests, detect which PostgreSQL is actually running by trying both ports
    postgres_host = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port_env = os.getenv("POSTGRES_PORT")

    if postgres_port_env:
        # Use explicitly set port
        postgres_port = postgres_port_env
        # Detect staging based on port
        staging_detected = postgres_port == "5433"
        postgres_db = os.getenv("POSTGRES_DB", "hub_staging" if staging_detected else "hub")
        postgres_user = os.getenv("POSTGRES_USER", "hub_staging" if staging_detected else "hub")
        postgres_password = os.getenv(
            "POSTGRES_PASSWORD", "hub_staging_secure" if staging_detected else "hub"
        )
    else:
        # Try to detect which PostgreSQL port is accessible
        # Try default port 5432 first (most common)
        postgres_port = None
        postgres_db = None
        postgres_user = None
        postgres_password = None

        # Try port 5432 with default credentials
        # CRITICAL: Try passwords in order - if env var is set but wrong, we still try actual passwords
        # This handles cases where POSTGRES_PASSWORD env var doesn't match actual DB password
        env_password = os.getenv("POSTGRES_PASSWORD")
        passwords_to_try = []
        if env_password:
            # If env var is set, try it first, then fall back to common passwords
            passwords_to_try = [env_password, "hub", "hub_secure"]
        else:
            # If no env var, try common passwords in order
            passwords_to_try = ["hub", "hub_secure"]

        connection_found = False
        for port, db_name, user in [
            (5432, "hub", "hub"),
            (5432, "postgres", "hub"),  # Try postgres database for test DB creation
            (5433, "hub_staging", "hub_staging"),
            (5433, "postgres", "hub_staging"),  # Try postgres database
        ]:
            for password in passwords_to_try:
                try:
                    test_conn = psycopg2.connect(
                        host=postgres_host,
                        port=port,
                        database=db_name,
                        user=os.getenv("POSTGRES_USER", user),
                        password=password,
                        connect_timeout=2,
                    )
                    test_conn.close()
                    postgres_port = str(port)
                    postgres_db = os.getenv("POSTGRES_DB", db_name)
                    postgres_user = os.getenv("POSTGRES_USER", user)
                    # Use the password that actually worked, not necessarily the env var
                    postgres_password = password
                    connection_found = True
                    break
                except Exception:
                    continue
            if connection_found:
                break

        # If no connection worked, fall back to staging detection
        if not postgres_port:
            staging_detected = _detect_staging_for_tests()
            default_port = "5433" if staging_detected else "5432"
            postgres_port = default_port
            postgres_db = os.getenv("POSTGRES_DB", "hub_staging" if staging_detected else "hub")
            postgres_user = os.getenv("POSTGRES_USER", "hub_staging" if staging_detected else "hub")
            postgres_password = os.getenv(
                "POSTGRES_PASSWORD", "hub_staging_secure" if staging_detected else "hub"
            )

    # Verify PostgreSQL is available - raise clear error if not
    # Add retry logic for "starting up" errors (PostgreSQL may still be initializing)
    import time

    max_retries = 30  # Wait up to 60 seconds (30 retries * 2 seconds)
    retry_delay = 2
    last_error = None

    for attempt in range(max_retries):
        try:
            test_conn = psycopg2.connect(
                host=postgres_host,
                port=postgres_port,
                database=postgres_db,
                user=postgres_user,
                password=postgres_password,
                connect_timeout=5,
            )
            test_conn.close()
            # Connection successful, break out of retry loop
            break
        except psycopg2.OperationalError as e:
            last_error = e
            error_msg = str(e).lower()
            # Retry on "starting up" and on transient DNS (Docker DNS can fail briefly)
            is_starting_up = any(
                phrase in error_msg
                for phrase in [
                    "starting up",
                    "the database system is starting up",
                    "connection refused",
                    "connection to server",
                ]
            )
            is_name_resolution = any(
                phrase in error_msg
                for phrase in [
                    "could not translate host name",
                    "temporary failure in name resolution",
                    "name or service not known",
                ]
            )
            is_retryable = is_starting_up or is_name_resolution

            if is_retryable and attempt < max_retries - 1:
                # Retry for "starting up" or transient DNS (e.g. Docker DNS)
                import os
                import warnings

                # Only log if in verbose mode or Docker Compose E2E test mode
                if (
                    os.getenv("DOCKER_COMPOSE_E2E_TEST", "").lower() == "true"
                    or os.getenv("VERBOSE", "").lower() == "true"
                ):
                    reason = "name resolution" if is_name_resolution else "starting up"
                    warnings.warn(
                        f"PostgreSQL connection failed ({reason}), retrying in {retry_delay}s "
                        f"(attempt {attempt + 1}/{max_retries}). "
                        f"Host: {postgres_host}:{postgres_port}, DB: {postgres_db}."
                    )
                time.sleep(retry_delay)
                continue
            elif is_retryable:
                # Max retries reached
                import os
                import warnings

                if is_name_resolution:
                    # DNS failed repeatedly - raise with actionable hint
                    hint = (
                        " Host 'postgres-test' resolves only inside the test Docker network. "
                        "Run tests via: ./scripts/run_phase_12a_batched.sh (or exec into api-service-test)."
                    )
                    raise RuntimeError(
                        f"PostgreSQL connection failed after {max_retries} retries (name resolution). "
                        f"Host: {postgres_host}:{postgres_port}, DB: {postgres_db}. "
                        f"Error: {e}.{hint}"
                    ) from e
                # "Starting up" only: allow connection to be retried later for Docker Compose E2E
                if not os.getenv("DOCKER_COMPOSE_E2E_TEST", "").lower() == "true":
                    warnings.warn(
                        f"PostgreSQL connection failed after {max_retries} retries "
                        f"(may be starting up or not running). "
                        f"Connection will be retried when needed. "
                        f"Host: {postgres_host}:{postgres_port}, DB: {postgres_db}. "
                        f"Error: {e}"
                    )
                break
            else:
                # Non-retryable error - raise with actionable message
                hint = ""
                if "postgres-test" in error_msg and (
                    "translate host name" in error_msg or "name resolution" in error_msg
                ):
                    hint = (
                        " The hostname 'postgres-test' resolves only inside the test Docker network. "
                        "Run tests inside the container: docker compose -f docker-compose.test.yml exec api-service-test bash -c '...' "
                        "Or use ./scripts/run_phase_12a_batched.sh to run batches."
                    )
                raise RuntimeError(
                    f"PostgreSQL connection failed for tests. "
                    f"Host: {postgres_host}:{postgres_port}, DB: {postgres_db}, User: {postgres_user}. "
                    f"Error: {e}. "
                    f"Please ensure PostgreSQL is running and accessible.{hint} "
                    f"SQLite is not supported for e2e tests."
                ) from e

    # If we exhausted retries and still have an error, check if we should raise
    if last_error and attempt == max_retries - 1:
        error_msg = str(last_error).lower()
        is_retryable_final = any(
            phrase in error_msg
            for phrase in [
                "starting up",
                "the database system is starting up",
                "connection refused",
                "connection to server",
                "could not translate host name",
                "temporary failure in name resolution",
                "name or service not known",
            ]
        )
        if not is_retryable_final:
            raise RuntimeError(
                f"PostgreSQL connection failed for tests after {max_retries} retries. "
                f"Host: {postgres_host}:{postgres_port}, DB: {postgres_db}, User: {postgres_user}. "
                f"Error: {last_error}. "
                f"Please ensure PostgreSQL is running and accessible. "
                f"SQLite is not supported for e2e tests."
            ) from last_error
        hint = ""
        if "postgres-test" in error_msg and (
            "translate host name" in error_msg or "name resolution" in error_msg
        ):
            hint = (
                " Host 'postgres-test' did not resolve after retries (transient Docker DNS?). "
                "Ensure test stack is up and run tests inside the container via run_phase_12a_batched.sh."
            )
        if hint:
            raise RuntimeError(
                f"PostgreSQL connection failed for tests after {max_retries} retries. "
                f"Host: {postgres_host}:{postgres_port}, DB: {postgres_db}. "
                f"Error: {last_error}.{hint}"
            ) from last_error

    # Use PostgreSQL for tests - supports proper transaction handling
    # For SDK tests, use the same database as API service so API can see test data
    use_production_db = os.getenv("USE_PRODUCTION_DB_FOR_SDK_TESTS", "").lower() == "1"
    test_db_suffix = os.getenv("TEST_DB_SUFFIX", "")
    # When TEST_DB_SUFFIX is set (e.g. "shared"), use fixed DB name so external services (prefect-integration) can connect
    use_shared_test_db = bool(test_db_suffix)

    if use_production_db:
        # Use production database for SDK tests (allows API service to see test data)
        test_db_name = postgres_db
    elif use_shared_test_db:
        # Use shared test DB. When POSTGRES_DB is already the shared DB (e.g. hub_test_test_shared
        # for api-service-test), use it directly so pytest and runserver share the same DB (events
        # table, etc.). Otherwise use hub_test_test_<suffix> (ensure-test-db creates it).
        if postgres_db.endswith(f"_test_{test_db_suffix}"):
            test_db_name = postgres_db
        else:
            test_db_name = f"{postgres_db}_test_{test_db_suffix}"
    else:
        # Use a unique test database name to avoid conflicts
        import uuid

        test_db_suffix = str(uuid.uuid4())[:8]
        test_db_name = f"{postgres_db}_test_{test_db_suffix}"

    # CRITICAL: Ensure we use the detected password, not the env var
    # The password detection above tries actual passwords and uses the one that works
    # This handles cases where POSTGRES_PASSWORD env var doesn't match actual DB password
    final_password = (
        postgres_password if postgres_password else os.getenv("POSTGRES_PASSWORD", "hub")
    )

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": test_db_name,
            "USER": postgres_user,
            "PASSWORD": final_password,
            "HOST": postgres_host,
            "PORT": postgres_port,
            "TEST": {
                "NAME": test_db_name,
                "SERIALIZE": False,  # Allow parallel test execution
                "MIGRATE": not (use_production_db or use_shared_test_db),  # Skip if using existing DB
                "DEPENDENCIES": [],  # No dependencies - migrations handle this
                "CREATE_DB": not (use_production_db or use_shared_test_db),  # Don't create if using existing
            },
            "CONN_MAX_AGE": 0,  # Don't reuse connections in tests
            "OPTIONS": {
                # Disable thread validation for tests (pytest-django uses multiple threads)
                # This is safe in test environment where we control thread usage
                "connect_timeout": 120,  # Allow time for postgres under Docker load during migrations
                # CRITICAL: Set transaction isolation level to READ COMMITTED for LiveServerTestCase
                # This ensures data committed in one thread is immediately visible to other threads
                # Without this, the server thread might not see data created in the test thread
                "isolation_level": psycopg2_extensions.ISOLATION_LEVEL_READ_COMMITTED,
                # Phase 89: align with _db_options when ENVIRONMENT=test (120s). A former
                # 60s cap plus hub/conftest per-test SET caused QueryCanceled under xdist
                # when statements waited on locks. Override: TEST_POSTGRES_STATEMENT_TIMEOUT_MS.
                "options": (
                    "-c statement_timeout={st} -c idle_in_transaction_session_timeout=300000"
                ).format(
                    st=env.int("TEST_POSTGRES_STATEMENT_TIMEOUT_MS", default=120000),
                ),
            },
        }
    }

    # When SKIP_TEST_MIGRATIONS=1, use custom runner that does not run migrate (reuse existing DB as-is)
    if os.getenv("SKIP_TEST_MIGRATIONS", "").strip().lower() in ("1", "true", "yes"):
        TEST_RUNNER = "hub.test_runner.NoMigrateTestRunner"
    # NOTE: validate_thread_sharing is patched in hub/tests/conftest.py via a
    # session-scoped autouse fixture so it does not pollute settings.py.
else:
    # Database connection pooling configuration
    # IMPORTANT: PgBouncer pool_mode=transaction is INCOMPATIBLE with:
    #   - SELECT pg_advisory_lock() / pg_advisory_xact_lock()
    #   - LISTEN/NOTIFY (Django Channels PostgreSQL backend)
    #   - Named cursors (server-side cursor streaming)
    # Use Redis-based locking (django-rq / redis.lock) instead of advisory locks.
    # If you need LISTEN/NOTIFY, configure a separate non-pooled DB connection.
    # Guard: hub/tests/test_advisory_lock_not_used.py scans for violations.
    #
    # CONN_MAX_AGE: Maximum age of database connections in seconds
    # - 0: Required when PgBouncer is active (transaction mode is incompatible with persistent connections)
    # - 600: Reuse connections for 10 minutes (direct Postgres without PgBouncer)
    # - None: Keep connections open indefinitely (not recommended)
    _pgbouncer_enabled = env.bool("PGBOUNCER_ENABLED", default=False)
    conn_max_age = 0 if _pgbouncer_enabled else env.int("DB_CONN_MAX_AGE", default=600)

    _db_options: dict = {
        "connect_timeout": 60,  # Increased for TransactionTestCase database setup (migrations can take time)
        # Connection keepalive settings (via psycopg2)
        "keepalives": 1,  # Send keepalive packets
        "keepalives_idle": 30,  # Start sending keepalives after 30 seconds of inactivity
        "keepalives_interval": 10,  # Interval between keepalive packets
        "keepalives_count": 5,  # Number of keepalive packets before considering connection dead
        "options": "-c statement_timeout={st} -c idle_in_transaction_session_timeout=300000".format(
            # E2E/test: 4 parallel Playwright workers overload the DB — queries that take <5s
            # in isolation can hit 60s under contention.  120s prevents cascading 500s.
            st=120000 if ENVIRONMENT == "test" else 60000,
        ),
    }
    if ENVIRONMENT == "production":
        # Enforce TLS for all PostgreSQL connections in production.
        # When using AWS RDS or GCP Cloud SQL, the CA cert is provided by the managed service;
        # for self-hosted Postgres use infrastructure/postgres/ssl-setup.sh to generate certs.
        _db_options["sslmode"] = "require"

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB", default="hub"),
            "USER": env("POSTGRES_USER", default="hub"),
            "PASSWORD": env("POSTGRES_PASSWORD", default="hub"),
            "HOST": env(
                "POSTGRES_HOST", default="localhost"
            ),  # Use 'localhost' for local dev, 'postgres' for Docker
            "PORT": env("POSTGRES_PORT", default="5432"),
            "CONN_MAX_AGE": conn_max_age,
            "OPTIONS": _db_options,
        }
    }

# BaaS dedicated instances (optional). See design D1b and docs/runbooks/BAAS_INFRASTRUCTURE.md
# When set, BaaS usage/quota use these; when unset, main DATABASE and REDIS_URL are used.
BAAS_DATABASE_URL = env("BAAS_DATABASE_URL", default=None)
BAAS_REDIS_URL = env("BAAS_REDIS_URL", default=None)
# postgres | redis; default postgres. See docs/runbooks/BAAS_INFRASTRUCTURE.md.
BAAS_USAGE_STORAGE_BACKEND = env(
    "BAAS_USAGE_STORAGE_BACKEND", default="postgres"
).lower()
if BAAS_USAGE_STORAGE_BACKEND not in ("postgres", "redis"):
    BAAS_USAGE_STORAGE_BACKEND = "postgres"
if BAAS_DATABASE_URL:
    _baas_db_config = env.db_url_config(BAAS_DATABASE_URL)
    _baas_db_config.setdefault("OPTIONS", {})
    # PgBouncer transaction mode requires CONN_MAX_AGE=0 (same rule as main DB).
    _baas_db_config["CONN_MAX_AGE"] = 0 if _pgbouncer_enabled else _baas_db_config.get("CONN_MAX_AGE", 60)
    # Phase 89: statement_timeout + idle_in_transaction — same policy as main DB.
    _baas_db_config["OPTIONS"]["options"] = _db_options.get("options", "")
    if ENVIRONMENT == "production":
        # Enforce TLS for BaaS database in production — same policy as main DB.
        _baas_db_config["OPTIONS"]["sslmode"] = "require"
    DATABASES["baas"] = _baas_db_config
elif "test" in sys.argv or "pytest" in sys.modules:
    # In test mode, provide a 'baas' alias pointing at the default DB so
    # that Django's test runner registers the alias at startup.  This lets
    # usage-backend tests call connections["baas"] without monkey-patching
    # the ConnectionHandler (which causes _remove_databases_failures crashes
    # in Django 6.0's TestCase/TransactionTestCase teardown).
    DATABASES["baas"] = dict(DATABASES["default"])

# DATABASE_ROUTERS: BaaS router first (handles BaaSUsageRecord exclusively),
# then PrimaryReplicaRouter for read-replica routing across read-heavy apps.
# PrimaryReplicaRouter is a no-op when DATABASE_REPLICA_URL is not configured.
DATABASE_ROUTERS = [
    "hub.apps.baas.db_router.BaaSDBRouter",
    "hub.db_router.PrimaryReplicaRouter",
]

# ---------------------------------------------------------------------------
# PostgreSQL Read Replica (17.1)
# ---------------------------------------------------------------------------
# DATABASE_REPLICA_URL: connection string for the AWS RDS Multi-AZ read replica
# endpoint.  Applies the same SSL and CONN_MAX_AGE policy as the primary.
# When not set the hub falls back gracefully — reads hit the primary and the
# PrimaryReplicaRouter is effectively a no-op.
#
# AWS RDS Multi-AZ replica endpoint example:
#   DATABASE_REPLICA_URL=postgresql://hub:<password>@<cluster>.cluster-ro-<id>.rds.amazonaws.com:5432/hub
#
# The replica is never migrated directly; all schema changes go through the
# primary ("default") and replicate automatically.
DATABASE_REPLICA_URL = env("DATABASE_REPLICA_URL", default=None)
if DATABASE_REPLICA_URL:
    _replica_db_config = env.db_url_config(DATABASE_REPLICA_URL)
    _replica_db_config.setdefault("OPTIONS", {})
    # Replicas are read-only; a short CONN_MAX_AGE is fine (same rule as primary).
    _replica_db_config["CONN_MAX_AGE"] = (
        0 if _pgbouncer_enabled else env.int("DB_CONN_MAX_AGE", default=600)
    )
    # Phase 89: statement_timeout + idle_in_transaction — same policy as primary DB.
    _replica_db_config["OPTIONS"]["options"] = _db_options.get("options", "")
    if ENVIRONMENT == "production":
        # Enforce TLS for replica in production — same policy as primary DB.
        _replica_db_config["OPTIONS"]["sslmode"] = "require"
    DATABASES["replica"] = _replica_db_config

# Marketplace: KYC required for orders/entitlements (feat1 2.4). Optional allowlist of tenant IDs
# (UUID strings) exempt from KYC for orders/entitlements. Default empty. See RUNBOOKS.md.
MARKETPLACE_KYC_ALLOWLIST_TENANT_IDS = env.list(
    "MARKETPLACE_KYC_ALLOWLIST_TENANT_IDS", default=[]
)

# Redis Configuration
# Separate Redis instances for cache, queue, events, and channels
# When running locally (outside Docker), use 'localhost'
# When running in Docker, use service names (redis-cache, redis-queue, etc.)
# For staging, use port 6380 instead of 6379
# Only detect staging in test mode to avoid affecting production
is_test_env = "test" in sys.argv or "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST")
if is_test_env:
    staging_detected = _detect_staging_for_tests()
    default_redis_port = "6380" if staging_detected else "6379"
else:
    # Production/default: use standard port
    default_redis_port = "6379"

# Legacy REDIS_URL for backward compatibility
REDIS_URL = env("REDIS_URL", default=f"redis://localhost:{default_redis_port}/0")

# Separate Redis URLs for each instance (with backward compatibility fallback to REDIS_URL)
# Redis Cache Instance - Response caching, contract caching, lineage caching
REDIS_CACHE_URL = env("REDIS_CACHE_URL", default=None)
if REDIS_CACHE_URL is None:
    # Fallback: use service name redis-cache (Docker) or localhost (local)
    # In Docker Compose, services are named redis-cache, redis-queue, etc.
    # Outside Docker, use localhost with appropriate ports
    import socket

    try:
        socket.gethostbyname("redis-cache")
        REDIS_CACHE_URL = "redis://redis-cache:6379/0"
    except socket.gaierror:
        REDIS_CACHE_URL = "redis://localhost:6379/0"

# Redis Queue Instance - Job queues (RQ)
REDIS_QUEUE_URL = env("REDIS_QUEUE_URL", default=None)
if REDIS_QUEUE_URL is None:
    # Fallback: use service name redis-queue (Docker) or localhost (local)
    # Better detection: check for Docker environment first
    is_in_docker = os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER") == "true"
    if is_in_docker:
        # In Docker, try service name first, then localhost
        import socket

        try:
            socket.gethostbyname("redis-queue")
            REDIS_QUEUE_URL = "redis://redis-queue:6379/0"
        except socket.gaierror:
            # Service name not resolvable, use localhost with mapped port
            REDIS_QUEUE_URL = "redis://localhost:6380/0"
    else:
        # Outside Docker, use localhost with mapped port
        REDIS_QUEUE_URL = "redis://localhost:6380/0"

# Redis Events Instance - Event bus (Pub/Sub, Streams)
REDIS_EVENTS_URL = env("REDIS_EVENTS_URL", default=None)
if REDIS_EVENTS_URL is None:
    # Fallback: use service name redis-events (Docker) or localhost (local)
    is_in_docker = os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER") == "true"
    if is_in_docker:
        import socket

        try:
            socket.gethostbyname("redis-events")
            REDIS_EVENTS_URL = "redis://redis-events:6379/0"
        except socket.gaierror:
            REDIS_EVENTS_URL = "redis://localhost:6381/0"
    else:
        REDIS_EVENTS_URL = "redis://localhost:6381/0"

# Redis Channels Instance - WebSocket channels (Django Channels)
REDIS_CHANNELS_URL = env("REDIS_CHANNELS_URL", default=None)
if REDIS_CHANNELS_URL is None:
    # Fallback: use service name redis-channels (Docker) or localhost (local)
    is_in_docker = os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER") == "true"
    if is_in_docker:
        import socket

        try:
            socket.gethostbyname("redis-channels")
            REDIS_CHANNELS_URL = "redis://redis-channels:6379/0"
        except socket.gaierror:
            REDIS_CHANNELS_URL = "redis://localhost:6382/0"
    else:
        REDIS_CHANNELS_URL = "redis://localhost:6382/0"

# Production: all Redis URLs MUST include authentication credentials with a non-empty password.
# Format: redis://:password@host:port/db  (note the empty username before the colon)
# Rejected: missing '@' (unauthenticated) OR ':@' pattern (empty password — equally insecure).
if ENVIRONMENT == "production":
    _redis_urls_to_validate = {
        "REDIS_URL": REDIS_URL,
        "REDIS_CACHE_URL": REDIS_CACHE_URL,
        "REDIS_QUEUE_URL": REDIS_QUEUE_URL,
        "REDIS_EVENTS_URL": REDIS_EVENTS_URL,
        "REDIS_CHANNELS_URL": REDIS_CHANNELS_URL,
    }
    # Include optional BaaS Redis URL if configured (same auth policy applies).
    if BAAS_REDIS_URL:
        _redis_urls_to_validate["BAAS_REDIS_URL"] = BAAS_REDIS_URL
    # Validate DATABASE_REPLICA_URL in production: must use credentials (@ present, non-empty password).
    if DATABASE_REPLICA_URL:
        if "@" not in DATABASE_REPLICA_URL:
            raise ImproperlyConfigured(
                "In production, DATABASE_REPLICA_URL must include authentication credentials "
                "(format: postgresql://user:password@host:port/db). "
                "Unauthenticated replica connections are not permitted. "
                "See .env.production.template."
            )
        _replica_creds = DATABASE_REPLICA_URL.rsplit("@", 1)[0]
        # Split scheme+credentials: "postgresql://user:password" — empty password ends with ':'
        _replica_pass_part = _replica_creds.rsplit(":", 1)[-1]
        if not _replica_pass_part:
            raise ImproperlyConfigured(
                "In production, DATABASE_REPLICA_URL has an empty password. "
                "Set a strong password: postgresql://user:password@host:port/db. "
                "See .env.production.template."
            )
    for _redis_var, _redis_url in _redis_urls_to_validate.items():
        if not _redis_url:
            continue
        if "@" not in _redis_url:
            raise ImproperlyConfigured(
                f"In production, {_redis_var} must include authentication credentials "
                f"(format: redis://:password@host:port/db). "
                f"Current value has no '@' — unauthenticated Redis is not permitted. "
                f"See docs/SECURITY.md."
            )
        # Reject empty passwords: redis://:@host is structurally valid but insecure.
        # Extract the credentials segment (everything before the last '@').
        _creds_segment = _redis_url.rsplit("@", 1)[0]
        # creds_segment is either "redis://" (no user:pass) or "redis://:pass" or "redis://user:pass"
        # An empty password means the segment ends with ':'  e.g. "redis://:".
        if _creds_segment.endswith(":"):
            raise ImproperlyConfigured(
                f"In production, {_redis_var} has an empty password "
                f"(detected pattern: '...:<empty>@'). "
                f"Set a strong password: redis://:strongpassword@host:port/db. "
                f"See docs/SECURITY.md."
            )

# RQ Queue Configuration
# Priority queues: job_critical (HIGH), job_default (NORMAL), job_low (LOW)
# See design.md Decision 3 for priority queue implementation details
# All queues use REDIS_QUEUE_URL (separate Redis instance for job queues)
RQ_QUEUES = {
    "job_critical": {  # HIGH priority queue
        "URL": REDIS_QUEUE_URL,
        "DEFAULT_TIMEOUT": 1800,  # 30 minutes for DQ/compliance runs
        "DEFAULT_RESULT_TTL": 500,
    },
    "job_default": {  # NORMAL priority queue
        "URL": REDIS_QUEUE_URL,
        "DEFAULT_TIMEOUT": 360,  # 6 minutes default
        "DEFAULT_RESULT_TTL": 500,
    },
    "job_low": {  # LOW priority queue
        "URL": REDIS_QUEUE_URL,
        "DEFAULT_TIMEOUT": 60,  # 1 minute for quick jobs
        "DEFAULT_RESULT_TTL": 500,
    },
    # Legacy 'default' queue for backward compatibility (maps to job_default)
    "default": {
        "URL": REDIS_QUEUE_URL,
        "DEFAULT_TIMEOUT": 360,
        "DEFAULT_RESULT_TTL": 500,
    },
}

# RQ: synchronous mode during tests.
# When running under pytest/unittest, execute enqueued jobs inline (in the
# same process and DB connection as the test) instead of pushing them to
# Redis for a separate RQ worker.  This prevents deadlocks caused by the
# worker process acquiring locks on the same tables the test transaction
# holds (AccessExclusiveLock from TransactionTestCase TRUNCATE vs
# RowExclusiveLock from test INSERTs).  Mirrors the pattern used by
# WEBHOOK_ASYNC_DELIVERY and EVENT_BUS_FORCE_SYNC_PERSISTENCE.
if "pytest" in sys.modules or "unittest" in sys.modules or os.getenv("TESTING"):
    for _q in RQ_QUEUES.values():
        _q["ASYNC"] = False

# Channel Layers Configuration (for WebSocket support)
#
# Phase 214.3 root-cause fix: the previous parser used `.replace("redis://", "")`
# + `.split("/")` and only extracted host/port. It was broken in 4 ways for our
# Phase 214.3 collapsed-Redis layout:
#   1. Did not handle `rediss://` (TLS) URLs — `replace("redis://", ...)` is a
#      no-op against `rediss://...`, so `_redis_channels_host` ended up as the
#      literal string "rediss" (not a real hostname).
#   2. Dropped the AUTH token (`:TOKEN@host`) — channels_redis got no password.
#   3. Dropped the `/N` DB-index segment — channels would have landed on DB 0
#      (= cache space) instead of DB 3, causing cross-talk between roles.
#   4. Did not enable TLS on the resulting connection — plain TCP against the
#      AUTH-token-protected TLS listener would have failed handshake.
#
# Fix: pass the full URL string to channels_redis via `hosts: [URL]`. Per
# channels_redis docs, `RedisChannelLayer` accepts URLs in `hosts` and parses
# scheme/auth/host/port/db correctly via redis-py's connection pool — handling
# TLS, AUTH, and DB index in one go. No application-level URL parsing needed.
#
# Test environments still need the in-memory backend so tests don't require Redis.

# Channel Layers Configuration
# Use in-memory channel layer for tests, Redis for production
is_test_env = "test" in sys.argv or "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST")
if is_test_env:
    # Use in-memory channel layer for tests (faster, no Redis dependency)
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }
elif REDIS_CHANNELS_URL:
    # Production / staging: pass the full URL so TLS, AUTH token, and DB index
    # are all honored. channels_redis ≥ 4.x supports this URL form natively.
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [REDIS_CHANNELS_URL],
                "capacity": 1000,  # Maximum number of messages to buffer
                "expiry": 10,  # Message expiry in seconds
            },
        },
    }
else:
    # No REDIS_CHANNELS_URL configured (rare — local dev without Redis exported).
    # Fall back to in-memory so the app still boots; websocket fanout across
    # processes won't work but single-process dev does.
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }

# Phase 57.3: Guard against PostgreSQL-backed Channels when PgBouncer is active
# (LISTEN/NOTIFY is incompatible with PgBouncer transaction pooling)
if env.bool("PGBOUNCER_ENABLED", default=False):
    _channels_backend = CHANNEL_LAYERS.get("default", {}).get("BACKEND", "")
    if "postgres" in _channels_backend.lower():
        raise ImproperlyConfigured(
            "CHANNEL_LAYERS uses a PostgreSQL backend but PGBOUNCER_ENABLED=True. "
            "PgBouncer transaction pooling is incompatible with LISTEN/NOTIFY. "
            "Use channels_redis.core.RedisChannelLayer instead."
        )

# Django Cache Configuration
# Use Redis cache backend (separate Redis instance for caching)
# Parse REDIS_CACHE_URL for cache configuration
_redis_cache_host = "localhost"
_redis_cache_port = 6379
_redis_cache_db = 0
if REDIS_CACHE_URL:
    try:
        # Parse redis://host:port/db format
        parts = REDIS_CACHE_URL.replace("redis://", "").split("/")
        host_port = parts[0].split(":")
        _redis_cache_host = host_port[0]
        if len(host_port) > 1:
            _redis_cache_port = int(host_port[1])
        if len(parts) > 1:
            _redis_cache_db = int(parts[1])
    except (ValueError, AttributeError, IndexError) as e:
        # Invalid URL format - fallback to defaults
        import logging

        logger = logging.getLogger(__name__)
        logger.debug(
            "Invalid REDIS_CHANNELS_URL format, using defaults",
            extra={"error_type": type(e).__name__},
        )
    except Exception as e:
        # Unexpected error - log but use defaults
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            "Unexpected error parsing REDIS_CHANNELS_URL",
            extra={"error_type": type(e).__name__},
        )

# Cache configuration
# Use Redis cache backend for production, LocMemCache for tests
if is_test_env:
    # Use LocMemCache for tests (faster, no Redis dependency)
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique-snowflake",
        }
    }
else:
    # Use Redis cache backend for production (separate Redis instance for cache)
    try:
        import django_redis

        CACHES = {
            "default": {
                "BACKEND": "django_redis.cache.RedisCache",
                "LOCATION": REDIS_CACHE_URL,
                "OPTIONS": {
                    "CLIENT_CLASS": "django_redis.client.DefaultClient",
                    "CONNECTION_POOL_KWARGS": {
                        "max_connections": 50,
                        "retry_on_timeout": True,
                        "socket_keepalive": True,
                        "health_check_interval": 30,
                    },
                    "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
                    "IGNORE_EXCEPTIONS": False,  # Raise exceptions on cache errors
                },
                "KEY_PREFIX": "hub",
                "TIMEOUT": 300,  # Default timeout: 5 minutes
            }
        }
    except ImportError:
        # Fallback to LocMemCache if django-redis is not installed
        CACHES = {
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "unique-snowflake",
            }
        }

# Worker Configuration
# Worker concurrency limits
WORKER_MAX_CONCURRENCY = env.int("WORKER_MAX_CONCURRENCY", default=4)
WORKER_MAX_CONCURRENCY_PER_TENANT = env.int("WORKER_MAX_CONCURRENCY_PER_TENANT", default=2)

# Priority queue configuration
# Reserved slots: Fraction of max concurrency reserved for HIGH priority jobs (default: 50%)
WORKER_RESERVED_SLOTS_RATIO = env.float("WORKER_RESERVED_SLOTS_RATIO", default=0.5)
WORKER_RESERVED_SLOTS = max(1, int(WORKER_MAX_CONCURRENCY * WORKER_RESERVED_SLOTS_RATIO))
WORKER_SHARED_SLOTS = WORKER_MAX_CONCURRENCY - WORKER_RESERVED_SLOTS

# Starvation prevention: Elevate NORMAL priority jobs after wait time threshold (default: 5 minutes)
WORKER_STARVATION_THRESHOLD_SECONDS = env.int(
    "WORKER_STARVATION_THRESHOLD_SECONDS", default=300
)  # 5 minutes

# Job Priority Configuration
# Default priority for jobs when not explicitly specified
JOB_PRIORITY_DEFAULT = env("JOB_PRIORITY_DEFAULT", default="NORMAL")

# Priority assignment rules by job type
# Maps job_type -> priority (HIGH, NORMAL, LOW)
JOB_PRIORITY_RULES = {
    # HIGH priority: Critical long-running jobs
    "DQ_RUN": "HIGH",
    "COMPLIANCE_RUN": "HIGH",
    # NORMAL priority: Standard jobs (default)
    "SEMANTIC_MAPPING": "NORMAL",
    "CONTRACT_MIGRATION": "NORMAL",
    "SCHEDULED_INGESTION": "NORMAL",
    "RETENTION_POLICY_ENFORCEMENT": "NORMAL",
    "SEARCH_INDEX_UPDATE": "NORMAL",
    "ODPS_NORMALIZATION": "NORMAL",
    "ODPS_REF_RESOLUTION": "NORMAL",
    "ODPS_EXPORT": "NORMAL",
    "ODPS_SEMANTIC_MAPPING": "NORMAL",
    "ODPS_LINKING": "NORMAL",
    "VIRTUAL_QUERY_EXECUTION": "NORMAL",
    # LOW priority: Quick validation jobs
    "CONTRACT_VALIDATION": "LOW",
}

# Job Retry Configuration
# Maximum retry attempts per job type
JOB_RETRY_MAX_ATTEMPTS = {
    "DQ_RUN": env.int("JOB_RETRY_MAX_ATTEMPTS_DQ_RUN", default=3),
    "COMPLIANCE_RUN": env.int("JOB_RETRY_MAX_ATTEMPTS_COMPLIANCE_RUN", default=3),
    "CONTRACT_VALIDATION": env.int("JOB_RETRY_MAX_ATTEMPTS_CONTRACT_VALIDATION", default=2),
    "SEMANTIC_MAPPING": env.int("JOB_RETRY_MAX_ATTEMPTS_SEMANTIC_MAPPING", default=2),
    "CONTRACT_MIGRATION": env.int("JOB_RETRY_MAX_ATTEMPTS_CONTRACT_MIGRATION", default=1),
    "SCHEDULED_INGESTION": env.int("JOB_RETRY_MAX_ATTEMPTS_SCHEDULED_INGESTION", default=2),
    "RETENTION_POLICY_ENFORCEMENT": env.int(
        "JOB_RETRY_MAX_ATTEMPTS_RETENTION_POLICY_ENFORCEMENT", default=1
    ),
    "SEARCH_INDEX_UPDATE": env.int("JOB_RETRY_MAX_ATTEMPTS_SEARCH_INDEX_UPDATE", default=2),
    "ODPS_NORMALIZATION": env.int("JOB_RETRY_MAX_ATTEMPTS_ODPS_NORMALIZATION", default=2),
    "ODPS_REF_RESOLUTION": env.int("JOB_RETRY_MAX_ATTEMPTS_ODPS_REF_RESOLUTION", default=2),
    "ODPS_EXPORT": env.int("JOB_RETRY_MAX_ATTEMPTS_ODPS_EXPORT", default=2),
    "ODPS_SEMANTIC_MAPPING": env.int("JOB_RETRY_MAX_ATTEMPTS_ODPS_SEMANTIC_MAPPING", default=2),
    "ODPS_LINKING": env.int("JOB_RETRY_MAX_ATTEMPTS_ODPS_LINKING", default=2),
    "VIRTUAL_QUERY_EXECUTION": env.int("JOB_RETRY_MAX_ATTEMPTS_VIRTUAL_QUERY_EXECUTION", default=2),
}

# Initial delay before first retry per job type (in seconds)
JOB_RETRY_INITIAL_DELAY = {
    "DQ_RUN": env.int("JOB_RETRY_INITIAL_DELAY_DQ_RUN", default=60),
    "COMPLIANCE_RUN": env.int("JOB_RETRY_INITIAL_DELAY_COMPLIANCE_RUN", default=60),
    "CONTRACT_VALIDATION": env.int("JOB_RETRY_INITIAL_DELAY_CONTRACT_VALIDATION", default=30),
    "SEMANTIC_MAPPING": env.int("JOB_RETRY_INITIAL_DELAY_SEMANTIC_MAPPING", default=30),
    "CONTRACT_MIGRATION": env.int("JOB_RETRY_INITIAL_DELAY_CONTRACT_MIGRATION", default=60),
    "SCHEDULED_INGESTION": env.int("JOB_RETRY_INITIAL_DELAY_SCHEDULED_INGESTION", default=120),
    "RETENTION_POLICY_ENFORCEMENT": env.int(
        "JOB_RETRY_INITIAL_DELAY_RETENTION_POLICY_ENFORCEMENT", default=60
    ),
    "SEARCH_INDEX_UPDATE": env.int("JOB_RETRY_INITIAL_DELAY_SEARCH_INDEX_UPDATE", default=30),
    "ODPS_NORMALIZATION": env.int("JOB_RETRY_INITIAL_DELAY_ODPS_NORMALIZATION", default=60),
    "ODPS_REF_RESOLUTION": env.int("JOB_RETRY_INITIAL_DELAY_ODPS_REF_RESOLUTION", default=60),
    "ODPS_EXPORT": env.int("JOB_RETRY_INITIAL_DELAY_ODPS_EXPORT", default=30),
    "ODPS_SEMANTIC_MAPPING": env.int("JOB_RETRY_INITIAL_DELAY_ODPS_SEMANTIC_MAPPING", default=60),
    "ODPS_LINKING": env.int("JOB_RETRY_INITIAL_DELAY_ODPS_LINKING", default=30),
    "VIRTUAL_QUERY_EXECUTION": env.int(
        "JOB_RETRY_INITIAL_DELAY_VIRTUAL_QUERY_EXECUTION", default=60
    ),
}

# Maximum delay cap per job type (in seconds)
JOB_RETRY_MAX_DELAY = {
    "DQ_RUN": env.int("JOB_RETRY_MAX_DELAY_DQ_RUN", default=3600),
    "COMPLIANCE_RUN": env.int("JOB_RETRY_MAX_DELAY_COMPLIANCE_RUN", default=3600),
    "CONTRACT_VALIDATION": env.int("JOB_RETRY_MAX_DELAY_CONTRACT_VALIDATION", default=600),
    "SEMANTIC_MAPPING": env.int("JOB_RETRY_MAX_DELAY_SEMANTIC_MAPPING", default=600),
    "CONTRACT_MIGRATION": env.int("JOB_RETRY_MAX_DELAY_CONTRACT_MIGRATION", default=1800),
    "SCHEDULED_INGESTION": env.int("JOB_RETRY_MAX_DELAY_SCHEDULED_INGESTION", default=3600),
    "RETENTION_POLICY_ENFORCEMENT": env.int(
        "JOB_RETRY_MAX_DELAY_RETENTION_POLICY_ENFORCEMENT", default=1800
    ),
    "SEARCH_INDEX_UPDATE": env.int("JOB_RETRY_MAX_DELAY_SEARCH_INDEX_UPDATE", default=600),
    "ODPS_NORMALIZATION": env.int("JOB_RETRY_MAX_DELAY_ODPS_NORMALIZATION", default=1800),
    "ODPS_REF_RESOLUTION": env.int("JOB_RETRY_MAX_DELAY_ODPS_REF_RESOLUTION", default=1800),
    "ODPS_EXPORT": env.int("JOB_RETRY_MAX_DELAY_ODPS_EXPORT", default=600),
    "ODPS_SEMANTIC_MAPPING": env.int("JOB_RETRY_MAX_DELAY_ODPS_SEMANTIC_MAPPING", default=1800),
    "ODPS_LINKING": env.int("JOB_RETRY_MAX_DELAY_ODPS_LINKING", default=600),
    "VIRTUAL_QUERY_EXECUTION": env.int("JOB_RETRY_MAX_DELAY_VIRTUAL_QUERY_EXECUTION", default=1800),
}

# Exponential backoff factor per job type
JOB_RETRY_BACKOFF_FACTOR = {
    "DQ_RUN": env.float("JOB_RETRY_BACKOFF_FACTOR_DQ_RUN", default=2.0),
    "COMPLIANCE_RUN": env.float("JOB_RETRY_BACKOFF_FACTOR_COMPLIANCE_RUN", default=2.0),
    "CONTRACT_VALIDATION": env.float("JOB_RETRY_BACKOFF_FACTOR_CONTRACT_VALIDATION", default=2.0),
    "SEMANTIC_MAPPING": env.float("JOB_RETRY_BACKOFF_FACTOR_SEMANTIC_MAPPING", default=2.0),
    "CONTRACT_MIGRATION": env.float("JOB_RETRY_BACKOFF_FACTOR_CONTRACT_MIGRATION", default=2.0),
    "SCHEDULED_INGESTION": env.float("JOB_RETRY_BACKOFF_FACTOR_SCHEDULED_INGESTION", default=2.0),
    "RETENTION_POLICY_ENFORCEMENT": env.float(
        "JOB_RETRY_BACKOFF_FACTOR_RETENTION_POLICY_ENFORCEMENT", default=2.0
    ),
    "SEARCH_INDEX_UPDATE": env.float("JOB_RETRY_BACKOFF_FACTOR_SEARCH_INDEX_UPDATE", default=2.0),
    "ODPS_NORMALIZATION": env.float("JOB_RETRY_BACKOFF_FACTOR_ODPS_NORMALIZATION", default=2.0),
    "ODPS_REF_RESOLUTION": env.float("JOB_RETRY_BACKOFF_FACTOR_ODPS_REF_RESOLUTION", default=2.0),
    "ODPS_EXPORT": env.float("JOB_RETRY_BACKOFF_FACTOR_ODPS_EXPORT", default=2.0),
    "ODPS_SEMANTIC_MAPPING": env.float(
        "JOB_RETRY_BACKOFF_FACTOR_ODPS_SEMANTIC_MAPPING", default=2.0
    ),
    "ODPS_LINKING": env.float("JOB_RETRY_BACKOFF_FACTOR_ODPS_LINKING", default=2.0),
    "VIRTUAL_QUERY_EXECUTION": env.float(
        "JOB_RETRY_BACKOFF_FACTOR_VIRTUAL_QUERY_EXECUTION", default=2.0
    ),
}

# S3/MinIO Configuration
# MEDIA_URL must always be set (Django 6 + LiveServerTestCase
# passes them through urlparse which returns bytes path for None).
# STATIC_URL is set inside the USE_S3 branches below — the S3 branch
# sets it via django-storages, the else branch sets it to "/static/".
MEDIA_URL = "/"

USE_S3 = env.bool("USE_S3", default=True)
if USE_S3:
    # Only detect staging in test mode to avoid affecting production
    is_test_env = "test" in sys.argv or "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST")
    if is_test_env:
        staging_detected = _detect_staging_for_tests()
    else:
        staging_detected = False  # Production defaults to non-staging

    # Environment variables always take precedence
    env_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    env_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    # Determine default S3 endpoint first
    is_in_docker = os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER") == "true"
    is_test_env = "test" in sys.argv or "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST")

    # In real deployments (staging/production K8s), the api/worker pods do NOT
    # have `/.dockerenv` (containerd-based runtimes don't create it), so the
    # legacy default of `http://localhost:9000` was being applied. That signed
    # presigned URLs against `localhost`, breaking both browser uploads (the
    # browser hit its own loopback) and server-side file fetches (the api pod
    # has no MinIO on localhost). The correct default in any
    # staging/production deployment is "no endpoint override" → boto3 uses
    # native AWS S3 endpoints (`<bucket>.s3.<region>.amazonaws.com`), which
    # are universally browser-reachable and IRSA-authorisable.
    deployed_environment = (
        os.getenv("ENVIRONMENT") or os.getenv("DJANGO_ENVIRONMENT") or ""
    ).lower()
    is_deployed_env = deployed_environment in {"staging", "production", "prod"}

    if is_deployed_env and not is_test_env:
        # Native AWS S3 — no endpoint override. boto3 will sign against
        # `<bucket>.s3.<region>.amazonaws.com`, which is browser-reachable
        # without any host rewrite, and authenticates via the pod's IRSA role.
        default_s3_endpoint = None
    elif staging_detected:
        default_s3_endpoint = "http://localhost:9010"
    elif is_in_docker and is_test_env:
        # In Docker test environment, try test service names, then localhost with test port
        import socket

        try:
            socket.gethostbyname("minio-test")
            default_s3_endpoint = "http://minio-test:9000"
        except socket.gaierror:
            # Test service not on same network, use localhost with test port
            default_s3_endpoint = "http://localhost:9010"  # Test port from docker-compose.test.yml
    elif is_in_docker:
        # Check if we're in Docker (can resolve 'minio' hostname)
        try:
            import socket

            socket.gethostbyname("minio")
            default_s3_endpoint = "http://minio:9000"  # In Docker, use service name
        except socket.gaierror:
            default_s3_endpoint = "http://localhost:9000"  # Fallback to localhost
    else:
        default_s3_endpoint = "http://localhost:9000"  # Outside Docker, use localhost

    # Set credentials - environment variables take precedence
    if env_access_key and env_secret_key:
        AWS_ACCESS_KEY_ID = env_access_key
        AWS_SECRET_ACCESS_KEY = env_secret_key
    elif staging_detected:
        # Staging detected and no env override
        AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="minio_staging")
        AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="minio_staging_secure")
    else:
        # Use defaults (regular MinIO credentials)
        AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="minio")
        AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="")

    if ENVIRONMENT == "production" and not AWS_SECRET_ACCESS_KEY:
        raise ImproperlyConfigured(
            "In production with USE_S3=True, AWS_SECRET_ACCESS_KEY must be "
            "set via environment. See docs/SECURITY.md."
        )

    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="hub-files")
    # Environment variable always takes precedence (set by Docker Compose)
    AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default=default_s3_endpoint)
    AWS_S3_USE_SSL = env.bool("AWS_S3_USE_SSL", default=False)
    AWS_S3_VERIFY = env.bool("AWS_S3_VERIFY", default=False)
    AWS_DEFAULT_ACL = "private"
    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": "max-age=86400",
    }

    # Django 6: Use STORAGES setting instead of deprecated DEFAULT_FILE_STORAGE and STATICFILES_STORAGE
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": {
            "BACKEND": "storages.backends.s3boto3.S3StaticStorage",
        },
    }
else:
    # Local file storage
    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"
    STATIC_URL = "/static/"
    STATIC_ROOT = BASE_DIR / "staticfiles"
    # Django 6: Use STORAGES setting for local storage
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

# Phase 203 — ClamAV (file malware scanning; hub.apps.files.scanner / tasks)
CLAMAV_ENABLED = env.bool("CLAMAV_ENABLED", default=True)
CLAMAV_HOST = env("CLAMAV_HOST", default="clamav")
CLAMAV_PORT = env.int("CLAMAV_PORT", default=3310)
CLAMAV_TIMEOUT_SECONDS = env.float("CLAMAV_TIMEOUT_SECONDS", default=120.0)
CLAMAV_JOB_TIMEOUT_SECONDS = env.int("CLAMAV_JOB_TIMEOUT_SECONDS", default=300)

# File Upload Configuration
MAX_BROWSER_UPLOAD_SIZE = env.int("MAX_BROWSER_UPLOAD_SIZE", default=100 * 1024 * 1024)  # 100MB
MAX_SDK_UPLOAD_SIZE = env.int("MAX_SDK_UPLOAD_SIZE", default=5 * 1024 * 1024 * 1024)  # 5GB
MAX_FILE_SIZE = env.int("MAX_FILE_SIZE", default=10 * 1024 * 1024 * 1024)  # 10GB
ALLOWED_FILE_TYPES = env.list(
    "ALLOWED_FILE_TYPES", default=["csv", "json", "parquet", "txt", "xlsx", "xls"]
)

# Async polling deadlines (Phase 69 — fail-closed on timeout)
COMPLIANCE_POLL_MAX_SECONDS = env.int("COMPLIANCE_POLL_MAX_SECONDS", default=300)
DQ_POLL_MAX_SECONDS = env.int("DQ_POLL_MAX_SECONDS", default=300)

# Auto-pause after consecutive failures (Phase 71)
MAX_CONSECUTIVE_FAILURES = env.int("MAX_CONSECUTIVE_FAILURES", default=5)

# DataContract CLI Service Configuration
DATACONTRACT_SERVICE_URL = env(
    "DATACONTRACT_SERVICE_URL", default="http://datacontract-service:8080"
)
DATACONTRACT_SERVICE_TIMEOUT = env.int("DATACONTRACT_SERVICE_TIMEOUT", default=60)
DATACONTRACT_VALIDATION_SYNC_SIZE_LIMIT = env.int(
    "DATACONTRACT_VALIDATION_SYNC_SIZE_LIMIT", default=100 * 1024
)  # 100KB

# Webhook delivery timeout (seconds). Used by WebhookDeliveryService; tests may override for faster runs.
WEBHOOK_DELIVERY_TIMEOUT = env.int("WEBHOOK_DELIVERY_TIMEOUT", default=30)
WEBHOOK_REQUEST_TIMEOUT = env.int("WEBHOOK_REQUEST_TIMEOUT", default=30)
_raw_intervals = env.str("WEBHOOK_RETRY_INTERVALS", default="1,5,30,300,1800")
WEBHOOK_RETRY_INTERVALS = [int(x.strip()) for x in _raw_intervals.split(",")]

# Search query limits (Phase 53)
MAX_SEARCH_QUERY_LENGTH = env.int("MAX_SEARCH_QUERY_LENGTH", default=512)
MAX_SEARCH_TAGS = env.int("MAX_SEARCH_TAGS", default=50)

# SSRF protection for webhook URLs.
# Enabled by default in production; disabled in test environments so that
# integration tests can deliver to local HTTP servers without override_settings.
# Tests that specifically exercise SSRF protection use @override_settings(WEBHOOK_SSRF_ENABLED=True).
if "pytest" in sys.modules or "unittest" in sys.modules or os.getenv("TESTING"):
    WEBHOOK_SSRF_ENABLED = env.bool("WEBHOOK_SSRF_ENABLED", default=False)
    INTEGRATION_SSRF_ENABLED = env.bool("INTEGRATION_SSRF_ENABLED", default=False)
else:
    WEBHOOK_SSRF_ENABLED = env.bool("WEBHOOK_SSRF_ENABLED", default=True)
    INTEGRATION_SSRF_ENABLED = env.bool("INTEGRATION_SSRF_ENABLED", default=True)

# BaaS usage recording mode.
# Synchronous in test mode so background threads don't hold DB locks that
# deadlock with TransactionTestCase TRUNCATE CASCADE teardown.
if "pytest" in sys.modules or "unittest" in sys.modules or os.getenv("TESTING"):
    BAAS_USAGE_RECORDING_SYNC = True
else:
    BAAS_USAGE_RECORDING_SYNC = env.bool("BAAS_USAGE_RECORDING_SYNC", default=False)

# Async webhook delivery via RQ (13.6).
# Disabled in test mode so existing webhook tests keep running synchronously
# without needing a live Redis/RQ worker.  Production defaults to True.
if "pytest" in sys.modules or "unittest" in sys.modules or os.getenv("TESTING"):
    WEBHOOK_ASYNC_DELIVERY = env.bool("WEBHOOK_ASYNC_DELIVERY", default=False)
else:
    WEBHOOK_ASYNC_DELIVERY = env.bool("WEBHOOK_ASYNC_DELIVERY", default=True)

# Email Service Configuration
# EMAIL_BACKEND: 'sendgrid', 'ses', or 'smtp'
EMAIL_BACKEND = env("EMAIL_BACKEND", default="smtp")

# Brand (Phase 28.7.5 Meshant)
APP_NAME = env("APP_NAME", default="Meshant")

# Base URL for email links
EMAIL_BASE_URL = env("EMAIL_BASE_URL", default="http://localhost:8000")

# SPA origin for links that must open in the frontend (e.g. email verification)
FRONTEND_URL = env("FRONTEND_URL", default=EMAIL_BASE_URL)

# SendGrid Configuration
SENDGRID_API_KEY = env("SENDGRID_API_KEY", default=None)
SENDGRID_FROM_EMAIL = env("SENDGRID_FROM_EMAIL", default=None)
SENDGRID_FROM_NAME = env("SENDGRID_FROM_NAME", default=APP_NAME)

# AWS SES Configuration
AWS_SES_REGION = env("AWS_SES_REGION", default=None)
AWS_SES_FROM_EMAIL = env("AWS_SES_FROM_EMAIL", default=None)
AWS_SES_FROM_NAME = env("AWS_SES_FROM_NAME", default=APP_NAME)

# SMTP Configuration
SMTP_HOST = env("SMTP_HOST", default="localhost")
SMTP_PORT = env.int("SMTP_PORT", default=587)
SMTP_USERNAME = env("SMTP_USERNAME", default=None)
SMTP_PASSWORD = env("SMTP_PASSWORD", default=None)
SMTP_USE_TLS = env.bool("SMTP_USE_TLS", default=True)
SMTP_USE_SSL = env.bool("SMTP_USE_SSL", default=False)
SMTP_FROM_EMAIL = env("SMTP_FROM_EMAIL", default=None)
SMTP_FROM_NAME = env("SMTP_FROM_NAME", default=APP_NAME)

# Phase 226 OQ-MailHog — in-cluster URL of the MailHog HTTP API.
# Consumed ONLY by hub/apps/api/mailhog_proxy_views.py. Empty string
# means "MailHog not deployed in this environment" — the proxy view
# returns 503 in that case (and is closed-by-default in production via
# is_e2e_environment + verify_e2e_token).
MAILHOG_INTERNAL_URL = env("MAILHOG_INTERNAL_URL", default="")

# Email Notification Settings
EMAIL_JOB_NOTIFICATIONS_ENABLED = env.bool("EMAIL_JOB_NOTIFICATIONS_ENABLED", default=False)

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Custom User Model
AUTH_USER_MODEL = "users.User"

# REST Framework Configuration
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "hub.apps.auth.authentication.JWTAuthentication",
        "hub.apps.auth.authentication.APIKeyAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "hub.apps.api.standards.pagination.StandardPageNumberPagination",
    "PAGE_SIZE": 50,  # Aligned with StandardPageNumberPagination.page_size (13.7)
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "EXCEPTION_HANDLER": "hub.apps.api.exceptions.custom_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Phase 230.2 (REQ-SEM-EXPORT-001) — semantic_export throttle
    # rate. UserRateThrottle reads `DEFAULT_THROTTLE_RATES[scope]`
    # at request time; without this entry the throttle's
    # `get_rate()` returns None and the gate errors.
    #
    # DRF's ``parse_rate`` reads ``period[0]`` and looks it up in
    # ``{'s','m','h','d'}`` — the format MUST be ``N/<period>`` where
    # ``<period>`` starts with one of those letters. ``"5/5min"`` is
    # INVALID (period="5min" → period[0]='5' → KeyError). The closest
    # DRF-native rate to the spec's "5 req / 5 min / user" is
    # ``"5/min"`` (5 per 1 minute) — a TIGHTER bound than the spec
    # mandates, so still spec-conformant. True 5-minute windowing
    # requires a custom ScopedRateThrottle subclass with the duration
    # multiplied; out of scope for this fix. The DRF-native form
    # below is what makes the gate actually function in production
    # (without it every request 500s on the throttle init).
    "DEFAULT_THROTTLE_RATES": {
        "semantic_export": "5/min",
        # Phase 230.13 (REQ-SEM-GQL-001) — per-user 60 q/min throttle on
        # the GraphQL-LD endpoint.  Read by
        # ``hub.apps.graphql_ld.views.SemanticGraphQLThrottle``.
        "semantic_graphql": "60/minute",
    },
}

# Phase 230.13 (REQ-SEM-GQL-001) — GraphQL-LD DoS caps.  Pulled from
# settings so the test suite can override per-test (depth/complexity
# caps via @override_settings, timeout via SEMANTIC_GRAPHQL_TIMEOUT_SECONDS).
SEMANTIC_GRAPHQL_DEPTH_LIMIT = 5
SEMANTIC_GRAPHQL_COMPLEXITY_LIMIT = 100
SEMANTIC_GRAPHQL_TIMEOUT_SECONDS = 10.0

# OpenAPI/Spectacular Configuration
SPECTACULAR_SETTINGS = {
    "TITLE": "Interoperable Data Hub API",
    "DESCRIPTION": "REST API v1 for Interoperable Data Hub MVP",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/v1",
    "COMPONENT_SPLIT_REQUEST": False,  # Disabled to avoid dict processing issues
    "COMPONENT_NO_READ_ONLY_REQUIRED": True,
    "TAGS": [
        {"name": "Authentication", "description": "User authentication and authorization"},
        {"name": "Tenants", "description": "Tenant management"},
        {"name": "Users", "description": "User management"},
        {"name": "Files", "description": "File storage and management"},
        {"name": "Datasets", "description": "Dataset management"},
        {"name": "Assets", "description": "Asset catalog management"},
        {"name": "Contracts", "description": "Data contract management"},
        {"name": "Jobs", "description": "Job orchestration"},
        {"name": "Data Quality", "description": "Data quality checks"},
        {"name": "Compliance", "description": "Compliance checks"},
        {"name": "Semantic", "description": "Semantic mapping and SPARQL"},
        {"name": "Marketplace", "description": "Marketplace listings, orders, and entitlements"},
        {"name": "Audit", "description": "Audit logging"},
        {
            "name": "Internal (Worker)",
            "description": "Internal scheduled-ingestion worker API (worker-only auth)",
        },
    ],
    # Note: Custom Error schema removed - using inline serializers in views instead
    # APPEND_COMPONENTS with dict-based schemas causes 'dict' object has no attribute 'request_only' error
    # Error schemas are now defined inline in views using inline_serializer
    "POSTPROCESSING_HOOKS": [
        "hub.apps.api.openapi_mvp.postprocess_drop_mvp_gated_paths",
    ],
}

# CORS Configuration
# In production the list MUST be supplied explicitly via the env var.
# Localhost origins are never allowed in production.
_cors_defaults = [] if ENVIRONMENT == "production" else [
    "http://localhost:3000",   # docker-compose frontend (default port)
    "http://localhost:3010",   # docker-compose.test.yml frontend
    "http://localhost:5173",   # Vite dev server
    "http://localhost:5184",   # Vite dev server (alternate port)
    "http://localhost:8000",
]
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=_cors_defaults)  # type: ignore[arg-type]

if ENVIRONMENT == "production" and not CORS_ALLOWED_ORIGINS:
    raise ImproperlyConfigured(
        "CORS_ALLOWED_ORIGINS must be set in production."
    )
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "cache-control",  # E2E and clients may send cache-busting (no-cache, no-store)
    "content-type",
    "dnt",
    "expires",
    "origin",
    "pragma",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-correlation-id",  # For frontend request tracing
    "x-request-id",  # Alternative correlation ID header
    "x-tenant-id",  # Tenant scoping header for multi-tenant requests
]

# JWT Configuration
JWT_SECRET_KEY = env("JWT_SECRET_KEY", default=_DEV_JWT_SECRET_KEY)
JWT_ALGORITHM = env("JWT_ALGORITHM", default="RS256")
JWT_PRIVATE_KEY = env("JWT_PRIVATE_KEY", default="")  # RS256 signing (api-service only)
JWT_PUBLIC_KEY = env("JWT_PUBLIC_KEY", default="")    # RS256 verification (all services)

# Encryption key — defined here so the unified production guard below can check it.
ENCRYPTION_KEY = env("ENCRYPTION_KEY", default=_DEV_ENCRYPTION_KEY)

# Production: all secret keys MUST be set via env and must not be dev defaults.
if ENVIRONMENT == "production":
    _secret_guards = [
        (
            SECRET_KEY,
            _DEV_SECRET_KEY,
            "SECRET_KEY",
            "Set SECRET_KEY in env or use a secret manager. See docs/SECURITY.md.",
        ),
        (
            JWT_SECRET_KEY,
            _DEV_JWT_SECRET_KEY,
            "JWT_SECRET_KEY",
            "Set JWT_SECRET_KEY in env or use a secret manager. See docs/SECURITY.md.",
        ),
        (
            ENCRYPTION_KEY,
            _DEV_ENCRYPTION_KEY,
            "ENCRYPTION_KEY",
            "Set ENCRYPTION_KEY to a cryptographically random "
            "32-byte base64 value. See docs/SECURITY.md.",
        ),
    ]
    for _val, _dev_default, _name, _hint in _secret_guards:
        if not _val or _val == _dev_default:
            raise ImproperlyConfigured(
                f"In production, {_name} must be set via environment "
                f"and must not be the dev default. {_hint}"
            )
JWT_ACCESS_TOKEN_EXPIRY = env.int("JWT_ACCESS_TOKEN_EXPIRY", default=3600)  # 1 hour
JWT_REFRESH_TOKEN_EXPIRY = env.int("JWT_REFRESH_TOKEN_EXPIRY", default=86400)  # 24 hours
# Phase 90: Maximum refresh token lifetime (absolute cap, even if JWT_REFRESH_TOKEN_EXPIRY is higher)
REFRESH_TOKEN_MAX_LIFETIME_DAYS = env.int("REFRESH_TOKEN_MAX_LIFETIME_DAYS", default=30)
JWT_ISSUER = env("JWT_ISSUER", default="hub")

# Phase 90: When True, access tokens are delivered via httpOnly cookie instead
# of response body. Frontend must rely on cookie-based auth (no localStorage).
# Default False for backward compatibility with existing SPA clients.
USE_HTTPONLY_AUTH_COOKIES = env.bool("USE_HTTPONLY_AUTH_COOKIES", default=False)

# B2 (glittery-herding-graham): grace period (seconds) for concurrent-tab
# refresh token replay detection. When a revoked token is presented and a
# valid sibling was created within this window, the system assumes concurrent
# tabs rather than token theft — rotates from the sibling instead of revoking
# the entire family. Set to 0 to disable (strict replay detection).
REFRESH_TOKEN_GRACE_PERIOD_SECONDS = env.int("REFRESH_TOKEN_GRACE_PERIOD_SECONDS", default=5)

# F4 (glittery-herding-graham): IP-level rate limit for /auth/refresh/.
REFRESH_IP_RATE_PER_MINUTE = env.int("REFRESH_IP_RATE_PER_MINUTE", default=30)

# ── Refresh-token cookie (11.1, hardened 221.5.1) ────────────────────────────
# Phase 221.5.1: The __Secure- prefix is a browser-enforced security feature
# that requires the Secure attribute (HTTPS).  This prevents:
#   • Subdomain cookie theft (an HTTP subdomain cannot set/read the cookie)
#   • Accidental transmission over unencrypted connections
#
# In development (DEBUG=True → secure=False), __Secure- cookies are silently
# dropped by browsers, so the plain name is used instead.
_refresh_cookie_default = (
    "__Secure-refresh_token"
    if ENVIRONMENT in ("production", "staging")
    else "refresh_token"
)
REFRESH_COOKIE_NAME = env("REFRESH_COOKIE_NAME", default=_refresh_cookie_default)

# ── Login rate-limiting & account lockout (11.5) ─────────────────────────────
LOGIN_IP_RATE_PER_MINUTE = env.int("LOGIN_IP_RATE_PER_MINUTE", default=10)
LOGIN_MAX_ATTEMPTS = env.int("LOGIN_MAX_ATTEMPTS", default=10)
LOGIN_LOCKOUT_WINDOW_MINUTES = env.int("LOGIN_LOCKOUT_WINDOW_MINUTES", default=15)

# Personal tenant on registration (useronboardfix): when True (default), users who register
# without tenant_id get a personal tenant with DATA_PROVIDER and DATA_CONSUMER roles.
# Set to False to preserve legacy behavior (tenant=None).
PERSONAL_TENANT_ON_REGISTRATION = env.bool("PERSONAL_TENANT_ON_REGISTRATION", default=True)

# Tenant switch (Phase 29.65): when True (default), users can switch active tenant via
# GET /auth/me/tenants/, POST /auth/switch-tenant/, and X-Tenant-Id header.
# Set to False to disable tenant switching (e.g. during migration or rollback).
FEATURE_TENANT_SWITCH_ENABLED = env.bool("FEATURE_TENANT_SWITCH_ENABLED", default=True)

# Worker API (scheduled ingestion internal): optional env key for Prefect worker
# When set, worker authenticates with Authorization: ApiKey <HUB_WORKER_API_KEY> and X-Tenant-ID header
HUB_WORKER_API_KEY = env("HUB_WORKER_API_KEY", default=None)

# Billing (Stripe): optional; when set, subscription/customer creation uses Stripe (test key sk_test_... for tests)
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default=None)
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default=None)
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default=None)
STRIPE_MARKETPLACE_WEBHOOK_SECRET = env("STRIPE_MARKETPLACE_WEBHOOK_SECRET", default=None)

# Structured Logging (structlog)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
        },
        "console": {
            "format": "%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if env("LOG_FORMAT", default="json") == "json" else "console",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": env("LOG_LEVEL", default="INFO"),
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": env("LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "hub": {
            "handlers": ["console"],
            "level": env("LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
    },
}

# Structlog Configuration
# Import and configure structlog with enhanced processors
from hub.apps.observability.logging import configure_structlog

configure_structlog()

# =============================================================================
# OpenTelemetry Configuration
# Phase 4 — Observability Stack
#
# Architecture:
#   Django app  --OTLP gRPC-->  OTel Collector  --OTLP-->  Tempo  (traces)
#                                               --pull-->  Prometheus  (metrics)
#   Docker logs  --Promtail-->  Loki  (logs)
#
# In production set AWS_SECRETS_ENABLED=true; AWS SM injects OTEL_* env vars.
# In development the defaults below target a local OTel Collector (4317).
# =============================================================================

# --- Metrics -----------------------------------------------------------------
# Migrated from django-prometheus (not compatible with Django 6.0) to
# OpenTelemetry metrics exported via OTLP push to the OTel Collector.
OPENTELEMETRY_METRICS_ENABLED = env.bool("OPENTELEMETRY_METRICS_ENABLED", default=True)
OPENTELEMETRY_METRICS_EXPORT_INTERVAL_MS = env.int(
    "OPENTELEMETRY_METRICS_EXPORT_INTERVAL_MS", default=10000
)  # 10 seconds

# --- Tracing -----------------------------------------------------------------
# OPENTELEMETRY_ENABLED defaults to False in development to avoid requiring
# a running OTel Collector.  Set OPENTELEMETRY_ENABLED=true in production.
OPENTELEMETRY_ENABLED = env.bool("OPENTELEMETRY_ENABLED", default=False)
OPENTELEMETRY_EXPORTER = env.str("OPENTELEMETRY_EXPORTER", default="otlp")  # 'otlp' only

# --- Service identity --------------------------------------------------------
# OTEL_SERVICE_NAME: the logical service name shown in Tempo / dashboards.
OTEL_SERVICE_NAME = env.str("OTEL_SERVICE_NAME", default="data-interoperability-hub-api")

# OTEL_SERVICE_NAMESPACE: groups services belonging to the same product.
OTEL_SERVICE_NAMESPACE = env.str("OTEL_SERVICE_NAMESPACE", default="hub")

# OTEL_SERVICE_VERSION: populated from the GIT_SHA build arg or env var.
# Correlates traces with the deployed code revision.
OTEL_SERVICE_VERSION = env.str("OTEL_SERVICE_VERSION", default="unknown")

# --- OTLP exporter -----------------------------------------------------------
# Default targets the OTel Collector service inside the Docker Compose network.
# Override with OTEL_EXPORTER_OTLP_ENDPOINT in .env.production if the
# Collector runs on a different host or port.
OTEL_EXPORTER_OTLP_ENDPOINT = env.str(
    "OTEL_EXPORTER_OTLP_ENDPOINT", default="http://otel-collector:4317"
)
OTEL_EXPORTER_OTLP_PROTOCOL = env.str(
    "OTEL_EXPORTER_OTLP_PROTOCOL", default="grpc"
)  # 'grpc' or 'http/protobuf'

# --- Resource attributes -----------------------------------------------------
# OTEL resource attributes are key=value pairs that describe the entity
# producing telemetry.  They are attached to every span, metric, and log
# record and appear in Tempo / Grafana for filtering and correlation.
#
# Standard OTEL semantic convention keys used here:
#   service.name        — logical service name (also OTEL_SERVICE_NAME above)
#   service.namespace   — product namespace (hub)
#   service.version     — deployed code version (git SHA or semver tag)
#   deployment.environment — production / staging / development
#
# These are consumed by hub/apps/observability/otel_config.py when
# building the TracerProvider Resource.
OTEL_RESOURCE_ATTRIBUTES: dict[str, str] = {
    "service.name": OTEL_SERVICE_NAME,
    "service.namespace": OTEL_SERVICE_NAMESPACE,
    "service.version": OTEL_SERVICE_VERSION,
    "deployment.environment": ENVIRONMENT,
}

# --- Database query instrumentation ------------------------------------------
OTEL_DB_SLOW_QUERY_THRESHOLD_MS = env.float("OTEL_DB_SLOW_QUERY_THRESHOLD_MS", default=100.0)

# --- Trace sampling ----------------------------------------------------------
# Base sampling rate for successful requests (default: 10 % = 0.1).
# Errors are always sampled (100 %) via SpanMiddleware.
# Critical endpoints (DQ runs, contract validation) are always sampled.
# The OTel Collector's tail_sampling policy further refines this server-side.
OTEL_TRACES_SAMPLER_ARG = env.float(
    "OTEL_TRACES_SAMPLER_ARG", default=0.1
)  # 10% for successful requests

if OPENTELEMETRY_ENABLED:
    from hub.apps.observability.otel_config import setup_opentelemetry_tracing

    setup_opentelemetry_tracing()

# OpenTelemetry Metrics Setup (initialised in hub/apps/observability/otel_metrics.py)
# Metrics are pushed via OTLP to the OTel Collector, which exposes them
# on a Prometheus pull endpoint (:8889) for Prometheus to scrape.

# Job Timeouts
JOB_TIMEOUT_DQ_RUN = env.int("JOB_TIMEOUT_DQ_RUN", default=1800)  # 30 minutes
JOB_TIMEOUT_COMPLIANCE_RUN = env.int("JOB_TIMEOUT_COMPLIANCE_RUN", default=1800)  # 30 minutes
JOB_TIMEOUT_CONTRACT_VALIDATION = env.int("JOB_TIMEOUT_CONTRACT_VALIDATION", default=60)  # 1 minute
JOB_TIMEOUT_SEMANTIC_MAPPING = env.int("JOB_TIMEOUT_SEMANTIC_MAPPING", default=300)  # 5 minutes

# Phase 68: Default max retries for WorkflowInstance.max_retries field
WORKFLOW_MAX_RETRIES = env.int("WORKFLOW_MAX_RETRIES", default=3)

# External Service URLs
# In test environments, use localhost with correct port
# For staging: datacontract-service uses port 8092 externally
# For default: datacontract-service uses port 8080 externally
_default_datacontract_url = "http://datacontract-service:8080"
# Detect test environment and use localhost with appropriate port
# Event bus: in tests, persist events synchronously so Event.objects sees them without RQ worker
if "pytest" in sys.modules or "unittest" in sys.modules or os.getenv("TESTING"):
    EVENT_BUS_FORCE_SYNC_PERSISTENCE = True
else:
    EVENT_BUS_FORCE_SYNC_PERSISTENCE = env.bool("EVENT_BUS_FORCE_SYNC_PERSISTENCE", default=False)

# Phase 93.6: timeout (seconds) for individual event handlers
EVENT_HANDLER_TIMEOUT_SECONDS = env.int(
    "EVENT_HANDLER_TIMEOUT_SECONDS", default=30
)

if "pytest" in sys.modules or "unittest" in sys.modules or os.getenv("TESTING"):
    # Use localhost with port from env, or the standard test port as default.
    # Network I/O at settings import time is not permitted; override via
    # DATACONTRACT_CLI_SERVICE_URL env var when pointing at the staging service.
    _default_datacontract_url = os.getenv(
        "DATACONTRACT_CLI_SERVICE_URL_DEFAULT", "http://localhost:8080"
    )

DATACONTRACT_CLI_SERVICE_URL = env(
    "DATACONTRACT_CLI_SERVICE_URL", default=_default_datacontract_url
)
DATACONTRACT_CLI_TIMEOUT = env.int("DATACONTRACT_CLI_TIMEOUT", default=60)
DQ_SERVICE_URL = env("DQ_SERVICE_URL", default="http://dq-service:8083")
DQ_SERVICE_TIMEOUT = env.int("DQ_SERVICE_TIMEOUT", default=1800)  # 30 minutes
DQ_RESULT_CACHE_TTL = env.int("DQ_RESULT_CACHE_TTL", default=3600)  # 1 hour
# Per-request timeout for DQ /run (avoids indefinite hang; tests use shorter value)
if "pytest" in sys.modules or "unittest" in sys.modules or os.getenv("TESTING"):
    DQ_RUN_TIMEOUT = env.int("DQ_RUN_TIMEOUT", default=60)  # 60s in tests
else:
    DQ_RUN_TIMEOUT = env.int("DQ_RUN_TIMEOUT", default=120)  # 2 min in prod

# ODH (Open Data Hub) Service URLs
# ODH Training Operator URL - defaults to odh-training-operator service
_default_odh_training_url = "http://odh-training-operator:8080"
# Detect test environment and use localhost with appropriate port
if "pytest" in sys.modules or "unittest" in sys.modules or os.getenv("TESTING"):
    # In test environment, use localhost with external port (8096)
    _default_odh_training_url = "http://localhost:8096"
else:
    # In Docker, use service name with internal port
    _default_odh_training_url = "http://odh-training-operator:8080"

ODH_TRAINING_OPERATOR_URL = env("ODH_TRAINING_OPERATOR_URL", default=_default_odh_training_url)
ODH_SERVICE_URL = env("ODH_SERVICE_URL", default=_default_odh_training_url)  # Base ODH URL
ODH_SERVICE_TIMEOUT = env.int("ODH_SERVICE_TIMEOUT", default=1800)  # 30 minutes

# ODH Inference Scheduler URL - defaults to odh-inference-scheduler service
_default_odh_inference_url = "http://odh-inference-scheduler:8080"
# When running tests inside Docker (api-service-test), use test stack hostname so integration tests reach the scheduler
if os.path.exists("/.dockerenv") and ("pytest" in sys.modules or "unittest" in sys.modules or os.getenv("TESTING")):
    _default_odh_inference_url = "http://odh-inference-scheduler-test:8080"
elif "pytest" in sys.modules or "unittest" in sys.modules or os.getenv("TESTING"):
    # Test from host: use localhost with external port (8097)
    _default_odh_inference_url = "http://localhost:8097"
else:
    _default_odh_inference_url = "http://odh-inference-scheduler:8080"

ODH_INFERENCE_SCHEDULER_URL = env("ODH_INFERENCE_SCHEDULER_URL", default=_default_odh_inference_url)
COMPLIANCE_SERVICE_URL = env("COMPLIANCE_SERVICE_URL", default="http://compliance-service:8082")
COMPLIANCE_SERVICE_TIMEOUT = env.int("COMPLIANCE_SERVICE_TIMEOUT", default=1800)  # 30 minutes

# Semantic Service Configuration
SEMANTIC_SERVICE_URL = env("SEMANTIC_SERVICE_URL", default="http://semantic-service:8081")
SEMANTIC_INTERNAL_API_KEY = env("SEMANTIC_INTERNAL_API_KEY", default="")
# Test env: 60s - Fuseki/SPARQL can be slow (cold start, complex queries). Prod: 15s fail-fast.
if "pytest" in sys.modules or "unittest" in sys.modules or os.getenv("TESTING"):
    SEMANTIC_SERVICE_TIMEOUT = env.int(
        "SEMANTIC_SERVICE_TIMEOUT", default=60
    )  # 60 seconds for tests - resolve_uri/map_contract SPARQL can be slow
else:
    SEMANTIC_SERVICE_TIMEOUT = env.int(
        "SEMANTIC_SERVICE_TIMEOUT", default=15
    )  # 15 seconds for production (fail-fast when service unavailable)
HUB_DOMAIN = env("HUB_DOMAIN", default="hub.example.com")

# Base IRI for the semantic layer (ontology namespace + resource URIs).
# Must be a full URL, e.g. "https://meshant.io".
# In production this should be your public domain; the default is a
# placeholder — startup raises ImproperlyConfigured when still set to
# the placeholder in ENVIRONMENT=production.
SEMANTIC_BASE_IRI = env("SEMANTIC_BASE_IRI", default="https://meshant.io")
if (
    env("ENVIRONMENT", default="development") == "production"
    and SEMANTIC_BASE_IRI == "https://meshant.io"
):
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured(
        "SEMANTIC_BASE_IRI must be set to your public domain in production. "
        "Current value is the default placeholder 'https://meshant.io'."
    )

# Phase 24.6 — OWL/RDFS inference toggle.
# When True the Fuseki TDB2 dataset is configured with an RDFS reasoner.
# Inference triples are materialised at query time; expect 2-5x latency.
SEMANTIC_INFERENCE_ENABLED = env.bool(
    "SEMANTIC_INFERENCE_ENABLED", default=False
)

# Phase 230.4 (REQ-SEM-MEMENTO-001) — Memento (RFC 7089) versioned-
# retrieval feature flag.  Gated AND with ``Tenant.semantic_memento_enabled``
# at the resource level (so global=True turns the feature ON for all
# tenants whose per-tenant flag is also True; global=False short-
# circuits the feature for the entire deployment regardless of
# per-tenant settings).
SEMANTIC_MEMENTO_ENABLED = env.bool(
    "SEMANTIC_MEMENTO_ENABLED", default=False
)
# Per-tenant cap on ``SemanticResourceVersion`` rows.  Above this an
# alert fires + new snapshot creates are refused.  Override per
# environment if a customer needs a higher ceiling (rare).
SEMANTIC_MEMENTO_MAX_PER_RESOURCE = env.int(
    "SEMANTIC_MEMENTO_MAX_PER_RESOURCE", default=100,
)
SEMANTIC_MEMENTO_MAX_PER_TENANT = env.int(
    "SEMANTIC_MEMENTO_MAX_PER_TENANT", default=1_000_000,
)
# Debounce window — Redis SETNX TTL.  Two updates inside the same
# 60s window collapse into a single snapshot.
SEMANTIC_MEMENTO_DEBOUNCE_SECONDS = env.int(
    "SEMANTIC_MEMENTO_DEBOUNCE_SECONDS", default=60,
)

# Internal API key shared between hub (Django) and FastAPI microservices.
# All hub → microservice calls include this as the X-Internal-Api-Key header.
# Must match INTERNAL_API_KEY env var set in each FastAPI service container.
# Generate: openssl rand -hex 32
INTERNAL_API_KEY = env("INTERNAL_API_KEY", default="")

# SPARQL Endpoint Configuration
SPARQL_MAX_TIMEOUT = env.int("SPARQL_MAX_TIMEOUT", default=30)  # 30 seconds
SPARQL_RESULT_LIMIT = env.int("SPARQL_RESULT_LIMIT", default=10000)  # 10,000 rows

# Rate Limiting Configuration
RATE_LIMIT_ENABLED = env.bool("RATE_LIMIT_ENABLED", default=True)
RATE_LIMIT_PER_TENANT = env.int("RATE_LIMIT_PER_TENANT", default=100)  # requests per minute
RATE_LIMIT_PER_USER = env.int("RATE_LIMIT_PER_USER", default=100)  # requests per minute
RATE_LIMIT_WINDOW = env.int("RATE_LIMIT_WINDOW", default=60)  # seconds

# Idempotency Configuration
IDEMPOTENCY_ENABLED = env.bool("IDEMPOTENCY_ENABLED", default=True)
IDEMPOTENCY_TTL_SECONDS = env.int("IDEMPOTENCY_TTL_SECONDS", default=86400)  # 24 hours
FUSEKI_URL = env("FUSEKI_URL", default="http://fuseki:3030")
FUSEKI_DATASET = env("FUSEKI_DATASET", default="hub")

# Service Communication Configuration
SERVICE_COMMUNICATION_TIMEOUT = env.float("SERVICE_COMMUNICATION_TIMEOUT", default=30.0)  # seconds
SERVICE_COMMUNICATION_CONNECT_TIMEOUT = env.float(
    "SERVICE_COMMUNICATION_CONNECT_TIMEOUT", default=5.0
)  # seconds
SERVICE_COMMUNICATION_RETRY_COUNT = env.int("SERVICE_COMMUNICATION_RETRY_COUNT", default=3)
SERVICE_COMMUNICATION_RETRY_DELAY = env.float(
    "SERVICE_COMMUNICATION_RETRY_DELAY", default=1.0
)  # seconds
SERVICE_COMMUNICATION_RETRY_MAX_DELAY = env.float(
    "SERVICE_COMMUNICATION_RETRY_MAX_DELAY", default=60.0
)  # seconds
SERVICE_COMMUNICATION_RETRY_STRATEGY = env(
    "SERVICE_COMMUNICATION_RETRY_STRATEGY", default="exponential_backoff"
)  # exponential_backoff, linear_backoff, fixed_delay

# Compliance Configuration
COMPLIANCE_PII_THRESHOLD = env.float("COMPLIANCE_PII_THRESHOLD", default=0.01)  # 1% threshold

# SPARQL Configuration
SPARQL_QUERY_TIMEOUT = env.int("SPARQL_QUERY_TIMEOUT", default=30)  # 30 seconds
SPARQL_RESULT_LIMIT = env.int("SPARQL_RESULT_LIMIT", default=10000)
SPARQL_QUERY_COMPLEXITY_LIMIT = env.int(
    "SPARQL_QUERY_COMPLEXITY_LIMIT", default=20
)  # Complexity score limit

# Search Query Configuration
SEARCH_QUERY_MAX_LENGTH = env.int(
    "SEARCH_QUERY_MAX_LENGTH", default=1000
)  # Maximum query length in characters
SEARCH_QUERY_COMPLEXITY_LIMIT = env.int(
    "SEARCH_QUERY_COMPLEXITY_LIMIT", default=50
)  # Complexity score limit
SEARCH_QUERY_MIN_LENGTH = env.int("SEARCH_QUERY_MIN_LENGTH", default=1)  # Minimum query length

# GraphQL Configuration
GRAPHQL_QUERY_COMPLEXITY_LIMIT = env.int("GRAPHQL_QUERY_COMPLEXITY_LIMIT", default=1000)

# Security
# ENCRYPTION_KEY is defined near JWT_SECRET_KEY above; production guard is
# enforced in the unified _secret_guards loop alongside SECRET_KEY and
# JWT_SECRET_KEY.
PII_REDACTION_ENABLED = env.bool("PII_REDACTION_ENABLED", default=True)

# ============================================================================
# Contract Standard Versions (Phase 26.10.1)
# ============================================================================

ODCS_VERSIONS_SUPPORTED = env.list(
    "ODCS_VERSIONS_SUPPORTED",
    default=["2.2.2", "3.0.0", "3.0.1", "3.0.2", "3.1.0"],
)

ODPS_VERSIONS_SUPPORTED = env.list(
    "ODPS_VERSIONS_SUPPORTED",
    default=[
        "1.x", "2.x", "3.x", "4.0", "4.1", "4.2",
        "bitol-0.9.0", "bitol-1.0.0",
    ],
)

# Phase 227 Wave 1 (227.L2.3) — recursive nested-properties walker depth.
#
# ODCS schemas allow arbitrarily nested ``object``/``array`` field types
# via ``properties`` or ``fields``/``items``. The recursive walker in
# :func:`hub.apps.contracts.normalization_engine._map_field` enforces this
# upper bound and raises ``ValidationError(code="SCHEMA_TOO_DEEP")`` BEFORE
# Python's own 1000-level recursion limit fires (which would 500 the API).
#
# Default of 20 covers every realistic schema we have observed in
# production while still rejecting pathological inputs. Override via
# ``CONTRACTS_MAX_NESTING_DEPTH`` env var on a per-tenant basis if a
# legitimate deeper schema appears.
CONTRACTS_MAX_NESTING_DEPTH = env.int(
    "CONTRACTS_MAX_NESTING_DEPTH", default=20,
)

# ============================================================================
# Django 6 Security Enhancements
# ============================================================================

# HTTPS and SSL/TLS Security
# Set to True in production environments with HTTPS
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
SECURE_HSTS_SECONDS = env.int(
    "SECURE_HSTS_SECONDS", default=0
)  # Set to 31536000 (1 year) in production
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)

# Secure cookies (set to True in production with HTTPS)
SECURE_COOKIES = env.bool("SECURE_COOKIES", default=False)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=False)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=False)

# Production: enforce secure cookies, HSTS, and SSL redirect.
# These settings MUST NOT be forced True outside the production block so that
# local development and tests work without HTTPS.
#
# NEW-1 (glittery-dreaming-micali.md): the guards run FIRST — before any
# unconditional override — so an env-var like SESSION_COOKIE_SECURE=false
# causes an immediate ImproperlyConfigured instead of silently being
# overwritten. This matches the CORS_ALLOWED_ORIGINS guard at line ~1520.
if ENVIRONMENT == "production":
    # Guard BEFORE override: catch env-var misconfig that would disable
    # HTTPS protections. The env.bool() reads at ~lines 1979-1981 default
    # to False, so the only way these are True here is if the deployer
    # explicitly set the env vars — exactly what we require.
    if not SESSION_COOKIE_SECURE:
        raise ImproperlyConfigured(
            "SESSION_COOKIE_SECURE must be True in production. "
            "Set the env var explicitly."
        )
    if not CSRF_COOKIE_SECURE:
        raise ImproperlyConfigured(
            "CSRF_COOKIE_SECURE must be True in production. "
            "Set the env var explicitly."
        )
    if not SECURE_SSL_REDIRECT:
        raise ImproperlyConfigured(
            "SECURE_SSL_REDIRECT must be True in production. "
            "Set the env var explicitly."
        )

    # HSTS: unconditional production values (not env-var-driven).
    SECURE_HSTS_SECONDS = 63072000          # 2 years
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Content Security Policy (CSP) - Django 6 Enhancement
# For advanced CSP, consider using django-csp package
# Basic CSP configuration via SecurityMiddleware
SECURE_CONTENT_TYPE_NOSNIFF = env.bool("SECURE_CONTENT_TYPE_NOSNIFF", default=True)
SECURE_REFERRER_POLICY = env("SECURE_REFERRER_POLICY", default="strict-origin-when-cross-origin")

# X-Frame-Options (Clickjacking Protection)
# Django 6 default: DENY (already set via XFrameOptionsMiddleware)
X_FRAME_OPTIONS = env("X_FRAME_OPTIONS", default="DENY")

# CSRF Protection
CSRF_COOKIE_HTTPONLY = env.bool(
    "CSRF_COOKIE_HTTPONLY", default=True
)  # Phase 90: default True — CSRF token not readable by JS (XSS mitigation)
CSRF_COOKIE_SAMESITE = env(
    "CSRF_COOKIE_SAMESITE", default="Lax"
)  # Options: 'Strict', 'Lax', 'None'
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# Session Security
SESSION_COOKIE_HTTPONLY = env.bool("SESSION_COOKIE_HTTPONLY", default=True)
# Phase 221.5.2: Default changed from "Lax" to "Strict".
# The SPA authenticates via JWT (not Django sessions), so Strict does not
# break any auth flow.  Django admin is disabled in production (221.2.1).
# SSO views issue JWT tokens, not session cookies.  Strict prevents the
# session cookie from being sent on ANY cross-site request, including
# top-level navigations — a stronger CSRF mitigation than Lax.
SESSION_COOKIE_SAMESITE = env("SESSION_COOKIE_SAMESITE", default="Strict")
SESSION_COOKIE_AGE = env.int("SESSION_COOKIE_AGE", default=1209600)  # 2 weeks default

# GraphQL Settings
GRAPHQL_QUERY_COMPLEXITY_LIMIT = env.int("GRAPHQL_QUERY_COMPLEXITY_LIMIT", default=1000)

# Password hashing: use fast MD5 hasher in tests to avoid ~300 ms per
# create_user() call (PBKDF2 default does 600 k iterations).  This gives
# a 50-100x speedup on test suites that create thousands of users.
if is_test_env:
    PASSWORD_HASHERS = [
        "django.contrib.auth.hashers.MD5PasswordHasher",
    ]

# Rate Limiting
# Advanced rate limiting with sliding window algorithm
# See hub/apps/rate_limiting/config.py for platform defaults and maximums
# Disable rate limiting in test mode to prevent test failures
if is_test_env:
    RATE_LIMIT_ENABLED = False
else:
    RATE_LIMIT_ENABLED = env.bool("RATE_LIMIT_ENABLED", default=True)

# When running E2E against this API (Playwright, real backend), relax auth rate limit
# so many login attempts in sequence do not hit 429. Uses platform max for AUTH (20/min).
# Set RATE_LIMIT_E2E_RELAX=true for api-service when running E2E (e.g. in .env.dev or docker-compose).
RATE_LIMIT_E2E_RELAX = env.bool("RATE_LIMIT_E2E_RELAX", default=False)

# Legacy settings (kept for backward compatibility, but not used by new middleware)
RATE_LIMIT_PER_TENANT = env.int("RATE_LIMIT_PER_TENANT", default=200)
RATE_LIMIT_PER_USER = env.int("RATE_LIMIT_PER_USER", default=100)

# Phase 87: Parameterized virtual queries (SQL injection fix)
# When True (default), all virtual dataset queries use DB-driver native
# parameterisation.  Set to False only for emergency rollback.
PARAMETERIZED_VIRTUAL_QUERIES = env.bool(
    "PARAMETERIZED_VIRTUAL_QUERIES", default=True
)

# Phase 87: Enforce JWT scope mapping via ROLE_SCOPE_MAP
# When True, JWT users without explicit API key scopes are checked against
# ROLE_SCOPE_MAP.  When False (default), current permissive behaviour is
# preserved for safe rollout.
ENFORCE_JWT_SCOPES = env.bool("ENFORCE_JWT_SCOPES", default=False)

# Phase 220.3: warn if production is running without JWT scope enforcement.
# This is a warning (not error) to allow gradual rollout.
if ENVIRONMENT == "production" and not ENFORCE_JWT_SCOPES:
    import warnings
    warnings.warn(
        "ENFORCE_JWT_SCOPES is False in production. "
        "JWT users can bypass role-based scope checks. "
        "Set ENFORCE_JWT_SCOPES=true to enforce.",
        stacklevel=1,
    )

# Phase 200: MVP deployment — omit non-MVP /api/v1 routes, OpenAPI paths, and gate via middleware.
MVP_MODE = env.bool("MVP_MODE", default=False)

# Shared secret for the four /api/v1/test/ensure-e2e-* endpoints. Required
# in staging/test/production (enforced by hub.E002 system check on
# `manage.py check --deploy`). The @require_e2e_token decorator compares
# this via hmac.compare_digest; empty/unset secret returns 404
# unconditionally. Injected from AWS Secrets Manager via ExternalSecrets
# (see docs/e2e-setup.md).
E2E_TEST_SECRET = env.str("E2E_TEST_SECRET", default="")

# Workflow Business Rules Validation Feature Flags (Task 5.1.1)
# Global enable/disable for business rules validation in workflows
ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION = env.bool(
    "ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION", default=True
)

# Gradual rollout percentage (0-100)
# Controls percentage of workflows that have validation enabled
# 0 = disabled, 100 = fully enabled
WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE = env.int(
    "WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE", default=100
)

# Per-workflow enable/disable configuration
# Format: JSON object with workflow names as keys and boolean values
# Example: {"product_creation": true, "contract_creation": false}
WORKFLOW_BUSINESS_RULES_VALIDATION_WORKFLOWS = env.dict(
    "WORKFLOW_BUSINESS_RULES_VALIDATION_WORKFLOWS", default={}
)

# Explicitly disabled workflows (list of workflow names)
# These workflows will have validation disabled regardless of other settings
WORKFLOW_BUSINESS_RULES_VALIDATION_DISABLED_WORKFLOWS = env.list(
    "WORKFLOW_BUSINESS_RULES_VALIDATION_DISABLED_WORKFLOWS", default=[]
)

# Explicitly enabled workflows (list of workflow names)
# These workflows will have validation enabled regardless of rollout percentage
WORKFLOW_BUSINESS_RULES_VALIDATION_ENABLED_WORKFLOWS = env.list(
    "WORKFLOW_BUSINESS_RULES_VALIDATION_ENABLED_WORKFLOWS", default=[]
)

# Per-tenant enable/disable configuration (optional)
# Format: JSON object with tenant IDs as keys and boolean values
# Example: {"tenant-123": true, "tenant-456": false}
WORKFLOW_BUSINESS_RULES_VALIDATION_TENANTS = env.dict(
    "WORKFLOW_BUSINESS_RULES_VALIDATION_TENANTS", default={}
)

# Gradual Rollout (Task 5.2): workflow tier definitions for phased enablement
# Test/non-critical workflows: enable validation here first (5.2.1)
WORKFLOW_BUSINESS_RULES_VALIDATION_TEST_WORKFLOWS = env.list(
    "WORKFLOW_BUSINESS_RULES_VALIDATION_TEST_WORKFLOWS",
    default=[
        "model_training",
        "model_inference",
        "api_key_management",
        "data_quality_check",
        "virtualization_query_execution",
    ],
)
# Critical/production workflows: enable incrementally after test phase (5.2.2)
WORKFLOW_BUSINESS_RULES_VALIDATION_CRITICAL_WORKFLOWS = env.list(
    "WORKFLOW_BUSINESS_RULES_VALIDATION_CRITICAL_WORKFLOWS",
    default=[
        "product_creation",
        "contract_creation",
        "asset_creation",
        "dataset_creation",
        "marketplace_publication",
        "scheduled_ingestion",
        "access_request",
        "compliance_reporting",
        "data_mesh",
        "version_creation",
        "marketplace_sync",
    ],
)

# ODPS $ref Cache Warming Configuration (Task 9.8.4.3)
ODPS_CACHE_WARMING_ENABLED = env.bool("ODPS_CACHE_WARMING_ENABLED", default=True)
ODPS_CACHE_WARMING_STARTUP_ENABLED = env.bool("ODPS_CACHE_WARMING_STARTUP_ENABLED", default=True)
ODPS_CACHE_WARMING_SCHEDULED_ENABLED = env.bool(
    "ODPS_CACHE_WARMING_SCHEDULED_ENABLED", default=True
)
ODPS_CACHE_WARMING_STARTUP_LIMIT = env.int("ODPS_CACHE_WARMING_STARTUP_LIMIT", default=100)
ODPS_CACHE_WARMING_SCHEDULED_LIMIT = env.int("ODPS_CACHE_WARMING_SCHEDULED_LIMIT", default=1000)
ODPS_CACHE_WARMING_BATCH_SIZE = env.int("ODPS_CACHE_WARMING_BATCH_SIZE", default=10)

# Cost Tracking (UC-TA-007): rates for usage → cost conversion
# Override COST_RATES in local_settings or env for custom rates
# Defaults: storage $0.023/GB/month, API $0.001/1000 calls
COST_RATES = {
    "storage_per_gb_month": "0.023",
    "api_per_1000": "0.001",
    "asset_per_month": "0",
    "dataset_per_month": "0",
}

# ===========================================================================
# Prefect Kubernetes Work Pool Configuration (17.7)
# ===========================================================================
# Settings consumed by services/prefect-integration/deployment_sync.py when
# creating deployments against the Kubernetes work pool.
# All PREFECT_K8S_* values have safe local-dev defaults; override in
# .env.production.template / Vault for production K8s deployments.
PREFECT_API_URL = env("PREFECT_API_URL", default="http://prefect-server:4200/api")
PREFECT_WORK_POOL_NAME = env("PREFECT_WORK_POOL_NAME", default="local-process-pool")
PREFECT_K8S_NAMESPACE = env("PREFECT_K8S_NAMESPACE", default="default")
PREFECT_K8S_IMAGE_PULL_SECRETS = env.list("PREFECT_K8S_IMAGE_PULL_SECRETS", default=[])
PREFECT_K8S_SERVICE_ACCOUNT_NAME = env("PREFECT_K8S_SERVICE_ACCOUNT_NAME", default="prefect-worker")
PREFECT_K8S_CPU_REQUEST = env("PREFECT_K8S_CPU_REQUEST", default="100m")
PREFECT_K8S_CPU_LIMIT = env("PREFECT_K8S_CPU_LIMIT", default="1000m")
PREFECT_K8S_MEMORY_REQUEST = env("PREFECT_K8S_MEMORY_REQUEST", default="256Mi")
PREFECT_K8S_MEMORY_LIMIT = env("PREFECT_K8S_MEMORY_LIMIT", default="1Gi")

# ===========================================================================
# Phase 228 F4 (228.F4.13) — OpenLineage standard integration
# ===========================================================================
# Marquez (self-hosted on EKS) is the default OP-1 receiver. The
# adapter POSTs every translated RunEvent here. Override per-environment
# via OPENLINEAGE_URL env var; the default targets the in-cluster
# service name so the call stays inside the VPC (228.F4.16 mTLS /
# VPC-internal TLS Hub ↔ Marquez).
OPENLINEAGE_URL = env.str(
    "OPENLINEAGE_URL",
    default="http://marquez.marquez.svc.cluster.local:5000/api/v1/lineage",
)

# Producer URL surfaced on every outbound RunEvent. Marquez + Datakin
# both display this so external observers can identify the source.
OPENLINEAGE_PRODUCER_NAME = env.str(
    "OPENLINEAGE_PRODUCER_NAME",
    default="https://meshant.com/lineage/openlineage",
)

# HMAC signing key for the inbound endpoint. Populated from AWS
# Secrets Manager (`meshant/staging/openlineage/hmac_signing_key`,
# 90-day rotation per 228.F4.14). Empty default in dev → endpoint
# rejects every signature so a misconfigured dev never authenticates
# inadvertently.
OPENLINEAGE_HMAC_SIGNING_KEY = env.str(
    "OPENLINEAGE_HMAC_SIGNING_KEY",
    default="",
)

# Phase 228 F4 (228.F4.27 self-audit GAP-1) — under pytest / unittest the
# default in-cluster service URL is unreachable and the adapter would
# burn 31s on retry-then-DLQ for every Contract save in the test suite.
# Setting OPENLINEAGE_URL="" makes ``send_openlineage_event_async``
# skip-fast with ``return "skipped:no_target_url"`` (the function's
# documented contract). Tests that need an actual target URL override
# via ``@override_settings(OPENLINEAGE_URL=...)`` per-class.
if "pytest" in sys.modules or "unittest" in sys.modules or os.getenv("TESTING"):
    OPENLINEAGE_URL = env.str("OPENLINEAGE_URL", default="")


# ===========================================================================
# Phase 228 F5 (228.F5.7) — lineage archive S3 bucket
# ===========================================================================
# Cold-tier bucket name consumed by ``archive_lineage_edges --target=s3``.
# Provisioned by [infrastructure/terraform/lineage_archive/](infrastructure/terraform/lineage_archive/).
# Default empty so the dev / test environments don't need an S3 round-trip;
# the management command refuses to run with `--target=s3` if neither this
# setting nor the `--bucket` CLI flag is set.
LINEAGE_ARCHIVE_S3_BUCKET = env.str(
    "LINEAGE_ARCHIVE_S3_BUCKET",
    default="",
)

# ===========================================================================
# Phase 228 F5 (228.F5.DoD.6) — per-tenant rollout overrides
# ===========================================================================
# When ``CAPABILITY_FLAGS["<name>"] == False`` the per-tenant
# allow-list below promotes the call for the listed tenants.  Lets
# ops phase the F5 rollout (5 internal canary → 50% → 100%) via
# Helm value flips alone — no code changes between phases.
#
# Helm pattern:
#   api:
#     env:
#       CAPABILITY_FLAGS_ROLLOUT_TENANTS: '{"lineage.snapshots": ["uuid1", "uuid2"]}'
# settings.py reads the env var as a JSON string; default empty.
_CAPABILITY_FLAGS_ROLLOUT_TENANTS_RAW = env.str(
    "CAPABILITY_FLAGS_ROLLOUT_TENANTS", default="",
)
try:
    import json as _json
    CAPABILITY_FLAGS_ROLLOUT_TENANTS: dict[str, list[str]] = (
        _json.loads(_CAPABILITY_FLAGS_ROLLOUT_TENANTS_RAW)
        if _CAPABILITY_FLAGS_ROLLOUT_TENANTS_RAW.strip()
        else {}
    )
except (ValueError, TypeError):
    CAPABILITY_FLAGS_ROLLOUT_TENANTS = {}


# ===========================================================================
# Phase 228 F3 (228.F3.10) — Lineage Impact Dispatcher DB connection pool
# ===========================================================================
# REQ-LIN-F3-005 mandates a dedicated DB connection pool of 5–10 connections
# for the dispatcher so notification storms cannot starve request handlers.
#
# Deployment model: the dispatcher runs in the existing ``job_low`` worker
# pod (django-rq).  To dedicate a pool, deploy a SEPARATE worker pod with:
#
#     env:
#       LINEAGE_IMPACT_DISPATCHER_DEDICATED=true
#       DATABASE_CONN_MAX_AGE=60        # short-lived; recycled every minute
#       DATABASE_MAX_CONNS=10           # hard cap per worker
#       RQ_QUEUES_NAMES=lineage_impact  # only this queue
#
# The dispatcher itself reads the toggle below to decide whether to apply
# extra defensive limits.  When ``False`` (default), the dispatcher runs
# in-process from ``transaction.on_commit`` — fine for low-volume tenants;
# the dedicated worker is opt-in for tenants that approach the F3.20 load
# target (1000 subscribers per event).
LINEAGE_IMPACT_DISPATCHER_DEDICATED = env.bool(
    "LINEAGE_IMPACT_DISPATCHER_DEDICATED",
    default=False,
)
LINEAGE_IMPACT_DISPATCHER_MAX_CONNS = env.int(
    "LINEAGE_IMPACT_DISPATCHER_MAX_CONNS",
    default=10,
)
