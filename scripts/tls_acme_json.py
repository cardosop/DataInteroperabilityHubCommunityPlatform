#!/usr/bin/env python3
"""Traefik acme.json tooling for the pilot-readiness 4.4 TLS rotation drill.

Reads and edits the REAL acme.json Traefik writes (v3 shape: resolver →
Certificates → {domain, certificate (b64 PEM), key (b64 PEM)}). No state is
fabricated: expiry/serial/issuer are parsed from the embedded PEM with the
openssl CLI, exactly as an operator would.

Subcommands:
    list FILE [--json]          — per-certificate domain/serial/not_after/issuer
    remove FILE --domain DOMAIN — drop ONE domain's certificate entry
                                  (the rotation trigger: Traefik re-requests
                                  on the next ACME challenge)
    stats FILE                  — resolver summary + soonest expiry

Exit codes: 0 success; 1 usage; 2 file/parse failure; 3 domain not found.
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path


def _openssl_x509(pem: bytes, *args: str) -> str:
    # input is BYTES — text=True would make subprocess try to .encode() it.
    result = subprocess.run(
        ["openssl", "x509", "-noout", *args],
        input=pem,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"openssl x509 failed: {result.stderr.decode().strip()}")
    return result.stdout.decode().strip()


def _cert_fields(entry: dict) -> dict[str, str]:
    pem = base64.b64decode(entry["certificate"])
    # The stored chain is PEM blocks; the FIRST certificate is the leaf.
    first = pem.split(b"-----END CERTIFICATE-----")[0] + b"-----END CERTIFICATE-----"
    serial = _openssl_x509(first, "-serial").removeprefix("serial=")
    not_after = _openssl_x509(first, "-enddate").removeprefix("notAfter=")
    issuer = _openssl_x509(first, "-issuer").removeprefix("issuer=")
    return {
        "domain": entry["domain"]["main"],
        "serial": serial,
        "not_after": not_after,
        "issuer": issuer,
    }


def _load(acme_path: Path) -> dict:
    try:
        payload = json.loads(acme_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read {acme_path}: {exc}", file=sys.stderr)
        sys.exit(2)
    return payload


def _certificates(payload: dict) -> list[dict]:
    out: list[dict] = []
    for resolver, state in payload.items():
        for entry in state.get("Certificates", []):
            row = _cert_fields(entry)
            row["resolver"] = resolver
            out.append(row)
    return out


def cmd_list(args: argparse.Namespace) -> int:
    payload = _load(Path(args.acme_json))
    rows = _certificates(payload)
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    print(f"certificates: {len(rows)}")
    for row in rows:
        print(
            f"  {row['domain']}  serial={row['serial']}  "
            f"notAfter={row['not_after']}  issuer={row['issuer'][:60]}"
        )
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    path = Path(args.acme_json)
    payload = _load(path)
    removed = 0
    for state in payload.values():
        kept = [e for e in state.get("Certificates", []) if e["domain"]["main"] != args.domain]
        removed += len(state.get("Certificates", [])) - len(kept)
        state["Certificates"] = kept
    if removed == 0:
        print(f"ERROR: no certificate for {args.domain} in {path}", file=sys.stderr)
        return 3
    path.write_text(json.dumps(payload))
    print(f"removed {removed} certificate entry for {args.domain} from {path}")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    payload = _load(Path(args.acme_json))
    rows = _certificates(payload)
    if not rows:
        print("certificates: 0")
        return 0
    soonest = min(rows, key=lambda r: r["not_after"])
    print(f"certificates: {len(rows)}")
    print(f"soonest expiry: {soonest['domain']} at {soonest['not_after']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="list certificates")
    p_list.add_argument("acme_json")
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_remove = sub.add_parser("remove", help="remove one domain's certificate")
    p_remove.add_argument("acme_json")
    p_remove.add_argument("--domain", required=True)
    p_remove.set_defaults(func=cmd_remove)

    p_stats = sub.add_parser("stats", help="resolver summary")
    p_stats.add_argument("acme_json")
    p_stats.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
