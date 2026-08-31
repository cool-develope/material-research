from uuid import UUID


def raw_original(source_id: UUID) -> str:
    return f"raw/{source_id}/original"


def discovery_manifest(source_id: UUID, discovery_run_id: UUID) -> str:
    return f"manifests/{source_id}/{discovery_run_id}.json"


def material_content_root(material_id: UUID) -> str:
    return f"materials/{material_id}/content"


def material_content_manifest(material_id: UUID) -> str:
    return f"materials/{material_id}/content-manifest.json"


def material_content(material_id: UUID, relative_path: str) -> str:
    normalized = relative_path.replace("\\", "/").lstrip("/")
    return f"materials/{material_id}/content/{normalized}"
