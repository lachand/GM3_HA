"""Regression test for the failure mode that shipped in
plum_transport.py: `from .plum_utils import BoilerFrame, ...` where
`plum_utils.py` never existed (the module was actually renamed to
`plum_protocol.py`). That raises ImportError only when the module is
actually imported at runtime -- plum_transport.py wasn't imported by
anything else, so the break sat unnoticed until this was caught by
reading the source directly against the protocol spec.

This is a static, AST-based check (no Home Assistant import, no running
integration) so it doubles as a fast pre-commit-style guard: every
`from .module import name` in the component must point at a module file
that exists AND actually defines/re-exports that name.
"""

from __future__ import annotations

import ast
from pathlib import Path

COMPONENT_DIR = Path(__file__).resolve().parents[2] / "custom_components" / "plum_ecomax"


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _module_level_names(path: Path) -> set[str]:
    """Every name a module defines or re-exports at module level:
    function/class defs, plain assignments, and names brought in via its
    own imports (so a re-export chain still resolves).
    """
    names: set[str] = set()
    tree = _parse(path)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


def _relative_imports(path: Path) -> list[ast.ImportFrom]:
    tree = _parse(path)
    return [node for node in tree.body if isinstance(node, ast.ImportFrom) and node.level == 1]


def _iter_component_files():
    return sorted(COMPONENT_DIR.glob("*.py"))


class TestRelativeImportsResolve:
    def test_every_from_dot_import_target_module_exists(self):
        broken = []
        for path in _iter_component_files():
            for node in _relative_imports(path):
                if node.module is None:
                    continue  # `from . import x` -- package __init__, not checked here
                target = COMPONENT_DIR / f"{node.module}.py"
                if not target.exists():
                    broken.append(
                        f"{path.name}: 'from .{node.module} import ...' -- {target.name} does not exist"
                    )

        assert not broken, (
            "Broken relative import(s) -- module file doesn't exist, this "
            "is an ImportError waiting to happen the moment something "
            "actually imports the file:\n" + "\n".join(broken)
        )

    def test_every_imported_name_is_defined_in_its_target_module(self):
        broken = []
        for path in _iter_component_files():
            for node in _relative_imports(path):
                if node.module is None:
                    continue
                target = COMPONENT_DIR / f"{node.module}.py"
                if not target.exists():
                    continue  # already reported by the previous test
                available = _module_level_names(target)
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    if alias.name not in available:
                        broken.append(
                            f"{path.name}: 'from .{node.module} import {alias.name}' "
                            f"-- '{alias.name}' is not defined in {target.name}"
                        )

        assert not broken, (
            "Import of a name that doesn't actually exist in its source "
            "module:\n" + "\n".join(broken)
        )
