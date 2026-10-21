# Changelog

All notable changes to the DataHub Interoperability JS SDK
(`@meshant/interoperability-sdk`) are documented here, following
[Keep a Changelog](https://keepachangelog.com/) and
[Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-10-14

### Added
- `DataHubClient` with API-key + JWT auth, retries, and error
  classification.

### Known limitation
- **W6.2 (blocker, xfail-pinned `TICKET=W62-axios-eviction
  EXPIRES=2026-11-01`)** — the transport still depends on the
  repo-evicted `axios` package; the public npm publish waits for the
  client eviction in W6.2.

## [Unreleased]
