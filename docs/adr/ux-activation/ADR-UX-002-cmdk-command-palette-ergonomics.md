# ADR-UX-002 — Cmd-K Command Palette Ergonomics

- **Status**: accepted
- **Date**: 2026-05-13
- **Deciders**: Frontend team
- **Stakeholders**: Data Engineers, Platform Admins (primary power-user personas)

## Context

Phase 278.E.1 required a global command palette for power-user navigation. The palette was already implemented in Phase 223.5.3 using the `cmdk` library. This ADR documents the ergonomic choices made during that implementation and validated during Phase 278 audit.

Key design tensions:
1. Keyboard shortcut convention (Cmd-K vs Ctrl-K vs platform-adaptive).
2. Search algorithm (prefix match vs fuzzy vs hybrid).
3. Scope of discoverable commands (navigation-only vs actions + navigation).

## Decision

1. **Platform-adaptive shortcut:** `Cmd-K` on macOS, `Ctrl-K` on Windows/Linux — detected via `navigator.platform`. This follows OS convention and avoids the discoverability problem of a custom chord.

2. **Fuzzy search via `cmdk`:** The library provides built-in fuzzy matching with weighted scoring. Commands are filtered as the user types; no prefix-only limitation. This accommodates users who recall a feature's function but not its exact menu label.

3. **Navigation-first scope with action extensibility:** The initial palette surfaces route navigation (pages, sub-pages) and keyboard shortcut discoverability. Action commands (create asset, run DQ scan, publish listing) can be registered via `useCommandPaletteActions()` hook — the registration point exists but the action catalog is populated incrementally per feature team.

4. **No per-persona command filtering:** All registered commands are visible to all users. Routes that a user cannot access (RBAC-gated) fail gracefully with a toast rather than being hidden — this avoids the confusion of "I know this exists but I can't find it."

## Consequences

- **Positive:** Single keyboard shortcut reaches any page in the application; reduces time-to-first-action for power users.
- **Positive:** `cmdk` provides built-in a11y (combobox pattern, arrow-key navigation, screen-reader announcements).
- **Neutral:** Action commands are opt-in per feature team; palette is navigation-heavy until teams register their actions.
- **Negative:** Fuzzy matching can surface unexpected results for very short queries (1-2 chars). Mitigated by minimum 2-char trigger.

## Cross-references

- Implementation: Phase 223.5.3 (command palette), `frontend/src/shared/components/CommandPalette.tsx`
- Integration: `frontend/src/AppShell.tsx`
- Library: `cmdk` (https://cmdk.paco.me)
- Related: Phase 278.E.1 (Cmd-K task), Phase 278.E.4 (KeyboardShortcuts cheatsheet)
