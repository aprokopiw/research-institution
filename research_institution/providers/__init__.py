"""research_institution.providers — OS-level mathlint.providers plugin.

Per @ADR-0007, this module fills mathlint's ``WorkSourceProvider``
slot from research-institution (the OS layer in the kernel/OS
mental model), not from kaplansky (a research program, i.e. the
artifact the OS produces). Mathlint's
``discover_program_providers`` discovers the
``mathlint.providers`` entry point registered in this repo's
``pyproject.toml`` and calls ``register()`` at mathlint-side
import time.

The plugin's contract is documented in
``docs/semantic/contracts/ctr-0094-work-source-provider-dispatch-envelope.md``.
"""

from __future__ import annotations
