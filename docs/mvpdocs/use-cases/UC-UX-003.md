# UC-UX-003: Use Keyboard Shortcuts Cheatsheet

**Persona:** All authenticated users
**Phase:** 278 (UX Activation)
**Phase 278 Task:** `278.E.4`

## Description

An authenticated user presses the `?` key to open a keyboard shortcuts
cheatsheet overlay. The cheatsheet displays 3 groups of shortcuts:
Navigation (e.g., `g h` → Home, `g m` → Marketplace), Actions (e.g.,
`c` → Create Asset, `Cmd/Ctrl+K` → Command Palette), and Lists (e.g.,
`j/k` → move selection, `x` → toggle select). The overlay dismisses on
Escape, click-outside, or pressing `?` again.

## Preconditions

- The user is authenticated and the `KeyboardShortcuts` component is
  mounted in `App.tsx` (Phase 278.E.4).
- The `?` keypress listener skips INPUT/TEXTAREA elements to avoid
  interfering with text entry.

## Steps

1. User presses `?` anywhere in the app (outside an input field).
2. The `KeyboardShortcuts` overlay opens with `role="dialog"`.
3. User sees a heading "Keyboard Shortcuts" and 3 group sections:
   - **Navigation**: routes with keyboard shortcuts
   - **Actions**: verb-style commands
   - **Lists**: row-selection and navigation
4. Each shortcut is displayed in a `<kbd>` styled key (e.g., `g h`).
5. User reads the shortcuts and presses Escape, clicks outside the
   overlay, or presses `?` again to dismiss.

## Expected Outcome

- `?` key opens the cheatsheet overlay.
- Cheatsheet displays all 3 shortcut groups with correct key bindings.
- Escape, click-outside, and `?` toggle dismiss the overlay.
- `?` does NOT open when focus is in an INPUT or TEXTAREA element.
- Screen-reader: `role="dialog"` with accessible heading.

## Error Handling

| Condition | Expected Response |
|---|---|
| `?` pressed inside INPUT/TEXTAREA | Event skipped; overlay does not open |
| Overlay already open | `?` toggles closed |

## Related

- Components: `KeyboardShortcuts`
- Phase 278 tasks: `278.E.4` (Keyboard shortcuts cheatsheet)
- E2E: `keyboard-shortcuts-cheatsheet.spec.ts` (278.V.18)
