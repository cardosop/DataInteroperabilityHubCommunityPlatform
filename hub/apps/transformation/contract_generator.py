"""
285.9.2.1.1 — DbtContractGenerator: dbt model YAML / catalog.json → HubContract JSON.

Parses dbt model schema YAML (``models/*.yml``) and/or ``catalog.json``
(from ``dbt docs generate``) and produces a HubContract-compatible JSON
dict suitable for storage in ``Contract.hub_contract_json``.

Sources:
  - ``models/*.yml`` → column names, descriptions, tests (constraints)
  - ``catalog.json`` → column types (from warehouse introspection)

When both sources are available, the catalog types enrich the YAML
definitions.  Columns present in YAML but missing from the catalog
emit a warning and default to ``type: null``.
"""
from __future__ import annotations
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

# dbt test name → HubContract constraint mapping.
_TEST_TO_CONSTRAINT: Dict[str, str] = {
    "unique": "is_unique",
    "not_null": "is_not_null",
}


class DbtContractGeneratorError(Exception):
    """Raised when contract generation fails — missing files, malformed
    YAML, empty models list."""


class DbtContractGenerator:
    """Generate HubContract JSON from dbt model definitions.

    Two primary entry points:

    - ``generate_from_yaml(schema_yml_path, catalog_path=None)`` —
      parse a single ``schema.yml`` file, optionally enriched with
      ``catalog.json`` column types.
    - ``generate_from_catalog(catalog_dict, model_names)`` —
      build a contract purely from ``catalog.json`` data (no YAML
      descriptions or tests).

    The returned dict is compatible with ``Contract.hub_contract_json``::

        {
            "schema": {
                "fields": [
                    {"name": "customer_id", "type": "integer",
                     "description": "Primary key",
                     "is_primary_key": true, "is_unique": true,
                     "is_not_null": true},
                    ...
                ],
                "primary_key": ["customer_id"],
            },
            "info": {"title": "...", "description": "..."},
        }
    """

    # ── Public API ────────────────────────────────────────────────────

    def generate_from_yaml(
        self,
        schema_yml_path: str,
        catalog_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Parse a dbt ``schema.yml`` file and return a HubContract dict.

        Args:
            schema_yml_path: Path to ``models/schema.yml``.
            catalog_path: Optional path to ``target/catalog.json`` for
                column type enrichment.

        Returns:
            HubContract JSON-compatible dict.
        """
        models = self._parse_models_yaml(schema_yml_path)

        # Build per-model catalog lookups if available.
        catalog_columns: Dict[str, Dict[str, Dict[str, Any]]] = {}
        if catalog_path:
            for model in models:
                cols = self._extract_catalog_columns(
                    catalog_path, model_name=model["name"]
                )
                if cols:
                    catalog_columns[model["name"]] = cols

        all_fields: List[Dict[str, Any]] = []
        primary_keys: List[str] = []
        descriptions: List[str] = []

        for model in models:
            model_name = model["name"]
            cat_cols = catalog_columns.get(model_name, {})

            if model.get("description"):
                descriptions.append(f"{model_name}: {model['description']}")

            for col in model["columns"]:
                field: Dict[str, Any] = {
                    "name": col["name"],
                    "type": None,
                    "description": col.get("description", ""),
                }

                # Enrich with catalog type if available.
                if col["name"] in cat_cols:
                    field["type"] = cat_cols[col["name"]].get("type")
                elif catalog_path:
                    # Column in YAML but not in catalog — warn.
                    logger.warning(
                        "Column '%s' in model '%s' not found in catalog.json "
                        "— type will be null",
                        col["name"],
                        model_name,
                    )

                # Map dbt tests to constraints.
                for test in col.get("tests", []):
                    constraint = _TEST_TO_CONSTRAINT.get(test)
                    if constraint:
                        field[constraint] = True

                # Detect primary key: unique + not_null on same column.
                if field.get("is_unique") and field.get("is_not_null"):
                    field["is_primary_key"] = True
                    if col["name"] not in primary_keys:
                        primary_keys.append(col["name"])

                all_fields.append(field)

        return {
            "schema": {
                "fields": all_fields,
                "primary_key": primary_keys,
            },
            "info": {
                "title": self._infer_dataset_name(schema_yml_path),
                "description": "; ".join(descriptions) if descriptions else "",
            },
        }

    def generate_from_catalog(
        self,
        catalog: Dict[str, Any],
        model_names: Optional[List[str]] = None,
        dataset_name: str = "",
    ) -> Dict[str, Any]:
        """Build a HubContract from raw ``catalog.json`` data.

        Args:
            catalog: Parsed catalog.json dict (as returned by
                ``json.load``).
            model_names: Optional list of model names to include.  When
                ``None``, all models in the catalog are used.
            dataset_name: Human-readable dataset name for the ``info``
                section.

        Returns:
            HubContract JSON-compatible dict.
        """
        nodes = catalog.get("nodes", {})
        if model_names is None:
            model_names = []

        fields: List[Dict[str, Any]] = []
        primary_keys: List[str] = []

        for node_id, node in nodes.items():
            node_name = node.get("name", node_id)
            if model_names and node_name not in model_names:
                continue

            for col_name, col_info in node.get("columns", {}).items():
                field = {
                    "name": col_name,
                    "type": col_info.get("type"),
                    "description": col_info.get("comment", ""),
                }
                fields.append(field)

        return {
            "schema": {
                "fields": fields,
                "primary_key": primary_keys,
            },
            "info": {
                "title": dataset_name or "dbt_catalog",
                "description": f"Generated from dbt catalog ({len(fields)} columns)",
            },
        }

    def generate_from_models_dir(
        self,
        models_dir: str,
        catalog_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Scan ``models/`` for ``*.yml`` schema files and merge them
        into a single HubContract.

        Args:
            models_dir: Path to the dbt ``models/`` directory.
            catalog_path: Optional path to ``target/catalog.json``.

        Returns:
            HubContract JSON-compatible dict.
        """
        yml_files = sorted(Path(models_dir).glob("*.yml"))
        if not yml_files:
            raise DbtContractGeneratorError(
                f"No YAML schema files found in {models_dir}"
            )

        all_fields: List[Dict[str, Any]] = []
        all_primary_keys: List[str] = []
        all_descriptions: List[str] = []

        for yml_path in yml_files:
            contract = self.generate_from_yaml(str(yml_path), catalog_path=catalog_path)
            all_fields.extend(contract["schema"]["fields"])
            all_primary_keys.extend(contract["schema"]["primary_key"])
            desc = contract["info"].get("description", "")
            if desc:
                all_descriptions.append(desc)

        return {
            "schema": {
                "fields": all_fields,
                "primary_key": sorted(set(all_primary_keys)),
            },
            "info": {
                "title": self._infer_dataset_name(models_dir),
                "description": "; ".join(all_descriptions) if all_descriptions else "",
            },
        }

    # ── Static parsing helpers ────────────────────────────────────────

    @staticmethod
    def _parse_models_yaml(schema_yml_path: str) -> List[Dict[str, Any]]:
        """Parse a dbt schema.yml file into a list of model dicts.

        Each returned dict has:
          - ``name`` (str)
          - ``description`` (str, empty if missing)
          - ``columns`` (list of {name, description, tests})
        """
        if not os.path.isfile(schema_yml_path):
            raise DbtContractGeneratorError(
                f"Schema file not found: {schema_yml_path}"
            )

        try:
            with open(schema_yml_path) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise DbtContractGeneratorError(
                f"Failed to parse YAML in {schema_yml_path}: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise DbtContractGeneratorError(
                f"Schema file {schema_yml_path} must contain a YAML mapping"
            )

        models_raw = data.get("models", [])
        if not models_raw:
            raise DbtContractGeneratorError(
                f"No models found in {schema_yml_path}"
            )

        models: List[Dict[str, Any]] = []
        for m in models_raw:
            if "name" not in m:
                raise DbtContractGeneratorError(
                    f"Model in {schema_yml_path} is missing required 'name' field"
                )
            columns: List[Dict[str, Any]] = []
            for c in m.get("columns", []):
                if "name" not in c:
                    raise DbtContractGeneratorError(
                        f"Column in model '{m['name']}' is missing required 'name' field"
                    )
                columns.append({
                    "name": c["name"],
                    "description": c.get("description", ""),
                    "tests": c.get("tests", []),
                })
            models.append({
                "name": m["name"],
                "description": m.get("description", ""),
                "columns": columns,
            })

        return models

    @staticmethod
    def _extract_catalog_columns(
        catalog_path: str, model_name: str
    ) -> Dict[str, Dict[str, Any]]:
        """Extract column name → {type} mapping from catalog.json for a
        specific model.

        dbt catalog.json stores columns under:
        ``nodes["model.<project>.<name>"]["columns"]``

        Returns an empty dict when the file is missing, unparseable, or
        the model is not found.
        """
        if not os.path.isfile(catalog_path):
            logger.debug("catalog_not_found path=%s", catalog_path)
            return {}

        try:
            with open(catalog_path) as f:
                catalog = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "catalog_unparseable path=%s error=%s", catalog_path, str(exc)
            )
            return {}

        nodes = catalog.get("nodes", {})
        # dbt unique_id format: model.<project>.<name>
        for node_id, node in nodes.items():
            node_name = node.get("name", "")
            if node_name == model_name:
                columns = node.get("columns", {})
                return {
                    col_name: {"type": col_info.get("type")}
                    for col_name, col_info in columns.items()
                }

        logger.debug(
            "model_not_in_catalog model_name=%s path=%s", model_name, catalog_path
        )
        return {}

    @staticmethod
    def _infer_dataset_name(path: str) -> str:
        """Infer a dataset name from the project directory path."""
        # Walk up from the schema.yml to find dbt_project.yml
        current = Path(path).resolve()
        for _ in range(5):
            if current.is_dir():
                project_yml = current / "dbt_project.yml"
            else:
                current = current.parent
                continue

            if project_yml.exists():
                try:
                    with open(project_yml) as f:
                        proj = yaml.safe_load(f)
                    if isinstance(proj, dict) and proj.get("name"):
                        return str(proj["name"])
                except Exception:
                    pass
            current = current.parent

        return "dbt_models"
