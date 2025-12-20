/**
 * Contract Upload Step
 *
 * Step for contract-first and contract-only flows
 * Allows creating or uploading a contract
 */

import React, { useState } from 'react'
import { Box, Typography, Tabs, Tab, Paper, Button } from '@mui/material'
import { Add as AddIcon, Upload as UploadIcon } from '@mui/icons-material'
import { useCreateContract } from '@/hooks/useCreateContract'
import { TextInput } from '@/components/forms/TextInput'
import { Textarea } from '@/components/forms/Textarea'
import { FileUpload } from '@/components/forms/FileUpload'
import type { AssetFormData } from '../AssetFormPage'

export interface ContractUploadStepProps {
  formData: AssetFormData
  onUpdate: (updates: Partial<AssetFormData>) => void
  onCreateAsset: () => Promise<string>
  isContractOnly?: boolean
}

/**
 * Contract Upload Step Component
 */
export const ContractUploadStep: React.FC<ContractUploadStepProps> = ({
  formData,
  onUpdate,
  onCreateAsset,
  isContractOnly = false,
}) => {
  const [tab, setTab] = useState<'create' | 'upload'>('create')
  const [contractName, setContractName] = useState('')
  const [contractDescription, setContractDescription] = useState('')
  const [contractJson, setContractJson] = useState('')
  const [uploadError, setUploadError] = useState<string | null>(null)

  const createContract = useCreateContract()

  // Handle contract creation
  const handleCreateContract = async () => {
    try {
      if (!contractName.trim()) {
        setUploadError('Contract name is required')
        return
      }

      // Parse JSON if provided
      let contractData = null
      if (contractJson.trim()) {
        try {
          contractData = JSON.parse(contractJson)
        } catch (e) {
          setUploadError('Invalid JSON format')
          return
        }
      }

      // Create asset first if needed
      let assetId = formData.workflowInstanceId
      if (!assetId) {
        assetId = await onCreateAsset()
        onUpdate({ workflowInstanceId: assetId })
      }

      // Create contract
      const contract = await createContract.mutateAsync({
        original_raw: contractData || {},
        original_format: 'JSON',
        asset_id: assetId,
      })

      onUpdate({ contractId: contract.id, contractData: contract })
      setUploadError(null)
    } catch (error) {
      console.error('Contract creation failed:', error)
      setUploadError(
        error instanceof Error ? error.message : 'Failed to create contract'
      )
    }
  }

  // Handle contract file upload
  const handleFileUpload = async (file: File) => {
    try {
      // Read file content
      const text = await file.text()
      let contractData

      try {
        contractData = JSON.parse(text)
      } catch (e) {
        setUploadError('Invalid JSON file')
        return
      }

      // Create asset first if needed
      let assetId = formData.workflowInstanceId
      if (!assetId) {
        assetId = await onCreateAsset()
        onUpdate({ workflowInstanceId: assetId })
      }

      // Create contract from file
      const contract = await createContract.mutateAsync({
        original_raw: contractData,
        original_format: 'JSON',
        asset_id: assetId,
      })

      onUpdate({ contractId: contract.id, contractData: contract })
      setUploadError(null)
    } catch (error) {
      console.error('Contract upload failed:', error)
      setUploadError(
        error instanceof Error ? error.message : 'Failed to upload contract'
      )
    }
  }

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        {isContractOnly ? 'Create Contract' : 'Create or Upload Contract'}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
        {isContractOnly
          ? 'Create a contract for your asset. You can add a dataset later if needed.'
          : 'Create a new contract or upload an existing contract file.'}
      </Typography>

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 3 }}>
        <Tab label="Create New" value="create" />
        <Tab label="Upload File" value="upload" />
      </Tabs>

      {tab === 'create' && (
        <Paper sx={{ p: 3 }}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            <TextInput
              label="Contract Name"
              value={contractName}
              onChange={setContractName}
              placeholder="e.g., Customer Data Contract"
              required
            />

            <Textarea
              label="Description"
              value={contractDescription}
              onChange={setContractDescription}
              rows={3}
              placeholder="Describe the contract..."
            />

            <Textarea
              label="Contract JSON (Optional)"
              value={contractJson}
              onChange={setContractJson}
              rows={10}
              placeholder='{"hub_contract_version": "1.0.0", ...}'
              helperText="Optional: Provide contract JSON. If empty, a basic contract will be created."
            />

            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={handleCreateContract}
              disabled={createContract.isPending || !contractName.trim()}
            >
              {createContract.isPending ? 'Creating...' : 'Create Contract'}
            </Button>
          </Box>
        </Paper>
      )}

      {tab === 'upload' && (
        <Paper sx={{ p: 3 }}>
          <FileUpload
            accept=".json,.yaml,.yml"
            maxSize={10 * 1024 * 1024} // 10MB
            onUpload={handleFileUpload}
            error={uploadError}
          />
        </Paper>
      )}

      {uploadError && (
        <Paper sx={{ p: 2, mt: 2, backgroundColor: 'error.50' }}>
          <Typography variant="body2" color="error">
            {uploadError}
          </Typography>
        </Paper>
      )}

      {formData.contractId && (
        <Paper sx={{ p: 2, mt: 2, backgroundColor: 'success.50' }}>
          <Typography variant="body2" color="success.main">
            Contract created successfully! Contract ID: {formData.contractId}
          </Typography>
        </Paper>
      )}
    </Box>
  )
}

