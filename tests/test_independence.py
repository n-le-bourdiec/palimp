"""The analyzer and the simulator never import each other (decision 0009)."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def imported_roots(directory: Path) -> set[str]:
    roots = set()
    for path in directory.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                roots.add(node.module.split(".")[0])
    return roots


def test_analyzer_does_not_import_simulator() -> None:
    assert "palimp_sim" not in imported_roots(ROOT / "src" / "palimp")


def test_simulator_does_not_import_analyzer() -> None:
    assert "palimp" not in imported_roots(ROOT / "simulator")
