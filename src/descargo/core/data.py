"""Locate the data folders (profiles, jurisdictions, schemas) shipped with Descargo."""

from importlib.resources import files
from pathlib import Path
from typing import Literal

DataFolder = Literal["profiles", "jurisdictions", "schemas"]


def data_dir(name: DataFolder) -> Path:
    """Path to a bundled data folder.

    Wheels carry the folders under ``descargo/_data/``; a source checkout (including an
    editable install) uses the folders at the repository root.
    """
    bundled = Path(str(files("descargo"))) / "_data" / name
    if bundled.is_dir():
        return bundled
    checkout = Path(__file__).resolve().parents[3] / name
    if checkout.is_dir():
        return checkout
    raise FileNotFoundError(f"bundled data folder {name!r} not found")  # pragma: no cover
