# Changelog

All notable changes to the DataHub Interoperability Python SDK
(`datahub-interoperability`) are documented here, following
[Keep a Changelog](https://keepachangelog.com/) and
[Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-10-14

### Added
- Async `DataHubClient` with API-key + JWT auto-refresh auth, retries,
  and error classification (DataHubError family).
- Module-per-surface API classes mirroring the CLI command tree.

### Fixed
- **W6.1** — the wheel build was broken (CWD-relative requirements
  read + setup.py/pyproject dual-config drift); now single-sourced in
  pyproject with PEP-639 license metadata.
- **W6.1** — the generated-py collision: regeneration now emits
  `packageName=datahub_generated_sdk`.

### Added (W6.4)
- RFC-8594 deprecation interceptor: deprecated API surfaces raise
  `DeprecationWarning` once per (endpoint, sunset date) pair — visible
  through the standard `warnings` machinery.

## [Unreleased]
