"""
Phase 313.H.3 — audit-safe tax-id masking (core extraction).

``mask_tax_id`` moved out of ``hub.apps.billing.views`` because CORE
views (tenants tax-id submission audit rows) need the masked form.
Pure string logic — table-driven tests, no DB.
"""

from __future__ import annotations

import pytest

from hub.apps.security.tax_id import mask_tax_id


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("GB123456789", "GB*****6789"),
        ("DE12345678", "DE****5678"),
        ("US123456", "US**3456"),
        ("123456", "******"),
        ("12345", "*****"),
        ("AB", "**"),
        ("", ""),
        (None, ""),
        # Non-string input normalizes (defensive callers pass ints).
        (1234567890, "12****7890"),
    ],
)
def test_mask_tax_id_shapes(raw, expected):
    assert mask_tax_id(raw) == expected


def test_mask_tax_id_preserves_country_prefix_and_last_four():
    masked = mask_tax_id("GB123456789")
    assert masked.startswith("GB")
    assert masked.endswith("6789")
    assert len(masked) == len("GB123456789")
    assert "12345" not in masked
