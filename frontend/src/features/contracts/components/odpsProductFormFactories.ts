/**
 * Factory helpers for ODPSProductForm. Lives in its own module so
 * ``react-refresh/only-export-components`` keeps the component file
 * (``./ODPSProductForm``) component-only and Fast Refresh boundaries
 * stay clean.
 */
import { BITOL_V1_SCHEMA_URL } from '../utils/odpsDocumentBuilder';
import type { ODPSFormData } from '../../../shared/types/odps';

export function makeEmptyODPSFormData(): ODPSFormData {
  return {
    schema: BITOL_V1_SCHEMA_URL,
    apiVersion: 'v1.0.0',
    kind: 'DataProduct',
    language: 'en',
    productID: '',
    productName: '',
    productVersion: '1.0.0',
    productStatus: 'draft',
    productDescription: '',
    productDomain: '',
    productTenant: '',
    productVisibility: 'internal',
    productCategory: undefined,
    productType: undefined,
    team: [],
    outputPorts: [],
    inputPorts: [],
    inputSchemas: [],
    slaProperties: [],
    qualityRules: [],
    tags: [],
    categories: [],
    price: undefined,
    currency: undefined,
    licenseType: undefined,
    marketplaceListed: false,
    marketplaceDescription: undefined,
    linkedAssetId: null,
    linkedContractId: null,
  };
}
