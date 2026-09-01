from pathlib import Path
from zipfile import ZipFile

from py7zr import SevenZipFile


def write_wheel(path: Path, *, name: str = "requests", version: str = "2.32.3") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w") as archive:
        archive.writestr(
            f"{name}-{version}.dist-info/METADATA",
            f"Name: {name}\nVersion: {version}\n",
        )
        archive.writestr(f"{name}/__init__.py", "x = 1\n")
    return path


def write_jar(path: Path, *, title: str = "guava", version: str = "32.0") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "META-INF/MANIFEST.MF",
            f"Manifest-Version: 1.0\nImplementation-Title: {title}\n"
            f"Implementation-Version: {version}\n",
        )
        archive.writestr("com/example/A.class", b"\xca\xfe\xba\xbe")
    return path


def write_docx(path: Path, text: str = "Notes on materials") -> Path:
    from docx import Document

    path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.add_paragraph(text)
    document.save(path)
    return path


def write_pe(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"MZ" + b"\x00" * 64)
    return path


def write_7z(path: Path, entries: dict[str, bytes]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.parent / f"{path.stem}_src"
    staging.mkdir(exist_ok=True)
    with SevenZipFile(path, "w") as archive:
        for index, (name, data) in enumerate(entries.items()):
            file = staging / f"member_{index}"
            file.write_bytes(data)
            archive.write(file, name)
    return path
