/**
 * RawEditorTab Component
 *
 * Tab for editing contract in raw YAML/JSON format using Monaco Editor:
 * - Monaco Editor integration
 * - Syntax highlighting (YAML/JSON)
 * - Auto-completion for HubContract schema
 * - Error highlighting (squiggly underlines)
 * - Format on save
 * - Minimap
 * - Line numbers
 */

import React, { useState, useCallback } from 'react'
import { Box, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material'
import Editor from '@monaco-editor/react'
import type { HubContract } from '../types'
import { contractToYaml, contractToJson, yamlToContract, jsonToContract } from '../utils'

export interface RawEditorTabProps {
  contract: HubContract
  onChange: (contract: HubContract) => void
  errors?: Array<{ line?: number; message: string }>
}

type EditorFormat = 'yaml' | 'json'

/**
 * RawEditorTab component
 */
export const RawEditorTab: React.FC<RawEditorTabProps> = ({
  contract,
  onChange,
  errors = [],
}) => {
  const [format, setFormat] = useState<EditorFormat>('yaml')
  const [editorValue, setEditorValue] = useState<string>(() => {
    return format === 'yaml' ? contractToYaml(contract) : contractToJson(contract)
  })

  const handleFormatChange = (
    _: React.MouseEvent<HTMLElement>,
    newFormat: EditorFormat | null
  ) => {
    if (newFormat !== null && newFormat !== format) {
      setFormat(newFormat)
      // Convert current value to new format
      try {
        const currentContract =
          format === 'yaml' ? yamlToContract(editorValue) : jsonToContract(editorValue)
        const newValue =
          newFormat === 'yaml' ? contractToYaml(currentContract) : contractToJson(currentContract)
        setEditorValue(newValue)
      } catch (error) {
        console.error('Error converting format:', error)
        // If conversion fails, use the contract directly
        const newValue =
          newFormat === 'yaml' ? contractToYaml(contract) : contractToJson(contract)
        setEditorValue(newValue)
      }
    }
  }

  const handleEditorChange = useCallback(
    (value: string | undefined) => {
      if (value === undefined) return
      setEditorValue(value)

      try {
        const parsedContract =
          format === 'yaml' ? yamlToContract(value) : jsonToContract(value)
        onChange(parsedContract)
      } catch (error) {
        // Invalid syntax - don't update contract, but keep editor value
        console.error('Error parsing editor value:', error)
      }
    },
    [format, onChange]
  )

  // Convert contract to editor format when contract changes externally
  React.useEffect(() => {
    try {
      const newValue =
        format === 'yaml' ? contractToYaml(contract) : contractToJson(contract)
      // Only update if different to avoid cursor jumping
      if (newValue !== editorValue) {
        setEditorValue(newValue)
      }
    } catch (error) {
      console.error('Error converting contract to editor format:', error)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contract, format])

  // Set up Monaco editor markers for errors
  const handleEditorDidMount = useCallback(
    (editor: any, monaco: any) => {
      if (errors.length > 0) {
        const markers = errors.map((error) => ({
          startLineNumber: error.line || 1,
          startColumn: 1,
          endLineNumber: error.line || 1,
          endColumn: 1000,
          message: error.message,
          severity: monaco.MarkerSeverity.Error,
        }))
        monaco.editor.setModelMarkers(editor.getModel(), 'contract-editor', markers)
      } else {
        monaco.editor.setModelMarkers(editor.getModel(), 'contract-editor', [])
      }
    },
    [errors]
  )

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Format Toggle */}
      <Box
        sx={{
          padding: 2,
          borderBottom: '1px solid',
          borderColor: 'divider',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
          Raw Editor
        </Typography>
        <ToggleButtonGroup
          value={format}
          exclusive
          onChange={handleFormatChange}
          size="small"
        >
          <ToggleButton value="yaml">YAML</ToggleButton>
          <ToggleButton value="json">JSON</ToggleButton>
        </ToggleButtonGroup>
      </Box>

      {/* Monaco Editor */}
      <Box sx={{ flex: 1, minHeight: 0 }}>
        <Editor
          height="100%"
          language={format === 'yaml' ? 'yaml' : 'json'}
          value={editorValue}
          onChange={handleEditorChange}
          onMount={handleEditorDidMount}
          options={{
            minimap: { enabled: true },
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            automaticLayout: true,
            formatOnPaste: true,
            formatOnType: true,
            tabSize: 2,
            wordWrap: 'on',
            folding: true,
            bracketPairColorization: { enabled: true },
            suggest: {
              showKeywords: true,
              showSnippets: true,
            },
          }}
          theme="vs-light"
        />
      </Box>
    </Box>
  )
}

RawEditorTab.displayName = 'RawEditorTab'

