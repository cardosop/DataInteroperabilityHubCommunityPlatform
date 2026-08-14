/**
 * 280.C.1.1 — French (fr) translation seed.
 *
 * Machine-generated seed with comprehensive term-mapping across all 179 keys.
 * Target: >90% translation coverage across all frontend keys.
 * Strings marked // REVIEW: require native-speaker validation.
 */
export const ALL_I18N_FR: Record<string, string> = {
  // ═══ LINEAGE TIMETRAVEL (13 keys) ═══
  'lineage.timetravel.controls_aria_label': 'Contrôles de voyage dans le temps du lignage',
  'lineage.timetravel.as_of_label': 'À la date du',
  'lineage.timetravel.as_of_help': 'Afficher le lignage à ce moment précis.',
  'lineage.timetravel.version_label': 'Version',
  'lineage.timetravel.version_placeholder': '— choisir une version —',
  'lineage.timetravel.apply': 'Appliquer',
  'lineage.timetravel.apply_aria': 'Appliquer l\'ancre de voyage dans le temps',
  'lineage.timetravel.reset': 'Réinitialiser',
  'lineage.timetravel.reset_aria': 'Réinitialiser à la vue en direct',
  'lineage.diff.added': 'Ajouté',
  'lineage.diff.removed': 'Supprimé',
  'lineage.diff.unchanged': 'Inchangé',
  'lineage.diff.modified': 'Modifié',

  // ═══ LINEAGE DIFF (9 keys) ═══
  'lineage.diff.heading': 'Différences de lignage',
  'lineage.diff.summary': 'Résumé :',
  'lineage.diff.from': 'de',
  'lineage.diff.to': 'à',
  'lineage.diff.loading': 'Chargement des différences de lignage…',
  'lineage.diff.error': 'Échec du chargement des différences :',
  'lineage.diff.no_anchor': 'Sélectionnez deux points d\'ancrage pour calculer les différences.',
  'lineage.diff.empty_bucket': '— aucune arête dans ce groupe —',

  // ═══ ASSETS SCHEMA DRIFT (19 keys) ═══
  'assets.schema_drift.heading.warn': 'Dérive de schéma détectée',
  'assets.schema_drift.heading.fail': 'Le schéma ne correspond pas au contrat',
  'assets.schema_drift.body.warn':
    'Le jeu de données contient des colonnes que le contrat ne déclare pas, ou des types plus larges que requis. L\'actif a tout de même été créé — examinez les différences ci-dessous et mettez à jour le contrat si nécessaire.',
  'assets.schema_drift.body.fail':
    'Le jeu de données manque de champs requis par le contrat, ou présente des types incompatibles. L\'actif a été créé pour vous permettre de corriger les données, mais les consommateurs qui dépendent du contrat verront des erreurs jusqu\'à ce que le schéma corresponde.',
  'assets.schema_drift.section.missing': 'Champs manquants',
  'assets.schema_drift.section.missing_help':
    'Déclarés par le contrat, absents du jeu de données.',
  'assets.schema_drift.section.extra': 'Champs supplémentaires',
  'assets.schema_drift.section.extra_help':
    'Présents dans le jeu de données, non déclarés par le contrat.',
  'assets.schema_drift.section.mismatches': 'Incompatibilités de type',
  'assets.schema_drift.section.mismatches_help':
    'Même nom de champ, type différent. Marqué compatible si le type du jeu de données est un élargissement sûr du type du contrat.',
  'assets.schema_drift.mismatch_col.field': 'Champ',
  'assets.schema_drift.mismatch_col.contract_type': 'Type du contrat',
  'assets.schema_drift.mismatch_col.dataset_type': 'Type du jeu de données',
  'assets.schema_drift.mismatch_col.compatible': 'Compatible ?',
  'assets.schema_drift.mismatch.compatible_yes': 'Oui — élargissement sûr',
  'assets.schema_drift.mismatch.compatible_no': 'Non',
  'assets.schema_drift.empty_section': '— aucun —',
  'assets.schema_drift.collapsed_count':
    '{count} élément(s) — développer pour voir les détails',
  'assets.schema_drift.banner_aria_label': 'Rapport de dérive de schéma pour le nouvel actif',

  // ═══ ASSETS TYPE PICKER (18 keys) ═══
  'assets.type_picker.heading': 'Qu\'apportez-vous au catalogue ?',
  'assets.type_picker.body':
    'Choisissez l\'option qui correspond à ce que vous avez. Nous préconfigurons l\'étape suivante selon votre choix — vous pourrez toujours changer après.',
  'assets.type_picker.aria_label': 'Choisissez le type d\'actif que vous créez',
  'assets.type_picker.skip_label': 'Passer et configurer manuellement',
  'assets.type_picker.option.data.title': 'Un fichier de données',
  'assets.type_picker.option.data.body':
    'Téléversez un fichier CSV / JSON / Parquet. Nous inférons le schéma et exécutons des contrôles de qualité et de conformité avant publication.',
  'assets.type_picker.option.data.aria_label': 'Créer un actif à partir d\'un fichier de données',
  'assets.type_picker.option.contract.title': 'Un document de contrat',
  'assets.type_picker.option.contract.body':
    'Téléversez un YAML / JSON ODCS ou DataContract.com. Cataloguez la spécification sans téléverser de données.',
  'assets.type_picker.option.contract.aria_label': 'Créer un actif à partir d\'un document de contrat',
  'assets.type_picker.option.both.title': 'Les deux — fichier + contrat',
  'assets.type_picker.option.both.body':
    'Téléversez un fichier de données ET son contrat. Nous validons que les données sont conformes au contrat avant publication.',
  'assets.type_picker.option.both.aria_label':
    'Créer un actif à partir d\'un fichier de données et d\'un contrat',
  'assets.type_picker.option.metadata.title': 'Métadonnées uniquement',
  'assets.type_picker.option.metadata.body':
    'Référencez une source de données externe. Cataloguez l\'actif sans rien téléverser sur le hub.',
  'assets.type_picker.option.metadata.aria_label':
    'Créer un actif avec métadonnées uniquement — sans téléversement ni contrat',
  'assets.type_picker.onboarding_incomplete.heading':
    'Terminez l\'intégration pour commencer à créer des actifs',
  'assets.type_picker.onboarding_incomplete.body':
    'La création d\'actifs est débloquée lorsque votre administrateur de tenant est invité, le KYC est soumis et la facturation configurée. Terminez les étapes restantes pour continuer.',
  'assets.type_picker.onboarding_incomplete.cta': 'Terminer l\'intégration',

  // ═══ MARKETPLACE KYC (5 keys) ═══
  'marketplace.publish.kyc_blocked.heading': 'Vérification KYC requise pour publier',
  'marketplace.publish.kyc_blocked.body':
    'Votre tenant doit terminer la vérification KYC avant qu\'une annonce puisse être publiée dans le catalogue marketplace. Le brouillon a été enregistré — une fois la vérification terminée, vous pourrez publier sans ressaisir les détails.',
  'marketplace.publish.kyc_blocked.cta_label': 'Vérifier KYC maintenant',
  'marketplace.publish.kyc_blocked.status_label': 'Statut KYC actuel :',
  'marketplace.publish.kyc_blocked.aria_label': 'Vérification KYC requise pour publier l\'annonce',

  // ═══ MARKETPLACE KYB (4 keys) ═══
  'marketplace.publish.kyb_blocked.heading':
    'Intégration Stripe Connect requise pour publier des annonces payantes',
  'marketplace.publish.kyb_blocked.body':
    'Pour recevoir des paiements pour cette annonce, vous devez terminer l\'intégration Stripe Connect. Les annonces gratuites ne sont pas affectées — cette annonce sera publiée comme brouillon jusqu\'à ce que l\'intégration soit terminée.',
  'marketplace.publish.kyb_blocked.cta_label': 'Terminer l\'intégration Stripe Connect',
  'marketplace.publish.kyb_blocked.aria_label':
    'Intégration Stripe Connect requise pour publier une annonce payante',

  // ═══ PUBLIC LEGAL (13 keys) ═══
  'public.legal.home.title': 'Légal et transparence',
  'public.legal.home.intro':
    'Ces pages résument comment la plateforme Meshant traite les données personnelles. Elles ne remplacent pas l\'Accord de Traitement des Données contractuel de votre organisation.',
  'public.legal.home.privacy_link': 'Avis de confidentialité',
  'public.legal.home.subprocessors_link': 'Sous-traitants',
  'public.legal.home.dpia_link': 'Résumé des transferts / AIPD',
  'public.legal.home.dsar_link': 'Exercer vos droits de personne concernée (DSAR)',
  'public.legal.privacy.title': 'Avis de confidentialité de la plateforme',
  'public.legal.privacy.body':
    'Meshant traite la configuration du tenant, les identifiants d\'authentification, les contacts de facturation et la télémétrie opérationnelle nécessaire au fonctionnement du hub. La télémétrie agrégée exclut le contenu brut des personnes concernées ; évitez d\'inclure des données personnelles dans les URLs ou les corps de tickets. Les données personnelles que vous téléversez restent dans la limite de votre tenant avec isolation au niveau des lignes. Les flux à haut risque (fédération, sauvegardes, marketplaces) sont décrits dans le résumé des transferts/AIPD.',
  'public.legal.subprocessors.title': 'Aperçu des sous-traitants',
  'public.legal.subprocessors.body':
    'Les processeurs d\'infrastructure représentatifs incluent le stockage d\'objets (par exemple Amazon S3) pour les artefacts et exportations, et le courrier électronique transactionnel (par exemple Amazon SES) pour les OTP DSAR et les notifications légales. La vérification d\'identité peut être déléguée à un partenaire IDV lorsque cette fonctionnalité sera activée ; le nom du fournisseur apparaîtra ici et dans votre annexe DPA. Les processeurs spécifiques aux connecteurs par tenant sont listés dans votre RoPA.',
  'public.legal.dpia.title': 'Impact des transferts et résumé AIPD',
  'public.legal.dpia.body':
    'Les flux de travail à haut risque (facturation, SSO, fédération, sauvegardes) font l\'objet de revues de confidentialité régulières. Des AIPD récursives sont maintenues par sous-système ; les artefacts sont divulgués aux contacts juridiques autorisés du client sous NDA.',

  // ═══ PUBLIC LEGAL DSAR (23 keys) ═══
  'public.legal.dsar.title': 'Demande de droits de la personne concernée',
  'public.legal.dsar.heading': 'Soumettre une demande de droits',
  'public.legal.dsar.intro':
    'Indiquez-nous comment vous contacter et quels régimes s\'appliquent. Après soumission, vérifiez avec le code que nous vous envoyons par e-mail.',
  'public.legal.dsar.captcha_notice':
    'Ce formulaire est protégé par hCaptcha — collez le jeton de vérification produit par votre intégration hCaptcha.',
  'public.legal.dsar.field_tenant_id': 'Identifiant d\'organisation (UUID)',
  'public.legal.dsar.field_email': 'Votre adresse e-mail',
  'public.legal.dsar.field_type': 'Type de demande',
  'public.legal.dsar.field_regimes': 'Régimes applicables',
  'public.legal.dsar.regimes_help': 'Séparés par des virgules ; par défaut RGPD si laissé vide.',
  'public.legal.dsar.field_hcaptcha': 'Jeton de vérification hCaptcha',
  'public.legal.dsar.submit': 'Soumettre la demande',
  'public.legal.dsar.submitting': 'Soumission en cours…',
  'public.legal.dsar.created_blurb':
    'Demande enregistrée. Suivez le lien du mot de passe à usage unique envoyé par e-mail pour activer le traitement lorsque requis.',
  'public.legal.dsar.reference': 'Lien de statut',
  'public.legal.dsar.status_label': 'Statut actuel',
  'public.legal.dsar.otp_label': 'Code de vérification par e-mail',
  'public.legal.dsar.verify': 'Vérifier le code',
  'public.legal.dsar.status.title': 'Statut de la demande',
  'public.legal.dsar.status.labels.status': 'Statut',
  'public.legal.dsar.status.labels.type': 'Type de demande',
  'public.legal.dsar.status.labels.ack_deadline': 'Délai légal d\'accusé de réception (UTC)',
  'public.legal.dsar.status.labels.fulfil_deadline': 'Délai légal d\'exécution (UTC)',
  'public.legal.dsar.status.labels.subject_local': 'Délai d\'exécution (fuseau horaire du demandeur)',
  'public.legal.dsar.status.labels.regulator_local': 'Délai d\'exécution (fuseau horaire du régulateur)',
  'public.legal.dsar.status.labels.countdown': 'Compte à rebours (délai UTC d\'exécution)',
  'public.legal.dsar.field_subject_tz': 'Votre fuseau horaire (IANA)',
  'public.legal.dsar.field_regulator_tz': 'Fuseau horaire du régulateur (IANA)',
  'public.legal.dsar.tz_help': 'Exemples : UTC, America/New_York, Europe/Paris. Utilisé uniquement pour la présentation légale des délais.',

  // ═══ GOVERNANCE DSAR (27 keys) ═══
  'governance.dsar.queue_title': 'Demandes des personnes concernées (DSAR)',
  'governance.dsar.col_type': 'Type',
  'governance.dsar.col_subject': 'E-mail du demandeur',
  'governance.dsar.col_status': 'Statut',
  'governance.dsar.col_sla_scan': 'Niveau d\'analyse SLA',
  'governance.dsar.col_deadline': 'Délai d\'exécution (UTC)',
  'governance.dsar.col_fulfil_detail': 'Horloge d\'exécution',
  'governance.dsar.col_action': 'Action',
  'governance.dsar.countdown_prefix': 'Temps restant jusqu\'au délai légal d\'exécution',
  'governance.dsar.countdown_overdue': 'Délai légal d\'exécution dépassé',
  'governance.dsar.subject_tz_label': 'Heure locale du demandeur',
  'governance.dsar.regulator_tz_label': 'Heure locale du régulateur',
  'governance.dsar.open': 'Ouvrir',
  'governance.dsar.empty': 'Aucune demande dans ce tenant pour l\'instant.',
  'governance.dsar.detail_title': 'Détail DSAR',
  'governance.dsar.loading': 'Chargement…',
  'governance.dsar.btn_materialize': 'Construire le dossier de réponse',
  'governance.dsar.btn_reject': 'Rejeter',
  'governance.dsar.btn_legal_hold': 'Conservation légale',
  'governance.dsar.btn_download': 'Émettre l\'URL de téléchargement (24h)',
  'governance.dsar.download_ready': 'URL de téléchargement pré-signée (copiez rapidement ; peut expirer) :',
  'governance.dsar.prompt_reject': 'Motif de rejet (visible dans la piste d\'audit)',
  'governance.dsar.prompt_hold_reason': 'Motif de conservation légale (facultatif)',

  // ═══ MARKETPLACE RECOMMENDATIONS + TRUST + COMPARISON + PREVIEW + SAVED SEARCH (39 keys) ═══
  'marketplace.recommendations.title': 'Recommandé pour vous',
  'marketplace.recommendations.empty': 'Pas encore de recommandations.',
  'marketplace.recommendations.based_on': 'Basé sur votre activité',
  'marketplace.trustSignal.compliance_verified': 'Conformité vérifiée',
  'marketplace.trustSignal.kyb_verified': 'KYB vérifié',
  'marketplace.trustSignal.active_since': 'Actif depuis',
  'marketplace.trustSignal.orders_fulfilled': 'Commandes exécutées',
  'marketplace.comparison.title': 'Comparer les annonces',
  'marketplace.comparison.add_listing': 'Ajouter à la comparaison',
  'marketplace.comparison.remove': 'Retirer',
  'marketplace.comparison.empty': 'Ajoutez des annonces à comparer.',
  'marketplace.comparison.field.price': 'Prix',
  'marketplace.comparison.field.pricing_model': 'Modèle de tarification',
  'marketplace.comparison.field.compliance': 'Conformité',
  'marketplace.comparison.field.data_quality': 'Qualité des données',
  'marketplace.comparison.field.updated': 'Dernière mise à jour',
  'marketplace.quickPreview.title': 'Aperçu rapide',
  'marketplace.quickPreview.schema': 'Schéma',
  'marketplace.quickPreview.pricing': 'Tarification',
  'marketplace.quickPreview.compliance': 'Conformité',
  'marketplace.quickPreview.ratings': 'Évaluations',
  'marketplace.quickPreview.view_details': 'Voir les détails',
  'marketplace.quickPreview.close': 'Fermer l\'aperçu',
  'marketplace.savedSearch.save': 'Enregistrer la recherche',
  'marketplace.savedSearch.saved': 'Recherche enregistrée',
  'marketplace.savedSearch.name_label': 'Nom de la recherche',
  'marketplace.savedSearch.name_placeholder': 'ex. Jeux de données de santé',
  'marketplace.savedSearch.notify_label': 'Me notifier des nouveaux résultats',
  'marketplace.savedSearch.frequency_instant': 'Instantanément',
  'marketplace.savedSearch.frequency_daily': 'Résumé quotidien',
  'marketplace.savedSearch.frequency_weekly': 'Résumé hebdomadaire',
  'marketplace.savedSearch.delete': 'Supprimer la recherche enregistrée',
  'marketplace.savedSearch.empty': 'Aucune recherche enregistrée.',

  // ═══ GOVERNANCE APPROVAL INBOX (19 keys) ═══
  'governance.approvalInbox.title': 'En attente de mon approbation',
  'governance.approvalInbox.empty': 'Aucun élément en attente de votre approbation.',
  'governance.approvalInbox.view_all': 'Voir tous les éléments de gouvernance →',
  'governance.approvalInbox.select_all': 'Tout sélectionner',
  'governance.approvalInbox.reject_reason': 'Motif de rejet (facultatif)',
  'governance.approvalInbox.approve': 'Approuver',
  'governance.approvalInbox.reject': 'Rejeter',
  'governance.approvalInbox.type.access_request': 'Accès',
  'governance.approvalInbox.type.dsar': 'DSAR',
  'governance.approvalInbox.type.breach': 'Violation',
  'governance.approvalInbox.type.dpia': 'AIPD',
  'governance.approvalInbox.type.kyb': 'KYB',
  'governance.approvalInbox.priority.high': 'élevée',
  'governance.approvalInbox.priority.medium': 'moyenne',
  'governance.approvalInbox.priority.low': 'basse',
};
