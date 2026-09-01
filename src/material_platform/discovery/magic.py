from __future__ import annotations

from pathlib import Path

_ZIP = b"PK"
_GZIP = b"\x1f\x8b"
_SEVENZ = b"7z\xbc\xaf'\x1c"
_ELF = b"\x7fELF"
_PE = b"MZ"
_OLE = b"\xd0\xcf\x11\xe0"
_MACHO = (
    b"\xfe\xed\xfa\xce",
    b"\xfe\xed\xfa\xcf",
    b"\xce\xfa\xed\xfe",
    b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe",
)


def sniff_magic(path: Path) -> str | None:
    header = path.read_bytes()[:16]
    if header.startswith(_SEVENZ):
        return "7z"
    if header.startswith(_GZIP):
        return "gzip"
    if header.startswith(_ZIP):
        return "zip"
    if header.startswith(_ELF):
        return "elf"
    if header.startswith(_PE):
        return "pe"
    if header.startswith(_OLE):
        return "ole"
    if any(header.startswith(mark) for mark in _MACHO):
        return "macho"
    if _looks_like_tar(header, path):
        return "tar"
    return None


def _looks_like_tar(header: bytes, path: Path) -> bool:
    if path.stat().st_size < 262:
        return False
    with path.open("rb") as handle:
        handle.seek(257)
        ustar = handle.read(5)
    return ustar == b"ustar"
