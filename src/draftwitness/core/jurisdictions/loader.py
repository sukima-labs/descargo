"""Load jurisdiction packs and resolve ``extends`` chains."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from draftwitness.core.jurisdictions.models import AccessRequestSpec, Pack


class PackError(ValueError):
    """A pack cannot be found, read or validated, or its ``extends`` chain is broken."""


def load_pack(root: Path, pack_id: str) -> Pack:
    """Read and validate ``root/<pack_id>/pack.yaml``."""
    path = root / pack_id / "pack.yaml"
    try:
        data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        pack = Pack.model_validate(data)
    except FileNotFoundError as exc:
        raise PackError(f"no jurisdiction pack {pack_id!r} under {root}") from exc
    except (OSError, UnicodeDecodeError, yaml.YAMLError, ValidationError) as exc:
        raise PackError(f"{path}: {exc}") from exc
    if pack.id != pack_id:
        raise PackError(f"{path}: id {pack.id!r} does not match folder {pack_id!r}")
    for template in (pack.access_request.templates if pack.access_request else {}).values():
        if not (root / pack_id / template).is_file():
            raise PackError(f"{path}: template {template!r} not found")
    return pack


def pack_ids(root: Path) -> list[str]:
    return sorted(p.parent.name for p in root.glob("*/pack.yaml"))


@dataclass(frozen=True)
class ResolvedAccessRequest:
    """An access-request spec with ``extends`` applied, and where each template lives."""

    chain: tuple[str, ...]
    """Pack ids from the requested pack up to the most general one."""
    spec: AccessRequestSpec
    template_files: dict[str, Path]


def _chain(root: Path, pack_id: str) -> list[Pack]:
    chain: list[Pack] = []
    seen: set[str] = set()
    current: str | None = pack_id
    while current is not None:
        if current in seen:
            raise PackError(f"circular extends: {' -> '.join([*seen, current])}")
        seen.add(current)
        pack = load_pack(root, current)
        chain.append(pack)
        current = pack.extends
    return chain


def resolve_access_request(root: Path, pack_id: str) -> ResolvedAccessRequest:
    """Merge the access-request spec of ``pack_id`` with the packs it extends."""
    chain = _chain(root, pack_id)
    merged: dict[str, Any] = {"legal_bases": [], "prerequisites": []}
    templates: dict[str, Path] = {}
    for pack in reversed(chain):  # general → specific
        spec = pack.access_request
        if spec is None:
            continue
        merged["legal_bases"] = [*merged["legal_bases"], *spec.legal_bases]
        merged["prerequisites"] = [*merged["prerequisites"], *spec.prerequisites]
        for name in ("response_deadline", "authority"):
            if getattr(spec, name) is not None:
                merged[name] = getattr(spec, name)
        if spec.recipient_roles:
            merged["recipient_roles"] = spec.recipient_roles
        for language, template in spec.templates.items():
            templates[language] = root / pack.id / template
    if not templates:
        raise PackError(f"pack {pack_id!r} has no access-request template")
    resolved_spec = AccessRequestSpec.model_validate(merged)
    return ResolvedAccessRequest(
        chain=tuple(p.id for p in chain), spec=resolved_spec, template_files=templates
    )
