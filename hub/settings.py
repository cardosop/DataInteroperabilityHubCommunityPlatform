"""
Django settings for hub project.

Generated with configuration for Interoperable Data Hub MVP.
"""

import os
from pathlib import Path

import environ

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

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY", default="dev-secret-key-not-for-production")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env("DEBUG", default=True)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "api-service"])

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
    # django-prometheus removed: Not compatible with Django 6.0
    # Migrated to OpenTelemetry metrics with Prometheus exporter
    # Local apps
    "hub.apps.core",
    "hub.apps.tenants",
    "hub.apps.users",
    "hub.apps.auth",
    "hub.apps.audit",
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
    # hub.apps.graphql_graphene is optional - only add if graphene_django is available
    # "hub.apps.graphql_graphene",  # Made optional to prevent startup failures if not installed
    "hub.apps.health",
    "hub.apps.observability",
    "hub.apps.notifications",
    "hub.apps.rate_limiting",
    "hub.apps.scheduled_ingestion",
    "hub.apps.search",
    "hub.apps.webhooks.apps.WebhooksConfig",
    "hub.apps.api.analytics",
    "hub.apps.orchestration",
    "hub.apps.transformation",  # Transformation pipelines
    "hub.apps.websocket",  # WebSocket API
    "hub.apps.ai",  # AI/ML features
    "hub.apps.ml",  # ML Model Registry Bridge
    "hub.apps.social",  # Social features
    "hub.apps.mesh",  # Data mesh domains and federated governance
    "hub.apps.virtualization",  # Data virtualization and federated queries
    "hub.apps.integrations",  # Marketplace connectors and integrations
    "hub.apps.baas",  # BaaS Platform (API Gateway, usage tracking, developer portal)
]

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
    # django-prometheus middleware removed: Not compatible with Django 6.0
    # Migrated to OpenTelemetry metrics with Prometheus exporter
    "hub.apps.observability.middleware.MetricsMiddleware",  # Custom metrics middleware (from middleware package)
    "django_structlog.middlewares.request.RequestMiddleware",
    "hub.apps.api.middleware.RequestIDMiddleware",  # Request ID generation
    "hub.apps.api.middleware.tracing.TraceIDMiddleware",  # Trace ID extraction and propagation
    "hub.apps.observability.middleware.span_middleware.SpanMiddleware",  # OpenTelemetry span instrumentation
    "hub.apps.api.standards.validation_middleware.APIValidationMiddleware",  # API validation middleware
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "hub.apps.api.middleware.csrf_exempt.APIEndpointCSRFExemptMiddleware",  # CSRF exemption for API endpoints
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "hub.apps.auth.middleware.TenantScopingMiddleware",  # Tenant scoping after authentication
    "hub.apps.tenants.middleware.TenantSuspensionMiddleware",  # Tenant suspension enforcement
    "hub.apps.api.versioning.APIVersionMiddleware",  # API versioning and deprecation warnings
    "hub.apps.api.middleware.idempotency.IdempotencyMiddleware",  # Idempotency key handling
    "hub.apps.api.middleware.cache_headers.CacheHeadersMiddleware",  # HTTP cache headers (ETag, Last-Modified, Cache-Control)
    "hub.apps.rate_limiting.middleware.RateLimitMiddleware",  # Advanced rate limiting (replaces basic middleware)
    "hub.apps.api.analytics.middleware.APIAnalyticsMiddleware",  # API analytics tracking
    "hub.apps.governance.middleware.AccessLoggingMiddleware",  # Access logging for analytics
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # django-prometheus middleware removed: Not compatible with Django 6.0
    # Migrated to OpenTelemetry metrics with Prometheus exporter
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
    except Exception:
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
        except Exception:
            pass

    # Default to False (non-staging) if detection fails
    # This prevents production from accidentally using staging ports
    return False


# Fix threading issue: Disable Django's thread validation for tests
# Root cause: pytest-django creates database connections in one thread,
# but Django's TestCase uses them in another thread.
# This is safe because pytest-django properly manages connection lifecycle
if "test" in sys.argv or "pytest" in sys.modules:
    import django.db.backends.base.base

    _original_validate = django.db.backends.base.base.BaseDatabaseWrapper.validate_thread_sharing

    def _noop_validate_thread_sharing(self):
        """Disable thread validation for tests - safe because pytest-django manages connections"""
        pass

    django.db.backends.base.base.BaseDatabaseWrapper.validate_thread_sharing = (
        _noop_validate_thread_sharing
    )

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
            # Check if this is a "starting up" error that we should retry
            is_starting_up = any(
                phrase in error_msg
                for phrase in [
                    "starting up",
                    "the database system is starting up",
                    "connection refused",
                    "connection to server",
                ]
            )

            if is_starting_up and attempt < max_retries - 1:
                # Retry for "starting up" errors
                import os
                import warnings

                # Only log if in verbose mode or Docker Compose E2E test mode
                if (
                    os.getenv("DOCKER_COMPOSE_E2E_TEST", "").lower() == "true"
                    or os.getenv("VERBOSE", "").lower() == "true"
                ):
                    warnings.warn(
                        f"PostgreSQL is starting up, retrying in {retry_delay}s "
                        f"(attempt {attempt + 1}/{max_retries}). "
                        f"Host: {postgres_host}:{postgres_port}, DB: {postgres_db}."
                    )
                time.sleep(retry_delay)
                continue
            elif is_starting_up:
                # Max retries reached, but it's a "starting up" error
                # Allow it for Docker Compose E2E tests (they will retry later)
                import os
                import warnings

                if not os.getenv("DOCKER_COMPOSE_E2E_TEST", "").lower() == "true":
                    warnings.warn(
                        f"PostgreSQL connection failed after {max_retries} retries "
                        f"(may be starting up or not running). "
                        f"Connection will be retried when needed. "
                        f"Host: {postgres_host}:{postgres_port}, DB: {postgres_db}. "
                        f"Error: {e}"
                    )
                # Don't raise - allow connection to be retried later
                break
            else:
                # Not a "starting up" error - raise immediately
                raise RuntimeError(
                    f"PostgreSQL connection failed for tests. "
                    f"Host: {postgres_host}:{postgres_port}, DB: {postgres_db}, User: {postgres_user}. "
                    f"Error: {e}. "
                    f"Please ensure PostgreSQL is running and accessible. "
                    f"SQLite is not supported for e2e tests."
                ) from e

    # If we exhausted retries and still have an error, check if we should raise
    if last_error and attempt == max_retries - 1:
        error_msg = str(last_error).lower()
        is_starting_up = any(
            phrase in error_msg
            for phrase in [
                "starting up",
                "the database system is starting up",
                "connection refused",
                "connection to server",
            ]
        )
        if not is_starting_up:
            # Non-starting-up error after retries - raise it
            raise RuntimeError(
                f"PostgreSQL connection failed for tests after {max_retries} retries. "
                f"Host: {postgres_host}:{postgres_port}, DB: {postgres_db}, User: {postgres_user}. "
                f"Error: {last_error}. "
                f"Please ensure PostgreSQL is running and accessible. "
                f"SQLite is not supported for e2e tests."
            ) from last_error

    # Use PostgreSQL for tests - supports proper transaction handling
    # For SDK tests, use the same database as API service so API can see test data
    use_production_db = os.getenv("USE_PRODUCTION_DB_FOR_SDK_TESTS", "").lower() == "1"

    if use_production_db:
        # Use production database for SDK tests (allows API service to see test data)
        test_db_name = postgres_db
    else:
        # Use a unique test database name to avoid conflicts
        import uuid

        test_db_suffix = os.getenv("TEST_DB_SUFFIX", str(uuid.uuid4())[:8])
        test_db_name = f"{postgres_db}_test_{test_db_suffix}"

    # CRITICAL: Ensure we use the detected password, not the env var
    # The password detection above tries actual passwords and uses the one that works
    # This handles cases where POSTGRES_PASSWORD env var doesn't match actual DB password
    final_password = postgres_password if postgres_password else os.getenv("POSTGRES_PASSWORD", "hub")

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
                "MIGRATE": not use_production_db,  # Skip migrations if using production DB (already migrated)
                "DEPENDENCIES": [],  # No dependencies - migrations handle this
                "CREATE_DB": not use_production_db,  # Don't create DB if using production
            },
            "CONN_MAX_AGE": 0,  # Don't reuse connections in tests
            "OPTIONS": {
                # Disable thread validation for tests (pytest-django uses multiple threads)
                # This is safe in test environment where we control thread usage
                "connect_timeout": 10,
                # CRITICAL: Set transaction isolation level to READ COMMITTED for LiveServerTestCase
                # This ensures data committed in one thread is immediately visible to other threads
                # Without this, the server thread might not see data created in the test thread
                "isolation_level": psycopg2_extensions.ISOLATION_LEVEL_READ_COMMITTED,
            },
        }
    }

    # Disable database connection thread validation for tests
    # pytest-django creates connections in one thread but TestCase uses them in another
    # This is safe because pytest-django manages the connection lifecycle properly
    import django.db.backends.base.base

    original_validate_thread_sharing = (
        django.db.backends.base.base.BaseDatabaseWrapper.validate_thread_sharing
    )

    def noop_validate_thread_sharing(self):
        """Disable thread validation for tests"""
        pass

    django.db.backends.base.base.BaseDatabaseWrapper.validate_thread_sharing = (
        noop_validate_thread_sharing
    )
else:
    # Database connection pooling configuration
    # CONN_MAX_AGE: Maximum age of database connections in seconds
    # - 0: Disable connection pooling (each request gets a new connection)
    # - 600: Reuse connections for 10 minutes (recommended for production)
    # - None: Keep connections open indefinitely (not recommended)
    conn_max_age = env.int("DB_CONN_MAX_AGE", default=600)

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
            "CONN_MAX_AGE": conn_max_age,  # Connection pooling for production
            "OPTIONS": {
                "connect_timeout": 10,
                # Connection pool settings (via psycopg2)
                # These are applied at the psycopg2 level
                "keepalives": 1,  # Send keepalive packets every 1 second
                "keepalives_idle": 30,  # Start sending keepalives after 30 seconds of inactivity
                "keepalives_interval": 10,  # Interval between keepalive packets
                "keepalives_count": 5,  # Number of keepalive packets before considering connection dead
            },
        }
    }

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
    import socket
    try:
        socket.gethostbyname("redis-queue")
        REDIS_QUEUE_URL = "redis://redis-queue:6379/0"
    except socket.gaierror:
        REDIS_QUEUE_URL = "redis://localhost:6380/0"

# Redis Events Instance - Event bus (Pub/Sub, Streams)
REDIS_EVENTS_URL = env("REDIS_EVENTS_URL", default=None)
if REDIS_EVENTS_URL is None:
    # Fallback: use service name redis-events (Docker) or localhost (local)
    import socket
    try:
        socket.gethostbyname("redis-events")
        REDIS_EVENTS_URL = "redis://redis-events:6379/0"
    except socket.gaierror:
        REDIS_EVENTS_URL = "redis://localhost:6381/0"

# Redis Channels Instance - WebSocket channels (Django Channels)
REDIS_CHANNELS_URL = env("REDIS_CHANNELS_URL", default=None)
if REDIS_CHANNELS_URL is None:
    # Fallback: use service name redis-channels (Docker) or localhost (local)
    import socket
    try:
        socket.gethostbyname("redis-channels")
        REDIS_CHANNELS_URL = "redis://redis-channels:6379/0"
    except socket.gaierror:
        REDIS_CHANNELS_URL = "redis://localhost:6382/0"
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

# Channel Layers Configuration (for WebSocket support)
# Parse REDIS_CHANNELS_URL for channel layers
_redis_channels_host = "localhost"
_redis_channels_port = 6382
if REDIS_CHANNELS_URL:
    try:
        # Parse redis://host:port/db format
        parts = REDIS_CHANNELS_URL.replace("redis://", "").split("/")
        host_port = parts[0].split(":")
        _redis_channels_host = host_port[0]
        if len(host_port) > 1:
            _redis_channels_port = int(host_port[1])
    except Exception:
        # Fallback to defaults
        pass

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
else:
    # Use Redis channel layer for production (separate Redis instance for channels)
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [(_redis_channels_host, _redis_channels_port)],
                "capacity": 1000,  # Maximum number of messages to buffer
                "expiry": 10,  # Message expiry in seconds
            },
        },
    }

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
    except Exception:
        # Fallback to defaults
        pass

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
    "TRANSFORMATION_PIPELINE_EXECUTION": "NORMAL",
    "VIRTUAL_QUERY_EXECUTION": "NORMAL",
    # LOW priority: Quick validation jobs
    "CONTRACT_VALIDATION": "LOW",
}

# Job Retry Configuration
# Maximum retry attempts per job type
JOB_RETRY_MAX_ATTEMPTS = {
    'DQ_RUN': env.int("JOB_RETRY_MAX_ATTEMPTS_DQ_RUN", default=3),
    'COMPLIANCE_RUN': env.int("JOB_RETRY_MAX_ATTEMPTS_COMPLIANCE_RUN", default=3),
    'CONTRACT_VALIDATION': env.int("JOB_RETRY_MAX_ATTEMPTS_CONTRACT_VALIDATION", default=2),
    'SEMANTIC_MAPPING': env.int("JOB_RETRY_MAX_ATTEMPTS_SEMANTIC_MAPPING", default=2),
    'CONTRACT_MIGRATION': env.int("JOB_RETRY_MAX_ATTEMPTS_CONTRACT_MIGRATION", default=1),
    'SCHEDULED_INGESTION': env.int("JOB_RETRY_MAX_ATTEMPTS_SCHEDULED_INGESTION", default=2),
    'RETENTION_POLICY_ENFORCEMENT': env.int("JOB_RETRY_MAX_ATTEMPTS_RETENTION_POLICY_ENFORCEMENT", default=1),
    'SEARCH_INDEX_UPDATE': env.int("JOB_RETRY_MAX_ATTEMPTS_SEARCH_INDEX_UPDATE", default=2),
    'ODPS_NORMALIZATION': env.int("JOB_RETRY_MAX_ATTEMPTS_ODPS_NORMALIZATION", default=2),
    'ODPS_REF_RESOLUTION': env.int("JOB_RETRY_MAX_ATTEMPTS_ODPS_REF_RESOLUTION", default=2),
    'ODPS_EXPORT': env.int("JOB_RETRY_MAX_ATTEMPTS_ODPS_EXPORT", default=2),
    'ODPS_SEMANTIC_MAPPING': env.int("JOB_RETRY_MAX_ATTEMPTS_ODPS_SEMANTIC_MAPPING", default=2),
    'ODPS_LINKING': env.int("JOB_RETRY_MAX_ATTEMPTS_ODPS_LINKING", default=2),
    'TRANSFORMATION_PIPELINE_EXECUTION': env.int("JOB_RETRY_MAX_ATTEMPTS_TRANSFORMATION_PIPELINE_EXECUTION", default=2),
    'VIRTUAL_QUERY_EXECUTION': env.int("JOB_RETRY_MAX_ATTEMPTS_VIRTUAL_QUERY_EXECUTION", default=2),
}

# Initial delay before first retry per job type (in seconds)
JOB_RETRY_INITIAL_DELAY = {
    'DQ_RUN': env.int("JOB_RETRY_INITIAL_DELAY_DQ_RUN", default=60),
    'COMPLIANCE_RUN': env.int("JOB_RETRY_INITIAL_DELAY_COMPLIANCE_RUN", default=60),
    'CONTRACT_VALIDATION': env.int("JOB_RETRY_INITIAL_DELAY_CONTRACT_VALIDATION", default=30),
    'SEMANTIC_MAPPING': env.int("JOB_RETRY_INITIAL_DELAY_SEMANTIC_MAPPING", default=30),
    'CONTRACT_MIGRATION': env.int("JOB_RETRY_INITIAL_DELAY_CONTRACT_MIGRATION", default=60),
    'SCHEDULED_INGESTION': env.int("JOB_RETRY_INITIAL_DELAY_SCHEDULED_INGESTION", default=120),
    'RETENTION_POLICY_ENFORCEMENT': env.int("JOB_RETRY_INITIAL_DELAY_RETENTION_POLICY_ENFORCEMENT", default=60),
    'SEARCH_INDEX_UPDATE': env.int("JOB_RETRY_INITIAL_DELAY_SEARCH_INDEX_UPDATE", default=30),
    'ODPS_NORMALIZATION': env.int("JOB_RETRY_INITIAL_DELAY_ODPS_NORMALIZATION", default=60),
    'ODPS_REF_RESOLUTION': env.int("JOB_RETRY_INITIAL_DELAY_ODPS_REF_RESOLUTION", default=60),
    'ODPS_EXPORT': env.int("JOB_RETRY_INITIAL_DELAY_ODPS_EXPORT", default=30),
    'ODPS_SEMANTIC_MAPPING': env.int("JOB_RETRY_INITIAL_DELAY_ODPS_SEMANTIC_MAPPING", default=60),
    'ODPS_LINKING': env.int("JOB_RETRY_INITIAL_DELAY_ODPS_LINKING", default=30),
    'TRANSFORMATION_PIPELINE_EXECUTION': env.int("JOB_RETRY_INITIAL_DELAY_TRANSFORMATION_PIPELINE_EXECUTION", default=60),
    'VIRTUAL_QUERY_EXECUTION': env.int("JOB_RETRY_INITIAL_DELAY_VIRTUAL_QUERY_EXECUTION", default=60),
}

# Maximum delay cap per job type (in seconds)
JOB_RETRY_MAX_DELAY = {
    'DQ_RUN': env.int("JOB_RETRY_MAX_DELAY_DQ_RUN", default=3600),
    'COMPLIANCE_RUN': env.int("JOB_RETRY_MAX_DELAY_COMPLIANCE_RUN", default=3600),
    'CONTRACT_VALIDATION': env.int("JOB_RETRY_MAX_DELAY_CONTRACT_VALIDATION", default=600),
    'SEMANTIC_MAPPING': env.int("JOB_RETRY_MAX_DELAY_SEMANTIC_MAPPING", default=600),
    'CONTRACT_MIGRATION': env.int("JOB_RETRY_MAX_DELAY_CONTRACT_MIGRATION", default=1800),
    'SCHEDULED_INGESTION': env.int("JOB_RETRY_MAX_DELAY_SCHEDULED_INGESTION", default=3600),
    'RETENTION_POLICY_ENFORCEMENT': env.int("JOB_RETRY_MAX_DELAY_RETENTION_POLICY_ENFORCEMENT", default=1800),
    'SEARCH_INDEX_UPDATE': env.int("JOB_RETRY_MAX_DELAY_SEARCH_INDEX_UPDATE", default=600),
    'ODPS_NORMALIZATION': env.int("JOB_RETRY_MAX_DELAY_ODPS_NORMALIZATION", default=1800),
    'ODPS_REF_RESOLUTION': env.int("JOB_RETRY_MAX_DELAY_ODPS_REF_RESOLUTION", default=1800),
    'ODPS_EXPORT': env.int("JOB_RETRY_MAX_DELAY_ODPS_EXPORT", default=600),
    'ODPS_SEMANTIC_MAPPING': env.int("JOB_RETRY_MAX_DELAY_ODPS_SEMANTIC_MAPPING", default=1800),
    'ODPS_LINKING': env.int("JOB_RETRY_MAX_DELAY_ODPS_LINKING", default=600),
    'TRANSFORMATION_PIPELINE_EXECUTION': env.int("JOB_RETRY_MAX_DELAY_TRANSFORMATION_PIPELINE_EXECUTION", default=1800),
    'VIRTUAL_QUERY_EXECUTION': env.int("JOB_RETRY_MAX_DELAY_VIRTUAL_QUERY_EXECUTION", default=1800),
}

# Exponential backoff factor per job type
JOB_RETRY_BACKOFF_FACTOR = {
    'DQ_RUN': env.float("JOB_RETRY_BACKOFF_FACTOR_DQ_RUN", default=2.0),
    'COMPLIANCE_RUN': env.float("JOB_RETRY_BACKOFF_FACTOR_COMPLIANCE_RUN", default=2.0),
    'CONTRACT_VALIDATION': env.float("JOB_RETRY_BACKOFF_FACTOR_CONTRACT_VALIDATION", default=2.0),
    'SEMANTIC_MAPPING': env.float("JOB_RETRY_BACKOFF_FACTOR_SEMANTIC_MAPPING", default=2.0),
    'CONTRACT_MIGRATION': env.float("JOB_RETRY_BACKOFF_FACTOR_CONTRACT_MIGRATION", default=2.0),
    'SCHEDULED_INGESTION': env.float("JOB_RETRY_BACKOFF_FACTOR_SCHEDULED_INGESTION", default=2.0),
    'RETENTION_POLICY_ENFORCEMENT': env.float("JOB_RETRY_BACKOFF_FACTOR_RETENTION_POLICY_ENFORCEMENT", default=2.0),
    'SEARCH_INDEX_UPDATE': env.float("JOB_RETRY_BACKOFF_FACTOR_SEARCH_INDEX_UPDATE", default=2.0),
    'ODPS_NORMALIZATION': env.float("JOB_RETRY_BACKOFF_FACTOR_ODPS_NORMALIZATION", default=2.0),
    'ODPS_REF_RESOLUTION': env.float("JOB_RETRY_BACKOFF_FACTOR_ODPS_REF_RESOLUTION", default=2.0),
    'ODPS_EXPORT': env.float("JOB_RETRY_BACKOFF_FACTOR_ODPS_EXPORT", default=2.0),
    'ODPS_SEMANTIC_MAPPING': env.float("JOB_RETRY_BACKOFF_FACTOR_ODPS_SEMANTIC_MAPPING", default=2.0),
    'ODPS_LINKING': env.float("JOB_RETRY_BACKOFF_FACTOR_ODPS_LINKING", default=2.0),
    'TRANSFORMATION_PIPELINE_EXECUTION': env.float("JOB_RETRY_BACKOFF_FACTOR_TRANSFORMATION_PIPELINE_EXECUTION", default=2.0),
    'VIRTUAL_QUERY_EXECUTION': env.float("JOB_RETRY_BACKOFF_FACTOR_VIRTUAL_QUERY_EXECUTION", default=2.0),
}

# S3/MinIO Configuration
USE_S3 = env.bool("USE_S3", default=True)
if USE_S3:
    # Only detect staging in test mode to avoid affecting production
    is_test_env = "test" in sys.argv or "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST")
    if is_test_env:
        staging_detected = _detect_staging_for_tests()
    else:
        staging_detected = False  # Production defaults to non-staging

    # Environment variables always take precedence
    env_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    env_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')

    # Determine default S3 endpoint first
    is_in_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER') == 'true'
    is_test_env = "test" in sys.argv or "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST")

    if staging_detected:
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
        AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="minio123")

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

# File Upload Configuration
MAX_BROWSER_UPLOAD_SIZE = env.int("MAX_BROWSER_UPLOAD_SIZE", default=100 * 1024 * 1024)  # 100MB
MAX_SDK_UPLOAD_SIZE = env.int("MAX_SDK_UPLOAD_SIZE", default=5 * 1024 * 1024 * 1024)  # 5GB
MAX_FILE_SIZE = env.int("MAX_FILE_SIZE", default=10 * 1024 * 1024 * 1024)  # 10GB
ALLOWED_FILE_TYPES = env.list(
    "ALLOWED_FILE_TYPES", default=["csv", "json", "parquet", "txt", "xlsx", "xls"]
)

# DataContract CLI Service Configuration
DATACONTRACT_SERVICE_URL = env(
    "DATACONTRACT_SERVICE_URL", default="http://datacontract-service:8080"
)
DATACONTRACT_SERVICE_TIMEOUT = env.int("DATACONTRACT_SERVICE_TIMEOUT", default=60)
DATACONTRACT_VALIDATION_SYNC_SIZE_LIMIT = env.int(
    "DATACONTRACT_VALIDATION_SYNC_SIZE_LIMIT", default=100 * 1024
)  # 100KB

# Email Service Configuration
# EMAIL_BACKEND: 'sendgrid', 'ses', or 'smtp'
EMAIL_BACKEND = env("EMAIL_BACKEND", default="smtp")

# Base URL for email links
EMAIL_BASE_URL = env("EMAIL_BASE_URL", default="http://localhost:8000")

# SendGrid Configuration
SENDGRID_API_KEY = env("SENDGRID_API_KEY", default=None)
SENDGRID_FROM_EMAIL = env("SENDGRID_FROM_EMAIL", default=None)
SENDGRID_FROM_NAME = env("SENDGRID_FROM_NAME", default="Data Interoperability Hub")

# AWS SES Configuration
AWS_SES_REGION = env("AWS_SES_REGION", default=None)
AWS_SES_FROM_EMAIL = env("AWS_SES_FROM_EMAIL", default=None)
AWS_SES_FROM_NAME = env("AWS_SES_FROM_NAME", default="Data Interoperability Hub")

# SMTP Configuration
SMTP_HOST = env("SMTP_HOST", default="localhost")
SMTP_PORT = env.int("SMTP_PORT", default=587)
SMTP_USERNAME = env("SMTP_USERNAME", default=None)
SMTP_PASSWORD = env("SMTP_PASSWORD", default=None)
SMTP_USE_TLS = env.bool("SMTP_USE_TLS", default=True)
SMTP_USE_SSL = env.bool("SMTP_USE_SSL", default=False)
SMTP_FROM_EMAIL = env("SMTP_FROM_EMAIL", default=None)
SMTP_FROM_NAME = env("SMTP_FROM_NAME", default="Data Interoperability Hub")

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

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

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
    "PAGE_SIZE": 20,
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
}

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
    ],
    # Note: Custom Error schema removed - using inline serializers in views instead
    # APPEND_COMPONENTS with dict-based schemas causes 'dict' object has no attribute 'request_only' error
    # Error schemas are now defined inline in views using inline_serializer
}

# CORS Configuration
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=[
        "http://localhost:3000",
        "http://localhost:8000",
    ],
)
CORS_ALLOW_CREDENTIALS = True

# JWT Configuration
JWT_SECRET_KEY = env("JWT_SECRET_KEY", default="dev-jwt-secret-key-not-for-production")
JWT_ALGORITHM = env("JWT_ALGORITHM", default="HS256")
JWT_ACCESS_TOKEN_EXPIRY = env.int("JWT_ACCESS_TOKEN_EXPIRY", default=3600)  # 1 hour
JWT_REFRESH_TOKEN_EXPIRY = env.int("JWT_REFRESH_TOKEN_EXPIRY", default=86400)  # 24 hours
JWT_ISSUER = env("JWT_ISSUER", default="hub")

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

# OpenTelemetry Metrics Configuration
# Migrated from django-prometheus (not compatible with Django 6.0) to OpenTelemetry metrics
OPENTELEMETRY_METRICS_ENABLED = env.bool("OPENTELEMETRY_METRICS_ENABLED", default=True)
OPENTELEMETRY_METRICS_EXPORT_INTERVAL_MS = env.int(
    "OPENTELEMETRY_METRICS_EXPORT_INTERVAL_MS", default=10000
)  # 10 seconds

# OpenTelemetry Tracing Configuration
# Use the new unified configuration module
OPENTELEMETRY_ENABLED = env.bool("OPENTELEMETRY_ENABLED", default=False)
OPENTELEMETRY_EXPORTER = env.str("OPENTELEMETRY_EXPORTER", default="otlp")  # 'otlp' or 'jaeger'
OTEL_SERVICE_NAME = env.str("OTEL_SERVICE_NAME", default="data-interoperability-hub-api")
OTEL_EXPORTER_OTLP_ENDPOINT = env.str("OTEL_EXPORTER_OTLP_ENDPOINT", default="http://localhost:4317")
OTEL_EXPORTER_OTLP_PROTOCOL = env.str("OTEL_EXPORTER_OTLP_PROTOCOL", default="grpc")  # 'grpc' or 'http/protobuf'

# Database query instrumentation threshold (milliseconds)
OTEL_DB_SLOW_QUERY_THRESHOLD_MS = env.float("OTEL_DB_SLOW_QUERY_THRESHOLD_MS", default=100.0)

# Trace Sampling Configuration
# Base sampling rate for successful requests (default: 10% = 0.1)
# Errors are always sampled (100%) via middleware
# Critical endpoints are always sampled (100%) via adaptive sampler
OTEL_TRACES_SAMPLER_ARG = env.float("OTEL_TRACES_SAMPLER_ARG", default=0.1)  # 10% for successful requests

if OPENTELEMETRY_ENABLED:
    from hub.apps.observability.otel_config import setup_opentelemetry_tracing
    setup_opentelemetry_tracing()

# OpenTelemetry Metrics Setup (will be initialized in hub/apps/observability/otel_metrics.py)
# Metrics are exported to Prometheus format via /metrics endpoint

# File Upload Limits
MAX_BROWSER_UPLOAD_SIZE_BYTES = env.int("MAX_BROWSER_UPLOAD_SIZE_BYTES", default=1073741824)  # 1 GB
MAX_SDK_UPLOAD_SIZE_BYTES = env.int("MAX_SDK_UPLOAD_SIZE_BYTES", default=10737418240)  # 10 GB
SIMPLE_UPLOAD_THRESHOLD_BYTES = env.int("SIMPLE_UPLOAD_THRESHOLD_BYTES", default=67108864)  # 64 MB

# Job Timeouts
JOB_TIMEOUT_DQ_RUN = env.int("JOB_TIMEOUT_DQ_RUN", default=1800)  # 30 minutes
JOB_TIMEOUT_COMPLIANCE_RUN = env.int("JOB_TIMEOUT_COMPLIANCE_RUN", default=1800)  # 30 minutes
JOB_TIMEOUT_CONTRACT_VALIDATION = env.int("JOB_TIMEOUT_CONTRACT_VALIDATION", default=60)  # 1 minute
JOB_TIMEOUT_SEMANTIC_MAPPING = env.int("JOB_TIMEOUT_SEMANTIC_MAPPING", default=300)  # 5 minutes

# External Service URLs
# In test environments, use localhost with correct port
# For staging: datacontract-service uses port 8092 externally
# For default: datacontract-service uses port 8080 externally
_default_datacontract_url = "http://datacontract-service:8080"
# Detect test environment and use localhost with appropriate port
if "pytest" in sys.modules or "unittest" in sys.modules or os.getenv("TESTING"):
    # Try to detect staging vs default by checking port availability
    try:
        import httpx

        # Check if staging port is accessible
        response = httpx.get("http://localhost:8092/health", timeout=1)
        if response.status_code == 200:
            _default_datacontract_url = "http://localhost:8092"
        else:
            _default_datacontract_url = "http://localhost:8080"
    except Exception:
        # Default to standard port if detection fails
        _default_datacontract_url = "http://localhost:8080"

DATACONTRACT_CLI_SERVICE_URL = env(
    "DATACONTRACT_CLI_SERVICE_URL", default=_default_datacontract_url
)
DATACONTRACT_CLI_TIMEOUT = env.int("DATACONTRACT_CLI_TIMEOUT", default=60)
DQ_SERVICE_URL = env("DQ_SERVICE_URL", default="http://dq-service:8083")
DQ_SERVICE_TIMEOUT = env.int("DQ_SERVICE_TIMEOUT", default=1800)  # 30 minutes
DQ_RESULT_CACHE_TTL = env.int("DQ_RESULT_CACHE_TTL", default=3600)  # 1 hour

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
# Detect test environment and use localhost with appropriate port
if "pytest" in sys.modules or "unittest" in sys.modules or os.getenv("TESTING"):
    # In test environment, use localhost with external port (8097)
    _default_odh_inference_url = "http://localhost:8097"
else:
    # In Docker, use service name with internal port
    _default_odh_inference_url = "http://odh-inference-scheduler:8080"

ODH_INFERENCE_SCHEDULER_URL = env("ODH_INFERENCE_SCHEDULER_URL", default=_default_odh_inference_url)
COMPLIANCE_SERVICE_URL = env("COMPLIANCE_SERVICE_URL", default="http://compliance-service:8082")
COMPLIANCE_SERVICE_TIMEOUT = env.int("COMPLIANCE_SERVICE_TIMEOUT", default=1800)  # 30 minutes

# Semantic Service Configuration
SEMANTIC_SERVICE_URL = env("SEMANTIC_SERVICE_URL", default="http://semantic-service:8081")
SEMANTIC_SERVICE_TIMEOUT = env.int("SEMANTIC_SERVICE_TIMEOUT", default=60)  # 1 minute
HUB_DOMAIN = env("HUB_DOMAIN", default="hub.example.com")

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
SPARQL_QUERY_COMPLEXITY_LIMIT = env.int("SPARQL_QUERY_COMPLEXITY_LIMIT", default=20)  # Complexity score limit

# Search Query Configuration
SEARCH_QUERY_MAX_LENGTH = env.int("SEARCH_QUERY_MAX_LENGTH", default=1000)  # Maximum query length in characters
SEARCH_QUERY_COMPLEXITY_LIMIT = env.int("SEARCH_QUERY_COMPLEXITY_LIMIT", default=50)  # Complexity score limit
SEARCH_QUERY_MIN_LENGTH = env.int("SEARCH_QUERY_MIN_LENGTH", default=1)  # Minimum query length

# GraphQL Configuration
GRAPHQL_QUERY_COMPLEXITY_LIMIT = env.int("GRAPHQL_QUERY_COMPLEXITY_LIMIT", default=1000)

# Security
ENCRYPTION_KEY = env("ENCRYPTION_KEY", default="dev-encryption-key-not-for-production")
PII_REDACTION_ENABLED = env.bool("PII_REDACTION_ENABLED", default=True)

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
    "CSRF_COOKIE_HTTPONLY", default=False
)  # Set to True for better security
CSRF_COOKIE_SAMESITE = env(
    "CSRF_COOKIE_SAMESITE", default="Lax"
)  # Options: 'Strict', 'Lax', 'None'
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# Session Security
SESSION_COOKIE_HTTPONLY = env.bool("SESSION_COOKIE_HTTPONLY", default=True)
SESSION_COOKIE_SAMESITE = env("SESSION_COOKIE_SAMESITE", default="Lax")
SESSION_COOKIE_AGE = env.int("SESSION_COOKIE_AGE", default=1209600)  # 2 weeks default

# GraphQL Settings
GRAPHQL_QUERY_COMPLEXITY_LIMIT = env.int("GRAPHQL_QUERY_COMPLEXITY_LIMIT", default=1000)

# Rate Limiting
# Advanced rate limiting with sliding window algorithm
# See hub/apps/rate_limiting/config.py for platform defaults and maximums
RATE_LIMIT_ENABLED = env.bool("RATE_LIMIT_ENABLED", default=True)

# Legacy settings (kept for backward compatibility, but not used by new middleware)
RATE_LIMIT_PER_TENANT = env.int("RATE_LIMIT_PER_TENANT", default=200)
RATE_LIMIT_PER_USER = env.int("RATE_LIMIT_PER_USER", default=100)

# ODPS $ref Cache Warming Configuration (Task 9.8.4.3)
ODPS_CACHE_WARMING_ENABLED = env.bool("ODPS_CACHE_WARMING_ENABLED", default=True)
ODPS_CACHE_WARMING_STARTUP_ENABLED = env.bool("ODPS_CACHE_WARMING_STARTUP_ENABLED", default=True)
ODPS_CACHE_WARMING_SCHEDULED_ENABLED = env.bool("ODPS_CACHE_WARMING_SCHEDULED_ENABLED", default=True)
ODPS_CACHE_WARMING_STARTUP_LIMIT = env.int("ODPS_CACHE_WARMING_STARTUP_LIMIT", default=100)
ODPS_CACHE_WARMING_SCHEDULED_LIMIT = env.int("ODPS_CACHE_WARMING_SCHEDULED_LIMIT", default=1000)
ODPS_CACHE_WARMING_BATCH_SIZE = env.int("ODPS_CACHE_WARMING_BATCH_SIZE", default=10)
