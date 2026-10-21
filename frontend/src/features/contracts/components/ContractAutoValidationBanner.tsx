/**
 * ContractAutoValidationBanner — inline feedback after attaching a contract.
 *
 * Runs a one-shot dry-run validation against `/contracts/validate-draft/`
 * via `useAutoValidateContract` (ref-guarded, no re-runs on re-renders) and
 * renders a shared `<Banner>` with success / warning / error variant based
 * on the outcome. Silent while idle or during the network round-trip so
 * the UI never flickers banners during attachment.
 */

import { Banner } from '../../../shared/components/Banner';
import type {
  AutoValidateContractInput,
} from '../hooks/useAutoValidateContract';
import { useAutoValidateContract } from '../hooks/useAutoValidateContract';

export interface ContractAutoValidationBannerProps {
  /** Contract to validate. Pass `null` to suspend. */
  contract: AutoValidateContractInput | null;
}

export function ContractAutoValidationBanner({
  contract,
}: ContractAutoValidationBannerProps) {
  const { status, warningCount, errorSummary } =
    useAutoValidateContract(contract);

  if (status === 'idle' || status === 'validating' || status === 'error') {
    return null;
  }

  return (
    <div data-testid="contract-auto-validation-banner">
      {status === 'valid' && (
        <Banner variant="success">Contract valid.</Banner>
      )}
      {status === 'warnings' && (
        <Banner variant="warning">
          Validation warnings: {warningCount}.
        </Banner>
      )}
      {status === 'invalid' && (
        <Banner variant="error">
          Validation failed: {errorSummary || 'see contract details'}
        </Banner>
      )}
    </div>
  );
}
