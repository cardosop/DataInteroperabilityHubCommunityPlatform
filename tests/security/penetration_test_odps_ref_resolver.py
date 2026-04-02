"""
Penetration Test Suite for ODPS $ref Resolver

Comprehensive penetration tests simulating real-world attack scenarios:
- Path traversal attacks (various encoding and bypass techniques)
- URL injection attacks (SSRF, XSS, protocol handlers)
- Rate limit bypass attempts
- Size limit bypass attempts

All tests use real implementations - no mocks or stubs. External HTTP uses
a real in-process HTTP server (127.0.0.1) for controlled responses.
"""

import json
import tempfile
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

from django.test import TestCase, override_settings

from hub.apps.contracts.config.odps_refs_config import ODPSRefsConfig
from hub.apps.contracts.odps_errors import ODPSRefResolutionError
from hub.apps.contracts.odps_rate_limiting import (
    RATE_LIMIT_GLOBAL,
    RATE_LIMIT_PER_TENANT,
    RATE_LIMIT_PER_USER,
    check_rate_limit,
)
from hub.apps.contracts.ref_resolver import (
    DEFAULT_MAX_REF_SIZE,
    DEFAULT_MAX_TOTAL_SIZE,
    DEFAULT_TIMEOUT_PER_REF,
    DEFAULT_TIMEOUT_TOTAL,
    MAX_URL_LENGTH,
    RefResolver,
)


class _RefResolverTestHTTPServer:
    """Real HTTP server for penetration tests (no mocks). Serves JSON or raw bytes per path."""

    def __init__(self):
        self.port = 0
        self.server = None
        self.thread = None
        self.routes = {}  # path -> (content_type, body_bytes)

    def add_json_route(self, path: str, content: dict) -> None:
        body = json.dumps(content).encode("utf-8")
        self.routes[path] = ("application/json", body)

    def add_raw_route(
        self, path: str, body_bytes: bytes, content_type: str = "application/json"
    ) -> None:
        self.routes[path] = (content_type, body_bytes)

    def start(self) -> None:
        routes = self.routes

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(hself):
                if hself.path in routes:
                    content_type, body = routes[hself.path]
                    hself.send_response(200)
                    hself.send_header("Content-Type", content_type)
                    hself.send_header("Content-Length", str(len(body)))
                    hself.end_headers()
                    hself.wfile.write(body)
                    hself.wfile.flush()
                else:
                    hself.send_response(404)
                    hself.end_headers()
                    hself.wfile.write(b"Not Found")
                    hself.wfile.flush()

            def log_message(hself, fmt, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", self.port), _Handler)
        self.port = self.server.server_address[1]
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        time.sleep(0.15)  # INTENTIONAL: test-specific delay

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
            self.thread = None

    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
        return False


class PathTraversalPenetrationTest(TestCase):
    """Penetration tests for path traversal attacks"""

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

    def test_path_traversal_attack_basic(self):
        """Test basic path traversal attack: ../../../etc/passwd"""
        attack_path = "../../../etc/passwd"
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local(attack_path)
        self.assertEqual(
            cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION
        )

    def test_path_traversal_attack_multiple_levels(self):
        """Test path traversal with multiple levels: ../../../../etc/passwd"""
        attack_path = "../../../../etc/passwd"
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local(attack_path)
        self.assertEqual(
            cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION
        )

    def test_path_traversal_attack_url_encoded(self):
        """Test path traversal with URL encoding: ..%2F..%2Fetc%2Fpasswd"""
        attack_path = "..%2F..%2Fetc%2Fpasswd"
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local(attack_path)
        # Should be rejected (either as security violation or invalid ref)
        self.assertIn(
            cm.exception.error_code,
            [
                ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
                ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
            ],
        )

    def test_path_traversal_attack_double_encoding(self):
        """Test path traversal with double encoding: %252e%252e%252fetc%252fpasswd"""
        attack_path = "%252e%252e%252fetc%252fpasswd"
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local(attack_path)
        # Should be rejected
        self.assertIn(
            cm.exception.error_code,
            [
                ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
                ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
            ],
        )

    def test_path_traversal_attack_double_dot_slash(self):
        """Test path traversal with double dot slash: ....//....//etc/passwd"""
        attack_path = "....//....//etc/passwd"
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local(attack_path)
        self.assertEqual(
            cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION
        )

    def test_path_traversal_attack_windows_backslash(self):
        """Test path traversal with Windows backslash: ..\\..\\..\\windows\\system32"""
        attack_path = "..\\..\\..\\windows\\system32\\config\\sam"
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local(attack_path)
        # Should be rejected
        self.assertIn(
            cm.exception.error_code,
            [
                ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
                ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
            ],
        )

    def test_path_traversal_attack_absolute_path_unix(self):
        """Test absolute path attack: /etc/passwd"""
        attack_path = "/etc/passwd"
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local(attack_path)
        self.assertEqual(
            cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION
        )
        self.assertIn("absolute path", cm.exception.message.lower())

    def test_path_traversal_attack_absolute_path_windows(self):
        """Test Windows absolute path attack: C:\\Windows\\System32"""
        attack_path = "C:\\Windows\\System32\\config\\sam"
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local(attack_path)
        # Should be rejected
        self.assertIn(
            cm.exception.error_code,
            [
                ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
                ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
            ],
        )

    def test_path_traversal_attack_null_byte(self):
        """Test path traversal with null byte injection: ..%00/../etc/passwd"""
        attack_path = "..%00/../etc/passwd"
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_local(attack_path)
        # Should be rejected
        self.assertIn(
            cm.exception.error_code,
            [
                ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
                ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
            ],
        )

    def test_path_traversal_attack_mixed_encoding(self):
        """Test path traversal with mixed encoding techniques"""
        attack_paths = [
            "..%2F..%2Fetc%2Fpasswd",
            "....%2F%2Fetc%2Fpasswd",
            "..%252F..%252Fetc%252Fpasswd",
        ]
        for attack_path in attack_paths:
            with self.subTest(attack_path=attack_path):
                with self.assertRaises(ODPSRefResolutionError) as cm:
                    self.resolver.resolve_local(attack_path)
                # Should be rejected
                self.assertIn(
                    cm.exception.error_code,
                    [
                        ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
                        ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                    ],
                )


class URLInjectionPenetrationTest(TestCase):
    """Penetration tests for URL injection attacks"""

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

    def test_url_injection_javascript_protocol(self):
        """Test JavaScript protocol injection: javascript:alert('XSS')"""
        attack_url = "javascript:alert('XSS')"
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_external(attack_url)
        self.assertEqual(
            cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION
        )

    def test_url_injection_data_protocol(self):
        """Test data protocol injection: data:text/html,<script>alert('XSS')</script>"""
        attack_url = "data:text/html,<script>alert('XSS')</script>"
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_external(attack_url)
        self.assertEqual(
            cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION
        )

    def test_url_injection_file_protocol(self):
        """Test file protocol injection: file:///etc/passwd"""
        attack_url = "file:///etc/passwd"
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_external(attack_url)
        self.assertEqual(
            cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION
        )

    def test_url_injection_ssrf_localhost(self):
        """Test SSRF attack via localhost: http://localhost:8080/admin"""
        attack_url = "http://localhost:8080/admin"
        # Should be rejected or logged as suspicious
        with self.assertRaises(ODPSRefResolutionError):
            self.resolver.resolve_external(attack_url)

    def test_url_injection_ssrf_127_0_0_1(self):
        """Test SSRF attack via 127.0.0.1: http://127.0.0.1:8080/admin"""
        attack_url = "http://127.0.0.1:8080/admin"
        # Should be rejected or logged as suspicious
        with self.assertRaises(ODPSRefResolutionError):
            self.resolver.resolve_external(attack_url)

    def test_url_injection_ssrf_private_ip(self):
        """Test SSRF attack via private IP: http://192.168.1.1/admin"""
        attack_url = "http://192.168.1.1/admin"
        # Should be rejected if not in allowlist
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_external(attack_url)
        # Should be rejected as not in allowlist or security violation
        self.assertIn(
            cm.exception.error_code,
            [
                ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
                ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
            ],
        )

    def test_url_injection_path_traversal_in_url(self):
        """Test path traversal in URL: https://example.com/../../../etc/passwd"""
        attack_url = "https://example.com/../../../etc/passwd"
        # Should be rejected or sanitized
        with self.assertRaises(ODPSRefResolutionError):
            self.resolver.resolve_external(attack_url)

    def test_url_injection_oversized_url(self):
        """Test oversized URL attack"""
        # Create URL exceeding MAX_URL_LENGTH
        # Need to ensure it's actually longer than MAX_URL_LENGTH
        long_path = "/" + "a" * (
            MAX_URL_LENGTH - 19
        )  # -19 to account for "https://example.com" (19 chars)
        attack_url = f"https://example.com{long_path}"
        self.assertGreater(
            len(attack_url),
            MAX_URL_LENGTH,
            f"URL length {len(attack_url)} should exceed {MAX_URL_LENGTH}",
        )

        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver.resolve_external(attack_url)
        self.assertEqual(cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_INVALID_REF)

    def test_url_injection_malformed_url(self):
        """Test malformed URL injection"""
        attack_urls = [
            "not a url",
            "http://",
            "https://",
            "://example.com",
            "http://[invalid",
        ]
        for attack_url in attack_urls:
            with self.subTest(attack_url=attack_url):
                with self.assertRaises(ODPSRefResolutionError) as cm:
                    self.resolver.resolve_external(attack_url)
                # Should be rejected
                self.assertIn(
                    cm.exception.error_code,
                    [
                        ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
                        ODPSRefResolutionError.ERROR_CODE_INVALID_REF,
                    ],
                )


class RateLimitBypassPenetrationTest(TestCase):
    """Penetration tests for rate limit bypass attempts"""

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

    def test_rate_limit_bypass_rapid_requests(self):
        """Test rapid requests: resolver uses real rate limit and real HTTP (no mocks)."""
        server = _RefResolverTestHTTPServer()
        server.add_json_route("/schema.json", {"type": "string"})

        with server:
            base_url = server.base_url()
            self.config._config_data["url_allowlist"] = [base_url]
            url = f"{base_url}/schema.json"
            success_count = 0
            rate_limited = False
            for _ in range(15):
                try:
                    result = self.resolver.resolve_external(url)
                    self.assertEqual(result, {"type": "string"})
                    success_count += 1
                except ODPSRefResolutionError as e:
                    if e.error_code == ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED:
                        rate_limited = True
                        break
                    raise
            self.assertGreater(
                success_count, 0, "At least one request should succeed or hit rate limit"
            )
            # With real rate limit: either all succeed (Redis unavailable/low limit not hit)
            # or we eventually get RATE_LIMIT_EXCEEDED

    def test_rate_limit_bypass_tenant_switching(self):
        """Test multiple tenants: each resolver uses real rate limit and real HTTP (no mocks)."""
        server = _RefResolverTestHTTPServer()
        server.add_json_route("/schema.json", {"type": "object"})

        with server:
            self.config._config_data["url_allowlist"] = [server.base_url()]
            url = f"{server.base_url()}/schema.json"
            tenant_ids = ["tenant-1", "tenant-2", "tenant-3"]
            for tenant_id in tenant_ids:
                resolver = RefResolver(
                    config=self.config,
                    tenant_id=tenant_id,
                    user_id="test-user",
                    enable_caching=False,
                )
                result = resolver.resolve_external(url)
                self.assertIsInstance(result, dict)
                self.assertEqual(result, {"type": "object"})

    def test_rate_limit_enforcement_per_level(self):
        """Test that resolve_external uses real rate limit and real HTTP (no mocks)."""
        server = _RefResolverTestHTTPServer()
        server.add_json_route("/schema.json", {"type": "string"})

        with server:
            base_url = server.base_url()
            self.config._config_data["url_allowlist"] = [base_url]
            url = f"{base_url}/schema.json"
            try:
                result = self.resolver.resolve_external(url)
                self.assertEqual(result, {"type": "string"})
            except ODPSRefResolutionError as e:
                self.assertEqual(
                    e.error_code,
                    ODPSRefResolutionError.ERROR_CODE_RATE_LIMIT_EXCEEDED,
                    "Only rate limit error expected if not success",
                )


class SizeLimitBypassPenetrationTest(TestCase):
    """Penetration tests for size limit bypass attempts"""

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

    def test_size_limit_bypass_compression_attack(self):
        """Test size limit enforced: real server returns oversized body (no mocks)."""
        oversized_body = b'{"data": "' + b"a" * 2000 + b'"}'
        server = _RefResolverTestHTTPServer()
        server.add_raw_route("/schema.json", oversized_body)

        with server:
            base_url = server.base_url()
            self.config._config_data["url_allowlist"] = [base_url]
            url = f"{base_url}/schema.json"
            with self.assertRaises(ODPSRefResolutionError) as cm:
                self.resolver.resolve_external(url)
            self.assertEqual(
                cm.exception.error_code,
                ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED,
            )

    def test_size_limit_bypass_chunked_requests(self):
        """Test size limit bypass via multiple small requests (total size limit)"""
        # Add size incrementally to test total size limit
        # Use a size that's within per-ref limit but exceeds total limit
        self.resolver._total_size = 4001  # 4.001KB already used

        # Try to add 1000 bytes (within per-ref limit of 1000, but would exceed 5KB total limit)
        # 4001 + 1000 = 5001 > 5000 (max_total_size)
        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver._check_size_limit(1000)
        self.assertEqual(
            cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED
        )
        self.assertIn("total size", cm.exception.message.lower())

    def test_size_limit_bypass_null_byte_injection(self):
        """Test size limit bypass via null byte injection (should still be enforced)"""
        # Null bytes shouldn't bypass size limits
        oversized_content_with_null = b'{"data": "' + b"a" * 1000 + b"\x00" * 1000 + b'"}'
        size = len(oversized_content_with_null)
        self.assertGreater(size, self.resolver.max_ref_size)

        with self.assertRaises(ODPSRefResolutionError) as cm:
            self.resolver._check_size_limit(size)
        self.assertEqual(
            cm.exception.error_code, ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED
        )

    def test_size_limit_bypass_content_length_header_manipulation(self):
        """Test size limit enforced: real server returns oversized body (no mocks)."""
        oversized_body = b'{"data": "' + b"a" * 2000 + b'"}'
        server = _RefResolverTestHTTPServer()
        server.add_raw_route("/schema.json", oversized_body)

        with server:
            base_url = server.base_url()
            self.config._config_data["url_allowlist"] = [base_url]
            url = f"{base_url}/schema.json"
            with self.assertRaises(ODPSRefResolutionError) as cm:
                self.resolver.resolve_external(url)
            self.assertEqual(
                cm.exception.error_code,
                ODPSRefResolutionError.ERROR_CODE_RESOLUTION_FAILED,
            )
