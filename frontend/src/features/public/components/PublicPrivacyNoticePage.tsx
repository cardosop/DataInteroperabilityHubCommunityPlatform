import { Helmet } from 'react-helmet-async';
import { APP_NAME } from '../../../shared/constants/brand';
import { useTranslation } from '../../../shared/i18n/useTranslation';

export function PublicPrivacyNoticePage() {
  const { t } = useTranslation();
  return (
    <>
      <Helmet>
        <title>{APP_NAME} — Privacy notice</title>
      </Helmet>
      <article className="prose prose-slate">
        <h2>{t('public.legal.privacy.title')}</h2>
        <p>{t('public.legal.privacy.body')}</p>
      </article>
    </>
  );
}
