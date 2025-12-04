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
    SECRET_KEY=(str, ''),
    ALLOWED_HOSTS=(list, []),
)

# Read .env file
environ.Env.read_env(os.path.join(BASE_DIR, '.env.dev'))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY', default='dev-secret-key-not-for-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env('DEBUG', default=True)

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1', 'api-service'])

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'rest_framework',
    'drf_spectacular',  # OpenAPI 3.0 schema generation
    'corsheaders',
    'django_rq',
    'strawberry.django',
    'django_structlog',
    'django_prometheus',
    
    # Local apps
    'hub.apps.tenants',
    'hub.apps.users',
    'hub.apps.auth',
    'hub.apps.audit',
    'hub.apps.files',
    'hub.apps.datasets',
    'hub.apps.assets',
    'hub.apps.jobs',
    'hub.apps.contracts',
    'hub.apps.dq',
    'hub.apps.compliance',
    'hub.apps.semantic',
    'hub.apps.marketplace',
    # 'hub.apps.marketplace',
    'hub.apps.api',
    'hub.apps.graphql',
    'hub.apps.health',
    'hub.apps.observability',
    'hub.apps.notifications',
    'hub.apps.rate_limiting',
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'hub.apps.observability.middleware.MetricsMiddleware',  # Custom metrics middleware
    'django_structlog.middlewares.request.RequestMiddleware',
    'hub.apps.api.middleware.RequestIDMiddleware',  # Request ID generation
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'hub.apps.auth.middleware.TenantScopingMiddleware',  # Tenant scoping after authentication
    'hub.apps.tenants.middleware.TenantSuspensionMiddleware',  # Tenant suspension enforcement
    'hub.apps.rate_limiting.middleware.RateLimitMiddleware',  # Advanced rate limiting (replaces basic middleware)
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

ROOT_URLCONF = 'hub.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'hub.wsgi.application'

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
    test_env = os.getenv('TEST_ENVIRONMENT', '').lower()
    if test_env == 'staging':
        return True
    if test_env == 'default':
        return False
    
    # Auto-detect by checking staging API port
    try:
        import httpx
        response = httpx.get("http://localhost:8001/health", timeout=1)
        if response.status_code in [200, 503]:
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
if 'test' in sys.argv or 'pytest' in sys.modules:
    import django.db.backends.base.base
    _original_validate = django.db.backends.base.base.BaseDatabaseWrapper.validate_thread_sharing
    
    def _noop_validate_thread_sharing(self):
        """Disable thread validation for tests - safe because pytest-django manages connections"""
        pass
    
    django.db.backends.base.base.BaseDatabaseWrapper.validate_thread_sharing = _noop_validate_thread_sharing

if 'test' in sys.argv or 'pytest' in sys.modules:
    # Try to use PostgreSQL for tests (better for threading and transaction handling)
    try:
        import psycopg2
        from psycopg2 import extensions as psycopg2_extensions
        import os
        
        # Detect staging environment for tests
        # Check if staging API port is accessible (indicates staging environment)
        staging_detected = False
        try:
            import httpx
            response = httpx.get("http://localhost:8001/health", timeout=1)
            if response.status_code in [200, 503]:  # 503 is OK - service might be unhealthy but exists
                staging_detected = True
        except Exception:
            pass
        
        postgres_host = os.getenv('POSTGRES_HOST', 'localhost')
        postgres_db = os.getenv('POSTGRES_DB', 'hub_staging' if staging_detected else 'hub')
        postgres_user = os.getenv('POSTGRES_USER', 'hub_staging' if staging_detected else 'hub')
        postgres_password = os.getenv('POSTGRES_PASSWORD', 'hub_staging_secure' if staging_detected else 'hub')
        # Use staging port if staging detected, otherwise default
        default_port = '5433' if staging_detected else '5432'
        postgres_port = os.getenv('POSTGRES_PORT', default_port)
        
        # Try to connect to verify PostgreSQL is available
        test_conn = psycopg2.connect(
            host=postgres_host,
            port=postgres_port,
            database=postgres_db,
            user=postgres_user,
            password=postgres_password,
            connect_timeout=2
        )
        test_conn.close()
        
        # Use PostgreSQL for tests - supports proper transaction handling
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': postgres_db + '_test',
                'USER': postgres_user,
                'PASSWORD': postgres_password,
                'HOST': postgres_host,
                'PORT': postgres_port,
                'TEST': {
                    'NAME': postgres_db + '_test',
                    'SERIALIZE': False,  # Allow parallel test execution
                    'MIGRATE': False,  # Disable automatic migrations - we'll run them manually via pytest hook
                },
                'CONN_MAX_AGE': 0,  # Don't reuse connections in tests
                'OPTIONS': {
                    # Disable thread validation for tests (pytest-django uses multiple threads)
                    # This is safe in test environment where we control thread usage
                    'connect_timeout': 10,
                    # CRITICAL: Set transaction isolation level to READ COMMITTED for LiveServerTestCase
                    # This ensures data committed in one thread is immediately visible to other threads
                    # Without this, the server thread might not see data created in the test thread
                    'isolation_level': psycopg2_extensions.ISOLATION_LEVEL_READ_COMMITTED,
                },
            }
        }
        
        # Disable database connection thread validation for tests
        # pytest-django creates connections in one thread but TestCase uses them in another
        # This is safe because pytest-django manages the connection lifecycle properly
        import django.db.backends.base.base
        original_validate_thread_sharing = django.db.backends.base.base.BaseDatabaseWrapper.validate_thread_sharing
        
        def noop_validate_thread_sharing(self):
            """Disable thread validation for tests"""
            pass
        
        django.db.backends.base.base.BaseDatabaseWrapper.validate_thread_sharing = noop_validate_thread_sharing
    except Exception:
        # Fallback to SQLite - use file-based (not in-memory) for proper threading
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db_test.sqlite3',
                'OPTIONS': {
                    'timeout': 20,
                },
                'TEST': {
                    'NAME': BASE_DIR / 'db_test.sqlite3',
                    'SERIALIZE': False,
                },
            }
        }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': env('POSTGRES_DB', default='hub'),
            'USER': env('POSTGRES_USER', default='hub'),
            'PASSWORD': env('POSTGRES_PASSWORD', default='hub'),
            'HOST': env('POSTGRES_HOST', default='localhost'),  # Use 'localhost' for local dev, 'postgres' for Docker
            'PORT': env('POSTGRES_PORT', default='5432'),
            'OPTIONS': {
                'connect_timeout': 10,
            },
        }
    }

# Redis Configuration (for django-rq)
# When running locally (outside Docker), use 'localhost'
# When running in Docker, use 'redis' (service name)
# For staging, use port 6380 instead of 6379
# Only detect staging in test mode to avoid affecting production
is_test_env = 'test' in sys.argv or 'pytest' in sys.modules or os.getenv('PYTEST_CURRENT_TEST')
if is_test_env:
    staging_detected = _detect_staging_for_tests()
    default_redis_port = '6380' if staging_detected else '6379'
else:
    # Production/default: use standard port
    default_redis_port = '6379'
REDIS_URL = env('REDIS_URL', default=f'redis://localhost:{default_redis_port}/0')
# RQ Queue Configuration
# Priority queues: job_critical (HIGH), job_default (NORMAL), job_low (LOW)
# See design.md Decision 3 for priority queue implementation details
RQ_QUEUES = {
    'job_critical': {  # HIGH priority queue
        'URL': REDIS_URL,
        'DEFAULT_TIMEOUT': 1800,  # 30 minutes for DQ/compliance runs
        'DEFAULT_RESULT_TTL': 500,
    },
    'job_default': {  # NORMAL priority queue
        'URL': REDIS_URL,
        'DEFAULT_TIMEOUT': 360,  # 6 minutes default
        'DEFAULT_RESULT_TTL': 500,
    },
    'job_low': {  # LOW priority queue
        'URL': REDIS_URL,
        'DEFAULT_TIMEOUT': 60,  # 1 minute for quick jobs
        'DEFAULT_RESULT_TTL': 500,
    },
    # Legacy 'default' queue for backward compatibility (maps to job_default)
    'default': {
        'URL': REDIS_URL,
        'DEFAULT_TIMEOUT': 360,
        'DEFAULT_RESULT_TTL': 500,
    },
}

# Worker Configuration
# Worker concurrency limits
WORKER_MAX_CONCURRENCY = env.int('WORKER_MAX_CONCURRENCY', default=4)
WORKER_MAX_CONCURRENCY_PER_TENANT = env.int('WORKER_MAX_CONCURRENCY_PER_TENANT', default=2)

# Priority queue configuration
# Reserved slots: Fraction of max concurrency reserved for HIGH priority jobs (default: 50%)
WORKER_RESERVED_SLOTS_RATIO = env.float('WORKER_RESERVED_SLOTS_RATIO', default=0.5)
WORKER_RESERVED_SLOTS = max(1, int(WORKER_MAX_CONCURRENCY * WORKER_RESERVED_SLOTS_RATIO))
WORKER_SHARED_SLOTS = WORKER_MAX_CONCURRENCY - WORKER_RESERVED_SLOTS

# Starvation prevention: Elevate NORMAL priority jobs after wait time threshold (default: 5 minutes)
WORKER_STARVATION_THRESHOLD_SECONDS = env.int('WORKER_STARVATION_THRESHOLD_SECONDS', default=300)  # 5 minutes

# S3/MinIO Configuration
USE_S3 = env.bool('USE_S3', default=True)
if USE_S3:
    # Only detect staging in test mode to avoid affecting production
    is_test_env = 'test' in sys.argv or 'pytest' in sys.modules or os.getenv('PYTEST_CURRENT_TEST')
    if is_test_env:
        staging_detected = _detect_staging_for_tests()
    else:
        staging_detected = False  # Production defaults to non-staging
    
    if staging_detected:
        AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID', default='minio_staging')
        AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY', default='minio_staging_secure')
        default_s3_endpoint = 'http://localhost:9010'
    else:
        AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID', default='minio')
        AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY', default='minio123')
        # Check if we're in Docker (can resolve 'minio' hostname)
        try:
            import socket
            socket.gethostbyname('minio')
            default_s3_endpoint = 'http://minio:9000'  # In Docker, use service name
        except socket.gaierror:
            default_s3_endpoint = 'http://localhost:9000'  # Outside Docker, use localhost
    
    AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME', default='hub-files')
    AWS_S3_ENDPOINT_URL = env('AWS_S3_ENDPOINT_URL', default=default_s3_endpoint)
    AWS_S3_USE_SSL = env.bool('AWS_S3_USE_SSL', default=False)
    AWS_S3_VERIFY = env.bool('AWS_S3_VERIFY', default=False)
    AWS_DEFAULT_ACL = 'private'
    AWS_S3_OBJECT_PARAMETERS = {
        'CacheControl': 'max-age=86400',
    }
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    STATICFILES_STORAGE = 'storages.backends.s3boto3.S3StaticStorage'
else:
    # Local file storage
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'
    STATIC_URL = '/static/'
    STATIC_ROOT = BASE_DIR / 'staticfiles'

# File Upload Configuration
MAX_BROWSER_UPLOAD_SIZE = env.int('MAX_BROWSER_UPLOAD_SIZE', default=100 * 1024 * 1024)  # 100MB
MAX_SDK_UPLOAD_SIZE = env.int('MAX_SDK_UPLOAD_SIZE', default=5 * 1024 * 1024 * 1024)  # 5GB
MAX_FILE_SIZE = env.int('MAX_FILE_SIZE', default=10 * 1024 * 1024 * 1024)  # 10GB
ALLOWED_FILE_TYPES = env.list('ALLOWED_FILE_TYPES', default=['csv', 'json', 'parquet', 'txt', 'xlsx', 'xls'])

# DataContract CLI Service Configuration
DATACONTRACT_SERVICE_URL = env('DATACONTRACT_SERVICE_URL', default='http://datacontract-service:8080')
DATACONTRACT_SERVICE_TIMEOUT = env.int('DATACONTRACT_SERVICE_TIMEOUT', default=60)
DATACONTRACT_VALIDATION_SYNC_SIZE_LIMIT = env.int('DATACONTRACT_VALIDATION_SYNC_SIZE_LIMIT', default=100 * 1024)  # 100KB

# Email Service Configuration
# EMAIL_BACKEND: 'sendgrid', 'ses', or 'smtp'
EMAIL_BACKEND = env('EMAIL_BACKEND', default='smtp')

# Base URL for email links
EMAIL_BASE_URL = env('EMAIL_BASE_URL', default='http://localhost:8000')

# SendGrid Configuration
SENDGRID_API_KEY = env('SENDGRID_API_KEY', default=None)
SENDGRID_FROM_EMAIL = env('SENDGRID_FROM_EMAIL', default=None)
SENDGRID_FROM_NAME = env('SENDGRID_FROM_NAME', default='Data Interoperability Hub')

# AWS SES Configuration
AWS_SES_REGION = env('AWS_SES_REGION', default=None)
AWS_SES_FROM_EMAIL = env('AWS_SES_FROM_EMAIL', default=None)
AWS_SES_FROM_NAME = env('AWS_SES_FROM_NAME', default='Data Interoperability Hub')

# SMTP Configuration
SMTP_HOST = env('SMTP_HOST', default='localhost')
SMTP_PORT = env.int('SMTP_PORT', default=587)
SMTP_USERNAME = env('SMTP_USERNAME', default=None)
SMTP_PASSWORD = env('SMTP_PASSWORD', default=None)
SMTP_USE_TLS = env.bool('SMTP_USE_TLS', default=True)
SMTP_USE_SSL = env.bool('SMTP_USE_SSL', default=False)
SMTP_FROM_EMAIL = env('SMTP_FROM_EMAIL', default=None)
SMTP_FROM_NAME = env('SMTP_FROM_NAME', default='Data Interoperability Hub')

# Email Notification Settings
EMAIL_JOB_NOTIFICATIONS_ENABLED = env.bool('EMAIL_JOB_NOTIFICATIONS_ENABLED', default=False)

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'users.User'

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'hub.apps.auth.authentication.JWTAuthentication',
        'hub.apps.auth.authentication.APIKeyAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
    'EXCEPTION_HANDLER': 'hub.apps.api.exceptions.custom_exception_handler',
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# OpenAPI/Spectacular Configuration
SPECTACULAR_SETTINGS = {
    'TITLE': 'Interoperable Data Hub API',
    'DESCRIPTION': 'REST API v1 for Interoperable Data Hub MVP',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SCHEMA_PATH_PREFIX': '/api/v1',
    'COMPONENT_SPLIT_REQUEST': False,  # Disabled to avoid dict processing issues
    'COMPONENT_NO_READ_ONLY_REQUIRED': True,
    'TAGS': [
        {'name': 'Authentication', 'description': 'User authentication and authorization'},
        {'name': 'Tenants', 'description': 'Tenant management'},
        {'name': 'Users', 'description': 'User management'},
        {'name': 'Files', 'description': 'File storage and management'},
        {'name': 'Datasets', 'description': 'Dataset management'},
        {'name': 'Assets', 'description': 'Asset catalog management'},
        {'name': 'Contracts', 'description': 'Data contract management'},
        {'name': 'Jobs', 'description': 'Job orchestration'},
        {'name': 'Data Quality', 'description': 'Data quality checks'},
        {'name': 'Compliance', 'description': 'Compliance checks'},
        {'name': 'Semantic', 'description': 'Semantic mapping and SPARQL'},
        {'name': 'Marketplace', 'description': 'Marketplace listings, orders, and entitlements'},
        {'name': 'Audit', 'description': 'Audit logging'},
    ],
    # Note: Custom Error schema removed - using inline serializers in views instead
    # APPEND_COMPONENTS with dict-based schemas causes 'dict' object has no attribute 'request_only' error
    # Error schemas are now defined inline in views using inline_serializer
}

# CORS Configuration
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[
    'http://localhost:3000',
    'http://localhost:8000',
])
CORS_ALLOW_CREDENTIALS = True

# JWT Configuration
JWT_SECRET_KEY = env('JWT_SECRET_KEY', default='dev-jwt-secret-key-not-for-production')
JWT_ALGORITHM = env('JWT_ALGORITHM', default='HS256')
JWT_ACCESS_TOKEN_EXPIRY = env.int('JWT_ACCESS_TOKEN_EXPIRY', default=3600)  # 1 hour
JWT_REFRESH_TOKEN_EXPIRY = env.int('JWT_REFRESH_TOKEN_EXPIRY', default=86400)  # 24 hours
JWT_ISSUER = env('JWT_ISSUER', default='hub')

# Structured Logging (structlog)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            'format': '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
        },
        'console': {
            'format': '%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json' if env('LOG_FORMAT', default='json') == 'json' else 'console',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': env('LOG_LEVEL', default='INFO'),
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': env('LOG_LEVEL', default='INFO'),
            'propagate': False,
        },
        'hub': {
            'handlers': ['console'],
            'level': env('LOG_LEVEL', default='INFO'),
            'propagate': False,
        },
    },
}

# Structlog Configuration
# Import and configure structlog with enhanced processors
from hub.apps.observability.logging import configure_structlog
configure_structlog()

# Prometheus Metrics
PROMETHEUS_EXPORT_MIGRATIONS = False
if env.bool('PROMETHEUS_ENABLED', default=True):
    MIDDLEWARE.insert(0, 'django_prometheus.middleware.PrometheusBeforeMiddleware')
    MIDDLEWARE.append('django_prometheus.middleware.PrometheusAfterMiddleware')

# OpenTelemetry Configuration
OPENTELEMETRY_ENABLED = env.bool('OPENTELEMETRY_ENABLED', default=False)
if OPENTELEMETRY_ENABLED:
    from hub.apps.observability.tracing import setup_opentelemetry
    setup_opentelemetry()

# File Upload Limits
MAX_BROWSER_UPLOAD_SIZE_BYTES = env.int('MAX_BROWSER_UPLOAD_SIZE_BYTES', default=1073741824)  # 1 GB
MAX_SDK_UPLOAD_SIZE_BYTES = env.int('MAX_SDK_UPLOAD_SIZE_BYTES', default=10737418240)  # 10 GB
SIMPLE_UPLOAD_THRESHOLD_BYTES = env.int('SIMPLE_UPLOAD_THRESHOLD_BYTES', default=67108864)  # 64 MB

# Job Timeouts
JOB_TIMEOUT_DQ_RUN = env.int('JOB_TIMEOUT_DQ_RUN', default=1800)  # 30 minutes
JOB_TIMEOUT_COMPLIANCE_RUN = env.int('JOB_TIMEOUT_COMPLIANCE_RUN', default=1800)  # 30 minutes
JOB_TIMEOUT_CONTRACT_VALIDATION = env.int('JOB_TIMEOUT_CONTRACT_VALIDATION', default=60)  # 1 minute
JOB_TIMEOUT_SEMANTIC_MAPPING = env.int('JOB_TIMEOUT_SEMANTIC_MAPPING', default=300)  # 5 minutes

# External Service URLs
DATACONTRACT_CLI_SERVICE_URL = env('DATACONTRACT_CLI_SERVICE_URL', default='http://datacontract-service:8080')
DATACONTRACT_CLI_TIMEOUT = env.int('DATACONTRACT_CLI_TIMEOUT', default=60)
DQ_SERVICE_URL = env('DQ_SERVICE_URL', default='http://dq-service:8083')
DQ_SERVICE_TIMEOUT = env.int('DQ_SERVICE_TIMEOUT', default=1800)  # 30 minutes
DQ_RESULT_CACHE_TTL = env.int('DQ_RESULT_CACHE_TTL', default=3600)  # 1 hour
COMPLIANCE_SERVICE_URL = env('COMPLIANCE_SERVICE_URL', default='http://compliance-service:8082')
COMPLIANCE_SERVICE_TIMEOUT = env.int('COMPLIANCE_SERVICE_TIMEOUT', default=1800)  # 30 minutes

# Semantic Service Configuration
SEMANTIC_SERVICE_URL = env('SEMANTIC_SERVICE_URL', default='http://semantic-service:8081')
SEMANTIC_SERVICE_TIMEOUT = env.int('SEMANTIC_SERVICE_TIMEOUT', default=60)  # 1 minute
HUB_DOMAIN = env('HUB_DOMAIN', default='hub.example.com')

# SPARQL Endpoint Configuration
SPARQL_MAX_TIMEOUT = env.int('SPARQL_MAX_TIMEOUT', default=30)  # 30 seconds
SPARQL_RESULT_LIMIT = env.int('SPARQL_RESULT_LIMIT', default=10000)  # 10,000 rows

# Rate Limiting Configuration
RATE_LIMIT_ENABLED = env.bool('RATE_LIMIT_ENABLED', default=True)
RATE_LIMIT_PER_TENANT = env.int('RATE_LIMIT_PER_TENANT', default=100)  # requests per minute
RATE_LIMIT_PER_USER = env.int('RATE_LIMIT_PER_USER', default=100)  # requests per minute
RATE_LIMIT_WINDOW = env.int('RATE_LIMIT_WINDOW', default=60)  # seconds
FUSEKI_URL = env('FUSEKI_URL', default='http://fuseki:3030')
FUSEKI_DATASET = env('FUSEKI_DATASET', default='hub')

# Compliance Configuration
COMPLIANCE_PII_THRESHOLD = env.float('COMPLIANCE_PII_THRESHOLD', default=0.01)  # 1% threshold

# SPARQL Configuration
SPARQL_QUERY_TIMEOUT = env.int('SPARQL_QUERY_TIMEOUT', default=30)  # 30 seconds
SPARQL_RESULT_LIMIT = env.int('SPARQL_RESULT_LIMIT', default=10000)

# GraphQL Configuration
GRAPHQL_QUERY_COMPLEXITY_LIMIT = env.int('GRAPHQL_QUERY_COMPLEXITY_LIMIT', default=1000)

# Security
ENCRYPTION_KEY = env('ENCRYPTION_KEY', default='dev-encryption-key-not-for-production')
PII_REDACTION_ENABLED = env.bool('PII_REDACTION_ENABLED', default=True)

# Rate Limiting
# Advanced rate limiting with sliding window algorithm
# See hub/apps/rate_limiting/config.py for platform defaults and maximums
RATE_LIMIT_ENABLED = env.bool('RATE_LIMIT_ENABLED', default=True)

# Legacy settings (kept for backward compatibility, but not used by new middleware)
RATE_LIMIT_PER_TENANT = env.int('RATE_LIMIT_PER_TENANT', default=200)
RATE_LIMIT_PER_USER = env.int('RATE_LIMIT_PER_USER', default=100)

