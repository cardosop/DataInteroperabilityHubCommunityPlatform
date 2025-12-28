"""
Unit tests for TransformationNode model.
"""
import uuid
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from hub.apps.transformation.models import (
    TransformationPipeline,
    TransformationNode,
    PipelineStatus
)
from hub.apps.tenants.models import Tenant

User = get_user_model()


class TransformationNodeModelTest(TestCase):
    """Test cases for TransformationNode model."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        self.valid_pipeline_definition = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "step1",
                    "type": "task",
                    "task": "extract_data",
                    "input": {}
                }
            ]
        }
        self.pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            description="Test pipeline description",
            pipeline_definition=self.valid_pipeline_definition,
            version="1.0.0",
            status=PipelineStatus.DRAFT
        )

    def test_create_transformation_node(self):
        """Test creating a transformation node."""
        node = TransformationNode.objects.create(
            pipeline=self.pipeline,
            node_type="filter",
            node_config={
                "filter_expression": "age > 18",
                "description": "Filter adults"
            },
            position={"x": 100, "y": 200},
            order=1
        )

        self.assertIsNotNone(node.id)
        self.assertEqual(node.pipeline, self.pipeline)
        self.assertEqual(node.node_type, "filter")
        self.assertEqual(node.node_config, {
            "filter_expression": "age > 18",
            "description": "Filter adults"
        })
        self.assertEqual(node.position, {"x": 100, "y": 200})
        self.assertEqual(node.order, 1)

    def test_node_str_representation(self):
        """Test node string representation."""
        node = TransformationNode.objects.create(
            pipeline=self.pipeline,
            node_type="filter",
            node_config={},
            position={"x": 100, "y": 200},
            order=1
        )

        expected_str = f"filter (order: 1) - {self.pipeline.name}"
        self.assertEqual(str(node), expected_str)

    def test_node_default_config(self):
        """Test node has default empty config."""
        node = TransformationNode.objects.create(
            pipeline=self.pipeline,
            node_type="transform",
            position={"x": 0, "y": 0},
            order=1
        )

        self.assertEqual(node.node_config, {})

    def test_node_default_position(self):
        """Test node has default position."""
        node = TransformationNode.objects.create(
            pipeline=self.pipeline,
            node_type="output",
            node_config={},
            order=1
        )

        self.assertEqual(node.position, {})

    def test_node_validation_node_type_required(self):
        """Test node validation fails with empty node_type."""
        node = TransformationNode(
            pipeline=self.pipeline,
            node_type="",
            node_config={},
            position={"x": 0, "y": 0},
            order=1
        )

        with self.assertRaises(ValidationError):
            node.full_clean()

    def test_node_validation_node_type_whitespace(self):
        """Test node validation fails with whitespace-only node_type."""
        node = TransformationNode(
            pipeline=self.pipeline,
            node_type="   ",
            node_config={},
            position={"x": 0, "y": 0},
            order=1
        )

        with self.assertRaises(ValidationError):
            node.full_clean()

    def test_node_validation_invalid_node_config_not_dict(self):
        """Test node validation fails when node_config is not a dict."""
        node = TransformationNode(
            pipeline=self.pipeline,
            node_type="filter",
            node_config="not a dict",
            position={"x": 0, "y": 0},
            order=1
        )

        with self.assertRaises(ValidationError):
            node.full_clean()

    def test_node_validation_invalid_position_not_dict(self):
        """Test node validation fails when position is not a dict."""
        node = TransformationNode(
            pipeline=self.pipeline,
            node_type="filter",
            node_config={},
            position="not a dict",
            order=1
        )

        with self.assertRaises(ValidationError):
            node.full_clean()

    def test_node_validation_order_required(self):
        """Test node validation fails when order is None."""
        node = TransformationNode(
            pipeline=self.pipeline,
            node_type="filter",
            node_config={},
            position={"x": 0, "y": 0},
            order=None
        )

        with self.assertRaises(ValidationError):
            node.full_clean()

    def test_node_validation_order_negative(self):
        """Test node validation fails when order is negative."""
        node = TransformationNode(
            pipeline=self.pipeline,
            node_type="filter",
            node_config={},
            position={"x": 0, "y": 0},
            order=-1
        )

        with self.assertRaises(ValidationError):
            node.full_clean()

    def test_node_validation_valid_node_types(self):
        """Test node validation accepts valid node types."""
        valid_types = ["filter", "join", "aggregate", "transform", "output"]

        for node_type in valid_types:
            node = TransformationNode(
                pipeline=self.pipeline,
                node_type=node_type,
                node_config={},
                position={"x": 0, "y": 0},
                order=1
            )
            # Should not raise ValidationError
            node.full_clean()

    def test_node_cascade_delete_with_pipeline(self):
        """Test that nodes are deleted when pipeline is deleted."""
        node = TransformationNode.objects.create(
            pipeline=self.pipeline,
            node_type="filter",
            node_config={},
            position={"x": 0, "y": 0},
            order=1
        )
        node_id = node.id

        # Delete pipeline
        self.pipeline.delete()

        # Node should be deleted
        self.assertFalse(
            TransformationNode.objects.filter(id=node_id).exists(),
            "Node should be deleted when pipeline is deleted"
        )

    def test_node_multiple_nodes_same_pipeline(self):
        """Test that multiple nodes can belong to the same pipeline."""
        node1 = TransformationNode.objects.create(
            pipeline=self.pipeline,
            node_type="filter",
            node_config={},
            position={"x": 0, "y": 0},
            order=1
        )
        node2 = TransformationNode.objects.create(
            pipeline=self.pipeline,
            node_type="transform",
            node_config={},
            position={"x": 100, "y": 100},
            order=2
        )
        node3 = TransformationNode.objects.create(
            pipeline=self.pipeline,
            node_type="output",
            node_config={},
            position={"x": 200, "y": 200},
            order=3
        )

        self.assertEqual(
            TransformationNode.objects.filter(pipeline=self.pipeline).count(),
            3
        )
        self.assertNotEqual(node1.id, node2.id)
        self.assertNotEqual(node2.id, node3.id)

    def test_node_ordering(self):
        """Test that nodes can be ordered correctly."""
        node3 = TransformationNode.objects.create(
            pipeline=self.pipeline,
            node_type="output",
            node_config={},
            position={"x": 0, "y": 0},
            order=3
        )
        node1 = TransformationNode.objects.create(
            pipeline=self.pipeline,
            node_type="filter",
            node_config={},
            position={"x": 0, "y": 0},
            order=1
        )
        node2 = TransformationNode.objects.create(
            pipeline=self.pipeline,
            node_type="transform",
            node_config={},
            position={"x": 0, "y": 0},
            order=2
        )

        # Query ordered by order field
        nodes = list(
            TransformationNode.objects.filter(pipeline=self.pipeline).order_by("order")
        )
        self.assertEqual(nodes[0], node1)
        self.assertEqual(nodes[1], node2)
        self.assertEqual(nodes[2], node3)

    def test_node_complex_config(self):
        """Test node can store complex configuration."""
        complex_config = {
            "filter_expression": "age > 18 AND status = 'active'",
            "join_type": "inner",
            "join_keys": ["customer_id", "order_id"],
            "aggregation_functions": [
                {"field": "amount", "function": "sum"},
                {"field": "count", "function": "count"}
            ],
            "transform_rules": [
                {"field": "name", "transform": "uppercase"},
                {"field": "email", "transform": "lowercase"}
            ],
            "output_format": "parquet",
            "output_path": "/data/output"
        }

        node = TransformationNode.objects.create(
            pipeline=self.pipeline,
            node_type="transform",
            node_config=complex_config,
            position={"x": 100, "y": 200},
            order=1
        )

        self.assertEqual(node.node_config, complex_config)
        self.assertEqual(node.node_config["filter_expression"], "age > 18 AND status = 'active'")
        self.assertEqual(len(node.node_config["aggregation_functions"]), 2)

    def test_node_position_coordinates(self):
        """Test node position can store x and y coordinates."""
        positions = [
            {"x": 0, "y": 0},
            {"x": 100, "y": 200},
            {"x": -50, "y": -100},
            {"x": 1000, "y": 2000}
        ]

        for i, pos in enumerate(positions):
            node = TransformationNode.objects.create(
                pipeline=self.pipeline,
                node_type="filter",
                node_config={},
                position=pos,
                order=i + 1
            )
            self.assertEqual(node.position, pos)
            self.assertEqual(node.position["x"], pos["x"])
            self.assertEqual(node.position["y"], pos["y"])

    def test_node_position_empty_dict(self):
        """Test node position can be empty dict."""
        node = TransformationNode.objects.create(
            pipeline=self.pipeline,
            node_type="filter",
            node_config={},
            position={},
            order=1
        )

        self.assertEqual(node.position, {})

    def test_node_related_name(self):
        """Test that pipeline has related_name for nodes."""
        node = TransformationNode.objects.create(
            pipeline=self.pipeline,
            node_type="filter",
            node_config={},
            position={"x": 0, "y": 0},
            order=1
        )

        # Access nodes through related_name
        nodes = self.pipeline.transformation_nodes.all()
        self.assertEqual(nodes.count(), 1)
        self.assertEqual(nodes.first(), node)

    def test_node_indexes_exist(self):
        """Test that database indexes are created for node fields."""
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    i.relname AS index_name,
                    array_agg(a.attname ORDER BY a.attnum) AS column_names
                FROM pg_class t
                JOIN pg_index ix ON t.oid = ix.indrelid
                JOIN pg_class i ON i.oid = ix.indexrelid
                JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
                WHERE t.relname = 'transformation_nodes'
                AND t.relkind = 'r'
                GROUP BY i.relname
                ORDER BY i.relname;
            """)
            indexes = {row[0]: row[1] for row in cursor.fetchall()}

            # Verify indexes exist on required columns
            has_pipeline_index = any('pipeline_id' in cols for cols in indexes.values())
            has_node_type_index = any('node_type' in cols for cols in indexes.values())
            has_order_index = any('order' in cols for cols in indexes.values())

            self.assertTrue(has_pipeline_index, "Should have index on pipeline_id")
            self.assertTrue(has_node_type_index, "Should have index on node_type")
            self.assertTrue(has_order_index, "Should have index on order")

    def test_node_created_at_auto_set(self):
        """Test created_at is automatically set."""
        node = TransformationNode.objects.create(
            pipeline=self.pipeline,
            node_type="filter",
            node_config={},
            position={"x": 0, "y": 0},
            order=1
        )

        self.assertIsNotNone(node.created_at)

    def test_node_updated_at_auto_set(self):
        """Test updated_at is automatically set and updated."""
        node = TransformationNode.objects.create(
            pipeline=self.pipeline,
            node_type="filter",
            node_config={},
            position={"x": 0, "y": 0},
            order=1
        )

        original_updated_at = node.updated_at

        # Update node
        node.node_config = {"new": "config"}
        node.save()

        node.refresh_from_db()
        self.assertGreater(node.updated_at, original_updated_at)

    def test_node_can_store_arbitrary_config(self):
        """Test node_config can store arbitrary JSON data."""
        arbitrary_config = {
            "custom_field_1": "value1",
            "custom_field_2": 123,
            "custom_field_3": [1, 2, 3],
            "custom_field_4": {"nested": "object"},
            "custom_field_5": True,
            "custom_field_6": None
        }

        node = TransformationNode.objects.create(
            pipeline=self.pipeline,
            node_type="transform",
            node_config=arbitrary_config,
            position={"x": 0, "y": 0},
            order=1
        )

        self.assertEqual(node.node_config, arbitrary_config)
        self.assertEqual(node.node_config["custom_field_1"], "value1")
        self.assertEqual(node.node_config["custom_field_2"], 123)
        self.assertEqual(node.node_config["custom_field_3"], [1, 2, 3])
        self.assertEqual(node.node_config["custom_field_4"], {"nested": "object"})
        self.assertEqual(node.node_config["custom_field_5"], True)
        self.assertEqual(node.node_config["custom_field_6"], None)

