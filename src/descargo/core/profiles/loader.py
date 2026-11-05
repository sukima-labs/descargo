"""Load, validate and inspect profile files."""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

from descargo.core.facts import Fact, Verification
from descargo.core.profiles.models import Profile


class ProfileError(ValueError):
    """A profile file cannot be read or does not match the schema."""

    def __init__(self, path: Path, problems: list[str]) -> None:
        self.path = path
        self.problems = problems
        super().__init__(f"{path}: " + "; ".join(problems))


def _format(error: ValidationError) -> list[str]:
    problems = []
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"]) or "(root)"
        problems.append(f"{location}: {item['msg']}")
    return problems


def load_profile(path: Path, *, root: Path | None = None) -> Profile:
    """Read a YAML profile and validate it.

    When ``root`` is given, the file must live at ``root/<country>/<institution>.yaml``
    matching the profile's ``id``.
    """
    try:
        data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ProfileError(path, [f"cannot read file: {exc}"]) from exc
    try:
        profile = Profile.model_validate(data)
    except ValidationError as exc:
        raise ProfileError(path, _format(exc)) from exc
    if root is not None:
        expected = Path(*profile.id.split("/")).with_suffix(".yaml")
        actual = path.resolve().relative_to(root.resolve())
        if actual != expected:
            raise ProfileError(path, [f"profile {profile.id!r} must live at {expected}"])
    return profile


def profile_paths(root: Path) -> list[Path]:
    """All profile files under ``root``, sorted."""
    return sorted(p for p in root.glob("*/*.yaml") if p.is_file())


def find_profile(root: Path, profile_id: str) -> Profile:
    """Load the profile with ``profile_id`` from ``root``."""
    path = root / Path(*profile_id.split("/")).with_suffix(".yaml")
    if not path.is_file():
        raise FileNotFoundError(f"no profile {profile_id!r} under {root}")
    return load_profile(path, root=root)


@dataclass(frozen=True)
class Unverified:
    """A fact still marked ``needs_verification``."""

    location: str
    fact: Fact[Any]


def _walk(value: object, location: str) -> Iterator[Unverified]:
    if isinstance(value, Fact):
        if value.verification is Verification.NEEDS_VERIFICATION:
            yield Unverified(location, value)
        return
    if isinstance(value, BaseModel):
        for name in type(value).model_fields:
            yield from _walk(getattr(value, name), f"{location}.{name}" if location else name)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            label = getattr(item, "id", None)
            yield from _walk(item, f"{location}[{label if label else index}]")


def unverified_facts(profile: Profile) -> list[Unverified]:
    """Every fact in ``profile`` that still needs human verification."""
    return list(_walk(profile, ""))
