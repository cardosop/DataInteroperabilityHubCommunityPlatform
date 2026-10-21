import { Helmet } from 'react-helmet-async';
import { APP_NAME } from '../../../shared/constants/brand';
import { useTranslation } from '../../../shared/i18n/useTranslation';

export function PublicPlatformDpiaSummaryPage() {
  const { t } = useTranslation();
  return (
    <>
      <Helmet>
        <title>{APP_NAME} — Transfer & DPIA summary</title>
      </Helmet>
      <article className="prose prose-slate">
        <h2>{t('public.legal.dpia.title')}</h2>
        <p>{t('public.legal.dpia.body')}</p>
      </article>
    </>
  );
}
