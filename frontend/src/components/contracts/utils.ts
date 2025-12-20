/**
 * Contract Editor Utility Functions
 *
 * Helper functions for contract editor operations
 */

import type { HubContract, SchemaField, SchemaComparison } from './types'
import { jsYaml } from '@/lib/utils/yaml'

/**
 * Convert HubContract to YAML string
 */
export function contractToYaml(contract: HubContract): string {
  try {
    return jsYaml.dump(contract, {
      indent: 2,
      lineWidth: -1,
      quotingType: '"',
      forceQuotes: false,
    })
  } catch (error) {
    console.error('Error converting contract to YAML:', error)
    throw new Error('Failed to convert contract to YAML')
  }
}

/**
 * Convert HubContract to JSON string
 */
export function contractToJson(contract: HubContract): string {
  try {
    return JSON.stringify(contract, null, 2)
  } catch (error) {
    console.error('Error converting contract to JSON:', error)
    throw new Error('Failed to convert contract to JSON')
  }
}

/**
 * Parse YAML string to HubContract
 */
export function yamlToContract(yamlString: string): HubContract {
  try {
    const parsed = jsYaml.load(yamlString) as HubContract
    if (!parsed || typeof parsed !== 'object') {
      throw new Error('Invalid YAML structure')
    }
    return parsed
  } catch (error) {
    console.error('Error parsing YAML to contract:', error)
    throw new Error(`Failed to parse YAML: ${error instanceof Error ? error.message : 'Unknown error'}`)
  }
}

/**
 * Parse JSON string to HubContract
 */
export function jsonToContract(jsonString: string): HubContract {
  try {
    const parsed = JSON.parse(jsonString) as HubContract
    if (!parsed || typeof parsed !== 'object') {
      throw new Error('Invalid JSON structure')
    }
    return parsed
  } catch (error) {
    console.error('Error parsing JSON to contract:', error)
    throw new Error(`Failed to parse JSON: ${error instanceof Error ? error.message : 'Unknown error'}`)
  }
}

/**
 * Create default empty HubContract
 */
export function createDefaultContract(id?: string): HubContract {
  return {
    hub_contract_version: 1,
    id: id || `contract-${Date.now()}`,
    info: {
      name: '',
    },
    schema: {
      fields: [],
    },
  }
}

/**
 * Compare two schema fields
 */
export function compareSchemaFields(
  inferred: SchemaField[],
  contract: SchemaField[]
): SchemaComparison {
  const inferredMap = new Map(inferred.map((f) => [f.name, f]))
  const contractMap = new Map(contract.map((f) => [f.name, f]))

  const added: SchemaField[] = []
  const removed: SchemaField[] = []
  const modified: Array<{
    field: string
    inferred: SchemaField
    contract: SchemaField
    differences: string[]
  }> = []

  // Find added fields (in inferred but not in contract)
  for (const field of inferred) {
    if (!contractMap.has(field.name)) {
      added.push(field)
    }
  }

  // Find removed fields (in contract but not in inferred)
  for (const field of contract) {
    if (!inferredMap.has(field.name)) {
      removed.push(field)
    }
  }

  // Find modified fields
  for (const field of inferred) {
    const contractField = contractMap.get(field.name)
    if (contractField) {
      const differences: string[] = []
      if (field.data_type !== contractField.data_type) {
        differences.push(`data_type: ${contractField.data_type} → ${field.data_type}`)
      }
      if (field.nullable !== contractField.nullable) {
        differences.push(`nullable: ${contractField.nullable} → ${field.nullable}`)
      }
      if (field.description !== contractField.description) {
        differences.push('description changed')
      }
      if (JSON.stringify(field.enum) !== JSON.stringify(contractField.enum)) {
        differences.push('enum changed')
      }
      if (field.min_length !== contractField.min_length) {
        differences.push(`min_length: ${contractField.min_length} → ${field.min_length}`)
      }
      if (field.max_length !== contractField.max_length) {
        differences.push(`max_length: ${contractField.max_length} → ${field.max_length}`)
      }
      if (field.minimum !== contractField.minimum) {
        differences.push(`minimum: ${contractField.minimum} → ${field.minimum}`)
      }
      if (field.maximum !== contractField.maximum) {
        differences.push(`maximum: ${contractField.maximum} → ${field.maximum}`)
      }

      if (differences.length > 0) {
        modified.push({
          field: field.name,
          inferred: field,
          contract: contractField,
          differences,
        })
      }
    }
  }

  return {
    inferredSchema: inferred,
    contractSchema: contract,
    differences: {
      added,
      removed,
      modified,
    },
  }
}

/**
 * Validate contract structure
 */
export function validateContractStructure(contract: HubContract): {
  isValid: boolean
  errors: string[]
} {
  const errors: string[] = []

  if (!contract.hub_contract_version) {
    errors.push('hub_contract_version is required')
  }

  if (!contract.id) {
    errors.push('id is required')
  }

  if (!contract.info?.name) {
    errors.push('info.name is required')
  }

  if (!contract.schema?.fields || contract.schema.fields.length === 0) {
    errors.push('schema.fields must contain at least one field')
  }

  // Validate schema fields
  if (contract.schema?.fields) {
    for (const field of contract.schema.fields) {
      if (!field.name) {
        errors.push('Schema field name is required')
      }
      if (!field.data_type) {
        errors.push(`Schema field ${field.name || 'unknown'}: data_type is required`)
      }
    }
  }

  return {
    isValid: errors.length === 0,
    errors,
  }
}

