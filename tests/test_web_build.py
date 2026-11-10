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


def test_page_names_its_canonical_url() -> None:
    # One URL serves both languages (chosen in the browser), so one canonical covers them,
    # and it matches the og:url that link previews use.
    page = (REPO_ROOT / "web/index.html").read_text("utf-8")
    url = "https://sukima-labs.github.io/descargo/"
    assert re.findall(r'<link rel="canonical" href="([^"]+)">', page) == [url]
    assert f'<meta property="og:url" content="{url}">' in page


def _walk(blocks: list[Any]) -> list[dict[str, Any]]:
    """Every block in ``blocks``, nested ones included."""
    found: list[dict[str, Any]] = []
    for block in blocks:
        if isinstance(block, list):
            found += _walk(block)
            continue
        found.append(block)
        found += _walk(block.get("items", []) + block.get("blocks", []))
    return found


def _runs(block: dict[str, Any]) -> list[dict[str, Any]]:
    cells = [block["head"], *block["rows"]] if block["type"] == "table" else []
    runs: list[dict[str, Any]] = block.get("runs", [])
    return runs + [run for row in cells for cell in row for run in cell]


def test_every_guide_converts_and_its_links_resolve() -> None:
    guides = build_web.web_guides()
    assert set(guides) == {"es", "en"}
    for language, countries in guides.items():
        assert list(countries) == ["es", "co", "mx", "ar", "cl", "pe"]
        ids = {
            country: {b["id"] for b in _walk(guide["blocks"]) if "id" in b}
            for country, guide in countries.items()
        }
        for country, guide in countries.items():
            assert guide["title"]
            assert guide["source"].startswith(build_web.REPOSITORY)
            blocks = _walk(guide["blocks"])
            assert blocks
            assert not any(b["type"] == "h1" for b in blocks)
            for run in (run for block in blocks for run in _runs(block)):
                if "href" in run:
                    assert run["href"].startswith("https://"), (language, country, run)
                if "guide" in run:
                    assert run["guide"] in countries, (language, country, run)
                if "anchor" in run:
                    target = run.get("guide", country)
                    assert run["anchor"] in ids[target], (language, country, run)


def test_a_two_country_guide_is_split_by_country() -> None:
    spain = build_web.web_guides()["es"]["es"]["blocks"]
    colombia = build_web.web_guides()["es"]["co"]["blocks"]
    sections = [
        ["".join(run["t"] for run in b["runs"]) for b in blocks if b["type"] == "h2"]
        for blocks in (spain, colombia)
    ]
    assert sections == [
        ["Idea común a los dos países", "España", "Cómo se ha comprobado"],
        ["Idea común a los dos países", "Colombia", "Cómo se ha comprobado"],
    ]
    # The line that links the guide's other language is dropped: the page has a switch.
    assert not any("English" in run["t"] for b in spain if b["type"] == "p" for run in b["runs"])


def test_guide_links() -> None:
    document = "docs/procedimientos-mx.md"
    assert build_web._href("https://example.org/a", document) == {"href": "https://example.org/a"}
    assert build_web._href("#plazos", document) == {"anchor": "plazos"}
    assert build_web._href("procedimientos-ar.md", document) == {"guide": "ar"}
    assert build_web._href("procedimientos.md#espana", document) == {
        "guide": "es",
        "anchor": "espana",
    }
    assert build_web._href("../jurisdictions/mx/pack.yaml", document) == {
        "href": build_web.REPOSITORY + "jurisdictions/mx/pack.yaml"
    }
    assert build_web.slug("Qué manda (comprobado el 08-11-2026)") == (
        "qué-manda-comprobado-el-08-11-2026"
    )
