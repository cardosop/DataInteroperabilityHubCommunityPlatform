"""
ODPS 4.2 Normalizer

Version-specific normalizer for ODPS (Open Data Product Standard) version 4.2.
Inherits from ODPSNormalizerV4_1 (4.2 is backwards-compatible with 4.1 at
field level) and adds mappings for:

- paymentGateways[].currency / .provider  → pricing.payment_gateways[]
- productStrategy.kpi[].target / .unit    → strategy.kpis[]
"""

from typing import Any

import structlog

from hub.apps.contracts.normalization.odps_normalizer_v4_1 import ODPSNormalizerV4_1

logger = structlog.get_logger(__name__)


class ODPSNormalizerV4_2(ODPSNormalizerV4_1):
    """
    ODPS 4.2-specific normalizer implementation.

    Extends ODPSNormalizerV4_1 with 4.2-specific enhancements:
    - Structured paymentGateways with ``currency`` and ``provider`` fields
    - Product strategy KPIs with ``target`` and ``unit`` sub-fields

    All 4.1 features (marketplace, product strategy) are inherited.
    """

    def _supports_version(self, spec_version: str) -> bool:
        """Support only ODPS version 4.2."""
        return spec_version == "4.2"

    def _map_version_specific_fields(
        self,
        contract_data: dict[str, Any],
        hub_contract: dict[str, Any],
        warnings: list[str],
        spec_version: str,
    ) -> None:
        """
        Map ODPS 4.2-specific fields after all common normalisation.

        Enhancements over 4.1:
        - paymentGateways entries gain ``currency`` and ``provider`` keys
        - productStrategy.kpi entries gain ``target`` and ``unit`` keys
        """
        # Run inherited 4.1 logic first (product strategy, marketplace)
        super()._map_version_specific_fields(
            contract_data,
            hub_contract,
            warnings,
            spec_version,
        )

        product = contract_data.get("product", {})
        if not isinstance(product, dict):
            return

        # --- paymentGateways → pricing.payment_gateways ----------------
        marketplace = product.get("marketplace", {})
        if isinstance(marketplace, dict):
            gateways_raw = marketplace.get("paymentGateways")
            if isinstance(gateways_raw, list) and gateways_raw:
                gw_list = []
                for gw in gateways_raw:
                    if isinstance(gw, dict):
                        gw_list.append(
                            {
                                "currency": gw.get("currency"),
                                "provider": gw.get("provider"),
                                **{
                                    k: v for k, v in gw.items() if k not in ("currency", "provider")
                                },
                            }
                        )
                hub_contract.setdefault("pricing", {})
                hub_contract["pricing"]["payment_gateways"] = gw_list

        # --- productStrategy.kpi → strategy.kpis ----------------------
        strategy_raw = product.get("productStrategy", {})
        if isinstance(strategy_raw, dict):
            kpis_raw = strategy_raw.get("kpi")
            if isinstance(kpis_raw, list) and kpis_raw:
                kpi_list = []
                for kpi in kpis_raw:
                    if isinstance(kpi, dict):
                        kpi_list.append(
                            {
                                "target": kpi.get("target"),
                                "unit": kpi.get("unit"),
                                **{k: v for k, v in kpi.items() if k not in ("target", "unit")},
                            }
                        )
                hub_contract.setdefault("strategy", {})
                hub_contract["strategy"]["kpis"] = kpi_list
