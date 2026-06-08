# JOURNEY-DE-016: Error Recovery Flow

**Persona:** [Data Engineer](../personas/data-engineer/)
**Use Cases:** UC-UX-ERR-001, UC-UX-ERR-002
**Phase:** 278 (UX Activation)
**Status:** Implemented (278.F.2, 278.J.12, 278.F.4, 278.V.15, 278.V.20)
**E2E:** `frontend/e2e/journeys/features/job-completion-toast.spec.ts`, `frontend/e2e/journeys/features/progress-bar-async-ops.spec.ts`

## Overview

A Data Engineer encounters errors during long-running async operations (DQ
runs, compliance scans, file uploads, scheduled ingestions). The Phase 278
error-recovery UX provides layered feedback: progress bars with determinate
and indeterminate states, job-completion toast notifications with action
links, auto-retry banners for transient failures, and form-field navigation
for validation errors. Each layer is designed to reduce mean-time-to-recovery
(MTTR) without requiring the user to leave their current context.

## Journey Steps

1. **Operation starts** — The DE initiates an async operation (e.g., a DQ run
   on a large dataset). A `ProgressBar` appears in the operation's detail
   page with `role="progressbar"` and `aria-valuenow/min/max` attributes. If
   the backend reports a known percentage, the bar is **determinate**
   (filled proportionally, shows "N%"). If the total work is unknown, the
   bar is **indeterminate** (animated shimmer, no percentage text).

2. **Operation completes** — When the job status transitions from
   `PENDING`/`RUNNING` to `COMPLETED`/`SUCCEEDED`, a **success toast**
   fires: `"{resourceLabel} completed — {id[0:8]}…"`. The toast renders
   with `role="status"` and `aria-live="polite"`, auto-dismisses after 4
   seconds, and can be manually dismissed via the × button. Duplicate
   identical toasts within 500 ms are suppressed.

3. **Operation fails** — When the job status transitions to `FAILED`/`ERROR`,
   an **error toast** fires with `toast-error` class and the failure
   message. The DE can click the toast to navigate to the job detail page
   for full diagnostics.

4. **Retry on transient failure** — For transient errors (network timeouts,
   backend 503, temporary resource exhaustion), a `RetryBanner` appears
   with `role="alert"` and `aria-live="polite"`. It shows an auto-retry
   countdown and a manual "Retry Now" button. The auto-retry uses
   exponential backoff.

5. **Form validation errors** — When the DE submits a form with invalid
   fields (e.g., asset create with missing required fields), a
   `FormErrors` component renders with `role="alert"`. Each field error is
   a clickable link that focuses the offending input. The heading reads
   "Please fix N error(s) before submitting."

6. **Progress bar terminal states** — After operation completion or failure:
   - **Complete**: green bar (`progress-bar__track--complete`), fill at
     100%, text "Done", `aria-valuenow="100"`.
   - **Error**: red bar (`progress-bar__track--error`), error message text
     with `progress-bar__text--error` class, `aria-valuenow="0"`.

## Success Criteria

- Progress bar shows determinate state with percentage for known-duration
  operations and indeterminate shimmer for unknown-duration operations.
- Job completion toast fires on status transition (not on initial mount or
  same-status re-render).
- Error toast renders with `toast-error` class and descriptive message.
- Retry banner auto-retries transient failures with exponential backoff.
- FormErrors field links focus the correct input on click.
- Complete state shows green bar + "Done"; error state shows red bar +
  error message.
- All surfaces meet WCAG 2.1 AA: `role="progressbar"`, `role="status"`,
  `role="alert"`, `aria-live="polite"` as appropriate.

## Related

- Phase 278 tasks: 278.F.2 (job completion toast), 278.F.4 (progress bar),
  278.J.12 (FormErrors field navigation), 278.V.15 (progress bar E2E),
  278.V.20 (job toast E2E)
- E2E tests: `progress-bar-async-ops.spec.ts`,
  `job-completion-toast.spec.ts`, `error-ux-remediation.spec.ts`
- Concepts: [Jobs](../concepts/jobs.md), [DQ Runs](../concepts/dq-runs.md),
  [Error Handling](../concepts/error-handling.md)
- Journeys: [JOURNEY-DPO-001](JOURNEY-DPO-001.md) (Asset Creation),
  [JOURNEY-CPO-001](JOURNEY-CPO-001.md) (Compliance Scan)
