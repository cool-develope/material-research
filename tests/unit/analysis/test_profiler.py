from pathlib import Path

from material_platform.analysis.document import hierarchical_digests
from material_platform.analysis.group import content_tokens, group_units
from material_platform.analysis.profiler import build_profile
from material_platform.classification import classify_files
from material_platform.config import Settings
from material_platform.extraction import MaterialFile, extract_units
from tests.unit.discovery.artifacts import write_wheel
from tests.unit.helpers.analysis import (
    document_decision,
    fake_material,
    file_unit,
    page_unit,
    project_decision,
)


def test_group_units_covers_all_pages_without_sampling() -> None:
    units = tuple(
        page_unit(page, f"unique body for page {page} " + ("word " * 40))
        for page in range(1, 41)
    )
    groups = group_units(units, target_tokens=200)
    packed = [unit for group in groups for unit in group]
    assert len(packed) == 40
    assert packed[0].location.page == 1
    assert packed[-1].location.page == 40
    assert all(content_tokens(group) <= 200 + 40 for group in groups)


def test_group_units_prefers_heading_boundaries() -> None:
    body = "word " * 32
    units = (
        page_unit(1, body),
        page_unit(2, "# Methods\n" + ("word " * 10)),
        page_unit(3, "word " * 10),
    )
    groups = group_units(units, target_tokens=50)
    assert groups[0][0].location.page == 1
    assert len(groups[0]) == 1
    assert groups[1][0].location.page == 2
    assert groups[1][0].content.startswith("# Methods")


def test_hierarchical_digest_covers_every_page() -> None:
    units = tuple(
        page_unit(page, f"Chapter topic page {page}. " + ("data " * 30))
        for page in range(1, 25)
    )
    leaves = hierarchical_digests(units, leaf_tokens=150, fan_in=4)
    assert len(leaves) == 1
    covered = leaves[0]["covered_locations"]
    assert covered["page_start"] == 1
    assert covered["page_end"] == 24


def test_small_document_profile_is_direct() -> None:
    units = (page_unit(1, "Introduction to materials science."),)
    profile = build_profile(fake_material(), document_decision(), units)
    assert profile.mode == "direct"
    assert profile.coverage.ratio == 1.0
    assert profile.coverage.analyzed_units == 1
    assert "materials" in {item.lower() for item in profile.candidate_keywords}


def test_large_document_profile_is_hierarchical() -> None:
    units = tuple(
        page_unit(page, f"Section {page}. " + ("token " * 80)) for page in range(1, 30)
    )
    settings = Settings(
        _env_file=None,
        analysis_direct_tokens=200,
        analysis_leaf_tokens=300,
        analysis_reduce_fanin=4,
    )
    profile = build_profile(
        fake_material(), document_decision(), units, settings=settings
    )
    assert profile.mode == "hierarchical"
    assert profile.coverage.total_units == 29
    assert profile.coverage.analyzed_units == 29
    assert profile.coverage.ratio == 1.0
    assert profile.group_count > 1


def test_project_profile_scans_all_files_and_caps_deep_read() -> None:
    files = []
    from material_platform.extraction.common import MaterialFile

    files.append(MaterialFile(path="pyproject.toml", data=b"[project]\nname='x'\n"))
    files.append(MaterialFile(path="src/main.py", data=b"print('ok')\n"))
    files.append(
        MaterialFile(
            path="src/api.py",
            data=b"def handle_request(path: str) -> str:\n    return 'ok'\n",
        )
    )
    for index in range(30):
        files.append(
            MaterialFile(
                path=f"src/mod_{index:02d}.py",
                data=f"def fn_{index}():\n    return {index}\n".encode(),
            )
        )
    packed = tuple(files)
    units = tuple(file_unit(item.path, item.data.decode()) for item in packed[:8])
    profile = build_profile(
        fake_material("backend"), project_decision(), units, files=packed
    )
    assert profile.mode == "structural_sample"
    assert profile.coverage.structurally_scanned_files == 33
    assert profile.coverage.total_files == 33
    assert profile.coverage.deeply_analyzed_files == 8
    assert profile.coverage.deeply_analyzed_files < profile.coverage.total_files


def test_artifact_profile_uses_package_metadata(tmp_path: Path) -> None:
    wheel = write_wheel(tmp_path / "requests-2.32.3-py3-none-any.whl")
    files = (MaterialFile(path=wheel.name, data=wheel.read_bytes()),)
    decision = classify_files(tuple(item.path for item in files))
    units = extract_units(decision, files)
    profile = build_profile(fake_material(wheel.name), decision, units, files=files)
    assert profile.mode == "artifact_metadata"
    assert profile.identity.get("package") == "requests"
    assert profile.coverage.mode == "artifact_metadata"
    assert profile.coverage.ratio == 1.0
    assert "x = 1" not in (profile.section_digests[0].get("summary") or "")
