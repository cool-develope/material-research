from __future__ import annotations

import json
import re
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from tarfile import TarError, TarFile
from zipfile import BadZipFile, ZipFile

from material_platform.domain.research_material import ContentUnit
from material_platform.extraction.common import MaterialFile, make_unit

_REQ_SPLIT = re.compile(r"[<>=!~\[; ]")
_SKIP_WHEEL = frozenset({".dist-info", ".data"})


def extract_artifact(item: MaterialFile, subtype: str | None) -> ContentUnit:
    kind = subtype or "artifact"
    stem = Path(item.path).name
    if kind in {"python_wheel", "python_egg"}:
        fields, content = _from_zip(item.data, kind, stem, _wheel)
    elif kind in {"java_jar", "java_war"}:
        fields, content = _from_zip(item.data, kind, stem, _jar)
    elif kind == "node_tarball":
        fields, content = _npm(item.data, stem)
    else:
        fields = {"format": kind, "filename": stem}
        content = f"{kind} artifact"
    return make_unit(
        path=item.path,
        content=content,
        unit_type="artifact",
        metadata=fields,
    )


def _from_zip(
    data: bytes,
    kind: str,
    stem: str,
    reader: Callable[[ZipFile, str, str], tuple[dict[str, object], str]],
) -> tuple[dict[str, object], str]:
    try:
        with ZipFile(BytesIO(data)) as archive:
            return reader(archive, kind, stem)
    except BadZipFile:
        return {"format": kind, "filename": stem}, f"{kind} artifact"


def _wheel(
    archive: ZipFile, kind: str, stem: str
) -> tuple[dict[str, object], str]:
    meta_name = next(
        (name for name in archive.namelist() if name.endswith(".dist-info/METADATA")),
        None,
    )
    if meta_name is None:
        return {"format": kind, "filename": stem}, f"{kind} artifact"
    text = archive.read(meta_name).decode("utf-8", errors="replace")
    name = _header(text, "Name") or stem
    version = _header(text, "Version") or ""
    summary = _header(text, "Summary") or ""
    requires = [_req_name(item) for item in _headers(text, "Requires-Dist")]
    names = archive.namelist()
    modules = _wheel_modules(names)
    entry_points = _wheel_entry_points(archive, names)
    python_files = sum(1 for item in names if item.endswith(".py"))
    fields: dict[str, object] = {
        "format": kind,
        "filename": stem,
        "package": name,
        "title": f"{name} {version}".strip(),
        "version": version,
        "python_files": python_files,
    }
    if summary:
        fields["summary"] = summary
    if requires:
        fields["dependencies"] = requires[:30]
    if modules:
        fields["modules"] = modules[:20]
    if entry_points:
        fields["entry_points"] = entry_points[:20]
    return fields, _render(f"Python wheel {fields['title']}", fields)


def _jar(archive: ZipFile, kind: str, stem: str) -> tuple[dict[str, object], str]:
    names = archive.namelist()
    if "META-INF/MANIFEST.MF" not in names:
        return {"format": kind, "filename": stem}, f"{kind} artifact"
    text = archive.read("META-INF/MANIFEST.MF").decode("utf-8", errors="replace")
    title = (
        _header(text, "Implementation-Title")
        or _header(text, "Bundle-Name")
        or stem
    )
    version = _header(text, "Implementation-Version") or _header(
        text, "Bundle-Version"
    )
    packages = _jar_packages(names)
    label = f"{title} {version}".strip() if version else title
    fields: dict[str, object] = {
        "format": kind,
        "filename": stem,
        "package": title,
        "title": label,
        "version": version or "",
    }
    if packages:
        fields["modules"] = packages[:20]
    class_count = sum(1 for item in names if item.endswith(".class"))
    fields["class_count"] = class_count
    main_class = _header(text, "Main-Class")
    if main_class:
        fields["entry_points"] = [main_class]
    return fields, _render(f"Java archive {label}", fields)


def _npm(data: bytes, stem: str) -> tuple[dict[str, object], str]:
    raw = _npm_json(data)
    if raw is None:
        return {"format": "node_tarball", "filename": stem}, "node_tarball artifact"
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    name = payload.get("name") if isinstance(payload.get("name"), str) else stem
    version = payload.get("version") if isinstance(payload.get("version"), str) else ""
    summary = (
        payload.get("description")
        if isinstance(payload.get("description"), str)
        else ""
    )
    deps: list[str] = []
    for key in ("dependencies", "peerDependencies"):
        block = payload.get(key)
        if isinstance(block, dict):
            deps.extend(str(item) for item in block)
    label = f"{name} {version}".strip() if version else name
    fields: dict[str, object] = {
        "format": "node_tarball",
        "filename": stem,
        "package": name,
        "title": label,
        "version": version,
    }
    if summary:
        fields["summary"] = summary
    if deps:
        fields["dependencies"] = deps[:30]
    raw_keywords = payload.get("keywords")
    if isinstance(raw_keywords, list):
        fields["keywords"] = [
            str(item) for item in raw_keywords if isinstance(item, str)
        ][:20]
    bin_field = payload.get("bin")
    if isinstance(bin_field, dict):
        fields["entry_points"] = [str(item) for item in bin_field][:12]
    elif isinstance(bin_field, str):
        fields["entry_points"] = [bin_field]
    return fields, _render(f"npm package {label}", fields)


def _npm_json(data: bytes) -> str | None:
    try:
        with TarFile.open(fileobj=BytesIO(data), mode="r:*") as archive:
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
            return member.read().decode("utf-8", errors="replace")
    except (TarError, OSError):
        return None


def _wheel_entry_points(archive: ZipFile, names: list[str]) -> list[str]:
    path = next(
        (name for name in names if name.endswith(".dist-info/entry_points.txt")),
        None,
    )
    if path is None:
        return []
    text = archive.read(path).decode("utf-8", errors="replace")
    found: list[str] = []
    for line in text.splitlines():
        if "=" not in line or line.startswith("[") or line.startswith("#"):
            continue
        name = line.split("=", maxsplit=1)[0].strip()
        if name:
            found.append(name)
    return found


def _wheel_modules(names: tuple[str, ...] | list[str]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for name in names:
        top = name.split("/", maxsplit=1)[0]
        if not top or any(top.endswith(suffix) for suffix in _SKIP_WHEEL):
            continue
        if top in seen:
            continue
        seen.add(top)
        found.append(top)
    return found


def _jar_packages(names: list[str]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for name in names:
        if not name.endswith(".class") or name.startswith("META-INF/"):
            continue
        parent = name.rsplit("/", maxsplit=1)[0]
        if not parent or parent in seen:
            continue
        seen.add(parent)
        found.append(parent.replace("/", "."))
    return found


def _render(headline: str, fields: dict[str, object]) -> str:
    lines = [headline]
    for key in (
        "package",
        "version",
        "summary",
        "dependencies",
        "modules",
        "entry_points",
        "keywords",
        "python_files",
        "class_count",
    ):
        value = fields.get(key)
        if not value:
            continue
        if isinstance(value, list):
            lines.append(f"{key}: {', '.join(str(item) for item in value)}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def _header(text: str, key: str) -> str | None:
    values = _headers(text, key)
    return values[0] if values else None


def _headers(text: str, key: str) -> list[str]:
    prefix = f"{key}:"
    found: list[str] = []
    for line in text.splitlines():
        if line.startswith(prefix):
            value = line[len(prefix) :].strip()
            if value:
                found.append(value)
    return found


def _req_name(spec: str) -> str:
    return _REQ_SPLIT.split(spec, maxsplit=1)[0].strip() or spec
