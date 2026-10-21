# UC-UX-002: Use Global Command Palette

**Persona:** All authenticated users
**Phase:** 223 (Shell + Sidebar), 278 (UX Activation)
**Phase 278 Task:** `278.E.1` (Cmd-K / Ctrl-K global command palette)

## Description

An authenticated user presses Cmd-K (Mac) or Ctrl-K (Linux/Windows) to
open a global command palette that provides fuzzy search across all
available navigation pages and quick actions. The palette groups results
into Recent (from localStorage), Pages (sidebar routes filtered by role
and capabilities), and Actions (verb-style shortcuts). Selecting a result
navigates to the route. The palette closes on Escape.

## Preconditions

- The user is authenticated (palette is mounted inside AppShell which
  requires auth).
- The palette keyboard shortcut is registered via `useKeyboardShortcut`.

## Steps

1. User presses Cmd-K / Ctrl-K. The `CommandPalette` opens a
   `Command.Dialog` overlay.
2. A search input (`.command-palette-input`) is auto-focused.
3. User types to fuzzy-filter across: Recent items (last ≤8 navigated
   routes via the palette), Pages (filtered sidebar nav items), and
   Actions (verb-style shortcuts like "Create Asset").
4. Results appear grouped under "Recent", "Pages", and "Actions"
   headings (`.command-palette-group`).
5. User navigates results via arrow keys or continues typing to refine
   the fuzzy match.
6. User presses Enter on a highlighted item or clicks it. The palette
   closes, the route is navigated to, and the item is prepended to the
   Recent list in localStorage (`meshant.palette.recent`).
7. If no results match, the palette shows `.command-palette-empty` with
   "No results."
8. User presses Escape at any time to close the palette.

## Expected Outcome

- Cmd-K / Ctrl-K toggles the palette open/closed.
- Typing filters results with fuzzy matching (cmdk library).
- Selecting a result navigates to the correct route.
- Recent items are persisted across sessions and tab reloads.
- Screen-reader: Radix Dialog provides `Dialog.Title` ("Command palette")
  and `Dialog.Description` in sr-only. cmdk provides `role="combobox"`
  on the input and `role="listbox"` + `role="option"` on results.

## Error Handling

| Condition | Expected Response |
|---|---|
| No results match search | "No results." empty state shown |
| Unauthenticated user | Palette does not render (inside AppShell) |

## Related

- Components: `CommandPalette`, `cmdk` (library), `useKeyboardShortcut`
- Phase 278 tasks: `278.E.1` (Cmd-K palette)
- E2E: `command-palette-cmdk.spec.ts` (278.V.19)
