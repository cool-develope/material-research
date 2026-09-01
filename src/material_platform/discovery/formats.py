from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from material_platform.domain.enums import MaterialType, NodeKind


class FormatAction(StrEnum):
    EXPAND = "expand"
    ARTIFACT = "artifact"
    FILE = "file"
    DIRECTORY = "directory"


@dataclass(frozen=True)
class FormatDecision:
    action: FormatAction
    node_kind: NodeKind
    format: str
    material_hint: str | None = None
    peek: dict[str, object] = field(default_factory=dict)


_COMPOUND: tuple[tuple[str, str, FormatAction], ...] = (
    (".tar.gz", "tar.gz", FormatAction.EXPAND),
    (".tar.bz2", "tar.bz2", FormatAction.EXPAND),
    (".tar.xz", "tar.xz", FormatAction.EXPAND),
)

_SUFFIX: dict[str, tuple[FormatAction, str]] = {
    ".whl": (FormatAction.ARTIFACT, "python_wheel"),
    ".egg": (FormatAction.ARTIFACT, "python_egg"),
    ".jar": (FormatAction.ARTIFACT, "java_jar"),
    ".war": (FormatAction.ARTIFACT, "java_war"),
    ".nupkg": (FormatAction.ARTIFACT, "nuget"),
    ".docx": (FormatAction.FILE, "docx"),
    ".xlsx": (FormatAction.FILE, "xlsx"),
    ".pptx": (FormatAction.FILE, "pptx"),
    ".apk": (FormatAction.FILE, "android_apk"),
    ".ipa": (FormatAction.FILE, "ios_ipa"),
    ".appx": (FormatAction.FILE, "appx"),
    ".exe": (FormatAction.FILE, "installer"),
    ".msi": (FormatAction.FILE, "installer"),
    ".msix": (FormatAction.FILE, "installer"),
    ".dmg": (FormatAction.FILE, "installer"),
    ".pkg": (FormatAction.FILE, "installer"),
    ".zip": (FormatAction.EXPAND, "zip"),
    ".tar": (FormatAction.EXPAND, "tar"),
    ".tgz": (FormatAction.EXPAND, "tar.gz"),
    ".7z": (FormatAction.EXPAND, "7z"),
    ".gz": (FormatAction.EXPAND, "gzip"),
}

_HINT_TYPE: dict[str, tuple[MaterialType, str]] = {
    "python_wheel": (MaterialType.CODE, "python_wheel"),
    "python_egg": (MaterialType.CODE, "python_egg"),
    "java_jar": (MaterialType.CODE, "java_jar"),
    "java_war": (MaterialType.CODE, "java_war"),
    "nuget": (MaterialType.CODE, "nuget"),
    "node_tarball": (MaterialType.CODE, "node_tarball"),
    "docx": (MaterialType.DOCUMENT, "docx"),
    "xlsx": (MaterialType.SPREADSHEET, "xlsx"),
    "pptx": (MaterialType.PRESENTATION, "pptx"),
    "android_apk": (MaterialType.UNKNOWN, "android_apk"),
    "ios_ipa": (MaterialType.UNKNOWN, "ios_ipa"),
    "appx": (MaterialType.UNKNOWN, "appx"),
    "installer": (MaterialType.UNKNOWN, "installer"),
    "binary": (MaterialType.UNKNOWN, "binary"),
}

ARTIFACT_FORMATS = frozenset(
    {
        "python_wheel",
        "python_egg",
        "java_jar",
        "java_war",
        "nuget",
        "node_tarball",
    }
)
OFFICE_FORMATS = frozenset({"docx", "xlsx", "pptx"})
BINARY_FORMATS = frozenset(
    {"installer", "binary", "android_apk", "ios_ipa", "appx"}
)


def suffix_match(name: str) -> tuple[FormatAction, str] | None:
    lower = name.lower()
    for suffix, kind, action in _COMPOUND:
        if lower.endswith(suffix):
            return action, kind
    suffix = Path(lower).suffix
    found = _SUFFIX.get(suffix)
    return found


def type_from_hint(hint: str | None) -> tuple[MaterialType, str | None] | None:
    if hint is None:
        return None
    if hint.endswith("_project"):
        return MaterialType.PROJECT, hint.removesuffix("_project")
    if hint == "csv_dataset":
        return MaterialType.DATASET, "csv"
    matched = _HINT_TYPE.get(hint)
    if matched is None:
        return None
    return matched
