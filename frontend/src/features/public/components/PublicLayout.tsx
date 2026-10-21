/**
 * Lightweight shell for unauthenticated legal/transparency routes (Phase 232.0).
 */

import { Link, Outlet } from 'react-router-dom';
import { useTranslation } from '../../../shared/i18n/useTranslation';

export function PublicLayout() {
  const { t } = useTranslation();
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-10">
      <header>
        <h1 className="text-2xl font-semibold">{t('public.legal.home.title')}</h1>
        <nav className="mt-4 flex flex-wrap gap-4 text-sm">
          <Link className="text-blue-700 underline hover:no-underline" to="/legal">
            {t('public.legal.home.title')}
          </Link>
          <Link className="text-blue-700 underline hover:no-underline" to="/legal/privacy">
            {t('public.legal.home.privacy_link')}
          </Link>
          <Link className="text-blue-700 underline hover:no-underline" to="/legal/subprocessors">
            {t('public.legal.home.subprocessors_link')}
          </Link>
          <Link className="text-blue-700 underline hover:no-underline" to="/legal/dpia">
            {t('public.legal.home.dpia_link')}
          </Link>
        </nav>
      </header>
      <Outlet />
    </div>
  );
}
