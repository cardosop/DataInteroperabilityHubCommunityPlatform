/**
 * Phase 228 X (228.X.1 / REQ-LIN-X-001) — locale-aware formatters.
 *
 * Wrappers around the browser-native `Intl.*` constructors so the
 * lineage UI surfaces (and any future feature) format dates +
 * numbers consistently in the user's locale without sprinkling
 * `new Intl.DateTimeFormat(...)` across every component.
 *
 * All wrappers accept an optional `locale` arg; when omitted they
 * read `navigator.language` at call time. Locales NOT supported
 * by `Intl` fall through to the browser default (no exception).
 */

const FALLBACK_LOCALE = 'en-US';

function resolveLocale(locale?: string): string {
  if (locale) return locale;
  if (typeof navigator !== 'undefined' && navigator.language) {
    return navigator.language;
  }
  return FALLBACK_LOCALE;
}

/**
 * Locale-aware date-time formatting.
 * Default style mirrors the time-travel datetime picker (medium
 * date + short time) so the URL bar and the picker render the
 * same string for the same instant.
 */
export function formatDateTime(
  iso: string | Date,
  options: Intl.DateTimeFormatOptions = {
    dateStyle: 'medium',
    timeStyle: 'short',
  },
  locale?: string,
): string {
  const date = iso instanceof Date ? iso : new Date(iso);
  if (Number.isNaN(date.getTime())) return String(iso);
  try {
    return new Intl.DateTimeFormat(resolveLocale(locale), options).format(date);
  } catch {
    return new Intl.DateTimeFormat(FALLBACK_LOCALE, options).format(date);
  }
}

/** Locale-aware short-relative formatting ("2 hours ago", "in 3 days"). */
export function formatRelative(
  iso: string | Date,
  locale?: string,
): string {
  const date = iso instanceof Date ? iso : new Date(iso);
  if (Number.isNaN(date.getTime())) return String(iso);
  const diffMs = date.getTime() - Date.now();
  const absSec = Math.round(Math.abs(diffMs) / 1000);
  const sign = diffMs >= 0 ? 1 : -1;

  const units: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ['year', 60 * 60 * 24 * 365],
    ['month', 60 * 60 * 24 * 30],
    ['day', 60 * 60 * 24],
    ['hour', 60 * 60],
    ['minute', 60],
    ['second', 1],
  ];
  const [unit, secs] = units.find(([, s]) => absSec >= s) ?? ['second', 1];
  const value = sign * Math.round(absSec / secs);

  try {
    return new Intl.RelativeTimeFormat(resolveLocale(locale), {
      numeric: 'auto',
    }).format(value, unit);
  } catch {
    return new Intl.RelativeTimeFormat(FALLBACK_LOCALE, {
      numeric: 'auto',
    }).format(value, unit);
  }
}

/** Locale-aware integer / decimal formatting. */
export function formatNumber(
  value: number,
  options: Intl.NumberFormatOptions = {},
  locale?: string,
): string {
  if (!Number.isFinite(value)) return String(value);
  try {
    return new Intl.NumberFormat(resolveLocale(locale), options).format(value);
  } catch {
    return new Intl.NumberFormat(FALLBACK_LOCALE, options).format(value);
  }
}

/**
 * Locale-aware currency formatting.
 *
 * Returns a formatted currency string (e.g. "$1,234.56") using the
 * user's locale. When `currency` is omitted it defaults to "USD".
 */
export function formatCurrency(amount: number, currency: string = 'USD', locale?: string): string {
  if (!Number.isFinite(amount)) return String(amount);
  try {
    return new Intl.NumberFormat(resolveLocale(locale), {
      style: 'currency',
      currency,
    }).format(amount);
  } catch {
    return new Intl.NumberFormat(FALLBACK_LOCALE, {
      style: 'currency',
      currency,
    }).format(amount);
  }
}

/**
 * Locale-aware date formatting. Returns a localized date string
 * (long month + numeric day + numeric year by default, e.g.
 * "June 4, 2026" for en-US).
 */
export function formatDate(date: string | Date, locale?: string): string {
  const d = date instanceof Date ? date : new Date(date);
  if (Number.isNaN(d.getTime())) return String(date);
  try {
    return new Intl.DateTimeFormat(resolveLocale(locale), {
      dateStyle: 'long',
    }).format(d);
  } catch {
    return new Intl.DateTimeFormat(FALLBACK_LOCALE, {
      dateStyle: 'long',
    }).format(d);
  }
}
