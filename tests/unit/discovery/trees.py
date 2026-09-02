import tarfile
from pathlib import Path
from shutil import rmtree
from zipfile import ZipFile

from tests.unit.helpers.pdf import build_text_pdf
from tests.unit.helpers.text import numbered_words

COMPLEX_MATERIALS = (
    "README.md",
    "code/backend/",
    "frontend/",
    "lab/dataset/",
    "notes.txt",
    "papers/methods.md",
    "papers/survey.pdf",
    "shared.py",
    "snippet.py",
    "stats.csv",
    "tools/cli/",
)

FIXTURE_ZIP = (
    Path(__file__).resolve().parents[2] / "fixtures" / "mixed_zip" / "research.zip"
)
SIMPLE_ZIP = (
    Path(__file__).resolve().parents[2] / "fixtures" / "simple_mix" / "research.zip"
)
EVAL_HARD_ZIP = (
    Path(__file__).resolve().parents[2] / "fixtures" / "eval_hard" / "research.zip"
)
EVAL_LONG_ZIP = (
    Path(__file__).resolve().parents[2] / "fixtures" / "eval_long" / "research.zip"
)


def make_go_project(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "go.mod").write_text("module example.com/tools\n\ngo 1.22\n")
    (path / "main.go").write_text(
        "package main\n\nfunc HandleRequest(path string) string {\n"
        "\treturn \"ok\"\n}\n"
    )
    return path


def make_python_project(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "pyproject.toml").write_text("[project]\nname = 'backend'\n")
    (path / "src").mkdir()
    (path / "src" / "main.py").write_text("print('ok')\n")
    (path / "src" / "api.py").write_text(
        "def handle_request(path: str) -> str:\n    return 'ok'\n"
    )
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


def make_nested_lab_data(path: Path) -> Path:
    path.mkdir(parents=True)
    data = path / "lab" / "data"
    data.mkdir(parents=True)
    (data / "2023").mkdir()
    (data / "2024").mkdir()
    (data / "2023" / "results.csv").write_text("n,value\n1,2\n")
    (data / "2024" / "results.csv").write_text("n,value\n3,4\n")
    return path


def make_node_project(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "package.json").write_text('{"name":"frontend"}\n')
    (path / "src").mkdir()
    (path / "src" / "app.js").write_text("export const n = 1;\n")
    return path


def make_requirements_project(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "requirements.txt").write_text("pandas==2.2.0\n")
    (path / "cli.py").write_text("def main() -> None:\n    print('ok')\n")
    return path


def make_mixed_tree(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "paper.pdf").write_bytes(build_text_pdf(["Introduction to materials"]))
    make_python_project(path / "backend")
    make_dataset(path / "dataset")
    return path


def make_eval_hard_tree(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "README.md").write_text("# Research dump\n")
    (path / "notes.txt").write_text("todo: plot results\n")
    (path / "stats.csv").write_text("n,value\n1,3.2\n")
    (path / "lab_notes.md").write_text(
        "# Lab notes\nWe measured thermal runaway of a cell on a hot plate.\n"
    )
    (path / "batteries.pdf").write_bytes(
        build_text_pdf(
            [
                "Introduction to battery materials. Thermal properties of "
                "lithium cells are reviewed at a high level.",
                "Separator swelling under fast charge leads to thermal runaway. "
                "The failure starts at the separator.",
            ]
        )
    )
    backend = path / "backend"
    backend.mkdir()
    (backend / "pyproject.toml").write_text("[project]\nname = 'backend'\n")
    src = backend / "src"
    src.mkdir()
    (src / "main.py").write_text("print('ok')\n")
    (src / "api.py").write_text(
        "def handle_request(path: str) -> str:\n"
        "    return 'ok'\n"
        "\n"
        "def retry_failed_request(path: str) -> str:\n"
        "    delay = 0.1\n"
        "    return 'backoff'\n"
    )
    make_dataset(path / "dataset")
    make_requirements_project(path / "tools" / "cli")
    return path


def make_eval_long_tree(path: Path) -> Path:
    path.mkdir(parents=True)
    treatise = (
        "headmark_alpha appears at the start of the treatise.\n"
        + numbered_words(2_000, "bodyw")
        + "tailmark_omega appears at the end of the treatise.\n"
    )
    (path / "treatise.txt").write_text(treatise)
    make_python_project(path / "backend")
    make_dataset(path / "dataset")
    return path


def make_complex_tree(path: Path) -> Path:
    path.mkdir(parents=True)
    staging = path / "_staging"

    (path / "README.md").write_text("# Research dump\n")
    (path / "notes.txt").write_text("todo: plot results\n")
    (path / "stats.csv").write_text("n,value\n1,3.2\n")

    papers = path / "papers"
    papers.mkdir()
    (papers / "survey.pdf").write_bytes(build_text_pdf(["Survey of materials"]))
    (papers / "methods.md").write_text("# Methods\nWe measured X.\n")

    make_dataset(path / "lab" / "dataset")
    backend = make_python_project(path / "code" / "backend")
    junk = backend / "node_modules" / "left-pad"
    junk.mkdir(parents=True)
    (junk / "index.js").write_text("module.exports = 1\n")
    make_requirements_project(path / "tools" / "cli")

    macosx = path / "__MACOSX"
    macosx.mkdir()
    (macosx / "._README.md").write_text("resource fork\n")
    (path / ".DS_Store").write_bytes(b"junk")

    try:
        frontend = make_node_project(staging / "frontend")
        zip_named(frontend, path / "packages.zip")

        lib_src = staging / "libsrc"
        lib_src.mkdir()
        (lib_src / "shared.py").write_text("VALUE = 1\n")
        vendor = path / "vendor"
        vendor.mkdir()
        zip_contents(lib_src, vendor / "libs.zip")

        deep_src = staging / "deep"
        deep_src.mkdir()
        (deep_src / "snippet.py").write_text("def run():\n    return 42\n")
        deeper = staging / "deeper.zip"
        zip_contents(deep_src, deeper)
        inner_src = staging / "inner"
        inner_src.mkdir()
        (inner_src / "deeper.zip").write_bytes(deeper.read_bytes())
        nested = path / "nested"
        nested.mkdir()
        zip_contents(inner_src, nested / "inner.zip")
    finally:
        if staging.exists():
            rmtree(staging)

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


def tar_gz_contents(folder: Path, tar_path: Path) -> Path:
    with tarfile.open(tar_path, "w:gz") as archive:
        for file in folder.rglob("*"):
            if file.is_file():
                archive.add(file, arcname=file.relative_to(folder).as_posix())
    return tar_path
