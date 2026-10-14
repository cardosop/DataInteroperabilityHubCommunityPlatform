"""
Contract tests for scripts/verify_privacy_pack.py (pilot-readiness 3.3).

The runner executes the REAL privacy pack over HTTP. These pins use a
scripted stdlib HTTP server that records every request — the wire
protocol is exercised for real, the responses are scripted:
- the DPIA flow keeps REAL role separation: the create/submit calls
  carry the TENANT_ADMIN bearer and the review call carries the DPO
  bearer (pinned, never the platform-admin bypass);
- the DPA agreement body carries the REAL sha256 of the addendum file;
- the RoPA artefact is downloaded and must be a PDF (magic bytes);
- the erasure probes never issue destructive calls (OPTIONS only;
  the request-erasure probe expects the handler's 400);
- no secret (password/token) ever appears in an error message.

The W16 environment policy applies to the main() probes: CI + missing
API raises; local + missing API skips; --strict turns the skip into a
failure.
"""

import hashlib
import importlib.util
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

import pytest

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

script_path = scripts_dir / "verify_privacy_pack.py"
spec = importlib.util.spec_from_file_location("verify_privacy_pack", script_path)
runner_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner_mod)

ADDENDUM_BODY = b"DPA addendum - Meshant (Processor) / Customer (Controller).\n"
ADDENDUM_SHA = hashlib.sha256(ADDENDUM_BODY).hexdigest()

ADMIN = "pilot_admin@example.com"
DPO = "pilot_dpo@example.com"
PLATFORM = "e2e_platform@example.com"
PASSWORD = "TestPass123"


class _Handler(BaseHTTPRequestHandler):
    """Scripted router: the ``routes`` dict maps (method, path-prefix) to a
    handler(method, path, body) -> (status, payload_dict_or_bytes)."""

    routes: ClassVar[dict] = {}
    log: ClassVar[list] = []

    def _handle(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        record = {
            "method": self.command,
            "path": self.path,
            "body": body.decode(),
            "auth": self.headers.get("Authorization"),
        }
        _Handler.log.append(record)
        # Longest-prefix wins — a list route must never shadow its own
        # detail/action routes (the insertion-order bug this guards).
        candidates = [
            (prefix, fn)
            for (method, prefix), fn in _Handler.routes.items()
            if method == self.command and self.path.startswith(prefix)
        ]
        if candidates:
            _prefix, fn = max(candidates, key=lambda item: len(item[0]))
            status, payload, *rest = fn(self.command, self.path, body)
            self._reply(status, payload, rest[0] if rest else None)
            return
        self._reply(404, {"detail": f"no route for {self.command} {self.path}"})

    def _reply(self, status, payload, headers=None):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if isinstance(payload, bytes):
            self.wfile.write(payload)
        else:
            self.wfile.write(json.dumps(payload).encode())

    do_GET = _handle
    do_POST = _handle
    do_OPTIONS = _handle

    def log_message(self, *_args):
        pass


@pytest.fixture
def server():
    _Handler.routes = {}
    _Handler.log = []
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def _json(status, payload):
    return status, payload


def _bearer(email):
    return f"Bearer token-{email}"


def _login_routes():
    _Handler.routes.update(
        {
            ("POST", "/api/v1/auth/login/"): lambda _m, _p, _b: _json(
                200, {"access_token": "token", "token_type": "Bearer", "expires_in": 3600}
            ),
        }
    )


def _tenant_routes():
    _Handler.routes.update(
        {
            ("GET", "/api/v1/tenants/"): lambda _m, _p, _b: _json(
                200,
                {
                    "results": [
                        {
                            "id": "aaaaaaa1-0001-4001-8001-000000000001",
                            "slug": "pilot-co",
                            "status": "ACTIVE",
                        }
                    ]
                },
            ),
        }
    )


def _dpia_routes(approved=True):
    record = {
        "id": "ddddddd1-0001-4001-8001-000000000001",
        "title": "Pilot CRM DPIA",
        "status": "APPROVED" if approved else "REJECTED",
        "next_review_due_at": "2027-10-05T00:00:00Z",
    }
    _Handler.routes.update(
        {
            ("GET", "/api/v1/assets/"): lambda _m, _p, _b: _json(
                200, {"results": [{"id": "aaaaaaa2-0002-4002-8002-000000000002",
                                   "key": "pilot-crm"}]}
            ),
            ("GET", "/api/v1/dpia/records/"): lambda _m, _p, _b: _json(200, {"results": []}),
            ("POST", "/api/v1/dpia/records/"): lambda _m, _p, _b: _json(
                201, {"id": record["id"], "status": "DRAFT"}
            ),
            ("POST", "/api/v1/dpia/records/dddddd"): lambda _m, _p, _b: _json(200, {"status": "IN_REVIEW"}),
            ("GET", "/api/v1/dpia/records/dddddd"): lambda _m, _p, _b: _json(200, record),
        }
    )
    if approved:
        _Handler.routes[("POST", "/api/v1/dpia/records/dddddd")] = lambda _m, _p, _b: _json(
            200, {"status": "APPROVED"}
        )
    else:
        _Handler.routes[("POST", "/api/v1/dpia/records/dddddd")] = lambda _m, _p, _b: _json(
            200, {"status": "REJECTED"}
        )


def _make_runner(server_url, addendum):
    api = runner_mod.Api(f"{server_url}/api/v1")
    return runner_mod.Runner(api, slug="pilot-co", addendum=addendum)


def _login(runner):
    # Raw tokens — the Api client adds the Bearer prefix itself.
    runner._admin_token = f"token-{ADMIN}"
    runner._dpo_token = f"token-{DPO}"
    runner._platform_token = f"token-{PLATFORM}"


def _calls(method, prefix):
    return [r for r in _Handler.log if r["method"] == method and r["path"].startswith(prefix)]


def test_login_uses_credentials_and_returns_token(server):
    _login_routes()
    api = runner_mod.Api(f"{server}/api/v1")
    token = api.login(ADMIN, PASSWORD)
    assert token == "token"
    call = _Handler.log[0]
    assert call["body"] == json.dumps({"email": ADMIN, "password": PASSWORD})
    assert "password" in call["body"]


def test_dpia_phase_role_separation(server, tmp_path):
    _login_routes()
    _tenant_routes()
    _dpia_routes()
    addendum = tmp_path / "addendum.md"
    addendum.write_bytes(ADDENDUM_BODY)
    runner = _make_runner(server, addendum)
    _login(runner)
    runner.phase_tenant()
    runner.phase_dpia()
    assert "APPROVED" in runner.results["dpia"]
    create = next(iter(_calls("POST", "/api/v1/dpia/records/")))
    review = next(
        r for r in _Handler.log if r["method"] == "POST" and r["path"].endswith("/review/")
    )
    submit = next(
        r for r in _Handler.log if r["method"] == "POST" and r["path"].endswith("/submit/")
    )
    assert create["auth"] == _bearer(ADMIN)
    assert submit["auth"] == _bearer(ADMIN)
    # The REVIEW must come from the DPO's bearer — the role check path,
    # never the platform-admin bypass.
    assert review["auth"] == _bearer(DPO)
    body = json.loads(review["body"])
    assert body["outcome"] == "APPROVED"
    assert body["risk_residual"] == "LOW"


def test_dpia_rejected_review_fails(server, tmp_path):
    _dpia_routes(approved=False)
    addendum = tmp_path / "addendum.md"
    addendum.write_bytes(ADDENDUM_BODY)
    runner = _make_runner(server, addendum)
    _login(runner)
    with pytest.raises(runner_mod.PrivacyPackError, match="REJECTED"):
        runner.phase_dpia()


def test_dpia_pre_existing_approved_short_circuits(server, tmp_path):
    record = {
        "id": "ddddddd1-0001-4001-8001-000000000001",
        "title": "Pilot CRM DPIA",
        "status": "APPROVED",
    }
    _Handler.routes.update(
        {
            ("GET", "/api/v1/assets/"): lambda _m, _p, _b: _json(200, {"results": []}),
            ("GET", "/api/v1/dpia/records/"): lambda _m, _p, _b: _json(
                200, {"results": [record]}
            ),
        }
    )
    addendum = tmp_path / "addendum.md"
    addendum.write_bytes(ADDENDUM_BODY)
    runner = _make_runner(server, addendum)
    _login(runner)
    runner.phase_dpia()
    assert "pre-existing" in runner.results["dpia"]
    assert not _calls("POST", "/api/v1/dpia/records/")


def test_ropa_sync_generation_downloads_pdf(server, tmp_path):
    generation = {
        "id": "eeeeeee1-0001-4001-8001-000000000001",
        "status": "COMPLETED",
        "byte_size": 7,
        "summary_json": {"asset_count": 1},
    }
    artefact = b"%PDF-1.7 fake ropa"
    _Handler.routes.update(
        {
            ("POST", "/api/v1/ropa/generate"): lambda _m, _p, _b: _json(
                201, {"id": generation["id"], "status": "COMPLETED", "async": False}
            ),
            ("GET", "/api/v1/ropa/generations/eeeee"): lambda _m, _p, _b: _json(
                200, generation
            ),
            ("GET", "/artifacts/ropa.pdf"): lambda _m, _p, _b: (200, artefact),
        }
    )
    # The download endpoint (longest prefix wins) returns a presigned URL
    # pointing back at the scripted server — the artefact fetch then
    # really happens over the wire.
    _Handler.routes[
        ("GET", "/api/v1/ropa/generations/eeeeeee1-0001-4001-8001-000000000001/download/")
    ] = lambda _m, _p, _b: _json(200, {"download_url": f"{server}/artifacts/ropa.pdf"})
    addendum = tmp_path / "addendum.md"
    addendum.write_bytes(ADDENDUM_BODY)
    runner = _make_runner(server, addendum)
    _login(runner)
    runner.phase_ropa()
    assert "COMPLETED" in runner.results["ropa"]
    fetched = _calls("GET", "/artifacts/ropa.pdf")
    assert fetched, "the presigned artefact was never downloaded"


def test_ropa_async_polls_until_completed(server, tmp_path):
    state = {"polls": 0}

    def _generation(_state):
        _state["polls"] += 1
        status = "COMPLETED" if _state["polls"] >= 2 else "PROCESSING"
        return {
            "id": "eeeeeee1-0001-4001-8001-000000000001",
            "status": status,
            "byte_size": 7,
            "summary_json": {"asset_count": 1},
        }

    _Handler.routes.update(
        {
            ("POST", "/api/v1/ropa/generate"): lambda _m, _p, _b: _json(
                202,
                {"ropa_generation_id": "eeeeeee1-0001-4001-8001-000000000001", "async": True},
            ),
            ("GET", "/api/v1/ropa/generations/eeeee"): lambda _m, _p, _b: _json(
                200, _generation(state)
            ),
            ("GET", "/artifacts/ropa.pdf"): lambda _m, _p, _b: (200, b"%PDF-1.7 fake"),
        }
    )
    _Handler.routes[
        ("GET", "/api/v1/ropa/generations/eeeeeee1-0001-4001-8001-000000000001/download/")
    ] = lambda _m, _p, _b: _json(200, {"download_url": f"{server}/artifacts/ropa.pdf"})
    runner_mod._ROPA_POLL_INTERVAL_S = 0.01
    addendum = tmp_path / "addendum.md"
    addendum.write_bytes(ADDENDUM_BODY)
    runner = _make_runner(server, addendum)
    _login(runner)
    runner.phase_ropa()
    assert state["polls"] >= 2


def test_ropa_non_pdf_artefact_fails(server, tmp_path):
    _Handler.routes.update(
        {
            ("POST", "/api/v1/ropa/generate"): lambda _m, _p, _b: _json(
                201, {"id": "eeeeeee1-0001-4001-8001-000000000001", "status": "COMPLETED"}
            ),
            ("GET", "/api/v1/ropa/generations/eeeee"): lambda _m, _p, _b: _json(
                200,
                {
                    "status": "COMPLETED",
                    "download_url": f"{server}/artifacts/ropa.pdf",
                    "byte_size": 7,
                    "summary_json": {},
                },
            ),
            ("GET", "/artifacts/ropa.pdf"): lambda _m, _p, _b: (200, b"GIF89a not a pdf"),
        }
    )
    addendum = tmp_path / "addendum.md"
    addendum.write_bytes(ADDENDUM_BODY)
    runner = _make_runner(server, addendum)
    _login(runner)
    with pytest.raises(runner_mod.PrivacyPackError, match="not a PDF"):
        runner.phase_ropa()


def test_dpa_registers_agreement_with_real_addendum_hash(server, tmp_path):
    _Handler.routes.update(
        {
            ("GET", "/api/v1/processor-agreements/processors/"): lambda _m, _p, _b: _json(
                200, {"results": []}
            ),
            ("POST", "/api/v1/processor-agreements/processors/"): lambda _m, _p, _b: _json(
                201, {"id": "fffffff1-0001-4001-8001-000000000001", "name": "Meshant"}
            ),
            ("GET", "/api/v1/processor-agreements/processor-agreements/"): (
                lambda _m, _p, _b: _json(200, {"results": []})
            ),
            ("POST", "/api/v1/processor-agreements/processor-agreements/"): (
                lambda _m, _p, _b: _json(
                    201,
                    {
                        "id": "fffffff2-0002-4002-8002-000000000002",
                        "status": "ACTIVE",
                        "agreement_type": "DPA",
                    },
                )
            ),
        }
    )
    addendum = tmp_path / "addendum.md"
    addendum.write_bytes(ADDENDUM_BODY)
    runner = _make_runner(server, addendum)
    _login(runner)
    runner.phase_dpa()
    assert "ACTIVE" in runner.results["dpa"]
    create = _calls("POST", "/api/v1/processor-agreements/processor-agreements/")[0]
    body = json.loads(create["body"])
    assert body["agreement_type"] == "DPA"
    assert body["document_hash"] == ADDENDUM_SHA
    assert body["document_uri"] == "https://example.com/dpa.pdf"
    assert body["registration_reference"] == "PILOT-DPA-2026-001"
    assert body["sub_processors_declared"] == [
        {"name": "AWS", "details": "Compute (EKS), object storage (S3)"},
        {"name": "Stripe", "details": "Payment processing (billing only)"},
        {"name": "SendGrid", "details": "Transactional email"},
    ]


def test_dpa_pre_existing_active_short_circuits(server, tmp_path):
    _Handler.routes.update(
        {
            ("GET", "/api/v1/processor-agreements/processors/"): lambda _m, _p, _b: _json(
                200,
                {"results": [{"id": "fffffff1-0001-4001-8001-000000000001",
                              "name": "Meshant"}]},
            ),
            ("GET", "/api/v1/processor-agreements/processor-agreements/"): (
                lambda _m, _p, _b: _json(
                    200,
                    {
                        "results": [
                            {
                                "id": "fffffff2-0002-4002-8002-000000000002",
                                "status": "ACTIVE",
                                "registration_reference": "PILOT-DPA-2026-001",
                                "document_hash": ADDENDUM_SHA,
                            }
                        ]
                    },
                )
            ),
        }
    )
    addendum = tmp_path / "addendum.md"
    addendum.write_bytes(ADDENDUM_BODY)
    runner = _make_runner(server, addendum)
    _login(runner)
    runner.phase_dpa()
    assert "pre-existing" in runner.results["dpa"]


def test_dpa_pre_existing_hash_mismatch_fails(server, tmp_path):
    _Handler.routes.update(
        {
            ("GET", "/api/v1/processor-agreements/processors/"): lambda _m, _p, _b: _json(
                200,
                {"results": [{"id": "fffffff1-0001-4001-8001-000000000001",
                              "name": "Meshant"}]},
            ),
            ("GET", "/api/v1/processor-agreements/processor-agreements/"): (
                lambda _m, _p, _b: _json(
                    200,
                    {
                        "results": [
                            {
                                "id": "fffffff2-0002-4002-8002-000000000002",
                                "status": "ACTIVE",
                                "registration_reference": "PILOT-DPA-2026-001",
                                "document_hash": "c" * 64,
                            }
                        ]
                    },
                )
            ),
        }
    )
    addendum = tmp_path / "addendum.md"
    addendum.write_bytes(ADDENDUM_BODY)
    runner = _make_runner(server, addendum)
    _login(runner)
    with pytest.raises(runner_mod.PrivacyPackError, match="document_hash"):
        runner.phase_dpa()


def test_erasure_phase_probes_without_destruction(server, tmp_path):
    _Handler.routes.update(
        {
            ("POST", "/api/v1/gdpr/export-jobs/export-data/"): lambda _m, _p, _b: _json(
                201,
                {
                    "job_id": "ddddddd2-0002-4002-8002-000000000002",
                    "status": "COMPLETED",
                    "download_url": f"{server}/exports/me.zip",
                },
            ),
            ("GET", "/api/v1/gdpr/export-jobs/"): lambda _m, _p, _b: _json(
                200,
                {
                    "id": "ddddddd2-0002-4002-8002-000000000002",
                    "status": "COMPLETED",
                    "download_url": f"{server}/exports/me.zip",
                },
            ),
            ("OPTIONS", "/api/v1/gdpr/erasure-requests/request-erasure/"): (
                lambda _m, _p, _b: (200, {}, {"Allow": "GET, POST, HEAD, OPTIONS"})
            ),
            ("OPTIONS", "/api/v1/tenants/"): lambda _m, _p, _b: (
                200,
                {},
                {"Allow": "GET, PUT, PATCH, DELETE, HEAD, OPTIONS"},
            ),
            ("OPTIONS", "/api/v1/admin/tenants/"): lambda _m, _p, _b: (
                200,
                {},
                {"Allow": "GET, DELETE, HEAD, OPTIONS"},
            ),
        }
    )
    addendum = tmp_path / "addendum.md"
    addendum.write_bytes(ADDENDUM_BODY)
    runner = _make_runner(server, addendum)
    _login(runner)
    runner._tenant_id = "aaaaaaa1-0001-4001-8001-000000000001"
    runner.phase_erasure()
    assert "export job" in runner.results["erasure"]
    assert "request-erasure" in runner.results["erasure"]
    assert "DELETE" in runner.results["erasure"]
    # The destructive leg must NEVER be issued: no POST to the erasure
    # endpoint at all (the live incident this pin guards — the endpoint
    # executes immediately and ignores the body), and no DELETE call.
    for call in _Handler.log:
        assert call["method"] != "DELETE"
        if "request-erasure" in call["path"]:
            assert call["method"] == "OPTIONS"


def test_erasure_export_not_completed_fails(server, tmp_path):
    _Handler.routes.update(
        {
            ("POST", "/api/v1/gdpr/export-jobs/export-data/"): lambda _m, _p, _b: _json(
                201, {"job_id": "ddddddd2-0002-4002-8002-000000000002"}
            ),
            ("GET", "/api/v1/gdpr/export-jobs/"): lambda _m, _p, _b: _json(
                200, {"id": "ddddddd2-0002-4002-8002-000000000002", "status": "FAILED"}
            ),
        }
    )
    addendum = tmp_path / "addendum.md"
    addendum.write_bytes(ADDENDUM_BODY)
    runner = _make_runner(server, addendum)
    _login(runner)
    with pytest.raises(runner_mod.PrivacyPackError, match="FAILED"):
        runner.phase_erasure()


def test_http_error_never_leaks_secrets(server, tmp_path):
    _Handler.routes.update(
        {
            ("POST", "/api/v1/auth/login/"): lambda _m, _p, _b: _json(
                500, {"detail": "internal"}
            ),
        }
    )
    api = runner_mod.Api(f"{server}/api/v1")
    with pytest.raises(runner_mod.PrivacyPackError) as exc_info:
        api.login(ADMIN, PASSWORD)
    message = str(exc_info.value)
    assert PASSWORD not in message
    assert ADMIN not in message


class TestMainPolicy:
    def test_unreachable_api_strict_exits_1(self, monkeypatch):
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "verify_privacy_pack.py",
                "--api-base",
                "http://127.0.0.1:1/api/v1",
                "--strict",
            ],
        )
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.delenv("MESHANT_API_URL", raising=False)
        with pytest.raises(SystemExit) as exc_info:
            runner_mod.main()
        assert exc_info.value.code == 1

    def test_unreachable_api_local_skips_exit_0(self, monkeypatch):
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "verify_privacy_pack.py",
                "--api-base",
                "http://127.0.0.1:1/api/v1",
            ],
        )
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.delenv("MESHANT_API_URL", raising=False)
        with pytest.raises(SystemExit) as exc_info:
            runner_mod.main()
        assert exc_info.value.code == 0

    def test_unreachable_api_ci_raises_w16(self, monkeypatch):
        from envpolicy import EnvironmentFailureError

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "verify_privacy_pack.py",
                "--api-base",
                "http://127.0.0.1:1/api/v1",
            ],
        )
        monkeypatch.setenv("CI", "true")
        with pytest.raises(EnvironmentFailureError):
            runner_mod.main()


def test_command_files_exist_in_repo():
    for path in runner_mod.COMMAND_FILES:
        assert path.exists()
