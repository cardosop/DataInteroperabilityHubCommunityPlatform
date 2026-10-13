"""check_access_request_order_kwarg.py tests — TDD fixtures, no mocks."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from check_access_request_order_kwarg import collect_violations, main

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _write(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


class TestRules:
    def test_objects_create_with_order_kwarg_is_flagged(self, tmp_path):
        _write(
            tmp_path,
            "hub/apps/marketplace/views.py",
            "AccessRequest.objects.create(tenant_id='t', order=order)\n",
        )
        violations = collect_violations(tmp_path)
        assert violations
        assert any("views.py:1" in v for v in violations)

    def test_direct_constructor_with_order_is_flagged(self, tmp_path):
        _write(tmp_path, "tests/x.py", "ar = AccessRequest(order=order)\n")
        assert collect_violations(tmp_path)

    def test_get_or_create_with_order_is_flagged(self, tmp_path):
        _write(
            tmp_path,
            "hub/apps/x.py",
            "AccessRequest.objects.get_or_create(order=order)\n",
        )
        assert collect_violations(tmp_path)

    def test_new_contract_is_not_flagged(self, tmp_path):
        _write(
            tmp_path,
            "hub/apps/x.py",
            "ar = AccessRequest.objects.create(tenant_id='t')\norder.access_request = ar\n",
        )
        assert collect_violations(tmp_path) == []

    def test_comment_and_string_mentions_are_not_flagged(self, tmp_path):
        _write(
            tmp_path,
            "hub/apps/x.py",
            '# AccessRequest(order=x) is banned\ntext = "AccessRequest(order=x)"\n',
        )
        assert collect_violations(tmp_path) == []

    def test_other_models_order_kwarg_is_not_flagged(self, tmp_path):
        _write(
            tmp_path,
            "hub/apps/x.py",
            "PaymentTransaction.objects.create(order=order)\n"
            "Entitlement.objects.create(order=order)\n",
        )
        assert collect_violations(tmp_path) == []


class TestRealRepo:
    def test_real_repo_is_clean(self):
        """After the 2.2 fixes, zero AccessRequest(order=) sites remain."""
        assert main(["--root", str(REPO_ROOT)]) == 0
