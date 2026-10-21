# UC-UX-004: View Inline Help for Jargon Terms

**Persona:** All authenticated users
**Phase:** 278 (UX Activation)
**Phase 278 Task:** `278.D.3` (Inline term definitions / glossary tooltips)

## Description

A user encounters a domain-specific term (e.g., "ODPS", "KYB", "DSAR",
"DQR", "RoPA") in the Meshant UI. Hovering over or focusing the term
displays an inline tooltip with a plain-language definition and an
optional "Learn more" link to the relevant documentation. This reduces
the onboarding friction for new users and provides just-in-time context
for infrequent users.

## Preconditions

- The `GlossaryTooltip` component is wrapped around jargon terms in the
  UI (inline in page content, form labels, and table headers).
- A glossary of terms is defined (static JSON or CMS-driven).

## Steps

1. User navigates to a page containing a jargon term (e.g., the
   governance page header mentions "DSAR").
2. User hovers over the underlined term. A tooltip appears with:
   - **Term name** in bold
   - **Definition** (1–2 sentences in plain language)
   - **Learn more** link to `/docs/glossary#term` (optional)
3. User moves the mouse away. The tooltip dismisses after a short delay.
4. User tabs to the term via keyboard. The tooltip appears on focus and
   dismisses on blur.
5. The tooltip is positioned responsively — above/below the term based
   on viewport space.

## Expected Outcome

- Jargon terms are visually distinguishable (dotted underline or
  different color).
- Hover/focus reveals a tooltip with definition.
- Tooltip is keyboard-accessible (Tab to term → Enter/Space to open,
  Escape to close).
- "Learn more" link navigates to the correct documentation anchor.
- No layout shift when tooltip appears/disappears.

## Error Handling

| Condition | Expected Response |
|---|---|
| Term not in glossary | Renders without underline (plain text) |
| Docs page unavailable | "Learn more" link omitted; tooltip still shows definition |
| Very small viewport | Tooltip repositions to fit; may show above term |

## Related

- Concepts: [Glossary / Terminology]
- Components: `GlossaryTooltip`
- Phase 278 tasks: `278.D.3` (Inline term definitions)
- E2E: `helptip-glossary.spec.ts` (278.V.22)
