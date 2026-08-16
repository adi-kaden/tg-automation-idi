import ast
from pathlib import Path

from app.api import auth


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent


def test_auth_router_has_no_unauthenticated_setup_endpoint() -> None:
    paths = {getattr(route, "path", None) for route in auth.router.routes}
    assert "/setup" not in paths


def test_password_hashing_never_uses_source_controlled_literal() -> None:
    python_paths = [*BACKEND_ROOT.joinpath("app").rglob("*.py")]
    python_paths.extend(BACKEND_ROOT.glob("seed*.py"))
    violations: list[str] = []
    for path in python_paths:
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            if isinstance(node.func, ast.Name) and node.func.id == "hash_password":
                if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    violations.append(str(path.relative_to(BACKEND_ROOT)))
    assert violations == []


def test_public_login_source_contains_no_demo_credentials() -> None:
    source = REPOSITORY_ROOT.joinpath(
        "frontend", "src", "app", "(auth)", "login", "page.tsx"
    ).read_text()
    assert "Demo credentials:" not in source
    assert "Admin123!" not in source
