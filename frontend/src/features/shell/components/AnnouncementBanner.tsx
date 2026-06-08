/**
 * 281.A.14.1 — In-app announcement banner.
 *
 * Dismissible, targetable, schedulable banner for maintenance notices,
 * feature announcements, and security advisories.  Dismissal is
 * persisted to localStorage per (bannerId, userId) so the same user
 * never sees the same banner twice.
 */
import { useCallback, useEffect, useState } from 'react';
import { Banner } from '../../../shared/components/Banner';
import './AnnouncementBanner.css';

export interface Announcement {
  /** Unique identifier for dedup / dismissal tracking. */
  id: string;
  /** Severity drives the banner colour variant. */
  variant: 'info' | 'warning' | 'error' | 'success';
  /** Rich content (links allowed). */
  message: string;
  /** ISO-8601 — banner is hidden before this time. */
  startsAt?: string;
  /** ISO-8601 — banner is hidden after this time. */
  expiresAt?: string;
  /** Comma-separated tenant IDs; empty = all tenants. */
  targetTenants?: string;
  /** Comma-separated persona slugs; empty = all personas. */
  targetPersonas?: string;
}

interface AnnouncementBannerProps {
  announcement: Announcement;
  userId?: string;
  tenantId?: string;
  personaSlug?: string;
}

const DISMISSED_KEY = 'meshant.announcement.dismissed';

function getDismissed(): Record<string, number> {
  try {
    return JSON.parse(localStorage.getItem(DISMISSED_KEY) ?? '{}');
  } catch {
    return {};
  }
}

function isDismissed(bannerId: string, userId?: string): boolean {
  const key = userId ? `${bannerId}:${userId}` : bannerId;
  const dismissed = getDismissed();
  return key in dismissed;
}

function persistDismissal(bannerId: string, userId?: string): void {
  const key = userId ? `${bannerId}:${userId}` : bannerId;
  const dismissed = getDismissed();
  dismissed[key] = Date.now();
  localStorage.setItem(DISMISSED_KEY, JSON.stringify(dismissed));
}

export function AnnouncementBanner({
  announcement,
  userId,
  tenantId,
  personaSlug,
}: AnnouncementBannerProps) {
  const [visible, setVisible] = useState(true);

  // ── Visibility gates ──────────────────────────────────────────────
  useEffect(() => {
    const now = new Date().toISOString();

    // Schedule window
    if (announcement.startsAt && now < announcement.startsAt) {
      setVisible(false);
      return;
    }
    if (announcement.expiresAt && now > announcement.expiresAt) {
      setVisible(false);
      return;
    }

    // Tenant targeting
    if (announcement.targetTenants && tenantId) {
      const allowed = announcement.targetTenants.split(',').map((t) => t.trim());
      if (!allowed.includes(tenantId)) {
        setVisible(false);
        return;
      }
    }

    // Persona targeting
    if (announcement.targetPersonas && personaSlug) {
      const allowed = announcement.targetPersonas.split(',').map((p) => p.trim());
      if (!allowed.includes(personaSlug)) {
        setVisible(false);
        return;
      }
    }

    // Dismissal
    if (isDismissed(announcement.id, userId)) {
      setVisible(false);
      return;
    }

    setVisible(true);
  }, [announcement, userId, tenantId, personaSlug]);

  const handleDismiss = useCallback(() => {
    persistDismissal(announcement.id, userId);
    setVisible(false);
  }, [announcement.id, userId]);

  if (!visible) return null;

  return (
    <div className="announcement-banner" data-testid="announcement-banner">
      <Banner
        variant={announcement.variant}
        onDismiss={handleDismiss}
      >
        <span
          dangerouslySetInnerHTML={{ __html: announcement.message }}
          data-testid="announcement-message"
        />
      </Banner>
    </div>
  );
}
