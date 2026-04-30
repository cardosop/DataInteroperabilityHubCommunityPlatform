"""
Phase 227 L10 audit-3 — ``INVALID_YAML`` wire-code emission.

Pre-audit: the error catalog
(``docs/mvpdocs/reference/error-codes.md``) and the OpenAPI snapshot
(``views.py:create``/``update`` ``@extend_schema`` annotations) both
documented ``INVALID_YAML`` as a real wire code, but the runtime never
emitted it — every YAML parse error was bucketed as
``NORMALIZATION_FAILED``. SDK consumers branching on
``error.code == "INVALID_YAML"`` would never hit the branch. The fix
threads a typed ``InvalidYAMLError`` from
:func:`hub.apps.contracts.normalization_engine.parse_contract` through
the engine's normalisation tuple via the ``INVALID_YAML:`` discriminator
prefix; the service layer detects the prefix and raises
``ValidationError(details={"code": "INVALID_YAML", ...})``.

These tests pin the wire-level contract end-to-end:

* Engine layer: ``parse_contract`` raises the typed
  ``InvalidYAMLError`` on malformed YAML.
* Engine layer: ``normalize_contract`` propagates the typed error
  through the ``errors[]`` tuple slot with the
  ``INVALID_YAML:`` prefix the service layer recognises.
* Service layer: ``ContractService.create_contract`` raises
  ``ValidationError(code="INVALID_YAML")`` instead of
  ``NORMALIZATION_FAILED``.
* Service layer: a syntactically valid but structurally empty YAML
  (``"---"``) does NOT trigger ``INVALID_YAML`` — that's the
  structural-floor's job.
"""
from __future__ import annotations

import uuid

import pytest
import yaml
from django.test import TestCase

from hub.apps.contracts.normalization_engine import (
    INVALID_YAML_ERROR_PREFIX,
    InvalidYAMLError,
    normalize_contract,
    parse_contract,
)


def _unique_tenant():
    from hub.apps.tenants.models import Tenant

    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"L10-Audit3-Co {suffix}",
        slug=f"l10-audit3-co-{suffix}",
    )


# ---------------------------------------------------------------------------
# Engine layer
# ---------------------------------------------------------------------------


class TestParseContractRaisesInvalidYAMLError:
    """``parse_contract`` raises the typed wrapper on malformed YAML."""

    def test_unclosed_bracket_raises_typed(self):
        bad_yaml = """
        product:
          outputPorts: [unclosed
        """
        with pytest.raises(InvalidYAMLError) as exc:
            parse_contract(bad_yaml, "YAML")
        # Original yaml.YAMLError is preserved on .original.
        assert isinstance(exc.value.original, yaml.YAMLError)

    def test_unsafe_python_object_tag_raises_typed(self):
        # ``!!python/object/apply:os.system`` would be RCE under
        # ``yaml.load`` but ``safe_load`` rejects it via
        # ``ConstructorError`` (a YAMLError subclass).
        unsafe = "key: !!python/object/apply:os.system ['echo pwned']"
        with pytest.raises(InvalidYAMLError) as exc:
            parse_contract(unsafe, "YAML")
        assert isinstance(exc.value.original, yaml.YAMLError)

    def test_well_formed_yaml_does_not_raise(self):
        ok = "product:\n  details:\n    en:\n      name: x"
        result = parse_contract(ok, "YAML")
        assert result["product"]["details"]["en"]["name"] == "x"


class TestNormalizeContractMarksInvalidYAMLInErrors:
    """The engine's ``normalize_contract`` returns the discriminator
    prefix in the errors list rather than re-raising — preserving the
    fixed 6-tuple return shape every existing caller expects."""

    def test_invalid_yaml_yields_discriminator_prefix(self):
        bad_yaml = "outputPorts: [unclosed"
        result = normalize_contract(bad_yaml, "YAML")
        # 6-tuple: (hub_contract, spec_type, spec_version, status, errors, warnings)
        hub_contract, _, _, status, errors, _ = result
        assert hub_contract is None
        assert status.value == "NORMALIZATION_FAILED" or str(status) == "NORMALIZATION_FAILED"
        assert any(
            isinstance(err, str) and err.startswith(INVALID_YAML_ERROR_PREFIX)
            for err in errors
        ), f"expected ``{INVALID_YAML_ERROR_PREFIX}`` prefix in {errors!r}"

    def test_well_formed_but_unknown_spec_does_not_yield_invalid_yaml_prefix(self):
        # Valid YAML that just lacks the expected ODCS/ODPS structure —
        # should NOT carry the INVALID_YAML prefix.
        ok = "totally: unrelated\nshape: here"
        result = normalize_contract(ok, "YAML")
        _, _, _, _, errors, _ = result
        assert not any(
            isinstance(err, str) and err.startswith(INVALID_YAML_ERROR_PREFIX)
            for err in errors
        )


# ---------------------------------------------------------------------------
# Service layer (end-to-end)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestContractServiceEmitsInvalidYAMLWireCode(TestCase):
    """The catalog-promised ``INVALID_YAML`` reaches the API consumer."""

    def _service(self, tenant):
        from hub.apps.contracts.services import ContractService
        return ContractService(tenant_id=str(tenant.id))

    def test_malformed_yaml_raises_invalid_yaml_not_normalization_failed(self):
        from hub.apps.core.services.base import ValidationError

        tenant = _unique_tenant()
        bad_yaml = """
        kind: DataContract
        apiVersion: v3.0.2
        id: x
        name: x
        version: 1.0.0
        status: active
        schema:
          - name: m
            fields: [unclosed
        """
        with pytest.raises(ValidationError) as exc:
            self._service(tenant).create_contract(
                original_raw=bad_yaml,
                original_format="YAML",
                original_spec_type="ODCS",
            )
        # Typed wire code; SDK consumers branch on this.
        details = exc.value.details or {}
        assert details.get("code") == "INVALID_YAML", (
            f"expected wire code INVALID_YAML, got {details.get('code')!r}; "
            f"full details={details!r}"
        )

    def test_unsafe_yaml_python_object_tag_raises_invalid_yaml(self):
        """The ``!!python/object/apply:os.system`` payload from
        ``test_yaml_safety.py`` reaches the contract-create boundary
        as ``INVALID_YAML``, not as an unhandled exception."""
        from hub.apps.core.services.base import ValidationError

        tenant = _unique_tenant()
        unsafe = "key: !!python/object/apply:os.system ['echo pwned']"
        with pytest.raises(ValidationError) as exc:
            self._service(tenant).create_contract(
                original_raw=unsafe,
                original_format="YAML",
                original_spec_type="ODCS",
            )
        details = exc.value.details or {}
        assert details.get("code") == "INVALID_YAML", details

    def test_empty_yaml_does_not_raise_invalid_yaml(self):
        """A bare ``---`` is valid YAML that parses to None — that's a
        normalisation/structural problem, not an INVALID_YAML one."""
        from hub.apps.core.services.base import ValidationError

        tenant = _unique_tenant()
        with pytest.raises(ValidationError) as exc:
            self._service(tenant).create_contract(
                original_raw="---\n",
                original_format="YAML",
                original_spec_type="ODCS",
            )
        details = exc.value.details or {}
        assert details.get("code") != "INVALID_YAML", (
            "Empty/null YAML must NOT be classified as INVALID_YAML — "
            "the YAML parsed cleanly. The code should be "
            "STRUCTURELESS_CONTRACT or NORMALIZATION_FAILED."
        )

    def test_well_formed_structureless_yaml_keeps_structureless_code(self):
        """Phase 227's existing ``STRUCTURELESS_CONTRACT`` path must
        not regress to ``INVALID_YAML`` — the YAML parses, the
        normaliser runs, the floor catches the empty structure."""
        from hub.apps.core.services.base import ValidationError

        tenant = _unique_tenant()
        ok_but_empty = """
        kind: DataContract
        apiVersion: v3.0.2
        id: x
        name: x
        version: 1.0.0
        status: active
        info:
          description: just narrative, no schema block
        """
        with pytest.raises(ValidationError) as exc:
            self._service(tenant).create_contract(
                original_raw=ok_but_empty,
                original_format="YAML",
                original_spec_type="ODCS",
            )
        # The structural-floor wire code wins.
        assert exc.value.code == "STRUCTURELESS_CONTRACT" or (
            (exc.value.details or {}).get("code") == "STRUCTURELESS_CONTRACT"
        ), (
            f"expected STRUCTURELESS_CONTRACT for well-formed empty YAML; "
            f"got code={exc.value.code!r} details={exc.value.details!r}"
        )
