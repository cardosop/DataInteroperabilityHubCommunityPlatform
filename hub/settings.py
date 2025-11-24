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
    'hub.apps.api.middleware.RateLimitMiddleware',  # Rate limiting
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
# For tests, use SQLite in-memory database
import sys
if 'test' in sys.argv or 'pytest' in sys.modules:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
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
REDIS_URL = env('REDIS_URL', default='redis://localhost:6379/0')
RQ_QUEUES = {
    'default': {
        'URL': REDIS_URL,
        'DEFAULT_TIMEOUT': 360,
        'DEFAULT_RESULT_TTL': 500,
    },
    'high': {
        'URL': REDIS_URL,
        'DEFAULT_TIMEOUT': 1800,  # 30 minutes for DQ/compliance runs
    },
    'low': {
        'URL': REDIS_URL,
        'DEFAULT_TIMEOUT': 60,
    },
}

# S3/MinIO Configuration
USE_S3 = env.bool('USE_S3', default=True)
if USE_S3:
    AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID', default='minio')
    AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY', default='minio123')
    AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME', default='hub-files')
    AWS_S3_ENDPOINT_URL = env('AWS_S3_ENDPOINT_URL', default='http://minio:9000')
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
    'COMPONENT_SPLIT_REQUEST': True,
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
    # Add custom Error schema component
    'APPEND_COMPONENTS': {
        'schemas': {
            'Error': {
                'type': 'object',
                'properties': {
                    'error': {
                        'type': 'object',
                        'properties': {
                            'code': {'type': 'string', 'description': 'Error code'},
                            'message': {'type': 'string', 'description': 'Human-readable error message'},
                            'http_status': {'type': 'integer', 'description': 'HTTP status code'},
                            'request_id': {'type': 'string', 'format': 'uuid', 'description': 'Request ID for tracing'},
                            'timestamp': {'type': 'string', 'format': 'date-time', 'description': 'Error timestamp'},
                            'details': {'type': 'object', 'description': 'Additional error details'},
                        },
                        'required': ['code', 'message', 'http_status', 'request_id', 'timestamp'],
                    },
                },
                'required': ['error'],
            },
        },
    },
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
RATE_LIMIT_ENABLED = env.bool('RATE_LIMIT_ENABLED', default=True)
RATE_LIMIT_PER_TENANT = env.int('RATE_LIMIT_PER_TENANT', default=200)
RATE_LIMIT_PER_USER = env.int('RATE_LIMIT_PER_USER', default=100)

