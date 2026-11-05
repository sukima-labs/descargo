import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from descargo.core.data import data_dir
from descargo.core.jurisdictions import (
    PACK_SCHEMA_VERSION,
    PackError,
    load_pack,
    pack_ids,
    resolve_access_request,
)
from descargo.core.jurisdictions.models import localized
from tests.conftest import REPO_ROOT

ROOT = data_dir("jurisdictions")
SCHEMA = json.loads(
    (REPO_ROOT / "schemas" / "jurisdiction" / f"{PACK_SCHEMA_VERSION}.json").read_text()
)
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)


def _as_json(path: Path) -> object:
    return json.loads(json.dumps(yaml.safe_load(path.read_text()), default=str))


def test_expected_packs_are_bundled() -> None:
    assert set(pack_ids(ROOT)) >= {"eu", "es", "uk", "us", "co"}


@pytest.mark.parametrize("pack_id", pack_ids(ROOT))
def test_bundled_packs_are_valid(pack_id: str) -> None:
    load_pack(ROOT, pack_id)
    VALIDATOR.validate(_as_json(ROOT / pack_id / "pack.yaml"))
    resolved = resolve_access_request(ROOT, pack_id)
    assert resolved.spec.response_deadline is not None
    assert resolved.spec.authority is not None
    assert resolved.spec.legal_bases


@pytest.mark.parametrize("pack_id", pack_ids(ROOT))
def test_every_fact_has_a_source(pack_id: str) -> None:
    spec = resolve_access_request(ROOT, pack_id).spec
    facts = [*spec.legal_bases, *spec.prerequisites, spec.response_deadline, spec.authority]
    for fact in facts:
        assert fact is not None
        assert fact.source_url


def test_spain_extends_the_eu() -> None:
    resolved = resolve_access_request(ROOT, "es")
    assert resolved.chain == ("es", "eu")
    citations = [b.value.citation for b in resolved.spec.legal_bases]
    assert citations[0].startswith("GDPR")  # general first
    assert any("LOPDGDD" in c for c in citations)
    assert resolved.spec.response_deadline is not None
    assert resolved.spec.response_deadline.value.amount == 1  # inherited from the EU
    assert resolved.spec.authority is not None
    assert "AEPD" in localized(resolved.spec.authority.value.name, "es")  # overridden
    assert resolved.template_files["es"].parent.name == "es"
    assert resolved.template_files["en"].parent.name == "eu"  # falls back to the EU template


def test_localized_fallbacks() -> None:
    assert localized("plain", "es") == "plain"
    assert localized({"en": "a", "es": "b"}, "es") == "b"
    assert localized({"en": "a", "es": "b"}, "fr") == "a"
    assert localized({"pt": "c"}, "es") == "c"


def _write_pack(root: Path, pack_id: str, body: str, templates: tuple[str, ...] = ()) -> None:
    folder = root / pack_id
    folder.mkdir(parents=True)
    (folder / "pack.yaml").write_text(body)
    for name in templates:
        (folder / name).write_text("# Title\n")


def test_pack_errors(tmp_path: Path) -> None:
    with pytest.raises(PackError, match="no jurisdiction pack"):
        load_pack(tmp_path, "zz")
    _write_pack(tmp_path, "aa", 'schema_version: "0.1"\nid: bb\nname: A\n')
    with pytest.raises(PackError, match="does not match folder"):
        load_pack(tmp_path, "aa")
    _write_pack(
        tmp_path,
        "cc",
        'schema_version: "0.1"\nid: cc\nname: C\naccess_request:\n'
        "  templates: {en: missing.md.j2}\n",
    )
    with pytest.raises(PackError, match=r"template 'missing\.md\.j2' not found"):
        load_pack(tmp_path, "cc")
    _write_pack(tmp_path, "dd", "id: [broken\n")
    with pytest.raises(PackError):
        load_pack(tmp_path, "dd")


def test_circular_extends_and_missing_templates(tmp_path: Path) -> None:
    _write_pack(tmp_path, "aa", 'schema_version: "0.1"\nid: aa\nname: A\nextends: bb\n')
    _write_pack(tmp_path, "bb", 'schema_version: "0.1"\nid: bb\nname: B\nextends: aa\n')
    with pytest.raises(PackError, match="circular"):
        resolve_access_request(tmp_path, "aa")
    _write_pack(tmp_path, "cc", 'schema_version: "0.1"\nid: cc\nname: C\n')
    with pytest.raises(PackError, match="no access-request template"):
        resolve_access_request(tmp_path, "cc")
