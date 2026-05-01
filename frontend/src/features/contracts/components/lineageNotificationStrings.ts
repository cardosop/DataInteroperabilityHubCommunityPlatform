/**
 * Phase 228.F3.23 — i18n strings for the lineage-notification surface.
 *
 * Mirrors the F2 ``lineageEditorStrings`` pattern: a single map of
 * canonical keys to default English strings.  Components import
 * ``t('lineage.notifications.<key>')`` instead of inlining the
 * literal so a future i18n loader can swap the table per locale
 * without touching the components.
 *
 * Why an inline map vs the standard i18n library?  The repo doesn't
 * yet ship a structured ``locales/<lang>/<file>.json`` pipeline
 * (see Phase 228.F2 i18n decision); these strings will fold into it
 * the day that pipeline lands.  Until then this file IS the
 * translation table — concentrated in one place so the future
 * migration is mechanical.
 */
const STRINGS: Record<string, string> = {
  // SubscriptionPanel (per-resource Subscribe button).
  'lineage.notifications.subscribe.cta': 'Subscribe to lineage changes',
  'lineage.notifications.subscribing.cta': 'Subscribing…',
  'lineage.notifications.unsubscribe.cta': 'Unsubscribe',
  'lineage.notifications.unsubscribing.cta': 'Unsubscribing…',
  'lineage.notifications.subscribed.status': 'Subscribed to lineage changes.',
  'lineage.notifications.severity.label': 'Severity threshold',

  // SubscriptionsPage (settings/subscriptions).
  'lineage.notifications.page.title': 'Lineage subscriptions',
  'lineage.notifications.page.description': (
    "You receive a notification whenever a contract you subscribe to has a "
    + 'lineage change at or above the configured severity threshold.'
  ),
  'lineage.notifications.page.empty': (
    'No subscriptions yet — open a contract or asset to subscribe.'
  ),

  // Severity tier labels.
  'lineage.notifications.severity.low': 'Low',
  'lineage.notifications.severity.medium': 'Medium',
  'lineage.notifications.severity.high': 'High',
  'lineage.notifications.severity.critical': 'Critical',

  // Notification body fallbacks (server is canonical, but the UI
  // benefits from a hard-coded fallback when a body string is empty).
  'lineage.notifications.fallback.title': 'Lineage changed',
  'lineage.notifications.fallback.body': (
    'A contract you subscribe to has changed.  Open it to see what changed.'
  ),
};

export function t(key: string): string {
  return STRINGS[key] ?? key;
}

export const lineageNotificationStrings = STRINGS;
