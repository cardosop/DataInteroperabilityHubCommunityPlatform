# UC-UX-005: Recover from Errors with Action Links

**Persona:** All authenticated users
**Phase:** 278 (UX Activation)
**Phase 278 Task:** `278.D.2` (FormErrors), `278.D.4` (RetryBanner), `278.F.2` (useJobCompletionToast)

## Description

A user encounters an error in the Meshant UI — a form validation failure,
a transient server error (503), or a long-running job failure. The error
UX provides actionable remediation: FormErrors groups field-level errors
with clickable field names that focus the input; ErrorDisplay wraps
transient errors in a RetryBanner with countdown auto-retry; and job
completion toasts surface success/failure with action links to view the
result or retry.

## Preconditions

- The user is authenticated.
- The error UX components (FormErrors, ErrorDisplay/RetryBanner,
  useJobCompletionToast) are integrated into the relevant pages.

## Steps

### FormErrors

1. User submits a form (e.g., Asset Create) with validation errors.
2. Backend returns a `422` with field-level error details.
3. `FormErrors` renders at the top of the form with `role="alert"`:
   - Heading: "Please fix N errors:"
   - Per-field: clickable field name (`.form-errors__field-link`) +
     error message
4. User clicks a field name. The page scrolls to and focuses the
   corresponding input (`#prefix-fieldName`).
5. User fixes the error and re-submits. FormErrors clears on successful
   submission.

### RetryBanner (via ErrorDisplay)

6. User visits a page that makes an API call. The call fails with a
   transient error (503, 502, 504, or SERVICE_UNAVAILABLE).
7. `ErrorDisplay` detects the transient error and renders `RetryBanner`:
   - Message: "We couldn't reach the server. Retrying in Ns…"
   - Countdown ticks each second.
   - "Retry now" button for manual retry.
8. When countdown reaches 0, `onRetry` fires automatically.
9. After `maxRetries` (default 5), banner switches to exhausted state:
   "Still unable to reach the server after N attempts."

### Job Completion Toast

10. User triggers a long-running job (e.g., DQ run, compliance scan).
11. The job transitions from PENDING → RUNNING → terminal (SUCCESS /
    FAILED).
12. `useJobCompletionToast` fires a toast on the status transition:
    - Success: "{label} completed — {id}"
    - Failure: "{label} failed — {id}"

## Expected Outcome

- FormErrors renders with `role="alert"` and clickable field links.
- RetryBanner auto-retries with countdown; RetryBanner has
  `role="alert"` and `aria-live="polite"`.
- Job completion toasts appear on status transitions (not on initial
  load).
- Error display never leaks sensitive data (passwords, tokens
  sanitized).

## Error Handling

| Component | Condition | Expected Response |
|---|---|---|
| FormErrors | No errors to display | Returns null |
| RetryBanner | Countdown reaches 0 | Auto-fires retry |
| RetryBanner | maxRetries exhausted | Shows exhausted state |
| ErrorDisplay | Non-transient error | Shows static display with manual Retry button |

## Related

- Components: `FormErrors`, `ErrorDisplay`, `RetryBanner`, `useJobCompletionToast`, `useOptimisticMutation`
- Concepts: [Error Handling / Error Codes](../../api/error-codes.md)
- Phase 278 tasks: `278.D.2` (FormErrors), `278.D.4` (RetryBanner), `278.F.2` (Job completion toast), `278.N.1-4` (Error UX remediation)
- E2E: `error-ux-remediation.spec.ts` (278.V.14), `optimistic-mutations.spec.ts` (278.V.21)
