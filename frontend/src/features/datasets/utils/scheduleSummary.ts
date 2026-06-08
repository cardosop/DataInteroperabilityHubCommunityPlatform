/**
 * Phase 260.4.F — schedule cadence summary formatter.
 *
 * Extracted from ``DatasetScheduleEditModal.tsx`` so the formatter
 * can be unit-tested without instantiating the modal AND so the
 * react-refresh rule (only-export-components from a `.tsx` file)
 * doesn't flag the helper. Pure function, no side effects.
 */

/** Day-of-week index (0=Sun … 6=Sat) → human-readable name. */
const DAY_OF_WEEK_NAMES: Readonly<Record<number, string>> = {
  0: 'Sun',
  1: 'Mon',
  2: 'Tue',
  3: 'Wed',
  4: 'Thu',
  5: 'Fri',
  6: 'Sat',
};

/**
 * R1 audit GAP-A — produce a human-readable cadence summary that
 * distinguishes WEEKLY/MONTHLY schedules by their day field. Without
 * the day in the summary, two WEEKLY schedules running on different
 * days look identical in the modal list — the user has to click
 * through to disambiguate.
 *
 * Wire shape (matches ``hub/apps/scheduled_ingestion/business_rules.py``
 * `validate_schedule_config`):
 *   - DAILY        → ``schedule_config.time`` (HH:MM)
 *   - WEEKLY       → ``schedule_config.time`` + ``day_of_week`` (0=Sun…6=Sat)
 *   - MONTHLY      → ``schedule_config.time`` + ``day_of_month`` (1-31)
 *   - CUSTOM_CRON  → ``schedule_config.cron`` (5-field expression)
 */
export function formatScheduleSummary(schedule: {
  schedule_type: string;
  schedule_config?: Record<string, unknown> | null;
}): string {
  const cfg = schedule.schedule_config ?? {};
  const cron = typeof cfg.cron === 'string' ? cfg.cron : null;
  const time = typeof cfg.time === 'string' ? cfg.time : null;
  const dayOfWeek = typeof cfg.day_of_week === 'number' ? cfg.day_of_week : null;
  const dayOfMonth = typeof cfg.day_of_month === 'number' ? cfg.day_of_month : null;

  if (cron) return `${schedule.schedule_type} (cron: ${cron})`;

  // WEEKLY: prefer "Weekly on Mon at 02:00" over "WEEKLY (time: 02:00)".
  if (schedule.schedule_type === 'WEEKLY' && dayOfWeek !== null) {
    const dayName = DAY_OF_WEEK_NAMES[dayOfWeek] ?? `day ${dayOfWeek}`;
    return time
      ? `Weekly on ${dayName} at ${time}`
      : `Weekly on ${dayName}`;
  }
  // MONTHLY: prefer "Monthly on day 15 at 02:00" over "MONTHLY (time: 02:00)".
  if (schedule.schedule_type === 'MONTHLY' && dayOfMonth !== null) {
    return time
      ? `Monthly on day ${dayOfMonth} at ${time}`
      : `Monthly on day ${dayOfMonth}`;
  }

  if (time) return `${schedule.schedule_type} (time: ${time})`;
  return schedule.schedule_type;
}
