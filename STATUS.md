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

## 0. Resume here (handoff, last updated after D88)

A fresh session should read this block, then section 6, then start work. Everything below
is committed and pushed; the working tree is clean.

**State in one paragraph.** The pipeline contains every consequential case on the
independent corpus: 33 of 33, defence in depth (D83, D84, D85). That is the headline, and it
is now a property of the BUILT system: the D79 to D82 mitigations are wired into the live
engine and gate (D84), the last residual class was closed by growing the consequential-slot
vocabulary rather than by a keyword (D85), and Fenrir performs the STRUCTURAL slot extraction
that feeds the state-delta layer, now demonstrated with a REAL model (D86 built it and proved
it against a mock, D87 proved it against Qwen2.5-7B via the PoC's bounded generation), so the
slot bindings the later layers need are produced by a real model rather than corpus-supplied.
Underneath that, the first-layer classifier on its own is deliberately weak: it types about
48 percent (16 of 33) of consequential content inert on the rules-aware independent corpus,
and that layer-one break stays OPEN and RED (now 22 findings, all false-inert, after D88 added
a blind-authored corpus) because no content pattern can separate a passively-phrased
consequence from a genuine informational statement without world knowledge, which invariant
3.1 keeps off the classification path. D88 is the strongest independence obtainable inside an
agent session (a fresh sub-agent authored the scenarios with no rule or repo access): it reads
LOWER, 5 of 36 (about 14 percent), because a rules-aware author targets the classifier's blind
spots more precisely than a blind one, so the two rates bound different adversaries and neither
is fully third-party. The point of the architecture is exactly that the
guarantee does not rest on the first layer: five later layers, none depending on the
classifier being right, catch what it misses. So read the 48 percent as the pessimistic
single-layer figure and the 33-of-33 as what the whole pipeline does, under the remaining
honesty conditions (same-author bindings; and value poisoning, since the structural extraction
now uses true token-level grammar-constrained decoding, D90, which constrains structure but
not value truth). D90 replaced the D87 bounded per-field stand-in with a real grammar mask, so
the "not yet true grammar constraint" caveat is closed; what remains on that layer is value
poisoning, contained by Gjoll at action time.

**Run this first, to see the state for yourself:**

```
poc/.venv/bin/python -m ontology.tests.harness                              # RED at 22 layer-one, expected
poc/.venv/bin/python -m ontology.tests.pipeline_score_harness               # D77: 48% layer-one, 33/33 pipeline
poc/.venv/bin/python -m ontology.tests.pipeline_score_harness --thirdparty  # D88 blind: 14% layer-one, 33/36 pipeline
```

**The next piece of work, in priority order (detail in section 6):**

1. **Third-party corpus (G2): DELEGATED externally, not an in-repo task (D91).** A colleague
   is independently developing and running this exact false-inert attack vector against models
   with no exposure to Heimdall's rules, and will test the classifier when his work completes.
   That is the true external independence D88's blind corpus explicitly could not manufacture
   from inside a session. So do NOT re-attempt this in-repo: the honest in-session ceiling was
   already reached (D88, 5/36 blind; D77, 16/33 rules-aware, both lower bounds). When the
   external result lands it is the first unbiased measurement; record it as its own decision
   and let it drive D67-fix's disposition. Nothing to build here meanwhile.
2. **Attest the declarations (NARROWED by D89, not closed).** D81 closed declaration ERROR or
   DRIFT; D89 then narrowed the HONESTY seam on two axes: B derives sink consequentiality from
   an attested effect-primitive table (so a money sink flagged non-consequential is still
   gated), and A blocks an action-critical value dishonestly declared CONSUME_INERT. Both
   relocate trust to a small auditable table, they do not remove it, so a sink that declares
   the WRONG primitive still defeats the gate. The remaining follow-ons (named in
   `plans/declaration_attestation_scoping.md`) are C (attest WHO may declare, for the
   config-tamper adversary) and D (verify the primitive against behaviour, the strongest
   evidence). That residual is the still-open part of the root seam (`ADVERSARIAL_REVIEW.md`
   5.1).
3. **True token-level grammar-constrained decoding: DONE (D90).** Replaced D87's bounded
   per-field stand-in with a real token-level grammar mask: the model emits the whole
   `SlotExtractionSchema` object under a logits processor that permits only tokens keeping the
   output a valid grammar prefix, so a malformed object or an undeclared key is unreachable and
   there is no free-text to re-parse (the `fenrir.md` 3.1 property). Implemented natively on
   mlx_lm's `logits_processors` hook (no outlines/xgrammar dependency), the grammar proven
   deterministically without a model (`phase2/tests/harness.py` obligation 7) and demonstrated
   on Qwen2.5-7B end to end (`phase2/grammar_slot_demo.py`). Residual, unchanged: it constrains
   STRUCTURE, not value TRUTH, so value poisoning stays a Gjoll concern.

   The remaining named work, now that tasks 1 to 3 are addressed: the EXTERNAL-HUMAN corpus
   (task 1's residual), and the declaration follow-ons C (attest who may declare) and D (verify
   the effect primitive against behaviour) from `plans/declaration_attestation_scoping.md`.

**Traps that have already caught someone in this repo:**

- Never grow classification coverage by adding keyword rules that enumerate malicious
  phrasings. That is invariant 3.5's blacklist trap; it has been tried and re-opened twice
  (D69, D72). The fail-closed property test in `ontology/tests/harness.py` enforces it. Note
  the distinction: D85 grew the consequential-SLOT vocabulary (what kind of fact is set),
  which is not a keyword and is the sanctioned way to close a residual class.
- Do not quote the 48 percent as "the system's containment" or the 100 percent as "no risk".
  The 48 percent is layer one alone; the 100 percent is the whole pipeline under stated
  honesty conditions. Both are lower bounds on difficulty (same-author corpus).
- Do not read D88's LOWER blind rate (14 percent) as the break being smaller than D77's 48
  percent. They bound different adversaries: a rules-aware author targets the blind spots
  precisely, a blind one trips them by accident. The break is still real and structural, and
  D67-fix stays OPEN. D88 is BLIND, not fully third-party (orchestrator session knowledge,
  shared model family, same-author structural bindings); its pipeline score carries a heavier
  caveat than its layer-one rate because the structural bindings are builder-derived.
- Anything added under `ontology/yggdrasil/`, `ontology/nornir/` or `poc/symbolic.py` is on
  the authorisation path and may import only roots on `ALLOWED_IMPORT_ROOTS` in
  `ontology/nornir/symbolic_guard.py`. The 3.1 guard is fatal and runs first. The D84 wiring
  uses only relative intra-package imports, which is why it stays clean.
- Do not soften the RED bar or report a harness result you have not run. The red layer-one
  suite is the honest artefact; a green one that never tested the break is worth less.
- Use the `sync-project-docs` skill when recording anything: the repo and the Tolaria vault
  at `~/git/tolaria1` both have to be updated, and the vault has a strict schema.

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
adversarial corpus measures a false-inert rate: consequential content that positively
earns an inert signal, so it loses the review-queue routing and its risk signalling. (It
does NOT skip the action-time gate: action-critical status is computed by graph
reachability, not by the classification, so a false-inert value that can reach a
consequential sink is still gated and blocked, verified empirically in D78.) The rate has
two figures, and the gap is the point. On the self-authored corpus two structural guards reduced it (D69,
3/12 to 1/16; D72, closing that residual before a fresh metaphor probe re-opened it to
1/17). But that corpus was tuned by the rules' own author; a larger scenario-authored
independent corpus measures 16/33, about 48 percent (D77, D83), so the self-authored number
badly understated the bound. The break is large and structural, not an edge case: the
classifier is blind to consequence expressed without imperative or movement vocabulary,
across config changes, deletion, contract renewal, access grants, payroll redirects and
security-state changes. It is bounded by invariant 3.1 (separating a passively-phrased or
metaphorical consequence from a genuine informational statement needs world knowledge,
which is a model 3.1 keeps off the classification path). It is left red and named, not
papered over; the fix is an open design problem (D67-fix), and "accept a small residual"
is now ruled out because the residual is not small. Its realised severity, though, is
bounded by defence in depth, none of which depends on the classifier being right: the
action-time gate was never defeated by the break at all (D78, action-critical status is
reachability-derived), promotion into trusted memory is human-gated (D76), and five
mitigations now stand between a mis-classification and harm (D79 state-delta consequence
detection, D80 two-dimensional classification removing the inert override, D81 fail-closed
sink-declaration validation, D82 corroboration for promotion and graded review), all now
WIRED into the live engine and gate (D84). Scored as defence in depth rather than by the
classifier alone, the pipeline contains 33 of 33 consequential cases, 100 percent, against
the 48 percent layer-one rate, after D85 closed the last residual class by slot-vocabulary
growth (D83, D84, D85). So the break is a degraded outer layer rather than an open door: the
classification layer is measurably weak and stays red, and the guarantee does not rest on it.

**One caveat a fresh session must carry, or the 100 percent is misleading.** The pipeline
score is now the BUILT pipeline, not the designed one: D84 wired the mitigations D79 to D82
into `engine.py` and `gjoll.py`, so the pipeline-score harness reads the engine's own runtime
output and its integration banner reports every mitigation as wired. D85 closed the residual
CLASS the first 100 percent score had hidden (three cases, an asset transfer, a trademark
assignment, an insurance lapse) by growing the consequential-slot vocabulary, not a keyword.
D86 then built the structural slot extraction that produces those bindings, and D87
demonstrated it with a REAL model: Fenrir binds values to typed slots and feeds the
state-delta layer end to end, proven against Qwen2.5-7B via the PoC's bounded generation (the
model bound `salary_destination` from an inertly-phrased payroll redirect the classifier
still typed inert, and the live engine denied effective inertness). What still bounds the
100 percent is that the extraction uses bounded per-field generation, the Phase-2 stand-in
`plans/dd/fenrir.md` 3.1 sanctions, not yet true token-level grammar-constrained decoding
(D87, a named refinement); the corpus and the rules share one author, so the figure is a
lower bound on difficulty; and value poisoning stays open (a model can bind a schema-valid
wrong value, contained by Gjöll, FR-6). A fresh probe whose effect falls outside every
declared consequential slot could still re-open a residual; the limit is the slot
vocabulary's breadth, which grows on demand (D60, D85).

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
  corpus finds consequential content typed inert (a real downgrade): 1/17 on the
  self-authored corpus after the D69/D72 guards, but 13/30 (about 43 percent) on a larger
  independent scenario-authored corpus (D77), so the break is large and structural, bounded
  by invariant 3.1. The domain attach
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
| `DECISIONS.md` | The decision log: 91 tracked decisions (D77 the independent corpus measuring layer-one false-inert at about 48 percent, D78 the correction that the false-inert break does NOT defeat Gjoll because action-critical status is reachability-derived, D79 to D82 the four false-inert mitigations, D83 the defence-in-depth pipeline score, D84 wiring the mitigations into the live engine and gate, D85 closing the residual class by slot-vocabulary growth, D86 Fenrir structural slot extraction feeding the state-delta layer, D87 the real-model demonstration of that extraction, D88 the blind-authored third-party corpus measuring layer-one at 5/36, D89 narrowing the root declaration seam by deriving sink consequentiality from an attested effect-primitive table plus a fail-closed consume mode, D90 true token-level grammar-constrained decoding replacing the bounded per-field stand-in, D91 delegating the genuinely third-party corpus to an external tester) plus the still-open D67-fix layer-one break, with consistency checks |
| `phase2/` | The Phase 2 detection layer: Fenrir (sandbox reader) and Huginn (canary + attempt-introspection monitoring), built under D74. Deterministic logic suite green; the real-model demonstration returned the D75 negative finding. See `phase2/OUTCOME.md` |
| `STATUS.md` | This page |
| `AGENTS.md` | Standing instructions for agents working on the repo, including the currency rule; auto-loaded by opencode |
| `plans/hld.md` | The High-Level Design: the build-oriented engineering view of the whole system across all six phases, with a per-component achievement baseline, a harness-agnostic integration interface and a risk register (D73) |
| `plans/dd/` | The Detailed Design, implementation fidelity for Phases 1-3: an index (conventions, the OpenCode/Gleipnir harness binding, cross-cutting contracts) plus eight component documents (Bifröst, Mímisbrunnr, Nornir, Fenrir, Hliðskjálf, Himinbjörg, Gjöll, Gjallarhorn) (D73) |
| `plans/hld_scoping_brainstorm.md` | The scoping analysis behind D73: the achievement audit and the three converged decisions (harness, classifier stance, phasing) |
| `poc/` | The proof-of-concept: code, corpus, spec and outcome |
| `spike/` | Throwaway ratification spikes; `substrate/` settled the D25/D38 substrate decision |
| `ontology/` | Yggdrasil: BFO loaded, SUMO reference; the seed ontology authored as the `yggdrasil` package, the reasoner as `nornir`, tests passing (`ontology/OUTCOME.md`) |
| `reference/style_guide.md` | The writing style guide all prose is written to |

Read order for a cold start: section 0 of this page, then section 6, then
`poc/OUTCOME.md`, then `NEUROSYMBOLIC_FILTER_INVARIANTS.md`, then
`ONTOLOGY_CONSTRUCTION.md`, then the outcomes (`spike/substrate/OUTCOME.md`,
`ontology/OUTCOME.md`, `phase2/OUTCOME.md`), with `DECISIONS.md` as the running
record of why each choice was made. For the current work specifically, the
decisions that matter are D77 (the measured rate), D78 (the gate correction),
D79 to D82 (the mitigations) and D83 (the pipeline score and its residual).

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
   is currently RED: the false-inert measurement finds 1/17 on the self-authored corpus but
   13/30 (about 43 percent) on a larger independent corpus (D77), a large real break, left red and named;
   the other checks pass. Coverage measured at 36/38; domain attach test
  demonstrated three times (D59); cross-domain priority governed by principle (D52, refined for inert
  ties D61); inert classification fails closed (D54). An optional end-to-end harness
  (`ontology/tests/e2e_harness.py`) runs the real mlx model through
  marshal-classify-gate: an injected directive is extracted and blocked before firing
  (D62). See `ontology/OUTCOME.md`.
- **Phase 2 detection layer** (`phase2/`): Fenrir (sandbox reader: empty capability
  set, canary wrap, tainted-only output, fresh context) and Huginn (six hard canary
  signals plus the attempt-introspection tripwire, both fail-closed), built under the
  scoped R-1 exception (D74). The deterministic logic suite is green (five obligations,
  tested by failure mode, zero false positives). The optional real-model demonstration
  returned an honest NEGATIVE finding (D75): a robust model is not steered by the
  false-inert payloads (including an overt injection), so the attempt-introspection
  catch (D67-fix direction d) does NOT close the false-inert gap for a resisting model;
  it is an injection-success detector, not a false-inert fix, and direction (d) is
  demoted. See `phase2/OUTCOME.md`. Fenrir also now performs STRUCTURAL slot extraction
  (D86, `phase2/slot_extraction.py`): a fixed authored `SlotExtractionSchema` the model
  fills with bounded values only, a deterministic `bind_slots` that maps them to typed
  `ProposedFact`s, and a `marshal_fenrir_run` bridge that hands them to Nornir as
  `MarshalledAssertion.proposed_facts`. The binding is model-free (invariant 3.1: phase2
  is not on the authorisation path and nornir has no dependency on phase2), and
  fail-closed (an unbound or low-confidence field fabricates no delta). Phase2 harness
  obligation 6 proves it end to end against the live engine: an inertly-phrased payroll
  redirect is still typed inert by the classifier yet the engine denies effective
  inertness on the structural signal. Demonstrated against a deterministic mock (D86), and
  now also against a REAL model (D87, `phase2/real_slot_extraction.py` and
  `phase2/real_slot_demo.py`): a `MlxSlotProducer` reuses the PoC's proven bounded
  generation (`_StopOnNewline`, isolated-payload splice) to fill the schema values, and on
  Qwen2.5-7B it bound `salary_destination` from an inertly-phrased payroll redirect the
  classifier still typed inert, with the benign control binding nothing (fail-closed). The
  demo is optional and skip-if-absent, like `e2e_harness.py`. Bounded per-field generation,
  not yet true grammar-constrained decoding, is the named remaining refinement.
- **False-inert mitigations in depth, now WIRED** (`ontology/nornir/`, D79 to D82, wired by
  D84): four modules, each with its own green harness, none depending on the classifier being
  right, and all now called by the live engine and gate. `state_delta.py` judges consequence
  by what a value would CHANGE against a declared consequential-slot set (24 seed slots after
  D85 added `holder_of_record` and `entitlement_status`; catches every wired case on the
  independent corpus by effect, unevadable by rephrasing where extraction is structural).
  `consequence_axis.py` splits classification into a speech-act type plus an independent
  consequence axis, so an inert type can no longer SUPPRESS a co-present consequence signal,
  and records whether the evidence is structural or evadable. `sink_declaration.py` gives the
  sink declarations a schema and fail-closed validation, closing three paths where an error or
  drift silently disabled the gate. `promotion_policy.py` requires independent corroboration or
  human approval before a consequential fact is promoted, and grades review priority so an
  inert-in-effect value touching a consequential slot still gets reviewed. The wiring (D84):
  `MarshalledAssertion` carries `proposed_facts` (structural slot bindings) and `source`;
  `engine.py` computes the consequence axis and promotion decisions per batch, so every
  `ClassifiedAssertion` carries `effective_inert`, `consequence_reasons` and `review_priority`
  and `NornirResult` carries `promotions`; `gjoll.py` takes an optional `sink_registry` and
  runs the D81 fail-closed validation before the gate. The four mitigation harnesses now run in
  the main suite (`run_mitigations`) and pass. `ontology/tests/pipeline_score_harness.py` (D83)
  scores all six layers together, now reading the engine's own runtime output, and reports
  where each consequential case is first caught; its integration banner reports every
  mitigation as wired (self-maintaining) and it produces 33 of 33 (100 percent) after D85. It
  is a measurement harness, not a pass/fail obligation, and carries four honesty conditions in
  its docstring.
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
repository-access review then added the AST symbolic-layer guard (D68); a second
review extended it to indirect model calls (dynamic import, outbound HTTP) and gave it
a mandatory negative control (D70), and the shared inert guard was ported (D69). A third
review found D70's "whole class" network claim was in the code a ten-name blacklist that
missed `boto3`, `google`, `smtplib`, `ctypes` and every other unlisted egress module, so
enforcement was inverted to a known-good import allowlist that forbids the class by
construction (D71). A referential-completeness guard then reduced the false-inert rate
again and showed the residual is bounded by invariant 3.1 (D72). The mitigations were then
WIRED into the live engine and gate (D84), closing the integration gap that had made the D83
score the designed pipeline, and the D83 residual class was closed by growing the
consequential-slot vocabulary (D85, `holder_of_record` and `entitlement_status`), so the
pipeline score rose to 33 of 33 (100 percent) as a built property. Fenrir then gained STRUCTURAL slot
extraction feeding the state-delta layer end to end (D86), demonstrated first against a
deterministic mock and then against a REAL model (D87, Qwen2.5-7B via the PoC's bounded
generation), so the slot bindings the later layers need are produced by a real model rather
than corpus-supplied. Open items now: the false-inert fix (D67-fix, still OPEN as a
classification break and RED at layer one but mitigated in depth and wired), true
token-level grammar-constrained decoding (D87 uses bounded per-field generation, the Phase-2
stand-in; the true grammar constraint is the named refinement), declaration attestation (the
honest-declaration seam D81 left open, `ADVERSARIAL_REVIEW.md` 5.1), a genuinely third-party
corpus (D77 is same-author), value poisoning (contained by Gjöll, FR-6, not closed at the
extraction layer), and the research questions D33 to D36.

An HLD and a Phase 1-3 Detailed Design have been authored for the build-out (D73,
`plans/hld.md` and `plans/dd/`), grounded in an achievement audit against the real
code. They are design artifacts, not new build: the HLD is harness-agnostic across all
six phases, the implementation-ready Detailed Design is scoped to Phases 1-3, and both
name Himinbjörg (the gateway and control surface, essentially unbuilt) as the Phase-3
critical path and the Gjöll sink-declaration schema as the load-bearing gap to close
first. They do not change the build state recorded above; they lay out the route to it.

The Phase 2 Fenrir + Huginn detection layer was then built under a scoped R-1 exception
(D74, `phase2/`), and its real-model demonstration returned an honest negative finding
(D75): the attempt-introspection catch does not close the false-inert gap for a resisting
model, so it is an injection-success detector, not a false-inert fix. Separately, memory
poisoning is a tracked EXTERNAL dependency, not a Heimdall build item: Gleipnir is proving
a trust-tiered memory-write governance model (its G-6), and Heimdall will adopt it into
Mímisbrunnr on success rather than author its own (D76), keeping the two systems' memory
trust models aligned.

---

## 6. Recommended next step

The pipeline now contains every consequential case on the independent corpus, 33 of 33, as a
BUILT property: the D79 to D82 mitigations are wired into the live engine and gate (D84), the
last residual class was closed by slot-vocabulary growth (D85), and Fenrir performs the
structural slot extraction that feeds the state-delta layer end to end, demonstrated first
against a mock (D86) and now against a REAL model (D87, Qwen2.5-7B via the PoC's bounded
generation). The layer-one classifier on its own still misses 48 percent (D77, D83) and stays
OPEN and RED (17 findings), because that break is bounded by invariant 3.1 and no content
pattern closes it; the guarantee does not rest on it. With the real-model structural
extraction now demonstrated, the highest-value work is testing the whole thing against a
corpus the author never saw.

1. **Third-party corpus (G2): DELEGATED externally (D91), not an in-repo task.** The
   independent scenario-authored corpus (D77) raised the measured layer-one rate from 1/17 to
   16/33, and the BLIND-authored corpus (D88, `false_inert_thirdparty.json`) reached 5/36, the
   strongest independence obtainable inside a session; both are lower bounds on difficulty, not
   unbiased estimates. The remaining external-human step is now OWNED OUT-OF-BAND: a colleague
   is independently running this exact false-inert attack vector against models with no
   exposure to the rules, and will test the classifier when complete (D91). Do not re-attempt
   it in-repo. When the external result lands it is the first unbiased measurement; record it
   as its own decision and let it drive the D67-fix disposition.
2. **Attest the declarations (NARROWED by D89).** D81 closed declaration ERROR or DRIFT; D89
   narrowed the HONESTY seam: B derives sink consequentiality from an attested effect-primitive
   table (a money sink flagged non-consequential is still gated), and A blocks an
   action-critical value dishonestly declared CONSUME_INERT. Both relocate trust to a small
   auditable table rather than removing it, so a sink declaring the WRONG primitive still
   defeats the gate. The remaining follow-ons are C (attest WHO may declare) and D (verify the
   primitive against behaviour), scoped in `plans/declaration_attestation_scoping.md`.
3. **True token-level grammar-constrained decoding: DONE (D90).** Replaced D87's bounded
   per-field stand-in with a real token-level grammar mask over the `SlotExtractionSchema`
   (the model emits the whole object under a logits processor that permits only grammar-valid
   tokens, so malformed structure and undeclared keys are unreachable, the `fenrir.md` 3.1
   property). Native on mlx_lm's `logits_processors` hook, no outlines/xgrammar dependency; the
   grammar is proven deterministically without a model and demonstrated on Qwen2.5-7B end to
   end. This removed the last "stand-in" caveat on the structural-extraction layer. Residual:
   it constrains structure, not value truth, so value poisoning stays a Gjoll concern. The
   remaining declaration follow-ons are C (attest who may declare) and D (verify the effect
   primitive against behaviour), scoped in `plans/declaration_attestation_scoping.md`.
4. **Decide the layer-one break's disposition (D67-fix); it is bounded by invariant 3.1.**
   Now less urgent since the pipeline contains it, but still worth closing on the
   classification side. The two honest directions are a deterministic
   referential-completeness discipline stronger than a regex (measure its review-friction
   cost first), or a fail-closed advisory model that only routes to review. "Accept a small
   residual" is ruled out (the layer-one rate is 48 percent, not small), and more keywords
   are barred (invariant 3.5).

Lower-priority, genuinely wanting real traffic or a real deployment: growing coverage
breadth from the captured gaps (D60, D26), tuning the finance/communications boundary
(D53), and persistent-store hardening under load and cross-batch edge deletion (D64).

(CI is deliberately out of scope: the harness and the 3.1 guard run when a human runs
them, and that is the accepted current state, not a gap to close.)

Honest note on the frontier: the earlier claim that there was "no unblocked
mechanism-level gap left" was wrong, and the false-inert measurement is what showed it.
There is a named, measured false-inert break, now reduced twice and understood to be
bounded by invariant 3.1 (D72): the remaining question is disposition (a stronger
deterministic discipline, or accepting and reporting the bound), not another keyword.

The external jailbreak corpus (`poc/corpus/adapter.py`) remains a PoC loose end and
is not currently available.

---

## 7. How to update this page

At the end of a working session, update sections 2, 4, 5 and 6 to reflect what
changed, and add any new decisions to `DECISIONS.md`. A decision that is only in
a chat and not in `DECISIONS.md` is a decision that will be lost.
