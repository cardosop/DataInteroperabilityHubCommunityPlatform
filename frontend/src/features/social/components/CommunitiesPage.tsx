/**
 * Communities Page
 * Standalone page for data communities (Phase 27.2).
 * Replaces the Social page's Communities tab as the primary communities entry point.
 */

import { CommunitiesTab } from './CommunitiesTab';
import './CommunitiesPage.css';

export function CommunitiesPage() {
  return (
    <div className="communities-page" data-testid="communities-page">
      <CommunitiesTab />
    </div>
  );
}
