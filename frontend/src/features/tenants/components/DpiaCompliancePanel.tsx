/**
 * Phase 232.5 — DPIA panel (Tenant Settings → Compliance tab)
 */
import { Link } from 'react-router-dom';
import { useCapabilities } from '../../../shared/hooks/useCapabilities';

export function DpiaCompliancePanel() {
  const { isCapabilityAvailable } = useCapabilities();
  const enabled = isCapabilityAvailable('compliance_dpia');

  if (!enabled) {
    return (
      <div className="tenant-form-group" data-testid="dpia-compliance-disabled">
        <p className="tenant-settings-description">
          DPIA tooling is disabled. Enable <strong>compliance_dpia_enabled</strong> via tenant feature flags, then
          reload capabilities.
        </p>
      </div>
    );
  }

  return (
    <section className="tenant-form-group" data-testid="dpia-compliance-panel">
      <h3 className="tenant-settings-subheading">Data protection impact assessments (Article 35)</h3>
      <p className="tenant-settings-description">
        Maintain DPIA records, route assessments through DPO review, and track periodic re-review (12-month cycle).
      </p>
      <ul>
        <li>
          <Link to="/governance/dpia/new">New DPIA wizard</Link>
        </li>
        <li>
          <Link to="/governance/dpia/review-queue">DPO review queue</Link>
        </li>
      </ul>
    </section>
  );
}
