import stat
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest

from material_platform.discovery import (
    ArchiveLimits,
    SafeZipExpander,
    UnsafeArchiveError,
)

TIGHT = ArchiveLimits(
    max_files=10,
    max_total_bytes=2_000,
    max_member_bytes=1_000,
    max_ratio=20.0,
    timeout_seconds=5,
)


def _expander() -> SafeZipExpander:
    return SafeZipExpander(TIGHT)


def _zip_with(path: Path, entries: dict[str, bytes]) -> Path:
    with ZipFile(path, "w") as zip_file:
        for name, data in entries.items():
            zip_file.writestr(name, data)
    return path


def test_expands_safe_zip(tmp_path: Path) -> None:
    archive = _zip_with(
        tmp_path / "research.zip",
        {"paper.pdf": b"%PDF", "notes/readme.md": b"# hi"},
    )
    destination = tmp_path / "out"

    result = _expander().expand(archive, destination)

    assert result == destination.resolve()
    assert (destination / "paper.pdf").read_bytes() == b"%PDF"
    assert (destination / "notes" / "readme.md").read_bytes() == b"# hi"


def test_skips_macos_junk(tmp_path: Path) -> None:
    archive = _zip_with(
        tmp_path / "research.zip",
        {
            "paper.pdf": b"%PDF",
            "__MACOSX/._paper.pdf": b"junk",
            ".DS_Store": b"junk",
        },
    )
    destination = tmp_path / "out"

    _expander().expand(archive, destination)

    assert (destination / "paper.pdf").is_file()
    assert not (destination / ".DS_Store").exists()
    assert not (destination / "__MACOSX").exists()


def test_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "evil.zip"
    with ZipFile(archive, "w") as zip_file:
        zip_file.writestr(ZipInfo("../evil.txt"), b"nope")
    destination = tmp_path / "out"
    destination.mkdir()

    with pytest.raises(UnsafeArchiveError, match="path traversal"):
        _expander().expand(archive, destination)

    assert not destination.exists()


def test_rejects_encrypted_member() -> None:
    info = ZipInfo("secret.txt")
    info.flag_bits |= 0x1

    with pytest.raises(UnsafeArchiveError, match="encrypted"):
        _expander()._validate_member(info)


def test_rejects_symlink(tmp_path: Path) -> None:
    archive = tmp_path / "link.zip"
    info = ZipInfo("link")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with ZipFile(archive, "w") as zip_file:
        zip_file.writestr(info, b"/etc/passwd")

    with pytest.raises(UnsafeArchiveError, match="symlink"):
        _expander().expand(archive, tmp_path / "out")


def test_rejects_too_many_files(tmp_path: Path) -> None:
    archive = tmp_path / "many.zip"
    with ZipFile(archive, "w") as zip_file:
        for index in range(11):
            zip_file.writestr(f"f{index}.txt", b"x")

    with pytest.raises(UnsafeArchiveError, match="too many files"):
        _expander().expand(archive, tmp_path / "out")


def test_rejects_member_over_size_limit(tmp_path: Path) -> None:
    archive = _zip_with(tmp_path / "big.zip", {"blob.bin": b"x" * 1_001})

    with pytest.raises(UnsafeArchiveError, match="too large"):
        _expander().expand(archive, tmp_path / "out")


def test_rejects_suspicious_compression_ratio(tmp_path: Path) -> None:
    zeros = b"\x00" * 2_000
    archive = tmp_path / "bomb.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as zip_file:
        zip_file.writestr("zeros.bin", zeros)
    expander = SafeZipExpander(
        ArchiveLimits(
            max_files=10,
            max_total_bytes=50_000,
            max_member_bytes=50_000,
            max_ratio=5.0,
            timeout_seconds=5,
        )
    )

    with pytest.raises(UnsafeArchiveError, match="compression ratio"):
        expander.expand(archive, tmp_path / "out")
