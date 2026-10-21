"""
W6.3 (oss-release-remediation) — CLI fixes pins.

Covers the five W6.3 fixes, TDD RED-first, no mocks of the units under
test:

1. **login exit code** — a failed login must exit non-zero with the
   failure on stderr; a successful login exits 0, stores the tokens, and
   prints exactly ONE success message. The login HTTP traffic is REAL:
   a local threading HTTP server answers /auth/login/ and the global
   config points at it.
2. **dedupe login** — `datahub login` and `datahub auth login` are ONE
   implementation (pinned statically via the AST: both command bodies
   are a single call to the same helper) and behave identically.
3. **config 0600** — a saved config file is mode 0600, and a pre-fix
   0644 file is healed on load. Real filesystem.
4. **single version** — `--version` prints the package `__version__`
   (no hardcoded literal in main.py, pinned via the AST).
5. **JSON output helper adoption** — every `--format json` render in
   `datahub_cli` routes through `print_json_output` (pinned via the
   AST: no `click.echo(json.dumps(...))` remains outside output.py),
   and the helper itself is sort_keys/default=str/NaN-safe (pinned by
   parsing its real stdout as JSON).
"""

import ast
import json
import os
import stat
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from click.testing import CliRunner

CLI_SRC = Path(__file__).resolve().parents[1] / "datahub_cli"


# ---------------------------------------------------------------------------
# REAL login server — the CLI's requests.post talks to this over the wire.
# ---------------------------------------------------------------------------


class _LoginHandler(BaseHTTPRequestHandler):
    status_code: int = 200
    response_body: dict = {  # noqa: RUF012 — class-level responder state, mutated per test
        "access_token": "access-tok",
        "refresh_token": "refresh-tok",
    }

    def do_POST(self):
        body = json.dumps(self.response_body).encode()
        self.send_response(self.status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


@pytest.fixture
def login_server():
    server = HTTPServer(("127.0.0.1", 0), _LoginHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/api/v1", server
    server.shutdown()
    server.server_close()


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def pointed_config(temp_config_dir, login_server):
    """Point the GLOBAL config at the real login server (temp config dir)."""
    from datahub_cli.config import config as global_config

    base_url, server = login_server
    # Reset the class-level responder state so test order can never leak.
    server.RequestHandlerClass.status_code = 200
    server.RequestHandlerClass.response_body = {
        "access_token": "access-tok",
        "refresh_token": "refresh-tok",
    }
    global_config.set_api_base_url(base_url)
    yield global_config
    global_config.clear_auth()


def _invoke_login(runner, args: list[str]):
    """Invoke a login command without the interactive prompts."""
    from datahub_cli.main import cli

    return runner.invoke(
        cli,
        [*args, "--email", "test@example.com", "--password", "secret"],
    )


def _command_stderr(result) -> str:
    return f"{result.output}{getattr(result, 'stderr', '') or ''}"


# ---------------------------------------------------------------------------
# 1 + 2. login exit code, output, dedupe
# ---------------------------------------------------------------------------


class TestLoginExitCode:
    def test_failed_login_exits_nonzero(self, runner, pointed_config, login_server):
        _base, server = login_server
        server.RequestHandlerClass.status_code = 401
        server.RequestHandlerClass.response_body = {
            "error": {"message": "Invalid credentials"}
        }
        result = _invoke_login(runner, ["login"])
        assert result.exit_code == 1
        assert "Login failed" in _command_stderr(result)
        assert "Login successful" not in result.output

    def test_successful_login_exits_zero_and_stores_tokens(
        self, runner, pointed_config, login_server
    ):
        result = _invoke_login(runner, ["login"])
        assert result.exit_code == 0, _command_stderr(result)
        # Exactly ONE success message (pre-fix: auth_manager AND the
        # auth-group command each printed their own).
        assert result.output.count("Login successful") == 1
        # The tokens really landed in the config file.
        from datahub_cli.config import Config

        assert Config().get_access_token() == "access-tok"
        assert Config().get_refresh_token() == "refresh-tok"

    def test_auth_login_behaves_identically(self, runner, pointed_config, login_server):
        _base, server = login_server
        server.RequestHandlerClass.status_code = 401
        server.RequestHandlerClass.response_body = {"error": {"message": "Invalid"}}
        failed = _invoke_login(runner, ["auth", "login"])
        assert failed.exit_code == 1

        server.RequestHandlerClass.status_code = 200
        server.RequestHandlerClass.response_body = {
            "access_token": "access-tok",
            "refresh_token": "refresh-tok",
        }
        ok = _invoke_login(runner, ["auth", "login"])
        assert ok.exit_code == 0
        assert ok.output.count("Login successful") == 1

    def test_login_commands_share_one_implementation(self):
        """AST pin: both command bodies are a single call to the SAME helper."""
        main_tree = ast.parse((CLI_SRC / "main.py").read_text())
        auth_tree = ast.parse((CLI_SRC / "commands" / "auth.py").read_text())

        def find_login_body(tree):
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name in (
                    "login",
                    "auth_login",
                ):
                    return node
            raise AssertionError("login command not found")

        main_login = find_login_body(main_tree)
        auth_login = find_login_body(auth_tree)

        def sole_call(fn: ast.FunctionDef) -> ast.Call:
            # Statements other than the docstring/comment expressions must
            # be exactly ONE expression-statement: the delegation call.
            real_stmts = [
                s
                for s in fn.body
                if not (
                    isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)
                )
            ]
            assert len(real_stmts) == 1, (
                f"{fn.name} has {len(real_stmts)} statements — not a thin delegate"
            )
            assert isinstance(real_stmts[0], ast.Expr)
            assert isinstance(real_stmts[0].value, ast.Call)
            return real_stmts[0].value

        main_call = sole_call(main_login)
        auth_call = sole_call(auth_login)
        assert isinstance(main_call.func, ast.Name)
        assert isinstance(auth_call.func, ast.Name)
        assert main_call.func.id == auth_call.func.id
        # The shared helper is a plain name (single implementation home).
        assert main_call.func.id == "login_command"


# ---------------------------------------------------------------------------
# 3. config 0600
# ---------------------------------------------------------------------------


class TestConfigFileMode:
    def test_saved_config_is_0600(self, temp_config_dir):
        from datahub_cli.config import Config

        config = Config()
        config.set("api_key", "super-secret")
        _dir, config_file = temp_config_dir
        mode = stat.S_IMODE(os.stat(config_file).st_mode)
        assert mode == 0o600

    def test_preexisting_world_readable_config_is_healed(self, temp_config_dir):
        from datahub_cli.config import Config

        _dir, config_file = temp_config_dir
        config_file.write_text("api_base_url: http://example.com/api/v1\n")
        os.chmod(config_file, 0o644)

        Config()  # the load must heal the mode
        assert stat.S_IMODE(os.stat(config_file).st_mode) == 0o600


# ---------------------------------------------------------------------------
# 4. single version
# ---------------------------------------------------------------------------


class TestSingleVersion:
    def test_version_option_has_no_literal(self):
        tree = ast.parse((CLI_SRC / "main.py").read_text())
        literal = None
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "version_option"
            ):
                for kw in node.keywords:
                    if kw.arg == "version":
                        literal = kw.value
        assert not isinstance(literal, ast.Constant), (
            "version_option must reference the package __version__, not a literal"
        )

    def test_version_prints_package_version(self, runner):
        import datahub_cli
        from datahub_cli.main import cli

        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert datahub_cli.__version__ in result.output


# ---------------------------------------------------------------------------
# 5. JSON output helper
# ---------------------------------------------------------------------------


class TestJsonOutputHelper:
    def test_nan_inf_render_as_null(self, capsys):
        from datahub_cli.output import print_json_output

        print_json_output(
            {
                "z": 1,
                "a": float("nan"),
                "nested": {"b": float("inf"), "neg": float("-inf")},
            }
        )
        out = capsys.readouterr().out
        parsed = json.loads(out)  # valid JSON — pre-fix "NaN" is not
        assert parsed["a"] is None
        assert parsed["nested"]["b"] is None
        assert parsed["nested"]["neg"] is None

    def test_keys_sorted_and_non_serializable_via_str(self, capsys):
        from datahub_cli.output import print_json_output

        class Thing:
            def __str__(self):
                return "thing-str"

        print_json_output({"zzz": 1, "aaa": {"mid": Thing()}})
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert list(parsed.keys()) == ["aaa", "zzz"]  # sort_keys
        assert parsed["aaa"]["mid"] == "thing-str"  # default=str

    def test_all_json_rendering_routes_through_helper(self):
        """AST pin: no click.echo(json.dumps(...)) remains outside output.py."""
        offenders = []
        for path in sorted(CLI_SRC.rglob("*.py")):
            if path.name == "output.py" or "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                # click.echo(...) whose argument is json.dumps(...)
                if (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "echo"
                    and node.args
                    and isinstance(node.args[0], ast.Call)
                    and isinstance(node.args[0].func, ast.Attribute)
                    and node.args[0].func.attr == "dumps"
                ):
                    offenders.append(f"{path}:{node.lineno}")
        assert not offenders, (
            f"{len(offenders)} raw json.dumps renders remain "
            f"(route them through print_json_output): {offenders[:5]}..."
        )
