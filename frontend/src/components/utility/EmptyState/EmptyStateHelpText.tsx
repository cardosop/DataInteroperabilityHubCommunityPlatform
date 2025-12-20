import React from 'react'
import { colors, spacing } from '@/styles/tokens'
import { cn } from '@/components/utils'
import { Link } from '@mui/material'

export interface HelpLink {
  /**
   * Link text
   */
  text: string
  /**
   * Link URL
   */
  href: string
  /**
   * Open in new tab
   * @default false
   */
  external?: boolean
}

export interface EmptyStateHelpTextProps {
  /**
   * Help text content
   */
  text?: string
  /**
   * Help links
   */
  links?: HelpLink[]
  /**
   * Custom help content
   */
  children?: React.ReactNode
  className?: string
}

/**
 * Help text component for empty states
 *
 * Displays guidance text and links to help users understand what to do next.
 */
export const EmptyStateHelpText: React.FC<EmptyStateHelpTextProps> = ({
  text,
  links = [],
  children,
  className,
}) => {
  if (!text && links.length === 0 && !children) {
    return null
  }

  return (
    <div
      className={cn('empty-state-help-text', className)}
      style={{
        marginTop: spacing[4],
        paddingTop: spacing[4],
        borderTop: `1px solid ${colors.semantic.borderDivider}`,
      }}
    >
      {text && (
        <p
          style={{
            fontSize: '13px',
            color: colors.semantic.textSecondary,
            margin: 0,
            marginBottom: links.length > 0 ? spacing[2] : 0,
            lineHeight: 1.5,
          }}
        >
          {text}
        </p>
      )}

      {links.length > 0 && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: spacing[1],
            alignItems: 'center',
          }}
        >
          {links.map((link, index) => (
            <Link
              key={index}
              href={link.href}
              target={link.external ? '_blank' : undefined}
              rel={link.external ? 'noopener noreferrer' : undefined}
              style={{
                fontSize: '13px',
                color: colors.primary[600],
                textDecoration: 'none',
                cursor: 'pointer',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.textDecoration = 'underline'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.textDecoration = 'none'
              }}
            >
              {link.text} {link.external && '↗'}
            </Link>
          ))}
        </div>
      )}

      {children}
    </div>
  )
}

EmptyStateHelpText.displayName = 'EmptyStateHelpText'

