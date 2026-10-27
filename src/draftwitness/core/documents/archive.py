"""Safe reading of ZIP + XML documents (DOCX, ODT).

Each archive member is size-checked before it is read, and XML is parsed with defusedxml,
so a hostile file cannot exhaust memory or pull in external entities.
"""

import zipfile
from typing import Final
from xml.etree.ElementTree import Element

from defusedxml import DefusedXmlException, ElementTree

MAX_MEMBER_BYTES: Final = 64 * 1024 * 1024


class DocumentError(ValueError):
    """The file cannot be read as a supported document."""


def read_member(archive: zipfile.ZipFile, name: str) -> bytes | None:
    """The bytes of ``name``, or ``None`` if the archive has no such member."""
    try:
        info = archive.getinfo(name)
    except KeyError:
        return None
    if info.file_size > MAX_MEMBER_BYTES:
        raise DocumentError(f"{name} is larger than {MAX_MEMBER_BYTES} bytes")
    return archive.read(info)


def parse_xml(data: bytes, name: str) -> Element:
    try:
        root: Element = ElementTree.fromstring(data)
    except (ElementTree.ParseError, DefusedXmlException) as exc:
        raise DocumentError(f"{name}: {exc!r}") from exc
    return root
