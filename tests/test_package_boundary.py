"""Cross-package boundary invariants (repo-coherence audit).

These tests pin the canonical import directions between
`research_institution`'s modules. A regression that breaks these
invariants (e.g. someone re-puts `GateVerdict` in `cli.py`) will
surface here immediately.

Invariant 1 (RC1, boundary violation): the dispatcher does NOT
import anything from `cli.py`. The CLI is a presentation layer;
the dispatcher is a domain primitive that depends on contracts.

Invariant 2 (RC2, public surface): the package's top-level imports
expose every documented public type without forcing callers to
reach into deep module paths.

Invariant 3 (RC4, dead code): no leaf vocabulary module is dead.
Every contract module is reachable from the package's public
surface or from another module's import list.
"""

from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PKG = ROOT / "research_institution"


def _imports_of(module_path: pathlib.Path) -> set[str]:
    """Return the set of internal `research_institution.*` module imports.

    Attribute-level imports (e.g. `from foo.bar import baz`) are
    returned alongside their parent module so tests can decide
    whether to inspect them. To get only the module-level set,
    use `_module_imports_of` instead.
    """
    src = module_path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.startswith("research_institution"):
                found.add(mod)
                for n in node.names:
                    found.add(f"{mod}.{n.name}")
        elif isinstance(node, ast.Import):
            for n in node.names:
                if n.name.startswith("research_institution"):
                    found.add(n.name)
    return found


def _module_imports_of(module_path: pathlib.Path) -> set[str]:
    """Return only the module-level `research_institution.*` imports."""
    return {
        x
        for x in _imports_of(module_path)
        if "." not in x.split("research_institution.", 1)[-1]
        or x.count(".") == x.replace("research_institution.", "").count(".") + 1
    }


def test_dispatcher_does_not_depend_on_cli() -> None:
    """Invariant 1: dispatcher is a domain primitive; cli is presentation.

    Originally `dispatcher.py` imported `cli.GateVerdict`, an RC1
    boundary violation. After the fix the dispatcher depends only on
    `contracts`, `catalog`, and standard library. Pinned by this
    test so a refactor cannot silently re-introduce the cycle.
    """
    imports = _imports_of(PKG / "dispatcher.py")
    cli_imports = {x for x in imports if x.startswith("research_institution.cli")}
    assert cli_imports == set(), (
        f"dispatcher depends on cli modules (RC1 boundary violation): {sorted(cli_imports)}"
    )


def test_contracts_vocabulary_has_no_internal_deps() -> None:
    """Invariant 3: vocabulary is a pure-data leaf module."""
    imports = _imports_of(PKG / "contracts" / "vocabulary.py")
    internal = {x for x in imports if x.startswith("research_institution")}
    assert internal == set(), (
        f"vocabulary.py should be a leaf module; found internal deps: {sorted(internal)}"
    )


def test_gate_verdict_depends_only_on_vocabulary() -> None:
    """Invariant 1+3: gate_verdict imports enums but not the package init.

    The contracts/__init__ re-exports gate_verdict; gate_verdict
    must NOT re-import the package init (would create a cycle).
    It depends only on the leaf vocabulary module.
    """
    imports = _imports_of(PKG / "contracts" / "gate_verdict.py")
    # The expected internal module imports: only vocabulary.
    # (Attribute imports like `vocabulary.Foo` are substrings of
    # the module path and will be filtered out below.)
    expected_modules = {"research_institution.contracts.vocabulary"}
    # An import X.Y.Z is the module X.Y.Z when Y.Z is the suffix;
    # we accept any import whose prefix is one of the expected modules.
    unexpected = {
        x
        for x in imports
        if x.startswith("research_institution")
        and not any(x == m or x.startswith(m + ".") for m in expected_modules)
    }
    assert unexpected == set(), (
        f"gate_verdict should depend ONLY on the vocabulary module; "
        f"got unexpected module imports: {sorted(unexpected)}"
    )


def test_package_public_surface_includes_dispatcher_types() -> None:
    """Invariant 2: the package facade exposes the documented types."""
    import research_institution

    required = {
        "DEFAULT_POLICY",
        "Dispatcher",
        "DispatcherVerb",
        "ExitCode",
        "GateVerdict",
        "GateVerdictStatus",
        "Program",
        "SubprocessPolicy",
        "SubprocessResult",
        "TaskKind",
        "gate_verdict_from_task_kind",
        "load_catalog",
    }
    actual = set(research_institution.__all__)
    missing = required - actual
    assert not missing, f"public surface missing: {sorted(missing)}"


def test_no_import_cycles_in_internal_graph() -> None:
    """Invariant 3: the internal import graph is a DAG.

    A correct Tarjan SCC pass: build the canonical module-to-modules
    import graph (only edges where BOTH endpoints are in the graph),
    then find strongly-connected components. Any SCC with size > 1
    is a cycle.
    """
    # Canonical set of node IDs.
    nodes: set[str] = set()
    for py in PKG.rglob("*.py"):
        if "__pycache__" in py.parts:
            continue
        rel = str(py.relative_to(ROOT))[:-3].replace("/", ".")
        nodes.add(rel)

    # Build the graph: only keep edges where BOTH endpoints are in nodes.
    graph: dict[str, set[str]] = {n: set() for n in nodes}
    for py in PKG.rglob("*.py"):
        if "__pycache__" in py.parts:
            continue
        rel = str(py.relative_to(ROOT))[:-3].replace("/", ".")
        for imp in _imports_of(py):
            # Trim to the longest prefix that's a known node.
            target = imp
            while target and target not in nodes:
                if "." not in target:
                    target = ""
                    break
                target = target.rsplit(".", 1)[0]
            if target and target != rel:
                graph[rel].add(target)

    # Iterative Tarjan (avoids recursion-limit issues).
    index_of: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    counter = [0]
    sccs: list[list[str]] = []

    for root in sorted(nodes):
        if root in index_of:
            continue
        # Work list: (node, iterator over successors).
        work: list[tuple[str, iter]] = [(root, iter(sorted(graph[root])))]
        index_of[root] = lowlink[root] = counter[0]
        counter[0] += 1
        stack.append(root)
        on_stack.add(root)
        while work:
            v, it = work[-1]
            try:
                w = next(it)
            except StopIteration:
                if lowlink[v] == index_of[v]:
                    # Pop SCC.
                    scc: list[str] = []
                    while True:
                        w2 = stack.pop()
                        on_stack.discard(w2)
                        scc.append(w2)
                        if w2 == v:
                            break
                    sccs.append(scc)
                work.pop()
                if work:
                    parent = work[-1][0]
                    lowlink[parent] = min(lowlink[parent], lowlink[v])
                continue
            if w not in index_of:
                index_of[w] = lowlink[w] = counter[0]
                counter[0] += 1
                stack.append(w)
                on_stack.add(w)
                work.append((w, iter(sorted(graph[w]))))
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], index_of[w])

    cycles = [scc for scc in sccs if len(scc) > 1]
    assert not cycles, f"import cycles detected: {cycles}"
