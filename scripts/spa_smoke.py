#!/usr/bin/env python3
"""
pilot-readiness 1.6 — production-build SPA smoke.

Verifies a PRODUCTION frontend build the way a browser's first load
would: a real stdlib HTTP server serves the real dist output, the smoke
fetches index.html, asserts the SPA shell, fetches every referenced
asset (a missing chunk must fail), and — when ``--api-base`` is given —
checks that the VITE_API_BASE_URL literal is baked into the JS bundle.
A build made without the right API base silently points the pilot SPA
at the wrong API (the U.8 trap), so this is a blocking check.

Usage:
    python scripts/spa_smoke.py --dist frontend/dist --api-base /api/v1
    python scripts/spa_smoke.py --dist frontend/dist --port 8931

No mocks — real files, real HTTP against 127.0.0.1. Exit 0/1.
"""

from __future__ import annotations

import argparse
import contextlib
import functools
import http.server
import re
import sys
import threading
import urllib.request
from pathlib import Path

# any same-origin asset path — the repo's build emits to /static/ (custom
# assetsDir), NOT vite's default /assets/, so nothing is hardcoded here.
_ASSET_RE = re.compile(r"(?:src|href)=['\"](/[^'\"]+\.(?:js|css))['\"]")
_ROOT_RE = re.compile(r'<div[^>]+id="root"')


def assert_shell(index_text: str) -> list[str]:
    """Violations when the index.html is not a mountable SPA shell."""
    violations = []
    if not _ROOT_RE.search(index_text):
        violations.append("index.html has no <div id=\"root\"> mount point")
    if "<script" not in index_text:
        violations.append("index.html references no script bundle")
    return violations


def extract_assets(index_text: str) -> list[str]:
    return sorted(set(_ASSET_RE.findall(index_text)))


def api_base_baked(index_text: str, dist: Path, api_base: str) -> bool:
    """True when the EXACT quoted API-base literal appears in a JS file
    the index.html actually references.

    Q1 (W0.10): the previous check was vacuous in two directions — a
    bare substring search passes a bundle baked with a WRONG absolute
    base ("https://staging.example.com/api/v1" contains "/api/v1"), and
    scanning every ``*.js`` under dist lets stale build litter satisfy
    the check while the entry bundle points elsewhere. The exact quoted
    literal is what vite bakes for ``import.meta.env`` values
    (JSON.stringify → double quotes), so only that form decides; route
    literals ("/api/v1/ml/...") never match it.
    """
    pattern = re.compile(r"['\"]" + re.escape(api_base) + r"['\"]")
    for asset in extract_assets(index_text):
        if not asset.endswith(".js"):
            continue
        js_file = dist / asset.lstrip("/")
        if not js_file.is_file():
            continue  # the asset loop reports missing chunks; never crash here
        js = js_file.read_text(errors="replace")
        if pattern.search(js):
            return True
    return False


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # keep smoke output clean
        pass


@contextlib.contextmanager
def serve(dist: Path, port: int = 0):
    """Serve ``dist`` on 127.0.0.1; yields the base URL."""
    handler = functools.partial(_QuietHandler, directory=str(dist))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def smoke_dist(dist: Path, api_base: str | None) -> list[str]:
    """All violations of the dist under a real HTTP round-trip."""
    violations: list[str] = []
    index_file = dist / "index.html"
    if not index_file.is_file():
        return ["dist/index.html not found"]
    index_text = index_file.read_text()

    with serve(dist) as base:
        try:
            with urllib.request.urlopen(f"{base}/", timeout=10) as resp:
                resp.read()  # drain fully — avoids a server-side broken pipe
                if resp.status != 200:
                    violations.append(f"GET / returned {resp.status}")
                elif "text/html" not in resp.headers.get("Content-Type", ""):
                    violations.append("GET / is not served as text/html")
        except OSError as exc:
            violations.append(f"GET / failed: {exc}")

        violations.extend(assert_shell(index_text))

        asset_failures = 0
        for asset in extract_assets(index_text):
            try:
                with urllib.request.urlopen(f"{base}{asset}", timeout=10) as resp:
                    resp.read()
                    if resp.status != 200:
                        asset_failures += 1
                        violations.append(f"asset {asset} returned {resp.status}")
            except OSError as exc:
                asset_failures += 1
                violations.append(f"asset {asset} failed: {exc}")

    # The baked-base check only adds its violation when every referenced
    # asset actually loaded — a missing chunk is its own (precise)
    # violation; piling the baked verdict on top would misattribute it.
    if api_base and asset_failures == 0 and not api_base_baked(index_text, dist, api_base):
        violations.append(
            f"VITE_API_BASE_URL={api_base} is not baked into the JS bundle — "
            "the build was made with the wrong API base (U.8 trap)"
        )
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=Path("frontend/dist"))
    parser.add_argument(
        "--api-base",
        help="expected VITE_API_BASE_URL literal baked into the bundle",
    )
    args = parser.parse_args(argv)

    violations = smoke_dist(args.dist, args.api_base)
    if violations:
        for v in violations:
            print(f"SPA-SMOKE FAIL: {v}")
        return 1
    print("SPA-SMOKE PASS: shell + assets + baked API base verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
