/**
 * ContractUsedByAssets — 223.2.2.
 *
 * Reverse-relationship surface on the Contract detail page. Queries
 * `GET /assets/?contract_id={id}` via the shared `useAssets` hook and
 * renders a link list of the assets that bind to this contract.
 */

import { Link } from 'react-router-dom';
import { useAssets } from '../../assets/hooks/useAssets';

export interface ContractUsedByAssetsProps {
  contractId: string;
}

export function ContractUsedByAssets({ contractId }: ContractUsedByAssetsProps) {
  const { data, isLoading, error } = useAssets({
    contract_id: contractId,
    page_size: 20,
  });

  const assets = data?.results ?? [];

  return (
    <section
      className="contract-used-by-assets"
      data-testid="contract-used-by-assets"
      aria-labelledby="contract-used-by-assets-heading"
    >
      <h2 id="contract-used-by-assets-heading">
        Used by Assets {data ? `(${data.count})` : ''}
      </h2>
      {isLoading && <p>Loading…</p>}
      {!!error && (
        <p className="used-by-assets-error">
          Failed to load assets using this contract.
        </p>
      )}
      {!isLoading && !error && assets.length === 0 && (
        <p className="no-linked">No assets are currently using this contract.</p>
      )}
      {assets.length > 0 && (
        <ul className="used-by-assets-list">
          {assets.map((a) => (
            <li key={a.id} data-testid={`used-by-asset-${a.id}`}>
              <Link to={`/assets/${a.id}`}>{a.name || a.key}</Link>
              {a.status && (
                <span className={`status-badge status-${a.status.toLowerCase()}`}>
                  {' '}
                  {a.status}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
