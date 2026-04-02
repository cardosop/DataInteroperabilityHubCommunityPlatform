/**
 * Invoice Preview Component — Phase 116C.5
 * Displays a styled invoice preview from a CustomerBillingReport.
 */

import type { CustomerBillingReport } from '../../../shared/types/baas';

interface InvoicePreviewProps {
  report: CustomerBillingReport;
}

export function InvoicePreview({ report }: InvoicePreviewProps) {
  return (
    <div className="invoice-preview">
      <div className="invoice-preview-header">
        <h3>Invoice Preview</h3>
      </div>

      <div className="invoice-card">
        <div className="invoice-top">
          <div className="invoice-title">Invoice</div>
          <div className="invoice-id">
            <small>Report ID</small>
            <code>{report.id}</code>
          </div>
        </div>

        <div className="invoice-bill-to">
          <strong>Bill To</strong>
          <div>{report.customer_name || '—'}</div>
          <div className="invoice-cid">{report.customer_id}</div>
          {report.customer_email && <div>{report.customer_email}</div>}
        </div>

        <div className="invoice-period">
          <strong>Billing Period</strong>
          <div>
            {new Date(report.period_start).toLocaleDateString()} –{' '}
            {new Date(report.period_end).toLocaleDateString()}
          </div>
        </div>

        <table className="invoice-usage-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Total Requests</td>
              <td>{report.total_requests.toLocaleString()}</td>
            </tr>
            <tr>
              <td>Included Requests</td>
              <td>{report.included_requests.toLocaleString()}</td>
            </tr>
            <tr>
              <td>Overage Requests</td>
              <td>{report.overage_requests.toLocaleString()}</td>
            </tr>
          </tbody>
        </table>

        <table className="invoice-charges-table">
          <thead>
            <tr>
              <th>Description</th>
              <th>Amount ({report.currency})</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Base Fee</td>
              <td className="amount-cell">{report.base_fee}</td>
            </tr>
            <tr>
              <td>Overage Fee</td>
              <td className="amount-cell">{report.overage_fee}</td>
            </tr>
            <tr className="invoice-total-row">
              <td><strong>Total Amount Due</strong></td>
              <td className="amount-cell"><strong>{report.total_amount} {report.currency}</strong></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
