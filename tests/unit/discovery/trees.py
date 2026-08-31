from pathlib import Path
from zipfile import ZipFile


def make_python_project(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "pyproject.toml").write_text("[project]\nname = 'backend'\n")
    (path / "src").mkdir()
    (path / "src" / "main.py").write_text("print('ok')\n")
    (path / "tests").mkdir()
    (path / "tests" / "test_main.py").write_text(
        "def test_ok() -> None:\n    assert True\n"
    )
    (path / "docs").mkdir()
    (path / "docs" / "guide.md").write_text("# Guide\n")
    return path


def make_dataset(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "rows.csv").write_text("a,b\n1,2\n")
    return path


def make_mixed_tree(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "paper.pdf").write_bytes(b"%PDF-1.4")
    make_python_project(path / "backend")
    make_dataset(path / "dataset")
    return path


def zip_contents(folder: Path, zip_path: Path) -> Path:
    with ZipFile(zip_path, "w") as zip_file:
        for file in folder.rglob("*"):
            if file.is_file():
                zip_file.write(file, file.relative_to(folder).as_posix())
    return zip_path


def zip_named(folder: Path, zip_path: Path) -> Path:
    with ZipFile(zip_path, "w") as zip_file:
        for file in folder.rglob("*"):
            if file.is_file():
                arc = f"{folder.name}/{file.relative_to(folder).as_posix()}"
                zip_file.write(file, arc)
    return zip_path
