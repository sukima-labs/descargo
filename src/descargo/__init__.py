"""Descargo: local-first evidence toolkit for students facing detector false positives."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("descargo")
except PackageNotFoundError:  # pragma: no cover - only when running from a bare checkout
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
