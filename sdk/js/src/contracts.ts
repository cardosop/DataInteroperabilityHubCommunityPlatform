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
}

export interface CreateContractParams {
    originalRaw: string;
    originalFormat?: string;
    assetId?: string;
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
}

