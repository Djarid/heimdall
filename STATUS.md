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
  (classifier, reasoner, flow-to-sink) and a ground-truth corpus. All four test
  obligations of invariant 3.11 pass: coverage is measured (94.7% across four domains),
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
| `DECISIONS.md` | The decision log: 66 tracked decisions with consistency checks |
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
  fixtures. All four obligations of 3.11 pass, plus a classification fail-closed
  property test (obligation 8.2b, D55) that catches a blacklist/fail-open regression
  automatically, a strengthened reasoner-soundness check with a negative control
  (D56), the Gjoll action-critical gate (obligation 3.6, D58) that blocks an unsafe
  wiring before it fires while passing a safe one, a coverage-gap capture that
  reports the review queue by reason to drive demand-driven growth (D60), and a
  marshalling-contract check (D62) proving the PoC extraction envelope becomes a
  typed assertion; coverage measured at 94.7%; domain attach test demonstrated three
  times (D59); cross-domain priority governed by principle (D52, refined for inert
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
substrate binding, the action-critical gate, and demand-driven coverage growth. The
only items still open are the research questions D33 to D36.

---

## 6. Recommended next step

The substrate is ratified, bound to a live store and now run through Nornir with the
gate (D63); the seed ontology is built across four domains with a principled
cross-domain priority rule; the classifier fails closed; the reasoner is
soundness-tested with a control; Gjoll's action-critical gate is demonstrated in
memory and over the store; the marshalling seam is proven end to end with a real
model (D62); and coverage growth is demand-driven off a captured gap signal (D60).
The mechanism is now proven end to end on the seed. What genuinely remains is
coverage BREADTH and cross-batch PERSISTENCE, both of which want real traffic or a
real deployment to be more than guesswork. Candidate next steps, in leverage order:

1. **Grow coverage from the captured gaps, once there is real traffic.** Coverage is
   94.7% on a 38-case corpus; on the synthetic corpus the review queue is all
   intentional (fail-safe, evasions, genuine ties), so further growth here is padding
   or blacklisting. The honest trigger is real traffic (D26): then the gap-capture
   report (D60) names what to extend.
2. **Tune the finance/communications boundary demand-driven (D53)** once real traffic
   shows which payment overlaps actually occur.
3. **Exercise persistent-store Nornir under load / edge deletion across batches.**
   The persistent mode (D64) accumulates the flow graph and catches cross-batch
   staging; the natural follow-ons are edge-deletion (retraction) across batches at
   scale, and a persistent-store differential fuzz against the in-memory oracle, both
   of which want a longer-running store than a test spins up.

Honest note on the frontier: the mechanism is now proven end to end on the seed, over
the real substrate, and across batches. The remaining items (coverage breadth,
boundary tuning) genuinely want real traffic to be more than guesswork, and the
persistent-store hardening wants a real deployment. There is no unblocked
mechanism-level gap left to close on the synthetic seed.

The external jailbreak corpus (`poc/corpus/adapter.py`) remains a PoC loose end and
is not currently available.

---

## 7. How to update this page

At the end of a working session, update sections 2, 4, 5 and 6 to reflect what
changed, and add any new decisions to `DECISIONS.md`. A decision that is only in
a chat and not in `DECISIONS.md` is a decision that will be lost.
