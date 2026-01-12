/**
 * Compliance operations for DataHub SDK.
 *
 * Provides high-level methods for managing compliance runs with support for
 * asset, dataset, and file-based compliance checks.
 */

import { DataHubClient } from './client';

export type ScanMode = 'internal' | 'external';
export type ComplianceRunStatus = 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED';
export type RiskLevel = 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface CreateComplianceRunParams {
    /**
     * Asset ID to run compliance check on (optional)
     */
    assetId?: string;

    /**
     * Dataset ID to run compliance check on (optional)
     */
    datasetId?: string;

    /**
     * File ID for external/scan-only compliance check (optional)
     */
    fileId?: string;

    /**
     * Scan mode: 'internal' for stored data, 'external' for scan-only
     * Default: 'internal'
     */
    scanMode?: ScanMode;

    /**
     * List of regulations to check (e.g., ['GDPR', 'HIPAA'])
     * If not provided, all regulations are checked
     */
    applicableRegulations?: string[];
}

export interface ListComplianceRunsParams {
    /**
     * Filter by asset ID
     */
    assetId?: string;

    /**
     * Filter by status
     */
    status?: ComplianceRunStatus;

    /**
     * Limit number of results (default: 20)
     */
    limit?: number;

    /**
     * Offset for pagination (default: 0)
     */
    offset?: number;
}

export interface ComplianceRun {
    id: string;
    tenant?: string;
    asset?: string;
    dataset?: string;
    file?: string;
    job?: string;
    regulations?: string[];
    status: ComplianceRunStatus;
    overall_status?: string;
    risk_level?: RiskLevel;
    allowed_to_store?: boolean;
    detected_categories_json?: Record<string, number>;
    column_findings_json?: any;
    regulation_mapping_json?: Record<string, any>;
    started_at?: string;
    completed_at?: string;
    created_at?: string;
    updated_at?: string;
}

export interface ComplianceRunResults {
    compliance_run_id: string;
    overall_status: string;
    risk_level: RiskLevel;
    allowed_to_store: boolean;
    compliance_score?: number;
    score_breakdown?: Record<string, any>;
    detected_categories?: Record<string, number>;
    regulation_mapping?: Record<string, any>;
    column_findings?: any[];
    recommendations?: string[];
}

/**
 * Compliance API.
 */
export class ComplianceAPI {
    private client: DataHubClient;

    constructor(client: DataHubClient) {
        this.client = client;
    }

    /**
     * Create a new compliance run.
     *
     * At least one of assetId, datasetId, or fileId must be provided.
     *
     * @param params Compliance run creation parameters
     * @returns Created compliance run
     */
    async create(params: CreateComplianceRunParams): Promise<ComplianceRun> {
        // Validate that at least one resource ID is provided
        if (!params.assetId && !params.datasetId && !params.fileId) {
            throw new Error('At least one of assetId, datasetId, or fileId must be provided');
        }

        const data: any = {
            scan_mode: params.scanMode || 'internal',
        };

        if (params.assetId) {
            data.asset_id = params.assetId;
        }
        if (params.datasetId) {
            data.dataset_id = params.datasetId;
        }
        if (params.fileId) {
            data.file_id = params.fileId;
        }
        if (params.applicableRegulations && params.applicableRegulations.length > 0) {
            data.applicable_regulations = params.applicableRegulations;
        }

        return this.client.post('compliance/runs/', data);
    }

    /**
     * List compliance runs with optional filtering.
     *
     * @param params List parameters with filters
     * @returns Paginated list of compliance runs
     */
    async list(params: ListComplianceRunsParams = {}): Promise<{ results: ComplianceRun[]; count?: number; next?: string; previous?: string }> {
        const queryParams: any = {
            limit: params.limit || 20,
            offset: params.offset || 0,
        };

        if (params.assetId) {
            queryParams.asset_id = params.assetId;
        }
        if (params.status) {
            queryParams.status = params.status;
        }

        return this.client.get('compliance/runs/', { params: queryParams });
    }

    /**
     * Get compliance run by ID.
     *
     * @param complianceRunId Compliance run ID
     * @returns Compliance run details
     */
    async get(complianceRunId: string): Promise<ComplianceRun> {
        return this.client.get(`compliance/runs/${complianceRunId}/`);
    }

    /**
     * Get compliance run results.
     *
     * Returns detailed compliance results including risk assessment,
     * detected categories, and regulation mapping.
     *
     * @param complianceRunId Compliance run ID
     * @returns Compliance run results
     */
    async getResults(complianceRunId: string): Promise<ComplianceRunResults> {
        return this.client.get(`compliance/runs/${complianceRunId}/results/`);
    }

    /**
     * Helper method to check if compliance run is completed.
     *
     * @param complianceRun Compliance run object
     * @returns True if run is completed (SUCCEEDED or FAILED)
     */
    isCompleted(complianceRun: ComplianceRun): boolean {
        return complianceRun.status === 'SUCCEEDED' || complianceRun.status === 'FAILED';
    }

    /**
     * Helper method to check if compliance run passed.
     *
     * @param complianceRun Compliance run object
     * @returns True if run succeeded and overall status is PASS
     */
    isPassed(complianceRun: ComplianceRun): boolean {
        return complianceRun.status === 'SUCCEEDED' && complianceRun.overall_status === 'PASS';
    }

    /**
     * Helper method to get risk level as numeric value for comparison.
     *
     * @param riskLevel Risk level string
     * @returns Numeric risk level (0-4, where 0 is NONE and 4 is CRITICAL)
     */
    getRiskLevelValue(riskLevel?: RiskLevel): number {
        const levels: Record<RiskLevel, number> = {
            'NONE': 0,
            'LOW': 1,
            'MEDIUM': 2,
            'HIGH': 3,
            'CRITICAL': 4,
        };
        return riskLevel ? levels[riskLevel] : 0;
    }
}

