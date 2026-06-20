#!/usr/bin/env python3
"""
TR.O.6 — Translation key completeness check.

All keys in EN locale file must exist in ES, PT, FR, AR, HE locale files.
Fails CI on missing keys.

Usage:
    python scripts/check_i18n_key_completeness.py
    python scripts/check_i18n_key_completeness.py --locales-dir frontend/src/i18n
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json_keys(filepath: Path) -> dict | None:
    """Load JSON file and return flat key set."""
    try:
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"  ⚠ Cannot parse {filepath.name}: {e}")
        return None
    return data if isinstance(data, dict) else {}


def extract_all_keys(data: dict, prefix: str = "") -> set[str]:
    """Recursively extract all dot-notation keys from a nested JSON dict."""
    keys = set()
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            keys.update(extract_all_keys(value, full_key))
        else:
            keys.add(full_key)
    return keys


def check_locale(en_data: dict, locale_data: dict | None, locale_name: str) -> list[str]:
    """Find keys in EN that are missing from the target locale."""
    if locale_data is None:
        return [f"{locale_name}: file missing or unparseable"]

    en_keys = extract_all_keys(en_data)
    locale_keys = extract_all_keys(locale_data)
    missing = en_keys - locale_keys
    return [f"{locale_name}: missing '{k}'" for k in sorted(missing)]


def run_check(locales_dir: Path) -> int:
    if not locales_dir.is_dir():
        print(f"Locales directory not found: {locales_dir}")
        return 0

    en_file = locales_dir / "en.json"
    if not en_file.exists():
        print(f"EN locale file not found: {en_file}")
        return 1

    en_data = load_json_keys(en_file)
    if en_data is None:
        return 1

    target_locales = ["es", "pt", "fr", "ar", "he"]
    all_missing: list[str] = []

    for locale in target_locales:
        locale_file = locales_dir / f"{locale}.json"
        locale_data = load_json_keys(locale_file)
        missing = check_locale(en_data, locale_data, locale)
        all_missing.extend(missing)

    if all_missing:
        print(f"i18n key completeness FAILED — {len(all_missing)} missing key(s):")
        for m in all_missing:
            print(f"  - {m}")
        return 1

    print(f"i18n key completeness PASSED — all {len(target_locales)} locales match EN keys.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="TR.O.6 — i18n key completeness check")
    parser.add_argument("--locales-dir", type=Path, default=Path("frontend/src/i18n"))
    args = parser.parse_args()
    return run_check(args.locales_dir)


if __name__ == "__main__":
    raise SystemExit(main())
