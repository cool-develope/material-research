from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from material_platform.discovery.detectors.project import PROJECT_MARKERS
from material_platform.extraction.common import MaterialFile, decode_text

_REQ_SPLIT = re.compile(r"[<>=!~\[; ]")
_TOML_NAME = re.compile(r"(?m)^name\s*=\s*['\"]([^'\"]+)['\"]")
_GO_MODULE = re.compile(r"(?m)^module\s+(\S+)")
_GO_REQUIRE = re.compile(r"(?m)^\s*([a-zA-Z0-9./\-_]+)\s+v")


def project_identity(files: tuple[MaterialFile, ...]) -> dict[str, object]:
    fields: dict[str, object] = {}
    deps: list[str] = []
    names = {Path(item.path).name for item in files}
    for marker, language in PROJECT_MARKERS.items():
        if marker in names:
            fields["language"] = language
            break
    for item in files:
        parsed, extra = _parse(Path(item.path).name, decode_text(item.data))
        if parsed.get("package") and "package" not in fields:
            fields["package"] = parsed["package"]
        if parsed.get("title") and "title" not in fields:
            fields["title"] = parsed["title"]
        deps.extend(extra)
    unique = _unique(deps, limit=30)
    if unique:
        fields["dependencies"] = unique
    return fields


def _parse(name: str, text: str) -> tuple[dict[str, object], list[str]]:
    lower = name.lower()
    if lower == "package.json":
        return _package_json(text)
    if lower == "pyproject.toml":
        return _pyproject(text)
    if lower == "requirements.txt":
        return {}, _requirements(text)
    if lower == "go.mod":
        return _go_mod(text)
    if lower == "cargo.toml":
        return _cargo(text)
    return {}, []


def _package_json(text: str) -> tuple[dict[str, object], list[str]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}, []
    if not isinstance(payload, dict):
        return {}, []
    fields: dict[str, object] = {}
    name = payload.get("name")
    if isinstance(name, str) and name.strip():
        fields["package"] = name.strip()
        fields["title"] = name.strip()
    deps: list[str] = []
    for key in ("dependencies", "peerDependencies"):
        block = payload.get(key)
        if isinstance(block, dict):
            deps.extend(str(item) for item in block)
    return fields, deps


def _pyproject(text: str) -> tuple[dict[str, object], list[str]]:
    fields: dict[str, object] = {}
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        data = {}
    project = _table(data, "project")
    name = project.get("name") if isinstance(project.get("name"), str) else None
    if not name:
        match = _TOML_NAME.search(text)
        name = match.group(1) if match else None
    if name:
        fields["package"] = name
        fields["title"] = name
    deps = project.get("dependencies")
    extra = [_req_name(str(item)) for item in deps] if isinstance(deps, list) else []
    return fields, extra


def _cargo(text: str) -> tuple[dict[str, object], list[str]]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return {}, []
    package = _table(data, "package")
    fields: dict[str, object] = {}
    name = package.get("name")
    if isinstance(name, str) and name.strip():
        fields["package"] = name.strip()
        fields["title"] = name.strip()
    block = data.get("dependencies")
    deps = list(block) if isinstance(block, dict) else []
    return fields, deps


def _go_mod(text: str) -> tuple[dict[str, object], list[str]]:
    fields: dict[str, object] = {}
    match = _GO_MODULE.search(text)
    if match:
        fields["package"] = match.group(1)
        fields["title"] = match.group(1)
    return fields, [item.group(1) for item in _GO_REQUIRE.finditer(text)]


def _requirements(text: str) -> list[str]:
    found: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            continue
        name = _req_name(stripped)
        if name:
            found.append(name)
    return found


def _table(data: dict[str, object], key: str) -> dict[str, object]:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def _req_name(spec: str) -> str:
    return _REQ_SPLIT.split(spec, maxsplit=1)[0].strip()


def _unique(items: list[str], *, limit: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip()
        if not key:
            continue
        lowered = key.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        out.append(key)
        if len(out) >= limit:
            break
    return out
