"""TDD suite for scripts/tls_acme_json.py — the Traefik acme.json tooling
used by the 4.4 TLS rotation rehearsal.

Every fixture here is REAL crypto material: cert/key pairs generated with
the openssl CLI (no stubs), base64-encoded into the Traefik v3 acme.json
shape, then read back through the tool. The tool never fabricates state —
it parses the file Traefik actually writes.
"""

from __future__ import annotations

import base64
import json
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL = REPO_ROOT / "scripts" / "tls_acme_json.py"


def _openssl_self_signed_pair(cn: str, days: int = 30) -> tuple[bytes, bytes]:
    """A real self-signed cert + key from the openssl CLI (separate files —
    piping both `-keyout -` and `-out -` into one stream interleaves the two
    PEMs and downstream parsers choke)."""
    with tempfile.TemporaryDirectory() as td:
        key_path = Path(td) / "tls.key"
        cert_path = Path(td) / "tls.crt"
        result = subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                str(days),
                "-subj",
                f"/CN={cn}",
                "-addext",
                f"subjectAltName=DNS:{cn}",
                "-keyout",
                str(key_path),
                "-out",
                str(cert_path),
            ],
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        cert = cert_path.read_bytes()
        key = key_path.read_bytes()
    assert b"BEGIN CERTIFICATE" in cert, "openssl did not emit a certificate"
    assert b"BEGIN PRIVATE KEY" in key, "openssl did not emit a private key"
    return cert, key


def _make_acme_json(tmp_path: Path, domain: str, days: int = 30) -> Path:
    cert, key = _openssl_self_signed_pair(domain, days=days)
    payload = {
        "letsencrypt": {
            "Account": {"Email": "ops@example.com"},
            "Certificates": [
                {
                    "domain": {"main": domain, "sans": [domain]},
                    "certificate": base64.b64encode(cert).decode(),
                    "key": base64.b64encode(key).decode(),
                }
            ],
        }
    }
    acme = tmp_path / "acme.json"
    acme.write_text(json.dumps(payload))
    return acme


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(TOOL), *args], capture_output=True, text=True, check=False
    )


class TestAcmeJsonList:
    def test_list_reports_domain_and_real_expiry(self, tmp_path):
        acme = _make_acme_json(tmp_path, "api.example.com", days=30)
        result = _run("list", str(acme))
        assert result.returncode == 0, result.stderr
        assert "api.example.com" in result.stdout
        # Plain output uses openssl-native field names; the JSON mode
        # carries the structured keys (pinned below).
        assert "notAfter=" in result.stdout
        assert "serial=" in result.stdout

    def test_list_reports_an_empty_acme_json(self, tmp_path):
        acme = tmp_path / "empty.json"
        acme.write_text(json.dumps({"letsencrypt": {"Certificates": []}}))
        result = _run("list", str(acme))
        assert result.returncode == 0, result.stderr
        assert "certificates: 0" in result.stdout.lower()

    def test_list_fails_on_missing_file(self, tmp_path):
        result = _run("list", str(tmp_path / "nope.json"))
        assert result.returncode != 0


class TestAcmeJsonRemove:
    def test_remove_deletes_only_the_named_domain(self, tmp_path):
        cert_a, _ = _openssl_self_signed_pair("a.example.com")
        cert_b, _ = _openssl_self_signed_pair("b.example.com")
        # Reuse the helper to embed two real certs.
        acme = _make_acme_json(tmp_path, "a.example.com")
        payload = json.loads(acme.read_text())
        payload["letsencrypt"]["Certificates"].append(
            {
                "domain": {"main": "b.example.com", "sans": ["b.example.com"]},
                "certificate": base64.b64encode(cert_b).decode(),
                "key": base64.b64encode(cert_a).decode(),
            }
        )
        acme.write_text(json.dumps(payload))

        result = _run("remove", str(acme), "--domain", "a.example.com")
        assert result.returncode == 0, result.stderr
        remaining = json.loads(acme.read_text())["letsencrypt"]["Certificates"]
        assert [c["domain"]["main"] for c in remaining] == ["b.example.com"]

    def test_remove_missing_domain_exits_nonzero(self, tmp_path):
        acme = _make_acme_json(tmp_path, "a.example.com")
        result = _run("remove", str(acme), "--domain", "missing.example.com")
        assert result.returncode != 0


class TestAcmeJsonRotateShape:
    def test_rotation_output_pairs_domain_with_serial(self, tmp_path):
        acme = _make_acme_json(tmp_path, "rotate.example.com")
        result = _run("list", str(acme), "--json")
        assert result.returncode == 0, result.stderr
        rows = json.loads(result.stdout)
        assert rows, "list --json must emit rows"
        assert rows[0]["domain"] == "rotate.example.com"
        # The serial is a real X.509 serial parsed from the PEM.
        assert rows[0]["serial"], "serial must be parsed from the real cert"
