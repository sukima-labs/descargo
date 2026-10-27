import copy
import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from draftwitness.core.report_schema import (
    SCHEMA_VERSION,
    Report,
    ReportKind,
    dump_report,
    load_report,
)
from tests.conftest import FIXTURES, REPO_ROOT

REPORT_FIXTURES = sorted((FIXTURES / "reports").glob("*.json"))
SCHEMA = json.loads((REPO_ROOT / "schemas" / "report" / f"{SCHEMA_VERSION}.json").read_text())
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)


def _base() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / "reports" / "similarity_full.json").read_text())
    return data


def test_published_schema_is_itself_valid() -> None:
    jsonschema.Draft202012Validator.check_schema(SCHEMA)


@pytest.mark.parametrize("path", REPORT_FIXTURES, ids=lambda p: p.name)
def test_fixtures_validate_with_both_implementations(path: Path) -> None:
    VALIDATOR.validate(json.loads(path.read_text()))
    load_report(path)


@pytest.mark.parametrize("path", REPORT_FIXTURES, ids=lambda p: p.name)
def test_round_trip_is_lossless(path: Path, tmp_path: Path) -> None:
    report = load_report(path)
    out = tmp_path / "out.json"
    out.write_text(dump_report(report))
    assert load_report(out) == report
    VALIDATOR.validate(json.loads(out.read_text()))


def test_schema_version_defaults_in_python_but_is_required_in_files() -> None:
    data = _base()
    del data["schema_version"]
    assert Report.model_validate(data).schema_version == SCHEMA_VERSION
    with pytest.raises(jsonschema.ValidationError):
        VALIDATOR.validate(data)


def test_upper_bound_source_is_kept() -> None:
    report = load_report(FIXTURES / "reports" / "similarity_full.json")
    assert report.similarity is not None
    s4 = report.similarity.sources[3]
    assert s4.percent == 1
    assert s4.percent_is_upper_bound


def _set(data: dict[str, Any], dotted: str, value: Any) -> dict[str, Any]:
    data = copy.deepcopy(data)
    *parents, last = dotted.split(".")
    node: Any = data
    for key in parents:
        node = node[int(key)] if key.isdigit() else node[key]
    if value is _DELETE:
        del node[last]
    elif isinstance(node, list):
        node[int(last)] = value
    else:
        node[last] = value
    return data


_DELETE = object()

# (case id, dotted path, value, also rejected by the JSON Schema?)
INVALID_CASES: list[tuple[str, str, Any, bool]] = [
    ("percent above 100", "similarity.overall_percent", 101, True),
    ("negative percent", "similarity.sources.0.percent", -1, True),
    ("unknown field", "submission.author", "x", True),
    ("student name has no field", "student_name", "x", True),
    ("naive datetime", "provenance.parsed_at", "2026-10-27T10:00:00", False),
    ("bad sha256", "provenance.report_file.sha256", "abc", True),
    ("tool name not a slug", "tool.name", "Turn It In", True),
    ("unknown source kind", "similarity.sources.0.kind", "blog", True),
    ("rank zero", "similarity.sources.0.rank", 0, True),
    ("bad extension key", "extensions", {"Not A Slug": {}}, True),
    ("similarity kind without section", "similarity", _DELETE, True),
    ("start without end", "similarity.matches.0.end", _DELETE, False),
    ("end before start", "similarity.matches.0.end", 100, False),
    ("match to unknown source", "similarity.matches.0.source_id", "s99", False),
    ("duplicate source id", "similarity.sources.1.id", "s1", False),
    ("duplicate match id", "similarity.matches.1.id", "m1", False),
    ("upper bound without percent", "similarity.sources.3.percent", _DELETE, False),
    ("wrong schema version", "schema_version", "9.9", True),
]


@pytest.mark.parametrize(
    ("dotted", "value", "schema_rejects"),
    [c[1:] for c in INVALID_CASES],
    ids=[c[0] for c in INVALID_CASES],
)
def test_invalid_reports_are_rejected(dotted: str, value: Any, schema_rejects: bool) -> None:
    data = _set(_base(), dotted, value)
    with pytest.raises(ValidationError):
        Report.model_validate(data)
    if schema_rejects:
        assert not VALIDATOR.is_valid(data)


def test_ai_writing_needs_a_result() -> None:
    data = json.loads((FIXTURES / "reports" / "ai_writing_label_only.json").read_text())
    del data["ai_writing"]["label"]
    with pytest.raises(ValidationError, match="overall_percent or label"):
        Report.model_validate(data)


def test_ai_kind_without_section_is_rejected_by_both() -> None:
    data = json.loads((FIXTURES / "reports" / "ai_writing_label_only.json").read_text())
    del data["ai_writing"]
    with pytest.raises(ValidationError):
        Report.model_validate(data)
    assert not VALIDATOR.is_valid(data)


def test_combined_needs_one_section() -> None:
    data = json.loads((FIXTURES / "reports" / "combined_minimal.json").read_text())
    assert Report.model_validate(data).tool.report_kind is ReportKind.COMBINED
    del data["similarity"]
    with pytest.raises(ValidationError):
        Report.model_validate(data)
    assert not VALIDATOR.is_valid(data)


def test_ai_segment_offsets_are_checked() -> None:
    data = json.loads((FIXTURES / "reports" / "ai_writing_label_only.json").read_text())
    data["ai_writing"]["segments"][0]["end"] = 0
    with pytest.raises(ValidationError, match="end must be greater"):
        Report.model_validate(data)
    del data["ai_writing"]["segments"][0]["end"]
    with pytest.raises(ValidationError, match="together"):
        Report.model_validate(data)


def test_models_are_immutable() -> None:
    report = load_report(FIXTURES / "reports" / "similarity_full.json")
    with pytest.raises(ValidationError):
        report.warnings = ["changed"]  # type: ignore[misc]
