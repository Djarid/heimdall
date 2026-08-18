"""Pipeline score: defence in depth, not the classifier alone.

Run from the repo root:

    python -m ontology.tests.pipeline_score_harness

Why this exists. The false-inert measurement (D67, D77) scores ONE layer: did Nornir type
consequential content as inert? That number is about 43 percent on the independent corpus, and
it is the right number for what it measures. But it is a poor proxy for the question anyone
actually cares about, which is whether a mis-classification leads to harm. The guarantee is a
property of the PIPELINE, and several layers sit between a mis-classification and an effect,
none of which depends on the classification being right:

  layer 1  classification (Nornir)          caught if typed high-risk or routed to review
  layer 2  state-delta detection (D79)      caught if it would change a declared consequential slot
  layer 3  consequence axis (D80)           caught if any signal occupies the axis, denying effective inertness
  layer 4  action-time gate (D78, D81)      caught if action-critical and consumed as an ACTION at a consequential sink
  layer 5  promotion policy (D82)           caught if promotion needs corroboration or a human
  layer 6  graded review (D82)              caught, weakly, if it still earns a place in the review queue

A case is a RESIDUAL PIPELINE BREAK only if it escapes every layer. This harness reports
where each consequential case is first caught, and what escapes everything.

## The honesty conditions, which matter more than the number

1. **This scores the DESIGNED pipeline, not the BUILT one.** Layers 2 to 5 consume structural
   inputs (a value bound to a typed slot, a flow edge to a declared sink, a provenance
   source). Today Fenrir produces interpretive summaries, and Mímisbrunnr does not exist, so
   those inputs are supplied here from each corpus case's `structural` block rather than
   derived from a live extraction. The score is therefore an upper bound on what the current
   code achieves and a realistic estimate of what the designed pipeline achieves once
   structural extraction and the store are real. It is not a claim about today's runtime.
2. **The bindings are scenario-derived, not outcome-derived.** Each `structural` block answers
   "what would this content actually do", by the same external consequence test that sets
   `ground_truth`, and was written without reference to which cases the classifier missed. The
   discipline is that a binding is added only when a declared consequential slot HONESTLY covers
   the effect; a slot is never invented to force a case's containment, which would be the
   circularity this measurement exists to avoid. D85 grew the slot vocabulary to cover the
   holder-of-record and entitlement-status class (the former D83 residual ind-41 to ind-43),
   because a change of who controls a registered asset, or whether a protection is active,
   passes the same external-effect test as the money and access slots. That is coverage growth
   (D60), not a keyword rule. A FRESH probe whose effect falls outside every declared slot could
   still re-open a residual; the honest limit is the slot vocabulary's breadth, which grows on
   demand, not a claim that the class is closed forever.
3. **Same-author caveat, inherited from D77.** The rules, the corpus and the bindings share
   one author, so both the 43 percent and this pipeline score are lower bounds on the true
   difficulty, not unbiased estimates.
4. **Layer 6 is deliberately counted separately.** Reaching a review queue is not containment,
   it is a human being given a chance. It is reported, but a case whose only catch is layer 6
   is called out rather than folded into the caught total.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from pathlib import Path

from ..nornir.assertions import MarshalledAssertion
from ..nornir.consequence_axis import (
    classify_two_dimensional,
    flow_to_sink_signal,
    state_delta_signal,
)
from ..nornir.engine import Nornir
from ..nornir.promotion_policy import (
    ReviewPriority,
    SourcedValue,
    evaluate_promotion,
    review_priority,
)
from ..nornir.sink_declaration import (
    CONSUME_ACTION,
    SinkDeclaration,
    SinkRegistry,
    effective_consequential,
)
from ..nornir.state_delta import ProposedFact, SlotRef, dict_oracle, evaluate
from ..yggdrasil.control_surface import AgentContext
from .harness import high_risk_types, inert_types, load

CORPUS = Path(__file__).parent / "corpora" / "false_inert_independent.json"
THIRDPARTY_CORPUS = Path(__file__).parent / "corpora" / "false_inert_thirdparty.json"

# The mitigation modules whose layers this harness scores, and the live pipeline modules that
# would have to call them for the score to describe the BUILT system rather than the designed
# one. Checked at run time rather than asserted in prose, so the warning below cannot go stale:
# the moment someone wires a mitigation in, this harness stops claiming it is unwired.
_MITIGATION_MODULES = ("state_delta", "consequence_axis", "sink_declaration", "promotion_policy")
_PIPELINE_MODULES = ("engine.py", "rules.py", "gjoll.py")


def integration_status() -> dict:
    """Detect which mitigation modules the live pipeline actually imports.

    Returns a mapping of mitigation module name to the list of pipeline modules importing it.
    An empty list means that layer is proven in isolation but is not in the runtime path, so
    its contribution to the score below is DESIGNED rather than built."""
    nornir = Path(__file__).resolve().parents[1] / "nornir"
    wired: dict = {m: [] for m in _MITIGATION_MODULES}
    for fname in _PIPELINE_MODULES:
        f = nornir / fname
        if not f.exists():
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module.split(".")[-1])
            elif isinstance(node, ast.Import):
                names.extend(a.name.split(".")[-1] for a in node.names)
            for n in names:
                if n in wired:
                    wired[n].append(fname)
    return wired


def print_integration_banner() -> bool:
    """Print the integration state. Returns True when every mitigation is wired in.

    This is the mechanism that makes the caveat self-maintaining. A future session does not
    have to remember that the mitigations are standalone: running this harness says so, and
    stops saying so once they are not."""
    wired = integration_status()
    unwired = [m for m, importers in wired.items() if not importers]
    if not unwired:
        print("INTEGRATION: every mitigation module is imported by the live pipeline, so the")
        print("score below describes the BUILT pipeline. Re-check that the main suite runs the")
        print("mitigation harnesses too, then the layer-one rate should move.")
        return True
    print("INTEGRATION GAP (detected live, not asserted): the following mitigation modules are")
    print("NOT imported by any of engine.py, rules.py or gjoll.py, so their layers below are")
    print("DESIGNED, not built, and the measured layer-one rate is unchanged by them:")
    for m in unwired:
        print(f"  - {m}.py")
    for m, importers in wired.items():
        if importers:
            print(f"  + {m}.py is wired into {', '.join(sorted(set(importers)))}")
    print("Closing this gap is task 1 in STATUS.md section 0. Until it is closed, quote the")
    print("pipeline score as the designed pipeline, never as the system's current behaviour.")
    return False

# The consequential sinks the scoring deployment arms, and their declarations. A real
# deployment declares these; here they are the fixture the flow-bearing cases point at.
SINKS = (
    "sink:payments.execute",
    "sink:exec.run",
    "sink:data.export",
    "sink:data.delete",
    "sink:orders.place",
)


def build_registry() -> SinkRegistry:
    r = SinkRegistry()
    for s in SINKS:
        r.declare(SinkDeclaration(name=s, parameters=frozenset({"value"}),
                                  consequential_by_default=True))
    return r


# A world state that already holds a benign value for every slot the corpus would change, so
# a delta is a real change rather than an artefact of an empty store.
def build_state(cases: list) -> dict:
    state = {}
    for c in cases:
        st = c.get("structural") or {}
        slot = st.get("slot")
        if slot:
            state[f"{slot['entity']}::{slot['slot']}"] = "existing-benign-value"
    return state


@dataclass
class CaseOutcome:
    case_id: str
    classified: str
    caught_at: "str | None" = None      # the first layer that caught it
    layers: list = field(default_factory=list)   # every layer that would catch it
    review: str = "none"

    @property
    def contained(self) -> bool:
        """Contained means caught by a layer that actually stops or gates the value.
        Layer 6 (review queue) is explicitly NOT containment."""
        return any(l != "6 graded review" for l in self.layers)


def score(nornir: Nornir, cases: list, INERT: frozenset, HIGH: frozenset) -> list:
    registry = build_registry()
    agent_sinks = frozenset(SINKS)

    # Since D84 the mitigations are WIRED INTO the engine, so this harness now reads the
    # engine's own runtime output for layers 1 to 3, 5 and 6 rather than reconstructing
    # them in parallel. That is the point of the wiring: the score describes what the
    # code actually produces. The Nornir under test is built with the same populated
    # state oracle, so a proposed value on an already-set consequential slot is a real
    # change, not an artefact of an empty store.
    oracle = dict_oracle(build_state(cases))
    engine = Nornir(nornir.onto, state_oracle=oracle)

    outcomes = []
    for case in cases:
        if case["ground_truth"] != "consequential":
            continue
        st = case.get("structural") or {}

        # Build the marshalled assertion WITH its structural bindings, exactly as a
        # structural extraction would hand it to Nornir.
        proposed = ()
        if st.get("slot"):
            proposed = (ProposedFact(
                SlotRef(st["slot"]["entity"], st["slot"]["slot"]), st.get("value", "")),)
        a = MarshalledAssertion(
            case["id"], case["taint_class"], dict(case["fields"]),
            flows=tuple(st.get("flows_to", ())),
            proposed_facts=proposed,
            source=st.get("source", ""),
        )
        res = engine.run([a], AgentContext(agent_id="scorer",
                                           consequential_sinks=agent_sinks))
        c = res.classified[0]
        typed = c.type_name or "(none)"
        out = CaseOutcome(case_id=case["id"], classified=typed)

        # --- layer 1: classification (engine output) --------------------------------
        if typed not in INERT:
            out.layers.append("1 classification")

        # --- layer 2: state-delta (engine consequence axis) -------------------------
        # A state-delta signal on the engine's consequence axis is the wired D79 result.
        delta_signal = any(r.startswith("state_delta:") for r in c.consequence_reasons)
        if delta_signal:
            out.layers.append("2 state-delta")

        # --- layer 3: consequence axis (engine effective_inert) ---------------------
        # The engine denied effective inertness for an inert speech-act type: the D80
        # override removal, rescuing a case the classifier typed inert. Counted as a
        # distinct catch only when the state-delta layer did not already claim it.
        if c.effective_inert is False and typed in INERT and not delta_signal:
            out.layers.append("3 consequence axis")

        # --- layer 4: action-time gate ----------------------------------------------
        if st.get("flows_to"):
            sink = st["flows_to"][0]
            if effective_consequential(sink, registry, agent_sinks) and c.action_critical:
                out.layers.append("4 action-time gate")

        # --- layer 5: promotion policy (engine promotions) --------------------------
        if st.get("slot"):
            key = SlotRef(st["slot"]["entity"], st["slot"]["slot"]).key()
            promo = res.promotions.get(key)
            if promo is not None and not promo.promoted:
                out.layers.append("5 promotion policy")

        # --- layer 6: graded review (engine review_priority) ------------------------
        out.review = c.review_priority or "none"
        if c.review_priority and c.review_priority != ReviewPriority.NONE.value:
            out.layers.append("6 graded review")

        out.caught_at = out.layers[0] if out.layers else None
        outcomes.append(out)
    return outcomes


def main() -> int:
    import sys
    thirdparty = "--thirdparty" in sys.argv[1:]
    corpus_path = THIRDPARTY_CORPUS if thirdparty else CORPUS
    data = json.loads(corpus_path.read_text())
    cases = data["cases"]
    onto = load()
    nornir = Nornir(onto)
    INERT = inert_types(onto)
    HIGH = high_risk_types()

    outcomes = score(nornir, cases, INERT, HIGH)
    n = len(outcomes)

    if thirdparty:
        print("Pipeline score: defence in depth over the BLIND-AUTHORED third-party corpus (D88)")
        print("HEAVIER CAVEAT than the default D77 run: the structural bindings this score depends")
        print("on (layers 2 to 5) were added by the D88 builder from the blind author's stated")
        print("consequence_domain, NOT by the blind author, so this pipeline score is designed")
        print("behaviour under same-author bindings even though the LAYER-1 classification input is")
        print("blind-authored. Quote the blind layer-1 rate (5/36) as the independent figure and")
        print("this pipeline score only as designed behaviour. See the corpus independence_discipline.")
    else:
        print("Pipeline score: defence in depth over the independent false-inert corpus")
    print("See the module docstring for the four honesty conditions before quoting any number")
    print("from this. Layers 2 to 5 also consume structural inputs (slot bindings, flow edges)")
    print("that Fenrir and Mimisbrunnr do not yet produce from a live extraction.")
    print()
    fully_wired = print_integration_banner()
    print()

    # The single-layer number, for contrast.
    false_inert = [o for o in outcomes if o.classified in INERT]
    headline = "the blind-authored D88 figure" if thirdparty else "the D77 headline"
    print(f"LAYER 1 ONLY ({headline}): false-inert {len(false_inert)}/{n} "
          f"({100*len(false_inert)//n} percent) typed inert by the classifier.")
    print()

    print("Where each consequential case is FIRST caught:")
    from collections import Counter
    first = Counter(o.caught_at or "NOTHING" for o in outcomes)
    for layer, count in sorted(first.items()):
        print(f"  {count:2}  {layer}")
    print()

    contained = [o for o in outcomes if o.contained]
    review_only = [o for o in outcomes if not o.contained and o.layers]
    escaped = [o for o in outcomes if not o.layers]

    print(f"PIPELINE SCORE: {len(contained)}/{n} consequential cases are contained by a layer")
    print(f"that stops or gates the value ({100*len(contained)//n} percent).")
    print(f"  review-queue only (a human is given a chance, not containment): {len(review_only)}")
    for o in review_only:
        print(f"      {o.case_id} -> {o.classified} (review={o.review})")
    print(f"  ESCAPES EVERY LAYER (the residual pipeline break): {len(escaped)}")
    for o in escaped:
        print(f"      {o.case_id} -> {o.classified}")
    print()

    print("Rescued by the mitigations (typed inert at layer 1, still contained later):")
    rescued = [o for o in outcomes if o.classified in INERT and o.contained]
    for o in rescued:
        others = [l for l in o.layers if l != "6 graded review"]
        print(f"  {o.case_id[:36]:38} inert as {o.classified[:28]:30} caught by {others[0]}")
    print()
    print(f"So of the {len(false_inert)} classifier misses, {len(rescued)} are still contained")
    print(f"downstream and {len(false_inert)-len(rescued)} are not.")
    print()

    # The verdict is a report, not a pass/fail: this is a measurement harness.
    if escaped:
        print("RESIDUAL: at least one consequential case escapes every layer. That is the")
        print("honest pipeline break, and it is smaller than the layer-1 number but not zero.")
        return 0
    print("No consequential case escapes every layer ON THIS CORPUS, under the now-BUILT")
    print("pipeline (D84 wired the mitigations into the engine and gate) and the honesty")
    print("conditions above. Not a claim of zero risk: the bindings are same-author, the")
    print("structural inputs are not yet produced by the real extraction, reaching a review")
    print("queue is not containment, and a fresh probe whose effect falls outside every")
    print("declared consequential slot could still re-open a residual (the limit is the slot")
    print("vocabulary's breadth, which grows on demand, D85).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
