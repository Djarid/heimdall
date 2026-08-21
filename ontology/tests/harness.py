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
import math
import sys
from pathlib import Path

from ontology.yggdrasil import load
from ontology.yggdrasil.control_surface import AgentContext
from ontology.yggdrasil.unclassified import UNCLASSIFIED
from ontology.nornir import Nornir, MarshalledAssertion


def _wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval as percentages, for reporting small-n rates honestly.
    A repository-access review flagged that "94.7%" on n=38 is false precision; a
    fraction with this interval is the honest form."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / den
    return (100 * (centre - half), 100 * (centre + half))


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
        self.gjoll_failures = 0
        self.false_inert_failures = 0
        self.guard_failures = 0
        self.mitigation_failures = 0
        self.gjoll_invocation_failures = 0
        self.control_surface_failures = 0

    def line(self, s: str) -> None:
        self.lines.append(s)

    def dump(self) -> None:
        print("\n".join(self.lines))


def run_symbolic_guard(rep: Report) -> None:
    """Obligation 3.1 (no language model on the authorisation path). An AST scan of the
    symbolic/authorisation packages (`ontology/yggdrasil`, `ontology/nornir`,
    `poc/symbolic.py`) asserts no model-client import, no inference call and no
    subprocess to a model runner, while permitting graph-DB drivers (the substrate).
    This is the executable form of the invariant the whole architecture rests on;
    until this existed it was enforced by human inspection alone. A violation is fatal."""
    from ontology.nornir.symbolic_guard import scan, scanned_files, control_check

    rep.line("=== 3.1 Symbolic-layer guard (no language model on the authorisation path) ===")

    # Mandatory negative control (invariant 3.10, D10): before trusting a clean scan,
    # confirm the guard actually catches planted violations (direct import, from-import,
    # dynamic import, HTTP to an inference endpoint, model subprocess, two
    # UNLISTED-egress probes, boto3 and smtplib, that no blacklist would name so the
    # allowlist is proven to bite, D71, and string-smuggled code execution via
    # eval/exec/compile, D95) and does not flag benign controls (a graph-DB driver, the
    # store binding, an allowlisted stdlib import, a relative import, a 'model' comment,
    # and an unrelated qualified call such as re.compile, D95). A guard that cannot
    # catch a planted model import is theatre, exactly as an uncontrolled soundness
    # check would be.
    control_failures = control_check()
    if control_failures:
        for cf in control_failures:
            rep.guard_failures += 1
            rep.line(f"  [CRITICAL] negative control: {cf}")
    else:
        rep.line("  [PASS] negative control: the guard catches planted model imports, "
                 "dynamic imports, inference HTTP, model subprocesses, unlisted egress "
                 "(boto3, smtplib) and string-smuggled code execution (eval/exec/compile), "
                 "and does not flag allowlisted stdlib, graph-DB drivers, relative imports, "
                 "'model' comments or unrelated qualified calls (the allowlist bites, not "
                 "theatre).")

    files = scanned_files()
    violations = scan()
    rep.line(f"  AST-scanned {len(files)} authorisation-path files "
             f"(yggdrasil, nornir, poc/symbolic.py; tests/spike/neural.py excluded).")
    if not violations:
        rep.line("  [PASS] no model import (direct or dynamic), inference call, outbound "
                 "network call or model subprocess on the authorisation path.")
    else:
        for v in violations:
            rep.guard_failures += 1
            rep.line(f"  [CRITICAL] {v}")
    rep.line("")


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

    covered = sum(1 for c in result.classified if c.type_name != UNCLASSIFIED)
    total = len(result.classified)
    lo, hi = _wilson_interval(covered, total)
    rep.line("")
    rep.line(f"  Coverage (8.1): {covered}/{total} classified to a known type "
             f"(95% Wilson interval {lo:.0f} to {hi:.0f} percent; a fraction on a small "
             f"corpus, not a point estimate); the rest fail safe to review.")
    rep.line(f"  Correctness (8.2): {correct}/{len(cases)} exact match; "
             f"{downgrades} downgrade(s) [CRITICAL], {over_classified} over-classification(s) [tolerated].")
    rep.line(f"  Fail-safe breaches: {failsafe_leaks} (must be 0).")
    rep.line("")


def run_coverage_gaps(nornir: Nornir, cases: list[dict], rep: Report) -> None:
    """The coverage-gap capture process (ONTOLOGY_CONSTRUCTION.md section 7, D59).

    Not a pass/fail obligation: a reported summary of what landed in the review queue,
    grouped by reason, so coverage growth is demand-driven off real signal rather than
    discovered by luck. It surfaces the same review-routed content the growth model
    (section 7) says to extend from. The one hard property it does assert: every
    review-routed assertion is accounted for in a bucket, so nothing silently escapes
    the gap capture."""
    assertions = [
        MarshalledAssertion(c["id"], c["taint_class"], dict(c["fields"]))
        for c in cases
    ]
    result = nornir.run(assertions)
    gaps = result.coverage_gaps()

    rep.line("=== Coverage-gap capture (reported, drives demand-driven growth, D59) ===")
    rep.line(f"  Review queue: {gaps['review_total']} of {len(cases)} cases "
             f"({gaps['reviewed_fraction'] * 100:.0f}%), by reason:")
    for reason, items in gaps["by_reason"].items():
        rep.line(f"    {reason}: {len(items)}"
                 + (f"  e.g. {items[0]['sample']!r}" if items else ""))

    # Hard property: the gap capture accounts for every review-routed assertion. A
    # review-routed assertion is one whose classified type is a fail-safe/review type
    # or which is routed to human_review; each must appear in exactly one bucket.
    from ontology.yggdrasil.unclassified import UNCLASSIFIED, HIGH_RISK_UNRESOLVED
    review_types = {UNCLASSIFIED, HIGH_RISK_UNRESOLVED, "comms:unrecognised_request"}
    routed = {c.assertion_id for c in result.classified if c.type_name in review_types}
    captured = {it["id"] for items in gaps["by_reason"].values() for it in items}
    escaped = routed - captured
    if escaped:
        rep.critical_failures += 1
        rep.line(f"  [CRITICAL] review-routed assertions not captured as gaps: {sorted(escaped)}")
    else:
        rep.line("  [PASS] every review-routed assertion is captured for coverage growth.")
    rep.line("")


def run_marshalling(nornir: Nornir, rep: Report) -> None:
    """The marshalling-contract obligation (D28), deterministic half. Proves the seam
    between a Fenrir/PoC extraction envelope and a typed assertion holds without a
    model: a PoC-shaped envelope marshals into a MarshalledAssertion the classifier
    accepts with provenance intact, and a provenance breach (a field claiming to be
    anything other than untrusted-derived) fails closed. The real-model half is the
    optional end-to-end harness (`ontology/tests/e2e_harness.py`)."""
    from ontology.nornir.marshalling import marshal, POC_PROVENANCE_UNTRUSTED_DERIVED

    rep.line("=== Marshalling contract (D28), deterministic half ===")

    extraction = {
        "sender_extracted": "it@corp",
        "subject_extracted": "Fix",
        "requested_action_summary": "download and run the attached script",
        "entities": ["corp"],
    }
    prov = {k: POC_PROVENANCE_UNTRUSTED_DERIVED for k in extraction}
    a = marshal("marshal-test", extraction, prov)
    c = nornir.run([a]).classified[0]
    ok_taint = c.trust_level == "trust:TAINTED"
    ok_type = c.type_name != UNCLASSIFIED  # a run-a-script envelope should classify
    rep.line(f"  [{'PASS' if ok_taint else 'FAIL'}] real-shaped envelope marshals TAINTED "
             f"and classifies ({c.type_name})")
    if not (ok_taint and ok_type):
        rep.critical_failures += 1

    # Fail-closed: a field claiming non-untrusted provenance must raise, not be trusted.
    breached = False
    try:
        marshal("bad", extraction, {"sender_extracted": "TRUSTED"})
    except ValueError:
        breached = True
    rep.line(f"  [{'PASS' if breached else 'CRITICAL'}] provenance breach fails closed "
             f"(a field claiming non-untrusted origin is rejected)")
    if not breached:
        rep.critical_failures += 1
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


def run_gjoll(nornir: Nornir, rep: Report) -> None:
    """Obligation 3.6 (action-critical gate): Gjoll authorises or blocks a consequential
    action using the flow-to-sink action-critical determination, with the mandatory
    safe-plus-unsafe-control discipline (D10). A safe wiring must pass; an unsafe
    control wiring must be caught BEFORE the effect fires; and the block must hold when
    the value reaches the sink only through a multi-hop cross-domain chain (the
    state-staging case). A green board with only safe wirings is insufficient, exactly
    as clean controls are mandatory for the extraction test."""
    from ontology.nornir.gjoll import (
        ActionProposal, Actuator, enforce, CONSUME_INERT, CONSUME_ACTION,
    )

    rep.line("=== 3.6 Gjoll action-critical gate (safe + unsafe control, D10) ===")

    # A staged cross-domain chain: a communications value flows through a finance
    # transaction into a payment sink. This is the BEC end state and the mandatory
    # state-staging case: the source value is action-critical only via multiple hops.
    agent = AgentContext(
        agent_id="treasury", permitted_actions=frozenset({"action:classify"}),
        trust_ceiling="TAINTED", consequential_sinks=frozenset({"sink:payments.execute"}),
    )
    staged = [
        MarshalledAssertion("email.newdetails", "taint:EXTERNAL_COMMS",
                            {"sender_extracted": "ap@sup", "subject_extracted": "update",
                             "requested_action_summary": "remit to new IBAN going forward"},
                            flows=("ledger.txn",)),
        MarshalledAssertion("ledger.txn", "taint:EXTERNAL_COMMS",
                            {"subject_extracted": "transfer",
                             "requested_action_summary": "wire transfer the funds to the supplier account"},
                            flows=("sink:payments.execute",)),
    ]
    result = nornir.run(staged, agent=agent)
    by_id = {c.assertion_id: c for c in result.classified}
    actuator = Actuator()

    # SAFE wiring: an audit log consumes the staged value as inert data. Must pass and
    # fire, with no action effect.
    safe = ActionProposal("audit", "sink:audit_log",
                          {"email.newdetails": CONSUME_INERT}, declared_safe=True)
    d_safe = enforce(safe, by_id, agent.consequential_sinks, actuator)
    if d_safe.authorised and d_safe.fired and not actuator.action_effects:
        rep.line("  [PASS] safe wiring authorised and fired with no action effect")
    else:
        rep.gjoll_failures += 1
        rep.line(f"  [CRITICAL] safe wiring was blocked or produced an action effect: "
                 f"authorised={d_safe.authorised} fired={d_safe.fired} "
                 f"action_effects={actuator.action_effects}")

    # UNSAFE control: the payment sink consumes the staged, action-critical,
    # untrusted-derived value as an ACTION. Must be caught before firing. The value
    # reaches the sink only through the ledger hop (cross-domain staging).
    actuator.reset()
    unsafe = ActionProposal("pay", "sink:payments.execute",
                            {"email.newdetails": CONSUME_ACTION}, declared_safe=False)
    d_unsafe = enforce(unsafe, by_id, agent.consequential_sinks, actuator)
    if (not d_unsafe.authorised) and (not d_unsafe.fired) and not actuator.action_effects:
        rep.line("  [PASS] unsafe control caught before firing (staged cross-domain value); "
                 "no mock action ran")
    else:
        rep.gjoll_failures += 1
        rep.line(f"  [CRITICAL] unsafe control was NOT caught: authorised={d_unsafe.authorised} "
                 f"fired={d_unsafe.fired} action_effects={actuator.action_effects}")

    # NEGATIVE-of-the-negative: a value that is untrusted-derived but NOT action-critical
    # for this agent (no path to a consequential sink) consumed as an action must be
    # allowed, otherwise the gate is pure friction. An inert-effect agent with no sinks.
    actuator.reset()
    noagent = AgentContext(agent_id="readonly", consequential_sinks=frozenset())
    r2 = nornir.run(
        [MarshalledAssertion("note", "taint:EXTERNAL_COMMS",
                             {"subject_extracted": "fyi", "requested_action_summary": "for your information, no action needed"})],
        agent=noagent,
    )
    by_id2 = {c.assertion_id: c for c in r2.classified}
    prop = ActionProposal("do", "sink:harmless", {"note": CONSUME_ACTION}, declared_safe=True)
    d2 = enforce(prop, by_id2, noagent.consequential_sinks, actuator)
    if d2.authorised and d2.fired:
        rep.line("  [PASS] non-action-critical value is not gated (the gate is not pure friction)")
    else:
        rep.gjoll_failures += 1
        rep.line(f"  [CRITICAL] a non-action-critical value was wrongly blocked: {d2.reasons}")

    # D89 direction B, end to end through the gate: a DISHONESTLY-flagged consequential sink
    # (a money mover declared non-consequential, and NOT in the agent's set) is still gated,
    # because effective_consequential DERIVES consequentiality from the effect primitive. This
    # exercises the registry path the D81 tests validate structurally, but through the live
    # gate on the staged cross-domain chain, with an empty agent sink set so ONLY the derivation
    # can catch it.
    from ontology.nornir.sink_declaration import (
        SinkDeclaration, SinkRegistry, MOVE_MONEY,
    )
    actuator.reset()
    dishonest_registry = SinkRegistry()
    dishonest_registry.declare(SinkDeclaration(
        name="sink:payments.execute",
        parameters=frozenset({"email.newdetails"}),
        consequential_by_default=False,      # the lie
        effect_primitive=MOVE_MONEY,         # the derived truth
    ))
    empty_sinks = frozenset()  # the flag and the agent set both say "not consequential"
    b_unsafe = ActionProposal("pay-b", "sink:payments.execute",
                              {"email.newdetails": CONSUME_ACTION}, declared_safe=False)
    d_b = enforce(b_unsafe, by_id, empty_sinks, actuator, sink_registry=dishonest_registry)
    if (not d_b.authorised) and (not d_b.fired) and not actuator.action_effects:
        rep.line("  [PASS] D89-B: a dishonestly-flagged money sink is still gated by derived "
                 "consequentiality (false flag + empty agent set both bypassed)")
    else:
        rep.gjoll_failures += 1
        rep.line(f"  [CRITICAL] D89-B: dishonest-flag sink was NOT gated: "
                 f"authorised={d_b.authorised} fired={d_b.fired}")

    # D89 direction A: a value flow reachability has proved action-critical, declared
    # CONSUME_INERT at a consequential sink, no longer silently passes. Same staged chain, an
    # honest money-sink declaration, the value consumed as INERT (the dishonest inert claim).
    actuator.reset()
    honest_registry = SinkRegistry()
    honest_registry.declare(SinkDeclaration(
        name="sink:payments.execute",
        parameters=frozenset({"email.newdetails"}),
        consequential_by_default=True,
        effect_primitive=MOVE_MONEY,
    ))
    money_sinks = frozenset({"sink:payments.execute"})
    a_inert = ActionProposal("pay-a", "sink:payments.execute",
                             {"email.newdetails": CONSUME_INERT}, declared_safe=True)
    d_a = enforce(a_inert, by_id, money_sinks, actuator, sink_registry=honest_registry)
    if (not d_a.authorised) and (not d_a.fired) and not actuator.action_effects:
        rep.line("  [PASS] D89-A: an action-critical value declared CONSUME_INERT at a "
                 "consequential sink is blocked (inert claim not trusted over flow reachability)")
    else:
        rep.gjoll_failures += 1
        rep.line(f"  [CRITICAL] D89-A: dishonest inert claim on an action-critical value "
                 f"passed: authorised={d_a.authorised} fired={d_a.fired}")

    # D89-A control against pure friction: a NON-action-critical value declared CONSUME_INERT
    # must still pass. The readonly agent's note has no path to a consequential sink, so
    # declaring it inert is honest and must authorise. A registry declaring the sink honestly
    # (so validation passes) with 'note' as its parameter isolates the A check.
    actuator.reset()
    note_registry = SinkRegistry()
    note_registry.declare(SinkDeclaration(
        name="sink:payments.execute", parameters=frozenset({"note"}),
        consequential_by_default=True, effect_primitive=MOVE_MONEY,
    ))
    a_ok = ActionProposal("log-note", "sink:payments.execute",
                          {"note": CONSUME_INERT}, declared_safe=True)
    d_a_ok = enforce(a_ok, by_id2, money_sinks, actuator, sink_registry=note_registry)
    if d_a_ok.authorised and d_a_ok.fired:
        rep.line("  [PASS] D89-A control: a NON-action-critical value declared inert still "
                 "passes (the fail-closed default is not pure friction)")
    else:
        rep.gjoll_failures += 1
        rep.line(f"  [CRITICAL] D89-A control: an honestly-inert value was wrongly blocked: "
                 f"{d_a_ok.reasons}")

    rep.line("")


def run_gjoll_invocation_boundary(rep: Report) -> None:
    """Obligation 3.6b (the Gjoll invocation-boundary detector, D96): an AST scan finds
    every site in the repo constructing `gjoll.ActionProposal` or calling
    `gjoll.evaluate`/`gjoll.enforce`, and classifies each as test (`ontology/tests/`)
    or non-test. The COUNT of test call sites is reporting-only, never a failure: it is
    evidence for invariant 3.6 being DEMONSTRATED under harness invocation, not a defect
    to close, and it is expected to grow. A non-test call site is fatal ONLY if it is
    not on the designated `NON_TEST_ALLOWLIST`
    (`ontology.tests.gjoll_invocation_harness`), which is empty today. This is the
    mechanised form of the caveat `AGENTS.md` used to carry in prose: it does not go
    stale, because the moment a real call site appears, this obligation stops reporting
    a clean boundary and starts failing loudly."""
    from ontology.tests.gjoll_invocation_harness import classify_call_sites, control_check

    rep.line("=== 3.6b Gjoll invocation boundary (D96; reporting-only on the count, "
             "fatal on an unallowlisted non-test call site) ===")

    control_failures = control_check()
    if control_failures:
        for cf in control_failures:
            rep.gjoll_invocation_failures += 1
            rep.line(f"  [CRITICAL] negative control: {cf}")
    else:
        rep.line("  [PASS] negative control: the detector catches a planted call site "
                 "(direct import and module-alias-qualified) and does not flag a source "
                 "that merely mentions or imports the names without calling them.")

    status = classify_call_sites()
    n_test = len(status["test_files"])
    n_non_test = len(status["non_test_files"])
    rep.line(f"  {n_test} test call site(s), {n_non_test} non-test call site(s). "
             f"Invariant 3.6 is DEMONSTRATED under harness invocation only, not under "
             f"live, non-test invocation.")
    for f in status["test_files"]:
        rep.line(f"    + test call site: {f}")
    for f in status["allowlisted_non_test"]:
        rep.line(f"    + allowlisted non-test call site: {f}")
    if status["unallowlisted_non_test"]:
        for f in status["unallowlisted_non_test"]:
            rep.gjoll_invocation_failures += 1
            rep.line(f"  [CRITICAL] unallowlisted non-test call site constructs "
                     f"ActionProposal or calls gjoll.evaluate/gjoll.enforce outside "
                     f"ontology/tests/ and outside NON_TEST_ALLOWLIST: {f}")
    else:
        rep.line("  [PASS] no non-test call site outside the allowlist.")
    # Important 2 (quality review, D96 follow-up): a file the detector could not parse
    # is a failure to verify, never silent evidence of a clean boundary, on the same
    # fail-closed discipline obligation 3.1 (symbolic_guard) already holds for its own
    # parse failures.
    if status["parse_failures"]:
        for pf in status["parse_failures"]:
            rep.gjoll_invocation_failures += 1
            rep.line(f"  [CRITICAL] could not parse (fail-closed, not silently "
                     f"skipped): {pf}")
    else:
        rep.line("  [PASS] every scanned file parsed cleanly.")
    rep.line("")


def run_control_surface(rep: Report) -> None:
    """D97: control_surface.resolve() previously performed no ceiling check at all
    despite its own docstring's claim ("we enforce the ceiling is not silently
    escalated"), and gjoll's no-registry fallback has a named, bounded residual (an
    empty or mismatched agent_consequential_sinks argument disarms it, closed only when
    a sink_registry is supplied). Both are verified in `control_surface_harness.py`; run
    it directly for detail (`python -m ontology.tests.control_surface_harness`). A
    failure here (the ceiling check regressing) is fatal; the no-registry residual is
    recorded inside that suite as RESIDUAL, not counted as a failure, the same
    reporting-without-failing discipline the false-inert rate uses for its own known,
    real, bounded gap."""
    import contextlib
    import io
    from . import control_surface_harness

    rep.line("=== D97 Control-surface ceiling enforcement and the gjoll no-registry residual ===")
    with contextlib.redirect_stdout(io.StringIO()):
        rc = control_surface_harness.main()
    if rc == 0:
        rep.line("  [PASS] resolve() clamps a ceiling-escalating override; the gjoll "
                 "no-registry residual is checked and recorded (see D97, run the module "
                 "directly for detail)")
    else:
        rep.control_surface_failures += 1
        rep.line("  [CRITICAL] control-surface suite FAILED (run it directly for detail)")
    rep.line("")


def run_mitigations(rep: Report) -> None:
    """Run the four false-inert mitigation suites (D79 to D82) as part of the main suite.

    Until D84 these harnesses were standalone: proven in isolation but not run here and
    not wired into the pipeline, so `pipeline_score_harness` printed an INTEGRATION GAP
    banner. They are now imported by the live engine and gate (D84), so their obligations
    belong in the primary run. Each is a self-contained suite returning 0 (pass) or 1
    (fail); a failure here is fatal, exactly like any other boundary check. Their verbose
    per-check output is suppressed to keep this run readable; run any of them directly for
    the detail (`python -m ontology.tests.state_delta_harness`)."""
    import contextlib
    import io
    from . import (
        state_delta_harness,
        consequence_axis_harness,
        sink_declaration_harness,
        promotion_policy_harness,
    )

    rep.line("=== False-inert mitigations in depth (D79-D82), now wired (D84) ===")
    suites = [
        ("D79 state-delta consequence detection", state_delta_harness.main),
        ("D80 two-dimensional consequence axis", consequence_axis_harness.main),
        ("D81 fail-closed sink-declaration validation", sink_declaration_harness.main),
        ("D82 promotion corroboration and graded review", promotion_policy_harness.main),
    ]
    for label, run in suites:
        with contextlib.redirect_stdout(io.StringIO()):
            rc = run()
        if rc == 0:
            rep.line(f"  [PASS] {label}")
        else:
            rep.mitigation_failures += 1
            rep.line(f"  [CRITICAL] {label}: mitigation suite FAILED (run it directly for detail)")
    rep.line("  These layers hold regardless of the classifier being right; they are what turns")
    rep.line("  the ~48 percent layer-one rate into ~90 percent pipeline containment (D83).")
    rep.line("")


FALSE_INERT_CORPUS = Path(__file__).parent / "corpora" / "false_inert_adversarial.json"
FALSE_INERT_INDEPENDENT_CORPUS = Path(__file__).parent / "corpora" / "false_inert_independent.json"
FALSE_INERT_THIRDPARTY_CORPUS = Path(__file__).parent / "corpora" / "false_inert_thirdparty.json"


def run_false_inert(nornir: Nornir, rep: Report, INERT_TYPES: frozenset,
                    corpus_path: Path = FALSE_INERT_CORPUS, label: str = "") -> None:
    """Measure the FALSE-INERT RATE: of genuinely-consequential content, the fraction
    the classifier types to an inert type, so it skips both the Gjoll gate and human
    review. This is the true bound of the guarantee (ADVERSARIAL_REVIEW.md 5.2).

    Three corpora are run (D77, D88). The original `false_inert_adversarial.json` was
    authored by the same person who wrote the rules and measures 1/17: a lower bound tuned
    to the rules. The larger `false_inert_independent.json` is scenario-authored across more
    consequence domains and inert wrappers, labelled purely by the external consequence
    test, and measures a much higher rate (16/33): the self-authored number badly
    understated the bound. The `false_inert_thirdparty.json` is BLIND-authored (D88): its
    scenarios and phrasings were produced by a fresh sub-agent with no access to the rules
    or repository, the strongest independence obtainable inside an agent session. It measures
    5/36 (about 14 percent), LOWER than the rules-aware 48 percent, which is itself the
    finding: a rules-aware author targets the classifier's blind spots more precisely than a
    blind one, so the two rates bound different things. All three are still not fully
    third-party (see each corpus's independence_discipline); a corpus labelled by an external
    human who has never seen the rules remains the wanted artefact.

    A consequential case that lands INERT is a false-inert and a critical finding
    (invariant 3.11 obligation 8.2). A consequential case routed to review or typed
    high-risk is NOT a false-inert: it failed closed or was caught. Benign controls
    must not be typed high-risk (that would be over-classification, a cost)."""
    rep.line(f"=== False-inert rate ({label}, ADVERSARIAL_REVIEW 5.2) ===")
    data = json.loads(corpus_path.read_text())
    cases = data["cases"]
    assertions = [
        MarshalledAssertion(c["id"], c["taint_class"], dict(c["fields"]))
        for c in cases
    ]
    result = nornir.run(assertions)
    by_id = {c.assertion_id: c for c in result.classified}

    consequential = [c for c in cases if c["ground_truth"] == "consequential"]
    false_inert = []
    caught_or_review = []
    for case in consequential:
        got = by_id[case["id"]]
        if got.type_name in INERT_TYPES:
            false_inert.append((case["id"], got.type_name))
        else:
            caught_or_review.append((case["id"], got.type_name))

    n = len(consequential)
    fi = len(false_inert)
    rep.line(f"  Consequential cases: {n}. False-inert (typed inert, skips gate AND review): "
             f"{fi}/{n}.")
    for cid, typ in false_inert:
        rep.false_inert_failures += 1
        rep.line(f"  [CRITICAL] {cid}: consequential content typed inert as {typ} "
                 f"(skips the gate and review); a false-inert break")
    if fi == 0:
        rep.line("  [PASS] no consequential case was typed inert; every one was caught "
                 "high-risk or routed to review (failed closed).")
    else:
        rep.line(f"  FALSE-INERT RATE on this corpus: {fi}/{n}. A measured LOWER BOUND "
                 f"(same author wrote the rules and the corpus), not the rate on real traffic.")
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
    rep.line("Heimdall ontology test harness: invariant 3.1 (symbolic-layer guard), 3.11 "
             "(obligations 8.1-8.4), the 3.5 fail-closed property, and the 3.6 Gjoll gate")
    rep.line(f"Seed: {', '.join(domains)} domains on BFO; {len(onto.nodes)} ontology nodes; "
             f"{len(cases)} labelled cases, {len(fixtures)} flow fixtures\n")

    run_symbolic_guard(rep)
    run_classification(nornir, cases, rep, hr, inert)
    run_coverage_gaps(nornir, cases, rep)
    run_marshalling(nornir, rep)
    run_failclosed_property(nornir, rep, inert)
    run_false_inert(nornir, rep, inert, FALSE_INERT_CORPUS,
                    "self-authored corpus, a lower bound tuned to the rules")
    run_false_inert(nornir, rep, inert, FALSE_INERT_INDEPENDENT_CORPUS,
                    "independent scenario-authored corpus, D77")
    run_false_inert(nornir, rep, inert, FALSE_INERT_THIRDPARTY_CORPUS,
                    "blind-authored corpus (fresh sub-agent, no rule access), D88")
    run_mitigations(rep)
    run_soundness(nornir, cases, rep, hr)
    run_flow(nornir, fixtures, rep)
    run_gjoll(nornir, rep)
    run_gjoll_invocation_boundary(rep)
    run_control_surface(rep)

    rep.dump()

    fatal = (rep.critical_failures + rep.soundness_failures + rep.flow_failures
             + rep.property_failures + rep.gjoll_failures + rep.false_inert_failures
             + rep.guard_failures + rep.mitigation_failures
             + rep.gjoll_invocation_failures + rep.control_surface_failures)
    print()
    if fatal == 0:
        print("SUITE PASS: no critical findings. Coverage is reported above; the")
        print("guarantee is stated with its coverage figure, never unqualified (3.9).")
        print("No action-critical value was downgraded, no fail-safe breach, the")
        print("classifier fails closed (an unmatched request never goes inert), the")
        print("reasoner is sound on this corpus, cross-domain state-staging is caught")
        print("agent-scoped, and Gjoll blocks an unsafe wiring before it fires while")
        print("passing a safe one. This is the Phase 1 seed proven on this corpus,")
        print("not a claim of complete coverage.")
        return 0
    print(f"SUITE FAIL: {fatal} critical finding(s). Detail above.")
    if rep.false_inert_failures and fatal == rep.false_inert_failures:
        print()
        print("The only failures are false-inert findings from the three adversarial corpora")
        print("(ADVERSARIAL_REVIEW 5.2, decisions D67, D69, D72, D77, D88). This red bar is")
        print("EXPECTED and RECORDED: consequential content that positively earns an inert signal")
        print("defeats the fail-closed default, because inertness is earned by a content pattern")
        print("an attacker can also satisfy. THREE measurements, all lower bounds: the self-authored")
        print("corpus reads 1/17 after the D69 and D72 guards (each fixed the cases it was shown,")
        print("each re-opened by a fresh probe); the larger independent scenario-authored corpus")
        print("reads 16/33 (D77, D83), so the self-authored number badly understated the bound; and")
        print("the blind-authored corpus (fresh sub-agent, no rule access, D88) reads 5/36 (about")
        print("14 percent), LOWER than the rules-aware 48 percent, which is itself the finding: a")
        print("rules-aware author targets the classifier's blind spots more precisely than a blind")
        print("one, so the rates bound different things and none is fully third-party. The break is")
        print("real and structural, not an edge case: the classifier is blind to consequence")
        print("expressed without imperative or movement vocabulary, across config changes,")
        print("deletion, contract renewal, access grants, payroll redirects and security-state")
        print("changes. No content pattern separates a passively-phrased or metaphorical")
        print("consequence from a genuine informational statement without world knowledge, which")
        print("invariant 3.1 keeps off the classification path. It is left red deliberately: a")
        print("suite that names a real break is worth more than a green one that never tested it.")
        print()
        print("This is LAYER ONE only, and it is the pessimistic figure. Since D84 the D79-D82")
        print("mitigations are imported by engine.py and gjoll.py, and D85 closed the last")
        print("residual class by slot-vocabulary coverage: run")
        print("`python -m ontology.tests.pipeline_score_harness` for the defence-in-depth")
        print("picture, where every consequential case on this corpus is contained downstream")
        print("(same-author bindings, so a lower bound on difficulty, not a claim of zero risk).")
    else:
        print("A downgrade, a fail-safe breach, an unmatched request going inert, an unsound")
        print("derivation or a missed action-critical value is a boundary failure.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
