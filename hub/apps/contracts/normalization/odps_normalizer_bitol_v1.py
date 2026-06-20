"""
Bitol ODPS v1.0.0 Normalizer

Version-specific normalizer for Bitol/LF ODPS (Open Data Product Standard)
version 1.0.0.  The Bitol lineage diverges from the pre-Bitol ODPS
(Niilahti et al.) at v0.9.0.

Key differences from pre-Bitol ODPS:
- ``team`` is an object ``{members: [...]}`` (aligned with ODCS v3.1.0)
- ``outputPorts`` / ``inputPorts`` with ``customProperties``, ``tags``,
  ``authoritativeDefinitions``, and ``contractId`` fields
- Schema URL: bitol-io.github.io/open-data-product-standard/v1.0.0
"""

import re
from typing import Any

import structlog

from hub.apps.contracts.normalization.odps_normalizer_base import (
    ODPSNormalizerBase,
)

logger = structlog.get_logger(__name__)

# Expected Bitol ODPS schema URL domain
_EXPECTED_BITOL_DOMAIN = "bitol-io.github.io"

# Match "bitol-1.0.0" and any "bitol-1.0.x"
_BITOL_V1_PATTERN = re.compile(r"^bitol-1\.0\.\d+$")

# Match any bitol-0.9.x
_BITOL_V09_PATTERN = re.compile(r"^bitol-0\.9\.\d+$")


class ODPSBitolNormalizerV1_0_0(ODPSNormalizerBase):
    """
    Bitol ODPS v1.0.0 normalizer.

    Handles the Bitol/LF fork of ODPS, which introduces:

    1. **team object**: same ``{members: [...]}`` shape as ODCS v3.1.0
       (reuses ``_parse_team_v31`` from the ODCS normalizer base).
    2. **outputPorts / inputPorts**: port-based I/O model with
       ``customProperties``, ``tags``, ``authoritativeDefinitions``,
       and ``contractId`` (links to an ODCS Contract UUID).
    3. **Schema URL**: ``bitol-io.github.io/open-data-product-standard``
    """

    def _supports_version(self, spec_version: str) -> bool:
        """Support bitol-1.0.x and bitol-0.9.x versions."""
        if spec_version is None:
            return False
        if spec_version in ("bitol-1.0.0", "bitol-0.9.0"):
            return True
        if _BITOL_V1_PATTERN.match(spec_version):
            return True
        if _BITOL_V09_PATTERN.match(spec_version):
            return True
        return False

    # ------------------------------------------------------------------
    # Version-specific hook
    # ------------------------------------------------------------------

    def _map_version_specific_fields(
        self,
        contract_data: dict[str, Any],
        hub_contract: dict[str, Any],
        warnings: list[str],
        spec_version: str,
    ) -> None:
        """
        Map Bitol ODPS v1.0.0–specific fields after base normalisation.

        1. team object → info.owners + team (via _parse_team_v31)
        2. outputPorts → extensions.x_odps.output_ports
        3. inputPorts  → extensions.x_odps.input_ports
        """
        # --- 0. Audit unexpected schema URL domain ---
        self._audit_schema_url(contract_data, warnings)

        # --- 1. team object (same shape as ODCS v3.1.0) ---
        self._map_bitol_team(contract_data, hub_contract, warnings)

        # --- 2. outputPorts ---
        self._map_output_ports(contract_data, hub_contract, warnings)

        # --- 3. inputPorts ---
        self._map_input_ports(contract_data, hub_contract, warnings)

        logger.debug(
            "odps_bitol_v1_version_specific_mapping_complete",
            spec_version=spec_version,
        )

    # ------------------------------------------------------------------
    # Schema URL audit
    # ------------------------------------------------------------------

    @staticmethod
    def _audit_schema_url(
        contract_data: dict[str, Any],
        warnings: list[str],
    ) -> None:
        """
        Log a security event if the schema URL points to an unexpected
        domain.  The Bitol ODPS spec schema should come from
        ``bitol-io.github.io``.
        """
        schema_url = contract_data.get("schema")
        if not isinstance(schema_url, str) or not schema_url:
            return
        try:
            from urllib.parse import urlparse

            parsed = urlparse(schema_url)
            host = (parsed.hostname or "").lower()
            if host and host != _EXPECTED_BITOL_DOMAIN:
                # Unexpected domain — log security event
                try:
                    from hub.apps.contracts.odps_security_logging import (
                        SecurityEventType,
                        SecuritySeverity,
                        get_security_logger,
                    )

                    sec_logger = get_security_logger()
                    sec_logger.log_security_violation(
                        event_type=SecurityEventType.SECURITY_VIOLATION,
                        severity=SecuritySeverity.MEDIUM,
                        violation_type="UNEXPECTED_SCHEMA_URL",
                        description=(
                            f"Bitol ODPS schema URL points to "
                            f"unexpected domain '{host}' "
                            f"(expected '{_EXPECTED_BITOL_DOMAIN}'): "
                            f"{schema_url}"
                        ),
                        attempted_url=schema_url,
                    )
                except Exception:
                    pass  # security logging must not break normalisation
                warnings.append(
                    f"Bitol ODPS schema URL points to unexpected "
                    f"domain '{host}' (expected "
                    f"'{_EXPECTED_BITOL_DOMAIN}')"
                )
        except Exception:
            pass  # URL parsing failure — not a security event

    # ------------------------------------------------------------------
    # Team mapping (Bitol uses same shape as ODCS v3.1.0)
    # ------------------------------------------------------------------

    def _map_bitol_team(
        self,
        contract_data: dict[str, Any],
        hub_contract: dict[str, Any],
        warnings: list[str],
    ) -> None:
        """
        Map Bitol ODPS ``team`` object to HubContract info.owners + team.

        Bitol ODPS v1.0.0 uses the same team structure as ODCS v3.1.0::

            {"members": [{name, email, role, id}]}

        Reuses ``_parse_team_v31`` from ODCS normalizer base (imported
        via the normalization package).
        """
        team_raw = contract_data.get("team")
        if not isinstance(team_raw, dict) or "members" not in team_raw:
            # Also check under product.team
            product = contract_data.get("product", {})
            if isinstance(product, dict):
                team_raw = product.get("team")
            if not isinstance(team_raw, dict) or "members" not in team_raw:
                return

        # Use the ODCS base _parse_team_v31 helper
        from hub.apps.contracts.normalization.odcs_normalizer_base import (
            ODCSNormalizerBase,
        )

        parsed = ODCSNormalizerBase._parse_team_v31(team_raw)

        if not parsed:
            warnings.append("Bitol ODPS team object has no valid members")
            return

        # Populate info.owners
        owners = []
        for m in parsed:
            owner: dict[str, Any] = {}
            if "name" in m:
                owner["name"] = m["name"]
            if "email" in m:
                owner["email"] = m["email"]
            if owner:
                owners.append(owner)
        if owners:
            hub_contract.setdefault("info", {})["owners"] = owners

        # Store team in hub_contract
        hub_contract["team"] = parsed

    # ------------------------------------------------------------------
    # Port mapping helpers
    # ------------------------------------------------------------------

    def _map_output_ports(
        self,
        contract_data: dict[str, Any],
        hub_contract: dict[str, Any],
        warnings: list[str],
    ) -> None:
        """
        Phase 227 Wave 1 — port METADATA only.

        Schema → ``models[]`` extraction is performed once in the base
        normaliser via :func:`_ports_helper.normalize_models_from_ports`
        (called from :meth:`ODPSNormalizerBase._normalize_ports_to_models`
        BEFORE this method runs). This method's sole remaining job is
        to preserve the Bitol-specific port-level metadata that does
        NOT belong on a model entry:

        * ``contractId`` — already used for resolution by the helper,
          but kept here as an audit breadcrumb under ``extensions``.
        * ``customProperties`` — arbitrary key/value pairs.
        * ``tags`` — taxonomy labels.
        * ``authoritativeDefinitions`` — definition refs.

        Removing this method entirely would lose those non-schema
        attributes from the canonical HubContract (frontends and
        downstream consumers read them via
        ``extensions.x_odps.output_ports``).
        """
        ports = self._get_ports(contract_data, "outputPorts")
        if not ports:
            return

        mapped_ports = []
        for port in ports:
            if not isinstance(port, dict):
                continue
            mapped = self._map_single_port(port)
            if mapped:
                mapped_ports.append(mapped)

        if mapped_ports:
            x_odps = hub_contract.setdefault(
                "extensions",
                {},
            ).setdefault("x_odps", {})
            x_odps["output_ports"] = mapped_ports

    def _map_input_ports(
        self,
        contract_data: dict[str, Any],
        hub_contract: dict[str, Any],
        warnings: list[str],
    ) -> None:
        """Bitol ``inputPorts`` METADATA only.

        Phase 227 Wave 1 — see :meth:`_map_output_ports` for the
        rationale. The schema/lineage extraction is in the base helper;
        we retain only the per-port custom metadata under
        ``extensions.x_odps.input_ports``.
        """
        ports = self._get_ports(contract_data, "inputPorts")
        if not ports:
            return

        mapped_ports = []
        for port in ports:
            if not isinstance(port, dict):
                continue
            mapped = self._map_single_port(port)
            if mapped:
                mapped_ports.append(mapped)

        if mapped_ports:
            x_odps = hub_contract.setdefault(
                "extensions",
                {},
            ).setdefault("x_odps", {})
            x_odps["input_ports"] = mapped_ports

    @staticmethod
    def _get_ports(
        contract_data: dict[str, Any],
        port_key: str,
    ) -> list | None:
        """
        Extract ports from contract data.

        Ports may be at top level or under ``product``.
        """
        ports = contract_data.get(port_key)
        if isinstance(ports, list):
            return ports
        product = contract_data.get("product", {})
        if isinstance(product, dict):
            ports = product.get(port_key)
            if isinstance(ports, list):
                return ports
        return None

    @staticmethod
    def _map_single_port(port: dict[str, Any]) -> dict[str, Any]:
        """Map a single port dict to normalised form."""
        mapped: dict[str, Any] = {}

        # Core fields
        for key in ("name", "description", "version"):
            if key in port:
                mapped[key] = port[key]

        # contractId → links to ODCS contract UUID
        contract_id = port.get("contractId")
        if contract_id:
            mapped["contract_id"] = contract_id

        # customProperties
        custom_props = port.get("customProperties")
        if isinstance(custom_props, list):
            mapped["custom_properties"] = custom_props
        elif isinstance(custom_props, dict):
            mapped["custom_properties"] = [custom_props]

        # tags
        tags = port.get("tags")
        if isinstance(tags, list):
            mapped["tags"] = tags

        # authoritativeDefinitions
        auth_defs = port.get("authoritativeDefinitions")
        if isinstance(auth_defs, list):
            mapped["authoritative_definitions"] = auth_defs

        # Preserve any extra fields
        known = {
            "name",
            "description",
            "version",
            "contractId",
            "customProperties",
            "tags",
            "authoritativeDefinitions",
        }
        for k, v in port.items():
            if k not in known and k not in mapped:
                mapped[k] = v

        return mapped
