/**
 * Dataset Factory
 *
 * Factory for creating test Dataset objects.
 */

import type {
  Dataset,
  DatasetFormat,
  DatasetSchema,
  SchemaField,
} from '@/lib/api/datasets'
import { generateId, generateUUID, randomDate, type FactoryOptions, type FactoryTrait } from './utils'

/**
 * Dataset factory implementation
 */
class DatasetFactory implements FactoryTrait<Dataset> {
  /**
   * Build a single Dataset
   */
  build(options: FactoryOptions<Dataset> = {}): Dataset {
    const { overrides = {}, uniqueIds = true } = options
    const id = uniqueIds ? generateUUID() : 'test-dataset-1'
    const now = new Date().toISOString()

    const schema: DatasetSchema = {
      fields: [
        { name: 'id', type: 'string', nullable: false },
        { name: 'name', type: 'string', nullable: false },
        { name: 'value', type: 'number', nullable: true },
        { name: 'created_at', type: 'datetime', nullable: false },
      ],
    }

    return {
      id,
      tenant: 'test-tenant',
      asset: null,
      file: `test-file-${id.substring(0, 8)}.csv`,
      schema_json: schema,
      sample_data_json: [
        { id: '1', name: 'Test Item 1', value: 100, created_at: now },
        { id: '2', name: 'Test Item 2', value: 200, created_at: now },
        { id: '3', name: 'Test Item 3', value: 300, created_at: now },
      ],
      row_count: 1000,
      format: 'CSV' as DatasetFormat,
      version: 1,
      parent_version: null,
      semantic_version: '1.0.0',
      version_tags: ['v1.0.0'],
      is_current: true,
      created_by: 'test-user',
      created_at: randomDate(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)),
      updated_at: now,
      ...overrides,
    }
  }

  buildMany(count: number, options: FactoryOptions<Dataset> = {}): Dataset[] {
    return Array.from({ length: count }, (_, index) =>
      this.build({
        ...options,
        overrides: {
          ...options.overrides,
          format: (['CSV', 'JSON', 'PARQUET'] as DatasetFormat[])[index % 3],
          version: index + 1,
        },
      })
    )
  }

  buildSequence(builder: (index: number) => Partial<Dataset>): Dataset[] {
    const datasets: Dataset[] = []
    let index = 0
    let dataset = this.build({ overrides: builder(index) })

    while (dataset) {
      datasets.push(dataset)
      index++
      const overrides = builder(index)
      if (overrides === null || overrides === undefined) {
        break
      }
      dataset = this.build({ overrides })
    }

    return datasets
  }

  /**
   * Build a Dataset with CSV format
   */
  csv(options: FactoryOptions<Dataset> = {}): Dataset {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        format: 'CSV' as DatasetFormat,
        file: `test-file-${generateUUID().substring(0, 8)}.csv`,
      },
    })
  }

  /**
   * Build a Dataset with JSON format
   */
  json(options: FactoryOptions<Dataset> = {}): Dataset {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        format: 'JSON' as DatasetFormat,
        file: `test-file-${generateUUID().substring(0, 8)}.json`,
      },
    })
  }

  /**
   * Build a Dataset with PARQUET format
   */
  parquet(options: FactoryOptions<Dataset> = {}): Dataset {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        format: 'PARQUET' as DatasetFormat,
        file: `test-file-${generateUUID().substring(0, 8)}.parquet`,
      },
    })
  }

  /**
   * Build a Dataset with an asset
   */
  withAsset(assetId: string, options: FactoryOptions<Dataset> = {}): Dataset {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        asset: assetId,
      },
    })
  }

  /**
   * Build a Dataset with a specific row count
   */
  withRowCount(rowCount: number, options: FactoryOptions<Dataset> = {}): Dataset {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        row_count: rowCount,
      },
    })
  }

  /**
   * Build a Dataset version (non-current)
   */
  version(version: number, parentVersion: string, options: FactoryOptions<Dataset> = {}): Dataset {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        version,
        parent_version: parentVersion,
        is_current: false,
        semantic_version: `${version}.0.0`,
        version_tags: [`v${version}.0.0`],
      },
    })
  }
}

export const datasetFactory = new DatasetFactory()
export { DatasetFactory }

