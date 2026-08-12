# Substrate Spike: Outcome (D25 / D38)

**Author:** Jason Huxley
**Version:** 1.0
**Date:** August 2026
**Status:** result of the Phase 2 substrate ratification spike; throwaway code, kept as evidence
**Reads with:** `ONTOLOGY_CONSTRUCTION.md` section 3, `DECISIONS.md` (D25, D32, D38), `NEUROSYMBOLIC_FILTER_INVARIANTS.md` invariant 3.11

---

## 1. Result

The spike **ratifies D25** (a property graph, Memgraph, as store and reasoning substrate) and, with it, **D38** (BFO as the loaded spine). The load-bearing question, edge-deletion label retraction in the flow-to-sink reachability graph (D32), is answered: it is soundly solvable at write time without an authorisation-time traversal, and it does not require falling back to a Datalog engine.

All four pass criteria from `ONTOLOGY_CONSTRUCTION.md` section 3.3, plus the mandatory adversarial cross-domain state-staging case from section 8.4, hold. The harness runs 23 checks and every one passes.

The spike is substrate-neutral by construction. It tests the one algorithm any chosen store must support, not Memgraph's Cypher surface. If the algorithm is sound and cheap here (it is), binding it to a property graph is mechanical: an edge-insert trigger, an edge-delete trigger and a boolean node property read. If it had been unsound or expensive here, no store choice would have rescued it, and this document would recommend Souffle for the reasoning layer per 3.3. It does not.

---

## 2. What was built

Two files under `spike/substrate/`, run in the existing `poc/.venv` with no third-party dependency:

- `reachability.py`: the flow-to-sink reachability graph with an incremental `action_critical` label. A node is a value in Mimisbrunnr; a directed edge means the value at the tail can flow into the value at the head; a sink is an agent-scoped consequential sink (D24). A node is action-critical iff a directed path reaches any sink in the agent's target set. The label is maintained on every edge add and delete.
- `harness.py`: the audit artefact, in the spirit of `poc/harness.py` (D12). Failures are loud, and a brute-force backward-BFS oracle is the control that makes a pass mean something. The core soundness check is differential fuzzing: drive a long random add and delete sequence, and after every single operation compare the incremental label to the oracle.

To reproduce: `poc/.venv/bin/python harness.py` from `spike/substrate/`.

---

## 3. The four criteria

### 3.1 Criterion 1: write-time label maintenance, bounded

Adding an edge that creates a path to a sink marks the source action-critical at write time, in work bounded by the set of nodes that newly become critical, never a full-graph traversal. On a 5000-node chain each add touched exactly one node. An add whose head is not action-critical touches nothing (O(1)). PASS.

### 3.2 Criterion 2: authorisation-time read is a property read

Asking whether a value is action-critical at action time is a set-membership read, not a graph query. At 50,000 nodes the read cost measured at about 0.18 microseconds per read. In a property graph this is reading a boolean node property. PASS.

### 3.3 Criterion 3: edge-deletion retraction, sound (D32)

This is the hard case, and the one the whole substrate decision turned on. Deletion is non-monotonic: removing an edge can strip reachability from the source and everything that reached a sink only through it, but must leave every node with a surviving path untouched. The invariant that must never break is that we never retract a label that should stay. Over-retention (keeping a label that could be dropped) is a sound conservative over-approximation, which 3.3 explicitly permits. Over-retraction (dropping a label a value should keep) would let an action-critical value silently become inert and skip Gjoll, which is a critical fault.

Across 20,000 fuzzed operations over five seeds, soundness held on every operation in both deletion modes (see section 4). Zero unsound operations. PASS.

### 3.4 Criterion 4: scale, and the mandatory cross-domain staging case

At 50,000 nodes and 150,000 edges the algorithm holds soundness and, in exact mode, exactness against the oracle. The mandatory adversarial case from 8.4 and D30 is a chain of individually-reversible, individually-non-consequential writes that composes into a consequential action across a domain boundary: a value marshalled in the communications domain staged through scheduling into an infrastructure execution sink. The value is inert until the composing write completes, becomes action-critical the instant a path to the sink exists, and retracts when that path is broken. Deleting one of two paths to a sink does not over-retract the survivor, tested in both modes. PASS.

---

## 4. The finding: two deletion modes, and the price of exactness

The spike was asked to implement both a conservative and an exact deletion strategy and compare them (the framing 3.3 uses). It did, and the comparison is the substantive result.

The algorithm maintains, per node, a support count: the number of its out-edges whose head is action-critical. A node is action-critical iff it is a sink or its support is positive. Adds are monotonic and cycles cause no trouble on insertion. Deletion is where the two modes diverge.

- **Conservative mode** keeps an O(1) early-return: if the source retains positive support after losing the deleted edge, it might still be grounded and we do not pay to check. This is sound, but it over-approximates when the residual support is a stale cycle whose only real exit was the deleted edge. In the fuzzer this over-approximation appeared on roughly 3 to 6 percent of operations, varying by seed, and was always sound, never unsound.
- **Exact mode** treats positive residual support as insufficient proof, because it can come from a cycle that depended on the deleted edge. On any delete of an edge to a critical head it runs a grounded rederive over the affected region, re-establishing only nodes with a path that leaves the region to a real sink. It matched the oracle exactly on all 20,000 operations.

The cost difference is large and is the reason the modes matter. Grounded rederive on a realistic layered flow graph re-derives the whole upstream cone of the deleted edge. At 50,000 nodes and 150,000 edges:

| Mode | Cost per delete | Nodes touched per delete |
|------|-----------------|--------------------------|
| Conservative | about 3 ms (worst case) | mostly zero, worst case about 47,000 |
| Exact | about 56 ms | about 28,000 average |

Conservative is roughly 15 to 20 times cheaper per delete and does no work at all on the common delete, because most deletes leave positive support and hit the early-return. Exact pays a near-full-graph rederive on almost every forward-edge deletion.

The engineering conclusion for the live build: **use conservative mode by default.** The over-approximation it produces is exactly the sound conservative behaviour 3.3 allows, and its only effect is that a value may briefly read action-critical slightly longer than strictly necessary, which fails safe. Exact mode exists and works, and is available where a precise label is worth its cost (for example an offline audit, or a query that must report the true minimal action-critical set), but it is not the hot path.

---

## 5. The honest caveat: dense cyclic reachability

There is a degenerate case, and it is reported rather than hidden because it bears on the substrate. A dense random graph sits above the giant-strongly-connected-component threshold, so almost every node lies in one large cycle and reaches a sink through it. In that shape a single edge deletion's affected region is close to the whole graph, and localised rederive degrades toward full-graph work in either mode. The spike measured this directly: on a 5000-node dense graph with 94 percent of nodes in one component, a single delete touched up to 4668 nodes.

This is a real property of incremental reachability maintenance, not a defect in the algorithm, and it is sound throughout (it never drops a label wrongly). It matters for D25 only if a realistic Mimisbrunnr looks like one dense strongly-connected component. It does not. A flow-to-sink graph is values flowing forward through processing stages toward a small set of sinks: sparse, largely a directed acyclic graph, with occasional back-edges. The scale test models that shape, and there both modes stay well-behaved. The caveat to carry forward is a monitoring one: if a future domain's flow graph develops large dense cycles, deletion cost will rise, and that is the signal to revisit either the topology or the mode.

---

## 6. What this ratifies, and what it leaves open

Ratified:

- **D25.** A property graph serves the load-bearing requirement. Write-time incremental labelling, O(1) authorisation-time reads and sound edge-deletion retraction are all demonstrated. No authorisation-time path query is needed, which was the deciding criterion against an RDF triple store answering SPARQL property paths on the hot path.
- **D38.** With the substrate confirmed as a property graph, BFO as the loaded spine composes cleanly: the loaded layers are authored as graph nodes and relations rather than OWL, as `ontology/README.md` anticipated. Nothing in the spike contradicts the load-and-extend assumption. The BFO load-and-extend itself is a separate, smaller check still to run against the real store.
- **D32.** Edge-deletion label retraction is solved, with a sound-and-cheap default (conservative) and an exact fallback, and the price of each is measured.

Left open, and unchanged by the spike:

- The spike is substrate-neutral, so it does not exercise Memgraph's own triggers, transaction semantics or persistence. Binding the algorithm to Memgraph and re-checking the four criteria against the live store is the next substrate step, now low-risk because the algorithm is proven.
- The dense-cycle caveat (section 5) is a monitoring obligation, not a resolved question.
- Everything downstream of the substrate in `ONTOLOGY_CONSTRUCTION.md` section 9 (the seed ontology, the marshalling contract wired to Fenrir, the coverage and correctness corpora) is untouched by this spike and remains Phase 2 work.

---

## 7. Disposition of the code

Per 3.3 the spike is throwaway. It is kept in the tree as evidence for the decision, not as a component. The algorithm in `reachability.py` is the reference the live Memgraph binding should reproduce and re-test, but the Python is not itself part of the build. If it is ever promoted, note that the label semantics, not the Python, are the artefact.
