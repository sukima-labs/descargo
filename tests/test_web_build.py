import importlib.util
import re
import tomllib
from types import ModuleType
from typing import Any

import pytest

from tests.conftest import REPO_ROOT


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_web", REPO_ROOT / "scripts/build_web.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_web = _module()


def _pyodide_lock(*names: str, **depends: list[str]) -> dict[str, Any]:
    return {
        "packages": {
            name: {"depends": depends.get(name.replace("-", "_"), []), "file_name": f"{name}.whl"}
            for name in names
        }
    }


def _requirements() -> list[str]:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text("utf-8"))
    requirements: list[str] = pyproject["project"]["dependencies"]
    return requirements


def _uv_lock() -> dict[str, Any]:
    return tomllib.loads((REPO_ROOT / "uv.lock").read_text("utf-8"))


def test_plan_takes_compiled_packages_from_pyodide_and_the_rest_from_uv_lock() -> None:
    shipped = _pyodide_lock(
        "pydantic",
        "pydantic-core",
        "pyyaml",
        "regex",
        "jinja2",
        "markupsafe",
        "fonttools",
        "pillow",
        pydantic=["pydantic_core"],
        jinja2=["markupsafe"],
    )
    from_pyodide, from_pypi = build_web.plan(_requirements(), _uv_lock(), shipped)
    assert from_pyodide == [
        "fonttools",
        "jinja2",
        "markupsafe",
        "pillow",
        "pydantic",
        "pydantic-core",
        "pyyaml",
        "regex",
    ]
    assert [entry["name"] for entry in from_pypi] == ["defusedxml", "fpdf2", "pypdf"]


def test_plan_leaves_out_the_cli() -> None:
    _, from_pypi = build_web.plan(["typer>=0.15", "pypdf>=5"], _uv_lock(), _pyodide_lock())
    assert [entry["name"] for entry in from_pypi] == ["pypdf"]


def test_plan_refuses_a_package_it_cannot_find() -> None:
    with pytest.raises(SystemExit, match="no-such-package"):
        build_web.plan(["no_such_package"], _uv_lock(), _pyodide_lock())


def test_plan_refuses_a_compiled_package_pyodide_lacks() -> None:
    lock = {"package": [{"name": "native", "wheels": [{"url": "x/native-cp312-linux.whl"}]}]}
    with pytest.raises(SystemExit, match="no pure Python wheel"):
        build_web.plan(["native"], lock, _pyodide_lock())


@pytest.mark.parametrize(
    ("requirement", "name"),
    [("PyYAML>=6.0", "pyyaml"), ("typing_extensions", "typing-extensions"), ("a.b[c]", "a-b")],
)
def test_requirement_name(requirement: str, name: str) -> None:
    assert build_web.requirement_name(requirement) == name


def test_every_string_the_page_uses_exists() -> None:
    strings = build_web.web_strings()
    assert set(strings) == {"en", "es"}
    page = (REPO_ROOT / "web/index.html").read_text("utf-8")
    script = (REPO_ROOT / "web/app.js").read_text("utf-8")
    used = set(re.findall(r'data-i18n="(\w+)"', page)) | set(re.findall(r'\bt\("(\w+)"', script))
    assert used
    for locale, table in strings.items():
        assert used <= set(table), (locale, used - set(table))
