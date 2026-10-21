"""Tax-ID masking utilities (core).

``mask_tax_id`` produces the audit-log-safe form of a tax identifier:
country prefix + last 4 chars, everything else starred. Moved here from
``hub.apps.billing.views`` (Phase 313.H.3) — the helper is pure string
logic used by CORE views (tenants tax-id submission audit rows), so it
belongs in the core security app; billing keeps using it via import.
"""

from __future__ import annotations


def mask_tax_id(tax_id_value: str) -> str:
    """Return a masked-last-4 form for audit logs.

    e.g. ``GB123456789`` → ``GB*****6789`` (preserve country
    prefix + last 4 chars). The unmasked value lives in the
    encrypted ``Tenant.tax_id`` column; the audit log surface
    is wider read-permission so we mask there.
    """
    if not tax_id_value:
        return ""
    tax_id_value = str(tax_id_value)
    if len(tax_id_value) <= 6:
        return "*" * len(tax_id_value)
    return tax_id_value[:2] + "*" * (len(tax_id_value) - 6) + tax_id_value[-4:]
