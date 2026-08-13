"""Memgraph-backed flow-to-sink store: the live-substrate binding the spike anticipated.

The substrate spike (`OUTCOME.md`) proved the flow-to-sink action-critical algorithm
substrate-neutrally in `reachability.py`, and its residual was to bind that proven
algorithm to a live property-graph store and re-check the four criteria of
`ONTOLOGY_CONSTRUCTION.md` 3.3 against the real thing. This module is that binding,
against Memgraph over the Bolt protocol.

It reproduces the SAME semantics as `reachability.py` conservative mode (D43, D44):

- A node is a `Value` (or a `Sink`). An edge `(:Value)-[:CAN_REACH]->(x)` means the
  value can flow into x.
- A boolean node property `action_critical` is the label. Authorisation-time read is
  a property read (criterion 2), never a traversal.
- On add-edge, if the head is action-critical, propagate the label backward to newly
  critical predecessors (criterion 1), bounded work.
- A per-node `support` count (number of out-edges to action-critical heads) drives
  the conservative delete: on delete-edge, decrement support; only when support hits
  zero run a localised delete-rederive that regrounds against real paths to a sink
  (criterion 3, the hard case D32).

The point of this file is NOT to be the reference (the in-memory version is, D43).
It is to confirm the real store can hold the label and maintain it with the same
soundness the spike proved. The in-memory `ReachabilityGraph` is the oracle the
binding is checked against.

Requires the `neo4j` Bolt driver and a reachable Memgraph. Both are optional: the
test that uses this skips cleanly when Memgraph is not reachable, so the core suite
stays dependency-free (D01, and the reproducibility rule).
"""

from __future__ import annotations

from collections import deque


class MemgraphReachability:
    """A flow-to-sink reachability store backed by Memgraph, mirroring the in-memory
    reference's conservative-mode semantics. One instance models one agent's view (its
    sink set), the same scoping the reference uses (D24)."""

    def __init__(self, driver, wipe: bool = True) -> None:
        self._driver = driver
        if wipe:
            self._run("MATCH (n) DETACH DELETE n")
            # A uniqueness/index on id keeps MERGE and lookups fast and correct.
            try:
                self._run("CREATE INDEX ON :Node(id)")
            except Exception:
                pass  # index may already exist; not fatal

    def _run(self, cypher: str, **params):
        with self._driver.session() as s:
            return list(s.run(cypher, **params))

    # --- node and sink management ---

    def add_node(self, n: str) -> None:
        self._run(
            "MERGE (x:Node {id:$id}) "
            "ON CREATE SET x.action_critical=false, x.support=0, x.is_sink=false",
            id=n,
        )

    def mark_sink(self, n: str) -> None:
        self.add_node(n)
        rec = self._run("MATCH (x:Node {id:$id}) RETURN x.is_sink AS s", id=n)
        if rec and rec[0]["s"]:
            return
        self._run("MATCH (x:Node {id:$id}) SET x.is_sink=true", id=n)
        # A sink is action-critical by definition; marking it can only add labels.
        rec = self._run("MATCH (x:Node {id:$id}) RETURN x.action_critical AS ac", id=n)
        if not (rec and rec[0]["ac"]):
            self._become_ac(n)

    # --- authorisation-time read (criterion 2): a property read, not a traversal ---

    def is_action_critical(self, n: str) -> bool:
        rec = self._run("MATCH (x:Node {id:$id}) RETURN x.action_critical AS ac", id=n)
        return bool(rec and rec[0]["ac"])

    # --- write-time add (criterion 1) ---

    def add_edge(self, u: str, v: str) -> None:
        self.add_node(u)
        self.add_node(v)
        self._run(
            "MATCH (a:Node {id:$u}),(b:Node {id:$v}) CREATE (a)-[:CAN_REACH]->(b)",
            u=u, v=v,
        )
        # If v is action-critical, u gains one unit of support; if that lifts u from
        # zero, u becomes critical and the gain propagates backward.
        if self.is_action_critical(v):
            prev = self._support(u)
            self._set_support(u, prev + 1)
            if prev == 0 and not self._is_sink(u) and not self.is_action_critical(u):
                self._become_ac(u)

    def _become_ac(self, start: str) -> None:
        """Mark start action-critical and propagate the gain to predecessors. Only
        nodes transitioning not-critical -> critical do work (bounded frontier)."""
        queue = deque([start])
        while queue:
            node = queue.popleft()
            if self.is_action_critical(node):
                continue
            self._run("MATCH (x:Node {id:$id}) SET x.action_critical=true", id=node)
            preds = self._run(
                "MATCH (p:Node)-[:CAN_REACH]->(x:Node {id:$id}) "
                "RETURN p.id AS pid, count(*) AS mult", id=node,
            )
            for row in preds:
                pid, mult = row["pid"], row["mult"]
                prev = self._support(pid)
                self._set_support(pid, prev + mult)
                if prev == 0 and not self._is_sink(pid) and not self.is_action_critical(pid):
                    queue.append(pid)

    # --- write-time delete (criterion 3, the hard case D32), conservative mode ---

    def delete_edge(self, u: str, v: str) -> None:
        # Remove one CAN_REACH edge u->v if present.
        existed = self._run(
            "MATCH (a:Node {id:$u})-[r:CAN_REACH]->(b:Node {id:$v}) "
            "WITH r LIMIT 1 DELETE r RETURN count(r) AS c",
            u=u, v=v,
        )
        if not existed or existed[0]["c"] == 0:
            return
        if not self.is_action_critical(v):
            return  # v was inert; u never drew support from it. O(1).
        self._set_support(u, self._support(u) - 1)
        if self._is_sink(u) or not self.is_action_critical(u):
            return
        if self._support(u) > 0:
            return  # conservative fast path: still supported, may be a stale cycle
        self._delete_rederive(u)

    def _delete_rederive(self, seed: str) -> None:
        # Phase 1: shaken set = seed plus critical, non-sink ancestors that could
        # depend on it. Bounds all work to the affected region.
        shaken: set[str] = set()
        stack = [seed]
        while stack:
            node = stack.pop()
            if node in shaken or self._is_sink(node) or not self.is_action_critical(node):
                continue
            shaken.add(node)
            for row in self._run(
                "MATCH (p:Node)-[:CAN_REACH]->(x:Node {id:$id}) RETURN DISTINCT p.id AS pid",
                id=node,
            ):
                pid = row["pid"]
                if pid not in shaken and not self._is_sink(pid) and self.is_action_critical(pid):
                    stack.append(pid)

        # Phase 2: provisionally retract the whole shaken set.
        for node in shaken:
            self._run("MATCH (x:Node {id:$id}) SET x.action_critical=false", id=node)

        # Phase 3: re-establish, grounded. A shaken node is re-established iff it has an
        # out-edge to a confirmed-critical node OUTSIDE the shaken set, then the
        # re-establishment propagates backward within the set. Grounded in real sink
        # paths, so a self-supporting cycle with no exit stays retracted (exact).
        reestablished: set[str] = set()
        queue: deque[str] = deque()
        for node in shaken:
            heads = self._run(
                "MATCH (x:Node {id:$id})-[:CAN_REACH]->(w:Node) "
                "RETURN w.id AS wid, w.action_critical AS wac", id=node,
            )
            if any((row["wid"] not in shaken and row["wac"]) for row in heads):
                queue.append(node)
        while queue:
            node = queue.popleft()
            if node in reestablished:
                continue
            reestablished.add(node)
            self._run("MATCH (x:Node {id:$id}) SET x.action_critical=true", id=node)
            for row in self._run(
                "MATCH (p:Node)-[:CAN_REACH]->(x:Node {id:$id}) RETURN DISTINCT p.id AS pid",
                id=node,
            ):
                if row["pid"] in shaken and row["pid"] not in reestablished:
                    queue.append(row["pid"])

        # Phase 4: recompute support for every shaken node against the final labels.
        for node in shaken:
            rec = self._run(
                "MATCH (x:Node {id:$id})-[e:CAN_REACH]->(w:Node) "
                "WHERE w.action_critical RETURN count(e) AS s", id=node,
            )
            self._set_support(node, rec[0]["s"] if rec else 0)

    # --- helpers ---

    def _support(self, n: str) -> int:
        rec = self._run("MATCH (x:Node {id:$id}) RETURN x.support AS s", id=n)
        return int(rec[0]["s"]) if rec and rec[0]["s"] is not None else 0

    def _set_support(self, n: str, val: int) -> None:
        self._run("MATCH (x:Node {id:$id}) SET x.support=$v", id=n, v=int(val))

    def _is_sink(self, n: str) -> bool:
        rec = self._run("MATCH (x:Node {id:$id}) RETURN x.is_sink AS s", id=n)
        return bool(rec and rec[0]["s"])

    # --- oracle helpers for the test ---

    def brute_force_action_critical(self) -> set[str]:
        """Ground truth by traversal from the sink set (the expensive query the label
        exists to avoid), used only as the test oracle, never on a hot path."""
        rows = self._run(
            "MATCH (s:Node {is_sink:true}) "
            "OPTIONAL MATCH (a:Node)-[:CAN_REACH*]->(s) "
            "WITH collect(DISTINCT s.id) AS sinks, collect(DISTINCT a.id) AS anc "
            "RETURN sinks, anc"
        )
        result: set[str] = set()
        if rows:
            result.update(x for x in (rows[0]["sinks"] or []) if x is not None)
            result.update(x for x in (rows[0]["anc"] or []) if x is not None)
        return result

    def all_labelled(self) -> set[str]:
        rows = self._run("MATCH (x:Node) WHERE x.action_critical RETURN x.id AS id")
        return {r["id"] for r in rows}
