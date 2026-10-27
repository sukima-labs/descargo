"""Compute the policies that apply to one course, degree or faculty.

Rules, applied from the institution down to the requested node:

* ``ai_policy``, ``self_plagiarism``, ``similarity_thresholds`` and ``tools`` are
  **overridden**: the most specific level that states them wins.
* ``regulations``, ``deadlines`` and ``contacts`` **accumulate**: a course still falls under
  its institution's regulations.
"""

from dataclasses import dataclass, field
from typing import Any, Final

from draftwitness.core.profiles.models import Degree, Faculty, Institution, Node, Policies, Profile

OVERRIDDEN: Final = ("ai_policy", "self_plagiarism", "similarity_thresholds", "tools")
ACCUMULATED: Final = ("regulations", "deadlines", "contacts")


class UnknownNodeError(LookupError):
    """The requested faculty/degree/course path does not exist in the profile."""


@dataclass(frozen=True)
class Resolved:
    """Effective policies for one node, and where each field came from."""

    chain: tuple[str, ...]
    """Node ids from the institution to the requested node."""
    policies: Policies
    origins: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Field name → ids of the nodes that supplied it."""


def _children(node: Node) -> list[Node]:
    if isinstance(node, Institution):
        return list(node.faculties)
    if isinstance(node, Faculty):
        return list(node.degrees)
    if isinstance(node, Degree):
        return list(node.courses)
    return []


def _chain(profile: Profile, path: str | None) -> list[Node]:
    node: Node = profile.institution
    chain = [node]
    parts = [p for p in (path or "").split("/") if p]
    if len(parts) > 3:
        raise UnknownNodeError(f"path {path!r} is deeper than faculty/degree/course")
    for level, part in zip(("faculty", "degree", "course"), parts, strict=False):
        found = {child.id: child for child in _children(node)}.get(part)
        if found is None:
            raise UnknownNodeError(f"no {level} {part!r} in {profile.id}")
        node = found
        chain.append(node)
    return chain


def resolve(profile: Profile, path: str | None = None) -> Resolved:
    """Merge policies along ``path`` (``"faculty"``, ``"faculty/degree"``, …)."""
    chain = _chain(profile, path)
    merged: dict[str, Any] = {}
    origins: dict[str, tuple[str, ...]] = {}
    for node in chain:
        for name in OVERRIDDEN:
            value = getattr(node.policies, name)
            if value:
                merged[name] = value
                origins[name] = (node.id,)
        for name in ACCUMULATED:
            items = getattr(node.policies, name)
            if items:
                merged[name] = [*merged.get(name, []), *items]
                origins[name] = (*origins.get(name, ()), node.id)
    return Resolved(
        chain=tuple(node.id for node in chain),
        policies=Policies.model_validate(merged),
        origins=origins,
    )
