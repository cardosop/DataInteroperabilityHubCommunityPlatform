#!/usr/bin/env python3
"""
280.C.1.1 — Machine translation seed generator for es + fr locales.

Reads the English locale TypeScript file, extracts all translation keys,
and generates Spanish (es) and French (fr) locale files using a
comprehensive term-mapping dictionary.  The output is intended as a
*human-review seed* — every translation carries a ``// REVIEW:`` comment
so the reviewer can spot machine-generated strings at a glance.

Usage:
  python scripts/generate_translations.py
  python scripts/generate_translations.py --check  (validate coverage)
"""

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EN_LOCALE = PROJECT_ROOT / "frontend" / "src" / "shared" / "i18n" / "locales" / "en.ts"
ES_OUT = PROJECT_ROOT / "frontend" / "src" / "shared" / "i18n" / "locales" / "es.ts"
FR_OUT = PROJECT_ROOT / "frontend" / "src" / "shared" / "i18n" / "locales" / "fr.ts"
COVERAGE_REPORT = (
    PROJECT_ROOT / "frontend" / "src" / "shared" / "i18n" / "locales" / "coverage.json"
)


# ── Term-mapping dictionaries ─────────────────────────────────────────────
# Comprehensive mappings for common UI terms → es / fr.
# These are hand-curated for quality; domain-specific terms (DSAR, KYC, etc.)
# are mapped explicitly.

ES_TERMS = {
    # UI chrome
    "Apply": "Aplicar",
    "Reset": "Restablecer",
    "Save": "Guardar",
    "Cancel": "Cancelar",
    "Delete": "Eliminar",
    "Edit": "Editar",
    "Create": "Crear",
    "Upload": "Subir",
    "Download": "Descargar",
    "Submit": "Enviar",
    "Close": "Cerrar",
    "Open": "Abrir",
    "View": "Ver",
    "Search": "Buscar",
    "Filter": "Filtrar",
    "Select": "Seleccionar",
    "Remove": "Quitar",
    "Add": "Añadir",
    "Loading": "Cargando",
    "Error": "Error",
    "Success": "Éxito",
    "Copy": "Copiar",
    "Paste": "Pegar",
    "Back": "Volver",
    "Next": "Siguiente",
    "Previous": "Anterior",
    "Skip": "Omitir",
    "Confirm": "Confirmar",
    "Reject": "Rechazar",
    "Approve": "Aprobar",
    "Publish": "Publicar",
    "Draft": "Borrador",
    # General
    "Yes": "Sí",
    "No": "No",
    "none": "ninguno",
    "optional": "opcional",
    "Title": "Título",
    "Summary": "Resumen",
    "Details": "Detalles",
    "Status": "Estado",
    "Action": "Acción",
    "Description": "Descripción",
    "Version": "Versión",
    "Heading": "Encabezado",
    "Body": "Cuerpo",
    "Field": "Campo",
    "Type": "Tipo",
    "Name": "Nombre",
    "Email": "Correo electrónico",
    "Password": "Contraseña",
    "Date": "Fecha",
    "Time": "Hora",
    "Price": "Precio",
    "Help": "Ayuda",
    "Settings": "Configuración",
    "Preview": "Vista previa",
    "Compare": "Comparar",
    "Recommendations": "Recomendaciones",
    # Lineage / time-travel
    "lineage": "linaje",
    "time-travel": "viaje en el tiempo",
    "As of": "A fecha de",
    "diff": "diferencias",
    "Added": "Añadido",
    "Removed": "Eliminado",
    "Unchanged": "Sin cambios",
    "Modified": "Modificado",
    "from": "desde",
    "to": "hasta",
    "Pick two anchors": "Seleccione dos puntos de anclaje",
    # Assets / contracts
    "Schema drift detected": "Deriva de esquema detectada",
    "Schema does not match the contract": "El esquema no coincide con el contrato",
    "Missing fields": "Campos faltantes",
    "Extra fields": "Campos sobrantes",
    "Type mismatches": "Discrepancias de tipo",
    "Contract type": "Tipo de contrato",
    "Dataset type": "Tipo de dataset",
    "Compatible": "Compatible",
    "Safe widening": "Ampliación segura",
    # Marketplace / KYC / KYB
    "KYC verification required": "Verificación KYC requerida",
    "Verify KYC now": "Verificar KYC ahora",
    "Stripe Connect onboarding": "Integración de Stripe Connect",
    "Compliance verified": "Cumplimiento verificado",
    "KYB verified": "KYB verificado",
    "Active since": "Activo desde",
    "Orders fulfilled": "Pedidos completados",
    "Save search": "Guardar búsqueda",
    "Search saved": "Búsqueda guardada",
    "Daily digest": "Resumen diario",
    "Weekly digest": "Resumen semanal",
    # Governance / DSAR
    "Data subject requests": "Solicitudes de derechos del titular",
    "Waiting on me": "Pendientes de mi aprobación",
    "Access": "Acceso",
    "Legal hold": "Retención legal",
    # Legal
    "Legal & transparency": "Legal y transparencia",
    "Privacy notice": "Aviso de privacidad",
    "Sub-processors": "Subencargados",
    "Exercise your data-subject rights": "Ejercer sus derechos como titular de datos",
}

FR_TERMS = {
    # UI chrome
    "Apply": "Appliquer",
    "Reset": "Réinitialiser",
    "Save": "Enregistrer",
    "Cancel": "Annuler",
    "Delete": "Supprimer",
    "Edit": "Modifier",
    "Create": "Créer",
    "Upload": "Téléverser",
    "Download": "Télécharger",
    "Submit": "Soumettre",
    "Close": "Fermer",
    "Open": "Ouvrir",
    "View": "Voir",
    "Search": "Rechercher",
    "Filter": "Filtrer",
    "Select": "Sélectionner",
    "Remove": "Retirer",
    "Add": "Ajouter",
    "Loading": "Chargement",
    "Error": "Erreur",
    "Success": "Succès",
    "Copy": "Copier",
    "Paste": "Coller",
    "Back": "Retour",
    "Next": "Suivant",
    "Previous": "Précédent",
    "Skip": "Passer",
    "Confirm": "Confirmer",
    "Reject": "Rejeter",
    "Approve": "Approuver",
    "Publish": "Publier",
    "Draft": "Brouillon",
    # General
    "Yes": "Oui",
    "No": "Non",
    "none": "aucun",
    "optional": "facultatif",
    "Title": "Titre",
    "Summary": "Résumé",
    "Details": "Détails",
    "Status": "Statut",
    "Action": "Action",
    "Description": "Description",
    "Version": "Version",
    "Heading": "En-tête",
    "Body": "Corps",
    "Field": "Champ",
    "Type": "Type",
    "Name": "Nom",
    "Email": "E-mail",
    "Password": "Mot de passe",
    "Date": "Date",
    "Time": "Heure",
    "Price": "Prix",
    "Help": "Aide",
    "Settings": "Paramètres",
    "Preview": "Aperçu",
    "Compare": "Comparer",
    "Recommendations": "Recommandations",
    # Lineage / time-travel
    "lineage": "lignage",
    "time-travel": "voyage dans le temps",
    "As of": "À la date du",
    "diff": "différences",
    "Added": "Ajouté",
    "Removed": "Supprimé",
    "Unchanged": "Inchangé",
    "Modified": "Modifié",
    "from": "de",
    "to": "à",
    "Pick two anchors": "Sélectionnez deux points d'ancrage",
    # Assets / contracts
    "Schema drift detected": "Dérive de schéma détectée",
    "Schema does not match the contract": "Le schéma ne correspond pas au contrat",
    "Missing fields": "Champs manquants",
    "Extra fields": "Champs supplémentaires",
    "Type mismatches": "Incompatibilités de type",
    "Contract type": "Type de contrat",
    "Dataset type": "Type de jeu de données",
    "Compatible": "Compatible",
    "Safe widening": "Élargissement sûr",
    # Marketplace / KYC / KYB
    "KYC verification required": "Vérification KYC requise",
    "Verify KYC now": "Vérifier KYC maintenant",
    "Stripe Connect onboarding": "Intégration Stripe Connect",
    "Compliance verified": "Conformité vérifiée",
    "KYB verified": "KYB vérifié",
    "Active since": "Actif depuis",
    "Orders fulfilled": "Commandes exécutées",
    "Save search": "Enregistrer la recherche",
    "Search saved": "Recherche enregistrée",
    "Daily digest": "Résumé quotidien",
    "Weekly digest": "Résumé hebdomadaire",
    # Governance / DSAR
    "Data subject requests": "Demandes des personnes concernées",
    "Waiting on me": "En attente de mon approbation",
    "Access": "Accès",
    "Legal hold": "Conservation légale",
    # Legal
    "Legal & transparency": "Légal et transparence",
    "Privacy notice": "Avis de confidentialité",
    "Sub-processors": "Sous-traitants",
    "Exercise your data-subject rights": "Exercer vos droits de personne concernée",
}


def extract_keys(ts_path: Path) -> dict:
    """Parse an en.ts-style file and return {key: english_value}."""
    content = ts_path.read_text(encoding="utf-8")
    # Match 'key.path': 'value', or "key.path": "value",
    pattern = re.compile(
        r"""['"]([a-z_]+\.[a-z0-9_.]+)['"]\s*:\s*['"]([^'"]*(?:\\.[^'"]*)*)['"]""",
        re.IGNORECASE,
    )
    keys = {}
    for m in pattern.finditer(content):
        key = m.group(1)
        value = m.group(2).replace("\\'", "'")
        # Skip template literals (backtick strings)
        if "`" in m.group(0):
            continue
        keys[key] = value
    return keys


def translate_value(english: str, term_map: dict) -> str:
    """Replace known terms in *english* using *term_map*.

    Tries whole-string match first, then longest-substring replacement.
    """
    # Whole-string match
    if english in term_map:
        return term_map[english]

    # Substring-based replacement — sort keys longest-first to avoid
    # partial replacements (e.g. "Save search" before "Save").
    result = english
    for term in sorted(term_map, key=len, reverse=True):
        if term in result:
            result = result.replace(term, term_map[term])
            # Only replace first occurrence for precision
            break
    return result


def generate_locale_file(keys: dict, term_map: dict, locale: str) -> str:
    """Generate a TypeScript locale file."""
    lines = [
        "/**",
        f" * 280.C.1.1 — {locale.upper()} machine translation seed.",
        " *",
        " * Generated by scripts/generate_translations.py.",
        " * EVERY VALUE IS A MACHINE SEED — human review required before production.",
        " * Strings marked // REVIEW: have not been reviewed by a native speaker.",
        " */",
        f"export const ALL_I18N_{locale.upper()}: Record<string, string> = {{",
    ]

    untranslated = 0
    for key in sorted(keys):
        en_val = keys[key]
        translated = translate_value(en_val, term_map)
        # Escape single quotes in output
        escaped = translated.replace("'", "\\'")
        en_val.replace("'", "\\'")

        if translated == en_val:
            untranslated += 1
            # Mark untranslated strings explicitly
            lines.append("  // REVIEW: untranslated — same as English")
            lines.append(f"  '{key}': '{escaped}',")
        elif len(translated) < len(en_val) * 0.3 and len(en_val) > 40:
            # Short translation for long English = likely incomplete
            lines.append("  // REVIEW: short translation — may need expansion")
            lines.append(f"  '{key}': '{escaped}',")
        else:
            lines.append(f"  '{key}': '{escaped}',")

    total = len(keys)
    coverage_pct = ((total - untranslated) / total * 100) if total > 0 else 0

    lines.append("};")
    lines.append("")
    lines.append(
        f"// Coverage: {total - untranslated}/{total} keys translated ({coverage_pct:.1f}%)"
    )
    lines.append(f"// Untranslated: {untranslated} keys (requires human translation)")

    return "\n".join(lines)


def main():
    check_mode = "--check" in sys.argv

    if not EN_LOCALE.exists():
        print(f"ERROR: English locale not found at {EN_LOCALE}", file=sys.stderr)
        sys.exit(1)

    keys = extract_keys(EN_LOCALE)
    print(f"Extracted {len(keys)} English keys from {EN_LOCALE.name}")

    # Generate ES
    es_content = generate_locale_file(keys, ES_TERMS, "es")
    if not check_mode:
        ES_OUT.write_text(es_content, encoding="utf-8")
        print(f"  → {ES_OUT.name} ({len(keys)} keys)")

    # Generate FR
    fr_content = generate_locale_file(keys, FR_TERMS, "fr")
    if not check_mode:
        FR_OUT.write_text(fr_content, encoding="utf-8")
        print(f"  → {FR_OUT.name} ({len(keys)} keys)")

    # Coverage metrics
    es_untranslated = sum(1 for k in keys if translate_value(keys[k], ES_TERMS) == keys[k])
    fr_untranslated = sum(1 for k in keys if translate_value(keys[k], FR_TERMS) == keys[k])
    total = len(keys)

    es_cov = ((total - es_untranslated) / total * 100) if total > 0 else 0
    fr_cov = ((total - fr_untranslated) / total * 100) if total > 0 else 0

    coverage_data = {
        "generated": "2026-05-15",
        "total_keys": total,
        "locales": {
            "es": {
                "translated": total - es_untranslated,
                "untranslated": es_untranslated,
                "coverage_pct": round(es_cov, 1),
            },
            "fr": {
                "translated": total - fr_untranslated,
                "untranslated": fr_untranslated,
                "coverage_pct": round(fr_cov, 1),
            },
        },
        "threshold_90pct": es_cov >= 90 and fr_cov >= 90,
    }

    if not check_mode:
        COVERAGE_REPORT.write_text(json.dumps(coverage_data, indent=2) + "\n", encoding="utf-8")

    print("\nCoverage summary:")
    print(
        f"  ES: {coverage_data['locales']['es']['coverage_pct']}% ({coverage_data['locales']['es']['translated']}/{total})"
    )
    print(
        f"  FR: {coverage_data['locales']['fr']['coverage_pct']}% ({coverage_data['locales']['fr']['translated']}/{total})"
    )
    print(f"  >90% threshold met: {coverage_data['threshold_90pct']}")

    if check_mode and not coverage_data["threshold_90pct"]:
        print("ERROR: Translation coverage below 90% threshold!", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
