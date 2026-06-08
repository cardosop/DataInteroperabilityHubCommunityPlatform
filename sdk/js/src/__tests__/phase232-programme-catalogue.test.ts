import { Phase232ProgrammeAPI } from '../phase232';

describe('Phase232ProgrammeAPI', () => {
  it('exposes seven list methods', () => {
    const names = Object.getOwnPropertyNames(Phase232ProgrammeAPI.prototype).filter(
      (n) => n.startsWith('list') && n !== 'list'
    );
    expect(names.sort()).toEqual(
      [
        'listBreachIncidents',
        'listComplianceRuns',
        'listConsentPurposes',
        'listDpiaRecords',
        'listDsarRequests',
        'listProcessorAgreements',
        'listRopaGenerations',
      ].sort()
    );
  });
});
