/**
 * formatScheduleSummary tests — Phase 260.4.F.R1 GAP-A.
 *
 * Pure unit tests for the cadence summary formatter. Distinguishes
 * WEEKLY / MONTHLY schedules by their day field so the modal list
 * doesn't surface two different schedules with identical-looking
 * summaries.
 */
import { describe, expect, it } from 'vitest';

import { formatScheduleSummary } from './scheduleSummary';

describe('formatScheduleSummary', () => {
  it('formats DAILY with time as "DAILY (time: HH:MM)"', () => {
    expect(
      formatScheduleSummary({
        schedule_type: 'DAILY',
        schedule_config: { time: '02:00' },
      }),
    ).toBe('DAILY (time: 02:00)');
  });

  it('formats CUSTOM_CRON with cron expression', () => {
    expect(
      formatScheduleSummary({
        schedule_type: 'CUSTOM_CRON',
        schedule_config: { cron: '0 */2 * * *' },
      }),
    ).toBe('CUSTOM_CRON (cron: 0 */2 * * *)');
  });

  it('formats WEEKLY with day_of_week + time as "Weekly on Mon at HH:MM"', () => {
    // Without the day_of_week in the summary, a "WEEKLY on Mondays"
    // schedule and a "WEEKLY on Fridays" schedule look identical in
    // the modal list.
    expect(
      formatScheduleSummary({
        schedule_type: 'WEEKLY',
        schedule_config: { day_of_week: 1, time: '09:00' },
      }),
    ).toBe('Weekly on Mon at 09:00');
  });

  it('formats WEEKLY without time as "Weekly on <Day>"', () => {
    expect(
      formatScheduleSummary({
        schedule_type: 'WEEKLY',
        schedule_config: { day_of_week: 5 },
      }),
    ).toBe('Weekly on Fri');
  });

  it('formats MONTHLY with day_of_month + time', () => {
    expect(
      formatScheduleSummary({
        schedule_type: 'MONTHLY',
        schedule_config: { day_of_month: 15, time: '03:30' },
      }),
    ).toBe('Monthly on day 15 at 03:30');
  });

  it('falls back to schedule_type when schedule_config is null', () => {
    expect(
      formatScheduleSummary({
        schedule_type: 'DAILY',
        schedule_config: null,
      }),
    ).toBe('DAILY');
  });

  it('handles unknown day_of_week index defensively', () => {
    // Out-of-range day_of_week shouldn't crash — defensive default
    // prints "day N" rather than throwing.
    expect(
      formatScheduleSummary({
        schedule_type: 'WEEKLY',
        schedule_config: { day_of_week: 99, time: '10:00' },
      }),
    ).toBe('Weekly on day 99 at 10:00');
  });
});
