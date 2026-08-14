# Heimdall: Project Status

**Author:** Jason Huxley
**Version:** 1.0
**Date:** August 2026
**Status:** living status page; update at the end of each working session

This is the "you are here" page. It orients a reader (or a fresh agent session
with no prior context) on where the project stands, what is proven, what is
open, and what to do next. For the full detail, follow the links; this page is
the map, not the territory.

---

## 1. What Heimdall is

A neurosymbolic architecture that lets LLM agents work with untrusted external
content (web, social media, email, documents, tool output) without that content
being able to cause action. Trust is assigned by origin at a structural
boundary, not by detecting malicious content. Read `HEIMDALL.md` for the full
architecture and `README.md` for the orientation paths.

---

## 2. Where we are now

**The premise is proven; the substrate is ratified; the seed ontology is built;
and an adversarial measurement has found a real classification break, so the test
suite is deliberately RED.** That is the state of the project. The break (D67): an
independent adversarial corpus measures a false-inert rate of 3/12, consequential
content that positively earns an inert signal skips both the gate and review. It is
left red and named, not patched, because a suite that names a real break is worth
more than a green one that never tested it; the fix is an open design problem
(D67-fix), not more keywords.

- **Proven (the PoC).** The neurosymbolic filter's structural half holds: a
  deterministic layer with no LLM quarantines untrusted content as typed data,
  the model only ever receives it as inert data, and nothing acts on the output
  unless a wiring is proven safe by provenance. Demonstrated on an adversarial
  corpus with a real local model, at decoding temperatures 0.0 and 0.7. See
  `poc/OUTCOME.md`.
- **Ratified and bound to a live store (the substrate).** The Phase 2 substrate
  spike settled D25 and D38: a property graph maintains the flow-to-sink
  action-critical label incrementally, with sound edge-deletion retraction (D32),
  without an authorisation-time traversal. All four criteria of
  `ONTOLOGY_CONSTRUCTION.md` 3.3 pass, including the mandatory cross-domain
  state-staging case. The spike's residual is resolved (D57): the proven algorithm
  is bound to a live Memgraph store (via podman) and matches the in-memory reference
  exactly across fuzzed sequences. Nornir with the Gjoll gate now runs over that
  store via an injectable backend (D63), matching the in-memory oracle, and a
  persistent store catches CROSS-BATCH state staging that the per-batch path misses
  (D64): a value staged across separate turns becomes action-critical when the path
  completes, and the gate blocks it. See `spike/substrate/OUTCOME.md`.
- **Built and tested on a four-domain seed (the ontology).** The Phase 1
  communications, scheduling, finance and publication domains are authored on BFO
  as a runnable property-graph-native package, with a deterministic Nornir
  (classifier, reasoner, flow-to-sink) and a ground-truth corpus. Most 3.11
  obligations pass but the suite is RED (the false-inert break, D67): coverage is
  measured (36/38, 95% Wilson interval 83 to 99 percent); the reasoner is sound (with
  a chained derivation and a negative control that catches an unsound rule, D56);
  cross-domain state-staging is caught agent-scoped; but the independent adversarial
  corpus finds consequential content typed inert (a real downgrade, 1/16 after the
  D69 guard-port, down from 3/12). The domain attach
  test (D29) is demonstrated twice (scheduling, then finance) without editing the
  existing domains or the spine. Domain governance (D31) is settled single-curated,
  with a cross-domain priority principle (D52) whose review-queue cost the finance
  domain measured (D53). Classification fails closed (D54): the inert type is earned
  by a positive informational signal, and unconfirmed requests route to review, so
  realistic BEC evasions no longer silently go inert, closed without a keyword
  blacklist. That discipline is now enforced structurally, not by review alone
  (D55): a fail-closed property test in the harness, a standing rule in `AGENTS.md`,
  an authoring checklist, and a sharpened invariant 3.5. And Gjoll's action-critical
  gate (invariant 3.6, D58) is demonstrated: a consequential action is blocked before
  it fires when a parameter is an untrusted-derived, action-critical value, including
  when that value reaches the sink through a multi-hop cross-domain chain, with the
  mandatory safe-plus-unsafe control. See `ontology/OUTCOME.md`.
- **Not yet tested (full coverage).** The guarantee's extent depends on coverage
  growing beyond the seed. The substrate, the classifier, the reasoner, the gate and
  the marshalling seam to the real model (D62) are all demonstrated on the seed; what
  remains is coverage breadth. See `NEUROSYMBOLIC_FILTER_INVARIANTS.md` invariant 3.11.

---

## 3. The document map

| Document | What it is |
|----------|-----------|
| `HEIMDALL.md` | The full architecture specification |
| `README.md` | Orientation, with audience-specific reading paths |
| `GLOSSARY.md` | Norse component names mapped to their architectural roles |
| `NEUROSYMBOLIC_FILTER_INVARIANTS.md` | The invariants the live build must hold, each marked PROVEN, DEMONSTRATED or NOT YET TESTED |
| `ONTOLOGY_CONSTRUCTION.md` | How the ontology (Yggdrasil) is built, grown and tested |
| `ADVERSARIAL_REVIEW.md` | A briefing for a hostile reviewer: the claims, the evidence, and the honest seam list of where to attack |
| `DECISIONS.md` | The decision log: 69 tracked decisions (D68 the AST symbolic-layer guard, D69 the shared inert guard) plus the open D67-fix item, with consistency checks |
| `STATUS.md` | This page |
| `AGENTS.md` | Standing instructions for agents working on the repo, including the currency rule; auto-loaded by opencode |
| `poc/` | The proof-of-concept: code, corpus, spec and outcome |
| `spike/` | Throwaway ratification spikes; `substrate/` settled the D25/D38 substrate decision |
| `ontology/` | Yggdrasil: BFO loaded, SUMO reference; the seed ontology authored as the `yggdrasil` package, the reasoner as `nornir`, tests passing (`ontology/OUTCOME.md`) |
| `reference/style_guide.md` | The writing style guide all prose is written to |

Read order for a cold start: this page, then `poc/OUTCOME.md`,
then `NEUROSYMBOLIC_FILTER_INVARIANTS.md`, then `ONTOLOGY_CONSTRUCTION.md`, then
the two Phase 2 outcomes (`spike/substrate/OUTCOME.md`, `ontology/OUTCOME.md`),
with `DECISIONS.md` as the running record of why each choice was made.

---

## 4. What is built

- **PoC** (`poc/`): `symbolic.py`, `neural.py`, `harness.py`, `sinks.py`, a
  31-case corpus, an external-jailbreak adapter. Runs in a venv via `mlx-lm` on
  Apple silicon. All cases pass both assertions at temp 0.0 and 0.7.
- **Substrate spike** (`spike/substrate/`): `reachability.py` and `harness.py`, a
  substrate-neutral test of the flow-to-sink action-critical label. 23 checks, all
  pass. Ratifies D25/D38 and resolves D32. Throwaway per 3.3, kept as evidence.
- **Seed ontology and Nornir** (`ontology/yggdrasil/`, `ontology/nornir/`): the
  Phase 1 communications, scheduling, finance and publication domains on BFO as a
  runnable property-graph package (58 nodes), the deterministic classifier and
  reasoner (no model, per-domain rule registry, fail-closed inert gate), and the
  test harness (`ontology/tests/`) with a 38-case ground-truth corpus and 4 flow
  fixtures. The harness runs the four 3.11 obligations plus a classification
  fail-closed property test (obligation 8.2b, D55), a strengthened reasoner-soundness
  check with a negative control (D56), the Gjoll action-critical gate (obligation
  3.6, D58) that blocks an unsafe wiring before it fires while passing a safe one, a
  coverage-gap capture that reports the review queue by reason (D60), a
  marshalling-contract check (D62), and the false-inert measurement (D67). The suite
  is currently RED: the false-inert measurement finds 3/12 (a real break, left red
  and named); the other checks pass. Coverage measured at 36/38; domain attach test
  demonstrated three times (D59); cross-domain priority governed by principle (D52, refined for inert
  ties D61); inert classification fails closed (D54). An optional end-to-end harness
  (`ontology/tests/e2e_harness.py`) runs the real mlx model through
  marshal-classify-gate: an injected directive is extracted and blocked before firing
  (D62). See `ontology/OUTCOME.md`.
- **Ontology sources** (`ontology/`): BFO 2020 loaded (`upper/bfo`, CC BY 4.0);
  SUMO fetched as unloaded GPL reference (`reference/sumo`).
- **The documentation spine**: invariants, ontology methodology, decision log,
  status page, style guide, and `AGENTS.md` (the standing currency rule), all
  committed.

---

## 5. What is open, and who forces it

From `DECISIONS.md` section 5. Nothing here is a surprise; each has a trigger.

| Item | Kind | Trigger / phase |
|------|------|-----------------|
| D33 constrained decomposition grammar | OPEN (research) | If opaque summaries prove too coarse |
| D34 Huginn discriminating features (honest vs injection error; pure euphemism) | OPEN (research) | Needed for classification-correctness testing; the fail-closed default (D54) makes the gap safe meanwhile |
| D35 Odin self-modification | OPEN (research) | Currently excluded |
| D36 cross-harness portability | DEFERRED | Post-Phase 1 |
| D45 dense-cycle deletion locality | SETTLED (caveat) | Monitoring: watch for large dense cycles in a future domain |

D25, D32 and D38 were resolved by the substrate spike. D31 (domain governance) is
settled single-curated, with its cross-domain priority principle D52; D51 (masking)
is resolved by D52; D53 records the review-queue cost the finance domain measured;
D54 makes inert classification fail closed (evasions route to review, no keyword
blacklist), and D55 enforces that discipline with a property test, AGENTS.md rule,
authoring checklist and a sharpened invariant 3.5. D56 strengthens reasoner-soundness
testing (per-rule entailment oracle, a chained derivation, a negative control). D57
binds the flow-to-sink algorithm to a live Memgraph store; D58 wires Gjoll's gate to
the action-critical determination. D59 adds the publication domain (open-web
surface), D60 the coverage-gap capture process, D61 the inert-tie refinement. D46 to
D61 record the seed ontology, Nornir, the classification rulings, the test-corpus
provenance, the per-domain rule registry (attach test demonstrated three times), the
cross-domain priority principle and its cost, the fail-closed inert gate, the
substrate binding, the action-critical gate, and demand-driven coverage growth. A
repository-access review then added the AST symbolic-layer guard (D68) and the shared
inert guard (D69). Open items: the false-inert fix (D67-fix, reduced to 1/16 but not
closed, the suite is red), CI wiring (the checks exist but nothing runs them
automatically), and the research questions D33 to D36.

---

## 6. Recommended next step

A repository-access review closed two gaps this round: invariant 3.1 now has an
executable AST guard (D68, it had no automated enforcement before), and the false-inert
break was reduced from 3/12 to 1/16 by porting a shared inert-earning guard to all
domains (D69). The suite is still RED at 1/16, so that remains the top of the list.

1. **Close the false-inert break (D67-fix), and it must be a design change, not
   keywords.** D69 reduced it by applying the rule set's own discipline consistently,
   but a fresh passively-phrased case still slips (1/16) and widening the keyword
   guard is the treadmill invariant 3.5 forbids. The real fix changes how inertness is
   earned (candidate: a narrow grammar-constrained model question "does this ask the
   reader to do something with an effect", inert requires a no). Re-measure after, on
   an independent corpus, not the self-authored one.
2. **Build a genuinely independent adversarial corpus.** 1/16 is a lower bound: one
   author wrote both the rules and the corpus, and D69 demonstrated the circularity
   directly (tuned to catch three cases, a fresh probe found a fourth). A corpus
   labelled by someone who has not read the rules turns the lower bound into an
   estimate, and is the single highest-information next artefact (G2).
3. **Publish the sink-declaration schema and add gate-boundary validation** so the
   seam ranked first (sink-wiring honesty) becomes attackable by someone other than
   its author; `ActionProposal.consumes` is currently an unchecked dict (review 3.2).
4. **Wire CI** to run the harness and the AST guard on push (D68 built the guard but
   there is no CI; the checks run only when a human runs them).

Lower-priority, genuinely wanting real traffic or a real deployment: growing coverage
breadth from the captured gaps (D60, D26), tuning the finance/communications boundary
(D53), and persistent-store hardening under load and cross-batch edge deletion (D64).

Honest note on the frontier: the earlier claim that there was "no unblocked
mechanism-level gap left" was wrong, and the false-inert measurement is what showed it.
There is now a named, measured, unblocked mechanism-level break, and closing it is the
work.

The external jailbreak corpus (`poc/corpus/adapter.py`) remains a PoC loose end and
is not currently available.

---

## 7. How to update this page

At the end of a working session, update sections 2, 4, 5 and 6 to reflect what
changed, and add any new decisions to `DECISIONS.md`. A decision that is only in
a chat and not in `DECISIONS.md` is a decision that will be lost.
