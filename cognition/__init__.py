"""The cognition plane's Python sidecar package (build-order step seven).

`.opencode/plans/build-order-step-seven-spec.md` REQ-14: a new, top-level package,
sitting under none of `ontology/`, `crates/`, `poc/` or `phase2/`. `crates/cognition-client/`
spawns `cognition.sidecar` as a module (`python3 -m cognition.sidecar`, REQ-15), never as a
path, so this package's own location and its own `PYTHONPATH` entry are the whole contract
between the two languages.

Why a new top-level package and not `ontology/tools/` (ST7-6, section 3.2 item three of the
spec). The decisive reason is structural immunity to a future tightening of
`ontology/nornir/symbolic_guard.py`'s scan roots. Today the guard's three scan roots are
`ontology/yggdrasil/`, `ontology/nornir/` and `poc/symbolic.py`, so a module under
`ontology/tools/` sits outside them and the guard stays green. But `ontology/` is a plausible
future scan-root widening, and if the model-calling module lived under `ontology/tools/` that
widening would immediately fail the guard on an `mlx_lm` import, creating pressure to add
`mlx_lm` to `ALLOWED_IMPORT_ROOTS` -- the single worst edit available anywhere in this
repository (invariant 3.1's own boundary, D71's allowlist inversion). A top-level `cognition/`
package cannot create that pressure, in this step or in any later one.

What this package does and does not do, on `poc/neural.py`'s own precedent for the identical
distinction: it authors a commit message under a fixed, grammar-constrained prompt. It
adjudicates nothing, imports nothing from the authorisation path
(`ontology/yggdrasil/`, `ontology/nornir/`, `poc/symbolic.py`), and is never imported by
`ontology/tests/harness.py` or any sub-harness (REQ-19). `ontology/nornir/symbolic_guard.py`
is not edited to accommodate it: it is simply outside every scan root, and because the guard's
boundary is `ALLOWED_IMPORT_ROOTS` (an allowlist, not a blacklist, D71), any authorisation-path
file that ever imported `cognition` would be a violation by construction, with no rule needing
to be added (REQ-20).

Two modules live here:

- `sidecar.py`: the module the sixth crate spawns with `-m`. Builds the trusted prompt
  (reusing `poc/neural.py`'s prompt discipline by import), generates one commit message under
  D90's existing grammar mask (`phase2/grammar_slot_extraction.py`'s `GrammarState`,
  parameterised for a single-field commit-message schema), and prints the fixed,
  line-oriented, non-JSON output form REQ-22 fixes. Fails loudly (non-zero exit) on any
  failure; it never prints a default or fallback value.
- `demo.py`: the standalone, operator-invoked demonstration (REQ-21), skip-if-absent on
  `phase2/grammar_slot_demo.py`'s precedent. Never run by `ontology/tests/harness.py`.
"""

from __future__ import annotations
