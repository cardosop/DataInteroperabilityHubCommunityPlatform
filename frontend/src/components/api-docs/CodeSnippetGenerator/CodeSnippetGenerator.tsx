/**
 * CodeSnippetGenerator Component
 *
 * Component for generating and displaying code snippets in multiple languages:
 * - Language tabs (cURL, JavaScript, Python)
 * - Syntax highlighting using Monaco Editor
 * - Copy to clipboard functionality
 * - Language switching
 */

import React, { useState, useMemo, useCallback } from 'react'
import { Box, Tabs, Tab, IconButton, Tooltip, Typography } from '@mui/material'
import { ContentCopy as CopyIcon } from '@mui/icons-material'
import Editor from '@monaco-editor/react'
import type { APIEndpoint } from '../APIEndpointCard/types'
import {
  generateCurlSnippet,
  generateJavaScriptSnippet,
  generatePythonSnippet,
} from '../APIRequestExample/utils'

export type CodeSnippetLanguage = 'curl' | 'javascript' | 'python'

export interface CodeSnippetGeneratorProps {
  /**
   * API endpoint information
   */
  endpoint: APIEndpoint
  /**
   * Base URL for the API
   */
  baseUrl: string
  /**
   * Authentication token (optional, for code examples)
   */
  authToken?: string
  /**
   * Available languages
   * @default ['curl', 'javascript', 'python']
   */
  languages?: CodeSnippetLanguage[]
  /**
   * Default language
   * @default 'curl'
   */
  defaultLanguage?: CodeSnippetLanguage
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
 * Get Monaco Editor language from code snippet language
 */
function getMonacoLanguage(language: CodeSnippetLanguage): string {
  switch (language) {
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
 * Get language display name
 */
function getLanguageName(language: CodeSnippetLanguage): string {
  switch (language) {
    case 'curl':
      return 'cURL'
    case 'javascript':
      return 'JavaScript'
    case 'python':
      return 'Python'
    default:
      return language
  }
}

/**
 * CodeSnippetGenerator component
 */
export const CodeSnippetGenerator: React.FC<CodeSnippetGeneratorProps> = ({
  endpoint,
  baseUrl,
  authToken,
  languages = ['curl', 'javascript', 'python'],
  defaultLanguage = 'curl',
  height = '300px',
  className,
}) => {
  const [selectedLanguage, setSelectedLanguage] = useState<CodeSnippetLanguage>(defaultLanguage)
  const [copied, setCopied] = useState(false)

  // Generate code snippet based on selected language
  const codeSnippet = useMemo(() => {
    const token = authToken || 'YOUR_AUTH_TOKEN'

    switch (selectedLanguage) {
      case 'curl':
        return generateCurlSnippet(endpoint, baseUrl, token)
      case 'javascript':
        return generateJavaScriptSnippet(endpoint, baseUrl, token)
      case 'python':
        return generatePythonSnippet(endpoint, baseUrl, token)
      default:
        return ''
    }
  }, [endpoint, baseUrl, selectedLanguage, authToken])

  const handleLanguageChange = useCallback((_event: React.SyntheticEvent, newValue: CodeSnippetLanguage) => {
    setSelectedLanguage(newValue)
    setCopied(false)
  }, [])

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(codeSnippet)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }, [codeSnippet])

  const monacoLanguage = getMonacoLanguage(selectedLanguage)

  return (
    <Box className={className}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
          Code Example
        </Typography>
        <Tooltip title={copied ? 'Copied!' : 'Copy code'}>
          <IconButton size="small" onClick={handleCopy}>
            <CopyIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>
      <Tabs
        value={selectedLanguage}
        onChange={handleLanguageChange}
        sx={{ borderBottom: 1, borderColor: 'divider', mb: 1 }}
      >
        {languages.map((language) => (
          <Tab
            key={language}
            label={getLanguageName(language)}
            value={language}
            sx={{ textTransform: 'none' }}
          />
        ))}
      </Tabs>
      <Box sx={{ position: 'relative' }}>
        <Editor
          height={height}
          language={monacoLanguage}
          value={codeSnippet}
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

CodeSnippetGenerator.displayName = 'CodeSnippetGenerator'

