import React from 'react'
import { Button } from '@mui/material'
import { cn } from '@/components/utils'
import { colors, spacing, borderRadius } from '@/styles/tokens'
import { EmptyStateHelpText, type HelpLink } from './EmptyStateHelpText'
import {
  EmptyBoxIllustration,
  EmptyFolderIllustration,
  EmptySearchIllustration,
  EmptyListIllustration,
  EmptyDataIllustration,
  EmptyNetworkIllustration,
} from './EmptyStateIllustrations'

export type EmptyStateContext =
  | 'no-data'
  | 'no-results'
  | 'no-items'
  | 'no-files'
  | 'no-connections'
  | 'error'
  | 'custom'

export interface EmptyStateAction {
  /**
   * Action label
   */
  label: string
  /**
   * Action handler
   */
  onClick: () => void
  /**
   * Primary action (styled as primary button)
   * @default false
   */
  primary?: boolean
  /**
   * Action variant
   * @default 'contained'
   */
  variant?: 'contained' | 'outlined' | 'text'
}

export interface EnhancedEmptyStateProps {
  /**
   * Context type for predefined empty states
   */
  context?: EmptyStateContext
  /**
   * Custom illustration component
   */
  illustration?: React.ReactNode
  /**
   * Illustration size
   * @default 120
   */
  illustrationSize?: number
  /**
   * Title text
   */
  title: string
  /**
   * Description text
   */
  description?: string
  /**
   * Primary action (CTA button)
   */
  primaryAction?: EmptyStateAction
  /**
   * Secondary actions
   */
  secondaryActions?: EmptyStateAction[]
  /**
   * Help text
   */
  helpText?: string
  /**
   * Help links
   */
  helpLinks?: HelpLink[]
  /**
   * Custom help content
   */
  helpContent?: React.ReactNode
  /**
   * Custom content to render below description
   */
  children?: React.ReactNode
  /**
   * Minimum height
   * @default 'auto'
   */
  minHeight?: string | number
  className?: string
}

/**
 * Get default illustration for context
 */
function getContextIllustration(
  context: EmptyStateContext,
  size: number
): React.ReactNode {
  switch (context) {
    case 'no-data':
      return <EmptyDataIllustration size={size} />
    case 'no-results':
      return <EmptySearchIllustration size={size} />
    case 'no-items':
      return <EmptyListIllustration size={size} />
    case 'no-files':
      return <EmptyFolderIllustration size={size} />
    case 'no-connections':
      return <EmptyNetworkIllustration size={size} />
    case 'error':
      return <EmptyBoxIllustration size={size} />
    default:
      return <EmptyBoxIllustration size={size} />
  }
}

/**
 * Enhanced EmptyState component with comprehensive features
 *
 * Features:
 * - Contextual empty states with predefined illustrations
 * - Primary and secondary action buttons
 * - SVG illustrations
 * - Help text with links
 * - Fully customizable
 *
 * @example
 * ```tsx
 * <EnhancedEmptyState
 *   context="no-data"
 *   title="No assets yet"
 *   description="Create your first asset to get started"
 *   primaryAction={{
 *     label: "Create Asset",
 *     onClick: () => navigate('/assets/create'),
 *     primary: true,
 *   }}
 *   helpLinks={[
 *     { text: "Learn more", href: "/docs/assets" },
 *     { text: "View examples", href: "/examples", external: true },
 *   ]}
 * />
 * ```
 */
export const EnhancedEmptyState: React.FC<EnhancedEmptyStateProps> = ({
  context = 'custom',
  illustration,
  illustrationSize = 120,
  title,
  description,
  primaryAction,
  secondaryActions = [],
  helpText,
  helpLinks = [],
  helpContent,
  children,
  minHeight = 'auto',
  className,
}) => {
  // Get illustration based on context if not provided
  const displayIllustration =
    illustration || getContextIllustration(context, illustrationSize)

  const hasActions = primaryAction || secondaryActions.length > 0
  const hasHelp = helpText || helpLinks.length > 0 || helpContent

  return (
    <div
      className={cn('enhanced-empty-state', className)}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: spacing[8],
        textAlign: 'center',
        minHeight: typeof minHeight === 'number' ? `${minHeight}px` : minHeight,
      }}
    >
      {/* Illustration */}
      {displayIllustration && (
        <div
          style={{
            marginBottom: spacing[6],
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {displayIllustration}
        </div>
      )}

      {/* Title */}
      <h3
        style={{
          fontSize: '24px',
          fontWeight: 600,
          color: colors.semantic.textPrimary,
          margin: 0,
          marginBottom: spacing[2],
          lineHeight: 1.3,
        }}
      >
        {title}
      </h3>

      {/* Description */}
      {description && (
        <p
          style={{
            fontSize: '16px',
            color: colors.semantic.textSecondary,
            margin: 0,
            marginBottom: hasActions || children ? spacing[6] : hasHelp ? spacing[4] : 0,
            maxWidth: '500px',
            lineHeight: 1.6,
          }}
        >
          {description}
        </p>
      )}

      {/* Custom children */}
      {children}

      {/* Actions */}
      {hasActions && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: spacing[2],
            alignItems: 'center',
            marginBottom: hasHelp ? spacing[6] : 0,
            width: '100%',
            maxWidth: '400px',
          }}
        >
          {/* Primary Action */}
          {primaryAction && (
            <Button
              variant={primaryAction.variant || 'contained'}
              color={primaryAction.primary !== false ? 'primary' : 'inherit'}
              onClick={primaryAction.onClick}
              sx={{
                minWidth: '200px',
                padding: `${spacing[2]}px ${spacing[4]}px`,
                fontSize: '14px',
                fontWeight: 500,
                borderRadius: borderRadius.md,
                textTransform: 'none',
              }}
            >
              {primaryAction.label}
            </Button>
          )}

          {/* Secondary Actions */}
          {secondaryActions.length > 0 && (
            <div
              style={{
                display: 'flex',
                gap: spacing[2],
                flexWrap: 'wrap',
                justifyContent: 'center',
              }}
            >
              {secondaryActions.map((action, index) => (
                <Button
                  key={index}
                  variant={action.variant || 'outlined'}
                  onClick={action.onClick}
                  sx={{
                    padding: `${spacing[2]}px ${spacing[4]}px`,
                    fontSize: '14px',
                    fontWeight: 400,
                    borderRadius: borderRadius.md,
                    textTransform: 'none',
                    borderColor: colors.semantic.borderDefault,
                    color: colors.semantic.textPrimary,
                    '&:hover': {
                      borderColor: colors.primary[500],
                      backgroundColor: colors.primary[50],
                    },
                  }}
                >
                  {action.label}
                </Button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Help Text */}
      {hasHelp && (
        <EmptyStateHelpText text={helpText} links={helpLinks}>
          {helpContent}
        </EmptyStateHelpText>
      )}
    </div>
  )
}

EnhancedEmptyState.displayName = 'EnhancedEmptyState'

