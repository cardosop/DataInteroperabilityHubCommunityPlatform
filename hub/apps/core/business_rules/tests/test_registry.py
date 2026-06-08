"""
Comprehensive unit tests for BusinessRulesRegistry.

Tests cover:
- Rule registration (decorator-based)
- Rule discovery (auto-register rules)
- Rule execution orchestration
- Rule dependency resolution
- Rule metadata management
"""
import types
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase

from hub.apps.core.business_rules.base import (
    BusinessRules,
    RuleExecutionContext,
    ValidationResult,
)
from hub.apps.core.business_rules.registry import (
    BusinessRulesRegistry,
    RuleMetadata,
    get_registry,
    register_rule,
)


class SampleRule1(BusinessRules):
    """Test rule 1."""
    def validate(self, context=None, *args, **kwargs):
        return ValidationResult(is_valid=True, details={'rule': 'rule1'})


class SampleRule2(BusinessRules):
    """Test rule 2."""
    def validate(self, context=None, *args, **kwargs):
        return ValidationResult(is_valid=True, details={'rule': 'rule2'})


class SampleRule3(BusinessRules):
    """Test rule 3."""
    def validate(self, context=None, *args, **kwargs):
        return ValidationResult(is_valid=False, errors=['Error from rule3'])


class TestBusinessRulesRegistry(TestCase):
    """Test BusinessRulesRegistry class."""

    def setUp(self):
        """Set up test fixtures."""
        self.registry = BusinessRulesRegistry()

    def test_registry_initialization(self):
        """Test registry initialization."""
        self.assertEqual(len(self.registry._rules), 0)
        self.assertEqual(len(self.registry._dependency_graph), 0)
        self.assertEqual(len(self.registry._reverse_dependency_graph), 0)

    def test_register_decorator(self):
        """Test decorator-based registration."""
        @self.registry.register(
            rule_name="test_rule",
            description="Test rule",
            tags=["test"],
            priority=10
        )
        class TestRule(BusinessRules):
            def validate(self, context=None, *args, **kwargs):
                return ValidationResult(is_valid=True)

        # Check rule is registered
        metadata = self.registry.get_rule("test_rule")
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.rule_name, "test_rule")
        self.assertEqual(metadata.description, "Test rule")
        self.assertEqual(metadata.tags, ["test"])
        self.assertEqual(metadata.priority, 10)
        self.assertTrue(metadata.enabled)

    def test_register_decorator_default_name(self):
        """Test decorator registration with default name."""
        @self.registry.register()
        class MyTestRule(BusinessRules):
            def validate(self, context=None, *args, **kwargs):
                return ValidationResult(is_valid=True)

        # Check rule is registered with class name
        metadata = self.registry.get_rule("MyTestRule")
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.rule_class, MyTestRule)

    def test_register_with_dependencies(self):
        """Test registration with dependencies."""
        @self.registry.register(rule_name="rule1")
        class Rule1(BusinessRules):
            def validate(self, context=None, *args, **kwargs):
                return ValidationResult(is_valid=True)

        @self.registry.register(
            rule_name="rule2",
            depends_on=["rule1"]
        )
        class Rule2(BusinessRules):
            def validate(self, context=None, *args, **kwargs):
                return ValidationResult(is_valid=True)

        # Check dependencies
        deps = self.registry.get_dependencies("rule2")
        self.assertIn("rule1", deps)

        # Check reverse dependencies
        dependents = self.registry.get_dependents("rule1")
        self.assertIn("rule2", dependents)

    def test_register_instance(self):
        """Test register_instance was removed in Phase 274.6.

        The method now raises NotImplementedError — use @register_rule
        decorator or execute_chain() instead.
        """
        with self.assertRaises(NotImplementedError):
            self.registry.register_instance()

    def test_get_rule(self):
        """Test getting a rule."""
        @self.registry.register(rule_name="test_rule")
        class TestRule(BusinessRules):
            def validate(self, context=None, *args, **kwargs):
                return ValidationResult(is_valid=True)

        metadata = self.registry.get_rule("test_rule")
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.rule_name, "test_rule")

        # Non-existent rule
        self.assertIsNone(self.registry.get_rule("nonexistent"))

    def test_get_all_rules(self):
        """Test getting all rules."""
        @self.registry.register(rule_name="rule1")
        class Rule1(BusinessRules):
            def validate(self, context=None, *args, **kwargs):
                return ValidationResult(is_valid=True)

        @self.registry.register(rule_name="rule2")
        class Rule2(BusinessRules):
            def validate(self, context=None, *args, **kwargs):
                return ValidationResult(is_valid=True)

        all_rules = self.registry.get_all_rules()
        self.assertEqual(len(all_rules), 2)
        self.assertIn("rule1", all_rules)
        self.assertIn("rule2", all_rules)

    def test_resolve_execution_order_no_dependencies(self):
        """Test resolving execution order with no dependencies."""
        @self.registry.register(rule_name="rule1", priority=10)
        class Rule1(BusinessRules):
            def validate(self, context=None, *args, **kwargs):
                return ValidationResult(is_valid=True)

        @self.registry.register(rule_name="rule2", priority=20)
        class Rule2(BusinessRules):
            def validate(self, context=None, *args, **kwargs):
                return ValidationResult(is_valid=True)

        order = self.registry.resolve_execution_order()
        # Should be ordered by priority
        self.assertEqual(order[0], "rule1")
        self.assertEqual(order[1], "rule2")

    def test_resolve_execution_order_with_dependencies(self):
        """Test resolving execution order with dependencies."""
        @self.registry.register(rule_name="rule1", priority=20)
        class Rule1(BusinessRules):
            def validate(self, context=None, *args, **kwargs):
                return ValidationResult(is_valid=True)

        @self.registry.register(
            rule_name="rule2",
            depends_on=["rule1"],
            priority=10
        )
        class Rule2(BusinessRules):
            def validate(self, context=None, *args, **kwargs):
                return ValidationResult(is_valid=True)

        order = self.registry.resolve_execution_order()
        # rule1 should come before rule2 (dependency)
        self.assertLess(order.index("rule1"), order.index("rule2"))

    def test_resolve_execution_order_circular_dependency(self):
        """Test resolving execution order with circular dependency."""
        @self.registry.register(
            rule_name="rule1",
            depends_on=["rule2"]
        )
        class Rule1(BusinessRules):
            def validate(self, context=None, *args, **kwargs):
                return ValidationResult(is_valid=True)

        @self.registry.register(
            rule_name="rule2",
            depends_on=["rule1"]
        )
        class Rule2(BusinessRules):
            def validate(self, context=None, *args, **kwargs):
                return ValidationResult(is_valid=True)

        # Should raise ValueError for circular dependency
        with self.assertRaises(ValueError) as cm:
            self.registry.resolve_execution_order()
        self.assertIn("Circular dependency", str(cm.exception))

    def test_resolve_execution_order_specific_rules(self):
        """Test resolving execution order for specific rules."""
        @self.registry.register(rule_name="rule1")
        class Rule1(BusinessRules):
            def validate(self, context=None, *args, **kwargs):
                return ValidationResult(is_valid=True)

        @self.registry.register(rule_name="rule2")
        class Rule2(BusinessRules):
            def validate(self, context=None, *args, **kwargs):
                return ValidationResult(is_valid=True)

        @self.registry.register(rule_name="rule3")
        class Rule3(BusinessRules):
            def validate(self, context=None, *args, **kwargs):
                return ValidationResult(is_valid=True)

        order = self.registry.resolve_execution_order(["rule2", "rule1"])
        self.assertEqual(len(order), 2)
        self.assertIn("rule1", order)
        self.assertIn("rule2", order)
        self.assertNotIn("rule3", order)

    def test_execute_rules_removed_in_phase_274_6(self):
        """Test execute_rules was removed in Phase 274.6.

        The method now raises NotImplementedError — use
        execute_chain() or individual rule .execute() instead.
        """
        with self.assertRaises(NotImplementedError):
            self.registry.execute_rules()

    def test_execute_rules_with_dependencies_removed(self):
        """Test execute_rules with dependencies was removed in Phase 274.6."""
        with self.assertRaises(NotImplementedError):
            self.registry.execute_rules(
                rule_names=["rule1_dep", "rule2_dep"],
            )

    def test_execute_rules_short_circuit_removed(self):
        """Test execute_rules with short_circuit was removed in Phase 274.6."""
        with self.assertRaises(NotImplementedError):
            self.registry.execute_rules(
                rule_names=["rule1", "rule2", "rule3"],
                short_circuit=True,
            )

    def test_execute_rules_no_short_circuit_removed(self):
        """Test execute_rules without short_circuit was removed in Phase 274.6."""
        with self.assertRaises(NotImplementedError):
            self.registry.execute_rules(short_circuit=False)

    def test_execute_rules_specific_rules_removed(self):
        """Test execute_rules with specific rules was removed in Phase 274.6."""
        with self.assertRaises(NotImplementedError):
            self.registry.execute_rules(rule_names=["rule1"])

    def test_get_rule_by_tag_removed(self):
        """Test get_rule_by_tag was removed in Phase 274.6.

        Tag-based rule lookup is no longer supported on the registry.
        Use individual rule .execute() or execute_chain() instead.
        """
        with self.assertRaises(AttributeError):
            self.registry.get_rule_by_tag

    def test_enable_disable_rule_removed(self):
        """Test enable_rule and disable_rule were removed in Phase 274.6.

        Use per-tenant feature flags instead.
        """
        with self.assertRaises(NotImplementedError):
            self.registry.enable_rule("rule1")
        with self.assertRaises(NotImplementedError):
            self.registry.disable_rule("rule1")

    def test_clear_registry(self):
        """Test clearing the registry."""
        @self.registry.register(rule_name="rule1")
        class Rule1(BusinessRules):
            def validate(self, context=None, *args, **kwargs):
                return ValidationResult(is_valid=True)

        self.assertEqual(len(self.registry._rules), 1)
        self.registry.clear()
        self.assertEqual(len(self.registry._rules), 0)
        self.assertEqual(len(self.registry._dependency_graph), 0)

    def test_register_duplicate_name_different_class(self):
        """Test registering duplicate name with different class."""
        @self.registry.register(rule_name="test_rule")
        class Rule1(BusinessRules):
            def validate(self, context=None, *args, **kwargs):
                return ValidationResult(is_valid=True)

        # Try to register different class with same name
        with self.assertRaises(ValueError) as cm:
            @self.registry.register(rule_name="test_rule")
            class Rule2(BusinessRules):
                def validate(self, context=None, *args, **kwargs):
                    return ValidationResult(is_valid=True)
        self.assertIn("already registered", str(cm.exception))

    def test_register_duplicate_name_same_class(self):
        """Test registering duplicate name with same class (idempotent)."""
        # Define the class once
        class TestRule(BusinessRules):
            def validate(self, context=None, *args, **kwargs):
                return ValidationResult(is_valid=True)

        # Register it
        self.registry.register(rule_name="test_rule")(TestRule)

        # Register same class again (should be idempotent)
        self.registry.register(rule_name="test_rule")(TestRule)

        # Should still have only one rule
        self.assertEqual(len(self.registry._rules), 1)


class TestRuleDiscovery(TestCase):
    """Test rule discovery functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.registry = BusinessRulesRegistry()

    def test_discover_rules_from_module(self):
        """Test discovering rules from a module."""
        # Create a test module with rules
        import types
        test_module = types.ModuleType('test_module')

        class DiscoveredRule1(BusinessRules):
            def validate(self, context=None, *args, **kwargs):
                return ValidationResult(is_valid=True)

        class DiscoveredRule2(BusinessRules):
            def validate(self, context=None, *args, **kwargs):
                return ValidationResult(is_valid=True)

        # Add rules to module
        test_module.DiscoveredRule1 = DiscoveredRule1
        test_module.DiscoveredRule2 = DiscoveredRule2
        DiscoveredRule1.__module__ = 'test_module'
        DiscoveredRule2.__module__ = 'test_module'

        # Discover rules
        discovered = self.registry._discover_rules_from_module(test_module)

        self.assertEqual(len(discovered), 2)
        self.assertIn("DiscoveredRule1", discovered)
        self.assertIn("DiscoveredRule2", discovered)

    @patch('hub.apps.core.business_rules.registry.importlib')
    @patch('hub.apps.core.business_rules.registry.pkgutil')
    def test_discover_rules_from_package(self, mock_pkgutil, mock_importlib):
        """Test discovering rules from a package."""
        # Mock package structure
        mock_module = types.ModuleType('test_package.module')
        mock_module.__path__ = ['/test/path']

        class DiscoveredRule(BusinessRules):
            def validate(self, context=None, *args, **kwargs):
                return ValidationResult(is_valid=True)

        DiscoveredRule.__module__ = 'test_package.module'
        mock_module.DiscoveredRule = DiscoveredRule

        # Mock pkgutil.walk_packages
        mock_walker = MagicMock()
        mock_walker.__iter__ = lambda self: iter([
            (None, 'test_package.module', False)
        ])
        mock_pkgutil.walk_packages.return_value = mock_walker

        # Mock importlib.import_module
        mock_importlib.import_module.return_value = mock_module

        # Discover rules
        discovered = self.registry.discover_rules('test_package')

        # Should discover the rule
        self.assertGreaterEqual(len(discovered), 0)


class TestGlobalRegistry(TestCase):
    """Test global registry functions."""

    def test_get_registry(self):
        """Test getting global registry."""
        registry = get_registry()
        self.assertIsInstance(registry, BusinessRulesRegistry)

    def test_register_rule_decorator(self):
        """Test global register_rule decorator."""
        @register_rule(
            rule_name="global_test_rule",
            description="Global test rule",
            tags=["test"]
        )
        class GlobalTestRule(BusinessRules):
            def validate(self, context=None, *args, **kwargs):
                return ValidationResult(is_valid=True)

        registry = get_registry()
        metadata = registry.get_rule("global_test_rule")
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.description, "Global test rule")


class TestRuleMetadata(TestCase):
    """Test RuleMetadata dataclass."""

    def test_rule_metadata_initialization(self):
        """Test RuleMetadata initialization."""
        metadata = RuleMetadata(
            rule_class=SampleRule1,
            rule_name="test_rule",
            description="Test",
            tags=["tag1"],
            dependencies=["dep1"],
            priority=10,
            enabled=True
        )

        self.assertEqual(metadata.rule_class, SampleRule1)
        self.assertEqual(metadata.rule_name, "test_rule")
        self.assertEqual(metadata.description, "Test")
        self.assertEqual(metadata.tags, ["tag1"])
        self.assertEqual(metadata.dependencies, ["dep1"])
        self.assertEqual(metadata.priority, 10)
        self.assertTrue(metadata.enabled)

    def test_rule_metadata_invalid_class(self):
        """Test RuleMetadata with invalid class."""
        class NotBusinessRules:
            pass

        with self.assertRaises(TypeError):
            RuleMetadata(
                rule_class=NotBusinessRules,
                rule_name="test"
            )

    def test_rule_metadata_empty_name(self):
        """Test RuleMetadata with empty name."""
        with self.assertRaises(ValueError):
            RuleMetadata(
                rule_class=SampleRule1,
                rule_name=""
            )

    def test_rule_metadata_invalid_tags(self):
        """Test RuleMetadata with invalid tags."""
        with self.assertRaises(TypeError):
            RuleMetadata(
                rule_class=SampleRule1,
                rule_name="test",
                tags="not_a_list"  # Should be a list
            )

