/**
 * Contract management operations for DataHub SDK.
 *
 * Provides high-level methods for managing contracts with support for
 * all new objects (Contact, Server, Terms, Definition, Lineage, ServiceLevel, Models).
 */

import { DataHubClient } from './client';

export interface ListContractsParams {
    page?: number;
    pageSize?: number;
    ordering?: string;
    ownerEmail?: string;
    ownerName?: string;
    tag?: string;
    qualityProfile?: string;
    complianceRegime?: string;
    contactEmail?: string;
    contactName?: string;
    serverType?: string;
    serverUrl?: string;
    minAvailability?: number;
    maxLatencyMs?: number;
    modelName?: string;
    specType?: string;
    odpsVersion?: string;
    hasOdpsLink?: boolean;
}

export interface CreateContractParams {
    originalRaw: string;
    originalFormat?: string;
    assetId?: string;
}

export interface CreateODPSParams {
    originalRaw: string;
    extractOdcs?: boolean;
    linkOdcsId?: string;
    originalFormat?: string;
    odpsVersion?: string;
    resolveExternalRefs?: boolean;
    assetId?: string;
}

export interface ExportODPSParams {
    contractId: string;
    version?: string;
    format?: 'json' | 'yaml';
}

export interface DownloadODPSParams {
    contractId: string;
    version?: string;
    format?: 'json' | 'yaml';
}

export interface LinkODPSToODCSParams {
    odcsContractId: string;
    odpsContractId?: string;
    odpsRaw?: string;
    odpsFormat?: string;
    resolveExternalRefs?: boolean;
}

export interface UpdateContractParams {
    originalRaw?: string;
    originalFormat?: string;
    [key: string]: any;
}

/**
 * Contract management API.
 */
export class ContractsAPI {
    private client: DataHubClient;

    constructor(client: DataHubClient) {
        this.client = client;
    }

    /**
     * List contracts with filtering.
     */
    async list(params: ListContractsParams = {}): Promise<any> {
        const queryParams: any = {
            page: params.page || 1,
            page_size: params.pageSize || 50,
        };

        if (params.ordering) queryParams.ordering = params.ordering;
        if (params.ownerEmail) queryParams.owner_email = params.ownerEmail;
        if (params.ownerName) queryParams.owner_name = params.ownerName;
        if (params.tag) queryParams.tag = params.tag;
        if (params.qualityProfile) queryParams.quality_profile = params.qualityProfile;
        if (params.complianceRegime) queryParams.compliance_regime = params.complianceRegime;
        if (params.contactEmail) queryParams.contact_email = params.contactEmail;
        if (params.contactName) queryParams.contact_name = params.contactName;
        if (params.serverType) queryParams.server_type = params.serverType;
        if (params.serverUrl) queryParams.server_url = params.serverUrl;
        if (params.minAvailability !== undefined) queryParams.min_availability = params.minAvailability;
        if (params.maxLatencyMs !== undefined) queryParams.max_latency_ms = params.maxLatencyMs;
        if (params.modelName) queryParams.model_name = params.modelName;
        if (params.specType) queryParams.spec_type = params.specType;
        if (params.odpsVersion) queryParams.odps_version = params.odpsVersion;
        if (params.hasOdpsLink !== undefined) queryParams.has_odps_link = params.hasOdpsLink;

        return this.client.get('contracts/', { params: queryParams });
    }

    /**
     * Get contract by ID.
     */
    async get(contractId: string): Promise<any> {
        return this.client.get(`contracts/${contractId}/`);
    }

    /**
     * Create contract from ODCS format.
     */
    async create(params: CreateContractParams): Promise<any> {
        const data: any = {
            original_raw: params.originalRaw,
            original_format: params.originalFormat || 'JSON',
        };
        if (params.assetId) {
            data.asset_id = params.assetId;
        }
        return this.client.post('contracts/', data);
    }

    /**
     * Update contract (partial update supported).
     */
    async update(contractId: string, params: UpdateContractParams): Promise<any> {
        return this.client.patch(`contracts/${contractId}/`, params);
    }

    /**
     * Delete contract (soft delete: sets status to RETIRED).
     */
    async delete(contractId: string): Promise<void> {
        return this.client.delete(`contracts/${contractId}/`);
    }

    /**
     * Validate contract.
     */
    async validate(contractId: string): Promise<any> {
        return this.client.post(`contracts/${contractId}/validate/`);
    }

    /**
     * Lint contract.
     */
    async lint(contractId: string): Promise<any> {
        return this.client.post(`contracts/${contractId}/lint/`);
    }

    // Helper methods for accessing contract objects

    /**
     * Get contact objects from contract.
     */
    getContact(contract: any): any[] | null {
        const hubContract = contract?.hub_contract_json || {};
        return hubContract.contact || null;
    }

    /**
     * Get server objects from contract.
     */
    getServers(contract: any): any[] | null {
        const hubContract = contract?.hub_contract_json || {};
        return hubContract.servers || null;
    }

    /**
     * Get terms object from contract.
     */
    getTerms(contract: any): any | null {
        const hubContract = contract?.hub_contract_json || {};
        return hubContract.terms || null;
    }

    /**
     * Get definition objects from contract.
     */
    getDefinitions(contract: any): any[] | null {
        const hubContract = contract?.hub_contract_json || {};
        return hubContract.definitions || null;
    }

    /**
     * Get lineage object from contract.
     */
    getLineage(contract: any): any | null {
        const hubContract = contract?.hub_contract_json || {};
        return hubContract.lineage || null;
    }

    /**
     * Get service level objects from contract.
     */
    getServiceLevels(contract: any): any[] | null {
        const hubContract = contract?.hub_contract_json || {};
        return hubContract.servicelevels || null;
    }

    /**
     * Get models from contract.
     */
    getModels(contract: any): any[] | null {
        const hubContract = contract?.hub_contract_json || {};
        return hubContract.models || null;
    }

    // ODPS methods

    /**
     * Create ODPS (Open Data Product Standard) contract.
     */
    async createOdps(params: CreateODPSParams): Promise<any> {
        if (params.extractOdcs && params.linkOdcsId) {
            throw new Error('Cannot use both extractOdcs and linkOdcsId. Choose one flow.');
        }
        if (!params.extractOdcs && !params.linkOdcsId) {
            throw new Error('Must specify either extractOdcs=true or linkOdcsId');
        }

        const data: any = {
            original_raw: params.originalRaw,
            original_format: params.originalFormat || 'JSON',
            resolve_external_refs: params.resolveExternalRefs !== false,
        };

        if (params.odpsVersion) {
            data.odps_version = params.odpsVersion;
        }
        if (params.assetId) {
            data.asset_id = params.assetId;
        }

        if (params.extractOdcs) {
            // Product-First flow
            return this.client.post('contracts/products/', data);
        } else {
            // Link flow
            return this.client.post(`contracts/${params.linkOdcsId}/link-odps/`, data);
        }
    }

    /**
     * Export contract as ODPS format.
     */
    async exportOdps(params: ExportODPSParams): Promise<any> {
        const queryParams: any = {
            format: 'odps',
            output_format: params.format || 'json',
        };
        if (params.version) {
            queryParams.version = params.version;
        }
        return this.client.get(`contracts/${params.contractId}/export/`, { params: queryParams });
    }

    /**
     * Download contract as ODPS format file.
     */
    async downloadOdps(params: DownloadODPSParams): Promise<ArrayBuffer> {
        const queryParams: any = {
            format: 'odps',
            output_format: params.format || 'json',
        };
        if (params.version) {
            queryParams.version = params.version;
        }
        const response = await this.client.request({
            method: 'GET',
            url: `contracts/${params.contractId}/download/`,
            params: queryParams,
            responseType: 'arraybuffer',
        });
        return response.data;
    }

    /**
     * Link ODPS contract to ODCS contract.
     */
    async linkOdpsToOdcs(params: LinkODPSToODCSParams): Promise<any> {
        if (!params.odpsContractId && !params.odpsRaw) {
            throw new Error('Must provide either odpsContractId (to link existing) or odpsRaw (to create new)');
        }

        const data: any = {};
        if (params.odpsContractId) {
            data.odps_contract_id = params.odpsContractId;
        } else {
            data.original_raw = params.odpsRaw;
            data.original_format = params.odpsFormat?.toUpperCase() || 'JSON';
            data.resolve_external_refs = params.resolveExternalRefs !== false;
        }

        return this.client.post(`contracts/${params.odcsContractId}/link-odps/`, data);
    }

    /**
     * Unlink ODPS contract from ODCS contract.
     */
    async unlinkOdpsFromOdcs(odcsContractId: string): Promise<any> {
        return this.client.post(`contracts/${odcsContractId}/unlink-odps/`);
    }

    /**
     * Get all linked contracts for a given contract.
     */
    async getLinkedContracts(contractId: string): Promise<any> {
        return this.client.get(`contracts/${contractId}/links/`);
    }

    // ODPS helper methods

    /**
     * Check if contract is an ODPS contract.
     */
    isOdpsContract(contract: any): boolean {
        return contract?.original_spec_type === 'ODPS';
    }

    /**
     * Get ODPS version from contract.
     */
    getOdpsVersion(contract: any): string | null {
        if (!this.isOdpsContract(contract)) {
            return null;
        }
        return contract?.original_spec_version || null;
    }

    /**
     * Get pricing plans from ODPS contract.
     */
    getPricingPlans(contract: any): any[] | null {
        const hubContract = contract?.hub_contract_json || {};
        const marketplace = hubContract?.marketplace || {};
        const xOdps = marketplace?.x_odps || {};
        const pricingPlans = xOdps?.pricing_plans;
        return Array.isArray(pricingPlans) ? pricingPlans : null;
    }

    /**
     * Get access methods from ODPS contract.
     */
    getAccessMethods(contract: any): any | null {
        const hubContract = contract?.hub_contract_json || {};
        const marketplace = hubContract?.marketplace || {};
        const xOdps = marketplace?.x_odps || {};
        const accessMethods = xOdps?.access_methods;
        return typeof accessMethods === 'object' && accessMethods !== null ? accessMethods : null;
    }

    /**
     * Get payment gateways from ODPS contract.
     */
    getPaymentGateways(contract: any): any | null {
        const hubContract = contract?.hub_contract_json || {};
        const marketplace = hubContract?.marketplace || {};
        const xOdps = marketplace?.x_odps || {};
        const paymentGateways = xOdps?.payment_gateways;
        return typeof paymentGateways === 'object' && paymentGateways !== null ? paymentGateways : null;
    }

    /**
     * Get product strategy from ODPS contract.
     */
    getProductStrategy(contract: any): any | null {
        const hubContract = contract?.hub_contract_json || {};

        // Check extensions.x_odps.product_strategy first
        const extensions = hubContract?.extensions || {};
        const xOdpsExt = extensions?.x_odps || {};
        if (xOdpsExt?.product_strategy && typeof xOdpsExt.product_strategy === 'object') {
            return xOdpsExt.product_strategy;
        }

        // Fallback to info.x_odps.product_strategy
        const info = hubContract?.info || {};
        const xOdpsInfo = info?.x_odps || {};
        if (xOdpsInfo?.product_strategy && typeof xOdpsInfo.product_strategy === 'object') {
            return xOdpsInfo.product_strategy;
        }

        return null;
    }

    /**
     * Get product details from ODPS contract for a specific language.
     */
    getProductDetails(contract: any, lang: string = 'en'): any | null {
        // First, try to extract from original_raw
        const originalRaw = contract?.original_raw;
        if (originalRaw) {
            try {
                const odpsData = JSON.parse(originalRaw);
                const product = odpsData?.product || {};
                const details = product?.details || {};
                const langDetails = details[lang];
                if (langDetails && typeof langDetails === 'object') {
                    return langDetails;
                }
            } catch (e) {
                // If JSON parsing fails, try to reconstruct from hub_contract_json
            }
        }

        // Fallback: reconstruct from hub_contract_json
        const hubContract = contract?.hub_contract_json || {};
        const info = hubContract?.info || {};

        const productDetails: any = {};
        if (hubContract.id) {
            productDetails.productID = hubContract.id;
        }
        if (info.name) {
            productDetails.name = info.name;
        }
        if (info.description) {
            productDetails.description = info.description;
        }
        if (info.version) {
            productDetails.productVersion = info.version;
        }

        return (productDetails.productID || productDetails.name) ? productDetails : null;
    }
}

