#!/usr/bin/env python3
"""
Generate static CLI reference Markdown pages for the 18 MVP command groups.

Reads cli/datahub_cli/_mvp_gates.py to identify post-MVP gated prefixes,
then writes docs/mvpdocs/cli-reference/{group}.md + index.md.

Idempotent: safe to re-run; overwrites existing files.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

# -------------------------------------------------------------------
# Paths
# -------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
MVP_GATES_PATH = (
    REPO_ROOT / "cli" / "datahub_cli" / "_mvp_gates.py"
)
DOCS_DIR = REPO_ROOT / "docs" / "mvpdocs" / "cli-reference"


# -------------------------------------------------------------------
# Parse post-MVP gated prefixes (_mvp_gates.py, no Django needed)
# -------------------------------------------------------------------


def read_gated_prefixes() -> frozenset[str]:
    """Return MVP_GATED_RELATIVE_PREFIXES via AST parsing."""
    source = MVP_GATES_PATH.read_text()
    tree = ast.parse(source, filename=str(MVP_GATES_PATH))
    for node in ast.walk(tree):
        target = None
        value = None
        if isinstance(node, ast.Assign):
            if (
                len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
            ):
                target = node.targets[0]
                value = node.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                target = node.target
                value = node.value

        if (
            target
            and target.id == "MVP_GATED_RELATIVE_PREFIXES"
            and value
        ):
            if (
                isinstance(value, ast.Call)
                and len(value.args) == 1
            ):
                set_node = value.args[0]
                if isinstance(set_node, ast.Set):
                    return frozenset(
                        str(elt.value)
                        for elt in set_node.elts
                        if isinstance(elt, ast.Constant)
                    )
    print(
        "WARNING: could not parse "
        "MVP_GATED_RELATIVE_PREFIXES",
        file=sys.stderr,
    )
    return frozenset()


# -------------------------------------------------------------------
# MVP CLI group definitions
# -------------------------------------------------------------------

CLI_GROUPS: list[dict] = [
    {
        "group": "assets",
        "desc": "Manage data assets (datasets, files, schemas)",
        "subcommands": [
            "list", "get", "create", "update",
            "archive", "publish",
        ],
        "resource": "asset",
        "api_prefix": "assets",
        "class": "Assets",
    },
    {
        "group": "contracts",
        "desc": "Manage and validate data contracts (ODCS/SLA)",
        "subcommands": [
            "list", "get", "create", "validate",
            "lint", "diff",
        ],
        "resource": "contract",
        "api_prefix": "contracts",
        "class": "Contracts",
    },
    {
        "group": "lineage",
        "desc": "Explore data lineage and dependency graphs",
        "subcommands": ["list", "get", "trace", "visualize"],
        "resource": "lineage",
        "api_prefix": "lineage",
        "class": "Lineage",
    },
    {
        "group": "files",
        "desc": (
            "Upload, download and manage files "
            "attached to assets"
        ),
        "subcommands": [
            "list", "get", "upload", "download", "delete",
        ],
        "resource": "file",
        "api_prefix": "files",
        "class": "Files",
    },
    {
        "group": "jobs",
        "desc": "Monitor and control background jobs and tasks",
        "subcommands": [
            "list", "get", "status", "cancel", "logs",
        ],
        "resource": "job",
        "api_prefix": "jobs",
        "class": "Jobs",
    },
    {
        "group": "config",
        "desc": "Read and write CLI and tenant configuration",
        "subcommands": ["get", "set", "list", "reset", "show"],
        "resource": "config",
        "api_prefix": "config",
        "class": "Config",
    },
    {
        "group": "dq",
        "desc": "Run data-quality checks and review results",
        "subcommands": [
            "run", "results", "profiles", "configure",
        ],
        "resource": "dq profile",
        "api_prefix": "dq",
        "class": "DataQuality",
    },
    {
        "group": "compliance",
        "desc": (
            "Scan assets for compliance violations "
            "and review results"
        ),
        "subcommands": [
            "scan", "results", "profiles", "configure",
        ],
        "resource": "compliance",
        "api_prefix": "compliance",
        "class": "Compliance",
    },
    {
        "group": "governance",
        "desc": (
            "Manage governance policies, retention "
            "rules and consent"
        ),
        "subcommands": ["policies", "retention", "consent"],
        "resource": "governance",
        "api_prefix": "governance",
        "class": "Governance",
    },
    {
        "group": "marketplace",
        "desc": (
            "Browse listings, place orders and "
            "manage entitlements"
        ),
        "subcommands": ["listings", "orders", "entitlements"],
        "resource": "marketplace",
        "api_prefix": "marketplace",
        "class": "Marketplace",
    },
    {
        "group": "webhooks",
        "desc": "Register, test and manage webhook endpoints",
        "subcommands": ["list", "create", "test", "delete"],
        "resource": "webhook",
        "api_prefix": "webhooks",
        "class": "Webhooks",
    },
    {
        "group": "audit",
        "desc": "Query and export the audit log",
        "subcommands": ["list", "export", "filter"],
        "resource": "audit entry",
        "api_prefix": "audit",
        "class": "Audit",
    },
    {
        "group": "health",
        "desc": "Check platform health and run diagnostics",
        "subcommands": ["check", "status", "diagnostics"],
        "resource": "health",
        "api_prefix": "health",
        "class": "Health",
    },
    {
        "group": "billing",
        "desc": (
            "View usage, invoices, quotas and "
            "plan details"
        ),
        "subcommands": [
            "usage", "invoices", "quotas", "upgrade",
        ],
        "resource": "billing",
        "api_prefix": "billing",
        "class": "Billing",
    },
    {
        "group": "tenants",
        "desc": (
            "Manage tenants, switch context and "
            "list members"
        ),
        "subcommands": [
            "list", "get", "create", "switch", "members",
        ],
        "resource": "tenant",
        "api_prefix": "tenants",
        "class": "Tenants",
    },
    {
        "group": "gdpr",
        "desc": (
            "GDPR data-subject requests: export, "
            "erase, consent"
        ),
        "subcommands": [
            "export", "erase", "consent", "status",
        ],
        "resource": "GDPR request",
        "api_prefix": "gdpr",
        "class": "GDPR",
    },
    {
        "group": "search",
        "desc": (
            "Full-text and faceted search across "
            "the catalogue"
        ),
        "subcommands": ["query", "suggest", "facets"],
        "resource": "search",
        "api_prefix": "search",
        "class": "Search",
    },
    {
        "group": "semantic",
        "desc": (
            "Semantic layer: resolve terms, "
            "SPARQL queries, browse"
        ),
        "subcommands": ["resolve", "sparql", "browse"],
        "resource": "semantic",
        "api_prefix": "semantic",
        "class": "Semantic",
    },
]

# -------------------------------------------------------------------
# Rendering helpers
# -------------------------------------------------------------------

_SUBCMD_DESCRIPTIONS: dict[str, str] = {
    "list": "List all {r}s",
    "get": "Get {a} {r} by ID",
    "create": "Create a new {r}",
    "update": "Update an existing {r}",
    "delete": "Delete {a} {r}",
    "archive": "Archive {a} {r}",
    "publish": "Publish {a} {r}",
    "validate": "Validate {a} {r} against its schema",
    "lint": "Lint {a} {r} definition",
    "diff": "Diff two {r} versions",
    "trace": "Trace lineage upstream or downstream",
    "visualize": "Render a lineage graph",
    "upload": "Upload {a} {r}",
    "download": "Download {a} {r}",
    "status": "Show current {r} status",
    "cancel": "Cancel a running {r}",
    "logs": "Stream logs for a {r}",
    "set": "Set a configuration value",
    "reset": "Reset configuration to defaults",
    "show": "Show current configuration",
    "run": "Run {a} {r} check",
    "results": "View {r} results",
    "profiles": "Manage {r} profiles",
    "configure": "Configure {r} settings",
    "scan": "Run {a} {r} scan",
    "policies": "Manage governance policies",
    "retention": "Manage retention rules",
    "consent": "Manage consent records",
    "listings": "Browse marketplace listings",
    "orders": "Manage marketplace orders",
    "entitlements": "View and manage entitlements",
    "test": "Send a test event to {a} {r}",
    "export": "Export {r} data",
    "filter": "Filter {r} entries",
    "check": "Run a health check",
    "diagnostics": "Run platform diagnostics",
    "usage": "View current usage metrics",
    "invoices": "List invoices",
    "quotas": "View quota limits and consumption",
    "upgrade": "Upgrade the current plan",
    "switch": "Switch active {r}",
    "members": "List {r} members",
    "erase": "Submit an erasure request",
    "query": "Run a search query",
    "suggest": "Get search suggestions",
    "facets": "List available search facets",
    "resolve": "Resolve a semantic term",
    "sparql": "Execute a SPARQL query",
    "browse": "Browse the semantic layer",
}


def _article(noun: str) -> str:
    """Return 'an' or 'a' depending on the noun."""
    return "an" if noun[0].lower() in "aeiou" else "a"


def _subcmd_desc(sub: str, resource: str) -> str:
    """Return a one-line description for a subcommand."""
    tpl = _SUBCMD_DESCRIPTIONS.get(sub, "Run {r}")
    return tpl.format(r=resource, a=_article(resource))


def render_group_page(grp: dict) -> str:
    """Return the full Markdown for one CLI group page."""
    g = grp["group"]
    desc = grp["desc"]
    resource = grp["resource"]
    api_prefix = grp["api_prefix"]
    cls = grp["class"]

    rows = "\n".join(
        f"| `{g} {s}` | {_subcmd_desc(s, resource)} |"
        for s in grp["subcommands"]
    )

    first_sub = grp["subcommands"][0]
    id_sub = (
        "get"
        if "get" in grp["subcommands"]
        else grp["subcommands"][-1]
    )

    return (
        f"# datahub {g}\n"
        f"\n"
        f"{desc}.\n"
        f"\n"
        f"## Synopsis\n"
        f"\n"
        f"```\n"
        f"datahub {g} [OPTIONS] COMMAND [ARGS]...\n"
        f"```\n"
        f"\n"
        f"## Subcommands\n"
        f"\n"
        f"| Command | Description |\n"
        f"|---------|-------------|\n"
        f"{rows}\n"
        f"\n"
        f"## Common Options\n"
        f"\n"
        f"| Flag | Description |\n"
        f"|------|-------------|\n"
        f"| `--format json\\|table\\|yaml`"
        f" | Output format (default: table) |\n"
        f"| `--tenant <slug>`"
        f" | Tenant context override |\n"
        f"| `-v, --verbose` | Verbose output |\n"
        f"| `--no-color`"
        f" | Disable coloured output |\n"
        f"| `--timeout <seconds>`"
        f" | Request timeout (default: 30) |\n"
        f"\n"
        f"## Exit Codes\n"
        f"\n"
        f"| Code | Meaning |\n"
        f"|------|---------|\n"
        f"| 0 | Success |\n"
        f"| 1 | General error |\n"
        f"| 2 | Invalid arguments |\n"
        f"| 3 | Authentication failure |\n"
        f"| 4 | Resource not found |\n"
        f"\n"
        f"## Examples\n"
        f"\n"
        f"```bash\n"
        f"# {_subcmd_desc(first_sub, resource)}\n"
        f"datahub {g} {first_sub} --format json\n"
        f"\n"
        f"# {_subcmd_desc(id_sub, resource)}\n"
        f"datahub {g} {id_sub} <id>\n"
        f"\n"
        f"# Use verbose output with a specific tenant\n"
        f"datahub {g} {first_sub}"
        f" --tenant acme --verbose\n"
        f"```\n"
        f"\n"
        f"## Related\n"
        f"\n"
        f"- API: [`/api/v1/{api_prefix}/`]"
        f"(../api-reference/{api_prefix}.md)\n"
        f"- SDK: [`{cls}API`]"
        f"(../sdk-reference/python/{cls.lower()}.md)\n"
    )


def render_index(
    groups: list[dict],
    gated_prefixes: frozenset[str],
) -> str:
    """Return the index.md content listing all MVP groups."""
    rows = "\n".join(
        f"| [`datahub {g['group']}`]"
        f"({g['group']}.md) | {g['desc']} |"
        for g in groups
    )

    gated_list = ", ".join(
        f"`{p.rstrip('/')}`" for p in sorted(gated_prefixes)
    )

    return (
        "# CLI Reference\n"
        "\n"
        "Complete reference for the **datahub** CLI"
        " (MVP release).\n"
        "\n"
        "## Command Groups\n"
        "\n"
        "| Group | Description |\n"
        "|-------|-------------|\n"
        f"{rows}\n"
        "\n"
        "## Global Options\n"
        "\n"
        "These flags are available on every command:\n"
        "\n"
        "| Flag | Description |\n"
        "|------|-------------|\n"
        "| `--format json\\|table\\|yaml`"
        " | Output format (default: table) |\n"
        "| `--tenant <slug>`"
        " | Tenant context override |\n"
        "| `-v, --verbose` | Verbose output |\n"
        "| `--no-color`"
        " | Disable coloured output |\n"
        "| `--timeout <seconds>`"
        " | Request timeout (default: 30) |\n"
        "| `--version`"
        " | Show CLI version and exit |\n"
        "| `--help` | Show help and exit |\n"
        "\n"
        "## Post-MVP (Gated) Features\n"
        "\n"
        "The following API prefixes are gated in MVP mode"
        " and not yet exposed\n"
        f"through the CLI: {gated_list}.\n"
        "\n"
        "These will be enabled in a future release."
        " Attempting to reach a gated\n"
        "endpoint returns error code"
        " `MVP_FEATURE_GATED`.\n"
    )


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------


def main() -> None:
    """Generate all CLI reference docs."""
    gated = read_gated_prefixes()
    print(
        f"Parsed {len(gated)} gated prefixes "
        f"from {MVP_GATES_PATH.name}"
    )

    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    for grp in CLI_GROUPS:
        path = DOCS_DIR / f"{grp['group']}.md"
        path.write_text(render_group_page(grp))
        print(f"  wrote {path.relative_to(REPO_ROOT)}")

    index_path = DOCS_DIR / "index.md"
    index_path.write_text(render_index(CLI_GROUPS, gated))
    print(f"  wrote {index_path.relative_to(REPO_ROOT)}")

    print(f"Done -- {len(CLI_GROUPS)} group pages + index.md")


if __name__ == "__main__":
    main()
