/**
 * Breadcrumbs Component Tests
 */

import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { Breadcrumbs } from '../Breadcrumbs';

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe('Breadcrumbs', () => {
  it('renders breadcrumb items', () => {
    renderWithRouter(
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/' },
          { label: 'Assets', href: '/assets' },
          { label: 'My Asset' },
        ]}
      />
    );
    expect(screen.getByRole('navigation', { name: /breadcrumb/i })).toBeInTheDocument();
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Assets')).toBeInTheDocument();
    expect(screen.getByText('My Asset')).toBeInTheDocument();
  });

  it('renders links for items with href', () => {
    renderWithRouter(
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/' },
          { label: 'Current' },
        ]}
      />
    );
    const homeLink = screen.getByRole('link', { name: 'Home' });
    expect(homeLink).toHaveAttribute('href', '/');
    expect(screen.getByText('Current')).not.toHaveAttribute('href');
  });

  it('last item is not a link', () => {
    renderWithRouter(
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/' },
          { label: 'Current' },
        ]}
      />
    );
    expect(screen.queryByRole('link', { name: 'Current' })).not.toBeInTheDocument();
  });

  it('returns null when items array is empty', () => {
    const { container } = renderWithRouter(<Breadcrumbs items={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
