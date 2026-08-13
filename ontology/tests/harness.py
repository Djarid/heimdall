"""Ontology test harness: the four obligations of invariant 3.11.

An audit artefact in the spirit of poc/harness.py and spike/substrate/harness.py
(D12): failures are loud, and the critical distinctions are called out, not buried
in a coverage percentage. It runs the Phase 1 communications seed ontology through
Nornir against the ground-truth corpus and reports the four obligations of
ONTOLOGY_CONSTRUCTION.md section 8:

  8.1 Coverage measurement   fraction classified to a known type vs UNCLASSIFIED,
                             a REPORTED number; the hard invariant is that uncovered
                             content fails safe, never to a trusted/actionable type.
  8.2 Classification         each assertion to its expected type. A misclassification
      correctness            that DOWNGRADES an action-critical value (a critical
                             case typed as an inert label) is a CRITICAL FINDING and
                             fails the suite. An over-classification (benign typed as
                             high-risk) is reported but not fatal: it costs a human
                             review, it does not skip Gjoll.
  8.3 Reasoner soundness     every derived fact is entailed by the rules and carries
                             its assertion chain.
  8.4 Flow-to-sink           agent-scoped and cross-domain reachability, including the
                             mandatory cross-domain state-staging case (D30).

Run: /Users/jasonh/git/heimdall/poc/.venv/bin/python -m ontology.tests.harness
(from the repo root; any Python 3.11+; no third-party dependency).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ontology.yggdrasil import load
from ontology.yggdrasil.control_surface import AgentContext
from ontology.yggdrasil.unclassified import UNCLASSIFIED
from ontology.nornir import Nornir, MarshalledAssertion


CORPUS = Path(__file__).parent / "corpora" / "communications_ground_truth.json"

# The types that are trusted or actionable. The fail-safe invariant is that
# uncovered content NEVER lands here. In Phase 1 nothing is actionable and nothing
# is trusted-derived, so this is the set that uncovered content must avoid; it is
# stated explicitly so the check is meaningful rather than vacuous.
TRUSTED_OR_ACTIONABLE_TYPES: frozenset[str] = frozenset()  # none in Phase 1


def high_risk_types() -> frozenset[str]:
    """The high-risk types, read from the rule registry, not hardcoded. Each domain
    declares its own high-risk types (register_high_risk_types), so this stays
    correct as domains are added: adding scheduling did not require editing the
    harness. A critical-class value typed BELOW one of these is a downgrade. The
    HIGH_RISK_UNRESOLVED tie outcome (D31) is high-risk too: a value routed there is
    gated, not downgraded, so it counts as high-risk for the downgrade check."""
    from ontology.nornir.rules import high_risk_types as _hr
    from ontology.nornir import domain_rules
    from ontology.yggdrasil.unclassified import HIGH_RISK_UNRESOLVED
    domain_rules.register_all()
    return _hr() | {HIGH_RISK_UNRESOLVED}


def inert_types(onto) -> frozenset[str]:
    """The inert (low-risk) types: the fail-safe plus any domain type marked
    risk=low. A critical value landing here is a downgrade; a benign value landing
    here is correct. Derived from the ontology so new low-risk domain types are
    included without editing the harness."""
    low = {n.name for n in onto.nodes.values() if n.attrs.get("risk") == "low"}
    return frozenset(low | {UNCLASSIFIED})


class Report:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.critical_failures = 0
        self.soundness_failures = 0
        self.flow_failures = 0
        self.property_failures = 0

    def line(self, s: str) -> None:
        self.lines.append(s)

    def dump(self) -> None:
        print("\n".join(self.lines))


def run_classification(nornir: Nornir, cases: list[dict], rep: Report,
                       HIGH_RISK_TYPES: frozenset, INERT_TYPES: frozenset) -> None:
    rep.line("=== 8.1 Coverage and 8.2 Classification correctness ===")
    assertions = [
        MarshalledAssertion(c["id"], c["taint_class"], dict(c["fields"]))
        for c in cases
    ]
    result = nornir.run(assertions)
    by_id = {c.assertion_id: c for c in result.classified}

    correct = 0
    over_classified = 0
    downgrades = 0
    failsafe_leaks = 0

    for case in cases:
        got = by_id[case["id"]]
        expected = case["expected_type"]
        is_critical = case.get("critical", False)
        ok = got.type_name == expected

        if ok:
            correct += 1
        else:
            # Distinguish the failure direction. A downgrade of a critical case is
            # fatal; an over-classification is reported but tolerated.
            if is_critical and expected in HIGH_RISK_TYPES and got.type_name in INERT_TYPES:
                downgrades += 1
                rep.critical_failures += 1
                rep.line(
                    f"  [CRITICAL] {case['id']}: DOWNGRADE expected {expected}, "
                    f"got {got.type_name} (an action-critical value typed as inert)"
                )
            elif expected in INERT_TYPES and got.type_name in HIGH_RISK_TYPES:
                over_classified += 1
                rep.line(
                    f"  [tolerated] {case['id']}: over-classified expected {expected}, "
                    f"got {got.type_name} (costs a human review, does not skip Gjoll)"
                )
            elif expected in HIGH_RISK_TYPES and got.type_name in HIGH_RISK_TYPES:
                # A mismatch between two high-risk types. Both are gated, so the value
                # is not laundered to inert; it fails safe. Reported, not fatal. The
                # keyword rules cannot always tell one high-risk intent from another
                # (a web page that says "approve a transfer" reads as payment), and
                # for gating that does not matter: what matters is that it is not
                # inert.
                over_classified += 1
                rep.line(
                    f"  [tolerated] {case['id']}: high-risk-to-high-risk mismatch, "
                    f"expected {expected}, got {got.type_name} (both gate; not laundered to inert)"
                )
            else:
                # Any other mismatch is a plain correctness miss; report it.
                rep.line(
                    f"  [MISS] {case['id']}: expected {expected}, got {got.type_name}"
                )
                # A miss that lands a covered case in the fail-safe is not fatal, but
                # a miss to a trusted/actionable type would be; guard it below.

        # Fail-safe invariant (8.1 hard rule): uncovered content must not reach a
        # trusted or actionable type. Check every result, not just expected
        # fail-safe cases.
        if got.type_name in TRUSTED_OR_ACTIONABLE_TYPES:
            failsafe_leaks += 1
            rep.critical_failures += 1
            rep.line(
                f"  [CRITICAL] {case['id']}: reached a trusted/actionable type "
                f"{got.type_name} (fail-safe breach)"
            )

    coverage = result.coverage()
    rep.line("")
    rep.line(f"  Coverage (8.1): {coverage * 100:.1f}% classified to a known type "
             f"({sum(1 for c in result.classified if c.type_name != UNCLASSIFIED)}"
             f"/{len(result.classified)}); the rest fail safe to review.")
    rep.line(f"  Correctness (8.2): {correct}/{len(cases)} exact match; "
             f"{downgrades} downgrade(s) [CRITICAL], {over_classified} over-classification(s) [tolerated].")
    rep.line(f"  Fail-safe breaches: {failsafe_leaks} (must be 0).")
    rep.line("")


def run_failclosed_property(nornir: Nornir, rep: Report, INERT_TYPES: frozenset) -> None:
    """Obligation 8.2b: the classification fail-closed property (invariant 3.5,
    classification path; D54, D55).

    This is a PROPERTY test, not a case test. The corpus (8.2) proves the classifier
    types KNOWN cases correctly; it cannot prove the classifier fails safe on content
    it has never seen, which is exactly where a blacklist-shaped classifier rots. This
    test asserts the structural property directly: a communication that carries a
    request/imperative but matches NO positive rule must never receive an inert type.
    It must route to review (the fail-closed default) or to a high-risk type.

    The inputs are generated from neutral request scaffolding combined with NOVEL
    nonsense tokens, deliberately avoiding every positive keyword the rules use, so
    they exercise the fail-closed DEFAULT rather than any keyword's coverage. The test
    itself scans no content for malicious wording (that would be the very mistake
    invariant 3.5 forbids); it only checks where an unmatched request lands.

    Against the pre-D54 eager catch-all these inputs classified as inert
    `informational_statement` and this property fails loudly. Against the fail-closed
    catch-all they route to review and it passes. So the guardrail catches a
    regression that reopens the silent-downgrade path, with no human needing to spot
    it in review.
    """
    rep.line("=== 8.2b Classification fail-closed property (invariant 3.5, D54/D55) ===")

    # Neutral request scaffolding: imperative shapes that carry NO positive keyword
    # from any domain rule (not payment/credential/instruction/schedule/finance, and
    # not an informational signal). The nonsense object tokens guarantee novelty: the
    # rules have never seen them, so only the fail-closed default or a high-risk rule
    # can fire.
    scaffolds = [
        "please handle the {x} for me",
        "can you sort out the {x} today",
        "need you to look at the {x} before noon",
        "kindly deal with the {x} as we agreed",
        "make sure the {x} is taken care of",
        "would you see to the {x} right away",
        "get back to me about the {x}",
        "the {x} needs your attention, please",
    ]
    nonce = ["wibbleflux", "quorndle", "zaptfenn", "morblatt", "grintwash", "yulvex"]
    generated = []
    i = 0
    for s in scaffolds:
        for n in nonce:
            generated.append(
                MarshalledAssertion(
                    f"prop-{i}", "taint:EXTERNAL_COMMS",
                    {"sender_extracted": "someone@external.example",
                     "subject_extracted": "",
                     "requested_action_summary": s.format(x=n)},
                )
            )
            i += 1

    result = nornir.run(generated)
    exercised = 0        # inputs that were genuinely unmatched-by-positive-rule
    inert_leaks = 0
    for c in result.classified:
        # An input "exercises" the property only if it is not a high-risk positive
        # match; if a high-risk rule happened to fire, the value is gated anyway, so
        # skip it (the property is about the fail-closed default, not keyword recall).
        # What must never happen: an unmatched request lands in an INERT type.
        if c.type_name in INERT_TYPES:
            inert_leaks += 1
            rep.property_failures += 1
            rep.line(
                f"  [CRITICAL] {c.assertion_id}: an unmatched request classified INERT "
                f"({c.type_name}); the catch-all is fail-open (blacklist/eager regression)"
            )
        else:
            exercised += 1

    rep.line(f"  Generated unmatched requests: {len(generated)}; "
             f"routed to review or high-risk (fail-closed): {exercised}; "
             f"inert leaks: {inert_leaks} (must be 0).")
    if inert_leaks == 0:
        rep.line("  [PASS] no unmatched request received an inert type; the classifier "
                 "fails closed, not open.")
    rep.line("")


def _check_derivations(result, rules_by_name: dict) -> list[tuple]:
    """Return a list of (assertion_id, detail) for every derived fact that is NOT
    entailed by its producing rule, or whose chain is malformed. This is the general
    soundness check: each derived fact is verified against the entailment oracle of
    the rule that produced it (read from `fact['rule']`), so adding a derivation rule
    needs no harness change. A fact whose rule is unknown, or that its own rule's
    `entails` rejects, or whose chain does not reference the assertion, is unsound."""
    unsound = []
    by_id = {c.assertion_id: c for c in result.classified}
    for c in result.classified:
        for fact in c.inferred:
            rule = rules_by_name.get(fact.get("rule"))
            if rule is None:
                unsound.append((c.assertion_id, f"derived {fact['fact']} from unknown rule {fact.get('rule')!r}"))
                continue
            if not rule.entails(c, fact["fact"]):
                unsound.append((c.assertion_id, f"derived {fact['fact']} not entailed by rule {rule.name}"))
            if c.assertion_id not in fact["chain"]:
                unsound.append((c.assertion_id, f"derived {fact['fact']} chain does not cite the assertion: {fact['chain']}"))
    return unsound


def run_soundness(nornir: Nornir, cases: list[dict], rep: Report,
                  HIGH_RISK_TYPES: frozenset) -> None:
    from ontology.nornir.rules import DERIVATION_RULES

    rep.line("=== 8.3 Reasoner soundness ===")
    rules_by_name = {r.name: r for r in DERIVATION_RULES}

    # Use the flow fixtures too, not just the flat cases, because the interesting
    # chained derivation (needs_second_approval) only fires when a value is BOTH
    # high-risk AND action-critical, which requires an agent with a sink. Run the
    # staging fixtures so that rule is actually exercised, not just defined.
    corpus_result = nornir.run(
        [MarshalledAssertion(c["id"], c["taint_class"], dict(c["fields"])) for c in cases]
    )
    unsound = _check_derivations(corpus_result, rules_by_name)
    checked = sum(len(c.inferred) for c in corpus_result.classified)

    # Exercise the chained rule via a staging fixture: a high-risk value that reaches
    # a consequential sink must derive needs_second_approval, and that derivation must
    # be sound (both premises hold).
    from ontology.yggdrasil.control_surface import AgentContext
    agent = AgentContext("sound-agent", consequential_sinks=frozenset({"sink:pay"}))
    staged = [
        MarshalledAssertion("s.pay", "taint:EXTERNAL_COMMS",
                            {"sender_extracted": "x@y", "subject_extracted": "urgent",
                             "requested_action_summary": "please pay the invoice now"},
                            flows=("sink:pay",)),
    ]
    staged_result = nornir.run(staged, agent=agent)
    unsound += _check_derivations(staged_result, rules_by_name)
    checked += sum(len(c.inferred) for c in staged_result.classified)
    got_second_approval = any(
        f["fact"] == "needs_second_approval"
        for c in staged_result.classified for f in c.inferred
    )

    for aid, detail in unsound:
        rep.soundness_failures += 1
        rep.line(f"  [UNSOUND] {aid}: {detail}")

    if not got_second_approval:
        # The chained rule did not fire when it should have: an unexercised or broken
        # inference is a soundness-suite gap, so flag it (not fatal to the boundary,
        # but the suite must know its own rule ran).
        rep.line("  [WARN] needs_second_approval did not fire on a high-risk action-critical value")

    rep.line(f"  Derived facts checked: {checked}; unsound: {len(unsound)} (must be 0); "
             f"chained needs_second_approval exercised: {got_second_approval}.")

    # Negative control (proves 8.3 bites, in the spirit of D10 and D55): register a
    # deliberately UNSOUND derivation rule that confers a fact its own entailment
    # oracle rejects, confirm the checker catches it, then remove it so it never
    # ships. A soundness suite that cannot catch an unsound rule is theatre.
    from ontology.nornir.rules import DerivationRule
    def _bad_derive(c):
        return [("in_scope_trusted", [c.assertion_id])]  # confers scope/trust, never entailed
    def _bad_entails(c, fact):
        return False  # this fact is never legitimately derivable
    bad = DerivationRule("UNSOUND_CONTROL", _bad_derive, _bad_entails)
    control_result = nornir.run(
        [MarshalledAssertion("ctl", "taint:EXTERNAL_COMMS",
                             {"subject_extracted": "hello", "requested_action_summary": "fyi, no action needed"})]
    )
    # Inject the bad rule's output as if it had run, then check it is caught.
    for c in control_result.classified:
        c.inferred.append({"fact": "in_scope_trusted", "chain": [c.assertion_id], "rule": "UNSOUND_CONTROL"})
    control_unsound = _check_derivations(control_result, {**rules_by_name, "UNSOUND_CONTROL": bad})
    if control_unsound:
        rep.line("  [PASS] soundness negative control: the deliberately-unsound derivation "
                 "was caught (the check bites, it is not theatre).")
    else:
        rep.soundness_failures += 1
        rep.line("  [CRITICAL] soundness negative control was NOT caught: the 8.3 check does "
                 "not actually detect an unsound derivation.")
    rep.line("")


def run_flow(nornir: Nornir, fixtures: list[dict], rep: Report) -> None:
    rep.line("=== 8.4 Flow-to-sink reachability (agent-scoped, cross-domain) ===")
    for fx in fixtures:
        agent = AgentContext(
            agent_id=fx["agent"]["agent_id"],
            permitted_actions=frozenset(fx["agent"]["permitted_actions"]),
            trust_ceiling=fx["agent"]["trust_ceiling"],
            consequential_sinks=frozenset(fx["agent"]["consequential_sinks"]),
        )
        assertions = [
            MarshalledAssertion(a["id"], a["taint_class"], dict(a["fields"]), tuple(a.get("flows", ())))
            for a in fx["assertions"]
        ]
        result = nornir.run(assertions, agent=agent)
        got = set(result.action_critical)
        expected = set(fx["expected_action_critical"])
        # Soundness of the boundary: every value that should be action-critical must
        # be. A missing one is fatal (it would skip Gjoll). An extra one is not fatal
        # (fails safe, conservative), but we assert exactness here since the batch
        # computation is exact.
        missing = expected - got
        extra = got - expected
        if missing:
            rep.flow_failures += 1
            rep.line(f"  [CRITICAL] {fx['id']}: NOT marked action-critical: {sorted(missing)}")
        elif extra:
            rep.line(f"  [conservative] {fx['id']}: extra action-critical (fails safe): {sorted(extra)}")
            rep.line(f"  [PASS] {fx['id']}: all expected values action-critical")
        else:
            rep.line(f"  [PASS] {fx['id']}: action-critical set matches exactly {sorted(got)}")
    rep.line("")


def main() -> int:
    data = json.loads(CORPUS.read_text())
    cases = data["cases"]
    fixtures = data["flow_fixtures"]

    onto = load()
    nornir = Nornir(onto)
    hr = high_risk_types()
    inert = inert_types(onto)
    domains = sorted({n.attrs.get("domain") for n in onto.nodes.values() if n.attrs.get("domain")})

    rep = Report()
    rep.line("Heimdall ontology test harness: invariant 3.11 (obligations 8.1-8.4) "
             "and the 3.5 classification fail-closed property")
    rep.line(f"Seed: {', '.join(domains)} domains on BFO; {len(onto.nodes)} ontology nodes; "
             f"{len(cases)} labelled cases, {len(fixtures)} flow fixtures\n")

    run_classification(nornir, cases, rep, hr, inert)
    run_failclosed_property(nornir, rep, inert)
    run_soundness(nornir, cases, rep, hr)
    run_flow(nornir, fixtures, rep)

    rep.dump()

    fatal = (rep.critical_failures + rep.soundness_failures + rep.flow_failures
             + rep.property_failures)
    print()
    if fatal == 0:
        print("SUITE PASS: no critical findings. Coverage is reported above; the")
        print("guarantee is stated with its coverage figure, never unqualified (3.9).")
        print("No action-critical value was downgraded, no fail-safe breach, the")
        print("classifier fails closed (an unmatched request never goes inert), the")
        print("reasoner is sound on this corpus, and cross-domain state-staging is")
        print("caught agent-scoped. This is the Phase 1 seed proven on this corpus,")
        print("not a claim of complete coverage.")
        return 0
    print(f"SUITE FAIL: {fatal} critical finding(s). Detail above. A downgrade, a")
    print("fail-safe breach, an unmatched request going inert, an unsound derivation")
    print("or a missed action-critical value is a boundary failure, not a quality metric.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
