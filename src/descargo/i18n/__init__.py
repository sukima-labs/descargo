"""User-interface strings, one TOML catalog per locale (ADR 003).

Keys are dotted names (``profile.valid``); values use ``str.format`` placeholders. English
is the fallback for missing keys and unknown locales.
"""

import os
import tomllib
from functools import cache
from importlib.resources import files
from typing import Final, Literal, get_args

Locale = Literal["en", "es"]

DEFAULT_LOCALE: Final = "en"
SUPPORTED_LOCALES: Final[tuple[str, ...]] = get_args(Locale)

_current = DEFAULT_LOCALE


def _flatten(table: dict[str, object], prefix: str = "") -> dict[str, str]:
    flat: dict[str, str] = {}
    for key, value in table.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, f"{name}."))
        else:
            flat[name] = str(value)
    return flat


@cache
def catalog(locale: str) -> dict[str, str]:
    """All strings for ``locale``, flattened to dotted keys."""
    text = files("descargo.i18n").joinpath("locales", f"{locale}.toml").read_text("utf-8")
    return _flatten(tomllib.loads(text))


def detect_locale(explicit: str | None = None) -> str:
    """Pick a supported locale from an explicit choice or the environment."""
    candidates = [
        explicit,
        os.environ.get("DESCARGO_LANG"),
        os.environ.get("LC_ALL"),
        os.environ.get("LC_MESSAGES"),
        os.environ.get("LANG"),
    ]
    for candidate in candidates:
        if candidate:
            code = candidate.split(".")[0].split("_")[0].split("-")[0].lower()
            if code in SUPPORTED_LOCALES:
                return code
    return DEFAULT_LOCALE


def set_locale(locale: str) -> None:
    """Set the locale used by :func:`t`."""
    global _current  # noqa: PLW0603 - one process-wide UI locale
    if locale not in SUPPORTED_LOCALES:
        raise ValueError(f"unsupported locale {locale!r}; supported: {SUPPORTED_LOCALES}")
    _current = locale


def get_locale() -> str:
    return _current


def tr(locale: str, key: str, /, **values: object) -> str:
    """Translate ``key`` into ``locale`` (falling back to English), e.g. for documents."""
    strings = catalog(locale) if locale in SUPPORTED_LOCALES else {}
    template = strings.get(key) or catalog(DEFAULT_LOCALE)[key]
    return template.format(**values)


def t(key: str, /, **values: object) -> str:
    """Translate ``key`` into the current interface locale, falling back to English."""
    return tr(_current, key, **values)
