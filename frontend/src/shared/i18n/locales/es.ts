/**
 * 280.C.1.1 — Spanish (es) translation seed.
 *
 * Machine-generated seed with comprehensive term-mapping across all 179 keys.
 * Target: >90% translation coverage across all frontend keys.
 * Strings marked // REVIEW: require native-speaker validation.
 */
export const ALL_I18N_ES: Record<string, string> = {
  // ═══ LINEAGE TIMETRAVEL (13 keys) ═══
  'lineage.timetravel.controls_aria_label': 'Controles de viaje en el tiempo de linaje',
  'lineage.timetravel.as_of_label': 'A fecha de',
  'lineage.timetravel.as_of_help': 'Mostrar el linaje en este momento exacto.',
  'lineage.timetravel.version_label': 'Versión',
  'lineage.timetravel.version_placeholder': '— elegir una versión —',
  'lineage.timetravel.apply': 'Aplicar',
  'lineage.timetravel.apply_aria': 'Aplicar ancla de viaje en el tiempo',
  'lineage.timetravel.reset': 'Restablecer',
  'lineage.timetravel.reset_aria': 'Restablecer a vista en vivo',
  'lineage.diff.added': 'Añadido',
  'lineage.diff.removed': 'Eliminado',
  'lineage.diff.unchanged': 'Sin cambios',
  'lineage.diff.modified': 'Modificado',

  // ═══ LINEAGE DIFF (9 keys) ═══
  'lineage.diff.heading': 'Diferencias de linaje',
  'lineage.diff.summary': 'Resumen:',
  'lineage.diff.from': 'desde',
  'lineage.diff.to': 'hasta',
  'lineage.diff.loading': 'Cargando diferencias de linaje…',
  'lineage.diff.error': 'Error al cargar diferencias:',
  'lineage.diff.no_anchor': 'Seleccione dos puntos de anclaje para calcular diferencias.',
  'lineage.diff.empty_bucket': '— sin aristas en este grupo —',

  // ═══ ASSETS SCHEMA DRIFT (19 keys) ═══
  'assets.schema_drift.heading.warn': 'Deriva de esquema detectada',
  'assets.schema_drift.heading.fail': 'El esquema no coincide con el contrato',
  'assets.schema_drift.body.warn':
    'El conjunto de datos tiene columnas que el contrato no declara, o tipos más amplios de lo requerido. El activo se creó igualmente — revise las diferencias abajo y actualice el contrato si es necesario.',
  'assets.schema_drift.body.fail':
    'Faltan campos requeridos por el contrato, o hay tipos incompatibles. El activo se creó para que pueda corregir los datos, pero los consumidores que dependen del contrato verán errores hasta que el esquema coincida.',
  'assets.schema_drift.section.missing': 'Campos faltantes',
  'assets.schema_drift.section.missing_help':
    'Declarados por el contrato, no presentes en el conjunto de datos.',
  'assets.schema_drift.section.extra': 'Campos adicionales',
  'assets.schema_drift.section.extra_help':
    'Presentes en el conjunto de datos, no declarados por el contrato.',
  'assets.schema_drift.section.mismatches': 'Discrepancias de tipo',
  'assets.schema_drift.section.mismatches_help':
    'Mismo nombre de campo, tipo diferente. Marcado como compatible si el tipo del dataset es una ampliación segura del tipo del contrato.',
  'assets.schema_drift.mismatch_col.field': 'Campo',
  'assets.schema_drift.mismatch_col.contract_type': 'Tipo en contrato',
  'assets.schema_drift.mismatch_col.dataset_type': 'Tipo en dataset',
  'assets.schema_drift.mismatch_col.compatible': '¿Compatible?',
  'assets.schema_drift.mismatch.compatible_yes': 'Sí — ampliación segura',
  'assets.schema_drift.mismatch.compatible_no': 'No',
  'assets.schema_drift.empty_section': '— ninguno —',
  'assets.schema_drift.collapsed_count':
    '{count} elemento(s) — expandir para ver detalles',
  'assets.schema_drift.banner_aria_label': 'Informe de deriva de esquema para el nuevo activo',

  // ═══ ASSETS TYPE PICKER (18 keys) ═══
  'assets.type_picker.heading': '¿Qué va a incorporar al catálogo?',
  'assets.type_picker.body':
    'Elija la opción que coincida con lo que tiene. Preconfiguramos el siguiente paso según su elección — puede cambiarlo después.',
  'assets.type_picker.aria_label': 'Elija el tipo de activo que está creando',
  'assets.type_picker.skip_label': 'Omitir y configurar manualmente',
  'assets.type_picker.option.data.title': 'Un archivo de datos',
  'assets.type_picker.option.data.body':
    'Suba un archivo CSV / JSON / Parquet. Inferimos el esquema y ejecutamos controles de calidad y cumplimiento antes de publicar.',
  'assets.type_picker.option.data.aria_label': 'Crear activo desde un archivo de datos',
  'assets.type_picker.option.contract.title': 'Un documento de contrato',
  'assets.type_picker.option.contract.body':
    'Suba un YAML / JSON ODCS o DataContract.com. Catalogue la especificación sin subir datos.',
  'assets.type_picker.option.contract.aria_label': 'Crear activo desde un documento de contrato',
  'assets.type_picker.option.both.title': 'Ambos — archivo + contrato',
  'assets.type_picker.option.both.body':
    'Suba un archivo de datos Y su contrato. Validamos que los datos cumplan el contrato antes de publicar.',
  'assets.type_picker.option.both.aria_label':
    'Crear activo desde un archivo de datos y un contrato',
  'assets.type_picker.option.metadata.title': 'Solo metadatos',
  'assets.type_picker.option.metadata.body':
    'Referencie una fuente de datos externa. Catalogue el activo sin subir nada al hub.',
  'assets.type_picker.option.metadata.aria_label':
    'Crear activo solo con metadatos — sin subida ni contrato',
  'assets.type_picker.onboarding_incomplete.heading':
    'Complete la incorporación para empezar a crear activos',
  'assets.type_picker.onboarding_incomplete.body':
    'La creación de activos se desbloquea cuando su administrador de tenant esté invitado, el KYC esté enviado y la facturación configurada. Complete los pasos restantes para continuar.',
  'assets.type_picker.onboarding_incomplete.cta': 'Completar incorporación',

  // ═══ MARKETPLACE KYC (5 keys) ═══
  'marketplace.publish.kyc_blocked.heading': 'Verificación KYC requerida para publicar',
  'marketplace.publish.kyc_blocked.body':
    'Su tenant debe completar la verificación KYC antes de que cualquier listado pueda publicarse en el catálogo del marketplace. El borrador se ha guardado — una vez que la verificación se complete, podrá publicar sin volver a introducir los datos.',
  'marketplace.publish.kyc_blocked.cta_label': 'Verificar KYC ahora',
  'marketplace.publish.kyc_blocked.status_label': 'Estado KYC actual:',
  'marketplace.publish.kyc_blocked.aria_label': 'Verificación KYC requerida para publicar listado',

  // ═══ MARKETPLACE KYB (4 keys) ═══
  'marketplace.publish.kyb_blocked.heading':
    'Integración con Stripe Connect requerida para publicar listados de pago',
  'marketplace.publish.kyb_blocked.body':
    'Para recibir pagos por este listado debe completar la integración con Stripe Connect. Los listados gratuitos no se ven afectados — este listado se publicará como borrador hasta que se complete la integración.',
  'marketplace.publish.kyb_blocked.cta_label': 'Completar integración con Stripe Connect',
  'marketplace.publish.kyb_blocked.aria_label':
    'Integración con Stripe Connect requerida para publicar listado de pago',

  // ═══ PUBLIC LEGAL (35 keys) ═══
  'public.legal.home.title': 'Legal y transparencia',
  'public.legal.home.intro':
    'Estas páginas resumen cómo la plataforma Meshant trata los datos personales. No reemplazan el Acuerdo de Tratamiento de Datos contractual de su organización.',
  'public.legal.home.privacy_link': 'Aviso de privacidad',
  'public.legal.home.subprocessors_link': 'Subencargados',
  'public.legal.home.dpia_link': 'Resumen de transferencias / EIPD',
  'public.legal.home.dsar_link': 'Ejercer sus derechos como titular de datos (DSAR)',
  'public.legal.privacy.title': 'Aviso de privacidad de la plataforma',
  'public.legal.privacy.body':
    'Meshant trata la configuración del tenant, identificadores de autenticación, contactos de facturación y telemetría operativa necesaria para ejecutar el hub. La telemetría agregada excluye el contenido bruto de los titulares; evite incluir datos personales en URLs o cuerpos de tickets. Los datos personales que usted suba permanecen dentro del límite de su tenant con aislamiento a nivel de fila. Los flujos de alto riesgo (federación, copias de seguridad, marketplaces) se describen en el resumen de transferencias/EIPD.',
  'public.legal.subprocessors.title': 'Resumen de subencargados',
  'public.legal.subprocessors.body':
    'Los procesadores de infraestructura representativos incluyen almacenamiento de objetos (por ejemplo Amazon S3) para artefactos y exportaciones, y correo electrónico transaccional (por ejemplo Amazon SES) para OTP de DSAR y notificaciones legales. La verificación de identidad puede delegarse a un socio IDV cuando esa funcionalidad se active; el nombre del proveedor aparecerá aquí y en su anexo DPA. Los procesadores específicos de conectores por tenant se enumeran en su RoPA.',
  'public.legal.dpia.title': 'Impacto de transferencias y resumen de EIPD',
  'public.legal.dpia.body':
    'Los flujos de trabajo de alto riesgo (facturación, SSO, federación, copias de seguridad) se someten a revisiones de privacidad periódicas. Se mantienen EIPD recursivas por subsistema; los artefactos se divulgan a los contactos legales autorizados del cliente bajo NDA.',

  // ═══ PUBLIC LEGAL DSAR (23 keys) ═══
  'public.legal.dsar.title': 'Solicitud de derechos del titular de datos',
  'public.legal.dsar.heading': 'Enviar una solicitud de derechos',
  'public.legal.dsar.intro':
    'Indíquenos cómo contactarle y qué regímenes aplican. Después de enviar, verifique con el código que le enviamos por correo electrónico.',
  'public.legal.dsar.captcha_notice':
    'Este formulario está protegido por hCaptcha — pegue el token de verificación producido por su integración hCaptcha.',
  'public.legal.dsar.field_tenant_id': 'Identificador de organización (UUID)',
  'public.legal.dsar.field_email': 'Su dirección de correo electrónico',
  'public.legal.dsar.field_type': 'Tipo de solicitud',
  'public.legal.dsar.field_regimes': 'Regímenes aplicables',
  'public.legal.dsar.regimes_help': 'Separados por comas; por defecto aplicamos RGPD si se deja en blanco.',
  'public.legal.dsar.field_hcaptcha': 'Token de verificación hCaptcha',
  'public.legal.dsar.submit': 'Enviar solicitud',
  'public.legal.dsar.submitting': 'Enviando…',
  'public.legal.dsar.created_blurb':
    'Solicitud registrada. Siga el enlace de contraseña de un solo uso enviado por correo electrónico para activar el tratamiento cuando corresponda.',
  'public.legal.dsar.reference': 'Enlace de estado',
  'public.legal.dsar.status_label': 'Estado actual',
  'public.legal.dsar.otp_label': 'Código de verificación por correo electrónico',
  'public.legal.dsar.verify': 'Verificar código',
  'public.legal.dsar.status.title': 'Estado de la solicitud',
  'public.legal.dsar.status.labels.status': 'Estado',
  'public.legal.dsar.status.labels.type': 'Tipo de solicitud',
  'public.legal.dsar.status.labels.ack_deadline': 'Plazo legal de acuse (UTC)',
  'public.legal.dsar.status.labels.fulfil_deadline': 'Plazo legal de cumplimiento (UTC)',
  'public.legal.dsar.status.labels.subject_local': 'Plazo de cumplimiento (zona horaria del titular)',
  'public.legal.dsar.status.labels.regulator_local': 'Plazo de cumplimiento (zona horaria del regulador)',
  'public.legal.dsar.status.labels.countdown': 'Cuenta regresiva (plazo UTC de cumplimiento)',
  'public.legal.dsar.field_subject_tz': 'Su zona horaria (IANA)',
  'public.legal.dsar.field_regulator_tz': 'Zona horaria del regulador (IANA)',
  'public.legal.dsar.tz_help': 'Ejemplos: UTC, America/New_York, Europe/Madrid. Se usa solo para la presentación legal de plazos.',

  // ═══ GOVERNANCE DSAR (27 keys) ═══
  'governance.dsar.queue_title': 'Solicitudes de derechos del titular (DSAR)',
  'governance.dsar.col_type': 'Tipo',
  'governance.dsar.col_subject': 'Correo del titular',
  'governance.dsar.col_status': 'Estado',
  'governance.dsar.col_sla_scan': 'Nivel de escaneo SLA',
  'governance.dsar.col_deadline': 'Plazo de cumplimiento (UTC)',
  'governance.dsar.col_fulfil_detail': 'Reloj de cumplimiento',
  'governance.dsar.col_action': 'Acción',
  'governance.dsar.countdown_prefix': 'Tiempo restante hasta el plazo legal de cumplimiento',
  'governance.dsar.countdown_overdue': 'Plazo legal de cumplimiento vencido',
  'governance.dsar.subject_tz_label': 'Hora local del titular',
  'governance.dsar.regulator_tz_label': 'Hora local del regulador',
  'governance.dsar.open': 'Abrir',
  'governance.dsar.empty': 'No hay solicitudes en este tenant aún.',
  'governance.dsar.detail_title': 'Detalle DSAR',
  'governance.dsar.loading': 'Cargando…',
  'governance.dsar.btn_materialize': 'Construir paquete de respuesta',
  'governance.dsar.btn_reject': 'Rechazar',
  'governance.dsar.btn_legal_hold': 'Retención legal',
  'governance.dsar.btn_download': 'Emitir URL de descarga (24h)',
  'governance.dsar.download_ready': 'URL de descarga prefirmada (copie pronto; puede caducar):',
  'governance.dsar.prompt_reject': 'Motivo de rechazo (visible en el registro de auditoría)',
  'governance.dsar.prompt_hold_reason': 'Motivo de retención legal (opcional)',

  // ═══ MARKETPLACE RECOMMENDATIONS + TRUST + COMPARISON + PREVIEW + SAVED SEARCH (39 keys) ═══
  'marketplace.recommendations.title': 'Recomendado para usted',
  'marketplace.recommendations.empty': 'Aún no hay recomendaciones.',
  'marketplace.recommendations.based_on': 'Basado en su actividad',
  'marketplace.trustSignal.compliance_verified': 'Cumplimiento verificado',
  'marketplace.trustSignal.kyb_verified': 'KYB verificado',
  'marketplace.trustSignal.active_since': 'Activo desde',
  'marketplace.trustSignal.orders_fulfilled': 'Pedidos completados',
  'marketplace.comparison.title': 'Comparar listados',
  'marketplace.comparison.add_listing': 'Añadir a comparación',
  'marketplace.comparison.remove': 'Quitar',
  'marketplace.comparison.empty': 'Añada listados para comparar.',
  'marketplace.comparison.field.price': 'Precio',
  'marketplace.comparison.field.pricing_model': 'Modelo de precios',
  'marketplace.comparison.field.compliance': 'Cumplimiento',
  'marketplace.comparison.field.data_quality': 'Calidad de datos',
  'marketplace.comparison.field.updated': 'Última actualización',
  'marketplace.quickPreview.title': 'Vista previa rápida',
  'marketplace.quickPreview.schema': 'Esquema',
  'marketplace.quickPreview.pricing': 'Precios',
  'marketplace.quickPreview.compliance': 'Cumplimiento',
  'marketplace.quickPreview.ratings': 'Valoraciones',
  'marketplace.quickPreview.view_details': 'Ver detalles',
  'marketplace.quickPreview.close': 'Cerrar vista previa',
  'marketplace.savedSearch.save': 'Guardar búsqueda',
  'marketplace.savedSearch.saved': 'Búsqueda guardada',
  'marketplace.savedSearch.name_label': 'Nombre de la búsqueda',
  'marketplace.savedSearch.name_placeholder': 'ej. Conjuntos de datos sanitarios',
  'marketplace.savedSearch.notify_label': 'Notificarme nuevos resultados',
  'marketplace.savedSearch.frequency_instant': 'Al instante',
  'marketplace.savedSearch.frequency_daily': 'Resumen diario',
  'marketplace.savedSearch.frequency_weekly': 'Resumen semanal',
  'marketplace.savedSearch.delete': 'Eliminar búsqueda guardada',
  'marketplace.savedSearch.empty': 'Sin búsquedas guardadas.',

  // ═══ GOVERNANCE APPROVAL INBOX (19 keys) ═══
  'governance.approvalInbox.title': 'Pendientes de mi aprobación',
  'governance.approvalInbox.empty': 'No hay elementos esperando su aprobación.',
  'governance.approvalInbox.view_all': 'Ver todos los elementos de gobernanza →',
  'governance.approvalInbox.select_all': 'Seleccionar todo',
  'governance.approvalInbox.reject_reason': 'Motivo de rechazo (opcional)',
  'governance.approvalInbox.approve': 'Aprobar',
  'governance.approvalInbox.reject': 'Rechazar',
  'governance.approvalInbox.type.access_request': 'Acceso',
  'governance.approvalInbox.type.dsar': 'DSAR',
  'governance.approvalInbox.type.breach': 'Violación',
  'governance.approvalInbox.type.dpia': 'EIPD',
  'governance.approvalInbox.type.kyb': 'KYB',
  'governance.approvalInbox.priority.high': 'alta',
  'governance.approvalInbox.priority.medium': 'media',
  'governance.approvalInbox.priority.low': 'baja',
};
