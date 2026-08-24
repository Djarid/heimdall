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

## 0. Resume here (handoff, last updated after D109)

A fresh session should read this block, then section 6, then start work. Everything below
is committed and pushed; the working tree is clean.

**State in one paragraph.** The pipeline contains every consequential case on the
independent corpus: 33 of 33, defence in depth (D83, D84, D85). That is the headline, and it
is now a property of the BUILT system: the D79 to D82 mitigations are imported by
`engine.py` and `gjoll.py` (D84), the last residual class was closed by growing the
consequential-slot vocabulary rather than by a keyword (D85), and Fenrir performs the
STRUCTURAL slot extraction
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
poisoning, contained by Gjoll at action time. D98 then retired D87's now-superseded stand-in
files (`phase2/real_slot_extraction.py`, `phase2/real_slot_demo.py`), since nothing else
imported them. On the declaration seam itself (5.1), all four
scoped directions are now built in-repo: D93 built direction D (a sink's declared effect
primitive is verified against its OBSERVED behaviour, so the WRONG-primitive lie D89-B had only
relocated is caught by evidence for every observable sink), and D94 built direction C, the
integrity axis (a declaration carries an `authoriser` id and a keyed attestation digest, and an
unattested, unknown-authoriser or tampered declaration is refused at load, closing the
config-tamper adversary). What remains on the seam is deployment-phase (public-key signing
rather than the keyed digest, the runtime-taint form of D, opaque-sink handling, all needing
real non-mock sinks) and flow-edge honesty, plus C's load-bearing honesty limit: attestation
binds identity and integrity, not honesty, so a malicious authoriser's lie still verifies and B
and D remain the honesty backstop.

**A separate caveat a fresh session must carry: import wiring is not call invocation (D96).**
D84 wired the mitigation MODULES into `engine.py` and `gjoll.py`, an import-level fact, verified
live by `pipeline_score_harness.integration_status()`. That is a different claim from whether
Gjöll's own gate functions (`ActionProposal`, `evaluate`, `enforce`) are CALLED from any
non-test code path. They are not: `ontology/tests/gjoll_invocation_harness.py` finds six test
call sites (`agentcontext_attestation_harness.py`, `control_surface_harness.py`,
`e2e_harness.py`, `effect_probe_harness.py`, `harness.py`, `memgraph_integration_harness.py`,
the first added by D103 via PR #9, before this build) and zero non-test call sites, so
invariant 3.6 is DEMONSTRATED under harness invocation only, not under live invocation against
a real action.
That absence is the phase-mapped intended state (D74 excludes Gjöll's action-time gate from the
R-1 exception; Himinbjörg, the intended caller, is Phase 3 and essentially unbuilt), not a
defect, and the detector's job is to keep that statement accurate without human memory.

**D97: the control surface's ceiling check is fixed; a gjoll gate residual is named, not
closed.** A read-only audit (`.opencode/plans/bifrost-secure-autonomous-harness-brainstorm.md`,
finding F4) claimed `control_surface.resolve()`'s docstring promised ceiling enforcement that
the body never performed. Tested and confirmed real: `resolve()` now ranks an override's
`trust_ceiling` against the global default's on the trust lattice and CLAMPS an escalation,
fail closed on an unranked level, with a control proving an honest override still passes
through untouched. The audit's second claim, that gjoll's no-registry fallback's
`sink_is_consequential` check is exactly `proposal.sink in agent_consequential_sinks`, so an
empty or mismatched sink set disarms it regardless of the value's `action_critical` status,
also reproduced, and is NOT closed: it is verified, named and documented as a bounded residual
(closed only when `sink_registry` is supplied, D89-B), because a narrower no-registry patch
would reintroduce friction on an honestly-inert sink, and unconditionally requiring a registry
would break every existing no-registry caller including this repo's own D10 mandatory
safe/unsafe proof. `AgentContext` attestation (extending D93/D94's authoriser-plus-digest
pattern to the agent binding itself) was named as a follow-on here, not built: materially larger
than the ceiling fix. It is now BUILT, with three inherited limits stated rather than closed
(D103, below). See D97 in `DECISIONS.md` and `ontology/tests/control_surface_harness.py`.

**D100 then narrowed the gjoll half of D97's residual, without closing it in full.**
`ClassifiedAssertion` now carries an additive `consequential_sinks_at_classify` stamp, set by
`engine.run` from the RESOLVED `AgentContext`, and the no-registry branch derives
consequentiality from that stamp rather than from the unbound `agent_consequential_sinks`
argument supplied at the gate call. This closes the REACHABLE half of D97's item (b): a
hollowed or swapped gate-time argument no longer disarms the block, and a value carrying no
classify-time provenance at all is now also treated fail closed. It does NOT close item (b) in
full: a caller able to rewrite the stamp on a `ClassifiedAssertion` in process, before the gate
call, still disarms the branch, exactly the in-process label-rewrite assumption the gate already
makes for `action_critical` and `trust_level`. The registry-supplied path (D89-B) is untouched.
`AgentContext` attestation (D97's item (c)) was a named, triggered follow-on here, not built and
not given its own `DECISIONS.md` row. It is now BUILT and given its own row, D103, but only on
the identity/integrity axis: three inherited limits are named rather than closed. See D100 in
`DECISIONS.md` and `ontology/tests/control_surface_harness.py`.

**D103 then closed D97's item (c) on the identity/integrity axis, with three limits stated, not
smoothed.** A new shared attested-record substrate, `ontology/nornir/authorisation_record.py`,
extends D94's authoriser-plus-keyed-digest pattern to a new record type, and `AgentContext`
becomes that substrate's first record type, gaining additive `authoriser`/`attestation` fields
(both defaulting `None`, so all 15 existing construction sites keep working unedited).
`resolve()` gains an optional trailing `trusted` parameter; when a `TrustedAuthoriserSet` is
supplied, the binding's attestation is verified BEFORE the D97 clamp, and an altered (a raised
`trust_ceiling`, a HOLLOWED `consequential_sinks` set, a swapped `agent_id` or `authoriser`),
unattested, or unknown-authoriser context is REFUSED (raises), never degraded to a narrower
context, because emptying `consequential_sinks` is the DISARMING direction here, not a safe one.
`Nornir.run` passes the same optional parameter through to `resolve()`, so D100's classify-time
stamp is now taken from a VERIFIED context whenever a trusted set is supplied. Three inherited
limits are carried forward, not closed, stated here rather than smoothed: **(1)** enforcement is
opt-in and no non-test caller supplies a trusted set today, so the unattested path survives,
fail-open-by-omission, mechanised by a live invocation detector rather than left in prose; **(2)**
attestation binds identity and integrity, never honesty, so a trusted authoriser who honestly
attests a HOLLOW `consequential_sinks` set produces a valid attestation of a disarmed surface,
and unlike the sink-declaration seam (D89-B, D93-D), there is NO honesty backstop on the control
surface at all, not even supplying a `sink_registry` to the gate (its D89-B derivation of
`sink_is_consequential` is ANDed with `action_critical`, computed from the agent's own attested
`consequential_sinks`, so a registry cannot supply reachability the agent's context never
granted); **(3)** D100's EC-8 in-process label rewrite (a caller rewriting
`consequential_sinks_at_classify` on a `ClassifiedAssertion` before the gate call) is untouched.
One reported number moves: the invariant 3.1 guard now scans **34** files, not 33
(`ALLOWED_IMPORT_ROOTS` unchanged at 13 roots), because `authorisation_record.py` is a new
module on the authorisation path; the two new harnesses live under `ontology/tests/`, outside
the guard's scan scope. `gjoll.py` is untouched. Both new harnesses are registered as main-suite
fatal-gated obligations, following D102's `run_sink_attestation` pattern. See D103 in
`DECISIONS.md`, `ontology/tests/authorisation_record_harness.py` and
`ontology/tests/agentcontext_attestation_harness.py`.

**D104 fixed a display-only rounding bug found during the D103 build.**
`pipeline_score_harness.py`'s `--thirdparty` percentages were floor-divided rather than
rounded, printing 13 percent and 91 percent where the correct figures are 14 percent and 92
percent; no documented figure was wrong, only the harness's own live output. Fixed and pinned
against recurrence by a new regression check in `ontology/tests/harness.py`. See D104 in
`DECISIONS.md`.

**D105 recorded a working session's capability-mapping matrix for Heimdall's synthesis with
AETOS and Gleipnir.** `plans/synthesis-capability-matrix.md` maps how the synthesis should
proceed given that both sibling projects are under active development: the production runtime
will be compiled Rust, not Python, because an interpreted core is reachable and rewritable by
the population it guards, and the sub-agent cohort pattern generalises, with Heimdall as the
substrate that runs many predefined cohorts rather than being a cohort itself. This is an input
artefact to a future synthesis architecture, not a build plan, and no code changed. See D105 in
`DECISIONS.md` and the new plans file for detail.

**D106 then gave the four control planes concrete module boundaries, grounded in what is
already specified.** `plans/synthesis-architecture.md` places the new process and hierarchy
planes around Himinbjörg, Gjöll, Hliðskjálf and Mímisbrunnr's existing Detailed Design
specifications rather than duplicating or contradicting them, and surfaces two items that
extend D105 without contradicting it: a trust-tier lattice the hierarchy plane's own
configuration needs (the agent registry, the cohort catalogue and the resident coordinator's
configuration), distinct from Mímisbrunnr's data-taint lattice, and a candidate context-shielding
technique for the output plane, not yet ruled on. A proposed Rust workspace layout is sketched,
not finalised, and no code changed. See D106 in `DECISIONS.md` and the new plans file for detail.

**D107 then resolved all seven open items D106 left open in its own section seven.**
`plans/synthesis-resolutions.md` works through each item and rules on it, grounding the ruling
in the relevant Heimdall Detailed Design document, Gleipnir specification or AETOS component,
and confirms an eighth item, Gleipnir's own named engineering seams, needs no ruling because it
was never a Heimdall obligation. The headline rulings: the hierarchy plane's policy tier is
enforced as a load-time-attested manifest extending D103's `AgentContext` attestation pattern,
rather than compiled into the binary; Gjöll's promotion-requirement gate reuses
`promotion_policy.py`'s existing trust-level output, while the other three re-validation gates
get new mechanisms; and two real gaps are closed, notify (adopted as the concrete
delivery-to-the-operator mechanism a full reading of `plans/dd/gjallarhorn.md` confirms it never
defined) and the resident coordinator's memory (built on Gleipnir's newer concept-graph shape
rather than a port of AETOS's SQLite model). No code changed. See D107 in `DECISIONS.md` and the
new plans file for detail.

**D108 then answers the question D105 to D107 left unaddressed: what to build first.**
`plans/synthesis-bootstrap.md` defines a walking-skeleton build-order strategy toward
self-hosting, using Heimdall to build Heimdall, with the cognition plane, the external model
call, stubbed last rather than first because it carries the highest uncertainty. The strategy
converges on a single target loop: a heimdall-dev cohort proposes a real commit and push, gated
by a Rust re-expression of Gjöll inside a minimal Himinbjörg slice, that executes against a real
git remote only if authorised, and is proven only once a deliberately disallowed action is shown
blocked by the same pipeline. A seven-step build order follows, starting with re-expressing Gjöll
in Rust. No code changed. See D108 in `DECISIONS.md` and the new plans file for detail.

**D109 then completes build-order step one: Gjöll's gate is re-expressed in Rust.**
`crates/boundary-gjoll/`, the repository's first Rust crate, carries a pure total rule core (the
three-condition rule plus the D89-A inert-contradiction check) behind a registry-mandatory
consequentiality shell (D81 validation, D89-B derivation). Correctness is checked against 22
golden vectors (six carrying a layer-two section) captured from the three existing Python
harnesses, with SHA-256 digests of `gjoll.py` and `sink_declaration.py` guarding against drift,
folded into `ontology.tests.harness` as an additive `run_rust_gjoll` obligation on
`run_effect_probe`'s exact shape. Three items are designed out entirely, not merely untested:
the Python no-registry branch, D97's named residual and D100's stamp-rewrite limit, all
structurally absent because the shell requires a registry on every call. Four items are named
and deferred: D93's behavioural effect-probe cross-check, D103's `AgentContext` attestation
(out of scope, upstream), D94's sink-declaration attestation and the four re-validation gates
with their `GatePolicy`/`GateResult` scaffold. The workspace pins toolchain channel 1.98.0 with
MSRV 1.85, the crate's `[dependencies]` table is empty, and the conventions this establishes are
recorded once at `plans/rust-workspace-baseline.md` for build-order steps two to seven to
inherit. This build does not advance invariant 3.6's proof status, does not change the 22 RED
findings or the pipeline containment figure, and does not close the sink-declaration root seam.
The code licence stays OPEN and is now a named blocker (section 5). **A stale figure is also
corrected here:** `gjoll_invocation_harness` finds **six** test call sites, not five;
`ontology/tests/agentcontext_attestation_harness.py` (D103, landed via PR #9, before this build)
had already added a sixth by calling `gjoll.evaluate` directly, and the "five" figure this page
and the build spec carried was stale from before this build started, not caused by it. The zero
non-test call sites figure is unaffected. **A line-budget deviation is accepted here too:** the
crate's non-test source came to 671 lines against the spec's own 500-line budget (section 9.1),
171 lines over, about 34 percent (`declaration.rs` 287, `rule.rs` 138, `consequentiality.rs` 118, `types.rs` 106,
`lib.rs` 22); the operator accepted the overage rather than trimming or falling back to
Approach A, since the two-layer split is real architecture, not padding, and `declaration.rs`'s
size reflects genuinely re-expressing D81's five validation conditions plus the effect-primitive
taxonomy, work Approach A would have had to do anyway without the clean module boundary. See
D109 in `DECISIONS.md`.

**Run this first, to see the state for yourself:**

```
poc/.venv/bin/python -m ontology.tests.harness                              # RED at 22 layer-one, expected
poc/.venv/bin/python -m ontology.tests.pipeline_score_harness               # D77: 48% layer-one, 33/33 pipeline
poc/.venv/bin/python -m ontology.tests.pipeline_score_harness --thirdparty  # D88 blind: 14% layer-one, 33/36 pipeline
poc/.venv/bin/python -m ontology.tests.sink_declaration_harness             # D89-B: derive-from-primitive, GREEN
poc/.venv/bin/python -m ontology.tests.effect_probe_harness                 # D93 direction D: verify vs behaviour, GREEN
poc/.venv/bin/python -m ontology.tests.sink_attestation_harness             # D94 direction C: attest who declared, GREEN
```

D95 (the guard's eval/exec/compile detection gap) has no standalone harness file: its three
MUST_CATCH probes and one MUST_NOT_CATCH control live inside `symbolic_guard.py`'s own
`control_check()`, so it is already exercised by `ontology.tests.harness` above (obligation
3.1) and by `control_check()`/`scan()` directly; no new run command is needed for it.

D96 (the Gjöll invocation-boundary detector) does have a standalone entry point for direct
inspection, but it is also registered as obligation 3.6b inside `ontology.tests.harness` above,
so the main run already reports it:

```
poc/.venv/bin/python -m ontology.tests.gjoll_invocation_harness    # six test call sites, zero non-test
```

D97 (the control-surface ceiling fix) and D100 (the gjoll no-registry residual, narrowed) are
likewise registered inside `ontology.tests.harness` (obligation D97/D100), but have a
standalone entry point too:

```
poc/.venv/bin/python -m ontology.tests.control_surface_harness    # resolve() clamps; narrowed residual RECORDED
```

D103 (the `AgentContext` attestation substrate and its own suite) is likewise registered inside
`ontology.tests.harness` (obligations `authorisation_record`, `agentcontext_attestation`), but
has standalone entry points too:

```
poc/.venv/bin/python -m ontology.tests.authorisation_record_harness      # substrate: identity+integrity, GREEN
poc/.venv/bin/python -m ontology.tests.agentcontext_attestation_harness  # AgentContext refused when altered/unattested; three limits RECORDED
```

D109 (Gjöll's gate re-expressed in Rust) is likewise registered inside `ontology.tests.harness`
(`run_rust_gjoll`), but has a standalone entry point too, and the Rust suite itself is run
directly with Cargo from the repository root:

```
poc/.venv/bin/python -m ontology.tests.rust_gate_harness  # digest drift, dependency posture, cargo test: PASS
cargo test -p boundary-gjoll                              # layer-one (22), layer-two (six), D81/D89-B/D10 native tests: PASS
```

**D102 registers D93 and D94 as main-suite fatal-gated obligations, and deliberately leaves
D83 reporting-only.** `effect_probe_harness.py` (D93) and `sink_attestation_harness.py` (D94)
already had standalone entry points but were not wired into `ontology.tests.harness`'s own
fatal count, unlike D96, D97, D100 and D101. Both now are (`run_effect_probe`,
`run_sink_attestation`), following the same pattern as `run_control_surface`: each
sub-harness's own `main()` already returns a real pass/fail code, so a failure there now
folds into the main suite's `fatal` sum instead of staying silent unless run directly.
`pipeline_score_harness.py` (D83) is NOT folded in the same way: its own `main()` is
deliberately a measurement harness, not a pass/fail gate, and always returns 0 even when it
finds an uncontained case, so `run_pipeline_score_reporting` only confirms it still runs
without raising and does not add anything to `fatal`. Forcing that harness's always-0 return
into a fatal count would misrepresent a deliberately reported figure as a bug, against this
repository's own stated preference for honesty over reassurance. See D102 in `DECISIONS.md`.

**The next piece of work, in priority order (detail in section 6):**

1. **Build Vör's minimal single-cohort form: build-order step two (D108).** Step one (D109, Gjöll
   re-expressed in Rust) is now complete; step two builds Vör, a minimal single-cohort agent
   attestation form extending D103's `AgentContext` attestation pattern (keyed digest, verified
   once at process start) rather than the general four-tier lattice. This step is load-bearing
   for the build order's own sequencing: step three (Himinbjörg's minimal four-interface slice)
   depends on step two landing first. See `plans/synthesis-bootstrap.md` section six for the
   full build order and the target loop's definition.
2. **External end-to-end test: DELEGATED (D91), and STRONGER than a corpus (D92).** A colleague
   is running this exact false-inert attack vector against models independently, with no
   exposure to the rules. The key advantage (D92): he can put a VULNERABLE model in the agentic
   role and fire the attacks at the LIVE framework, so it tests the architecture's central claim
   end to end, a model that WOULD be steered is still prevented from acting because trust is
   structural at the boundary, which no corpus and no in-repo run has reached (a corpus only
   ever exercises layer one). It is the first OBSERVED (not simulated) containment measurement
   and inverts the D75 negative finding: a vulnerable model WILL attempt the action, so it
   reaches the case D75's robust model could not. So do NOT re-attempt in-repo: the in-session
   ceiling was already reached (D88 5/36 blind, D77 16/33 rules-aware, both lower bounds). When
   the result lands, record it as its own decision and update invariant 3.6's proof status and
   D67-fix's disposition; a pass is bounded containment (not universal), a fail is a genuine
   architecture finding.
3. **Attest the declarations: all four scoped directions (A, B, C, D) now built in-repo.** D81
   closed declaration ERROR or DRIFT; D89 narrowed the HONESTY seam on two axes (B derives sink
   consequentiality from an attested effect-primitive table so a money sink flagged
   non-consequential is still gated; A blocks an action-critical value dishonestly declared
   CONSUME_INERT); D93 built direction D, verifying the declared effect primitive against the
   sink's OBSERVED behaviour so the WRONG-primitive lie is caught by evidence for every
   observable sink; and D94 built direction C, the INTEGRITY axis: a sink declaration carries an
   `authoriser` id and a keyed `attestation` digest (`ontology/nornir/sink_attestation.py`), and
   `SinkRegistry.declare_attested` REFUSES an unattested, unknown-authoriser or tampered
   declaration at load, closing the config-tamper / supply-chain adversary. The remaining
   root-seam work is DEPLOYMENT-PHASE, not in-session buildable: public-key signing (D94 built a
   keyed-digest demonstration, not asymmetric non-repudiation, 5.7), the runtime-taint form of D
   (a live taint check on real sink outputs), and opaque-sink handling (both need real sinks,
   which are still mocked); plus the flow-EDGE honesty. Two honest limits are load-bearing and
   asserted, not smoothed: C binds IDENTITY and INTEGRITY, never HONESTY, so a MALICIOUS
   AUTHORISER's lie still verifies (B and D are the honesty backstop, not C); and coverage
    breadth stays untested. All named in `plans/declaration_attestation_scoping.md`.
4. **True token-level grammar-constrained decoding: DONE (D90).** Replaced D87's bounded
   per-field stand-in with a real token-level grammar mask: the model emits the whole
   `SlotExtractionSchema` object under a logits processor that permits only tokens keeping the
   output a valid grammar prefix, so a malformed object or an undeclared key is unreachable and
   there is no free-text to re-parse (the `fenrir.md` 3.1 property). Implemented natively on
   mlx_lm's `logits_processors` hook (no outlines/xgrammar dependency), the grammar proven
   deterministically without a model (`phase2/tests/harness.py` obligation 7) and demonstrated
   on Qwen2.5-7B end to end (`phase2/grammar_slot_demo.py`). Residual, unchanged: it constrains
   STRUCTURE, not value TRUTH, so value poisoning stays a Gjoll concern.

   The remaining named work, now that tasks 2 to 4 are addressed: the EXTERNAL-HUMAN corpus
   (task 2's residual), and the declaration follow-ons C (attest who may declare) and D (verify
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
- Do not trust a docstring's claim of enforcement without reading the body: D97 found
  `control_surface.resolve()`'s docstring claimed a ceiling check that the body never
  performed (`return agent`, no check at all). Verify a claimed check by probing it, the same
  discipline D93 to D96 each applied to their own gap, before trusting or fixing it.
- Gjoll's no-registry fallback (`sink_registry=None`) carried a real, bounded, DOCUMENTED
  residual (D97): `sink_is_consequential` there was exactly `proposal.sink in
  agent_consequential_sinks`, with no independent source of truth, so a hollow or mismatched
  sink set at the gate call disarmed it. D100 NARROWED this: the branch now derives
  consequentiality from the classify-time `consequential_sinks_at_classify` stamp the value
  already carries, so a hollowed or swapped gate-time argument no longer disarms it, and a
  value with no stamp at all is fail closed too. What remains is narrower and still a real,
  DOCUMENTED residual, not a bug to "fix" here: a caller able to rewrite the stamp on a
  `ClassifiedAssertion` in process, before the gate call, still disarms the branch, exactly the
  in-process label-rewrite assumption the gate already makes for `action_critical` and
  `trust_level`, and this is out of the threat model, not mitigated. Always supply
  `sink_registry` in new code; do not OR the value's `action_critical` flag into
  `sink_is_consequential` to "close" the no-registry branch further, that reintroduces friction
  on an honestly-inert sink (checked and rejected in D97's own text, and still forbidden by
  D100, REQ-7 and REQ-8).

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
IMPORTED into `engine.py` and `gjoll.py` (D84). Scored as defence in depth rather than by the
classifier alone, the pipeline contains 33 of 33 consequential cases, 100 percent, against
the 48 percent layer-one rate, after D85 closed the last residual class by slot-vocabulary
growth (D83, D84, D85). So the break is a degraded outer layer rather than an open door: the
classification layer is measurably weak and stays red, and the guarantee does not rest on it.
This is an import-wiring fact (D84), not a claim that Gjöll's gate functions are called from
any non-test code path; they are not, and D96's detector states that separately below.
D97 fixed a further, DIFFERENT gap in the control surface itself: `resolve()` now actually
enforces the trust ceiling it always claimed to (an escalating override is clamped, not
silently honoured), and named, without closing, a bounded residual in gjoll's no-registry
fallback (an empty or mismatched `agent_consequential_sinks` at the gate call could still
disarm it; the registry-supplied path, D89-B, is unaffected). D100 then narrowed that residual:
the branch now derives consequentiality from the classify-time stamp a value already carries
rather than from the gate-time argument, so neither a hollowed argument nor a value with no
stamp at all disarms the block any more. What survives is narrower still: a caller able to
rewrite the stamp on a `ClassifiedAssertion` in process, before the gate call, is out of the
threat model, exactly as it already is for `action_critical` and `trust_level`.
D103 then closed D97's item (c), the agent binding's own attestation, on its identity/integrity
axis only: `AgentContext` becomes a record type on a new shared substrate
(`ontology/nornir/authorisation_record.py`, extending D94's authoriser-plus-digest pattern), and
`resolve()` REFUSES an altered, unattested or unknown-authoriser context when a
`TrustedAuthoriserSet` is supplied. Three limits are named, not closed: enforcement is opt-in
(no non-test caller supplies a trusted set today); attestation binds identity and integrity,
never honesty, and the control surface has no honesty backstop at all, not even a supplied
`sink_registry`; and D100's EC-8 in-process label rewrite stays untouched. The invariant 3.1
guard's scanned-file count moves from 33 to 34 (one new module, `ALLOWED_IMPORT_ROOTS`
unchanged at 13 roots).

D109 then completed build-order step one of `plans/synthesis-bootstrap.md` (D108): the same gate
these decisions describe is now also re-expressed in Rust, at `crates/boundary-gjoll/`, checked
against 22 golden vectors captured from the Python harnesses these decisions already cover.
This is a translation-fidelity claim, not a new proof: it does not advance invariant 3.6's proof
status, does not change the 22 RED findings and does not close the sink-declaration root seam.
The Python reference (`ontology/nornir/gjoll.py`) is untouched and stays the reference
implementation. The crate's non-test source came to 671 lines against the spec's own 500-line
budget, 171 lines over; the operator accepted the overage as the cost of a genuine two-layer
split rather than trimming the crate or reverting to a single-layer approach.

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
| `DECISIONS.md` | The decision log: 109 tracked decisions (D77 the independent corpus measuring layer-one false-inert at about 48 percent, D78 the correction that the false-inert break does NOT defeat Gjoll because action-critical status is reachability-derived, D79 to D82 the four false-inert mitigations, D83 the defence-in-depth pipeline score, D84 wiring the mitigations into the live engine and gate, D85 closing the residual class by slot-vocabulary growth, D86 Fenrir structural slot extraction feeding the state-delta layer, D87 the real-model demonstration of that extraction, D88 the blind-authored third-party corpus measuring layer-one at 5/36, D89 narrowing the root declaration seam by deriving sink consequentiality from an attested effect-primitive table plus a fail-closed consume mode, D90 true token-level grammar-constrained decoding replacing the bounded per-field stand-in, D91 delegating the genuinely third-party corpus to an external tester, D92 scoping that external test as the first OBSERVED end-to-end containment test with a vulnerable model in the agentic role, D93 direction D verifying a sink's declared effect primitive against its observed behaviour to close the wrong-primitive lie for observable sinks, D94 direction C attesting who declared a sink via a keyed digest to close the config-tamper adversary and complete all four scoped declaration directions in-repo, D95 closing the guard's own eval/exec/compile detection gap that three prior adversarial rounds missed, D96 mechanising the import-wiring-versus-live-call-invocation distinction as an AST detector, D97 fixing `control_surface.resolve()`'s unenforced trust ceiling and naming, without closing, gjoll's no-registry `agent_consequential_sinks` residual, D98 retiring D87's now-superseded stand-in files and closing a staleness gap in `poc/OUTCOME.md`, D99 finding the BFO cross-domain relatedness claim had no automated check, D100 narrowing gjoll's no-registry residual with a classify-time stamp, D101 closing D99's gap with a mechanised relatedness harness, D102 registering D93/D94 as main-suite fatal-gated obligations, D103 attesting `AgentContext` as a record type on the new shared `authorisation_record.py` substrate, closing D97's item (c) on its identity/integrity axis only, with three inherited limits named rather than closed) plus the still-open D67-fix layer-one break, with consistency checks |
| `phase2/` | The Phase 2 detection layer: Fenrir (sandbox reader) and Huginn (canary + attempt-introspection monitoring), built under D74. Deterministic logic suite green; the real-model demonstration returned the D75 negative finding. See `phase2/OUTCOME.md` |
| `STATUS.md` | This page |
| `AGENTS.md` | Standing instructions for agents working on the repo, including the currency rule; auto-loaded by opencode |
| `plans/hld.md` | The High-Level Design: the build-oriented engineering view of the whole system across all six phases, with a per-component achievement baseline, a harness-agnostic integration interface and a risk register (D73) |
| `plans/dd/` | The Detailed Design, implementation fidelity for Phases 1-3: an index (conventions, the OpenCode/Gleipnir harness binding, cross-cutting contracts) plus eight component documents (Bifröst, Mímisbrunnr, Nornir, Fenrir, Hliðskjálf, Himinbjörg, Gjöll, Gjallarhorn) (D73) |
| `plans/hld_scoping_brainstorm.md` | The scoping analysis behind D73: the achievement audit and the three converged decisions (harness, classifier stance, phasing) |
| `plans/synthesis-capability-matrix.md` | The capability-mapping matrix for Heimdall's synthesis with AETOS and Gleipnir: what each contributes, the four control planes, and the rulings and open items from that working session (D105) |
| `plans/synthesis-architecture.md` | The follow-on architecture draft: concrete module boundaries for the four control planes, grounded in Himinbjörg, Gjöll, Hliðskjálf and Mímisbrunnr's existing Detailed Design documents, plus a hierarchy-plane trust-tier lattice, a candidate context-shielding technique and a sketched Rust workspace layout (D106) |
| `plans/synthesis-resolutions.md` | Resolves all seven open items `plans/synthesis-architecture.md` carried forward in its own section seven: the sandbox, Gjöll's gate policy, the hierarchy policy tier, context shielding, notify, coordinator memory and the absorption seam, plus confirming the master-control tier stays deferred and that Gleipnir's own open seams need no ruling (D107) |
| `plans/synthesis-bootstrap.md` | The build-order strategy: a walking skeleton toward self-hosting, cognition stubbed last, converging on a single target loop, a gated real git commit and push, and a seven-step build order starting with re-expressing Gjöll in Rust (D108) |
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
  marshalling-contract check (D62), the false-inert measurement (D67), and the
  BFO cross-domain relatedness check (D101, `run_bfo_relatedness`): every
  `DOMAIN_TYPE`/`FAILSAFE` node resolves a non-None anchor and every domain/failsafe
  root shares one BFO anchor, closing the gap D99 named (the domain attach test
  proved isolation, not relatedness). The suite
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
against a REAL model (D87): a bounded per-field generation stand-in reused the PoC's proven
mechanism (`_StopOnNewline`, isolated-payload splice) to fill the schema values, and on
Qwen2.5-7B it bound `salary_destination` from an inertly-phrased payroll redirect the
classifier still typed inert, with the benign control binding nothing (fail-closed). D90
then replaced that stand-in with true token-level grammar-constrained decoding
(`phase2/grammar_slot_extraction.py`, `phase2/grammar_slot_demo.py`), demonstrated end to
end on Qwen2.5-7B the same way; D98 retired D87's now-superseded stand-in files
(`phase2/real_slot_extraction.py`, `phase2/real_slot_demo.py`), confirming first that
nothing else imported them. The demo is optional and skip-if-absent, like
`e2e_harness.py`. Value poisoning, not structural or well-formedness failure, is the
named remaining refinement, contained by Gjoll at action time, not here.
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
- **The repository's first Rust crate** (`crates/boundary-gjoll/`, D109): re-expresses Gjöll's
  action-time gate as a two-layer boundary, a pure total rule core behind a registry-mandatory
  consequentiality shell, in a Cargo workspace pinning toolchain channel 1.98.0 with MSRV 1.85
  and an empty `[dependencies]` table. Checked against 22 committed golden vectors (six carrying
  a layer-two section) exported from the three existing Python harnesses
  (`ontology/tools/export_gate_vectors.py`), with SHA-256 digests of `gjoll.py` and
  `sink_declaration.py` guarding against drift (`ontology/tests/rust_gate_harness.py`, folded
  into the main suite as `run_rust_gjoll`, `run_effect_probe`'s exact shape). Test code and
  implementation code live in separate files in separate directories, so `run_gjoll` itself
  stays byte-identical. Designs out the Python no-registry branch, D97's named residual and
  D100's stamp-rewrite limit (structurally absent, not merely untested); defers D93's
  behavioural cross-check, D103's `AgentContext` attestation, D94's sink-declaration attestation
  and the four re-validation gates' `GatePolicy`/`GateResult` scaffold. Proves translation
  fidelity against the Python reference, which stays untouched; does not advance invariant 3.6's
  proof status or change the 22 RED findings. The code licence is OPEN (section 5). See
  `plans/rust-workspace-baseline.md` for the conventions this establishes for build-order steps
  two to seven.
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
| D100 narrowed the gjoll no-registry `agent_consequential_sinks` residual D97 named: consequentiality now derives from the classify-time stamp a value already carries, so a hollowed or swapped gate-time argument, or a value with no stamp at all, no longer disarms the block | SETTLED (narrowed, not fully closed) | The narrow remaining gap is a caller able to rewrite the stamp on a `ClassifiedAssertion` in process, before the gate call; out of the threat model, the same footing as `action_critical`/`trust_level` today |
| D103: `AgentContext` attestation (D97's item (c), identity/integrity axis only) | SETTLED (with three limits) | Built: `ontology/nornir/authorisation_record.py` extends D94's authoriser-plus-digest pattern to a new record type, and `AgentContext` becomes its first record type, verified at `resolve()`/`Nornir.run` when a `TrustedAuthoriserSet` is supplied; an altered, unattested or unknown-authoriser context is REFUSED. Three limits stated, not closed: (1) enforcement is opt-in, no non-test caller supplies a trusted set today; (2) attestation binds identity and integrity, never honesty, and unlike the sink-declaration seam there is NO honesty backstop at all on the control surface, not even a supplied `sink_registry`; (3) D100's EC-8 in-process label rewrite stays untouched. For the same reason as (2) and (3), it does NOT close D100's own narrow remaining gap (a caller rewriting the stamp in process) |
| D99 cross-domain relatedness has no automated check: `Ontology.ancestors()`/`anchor_of()`/`parents()` have zero callers, so the D23/D29/D59 claim that all domains anchor to the same BFO class is verified only by prose and by an attach test that proves isolation, not relatedness | SETTLED (closed by D101) | D101 added `run_bfo_relatedness` to `ontology/tests/harness.py`: every `DOMAIN_TYPE`/`FAILSAFE` node must resolve a non-None anchor, and the domain/failsafe roots must share exactly one BFO anchor, both checked against a mandatory negative control first. Live-verified on the seed ontology (23 nodes, six roots, one shared anchor, `bfo:generically_dependent_continuant`); the RED bar stayed at exactly 22, unaffected. This is a regression check re-verified on every run, not a one-off proof that a future domain will anchor correctly |
| **D109: the code licence is OPEN and blocks publication.** No source file in this repository carries a licence header, Python or Rust; `LICENSE.md` covers documentation only (CC-BY-SA-4.0), and `crates/boundary-gjoll/Cargo.toml` deliberately carries no `license` field | OPEN (blocker) | Must be settled before any code in this repository is published. `LICENSE.md`'s Scope section names AGPL-3.0-or-later only as an example (`e.g.`), so the question is genuinely unsettled and is a one-way door once decided; retro-heading the existing Python is part of settling this, not a separate task |

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
again and showed the residual is bounded by invariant 3.1 (D72). A later pass over the guard
itself found that D68, D70 and D71 had all hunted for indirect MODULE routes and never named
a call that interprets a string as code, so `eval`/`exec`/`compile` (bare or a
`builtins`-aliased qualified call) went unflagged; the guard now catches all three
unconditionally, without inspecting string content, closing that residual (D95). The
mitigation modules were then
IMPORTED into `engine.py` and `gjoll.py` (D84), closing the integration gap that had made the
D83 score the designed pipeline, and the D83 residual class was closed by growing the
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
BUILT property: the D79 to D82 mitigations are imported by `engine.py` and `gjoll.py` (D84,
an import-wiring fact; Gjöll's own gate functions still have zero non-test callers, D96), the
last residual class was closed by slot-vocabulary growth (D85), and Fenrir performs the
structural slot extraction that feeds the state-delta layer end to end, demonstrated first
against a mock (D86) and now against a REAL model (D87, Qwen2.5-7B via the PoC's bounded
generation). The layer-one classifier on its own still misses 48 percent (D77, D83) and stays
OPEN and RED (17 findings), because that break is bounded by invariant 3.1 and no content
pattern closes it; the guarantee does not rest on it. With the real-model structural
extraction now demonstrated, the highest-value work is testing the whole thing against a
corpus the author never saw.

1. **External end-to-end test: DELEGATED (D91), STRONGER than a corpus (D92).** The
   independent scenario-authored corpus (D77) raised the measured layer-one rate from 1/17 to
   16/33, and the BLIND-authored corpus (D88, `false_inert_thirdparty.json`) reached 5/36, the
   strongest independence obtainable inside a session; both are lower bounds on difficulty, not
   unbiased estimates, and both only ever exercised LAYER ONE. The external work is owned
   out-of-band AND is a stronger evidence class (D92): the colleague can put a VULNERABLE model
   in the agentic role and fire the attacks at the LIVE framework, testing the architecture's
   central claim end to end (a model that WOULD be steered is still prevented from acting), the
   first OBSERVED (not simulated) containment measurement, and the case D75's robust model could
   not reach. Do not re-attempt in-repo. When the result lands, record it as its own decision
   and update invariant 3.6's proof status and the D67-fix disposition; a pass is bounded
   containment, a fail is a genuine architecture finding.
2. **Attest the declarations: all four scoped directions (A, B, C, D) built in-repo.** D81
   closed declaration ERROR or DRIFT; D89 narrowed the HONESTY seam (B derives sink
   consequentiality from an attested effect-primitive table; A blocks an action-critical value
   dishonestly declared CONSUME_INERT); D93 built direction D (verify the declared effect
   primitive against OBSERVED behaviour, `ontology/nornir/effect_probe.py`, the verdict entering
   the gate via `evaluate`/`enforce`'s `effect_observations` parameter as a fail-closed OR); D94
   built direction C, the INTEGRITY axis (`ontology/nornir/sink_attestation.py`: an `authoriser`
   id and keyed `attestation` digest on the declaration, `SinkRegistry.declare_attested` refuses
   an unattested/unknown/tampered one at load, closing the config-tamper adversary). Remaining is
   deployment-phase and needs real non-mock sinks: public-key signing (D94 is a keyed-digest
   demonstration, 5.7), the runtime-taint form of D, and opaque-sink handling; plus flow-EDGE
   honesty. Load-bearing limit: C binds identity/integrity, not honesty, so a malicious
   authoriser's lie still verifies (B and D are the backstop). Scoped in
   `plans/declaration_attestation_scoping.md`.
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
5. **Queued: build Gjöll's missing re-validation gate mechanism (Approach E, D96).** Not
   started. `GatePolicy`, `GateResult` and the promotion-requirement gate (`plans/dd/gjoll.md`
   section 5.1, lines 86-90; section 8; section 10) do not exist, so invariant 3.6's "has not
   passed the gate" clause is currently vacuous: no branch of `evaluate` lets an
   action-critical value pass, because there is no gate to pass. `gjoll.md` section 10 names
   the promotion requirement as the one that "must be built", and section 8 lists gate
   policies as data Gjöll itself owns, so this is inside Gjöll's own boundary and does not
   pre-empt Himinbjörg's unfinalised design. It is queued rather than started because it
   touches the authorisation path while the external test (item 1) is in flight, and because
   starting it now would let a documentation/detector change (D96) drift into a Phase-3
   component build. Design question left open for when it starts: whether the gate reuses
   `promotion_policy.py`'s corroboration logic or is a separate mechanism.
6. **Built: the D97 follow-on on the control surface, `AgentContext` attestation, on its
   identity/integrity axis (D103).** D97 named two follow-ons; D100 built the first (the
   no-registry `agent_consequential_sinks` residual, narrowed rather than requiring
   `sink_registry` unconditionally or an attested `AgentContext`), and D103 now builds the
   second: `ontology/nornir/authorisation_record.py` extends D93/D94's authoriser-plus-keyed-
   digest pattern from sink declarations to the agent binding itself, and `resolve()`/`Nornir.run`
   REFUSE an altered, unattested or unknown-authoriser `AgentContext` when a
   `TrustedAuthoriserSet` is supplied, closing the identity/integrity half of Gleipnir's G-1
   failure ("the guard's own configuration reachable/editable by the population it guards")
   reproduced inside Heimdall (F4). What remains, named as requirements rather than closed:
   **(1)** enforcement is opt-in, and no non-test caller supplies a trusted set today, so the
   unattested path survives by omission, mechanised by a live invocation detector rather than
   left in prose; **(2)** attestation binds identity and integrity, never honesty, so a trusted
   authoriser who honestly attests a HOLLOW `consequential_sinks` set produces a valid
   attestation of a disarmed surface, and the control surface has NO honesty backstop at all,
   not even a supplied `sink_registry`, unlike the sink-declaration seam (D89-B, D93-D); **(3)**
   D100's EC-8 in-process label rewrite (a caller rewriting the classify-time stamp before the
   gate call) is untouched, and for the same reason D103 does not close D100's own narrow
   remaining gap either. The invariant 3.1 guard's scanned-file count moves from 33 to 34 (one
   new module; `ALLOWED_IMPORT_ROOTS` unchanged at 13 roots). `trust_ceiling`'s scale stays
   OPEN, unresolved by this build.
7. **Done: build-order step one of `plans/synthesis-bootstrap.md` (D108), re-expressing Gjöll's
   gate in Rust (D109).** `crates/boundary-gjoll/` carries a pure total rule core behind a
   registry-mandatory consequentiality shell, checked against 22 golden vectors (six with a
   layer-two section) exported from the three existing Python harnesses, with a source-digest
   drift detector folded into the main suite. It designs out the Python no-registry branch,
   D97's named residual and D100's stamp-rewrite limit; it defers D93's cross-check, D103's
   `AgentContext` attestation, D94's sink-declaration attestation and the four re-validation
   gates. **Next queued: build-order step two, Vör** (one hardcoded attested cohort), per
   `plans/synthesis-bootstrap.md`'s seven-step order; steps 3 to 7 (Himinbjörg's minimal slice,
   the git actuator, the process engine, the end-to-end loop, real cognition) follow it. The
   code licence (section 5) blocks publication of this crate and should be settled before
   step two adds a second one.

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
