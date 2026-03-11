/**
 * Virtual Dataset Source Builder
 * Structured UI for adding sources with type-specific form fields.
 * Supports ODBC, PostgreSQL, federated_asset, REST, SPARQL, etc.
 */

import { useState } from 'react';
import { VirtualDatasetSourceType, type OdbcSourceConfig } from '../../../shared/types/virtualization';
import './VirtualDatasetSourceBuilder.css';

export interface SourceEntry {
  type: string;
  [key: string]: unknown;
}

interface VirtualDatasetSourceBuilderProps {
  sources: SourceEntry[];
  onChange: (sources: SourceEntry[]) => void;
  errors?: Record<string, string>;
}

const SOURCE_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: VirtualDatasetSourceType.POSTGRESQL, label: 'PostgreSQL' },
  { value: VirtualDatasetSourceType.MYSQL, label: 'MySQL' },
  { value: VirtualDatasetSourceType.SQLSERVER, label: 'SQL Server' },
  { value: VirtualDatasetSourceType.ODBC, label: 'ODBC' },
  { value: VirtualDatasetSourceType.FEDERATED_ASSET, label: 'Federated Asset' },
  { value: VirtualDatasetSourceType.SPARQL, label: 'SPARQL' },
  { value: VirtualDatasetSourceType.REST, label: 'REST' },
  { value: VirtualDatasetSourceType.GRAPHQL, label: 'GraphQL' },
];

export function VirtualDatasetSourceBuilder({
  sources,
  onChange,
  errors = {},
}: VirtualDatasetSourceBuilderProps) {
  const [showAddForm, setShowAddForm] = useState(false);
  const [newSourceType, setNewSourceType] = useState<VirtualDatasetSourceType>(
    VirtualDatasetSourceType.ODBC
  );
  const [odbcConfig, setOdbcConfig] = useState<Partial<OdbcSourceConfig> & { useConnectionString?: boolean }>({
    type: 'odbc',
    useConnectionString: true,
    connection_string: '',
    driver: 'PostgreSQL Unicode',
    host: '',
    port: 5432,
    database: '',
    username: '',
    password: '',
  });

  const resetOdbcForm = () => {
    setOdbcConfig({
      type: 'odbc',
      useConnectionString: true,
      connection_string: '',
      driver: 'PostgreSQL Unicode',
      host: '',
      port: 5432,
      database: '',
      username: '',
      password: '',
    });
  };

  const buildOdbcSource = (): OdbcSourceConfig => {
    if (odbcConfig.useConnectionString && odbcConfig.connection_string?.trim()) {
      return {
        type: 'odbc',
        connection_string: odbcConfig.connection_string.trim(),
      };
    }
    return {
      type: 'odbc',
      driver: odbcConfig.driver || 'PostgreSQL Unicode',
      host: odbcConfig.host?.trim() || '',
      port: odbcConfig.port ?? 5432,
      database: odbcConfig.database?.trim() || '',
      username: odbcConfig.username?.trim() || undefined,
      password: odbcConfig.password || undefined,
    };
  };

  const handleAddSource = () => {
    if (newSourceType === VirtualDatasetSourceType.ODBC) {
      const built = buildOdbcSource();
      if (
        built.connection_string ||
        (built.host && built.database)
      ) {
        onChange([...sources, built]);
        setShowAddForm(false);
        resetOdbcForm();
      }
    } else {
      const template = getSourceTemplate(newSourceType);
      if (template) {
        onChange([...sources, template]);
        setShowAddForm(false);
      }
    }
  };

  const getSourceTemplate = (type: string): SourceEntry | null => {
    switch (type) {
      case VirtualDatasetSourceType.FEDERATED_ASSET:
        return { type: 'federated_asset', asset_id: '', query: 'SELECT * FROM metadata' };
      case VirtualDatasetSourceType.POSTGRESQL:
        return {
          type: 'postgresql',
          host: 'localhost',
          port: 5432,
          database: '',
          username: '',
          password: '',
          query: 'SELECT 1',
        };
      case VirtualDatasetSourceType.SPARQL:
        return { type: 'sparql', endpoint: '', query: 'SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 1' };
      case VirtualDatasetSourceType.REST:
        return { type: 'rest', url: '', method: 'GET' };
      default:
        return { type, query: 'SELECT 1' };
    }
  };

  const canAddOdbc = () => {
    if (odbcConfig.useConnectionString) {
      return !!odbcConfig.connection_string?.trim();
    }
    return !!(odbcConfig.host?.trim() && odbcConfig.database?.trim());
  };

  const handleRemoveSource = (index: number) => {
    onChange(sources.filter((_, i) => i !== index));
  };

  return (
    <div className="virtual-dataset-source-builder">
      <label className="source-builder-label">Sources</label>
      <div className="sources-list">
        {sources.map((src, i) => (
          <div key={i} className="source-item">
            <span className="source-type-badge">{src.type}</span>
            <button
              type="button"
              className="btn-remove-source"
              onClick={() => handleRemoveSource(i)}
              aria-label="Remove source"
            >
              ×
            </button>
          </div>
        ))}
      </div>

      {!showAddForm ? (
        <div className="source-type-dropdown-row">
          <select
            id="source_type"
            value={newSourceType}
            onChange={(e) => setNewSourceType(e.target.value as VirtualDatasetSourceType)}
            className="source-type-select"
          >
            {SOURCE_TYPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="btn-add-source"
            onClick={() => setShowAddForm(true)}
          >
            Add source
          </button>
        </div>
      ) : (
        <div className="source-add-form">
          {newSourceType === VirtualDatasetSourceType.ODBC && (
            <div className="odbc-form-fields" data-testid="odbc-source-form">
              <div className="form-group">
                <label>
                  <input
                    type="radio"
                    checked={!!odbcConfig.useConnectionString}
                    onChange={() =>
                      setOdbcConfig((c) => ({ ...c, useConnectionString: true }))
                    }
                  />
                  Connection string
                </label>
              </div>
              {odbcConfig.useConnectionString && (
                <div className="form-group">
                  <label htmlFor="odbc_connection_string">Connection string</label>
                  <input
                    id="odbc_connection_string"
                    type="text"
                    placeholder="DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=..."
                    value={odbcConfig.connection_string || ''}
                    onChange={(e) =>
                      setOdbcConfig((c) => ({
                        ...c,
                        connection_string: e.target.value,
                      }))
                    }
                  />
                </div>
              )}

              <div className="form-group">
                <label>
                  <input
                    type="radio"
                    data-testid="odbc-host-database-radio"
                    checked={!odbcConfig.useConnectionString}
                    onChange={() =>
                      setOdbcConfig((c) => ({ ...c, useConnectionString: false }))
                    }
                  />
                  Host + Database
                </label>
              </div>
              {!odbcConfig.useConnectionString && (
                <>
                  <div className="form-group">
                    <label htmlFor="odbc_driver">Driver</label>
                    <input
                      id="odbc_driver"
                      type="text"
                      placeholder="PostgreSQL Unicode"
                      value={odbcConfig.driver || ''}
                      onChange={(e) =>
                        setOdbcConfig((c) => ({ ...c, driver: e.target.value }))
                      }
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="odbc_host">Host</label>
                    <input
                      id="odbc_host"
                      data-testid="odbc-host"
                      type="text"
                      placeholder="localhost"
                      value={odbcConfig.host || ''}
                      onChange={(e) =>
                        setOdbcConfig((c) => ({ ...c, host: e.target.value }))
                      }
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="odbc_port">Port</label>
                    <input
                      id="odbc_port"
                      type="number"
                      placeholder="5432"
                      value={odbcConfig.port ?? ''}
                      onChange={(e) =>
                        setOdbcConfig((c) => ({
                          ...c,
                          port: parseInt(e.target.value, 10) || 5432,
                        }))
                      }
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="odbc_database">Database</label>
                    <input
                      id="odbc_database"
                      data-testid="odbc-database"
                      type="text"
                      placeholder="mydb"
                      value={odbcConfig.database || ''}
                      onChange={(e) =>
                        setOdbcConfig((c) => ({ ...c, database: e.target.value }))
                      }
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="odbc_username">Username</label>
                    <input
                      id="odbc_username"
                      data-testid="odbc-username"
                      type="text"
                      placeholder="user"
                      value={odbcConfig.username || ''}
                      onChange={(e) =>
                        setOdbcConfig((c) => ({ ...c, username: e.target.value }))
                      }
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="odbc_password">Password</label>
                    <input
                      id="odbc_password"
                      data-testid="odbc-password"
                      type="password"
                      placeholder="••••••••"
                      value={odbcConfig.password || ''}
                      onChange={(e) =>
                        setOdbcConfig((c) => ({ ...c, password: e.target.value }))
                      }
                    />
                  </div>
                </>
              )}
            </div>
          )}

          <div className="source-add-actions">
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                setShowAddForm(false);
                resetOdbcForm();
              }}
            >
              Cancel
            </button>
            <button
              type="button"
              className="btn-primary"
              data-testid="odbc-add-source-btn"
              onClick={handleAddSource}
              disabled={
                newSourceType === VirtualDatasetSourceType.ODBC && !canAddOdbc()
              }
            >
              Add
            </button>
          </div>
        </div>
      )}

      {errors.sources && (
        <span className="error-message">{errors.sources}</span>
      )}
    </div>
  );
}
