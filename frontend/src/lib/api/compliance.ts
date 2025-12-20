/**
 * Compliance API Service
 *
 * API functions for compliance scan management operations:
 * - List compliance scans with filtering, sorting, and pagination
 * - Get single compliance scan by ID
 * - Create/run compliance scan
 * - Get compliance scan results
 */

import type { ExtendedFetchRequestInit } from 'axios'
import { apiClient } from './client'
import { PaginatedResponse } from './responses'

/**
 * Compliance run status enum
 */
export type ComplianceRunStatus = 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED'

/**
 * Risk level enum
 */
export type RiskLevel = 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'

/**
 * Overall compliance status enum
 */
export type OverallComplianceStatus = 'PASS' | 'WARN' | 'FAIL'

/**
 * Scan mode enum
 */
export type ScanMode = 'internal' | 'external'

/**
 * Compliance regulation enum
 */
export type ComplianceRegulation = 'GDPR' | 'LGPD' | 'CCPA' | 'HIPAA' | 'SOX'

/**
 * Compliance run model
 */
export interface ComplianceScan {
  id: string
  tenant: string
  asset?: string | null
  dataset?: string | null
  file?: string | null
  job: string
  regulations?: ComplianceRegulation[] | null
  status: ComplianceRunStatus
  overall_status?: OverallComplianceStatus | null
  risk_level?: RiskLevel | null
  allowed_to_store?: boolean | null
  detected_categories_json?: Record<string, any> | null
  column_findings_json?: Record<string, any> | null
  regulation_mapping_json?: Record<string, any> | null
  started_at?: string | null
  completed_at?: string | null
  created_at: string
  updated_at: string
}

/**
 * List compliance scans query parameters
 */
export interface ListComplianceScansParams {
  /**
   * Page number (1-indexed)
   */
  page?: number
  /**
   * Number of items per page (default: 50, max: 100)
   */
  page_size?: number
  /**
   * Sort fields (comma-separated, prefix with `-` for descending)
   * Example: "-created_at"
   */
  ordering?: string
  /**
   * Filter by asset ID
   */
  asset_id?: string
  /**
   * Filter by dataset ID
   */
  dataset_id?: string
  /**
   * Filter by file ID
   */
  file_id?: string
  /**
   * Filter by status (PENDING, RUNNING, SUCCEEDED, FAILED)
   */
  status?: ComplianceRunStatus
  /**
   * Filter by regulation (GDPR, LGPD, CCPA, HIPAA, SOX)
   */
  regulation?: ComplianceRegulation
}

/**
 * Create/run compliance scan request payload
 */
export interface RunComplianceScanRequest {
  /**
   * Asset ID (optional, at least one of asset_id, dataset_id, or file_id required)
   */
  asset_id?: string | null
  /**
   * Dataset ID (optional, at least one of asset_id, dataset_id, or file_id required)
   */
  dataset_id?: string | null
  /**
   * File ID (optional, scan-only, at least one of asset_id, dataset_id, or file_id required)
   */
  file_id?: string | null
  /**
   * Scan mode: 'internal' for stored data, 'external' for scan-only
   * @default 'internal'
   */
  scan_mode?: ScanMode
  /**
   * List of regulations to check (e.g., ['GDPR', 'HIPAA'])
   * If not provided, all regulations are checked based on tenant configuration
   */
  applicable_regulations?: ComplianceRegulation[]
}

/**
 * Compliance scan results response
 */
export interface ComplianceScanResults {
  compliance_run_id: string
  overall_status: OverallComplianceStatus
  risk_level: RiskLevel
  allowed_to_store: boolean
  compliance_score?: number | null
  score_breakdown?: Record<string, any>
  violations?: Array<{
    id?: string
    type?: string
    severity?: string
    description?: string
    remediation?: string
    [key: string]: any
  }>
  violation_details?: Array<{
    [key: string]: any
  }>
  remediation_suggestions?: Array<{
    [key: string]: any
  }>
  risk_assessment?: Record<string, any>
  violation_timeline?: Array<{
    [key: string]: any
  }>
  regulations?: ComplianceRegulation[]
  detected_categories?: Record<string, any>
  column_findings?: Array<{
    [key: string]: any
  }>
  started_at?: string | null
  completed_at?: string | null
}

/**
 * List compliance scans response
 */
export type ListComplianceScansResponse = PaginatedResponse<ComplianceScan>

/**
 * List compliance scans with filtering, sorting, and pagination
 *
 * @param params - Query parameters for filtering and pagination
 * @param requestConfig - Optional Axios request config
 * @returns Paginated list of compliance scans
 */
export async function listComplianceScans(
  params?: ListComplianceScansParams,
  requestConfig?: ExtendedFetchRequestInit
): Promise<ListComplianceScansResponse> {
  const queryParams: Record<string, any> = {
    page: params?.page,
    page_size: params?.page_size,
    ordering: params?.ordering,
    asset_id: params?.asset_id,
    dataset_id: params?.dataset_id,
    file_id: params?.file_id,
    status: params?.status,
    regulation: params?.regulation,
  }

  const response = await apiClient.get<ListComplianceScansResponse>(
    '/api/v1/compliance/compliance-runs/',
    {
      ...requestConfig,
      params: queryParams,
    }
  )
  return response.data
}

/**
 * Get compliance scan by ID
 *
 * @param id - Compliance scan UUID
 * @param config - Optional Axios request config
 * @returns Compliance scan details
 */
export async function getComplianceScan(
  id: string,
  config?: ExtendedFetchRequestInit
): Promise<ComplianceScan> {
  const response = await apiClient.get<ComplianceScan>(
    `/api/v1/compliance/compliance-runs/${id}/`,
    config
  )
  return response.data
}

/**
 * Run/create a compliance scan
 *
 * @param data - Compliance scan creation data
 * @param requestConfig - Optional Axios request config
 * @returns Created compliance scan
 */
export async function runComplianceScan(
  data: RunComplianceScanRequest,
  requestConfig?: ExtendedFetchRequestInit
): Promise<ComplianceScan> {
  const response = await apiClient.post<ComplianceScan>(
    '/api/v1/compliance/compliance-runs/',
    data,
    requestConfig
  )
  return response.data
}

/**
 * Get compliance scan results
 *
 * @param id - Compliance scan UUID
 * @param requestConfig - Optional Axios request config
 * @returns Compliance scan results with detailed violation information
 */
export async function getComplianceScanResults(
  id: string,
  requestConfig?: ExtendedFetchRequestInit
): Promise<ComplianceScanResults> {
  const response = await apiClient.get<ComplianceScanResults>(
    `/api/v1/compliance/compliance-runs/${id}/results/`,
    requestConfig
  )
  return response.data
}

/**
 * Compliance report query parameters
 */
export interface ComplianceReportParams {
  /**
   * Start date for report period (ISO format)
   */
  start_date?: string
  /**
   * End date for report period (ISO format)
   */
  end_date?: string
  /**
   * Filter by asset ID
   */
  asset_id?: string
  /**
   * Filter by jurisdiction/regulation (GDPR, LGPD, CCPA, HIPAA, SOX)
   */
  jurisdiction?: ComplianceRegulation
}

/**
 * Compliance report overview
 */
export interface ComplianceReportOverview {
  /**
   * Report period
   */
  period: {
    start_date: string
    end_date: string
  }
  /**
   * Total compliance scans in period
   */
  total_scans: number
  /**
   * Pass rate (0.0 to 1.0)
   */
  pass_rate: number
  /**
   * Total violation count
   */
  violation_count: number
  /**
   * Average risk score (0.0 to 1.0)
   */
  risk_score: number
}

/**
 * Violation breakdown by category
 */
export interface ViolationCategoryBreakdown {
  category: string
  count: number
  severity_breakdown: {
    CRITICAL: number
    HIGH: number
    MEDIUM: number
    LOW: number
  }
}

/**
 * Violation breakdown by jurisdiction
 */
export interface ViolationJurisdictionBreakdown {
  jurisdiction: ComplianceRegulation
  total_violations: number
  pass_rate: number
  risk_score: number
}

/**
 * Violation timeline entry
 */
export interface ViolationTimelineEntry {
  date: string
  violations: number
  scans: number
  pass_rate: number
}

/**
 * Asset compliance status
 */
export interface AssetComplianceStatus {
  asset_id: string
  asset_name?: string
  last_scan_date?: string
  overall_status?: OverallComplianceStatus
  risk_level?: RiskLevel
  violation_count: number
  compliance_score?: number
}

/**
 * Compliance report data
 */
export interface ComplianceReportData {
  overview: ComplianceReportOverview
  violation_breakdown_by_category: ViolationCategoryBreakdown[]
  violation_breakdown_by_jurisdiction: ViolationJurisdictionBreakdown[]
  violation_timeline: ViolationTimelineEntry[]
  asset_compliance_status: AssetComplianceStatus[]
}

/**
 * Generate compliance report by aggregating compliance scan data
 *
 * This function aggregates data from compliance scans to create a comprehensive report.
 * It fetches all relevant scans and their results, then aggregates the data.
 *
 * @param params - Report parameters (date range, filters)
 * @param requestConfig - Optional Axios request config
 * @returns Aggregated compliance report data
 */
export async function generateComplianceReport(
  params?: ComplianceReportParams,
  requestConfig?: ExtendedFetchRequestInit
): Promise<ComplianceReportData> {
  // Build query parameters for fetching compliance scans
  const scanParams: ListComplianceScansParams = {
    page_size: 1000, // Get all scans (we'll paginate if needed)
    ordering: '-completed_at',
    asset_id: params?.asset_id,
    regulation: params?.jurisdiction,
    status: 'SUCCEEDED', // Only include completed scans
  }

  // Fetch all compliance scans
  let allScans: ComplianceScan[] = []
  let page = 1
  let hasMore = true

  while (hasMore) {
    const response = await listComplianceScans(
      { ...scanParams, page },
      requestConfig
    )
    allScans = [...allScans, ...response.results]

    // Filter by date range if provided
    if (params?.start_date || params?.end_date) {
      allScans = allScans.filter((scan) => {
        if (!scan.completed_at) return false
        const completedDate = new Date(scan.completed_at)
        if (params.start_date && completedDate < new Date(params.start_date)) {
          return false
        }
        if (params.end_date && completedDate > new Date(params.end_date)) {
          return false
        }
        return true
      })
    }

    hasMore = response.next !== null
    page++
  }

  // Fetch results for all scans (in parallel, but limit concurrency)
  const scanResultsPromises = allScans.map((scan) =>
    getComplianceScanResults(scan.id, requestConfig).catch(() => null)
  )
  const scanResults = await Promise.all(scanResultsPromises)
  const validResults = scanResults.filter(
    (result): result is ComplianceScanResults => result !== null
  )

  // Aggregate overview metrics
  const totalScans = allScans.length
  const passedScans = allScans.filter(
    (scan) => scan.overall_status === 'PASS'
  ).length
  const passRate = totalScans > 0 ? passedScans / totalScans : 0

  // Aggregate violations
  const allViolations = validResults.flatMap((result) => result.violations || [])
  const violationCount = allViolations.length

  // Calculate average risk score
  const riskScores = validResults
    .map((result) => result.compliance_score)
    .filter((score): score is number => score !== null && score !== undefined)
  const riskScore =
    riskScores.length > 0
      ? riskScores.reduce((sum, score) => sum + score, 0) / riskScores.length
      : 0

  // Violation breakdown by category
  const categoryMap = new Map<string, { count: number; severity: Record<string, number> }>()
  allViolations.forEach((violation) => {
    const category = violation.type || 'UNKNOWN'
    const severity = violation.severity || 'LOW'
    if (!categoryMap.has(category)) {
      categoryMap.set(category, { count: 0, severity: { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 } })
    }
    const entry = categoryMap.get(category)!
    entry.count++
    entry.severity[severity] = (entry.severity[severity] || 0) + 1
  })

  const violationBreakdownByCategory: ViolationCategoryBreakdown[] = Array.from(
    categoryMap.entries()
  ).map(([category, data]) => ({
    category,
    count: data.count,
    severity_breakdown: {
      CRITICAL: data.severity.CRITICAL || 0,
      HIGH: data.severity.HIGH || 0,
      MEDIUM: data.severity.MEDIUM || 0,
      LOW: data.severity.LOW || 0,
    },
  }))

  // Violation breakdown by jurisdiction
  const jurisdictionMap = new Map<
    ComplianceRegulation,
    { violations: number; scans: number; passed: number; riskScores: number[] }
  >()
  allScans.forEach((scan) => {
    const regulations = scan.regulations || []
    regulations.forEach((regulation) => {
      if (!jurisdictionMap.has(regulation)) {
        jurisdictionMap.set(regulation, {
          violations: 0,
          scans: 0,
          passed: 0,
          riskScores: [],
        })
      }
      const entry = jurisdictionMap.get(regulation)!
      entry.scans++
      if (scan.overall_status === 'PASS') {
        entry.passed++
      }
    })
  })

  validResults.forEach((result) => {
    const regulations = result.regulations || []
    regulations.forEach((regulation) => {
      const entry = jurisdictionMap.get(regulation)
      if (entry) {
        entry.violations += (result.violations || []).length
        if (result.compliance_score !== null && result.compliance_score !== undefined) {
          entry.riskScores.push(result.compliance_score)
        }
      }
    })
  })

  const violationBreakdownByJurisdiction: ViolationJurisdictionBreakdown[] = Array.from(
    jurisdictionMap.entries()
  ).map(([jurisdiction, data]) => ({
    jurisdiction,
    total_violations: data.violations,
    pass_rate: data.scans > 0 ? data.passed / data.scans : 0,
    risk_score:
      data.riskScores.length > 0
        ? data.riskScores.reduce((sum, score) => sum + score, 0) / data.riskScores.length
        : 0,
  }))

  // Violation timeline (group by date)
  const timelineMap = new Map<string, { violations: number; scans: number; passed: number }>()
  allScans.forEach((scan) => {
    if (!scan.completed_at) return
    const date = new Date(scan.completed_at).toISOString().split('T')[0]
    if (!timelineMap.has(date)) {
      timelineMap.set(date, { violations: 0, scans: 0, passed: 0 })
    }
    const entry = timelineMap.get(date)!
    entry.scans++
    if (scan.overall_status === 'PASS') {
      entry.passed++
    }
  })

  validResults.forEach((result) => {
    const scan = allScans.find((s) => s.id === result.compliance_run_id)
    if (scan?.completed_at) {
      const date = new Date(scan.completed_at).toISOString().split('T')[0]
      const entry = timelineMap.get(date)
      if (entry) {
        entry.violations += (result.violations || []).length
      }
    }
  })

  const violationTimeline: ViolationTimelineEntry[] = Array.from(timelineMap.entries())
    .map(([date, data]) => ({
      date,
      violations: data.violations,
      scans: data.scans,
      pass_rate: data.scans > 0 ? data.passed / data.scans : 0,
    }))
    .sort((a, b) => a.date.localeCompare(b.date))

  // Asset compliance status
  const assetMap = new Map<
    string,
    {
      asset_id: string
      scans: ComplianceScan[]
      results: ComplianceScanResults[]
    }
  >()

  allScans.forEach((scan) => {
    if (scan.asset) {
      if (!assetMap.has(scan.asset)) {
        assetMap.set(scan.asset, {
          asset_id: scan.asset,
          scans: [],
          results: [],
        })
      }
      assetMap.get(scan.asset)!.scans.push(scan)
    }
  })

  validResults.forEach((result) => {
    const scan = allScans.find((s) => s.id === result.compliance_run_id)
    if (scan?.asset) {
      const entry = assetMap.get(scan.asset)
      if (entry) {
        entry.results.push(result)
      }
    }
  })

  const assetComplianceStatus: AssetComplianceStatus[] = Array.from(assetMap.values()).map(
    (entry) => {
      const latestScan = entry.scans.sort(
        (a, b) =>
          new Date(b.completed_at || b.created_at).getTime() -
          new Date(a.completed_at || a.created_at).getTime()
      )[0]

      const allViolations = entry.results.flatMap((result) => result.violations || [])
      const complianceScores = entry.results
        .map((result) => result.compliance_score)
        .filter((score): score is number => score !== null && score !== undefined)

      return {
        asset_id: entry.asset_id,
        last_scan_date: latestScan?.completed_at || latestScan?.created_at,
        overall_status: latestScan?.overall_status || undefined,
        risk_level: latestScan?.risk_level || undefined,
        violation_count: allViolations.length,
        compliance_score:
          complianceScores.length > 0
            ? complianceScores.reduce((sum, score) => sum + score, 0) / complianceScores.length
            : undefined,
      }
    }
  )

  // Determine report period
  const dates = allScans
    .map((scan) => scan.completed_at || scan.created_at)
    .filter((date): date is string => !!date)
    .sort()

  const startDate = params?.start_date || dates[0] || new Date().toISOString()
  const endDate = params?.end_date || dates[dates.length - 1] || new Date().toISOString()

  return {
    overview: {
      period: {
        start_date: startDate,
        end_date: endDate,
      },
      total_scans: totalScans,
      pass_rate: passRate,
      violation_count: violationCount,
      risk_score: riskScore,
    },
    violation_breakdown_by_category: violationBreakdownByCategory,
    violation_breakdown_by_jurisdiction: violationBreakdownByJurisdiction,
    violation_timeline: violationTimeline,
    asset_compliance_status: assetComplianceStatus,
  }
}

