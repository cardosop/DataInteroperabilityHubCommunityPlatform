/**
 * Breadcrumbs Component
 * Navigation context for detail pages
 */

import { Link } from 'react-router-dom';
import { FEATURE_BREADCRUMBS_ENABLED } from '../config/featureFlags';
import './Breadcrumbs.css';

export interface BreadcrumbItem {
  label: string;
  href?: string;
  to?: string;
}

export interface BreadcrumbsProps {
  items: BreadcrumbItem[];
}

export function Breadcrumbs({ items }: BreadcrumbsProps) {
  if (!FEATURE_BREADCRUMBS_ENABLED || items.length === 0) return null;

  return (
    <nav className="breadcrumbs" aria-label="Breadcrumb">
      <ol className="breadcrumbs-list">
        {items.map((item, index) => (
          <li
            key={index}
            className={`breadcrumbs-item ${index < items.length - 1 ? 'breadcrumbs-item-with-sep' : ''}`}
          >
            {(() => {
              const linkTarget = item.href ?? item.to;
              if (linkTarget) {
                return (
                  <Link to={linkTarget} className="breadcrumbs-link">
                    {item.label}
                  </Link>
                );
              }
              return (
                <span className="breadcrumbs-current" aria-current="page">
                  {item.label}
                </span>
              );
            })()}
          </li>
        ))}
      </ol>
    </nav>
  );
}
