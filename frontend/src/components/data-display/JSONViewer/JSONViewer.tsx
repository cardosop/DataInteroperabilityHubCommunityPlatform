import React, { useState } from 'react'
import { cn } from '@/components/utils'
import { colors, spacing, borderRadius } from '@/styles/tokens'
import { typography } from '@/styles/tokens'

export interface JSONViewerProps {
  /**
   * JSON data to display
   */
  data: object | string
  /**
   * Whether to show copy button
   * @default true
   */
  showCopy?: boolean
  /**
   * Whether to show search
   * @default false
   */
  showSearch?: boolean
  className?: string
}

/**
 * JSONViewer component for displaying JSON data
 */
export const JSONViewer: React.FC<JSONViewerProps> = ({
  data,
  showCopy = true,
  showSearch = false,
  className,
}) => {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [copied, setCopied] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')

  const jsonString =
    typeof data === 'string' ? data : JSON.stringify(data, null, 2)
  const jsonData = typeof data === 'string' ? JSON.parse(data) : data

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(jsonString)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  const toggleExpand = (path: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(path)) {
        next.delete(path)
      } else {
        next.add(path)
      }
      return next
    })
  }

  const renderValue = (value: any, path: string = '', depth: number = 0): React.ReactNode => {
    if (value === null) {
      return <span style={{ color: '#808080' }}>null</span>
    }

    if (typeof value === 'string') {
      return <span style={{ color: '#98C379' }}>"{value}"</span>
    }

    if (typeof value === 'number') {
      return <span style={{ color: '#D19A66' }}>{value}</span>
    }

    if (typeof value === 'boolean') {
      return <span style={{ color: '#56B6C2' }}>{String(value)}</span>
    }

    if (Array.isArray(value)) {
      const isExpanded = expanded.has(path)
      return (
        <div style={{ marginLeft: `${depth * 20}px` }}>
          <span
            onClick={() => toggleExpand(path)}
            style={{
              cursor: 'pointer',
              color: '#C678DD',
              userSelect: 'none',
            }}
          >
            {isExpanded ? '▼' : '▶'} [
          </span>
          {isExpanded && (
            <div>
              {value.map((item, index) => (
                <div key={index}>
                  {renderValue(item, `${path}[${index}]`, depth + 1)}
                  {index < value.length - 1 && <span>,</span>}
                </div>
              ))}
            </div>
          )}
          {!isExpanded && <span style={{ color: '#C678DD' }}>...]</span>}
          {isExpanded && (
            <span style={{ color: '#C678DD' }}>
              {' '.repeat(depth * 20)}]
            </span>
          )}
        </div>
      )
    }

    if (typeof value === 'object') {
      const isExpanded = expanded.has(path)
      const keys = Object.keys(value)
      return (
        <div style={{ marginLeft: `${depth * 20}px` }}>
          <span
            onClick={() => toggleExpand(path)}
            style={{
              cursor: 'pointer',
              color: '#C678DD',
              userSelect: 'none',
            }}
          >
            {isExpanded ? '▼' : '▶'} {'{'}
          </span>
          {isExpanded && (
            <div>
              {keys.map((key, index) => (
                <div key={key}>
                  <span style={{ color: '#E06C75' }}>"{key}"</span>:{' '}
                  {renderValue(value[key], `${path}.${key}`, depth + 1)}
                  {index < keys.length - 1 && <span>,</span>}
                </div>
              ))}
            </div>
          )}
          {!isExpanded && <span style={{ color: '#C678DD' }}>...{'}'}</span>}
          {isExpanded && (
            <span style={{ color: '#C678DD' }}>
              {' '.repeat(depth * 20)}
              {'}'}
            </span>
          )}
        </div>
      )
    }

    return null
  }

  return (
    <div
      className={cn('json-viewer', className)}
      style={{
        position: 'relative',
        background: colors.gray[900],
        borderRadius: borderRadius.md,
        overflow: 'hidden',
      }}
    >
      {(showCopy || showSearch) && (
        <div
          style={{
            display: 'flex',
            gap: spacing[2],
            padding: spacing[2],
            borderBottom: `1px solid ${colors.gray[700]}`,
          }}
        >
          {showSearch && (
            <input
              type="text"
              placeholder="Search..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{
                flex: 1,
                padding: spacing[2],
                background: colors.gray[800],
                border: `1px solid ${colors.gray[700]}`,
                borderRadius: borderRadius.sm,
                color: '#FFFFFF',
                fontSize: '14px',
              }}
            />
          )}
          {showCopy && (
            <button
              onClick={handleCopy}
              style={{
                padding: `${spacing[1]}px ${spacing[2]}px`,
                background: colors.gray[700],
                border: 'none',
                borderRadius: borderRadius.sm,
                color: '#FFFFFF',
                fontSize: '12px',
                cursor: 'pointer',
              }}
            >
              {copied ? 'Copied!' : 'Copy'}
            </button>
          )}
        </div>
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
          maxHeight: '500px',
        }}
      >
        {renderValue(jsonData)}
      </pre>
    </div>
  )
}

JSONViewer.displayName = 'JSONViewer'

