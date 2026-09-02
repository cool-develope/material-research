"""Pin retrieval/analysis knobs so a developer shell or leftover exports
cannot change the default pytest path. `.env` is ignored separately
(see Settings.settings_customise_sources).
"""

from __future__ import annotations

import os

_TEST_KNOBS = {
    "EMBEDDER": "fake",
    "RERANKER": "off",
    "ANALYZER": "deterministic",
    "AGENT_MODE": "standard",
}


def pytest_configure() -> None:
    for key, value in _TEST_KNOBS.items():
        os.environ[key] = value
