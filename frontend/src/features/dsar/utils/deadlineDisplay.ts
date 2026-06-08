/** Statutory-clock presentation — ISO UTC + countdown (Phase 232.2.15 / 232.2.17). */

export function utcIsoLooksValid(iso: string | undefined | null): boolean {
  if (!iso) return false;
  const t = Date.parse(iso);
  return !Number.isNaN(t);
}

function timeZoneRenderable(zone: string | undefined): boolean {
  const z = (zone ?? 'UTC').trim() || 'UTC';
  try {
    new Intl.DateTimeFormat(undefined, { timeZone: z }).format(new Date());
    return true;
  } catch {
    return false;
  }
}

export function formatUtcInTimeZone(isoUtc: string | undefined | null, tz: string | undefined): string {
  if (!isoUtc || !utcIsoLooksValid(isoUtc)) return '—';
  const resolved = timeZoneRenderable(tz) ? (tz ?? 'UTC').trim() || 'UTC' : 'UTC';
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone: resolved,
    }).format(new Date(isoUtc));
  } catch {
    return isoUtc;
  }
}

export function countdownToUtcDeadline(
  isoUtc: string | undefined | null,
  nowMs: number,
  overdueLabel: string,
): string {
  if (!isoUtc || !utcIsoLooksValid(isoUtc)) return '—';
  const end = Date.parse(isoUtc);
  const ms = end - nowMs;
  if (ms <= 0) return overdueLabel;
  const days = Math.floor(ms / 86400000);
  const hours = Math.floor((ms % 86400000) / 3600000);
  const mins = Math.floor((ms % 3600000) / 60000);
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
}
