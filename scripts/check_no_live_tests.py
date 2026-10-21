#!/usr/bin/env python3
"""
pilot-readiness 1.5 — destructive-stack-operation guard.

Refuse (exit 1) when any live pytest/playwright run is active on the
host or inside a running container.  Used by ``make test-stack-reinit``
before it wipes the minio-test-data volume — an in-flight S3 batch would
corrupt mid-run (pilot-readiness 1.4 rehearsal finding).

Self-match immunity: the pattern is built by string concatenation, so
the literal ``pytest`` never appears in this source, in this process'
command line, or in any parent wrapper that quotes this file's text.
Containers are scanned with ``docker top`` (host-side process view) —
no shell is needed inside scratch containers (redis-exporters,
mock-server) where ``docker exec sh`` fails.

Exit 0 when nothing live was found, 1 otherwise.  Prints findings
(process command lines and container names) — never secrets.
"""

from __future__ import annotations

import os
import subprocess
import sys

# the literals are split so they can never appear in this source/cmdline
_PYTEST = "py" + "test"
_PLAYWRIGHT = "play" + "wright"


def classify_line(line: str) -> bool:
    """True when a ps/top command line INVOKES a live test run.

    Token-based, not substring-based: IDE tooling that merely names a
    ``*_pytest_options.py`` helper file is not a live run (VSCode Pylance
    false positive found during the pilot-readiness 1.5 rehearsal).
    """
    tokens = line.split()
    for i, tok in enumerate(tokens):
        # `pytest`, `/venv/bin/pytest`, `python -m pytest`
        if tok == _PYTEST or tok.endswith(("/" + _PYTEST, "/py.test")):
            return True
        if tok == "-m" and i + 1 < len(tokens) and tokens[i + 1] == _PYTEST:
            return True
    # `playwright test`, `npx playwright test`, `playwright@1.49.1 test`
    invokes_playwright = any(
        tok == _PLAYWRIGHT
        or tok.endswith("/" + _PLAYWRIGHT)
        or tok.startswith(_PLAYWRIGHT + "@")
        for tok in tokens
    )
    return invokes_playwright and "test" in tokens


def _ancestor_pids(pid: int) -> set[int]:
    """PIDs of every ancestor of ``pid`` (walk /proc, real process tree)."""
    ancestors: set[int] = set()
    current = pid
    while current > 1:
        try:
            with open(f"/proc/{current}/stat") as f:
                ppid = int(f.read().split()[3])  # field 4: parent pid
        except (OSError, ValueError, IndexError):
            break
        if ppid in ancestors or ppid <= 1:
            ancestors.add(ppid)
            break
        ancestors.add(ppid)
        current = ppid
    return ancestors


def host_live_lines() -> list[str]:
    """Command lines of live test processes on the host.

    The scanner's own process ancestry is excluded: a caller's wrapper
    shell may legitimately contain the pattern text (e.g. a compound
    command invoking a test batch alongside the guard) without being a
    live test run.
    """
    out = subprocess.run(
        ["ps", "-eo", "pid=,args="], capture_output=True, text=True, check=False
    )
    me = os.getpid()
    skip = _ancestor_pids(me) | {me}
    lines = []
    for ln in out.stdout.splitlines():
        try:
            pid = int(ln.strip().split()[0])
        except (ValueError, IndexError):
            continue
        if pid in skip:
            continue
        if classify_line(ln):
            lines.append(ln)
    return lines


def containers_with_live_tests() -> list[str]:
    """Names of running containers with live test processes inside."""
    names = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    hits: list[str] = []
    for name in names.stdout.splitlines():
        if not name:
            continue
        top = subprocess.run(
            ["docker", "top", name], capture_output=True, text=True, check=False
        )
        if top.returncode != 0:
            continue  # container exited mid-scan — nothing live to find
        if any(classify_line(ln) for ln in top.stdout.splitlines()):
            hits.append(name)
    return hits


def evaluate(host_lines: list[str], container_hits: list[str]) -> int:
    """Report findings and return the exit code (0 clean, 1 live found)."""
    if host_lines:
        print("LIVE TEST RUNS ON HOST:")
        for line in host_lines:
            print(f"  {line}")
    if container_hits:
        print("LIVE TEST RUNS IN CONTAINERS:")
        for name in container_hits:
            print(f"  {name}")
    if host_lines or container_hits:
        print("ABORT: live test runs detected — maintenance window required.")
        return 1
    print("no live pytest/playwright runs found (host + containers)")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if argv:
        print(__doc__)
        print(f"usage: {sys.argv[0]}  (no arguments)")
        return 2
    return evaluate(host_live_lines(), containers_with_live_tests())


if __name__ == "__main__":
    sys.exit(main())
