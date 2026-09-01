from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from tarfile import TarError, TarFile
from zipfile import BadZipFile, ZipFile


@dataclass(frozen=True)
class ArtifactPeek:
    title: str
    summary: str
    evidence: tuple[str, ...]
    metadata: dict[str, object]


def peek_wheel(path: Path) -> ArtifactPeek:
    return _peek_zip_file(path, kind="python_wheel", stem=path.stem)


def peek_jar(path: Path) -> ArtifactPeek:
    return _peek_zip_file(path, kind="java_jar", stem=path.stem)


def peek_zip_bytes(data: bytes, kind: str, stem: str) -> ArtifactPeek:
    return _peek_zip_file(BytesIO(data), kind=kind, stem=stem)


def peek_npm_tarball(path: Path) -> ArtifactPeek | None:
    try:
        with TarFile.open(path, mode="r:*") as archive:
            json_name = next(
                (
                    name
                    for name in archive.getnames()
                    if name.endswith("package/package.json")
                ),
                None,
            )
            if json_name is None:
                return None
            member = archive.extractfile(json_name)
            if member is None:
                return None
            raw = member.read().decode("utf-8", errors="replace")
    except (TarError, OSError):
        return None
    name = _json_field(raw, "name") or path.stem
    version = _json_field(raw, "version")
    title = f"{name} {version}".strip() if version else name
    return ArtifactPeek(
        title=title,
        summary=f"npm package {title}",
        evidence=("manifest:package.json",),
        metadata={"package": name, "version": version or ""},
    )


def peek_nuget(path: Path) -> ArtifactPeek:
    return ArtifactPeek(
        title=path.stem,
        summary="NuGet package",
        evidence=("suffix:nupkg",),
        metadata={},
    )


def _peek_zip_file(source: Path | BytesIO, *, kind: str, stem: str) -> ArtifactPeek:
    try:
        with ZipFile(source) as archive:
            if kind in {"python_wheel", "python_egg"}:
                return _wheel_from_zip(archive, stem)
            return _jar_from_zip(archive, stem, kind)
    except BadZipFile:
        return _missing(stem, kind)


def _wheel_from_zip(archive: ZipFile, stem: str) -> ArtifactPeek:
    meta_name = next(
        (name for name in archive.namelist() if name.endswith(".dist-info/METADATA")),
        None,
    )
    if meta_name is None:
        return _missing(stem, "python_wheel")
    text = archive.read(meta_name).decode("utf-8", errors="replace")
    name = _header(text, "Name") or stem
    version = _header(text, "Version")
    title = f"{name} {version}".strip() if version else name
    return ArtifactPeek(
        title=title,
        summary=f"Python wheel {title}",
        evidence=("manifest:METADATA",),
        metadata={"package": name, "version": version or ""},
    )


def _jar_from_zip(archive: ZipFile, stem: str, kind: str) -> ArtifactPeek:
    if "META-INF/MANIFEST.MF" not in archive.namelist():
        return _missing(stem, kind)
    text = archive.read("META-INF/MANIFEST.MF").decode("utf-8", errors="replace")
    title = (
        _header(text, "Implementation-Title")
        or _header(text, "Bundle-Name")
        or stem
    )
    version = _header(text, "Implementation-Version") or _header(
        text, "Bundle-Version"
    )
    label = f"{title} {version}".strip() if version else title
    return ArtifactPeek(
        title=label,
        summary=f"Java archive {label}",
        evidence=("manifest:MANIFEST.MF",),
        metadata={"package": title, "version": version or ""},
    )


def _missing(stem: str, kind: str) -> ArtifactPeek:
    return ArtifactPeek(
        title=stem,
        summary=f"{kind} artifact",
        evidence=("manifest:missing",),
        metadata={},
    )


def _header(text: str, key: str) -> str | None:
    prefix = f"{key}:"
    for line in text.splitlines():
        if line.startswith(prefix):
            value = line[len(prefix) :].strip()
            return value or None
    return None


def _json_field(raw: str, key: str) -> str | None:
    token = f'"{key}"'
    index = raw.find(token)
    if index < 0:
        return None
    rest = raw[index + len(token) :].lstrip()
    if not rest.startswith(":"):
        return None
    rest = rest[1:].lstrip()
    if not rest.startswith('"'):
        return None
    end = rest.find('"', 1)
    if end < 0:
        return None
    return rest[1:end]
