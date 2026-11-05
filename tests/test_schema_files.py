from pathlib import Path

import pytest

from descargo.core.schema_export import PUBLISHED, export, render
from tests.conftest import REPO_ROOT


@pytest.mark.parametrize("relative", sorted(PUBLISHED))
def test_committed_schema_matches_models(relative: str) -> None:
    committed = (REPO_ROOT / "schemas" / relative).read_text(encoding="utf-8")
    assert committed == render(PUBLISHED[relative]()), (
        f"schemas/{relative} is stale: run `uv run python -m descargo.core.schema_export`"
    )


def test_export_writes_every_schema(tmp_path: Path) -> None:
    written = export(tmp_path)
    assert sorted(p.relative_to(tmp_path).as_posix() for p in written) == sorted(PUBLISHED)
