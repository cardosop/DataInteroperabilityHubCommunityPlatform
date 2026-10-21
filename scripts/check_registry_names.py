#!/usr/bin/env python3
"""check_registry_names — W6.0 (oss-release-remediation) evidence tool.

Verifies the D3 publish-plan preconditions against the REAL registries:

  * the planned package names are free (pre-registration) or taken
    (post-registration);
  * the registry org accounts exist (npm scope + PyPI account);
  * the CI publish secrets are recorded in the deploy env (GitHub Actions).

No third-party dependencies: stdlib urllib for the registries, ``gh`` CLI
for the deploy env (the same tool the operator uses).

Usage:
  python scripts/check_registry_names.py                 # names available
  python scripts/check_registry_names.py --mode owned    # post-registration
  python scripts/check_registry_names.py --check-accounts
  python scripts/check_registry_names.py --check-secrets
  python scripts/check_registry_names.py --json

Exit codes: 0 = all checks pass; 1 = a precondition failed; 2 = a registry
was unreachable and the check could not run (local graceful; CI raises via
envpolicy — never silently "pass").

The D3 name table lives in ONE place (below) — the pins in
scripts/tests/test_check_registry_names.py assert the shipped package
metadata declares exactly these names (the namespace-collision guard).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

# D3 names (design.md "Fixes (per D3)", AMENDED 2026-10-12 in W6.0 — the
# npm org @datahub is third-party-owned; the scope is @meshant):
#   sdk/python → PyPI ``datahub-interoperability``
#   sdk/js     → npm  ``@meshant/interoperability-sdk``
#   cli        → PyPI ``datahub-cli``
PYPI_NAMES = ("datahub-interoperability", "datahub-cli")
NPM_PACKAGES = ("@meshant/interoperability-sdk",)
NPM_ORG = "meshant"
PYPI_ACCOUNT = "meshant"

# GitHub Actions secrets the publish workflows consume.
REQUIRED_SECRETS = ("NPM_TOKEN", "PYPI_TOKEN")
# Repo owner/name for the gh queries (single-remote unambiguous form).
DEFAULT_REPO = "cardosop/DataInteroperabilityHub"

# Overridable so the pins can drive the logic through a local threaded
# HTTP server (real round-trip, no mock libraries).
DEFAULT_PYPI_BASE = "https://pypi.org"
DEFAULT_NPM_BASE = "https://registry.npmjs.org"

TIMEOUT = 10.0


class RegistryUnreachable(RuntimeError):
    """A registry did not answer — the check could not run."""


def http_status(url: str, timeout: float = TIMEOUT) -> int | None:
    """Return the HTTP status for a GET, or None when the transport failed.

    Distinguishes three outcomes: HTTP response (any status), transport
    failure (unreachable), and DNS/timeout — the latter two are the
    "cannot verify" class, never "free".
    """
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (urllib.error.URLError, OSError, ValueError):
        return None


def pypi_name_state(name: str, base: str | None = None) -> dict:
    """Probe a PyPI project name. 404 = free; 200 = taken (owner metadata)."""
    base = base or DEFAULT_PYPI_BASE  # resolved at call time — pins override the module attribute
    url = f"{base}/pypi/{urllib.parse.quote(name)}/json"
    status = http_status(url)
    if status is None:
        raise RegistryUnreachable(f"PyPI unreachable: {base}")
    if status == 404:
        return {"registry": "pypi", "name": name, "state": "free"}
    if status == 200:
        return {"registry": "pypi", "name": name, "state": "taken"}
    return {"registry": "pypi", "name": name, "state": f"unexpected-{status}"}


def npm_package_state(package: str, base: str | None = None) -> dict:
    """Probe an npm package name (scoped names URL-encoded). 404 = free."""
    base = base or DEFAULT_NPM_BASE
    url = f"{base}/{urllib.parse.quote(package, safe='')}"
    status = http_status(url)
    if status is None:
        raise RegistryUnreachable(f"npm registry unreachable: {base}")
    if status == 404:
        return {"registry": "npm", "name": package, "state": "free"}
    if status == 200:
        return {"registry": "npm", "name": package, "state": "taken"}
    return {"registry": "npm", "name": package, "state": f"unexpected-{status}"}


def npm_org_exists(org: str = NPM_ORG, base: str | None = None) -> bool | None:
    """True when the npm org exists, False when absent, None when unreachable."""
    base = base or DEFAULT_NPM_BASE
    url = f"{base}/-/org/{urllib.parse.quote(org)}/package"
    status = http_status(url)
    if status is None:
        return None
    return status != 404


def pypi_account_exists(account: str = PYPI_ACCOUNT, base: str | None = None) -> bool | None:
    """True when the PyPI user/org account page exists (404 = absent)."""
    base = base or DEFAULT_PYPI_BASE
    url = f"{base}/user/{urllib.parse.quote(account)}/"
    status = http_status(url)
    if status is None:
        return None
    return status != 404


def gh_secret_presence(repo: str = DEFAULT_REPO) -> dict[str, bool]:
    """Query the deploy env (GitHub Actions) for the required secret NAMES.

    Uses the real ``gh`` CLI — never prints values, only names. A missing
    ``gh`` binary or unauthenticated call raises RuntimeError: the check
    cannot verify, which is the caller's "environment unavailable" case.
    """
    try:
        result = subprocess.run(
            ["gh", "secret", "list", "-R", repo],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("gh CLI not installed — cannot verify deploy-env secrets") from exc

    if result.returncode != 0:
        detail = (result.stderr or "").strip()[:200]
        raise RuntimeError(f"gh secret list failed ({result.returncode}): {detail}")

    recorded = {
        line.split()[0]
        for line in result.stdout.splitlines()
        if line.strip() and not line.lstrip().startswith(("NAME", "-"))
    }
    return {secret: (secret in recorded) for secret in REQUIRED_SECRETS}


def run_checks(mode: str, check_accounts: bool, check_secrets: bool,
               repo: str = DEFAULT_REPO) -> tuple[list[dict], bool]:
    """Run the requested checks. Returns (results, all_passed)."""
    results: list[dict] = []
    ok = True

    for name in PYPI_NAMES:
        state = pypi_name_state(name)
        results.append(state)
        if mode == "available" and state["state"] != "free":
            ok = False
        if mode == "owned" and state["state"] != "taken":
            ok = False

    for package in NPM_PACKAGES:
        state = npm_package_state(package)
        results.append(state)
        if mode == "available" and state["state"] != "free":
            ok = False
        if mode == "owned" and state["state"] != "taken":
            ok = False

    if check_accounts:
        npm_org = npm_org_exists()
        pypi_user = pypi_account_exists()
        if npm_org is None or pypi_user is None:
            raise RegistryUnreachable("an account probe was unreachable")
        results.append({"kind": "npm-org", "name": f"@{NPM_ORG}", "exists": npm_org})
        results.append({"kind": "pypi-account", "name": PYPI_ACCOUNT, "exists": pypi_user})
        if not npm_org or not pypi_user:
            ok = False

    if check_secrets:
        presence = gh_secret_presence(repo)
        for secret, present in presence.items():
            results.append({"kind": "gh-secret", "name": secret, "recorded": present})
            if not present:
                ok = False

    return results, ok


def render(results: list[dict], mode: str) -> None:
    """Human-readable report."""
    expected = "free" if mode == "available" else "taken"
    for r in results:
        if "state" in r:
            marker = "OK " if r["state"] == expected else "!! "
            print(f"{marker}{r['registry']:>4} {r['name']:<38} {r['state']}")
        elif r.get("kind") == "gh-secret":
            marker = "OK " if r["recorded"] else "!! "
            print(f"{marker}gh-secret {r['name']:<38} {'recorded' if r['recorded'] else 'MISSING'}")
        else:
            marker = "OK " if r["exists"] else "!! "
            print(f"{marker}{r['kind']:<14} {r['name']:<38} {'exists' if r['exists'] else 'ABSENT'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument(
        "--mode",
        choices=("available", "owned"),
        default="available",
        help="available = names must be FREE (pre-registration, default); "
             "owned = names must be TAKEN (post-registration gate)",
    )
    parser.add_argument("--check-accounts", action="store_true",
                        help="also verify the registry org accounts exist")
    parser.add_argument("--check-secrets", action="store_true",
                        help="also verify the GH Actions publish secrets are recorded")
    parser.add_argument("--repo", default=DEFAULT_REPO,
                        help=f"repo for --check-secrets (default: {DEFAULT_REPO})")
    parser.add_argument("--json", action="store_true",
                        help="emit one JSON object instead of the report")
    args = parser.parse_args(argv)

    try:
        results, ok = run_checks(args.mode, args.check_accounts, args.check_secrets, args.repo)
    except RegistryUnreachable as exc:
        # W16: in CI an unreachable registry fails loudly; local runs keep
        # the graceful "cannot verify" exit (2) — never a silent pass.
        if os.environ.get("CI", "") in ("true", "1"):
            raise SystemExit(f"[W16] CI cannot reach a registry: {exc}") from exc
        print(f"CANNOT VERIFY: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        if os.environ.get("CI", "") in ("true", "1"):
            raise SystemExit(f"[W16] CI cannot verify the deploy env: {exc}") from exc
        print(f"CANNOT VERIFY: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"mode": args.mode, "results": results, "passed": ok}, indent=2))
    else:
        render(results, args.mode)

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
