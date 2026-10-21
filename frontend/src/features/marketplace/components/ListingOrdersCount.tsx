/**
 * ListingOrdersCount — 223.2.3.
 *
 * Reverse-relationship surface on the Listing detail page. Queries
 * `GET /marketplace/orders/?listing_id={id}` via the shared `useOrders`
 * hook and renders a compact count card plus a link to the filtered
 * orders list.
 */

import { Link } from 'react-router-dom';
import { useOrders } from '../hooks/useOrders';

export interface ListingOrdersCountProps {
  listingId: string;
}

export function ListingOrdersCount({ listingId }: ListingOrdersCountProps) {
  // page_size=1 — we only need the paginated `count` metadata. Saves
  // bandwidth when the listing has thousands of orders.
  const { data, isLoading, error } = useOrders({
    listing_id: listingId,
    page_size: 1,
  });

  const total = data?.count ?? 0;

  return (
    <section
      className="listing-orders-count listing-section"
      data-testid="listing-orders-count"
      aria-labelledby="listing-orders-count-heading"
    >
      <h2 id="listing-orders-count-heading">Orders</h2>
      {isLoading && <p>Loading…</p>}
      {!!error && (
        <p className="listing-orders-error">Failed to load orders.</p>
      )}
      {!isLoading && !error && (
        <>
          <p data-testid="listing-orders-total">
            <strong>{total}</strong> {total === 1 ? 'order' : 'orders'} for this listing.
          </p>
          {total > 0 && (
            <Link to={`/marketplace/orders?listing_id=${listingId}`}>
              View orders
            </Link>
          )}
        </>
      )}
    </section>
  );
}
