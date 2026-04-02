# Mypy Ratchet Strategy

**Owner**: Backend Team
**Target date**: 2026-06-30
**Date**: 2026-03-26
**Status**: Active

---

## Overview

This document defines the phased strategy for improving type safety across the Meshant codebase using mypy strict mode adoption.

## Current State

- mypy is configured in `pyproject.toml` / `setup.cfg` with baseline settings
- mypy runs in CI as a non-blocking check
- Core modules (`hub/apps/auth/`, `hub/apps/assets/`, `hub/apps/contracts/`) have partial type annotations

## Phased Strategy

### Phase 1: Foundation (Complete)
- Enable mypy in CI pipeline
- Configure `mypy.ini` / `pyproject.toml` with baseline strictness
- Add type stubs for third-party dependencies

### Phase 2: Core Modules (In Progress)
- Annotate all public APIs in `hub/apps/auth/`
- Annotate all public APIs in `hub/apps/assets/`
- Annotate all public APIs in `hub/apps/contracts/`
- Target: zero mypy errors in core modules

### Phase 3: Service Layer
- Annotate service layer functions across all apps
- Annotate serializer type hints
- Add `-> None` return annotations to all management commands

### Phase 4: Full Strict Mode
- Enable `--strict` flag globally
- Address remaining `Any` types
- Configure per-module overrides for third-party integration code

## Ratchet Mechanism

Each PR must not introduce new mypy errors:
- CI compares current error count against baseline
- If new errors exceed baseline, PR is blocked
- Baseline is updated (ratcheted down) when errors are fixed

## Configuration

See `pyproject.toml` for current mypy configuration and per-module overrides.
