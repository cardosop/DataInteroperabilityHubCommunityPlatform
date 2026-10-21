# Changelog

All notable changes to the DataHub CLI (`datahub-cli`) are documented
here, following [Keep a Changelog](https://keepachangelog.com/) and
[Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-10-14

### Added
- Command tree for 54 API surfaces (assets, contracts, marketplace,
  governance, semantic, …) with `--format json|table` output.

### Changed
- **W6.3** — failed logins exit non-zero (1) with the failure on stderr;
  `datahub login` and `datahub auth login` are one implementation.
- **W6.3** — every `--format json` render routes through the canonical
  `print_json_output` helper (sorted keys, `default=str`, NaN-safe,
  paginated envelopes unwrapped to `results`).
- **W6.3** — the config file is created and healed to mode `0600`
  (it holds credentials); `--version` is single-sourced from
  `datahub_cli.__version__`.

### Fixed
- **W6.3** — 27 commands crashed with `TypeError` (called
  `api_client.post(..., json=)` while the client takes `json_data=`).

### Added (W6.4)
- RFC-8594 deprecation interceptor: deprecated API surfaces warn on
  stderr once per (endpoint, sunset date) pair.

## [Unreleased]
