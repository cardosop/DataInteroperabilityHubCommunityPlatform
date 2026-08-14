"""Build the filter-repo --replace-text file for the publish scrub (313.3.3).

Sources:
1. Secret-shaped values from the PRE-ROTATION env files committed at HEAD
   (SECRET_KEY, CKAN tokens, DB passwords, provider tokens) — extracted from
   git history itself, so no secret ever transits the conversation.
2. Internal hostnames (meshant.com subdomains, meshant-internal.example.com,
   meshant-internal.example.com) found in tracked text files.

Usage (inside a fresh `git clone --mirror` copy):
    python scripts/build_replace_text.py --out /tmp/replace_text.txt

The output maps each leaked value to a redacted placeholder and is consumed
by `git filter-repo --replace-text`.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

SECRET_KEY_RE = re.compile(r"KEY|SECRET|TOKEN|PASSWORD|JWT|CREDENTIAL", re.I)
HOSTNAME_RE = re.compile(
    r"[\w.-]+\.meshant\.com|wiki\.internal|grafana\.internal"
)
TEXT_SUFFIXES = (".md", ".py", ".yml", ".yaml", ".toml", ".txt", ".json", ".sh", ".js", ".ts", ".tsx", ".cjs", ".mjs", ".html", ".css", ".ini", ".cfg", ".env.example")

# Files whose values are local infrastructure defaults, not secrets — kept
# in the history on purpose (they were never secrets).
_SKIP_KEYS = {"POSTGRES_DB", "POSTGRES_HOST", "POSTGRES_PORT", "REDIS_HOST", "REDIS_PORT"}


def _git(*args: str) -> str | None:
    proc = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout


def collect(out: Path) -> int:
    entries: list[str] = []

    # 1) Pre-rotation env files at HEAD
    for f in (".env.dev", ".env.staging", ".env.test", ".env"):
        content = _git("show", f"HEAD:{f}")
        if not content:
            continue
        for line in content.splitlines():
            m = re.match(r"^([A-Z0-9_]+)=(.*)$", line.strip())
            if not m:
                continue
            key, value = m.group(1), m.group(2).strip().strip('"').strip("'")
            if key in _SKIP_KEYS or not value or len(value) <= 8:
                continue
            if SECRET_KEY_RE.search(key):
                entries.append(f"{value}==>REDACTED")
        for line in content.splitlines():
            if line.startswith("DATABASE_URL="):
                value = line.split("=", 1)[1].strip().strip('"')
                if value and len(value) > 8:
                    entries.append(f"{value}==>REDACTED")

    # 2) Internal hostnames in tracked text files
    tree = _git("ls-tree", "-r", "--name-only", "HEAD")
    hosts: set[str] = set()
    for path in (tree or "").splitlines():
        if not path.endswith(TEXT_SUFFIXES):
            continue
        content = _git("show", f"HEAD:{path}")
        if content:
            hosts.update(HOSTNAME_RE.findall(content))
    for host in sorted(hosts):
        entries.append(f"{host}==>meshant-internal.example.com")

    # Dedupe, keep order
    seen: set[str] = set()
    unique = [e for e in entries if not (e in seen or seen.add(e))]
    out.write_text("\n".join(unique) + "\n")
    return len(unique)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("/tmp/replace_text.txt"))
    args = parser.parse_args(argv)
    n = collect(args.out)
    print(f"replace-text written: {args.out} ({n} entries — values redacted from output)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
