from __future__ import annotations

import importlib
import sys

_COMMANDS = {
    "ingest": "material_platform.cli.ingest",
    "search": "material_platform.cli.search",
    "chat": "material_platform.cli.chat",
    "serve": "material_platform.cli.serve",
    "eval": "material_platform.eval.retrieve",
    "eval-aiml": "material_platform.eval.aiml",
}

_HELP = """\
usage: mp <command> ...

Commands:
  ingest      Discover materials in a file, directory, or ZIP
  search      Search indexed units and print citations
  chat        Deep Research: plan, retrieve, write a cited report
  serve       HTTP search and chat
  eval        Score labeled retrieval queries
  eval-aiml   Download/score the public AI/ML corpus
"""


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        sys.stdout.write(_HELP)
        return 0
    command = argv[0]
    module_name = _COMMANDS.get(command)
    if module_name is None:
        print(f"unknown command: {command}", file=sys.stderr)
        sys.stderr.write(_HELP)
        return 1
    module = importlib.import_module(module_name)
    return int(module.main(argv[1:]))
