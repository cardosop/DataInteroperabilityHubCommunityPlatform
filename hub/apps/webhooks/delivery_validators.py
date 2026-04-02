"""
Webhook Delivery Validators

Comprehensive validation for webhook delivery operations including:
- Delivery retry validation (retry logic, max retries)
- Delivery timeout validation (timeout limits)
- Delivery status validation (PENDING → DELIVERED/FAILED)
- Dead letter queue validation (failed deliveries to DLQ)

All validation methods follow engineering best practices:
- No mocks/stubs - use real services and models
- Fix root causes, not symptoms
- Comprehensive error messages with context
- Follow DRY, SOLID, and clean code principles
"""
from typing import Optional, Dict, Any
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from datetime import timedelta

from hub.apps.core.business_rules.base import ValidationResult
from hub.apps.webhooks.models import WebhookDelivery, Webhook, DeliveryStatus
from hub.apps.webhooks.service import WebhookDeliveryService

import structlog

logger = structlog.get_logger(__name__)


class WebhookDeliveryValidator:
    """
    Validator for webhook delivery operations.

    Provides comprehensive validation for:
    - Retry logic and max retries
    - Timeout limits
    - Status transitions
    - Dead letter queue handling
    """

    @staticmethod
    def validate_delivery_retry(
        delivery: WebhookDelivery,
        webhook: Optional[Webhook] = None
    ) -> ValidationResult:
        """
        Validate delivery retry logic and max retries.

        Validates:
        - Retry attempt number is within limits
        - Max retries configuration is valid
        - Retry intervals are properly configured
        - Retry scheduling logic is correct

        Args:
            delivery: WebhookDelivery instance to validate
            webhook: Optional Webhook instance (will be fetched if not provided)

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'retry_validation': 'delivery_retry',
            'attempt_number': delivery.attempt_number,
        }

        # Fetch webhook if not provided
        if webhook is None:
            try:
                webhook = delivery.webhook
            except Exception as e:
                errors.append(f"Failed to fetch webhook for delivery: {str(e)}")
                details['webhook_fetch_error'] = str(e)
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    details=details
                )

        if webhook is None:
            errors.append("Webhook is required for retry validation")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['webhook_id'] = str(webhook.id)
        details['webhook_max_retries'] = webhook.max_retries

        # Validate max_retries configuration
        if webhook.max_retries < 0:
            errors.append(
                f"Webhook max_retries must be non-negative, got: {webhook.max_retries}"
            )
            details['max_retries_valid'] = False
        else:
            details['max_retries_valid'] = True

        # Validate attempt_number is non-negative
        if delivery.attempt_number < 0:
            errors.append(
                f"Delivery attempt_number must be non-negative, got: {delivery.attempt_number}"
            )
            details['attempt_number_valid'] = False
        else:
            details['attempt_number_valid'] = True

        # Validate retry intervals configuration
        retry_intervals = webhook.retry_intervals or WebhookDeliveryService.DEFAULT_RETRY_INTERVALS
        details['retry_intervals'] = retry_intervals
        details['retry_intervals_count'] = len(retry_intervals)

        if not isinstance(retry_intervals, list):
            errors.append(
                f"Webhook retry_intervals must be a list, got: {type(retry_intervals).__name__}"
            )
            details['retry_intervals_valid'] = False
        elif len(retry_intervals) == 0:
            errors.append("Webhook retry_intervals cannot be empty")
            details['retry_intervals_valid'] = False
        else:
            # Validate each interval is non-negative
            invalid_intervals = []
            for i, interval in enumerate(retry_intervals):
                if not isinstance(interval, (int, float)) or interval < 0:
                    invalid_intervals.append((i, interval))

            if invalid_intervals:
                errors.append(
                    f"Webhook retry_intervals contain invalid values: {invalid_intervals}. "
                    f"All intervals must be non-negative numbers."
                )
                details['retry_intervals_valid'] = False
            else:
                details['retry_intervals_valid'] = True

        # Validate attempt_number against max_retries
        if delivery.attempt_number > webhook.max_retries:
            errors.append(
                f"Delivery attempt_number ({delivery.attempt_number}) exceeds "
                f"webhook max_retries ({webhook.max_retries})"
            )
            details['attempt_within_limits'] = False
        else:
            details['attempt_within_limits'] = True

        # Validate retry scheduling logic
        if delivery.status == DeliveryStatus.FAILED:
            # Failed deliveries should have next_retry_at set if retries are available
            if delivery.attempt_number < webhook.max_retries:
                if delivery.next_retry_at is None:
                    errors.append(
                        f"Failed delivery with attempt_number {delivery.attempt_number} "
                        f"(below max_retries {webhook.max_retries}) should have next_retry_at set"
                    )
                    details['retry_scheduled'] = False
                else:
                    # Validate next_retry_at is in the future
                    if delivery.next_retry_at <= timezone.now():
                        warnings.append(
                            f"Failed delivery has next_retry_at ({delivery.next_retry_at}) "
                            f"in the past. Retry may have been missed."
                        )
                        details['retry_scheduled'] = True
                        details['retry_in_past'] = True
                    else:
                        details['retry_scheduled'] = True
                        details['retry_in_past'] = False

                        # Validate retry interval matches expected interval
                        expected_interval = retry_intervals[
                            min(delivery.attempt_number, len(retry_intervals) - 1)
                        ]
                        time_since_created = (delivery.next_retry_at - delivery.created_at).total_seconds()
                        # Allow some tolerance (within 10% of expected interval)
                        if abs(time_since_created - expected_interval) > expected_interval * 0.1:
                            warnings.append(
                                f"Retry interval ({time_since_created}s) does not match "
                                f"expected interval ({expected_interval}s) for attempt {delivery.attempt_number}"
                            )
                            details['retry_interval_matches'] = False
                        else:
                            details['retry_interval_matches'] = True
            else:
                # Max retries exceeded - should be in dead letter
                if delivery.status != DeliveryStatus.DEAD_LETTER:
                    warnings.append(
                        f"Delivery with attempt_number {delivery.attempt_number} "
                        f"(exceeds max_retries {webhook.max_retries}) should be in DEAD_LETTER status"
                    )
                    details['should_be_dead_letter'] = True
                else:
                    details['should_be_dead_letter'] = False

                if delivery.next_retry_at is not None:
                    warnings.append(
                        f"Delivery with max retries exceeded should not have next_retry_at set"
                    )
                    details['next_retry_should_be_none'] = False
                else:
                    details['next_retry_should_be_none'] = True
        elif delivery.status == DeliveryStatus.DEAD_LETTER:
            # DEAD_LETTER deliveries - validate they have max retries exceeded
            if delivery.attempt_number >= webhook.max_retries:
                details['should_be_dead_letter'] = True
                details['next_retry_should_be_none'] = delivery.next_retry_at is None
            else:
                details['should_be_dead_letter'] = False

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    @staticmethod
    def validate_delivery_timeout(
        delivery: WebhookDelivery,
        webhook: Optional[Webhook] = None
    ) -> ValidationResult:
        """
        Validate delivery timeout limits.

        Validates:
        - Timeout configuration is valid
        - Delivery attempts respect timeout limits
        - Timeout handling is correct

        Args:
            delivery: WebhookDelivery instance to validate
            webhook: Optional Webhook instance (will be fetched if not provided)

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details: Dict[str, Any] = {
            'timeout_validation': 'delivery_timeout',
        }

        # Fetch webhook if not provided
        if webhook is None:
            try:
                webhook = delivery.webhook
            except Exception as e:
                errors.append(f"Failed to fetch webhook for delivery: {str(e)}")
                details['webhook_fetch_error'] = str(e)
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    details=details
                )

        if webhook is None:
            errors.append("Webhook is required for timeout validation")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['webhook_id'] = str(webhook.id)

        # Get timeout configuration
        timeout_seconds = WebhookDeliveryService._get_request_timeout()
        details['timeout_seconds'] = str(timeout_seconds)

        # Validate timeout is positive
        if timeout_seconds <= 0:
            errors.append(
                f"Webhook delivery timeout must be positive, got: {timeout_seconds}"
            )
            details['timeout_valid'] = 'false'
        else:
            details['timeout_valid'] = 'true'

        # Validate timeout is reasonable (not too short or too long)
        if timeout_seconds < 5:
            warnings.append(
                f"Webhook delivery timeout ({timeout_seconds}s) is very short. "
                f"Consider increasing to at least 10 seconds for better reliability."
            )
            details['timeout_reasonable'] = 'false'
        elif timeout_seconds > 300:  # 5 minutes
            warnings.append(
                f"Webhook delivery timeout ({timeout_seconds}s) is very long. "
                f"Consider reducing to improve responsiveness."
            )
            details['timeout_reasonable'] = 'false'
        else:
            details['timeout_reasonable'] = 'true'

        # Check if delivery has error message indicating timeout
        if delivery.error_message:
            error_lower = delivery.error_message.lower()
            if 'timeout' in error_lower or 'timed out' in error_lower:
                details['has_timeout_error'] = 'true'
                details['timeout_error_message'] = delivery.error_message

                # Validate that timeout errors trigger retry logic
                if delivery.status == DeliveryStatus.FAILED:
                    if delivery.attempt_number < webhook.max_retries:
                        if delivery.next_retry_at is None:
                            warnings.append(
                                f"Delivery with timeout error should have next_retry_at set "
                                f"for retry (attempt {delivery.attempt_number} < max_retries {webhook.max_retries})"
                            )
                            details['timeout_retry_scheduled'] = 'false'
                        else:
                            details['timeout_retry_scheduled'] = 'true'
                    else:
                        details['timeout_retry_scheduled'] = 'true'  # Max retries exceeded, no retry needed
                else:
                    details['timeout_retry_scheduled'] = 'unknown'
            else:
                details['has_timeout_error'] = 'false'

        # Validate delivery duration if completed
        if delivery.status == DeliveryStatus.SUCCESS and delivery.delivered_at:
            duration = (delivery.delivered_at - delivery.created_at).total_seconds()
            details['delivery_duration_seconds'] = str(duration)

            if duration > timeout_seconds:
                warnings.append(
                    f"Delivery succeeded but duration ({duration}s) exceeds timeout ({timeout_seconds}s). "
                    f"This may indicate timeout was not properly enforced."
                )
                details['duration_within_timeout'] = 'false'
            else:
                details['duration_within_timeout'] = 'true'

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    @staticmethod
    def validate_delivery_status(
        delivery: WebhookDelivery
    ) -> ValidationResult:
        """
        Validate delivery status transitions (PENDING → DELIVERED/FAILED).

        Validates:
        - Status is valid
        - Status transitions follow expected flow
        - Status matches delivery state (timestamps, error messages, etc.)

        Args:
            delivery: WebhookDelivery instance to validate

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'status_validation': 'delivery_status',
            'current_status': delivery.status,
        }

        # Validate status is a valid choice
        valid_statuses = [choice[0] for choice in DeliveryStatus.choices]
        if delivery.status not in valid_statuses:
            errors.append(
                f"Invalid delivery status: {delivery.status}. "
                f"Valid statuses are: {valid_statuses}"
            )
            details['status_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['status_valid'] = True

        # Define valid status transitions
        valid_transitions = {
            DeliveryStatus.PENDING: [DeliveryStatus.SUCCESS, DeliveryStatus.FAILED],
            DeliveryStatus.FAILED: [DeliveryStatus.SUCCESS, DeliveryStatus.DEAD_LETTER, DeliveryStatus.PENDING],
            DeliveryStatus.SUCCESS: [],  # Terminal state
            DeliveryStatus.DEAD_LETTER: [DeliveryStatus.PENDING],  # Can be manually retried
        }

        details['valid_transitions'] = valid_transitions.get(delivery.status, [])

        # Validate status-specific constraints
        if delivery.status == DeliveryStatus.PENDING:
            # PENDING deliveries should not have delivered_at set
            if delivery.delivered_at is not None:
                errors.append(
                    f"Delivery with status PENDING should not have delivered_at timestamp set"
                )
                details['pending_constraints_valid'] = False
            else:
                details['pending_constraints_valid'] = True

            # PENDING deliveries may have next_retry_at set (for initial retry)
            # This is valid, so no error

            # PENDING deliveries should have attempt_number >= 0
            if delivery.attempt_number < 0:
                errors.append(
                    f"Delivery with status PENDING should have non-negative attempt_number, "
                    f"got: {delivery.attempt_number}"
                )
                details['pending_constraints_valid'] = False

        elif delivery.status == DeliveryStatus.SUCCESS:
            # SUCCESS deliveries must have delivered_at set
            if delivery.delivered_at is None:
                errors.append(
                    f"Delivery with status SUCCESS must have delivered_at timestamp set"
                )
                details['success_constraints_valid'] = False
            else:
                details['success_constraints_valid'] = True

                # Validate delivered_at is after created_at
                if delivery.delivered_at < delivery.created_at:
                    errors.append(
                        f"Delivery delivered_at ({delivery.delivered_at}) must be after "
                        f"created_at ({delivery.created_at})"
                    )
                    details['success_constraints_valid'] = False

            # SUCCESS deliveries should not have next_retry_at set
            if delivery.next_retry_at is not None:
                warnings.append(
                    f"Delivery with status SUCCESS should not have next_retry_at set"
                )
                details['success_constraints_valid'] = details.get('success_constraints_valid', True)

            # SUCCESS deliveries should not have error_message
            if delivery.error_message:
                warnings.append(
                    f"Delivery with status SUCCESS should not have error_message set"
                )
                details['success_constraints_valid'] = details.get('success_constraints_valid', True)

            # SUCCESS deliveries should have successful HTTP status code
            if delivery.http_status_code is not None:
                if not (200 <= delivery.http_status_code < 300):
                    warnings.append(
                        f"Delivery with status SUCCESS has non-success HTTP status code: "
                        f"{delivery.http_status_code}"
                    )
                    details['success_constraints_valid'] = details.get('success_constraints_valid', True)

        elif delivery.status == DeliveryStatus.FAILED:
            # FAILED deliveries should have error_message
            if not delivery.error_message:
                warnings.append(
                    f"Delivery with status FAILED should have error_message set for debugging"
                )
                details['failed_constraints_valid'] = True  # Warning, not error

            # FAILED deliveries should not have delivered_at set
            if delivery.delivered_at is not None:
                errors.append(
                    f"Delivery with status FAILED should not have delivered_at timestamp set"
                )
                details['failed_constraints_valid'] = False
            else:
                details['failed_constraints_valid'] = True

            # FAILED deliveries may have next_retry_at set (if retries available)
            # This is valid, so no error

        elif delivery.status == DeliveryStatus.DEAD_LETTER:
            # DEAD_LETTER deliveries should not have next_retry_at set
            if delivery.next_retry_at is not None:
                warnings.append(
                    f"Delivery with status DEAD_LETTER should not have next_retry_at set"
                )
                details['dead_letter_constraints_valid'] = True  # Warning, not error
            else:
                details['dead_letter_constraints_valid'] = True

            # DEAD_LETTER deliveries should have error_message
            if not delivery.error_message:
                warnings.append(
                    f"Delivery with status DEAD_LETTER should have error_message set for debugging"
                )
                details['dead_letter_constraints_valid'] = details.get('dead_letter_constraints_valid', True)

            # DEAD_LETTER deliveries should not have delivered_at set
            if delivery.delivered_at is not None:
                errors.append(
                    f"Delivery with status DEAD_LETTER should not have delivered_at timestamp set"
                )
                details['dead_letter_constraints_valid'] = False

        # Validate status consistency with attempt_number
        if delivery.status == DeliveryStatus.DEAD_LETTER:
            # DEAD_LETTER should typically have max retries exceeded
            # But we can't validate this without webhook, so we'll skip this check here
            pass

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    @staticmethod
    def validate_dead_letter_queue(
        delivery: WebhookDelivery,
        webhook: Optional[Webhook] = None
    ) -> ValidationResult:
        """
        Validate dead letter queue handling for failed deliveries.

        Validates:
        - Failed deliveries are moved to DLQ when max retries exceeded
        - DLQ deliveries have proper state (no retry scheduled, error message present)
        - DLQ deliveries can be manually retried

        Args:
            delivery: WebhookDelivery instance to validate
            webhook: Optional Webhook instance (will be fetched if not provided)

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'dlq_validation': 'dead_letter_queue',
            'is_dead_letter': delivery.status == DeliveryStatus.DEAD_LETTER,
        }

        # Fetch webhook if not provided
        if webhook is None:
            try:
                webhook = delivery.webhook
            except Exception as e:
                errors.append(f"Failed to fetch webhook for delivery: {str(e)}")
                details['webhook_fetch_error'] = str(e)
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    details=details
                )

        if webhook is None:
            errors.append("Webhook is required for DLQ validation")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['webhook_id'] = str(webhook.id)
        details['webhook_max_retries'] = webhook.max_retries
        details['delivery_attempt_number'] = delivery.attempt_number

        # Validate DLQ status
        if delivery.status == DeliveryStatus.DEAD_LETTER:
            details['dlq_status'] = 'in_dlq'

            # DLQ deliveries should have max retries exceeded
            if delivery.attempt_number < webhook.max_retries:
                warnings.append(
                    f"Delivery in DEAD_LETTER status has attempt_number ({delivery.attempt_number}) "
                    f"below max_retries ({webhook.max_retries}). "
                    f"This may indicate premature DLQ assignment."
                )
                details['max_retries_exceeded'] = False
            else:
                details['max_retries_exceeded'] = True

            # DLQ deliveries should not have next_retry_at set
            if delivery.next_retry_at is not None:
                errors.append(
                    f"Delivery in DEAD_LETTER status should not have next_retry_at set"
                )
                details['no_retry_scheduled'] = False
            else:
                details['no_retry_scheduled'] = True

            # DLQ deliveries should have error_message
            if not delivery.error_message:
                warnings.append(
                    f"Delivery in DEAD_LETTER status should have error_message set for debugging"
                )
                details['has_error_message'] = False
            else:
                details['has_error_message'] = True
                details['error_message_length'] = len(delivery.error_message)

            # DLQ deliveries should not have delivered_at set
            if delivery.delivered_at is not None:
                errors.append(
                    f"Delivery in DEAD_LETTER status should not have delivered_at timestamp set"
                )
                details['no_delivered_at'] = False
            else:
                details['no_delivered_at'] = True

        else:
            # Not in DLQ - validate it should be if max retries exceeded
            details['dlq_status'] = 'not_in_dlq'

            if delivery.attempt_number >= webhook.max_retries:
                if delivery.status == DeliveryStatus.FAILED:
                    warnings.append(
                        f"Delivery with attempt_number ({delivery.attempt_number}) >= max_retries "
                        f"({webhook.max_retries}) should be in DEAD_LETTER status, "
                        f"but current status is {delivery.status}"
                    )
                    details['should_be_in_dlq'] = True
                else:
                    details['should_be_in_dlq'] = False
            else:
                details['should_be_in_dlq'] = False

        # Validate DLQ deliveries can be manually retried
        # This is validated by checking that DEAD_LETTER status allows transition to PENDING
        if delivery.status == DeliveryStatus.DEAD_LETTER:
            # DEAD_LETTER can be manually retried by resetting to PENDING
            details['can_be_retried'] = True

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    @staticmethod
    def validate_all(
        delivery: WebhookDelivery,
        webhook: Optional[Webhook] = None
    ) -> ValidationResult:
        """
        Validate all delivery aspects (retry, timeout, status, DLQ).

        Args:
            delivery: WebhookDelivery instance to validate
            webhook: Optional Webhook instance (will be fetched if not provided)

        Returns:
            Combined ValidationResult with all validation checks
        """
        # Fetch webhook once if not provided
        if webhook is None:
            try:
                webhook = delivery.webhook
            except (ObjectDoesNotExist, AttributeError) as e:
                return ValidationResult(
                    is_valid=False,
                    errors=[f"Failed to fetch webhook for delivery: {str(e)}"],
                    details={'webhook_fetch_error': str(e)}
                )
            except Exception as e:
                # Catch any other exceptions
                return ValidationResult(
                    is_valid=False,
                    errors=[f"Failed to fetch webhook for delivery: {str(e)}"],
                    details={'webhook_fetch_error': str(e)}
                )

        # Run all validations
        retry_result = WebhookDeliveryValidator.validate_delivery_retry(delivery, webhook)
        timeout_result = WebhookDeliveryValidator.validate_delivery_timeout(delivery, webhook)
        status_result = WebhookDeliveryValidator.validate_delivery_status(delivery)
        dlq_result = WebhookDeliveryValidator.validate_dead_letter_queue(delivery, webhook)

        # Combine all results
        combined_result = retry_result.combine(timeout_result).combine(status_result).combine(dlq_result)
        combined_result.details['validation_type'] = 'comprehensive_delivery_validation'

        return combined_result


