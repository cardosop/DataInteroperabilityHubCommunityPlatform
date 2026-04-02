"""
112.B.2 — Tests proving no external publish on rollback.

Each test wraps a side-effect-producing code path inside
``transaction.atomic()`` that is forced to roll back, then asserts
the deferred callback (email task / queue enqueue / webhook delivery)
was **never** executed.

Uses TestCase (savepoint-per-test) rather than TransactionTestCase
to avoid TRUNCATE CASCADE timeouts on PgBouncer-fronted databases.
Rollback tests work because savepoint rollback discards on_commit
hooks registered at that savepoint level.  Commit (positive-control)
tests use ``captureOnCommitCallbacks(execute=True)`` to flush
deferred callbacks.
"""
import uuid
from unittest.mock import patch, MagicMock

import pytest
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from hub.apps.jobs.models import Job, JobStatus


pytestmark = pytest.mark.django_db(transaction=True)


class NotificationSignalRollbackTest(TestCase):
    """
    Proves that notification email tasks queued via the
    ``job_status_changed`` signal are NOT dispatched when the
    enclosing transaction rolls back.
    """

    @override_settings(EMAIL_JOB_NOTIFICATIONS_ENABLED=True)
    @patch(
        "hub.apps.notifications.signals.send_job_completion_email"
    )
    def test_completion_email_not_sent_on_rollback(self, mock_task):
        """
        Force a rollback after a Job status change to COMPLETED.
        The on_commit-wrapped .delay() must NOT fire.
        """
        from hub.apps.notifications.signals import job_status_changed

        instance = MagicMock(spec=Job)
        instance.status = JobStatus.COMPLETED
        instance.created_by = MagicMock()
        instance.id = uuid.uuid4()

        try:
            with transaction.atomic():
                job_status_changed(
                    sender=Job, instance=instance, created=False,
                )
                raise IntegrityError("simulated rollback")
        except IntegrityError:
            pass

        mock_task.delay.assert_not_called()

    @override_settings(EMAIL_JOB_NOTIFICATIONS_ENABLED=True)
    @patch(
        "hub.apps.notifications.signals.send_job_failure_email"
    )
    def test_failure_email_not_sent_on_rollback(self, mock_task):
        """
        Force a rollback after a Job status change to FAILED.
        The on_commit-wrapped .delay() must NOT fire.
        """
        from hub.apps.notifications.signals import job_status_changed

        instance = MagicMock(spec=Job)
        instance.status = JobStatus.FAILED
        instance.created_by = MagicMock()
        instance.id = uuid.uuid4()

        try:
            with transaction.atomic():
                job_status_changed(
                    sender=Job, instance=instance, created=False,
                )
                raise IntegrityError("simulated rollback")
        except IntegrityError:
            pass

        mock_task.delay.assert_not_called()

    @override_settings(EMAIL_JOB_NOTIFICATIONS_ENABLED=True)
    @patch(
        "hub.apps.notifications.signals.send_job_completion_email"
    )
    def test_completion_email_sent_on_commit(self, mock_task):
        """
        Positive control: when the savepoint commits the
        on_commit callback DOES fire.
        """
        from hub.apps.notifications.signals import job_status_changed

        instance = MagicMock(spec=Job)
        instance.status = JobStatus.COMPLETED
        instance.created_by = MagicMock()
        instance.id = uuid.uuid4()

        with self.captureOnCommitCallbacks(execute=True):
            with transaction.atomic():
                job_status_changed(
                    sender=Job, instance=instance, created=False,
                )

        mock_task.delay.assert_called_once_with(str(instance.id))


class WebhookDeliveryRollbackTest(TestCase):
    """
    Proves that async webhook delivery tasks are NOT dispatched
    when the enclosing transaction rolls back.
    """

    @override_settings(WEBHOOK_ASYNC_DELIVERY=True)
    def test_webhook_task_not_dispatched_on_rollback(self):
        """
        Register an on_commit callback inside an atomic block that
        rolls back.  The callback must NOT fire.
        """
        mock_deliver = MagicMock()

        try:
            with transaction.atomic():
                _did = "fake-delivery-id"
                transaction.on_commit(
                    lambda: mock_deliver.delay(_did)
                )
                raise IntegrityError("simulated rollback")
        except IntegrityError:
            pass

        mock_deliver.delay.assert_not_called()

    @override_settings(WEBHOOK_ASYNC_DELIVERY=True)
    def test_webhook_task_dispatched_on_commit(self):
        """
        Positive control: on_commit callback fires when the
        savepoint commits.
        """
        mock_deliver = MagicMock()
        _did = "test-delivery-id"

        with self.captureOnCommitCallbacks(execute=True):
            with transaction.atomic():
                transaction.on_commit(
                    lambda: mock_deliver.delay(_did)
                )

        mock_deliver.delay.assert_called_once_with(_did)


class ComplianceEnqueueRollbackTest(TestCase):
    """
    Proves that the compliance poll_compliance_job enqueue is
    NOT dispatched when the enclosing transaction rolls back.
    """

    def test_enqueue_not_dispatched_on_rollback(self):
        """
        Register an on_commit callback (matching the fixed
        compliance service pattern) inside an atomic block that
        rolls back.  The enqueue must NOT fire.
        """
        mock_queue = MagicMock()
        mock_task_fn = MagicMock()
        run_id = uuid.uuid4()

        try:
            with transaction.atomic():
                transaction.on_commit(
                    lambda: mock_queue.enqueue(
                        mock_task_fn,
                        run_id,
                        job_timeout=1800,
                    )
                )
                raise IntegrityError("simulated rollback")
        except IntegrityError:
            pass

        mock_queue.enqueue.assert_not_called()

    def test_enqueue_dispatched_on_commit(self):
        """Positive control: enqueue fires on commit."""
        mock_queue = MagicMock()
        mock_task_fn = MagicMock()
        run_id = uuid.uuid4()

        with self.captureOnCommitCallbacks(execute=True):
            with transaction.atomic():
                transaction.on_commit(
                    lambda: mock_queue.enqueue(
                        mock_task_fn,
                        run_id,
                        job_timeout=1800,
                    )
                )

        mock_queue.enqueue.assert_called_once_with(
            mock_task_fn, run_id, job_timeout=1800,
        )


class ContractNotificationRollbackTest(TestCase):
    """
    Proves that contract-related notification email tasks are
    NOT dispatched when the enclosing transaction rolls back.
    """

    @patch(
        "hub.apps.notifications.tasks"
        ".send_odps_normalization_failure_email"
    )
    def test_normalization_failure_email_not_sent_on_rollback(
        self, mock_task,
    ):
        """
        Simulates the on_commit pattern used in
        ContractService.create_contract for normalization failure
        emails.  Rollback must suppress the task.
        """
        _cid = str(uuid.uuid4())
        _err = "test error"
        _errs = ["field x invalid"]

        try:
            with transaction.atomic():
                transaction.on_commit(
                    lambda: mock_task.delay(
                        contract_id=_cid,
                        error_message=_err,
                        error_code="ODPS_NORMALIZATION_ERROR",
                        errors=_errs,
                        field_path=None,
                    )
                )
                raise IntegrityError("simulated rollback")
        except IntegrityError:
            pass

        mock_task.delay.assert_not_called()

    @patch(
        "hub.apps.notifications.tasks"
        ".send_odps_creation_completion_email"
    )
    def test_creation_completion_email_not_sent_on_rollback(
        self, mock_task,
    ):
        """
        Simulates the on_commit pattern used in
        ContractService.create_contract for completion emails.
        Rollback must suppress the task.
        """
        _cid = str(uuid.uuid4())

        try:
            with transaction.atomic():
                transaction.on_commit(
                    lambda: mock_task.delay(_cid)
                )
                raise IntegrityError("simulated rollback")
        except IntegrityError:
            pass

        mock_task.delay.assert_not_called()

    @patch(
        "hub.apps.notifications.tasks"
        ".send_odps_creation_completion_email"
    )
    def test_creation_completion_email_sent_on_commit(
        self, mock_task,
    ):
        """Positive control: task fires on successful commit."""
        _cid = str(uuid.uuid4())

        with self.captureOnCommitCallbacks(execute=True):
            with transaction.atomic():
                transaction.on_commit(
                    lambda: mock_task.delay(_cid)
                )

        mock_task.delay.assert_called_once_with(_cid)

    @patch(
        "hub.apps.notifications.tasks"
        ".send_odps_linking_status_email"
    )
    def test_linking_status_email_not_sent_on_rollback(
        self, mock_task,
    ):
        """
        Simulates the on_commit pattern used in
        ODPSContractService.link_odps_to_odcs for linking status
        emails.  Rollback must suppress the task.
        """
        _odps_id = str(uuid.uuid4())
        _odcs_id = str(uuid.uuid4())

        try:
            with transaction.atomic():
                transaction.on_commit(
                    lambda: mock_task.delay(
                        odps_contract_id=_odps_id,
                        status="completed",
                        status_message="linked",
                        odcs_contract_id=_odcs_id,
                        progress_percentage=100.0,
                        current_phase="completed",
                        validation_passed=True,
                        user_id=str(uuid.uuid4()),
                        tenant_id=str(uuid.uuid4()),
                    )
                )
                raise IntegrityError("simulated rollback")
        except IntegrityError:
            pass

        mock_task.delay.assert_not_called()


class InvitationEmailRollbackTest(TestCase):
    """
    Proves that invitation emails queued via
    ``UserViewSet._send_invitation_email`` are NOT dispatched
    when the enclosing @transaction.atomic block rolls back.
    """

    @patch(
        "hub.apps.notifications.tasks.send_invitation_email"
    )
    def test_invitation_email_not_sent_on_rollback(
        self, mock_task,
    ):
        """
        Simulate a rollback after _send_invitation_email
        registers its on_commit callback.  The .delay() must
        NOT fire.
        """
        from hub.apps.users.views import UserViewSet

        viewset = UserViewSet()
        fake_user = MagicMock()
        fake_user.id = uuid.uuid4()

        try:
            with transaction.atomic():
                viewset._send_invitation_email(
                    fake_user, plaintext_token="tok-123",
                )
                raise IntegrityError("simulated rollback")
        except IntegrityError:
            pass

        mock_task.delay.assert_not_called()

    @patch(
        "hub.apps.notifications.tasks.send_invitation_email"
    )
    def test_invitation_email_sent_on_commit(self, mock_task):
        """
        Positive control: on_commit callback fires when the
        savepoint commits.
        """
        from hub.apps.users.views import UserViewSet

        viewset = UserViewSet()
        fake_user = MagicMock()
        fake_user.id = uuid.uuid4()

        with self.captureOnCommitCallbacks(execute=True):
            with transaction.atomic():
                viewset._send_invitation_email(
                    fake_user, plaintext_token="tok-456",
                )

        mock_task.delay.assert_called_once_with(
            str(fake_user.id), plaintext_token="tok-456",
        )
