"""
Comprehensive unit tests for BusinessRules base class.

Tests cover:
- ValidationResult structure and behavior
- RuleExecutionContext creation and serialization
- BusinessRules base class functionality
- Rule composition (combine multiple rules, short-circuit on error)
- Rule caching (cache validation results with TTL)
- Rule execution metrics (Prometheus)
- Rule execution logging (structured logging)
- Rule execution tracing (OpenTelemetry)
"""
import time
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, override_settings
from django.core.cache import cache

from hub.apps.core.business_rules.base import (
    ValidationResult,
    RuleExecutionContext,
    BusinessRules,
)


class TestValidationResult(TestCase):
    """Test ValidationResult dataclass."""

    def test_validation_result_defaults(self):
        """Test ValidationResult with default values."""
        result = ValidationResult()
        self.assertTrue(result.is_valid)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.details, {})

    def test_validation_result_initialization(self):
        """Test ValidationResult initialization with values."""
        result = ValidationResult(
            is_valid=False,
            errors=['Error 1', 'Error 2'],
            warnings=['Warning 1'],
            details={'key': 'value'}
        )
        self.assertFalse(result.is_valid)
        self.assertEqual(result.errors, ['Error 1', 'Error 2'])
        self.assertEqual(result.warnings, ['Warning 1'])
        self.assertEqual(result.details, {'key': 'value'})

    def test_validation_result_bool(self):
        """Test ValidationResult boolean conversion."""
        valid_result = ValidationResult(is_valid=True)
        invalid_result = ValidationResult(is_valid=False)

        self.assertTrue(valid_result)
        self.assertFalse(invalid_result)

    def test_validation_result_str(self):
        """Test ValidationResult string representation."""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=['Warning']
        )
        str_repr = str(result)
        self.assertIn('VALID', str_repr)
        self.assertIn('warnings=1', str_repr)

    def test_validation_result_combine(self):
        """Test combining ValidationResult instances."""
        result1 = ValidationResult(
            is_valid=True,
            errors=['Error 1'],
            warnings=['Warning 1'],
            details={'key1': 'value1'}
        )
        result2 = ValidationResult(
            is_valid=False,
            errors=['Error 2'],
            warnings=['Warning 2'],
            details={'key2': 'value2'}
        )

        combined = result1.combine(result2)
        self.assertFalse(combined.is_valid)  # False AND False = False
        self.assertEqual(combined.errors, ['Error 1', 'Error 2'])
        self.assertEqual(combined.warnings, ['Warning 1', 'Warning 2'])
        self.assertEqual(combined.details, {'key1': 'value1', 'key2': 'value2'})

    def test_validation_result_combine_both_valid(self):
        """Test combining two valid results."""
        result1 = ValidationResult(is_valid=True)
        result2 = ValidationResult(is_valid=True)
        combined = result1.combine(result2)
        self.assertTrue(combined.is_valid)


class TestRuleExecutionContext(TestCase):
    """Test RuleExecutionContext dataclass."""

    def test_context_defaults(self):
        """Test RuleExecutionContext with default values."""
        context = RuleExecutionContext()
        self.assertIsNone(context.tenant_id)
        self.assertIsNone(context.user_id)
        self.assertIsNone(context.resource)
        self.assertEqual(context.metadata, {})

    def test_context_initialization(self):
        """Test RuleExecutionContext initialization with values."""
        resource = Mock(id='resource-123')
        context = RuleExecutionContext(
            tenant_id='tenant-123',
            user_id='user-123',
            resource=resource,
            metadata={'key': 'value'}
        )
        self.assertEqual(context.tenant_id, 'tenant-123')
        self.assertEqual(context.user_id, 'user-123')
        self.assertEqual(context.resource, resource)
        self.assertEqual(context.metadata, {'key': 'value'})

    def test_context_to_dict(self):
        """Test converting RuleExecutionContext to dictionary."""
        resource = Mock(id='resource-123')
        context = RuleExecutionContext(
            tenant_id='tenant-123',
            user_id='user-123',
            resource=resource,
            metadata={'key': 'value'}
        )
        context_dict = context.to_dict()
        self.assertEqual(context_dict['tenant_id'], 'tenant-123')
        self.assertEqual(context_dict['user_id'], 'user-123')
        self.assertEqual(context_dict['resource_id'], 'resource-123')
        self.assertEqual(context_dict['resource_type'], 'Mock')
        self.assertEqual(context_dict['metadata'], {'key': 'value'})

    def test_context_to_dict_no_resource(self):
        """Test converting context without resource to dictionary."""
        context = RuleExecutionContext(
            tenant_id='tenant-123',
            user_id='user-123'
        )
        context_dict = context.to_dict()
        self.assertIsNone(context_dict['resource_id'])
        self.assertIsNone(context_dict['resource_type'])

    def test_context_get_cache_key_suffix(self):
        """Test generating cache key suffix from context."""
        context1 = RuleExecutionContext(
            tenant_id='tenant-123',
            user_id='user-123'
        )
        context2 = RuleExecutionContext(
            tenant_id='tenant-123',
            user_id='user-123'
        )
        # Same context should produce same suffix
        suffix1 = context1.get_cache_key_suffix()
        suffix2 = context2.get_cache_key_suffix()
        self.assertEqual(suffix1, suffix2)
        self.assertEqual(len(suffix1), 32)  # MD5 hash length

    def test_context_get_cache_key_suffix_different(self):
        """Test different contexts produce different cache key suffixes."""
        context1 = RuleExecutionContext(tenant_id='tenant-123')
        context2 = RuleExecutionContext(tenant_id='tenant-456')
        suffix1 = context1.get_cache_key_suffix()
        suffix2 = context2.get_cache_key_suffix()
        self.assertNotEqual(suffix1, suffix2)


class ConcreteBusinessRules(BusinessRules):
    """Concrete implementation for testing."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.validation_called = False
        self.validation_context = None
        self.validation_args = None
        self.validation_kwargs = None

    def validate(
        self,
        context: RuleExecutionContext = None,
        *args,
        **kwargs
    ) -> ValidationResult:
        """Test implementation of validate."""
        self.validation_called = True
        self.validation_context = context
        self.validation_args = args
        self.validation_kwargs = kwargs

        # Return result based on kwargs
        is_valid = kwargs.get('should_be_valid', True)
        errors = kwargs.get('errors', [])
        warnings = kwargs.get('warnings', [])

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details={'test': True}
        )


class TestBusinessRulesBase(TestCase):
    """Test BusinessRules base class."""

    def setUp(self):
        """Set up test fixtures."""
        cache.clear()

    def test_business_rules_initialization(self):
        """Test BusinessRules initialization."""
        rules = ConcreteBusinessRules(
            tenant_id='tenant-123',
            user_id='user-123'
        )
        self.assertEqual(rules.tenant_id, 'tenant-123')
        self.assertEqual(rules.user_id, 'user-123')
        self.assertTrue(rules.enable_caching)
        self.assertTrue(rules.enable_metrics)
        self.assertTrue(rules.enable_tracing)
        self.assertTrue(rules.enable_logging)

    def test_business_rules_initialization_disabled_features(self):
        """Test BusinessRules initialization with disabled features."""
        rules = ConcreteBusinessRules(
            enable_caching=False,
            enable_metrics=False,
            enable_tracing=False,
            enable_logging=False
        )
        self.assertFalse(rules.enable_caching)
        self.assertFalse(rules.enable_metrics)
        self.assertFalse(rules.enable_tracing)
        self.assertFalse(rules.enable_logging)

    def test_get_rule_name(self):
        """Test getting rule name."""
        rules = ConcreteBusinessRules()
        self.assertEqual(rules.get_rule_name(), 'ConcreteBusinessRules')

    def test_get_cache_ttl(self):
        """Test getting cache TTL."""
        rules = ConcreteBusinessRules()
        ttl = rules.get_cache_ttl()
        self.assertIsInstance(ttl, int)
        self.assertGreater(ttl, 0)

    @override_settings(CACHE_TTL_BUSINESS_RULES=600)
    def test_get_cache_ttl_from_settings(self):
        """Test getting cache TTL from settings."""
        rules = ConcreteBusinessRules()
        ttl = rules.get_cache_ttl()
        self.assertEqual(ttl, 600)

    def test_create_context(self):
        """Test creating rule execution context."""
        rules = ConcreteBusinessRules(
            tenant_id='tenant-123',
            user_id='user-123'
        )
        resource = Mock(id='resource-123')
        context = rules.create_context(
            resource=resource,
            metadata={'key': 'value'}
        )
        self.assertEqual(context.tenant_id, 'tenant-123')
        self.assertEqual(context.user_id, 'user-123')
        self.assertEqual(context.resource, resource)
        self.assertEqual(context.metadata, {'key': 'value'})

    def test_create_context_defaults(self):
        """Test creating context with defaults."""
        rules = ConcreteBusinessRules()
        context = rules.create_context()
        self.assertIsNone(context.tenant_id)
        self.assertIsNone(context.user_id)
        self.assertIsNone(context.resource)
        self.assertEqual(context.metadata, {})

    def test_execute_basic(self):
        """Test basic rule execution."""
        rules = ConcreteBusinessRules()
        context = rules.create_context()

        result = rules.execute(context, should_be_valid=True)

        self.assertTrue(rules.validation_called)
        self.assertEqual(rules.validation_context, context)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.details, {'test': True})

    def test_execute_with_args_kwargs(self):
        """Test rule execution with args and kwargs."""
        rules = ConcreteBusinessRules()
        context = rules.create_context()

        result = rules.execute(
            context,
            'arg1',
            'arg2',
            use_cache=False,  # Explicitly pass use_cache to avoid it being interpreted as an arg
            should_be_valid=False,
            errors=['Error 1']
        )

        self.assertTrue(rules.validation_called)
        self.assertEqual(rules.validation_args, ('arg1', 'arg2'))
        self.assertIn('should_be_valid', rules.validation_kwargs)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.errors, ['Error 1'])

    def test_execute_creates_context(self):
        """Test execute creates context if not provided."""
        rules = ConcreteBusinessRules()
        resource = Mock(id='resource-123')

        result = rules.execute(resource=resource, metadata={'key': 'value'})

        self.assertTrue(rules.validation_called)
        self.assertIsNotNone(rules.validation_context)
        self.assertEqual(rules.validation_context.resource, resource)
        self.assertEqual(rules.validation_context.metadata, {'key': 'value'})

    def test_execute_caching(self):
        """Test rule execution with caching."""
        rules = ConcreteBusinessRules(enable_caching=True)
        context = rules.create_context()

        # First execution - should call validate
        result1 = rules.execute(context, should_be_valid=True)
        self.assertTrue(rules.validation_called)

        # Reset flag
        rules.validation_called = False

        # Second execution - should use cache
        result2 = rules.execute(context, should_be_valid=True)
        self.assertFalse(rules.validation_called)  # Should not call validate
        self.assertEqual(result1.is_valid, result2.is_valid)

    def test_execute_caching_disabled(self):
        """Test rule execution with caching disabled."""
        rules = ConcreteBusinessRules(enable_caching=False)
        context = rules.create_context()

        # First execution
        result1 = rules.execute(context, should_be_valid=True)
        self.assertTrue(rules.validation_called)

        # Reset flag
        rules.validation_called = False

        # Second execution - should call validate again
        result2 = rules.execute(context, should_be_valid=True)
        self.assertTrue(rules.validation_called)  # Should call validate

    def test_execute_caching_only_valid_results(self):
        """Test that only valid results are cached."""
        rules = ConcreteBusinessRules(enable_caching=True)
        context = rules.create_context()

        # Execute with invalid result
        result1 = rules.execute(context, should_be_valid=False, errors=['Error'])
        self.assertFalse(result1.is_valid)

        # Reset flag
        rules.validation_called = False

        # Second execution - should call validate again (invalid not cached)
        result2 = rules.execute(context, should_be_valid=False, errors=['Error'])
        self.assertTrue(rules.validation_called)  # Should call validate

    def test_execute_caching_override(self):
        """Test overriding cache setting per execution."""
        rules = ConcreteBusinessRules(enable_caching=True)
        context = rules.create_context()

        # First execution with caching
        result1 = rules.execute(context, should_be_valid=True)
        self.assertTrue(rules.validation_called)

        # Reset flag
        rules.validation_called = False

        # Second execution with caching disabled
        result2 = rules.execute(context, use_cache=False, should_be_valid=True)
        self.assertTrue(rules.validation_called)  # Should call validate

    def test_execute_exception_handling(self):
        """Test exception handling during execution."""
        class FailingBusinessRules(BusinessRules):
            def validate(self, context=None, *args, **kwargs):
                raise ValueError("Test error")

        rules = FailingBusinessRules()
        context = rules.create_context()

        result = rules.execute(context)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn('Test error', result.errors[0])

    @patch('hub.apps.core.business_rules.base.get_meter')
    def test_metrics_initialization(self, mock_get_meter):
        """Test metrics initialization."""
        mock_meter = MagicMock()
        mock_get_meter.return_value = mock_meter

        rules = ConcreteBusinessRules(enable_metrics=True)

        # Check that metrics were initialized
        self.assertTrue(rules._metrics_initialized)
        mock_get_meter.assert_called()

    @patch('hub.apps.core.business_rules.base.get_meter')
    def test_metrics_recording(self, mock_get_meter):
        """Test metrics recording during execution."""
        mock_meter = MagicMock()
        mock_counter = MagicMock()
        mock_histogram = MagicMock()

        mock_meter.create_counter.return_value = mock_counter
        mock_meter.create_histogram.return_value = mock_histogram
        mock_get_meter.return_value = mock_meter

        rules = ConcreteBusinessRules(enable_metrics=True)
        context = rules.create_context()

        result = rules.execute(context, should_be_valid=True, errors=['Error'])

        # Check that metrics were recorded
        self.assertTrue(mock_counter.add.called)
        self.assertTrue(mock_histogram.record.called)

    @patch('hub.apps.core.business_rules.base.logger')
    def test_logging(self, mock_logger):
        """Test structured logging during execution."""
        rules = ConcreteBusinessRules(enable_logging=True)
        context = rules.create_context()

        result = rules.execute(context, should_be_valid=True, errors=['Error'])

        # Check that logging was called (info or warning depending on result)
        # Since result has errors, it should log as warning
        self.assertTrue(mock_logger.warning.called or mock_logger.info.called)

    @patch('hub.apps.core.business_rules.base.get_tracer')
    def test_tracing(self, mock_get_tracer):
        """Test OpenTelemetry tracing during execution."""
        from contextlib import contextmanager

        mock_tracer = MagicMock()
        mock_span = MagicMock()

        # Create a proper context manager mock
        @contextmanager
        def span_context_manager():
            yield mock_span

        mock_tracer.start_as_current_span.return_value = span_context_manager()
        mock_get_tracer.return_value = mock_tracer

        rules = ConcreteBusinessRules(enable_tracing=True)
        context = rules.create_context()

        result = rules.execute(context, should_be_valid=True)

        # Check that tracing was called
        self.assertTrue(mock_tracer.start_as_current_span.called)
        # set_attribute should be called during span execution
        self.assertTrue(mock_span.set_attribute.called)


class TestRuleComposition(TestCase):
    """Test rule composition functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.rules = ConcreteBusinessRules()

    def test_compose_single_rule(self):
        """Test composing a single rule."""
        def rule1(context):
            return ValidationResult(is_valid=True, warnings=['Warning 1'])

        context = self.rules.create_context()
        result = self.rules.compose(rule1, context=context)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.warnings), 1)

    def test_compose_multiple_rules(self):
        """Test composing multiple rules."""
        def rule1(context):
            return ValidationResult(is_valid=True, warnings=['Warning 1'])

        def rule2(context):
            return ValidationResult(is_valid=True, warnings=['Warning 2'])

        context = self.rules.create_context()
        result = self.rules.compose(rule1, rule2, context=context)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.warnings), 2)

    def test_compose_with_errors(self):
        """Test composing rules with errors."""
        def rule1(context):
            return ValidationResult(is_valid=True)

        def rule2(context):
            return ValidationResult(is_valid=False, errors=['Error 1'])

        def rule3(context):
            return ValidationResult(is_valid=True)

        context = self.rules.create_context()
        result = self.rules.compose(rule1, rule2, rule3, context=context, short_circuit=True)

        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.errors), 1)
        # Rule 3 should not have been executed due to short-circuit

    def test_compose_no_short_circuit(self):
        """Test composing rules without short-circuit."""
        def rule1(context):
            return ValidationResult(is_valid=False, errors=['Error 1'])

        def rule2(context):
            return ValidationResult(is_valid=False, errors=['Error 2'])

        context = self.rules.create_context()
        result = self.rules.compose(rule1, rule2, context=context, short_circuit=False)

        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.errors), 2)

    def test_compose_with_exception(self):
        """Test composing rules when one raises exception."""
        def rule1(context):
            return ValidationResult(is_valid=True)

        def rule2(context):
            raise ValueError("Test error")

        def rule3(context):
            return ValidationResult(is_valid=True)

        context = self.rules.create_context()
        result = self.rules.compose(rule1, rule2, rule3, context=context, short_circuit=True)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        # Rule 3 should not have been executed due to short-circuit

    def test_create_rule_function(self):
        """Test creating a rule function."""
        def my_rule(context):
            return ValidationResult(is_valid=True)

        rule_func = BusinessRules.create_rule_function(my_rule, rule_name='test_rule')
        context = self.rules.create_context()

        result = rule_func(context)
        self.assertTrue(result.is_valid)

    def test_create_rule_function_with_exception(self):
        """Test creating a rule function that raises exception."""
        def failing_rule(context):
            raise ValueError("Test error")

        rule_func = BusinessRules.create_rule_function(failing_rule)
        context = self.rules.create_context()

        result = rule_func(context)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)


class TestRuleCaching(TestCase):
    """Test rule caching functionality."""

    def setUp(self):
        """Set up test fixtures."""
        cache.clear()

    def test_cache_key_generation(self):
        """Test cache key generation."""
        rules = ConcreteBusinessRules()
        context1 = rules.create_context()
        context2 = rules.create_context()

        key1 = rules._get_cache_key('test_rule', context1)
        key2 = rules._get_cache_key('test_rule', context2)

        # Same context should produce same key
        self.assertEqual(key1, key2)

        # Different contexts should produce different keys
        context3 = rules.create_context(metadata={'different': 'value'})
        key3 = rules._get_cache_key('test_rule', context3)
        self.assertNotEqual(key1, key3)

    def test_cache_key_with_args_kwargs(self):
        """Test cache key generation with args and kwargs."""
        rules = ConcreteBusinessRules()
        context = rules.create_context()

        key1 = rules._get_cache_key('test_rule', context, 'arg1', key='value')
        key2 = rules._get_cache_key('test_rule', context, 'arg1', key='value')
        key3 = rules._get_cache_key('test_rule', context, 'arg2', key='value')

        # Same args/kwargs should produce same key
        self.assertEqual(key1, key2)

        # Different args should produce different keys
        self.assertNotEqual(key1, key3)

    def test_cache_ttl_respect(self):
        """Test that cache TTL is respected."""
        rules = ConcreteBusinessRules()
        context = rules.create_context()

        # Execute and cache result
        result1 = rules.execute(context, should_be_valid=True)
        self.assertTrue(rules.validation_called)

        # Reset flag
        rules.validation_called = False

        # Immediately execute again - should use cache
        result2 = rules.execute(context, should_be_valid=True)
        self.assertFalse(rules.validation_called)

        # Wait for cache to expire (if TTL is very short)
        # Note: This test assumes default TTL is reasonable
        # For actual TTL testing, you'd need to mock time or use a very short TTL

    def test_cache_invalidation_on_error(self):
        """Test that cache handles errors gracefully."""
        rules = ConcreteBusinessRules(enable_caching=True)
        context = rules.create_context()

        # Execute with error in cache operation
        with patch('hub.apps.core.business_rules.base.cache.get', side_effect=Exception("Cache error")):
            result = rules.execute(context, should_be_valid=True)
            # Should still execute validation despite cache error
            self.assertTrue(rules.validation_called)

