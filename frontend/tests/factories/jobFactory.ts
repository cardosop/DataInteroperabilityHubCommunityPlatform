/**
 * Job Factory
 *
 * Factory for creating test Job objects.
 */

import type { Job, JobType, JobStatus } from '@/lib/api/jobs'
import { generateId, generateUUID, randomDate, randomElement, type FactoryOptions, type FactoryTrait } from './utils'

/**
 * Job factory implementation
 */
class JobFactory implements FactoryTrait<Job> {
  /**
   * Build a single Job
   */
  build(options: FactoryOptions<Job> = {}): Job {
    const { overrides = {}, uniqueIds = true } = options
    const id = uniqueIds ? generateUUID() : 'test-job-1'
    const now = new Date()
    const startedAt = new Date(now.getTime() - 60000) // 1 minute ago

    return {
      id,
      tenant: 'test-tenant',
      type: 'DQ_RUN' as JobType,
      status: 'COMPLETED' as JobStatus,
      resource_type: 'ASSET',
      resource_id: 'test-asset-1',
      created_by: 'test-user',
      started_at: startedAt.toISOString(),
      completed_at: now.toISOString(),
      error_message: null,
      result_json: { success: true, records_processed: 1000 },
      details_json: { progress: 100, current_step: 'Completed' },
      timeout_seconds: 300,
      created_at: randomDate(new Date(now.getTime() - 120000), new Date(now.getTime() - 60000)),
      updated_at: now.toISOString(),
      ...overrides,
    }
  }

  buildMany(count: number, options: FactoryOptions<Job> = {}): Job[] {
    const jobTypes: JobType[] = [
      'DQ_RUN',
      'COMPLIANCE_RUN',
      'CONTRACT_VALIDATION',
      'SEMANTIC_MAPPING',
    ]
    const jobStatuses: JobStatus[] = ['PENDING', 'RUNNING', 'COMPLETED', 'FAILED']

    return Array.from({ length: count }, (_, index) =>
      this.build({
        ...options,
        overrides: {
          ...options.overrides,
          type: jobTypes[index % jobTypes.length],
          status: jobStatuses[index % jobStatuses.length],
        },
      })
    )
  }

  buildSequence(builder: (index: number) => Partial<Job>): Job[] {
    const jobs: Job[] = []
    let index = 0
    let job = this.build({ overrides: builder(index) })

    while (job) {
      jobs.push(job)
      index++
      const overrides = builder(index)
      if (overrides === null || overrides === undefined) {
        break
      }
      job = this.build({ overrides })
    }

    return jobs
  }

  /**
   * Build a PENDING job
   */
  pending(options: FactoryOptions<Job> = {}): Job {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        status: 'PENDING' as JobStatus,
        started_at: null,
        completed_at: null,
      },
    })
  }

  /**
   * Build a RUNNING job
   */
  running(options: FactoryOptions<Job> = {}): Job {
    const now = new Date()
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        status: 'RUNNING' as JobStatus,
        started_at: new Date(now.getTime() - 30000).toISOString(),
        completed_at: null,
        details_json: { progress: 50, current_step: 'Processing' },
      },
    })
  }

  /**
   * Build a COMPLETED job
   */
  completed(options: FactoryOptions<Job> = {}): Job {
    const now = new Date()
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        status: 'COMPLETED' as JobStatus,
        started_at: new Date(now.getTime() - 60000).toISOString(),
        completed_at: now.toISOString(),
        result_json: { success: true },
        details_json: { progress: 100, current_step: 'Completed' },
      },
    })
  }

  /**
   * Build a FAILED job
   */
  failed(options: FactoryOptions<Job> = {}): Job {
    const now = new Date()
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        status: 'FAILED' as JobStatus,
        started_at: new Date(now.getTime() - 60000).toISOString(),
        completed_at: now.toISOString(),
        error_message: 'Job execution failed: Test error',
        result_json: { success: false, error: 'Test error' },
        details_json: { progress: 0, current_step: 'Failed' },
      },
    })
  }

  /**
   * Build a CANCELLED job
   */
  cancelled(options: FactoryOptions<Job> = {}): Job {
    const now = new Date()
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        status: 'CANCELLED' as JobStatus,
        started_at: new Date(now.getTime() - 60000).toISOString(),
        completed_at: now.toISOString(),
        error_message: 'Job was cancelled',
        details_json: { progress: 0, current_step: 'Cancelled' },
      },
    })
  }

  /**
   * Build a job of a specific type
   */
  ofType(type: JobType, options: FactoryOptions<Job> = {}): Job {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        type,
      },
    })
  }

  /**
   * Build a job for a specific resource
   */
  forResource(resourceType: string, resourceId: string, options: FactoryOptions<Job> = {}): Job {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        resource_type: resourceType,
        resource_id: resourceId,
      },
    })
  }
}

export const jobFactory = new JobFactory()
export { JobFactory }

