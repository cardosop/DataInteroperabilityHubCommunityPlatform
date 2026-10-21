"""
pilot-readiness 4.1 — connector SSRF tests (marketplace/warehouse).

Adversarial URL vectors against the two connector endpoint builders the
pilot surfaces accept remote configuration for: the marketplace
connection service (create + update) and ``WarehouseConnection.save()``.
Real models, real validation — no mocks.

Attack classes (Phase-5 spec): loopback, the AWS IMDS address, RFC1918
private ranges, IPv6 loopback/mapped forms, and scheme confusion
(ftp://, file://, jdbc:) — the last one must be REJECTED by the scheme
gate, never silently skipped.

Root causes pinned here (found RED, fixed in the same task):
- marketplace ``update_connection`` had NO SSRF check (create-only);
- the marketplace URL-key list missed ``host`` (the databricks
  connector's primary field);
- scheme-confusion values (``ftp://…``) were skipped because the
  pre-fix checks only examined ``http(s)://``-prefixed values;
- ``WarehouseConnection.private_endpoint_url`` (the column) was never
  SSRF-checked — only the same-named key inside the config dict was.
"""

import uuid

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import override_settings

from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.integrations.base import MarketplaceType
from hub.apps.integrations.services import MarketplaceIntegrationService
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.warehouses.models import WarehouseConnection

pytestmark = pytest.mark.security

# IP-literal vectors — the SSRF guard's IP-literal fast path needs no
# DNS, so these are deterministic everywhere.
_BLOCKED_URLS = (
    "http://127.0.0.1:8000/",
    "http://localhost:8000/",
    "http://169.254.169.254/latest/meta-data/",
    "http://10.0.0.1/internal",
    "http://172.16.0.5/internal",
    "http://192.168.1.1/internal",
    "http://[::1]/",
    "http://[::ffff:127.0.0.1]/",
    "http://0.0.0.0/",
    "http://224.0.0.1/",
)

# Scheme confusion — non-http schemes must be rejected by the scheme
# gate, not skipped (the pre-fix "only http(s)" filter skipped them).
_SCHEME_CONFUSION = (
    "ftp://169.254.169.254/exfil",
    "file:///etc/passwd",
    "jdbc:postgresql://127.0.0.1:5432/x",
    "gopher://127.0.0.1:70/_",
)

_SAFE_URL = "https://github.com/meshant/hub"

_MARKETPLACE_URL_KEYS = (
    "url",
    "endpoint",
    "api_url",
    "base_url",
    "host_url",
    "callback_url",
    "host",
)

_WAREHOUSE_URL_KEYS = ("host", "endpoint", "api_url", "base_url", "private_endpoint_url")


@pytest.fixture
def tenant_user(db):
    tenant = Tenant.objects.create(
        name=f"ssrf-conn-{uuid.uuid4().hex[:8]}",
        slug=f"ssrf-conn-{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )
    # The marketplace service checks plan limits before the SSRF gate —
    # the standard seeded recipe (pro plan + active subscription).
    from hub.apps.tenants.models import TenantPlan
    from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

    pro_plan = TenantPlan.objects.filter(slug="pro", is_active=True).first()
    if pro_plan:
        tenant.plan = pro_plan
        tenant.save(update_fields=["plan"])
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"ssrf-conn-{uuid.uuid4().hex[:8]}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    return tenant, user


@pytest.fixture
def marketplace_service(tenant_user):
    tenant, user = tenant_user
    return MarketplaceIntegrationService(
        tenant_id=str(tenant.id),
        user_id=str(user.id),
    )


@pytest.mark.django_db(transaction=True)
class TestMarketplaceConnectionSSRF:
    """The marketplace connection service must reject every attack vector
    on BOTH create and update, for every URL-shaped config key."""

    @override_settings(INTEGRATION_SSRF_ENABLED=True)
    @pytest.mark.parametrize("attack_url", _BLOCKED_URLS + _SCHEME_CONFUSION)
    @pytest.mark.parametrize("key", _MARKETPLACE_URL_KEYS)
    def test_create_rejects_blocked_urls(self, db, tenant_user, attack_url, key):
        tenant, user = tenant_user
        service = MarketplaceIntegrationService(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
        )
        with pytest.raises(ServiceValidationError):
            service.create_connection(
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
                name=f"conn-{uuid.uuid4().hex[:8]}",
                config={key: attack_url},
            )

    @override_settings(INTEGRATION_SSRF_ENABLED=True)
    @pytest.mark.parametrize("attack_url", _BLOCKED_URLS + _SCHEME_CONFUSION)
    def test_update_rejects_blocked_urls(self, db, tenant_user, attack_url):
        tenant, user = tenant_user
        service = MarketplaceIntegrationService(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
        )
        connection = service.create_connection(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name=f"conn-{uuid.uuid4().hex[:8]}",
            config={"url": _SAFE_URL},
        )
        with pytest.raises(ServiceValidationError):
            service.update_connection(
                connection_id=str(connection.id),
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                config={"url": attack_url},
            )

    @override_settings(INTEGRATION_SSRF_ENABLED=True)
    def test_create_accepts_public_url(self, db, tenant_user):
        tenant, user = tenant_user
        service = MarketplaceIntegrationService(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
        )
        connection = service.create_connection(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name=f"conn-{uuid.uuid4().hex[:8]}",
            config={"url": _SAFE_URL},
        )
        assert connection.id is not None

    @override_settings(INTEGRATION_SSRF_ENABLED=True)
    def test_scheme_less_bare_hosts_stay_accepted(self, db, tenant_user):
        """Bare hostnames (no scheme) are connector-specific host configs,
        not URLs the guard must police — e.g. the databricks connector's
        workspace host. They must not be rejected by the scheme gate."""
        tenant, user = tenant_user
        service = MarketplaceIntegrationService(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
        )
        connection = service.create_connection(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name=f"conn-{uuid.uuid4().hex[:8]}",
            config={"host": "e2e-databricks.cloud.databricks.com"},
        )
        assert connection.id is not None


@pytest.mark.django_db(transaction=True)
class TestWarehouseConnectionSSRF:
    """``WarehouseConnection.save()`` must reject every attack vector on
    the URL-shaped config keys AND on the private_endpoint_url column."""

    def _connection(self, tenant, config=None, private_endpoint_url=""):
        return WarehouseConnection(
            tenant=tenant,
            name=f"wh-{uuid.uuid4().hex[:8]}",
            warehouse_type="SNOWFLAKE",
            region="eu-central-1",
            config=config or {},
            private_endpoint_url=private_endpoint_url,
        )

    @pytest.mark.parametrize("attack_url", _BLOCKED_URLS + _SCHEME_CONFUSION)
    @pytest.mark.parametrize("key", _WAREHOUSE_URL_KEYS)
    def test_save_rejects_blocked_config_urls(self, db, tenant_user, attack_url, key):
        tenant, _user = tenant_user
        with pytest.raises(DjangoValidationError):
            self._connection(tenant, config={key: attack_url}).save()

    @pytest.mark.parametrize("attack_url", _BLOCKED_URLS + _SCHEME_CONFUSION)
    def test_save_rejects_blocked_private_endpoint_url_column(self, db, tenant_user, attack_url):
        tenant, _user = tenant_user
        with pytest.raises(DjangoValidationError):
            self._connection(tenant, private_endpoint_url=attack_url).save()

    def test_save_accepts_public_config_url(self, db, tenant_user):
        tenant, _user = tenant_user
        connection = self._connection(tenant, config={"host": _SAFE_URL})
        connection.save()
        assert connection.id is not None

    def test_save_accepts_public_private_endpoint_url_column(self, db, tenant_user):
        tenant, _user = tenant_user
        connection = self._connection(tenant, private_endpoint_url=_SAFE_URL)
        connection.save()
        assert connection.id is not None

    def test_save_accepts_scheme_less_bare_host(self, db, tenant_user):
        """JDBC-style bare hosts are legitimate warehouse config values."""
        tenant, _user = tenant_user
        connection = self._connection(tenant, config={"host": "xyz123.snowflakecomputing.com"})
        connection.save()
        assert connection.id is not None
