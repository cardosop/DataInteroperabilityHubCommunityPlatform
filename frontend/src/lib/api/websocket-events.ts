/**
 * WebSocket Event Type Definitions
 *
 * Comprehensive type definitions for all WebSocket events.
 * These types correspond to the events emitted by the backend event bus.
 *
 * All event types follow the pattern: `resource.action` (e.g., `contract.created`)
 */

/**
 * Base event structure
 * All events extend this structure
 */
export interface BaseEvent {
  event_id: string
  event_type: string
  event_version: string
  timestamp: string
  source: {
    service: string
    tenant_id: string
    user_id?: string
    request_id?: string
  }
  data: Record<string, any>
  metadata?: {
    correlation_id?: string
    tags?: string[]
    [key: string]: any
  }
}

/**
 * Contract Event Types
 */
export type ContractEventType =
  | 'contract.created'
  | 'contract.updated'
  | 'contract.deleted'
  | 'contract.validated'
  | 'contract.normalized'

/**
 * Contract Created Event
 */
export interface ContractCreatedEvent extends BaseEvent {
  event_type: 'contract.created'
  data: {
    contract_id: string
    name?: string
    status?: string
    tenant_id: string
    created_by?: string
  }
}

/**
 * Contract Updated Event
 */
export interface ContractUpdatedEvent extends BaseEvent {
  event_type: 'contract.updated'
  data: {
    contract_id: string
    name?: string
    status?: string
    changes?: Record<string, any>
  }
}

/**
 * Contract Validated Event
 */
export interface ContractValidatedEvent extends BaseEvent {
  event_type: 'contract.validated'
  data: {
    contract_id: string
    validation_status: string
    validation_result?: Record<string, any>
    job_id?: string
  }
}

/**
 * Asset Event Types
 */
export type AssetEventType =
  | 'asset.created'
  | 'asset.updated'
  | 'asset.activated'
  | 'asset.published'
  | 'asset.retired'

/**
 * Asset Created Event
 */
export interface AssetCreatedEvent extends BaseEvent {
  event_type: 'asset.created'
  data: {
    asset_id: string
    key: string
    name: string
    status: string
    tenant_id: string
    created_by?: string
  }
}

/**
 * Asset Activated Event
 */
export interface AssetActivatedEvent extends BaseEvent {
  event_type: 'asset.activated'
  data: {
    asset_id: string
    key: string
    name: string
    previous_status?: string
    activated_by?: string
  }
}

/**
 * Asset Updated Event
 */
export interface AssetUpdatedEvent extends BaseEvent {
  event_type: 'asset.updated'
  data: {
    asset_id: string
    key?: string
    name?: string
    status?: string
    changes?: Record<string, any>
  }
}

/**
 * Dataset Event Types
 */
export type DatasetEventType =
  | 'dataset.created'
  | 'dataset.updated'
  | 'dataset.deleted'
  | 'dataset.uploaded'

/**
 * Dataset Created Event
 */
export interface DatasetCreatedEvent extends BaseEvent {
  event_type: 'dataset.created'
  data: {
    dataset_id: string
    name: string
    format?: string
    tenant_id: string
    created_by?: string
  }
}

/**
 * Dataset Uploaded Event
 */
export interface DatasetUploadedEvent extends BaseEvent {
  event_type: 'dataset.uploaded'
  data: {
    dataset_id: string
    name: string
    format: string
    size_bytes?: number
    upload_id?: string
  }
}

/**
 * Job Event Types
 */
export type JobEventType =
  | 'job.started'
  | 'job.completed'
  | 'job.failed'
  | 'job.cancelled'

/**
 * Job Started Event
 */
export interface JobStartedEvent extends BaseEvent {
  event_type: 'job.started'
  data: {
    job_id: string
    job_type: string
    resource_type: string
    resource_id: string
    started_at: string
  }
}

/**
 * Job Completed Event
 */
export interface JobCompletedEvent extends BaseEvent {
  event_type: 'job.completed'
  data: {
    job_id: string
    job_type: string
    resource_type: string
    resource_id: string
    started_at: string
    completed_at: string
    result_json?: Record<string, any>
  }
}

/**
 * Job Failed Event
 */
export interface JobFailedEvent extends BaseEvent {
  event_type: 'job.failed'
  data: {
    job_id: string
    job_type: string
    resource_type: string
    resource_id: string
    error_message: string
    started_at?: string
    failed_at: string
  }
}

/**
 * Workflow Event Types
 */
export type WorkflowEventType =
  | 'workflow.started'
  | 'workflow.completed'
  | 'workflow.failed'
  | 'workflow.cancelled'
  | 'workflow.step.completed'
  | 'workflow.step.failed'

/**
 * Workflow Started Event
 */
export interface WorkflowStartedEvent extends BaseEvent {
  event_type: 'workflow.started'
  data: {
    workflow_id: string
    workflow_type: string
    resource_id?: string
    started_at: string
  }
}

/**
 * Workflow Step Completed Event
 */
export interface WorkflowStepCompletedEvent extends BaseEvent {
  event_type: 'workflow.step.completed'
  data: {
    workflow_id: string
    step_id: string
    step_name: string
    result?: Record<string, any>
    completed_at: string
  }
}

/**
 * Data Quality Event Types
 */
export type QualityEventType =
  | 'quality.check.started'
  | 'quality.check.completed'
  | 'quality.check.failed'
  | 'quality.anomaly.detected'

/**
 * Quality Check Completed Event
 */
export interface QualityCheckCompletedEvent extends BaseEvent {
  event_type: 'quality.check.completed'
  data: {
    check_id: string
    dataset_id?: string
    asset_id?: string
    status: string
    score?: number
    results?: Record<string, any>
    completed_at: string
  }
}

/**
 * Quality Anomaly Detected Event
 */
export interface QualityAnomalyDetectedEvent extends BaseEvent {
  event_type: 'quality.anomaly.detected'
  data: {
    anomaly_id: string
    dataset_id?: string
    asset_id?: string
    anomaly_type: string
    severity: string
    details?: Record<string, any>
    detected_at: string
  }
}

/**
 * Compliance Event Types
 */
export type ComplianceEventType =
  | 'compliance.check.started'
  | 'compliance.check.completed'
  | 'compliance.check.failed'
  | 'compliance.report.generated'

/**
 * Compliance Check Completed Event
 */
export interface ComplianceCheckCompletedEvent extends BaseEvent {
  event_type: 'compliance.check.completed'
  data: {
    check_id: string
    asset_id?: string
    contract_id?: string
    status: string
    score?: number
    violations?: Array<{
      rule_id: string
      rule_name: string
      severity: string
      message: string
    }>
    completed_at: string
  }
}

/**
 * Union type of all event types
 */
export type WebSocketEventType =
  | ContractEventType
  | AssetEventType
  | DatasetEventType
  | JobEventType
  | WorkflowEventType
  | QualityEventType
  | ComplianceEventType

/**
 * Union type of all event interfaces
 */
export type WebSocketEvent =
  | ContractCreatedEvent
  | ContractUpdatedEvent
  | ContractValidatedEvent
  | AssetCreatedEvent
  | AssetActivatedEvent
  | AssetUpdatedEvent
  | DatasetCreatedEvent
  | DatasetUploadedEvent
  | JobStartedEvent
  | JobCompletedEvent
  | JobFailedEvent
  | WorkflowStartedEvent
  | WorkflowStepCompletedEvent
  | QualityCheckCompletedEvent
  | QualityAnomalyDetectedEvent
  | ComplianceCheckCompletedEvent
  | BaseEvent // Fallback for unknown event types

/**
 * Event type to interface mapping helper
 * This helps with type narrowing when handling events
 */
export const EventTypeMap = {
  // Contract events
  'contract.created': 'ContractCreatedEvent' as const,
  'contract.updated': 'ContractUpdatedEvent' as const,
  'contract.validated': 'ContractValidatedEvent' as const,
  // Asset events
  'asset.created': 'AssetCreatedEvent' as const,
  'asset.updated': 'AssetUpdatedEvent' as const,
  'asset.activated': 'AssetActivatedEvent' as const,
  // Dataset events
  'dataset.created': 'DatasetCreatedEvent' as const,
  'dataset.uploaded': 'DatasetUploadedEvent' as const,
  // Job events
  'job.started': 'JobStartedEvent' as const,
  'job.completed': 'JobCompletedEvent' as const,
  'job.failed': 'JobFailedEvent' as const,
  // Workflow events
  'workflow.started': 'WorkflowStartedEvent' as const,
  'workflow.step.completed': 'WorkflowStepCompletedEvent' as const,
  // Quality events
  'quality.check.completed': 'QualityCheckCompletedEvent' as const,
  'quality.anomaly.detected': 'QualityAnomalyDetectedEvent' as const,
  // Compliance events
  'compliance.check.completed': 'ComplianceCheckCompletedEvent' as const,
} as const

/**
 * Type guard to check if event is a specific type
 */
export function isEventType<T extends WebSocketEventType>(
  event: BaseEvent,
  eventType: T
): event is Extract<WebSocketEvent, { event_type: T }> {
  return event.event_type === eventType
}

/**
 * Get event data type for a specific event type
 */
export type EventDataForType<T extends WebSocketEventType> = Extract<
  WebSocketEvent,
  { event_type: T }
>['data']

