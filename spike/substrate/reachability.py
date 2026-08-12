"""Substrate-neutral flow-to-sink reachability with an incremental action-critical label.

This is the load-bearing half of the D25 / D38 substrate spike (Phase 2). It does
NOT decide the substrate. It isolates and tests the one algorithm the substrate
must support: maintaining Gjoll's action-critical label incrementally as edges are
added and, above all, correctly retracting it when edges are deleted (decision
D32, the known hard case named in ONTOLOGY_CONSTRUCTION.md 3.3 and 10.2).

The abstraction here is deliberately not Memgraph, not Cypher, not any store. It is
a directed graph with a target set and a per-node label, expressed in plain Python.
If the algorithm is sound and cheap here, binding it to a property graph is a
mechanical step (write-time triggers on edge insert/delete, a boolean node
property read at authorisation). If it is unsound or expensive here, no store
choice rescues it, and the spike report says reconsider a Datalog engine (Souffle)
per 3.3. Either way the substrate question is answered by this file's results, not
assumed.

Model, mapped to the architecture:

- A node is a value: a typed data assertion in Mimisbrunnr.
- A directed edge u -> v means "the value at u can flow into the value at v".
  Reachability is over out-edges: if u -> v and v can reach a sink, so can u.
- A sink node is a consequential sink. Sinks are AGENT-SCOPED (decision D24, D30):
  which nodes are sinks depends on a given agent's permitted action space, so the
  target set is a parameter, not a graph-global constant.
- A node is ACTION-CRITICAL iff there is a directed path from it to any sink in the
  agent's target set. A sink is trivially action-critical (path of length zero).

The invariant that must never break (ONTOLOGY_CONSTRUCTION.md 3.3 criterion 3):
NEVER retract a label that should stay. Under-retraction (keeping a label that
could be dropped) is a sound conservative over-approximation and is allowed.
Over-retraction (dropping a label a value should keep) is a critical fault: a value
would silently become inert and skip Gjoll. This module is built so the exact
algorithm is sound, and the spike separately checks it against a brute-force oracle.

The algorithm: support-counted incremental maintenance with localised
delete-rederive (DRed) on deletion.

- Each node carries support = the number of its out-edges whose head is
  action-critical (a sink counts itself as action-critical). A node is
  action-critical iff it is a sink OR support > 0.
- On ADD edge u -> v: if v is action-critical and u was not, u becomes
  action-critical and the gain propagates backward to u's predecessors. Work is
  bounded by the set of nodes that newly become action-critical, never a full
  traversal.
- On DELETE edge u -> v: if v was action-critical, u loses one unit of support.
  If u's support hits zero and u is not a sink, u may no longer be action-critical,
  but only if it has no other path to a sink. We cannot conclude that locally, so
  we run a bounded delete-rederive over the affected region: over-approximate the
  set that might have lost reachability (the "shaken" set), then rederive which of
  them still reach a sink and keep those. This is sound: a node is retracted only
  after we confirm it has no surviving path.
"""

from __future__ import annotations

from collections import deque


class ReachabilityGraph:
    """A directed graph with an agent-scoped sink set and an incremental
    action-critical label maintained on every edge add and delete.

    One instance models one agent's view (its sink set). The node space is shared
    across agents in the real system; here each agent-scoped test builds its own
    instance, which is the honest analogue of "reachability computed against a given
    agent's reachable sink set" (D24).
    """

    def __init__(self, mode: str = "conservative") -> None:
        """mode selects the deletion strategy, so the spike can compare the two the
        way ONTOLOGY_CONSTRUCTION.md 3.3 frames the choice:

        - "conservative": support-counted deletion with an O(1) early-return when the
          source keeps positive support. Sound and cheap, but over-approximates when
          the surviving support is a stale cycle whose only real exit was the deleted
          edge. This is the "sound conservative over-approximation" 3.3 explicitly
          allows (never retract a label that should stay).
        - "exact": on any delete of an edge to a critical head, run a grounded
          rederive over the affected region and re-establish only nodes with a path
          that leaves the region to a real sink. Always matches the oracle, at higher
          and less predictable deletion cost.

        Both share the same add path (adds are monotonic; cycles cause no trouble on
        insertion) and the same O(1) authorisation-time read.
        """
        if mode not in ("conservative", "exact"):
            raise ValueError(f"mode must be 'conservative' or 'exact', got {mode!r}")
        self.mode = mode
        # Adjacency. out_edges[u] and in_edges[v] are dicts mapping neighbour ->
        # multiplicity, so a repeated u -> v edge is counted, matching a property
        # graph that permits parallel edges. Multiplicity keeps support counting
        # exact.
        self._out: dict[str, dict[str, int]] = {}
        self._in: dict[str, dict[str, int]] = {}
        self._sinks: set[str] = set()
        # support[u] = sum over out-neighbours w of (multiplicity(u,w) if w is
        # action-critical else 0). Maintained incrementally.
        self._support: dict[str, int] = {}
        # The label. action_critical[u] is True iff u is a sink or support[u] > 0.
        self._ac: set[str] = set()
        # Instrumentation for the spike's cost measurements. Reset per operation.
        self.last_op_touched = 0

    # --- node and sink management ---

    def add_node(self, n: str) -> None:
        if n not in self._out:
            self._out[n] = {}
            self._in[n] = {}
            self._support[n] = 0

    def mark_sink(self, n: str) -> None:
        """Declare n a consequential sink for this agent. A sink is action-critical
        by definition; marking one can only add labels, so it propagates like an
        edge gain."""
        self.add_node(n)
        if n in self._sinks:
            return
        self._sinks.add(n)
        if n not in self._ac:
            self._become_ac(n)

    # --- authorisation-time read (criterion 2) ---

    def is_action_critical(self, n: str) -> bool:
        """Criterion 2: this is a set-membership read, O(1), never a traversal.
        In a property graph this is reading a boolean node property."""
        return n in self._ac

    # --- write-time maintenance: add (criterion 1) ---

    def add_edge(self, u: str, v: str) -> None:
        """Criterion 1: add an edge and maintain labels in bounded work.

        Work is proportional to the number of nodes that NEWLY become
        action-critical because of this edge, plus their in-degree. It is never a
        full-graph traversal. If v is not action-critical, the cost is O(1)."""
        self.add_node(u)
        self.add_node(v)
        self.last_op_touched = 0
        self._out[u][v] = self._out[u].get(v, 0) + 1
        self._in[v][u] = self._in[v].get(u, 0) + 1

        if v in self._ac:
            # u gains one unit of support from an already-critical head.
            prev = self._support[u]
            self._support[u] = prev + 1
            if prev == 0 and u not in self._sinks and u not in self._ac:
                # u was not critical and now is: propagate the gain backward.
                self._become_ac(u)

    def _become_ac(self, start: str) -> None:
        """Mark start action-critical and propagate the gain to predecessors.
        Only nodes that transition from not-critical to critical do any work, so
        the total work over one operation is bounded by the newly-critical frontier
        and its incoming edges."""
        queue = deque([start])
        while queue:
            node = queue.popleft()
            if node in self._ac:
                continue
            self._ac.add(node)
            self.last_op_touched += 1
            # Every predecessor now has one more action-critical out-neighbour.
            for pred, mult in self._in[node].items():
                prev = self._support[pred]
                self._support[pred] = prev + mult
                if prev == 0 and pred not in self._sinks and pred not in self._ac:
                    queue.append(pred)

    # --- write-time maintenance: delete (criterion 3, the hard case, D32) ---

    def delete_edge(self, u: str, v: str) -> None:
        """Criterion 3: delete an edge and SOUNDLY retract labels.

        Deletion is non-monotonic: removing u -> v can strip reachability from u and
        anything that reached a sink only through u, but must leave every node that
        still has a surviving path untouched. The invariant is that we never retract
        a label that should stay.

        Method (localised delete-rederive):
          1. Remove the edge and decrement u's support if v was action-critical.
          2. If that did not drop u below the critical threshold, nothing can have
             changed: return in O(1).
          3. Otherwise u is a retraction candidate. Compute the "shaken" set: u and
             every ancestor that could have depended on u for reachability. Provi-
             sionally clear their labels and support-from-within-the-set.
          4. Rederive: any shaken node with a surviving out-edge to an action-
             critical node OUTSIDE the shaken set (or that is itself a sink) is
             re-established and the gain propagates within the set. Whatever is not
             re-established had no surviving path and is correctly retracted.
        """
        self.last_op_touched = 0
        if v not in self._out.get(u, {}):
            return  # no such edge
        mult = self._out[u][v] - 1
        if mult > 0:
            self._out[u][v] = mult
        else:
            del self._out[u][v]
        imult = self._in[v][u] - 1
        if imult > 0:
            self._in[v][u] = imult
        else:
            del self._in[v][u]

        if v not in self._ac:
            return  # v was inert; u never drew support from it. O(1).

        # v was action-critical: u loses one unit of support.
        self._support[u] -= 1
        if u in self._sinks or u not in self._ac:
            return  # u is a sink (intrinsic label) or was never labelled. O(1).

        if self.mode == "conservative":
            # Conservative fast path: if u keeps positive support it MIGHT still be
            # grounded, and we do not pay to check. This is sound (we only ever keep
            # a label, never wrongly drop one) but over-approximates when the
            # residual support is a stale cycle. Only when support hits zero do we
            # run the localised rederive.
            if self._support[u] > 0:
                return  # O(1) early-return; the source of the over-approximation.
            self._delete_rederive(u)
        else:
            # Exact mode: positive residual support does NOT prove a grounded path,
            # because it may come from a cycle that depended on the deleted edge. So
            # whenever u lost support from a critical head we run the grounded
            # rederive regardless of residual support. Always exact; more deletions
            # pay the rederive cost. The spike measures how much more.
            self._delete_rederive(u)

    def _delete_rederive(self, seed: str) -> None:
        # Phase 1: shaken set. The seed and every ancestor that is currently
        # action-critical and not a sink. These are the only nodes whose label could
        # depend on the lost path. Sinks are never shaken (their label is intrinsic).
        # The seed is included unconditionally, because in exact mode it may still
        # carry (stale) positive support. This over-approximates the affected region
        # and bounds all further work to it.
        shaken: set[str] = set()
        stack = [seed]
        while stack:
            node = stack.pop()
            if node in shaken or node in self._sinks or node not in self._ac:
                continue
            shaken.add(node)
            for pred in self._in[node]:
                if pred not in shaken and pred not in self._sinks and pred in self._ac:
                    stack.append(pred)

        # Phase 2: provisionally retract every shaken node. Re-establishment in
        # phase 3 must be GROUNDED in a path that leaves the shaken set to a real
        # sink; it may not be justified by mutual support inside the set. This is
        # what makes the result exact rather than merely sound: a self-supporting
        # cycle whose only exit was the deleted edge (a -> b -> a, with a -> sink
        # removed) has no grounded path and must fully retract. Support counting
        # alone would keep such a cycle critical (each node supported by the other),
        # which is sound (over-retention) but not exact.
        for node in shaken:
            self._ac.discard(node)

        # A shaken node is re-established iff it has an out-edge to a node that is
        # confirmed critical: either OUTSIDE the shaken set (already grounded in a
        # sink path) or already re-established this pass (transitively grounded).
        # Seed the frontier from nodes with a surviving exit edge to an out-of-set
        # critical node, then propagate re-establishment strictly backward. Because a
        # node only enters when a SUCCESSOR is confirmed, the derivation is grounded
        # in the sink set and cannot bootstrap a cycle.
        reestablished: set[str] = set()
        queue: deque[str] = deque()
        for node in shaken:
            for w in self._out[node]:
                if w not in shaken and w in self._ac:
                    queue.append(node)
                    break
        while queue:
            node = queue.popleft()
            if node in reestablished:
                continue
            reestablished.add(node)
            self._ac.add(node)
            self.last_op_touched += 1
            for pred in self._in[node]:
                # pred is re-established because a successor (node) now is.
                if pred in shaken and pred not in reestablished:
                    queue.append(pred)

        # Phase 4: recompute support for every shaken node against the final label
        # state, so the incremental invariant (support = count of critical
        # out-neighbours) is restored exactly for the next operation. This is O(edges
        # incident to the shaken set), still localised.
        for node in shaken:
            s = 0
            for w, m in self._out[node].items():
                if w in self._ac:
                    s += m
            self._support[node] = s

    # --- oracle for the soundness check (not used in the hot path) ---

    def brute_force_action_critical(self) -> set[str]:
        """Ground truth by full backward BFS from the sink set. This is exactly the
        expensive authorisation-time traversal the incremental label exists to
        avoid; here it is the oracle the spike compares the incremental label
        against, never a production path."""
        result: set[str] = set(self._sinks)
        queue = deque(self._sinks)
        while queue:
            node = queue.popleft()
            for pred in self._in.get(node, {}):
                if pred not in result:
                    result.add(pred)
                    queue.append(pred)
        return result

    # --- introspection for tests ---

    def edge_count(self) -> int:
        return sum(sum(m for m in nbrs.values()) for nbrs in self._out.values())

    def node_count(self) -> int:
        return len(self._out)
