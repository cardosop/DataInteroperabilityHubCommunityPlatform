/**
 * Marketplace Utility Functions
 *
 * Helper functions for marketplace operations
 */

import type { Contract } from '@/lib/api/contracts'
import type { HubContract } from '@/components/contracts/types'

/**
 * Convert Contract to HubContract for preview
 */
export function contractToHubContract(contract: Contract): HubContract {
  const hubContractJson = contract.hub_contract_json || {}

  return {
    hub_contract_version: parseInt(hubContractJson.hub_contract_version || '1', 10),
    id: hubContractJson.id || contract.id,
    info: {
      name: hubContractJson.info?.name || 'Unnamed Contract',
      description: hubContractJson.info?.description,
      version: hubContractJson.info?.version,
      owners: contract.owners || hubContractJson.info?.owners,
      tags: contract.tags || hubContractJson.info?.tags,
      domain: hubContractJson.info?.domain,
      status: hubContractJson.info?.status,
      dataProduct: hubContractJson.info?.dataProduct,
      links: hubContractJson.info?.links,
      authoritativeDefinitions: hubContractJson.info?.authoritativeDefinitions,
    },
    schema: {
      fields: contract.schema_fields || hubContractJson.schema?.fields || [],
      primary_key: hubContractJson.schema?.primary_key,
      unique_constraints: hubContractJson.schema?.unique_constraints,
      indexes: hubContractJson.schema?.indexes,
    },
    quality: contract.quality_rules
      ? {
          rules: contract.quality_rules,
          default_profile_key: hubContractJson.quality?.default_profile_key,
        }
      : hubContractJson.quality,
    privacy_compliance: contract.compliance_policy || hubContractJson.privacy_compliance,
    lifecycle: contract.lifecycle_policy || hubContractJson.lifecycle,
    marketplace: contract.marketplace_policy || hubContractJson.marketplace,
    extensions: hubContractJson.extensions,
  }
}

