/**
 * APIResponseExample Component
 *
 * Component for displaying API response examples with syntax highlighting:
 * - JSON response formatting
 * - Syntax highlighting using Monaco Editor
 * - Status code badge with color coding
 * - Copy to clipboard functionality
 * - Response description
 */

import React, { useMemo, useState, useCallback } from 'react'
import { Box, Chip, Typography, IconButton, Tooltip } from '@mui/material'
import { ContentCopy as CopyIcon } from '@mui/icons-material'
import Editor from '@monaco-editor/react'
import type { APIResponse } from '../APIEndpointCard/types'

export interface APIResponseExampleProps {
  /**
   * API response information
   */
  response: APIResponse
  /**
   * Whether to show copy button
   * @default true
   */
  showCopy?: boolean
  /**
   * Height of the editor
   * @default '300px'
   */
  height?: string
  /**
   * Additional CSS class name
   */
  className?: string
}

/**
 * Get color for status code badge
 */
function getStatusColor(status: number): 'success' | 'info' | 'warning' | 'error' | 'default' {
  if (status >= 200 && status < 300) {
    return 'success'
  }
  if (status >= 300 && status < 400) {
    return 'info'
  }
  if (status >= 400 && status < 500) {
    return 'error'
  }
  if (status >= 500) {
    return 'error'
  }
  return 'default'
}

/**
 * APIResponseExample component
 */
export const APIResponseExample: React.FC<APIResponseExampleProps> = ({
  response,
  showCopy = true,
  height = '300px',
  className,
}) => {
  const [copied, setCopied] = useState(false)

  // Format response example as JSON
  const responseExample = useMemo(() => {
    if (response.example) {
      return JSON.stringify(response.example, null, 2)
    }
    return ''
  }, [response.example])

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(responseExample)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }, [responseExample])

  const statusColor = getStatusColor(response.status)

  return (
    <Box className={className}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
        <Chip label={response.status} size="small" color={statusColor} />
        <Typography variant="body2" color="text.secondary">
          {response.description}
        </Typography>
      </Box>
      <Box sx={{ position: 'relative' }}>
        {showCopy && responseExample && (
          <Box
            sx={{
              position: 'absolute',
              top: 8,
              right: 8,
              zIndex: 1,
              backgroundColor: 'background.paper',
              borderRadius: 1,
            }}
          >
            <Tooltip title={copied ? 'Copied!' : 'Copy code'}>
              <IconButton size="small" onClick={handleCopy}>
                <CopyIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        )}
        <Editor
          height={height}
          language="json"
          value={responseExample}
          options={{
            readOnly: true,
            minimap: { enabled: false },
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            automaticLayout: true,
            wordWrap: 'on',
            folding: true,
            bracketPairColorization: { enabled: true },
            fontSize: 14,
            theme: 'vs-dark',
          }}
        />
      </Box>
    </Box>
  )
}

APIResponseExample.displayName = 'APIResponseExample'

