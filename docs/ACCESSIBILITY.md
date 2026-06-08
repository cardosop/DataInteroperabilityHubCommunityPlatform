# Accessibility Compliance — Meshant Platform

**Owner:** platform-eng@meshant.com | **Last Updated:** 2026-05-20

## Standards

Meshant targets **WCAG 2.1 Level AA** compliance across all user-facing pages.

## Architecture

- **All modals:** `role="dialog"` + `aria-modal="true"` + `aria-labelledby`
- **All form controls:** `<label htmlFor>` paired with `<input id>`
- **All error states:** `role="alert"` on error messages
- **All interactive elements:** `data-testid` for test targeting
- **Keyboard navigation:** Tab order follows DOM order; Enter/Space for buttons; Escape for modals
- **Focus management:** Focus trap in modals; focus return on close
- **Color contrast:** CSS `var(--color-*)` tokens meet WCAG AA ratios (4.5:1 for text, 3:1 for large text)

## Automated Testing

- axe-core audit on every PR via `check_a11y_violation_ratchet.mjs`
- Playwright E2E tests include keyboard navigation assertions
- CI blocks PRs that introduce new accessibility violations

## Known Limitations

- GraphQL-LD query editor: no screen-reader announcement for query results
- Transformation wizard: drag-and-drop step reordering not keyboard-accessible (alternative: step order dropdown)
- Dark mode: some third-party component libraries may not fully respect `[data-theme='dark']`

## Review Cadence

- axe audit on every PR (automated)
- Manual keyboard audit every release
- Full WCAG 2.1 AA audit annually
