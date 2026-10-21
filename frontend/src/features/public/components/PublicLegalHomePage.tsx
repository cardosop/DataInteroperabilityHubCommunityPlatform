import { Helmet } from 'react-helmet-async';
import { Link } from 'react-router-dom';
import { APP_NAME } from '../../../shared/constants/brand';
import { useTranslation } from '../../../shared/i18n/useTranslation';

export function PublicLegalHomePage() {
  const { t } = useTranslation();
  return (
    <>
      <Helmet>
        <title>{APP_NAME} — Legal & transparency</title>
      </Helmet>
      <p className="text-gray-700">{t('public.legal.home.intro')}</p>
      <ul className="list-disc space-y-2 pl-6 text-blue-900">
        <li>
          <Link className="underline hover:no-underline" to="/legal/privacy">
            {t('public.legal.home.privacy_link')}
          </Link>
        </li>
        <li>
          <Link className="underline hover:no-underline" to="/legal/subprocessors">
            {t('public.legal.home.subprocessors_link')}
          </Link>
        </li>
        <li>
          <Link className="underline hover:no-underline" to="/legal/dpia">
            {t('public.legal.home.dpia_link')}
          </Link>
        </li>
        <li>
          <Link className="underline hover:no-underline" to="/legal/dsar">
            {t('public.legal.home.dsar_link')}
          </Link>
        </li>
      </ul>
    </>
  );
}
