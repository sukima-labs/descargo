"""Regenerate the published JSON Schemas under ``schemas/``.

Run ``uv run python -m draftwitness.core.schema_export`` after changing a schema model, and
commit the result. ``tests/test_schema_files.py`` fails when the files are stale.
"""

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from draftwitness.core.jurisdictions import PACK_SCHEMA_VERSION, Pack
from draftwitness.core.profiles import PROFILE_SCHEMA_VERSION, Profile
from draftwitness.core.report_schema import SCHEMA_VERSION as REPORT_VERSION
from draftwitness.core.report_schema import report_json_schema


def profile_json_schema() -> dict[str, Any]:
    """The JSON Schema for the current profile schema version."""
    return Profile.model_json_schema(mode="validation")


def pack_json_schema() -> dict[str, Any]:
    """The JSON Schema for the current jurisdiction pack schema version."""
    return Pack.model_json_schema(mode="validation")


#: Published path (relative to ``schemas/``) → schema factory.
PUBLISHED: dict[str, Callable[[], dict[str, Any]]] = {
    f"report/{REPORT_VERSION}.json": report_json_schema,
    f"profile/{PROFILE_SCHEMA_VERSION}.json": profile_json_schema,
    f"jurisdiction/{PACK_SCHEMA_VERSION}.json": pack_json_schema,
}


def render(schema: dict[str, Any]) -> str:
    """Stable text form used for the committed files."""
    return json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def export(root: Path) -> list[Path]:
    """Write every published schema under ``root`` and return the written paths."""
    written = []
    for relative, factory in PUBLISHED.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render(factory()), encoding="utf-8")
        written.append(target)
    return written


if __name__ == "__main__":  # pragma: no cover
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("schemas")
    for path in export(root):
        print(path)
