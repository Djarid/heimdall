# Detailed Design: Mímisbrunnr (world model)

**Author:** Jason Huxley
**Date:** August 2026
**Version:** 0.1 (draft)
**Phase:** 2
**Status of the component today:** demonstrated (the flow-to-sink algorithm proven in `spike/substrate/reachability.py` with a live Memgraph binding, per `plans/hld.md` section 3); the production world-model service is unbuilt.

---

## 1. Purpose

Mímisbrunnr is the persistent typed graph that holds the authoritative state of everything Heimdall knows. A normal agent never sees a raw content window: Himinbjörg builds its context from a subgraph of Mímisbrunnr (HLD section 5.1). Everything an agent reasons from, and everything an action is authorised against, comes from this store.

Two properties make Mímisbrunnr load-bearing rather than an ordinary graph database. Every node carries a taint level and a provenance chain, so trust is a structural property of the state itself. And every node carries a maintained flow-to-sink label that says whether the value can reach a declared consequential sink by any path, so Gjöll can gate a staging write, not only the final action (HLD section 5.2).

This document takes Mímisbrunnr to implementation fidelity for Phase 2: the node model, the edge and causal-graph model, how the flow-to-sink label is maintained incrementally at write time, and the write-interface enforcement that makes an unprovenanced node impossible. It builds directly on the substrate spike (`spike/substrate/reachability.py`), which proved the one algorithm the store must support before the store itself was chosen.

## 2. Responsibilities and boundaries

In scope for Mímisbrunnr:

- Persist typed nodes, each carrying a type, a taint level, a provenance chain, timestamps, a confidence, an actionable flag and an inferred flag.
- Enforce the mandatory-provenance contract at the write interface: no node exists without a provenance chain (`index.md` section 4.3).
- Hold the causal graph: an agent performed an action, the action produced a state change, with recorded pre- and post-conditions.
- Maintain the backward-propagated flow-to-sink action-critical label incrementally at write time, including sound retraction on edge deletion, so Gjöll's authorisation-time read is constant-time (HLD section 6).
- Serve typed subgraphs to Himinbjörg for context construction, and the flow-to-sink label to Gjöll.
- Support causal unwind (rollback), counterfactual queries and pre-execution blast-radius analysis over the causal graph.

Out of scope for Mímisbrunnr:

- Classification. Nodes arrive already typed and provenanced from Nornir (document 4). Mímisbrunnr does not decide what an assertion is.
- Trust decisions and promotion. Mímisbrunnr stores a taint level; it never raises one. Promotion is a human or cryptographic act mediated by Himinbjörg and Gjöll.
- The action decision. Mímisbrunnr answers whether a value can reach a sink; whether the action is authorised is Himinbjörg's, and whether the value is safe to act on now is Gjöll's.
- Declaring which sinks are consequential. That is the ontology's (Yggdrasil, HLD section 5.12); Mímisbrunnr consumes the declaration as its target set.

Mímisbrunnr mostly does not touch the harness. It is read by Himinbjörg during context construction, and the OpenCode/Gleipnir binding of that read path (the provider-request interception group of the HBI) is specified in the Himinbjörg document (document 7, `index.md` section 3). Mímisbrunnr itself is a service the gateway calls, not a harness hook.

## 3. The data and label contracts

### 3.1 The node model

Every node carries the property set from `HEIMDALL.md` (the world-model node-properties block) and HLD section 6:

- `id`: a uuid.
- `type`: an ontology type, from Yggdrasil. The type is a label on the node, per D46 (the ontology is authored as a property-graph-native package, so a type is a node and a subtype or BFO anchor a relation).
- `taint`: one of TAINTED, VOUCHED, TRUSTED, CANONICAL (the cross-cutting taint contract, `index.md` section 4.1 and HLD section 7.2). Content arriving via Bifröst and Nornir is TAINTED.
- `provenance`: a source chain, never absent (section 5, and `index.md` section 4.3).
- `created_at` and `updated_at`: timestamps.
- `confidence`: a float.
- `actionable`: a boolean. An `UNCLASSIFIED_DATA_ASSERTION` from Nornir enters with `actionable` false and is review-queued, never trusted (HLD section 5.4).
- `inferred`: a boolean. A fact derived by Nornir's forward-chaining reasoner carries `inferred` true and its assertion chain (HLD section 5.4).

The taint level and the provenance chain are on every node without exception. There is no schema path to a node that lacks either. This is the persistent form of the typed assertion (`index.md` section 4.1): the assertion is the unit that flows in from Nornir, and the node is its stored shape.

### 3.2 The edge model and the causal graph

Ordinary edges carry typed relations between nodes. Action edges form the causal graph, in the shape `HEIMDALL.md` fixes:

```
(agent) --[performed]--> (action) --[produced]--> (state_change)
(action) --[precondition]--> (world_state_before)
(action) --[postcondition]--> (world_state_after)
```

Every action taken by any agent writes such an edge. This structure is what supports three operations Himinbjörg and Hliðskjálf depend on: causal unwind (rollback of a state change by following the causal edges), counterfactual queries (if a given action had not run, is some later state still reachable) and pre-execution blast-radius analysis (which state a proposed action would touch, computed before it runs).

The causal graph and the flow-to-sink dependency graph are related but not identical. The flow-to-sink graph (section 3.4) is over value-flow edges: an edge u to v means the value at u can flow into the value at v. The causal graph is over action edges. A value-flow edge is often produced as a side effect of an action write, so the two are maintained together, but the reachability label is computed over value-flow edges only, matching the substrate spike's model (`reachability.py` module docstring: a node is a value, an edge means the value at the tail can flow into the value at the head).

### 3.3 Taint levels and provenance

The four taint levels are the shared contract (`index.md` section 4.1, HLD section 7.2), not redefined here. Mímisbrunnr stores the level; it is set upstream and Mímisbrunnr never raises it. The provenance chain records where a value came from and through what transformations. A value extracted by Fenrir from an email body carries the `EXTERNAL_COMMS` origin, the Fenrir invocation and the classification step (HLD section 6). Provenance answers where a value came from; it does not make the value safe to act on, which is why the flow-to-sink label and Gjöll exist alongside it (HLD section 5.2).

### 3.4 The flow-to-sink action-critical label

This is the property that lets Gjöll gate multi-step state staging. The rule, from `HEIMDALL.md` and HLD section 5.2: a value is action-critical if it can reach a declared consequential sink by any path, however many reversible hops intervene. The earlier per-step rule (a value is action-critical only if it directly parameterises a consequential action) is bypassable by chaining individually-reversible writes so that a later authorised action reads the staged state; the transitive rule closes that, because the value inherits action-critical status the instant a path to a sink exists.

The label is maintained by the algorithm proven in `spike/substrate/reachability.py`. The design binds that algorithm to the production store rather than reinventing it. Its properties, taken from the spike and its `OUTCOME.md`:

**Sinks are agent-scoped.** Which nodes are consequential sinks depends on a given agent's permitted action space (D24, D30). The target set is a parameter rather than a graph-global constant. In `reachability.py` this is one `ReachabilityGraph` instance per agent view; in the production store the equivalent is evaluating reachability against the agent's declared sink set at label-maintenance time. Sinks come from the ontology's declaration of which sinks are consequential (HLD section 5.12).

**Support counting is the mechanism.** Each node carries a support count: the number of its out-edges whose head is action-critical. A node is action-critical if and only if it is a sink or its support is positive (`reachability.py` lines 96 to 101, and the `_become_ac` propagation). Multiplicity is tracked so parallel edges count exactly, matching a property graph that permits them (`reachability.py` lines 90 to 94).

**Adds are bounded and monotonic.** Adding an edge u to v where v is action-critical gives u one unit of support; if u was not critical and now is, the gain propagates backward to u's predecessors, and only nodes that transition from not-critical to critical do any work (`add_edge` and `_become_ac`, lines 133 to 170). If v is not action-critical the add is constant-time. The spike measured each add on a 5000-node chain touching exactly one node, and an add with an inert head touching nothing (`OUTCOME.md` section 3.1).

**The authorisation-time read is constant-time.** `is_action_critical` is a set-membership read, not a traversal (`reachability.py` lines 126 to 129). In the property-graph binding this is reading a boolean node property. At 50,000 nodes the spike measured about 0.18 microseconds per read (`OUTCOME.md` section 3.2). This is the whole point of maintaining the label at write time: the cost moves off the authorisation path, which is where latency is least affordable (HLD section 5.2, and the `HEIMDALL.md` latency note, which frames incremental maintenance as available if the write-path cost proves to matter and is to be measured in Phase 2).

### 3.5 Edge deletion and retraction (the hard case)

Deletion is the case the substrate decision turned on, because it is non-monotonic: removing an edge can strip reachability from a value and everything that reached a sink only through it, but must leave every node with a surviving path untouched. The invariant that must never break is that a label is never retracted while it should stay (`reachability.py` lines 29 to 34). Over-retention (keeping a label that could be dropped) is a sound conservative over-approximation and is allowed. Over-retraction (dropping a label a value should keep) is a critical fault: an action-critical value would silently become inert and skip Gjöll.

The spike implements two deletion modes and the design carries both forward:

- **Conservative mode.** On deleting an edge to a critical head, the source loses one unit of support. If it keeps positive support, it might still be grounded and the mode does not pay to check: a constant-time early return (`reachability.py` lines 216 to 224). This over-approximates only when the residual support is a stale cycle whose one real exit was the deleted edge, and the over-approximation is always sound. The spike measured this on roughly 3 to 6 percent of operations, always sound, never unsound (`OUTCOME.md` section 4).
- **Exact mode.** Positive residual support is treated as insufficient proof, because it can come from a cycle that depended on the deleted edge. On any delete of an edge to a critical head the mode runs a grounded delete-rederive over the affected region, re-establishing only nodes with a path that leaves the region to a real sink (`reachability.py` lines 225 to 231, and `_delete_rederive`, lines 233 to 297). It matched the brute-force oracle exactly on every fuzzed operation.

The delete-rederive is localised: it computes a shaken set (the seed and every currently-critical ancestor that could depend on the lost path), provisionally clears their labels, then re-establishes only those with a surviving out-edge to a confirmed-critical node outside the set, propagating re-establishment strictly backward so the derivation is grounded in the sink set and cannot bootstrap a cycle (`reachability.py` lines 233 to 297). Support is recomputed for the shaken set against the final label state, so the incremental invariant holds for the next operation (lines 288 to 297).

**Default: conservative mode.** The spike's engineering conclusion (`OUTCOME.md` section 4) is to use conservative mode by default. Its over-approximation is exactly the sound behaviour the criteria permit, its only effect is that a value may read action-critical slightly longer than strictly necessary (which fails safe), and it is roughly 15 to 20 times cheaper per delete because most deletes leave positive support and hit the early return. Exact mode is retained for cases where a precise label is worth its cost, for example an offline audit or a query that must report the true minimal action-critical set, and is not the hot path. There is one caveat to carry forward: a dense strongly-connected reachability graph degrades either mode toward full-graph work on a delete, because the shaken region approaches the whole graph. A flow-to-sink graph is not that shape (values flow forward through processing stages toward a small set of sinks, sparse and largely acyclic), so this is a monitoring obligation rather than a present defect (`OUTCOME.md` section 5). If a future domain's flow graph develops large dense cycles, deletion cost rises and that is the signal to revisit the topology or the mode.

### 3.6 Key interfaces (signature level)

The four interfaces from HLD section 5.7, at signature level:

```
assert(typed_assertion: TypedAssertion) -> NodeId
subgraph(scope: Scope) -> Subgraph
causal_unwind(action_id: ActionId) -> None
reachable_to_sink(node: NodeId, agent: AgentId) -> bool
```

- `assert` writes a node with its taint and provenance and updates the flow-to-sink label incrementally through the add path in section 3.4. It is the sole write interface and the enforcement point for mandatory provenance (section 5). A write whose value-flow edges reach an agent's sink set marks the source action-critical at that write, in bounded work.
- `subgraph` returns a typed relevant subgraph for Himinbjörg context construction. It never returns a raw content window, because no such thing is stored: Mímisbrunnr holds typed nodes only, and the absence of a content window is a property of what is stored, not a filter applied on read.
- `causal_unwind` rolls back a state change by following the causal graph, anchored by Hliðskjálf entries (HLD section 5.8). It is a structural operation over the action edges of section 3.2.
- `reachable_to_sink` reads the maintained label for a node against a given agent's sink set. This is the interface Gjöll's `is_action_critical` calls (HLD section 5.2). It is constant-time (section 3.4), which is the reason the label is maintained at write time rather than computed on read.

The `agent` parameter on `reachable_to_sink` is explicit because sinks are agent-scoped (section 3.4, D24). A value may be action-critical for one agent's sink set and inert for another's; the label is not graph-global.

## 4. Store binding

The store choice is Open Question 1 in `HEIMDALL.md` (reasoner or store choice: OWL/RDF against a property graph against Datalog). The substrate spike ratified a property graph, Memgraph (D25), and the DD follows that ratification. The deciding criterion was the flow-to-sink label: action-critical status must be available at authorisation time without an expensive query, which a property graph serves as a boolean node-property read, whereas an RDF triple store answering SPARQL property-path queries pays the reachability cost on the hot path at authorisation, which is exactly where latency is least affordable (`ONTOLOGY_CONSTRUCTION.md` section 3, `OUTCOME.md` section 6).

The binding is mechanical, because the spike isolated the algorithm from the store deliberately: an edge-insert trigger runs the add path, an edge-delete trigger runs the delete path, and the authorisation-time read is a boolean node-property lookup (`OUTCOME.md` section 2 and 6). The live Memgraph binding exists in the spike (`memgraph_store.py`, `memgraph_harness.py`) and reproduces the conservative-mode semantics (D57). The production binding hardens that into the world-model service; it does not redesign the algorithm, whose label semantics are the artefact to preserve, per `OUTCOME.md` section 7 (the spike Python is disposable, the semantics are not).

## 5. Fail-closed behaviour

- **No node without provenance.** The `assert` interface rejects any assertion lacking a provenance chain. This is the enforcement point named in `index.md` section 4.3: an unprovenanced assertion is structurally untrusted and cannot be stored as a trusted node. Enforcement is at the write interface, in code rather than by convention. There is no code path that writes a node with an empty or absent `provenance` field.
- **Unprovenanced equals structurally untrusted.** A write that arrives without provenance is not stored as a low-confidence node or a TAINTED node; it is refused at the interface. The store has no representation for a trusted node without a source chain (section 3.1), so the failure is structural rather than a runtime check that could be skipped.
- **The label fails safe under uncertainty.** The default deletion mode over-approximates rather than under-approximates (section 3.5): a value may read action-critical for longer than strictly necessary, never for shorter. A value that should be gated by Gjöll is never silently dropped from the action-critical set, because over-retraction is the one fault the algorithm is built to exclude and the spike checks against a brute-force oracle after every operation.
- **No content window exists to leak.** Mímisbrunnr stores typed nodes only; there is no raw content field on a node, so `subgraph` cannot return one. A path by which tainted content reaches an agent context through Mímisbrunnr would require storing raw content, which the node model does not permit. This upholds the canonical-control-channel contract (`index.md` section 4.4): Mímisbrunnr holds data, and data never becomes an instruction by being read from the store.

## 6. Data owned

- All world state: the typed nodes and their ordinary typed-relation edges.
- The causal graph: the action edges of section 3.2.
- The flow-to-sink action-critical labels and their support counts, maintained per agent sink set.
- No trust decisions and no sink declarations. Taint levels are set upstream; sink declarations are owned by Yggdrasil and consumed as the target set.

Mímisbrunnr is the authoritative state store. It owns the state; it does not own what the state means (the ontology, Yggdrasil) or what may be done with it (the control surface, Himinbjörg).

## 7. Dependencies

- Upstream: Nornir (classified, provenanced assertions arrive via `assert`), and Fenrir via Nornir (Fenrir's extracted assertions are classified by Nornir before they land, so Fenrir never writes to Mímisbrunnr directly).
- Downstream: Himinbjörg (reads typed subgraphs for context construction), Gjöll (reads the flow-to-sink label at action time), Hliðskjálf (anchors causal-unwind and forensic reconstruction to signed log entries).
- Lateral: Yggdrasil (supplies the ontology types that label nodes, D46, and the sink declarations that define the target set).

## 8. Build delta from today

- The flow-to-sink algorithm is proven. `spike/substrate/reachability.py` (322 lines) implements support-counted incremental maintenance with sound conservative and exact retraction, and the harness runs it under differential fuzzing against a brute-force oracle (D25, D32, D38 ratified).
- A live store binding is proven. `memgraph_store.py` binds the algorithm to a live Memgraph store and `memgraph_harness.py` matched it against the in-memory reference across 1800 fuzzed operations with zero unsound operations (D57). The binding is optional and skips cleanly when Memgraph is not reachable, so the core suite stays dependency-free.
- The production world-model service is unbuilt. What exists is a spike plus an optional skip-if-absent verification harness, rather than a running service that real ingestion writes to (HLD section 3).
- The persistent typed-node schema for real ingestion is unbuilt. The node property set is specified (`HEIMDALL.md`, HLD section 6, section 3.1 here) but not implemented as a persisted schema with the write-interface provenance enforcement of section 5.
- The causal graph is unbuilt. The shape is specified (section 3.2) but no action write produces causal edges yet, and causal unwind has no implementation.
- Cross-batch maintenance is not the default today. In the spike the store binding maintains state across operations, but in the wider baseline per-batch is the default and cross-batch state persists only under `persist=True` (HLD section 3). A per-batch path cannot see a value staged in an earlier batch, which is exactly the multi-step state-staging case the flow-to-sink rule must catch, so cross-batch maintenance must become the default in the production service.
- The store choice (Open Question 1) is ratified by the spike toward a property graph, Memgraph, for the flow-to-sink workload (section 4). This is a firm ratification grounded in a falsifiable spike, not an assumption.

## 9. Test plan

Inherits the substrate spike's reachability suite (`spike/substrate/`, run via the harness), which is the proven baseline:

- The differential-fuzzing soundness suite: 20,000 operations over five seeds (4000 operations each), comparing the incremental label to a brute-force backward-BFS oracle after every single operation, in both deletion modes, with zero unsound operations (`harness.py` criterion 3, `OUTCOME.md` section 3.3). This is the load-bearing inherited test: over-retraction is the fault it exists to catch.
- The live Memgraph binding differential test: the same random add and delete sequences driven through both the in-memory reference and the Memgraph binding, matching after every operation across 1800 fuzzed operations with zero unsound operations (`memgraph_harness.py`, D57).
- Write-time bound, constant-time read and scale criteria at 50,000 nodes and 150,000 edges (`harness.py` criteria 1, 2 and 4).
- The mandatory adversarial cross-domain state-staging case (`harness.py` criterion_4_cross_domain_staging, `ONTOLOGY_CONSTRUCTION.md` section 8.4, D30): a value staged across the communications, scheduling and infrastructure domains reads inert until the composing write completes, becomes action-critical the instant a path to the sink exists, retracts when that path breaks and does not over-retract a survivor when one of two paths is deleted (tested in both modes).

Adds, before implementation:

- **Provenance-mandatory write tests.** For a corpus of assertions with and without a provenance chain, assert that `assert` stores the provenanced ones and refuses the unprovenanced ones at the interface, with no unprovenanced node persisted in any form. This tests the section 5 fail-closed contract by its failure mode: plant an unprovenanced write and assert a refusal, not merely a low-confidence store.
- **Node-model schema tests.** Assert every persisted node carries all nine properties of section 3.1, that `taint` is one of the four levels and never raised by a Mímisbrunnr operation, and that an `UNCLASSIFIED_DATA_ASSERTION` lands with `actionable` false.
- **Causal-unwind tests.** Build a causal graph of several actions with recorded pre- and post-conditions, unwind a chosen action, and assert the state returns to its pre-condition and that later state depending on the unwound action is correctly reachable or not per the counterfactual. Assert the unwind follows only causal edges and does not touch unrelated state (blast radius).
- **Cross-batch state-staging tests.** Stage a value in one batch and complete the composing write to a sink in a later batch, and assert the value reads action-critical after the later batch. This is the test a per-batch maintenance path would miss: run it against the per-batch default and assert it fails (demonstrating the gap), then against cross-batch maintenance and assert it passes. This makes the build delta of section 8 (cross-batch must be the default) a tested requirement rather than a note.
- **Subgraph no-content-window test.** Assert `subgraph` returns typed nodes only and that no node exposes a raw content field, so there is no path by which context construction reintroduces a content window (section 5, `index.md` section 4.4).

Coverage is reported line and branch. Per `index.md` section 5, a green count over low branch coverage on the fail-closed paths (the provenance refusal, the retraction paths) is not evidence, because those failure paths are the point; they are covered explicitly.

## 10. Decisions (index)

| # | Decision | Chosen | Rejected | Rationale |
|---|---|---|---|---|
| MM-1 | Store binding | Property graph, Memgraph, per the substrate spike (D25) | RDF triple store with SPARQL property-path queries; Datalog engine (Souffle) | The flow-to-sink label must be readable at authorisation time without a traversal. A property graph serves it as a boolean node-property read; a triple store pays the reachability cost on the hot path. Ratified by the spike rather than assumed. Open Question 1. |
| MM-2 | Default deletion mode | Conservative (support-counted, constant-time early return) | Exact (grounded rederive on every forward-edge delete) as the default | Conservative is sound, its over-approximation fails safe, and it is roughly 15 to 20 times cheaper per delete. Exact is retained for offline audit and true-minimal-set queries, not the hot path (`OUTCOME.md` section 4). |
| MM-3 | Reachability graph versus causal graph | Two related edge sets: value-flow edges carry the label, action edges form the causal graph | One merged edge set | The label is computed over value-flow only (the spike's model). The causal graph serves unwind and blast-radius. Keeping them distinct keeps the label computation exactly the proven algorithm. |
| MM-4 | Cross-batch maintenance | The default in the production service | Per-batch default (the current baseline) with cross-batch only under `persist=True` | A per-batch path cannot see a value staged in an earlier batch, which is the multi-step state-staging case the flow-to-sink rule exists to catch. Cross-batch maintenance is required for the guarantee to hold across ingestion batches (HLD section 3). |
| MM-5 | Provenance enforcement point | At the `assert` write interface, in code | By convention, or a downstream check | An unprovenanced node must be impossible, not merely discouraged. The store has no representation for a trusted node without a source chain, so the refusal is structural (`index.md` section 4.3). |

---

## Licence

Part of the Heimdall specification, licensed under CC-BY-SA-4.0. See `LICENSE.md`.
