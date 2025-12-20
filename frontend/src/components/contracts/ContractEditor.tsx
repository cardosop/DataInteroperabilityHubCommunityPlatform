/**
 * ContractEditor Component
 *
 * Main contract editor component with:
 * - Multi-mode editing (Form, YAML)
 * - Real-time validation
 * - Auto-save draft every 30 seconds
 * - Normalization status tracking
 * - Dirty state detection
 * - Schema comparison (contract-first flow)
 * - All 7 tabs (Overview, Schema, Quality, Compliance, Lifecycle, Marketplace, RawEditor)
 */

import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  Box,
  Tabs,
  Tab,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
} from '@mui/material'
import {
  Info as InfoIcon,
  Schema as SchemaIcon,
  CheckCircle as QualityIcon,
  Security as ComplianceIcon,
  Refresh as LifecycleIcon,
  Store as MarketplaceIcon,
  Code as RawEditorIcon,
} from '@mui/icons-material'
import { EditorHeader } from './EditorHeader'
import { ValidationPanel } from './ValidationPanel'
import { ContractPreview } from './ContractPreview'
import { OverviewTab } from './tabs/OverviewTab'
import { SchemaTab } from './tabs/SchemaTab'
import { QualityTab } from './tabs/QualityTab'
import { ComplianceTab } from './tabs/ComplianceTab'
import { LifecycleTab } from './tabs/LifecycleTab'
import { MarketplaceTab } from './tabs/MarketplaceTab'
import { RawEditorTab } from './tabs/RawEditorTab'
import { SchemaComparison } from './SchemaComparison'
import { useContractHistory } from './hooks/useContractHistory'
import { createDefaultContract, validateContractStructure } from './utils'
import type {
  ContractEditorProps,
  HubContract,
  ValidationResult,
  ValidationStatus,
  NormalizationStatus,
  SchemaField,
} from './types'

/**
 * Tab configuration
 */
const TAB_CONFIG = [
  { id: 'overview', label: 'Overview', icon: <InfoIcon /> },
  { id: 'schema', label: 'Schema', icon: <SchemaIcon /> },
  { id: 'quality', label: 'Quality', icon: <QualityIcon /> },
  { id: 'compliance', label: 'Compliance', icon: <ComplianceIcon /> },
  { id: 'lifecycle', label: 'Lifecycle', icon: <LifecycleIcon /> },
  { id: 'marketplace', label: 'Marketplace', icon: <MarketplaceIcon /> },
  { id: 'raw', label: 'Raw Editor', icon: <RawEditorIcon /> },
]

/**
 * ContractEditor component
 */
export const ContractEditor: React.FC<ContractEditorProps> = ({
  contractId,
  assetId,
  initialContract,
  mode = 'create',
  onboardingFlow,
  inferredSchema,
  onSave,
  onValidate,
  onCancel,
}) => {
  // Initial contract
  const initialContractState = initialContract || createDefaultContract(contractId)

  // Undo/Redo history
  const {
    currentContract: historyContract,
    canUndo,
    canRedo,
    undo: historyUndo,
    redo: historyRedo,
    push: historyPush,
  } = useContractHistory(initialContractState, {
    maxHistorySize: 50,
    enableKeyboardShortcuts: true,
  })

  // State
  const [contract, setContract] = useState<HubContract>(historyContract)
  const [activeTab, setActiveTab] = useState('overview')
  const [validationStatus, setValidationStatus] = useState<ValidationStatus | undefined>()
  const [normalizationStatus, setNormalizationStatus] = useState<NormalizationStatus | undefined>()
  const [isDirty, setIsDirty] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isValidating, setIsValidating] = useState(false)
  const [errors, setErrors] = useState<ValidationResult['errors']>([])
  const [warnings, setWarnings] = useState<ValidationResult['warnings']>([])
  const [showUnsavedDialog, setShowUnsavedDialog] = useState(false)
  const [pendingAction, setPendingAction] = useState<(() => void) | null>(null)
  const [showPreview, setShowPreview] = useState(false)

  // Refs
  const autoSaveTimerRef = useRef<NodeJS.Timeout | null>(null)
  const lastSavedContractRef = useRef<HubContract>(contract)

  // Sync contract with history
  useEffect(() => {
    setContract(historyContract)
  }, [historyContract])

  // Initialize contract from initialContract prop
  useEffect(() => {
    if (initialContract) {
      setContract(initialContract)
      lastSavedContractRef.current = initialContract
    }
  }, [initialContract])

  // Auto-save draft every 30 seconds
  useEffect(() => {
    if (isDirty && mode === 'edit' && contractId) {
      autoSaveTimerRef.current = setInterval(() => {
        handleAutoSave()
      }, 30000) // 30 seconds

      return () => {
        if (autoSaveTimerRef.current) {
          clearInterval(autoSaveTimerRef.current)
        }
      }
    }
  }, [isDirty, mode, contractId])

  // Real-time validation on contract changes
  useEffect(() => {
    if (isDirty) {
      const validation = validateContractStructure(contract)
      if (!validation.isValid) {
        setErrors(
          validation.errors.map((msg) => ({
            message: msg,
          }))
        )
        setValidationStatus('INVALID')
      } else {
        // Clear structure errors, but keep API validation errors
        setErrors((prev) => prev.filter((e) => !e.field || e.field.startsWith('schema')))
      }
    }
  }, [contract, isDirty])

  // Track dirty state
  useEffect(() => {
    const isContractDirty = JSON.stringify(contract) !== JSON.stringify(lastSavedContractRef.current)
    setIsDirty(isContractDirty)
  }, [contract])

  const handleContractChange = useCallback(
    (updatedContract: HubContract) => {
      setContract(updatedContract)
      // Push to history for undo/redo
      historyPush(updatedContract)
    },
    [historyPush]
  )

  const handleUndo = useCallback(() => {
    const previousContract = historyUndo()
    if (previousContract) {
      setContract(previousContract)
    }
  }, [historyUndo])

  const handleRedo = useCallback(() => {
    const nextContract = historyRedo()
    if (nextContract) {
      setContract(nextContract)
    }
  }, [historyRedo])

  const handlePreview = useCallback(() => {
    setShowPreview(true)
  }, [])

  const handleClosePreview = useCallback(() => {
    setShowPreview(false)
  }, [])

  const handleAutoSave = useCallback(async () => {
    if (!isDirty || isSaving) return

    try {
      setIsSaving(true)
      await onSave(contract)
      lastSavedContractRef.current = contract
      setIsDirty(false)
    } catch (error) {
      console.error('Auto-save failed:', error)
    } finally {
      setIsSaving(false)
    }
  }, [contract, isDirty, isSaving, onSave])

  const handleSave = useCallback(async () => {
    try {
      setIsSaving(true)
      await onSave(contract)
      lastSavedContractRef.current = contract
      setIsDirty(false)
    } catch (error) {
      console.error('Save failed:', error)
      throw error
    } finally {
      setIsSaving(false)
    }
  }, [contract, onSave])

  const handleValidate = useCallback(async () => {
    try {
      setIsValidating(true)
      const result: ValidationResult = await onValidate(contract)
      setValidationStatus(result.validation_status)
      setErrors(result.errors)
      setWarnings(result.warnings)
    } catch (error) {
      console.error('Validation failed:', error)
      setValidationStatus('ERROR')
      setErrors([
        {
          message: error instanceof Error ? error.message : 'Validation failed',
        },
      ])
    } finally {
      setIsValidating(false)
    }
  }, [contract, onValidate])

  const handleCancel = useCallback(() => {
    if (isDirty) {
      setPendingAction(() => onCancel)
      setShowUnsavedDialog(true)
    } else {
      onCancel()
    }
  }, [isDirty, onCancel])

  const handleConfirmCancel = useCallback(() => {
    setShowUnsavedDialog(false)
    if (pendingAction) {
      pendingAction()
      setPendingAction(null)
    }
  }, [pendingAction])

  const handleNavigateToField = useCallback((fieldName?: string) => {
    if (fieldName) {
      setActiveTab('schema')
      // Field navigation would be handled by SchemaTab component
    }
  }, [])

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return <OverviewTab contract={contract} onChange={handleContractChange} />
      case 'schema':
        return (
          <SchemaTab
            contract={contract}
            onChange={handleContractChange}
            inferredSchema={inferredSchema}
            onNavigateToField={handleNavigateToField}
          />
        )
      case 'quality':
        return <QualityTab contract={contract} onChange={handleContractChange} />
      case 'compliance':
        return <ComplianceTab contract={contract} onChange={handleContractChange} />
      case 'lifecycle':
        return <LifecycleTab contract={contract} onChange={handleContractChange} />
      case 'marketplace':
        return <MarketplaceTab contract={contract} onChange={handleContractChange} />
      case 'raw':
        return (
          <RawEditorTab
            contract={contract}
            onChange={handleContractChange}
            errors={errors.map((e) => ({
              line: e.field ? undefined : 1,
              message: e.message,
            }))}
          />
        )
      default:
        return null
    }
  }

  // Show schema comparison for contract-first flow
  const showSchemaComparison =
    onboardingFlow === 'contract-first' && inferredSchema && inferredSchema.length > 0

  // If preview mode, show preview component
  if (showPreview) {
    return (
      <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        <Box
          sx={{
            position: 'sticky',
            top: 0,
            zIndex: 100,
            backgroundColor: 'white',
            borderBottom: '1px solid',
            borderColor: 'divider',
            padding: 2,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            Contract Preview
          </Typography>
          <Button variant="outlined" onClick={handleClosePreview}>
            Close Preview
          </Button>
        </Box>
        <Box sx={{ flex: 1, overflow: 'auto' }}>
          <ContractPreview contract={contract} />
        </Box>
      </Box>
    )
  }

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <EditorHeader
        contractName={contract.info.name}
        contractDescription={contract.info.description}
        contractVersion={contract.info.version}
        normalizationStatus={normalizationStatus}
        validationStatus={validationStatus}
        isDirty={isDirty}
        isSaving={isSaving}
        isValidating={isValidating}
        canUndo={canUndo}
        canRedo={canRedo}
        onSave={handleSave}
        onValidate={handleValidate}
        onCancel={handleCancel}
        onUndo={handleUndo}
        onRedo={handleRedo}
        onPreview={handlePreview}
      />

      {/* Schema Comparison (if contract-first flow) */}
      {showSchemaComparison && (
        <Box sx={{ borderBottom: '1px solid', borderColor: 'divider' }}>
          <SchemaComparison
            inferredSchema={inferredSchema}
            contractSchema={contract.schema?.fields || []}
            onAcceptField={(field) => {
              handleContractChange({
                ...contract,
                schema: {
                  ...contract.schema,
                  fields: [...(contract.schema?.fields || []), field],
                },
              })
            }}
            onRejectField={(fieldName) => {
              // Field already rejected, no action needed
            }}
            onMergeSchemas={(mergedSchema) => {
              handleContractChange({
                ...contract,
                schema: {
                  ...contract.schema,
                  fields: mergedSchema,
                },
              })
            }}
          />
        </Box>
      )}

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={activeTab} onChange={(_, newValue) => setActiveTab(newValue)}>
          {TAB_CONFIG.map((tab) => (
            <Tab
              key={tab.id}
              value={tab.id}
              label={tab.label}
              icon={tab.icon}
              iconPosition="start"
            />
          ))}
        </Tabs>
      </Box>

      {/* Tab Content */}
      <Box sx={{ flex: 1, overflow: 'auto' }}>
        {renderTabContent()}
      </Box>

      {/* Validation Panel */}
      <ValidationPanel
        validationStatus={validationStatus}
        errors={errors}
        warnings={warnings}
        onNavigateToField={handleNavigateToField}
      />

      {/* Unsaved Changes Dialog */}
      <Dialog open={showUnsavedDialog} onClose={() => setShowUnsavedDialog(false)}>
        <DialogTitle>Unsaved Changes</DialogTitle>
        <DialogContent>
          <Typography>
            You have unsaved changes. Are you sure you want to leave without saving?
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowUnsavedDialog(false)}>Cancel</Button>
          <Button onClick={handleConfirmCancel} color="error">
            Leave Without Saving
          </Button>
          <Button
            variant="contained"
            onClick={async () => {
              try {
                await handleSave()
                setShowUnsavedDialog(false)
                onCancel()
              } catch (error) {
                console.error('Save failed:', error)
              }
            }}
          >
            Save and Leave
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

ContractEditor.displayName = 'ContractEditor'

