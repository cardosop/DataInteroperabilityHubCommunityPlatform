/**
 * Phase 231.5 — Legal basis checks that failed or need review (`legal_basis_violations`).
 */

import type { ComplianceLegalBasisViolation } from '../../../shared/types/compliance';

export interface LegalBasisViolationsListProps {
  violations: ComplianceLegalBasisViolation[] | null | undefined;
}

export function LegalBasisViolationsList({ violations }: LegalBasisViolationsListProps) {
  if (violations == null || violations.length === 0) {
    return null;
  }

  return (
    <section className="phase19-legal-basis" data-testid="legal-basis-violations-section">
      <h3 className="phase19-section-title">Legal basis issues</h3>
      <ul className="phase19-legal-basis-list" data-testid="legal-basis-violations-list">
        {violations.map((v, idx) => (
          <li key={`${v.regulation}-${v.basis ?? ''}-${v.violation ?? ''}-${idx}`} className="phase19-legal-basis-item">
            <span className="phase19-legal-basis-reg">{v.regulation}</span>
            {v.basis != null && v.basis !== '' && (
              <span className="phase19-legal-basis-basis">Basis: {v.basis}</span>
            )}
            {v.violation != null && v.violation !== '' && (
              <span className="phase19-legal-basis-violation">{v.violation}</span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
