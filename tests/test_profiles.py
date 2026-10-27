import copy
import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
import yaml
from pydantic import ValidationError

from draftwitness.core.data import data_dir
from draftwitness.core.profiles import (
    PROFILE_SCHEMA_VERSION,
    Profile,
    ProfileError,
    UnknownNodeError,
    Verification,
    find_profile,
    load_profile,
    profile_paths,
    resolve,
    unverified_facts,
)
from draftwitness.core.profiles.models import AiStance, ThresholdKind
from tests.conftest import FIXTURES, REPO_ROOT

SYNTHETIC_ROOT = FIXTURES / "profiles"
SYNTHETIC = SYNTHETIC_ROOT / "zz" / "synthetic-university.yaml"
SCHEMA = json.loads(
    (REPO_ROOT / "schemas" / "profile" / f"{PROFILE_SCHEMA_VERSION}.json").read_text()
)
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)
BUNDLED = profile_paths(data_dir("profiles"))


def _as_json(path: Path) -> Any:
    """YAML as a JSON document would see it (dates become strings), for jsonschema."""
    return json.loads(json.dumps(yaml.safe_load(path.read_text()), default=str))


def _data() -> dict[str, Any]:
    data: dict[str, Any] = _as_json(SYNTHETIC)
    return data


def test_synthetic_profile_loads_and_matches_schema() -> None:
    profile = load_profile(SYNTHETIC, root=SYNTHETIC_ROOT)
    assert profile.id == "zz/synthetic-university"
    VALIDATOR.validate(_data())


def test_bundled_profiles_exist() -> None:
    assert len(BUNDLED) >= 2


@pytest.mark.parametrize("path", BUNDLED, ids=lambda p: p.stem)
def test_bundled_profiles_are_valid(path: Path) -> None:
    load_profile(path, root=data_dir("profiles"))
    VALIDATOR.validate(_as_json(path))


@pytest.mark.parametrize("path", BUNDLED, ids=lambda p: p.stem)
def test_bundled_facts_have_sources_or_are_flagged(path: Path) -> None:
    """Every fact either has a source, or is flagged and says why it has none."""
    for item in unverified_facts(load_profile(path)):
        assert item.fact.source_url or item.fact.note, item.location


def test_resolution_overrides_and_accumulates() -> None:
    profile = load_profile(SYNTHETIC)
    top = resolve(profile)
    assert top.chain == ("synthetic-university",)
    assert top.policies.ai_policy is not None
    assert top.policies.ai_policy.value.stance is AiStance.INSTRUCTOR_DECIDES
    assert top.policies.similarity_thresholds[0].value.kind is ThresholdKind.NONE_PUBLISHED

    course = resolve(profile, "science/biology/bio-thesis")
    assert course.chain == ("synthetic-university", "science", "biology", "bio-thesis")
    assert course.policies.ai_policy is not None
    assert course.policies.ai_policy.value.stance is AiStance.ALLOWED_WITH_DISCLOSURE
    assert course.origins["ai_policy"] == ("bio-thesis",)
    assert course.policies.similarity_thresholds[0].value.percent == 20
    assert course.origins["similarity_thresholds"] == ("biology",)
    assert [d.value.kind.value for d in course.policies.deadlines] == [
        "grade_review",
        "grade_appeal",
    ]
    assert course.origins["deadlines"] == ("synthetic-university", "bio-thesis")
    assert len(course.policies.contacts) == 2
    assert course.policies.tools == top.policies.tools


@pytest.mark.parametrize("path", ["nope", "science/nope", "science/biology/nope", "a/b/c/d"])
def test_unknown_paths_raise(path: str) -> None:
    with pytest.raises(UnknownNodeError):
        resolve(load_profile(SYNTHETIC), path)


def test_unverified_facts_are_listed_with_locations() -> None:
    locations = [u.location for u in unverified_facts(load_profile(SYNTHETIC))]
    assert "institution.policies.similarity_thresholds[0]" in locations
    assert (
        "institution.faculties[science].degrees[biology].courses[bio-thesis].policies.ai_policy"
        in locations
    )
    assert "institution.policies.ai_policy" not in locations  # verified


def test_find_profile() -> None:
    assert find_profile(SYNTHETIC_ROOT, "zz/synthetic-university").country == "ZZ"
    with pytest.raises(FileNotFoundError):
        find_profile(SYNTHETIC_ROOT, "zz/missing")


def test_file_location_must_match_id(tmp_path: Path) -> None:
    misplaced = tmp_path / "zz" / "elsewhere.yaml"
    misplaced.parent.mkdir()
    misplaced.write_text(SYNTHETIC.read_text())
    with pytest.raises(ProfileError, match="must live at"):
        load_profile(misplaced, root=tmp_path)


def test_invalid_profile_reports_every_problem() -> None:
    with pytest.raises(ProfileError) as exc:
        load_profile(FIXTURES / "profiles_invalid" / "zz" / "bad.yaml")
    joined = " | ".join(exc.value.problems)
    assert "verified fact needs source_url and checked_on" in joined
    assert "hard thresholds need a percent" in joined


def test_broken_yaml_is_a_profile_error() -> None:
    with pytest.raises(ProfileError, match="cannot read file"):
        load_profile(FIXTURES / "profiles_invalid" / "zz" / "broken.yaml")


def _mutate(dotted: str, value: Any) -> dict[str, Any]:
    data = copy.deepcopy(_data())
    *parents, last = dotted.split(".")
    node: Any = data
    for key in parents:
        node = node[int(key)] if key.isdigit() else node[key]
    node[last] = value
    return data


INVALID: list[tuple[str, str, Any, bool]] = [
    ("country mismatch", "country", "ES", False),
    ("lowercase country", "country", "zz", True),
    ("institution id mismatch", "institution.id", "other", False),
    ("unknown stance", "institution.policies.ai_policy.value.stance", "maybe", True),
    ("verified without date", "institution.policies.ai_policy.checked_on", None, True),
    (
        "percent on none_published",
        "institution.policies.similarity_thresholds.0.value",
        {"kind": "none_published", "percent": 10},
        False,
    ),
    (
        "percent above 100",
        "institution.faculties.0.degrees.0.policies.similarity_thresholds.0.value",
        {"kind": "hard", "percent": 120},
        True,
    ),
    (
        "contact without channel",
        "institution.policies.contacts.0.value",
        {"role": "ombuds", "name": "Ombuds"},
        False,
    ),
    ("bad email", "institution.policies.contacts.0.value.email", "not-an-email", True),
    ("bad url", "institution.official_url", "ftp://x", True),
    (
        "tool without features",
        "institution.policies.tools.0.value",
        {"tool": "turnitin", "features": []},
        True,
    ),
    ("zero deadline", "institution.policies.deadlines.0.value.amount", 0, True),
    (
        "duplicate faculty",
        "institution.faculties",
        [{"id": "a", "name": "A"}, {"id": "a", "name": "B"}],
        False,
    ),
    ("unknown key", "institution.rank", 1, True),
]


@pytest.mark.parametrize(
    ("dotted", "value", "schema_rejects"), [c[1:] for c in INVALID], ids=[c[0] for c in INVALID]
)
def test_invalid_profiles_are_rejected(dotted: str, value: Any, schema_rejects: bool) -> None:
    data = _mutate(dotted, value)
    with pytest.raises(ValidationError):
        Profile.model_validate(data)
    if schema_rejects:
        assert not VALIDATOR.is_valid(data)


def test_duplicate_degree_and_course_ids() -> None:
    degree = _data()["institution"]["faculties"][0]["degrees"][0]
    data = _mutate("institution.faculties.0.degrees", [degree, degree])
    with pytest.raises(ValidationError, match="duplicate degree"):
        Profile.model_validate(data)
    course = degree["courses"][0]
    data = _mutate("institution.faculties.0.degrees.0.courses", [course, course])
    with pytest.raises(ValidationError, match="duplicate course"):
        Profile.model_validate(data)


def test_verification_default_is_needs_verification() -> None:
    profile = load_profile(SYNTHETIC)
    assert (
        profile.institution.policies.regulations[0].verification is Verification.NEEDS_VERIFICATION
    )
