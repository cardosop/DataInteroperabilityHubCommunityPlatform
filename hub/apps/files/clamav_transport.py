"""Low-level clamd transport for startup probes (Phase 260.0.17)."""

from __future__ import annotations
import re
import socket


def read_clamd_version_banner(
    host: str,
    port: int,
    *,
    timeout_seconds: float = 10.0,
) -> str:
    """
    Execute clamd ``VERSION`` over TCP (``z``-terminated wire format per clamd.8).

    Raises:
        OSError — connection / timeout / malformed reply.
    """
    payload = b"zVERSION\x00"
    with socket.create_connection((host, int(port)), timeout=timeout_seconds) as sock:
        sock.settimeout(timeout_seconds)
        sock.sendall(payload)
        chunks: list[bytes] = []
        while True:
            part = sock.recv(4096)
            if not part:
                break
            chunks.append(part)
            if b"\x00" in part:
                break
    raw = b"".join(chunks).split(b"\x00", 1)[0].decode("utf-8", errors="replace").strip()
    if not raw:
        raise OSError(f"clamav_daemon_empty_version_reply host={host!r}")
    return raw


def parse_clamd_semver(version_banner: str) -> tuple[int, int, int]:
    """
    Extract ``(major, minor, patch)`` tuples from banners like ``ClamAV 1.4.2/…``.
    """
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", version_banner)
    if not m:
        raise ValueError(f"clamav_daemon_unparseable_banner:{version_banner!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def version_meets_minimum(
    *,
    daemon_banner: str,
    required_text: str,
) -> tuple[bool, str]:
    """Return ``(True, effective_semver_text)`` when daemon semver >= requirement."""
    daemon_ver = parse_clamd_semver(daemon_banner)
    parts = required_text.strip().split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError("required_semver_must_be_major.minor.patch_digits")
    need = tuple(int(p) for p in parts)
    if daemon_ver < need:
        return False, ".".join(str(x) for x in daemon_ver)
    return True, ".".join(str(x) for x in daemon_ver)
