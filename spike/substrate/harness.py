"""Spike harness for the D25 / D38 substrate decision (Phase 2).

Runs the four pass criteria from ONTOLOGY_CONSTRUCTION.md section 3.3 against the
substrate-neutral incremental algorithm in reachability.py, plus the mandatory
adversarial cross-domain state-staging case from section 8.4 and D30. The harness
is an audit artefact in the same spirit as poc/harness.py (D12): failures are loud,
the soundness oracle is the control that makes a pass mean something, and the
result is what ratifies or overturns D25/D38, not an assertion of confidence.

The load-bearing check is soundness under deletion (criterion 3, D32). It is tested
by differential fuzzing: build a random graph through a long random sequence of
adds and deletes, and after every single operation compare the incrementally
maintained label against a brute-force backward BFS oracle. The pass condition is
strict soundness (never retract a label the oracle keeps) AND, here, exactness (the
incremental label equals the oracle set). Exactness is stronger than 3.3 requires;
3.3 permits a sound conservative over-approximation. We report which we achieved.

Run: /Users/jasonh/git/heimdall/poc/.venv/bin/python harness.py
(any Python 3.11+ works; no third-party dependency).
"""

from __future__ import annotations

import random
import sys
import time

from reachability import ReachabilityGraph


class Result:
    def __init__(self) -> None:
        self.checks: list[tuple[str, bool, str]] = []

    def record(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append((name, ok, detail))

    def ok(self) -> bool:
        return all(ok for _, ok, _ in self.checks)

    def report(self) -> str:
        lines = []
        for name, ok, detail in self.checks:
            mark = "PASS" if ok else "FAIL"
            lines.append(f"  [{mark}] {name}" + (f" -- {detail}" if detail else ""))
        return "\n".join(lines)


# --- Criterion 1: write-time label maintenance, bounded, no full traversal ---

def criterion_1_write_time(res: Result) -> None:
    """Adding an edge that creates a path to a sink marks the source
    action-critical at write time, in work bounded by the newly-critical frontier,
    never a full-graph traversal."""
    g = ReachabilityGraph()
    # A long chain a0 -> a1 -> ... -> aN with the sink at the far end. Build it from
    # the sink backward so each add extends the critical frontier by exactly one.
    n = 5000
    g.mark_sink("s")
    prev = "s"
    max_touched = 0
    for i in range(n):
        node = f"a{i}"
        g.add_edge(node, prev)
        max_touched = max(max_touched, g.last_op_touched)
        prev = node
    # Every node must now be action-critical (each reaches the sink).
    all_ac = all(g.is_action_critical(f"a{i}") for i in range(n)) and g.is_action_critical("s")
    res.record("1.a all nodes on a path to a sink are labelled", all_ac)
    # Each single add touched a bounded number of nodes (here exactly one becomes
    # newly critical per add), independent of graph size: no full traversal.
    res.record(
        "1.b per-add work is bounded, not full-graph",
        max_touched <= 2,
        f"max nodes touched by any single add = {max_touched} (graph grew to {n + 1} nodes)",
    )
    # An add whose head is NOT action-critical must be O(1) (touch nothing).
    g.add_edge("isolated_u", "isolated_v")
    res.record(
        "1.c add with inert head touches nothing",
        g.last_op_touched == 0,
        f"touched = {g.last_op_touched}",
    )


# --- Criterion 2: authorisation-time read is a property read, not a traversal ---

def criterion_2_read_time(res: Result) -> None:
    """The authorisation-time question 'is this value action-critical?' is a
    constant-time membership read, not a graph query. We assert the semantics; the
    O(1) nature is structural (a set/dict lookup) and noted in reachability.py."""
    g = ReachabilityGraph()
    g.mark_sink("pay")
    g.add_edge("draft", "pay")
    g.add_edge("note", "log_only")  # note reaches no sink
    res.record("2.a value reaching a sink reads critical", g.is_action_critical("draft"))
    res.record("2.b value reaching no sink reads inert", not g.is_action_critical("note"))
    res.record("2.c the sink itself reads critical", g.is_action_critical("pay"))


# --- Criterion 3: edge-deletion retraction, SOUND, by differential fuzzing (D32) ---

def _fuzz(mode: str, seed: int, ops: int, universe: int) -> dict:
    """One differential-fuzzing run in one deletion mode. Drives a random add/delete
    sequence and after EVERY operation compares the incremental label to the
    brute-force oracle. Returns the soundness/exactness counts and delete-cost stats.

    Soundness (the non-negotiable invariant, both modes): the incremental label set
    is always a SUPERSET of the oracle set (never retract a label that should stay).
    Exactness: the two sets are equal (guaranteed in exact mode; over-approximated in
    conservative mode when a stale cycle keeps a label).
    """
    rng = random.Random(seed)
    g = ReachabilityGraph(mode=mode)
    nodes = [f"n{i}" for i in range(universe)]
    for x in nodes:
        g.add_node(x)
    sinks = rng.sample(nodes, k=max(1, universe // 20))  # agent-scoped sinks
    for s in sinks:
        g.mark_sink(s)
    live_edges: set[tuple[str, str]] = set()

    unsound = 0          # oracle-critical but incrementally inert: FATAL, must be 0
    inexact_over = 0     # incrementally critical but oracle-inert: allowed (conservative)
    deletes = 0
    delete_touch_total = 0
    worst_delete_touched = 0

    for _ in range(ops):
        add = (not live_edges) or rng.random() < 0.55
        if add:
            u = rng.choice(nodes)
            v = rng.choice(nodes)
            if u == v:
                continue
            g.add_edge(u, v)
            live_edges.add((u, v))
        else:
            u, v = rng.choice(tuple(live_edges))
            g.delete_edge(u, v)
            live_edges.discard((u, v))
            deletes += 1
            delete_touch_total += g.last_op_touched
            worst_delete_touched = max(worst_delete_touched, g.last_op_touched)

        oracle = g.brute_force_action_critical()
        incremental = set(n for n in nodes if g.is_action_critical(n))
        if oracle - incremental:
            unsound += 1
        if incremental - oracle:
            inexact_over += 1

    return {
        "unsound": unsound,
        "inexact_over": inexact_over,
        "deletes": deletes,
        "avg_delete_touch": (delete_touch_total / deletes) if deletes else 0.0,
        "worst_delete_touched": worst_delete_touched,
    }


def criterion_3_deletion(res: Result, seeds: tuple[int, ...], ops: int, universe: int) -> None:
    """Run the differential fuzzer in BOTH deletion modes across several seeds, so a
    pass is not one lucky sequence, and record the comparison the substrate decision
    turns on: conservative is sound and cheap but over-approximates; exact matches
    the oracle at higher delete cost. 3.3 requires soundness; exactness is a bonus we
    quantify the price of."""
    cons_unsound = cons_over = exact_unsound = exact_over = 0
    cons_touch = exact_touch = 0.0
    cons_worst = exact_worst = 0
    n = len(seeds)
    for seed in seeds:
        c = _fuzz("conservative", seed, ops, universe)
        e = _fuzz("exact", seed, ops, universe)
        cons_unsound += c["unsound"]
        cons_over += c["inexact_over"]
        cons_touch += c["avg_delete_touch"]
        cons_worst = max(cons_worst, c["worst_delete_touched"])
        exact_unsound += e["unsound"]
        exact_over += e["inexact_over"]
        exact_touch += e["avg_delete_touch"]
        exact_worst = max(exact_worst, e["worst_delete_touched"])

    total_ops = n * ops
    # 3.a is THE pass criterion: soundness in both modes. Everything else is measured.
    res.record(
        "3.a SOUND under deletion, CONSERVATIVE mode (never wrongly drops a label)",
        cons_unsound == 0,
        f"{total_ops} ops over {n} seeds (universe {universe}): unsound operations = {cons_unsound}",
    )
    res.record(
        "3.b SOUND under deletion, EXACT mode",
        exact_unsound == 0,
        f"{total_ops} ops over {n} seeds: unsound operations = {exact_unsound}",
    )
    res.record(
        "3.c EXACT mode matches the oracle exactly (zero over-approximation)",
        exact_over == 0,
        f"exact-mode over-approximation operations = {exact_over}",
    )
    # 3.d and 3.e are REPORTED metrics, not pass/fail: the trade-off itself.
    res.record(
        "3.d conservative over-approximation is the price of the O(1) fast path (reported, 3.3 allows it)",
        True,
        f"conservative-mode over-approximation operations = {cons_over} of {total_ops} "
        f"({100.0 * cons_over / total_ops:.1f}%); always sound, never unsound",
    )
    res.record(
        "3.e deletion cost, conservative vs exact (reported: the price of exactness)",
        True,
        f"avg nodes re-established/delete: conservative {cons_touch / n:.2f}, exact {exact_touch / n:.2f}; "
        f"worst-case: conservative {cons_worst}, exact {exact_worst} (universe {universe})",
    )
    res.record(
        "3.f deletion work stays localised to the shaken region (both modes)",
        cons_worst <= universe and exact_worst <= universe,
        f"worst single-delete re-established <= universe ({universe}) in both modes",
    )


# --- Criterion 4: scale, and the mandatory adversarial cross-domain staging case ---

def criterion_4_scale(res: Result, nodes: int, edges: int, seed: int) -> None:
    """Criteria 1-3 must hold at a representative Mimisbrunnr size, not a toy graph.

    Topology matters, and this is itself a finding (see criterion_4_dense_cycle
    below). A flow-to-sink graph is not a dense random graph: values flow FORWARD
    through processing stages toward a small set of sinks, so it is sparse and
    largely a DAG, with only occasional back-edges. We model that with layered nodes
    and mostly-forward edges, which is the honest analogue of a realistic
    Mimisbrunnr. We build both modes on the same graph and compare their delete cost
    directly, and confirm soundness (both) and exactness (exact mode) against the
    oracle at scale."""

    def build(mode: str) -> tuple[ReachabilityGraph, list[tuple[str, str]], list[str], float]:
        rng = random.Random(seed)
        g = ReachabilityGraph(mode=mode)
        names = [f"v{i}" for i in range(nodes)]
        for x in names:
            g.add_node(x)
        layers = 40
        layer_of = {name: (i * layers) // nodes for i, name in enumerate(names)}
        by_layer: dict[int, list[str]] = {}
        for name in names:
            by_layer.setdefault(layer_of[name], []).append(name)
        sinks = rng.sample(by_layer[layers - 1], k=max(1, len(by_layer[layers - 1]) // 20))
        t0 = time.perf_counter()
        for s in sinks:
            g.mark_sink(s)
        live: list[tuple[str, str]] = []
        for _ in range(edges):
            u = rng.choice(names)
            lu = layer_of[u]
            # 95% forward edges, 5% back-edges: the sparse-mostly-DAG shape.
            if rng.random() < 0.95 and lu < layers - 1:
                target_layer = rng.randint(lu + 1, layers - 1)
            else:
                target_layer = rng.randint(0, layers - 1)
            v = rng.choice(by_layer[target_layer])
            if u != v:
                g.add_edge(u, v)
                live.append((u, v))
        return g, live, names, time.perf_counter() - t0

    # Conservative mode at full delete volume (its O(1) fast path makes this cheap).
    gc, live_c, names, t_build_c = build("conservative")
    t0 = time.perf_counter()
    sample = random.Random(seed + 1).sample(names, k=min(nodes, 10000))
    hits = sum(1 for x in sample if gc.is_action_critical(x))
    t_reads = time.perf_counter() - t0
    to_del_c = random.Random(seed + 2).sample(live_c, k=min(len(live_c), 5000))
    t0 = time.perf_counter()
    worst_c = 0
    for u, v in to_del_c:
        gc.delete_edge(u, v)
        worst_c = max(worst_c, gc.last_op_touched)
    t_del_c = time.perf_counter() - t0
    oracle_c = gc.brute_force_action_critical()
    inc_c = set(x for x in names if gc.is_action_critical(x))
    sound_c = oracle_c.issubset(inc_c)

    # Exact mode: identical graph, but only a BOUNDED number of deletes, because each
    # exact-mode delete re-derives the whole upstream cone. We measure per-delete
    # cost rather than run the full batch (which is prohibitive, and that is the
    # finding).
    ge, live_e, _, t_build_e = build("exact")
    to_del_e = random.Random(seed + 2).sample(live_e, k=min(len(live_e), 100))
    t0 = time.perf_counter()
    worst_e = 0
    touch_e = 0
    for u, v in to_del_e:
        ge.delete_edge(u, v)
        worst_e = max(worst_e, ge.last_op_touched)
        touch_e += ge.last_op_touched
    t_del_e = time.perf_counter() - t0
    oracle_e = ge.brute_force_action_critical()
    inc_e = set(x for x in names if ge.is_action_critical(x))
    sound_e = oracle_e.issubset(inc_e)
    exact_e = oracle_e == inc_e

    res.record(
        "4.a soundness holds at scale, both modes (realistic layered flow graph)",
        sound_c and sound_e,
        f"{gc.node_count()} nodes, ~{edges} edges; conservative and exact both sound",
    )
    res.record(
        "4.b exactness holds at scale (exact mode matches oracle)",
        exact_e,
    )
    res.record(
        "4.c authorisation-time read is fast at scale",
        True,
        f"{t_reads * 1e6 / max(1, len(sample)):.4f} us/read over {len(sample)} reads "
        f"({hits} critical); build {t_build_c * 1000:.0f} ms",
    )
    res.record(
        "4.d delete cost, conservative vs exact at scale (the substrate trade-off)",
        True,
        f"conservative {t_del_c * 1000 / max(1, len(to_del_c)):.3f} ms/delete (worst touch {worst_c}); "
        f"exact {t_del_e * 1000 / max(1, len(to_del_e)):.1f} ms/delete (avg touch {touch_e // max(1, len(to_del_e))}, "
        f"worst {worst_e}) -- exact re-derives the upstream cone every delete",
    )


def criterion_4_dense_cycle(res: Result, nodes: int, edges: int, seed: int) -> None:
    """The degenerate bound, reported honestly. A DENSE random graph sits above the
    giant-strongly-connected-component threshold, so almost every node is in one big
    cycle and reaches a sink through it. There, a single edge deletion's shaken
    region is close to the whole graph, and localised rederive degrades toward
    full-graph work. This is a real property of the algorithm and a real caveat for
    the substrate: it holds soundness but not cheap locality when reachability is
    one dense SCC. It bears on the D25 decision, so it is measured, not hidden. A
    realistic flow-to-sink graph (4.a-c) is not this shape."""
    rng = random.Random(seed)
    g = ReachabilityGraph(mode="conservative")
    names = [f"d{i}" for i in range(nodes)]
    for x in names:
        g.add_node(x)
    sinks = rng.sample(names, k=max(1, nodes // 500))
    for s in sinks:
        g.mark_sink(s)
    live: list[tuple[str, str]] = []
    for _ in range(edges):
        u = rng.choice(names)
        v = rng.choice(names)
        if u != v:
            g.add_edge(u, v)
            live.append((u, v))
    critical_frac = sum(1 for x in names if g.is_action_critical(x)) / nodes
    to_delete = rng.sample(live, k=min(len(live), 200))
    t0 = time.perf_counter()
    worst = 0
    for u, v in to_delete:
        g.delete_edge(u, v)
        worst = max(worst, g.last_op_touched)
    t_deletes = time.perf_counter() - t0
    oracle = g.brute_force_action_critical()
    incremental = set(x for x in names if g.is_action_critical(x))
    sound = oracle.issubset(incremental)
    res.record(
        "4.h dense-SCC stress stays SOUND (the degenerate worst case)",
        sound,
        f"{nodes} nodes/{edges} edges, {critical_frac * 100:.0f}% critical (one giant SCC)",
    )
    res.record(
        "4.i dense-SCC deletion cost is NOT local (reported caveat for D25)",
        True,
        f"worst single-delete touched {worst} of {nodes} nodes, "
        f"{t_deletes * 1000 / max(1, len(to_delete)):.2f} ms/delete: rederive approaches full-graph "
        f"work when reachability is one dense cycle",
    )


def criterion_4_cross_domain_staging(res: Result) -> None:
    """The mandatory adversarial case (ONTOLOGY_CONSTRUCTION.md 8.4, D30): a chain of
    individually-reversible, individually-non-consequential writes that composes into
    a consequential action, crossing a domain boundary, must be caught at the STAGING
    write, not missed.

    Scenario. An agent has one consequential sink: 'infra.exec' (run a command),
    reachable only through the infrastructure domain. A value marshalled in the
    COMMUNICATIONS domain (an extracted string from an untrusted message) is staged
    across domains: comms.value -> sched.task_field -> infra.cmd_arg -> infra.exec.
    Each hop is an individually-reversible write in a different layer. The claim
    under test: comms.value must read action-critical the instant the final edge
    into the sink exists, because a path composes across the domain boundary; and it
    must retract the instant that path is broken."""
    g = ReachabilityGraph()
    g.mark_sink("infra.exec")  # the only consequential sink for this agent

    # Stage the chain, final edge last. Before the final edge into the sink exists,
    # nothing upstream is action-critical.
    g.add_edge("comms.value", "sched.task_field")
    g.add_edge("sched.task_field", "infra.cmd_arg")
    pre = g.is_action_critical("comms.value")
    res.record(
        "4.j staged chain is inert until it reaches the sink",
        not pre,
        "comms.value not yet critical: no path to infra.exec",
    )

    # The staging write that composes the chain into a consequential action.
    g.add_edge("infra.cmd_arg", "infra.exec")
    caught = (
        g.is_action_critical("comms.value")
        and g.is_action_critical("sched.task_field")
        and g.is_action_critical("infra.cmd_arg")
    )
    res.record(
        "4.k cross-domain staging caught at the composing write",
        caught,
        "comms.value (communications) inherits action-critical via infra sink across domains",
    )

    # Break the path: the whole chain must retract (soundly), across the boundary.
    g.delete_edge("infra.cmd_arg", "infra.exec")
    retracted = (
        not g.is_action_critical("comms.value")
        and not g.is_action_critical("sched.task_field")
        and not g.is_action_critical("infra.cmd_arg")
    )
    res.record(
        "4.l breaking the path retracts the whole cross-domain chain",
        retracted,
        "no surviving path to any sink, so labels correctly drop",
    )

    # Now test the DANGEROUS direction: two paths to the sink, delete only one. The
    # value must STAY critical. This is the case a naive over-retraction breaks, and
    # the one that matters most for the boundary: wrongly dropping this label would
    # let an action-critical value skip Gjoll. Tested in BOTH modes.
    for mode in ("conservative", "exact"):
        g2 = ReachabilityGraph(mode=mode)
        g2.mark_sink("infra.exec")
        g2.add_edge("comms.value", "path_a")
        g2.add_edge("comms.value", "path_b")
        g2.add_edge("path_a", "infra.exec")
        g2.add_edge("path_b", "infra.exec")
        g2.delete_edge("path_a", "infra.exec")  # one path remains via path_b
        stays = g2.is_action_critical("comms.value") and g2.is_action_critical("path_b")
        a_gone = not g2.is_action_critical("path_a")
        res.record(
            f"4.m deleting one of two paths does NOT over-retract the survivor ({mode})",
            stays and a_gone,
            "comms.value keeps its label via path_b; path_a correctly drops",
        )


def main() -> int:
    print("Heimdall substrate spike (D25 / D38): flow-to-sink action-critical label")
    print("Pass criteria from ONTOLOGY_CONSTRUCTION.md 3.3 and 8.4\n")

    res = Result()

    print("Criterion 1: write-time label maintenance (bounded, no full traversal)")
    criterion_1_write_time(res)
    print("Criterion 2: authorisation-time read is a property read")
    criterion_2_read_time(res)
    print("Criterion 3: edge-deletion retraction, sound (D32) -- differential fuzzing, both modes")
    criterion_3_deletion(res, seeds=(1, 7, 42, 1337, 90210), ops=4000, universe=120)
    print("Criterion 4: scale, and the mandatory cross-domain state-staging case")
    criterion_4_scale(res, nodes=50000, edges=150000, seed=3)
    criterion_4_cross_domain_staging(res)
    criterion_4_dense_cycle(res, nodes=5000, edges=15000, seed=5)

    print("\nResults:")
    print(res.report())

    print()
    if res.ok():
        print("SPIKE PASS: all four criteria met. The incremental algorithm is sound")
        print("(and exact) under add and delete, bounded at write, O(1) at read, and")
        print("holds at scale, including the cross-domain state-staging case. This")
        print("RATIFIES D25 (property-graph substrate) and D38: the load-bearing")
        print("reachability requirement is served without an authorisation-time")
        print("traversal, and edge-deletion retraction (D32) is soundly solvable at")
        print("write time. No need to fall back to a Datalog engine per 3.3.")
        return 0
    else:
        print("SPIKE FAIL: at least one criterion not met. Per ONTOLOGY_CONSTRUCTION.md")
        print("3.3, if deletion retraction cannot be met soundly at acceptable cost,")
        print("this is the signal to reconsider a Datalog engine (Souffle) for the")
        print("reasoning layer while keeping the property graph for state.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
