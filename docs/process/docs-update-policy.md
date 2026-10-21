# Docs-Update-Per-PR Policy (281.A.10.6)

**Effective:** 2026-05-15  
**Owner:** Platform Engineering  
**Enforcement:** CI gate (`.github/workflows/docs-ci.yml`)

## Policy

### User-Facing PRs REQUIRE Documentation

A PR is **user-facing** if it:
- Adds, removes, or changes a user-visible feature or API endpoint
- Changes error messages, form labels, or UI copy
- Modifies authentication, authorization, or permission behavior
- Changes billing, pricing, or plan limits
- Adds or removes a configuration option
- Introduces a breaking change or deprecation

**Required docs for user-facing PRs:**
1. Update the changelog (`CHANGELOG.md`) with a user-facing entry
2. Update affected product documentation (persona guide, FAQ, glossary, API reference)
3. If the change affects a runbook procedure, update the runbook and note it in the PR description

### Docs-Only PRs ARE Accepted

PRs that only touch documentation files (`docs/`, `*.md`, `README.md`, `CHANGELOG.md`) are:
- Accepted without test coverage requirements
- Reviewed by at least 1 engineer (not necessarily a domain expert)
- Merged with a single approval (bypasses the standard 2-review requirement)

### Exemptions

A PR may skip documentation if:
- It is an internal refactor with zero user-visible behavior change
- It is a test-only change
- It is a dependency bump (security patch, minor version)
- The author explicitly notes `NO_DOCS: <reason>` in the PR description, AND a reviewer acknowledges the exemption

### CI Enforcement

The `docs-ci.yml` workflow runs on every PR that touches `docs/**` or user-facing code paths:
- Validates changelog entry format
- Checks for broken internal links
- Warns (does not block) if a user-facing PR has no changelog entry

### Reviewer Checklist

When reviewing a user-facing PR, verify:
- [ ] Changelog entry present with `### Added / Changed / Fixed / Deprecated / Removed` header
- [ ] Affected docs updated (persona guides, FAQ, glossary, API reference)
- [ ] Runbooks updated if operational procedure changed
- [ ] Breaking changes documented with migration guide
- [ ] Deprecations include sunset date + replacement path

### Changelog Entry Format

```markdown
## [vX.Y.Z] — YYYY-MM-DD

### Added
- **Feature name:** Brief description of what was added and who it benefits.

### Changed
- **Change:** What changed and what the previous behavior was.

### Fixed
- **Bug:** What was broken and how it was fixed.

### Deprecated
- **Feature name:** Deprecation notice with sunset date and replacement path.
```

### Exemption Examples

```
# PR: Refactor internal query builder — NO user-visible change
NO_DOCS: Internal refactor, zero behavior change

# PR: Bump django from 5.0.6 to 5.0.7 (security patch)
NO_DOCS: Dependency security patch, no user impact
```

### Review Cadence

- **Monthly:** Audit PRs that used NO_DOCS exemption; flag patterns of overuse
- **Quarterly:** Full documentation coverage audit against feature registry
