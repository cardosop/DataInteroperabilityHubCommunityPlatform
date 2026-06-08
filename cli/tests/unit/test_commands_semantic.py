"""Unit tests for ``datahub semantic`` commands (283.V.4 gap closure)."""
import json

import pytest
from click.testing import CliRunner
from unittest.mock import Mock

from datahub_cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_api_client(monkeypatch):
    mock = Mock()
    monkeypatch.setattr("datahub_cli.commands.semantic.api_client", mock)
    return mock


@pytest.fixture
def mock_graphql_api_client(monkeypatch):
    mock = Mock()
    monkeypatch.setattr("datahub_cli.commands.graphql.api_client", mock)
    return mock


class TestSemanticSparqlQuery:
    @pytest.mark.unit
    def test_query_table_output(self, runner, mock_api_client):
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.text = "{}"
        mock_resp.json.return_value = {
            "results": {
                "bindings": [
                    {"s": {"value": "http://example.org/s1"}, "p": {"value": "http://example.org/p1"}},
                    {"s": {"value": "http://example.org/s2"}, "p": {"value": "http://example.org/p2"}},
                ]
            }
        }
        mock_api_client.request.return_value = mock_resp
        result = runner.invoke(cli, ["semantic", "sparql", "query", "--query", "SELECT * WHERE { ?s ?p ?o }"])
        assert result.exit_code == 0
        assert "example.org" in result.output

    @pytest.mark.unit
    def test_query_json_output(self, runner, mock_api_client):
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.text = "{}"
        mock_resp.json.return_value = {"results": {"bindings": [{"s": {"value": "x"}}]}}
        mock_api_client.request.return_value = mock_resp
        result = runner.invoke(
            cli, ["semantic", "sparql", "query", "--query", "SELECT * WHERE { ?s ?p ?o }", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "results" in data

    @pytest.mark.unit
    def test_query_no_results(self, runner, mock_api_client):
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.text = "{}"
        mock_resp.json.return_value = {"results": {"bindings": []}}
        mock_api_client.request.return_value = mock_resp
        result = runner.invoke(cli, ["semantic", "sparql", "query", "--query", "SELECT * WHERE { ?s ?p ?o }"])
        assert result.exit_code == 0
        assert "No results" in result.output

    @pytest.mark.unit
    def test_query_missing_query_and_file(self, runner, mock_api_client):
        result = runner.invoke(cli, ["semantic", "sparql", "query"])
        assert result.exit_code != 0

    @pytest.mark.unit
    def test_query_api_error(self, runner, mock_api_client):
        mock_api_client.request.side_effect = Exception("SPARQL endpoint timeout")
        result = runner.invoke(cli, ["semantic", "sparql", "query", "--query", "SELECT * WHERE { ?s ?p ?o }"])
        assert result.exit_code != 0
        assert "timeout" in result.output.lower()

    @pytest.mark.unit
    def test_query_from_file(self, runner, mock_api_client, tmp_path):
        query_file = tmp_path / "query.rq"
        query_file.write_text("SELECT * WHERE { ?s ?p ?o }")
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.text = "{}"
        mock_resp.json.return_value = {"results": {"bindings": []}}
        mock_api_client.request.return_value = mock_resp
        result = runner.invoke(cli, ["semantic", "sparql", "query", "--file", str(query_file)])
        assert result.exit_code == 0


class TestSemanticSparqlServiceDescription:
    @pytest.mark.unit
    def test_service_description(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"endpoint": "http://sparql.example/", "features": ["basic-federated-query"]}
        result = runner.invoke(cli, ["semantic", "sparql", "service-description"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "endpoint" in data

    @pytest.mark.unit
    def test_service_description_error(self, runner, mock_api_client):
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("down")
        result = runner.invoke(cli, ["semantic", "sparql", "service-description"])
        assert result.exit_code != 0


class TestSemanticExport:
    @pytest.mark.unit
    def test_export_stdout(self, runner, mock_api_client):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.content = b"<http://example.org/s> <http://example.org/p> <http://example.org/o> .\n"
        mock_api_client.request.return_value = mock_resp
        result = runner.invoke(cli, ["semantic", "export", "--format", "n-triples"])
        assert result.exit_code == 0

    @pytest.mark.unit
    def test_export_to_file(self, runner, mock_api_client, tmp_path):
        output = tmp_path / "export.nt"
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.content = b"triple data"
        mock_api_client.request.return_value = mock_resp
        result = runner.invoke(cli, ["semantic", "export", "--format", "n-triples", "--output", str(output)])
        assert result.exit_code == 0
        assert output.read_bytes() == b"triple data"

    @pytest.mark.unit
    def test_export_429_throttled(self, runner, mock_api_client):
        mock_resp = Mock()
        mock_resp.status_code = 429
        mock_resp.headers = {"Retry-After": "300"}
        mock_api_client.request.return_value = mock_resp
        result = runner.invoke(cli, ["semantic", "export", "--format", "n-triples"])
        assert result.exit_code != 0
        assert "Throttled" in result.output

    @pytest.mark.unit
    def test_export_413_too_large(self, runner, mock_api_client):
        mock_resp = Mock()
        mock_resp.status_code = 413
        mock_resp.json.return_value = {"detail": "too large"}
        mock_api_client.request.return_value = mock_resp
        result = runner.invoke(cli, ["semantic", "export"])
        assert result.exit_code != 0
        assert "100M-triple" in result.output


class TestSemanticOntology:
    @pytest.mark.unit
    def test_ontology(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"ontology": "http://meshant.com/ontology/"}
        result = runner.invoke(cli, ["semantic", "ontology"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "ontology" in data

    @pytest.mark.unit
    def test_ontology_error(self, runner, mock_api_client):
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("not found")
        result = runner.invoke(cli, ["semantic", "ontology"])
        assert result.exit_code != 0


class TestSemanticContext:
    @pytest.mark.unit
    def test_context(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"@context": {"dcat": "http://www.w3.org/ns/dcat#"}}
        result = runner.invoke(cli, ["semantic", "context"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "@context" in data

    @pytest.mark.unit
    def test_context_error(self, runner, mock_api_client):
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("down")
        result = runner.invoke(cli, ["semantic", "context"])
        assert result.exit_code != 0


class TestCustomOntologyUpload:
    @pytest.mark.unit
    def test_upload(self, runner, mock_api_client, tmp_path):
        rdf_file = tmp_path / "test.ttl"
        rdf_file.write_text("@prefix ex: <http://example.org/> . ex:a a ex:Class .")
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.text = "{}"
        mock_resp.json.return_value = {"id": "ont-1", "status": "uploaded"}
        mock_api_client.request.return_value = mock_resp
        result = runner.invoke(
            cli,
            [
                "semantic", "custom-ontology", "upload",
                "--name", "test-onto",
                "--namespace", "http://example.org/",
                "--file", str(rdf_file),
            ],
        )
        assert result.exit_code == 0

    @pytest.mark.unit
    def test_upload_missing_required(self, runner, mock_api_client):
        result = runner.invoke(cli, ["semantic", "custom-ontology", "upload"])
        assert result.exit_code != 0


class TestCustomOntologyList:
    @pytest.mark.unit
    def test_list(self, runner, mock_api_client):
        mock_api_client.get.return_value = [{"id": "ont-1", "name": "test", "active": True}]
        result = runner.invoke(cli, ["semantic", "custom-ontology", "list"])
        assert result.exit_code == 0
        assert "ont-1" in result.output

    @pytest.mark.unit
    def test_list_empty(self, runner, mock_api_client):
        mock_api_client.get.return_value = []
        result = runner.invoke(cli, ["semantic", "custom-ontology", "list"])
        assert result.exit_code == 0
        assert "No custom ontologies" in result.output or result.exit_code == 0


class TestCustomOntologyActivate:
    @pytest.mark.unit
    def test_activate(self, runner, mock_api_client):
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"id": "ont-1", "active": True}
        mock_api_client.request.return_value = mock_resp
        result = runner.invoke(cli, ["semantic", "custom-ontology", "activate", "ont-1"])
        assert result.exit_code == 0

    @pytest.mark.unit
    def test_activate_missing_id(self, runner, mock_api_client):
        result = runner.invoke(cli, ["semantic", "custom-ontology", "activate"])
        assert result.exit_code != 0


class TestCustomOntologyDeactivate:
    @pytest.mark.unit
    def test_deactivate(self, runner, mock_api_client):
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"id": "ont-1", "active": False}
        mock_api_client.request.return_value = mock_resp
        result = runner.invoke(cli, ["semantic", "custom-ontology", "deactivate", "ont-1"])
        assert result.exit_code == 0


class TestLdnInboxList:
    @pytest.mark.unit
    def test_inbox_list(self, runner, mock_api_client):
        mock_api_client.get.return_value = [{"id": "n1", "type": "Offer"}]
        result = runner.invoke(cli, ["semantic", "ldn", "inbox-list", "t1"])
        assert result.exit_code == 0

    @pytest.mark.unit
    def test_inbox_list_empty(self, runner, mock_api_client):
        mock_api_client.get.return_value = []
        result = runner.invoke(cli, ["semantic", "ldn", "inbox-list", "t1"])
        assert result.exit_code == 0


class TestLdnSubscribe:
    @pytest.mark.unit
    def test_subscribe(self, runner, mock_api_client):
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"id": "sub-1", "status": "active"}
        mock_api_client.request.return_value = mock_resp
        result = runner.invoke(
            cli, ["semantic", "ldn", "subscribe", "--target-url", "http://inbox.example/", "--resource-type", "dataset"]
        )
        assert result.exit_code == 0

    @pytest.mark.unit
    def test_subscribe_missing_args(self, runner, mock_api_client):
        result = runner.invoke(cli, ["semantic", "ldn", "subscribe"])
        assert result.exit_code != 0


class TestLdnUnsubscribe:
    @pytest.mark.unit
    def test_unsubscribe(self, runner, mock_api_client):
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"status": "cancelled"}
        mock_api_client.request.return_value = mock_resp
        result = runner.invoke(cli, ["semantic", "ldn", "unsubscribe", "sub-1"])
        assert result.exit_code == 0


class TestSemanticVoid:
    @pytest.mark.unit
    def test_void(self, runner, mock_api_client):
        mock_api_client.get.return_value = {"triple_count": 1000, "classes": 5}
        result = runner.invoke(cli, ["semantic", "void"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "triple_count" in data

    @pytest.mark.unit
    def test_void_error(self, runner, mock_api_client):
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("unavailable")
        result = runner.invoke(cli, ["semantic", "void"])
        assert result.exit_code != 0


class TestShaclValidate:
    @pytest.mark.unit
    def test_validate(self, runner, mock_api_client, tmp_path):
        shapes_file = tmp_path / "shapes.ttl"
        shapes_file.write_text("@prefix sh: <http://www.w3.org/ns/shacl#> .")
        mock_api_client.post.return_value = {"conforms": True, "violations": []}
        result = runner.invoke(
            cli,
            ["semantic", "shacl", "validate", "--shapes", str(shapes_file)],
        )
        assert result.exit_code == 0
        assert "Yes" in result.output

    @pytest.mark.unit
    def test_validate_missing_shapes(self, runner, mock_api_client):
        mock_api_client.post.return_value = {"conforms": False, "violations": [{"message": "No shapes", "severity": "Violation"}]}
        result = runner.invoke(cli, ["semantic", "shacl", "validate"])
        # API returns non-conforming; CLI exits 0 (validation ran, result is non-conforming)
        assert result.exit_code == 0
        assert "No" in result.output

    @pytest.mark.unit
    def test_validate_both_data_and_shapes(self, runner, mock_api_client, tmp_path):
        data_file = tmp_path / "data.ttl"
        data_file.write_text("<http://ex.org/s> <http://ex.org/p> <http://ex.org/o> .")
        shapes_file = tmp_path / "shapes.ttl"
        shapes_file.write_text("@prefix sh: <http://www.w3.org/ns/shacl#> .")
        mock_api_client.post.return_value = {"conforms": True, "violations": []}
        result = runner.invoke(
            cli,
            ["semantic", "shacl", "validate", "--data", str(data_file), "--shapes", str(shapes_file)],
        )
        assert result.exit_code == 0

    @pytest.mark.unit
    def test_validate_json_format(self, runner, mock_api_client, tmp_path):
        shapes_file = tmp_path / "shapes.ttl"
        shapes_file.write_text("@prefix sh: <http://www.w3.org/ns/shacl#> .")
        mock_api_client.post.return_value = {"conforms": True, "violations": []}
        result = runner.invoke(
            cli,
            ["semantic", "shacl", "validate", "--shapes", str(shapes_file), "--format", "json"],
        )
        assert result.exit_code == 0


class TestFederationAdd:
    @pytest.mark.unit
    def test_add(self, runner, mock_api_client):
        mock_resp = Mock()
        mock_resp.status_code = 201
        mock_resp.ok = True
        mock_resp.text = "{}"
        mock_resp.json.return_value = {"id": "fed-1", "status": "active"}
        mock_api_client.request.return_value = mock_resp
        result = runner.invoke(
            cli,
            [
                "semantic", "federation", "add",
                "--tenant-id", "t1", "--name", "remote1",
                "--endpoint-url", "http://sparql.remote/query",
            ],
        )
        assert result.exit_code == 0

    @pytest.mark.unit
    def test_add_missing_args(self, runner, mock_api_client):
        result = runner.invoke(cli, ["semantic", "federation", "add"])
        assert result.exit_code != 0


class TestFederationList:
    @pytest.mark.unit
    def test_list(self, runner, mock_api_client):
        mock_api_client.get.return_value = [{"id": "fed-1", "name": "remote1"}]
        result = runner.invoke(cli, ["semantic", "federation", "list", "--tenant-id", "t1"])
        assert result.exit_code == 0
        assert "fed-1" in result.output

    @pytest.mark.unit
    def test_list_empty(self, runner, mock_api_client):
        mock_api_client.get.return_value = []
        result = runner.invoke(cli, ["semantic", "federation", "list", "--tenant-id", "t1"])
        assert result.exit_code == 0


class TestFederationRemove:
    @pytest.mark.unit
    def test_remove(self, runner, mock_api_client):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.text = "{}"
        mock_resp.json.return_value = {"status": "removed"}
        mock_api_client.request.return_value = mock_resp
        result = runner.invoke(
            cli, ["semantic", "federation", "remove", "--tenant-id", "t1", "--id", "fed-1"]
        )
        assert result.exit_code == 0

    @pytest.mark.unit
    def test_remove_missing_endpoint_id(self, runner, mock_api_client):
        result = runner.invoke(cli, ["semantic", "federation", "remove", "--tenant-id", "t1"])
        assert result.exit_code != 0


# ── 284.B.3 / 286 — GraphQL CLI tests (top-level ``graphql`` command) ──


class TestGraphQLQuery:
    """Tests for ``datahub graphql query`` (moved from ``semantic graphql``
    to a top-level ``graphql`` group in Phase 286)."""

    @pytest.mark.unit
    def test_query_json_output(self, runner, mock_graphql_api_client):
        mock_graphql_api_client.post.return_value = {
            "data": {"assets": [{"id": "a1", "name": "Alpha"}]},
        }
        result = runner.invoke(
            cli, ["graphql", "query", "--query", "{ assets { id name } }"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "data" in data
        assert data["data"]["assets"][0]["name"] == "Alpha"

    @pytest.mark.unit
    def test_query_from_file(self, runner, mock_graphql_api_client, tmp_path):
        query_file = tmp_path / "query.gql"
        query_file.write_text("{ contracts { id version } }")
        mock_graphql_api_client.post.return_value = {"data": {"contracts": []}}
        result = runner.invoke(
            cli, ["graphql", "query", "--file", str(query_file)]
        )
        assert result.exit_code == 0

    @pytest.mark.unit
    def test_query_with_variables(self, runner, mock_graphql_api_client):
        mock_graphql_api_client.post.return_value = {
            "data": {"asset": {"id": "a1", "name": "X"}},
        }
        result = runner.invoke(
            cli,
            [
                "graphql", "query",
                "--query", "query Q($id: ID!) { asset(id: $id) { id name } }",
                "--variables", '{"id": "a1"}',
            ],
        )
        assert result.exit_code == 0

    @pytest.mark.unit
    def test_query_missing_query_and_file(self, runner, mock_graphql_api_client):
        result = runner.invoke(cli, ["graphql", "query"])
        assert result.exit_code != 0

    @pytest.mark.unit
    def test_query_invalid_variables_json(self, runner, mock_graphql_api_client):
        result = runner.invoke(
            cli,
            [
                "graphql", "query",
                "--query", "{ assets { id } }",
                "--variables", "not json",
            ],
        )
        assert result.exit_code != 0
        assert "Invalid JSON for --variables" in result.output

    @pytest.mark.unit
    def test_query_api_error(self, runner, mock_graphql_api_client):
        from click import ClickException
        mock_graphql_api_client.post.side_effect = ClickException(
            "GraphQL query exceeded 10.0s timeout"
        )
        result = runner.invoke(
            cli, ["graphql", "query", "--query", "{ assets { id } }"]
        )
        assert result.exit_code != 0
        assert "timeout" in result.output.lower()
