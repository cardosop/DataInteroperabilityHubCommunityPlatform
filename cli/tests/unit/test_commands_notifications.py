"""
Unit tests for Notifications CLI commands.

Tests: list, get, unread-count, read, read-all commands.
"""

from datahub_cli.main import cli


class TestNotificationsList:
    """Test notifications list command"""

    def test_list_all_notifications(self, runner, mock_api_client):
        """Test listing all notifications"""
        mock_api_client.get.return_value = {
            "results": [{"id": "notif-1", "message": "Test notification", "read": False}],
            "count": 1,
        }

        result = runner.invoke(cli, ["notifications", "list"])

        assert result.exit_code == 0
        assert "notif-1" in result.output
        mock_api_client.get.assert_called_once_with("notifications/user-notifications/")

    def test_list_unread_only(self, runner, mock_api_client):
        """Test listing unread notifications only"""
        mock_api_client.get.return_value = {"results": [], "count": 0}

        result = runner.invoke(cli, ["notifications", "list", "--unread-only"])

        assert result.exit_code == 0
        mock_api_client.get.assert_called_once_with("notifications/user-notifications/?unread=true")

    def test_list_api_error(self, runner, mock_api_client):
        """Test list handles API error gracefully"""
        mock_api_client.get.side_effect = Exception("Connection refused")

        result = runner.invoke(cli, ["notifications", "list"])

        assert result.exit_code != 0


class TestNotificationsGet:
    """Test notifications get command"""

    def test_get_notification_by_id(self, runner, mock_api_client):
        """Test getting a notification by ID"""
        mock_api_client.get.return_value = {"id": "notif-1", "message": "Details", "read": False}

        result = runner.invoke(cli, ["notifications", "get", "notif-1"])

        assert result.exit_code == 0
        assert "notif-1" in result.output
        mock_api_client.get.assert_called_once_with("notifications/user-notifications/notif-1/")


class TestNotificationsUnreadCount:
    """Test unread-count command"""

    def test_unread_count(self, runner, mock_api_client):
        """Test getting unread count"""
        mock_api_client.get.return_value = {"count": 5}

        result = runner.invoke(cli, ["notifications", "unread-count"])

        assert result.exit_code == 0
        assert "5" in result.output


class TestNotificationsRead:
    """Test read command"""

    def test_mark_notification_read(self, runner, mock_api_client):
        """Test marking a notification as read"""
        mock_api_client.post.return_value = {"status": "read"}

        result = runner.invoke(cli, ["notifications", "read", "notif-1"])

        assert result.exit_code == 0
        mock_api_client.post.assert_called_once_with(
            "notifications/user-notifications/notif-1/read/", json={}
        )


class TestNotificationsReadAll:
    """Test read-all command"""

    def test_mark_all_read(self, runner, mock_api_client):
        """Test marking all notifications as read"""
        mock_api_client.post.return_value = {"status": "all_read"}

        result = runner.invoke(cli, ["notifications", "read-all"])

        assert result.exit_code == 0
        mock_api_client.post.assert_called_once_with(
            "notifications/user-notifications/read-all/", json={}
        )
