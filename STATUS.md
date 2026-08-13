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

**The premise is proven; the substrate is ratified; the seed ontology is built
and tested; full coverage is still untested.** That is the state of the project.

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
  state-staging case. The spike's residual is now also resolved (D57): the proven
  algorithm is bound to a live Memgraph store (via podman) and matches the
  in-memory reference exactly across fuzzed sequences. See
  `spike/substrate/OUTCOME.md`.
- **Built and tested on a three-domain seed (the ontology).** The Phase 1
  communications and scheduling domains are authored on BFO as a runnable
  property-graph-native package, with a deterministic Nornir (classifier,
  reasoner, flow-to-sink) and a ground-truth corpus. All four test obligations of
  invariant 3.11 pass: coverage is measured (93.9% across three domains),
  classification correctness has no downgrade or fail-safe breach, the reasoner is
  sound (with a chained derivation and a negative control that catches an unsound
  rule, D56), and cross-domain state-staging is caught agent-scoped. The domain attach
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
  growing beyond the seed. The substrate, the classifier, the reasoner and the gate
  are all demonstrated on the seed; what remains is coverage breadth. See
  `NEUROSYMBOLIC_FILTER_INVARIANTS.md` invariant 3.11.

---

## 3. The document map

| Document | What it is |
|----------|-----------|
| `HEIMDALL.md` | The full architecture specification |
| `README.md` | Orientation, with audience-specific reading paths |
| `GLOSSARY.md` | Norse component names mapped to their architectural roles |
| `NEUROSYMBOLIC_FILTER_INVARIANTS.md` | The invariants the live build must hold, each marked PROVEN, DEMONSTRATED or NOT YET TESTED |
| `ONTOLOGY_CONSTRUCTION.md` | How the ontology (Yggdrasil) is built, grown and tested |
| `DECISIONS.md` | The decision log: 58 tracked decisions with consistency checks |
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
  Phase 1 communications, scheduling and finance domains on BFO as a runnable
  property-graph package (55 nodes), the deterministic classifier and reasoner (no
  model, per-domain rule registry, fail-closed inert gate), and the test harness
  (`ontology/tests/`) with a 33-case ground-truth corpus and 4 flow fixtures. All
   four obligations of 3.11 pass, plus a classification fail-closed property test
   (obligation 8.2b, D55) that catches a blacklist/fail-open regression
   automatically, a strengthened reasoner-soundness check with a negative control
   (D56), and the Gjoll action-critical gate (obligation 3.6, D58) that blocks an
   unsafe wiring before it fires while passing a safe one; coverage measured at
   93.9%; domain attach test demonstrated twice; cross-domain priority governed by
   principle (D52); inert classification fails closed (D54). See `ontology/OUTCOME.md`.
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
testing (per-rule entailment oracle, a chained derivation, a negative control). D46
to D56 record the seed ontology, Nornir, the classification rulings,
the test-corpus provenance, the per-domain rule registry (attach test demonstrated
twice), the cross-domain priority principle, its measured cost, and the fail-closed
inert gate. The only items still open are the research questions D33 to D36.

---

## 6. Recommended next step

The substrate is ratified and bound to a live store, the seed ontology is built
across three domains with a principled cross-domain priority rule, the classifier
fails closed, the reasoner is soundness-tested with a control, and Gjoll's
action-critical gate is demonstrated. The mechanism is now largely proven on the
seed; what is left is breadth and persistence. Next steps, in leverage order:

1. **Grow coverage beyond the seed.** Coverage is 93.9% on a 33-case corpus; that
   is a start, not a claim. Extend the ground-truth corpus and the classification
   rules where real traffic (or new adversarial cases) demand it, hand-authored and
   human-curated (D26). This raises the measured guarantee (invariant 3.9) and
   sharpens the classification-correctness corpus that D34 (honest vs
   injection-induced error) needs.
2. **Tune the finance/communications boundary demand-driven (D53)** once real
   traffic shows which payment overlaps actually occur, to bring down the 15% tie
   rate without losing the tie-to-review safety net.
3. **Wire Nornir's live flow-to-sink and the Gjoll gate to the Memgraph binding.**
   The binding is verified against the reference (D57) and the gate is proven over
   the in-memory graph (D58); the natural follow-on is to run both over the store
   rather than the per-batch in-memory graph, when persistence or cross-batch scale
   is wanted.

The external jailbreak corpus (`poc/corpus/adapter.py`) remains a PoC loose end and
is not currently available.

---

## 7. How to update this page

At the end of a working session, update sections 2, 4, 5 and 6 to reflect what
changed, and add any new decisions to `DECISIONS.md`. A decision that is only in
a chat and not in `DECISIONS.md` is a decision that will be lost.
