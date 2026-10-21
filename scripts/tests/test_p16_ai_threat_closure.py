"""
P0-16 (close-oss-release-conditions, 1.19) — AI-threat closure pins
(Django-free legs).

The behavioral legs live in the hub battery (real Django/DRF stacks,
scripted third-party transports):
  hub/apps/ml/tests/test_p16_predict_routes_through_run_inference.py
  hub/apps/ml/tests/test_p16_inference_retention.py
  hub/apps/ai/tests/test_p16_llm_settings_guard.py
  hub/apps/marketplace/tests/test_p16_ai_agent_key_encryption.py

This file pins the artifacts those legs depend on: the LLM runbook
exists and states the guard order + the enablement boundary, the
threat-model recording carries all six closures + the
degrade-never-deny accepted-with-rationale, and the four hub pin
files are present (they cannot silently vanish).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

RUNBOOK = REPO_ROOT / "docs/runbooks/llm-settings-surface.md"
THREAT_DOC = REPO_ROOT / "docs/audits/w1112-ai-surface-threat-model-2026-10-16.md"

HUB_PINS = (
    "hub/apps/ml/tests/test_p16_predict_routes_through_run_inference.py",
    "hub/apps/ml/tests/test_p16_inference_retention.py",
    "hub/apps/ai/tests/test_p16_llm_settings_guard.py",
    "hub/apps/marketplace/tests/test_p16_ai_agent_key_encryption.py",
)


def test_llm_runbook_states_the_guard_and_boundary():
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "Fail-closed guard" in text
    assert "Non-TLS URL → key dropped" in text, (
        "the operator-misconfiguration guard must be documented"
    )
    assert "TLS URL + key → enabled" in text, (
        "the ONLY armed shape must be documented"
    )
    assert "dormant" in text.lower()
    assert "secrets manager" in text, (
        "the enablement checklist must route keys through the secrets "
        "manager, never committed files"
    )


def test_threat_model_records_all_six_closures():
    text = THREAT_DOC.read_text(encoding="utf-8")
    for marker in (
        "run_inference` bypass — CLOSED",
        "deployment_id` ownership — CLOSED",
        "raw I/O retention — CLOSED",
        "LLM settings surface — CLOSED",
        "ai-agent` key storage — CLOSED",
        "degrade-never-deny — ACCEPTED WITH RATIONALE",
    ):
        assert marker in text, f"missing closure record: {marker}"


def test_hub_behavioral_pin_files_exist():
    for rel in HUB_PINS:
        assert (REPO_ROOT / rel).is_file(), f"missing hub pin: {rel}"
