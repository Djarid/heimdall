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

    def __init__(self, driver, wipe: bool = True) -> None:
        self._driver = driver
        self._wipe = wipe
        # The proven store binding lives in the spike tree; import it lazily and by
        # path so the core package keeps no dependency on it.
        spike = Path(__file__).resolve().parents[2] / "spike" / "substrate"
        if str(spike) not in sys.path:
            sys.path.insert(0, str(spike))
        from memgraph_store import MemgraphReachability  # noqa: E402
        self._Store = MemgraphReachability

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
        store = self._Store(self._driver, wipe=self._wipe)
        # Declare the agent's consequential sinks, then write every flow edge. The
        # store maintains the action-critical label incrementally as edges are added
        # (the write-time labelling the spike proved), so after loading, the label is
        # already correct and reading it back is a property read, not a traversal.
        for s in sinks:
            store.mark_sink(s)
        for u, v in flow_edges:
            store.add_edge(u, v)
        # Read back the labelled set. Restrict to nodes that appear in this batch's
        # graph plus the sinks, matching the in-memory backend's node universe.
        nodes = {u for u, _ in flow_edges} | {v for _, v in flow_edges} | set(sinks)
        return {n for n in nodes if store.is_action_critical(n)}
