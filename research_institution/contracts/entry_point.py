"""Validator for the catalog's `entry_point` field.

Each catalog entry declares `entry_point = "<python.module>:<callable>"`,
e.g. `"kaplansky.mathlint_plugin:register"`. This module validates
that:

  - The string parses as `<module>:<callable>` with both parts non-empty.
  - The `<module>` is importable from the Python path.
  - The `<callable>` exists in `<module>`.

The validator is **diagnostic-only**: it never imports the module
itself unless the operator asks (`import_module=True`). For the
dispatcher's hot path (`start`, `stop`, etc.) we only need the
parse-and-string-shape check; the import happens at `mathlint
system-readiness` time (green gate).

This module is pure (no I/O, no subprocess). Tests inject mock
modules via `sys.modules` to simulate importable programs.

Wire format (catalog `entry_point` field):
  - "<dotted.module.path>:<callable_name>"
  - `<callable_name>` is the suffix after the last `:`.
  - Both sides are required; no whitespace tolerated.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EntryPointSpec:
    """Parsed catalog `entry_point` field.

    `module_path` is the dotted Python module path (e.g.
    `kaplansky.mathlint_plugin`).
    `callable_name` is the symbol to call within the module (e.g.
    `register`).
    """

    module_path: str
    callable_name: str

    @property
    def module_callable(self) -> str:
        """The original `"module:callable"` string (for diagnostics)."""
        return f"{self.module_path}:{self.callable_name}"


def parse_entry_point(entry_point: str) -> EntryPointSpec:
    """Parse a catalog `entry_point` string into its component parts.

    Raises `ValueError` on malformed input (no `:`, empty module,
    empty callable, non-string).

    The non-string guard is intentional: callers may bridge
    untyped dynamic data (TOML ``dict[str, object]`` values
    from the catalog loader) and pass non-strings without a
    pyright-visible type error. The guard rejects them loudly
    with a precise diagnostic. Tests in
    ``tests/test_entry_point_contract.py`` pin the contract.
    """
    if not isinstance(entry_point, str):
        raise ValueError(
            f"entry_point must be a string; got {type(entry_point).__name__}"
        )
    if ":" not in entry_point:
        raise ValueError(
            f"entry_point {entry_point!r} must contain ':' separating module from callable"
        )
    module_path, _, callable_name = entry_point.rpartition(":")
    # Whitespace checks BEFORE empty checks: a malformed `"x:  "` is
    # more usefully diagnosed as "callable has whitespace" than as
    # "callable is empty". The order also matches the predicate that
    # would catch a paste error (trailing space) first.
    if module_path != module_path.strip() or " " in module_path:
        raise ValueError(f"entry_point module path {module_path!r} contains whitespace")
    if " " in callable_name:
        raise ValueError(f"entry_point callable {callable_name!r} contains whitespace")
    if not module_path:
        raise ValueError(f"entry_point {entry_point!r} has empty module path")
    if not callable_name:
        raise ValueError(f"entry_point {entry_point!r} has empty callable name")
    return EntryPointSpec(module_path=module_path, callable_name=callable_name)


def validate_entry_point(
    spec: EntryPointSpec, *, import_module: bool = False
) -> tuple[bool, str | None]:
    """Check that `spec.module_path` is importable + `spec.callable_name` exists.

    Returns `(ok, reason)` where `ok=True` iff the entry point is well-formed
    and (optionally) importable. `reason` is the diagnostic when `ok=False`.

    With `import_module=False` (default): only checks the string shape.
    Already covered by `parse_entry_point`; this branch is for symmetry.

    With `import_module=True`: actually imports the module and looks up
    the callable. Used by the green gate's `system-readiness` step; not
    on the dispatcher's hot path.
    """
    if not import_module:
        return (True, None)
    try:
        module = importlib.import_module(spec.module_path)
    except ImportError as exc:
        return (False, f"import {spec.module_path!r} failed: {exc}")
    if not hasattr(module, spec.callable_name):
        return (False, f"module {spec.module_path!r} has no attribute {spec.callable_name!r}")
    return (True, None)


__all__ = [
    "EntryPointSpec",
    "parse_entry_point",
    "validate_entry_point",
]
