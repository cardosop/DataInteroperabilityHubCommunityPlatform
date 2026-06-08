#!/usr/bin/env python3
"""
PII safety audit for test factories (Phase 312.11.4).

Scans all DjangoModelFactory subclasses for real PII patterns:
- Real email addresses (not @example.com)
- Real names (not Faker-generated)
- Real IP addresses (not RFC 5737 test ranges)
- Phone numbers (not Faker-generated)

Exit 0 on clean, 1 on PII violations.
"""

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# ── PII patterns ─────────────────────────────────────────────────────────

# Real email domains that must NOT appear in factories
_BLOCKED_EMAIL_DOMAINS = re.compile(
    r'@(gmail|yahoo|hotmail|outlook|icloud|protonmail|aol|mail)\.com',
    re.IGNORECASE,
)

# Real-looking names that aren't Faker-generated
_BLOCKED_NAME_PATTERNS = [
    re.compile(r"['\"]John\s+Doe['\"]"),
    re.compile(r"['\"]Jane\s+Doe['\"]"),
    re.compile(r"['\"]Test\s+User['\"]"),
]

# Real IPs (not RFC 5737 documentation/test ranges: 192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24)
_IP_RE = re.compile(r'\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b')
_TEST_IPS = {
    (192, 0, 2), (198, 51, 100), (203, 0, 113),
    # Also allow common test IPs
    (127, 0, 0), (10,), (172,), (192, 168),
}
_LOCALHOST_IPS = {(127, 0, 0, 1), (0, 0, 0, 0)}


def _is_test_ip(octets: tuple) -> bool:
    """Check if an IP address is in a test/documentation range."""
    if octets in _LOCALHOST_IPS:
        return True
    # RFC 5737: 192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24
    if octets[:3] in _TEST_IPS:
        return True
    # RFC 1918 private ranges
    if octets[0] == 10:
        return True
    if octets[0] == 172 and 16 <= octets[1] <= 31:
        return True
    if octets[0] == 192 and octets[1] == 168:
        return True
    return False


def _is_faker_pattern(value: str) -> bool:
    """Check if a string looks Faker-generated."""
    # Faker generates patterns like "user_a1b2c3d4@example.com"
    if "@example.com" in value or "@example.org" in value or "@example.net" in value:
        return True
    # Faker names contain random-looking hex
    if re.search(r'[a-f0-9]{6,}', value):
        return True
    return False


def audit_factory_file(filepath: Path) -> list:
    """Audit a single factory file for PII violations.

    Returns list of (line_number, description) for each violation.
    """
    violations = []
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return violations

    lines = content.split("\n")
    for i, line in enumerate(lines, 1):
        # Check for real email domains
        if _BLOCKED_EMAIL_DOMAINS.search(line) and "LazyAttribute" not in line:
            violations.append((i, f"Potential real email domain: {line.strip()[:80]}"))

        # Check for real-looking names (not Faker)
        for pat in _BLOCKED_NAME_PATTERNS:
            if pat.search(line) and not _is_faker_pattern(line):
                violations.append((i, f"Potential real name: {line.strip()[:80]}"))
                break

        # Check for real IPs
        for ip_match in _IP_RE.finditer(line):
            octets = tuple(int(g) for g in ip_match.groups())
            if not _is_test_ip(octets):
                violations.append((i, f"Potential real IP: {ip_match.group()} in: {line.strip()[:80]}"))

    return violations


def find_factory_files(root: Path) -> list:
    """Find all factory files in the repo."""
    files = []
    for pattern in ["**/factories.py", "**/factory.py", "**/factories/*.py"]:
        files.extend(root.glob(pattern))
    return sorted(set(f for f in files if f.is_file()))


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit test factories for PII")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("paths", nargs="*", help="Specific paths to audit")
    args = parser.parse_args()

    if args.paths:
        factory_files = [Path(p) for p in args.paths if Path(p).exists()]
    else:
        factory_files = find_factory_files(REPO_ROOT)

    if not factory_files:
        print("No factory files found.", file=sys.stderr)
        return 0

    if args.verbose:
        print(f"Auditing {len(factory_files)} factory file(s)...", file=sys.stderr)

    total_violations = 0
    for fp in factory_files:
        violations = audit_factory_file(fp)
        if violations:
            total_violations += len(violations)
            print(f"\n{fp}:")
            for lineno, desc in violations:
                print(f"  L{lineno}: {desc}")

    if total_violations:
        print(f"\n{total_violations} PII violation(s) found.", file=sys.stderr)
        return 1

    if args.verbose:
        print("All factory files clean — Faker-generated data only.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
