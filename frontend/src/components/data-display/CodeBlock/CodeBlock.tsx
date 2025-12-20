import React, { useState } from 'react'
import { cn } from '@/components/utils'
import { colors, spacing, borderRadius } from '@/styles/tokens'
import { typography } from '@/styles/tokens'

export interface CodeBlockProps {
  /**
   * Code content
   */
  code: string
  /**
   * Language for syntax highlighting
   */
  language?: string
  /**
   * Whether to show copy button
   * @default true
   */
  showCopy?: boolean
  className?: string
}

/**
 * CodeBlock component for code display with syntax highlighting
 * Note: For full syntax highlighting, consider integrating a library like Prism.js or highlight.js
 */
export const CodeBlock: React.FC<CodeBlockProps> = ({
  code,
  language,
  showCopy = true,
  className,
}) => {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  return (
    <div
      className={cn('code-block', className)}
      style={{
        position: 'relative',
        background: colors.gray[900],
        borderRadius: borderRadius.md,
        overflow: 'hidden',
      }}
    >
      {showCopy && (
        <button
          onClick={handleCopy}
          style={{
            position: 'absolute',
            top: spacing[2],
            right: spacing[2],
            padding: `${spacing[1]}px ${spacing[2]}px`,
            background: colors.gray[700],
            border: 'none',
            borderRadius: borderRadius.sm,
            color: '#FFFFFF',
            fontSize: '12px',
            cursor: 'pointer',
            zIndex: 1,
          }}
        >
          {copied ? 'Copied!' : 'Copy'}
        </button>
      )}
      <pre
        style={{
          margin: 0,
          padding: spacing[4],
          overflow: 'auto',
          fontSize: typography.fontSize.code.rem,
          fontFamily: typography.fontFamily.monospace,
          color: '#FFFFFF',
          lineHeight: 1.5,
        }}
      >
        <code>{code}</code>
      </pre>
    </div>
  )
}

CodeBlock.displayName = 'CodeBlock'

