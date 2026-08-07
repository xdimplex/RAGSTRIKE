"""Project audit -- structure, imports, dead code, and documentation coverage.

WHY THIS IS SEPARATE FROM THE CONSISTENCY CHECKS
    ``consistency.py`` asks "does the machinery work". This asks "is the codebase maintainable" --
    a different question with a different audience. One is run before a scan; this is run before a
    release, or when someone new is deciding whether to trust the repository.

WHY THE CYCLE DETECTOR MODELS WHAT PYTHON EXECUTES
    Getting this right took three attempts, and the wrong answers are instructive.

    **Attempt one** treated a package and its ``__init__`` as separate nodes, then resolved an import
    of ``a.b`` to every module under ``a.b``. That reported **32 cycles**, essentially all of which
    were ordinary parent/child re-exports.

    **Attempt two** fixed the resolution and reported **1** -- between ``plugins.base.attack`` and
    ``plugins.base.payloads``. Still wrong: that edge exists only through a ``TYPE_CHECKING`` block
    and a function-level import, both of which are the *standard fixes* for a cycle, and the source
    carries a comment saying so.

    **This version** separates imports that run at import time from those that do not, and reports
    them in different fields. Import-time cycles can deadlock; a function-level import runs when both
    modules are already loaded and cannot.

    The point is not pedantry. An audit that cries wolf gets ignored, and an ignored audit misses the
    real finding when one arrives.
"""

from __future__ import annotations

import ast
import collections
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SRC = Path("src/ragstrike")


@dataclass
class AuditReport:
    """Everything the audit measured."""

    modules: int = 0
    code_lines: int = 0
    module_docstrings: int = 0
    packages: int = 0
    package_readmes: int = 0
    missing_readmes: list[str] = field(default_factory=list)
    #: Cycles among imports that execute at import time. These are the ones that can break.
    import_time_cycles: list[list[str]] = field(default_factory=list)
    #: Cycles that exist in the graph only because of a TYPE_CHECKING or function-level import.
    #: Deliberate, standard, and harmless -- reported so a naive tool flagging them can be
    #: answered without re-deriving the analysis.
    deferred_cycles: list[list[str]] = field(default_factory=list)
    unreferenced: list[str] = field(default_factory=list)

    @property
    def docstring_coverage(self) -> float:
        return self.module_docstrings / self.modules if self.modules else 0.0

    @property
    def readme_coverage(self) -> float:
        return self.package_readmes / self.packages if self.packages else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "modules": self.modules,
            "code_lines": self.code_lines,
            "docstring_coverage": round(self.docstring_coverage, 4),
            "packages": self.packages,
            "readme_coverage": round(self.readme_coverage, 4),
            "missing_readmes": self.missing_readmes,
            "import_time_cycles": self.import_time_cycles,
            "deferred_cycles": self.deferred_cycles,
            "unreferenced_modules": self.unreferenced,
        }


def _deferred_lines(tree: ast.Module) -> set[int]:
    """Line numbers whose imports do **not** execute when the module is first imported.

    Two kinds, and both matter for cycle detection:

    **``if TYPE_CHECKING:`` blocks** never execute at all.

    **Function bodies** execute when the function is *called*, by which point both modules are fully
    loaded. A function-level import can therefore close a graph cycle without being able to deadlock
    — which is precisely why it is the standard fix, and why ``plugins/base/attack.py`` uses it with
    a comment saying so.

    A class body is *not* deferred: it runs at import time like any other module-level statement.
    """
    deferred: set[int] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            test = node.test
            name = (
                test.id
                if isinstance(test, ast.Name)
                else test.attr if isinstance(test, ast.Attribute) else ""
            )
            if name == "TYPE_CHECKING":
                deferred.update(c.lineno for c in ast.walk(node) if hasattr(c, "lineno"))
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for statement in node.body:
                deferred.update(c.lineno for c in ast.walk(statement) if hasattr(c, "lineno"))

    return deferred


def _module_name(path: Path, root: Path) -> str:
    """The dotted name Python would use.

    ``__init__.py`` becomes the *package* name, not ``package.__init__``. Getting this wrong is what
    made the first version report 32 cycles: it treated a package and its ``__init__`` as two nodes,
    so every ordinary re-export looked like a loop.
    """
    parts = path.relative_to(root.parent).with_suffix("").parts
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def collect(root: Path = SRC) -> AuditReport:
    """Walk the source tree and measure it."""
    report = AuditReport()
    files = sorted(root.rglob("*.py"))
    report.modules = len(files)

    runtime: dict[str, set[str]] = collections.defaultdict(set)
    deferred: dict[str, set[str]] = collections.defaultdict(set)
    referenced: set[str] = set()

    for path in files:
        source = path.read_text(encoding="utf-8")
        report.code_lines += len(
            [
                line
                for line in source.splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
        )
        try:
            tree = ast.parse(source)
        except SyntaxError:  # pragma: no cover - a syntax error fails the lint gate first
            continue

        if ast.get_docstring(tree):
            report.module_docstrings += 1

        deferred_lines = _deferred_lines(tree)
        module = _module_name(path, root)

        for node in ast.walk(tree):
            targets: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                targets = [node.module]
            elif isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            for target in targets:
                if not target.startswith("ragstrike"):
                    continue
                referenced.add(target)
                bucket = deferred if node.lineno in deferred_lines else runtime
                bucket[module].add(target)

    report.import_time_cycles = _cycles(runtime)
    combined = {k: set(v) for k, v in runtime.items()}
    for module, deps in deferred.items():
        combined.setdefault(module, set()).update(deps)
    report.deferred_cycles = [c for c in _cycles(combined) if c not in report.import_time_cycles]

    packages = [d for d in root.rglob("*") if d.is_dir() and (d / "__init__.py").exists()]
    report.packages = len(packages)
    report.package_readmes = sum(1 for p in packages if (p / "README.md").exists())
    report.missing_readmes = sorted(
        str(p.relative_to(root)).replace("\\", "/")
        for p in packages
        if not (p / "README.md").exists()
    )

    # A module nobody imports is either an entry point, a plugin loaded by discovery, or dead.
    # Reported rather than judged: this audit does not know which.
    entry_points = {"ragstrike.cli.main", "ragstrike.dashboard.app", "ragstrike"}
    report.unreferenced = sorted(
        _module_name(path, root)
        for path in files
        if path.name != "__init__.py"
        and _module_name(path, root) not in entry_points
        and not any(
            ref == _module_name(path, root) or _module_name(path, root).startswith(ref + ".")
            for ref in referenced
        )
    )
    return report


def _cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Every distinct cycle in an import graph, resolving package imports to their modules."""
    # An import of `a.b.c` executes `a.b.c` -- and, if that is a package, its __init__ only. It does
    # NOT execute every sibling submodule. Fanning out to submodules (as the first version did)
    # manufactures cycles out of ordinary parent/child re-exports.
    resolved: dict[str, set[str]] = {}
    for module, deps in graph.items():
        edges = {dep for dep in deps if dep in graph}
        resolved[module] = edges - {module}

    found: list[list[str]] = []
    seen: set[frozenset[str]] = set()
    colour: dict[str, int] = collections.defaultdict(int)
    stack: list[str] = []

    def visit(node: str) -> None:
        colour[node] = 1
        stack.append(node)
        for neighbour in sorted(resolved.get(node, ())):
            if colour[neighbour] == 1:
                cycle = [*stack[stack.index(neighbour) :], neighbour]
                key = frozenset(cycle)
                if key not in seen:
                    seen.add(key)
                    found.append(cycle)
            elif colour[neighbour] == 0:
                visit(neighbour)
        colour[node] = 2
        stack.pop()

    for node in sorted(resolved):
        if colour[node] == 0:
            visit(node)
    return found
