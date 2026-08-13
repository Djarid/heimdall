# Nornir's rules

The deterministic rules Nornir runs over the ontology. No language model authors
or runs these (invariant 3.1). A change here is a change to the trust boundary
and is reviewed and tested as such (decision D07 lineage, and section 6 of
`ONTOLOGY_CONSTRUCTION.md`).

Four kinds:

- **classification** maps a marshalled assertion to its ontology type. No match
  means `UNCLASSIFIED_DATA_ASSERTION`, actionable false, routed to human review,
  never guessed.
- **derivation** forward-chaining inferences run after each assertion batch.
  Every derived fact is marked inferred and carries its assertion chain.
- **constraint** axioms stating what must not hold. A violation triggers
  Gjallarhorn.
- **flow-to-sink** propagates action-critical status backward from consequential
  sinks to every value that can reach them, agent-scoped (decisions D24, D30).
  Authored once over the shared structure, not per domain.

Authored (Phase 2): the runnable rules and the deterministic engine that applies
them live in the `nornir` package (`nornir/rules.py`, `nornir/engine.py`). The
flow-to-sink reachability reproduces the algorithm the substrate spike proved
(D43). This directory records the four rule kinds and the trust-boundary
discipline; the package holds the code. See `ontology/OUTCOME.md`.
