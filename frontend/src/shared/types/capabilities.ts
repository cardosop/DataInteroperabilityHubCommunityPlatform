/**
 * Capabilities Types
 * For runtime capability detection and gating
 */

export interface Capability {
  name: string;
  available: boolean;
  endpoint?: string;
  operationId?: string;
}

export interface CapabilitiesMap {
  [key: string]: Capability;
}

export interface OpenAPISchema {
  paths: Record<string, Record<string, unknown>>;
  components?: {
    schemas?: Record<string, unknown>;
  };
}
