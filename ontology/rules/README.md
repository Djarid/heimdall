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

Nascent: stub. Authoring and the substrate that runs the rules are Phase 2/3
(D25 substrate spike; section 9 phase mapping).
