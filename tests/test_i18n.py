import string

import pytest

from descargo.i18n import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    catalog,
    detect_locale,
    get_locale,
    set_locale,
    t,
)


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_every_locale_has_every_key(locale: str) -> None:
    assert set(catalog(locale)) == set(catalog(DEFAULT_LOCALE))


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_placeholders_match_english(locale: str) -> None:
    def fields(text: str) -> set[str]:
        return {name for _, name, _, _ in string.Formatter().parse(text) if name}

    english = catalog(DEFAULT_LOCALE)
    for key, text in catalog(locale).items():
        assert fields(text) == fields(english[key]), key


@pytest.mark.parametrize(
    ("explicit", "env", "expected"),
    [
        ("es", {}, "es"),
        (None, {"DESCARGO_LANG": "es"}, "es"),
        (None, {"LANG": "es_ES.UTF-8"}, "es"),
        (None, {"LANG": "fr_FR.UTF-8"}, "en"),
        (None, {}, "en"),
        ("de", {"LANG": "es_CO.UTF-8"}, "es"),
    ],
)
def test_detect_locale(
    explicit: str | None, env: dict[str, str], expected: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("DESCARGO_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    assert detect_locale(explicit) == expected


def test_translate_and_fallback() -> None:
    try:
        set_locale("es")
        assert get_locale() == "es"
        assert t("profile.summary", valid=1, invalid=0) == "1 válidos, 0 no válidos"
        with pytest.raises(ValueError, match="unsupported"):
            set_locale("xx")
    finally:
        set_locale(DEFAULT_LOCALE)
    assert t("common.not_legal_advice") == "Descargo is not legal advice."
