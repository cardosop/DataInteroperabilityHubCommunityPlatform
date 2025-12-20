/**
 * useComplianceReport Hook
 *
 * Query hook for generating compliance reports by aggregating compliance scan data.
 * Provides comprehensive compliance reporting functionality with filtering and date ranges.
 *
 * @example
 * ```tsx
 * function ComplianceReport() {
 *   const { data, isLoading, error } = useComplianceReport({
 *     start_date: '2024-01-01',
 *     end_date: '2024-12-31',
 *     jurisdiction: 'GDPR'
 *   })
 *
 *   if (isLoading) return <Loading />
 *   if (error) return <Error message={error.message} />
 *
 *   return (
 *     <div>
 *       <h2>Pass Rate: {(data?.overview.pass_rate * 100).toFixed(1)}%</h2>
 *       <ViolationsList violations={data?.violation_breakdown_by_category} />
 *     </div>
 *   )
 * }
 * ```
 */

import { useQuery, UseQueryOptions } from '@tanstack/react-query'
import {
  generateComplianceReport,
  type ComplianceReportData,
  type ComplianceReportParams,
} from '@/lib/api/compliance'
import { queryKeys } from '@/lib/api/react-query'

/**
 * useComplianceReport Hook
 *
 * Query hook for generating compliance reports.
 *
 * @param params - Report parameters (date range, filters)
 * @param options - Additional React Query options
 * @returns Compliance report query result
 */
export function useComplianceReport(
  params?: ComplianceReportParams,
  options?: Omit<UseQueryOptions<ComplianceReportData, Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery<ComplianceReportData, Error>({
    queryKey: queryKeys.compliance.report(params),
    queryFn: async () => {
      return await generateComplianceReport(params)
    },
    enabled: options?.enabled !== false,
    staleTime: options?.staleTime ?? 10 * 60 * 1000, // 10 minutes default (reports are expensive)
    ...options,
  })
}

