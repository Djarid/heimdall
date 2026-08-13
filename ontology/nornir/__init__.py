"""Nornir: the deterministic classifier and reasoner over Yggdrasil.

No language model authors or runs anything here (invariant 3.1, D02). Nornir is
plain deterministic Python: it takes marshalled assertions (the seam with Fenrir's
output, D28), classifies each against the loaded ontology's types, forward-chains
derivations, checks constraint axioms and propagates action-critical status by
flow-to-sink reachability. A change to a rule here is a change to the trust boundary
and is reviewed as such (`ONTOLOGY_CONSTRUCTION.md` section 6).

This is the minimal, substrate-neutral Nornir of Phase 2: it runs over an in-memory
graph, not Memgraph. The flow-to-sink reachability is the algorithm the substrate
spike proved (D43, D44, `spike/substrate/`), reproduced here as the live reference
the eventual Memgraph binding must match. Nothing here depends on Memgraph.

Modules:

- `assertions` the marshalled-assertion model (the input) and the classified
               result (the output).
- `rules`      the four rule kinds: classification, derivation, constraint,
               flow-to-sink, authored as deterministic data-plus-checks.
- `engine`     the runner that applies the rules to a batch of assertions against a
               loaded ontology and an agent context.
"""

from __future__ import annotations

from .engine import Nornir
from .assertions import MarshalledAssertion, ClassifiedAssertion

__all__ = ["Nornir", "MarshalledAssertion", "ClassifiedAssertion"]
