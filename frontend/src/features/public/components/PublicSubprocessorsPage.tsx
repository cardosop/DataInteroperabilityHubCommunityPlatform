import { Helmet } from 'react-helmet-async';
import { APP_NAME } from '../../../shared/constants/brand';
import { useTranslation } from '../../../shared/i18n/useTranslation';

export function PublicSubprocessorsPage() {
  const { t } = useTranslation();
  return (
    <>
      <Helmet>
        <title>{APP_NAME} — Sub-processors</title>
      </Helmet>
      <article className="prose prose-slate">
        <h2>{t('public.legal.subprocessors.title')}</h2>
        <p>{t('public.legal.subprocessors.body')}</p>
      </article>
    </>
  );
}
