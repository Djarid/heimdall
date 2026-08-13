"""Integration test: Nornir and the Gjoll gate running over a LIVE Memgraph store.

The substrate spike proved the reachability algorithm on Memgraph (D57), and the gate
was proven over the in-memory graph (D58). But the two had never actually run together
THROUGH Nornir: Nornir always computed flow-to-sink with its in-memory backend. This
harness closes that last integration (D63). It runs the same batches through Nornir
twice, once with the default in-memory backend and once with the MemgraphFlowBackend,
and asserts:

- The action-critical set Nornir computes over the live store equals the in-memory
  result (the in-memory backend is the oracle, as in the spike's differential test).
- The Gjoll gate, fed the store-computed labels, still blocks an unsafe wiring before
  it fires, including a value staged through a multi-hop cross-domain chain.

OPTIONAL and skip-if-absent (D01): if Memgraph is unreachable (or the neo4j driver is
missing) it SKIPS with a clear message and returns success, so the core suite stays
dependency-free. Start Memgraph via podman to run it (see spike/README.md).

Run: /Users/jasonh/git/heimdall/poc/.venv/bin/python -m ontology.tests.memgraph_integration_harness
"""

from __future__ import annotations

import sys

from ontology.yggdrasil import load
from ontology.yggdrasil.control_surface import AgentContext
from ontology.nornir import Nornir, MarshalledAssertion
from ontology.nornir.flow_backends import MemgraphFlowBackend
from ontology.nornir.gjoll import ActionProposal, Actuator, enforce, CONSUME_INERT, CONSUME_ACTION


def _batches():
    """Return (label, agent, assertions) fixtures exercising cross-domain staging."""
    infra_agent = AgentContext(
        "agent-infra", permitted_actions=frozenset({"action:classify"}),
        trust_ceiling="TAINTED", consequential_sinks=frozenset({"sink:infra.exec"}),
    )
    staging = [
        MarshalledAssertion("comms.value", "taint:EXTERNAL_COMMS",
                            {"sender_extracted": "x@y", "subject_extracted": "ticket",
                             "requested_action_summary": "please run the deploy script now"},
                            flows=("sched.task",)),
        MarshalledAssertion("sched.task", "taint:EXTERNAL_COMMS",
                            {"subject_extracted": "scheduled task"}, flows=("sink:infra.exec",)),
    ]
    readonly = AgentContext("agent-readonly", consequential_sinks=frozenset())
    return [
        ("cross-domain-staging", infra_agent, staging),
        ("agent-scoped-inert", readonly, staging),
    ]


def main() -> int:
    print("Heimdall integration: Nornir + Gjoll over a LIVE Memgraph store")
    driver = MemgraphFlowBackend.connect()
    if driver is None:
        print("  [SKIP] Memgraph not reachable (or neo4j driver absent). Nornir's")
        print("  in-memory flow backend is the proven default; running it over the")
        print("  live store is optional. Start Memgraph via podman to run this.")
        print("  Skipping is not a failure.")
        return 0

    onto = load()
    nornir_mem = Nornir(onto)                                   # in-memory (oracle)
    nornir_store = Nornir(onto, flow_backend=MemgraphFlowBackend(driver))  # live store

    checks: list[tuple[str, bool, str]] = []

    for label, agent, assertions in _batches():
        r_mem = nornir_mem.run(assertions, agent=agent)
        r_store = nornir_store.run(assertions, agent=agent)
        same = set(r_mem.action_critical) == set(r_store.action_critical)
        checks.append((f"{label}: store action-critical set matches in-memory oracle",
                       same, f"store={sorted(r_store.action_critical)}"))

    # The gate over store-computed labels: the staged comms value, wired into the
    # infra sink as an ACTION, must be blocked before firing.
    label, agent, assertions = _batches()[0]
    r_store = nornir_store.run(assertions, agent=agent)
    by_id = {c.assertion_id: c for c in r_store.classified}
    actuator = Actuator()
    proposal = ActionProposal("exec", "sink:infra.exec",
                              {"comms.value": CONSUME_ACTION}, declared_safe=False)
    decision = enforce(proposal, by_id, agent.consequential_sinks, actuator)
    checks.append(("gate blocks the staged value (store-computed labels) before firing",
                   (not decision.authorised) and (not decision.fired) and not actuator.action_effects,
                   str(decision.reasons[:1])))

    # --- Cross-batch state staging (D64): the attack the per-batch backend misses ---
    # An attacker stages a value across TWO separate Nornir batches: batch 1 writes
    # comms.value -> ledger.txn with no sink in view; batch 2 writes ledger.txn ->
    # payment sink. Only the composed, cross-batch path reaches the sink. A per-batch
    # backend forgets batch 1, so it never marks comms.value action-critical. The
    # persistent store accumulates the graph, so the label propagates back to
    # comms.value when batch 2 completes the path.
    stager_agent = AgentContext(
        "agent-treasury", permitted_actions=frozenset({"action:classify"}),
        trust_ceiling="TAINTED", consequential_sinks=frozenset({"sink:pay"}),
    )
    batch1 = [MarshalledAssertion("comms.value", "taint:EXTERNAL_COMMS",
                                  {"sender_extracted": "x@y", "subject_extracted": "ticket",
                                   "requested_action_summary": "please note the new supplier account"},
                                  flows=("ledger.txn",))]
    batch2 = [MarshalledAssertion("ledger.txn", "taint:EXTERNAL_COMMS",
                                  {"subject_extracted": "transfer",
                                   "requested_action_summary": "wire transfer the funds"},
                                  flows=("sink:pay",))]

    # Per-batch backend (the current default over the store): run the two batches; the
    # staged value must NOT be marked critical, demonstrating the gap.
    perbatch = MemgraphFlowBackend(driver)  # persist=False
    n_perbatch = Nornir(onto, flow_backend=perbatch)
    n_perbatch.run(batch1, agent=stager_agent)
    n_perbatch.run(batch2, agent=stager_agent)
    perbatch_misses = not perbatch.is_action_critical("comms.value")  # no accumulated graph
    checks.append(("per-batch backend MISSES cross-batch staging (documents the gap)",
                   perbatch_misses, "comms.value not tracked across batches"))

    # Persistent backend (D64): same two batches, accumulated. The staged value MUST
    # become action-critical once batch 2 completes the path.
    persistent = MemgraphFlowBackend(driver, persist=True)
    persistent.reset()
    n_persist = Nornir(onto, flow_backend=persistent)
    n_persist.run(batch1, agent=stager_agent)
    n_persist.run(batch2, agent=stager_agent)
    staged_caught = persistent.is_action_critical("comms.value")
    checks.append(("persistent backend CATCHES cross-batch staging (D64)",
                   staged_caught, "comms.value action-critical after the path completes across batches"))

    # And the gate blocks it: re-read the staged value's label from the store at
    # action time and gate an action on it.
    actuator2 = Actuator()
    from ontology.nornir.assertions import ClassifiedAssertion
    staged_view = ClassifiedAssertion(
        assertion_id="comms.value", type_name="comms:instruction_to_act", actionable=False,
        trust_level="trust:TAINTED", taint_class="taint:EXTERNAL_COMMS", fields={},
        action_critical=persistent.is_action_critical("comms.value"),
    )
    prop2 = ActionProposal("pay", "sink:pay", {"comms.value": CONSUME_ACTION}, declared_safe=False)
    d2 = enforce(prop2, {"comms.value": staged_view}, stager_agent.consequential_sinks, actuator2)
    checks.append(("gate blocks the cross-batch-staged value before firing",
                   (not d2.authorised) and (not d2.fired) and not actuator2.action_effects,
                   str(d2.reasons[:1])))

    # Cleanup.
    try:
        with driver.session() as s:
            s.run("MATCH (n) DETACH DELETE n").consume()
        driver.close()
    except Exception:
        pass

    print("\nResults (live Memgraph, through Nornir):")
    ok = True
    for name, passed, detail in checks:
        mark = "PASS" if passed else "FAIL"
        if not passed:
            ok = False
        print(f"  [{mark}] {name}" + (f" -- {detail}" if detail else ""))

    print()
    if ok:
        print("INTEGRATION PASS: Nornir computes the action-critical set over a live")
        print("Memgraph store, matching the in-memory oracle, and the Gjoll gate blocks")
        print("an unsafe wiring on those store-computed labels before it fires. With a")
        print("persistent store (D64) it also catches CROSS-BATCH state staging that the")
        print("per-batch backend misses: a value staged across two separate batches")
        print("becomes action-critical once the path completes, and the gate blocks it.")
        return 0
    print("INTEGRATION FAIL: the store-backed run diverged. Detail above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
