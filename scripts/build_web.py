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
