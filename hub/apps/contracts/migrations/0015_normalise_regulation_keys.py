"""
Migration 0015 — Phase 19.15.1 (data)

Normalise regulation keys stored in
  Contract.hub_contract_json["privacy_compliance"]["jurisdictions"]

Any legacy/variant key found in _REGULATION_KEY_ALIASES is replaced with its
canonical form so that every stored contract uses the same canonical key set
as the compliance-service regulations package.

Examples of replacements:
  "PIPL"      → "PIPL_CN"
  "PIPL_CHINA"→ "PIPL_CN"
  "CCPA_CPRA" → "CCPA"
  "CCPA/CPRA" → "CCPA"
  "PRIVACY_ACT" → "PRIVACY_ACT_AU"

Properties
----------
• Idempotent — re-running produces no change: canonical keys are never in the
  alias map, so a second pass leaves every row unchanged.
• Atomic — Django wraps the whole migration in a transaction (atomic = True).
• Bulk-updated — changed rows are batched in a single bulk_update call for
  efficiency; no per-row SQL.
• Self-contained — the alias dict is inlined rather than imported from live
  app code so the migration is stable even after the source dict changes.
• Reverse — no-op (normalisation is one-directional; original aliases are
  intentionally discarded).
"""

from django.db import migrations

# ---------------------------------------------------------------------------
# Alias map — mirrored from hub.apps.compliance.contract_integration.
# Inlined here so this migration is independent of live code that may change
# after the migration is recorded in the database.
# ---------------------------------------------------------------------------
_REGULATION_KEY_ALIASES: dict[str, str] = {
    # APAC
    "PIPL": "PIPL_CN",
    "PIPL_CHINA": "PIPL_CN",
    # Americas
    "CCPA_CPRA": "CCPA",
    "CCPA/CPRA": "CCPA",
    # APAC — Australia
    "PRIVACY_ACT": "PRIVACY_ACT_AU",
}


def normalise_regulation_keys(apps, schema_editor):
    """
    For every Contract whose hub_contract_json contains a
    privacy_compliance.jurisdictions list, replace any alias key with its
    canonical form.

    Only rows that require changes are added to the bulk_update batch, so
    re-running this function on an already-normalised database produces zero
    SQL UPDATE statements (fully idempotent).
    """
    Contract = apps.get_model("contracts", "Contract")

    to_update = []

    # Only load rows that have non-null hub_contract_json to avoid fetching
    # the entire contracts table when most rows may already be clean.
    qs = Contract.objects.filter(
        hub_contract_json__isnull=False
    ).only("id", "hub_contract_json")

    for contract in qs.iterator(chunk_size=500):
        hub_json = contract.hub_contract_json
        if not isinstance(hub_json, dict):
            continue

        privacy = hub_json.get("privacy_compliance")
        if not isinstance(privacy, dict):
            continue

        jurisdictions = privacy.get("jurisdictions")
        if not isinstance(jurisdictions, list) or not jurisdictions:
            continue

        # Build the normalised list.
        normalised = [_REGULATION_KEY_ALIASES.get(j, j) for j in jurisdictions]

        # Skip rows where nothing actually changes (idempotency check).
        if normalised == jurisdictions:
            continue

        # Mutate the in-memory copy; Django's JSONField tracks reassignment.
        import copy
        updated_json = copy.deepcopy(hub_json)
        updated_json["privacy_compliance"]["jurisdictions"] = normalised
        contract.hub_contract_json = updated_json
        to_update.append(contract)

    if to_update:
        Contract.objects.bulk_update(to_update, ["hub_contract_json"])


class Migration(migrations.Migration):

    # The whole migration runs inside one database transaction (Django default
    # for schema migrations).  Data migrations share that transaction so a
    # mid-migration crash leaves the database unchanged.
    atomic = True

    dependencies = [
        ("contracts", "0014_contract_search_vector"),
    ]

    operations = [
        migrations.RunPython(
            normalise_regulation_keys,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
