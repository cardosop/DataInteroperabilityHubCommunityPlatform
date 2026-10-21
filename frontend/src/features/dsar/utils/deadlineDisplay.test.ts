import { describe, expect, it } from 'vitest';

import { countdownToUtcDeadline, formatUtcInTimeZone, utcIsoLooksValid } from './deadlineDisplay';

describe('deadlineDisplay', () => {
  it('validates ISO UTC strings', () => {
    expect(utcIsoLooksValid('2026-05-05T12:00:00Z')).toBe(true);
    expect(utcIsoLooksValid('not-a-date')).toBe(false);
  });

  it('formats in UTC when asked', () => {
    const s = formatUtcInTimeZone('2026-01-15T12:00:00Z', 'UTC');
    expect(s).not.toBe('—');
  });

  it('uses overdue label after deadline', () => {
    const now = new Date('2026-06-01T00:00:00Z').getTime();
    expect(countdownToUtcDeadline('2026-05-01T00:00:00Z', now, 'LATE')).toBe('LATE');
  });
});
