/**
 * useErrorMessage Hook
 *
 * React hook for getting localized, user-friendly error messages:
 * - i18n support
 * - Contextual templates
 * - Suggested actions
 * - Help links
 * - Clear next steps
 */

import { useTranslation } from 'react-i18next'
import {
  getErrorMessageTemplate,
  type ErrorMessageTemplate,
  type SuggestedAction,
  type HelpLink,
} from './ErrorMessageTemplates'

export interface UseErrorMessageResult {
  /**
   * Error message template
   */
  template: ErrorMessageTemplate
  /**
   * Localized title
   */
  title: string
  /**
   * Localized message
   */
  message: string
  /**
   * Localized details (if available)
   */
  details?: string
  /**
   * Error severity
   */
  severity: ErrorMessageTemplate['severity']
  /**
   * Suggested actions
   */
  suggestedActions: SuggestedAction[]
  /**
   * Help links
   */
  helpLinks: HelpLink[]
  /**
   * Next steps
   */
  nextSteps: string[]
  /**
   * Whether error is recoverable
   */
  recoverable: boolean
}

/**
 * useErrorMessage Hook
 *
 * @example
 * ```tsx
 * function ErrorDisplay({ error }: { error: Error }) {
 *   const { title, message, suggestedActions, helpLinks } = useErrorMessage(error)
 *
 *   return (
 *     <Alert severity="error">
 *       <AlertTitle>{title}</AlertTitle>
 *       {message}
 *       {suggestedActions.map(action => (
 *         <Button key={action.label} onClick={action.onClick}>
 *           {action.label}
 *         </Button>
 *       ))}
 *     </Alert>
 *   )
 * }
 * ```
 */
export function useErrorMessage(error: unknown): UseErrorMessageResult {
  const { t, i18n } = useTranslation()
  const template = getErrorMessageTemplate(error)

  // Get localized messages if i18n key exists
  const getLocalizedText = (key: string, fallback: string): string => {
    if (template.i18nKey) {
      const translationKey = `${template.i18nKey}.${key}`
      const translated = t(translationKey, { defaultValue: fallback })
      // If translation exists and is different from key, use it
      if (translated !== translationKey) {
        return translated
      }
    }
    return fallback
  }

  const title = getLocalizedText('title', template.title)
  const message = getLocalizedText('message', template.message)
  const details = template.details
    ? getLocalizedText('details', template.details)
    : undefined

  // Localize next steps
  const nextSteps = template.nextSteps?.map((step, index) => {
    if (template.i18nKey) {
      const translationKey = `${template.i18nKey}.nextSteps.${index}`
      const translated = t(translationKey, { defaultValue: step })
      if (translated !== translationKey) {
        return translated
      }
    }
    return step
  }) || []

  // Localize help link labels
  const helpLinks: HelpLink[] = (template.helpLinks || []).map((link) => {
    if (template.i18nKey) {
      const translationKey = `${template.i18nKey}.helpLinks.${link.label}`
      const translated = t(translationKey, { defaultValue: link.label })
      return {
        ...link,
        label: translated !== translationKey ? translated : link.label,
      }
    }
    return link
  })

  // Localize action labels
  const suggestedActions: SuggestedAction[] = (template.suggestedActions || []).map((action) => {
    if (template.i18nKey) {
      const translationKey = `${template.i18nKey}.actions.${action.label}`
      const translated = t(translationKey, { defaultValue: action.label })
      return {
        ...action,
        label: translated !== translationKey ? translated : action.label,
      }
    }
    return action
  })

  return {
    template,
    title,
    message,
    details,
    severity: template.severity,
    suggestedActions,
    helpLinks,
    nextSteps,
    recoverable: template.recoverable,
  }
}

