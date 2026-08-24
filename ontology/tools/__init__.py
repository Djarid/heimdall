"""Build-time tooling, deliberately separate from `ontology/tests/`.

Nothing here is a pass/fail obligation of `ontology/tests/harness.py`'s `main()`
registry: this package holds generators an operator runs by hand (or a harness
invokes as a subprocess/import), never a suite `main()` folds into `fatal` itself.

Deliberately outside `ontology/nornir/symbolic_guard.py`'s scan roots
(`ontology/yggdrasil/`, `ontology/nornir/`, `poc/symbolic.py`): nothing under
`ontology/tools/` runs on the authorisation path, so adding this package does not
change the invariant 3.1 guard's scanned-file count (34, unchanged).
"""

from __future__ import annotations
