"""
285.9.2.2.1 — DbtModelScaffolder: HubContract JSON → dbt model files.

Generates dbt model SQL (SELECT + CAST), model YAML (columns, descriptions,
tests), and ``dbt_project.yml`` stub from a HubContract JSON definition.

Supports both HubContract canonical keys (``data_type``, ``nullable``,
``enum``) and the contract_generator's simplified keys (``type``,
``is_not_null``) for seamless interop between code-first and
contract-first flows.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional


class DbtModelScaffolder:
    """Generate dbt project files from a HubContract JSON definition.

    Entry points:
      - ``scaffold_all(contract, project_name, ...)`` → dict with
        ``model.sql``, ``model.yml``, ``dbt_project.yml``.
      - Static helpers ``_generate_sql``, ``_generate_yaml``,
        ``_generate_project_yml`` for single-file generation.
    """

    # ── Public API ────────────────────────────────────────────────────

    def scaffold_all(
        self,
        contract: Dict[str, Any],
        project_name: str = "dbt_project",
        source_name: str = "raw",
        table_name: Optional[str] = None,
        profile: str = "meshant_dbt",
        materialized: str = "table",
    ) -> Dict[str, str]:
        """Generate all three dbt scaffold files from a HubContract.

        Args:
            contract: HubContract JSON dict.
            project_name: Name for the dbt project.
            source_name: dbt source name for the FROM clause.
            table_name: Override table name (default: contract title).
            profile: dbt profile name.
            materialized: dbt materialization strategy.

        Returns:
            ``{"model.sql": ..., "model.yml": ..., "dbt_project.yml": ...}``
        """
        return {
            "model.sql": self._generate_sql(
                contract, source_name=source_name, table_name=table_name
            ),
            "model.yml": self._generate_yaml(contract),
            "dbt_project.yml": self._generate_project_yml(
                project_name, profile=profile, materialized=materialized
            ),
        }

    # ── Static generators ─────────────────────────────────────────────

    @staticmethod
    def _generate_sql(
        contract: Dict[str, Any],
        source_name: str = "raw",
        table_name: Optional[str] = None,
    ) -> str:
        """Generate a dbt model ``.sql`` file with SELECT + CAST.

        Primary key columns are emitted first, followed by non-PK columns
        in definition order.  Columns with a ``data_type`` or ``type`` get
        a ``CAST(source.<col> AS <type>)``; columns without a type are
        emitted as bare ``source.<col>`` references.
        """
        schema = contract.get("schema", {})
        fields: List[Dict[str, Any]] = schema.get("fields", [])
        primary_keys: List[str] = schema.get("primary_key", [])
        title = contract.get("info", {}).get("title", "model")
        effective_table = table_name or title

        if not fields:
            return (
                f"-- No schema fields defined\n"
                f"SELECT * FROM {{{{ source('{source_name}', '{effective_table}') }}}}\n"
            )

        # PK columns first, then non-PK in definition order.
        pk_fields = [f for f in fields if f.get("name") in primary_keys]
        non_pk_fields = [f for f in fields if f.get("name") not in primary_keys]
        ordered = pk_fields + non_pk_fields

        lines: List[str] = []
        for f in ordered:
            name = f.get("name", "unknown")
            dtype = f.get("data_type") or f.get("type")
            if dtype:
                lines.append(
                    f"    CAST(source.{name} AS {dtype}) AS {name}"
                )
            else:
                lines.append(f"    source.{name}")

        columns = ",\n".join(lines)
        return (
            f"SELECT\n"
            f"{columns}\n"
            f"FROM {{{{ source('{source_name}', '{effective_table}') }}}}\n"
        )

    @staticmethod
    def _generate_yaml(contract: Dict[str, Any]) -> str:
        """Generate a dbt model ``.yml`` schema file with columns,
        descriptions, and tests.

        Constraint mapping:
          - ``is_primary_key`` / ``is_unique`` → ``unique`` test
          - ``is_not_null`` / ``nullable: false`` → ``not_null`` test
          - ``enum`` → ``accepted_values`` test
        """
        import yaml

        schema = contract.get("schema", {})
        fields: List[Dict[str, Any]] = schema.get("fields", [])
        info = contract.get("info", {})
        title = info.get("title", "model")
        description = info.get("description", "")

        columns: List[Dict[str, Any]] = []
        for f in fields:
            col: Dict[str, Any] = {
                "name": f.get("name", "unknown"),
                "description": f.get("description", ""),
            }

            tests: List[Any] = []
            is_pk = f.get("is_primary_key", False)
            is_unique = f.get("is_unique", False)
            is_not_null = f.get("is_not_null", False)
            nullable = f.get("nullable", True)

            if is_pk or is_unique:
                tests.append("unique")
            if is_pk or is_not_null or not nullable:
                if "not_null" not in tests:
                    tests.append("not_null")

            # enum → accepted_values test
            enum_values = f.get("enum")
            if enum_values:
                tests.append({
                    "accepted_values": {"values": list(enum_values)}
                })

            col["tests"] = tests
            columns.append(col)

        model_yaml = {
            "version": 2,
            "models": [
                {
                    "name": title,
                    "description": description,
                    "columns": columns,
                }
            ],
        }
        return yaml.dump(model_yaml, default_flow_style=False, sort_keys=False)

    @staticmethod
    def _generate_project_yml(
        project_name: str,
        profile: str = "meshant_dbt",
        materialized: str = "table",
    ) -> str:
        """Generate a ``dbt_project.yml`` stub.

        Args:
            project_name: dbt project name.
            profile: dbt profile name for warehouse connection.
            materialized: Default materialization (table, view, etc.).
        """
        import yaml

        project = {
            "name": project_name,
            "version": "1.0.0",
            "config-version": 2,
            "profile": profile,
            "model-paths": ["models"],
            "analysis-paths": ["analyses"],
            "test-paths": ["tests"],
            "macro-paths": ["macros"],
            "snapshot-paths": ["snapshots"],
            "target-path": "target",
            "clean-targets": ["target", "dbt_packages"],
            "models": {
                project_name: {
                    "+materialized": materialized,
                }
            },
        }
        return yaml.dump(project, default_flow_style=False, sort_keys=False)
