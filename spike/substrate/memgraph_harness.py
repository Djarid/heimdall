"""Substrate binding test: the four spike criteria against a LIVE Memgraph store.

This resolves the substrate spike's residual (`OUTCOME.md` section 6): the in-memory
algorithm was proven substrate-neutrally (D43); this checks the SAME four criteria of
`ONTOLOGY_CONSTRUCTION.md` 3.3 against a real property-graph store, Memgraph, over
Bolt. The in-memory `ReachabilityGraph` is the oracle: the binding is correct iff its
labels match the reference on the same operation sequence.

Optional by design (D01, reproducibility). If the `neo4j` driver is missing or no
Memgraph is reachable, the test SKIPS with a clear message and returns success, so
the core ontology suite stays dependency-free on any machine. Where Memgraph is
reachable (e.g. via podman, see `start_memgraph`), it runs for real.

Run: /Users/jasonh/git/heimdall/poc/.venv/bin/python memgraph_harness.py
Start Memgraph first (optional helper): podman run -d --name heimdall-memgraph \
  -p 7687:7687 docker.io/memgraph/memgraph-mage:latest
"""

from __future__ import annotations

import random
import sys

from reachability import ReachabilityGraph  # the proven in-memory reference (oracle)

BOLT_URI = "bolt://localhost:7687"


def _connect():
    """Return a live neo4j driver if Memgraph is reachable, else None. Never raises:
    absence is a skip, not a failure."""
    try:
        from neo4j import GraphDatabase
    except Exception:
        return None
    try:
        driver = GraphDatabase.driver(BOLT_URI, auth=("", ""))
        with driver.session() as s:
            s.run("RETURN 1").consume()
        return driver
    except Exception:
        return None


def _differential(driver, seed: int, ops: int, universe: int) -> dict:
    """Drive the SAME random add/delete sequence through the in-memory reference and
    the Memgraph binding, and after every operation compare labels. The reference is
    the oracle; the binding must match it (both are conservative mode)."""
    from memgraph_store import MemgraphReachability

    rng = random.Random(seed)
    ref = ReachabilityGraph(mode="conservative")
    mem = MemgraphReachability(driver, wipe=True)

    nodes = [f"n{i}" for i in range(universe)]
    for x in nodes:
        ref.add_node(x)
        mem.add_node(x)
    sinks = rng.sample(nodes, k=max(1, universe // 20))
    for s in sinks:
        ref.mark_sink(s)
        mem.mark_sink(s)

    live: set[tuple[str, str]] = set()
    mismatches = 0
    unsound = 0  # oracle-critical but binding-inert: the fatal direction
    for _ in range(ops):
        add = (not live) or rng.random() < 0.55
        if add:
            u, v = rng.choice(nodes), rng.choice(nodes)
            if u == v:
                continue
            ref.add_edge(u, v)
            mem.add_edge(u, v)
            live.add((u, v))
        else:
            u, v = rng.choice(tuple(live))
            ref.delete_edge(u, v)
            mem.delete_edge(u, v)
            live.discard((u, v))

        ref_labels = {n for n in nodes if ref.is_action_critical(n)}
        mem_labels = mem.all_labelled() & set(nodes)
        if ref_labels != mem_labels:
            mismatches += 1
        # Soundness: the binding must never call a value inert that the reference (and
        # thus the oracle) holds critical.
        if ref_labels - mem_labels:
            unsound += 1

    return {"mismatches": mismatches, "unsound": unsound, "ops": ops}


def main() -> int:
    print("Heimdall substrate binding test: four criteria against LIVE Memgraph")
    driver = _connect()
    if driver is None:
        print("  [SKIP] Memgraph not reachable at", BOLT_URI, "(or neo4j driver absent).")
        print("  The in-memory reference (spike/substrate/harness.py) is the proven")
        print("  algorithm; this binding check is optional. Start Memgraph with podman")
        print("  to run it. Skipping is not a failure.")
        return 0

    from memgraph_store import MemgraphReachability

    checks: list[tuple[str, bool, str]] = []

    # Criterion 1: write-time label maintenance (add creates the label).
    g = MemgraphReachability(driver, wipe=True)
    g.mark_sink("s")
    g.add_edge("a", "s")
    g.add_edge("b", "a")
    checks.append(("1 write-time add labels the source", g.is_action_critical("a") and g.is_action_critical("b"), ""))

    # Criterion 2: authorisation-time read is a property read (semantics; the Cypher
    # is a single node-property lookup, not a path query).
    # Criterion 2: authorisation-time read is a property read (a single node-property
    # lookup, not a path query). Semantics: a value reaching a sink reads critical, a
    # freshly-added inert node reads inert.
    g.add_node("inert_node")
    checks.append(("2 read is a property read (critical vs inert)",
                   g.is_action_critical("a") and not g.is_action_critical("inert_node"), ""))

    # Criterion 3: edge-deletion retraction, and the dangerous survivor case.
    g2 = MemgraphReachability(driver, wipe=True)
    g2.mark_sink("k")
    g2.add_edge("x", "pa"); g2.add_edge("x", "pb")
    g2.add_edge("pa", "k"); g2.add_edge("pb", "k")
    g2.delete_edge("pa", "k")  # one path remains via pb
    survivor = g2.is_action_critical("x") and g2.is_action_critical("pb") and not g2.is_action_critical("pa")
    checks.append(("3 delete does not over-retract a surviving path", survivor, ""))
    # cycle case, CONSERVATIVE mode (D44): c1<->c2 with c1->S the only exit. After
    # deleting c1->S, conservative mode is ALLOWED to keep the cycle labelled (a sound
    # over-approximation), because c1's support survives via c2's stale label. The
    # binding reproduces the reference exactly here, so we assert SOUNDNESS (the cycle
    # is not wrongly dropped), not exact retraction. Exact retraction is an exact-mode
    # property; this binding, like the live default, is conservative. This mirrors the
    # in-memory reference in conservative mode.
    g3 = MemgraphReachability(driver, wipe=True)
    g3.mark_sink("S")
    g3.add_edge("c1", "c2"); g3.add_edge("c2", "c1"); g3.add_edge("c1", "S")
    g3.delete_edge("c1", "S")
    ref3 = ReachabilityGraph(mode="conservative")
    ref3.mark_sink("S")
    ref3.add_edge("c1", "c2"); ref3.add_edge("c2", "c1"); ref3.add_edge("c1", "S")
    ref3.delete_edge("c1", "S")
    cyc = (g3.is_action_critical("c1") == ref3.is_action_critical("c1")
           and g3.is_action_critical("c2") == ref3.is_action_critical("c2"))
    checks.append(("3 self-supporting cycle matches conservative reference (sound over-approx, D44)", cyc, ""))

    # Criterion 4 (scale-ish) via differential fuzzing against the in-memory oracle.
    total_mismatch = total_unsound = 0
    for seed in (1, 7, 42):
        r = _differential(driver, seed=seed, ops=600, universe=60)
        total_mismatch += r["mismatches"]
        total_unsound += r["unsound"]
    checks.append(("4a binding is SOUND vs the proven reference (never wrongly inert)",
                   total_unsound == 0, f"unsound ops = {total_unsound}"))
    checks.append(("4b binding matches the reference exactly on every op",
                   total_mismatch == 0, f"mismatched ops = {total_mismatch}"))

    print("\nResults (live Memgraph):")
    ok = True
    for name, passed, detail in checks:
        mark = "PASS" if passed else "FAIL"
        if not passed:
            ok = False
        print(f"  [{mark}] {name}" + (f" -- {detail}" if detail else ""))

    # Clean up test data.
    try:
        with driver.session() as s:
            s.run("MATCH (n) DETACH DELETE n").consume()
        driver.close()
    except Exception:
        pass

    print()
    if ok:
        print("BINDING PASS: the proven flow-to-sink algorithm holds on a live Memgraph")
        print("store, matching the in-memory reference exactly across add, delete and")
        print("fuzzed sequences. The substrate spike's residual (D25) is resolved: the")
        print("property graph maintains the action-critical label soundly in practice,")
        print("not just in the substrate-neutral proof.")
        return 0
    print("BINDING FAIL: the live store diverged from the proven reference. Detail above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
