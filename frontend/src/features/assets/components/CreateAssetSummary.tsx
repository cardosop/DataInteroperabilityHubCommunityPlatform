/**
 * CreateAssetSummary — shows what will be created and submission progress.
 *
 * Conservative: does not promise inferred contracts (data-first CAN return
 * contract_id=null). Shows only what is certain based on user input.
 */

import './CreateAssetSummary.css';

export interface CreateAssetSummaryProps {
  hasDataFile: boolean;
  hasContract: boolean;
  contractType?: string;
  detectedSpecType?: string;
  submitting: boolean;
  currentStep?: string;
}

export function CreateAssetSummary({
  hasDataFile,
  hasContract,
  detectedSpecType,
  submitting,
  currentStep,
}: CreateAssetSummaryProps) {
  if (submitting) {
    return (
      <div className="create-asset-summary create-asset-summary--submitting" role="status">
        <span className="create-asset-summary__spinner" />
        <span className="create-asset-summary__step">{currentStep || 'Processing...'}</span>
      </div>
    );
  }

  const parts = ['Asset'];
  if (hasDataFile) parts.push('Dataset');
  if (hasContract) parts.push('Contract');

  return (
    <div className="create-asset-summary">
      <span className="create-asset-summary__label">
        Will create: {parts.join(' + ')}
      </span>
      {detectedSpecType && (
        <span className={`create-asset-summary__badge create-asset-summary__badge--${detectedSpecType.toLowerCase()}`}>
          {detectedSpecType}
        </span>
      )}
    </div>
  );
}
