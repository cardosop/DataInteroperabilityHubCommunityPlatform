"""
Unit tests for GraphQL CLI commands.

Tests: query command with different endpoints, file input, variables, error handling.
"""

from datahub_cli.main import cli


class TestGraphQLQuery:
    """Test graphql query command"""

    def test_query_strawberry_success(self, runner, mock_api_client):
        """Test GraphQL query against strawberry endpoint"""
        mock_api_client.post.return_value = {"data": {"assets": [{"id": "1", "name": "test"}]}}

        result = runner.invoke(cli, ["graphql", "query", "--query", "{ assets { id name } }"])

        assert result.exit_code == 0
        assert "assets" in result.output
        mock_api_client.post.assert_called_once()
        call_args = mock_api_client.post.call_args
        assert "/graphql/" in str(call_args)

    def test_query_graphene_endpoint(self, runner, mock_api_client):
        """Test GraphQL query against graphene endpoint"""
        mock_api_client.post.return_value = {"data": {"assets": []}}

        result = runner.invoke(
            cli, ["graphql", "query", "--query", "{ assets { id } }", "--endpoint", "graphene"]
        )

        assert result.exit_code == 0
        call_args = mock_api_client.post.call_args
        assert "/graphql-graphene/" in str(call_args)

    def test_query_ld_endpoint(self, runner, mock_api_client):
        """Test GraphQL query against linked-data endpoint"""
        mock_api_client.post.return_value = {"data": {}}

        result = runner.invoke(
            cli, ["graphql", "query", "--query", "{ assets { id } }", "--endpoint", "ld"]
        )

        assert result.exit_code == 0
        call_args = mock_api_client.post.call_args
        assert "/api/v1/semantic/graphql" in str(call_args)

    def test_query_missing_query_and_file(self, runner, mock_api_client):
        """Test query with neither --query nor --file raises error"""
        result = runner.invoke(cli, ["graphql", "query"])

        assert result.exit_code != 0
        assert "Either --query or --file is required" in result.output
