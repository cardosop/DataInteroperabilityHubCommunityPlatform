# Design Decisions

**Last Updated**: 2026-03-07

This document records design decisions for the Data Interoperability Hub platform.

---

## Notifications (Header)

**Decision**: Implement minimal notifications placeholder in the header.

**Context**: The header included a notifications button (bell icon) that toggled state but displayed nothing when clicked, creating a dead UI element.

**Options considered**:
1. **Remove the button** — Clean removal; users would not see a non-functional control.
2. **Implement minimal placeholder** — Show a dropdown with empty state when clicked; sets expectations for future functionality.
3. **Implement full notifications** — Requires backend API, real-time updates, persistence; out of scope for current phase.

**Chosen**: Option 2 — Minimal placeholder.

**Implementation**:
- Notifications button remains in the header (bell icon with badge showing "0").
- When clicked, a dropdown opens with:
  - Title: "No notifications yet"
  - Message: "Notifications will appear here when you have updates (e.g. access requests, DQ results)."
- Click outside or Escape key closes the dropdown.
- Dropdown uses `role="region"` (informational content; not `role="menu"` which requires menu items).
- No backend integration; placeholder only.

**Future work**: When notifications backend is available (e.g. from audit events, access requests, DQ run completion), the dropdown will be extended to display real notification items. See `frontend/src/features/shell/components/Header.tsx` and `Header.css` for the implementation.
