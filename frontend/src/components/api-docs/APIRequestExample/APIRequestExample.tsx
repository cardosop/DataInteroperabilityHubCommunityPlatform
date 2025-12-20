/**
 * APIRequestExample Component
 *
 * Component for displaying API request examples with syntax highlighting:
 * - Supports multiple languages (JSON, cURL, JavaScript, Python)
 * - Syntax highlighting using Monaco Editor
 * - Copy to clipboard functionality
 * - Automatic formatting
 */

import React, { useMemo, useState, useCallback } from 'react'
import { Box, IconButton, Tooltip } from '@mui/material'
import { ContentCopy as CopyIcon } from '@mui/icons-material'
import Editor from '@monaco-editor/react'
import type { APIEndpoint } from '../APIEndpointCard/types'
import { generateCurlSnippet, generateJavaScriptSnippet, generatePythonSnippet } from './utils'

export type RequestExampleLanguage = 'json' | 'curl' | 'javascript' | 'python'

export interface APIRequestExampleProps {
  /**
   * API endpoint information
   */
  endpoint: APIEndpoint
  /**
   * Base URL for the API
   */
  baseUrl: string
  /**
   * Language for the request example
   * @default 'json'
   */
  language?: RequestExampleLanguage
  /**
   * Authentication token (optional, for code examples)
   */
  authToken?: string
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
 * Get Monaco Editor language from request example language
 */
function getMonacoLanguage(language: RequestExampleLanguage): string {
  switch (language) {
    case 'json':
      return 'json'
    case 'curl':
      return 'shell'
    case 'javascript':
      return 'javascript'
    case 'python':
      return 'python'
    default:
      return 'text'
  }
}

/**
 * APIRequestExample component
 */
export const APIRequestExample: React.FC<APIRequestExampleProps> = ({
  endpoint,
  baseUrl,
  language = 'json',
  authToken,
  showCopy = true,
  height = '300px',
  className,
}) => {
  const [copied, setCopied] = useState(false)

  // Generate request example based on language
  const requestExample = useMemo(() => {
    const token = authToken || 'YOUR_AUTH_TOKEN'

    switch (language) {
      case 'curl':
        return generateCurlSnippet(endpoint, baseUrl, token)
      case 'javascript':
        return generateJavaScriptSnippet(endpoint, baseUrl, token)
      case 'python':
        return generatePythonSnippet(endpoint, baseUrl, token)
      case 'json':
      default:
        // For JSON, show the request body if available
        if (endpoint.parameters?.body?.example) {
          return JSON.stringify(endpoint.parameters.body.example, null, 2)
        }
        return '{}'
    }
  }, [endpoint, baseUrl, language, authToken])

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(requestExample)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }, [requestExample])

  const monacoLanguage = getMonacoLanguage(language)

  return (
    <Box className={className} sx={{ position: 'relative' }}>
      {showCopy && (
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
        language={monacoLanguage}
        value={requestExample}
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
  )
}

APIRequestExample.displayName = 'APIRequestExample'

