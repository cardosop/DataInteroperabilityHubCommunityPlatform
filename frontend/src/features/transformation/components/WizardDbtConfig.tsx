/**
 * 285.9.4.1 — WizardDbtConfig sub-component.
 * 285.9b.UX.4 — Client-side validation (ARN pattern, HTTPS URL).
 * 285.9b.UX.6 — Help text + tooltips with aria-describedby.
 *
 * Configuration form for dbt project: git URL, credentials, warehouse type.
 */
import React, { useState, useId } from 'react';

const ARN_PATTERN = /^arn:aws:secretsmanager:[a-z0-9-]+:\d{12}:secret:.+/;

interface Props {
  pipelineId: string;
  onSubmit: (config: Record<string, unknown>) => void;
  onBack: () => void;
}

export function WizardDbtConfig({ pipelineId: _pipelineId, onSubmit, onBack }: Props): React.ReactElement {
  const [gitUrl, setGitUrl] = useState('');
  const [warehouseType, setWarehouseType] = useState('snowflake');
  const [warehouseCredentialRef, setWarehouseCredentialRef] = useState('');
  const [gitCredentialRef, setGitCredentialRef] = useState('');
  const [targetName, setTargetName] = useState('prod');
  const [timeout, setTimeout_] = useState('3600');
  const [errors, setErrors] = useState<Record<string, string>>({});

  // 285.9b.UX.6 — unique IDs for aria-describedby linking
  const gitUrlHelpId = useId();
  const arnHelpId = useId();
  const timeoutHelpId = useId();
  const whHelpId = useId();

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};
    // 285.9b.UX.4 — validate git URL is HTTPS
    if (gitUrl && !gitUrl.startsWith('https://')) {
      newErrors.gitUrl = 'Git URL must use HTTPS (e.g. https://github.com/org/repo.git)';
    }
    // 285.9b.UX.4 — validate ARN pattern
    if (warehouseCredentialRef && !ARN_PATTERN.test(warehouseCredentialRef)) {
      newErrors.warehouseCredentialRef = 'Must match ARN pattern: arn:aws:secretsmanager:<region>:<account>:secret:<name>';
    }
    if (gitCredentialRef && !ARN_PATTERN.test(gitCredentialRef)) {
      newErrors.gitCredentialRef = 'Must match ARN pattern: arn:aws:secretsmanager:<region>:<account>:secret:<name>';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    onSubmit({
      gitUrl,
      warehouseType,
      warehouseCredentialRef,
      gitCredentialRef,
      targetName,
      timeout,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="wizard-dbt-config">
      <h2>Configure dbt Project</h2>

      {/* Git Repository URL */}
      <label htmlFor="dbt-git-url">Git Repository URL</label>
      <input
        id="dbt-git-url"
        type="url"
        value={gitUrl}
        onChange={(e) => setGitUrl(e.target.value)}
        placeholder="https://github.com/acme/dbt-project.git"
        aria-describedby={errors.gitUrl ? `${gitUrlHelpId}-error` : gitUrlHelpId}
      />
      <small id={gitUrlHelpId} className="field-help">
        HTTPS URL of your dbt project repository. Must start with https://.
      </small>
      {errors.gitUrl && (
        <span id={`${gitUrlHelpId}-error`} className="field-error" role="alert">
          {errors.gitUrl}
        </span>
      )}

      {/* Warehouse Type */}
      <label htmlFor="dbt-warehouse-type">Warehouse Type</label>
      <select
        id="dbt-warehouse-type"
        value={warehouseType}
        onChange={(e) => setWarehouseType(e.target.value)}
        aria-describedby={whHelpId}
      >
        <option value="snowflake">Snowflake</option>
        <option value="bigquery">BigQuery</option>
        <option value="databricks">Databricks</option>
      </select>
      <small id={whHelpId} className="field-help">
        Target data warehouse where dbt will execute. Credentials are resolved from AWS Secrets Manager.
      </small>

      {/* Warehouse Credential Ref */}
      <label htmlFor="dbt-wh-cred-ref">Warehouse Credential Reference (AWS SM ARN)</label>
      <input
        id="dbt-wh-cred-ref"
        type="text"
        value={warehouseCredentialRef}
        onChange={(e) => setWarehouseCredentialRef(e.target.value)}
        placeholder="arn:aws:secretsmanager:us-east-1:123456789012:secret:wh-dbt"
        aria-describedby={errors.warehouseCredentialRef ? `${arnHelpId}-error` : arnHelpId}
      />
      <small id={arnHelpId} className="field-help">
        ARN format: arn:aws:secretsmanager:&lt;region&gt;:&lt;account-id&gt;:secret:&lt;name&gt;
      </small>
      {errors.warehouseCredentialRef && (
        <span id={`${arnHelpId}-error`} className="field-error" role="alert">
          {errors.warehouseCredentialRef}
        </span>
      )}

      {/* Git Credential Ref */}
      <label htmlFor="dbt-git-cred-ref">Git Credential Reference (AWS SM ARN)</label>
      <input
        id="dbt-git-cred-ref"
        type="text"
        value={gitCredentialRef}
        onChange={(e) => setGitCredentialRef(e.target.value)}
        placeholder="arn:aws:secretsmanager:us-east-1:123456789012:secret:git-pat"
        aria-describedby={errors.gitCredentialRef ? `${arnHelpId}-error-git` : `${arnHelpId}-git`}
      />
      <small id={`${arnHelpId}-git`} className="field-help">
        ARN for a secret containing a GitHub/GitLab Personal Access Token with repo scope.
      </small>
      {errors.gitCredentialRef && (
        <span id={`${arnHelpId}-error-git`} className="field-error" role="alert">
          {errors.gitCredentialRef}
        </span>
      )}

      {/* Target Name */}
      <label htmlFor="dbt-target">Target Name</label>
      <input
        id="dbt-target"
        type="text"
        value={targetName}
        onChange={(e) => setTargetName(e.target.value)}
      />

      {/* dbt Timeout */}
      <label htmlFor="dbt-timeout">dbt Timeout (seconds)</label>
      <input
        id="dbt-timeout"
        type="number"
        value={timeout}
        onChange={(e) => setTimeout_(e.target.value)}
        min="60"
        max="86400"
        aria-describedby={timeoutHelpId}
      />
      <small id={timeoutHelpId} className="field-help">
        Maximum execution time per dbt command. Default: 3600s (1 hour). Max: 86400s (24 hours).
      </small>

      <div className="wizard-buttons">
        <button type="button" onClick={onBack}>Back</button>
        <button type="submit">Next: Review</button>
      </div>
    </form>
  );
}
