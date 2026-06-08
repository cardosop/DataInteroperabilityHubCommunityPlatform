"""
Security Test Suite for ODPS $ref Resolver

Comprehensive security tests covering:
- URL validation (scheme, host, length, format)
- Path traversal prevention (local refs)
- Rate limiting (per-tenant, per-user, global)
- Size limits (per-ref and total)
- Timeout controls (per-ref and total)
- Security logging and audit trails

All tests use real implementations (no mocks of hub services).
Rate limiting uses real Redis. Size/timeout logging tests assert on SecurityAuditLog (real persistence).
Some URL/path validation tests use patch for log verification where real DB persistence is not exercised.
"""

import json
import tempfile
import time
import uuid
from pathlib import Path
from unittest.mock import patch

import httpx
import redis
from django.conf import settings
from django.test import TestCase, override_settings

from hub.apps.contracts.config.odps_refs_config import ODPSRefsConfig
from hub.apps.contracts.models import SecurityAuditLog
from hub.apps.contracts.odps_errors import ODPSRefResolutionError
from hub.apps.contracts.odps_rate_limiting import (
    RATE_LIMIT_PER_TENANT,
    RATE_LIMIT_PER_USER,
)
from hub.apps.contracts.odps_security_logging import SecurityEventType, SecuritySeverity
from hub.apps.contracts.ref_resolver import (
    DEFAULT_MAX_REF_SIZE,
    DEFAULT_MAX_TOTAL_SIZE,
    DEFAULT_TIMEOUT_PER_REF,
    DEFAULT_TIMEOUT_TOTAL,
    MAX_URL_LENGTH,
    RefResolver,
)


def _make_test_http_server():
    """Minimal HTTP server for tests (real implementation, no mocks)."""
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from threading import Thread

    class _Server:
        def __init__(self):
            self.port = 0
            self.server = None
            self.thread = None
            self.routes = {}

        def add_json(self, path: str, data: dict):
            self.routes[path] = ("application/json", json.dumps(data).encode("utf-8"))

        def add_raw(self, path: str, body: bytes):
            self.routes[path] = ("application/json", body)

        def add_delayed_json(self, path: str, data: dict, delay_sec: float):
            def delayed():
                time.sleep(delay_sec)  # INTENTIONAL: test-specific timing requirement
                return ("application/json", json.dumps(data).encode("utf-8"))

            self.routes[path] = ("delayed", delayed)

        def start(self):
            routes = self.routes

            class _Handler(BaseHTTPRequestHandler):
                def do_GET(hself):
                    if hself.path in routes:
                        val = routes[hself.path]
                        if isinstance(val, tuple) and val[0] == "delayed":
                            # The delayed callable may take several seconds;
                            # the client may have disconnected by the time
                            # it returns (e.g. timeout tests).  Catch
                            # connection errors so the server thread does
                            # not crash.
                            try:
                                ct, body = val[1]()
                            except (BrokenPipeError, ConnectionResetError):
                                return
                        else:
                            ct, body = val
                        try:
                            hself.send_response(200)
                            hself.send_header("Content-Type", ct)
                            hself.send_header("Content-Length", str(len(body)))
                            hself.end_headers()
                            hself.wfile.write(body)
                            hself.wfile.flush()
                        except (BrokenPipeError, ConnectionResetError):
                            # Client disconnected before response could be
                            # fully written — harmless in test scenarios
                            # where the client intentionally times out.
                            pass
                    else:
                        try:
                            hself.send_response(404)
                            hself.end_headers()
                        except (BrokenPipeError, ConnectionResetError):
                            pass

                def log_message(hself, *args):
                    pass

            self.server = HTTPServer(("127.0.0.1", self.port), _Handler)
            self.port = self.server.server_address[1]
            self.thread = Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            time.sleep(0.15)  # INTENTIONAL: test-specific timing requirement

        def stop(self):
            if self.server:
                self.server.shutdown()
                self.server.server_close()
                self.server = None
                self.thread = None

        def base_url(self):
            return f"http://127.0.0.1:{self.port}"

        def __enter__(self):
            self.start()
            return self

        def __exit__(self, *args):
            self.stop()
            return False

    return _Server()


def get_real_redis_client_or_none():
    """Get real Redis client or return None if unavailable."""
    try:
        redis_url = getattr(settings, "REDIS_URL", None) or "redis://redis-cache-test:6379/0"
        client = redis.from_url(
            redis_url, decode_responses=False, socket_connect_timeout=2, socket_timeout=2
        )
        client.ping()
        return client
    except Exception:
        return None


class RefResolverURLValidationTest(TestCase):
    """Test URL validation security controls"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = ODPSRefsConfig()
        self.config._config_data = {"url_allowlist": ["https://example.com"], "url_denylist": []}
        self.resolver = RefResolver(
            config=self.config,
            tenant_id="test-tenant",
            user_id="test-user",
            enable_caching=False,
        )

    def test_url_validation_valid_https_url(self):
        """Test that valid HTTPS URLs pass validation through public API."""
        import httpx

        url = "https://example.com/schema.json"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"type": "object"}, request=request)

        # Inject httpx_transport so ALL production security controls run
        # (_validate_external_url, check_rate_limit, is_url_allowed, etc.)
        # and only the network boundary is mocked.
        resolver = RefResolver(
            config=self.config,
            tenant_id=f"test-https-{uuid.uuid4()}",
            user_id="test-user",
            enable_caching=False,
            httpx_transport=httpx.MockTransport(handler),
        )

        result = resolver.resolve_external(url)
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "object")

    def test_url_validation_valid_http_url(self):
        """Test that valid HTTP URLs pass validation through public API."""
        import httpx

        url = "http://example.com/schema.json"

        # Create config that allows both http and https URLs.
        http_config = ODPSRefsConfig()
        http_config._config_data = {
            "url_allowlist": ["https://example.com", "http://example.com"],
            "url_denylist": [],
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"type": "object"}, request=request)

        # Inject httpx_transport so ALL production security controls run.
        resolver = RefResolver(
            config=http_config,
            tenant_id=f"test-http-{uuid.uuid4()}",
            user_id="test-user",
            enable_caching=False,
            httpx_transport=httpx.MockTransport(handler),
        )

        result = resolver.resolve_external(url)
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "object")

    def test_url_validation_rejects_invalid_scheme_javascript(self):
        """Test that JavaScript URLs are rejected through public API"""
        url = "javascript:alert('XSS')"
        # Test through public API - resolve_external() validates URL internally
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_external(url)
        self.assertEqual(
            cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION
        )
        self.assertIn("invalid scheme", cm.exception.message.lower())

    def test_url_validation_rejects_invalid_scheme_file(self):
        """Test that file:// URLs are rejected through public API"""
        url = "file:///etc/passwd"
        # Test through public API - resolve_external() validates URL internally
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_external(url)
        self.assertEqual(
            cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION
        )
        self.assertIn("invalid scheme", cm.exception.message.lower())

    def test_url_validation_rejects_invalid_scheme_data(self):
        """Test that data: URLs are rejected through public API"""
        url = "data:text/html,<script>alert('XSS')</script>"
        # Test through public API - resolve_external() validates URL internally
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_external(url)
        self.assertEqual(
            cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION
        )
        self.assertIn("invalid scheme", cm.exception.message.lower())

    def test_url_validation_rejects_missing_host(self):
        """Test that URLs without host are rejected through public API"""
        url = "https:///path/to/schema.json"
        # Test through public API - resolve_external() validates URL internally
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_external(url)
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_INVALID_REF)
        self.assertIn("missing host", cm.exception.message.lower())

    def test_url_validation_rejects_empty_host(self):
        """Test that URLs with empty host are rejected through public API"""
        url = "https://"
        # Test through public API - resolve_external() validates URL internally
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_external(url)
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_INVALID_REF)

    def test_url_validation_rejects_url_too_long(self):
        """Test that URLs exceeding MAX_URL_LENGTH are rejected through public API"""
        # Create a URL that exceeds MAX_URL_LENGTH (2048 chars)
        # Need to ensure it's actually longer than MAX_URL_LENGTH
        long_path = "/" + "a" * (
            MAX_URL_LENGTH - 19
        )  # -19 to account for "https://example.com" (19 chars)
        url = f"https://example.com{long_path}"
        self.assertGreater(
            len(url), MAX_URL_LENGTH, f"URL length {len(url)} should exceed {MAX_URL_LENGTH}"
        )

        # Test through public API - resolve_external() validates URL internally
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_external(url)
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_INVALID_REF)
        self.assertIn("exceeds maximum", cm.exception.message.lower())

    def test_url_validation_rejects_malformed_url(self):
        """Test that malformed URLs are rejected through public API"""
        url = "not a valid url"
        # Test through public API - resolve_external() validates URL internally
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_external(url)
        # Malformed URLs are rejected - the actual error code depends on where parsing fails
        # If URL parsing fails, it's INVALID_REF; if scheme validation fails, it's SECURITY_VIOLATION
        self.assertIn(
            cm.exception.error_code,
            [
                ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
            ],
        )

    def test_url_validation_logs_security_violation(self):
        """Test that security violations are logged through public API"""
        url = "javascript:alert('XSS')"
        # Mock security logger to verify logging behavior (acceptable for testing logging)
        with patch.object(self.resolver._security_logger, "log_security_violation") as mock_log:
            try:
                # Test through public API - resolve_external() validates URL internally and logs violations
                self.resolver.resolve_external(url)
            except ODPSRefResolutionError:
                pass

            # Verify security violation was logged
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            self.assertEqual(call_args.kwargs["event_type"], SecurityEventType.INVALID_URL)
            self.assertEqual(call_args.kwargs["severity"], SecuritySeverity.HIGH)


class RefResolverPathTraversalTest(TestCase):
    """Test path traversal prevention for local refs"""

    def setUp(self):
        """Set up test fixtures"""
        # Create temporary directory structure
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)

        # Create allowed directory
        self.allowed_dir = self.base_path / "contracts" / "refs"
        self.allowed_dir.mkdir(parents=True, exist_ok=True)

        # Create a valid file in allowed directory
        self.valid_file = self.allowed_dir / "schema.json"
        self.valid_file.write_text(json.dumps({"type": "object"}))

        # Create config with allowed base dirs
        self.config = ODPSRefsConfig()
        self.config._config_data = {
            "allowed_base_dirs": [str(self.allowed_dir)],
            "url_allowlist": [],
            "url_denylist": [],
        }

        self.resolver = RefResolver(
            config=self.config,
            base_path=self.base_path,
            tenant_id="test-tenant",
            user_id="test-user",
            enable_caching=False,
        )

    def tearDown(self):
        """Clean up temporary files"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_path_traversal_rejects_dot_dot_slash(self):
        """Test that ../ path traversal is rejected"""
        attack_path = "../../../etc/passwd"
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local(attack_path)
        self.assertEqual(
            cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION
        )

    def test_path_traversal_rejects_multiple_dot_dot(self):
        """Test that multiple ../ path traversal is rejected"""
        attack_path = "../../../../etc/passwd"
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local(attack_path)
        self.assertEqual(
            cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION
        )

    def test_path_traversal_rejects_absolute_path(self):
        """Test that absolute paths are rejected"""
        attack_path = "/etc/passwd"
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local(attack_path)
        self.assertEqual(
            cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION
        )
        self.assertIn("absolute path", cm.exception.message.lower())

    def test_path_traversal_rejects_windows_absolute_path(self):
        """Test that Windows absolute paths are rejected"""
        attack_path = "C:\\Windows\\System32\\config\\sam"
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local(attack_path)
        # Should be rejected as absolute path or invalid ref
        self.assertIn(
            cm.exception.error_code,
            [
                ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
                ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
            ],
        )

    def test_path_traversal_rejects_double_dot_encoding(self):
        """Test that double dot encoding (....//) is rejected"""
        attack_path = "....//....//etc/passwd"
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local(attack_path)
        self.assertEqual(
            cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION
        )

    def test_path_traversal_allows_valid_relative_path(self):
        """Test that valid relative paths within allowed directory are allowed"""
        # Valid path within allowed directory (file is at contracts/refs/schema.json)
        valid_path = "./contracts/refs/schema.json"
        result = self.resolver.resolve_local(valid_path)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["type"], "object")

    def test_path_traversal_logs_security_violation(self):
        """Test that path traversal attempts are logged"""
        attack_path = "../../../etc/passwd"
        with patch.object(self.resolver._security_logger, "log_security_violation") as mock_log:
            try:
                self.resolver.resolve_local(attack_path)
            except ODPSRefResolutionError:
                pass

            # Verify security violation was logged
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            self.assertEqual(call_args.kwargs["event_type"], SecurityEventType.PATH_TRAVERSAL)
            self.assertEqual(call_args.kwargs["severity"], SecuritySeverity.HIGH)


@override_settings(REDIS_URL="redis://redis-cache-test:6379/0")
class RefResolverRateLimitingTest(TestCase):
    """Test rate limiting security controls using real Redis.

    Uses TestCase (not TransactionTestCase) to avoid DB destroy/create cycles when
    runserver holds connections to hub_test_test_shared. Rate limiting uses Redis,
    not DB transactions, so TestCase is sufficient.
    """

    def setUp(self):
        """Set up test fixtures"""
        self.config = ODPSRefsConfig()
        self.config._config_data = {"url_allowlist": ["https://example.com"], "url_denylist": []}
        self.tenant_id = "test-tenant-rate-limit"
        self.user_id = "test-user-rate-limit"
        self.resolver = RefResolver(
            config=self.config,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            enable_caching=False,
        )

        # Get real Redis client for rate limiting
        self.redis_client = get_real_redis_client_or_none()
        if self.redis_client is None:
            self.skipTest("Redis not available for rate limiting tests")

        # Clear rate limit keys for test isolation
        try:
            pattern = f"odps_ref_rate_limit:*{self.tenant_id}*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
            pattern = "odps_ref_rate_limit:global:*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
        except (redis.ConnectionError, redis.TimeoutError, OSError):
            pass  # Redis unavailable during setup — test will skip itself

    def tearDown(self):
        """Clean up test fixtures"""
        if self.redis_client:
            try:
                pattern = f"odps_ref_rate_limit:*{self.tenant_id}*"
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
                pattern = "odps_ref_rate_limit:global:*"
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
            except (redis.ConnectionError, redis.TimeoutError, OSError):
                pass  # Redis unavailable during teardown — harmless

    def test_rate_limit_enforced(self):
        """Test that rate limiting is enforced using real Redis"""
        from hub.apps.contracts.odps_errors import ODPSRefResolutionError
        from hub.apps.contracts.odps_rate_limiting import check_rate_limit

        # Exceed rate limit using real Redis
        # Make requests up to the user limit (50 requests/hour)
        for i in range(RATE_LIMIT_PER_USER):
            is_allowed, error = check_rate_limit(
                tenant_id=self.tenant_id, user_id=self.user_id, redis_client=self.redis_client
            )
            self.assertTrue(is_allowed, f"Request {i+1} should be allowed")

        # Next request should be rejected
        is_allowed, error = check_rate_limit(
            tenant_id=self.tenant_id, user_id=self.user_id, redis_client=self.redis_client
        )
        self.assertFalse(is_allowed, "Request should be rejected when over limit")
        self.assertIsNotNone(error)
        self.assertEqual(error.error_code, ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED)

        # Test that RefResolver respects rate limiting (call real resolve_external;
        # rate limit check runs before HTTP, so no mock needed)
        url = "https://example.com/schema.json"
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_external(url)
        self.assertEqual(
            cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED
        )

    def test_rate_limit_allows_when_not_exceeded(self):
        """Test that requests are allowed when rate limit is not exceeded."""
        import httpx

        # Use a unique tenant_id so no rate limit has been accumulated.
        fresh_tenant = f"test-tenant-fresh-{uuid.uuid4()}"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"type": "string"}, request=request)

        # Inject httpx_transport so ALL production security controls run
        # (rate limiting, URL validation, allowlist check) and only the
        # network boundary is mocked.
        resolver = RefResolver(
            config=self.config,
            tenant_id=fresh_tenant,
            user_id="test-user",
            enable_caching=False,
            httpx_transport=httpx.MockTransport(handler),
        )

        url = "https://example.com/schema.json"
        result = resolver.resolve_external(url)
        self.assertEqual(result, {"type": "string"})

    def test_rate_limit_violation_logged(self):
        """Test that rate limit violations are logged to SecurityAuditLog (real Redis, no mocks)."""
        from hub.apps.contracts.odps_errors import ODPSRefResolutionError
        from hub.apps.contracts.odps_rate_limiting import check_rate_limit

        # Exceed rate limit using real Redis
        for i in range(RATE_LIMIT_PER_USER):
            check_rate_limit(
                tenant_id=self.tenant_id, user_id=self.user_id, redis_client=self.redis_client
            )

        # Trigger rate limit via resolver (will raise ODPSRefResolutionError)
        url = "https://example.com/schema.json"
        try:
            self.resolver.resolve_external(url)
        except ODPSRefResolutionError:
            pass

        # Verify rate limit violation was persisted to SecurityAuditLog (no mocks).
        # NOTE: ref-resolver tests use string tenant IDs (not Tenant model instances),
        # so we filter by event_type only. Rate limit events are unique enough that
        # cross-test contamination is negligible.
        self.assertTrue(
            SecurityAuditLog.objects.filter(
                event_type=SecurityEventType.RATE_LIMIT_EXCEEDED.value,
            ).exists(),
            "Expected RATE_LIMIT_EXCEEDED in SecurityAuditLog",
        )


class RefResolverSizeLimitTest(TestCase):
    """Test size limit security controls"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = ODPSRefsConfig()
        self.config._config_data = {"url_allowlist": ["https://example.com"], "url_denylist": []}
        # Use smaller limits for testing
        self.resolver = RefResolver(
            config=self.config,
            tenant_id="test-tenant",
            user_id="test-user",
            max_ref_size=1000,  # 1KB per ref
            max_total_size=5000,  # 5KB total
            enable_caching=False,
        )

    def test_size_limit_rejects_oversized_ref(self):
        """Test that refs exceeding max_ref_size are rejected through public API."""
        import httpx

        # Create oversized content that exceeds max_ref_size (1000 bytes)
        oversized_content = b'{"data": "' + b"a" * 2000 + b'"}'
        size = len(oversized_content)
        self.assertGreater(size, self.resolver.max_ref_size)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=oversized_content, request=request)

        # Inject httpx_transport so ALL production security controls run,
        # including the real _check_size_limit that validates content length.
        resolver = RefResolver(
            config=self.config,
            tenant_id="test-tenant-size-reject",
            user_id="test-user",
            max_ref_size=1000,
            max_total_size=5000,
            enable_caching=False,
            httpx_transport=httpx.MockTransport(handler),
        )

        with self.assertRaises(ODPSRefResolutionError) as cm:
            resolver.resolve_external("https://example.com/schema.json")
        self.assertEqual(
            cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED
        )
        self.assertIn("exceeds limit", cm.exception.message.lower())

    def test_size_limit_rejects_total_size_exceeded(self):
        """Test that total size limit is enforced through public API"""
        import json
        import tempfile
        from pathlib import Path

        # Set total size to simulate previous resolutions
        self.resolver._total_size = 4001  # 4.001KB already used

        # Create a local file that would exceed total size limit
        temp_dir = Path(tempfile.mkdtemp())
        try:
            test_file = temp_dir / "test.json"
            # Create content that's within per-ref limit but would exceed total
            test_data = {"data": "x" * 1000}  # 1000 bytes
            test_file.write_text(json.dumps(test_data))

            config = ODPSRefsConfig()
            config._config_data = {"allowed_base_dirs": [str(temp_dir)]}
            resolver = RefResolver(
                config=config,
                base_path=temp_dir,
                tenant_id="test-tenant",
                user_id="test-user",
                max_ref_size=1000,
                max_total_size=5000,
                enable_caching=False,
            )
            resolver._total_size = 4001  # Set total size

            # Test through public API - resolve_local() checks total size limit internally
            with self.assertRaises(ODPSRefResolutionError) as cm:
                resolver.resolve_local(str(test_file.relative_to(temp_dir)))
            self.assertEqual(
                cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED
            )
            # Accept either per-ref or total size limit message
            msg_lower = cm.exception.message.lower()
            self.assertTrue(
                "total size" in msg_lower or "exceeds limit" in msg_lower or "size" in msg_lower,
                f"Expected size limit message, got: {cm.exception.message}",
            )
        finally:
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_size_limit_allows_within_limits(self):
        """Test that refs within size limits are allowed through public API."""
        import httpx

        normal_content = b'{"data": "test"}'

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=normal_content, request=request)

        # Inject httpx_transport so the real _check_size_limit runs and
        # verifies the content is within the configured max_ref_size.
        resolver = RefResolver(
            config=self.config,
            tenant_id="test-tenant-size-allow",
            user_id="test-user",
            max_ref_size=1000,
            max_total_size=5000,
            enable_caching=False,
            httpx_transport=httpx.MockTransport(handler),
        )

        result = resolver.resolve_external("https://example.com/schema.json")
        self.assertIsNotNone(result)
        self.assertEqual(result, {"data": "test"})

    def test_size_limit_logs_security_violation(self):
        """Test that size limit violations are logged to SecurityAuditLog (real HTTP, no mocks)."""
        tenant_id = str(uuid.uuid4())  # Unique to avoid rate limit from other tests
        resolver = RefResolver(
            config=self.config,
            tenant_id=tenant_id,
            user_id="test-user",
            max_ref_size=1000,
            max_total_size=5000,
            enable_caching=False,
        )
        oversized_content = b'{"data": "' + b"a" * 2000 + b'}'
        server = _make_test_http_server()
        server.add_raw("/schema.json", oversized_content)

        with server:
            self.config._config_data["url_allowlist"] = [server.base_url()]
            url = f"{server.base_url()}/schema.json"
            with self.assertRaises(ODPSRefResolutionError) as cm:
                resolver.resolve_external(url)
            self.assertEqual(
                cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED
            )

        # Verify security violation was persisted to SecurityAuditLog.
        # Scope by tenant__isnull=True: the resolver uses a synthetic UUID tenant_id
        # that does not correspond to a real Tenant row, so the persist path stores
        # tenant=None.  This avoids cross-test contamination.
        self.assertTrue(
            SecurityAuditLog.objects.filter(
                event_type=SecurityEventType.SIZE_LIMIT_EXCEEDED,
                tenant__isnull=True,
            ).exists(),
            "Expected SIZE_LIMIT_EXCEEDED in SecurityAuditLog",
        )

    def test_size_limit_enforced_on_external_ref(self):
        """Test that size limits are enforced on external refs using real HTTP server."""
        tenant_id = str(uuid.uuid4())  # Unique to avoid rate limit from other tests
        resolver = RefResolver(
            config=self.config,
            tenant_id=tenant_id,
            user_id="test-user",
            max_ref_size=1000,
            max_total_size=5000,
            enable_caching=False,
        )
        oversized_content = b'{"data": "' + b"a" * 2000 + b'"}'
        server = _make_test_http_server()
        server.add_raw("/schema.json", oversized_content)

        with server:
            self.config._config_data["url_allowlist"] = [server.base_url()]
            url = f"{server.base_url()}/schema.json"
            with self.assertRaises(ODPSRefResolutionError) as cm:
                resolver.resolve_external(url)
            self.assertEqual(
                cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED
            )


class RefResolverTimeoutTest(TestCase):
    """Test timeout security controls"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = ODPSRefsConfig()
        self.config._config_data = {"url_allowlist": ["https://example.com"], "url_denylist": []}
        # Use very short timeout for testing
        self.resolver = RefResolver(
            config=self.config,
            tenant_id="test-tenant",
            user_id="test-user",
            timeout_per_ref=1,  # 1 second
            timeout_total=2,  # 2 seconds total
            enable_caching=False,
        )

    def test_timeout_check_initializes_start_time(self):
        """Test that resolve() initializes start time via _check_timeout."""
        tenant_id = str(uuid.uuid4())  # Unique to avoid rate limit from other tests
        resolver = RefResolver(
            config=self.config,
            tenant_id=tenant_id,
            user_id="test-user",
            timeout_per_ref=1,
            timeout_total=2,
            enable_caching=False,
        )
        self.assertIsNone(resolver._start_time)

        server = _make_test_http_server()
        server.add_json("/schema.json", {"type": "object"})

        with server:
            self.config._config_data["url_allowlist"] = [server.base_url()]
            url = f"{server.base_url()}/schema.json"
            result = resolver.resolve(url)
            self.assertIsNotNone(result)
            self.assertIsNotNone(resolver._start_time)

    def test_timeout_check_rejects_exceeded_total_timeout(self):
        """Test that total timeout violations are rejected when _start_time exceeded."""
        tenant_id = str(uuid.uuid4())  # Unique to avoid rate limit from other tests
        resolver = RefResolver(
            config=self.config,
            tenant_id=tenant_id,
            user_id="test-user",
            timeout_per_ref=1,
            timeout_total=2,
            enable_caching=False,
        )
        resolver._start_time = time.time() - 3  # 3 seconds ago (timeout_total=2)

        # resolve() calls _check_timeout() first, which raises before HTTP
        with self.assertRaises(ODPSRefResolutionError) as cm:
            resolver.resolve("https://example.com/schema.json")
        self.assertEqual(
            cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED
        )
        self.assertIn("timeout", cm.exception.message.lower())

    def test_timeout_check_allows_within_timeout(self):
        """Test that requests within timeout are allowed through public API."""
        import httpx

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"type": "object"}, request=request)

        # Inject httpx_transport so ALL production security controls run.
        resolver = RefResolver(
            config=self.config,
            tenant_id="test-tenant-timeout-allow",
            user_id="test-user",
            timeout_per_ref=1,
            timeout_total=2,
            enable_caching=False,
            httpx_transport=httpx.MockTransport(handler),
        )
        # Set _start_time to recent so _check_timeout() allows the call.
        resolver._start_time = time.time() - 1  # 1 second ago (within 2s total)

        result = resolver.resolve_external("https://example.com/schema.json")
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "object")

    def test_timeout_logs_security_violation(self):
        """Test that timeout violations are logged to SecurityAuditLog (real resolve, no mocks)."""
        tenant_id = str(uuid.uuid4())  # Unique to avoid rate limit from other tests
        resolver = RefResolver(
            config=self.config,
            tenant_id=tenant_id,
            user_id="test-user",
            timeout_per_ref=1,
            timeout_total=2,
            enable_caching=False,
        )
        # resolve() calls _check_timeout() first; set _start_time in past to trigger timeout
        resolver._start_time = time.time() - 3  # 3 seconds ago (timeout_total=2)

        with self.assertRaises(ODPSRefResolutionError) as cm:
            resolver.resolve("https://example.com/schema.json")
        self.assertEqual(
            cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED
        )
        self.assertIn("timeout", cm.exception.message.lower())

        # Verify security violation was persisted to SecurityAuditLog.
        # Scope by tenant__isnull=True — see comment on SIZE_LIMIT_EXCEEDED query above.
        self.assertTrue(
            SecurityAuditLog.objects.filter(
                event_type=SecurityEventType.TIMEOUT,
                tenant__isnull=True,
            ).exists(),
            "Expected TIMEOUT in SecurityAuditLog",
        )

    def test_timeout_enforced_on_external_ref(self):
        """Test that timeout is enforced on external refs using real HTTP server that delays."""
        tenant_id = str(uuid.uuid4())  # Unique to avoid rate limit from other tests
        resolver = RefResolver(
            config=self.config,
            tenant_id=tenant_id,
            user_id="test-user",
            timeout_per_ref=1,
            timeout_total=2,
            enable_caching=False,
        )
        server = _make_test_http_server()
        server.add_delayed_json("/schema.json", {"type": "object"}, delay_sec=5)

        with server:
            self.config._config_data["url_allowlist"] = [server.base_url()]
            url = f"{server.base_url()}/schema.json"
            with self.assertRaises(ODPSRefResolutionError) as cm:
                resolver.resolve(url)
            self.assertIn(
                cm.exception.error_code,
                [
                    ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED,
                    ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                ],
            )


class RefResolverSecurityLoggingTest(TestCase):
    """Test security logging and audit trails"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = ODPSRefsConfig()
        self.config._config_data = {"url_allowlist": ["https://example.com"], "url_denylist": []}
        self.resolver = RefResolver(
            config=self.config,
            tenant_id="test-tenant",
            user_id="test-user",
            enable_caching=False,
        )
        self.redis_client = get_real_redis_client_or_none()

    def test_security_logging_url_validation_violation(self):
        """Test that URL validation violations are logged through public API"""
        url = "javascript:alert('XSS')"
        # Mock security logger to verify logging behavior (acceptable for testing logging)
        with patch.object(self.resolver._security_logger, "log_security_violation") as mock_log:
            try:
                # Test through public API - resolve_external() validates URL internally and logs violations
                self.resolver.resolve_external(url)
            except ODPSRefResolutionError:
                pass

            mock_log.assert_called_once()
            call_args = mock_log.call_args
            self.assertEqual(call_args.kwargs["event_type"], SecurityEventType.INVALID_URL)
            self.assertEqual(call_args.kwargs["severity"], SecuritySeverity.HIGH)
            self.assertIn("attempted_url", call_args.kwargs)

    def test_security_logging_path_traversal_violation(self):
        """Test that path traversal violations are logged"""
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        base_path = Path(temp_dir)
        allowed_dir = base_path / "contracts" / "refs"
        allowed_dir.mkdir(parents=True, exist_ok=True)

        config = ODPSRefsConfig()
        config._config_data = {
            "allowed_base_dirs": [str(allowed_dir)],
            "url_allowlist": [],
            "url_denylist": [],
        }

        resolver = RefResolver(
            config=config,
            base_path=base_path,
            tenant_id="test-tenant",
            user_id="test-user",
            enable_caching=False,
        )

        attack_path = "../../../etc/passwd"
        with patch.object(resolver._security_logger, "log_security_violation") as mock_log:
            try:
                resolver.resolve_local(attack_path)
            except ODPSRefResolutionError:
                pass

            mock_log.assert_called_once()
            call_args = mock_log.call_args
            self.assertEqual(call_args.kwargs["event_type"], SecurityEventType.PATH_TRAVERSAL)
            self.assertEqual(call_args.kwargs["severity"], SecuritySeverity.HIGH)
            self.assertIn("attempted_path", call_args.kwargs)

        # Cleanup
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_security_logging_size_limit_violation(self):
        """Test that size limit violations are logged to SecurityAuditLog (real HTTP, no mocks)."""
        tenant_id = str(uuid.uuid4())  # Unique to avoid rate limit from other tests
        resolver = RefResolver(
            config=self.config,
            tenant_id=tenant_id,
            user_id="test-user",
            max_ref_size=1000,  # 1KB per ref
            enable_caching=False,
        )
        oversized_content = b'{"data": "' + b"a" * 2000 + b'"}'
        server = _make_test_http_server()
        server.add_raw("/schema.json", oversized_content)

        with server:
            resolver.config._config_data["url_allowlist"] = [server.base_url()]
            url = f"{server.base_url()}/schema.json"
            with self.assertRaises(ODPSRefResolutionError) as cm:
                resolver.resolve_external(url)
            self.assertEqual(
                cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED
            )

        self.assertTrue(
            SecurityAuditLog.objects.filter(
                event_type=SecurityEventType.SIZE_LIMIT_EXCEEDED,
                tenant__isnull=True,
            ).exists(),
            "Expected SIZE_LIMIT_EXCEEDED in SecurityAuditLog",
        )

    def test_security_logging_timeout_violation(self):
        """Test that timeout violations are logged to SecurityAuditLog (real resolve, no mocks)."""
        tenant_id = str(uuid.uuid4())  # Unique to avoid rate limit from other tests
        resolver = RefResolver(
            config=self.config,
            tenant_id=tenant_id,
            user_id="test-user",
            timeout_total=2,  # 2 seconds total
            enable_caching=False,
        )
        # resolve() calls _check_timeout() first; set _start_time in past to trigger timeout
        resolver._start_time = time.time() - 3  # 3 seconds ago (exceeds 2s timeout)

        with self.assertRaises(ODPSRefResolutionError) as cm:
            resolver.resolve("https://example.com/schema.json")
        self.assertEqual(
            cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED
        )
        self.assertIn("timeout", cm.exception.message.lower())

        self.assertTrue(
            SecurityAuditLog.objects.filter(
                event_type=SecurityEventType.TIMEOUT,
                tenant__isnull=True,
            ).exists(),
            "Expected TIMEOUT in SecurityAuditLog",
        )

    def test_security_logging_includes_tenant_user_context(self):
        """Test that security logs include tenant and user context through public API"""
        url = "javascript:alert('XSS')"
        # Mock security logger to verify logging behavior (acceptable for testing logging)
        with patch.object(self.resolver._security_logger, "log_security_violation") as mock_log:
            try:
                # Test through public API - resolve_external() validates URL internally and logs violations
                self.resolver.resolve_external(url)
            except ODPSRefResolutionError:
                pass

            mock_log.assert_called_once()
            call_args = mock_log.call_args
            self.assertEqual(call_args.kwargs["tenant_id"], "test-tenant")
            self.assertEqual(call_args.kwargs["user_id"], "test-user")

    # Edge cases and error handling tests
    def test_url_validation_with_none_url(self):
        """Test URL validation with None URL raises TypeError or validation error."""
        with self.assertRaises((TypeError, ValueError, ODPSRefResolutionError)):
            self.resolver.resolve_external(None)  # type: ignore[misc]  # test: edge-case type exercise

    def test_url_validation_with_empty_url(self):
        """Test URL validation with empty URL raises validation error."""
        with self.assertRaises(ODPSRefResolutionError):
            self.resolver.resolve_external("")

    def test_url_validation_with_unicode_in_url(self):
        """Test URL validation with unicode characters in URL through public API."""
        import httpx

        url = "https://example.com/产品.json"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"type": "object"}, request=request)

        # Use a unique tenant_id to avoid rate limit exhaustion from prior tests.
        resolver = RefResolver(
            config=self.config,
            tenant_id=f"test-unicode-{uuid.uuid4()}",
            user_id="test-user",
            enable_caching=False,
            httpx_transport=httpx.MockTransport(handler),
        )

        # The unicode URL should be handled — either resolved successfully
        # or rejected with a specific validation error.
        try:
            result = resolver.resolve_external(url)
            self.assertIsNotNone(result)
            self.assertEqual(result["type"], "object")
        except ODPSRefResolutionError as e:
            # Acceptable if unicode in paths triggers a validation rejection.
            self.assertIn(
                e.error_code,
                [ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                 ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION],
            )

    def test_path_traversal_with_none_path(self):
        """Test path traversal prevention with None path raises TypeError."""
        with self.assertRaises((TypeError, ValueError, ODPSRefResolutionError)):
            self.resolver.resolve_local(None)  # type: ignore[misc]  # test: edge-case type exercise

    def test_path_traversal_with_empty_path(self):
        """Test path traversal prevention with empty path raises error."""
        with self.assertRaises(ODPSRefResolutionError):
            self.resolver.resolve_local("")

    def test_path_traversal_with_very_long_path(self):
        """Test path traversal prevention with very long path."""
        very_long_path = "/" + "a" * 10000
        # Very long paths that are absolute should be rejected as security violation.
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local(very_long_path)
        self.assertIn(
            cm.exception.error_code,
            [ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
             ODPSRefResolutionError.ERROR_CODE_INVALID_REF],
        )

    def test_rate_limit_with_none_tenant_id(self):
        """Test rate limiting with None tenant_id raises or returns denied."""
        from hub.apps.contracts.odps_rate_limiting import check_rate_limit

        try:
            is_allowed, error = check_rate_limit(
                tenant_id=None, user_id="test-user", redis_client=self.redis_client  # type: ignore[misc]  # test: edge-case type exercise
            )
            self.assertFalse(is_allowed, "None tenant_id must not be allowed")
        except (ValueError, TypeError):
            # None tenant_id must raise — equally valid behavior.
            pass

    def test_rate_limit_with_empty_tenant_id(self):
        """Test rate limiting with empty tenant_id raises ValueError or returns denied."""
        from hub.apps.contracts.odps_rate_limiting import check_rate_limit

        try:
            is_allowed, error = check_rate_limit(
                tenant_id="", user_id="test-user", redis_client=self.redis_client
            )
            self.assertFalse(is_allowed, "Empty tenant_id must not be allowed")
        except ValueError:
            # Empty tenant_id must raise ValueError — equally valid.
            pass

    def test_size_limit_with_empty_response(self):
        """Test that empty (zero-byte) HTTP responses are handled gracefully."""
        import httpx

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"", request=request)

        # Empty response → _check_size_limit(0) passes, but json parse fails.
        resolver = RefResolver(
            config=self.config,
            tenant_id=f"test-empty-{uuid.uuid4()}",
            user_id="test-user",
            max_ref_size=1000,
            enable_caching=False,
            httpx_transport=httpx.MockTransport(handler),
        )

        with self.assertRaises(ODPSRefResolutionError) as cm:
            resolver.resolve_external("https://example.com/schema.json")
        # Empty body should produce either a resolution failure or invalid ref.
        self.assertIn(
            cm.exception.error_code,
            [ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED,
             ODPSRefResolutionError.ERROR_CODE_INVALID_REF],
        )

    def test_size_limit_with_small_valid_response(self):
        """Test that a small valid response passes size limit checks."""
        import httpx

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"type": "object"}, request=request)

        resolver = RefResolver(
            config=self.config,
            tenant_id=f"test-small-{uuid.uuid4()}",
            user_id="test-user",
            max_ref_size=1000,
            enable_caching=False,
            httpx_transport=httpx.MockTransport(handler),
        )

        # Small valid response should pass all checks.
        result = resolver.resolve_external("https://example.com/schema.json")
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "object")

    def test_timeout_check_with_none_start_time(self):
        """Test timeout check with None start_time — resolve() initializes it."""
        import httpx

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"type": "object"}, request=request)

        resolver = RefResolver(
            config=self.config,
            tenant_id=f"test-timeout-none-{uuid.uuid4()}",
            user_id="test-user",
            timeout_per_ref=5,
            timeout_total=30,
            enable_caching=False,
            httpx_transport=httpx.MockTransport(handler),
        )
        resolver._start_time = None  # type: ignore[misc]  # test: edge-case type exercise

        # resolve() calls _check_timeout(), which should initialize _start_time
        # when it is None, then proceed with resolution.
        result = resolver.resolve("https://example.com/schema.json")
        self.assertIsNotNone(result)
        # After resolve(), _start_time must have been initialized.
        self.assertIsNotNone(resolver._start_time)

    def test_security_logging_with_none_event_type(self):
        """Test security logging with None event_type raises TypeError."""
        with self.assertRaises((TypeError, ValueError)):
            self.resolver._security_logger.log_security_violation(
                event_type=None,  # type: ignore[misc]  # test: edge-case type exercise
                severity=SecuritySeverity.HIGH,
                tenant_id="test-tenant",
                user_id="test-user",
            )

    def test_security_logging_with_none_severity(self):
        """Test security logging with None severity raises TypeError."""
        with self.assertRaises((TypeError, ValueError)):
            self.resolver._security_logger.log_security_violation(
                event_type=SecurityEventType.INVALID_URL,
                severity=None,  # type: ignore[misc]  # test: edge-case type exercise
                tenant_id="test-tenant",
                user_id="test-user",
            )

    def test_url_validation_with_very_long_host(self):
        """Test URL validation with very long hostname — is_url_allowed rejects it."""
        long_host = "a" * 1000 + ".com"
        url = f"https://{long_host}/schema.json"

        # Create a fresh resolver with a unique tenant to avoid rate limit
        # exhaustion interfering with the security validation check.
        resolver = RefResolver(
            config=self.config,
            tenant_id=f"test-longhost-{uuid.uuid4()}",
            user_id="test-user",
            enable_caching=False,
        )

        # The host is not in the allowlist, so is_url_allowed should reject it.
        # No HTTP call should be made — the security check runs first.
        with self.assertRaises(ODPSRefResolutionError) as cm:
            resolver.resolve_external(url)
        self.assertEqual(
            cm.exception.error_code,
            ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
        )
        self.assertIn("not allowed", cm.exception.message.lower())

    def test_path_traversal_with_special_characters(self):
        """Test path traversal prevention with special characters."""
        attack_path = "../../../etc/passwd<>&\"'"
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local(attack_path)
        self.assertEqual(
            cm.exception.error_code,
            ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
        )
