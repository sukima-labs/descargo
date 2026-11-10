"""Build the static in-browser version of Descargo into ``build/web/`` (ADR 007).

Usage: ``uv run python scripts/build_web.py [--out build/web]``

Downloads Pyodide and the wheels the browser needs, checks every file against a pinned
SHA-256, and copies ``web/`` next to them. This script uses the network, at build time
only; the site it builds requests nothing but its own files. Downloads are cached in
``.cache/web/``.

What goes into the site:

* Pyodide's core files, from the release tarball pinned below.
* For each runtime dependency of Descargo (except the CLI-only ones), and their
  dependencies: Pyodide's own build when Pyodide ships the package, otherwise the pure
  Python wheel pinned in ``uv.lock``.
* The Descargo wheel, built from this checkout with ``uv build``.
* A trimmed ``pyodide-lock.json`` that lists only those packages, with their SHA-256, so
  Pyodide checks each one as it loads it and cannot fetch anything else.
* ``strings.json``, the page's texts, and ``guides.json``, the procedure guides of
  ``docs/`` as blocks the page draws with DOM calls (it never inserts HTML).
"""

import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
import tomllib
import urllib.request
from pathlib import Path
from typing import Any, Final

from markdown_it import MarkdownIt
from markdown_it.token import Token

ROOT: Final = Path(__file__).resolve().parent.parent
CACHE: Final = ROOT / ".cache" / "web"

PYODIDE_VERSION: Final = "314.0.7"
PYODIDE_CORE_URL: Final = (
    "https://github.com/pyodide/pyodide/releases/download/"
    f"{PYODIDE_VERSION}/pyodide-core-{PYODIDE_VERSION}.tar.bz2"
)
PYODIDE_CORE_SHA256: Final = "2abdcc2e35208af406e07724cffa85bc582ced97e9028383ecf5462541393f95"
PYODIDE_PACKAGES_URL: Final = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/"
#: Files of the core tarball the site needs (a module worker loads ``pyodide.mjs``).
PYODIDE_CORE_FILES: Final = (
    "pyodide.mjs",
    "pyodide.asm.mjs",
    "pyodide.asm.wasm",
    "python_stdlib.zip",
    "pyodide-lock.json",
)
#: Runtime dependencies the browser does not need: the CLI layer (ADR 003).
CLI_ONLY: Final = frozenset({"typer"})
#: Static files copied from ``web/``.
WEB_SUFFIXES: Final = frozenset({".html", ".js", ".css", ".svg", ".jpg"})


def normalize(name: str) -> str:
    """PEP 503 name normalisation."""
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_name(requirement: str) -> str:
    match = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", requirement)
    if match is None:
        raise ValueError(f"cannot read requirement {requirement!r}")
    return normalize(match.group(0))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str, expected: str) -> bytes:
    """Download ``url`` (or take it from the cache) and check its SHA-256."""
    cached = CACHE / expected
    if cached.is_file():
        data = cached.read_bytes()
    else:
        print(f"  downloading {url}")
        with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310 - https only
            data = response.read()
    if sha256(data) != expected:
        raise SystemExit(f"SHA-256 mismatch for {url}: expected {expected}, got {sha256(data)}")
    CACHE.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(data)
    return data


def plan(
    requirements: list[str], uv_lock: dict[str, Any], pyodide_lock: dict[str, Any]
) -> tuple[list[str], list[dict[str, Any]]]:
    """Decide where each package comes from.

    Returns the Pyodide package names (normalised, with their dependencies) and the
    ``uv.lock`` entries of the pure Python wheels to take from PyPI.
    """
    shipped = {normalize(name): entry for name, entry in pyodide_lock["packages"].items()}
    locked = {normalize(p["name"]): p for p in uv_lock["package"]}
    from_pyodide: set[str] = set()
    from_pypi: dict[str, dict[str, Any]] = {}
    pending = [requirement_name(r) for r in requirements]
    pending = [name for name in pending if name not in CLI_ONLY]
    while pending:
        name = pending.pop()
        if name in from_pyodide or name in from_pypi:
            continue
        if name in shipped:
            from_pyodide.add(name)
            pending.extend(normalize(d) for d in shipped[name]["depends"])
        elif name in locked:
            entry = locked[name]
            wheels = [w for w in entry.get("wheels", []) if w["url"].endswith("-none-any.whl")]
            if not wheels:
                raise SystemExit(f"{name}: not in Pyodide and no pure Python wheel in uv.lock")
            from_pypi[name] = entry
            pending.extend(normalize(d["name"]) for d in entry.get("dependencies", []))
        else:
            raise SystemExit(f"{name}: neither in Pyodide {PYODIDE_VERSION} nor in uv.lock")
    return sorted(from_pyodide), [from_pypi[name] for name in sorted(from_pypi)]


def lock_entry(
    name: str, version: str, file_name: str, digest: str, depends: list[str]
) -> dict[str, Any]:
    """A ``pyodide-lock.json`` entry for a wheel that Pyodide does not ship."""
    return {
        "name": name,
        "version": version,
        "file_name": file_name,
        "install_dir": "site",
        "sha256": digest,
        "package_type": "package",
        "imports": [],
        "depends": depends,
        "unvendored_tests": False,
        "tool": {},
    }


def web_strings() -> dict[str, dict[str, str]]:
    """The ``[web]`` table of every UI catalog, for the page to read before Python loads."""
    strings = {}
    for catalog in sorted((ROOT / "src/descargo/i18n/locales").glob("*.toml")):
        strings[catalog.stem] = tomllib.loads(catalog.read_text("utf-8"))["web"]
    return strings


#: The procedure guides the page shows, by language: ``(country, file, section)``. A guide
#: that covers two countries is split at its country section (``## España``); its other
#: sections, which are not about one country, go with each.
GUIDES: Final = {
    "es": (
        ("es", "docs/procedimientos.md", "España"),
        ("co", "docs/procedimientos.md", "Colombia"),
        ("mx", "docs/procedimientos-mx.md", None),
        ("ar", "docs/procedimientos-ar.md", None),
        ("cl", "docs/procedimientos-cl.md", None),
        ("pe", "docs/procedimientos-pe.md", None),
    ),
    "en": (
        ("es", "docs/en/procedures.md", "Spain"),
        ("co", "docs/en/procedures.md", "Colombia"),
        ("mx", "docs/en/procedures-mx.md", None),
        ("ar", "docs/en/procedures-ar.md", None),
        ("cl", "docs/en/procedures-cl.md", None),
        ("pe", "docs/en/procedures-pe.md", None),
    ),
}
#: Where a link to another file of the repository points on the site.
REPOSITORY: Final = "https://github.com/sukima-labs/descargo/blob/main/"
_GUIDE_FILE = re.compile(r"(?:^|/)(?:procedimientos|procedures)(?:-([a-z]{2}))?\.md$")

Inline = dict[str, Any]
Block = dict[str, Any]


def slug(text: str) -> str:
    """The anchor GitHub gives a heading: lower case, punctuation dropped, spaces as
    hyphens."""
    return re.sub(r"[^\w\- ]", "", text.lower()).replace(" ", "-")


def _href(href: str, document: str) -> Inline:
    """What a link in ``document`` becomes on the page: another guide, a heading of this
    one, a file of the repository, or an outside address."""
    if href.startswith(("http://", "https://")):
        return {"href": href}
    if href.startswith("#"):
        return {"anchor": href[1:]}
    path, _, anchor = href.partition("#")
    guide = _GUIDE_FILE.search(path)
    if guide:
        return {"guide": guide.group(1) or "es", **({"anchor": anchor} if anchor else {})}
    resolved = (ROOT / document).parent.joinpath(path).resolve().relative_to(ROOT)
    return {"href": REPOSITORY + resolved.as_posix() + (f"#{anchor}" if anchor else "")}


def _inlines(token: Token, document: str) -> list[Inline]:
    """The text of an ``inline`` token, as runs with their style and link."""
    runs: list[Inline] = []
    style: dict[str, Any] = {}
    for child in token.children or []:
        kind = child.type
        if kind in {"text", "code_inline", "softbreak", "hardbreak"}:
            text = " " if kind.endswith("break") else child.content
            run = {"t": text, **style, **({"code": True} if kind == "code_inline" else {})}
            if runs and {k: v for k, v in runs[-1].items() if k != "t"} == {
                k: v for k, v in run.items() if k != "t"
            }:
                runs[-1]["t"] += text
            else:
                runs.append(run)
        elif kind in {"strong_open", "em_open"}:
            style["bold" if kind == "strong_open" else "italic"] = True
        elif kind in {"strong_close", "em_close"}:
            style.pop("bold" if kind == "strong_close" else "italic", None)
        elif kind == "link_open":
            style.update(_href(str(child.attrs["href"]), document))
        elif kind == "link_close":
            for key in ("href", "guide", "anchor"):
                style.pop(key, None)
        else:
            raise ValueError(f"{document}: unsupported markdown {kind!r}")
    return runs


_CONTAINERS: Final = {
    "bullet_list_open": ("ul", "items"),
    "ordered_list_open": ("ol", "items"),
    "blockquote_open": ("quote", "blocks"),
}
_CLOSERS: Final = frozenset(
    {"bullet_list_close", "ordered_list_close", "blockquote_close", "list_item_close"}
)


def _blocks(tokens: list[Token], document: str) -> list[Block]:
    """``tokens`` as nested blocks: headings, paragraphs, lists, tables and quotes. A list
    item is a list of blocks; a table has a ``head`` row and ``rows``, each a list of
    cells, each a list of runs."""
    root: list[Block] = []
    stack: list[list[Any]] = [root]
    pending: Block | None = None  # the heading or paragraph whose text comes next
    row: list[list[Inline]] | None = None
    for token in tokens:
        kind = token.type
        if kind in {"heading_open", "paragraph_open"}:
            pending = {"type": token.tag if kind == "heading_open" else "p"}
            stack[-1].append(pending)
        elif kind == "inline" and row is not None:
            row.append(_inlines(token, document))
        elif kind == "inline":
            if pending is None:
                raise ValueError(f"{document}: text outside a block")
            pending["runs"] = _inlines(token, document)
            if pending["type"] != "p":
                pending["id"] = slug("".join(run["t"] for run in pending["runs"]))
            pending = None
        elif kind in _CONTAINERS:
            tag, key = _CONTAINERS[kind]
            block: Block = {"type": tag, key: []}
            stack[-1].append(block)
            stack.append(block[key])
        elif kind == "list_item_open":
            item: list[Block] = []
            stack[-1].append(item)
            stack.append(item)
        elif kind in _CLOSERS:
            stack.pop()
        elif kind in {"table_open", "tr_open", "tr_close"}:
            row = _table(kind, stack[-1], row)
    return root


def _table(
    kind: str, blocks: list[Block], row: list[list[Inline]] | None
) -> list[list[Inline]] | None:
    """Follow a table token: start the table, start a row, or file the row as the head
    (the first) or a body row. Returns the row being read, if any."""
    if kind == "table_open":
        blocks.append({"type": "table", "head": [], "rows": []})
        return None
    if kind == "tr_open":
        return []
    table = blocks[-1]
    if table["head"]:
        table["rows"].append(row)
    else:
        table["head"] = row
    return None


def _section(blocks: list[Block], country: str | None, others: set[str]) -> list[Block]:
    """The blocks for one country of a guide: everything but the other countries' ``##``
    sections."""
    if country is None:
        return blocks
    kept: list[Block] = []
    skipping = False
    for block in blocks:
        if block["type"] == "h2":
            title = "".join(run["t"] for run in block["runs"])
            skipping = title in others and title != country
        if not skipping:
            kept.append(block)
    return kept


def guide_blocks(document: str, country: str | None, others: set[str]) -> list[Block]:
    """A guide of ``docs/`` as blocks, without the line that links its other language (a
    paragraph in italics only)."""
    text = (ROOT / document).read_text("utf-8")
    tokens = MarkdownIt("commonmark", {"html": False}).enable("table").parse(text)
    blocks = [
        block
        for block in _blocks(tokens, document)
        if not (
            block["type"] == "p"
            and len(block["runs"]) >= 2
            and all(run.get("italic") for run in block["runs"])
        )
    ]
    return _section(blocks, country, others)


def web_guides() -> dict[str, dict[str, Any]]:
    """``language → country → {title, source, blocks}`` for every guide in :data:`GUIDES`."""
    guides: dict[str, dict[str, Any]] = {}
    for language, entries in GUIDES.items():
        sections = {section for _, _, section in entries if section}
        guides[language] = {}
        for country, document, section in entries:
            blocks = guide_blocks(document, section, sections)
            if not blocks or blocks[0]["type"] != "h1":
                raise ValueError(f"{document}: a guide starts with its title")
            title = "".join(run["t"] for run in blocks.pop(0)["runs"])
            guides[language][country] = {
                "title": title,
                "source": REPOSITORY + document,
                "blocks": blocks,
            }
    return guides


def build_wheel() -> Path:
    out = Path(tempfile.mkdtemp(prefix="descargo-wheel-"))
    subprocess.run(  # noqa: S603 - fixed arguments
        ["uv", "build", "--wheel", "--out-dir", str(out), str(ROOT)],  # noqa: S607
        check=True,
        capture_output=True,
    )
    (wheel,) = out.glob("descargo-*.whl")
    return wheel


def commit() -> str:
    result = subprocess.run(  # noqa: S603 - fixed arguments
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or "unknown"


def build(out: Path) -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    uv_lock = tomllib.loads((ROOT / "uv.lock").read_text("utf-8"))
    version = pyproject["project"]["version"]

    print(f"Pyodide {PYODIDE_VERSION}")
    core = fetch(PYODIDE_CORE_URL, PYODIDE_CORE_SHA256)
    if out.exists():
        shutil.rmtree(out)
    target = out / "pyodide"
    target.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(core), mode="r:bz2") as tar:
        for name in PYODIDE_CORE_FILES:
            member = tar.extractfile(f"pyodide/{name}")
            if member is None:
                raise SystemExit(f"{name} missing from the Pyodide tarball")
            (target / name).write_bytes(member.read())
    full_lock = json.loads((target / "pyodide-lock.json").read_text("utf-8"))

    from_pyodide, from_pypi = plan(pyproject["project"]["dependencies"], uv_lock, full_lock)
    shipped = {normalize(name): (name, entry) for name, entry in full_lock["packages"].items()}
    packages: dict[str, Any] = {}
    for name in from_pyodide:
        key, entry = shipped[name]
        print(f"  {entry['file_name']} (Pyodide)")
        data = fetch(PYODIDE_PACKAGES_URL + entry["file_name"], entry["sha256"])
        (target / entry["file_name"]).write_bytes(data)
        packages[key] = entry
    for entry in from_pypi:
        (wheel,) = (w for w in entry["wheels"] if w["url"].endswith("-none-any.whl"))
        file_name = wheel["url"].rsplit("/", 1)[1]
        print(f"  {file_name} (PyPI, uv.lock)")
        digest = wheel["hash"].removeprefix("sha256:")
        (target / file_name).write_bytes(fetch(wheel["url"], digest))
        depends = [normalize(d["name"]) for d in entry.get("dependencies", [])]
        packages[normalize(entry["name"])] = lock_entry(
            normalize(entry["name"]), entry["version"], file_name, digest, depends
        )

    print("  descargo (this checkout)")
    wheel = build_wheel()
    shutil.copy2(wheel, target / wheel.name)
    shutil.rmtree(wheel.parent)
    top_level = sorted(
        requirement_name(r)
        for r in pyproject["project"]["dependencies"]
        if requirement_name(r) not in CLI_ONLY
    )
    packages["descargo"] = lock_entry(
        "descargo", version, wheel.name, sha256((target / wheel.name).read_bytes()), top_level
    )
    packages["descargo"]["imports"] = ["descargo"]
    lock = {"info": full_lock["info"], "packages": dict(sorted(packages.items()))}
    (target / "pyodide-lock.json").write_text(json.dumps(lock, indent=1) + "\n", "utf-8")

    for source in sorted((ROOT / "web").iterdir()):
        if source.suffix in WEB_SUFFIXES:
            shutil.copy2(source, out / source.name)
    (out / "strings.json").write_text(
        json.dumps(web_strings(), ensure_ascii=False, indent=1) + "\n", "utf-8"
    )
    (out / "guides.json").write_text(
        json.dumps(web_guides(), ensure_ascii=False, separators=(",", ":")) + "\n", "utf-8"
    )
    (out / "build.json").write_text(
        json.dumps({"descargo": version, "commit": commit(), "pyodide": PYODIDE_VERSION}, indent=1)
        + "\n",
        "utf-8",
    )
    files = sorted(p for p in out.rglob("*") if p.is_file())
    (out / "SHA256SUMS").write_text(
        "".join(f"{sha256(p.read_bytes())}  {p.relative_to(out).as_posix()}\n" for p in files),
        "utf-8",
    )
    size = sum(p.stat().st_size for p in files)
    print(f"Built {out} ({len(files)} files, {size / 1_000_000:.1f} MB)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "web")
    args = parser.parse_args()
    build(args.out)


if __name__ == "__main__":
    main()
