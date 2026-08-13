"""Flow-to-sink backends: where Nornir computes the action-critical set.

Nornir's flow-to-sink step (engine.run) needs one thing from a backend: given the
batch's flow edges and an agent's consequential sink set, return the set of value ids
that are action-critical (can reach any sink). That is the whole contract, and it has
two implementations:

- `in_memory`: the default. A backward BFS over the batch's edges (the proven
  `rules.action_critical_set`). Dependency-free, per-batch, exact. This is what keeps
  the core suite runnable on any machine (D01) and it stays the default.

- `MemgraphFlowBackend`: optional. Runs the SAME determination over a live Memgraph
  store using the algorithm the substrate spike proved on that store (D57,
  `spike/substrate/memgraph_store.py`). This is the persistence path: the label lives
  in the store, maintained incrementally as edges are written, and read back at
  authorisation time. Wiring it into Nornir is the last integration the spike and the
  gate left unproven, that the live store and the gate actually run TOGETHER through
  Nornir, not just as separately-verified pieces.

Both return the same set for the same input; the optional integration test checks the
Memgraph backend against the in-memory one as its oracle. Nornir takes a backend by
injection and defaults to in-memory, so nothing about the store leaks into the core
path.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .rules import action_critical_set


def in_memory(flow_edges: list[tuple[str, str]], sinks: frozenset[str]) -> set[str]:
    """The default backend: the proven in-memory backward reachability."""
    return action_critical_set(flow_edges, sinks)


class MemgraphFlowBackend:
    """A flow-to-sink backend backed by a live Memgraph store.

    Reuses the spike's proven `MemgraphReachability` (D57) so the action-critical
    determination Nornir runs is the exact algorithm verified against the store. The
    store is wiped per call by default, matching the per-batch semantics of the
    in-memory backend; a persistent-store mode (accumulating across batches) is a
    later concern and would drop `wipe`.

    Construct with a `neo4j` driver. `available()` lets a caller (a test) check
    reachability and skip cleanly when Memgraph is absent, so this never forces a hard
    dependency.
    """

    def __init__(self, driver, persist: bool = False) -> None:
        self._driver = driver
        # persist=False (default): per-batch semantics, matching the in-memory
        # backend. Each call starts from a clean graph, so a batch sees only its own
        # edges. persist=True: the flow graph ACCUMULATES across calls, so a value
        # written in one batch that reaches a sink via an edge written in a LATER
        # batch is caught (cross-batch state staging, D64). The store holds the graph
        # either way; the difference is whether we wipe it between calls.
        self._persist = persist
        # The proven store binding lives in the spike tree; import it lazily and by
        # path so the core package keeps no dependency on it.
        spike = Path(__file__).resolve().parents[2] / "spike" / "substrate"
        if str(spike) not in sys.path:
            sys.path.insert(0, str(spike))
        from memgraph_store import MemgraphReachability  # noqa: E402
        self._Store = MemgraphReachability
        # In persist mode we keep one store over the accumulated graph and remember
        # what has already been written, so a repeated batch does not double-add
        # parallel edges (which would corrupt the support counts).
        self._store = None
        self._known_sinks: set[str] = set()
        self._known_edges: set[tuple[str, str]] = set()
        if self._persist:
            self._store = self._Store(driver, wipe=True)  # start clean once, then accumulate

    def reset(self) -> None:
        """Wipe the accumulated persistent graph and start fresh. No-op in per-batch
        mode. Used to isolate tests, and available operationally to clear state."""
        if self._persist and self._store is not None:
            self._store = self._Store(self._driver, wipe=True)
            self._known_sinks.clear()
            self._known_edges.clear()

    def is_action_critical(self, node: str) -> bool:
        """Query the current action-critical label of any node in the accumulated
        graph. In per-batch mode there is no persistent graph to query, so this only
        answers meaningfully in persist mode; it exists so a gate can re-read a value's
        label at action time, which is the whole point of persistence (a value staged
        earlier is already labelled when a later action touches it)."""
        if self._store is None:
            return False
        return self._store.is_action_critical(node)

    @staticmethod
    def connect(uri: str = "bolt://localhost:7687"):
        """Return a driver if Memgraph is reachable, else None. Never raises."""
        try:
            from neo4j import GraphDatabase
        except Exception:
            return None
        try:
            driver = GraphDatabase.driver(uri, auth=("", ""))
            with driver.session() as s:
                s.run("RETURN 1").consume()
            return driver
        except Exception:
            return None

    def __call__(self, flow_edges: list[tuple[str, str]], sinks: frozenset[str]) -> set[str]:
        if self._persist:
            store = self._store
            # Add only the delta, so accumulated parallel edges are not double-added.
            for s in sinks:
                if s not in self._known_sinks:
                    store.mark_sink(s)
                    self._known_sinks.add(s)
            for u, v in flow_edges:
                if (u, v) not in self._known_edges:
                    store.add_edge(u, v)
                    self._known_edges.add((u, v))
        else:
            # Per-batch: a clean graph each call, matching the in-memory backend.
            store = self._Store(self._driver, wipe=True)
            for s in sinks:
                store.mark_sink(s)
            for u, v in flow_edges:
                store.add_edge(u, v)
        # Read back the labelled set for THIS batch's node universe (so Nornir sets
        # action_critical on this batch's assertions). In persist mode the label is
        # computed over the whole accumulated graph, so a node here reads critical if
        # it reaches a sink via any edge ever written, not only this batch's.
        nodes = {u for u, _ in flow_edges} | {v for _, v in flow_edges} | set(sinks)
        return {n for n in nodes if store.is_action_critical(n)}
