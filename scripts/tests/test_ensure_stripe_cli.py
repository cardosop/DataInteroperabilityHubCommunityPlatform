"""Contract pins for scripts/ensure-stripe-cli.sh (W2.10, pilot 4.3).

The installer provisions the repo-owned Stripe CLI that the
``billing-stripe-webhook`` E2E drives (``stripe listen`` /
``stripe subscriptions delete`` / ``stripe events resend``).  Three
properties are contractual:

  1. **Pinning** — the script's baked-in defaults name the EXACT release
     the repo tests against (version, tarball sha256, extracted-binary
     sha256).  The expected values are hardcoded here as the source of
     truth, so an unpinned bump, a typo'd hash, or a silent version
     change turns this suite RED without any network access.

  2. **Checksum enforcement** — a tarball whose sha256 does not match
     the expected value must FAIL the run and leave no binary behind
     (a tampered download can never become the repo's tool).

  3. **Idempotence** — a second run with an already-verified binary
     must not touch the network.

The behaviour pins drive the REAL script (subprocess) against a scripted
stdlib HTTP server that serves a crafted tarball — the wire protocol is
exercised, never replaced; there are no behavioural mocks.
"""

import hashlib
import http.server
import io
import pathlib
import re
import stat
import subprocess
import tarfile
import threading
from types import SimpleNamespace

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "ensure-stripe-cli.sh"

# Source of truth — the official stripe-cli v1.53.1 GitHub release.
# The tarball sha is stripe-linux-checksums.txt's entry for
# stripe_1.53.1_linux_x86_64.tar.gz; the binary sha is the extracted
# `stripe` binary's sha256.
PINNED_VERSION = "1.53.1"
PINNED_TARBALL_SHA = "032fe0b849a9d6a222488bc846445bafeae993af1026b78a8121d02321ca1fd1"
PINNED_BINARY_SHA = "79414e039e75062df696f3fb4a062321fa9642a1a6c0e4769c9723b47b1281c7"

# Env seams — test-only overrides so behaviour pins can drive a local
# server + crafted tarball.  Production runs use the baked-in defaults.
ENV_BASE_URL = "STRIPE_CLI_BASE_URL"
ENV_TOOLS_DIR = "STRIPE_CLI_TOOLS_DIR"
ENV_TARBALL_SHA = "STRIPE_CLI_SHA256"
ENV_BINARY_SHA = "STRIPE_CLI_BINARY_SHA256"

FAKE_BIN = "#!/bin/sh\necho fake-stripe\n"


class _TarballHandler(http.server.BaseHTTPRequestHandler):
    """Serves one crafted tarball and counts hits."""

    def log_message(self, *_args):
        pass

    def do_GET(self):
        self.server.hits.append(self.path)
        self.send_response(200)
        self.send_header("Content-Length", str(len(self.server.tarball)))
        self.end_headers()
        self.wfile.write(self.server.tarball)


@pytest.fixture
def tarball_server():
    """Serve a crafted tarball; return a handle with ``url`` and ``hits``."""
    servers = []

    def _serve(tarball_bytes):
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _TarballHandler)
        server.hits = []
        server.tarball = tarball_bytes
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append((server, thread))
        return SimpleNamespace(
            url=f"http://127.0.0.1:{server.server_address[1]}",
            hits=server.hits,
        )

    yield _serve

    for server, _thread in servers:
        server.shutdown()
        server.server_close()


def _make_tarball() -> bytes:
    """tar.gz containing an executable `stripe` stub."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        info = tarfile.TarInfo("stripe")
        payload = FAKE_BIN.encode()
        info.size = len(payload)
        info.mode = 0o755
        tar.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def _run_script(handle, tmp_path, tarball_bytes, overrides=None):
    """Run the real installer with the standard test seams set.

    The expected shas are computed from the CRAFTED tarball (the pins in
    the script name the official release, which the scripted server never
    serves) — this exercises the verification pipeline end to end.
    """
    env = {
        ENV_BASE_URL: handle.url,
        ENV_TOOLS_DIR: str(tmp_path / "tools-bin"),
        ENV_TARBALL_SHA: hashlib.sha256(tarball_bytes).hexdigest(),
        ENV_BINARY_SHA: hashlib.sha256(FAKE_BIN.encode()).hexdigest(),
    }
    if overrides:
        env.update(overrides)
    return subprocess.run(
        [str(SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


class TestPinnedDefaults:
    """The script's baked-in pin must name the official release."""

    def test_version_pinned(self):
        text = SCRIPT.read_text()
        match = re.search(r'^STRIPE_CLI_VERSION="([^"]+)"$', text, re.MULTILINE)
        assert match, "STRIPE_CLI_VERSION constant missing from script"
        assert match.group(1) == PINNED_VERSION

    def test_tarball_sha_pinned(self):
        text = SCRIPT.read_text()
        # Env-first assignment: the env override must WIN over the pin,
        # which the default side of the :- expansion carries.
        match = re.search(
            r'^STRIPE_CLI_SHA256="\$\{STRIPE_CLI_SHA256:-([^}]+)\}"$',
            text,
            re.MULTILINE,
        )
        assert match, "STRIPE_CLI_SHA256 env-first assignment missing from script"
        assert match.group(1) == PINNED_TARBALL_SHA

    def test_binary_sha_pinned(self):
        text = SCRIPT.read_text()
        match = re.search(
            r'^STRIPE_CLI_BINARY_SHA256="\$\{STRIPE_CLI_BINARY_SHA256:-([^}]+)\}"$',
            text,
            re.MULTILINE,
        )
        assert match, "STRIPE_CLI_BINARY_SHA256 env-first assignment missing from script"
        assert match.group(1) == PINNED_BINARY_SHA


class TestInstallBehaviour:
    """Drive the real script against a scripted HTTP server."""

    def test_installs_fresh_binary(self, tarball_server, tmp_path):
        tarball = _make_tarball()
        handle = tarball_server(tarball)
        result = _run_script(handle, tmp_path, tarball)
        assert result.returncode == 0, f"stderr: {result.stderr}"
        binary = tmp_path / "tools-bin" / "stripe"
        assert binary.exists(), "installer did not write the binary"
        assert binary.stat().st_mode & stat.S_IXUSR, "binary is not executable"

    def test_second_run_is_idempotent_no_network(self, tarball_server, tmp_path):
        tarball = _make_tarball()
        handle = tarball_server(tarball)
        first = _run_script(handle, tmp_path, tarball)
        assert first.returncode == 0, f"stderr: {first.stderr}"
        hits_after_first = len(handle.hits)
        second = _run_script(handle, tmp_path, tarball)
        assert second.returncode == 0, f"stderr: {second.stderr}"
        assert len(handle.hits) == hits_after_first, (
            "second run must not download when the verified binary exists"
        )

    def test_checksum_mismatch_fails_without_installing(self, tarball_server, tmp_path):
        tarball = _make_tarball()
        handle = tarball_server(tarball)
        result = _run_script(
            handle, tmp_path, tarball, overrides={ENV_TARBALL_SHA: "0" * 64}
        )
        assert result.returncode != 0, "mismatched tarball sha must fail"
        assert not (tmp_path / "tools-bin" / "stripe").exists(), (
            "failed verification must not leave a binary behind"
        )

    def test_binary_sha_mismatch_after_extract_fails(self, tarball_server, tmp_path):
        """Tarball verifies but the extracted binary is not the pinned one."""
        tarball = _make_tarball()
        handle = tarball_server(tarball)
        result = _run_script(
            handle, tmp_path, tarball, overrides={ENV_BINARY_SHA: "1" * 64}
        )
        assert result.returncode != 0, "extracted binary must match the pinned sha"
        assert not (tmp_path / "tools-bin" / "stripe").exists(), (
            "binary sha mismatch must not leave a binary behind"
        )

    def test_tools_dir_override_respected(self, tarball_server, tmp_path):
        tarball = _make_tarball()
        handle = tarball_server(tarball)
        custom = tmp_path / "custom-dir"
        result = subprocess.run(
            [str(SCRIPT)],
            env={
                ENV_BASE_URL: handle.url,
                ENV_TOOLS_DIR: str(custom),
                ENV_TARBALL_SHA: hashlib.sha256(tarball).hexdigest(),
                ENV_BINARY_SHA: hashlib.sha256(FAKE_BIN.encode()).hexdigest(),
            },
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert (custom / "stripe").exists(), "STRIPE_CLI_TOOLS_DIR override ignored"
