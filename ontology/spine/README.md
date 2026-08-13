# The shared spine (Heimdall-authored)

The parts of the shared spine that Heimdall authors, sitting on the BFO upper
layer (`../upper/bfo`). Shared across all domains and all media. Not per-agent:
the per-agent binding lives in Himinbjörg's control surface (decision D20).

- `action/` the action **vocabulary**: the set of action types that can exist.
  Which agent may perform which action is not here; that is control-surface
  state. Phase 1 vocabulary is small and read-only or human-gated (classify,
  triage, summarise, draft-for-review).
- `constraint/` the constraint **vocabulary**: the axioms that can be expressed
  (what must not hold). A violation triggers Gjallarhorn.
- `trust/` the trust lattice: TAINTED, VOUCHED, TRUSTED, CANONICAL, and the
  promotion relations between them.

Authored (Phase 2). The runnable form lives in the `yggdrasil` package:
`yggdrasil/spine/trust.py`, `yggdrasil/spine/action.py`,
`yggdrasil/spine/constraint.py`. These directories hold the layer's intent and
map; the package holds the loaded nodes and relations, authored as a property
graph per D25. See `ontology/OUTCOME.md`.
