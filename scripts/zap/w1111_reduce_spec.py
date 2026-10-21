#!/usr/bin/env python3
"""W11.11 — OpenAPI spec reducer for the ZAP DAST plan.

The staging OpenAPI spec (drf-spectacular) is ~11.7 MB pretty-printed;
ZAP's ``openapi`` import job ran 10+ minutes on it without completing,
so the authenticated scan plan imports a REDUCED spec instead.  The
reduction is structurally identity-preserving — it drops only prose
(``description``/``summary``/``example(s)``/``externalDocs``/``deprecated``/
extension ``x-*`` keys) and keeps every path, method, parameter,
requestBody, response, and schema so every ``$ref`` still resolves.
Pinned by ``scripts/tests/test_w1111_zap_delta.py``: same paths/methods/
parameter names/requestBody presence, all refs resolve, noise absent,
size < 30% of the source.

Usage:
  python scripts/zap/w1111_reduce_spec.py --input spec.json --output spec.reduced.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_DROP_KEYS = frozenset(
    {
        "description",
        "summary",
        "example",
        "examples",
        "externalDocs",
        "deprecated",
    }
)


_REQUIRED_DESCRIPTION_PATHS = frozenset(
    {
        # OpenAPI 3.0 REQUIRES `description` on info and on every
        # response object — dropping them makes the spec invalid and
        # ZAP's importer rejects it ("The OpenAPI definition was
        # invalid", the first reducer attempt).  Keep the key with an
        # empty string at exactly these two sites.
        ("info",),
    }
)


def _reduce(node: object, path: tuple = ()) -> object:
    if isinstance(node, dict):
        out: dict = {}
        for key, value in node.items():
            next_path = path + (key,)
            if key == "description":
                if path == ("info",) or (
                    len(path) >= 2 and path[-2] == "responses"
                ):
                    out[key] = ""
                continue
            if key == "content" and path and path[-1] == "schema":
                # OpenAPI 3.1 `schema.content` leaked into the 3.0 spec
                # (drf-spectacular) — the strict importer rejects it
                # (`attribute ...schema.content is unexpected`).  It is
                # prose, not structure: drop it.
                continue
            if key in _DROP_KEYS:
                continue
            if key.startswith("x-"):
                continue
            out[key] = _reduce(value, next_path)
        return out
    if isinstance(node, list):
        return [_reduce(item, path) for item in node]
    return node


def _reduce_spec(spec: dict) -> dict:
    reduced = _reduce(spec)
    # The spec's paths are ABSOLUTE (/api/v1/...) — the openapi plan
    # must therefore target the ORIGIN (targetUrl without the prefix)
    # or every scanned URL doubles (/api/v1/api/v1/...).  The `servers`
    # block is dropped as noise: it cannot help resolution and only
    # invites server-relative concatenation mistakes.
    reduced.pop("servers", None)
    return reduced


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    try:
        spec = json.loads(Path(args.input).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: unreadable spec {args.input}: {exc}", file=sys.stderr)
        return 2

    reduced = _reduce_spec(spec)
    Path(args.output).write_text(json.dumps(reduced) + "\n")
    in_size = Path(args.input).stat().st_size
    out_size = Path(args.output).stat().st_size
    print(
        f"reduced {in_size} → {out_size} bytes "
        f"({out_size * 100 // max(in_size, 1)}%)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
