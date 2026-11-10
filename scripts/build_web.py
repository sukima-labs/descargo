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
import html
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


#: Where the site lives, and the path of each country's static guide page in each language.
SITE: Final = "https://sukima-labs.github.io/descargo/"
#: ``country → (name, path part)`` by language. The static pages exist so that search
#: engines and people can open a guide by its own address; the page (``index.html``) draws
#: the same guides with JavaScript.
COUNTRIES: Final = {
    "es": {
        "es": ("España", "espana"),
        "co": ("Colombia", "colombia"),
        "mx": ("México", "mexico"),
        "ar": ("Argentina", "argentina"),
        "cl": ("Chile", "chile"),
        "pe": ("Perú", "peru"),
    },
    "en": {
        "es": ("Spain", "spain"),
        "co": ("Colombia", "colombia"),
        "mx": ("Mexico", "mexico"),
        "ar": ("Argentina", "argentina"),
        "cl": ("Chile", "chile"),
        "pe": ("Peru", "peru"),
    },
}
_FOLDERS: Final = {"es": "guias", "en": "en/guides"}
#: The static pages ask for nothing but their stylesheet and the share picture.
_STATIC_CSP: Final = (
    "default-src 'none'; style-src 'self'; img-src 'self'; form-action 'none'; base-uri 'none'"
)
_PAGE_TEXT: Final = {
    "es": {
        "lang": "es",
        "locale": "es_ES",
        "hub_title": "Guías de procedimientos por país",
        "hub_description": (
            "Qué hacer si un detector de plagio o de IA marca tu trabajo: guías de seis países "
            "con sus fuentes. Gratis y sin subir archivos."
        ),
        "hub_lead": (
            "Una guía por país con los artículos, los plazos y las fuentes que pueden aplicar si "
            "un detector de plagio o de IA marca tu trabajo. Cada cita indica dónde y cuándo se "
            "comprobó."
        ),
        "description": (
            "Si un detector marca tu trabajo en {country}: artículos, plazos y fuentes. "
            "Guía gratuita de Descargo; no es asesoramiento legal."
        ),
        "notice": (
            "Descargo no es asesoramiento legal. Es una versión de prueba: algunas partes de "
            "esta guía están marcadas «por verificar». Comprueba las fuentes y, si te juegas "
            "mucho, habla con la defensoría universitaria, la representación estudiantil o un "
            "abogado."
        ),
        "tagline": "Prueba de autoría.",
        "cta_title": "Prueba la herramienta",
        "cta": (
            "Descargo revisa tu archivo y el informe del detector en tu navegador. No sube "
            "nada, no pide cuenta y no reescribe tu texto."
        ),
        "cta_link": "Abrir Descargo",
        "source": "Texto fuente de esta guía en GitHub",
        "others": "Otros países",
        "all": "Todas las guías",
        "home": "Descargo",
        "other_language": "English",
    },
    "en": {
        "lang": "en",
        "locale": "en_GB",
        "hub_title": "Procedure guides by country",
        "hub_description": (
            "What to do if a plagiarism or AI detector flags your work: guides for six countries "
            "with sources. Free; no files uploaded."
        ),
        "hub_lead": (
            "One guide per country with the articles, deadlines and sources that may apply if a "
            "plagiarism or AI detector flags your work. Each quote says where and when it was "
            "checked."
        ),
        "description": (
            "If a detector flags your work in {country}: articles, deadlines and sources. "
            "A free Descargo guide; not legal advice."
        ),
        "notice": (
            "Descargo is not legal advice. This is a test version: some parts of this guide are "
            "marked \u201cto verify\u201d. Check the sources and, if the stakes are high, talk to "
            "your student ombudsman, student union or a lawyer."
        ),
        "tagline": "Proof of authorship.",
        "cta_title": "Try the tool",
        "cta": (
            "Descargo checks your file and the detector's report in your browser. It uploads "
            "nothing, asks for no account and never rewrites your text."
        ),
        "cta_link": "Open Descargo",
        "source": "Source text of this guide on GitHub",
        "others": "Other countries",
        "all": "All guides",
        "home": "Descargo",
        "other_language": "Español",
    },
}


def guide_path(language: str, country: str | None = None) -> str:
    """The path, from the site root, of a static guide page (or of the list of guides)."""
    if country is None:
        return f"{_FOLDERS[language]}/"
    return f"{_FOLDERS[language]}/{COUNTRIES[language][country][1]}/"


def _text_html(run: Inline, language: str) -> str:
    """One run of text as HTML: escaped, styled and, if it is a link, linked."""
    out = html.escape(run["t"])
    if run.get("code"):
        out = f"<code>{out}</code>"
    if run.get("bold"):
        out = f"<strong>{out}</strong>"
    if run.get("italic"):
        out = f"<em>{out}</em>"
    if "href" in run:
        out = f'<a href="{html.escape(run["href"])}">{out}</a>'
    elif "guide" in run:
        target = "../" + COUNTRIES[language][run["guide"]][1] + "/"
        anchor = f"#{html.escape(run['anchor'])}" if "anchor" in run else ""
        out = f'<a href="{target}{anchor}">{out}</a>'
    elif "anchor" in run:
        out = f'<a href="#{html.escape(run["anchor"])}">{out}</a>'
    return out


def _block_html(block: Block, language: str) -> str:
    """One block of a guide as HTML."""
    kind = block["type"]
    if kind in {"p", "h2", "h3", "h4", "h5", "h6"}:
        inner = "".join(_text_html(run, language) for run in block["runs"])
        ident = f' id="{html.escape(block["id"])}"' if "id" in block else ""
        return f"<{kind}{ident}>{inner}</{kind}>"
    if kind in {"ul", "ol"}:
        items = "".join(
            "<li>" + "".join(_block_html(b, language) for b in item) + "</li>"
            for item in block["items"]
        )
        return f"<{kind}>{items}</{kind}>"
    if kind == "quote":
        return (
            "<blockquote>"
            + "".join(_block_html(b, language) for b in block["blocks"])
            + "</blockquote>"
        )
    if kind == "table":

        def row(cells: list[list[Inline]], tag: str) -> str:
            inner = "".join(
                f"<{tag}>" + "".join(_text_html(run, language) for run in cell) + f"</{tag}>"
                for cell in cells
            )
            return f"<tr>{inner}</tr>"

        head = f"<thead>{row(block['head'], 'th')}</thead>"
        body = "".join(row(cells, "td") for cells in block["rows"])
        return f'<div class="table-scroll"><table>{head}<tbody>{body}</tbody></table></div>'
    raise ValueError(f"unsupported block {kind!r}")


def _page(language: str, path: str, title: str, description: str, body: str) -> str:
    """A static page: ``body`` inside the shared header and footer, with the metadata that
    search engines and link previews read."""
    text = _PAGE_TEXT[language]
    other = "en" if language == "es" else "es"
    depth = path.count("/")
    root = "../" * depth
    # The same page in the other language, when there is one (a guide, or the list).
    parts = path.rstrip("/").split("/")
    country = next((c for c, (_, part) in COUNTRIES[language].items() if part == parts[-1]), None)
    twin = root + guide_path(other, country)
    twin_url = SITE + guide_path(other, country)
    mine = SITE + path
    alternates = "".join(
        f'<link rel="alternate" hreflang="{lang}" href="{href}">'
        for lang, href in sorted({language: mine, other: twin_url}.items())
    )
    hub = "../" if country else ""
    switch = (
        f'<a class="brand" href="{html.escape(twin)}" lang="{other}">{text["other_language"]}</a>'
    )
    return f"""<!doctype html>
<html lang="{language}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="{_STATIC_CSP}">
  <meta name="referrer" content="no-referrer">
  <title>{html.escape(title)} · Descargo</title>
  <meta name="description" content="{html.escape(description)}">
  <link rel="canonical" href="{mine}">
  {alternates}
  <meta property="og:type" content="article">
  <meta property="og:site_name" content="sukima-labs">
  <meta property="og:locale" content="{text["locale"]}">
  <meta property="og:title" content="{html.escape(title)} · Descargo">
  <meta property="og:description" content="{html.escape(description)}">
  <meta property="og:url" content="{mine}">
  <meta property="og:image" content="{SITE}og.jpg">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" href="{root}favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="{root}style.css">
</head>
<body>
  <header class="top">
    <div>
      <a class="brand" href="{root}">{text["home"]}</a>
      <p class="tagline">{text["tagline"]}</p>
    </div>
    <div class="languages">{switch}</div>
  </header>
  <main>
    <section class="notice"><p>{html.escape(text["notice"])}</p></section>
{body}
  </main>
  <footer>
    <p><a href="{root}">{text["home"]}</a> · <a href="{hub}">{text["all"]}</a></p>
  </footer>
</body>
</html>
"""


def static_guides() -> dict[str, str]:
    """``path → HTML`` of the static pages: one per guide and language, and a list of the
    guides in each language. Everything comes from :func:`web_guides`, so the pages and the
    tab can never disagree."""
    pages: dict[str, str] = {}
    for language, countries in web_guides().items():
        text = _PAGE_TEXT[language]
        links = []
        for country, guide in countries.items():
            name = COUNTRIES[language][country][0]
            # España and Colombia share one document, so they share its title: name the one.
            title = re.sub(r"(España y Colombia|Spain and Colombia)", name, guide["title"])
            body = "".join(_block_html(block, language) for block in guide["blocks"])
            to_app = "../../../" if language == "en" else "../../"
            others = "".join(
                f'<li><a href="../{part}/">{html.escape(other)}</a></li>'
                for code, (other, part) in COUNTRIES[language].items()
                if code != country
            )
            article = f"""    <article class="document guide">
      <h1>{html.escape(title)}</h1>
{body}
      <p class="guide-source"><a href="{html.escape(guide["source"])}">{text["source"]}</a></p>
    </article>
    <section class="cta">
      <h2>{text["cta_title"]}</h2>
      <p>{text["cta"]}</p>
      <p><a class="button" href="{to_app}">{text["cta_link"]}</a></p>
    </section>
    <nav class="others" aria-label="{text["others"]}">
      <h2>{text["others"]}</h2>
      <ul>{others}</ul>
    </nav>"""
            pages[guide_path(language, country) + "index.html"] = _page(
                language,
                guide_path(language, country),
                title,
                text["description"].format(country=name),
                article,
            )
            links.append(
                f'<li><a href="{COUNTRIES[language][country][1]}/">{html.escape(title)}</a></li>'
            )
        hub = f"""    <article class="document guide">
      <h1>{text["hub_title"]}</h1>
      <p>{text["hub_lead"]}</p>
      <ul>{"".join(links)}</ul>
    </article>"""
        pages[guide_path(language) + "index.html"] = _page(
            language, guide_path(language), text["hub_title"], text["hub_description"], hub
        )
    return pages


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
    for path, page in static_guides().items():
        (out / path).parent.mkdir(parents=True, exist_ok=True)
        (out / path).write_text(page, "utf-8")
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
