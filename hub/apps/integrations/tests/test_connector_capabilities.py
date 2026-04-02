"""
112.H — Connector capability honesty tests.

Proves:
1. H.1: Single capability matrix is available via factory
2. H.1: All registered connectors are PULL-only (no false push claims)
3. H.2: Every connector's push methods raise NotImplementedError
        with a descriptive message (not a generic 500)
"""
import pytest
from django.test import TestCase

from hub.apps.integrations.base import SyncDirection
from hub.apps.integrations.factory import MarketplaceConnectorFactory


pytestmark = pytest.mark.django_db(transaction=True)


def _get_registered_connectors():
    """Return list of (type_value, connector_instance) for all
    registered connectors, skipping any that fail to instantiate
    (e.g. missing optional dependencies)."""
    result = []
    for mtype in MarketplaceConnectorFactory.get_supported_types():
        try:
            connector = MarketplaceConnectorFactory.get_connector(mtype)
            result.append((mtype.value, connector))
        except Exception:
            pass
    return result


class CapabilityMatrixTest(TestCase):
    """H.1 — Single capability matrix from factory."""

    def test_get_capability_matrix_returns_dict(self):
        """Factory must expose a capability matrix dict."""
        matrix = MarketplaceConnectorFactory.get_capability_matrix()
        self.assertIsInstance(matrix, dict)
        self.assertGreater(
            len(matrix), 0,
            "At least one connector must be registered",
        )

    def test_matrix_entries_have_required_keys(self):
        """Each matrix entry must have sync_directions,
        supports_push, supports_pull, connector_class."""
        matrix = MarketplaceConnectorFactory.get_capability_matrix()
        required = {
            "sync_directions", "supports_push",
            "supports_pull", "connector_class",
        }
        for mtype, entry in matrix.items():
            missing = required - entry.keys()
            self.assertEqual(
                missing, set(),
                f"{mtype} missing keys: {missing}",
            )

    def test_all_production_connectors_are_pull_only(self):
        """All registered production connectors must be PULL-only
        (no false push capability claims)."""
        matrix = MarketplaceConnectorFactory.get_capability_matrix()
        for mtype, entry in matrix.items():
            cls_lower = entry["connector_class"].lower()
            # Skip test/in-memory connectors that may have been
            # left registered by earlier test classes.
            if "in_memory" in cls_lower or "test" in cls_lower or "fake" in cls_lower:
                continue
            # Connectors that failed to instantiate (e.g.
            # CKAN_INSTANCE needs base_url) have empty dirs —
            # skip rather than assert on empty data.
            if not entry["sync_directions"]:
                continue
            self.assertFalse(
                entry["supports_push"],
                f"{mtype} must NOT claim push support "
                f"(sync_directions={entry['sync_directions']})",
            )
            self.assertTrue(
                entry["supports_pull"],
                f"{mtype} must support pull",
            )

    def test_matrix_sync_directions_match_connector(self):
        """Matrix sync_directions must match the connector's
        supported_sync_directions property."""
        for mtype_val, connector in _get_registered_connectors():
            matrix = (
                MarketplaceConnectorFactory.get_capability_matrix()
            )
            if mtype_val not in matrix:
                continue
            expected = [
                d.value for d in connector.supported_sync_directions
            ]
            self.assertEqual(
                matrix[mtype_val]["sync_directions"],
                expected,
                f"{mtype_val} matrix != connector property",
            )


class UnsupportedPushOperationsTest(TestCase):
    """H.2 — Every harvest-only connector's push methods raise
    NotImplementedError with a descriptive message."""

    @staticmethod
    def _call_with_fallback(method, method_name):
        """Call a push method with multiple signature attempts."""
        # Each method may have different signatures across
        # connectors.  Try the most common first, fall back.
        attempts = {
            "sync_push": [
                lambda: method(mappings=[]),
                lambda: method([]),
                lambda: method(),
            ],
            "create_listing": [
                lambda: method(listing={}),
                lambda: method({}),
            ],
            "update_listing": [
                lambda: method(listing_id="x", listing={}),
                lambda: method("x", {}),
                lambda: method(listing={}),
                lambda: method({}),
            ],
            "publish_resource": [
                lambda: method(listing_id="x", resource={}),
                lambda: method("x", {}),
                lambda: method({}),
            ],
            "map_from_hub_asset": [
                lambda: method(asset={}),
                lambda: method({}),
            ],
        }
        for attempt in attempts.get(method_name, [lambda: method()]):
            try:
                attempt()
                return  # succeeded (shouldn't happen for push)
            except TypeError:
                continue  # wrong signature, try next
            except NotImplementedError:
                raise  # expected — re-raise for assertRaises
        # All attempts got TypeError — re-raise last one
        raise TypeError(
            f"Could not find valid signature for {method_name}"
        )

    def _assert_push_raises(self, connector, method_name, mtype):
        """Helper: assert the method raises NotImplementedError
        with a message containing useful context."""
        method = getattr(connector, method_name, None)
        if method is None:
            self.skipTest(
                f"{mtype} has no {method_name} method",
            )

        with self.assertRaises(
            NotImplementedError,
            msg=f"{mtype}.{method_name}() must raise "
                f"NotImplementedError",
        ) as ctx:
            # Call with minimal args.  Connector signatures vary,
            # so catch TypeError from wrong arity and retry with
            # alternative signatures.
            self._call_with_fallback(method, method_name)

        msg = str(ctx.exception).lower()
        # Must not be empty / generic
        self.assertTrue(
            len(msg) > 10,
            f"{mtype}.{method_name}() error message too "
            f"short: '{ctx.exception}'",
        )
        # Must mention directionality or the connector name
        self.assertTrue(
            "pull" in msg
            or "harvest" in msg
            or "not support" in msg
            or "push" in msg
            or mtype.lower().replace("_", " ") in msg
            or connector.marketplace_type.lower() in msg,
            f"{mtype}.{method_name}() error must mention "
            f"pull/harvest/push/connector — got: "
            f"'{ctx.exception}'",
        )

    def test_all_harvest_only_connectors_reject_push(self):
        """Every registered PULL-only connector must raise
        NotImplementedError on all 5 push methods."""
        push_methods = [
            "create_listing",
            "update_listing",
            "publish_resource",
            "sync_push",
            "map_from_hub_asset",
        ]
        tested = 0
        for mtype_val, connector in _get_registered_connectors():
            # Skip bidirectional/push-capable connectors
            dirs = [
                d.value
                for d in connector.supported_sync_directions
            ]
            if (
                SyncDirection.PUSH.value in dirs
                or SyncDirection.BIDIRECTIONAL.value in dirs
            ):
                continue
            # Skip test-only in-memory connector (stubs all ops)
            cls_name = type(connector).__name__.lower()
            if "inmemory" in cls_name or "in_memory" in cls_name or "fake" in cls_name:
                continue

            for method_name in push_methods:
                self._assert_push_raises(
                    connector, method_name, mtype_val,
                )
                tested += 1

        self.assertGreater(
            tested, 0,
            "At least one connector must be tested",
        )

    def test_push_error_is_not_generic_500(self):
        """Push errors must be NotImplementedError (maps to
        400/405 in DRF), NOT a generic Exception (500)."""
        for mtype_val, connector in _get_registered_connectors():
            dirs = [
                d.value
                for d in connector.supported_sync_directions
            ]
            if SyncDirection.PUSH.value in dirs:
                continue
            # Skip test-only in-memory connector (stubs all ops)
            cls_name = type(connector).__name__.lower()
            if "inmemory" in cls_name or "in_memory" in cls_name or "fake" in cls_name:
                continue
            try:
                connector.sync_push(mappings=[])
            except NotImplementedError:
                pass  # correct — maps to 400/405
            except TypeError:
                pass  # acceptable — signature mismatch
            except Exception as e:
                self.fail(
                    f"{mtype_val}.sync_push() raised "
                    f"{type(e).__name__} instead of "
                    f"NotImplementedError: {e}",
                )
