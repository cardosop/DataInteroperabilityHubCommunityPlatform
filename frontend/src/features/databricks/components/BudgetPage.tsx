/**
 * Databricks cost-budget page (openspec add-databricks-cost-guardrails
 * task 7.6) — the U9 budget surface.
 *
 * Renders the tenant's budget rows with the rolling-hour progress bar
 * (consumed / budget over the hour — the SAME window read the
 * enforcement enforces) and the per-warehouse breakdown from the
 * ledger. The BAR clamps at 100% but the visible percentage never
 * lies (the raw percent text); the enforcement-mode badge renders
 * BLOCK vs ALERT; an unlimited budget renders without a bar. A failed
 * load renders the machine-readable CODE in the alert; the flag-off
 * 403 surfaces the distinct banner.
 */
import { useCallback, useEffect, useState } from 'react';

import { useTranslation } from '../../../shared/i18n/useTranslation';

import type { DatabricksCostBudget } from '@/shared/types/databricks';

import { DatabricksApiError, listBudgets } from '../services/budgetService';

const FLAG_DISABLED_CODE = 'DATABRICKS_CONTROL_PLANE_DISABLED';

function formatUnits(value: string): string {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(1) : value;
}

export function BudgetPage(): React.ReactElement {
  const { t } = useTranslation();
  const [rows, setRows] = useState<DatabricksCostBudget[]>([]);
  const [loading, setLoading] = useState(true);
  const [flagDisabled, setFlagDisabled] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setFlagDisabled(false);
    try {
      setRows(await listBudgets());
    } catch (e) {
      if (e instanceof DatabricksApiError && e.code === FLAG_DISABLED_CODE) {
        setFlagDisabled(true);
        setRows([]);
      } else {
        const code = e instanceof DatabricksApiError ? e.code : undefined;
        const message = e instanceof Error ? e.message : String(e);
        setError(code ? `[${code}] ${message}` : message);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <div className="budget-list">{t('databricks.budgets.loading', 'Loading cost budgets…')}</div>
    );
  }

  if (flagDisabled) {
    return (
      <div role="alert" data-testid="flag-disabled-banner">
        <h2>{t('databricks.budgets.title', 'Databricks cost budgets')}</h2>
        <p>
          {t('databricks.page.flag_disabled_body', 'The Databricks control plane is disabled for this tenant.')}{' '}
          <code>{FLAG_DISABLED_CODE}</code>
        </p>
      </div>
    );
  }

  return (
    <div className="budget-list">
      <div className="budget-list-header">
        <h2>{t('databricks.budgets.title', 'Databricks cost budgets')}</h2>
        <button type="button" onClick={() => void load()} disabled={loading}>
          {t('databricks.budgets.refresh', 'Refresh')}
        </button>
      </div>

      {error && (
        <div role="alert" className="budget-error" data-testid="action-error">
          {error}
        </div>
      )}

      {rows.length === 0 ? (
        <p>{t('databricks.budgets.empty', 'No cost budgets configured yet.')}</p>
      ) : (
        <table aria-label={t('databricks.budgets.title', 'Databricks cost budgets')}>
          <thead>
            <tr>
              <th>{t('databricks.budgets.scope', 'Scope')}</th>
              <th>{t('databricks.budgets.mode', 'Mode')}</th>
              <th>{t('databricks.budgets.rolling_hour', 'Rolling hour')}</th>
              <th>{t('databricks.budgets.breakdown', 'Per-warehouse breakdown')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const percent = row.percent;
              const over = percent !== null && percent > 100;
              const near = percent !== null && !over && percent >= 90;
              const clamped = percent === null ? 0 : Math.min(100, percent);
              const rowClass = over ? 'over-budget' : near ? 'near-budget' : '';
              return (
                <tr key={row.id} className={`budget-row ${rowClass}`}>
                  <td>
                    {row.warehouse_name ??
                      t('databricks.budgets.tenant_scope', 'Tenant-wide')}
                  </td>
                  <td>
                    <span className={`mode-badge mode-${row.enforcement_mode.toLowerCase()}`}>
                      {row.enforcement_mode}
                    </span>
                  </td>
                  <td>
                    {percent === null ? (
                      <span className="budget-unlimited">
                        {t('databricks.budgets.unlimited', 'Unlimited')}
                      </span>
                    ) : (
                      <>
                        <div
                          role="progressbar"
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-valuenow={clamped}
                          aria-label={t(
                            'databricks.budgets.progress_label',
                            'Rolling-hour budget consumption'
                          )}
                          className="budget-bar"
                        >
                          <div className="budget-bar-fill" style={{ width: `${clamped}%` }} />
                        </div>
                        <span className="budget-numbers">
                          {formatUnits(row.consumed)} /{' '}
                          {row.budget_units_per_hour
                            ? formatUnits(row.budget_units_per_hour)
                            : '∞'}{' '}
                          {t('databricks.budgets.units', 'units')}{' '}
                          <span className="budget-percent">{percent}%</span>
                        </span>
                      </>
                    )}
                  </td>
                  <td>
                    {row.breakdown.length === 0 ? (
                      <span className="budget-no-breakdown">
                        {t(
                          'databricks.budgets.no_breakdown',
                          'No warehouse activity in the rolling hour'
                        )}
                      </span>
                    ) : (
                      <ul className="budget-breakdown">
                        {row.breakdown.map((entry) => (
                          <li key={entry.warehouse_id ?? 'unattributed'}>
                            {entry.warehouse_name ??
                              t('databricks.budgets.unattributed', 'Unattributed')}
                            : {formatUnits(entry.units)}
                          </li>
                        ))}
                      </ul>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
