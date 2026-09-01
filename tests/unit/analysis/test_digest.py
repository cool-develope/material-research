from material_platform.analysis.digest import build_digest
from tests.unit.helpers.analysis import (
    document_decision,
    file_unit,
    page_unit,
    project_decision,
)


def test_digest_samples_eight_pages_from_500() -> None:
    units = tuple(
        page_unit(page, f"unique body for page {page} " + ("word " * 40))
        for page in range(1, 501)
    )
    digest = build_digest(document_decision(), units)
    assert digest.unit_count == 8
    assert digest.omitted_units == 492
    assert digest.token_count <= 8192
    assert "unique body for page 1" in digest.text
    assert "unique body for page 500" in digest.text
    assert "unique body for page 100" not in digest.text


def test_digest_does_not_send_twenty_project_files() -> None:
    units = tuple(
        file_unit(
            f"src/mod_{index:02d}.py",
            f"def handle_{index}():\n    return {'x ' * 200}",
        )
        for index in range(20)
    )
    digest = build_digest(project_decision(), units)
    assert digest.unit_count == 8
    assert digest.omitted_units == 12
    assert digest.token_count <= 8192


def test_digest_keeps_project_identity_plus_bodies() -> None:
    identity = file_unit("pyproject.toml", "[project]\nname='backend'\n")
    bodies = tuple(
        file_unit(f"src/api_{index}.py", f"def fn_{index}():\n    return {index}\n")
        for index in range(12)
    )
    digest = build_digest(project_decision(), (identity, *bodies))
    assert digest.unit_count == 9
    assert "pyproject.toml" in digest.text
    assert digest.omitted_units == 4
