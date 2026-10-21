"""
Tests for ``hub.apps.warehouses.export_adapter`` — DLT / write adapters.

The ``dlt`` library is imported locally inside ``DltAdapter.write_rows()``.
Tests simulate all three paths: dlt installed (success), dlt installed
but raises, and dlt not installed.
"""

import sys
from unittest import mock

from django.test import SimpleTestCase


class DltAdapterTests(SimpleTestCase):
    """Tests for DltAdapter."""

    def setUp(self):
        from hub.apps.warehouses.export_adapter import DltAdapter

        self.adapter = DltAdapter(
            destination_type="snowflake",
            credentials={"account": "test"},
        )

    def test_dlt_adapter_is_importable(self):
        """DltAdapter class is importable."""
        from hub.apps.warehouses.export_adapter import DltAdapter

        assert DltAdapter is not None

    def test_create_table_is_noop(self):
        """create_table() does not raise — dlt creates tables on first write."""
        self.adapter.create_table("test_table", [])
        # No exception → pass

    def test_write_rows_dlt_not_installed(self):
        """write_rows returns error status when dlt import fails."""
        # Simulate dlt not being installed
        with (
            mock.patch.dict(sys.modules, {"dlt": None}),
            mock.patch("builtins.__import__", side_effect=ImportError("No module named 'dlt'")),
        ):
            result = self.adapter.write_rows("test_table", [{"col": "val"}])
        assert result["status"] == "error"
        assert "error" in result

    @mock.patch("builtins.__import__")
    def test_write_rows_dlt_exception(self, mock_import):
        """If dlt.pipeline().run() raises, status is error."""
        # Set up a fake dlt module with a failing pipeline
        fake_dlt = mock.MagicMock()
        fake_pipeline = mock.MagicMock()
        fake_pipeline.run.side_effect = RuntimeError("dlt pipeline error")
        fake_dlt.pipeline.return_value = fake_pipeline

        def _import(name, *args, **kwargs):
            if name == "dlt":
                return fake_dlt
            return __import__(name, *args, **kwargs)

        mock_import.side_effect = _import

        result = self.adapter.write_rows("test_table", [{"col": "val"}])
        assert result["status"] == "error"
        assert "dlt pipeline error" in result.get("error", "")

    @mock.patch("builtins.__import__")
    def test_write_rows_success(self, mock_import):
        """write_rows uses dlt.pipeline().run() and returns success."""
        fake_dlt = mock.MagicMock()
        fake_info = mock.MagicMock()
        fake_info.load_id = "load-123"
        fake_pipeline = mock.MagicMock()
        fake_pipeline.run.return_value = fake_info
        fake_dlt.pipeline.return_value = fake_pipeline

        def _import(name, *args, **kwargs):
            if name == "dlt":
                return fake_dlt
            return __import__(name, *args, **kwargs)

        mock_import.side_effect = _import

        result = self.adapter.write_rows("test_table", [{"col": "val"}])
        assert result["status"] == "success"
        assert result["rows_written"] == 1
        assert result["load_id"] == "load-123"


class WriteAdapterTests(SimpleTestCase):
    """Tests for WriteAdapter abstract base."""

    def test_write_adapter_is_importable(self):
        """WriteAdapter ABC is importable."""
        from hub.apps.warehouses.export_adapter import WriteAdapter

        assert WriteAdapter is not None

    def test_write_adapter_cannot_be_instantiated(self):
        """WriteAdapter is abstract — cannot instantiate directly."""
        from hub.apps.warehouses.export_adapter import WriteAdapter

        with self.assertRaises(TypeError):
            WriteAdapter()
