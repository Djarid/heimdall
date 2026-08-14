# Design Brief (RESEARCH): Heimdall HLD/Detailed-Design Scoping

**Status:** Part A achievement audit + Part B Decision Analysis — **OPERATOR-CONVERGED
at the precept-10 gate** (see Selected Approach below). This brief was originally
authored by the Gleipnir `gleipnir-brainstorm` agent (whose write grant is limited to
Gleipnir's own Tier-0 `plans/`), then relocated here to the Heimdall repo where it
belongs, since its subject matter is Heimdall and it is not part of Gleipnir's
enforcement boundary. The three material Part-B decisions were surfaced to the operator
via the orchestrator's `question` tool, and the operator's converged choices are
recorded in the Selected Approach section. The full Decision Analysis is retained below
as the justification for those choices.

**Read target:** `/Users/jasonh/git/heimdall/`. Companion artifact: `plans/HLD.md`
(the High-Level Design authored from this converged brief).

---

## Problem Statement

Heimdall (`HEIMDALL.md` v0.11, 1058 lines) is a comprehensive *specification* for a
neurosymbolic autonomous-agent security architecture: separate data channel from
control channel so an LLM can never act on instructions smuggled in untrusted
content. A deterministic symbolic layer owns all authorization; LLMs only propose.
The author wants to move from the current proven-premise / built-seed state toward
an implementation-ready HLD + Detailed Design, and must decide (1) target harness
(pi.dev as specified vs OpenCode, given a mature OpenCode framework — Gleipnir —
exists one directory over), (2) the Detailed-Design stance on the open false-inert
classification break (D67-fix), and (3) how far / at what fidelity the Detailed
Design should reach across the 6 Build Phases.

## Constraints

- HEIMDALL.md's Harness Integration is written entirely against pi.dev hooks
  (`before_provider_request`, `before_agent_start`, `project_trust`, tool-call
  interception, episode capture). Open Question 4 defers OpenCode to post-Phase-1.
- The project's own discipline: a RED test suite that *names* a real break is worth
  more than a green one that never tested it; do not patch classification with more
  keywords (invariant 3.5; D54/D55).
- D67-fix (false-inert break) is explicitly OPEN, measured 1/16 (down from 3/12),
  suite deliberately red.
- Build Phases 1-3 alone are ~5-7 months of the roadmap (4-6wk + 2-3mo + 2-3mo).

---

## Part A — Achievement Audit (evidence-grounded)

Classification key: **PROVEN** (running code + passing tests) / **DEMONSTRATED**
(partial / spike / seed-level, not production-integrated) / **SPECIFIED-ONLY**
(design in HEIMDALL.md, ~no code) / **OPEN** (unresolved per DECISIONS.md) /
**NOT ADDRESSED**.

All code below was read and confirmed to implement what its OUTCOME.md claims —
this audit is grounded in the artifacts, not the summarizing prose.

| Component (role) | Status | Evidence | DELTA to deployable Phase 1-3 |
|---|---|---|---|
| **Bifröst** (taint boundary) | **DEMONSTRATED (PoC shape)** | `poc/symbolic.py` (148 ln): deterministic email parse, `provenance=UNTRUSTED` stamp, control-marker neutralisation, out-of-band token-id boundary (`poc/neural.py`). Invariants 3.2/3.3 PROVEN. `ontology/media/` records taint-class→parser bindings as data only. | No live multi-medium parser layer (web/doc/OCR/STT = Phase 4). Single-crossing-point enforcement is PoC-scale, one medium (email). Mixed-trust-source re-stamping (ADVERSARIAL_REVIEW 5.9) unaddressed. |
| **Nornir** (classifier + reasoner) | **DEMONSTRATED, with one RED obligation** | `ontology/nornir/` real: `rules.py` (370 ln, 4 rule kinds, risk-tier priority principle D31/D52, shared `carries_imperative_or_consequence` guard D69), `engine.py`, fail-closed `unclassified.py`. Harness `ontology/tests/harness.py` (706 ln) runs 8.1-8.4. **8.2 classification correctness is FAILING: false-inert 1/16 (D67).** | Close/scope D67-fix (see Part B Q2). Coverage 36/38 on a self-authored 4-domain seed — breadth untested; independent-labelled corpus not built. Model-authored-rule provenance hole open (D68 note). |
| **Mímisbrunnr** (world model store) | **DEMONSTRATED (spike + binding)** | `spike/substrate/reachability.py` (322 ln): support-counted incremental flow-to-sink, sound conservative + exact retraction; `memgraph_store.py`/`memgraph_harness.py` bind to live Memgraph (D57, 1800 fuzzed ops zero-unsound). D25/D32/D38 ratified. | Live store is *optional skip-if-absent* verification, not the production world-model service. No persistent typed-node schema for real ingestion; no causal graph; per-batch is default (cross-batch only in `persist=True`, ADVERSARIAL_REVIEW 5.5). |
| **Himinbjörg** (gateway / control surface) | **SPECIFIED-ONLY (rich) + tiny DEMONSTRATED slice** | HEIMDALL.md 294-401: full agent-definition YAML (trust_level 0-5; controls: tools/filesystem/network/credentials/subagents/inter_agent/resources/exfiltration/temporal/escalation), 6-step proposal validation, global-default+override. Built: `ontology/yggdrasil/control_surface.py` (73 ln) — a **minimal dormant** `AgentContext` (agent_id, permitted_actions, trust_ceiling, consequential_sinks) only. | The gateway process itself does not exist. ~4 of ~20 control fields modelled. No proposal-validation pipeline, no credential broker, no tool-call interception, no context-construction-from-world-model. This is the single largest Phase-3 build. |
| **Gjallarhorn** (alert/escalation) | **SPECIFIED-ONLY** | HEIMDALL.md 405-413 + threat-model rows; `rules.py` `check_constraints`→"a violation is a Gjallarhorn event" (naming only). | No alert routing, aggregation, containment-decoupled-from-alerting, or protected escalation channel. Phase 3. |
| **Huginn** (introspection/anomaly) | **SPECIFIED-ONLY** | HEIMDALL.md canary hard/soft signal tables + attempt-introspection (513-592). D34 (honest-vs-injection features) OPEN. | Zero code. Episode capture, canary monitoring, baselining all unbuilt. Phase 2 (canary) / Phase 5 (patterns). |
| **Muninn** (episode store) | **SPECIFIED-ONLY** | HEIMDALL.md Phase 5; glossary. | Zero code. Phase 5. |
| **Odin** (self-modification proposer) | **OPEN / SPECIFIED-ONLY** | HEIMDALL.md 1005-1007, Open Q3; D26/D27/D35. Self-modification is the *only* human-approval-gated path; D35 OPEN (excluded). | Zero code. Provenance-gated proposal path is Phase 5-6. The one deliberately-KFA-gated loop. |
| **Hliðskjálf** (audit log) | **DEMONSTRATED in spirit only** | Harnesses are "audit artefacts, failures loud" (invariant 3.10 PROVEN as a *harness* property). Signed append-only chain is a trust-root assumption (threat model). | No signed append-only log service exists. Phase 2 ("Hliðskjálf logging all decisions"). |
| **Fenrir** (sandbox agent) | **DEMONSTRATED in shape, not deployment** | PoC `neural.py` is tool-less, egress-free, fresh-context extraction (invariant 3.8 DEMONSTRATED-in-shape). Canary mechanism / attempt-introspection fully SPECIFIED (HEIMDALL.md 519-592) but unbuilt. | No segmented sandbox deployment, no network-policy egress test, no canary wrapping, no Huginn monitoring, no attempt-introspection tripwire. Phase 2. |
| **Gjöll** (value-integrity / action-time gate) | **DEMONSTRATED (gate shape + action-critical)** | `ontology/nornir/gjoll.py` (151 ln): real four-term-conjunction gate, fails closed, blocks before actuator fires; wired to flow-to-sink action-critical (D58). Provenance-gate half PROVEN (PoC `sinks.py`). | Sink/flow declarations are *unattested trusted input* (ADVERSARIAL_REVIEW 5.1 — "the root"): no schema, no signing, no behaviour-derivation (`consumes` is an unchecked dict). Re-validation modes (re-derivation, semantic constraint, corroboration) specified not built. Phase 3. |
| **Yggdrasil** (ontology) | **DEMONSTRATED (4-domain seed)** | `ontology/yggdrasil/` real: `core.py` (BFO-anchored nodes, verified IRIs), `spine/`, 4 `domain/` modules, `media.py`, `unclassified.py`; BFO 2020 loaded, SUMO reference-only (D39/D40). Attach test D29 demonstrated 3×. 45-58 nodes. | Seed only. Coverage breadth untested; growth is hand-authored (Odin path Phase 5). Upper-ontology load-and-extend against live store is a low-risk residual. |

**Audit bottom line.** Two of eleven components are *demonstrated to a meaningful
depth* (Nornir/Yggdrasil as a seed with a named red break; Mímisbrunnr/Gjöll's
algorithm via spike+binding). The **taint-boundary premise (invariants 3.1-3.10) is
genuinely PROVEN** at PoC scale — the core value proposition holds. The **entire
control surface (Himinbjörg), the introspection triad (Huginn/Muninn/Odin),
Gjallarhorn, Hliðskjálf, and the deployed Fenrir sandbox are SPECIFIED-ONLY.** The
project's honesty discipline is unusually high: the red suite, the four named
guarantee bounds (coverage / inert-rule precision / declaration honesty / human
reviewer), and two rounds of adversarial self-review are all in-repo and verified.

---

## Part B — Decision Analysis (see full text in the agent's final report)

Three material decisions, NOT converged here. The orchestrator surfaces them to the
operator; the operator's converged choices are then recorded. Advisory
recommendations (input to convergence, not the decision):

- **Q1 (target harness):** Advisory lean → **HLD harness-agnostic; DD targets
  OpenCode/Gleipnir primitives as the Phase-1 reference implementation, pi.dev kept
  as the abstract contract.** Reversibility: two-way door at HLD level. Legitimate
  re-scoping (real infra now exists that didn't when Open Q4 was written), not
  reopening a settled call — but flagged for anchoring/IKEA/bandwagon bias.
- **Q2 (D67-fix stance):** Advisory lean → **(b) design the classifier interface
  swappable/pluggable so D67-fix can be slotted later, without committing to the
  candidate fix's specifics now.** Honours the project discipline (don't pre-commit
  an unproven-at-scale fix; don't block all DD on one open research item).
- **Q3 (DD fidelity/phasing):** Advisory lean → **(b) full HLD across all 6 phases;
  implementation-ready DD scoped to Phases 1-3; Phases 4-6 HLD-level with a named
  follow-on DD pass.** RICE-favoured; guards against scope-creep bias.

## Selected Approach (OPERATOR-CONVERGED at the precept-10 gate)

The operator converged, via the orchestrator's `question` tool at the precept-10
convergence gate, on the advisory recommendation for all three questions. The full
Decision Analysis above is the justification; the choices are:

- **Q1 — Target harness: CONVERGED → HLD harness-agnostic + DD targets
  OpenCode/Gleipnir.** The HLD stays harness-agnostic: the five pi.dev extension
  hooks (`before_provider_request`, `before_agent_start`, `project_trust`, tool-call
  interception, episode capture) are abstracted into a **portability interface at the
  HLD boundary** (this is Open Question 4's "abstraction layer", pulled forward only
  to the HLD seam). The **Detailed Design targets OpenCode/Gleipnir primitives as the
  Phase-1-3 reference implementation** — leveraging the proven deny-by-default
  permission map, the Tier-0/1/2/3 authority ladder, the G-5 deterministic
  sequencing and the enumerable-bypass lesson. Recorded as a *legitimate re-scoping*
  (real infrastructure now exists that did not when Open Q4 was written), not a
  reopening of a settled sequencing call. Bias caveats (anchoring on Open Q4's
  framing; IKEA/bandwagon pull toward the author's own neighbouring framework) were
  surfaced to the operator before convergence.

- **Q2 — D67-fix stance: CONVERGED → pluggable classifier + tracked arming gate
  (option b).** Nornir's classifier is designed as a **pluggable/swappable component
  with a fail-closed default as the interface contract**. The DD does **not** commit
  to the candidate fix's specifics now. **D67-fix + an independent-corpus
  re-measurement is tracked as a REQUIRED gate before any consequential capability is
  armed.** This honours the project's own discipline (a red suite naming a real break
  is worth more than a false green; no keyword treadmill, invariant 3.5 / D54 / D55)
  while keeping the structural DD unblocked.

- **Q3 — DD fidelity/phasing: CONVERGED → full HLD (6 phases) + DD scoped to Phases
  1-3 (option b).** The **HLD covers all 6 Build Phases** at architecture level so
  nothing downstream is designed in a vacuum. The **implementation-ready Detailed
  Design is scoped to Phases 1-3 only** (where HEIMDALL.md's core security properties
  — taint boundary, world model, Fenrir + canary, full control surface, Gjöll —
  become real). **Phases 4-6 (ingestion expansion, introspection, promotion) stay at
  HLD-level, with a named follow-on Detailed Design pass.** Pre-mortem mitigations
  carry forward: the DD leads with Himinbjörg (largest unbuilt piece, Phase-3
  critical path) and the sink/flow-declaration schema (ADVERSARIAL_REVIEW 5.1, "the
  root").

**Rationale:** As analysed above — the split-harness option dominated the weighted
matrix (373 vs 288/287) because the control surface is where OpenCode precedent helps
most and it is a Phase-3 concern, not a Phase-1 distraction; the pluggable classifier
is the option most consistent with the project's stated discipline; and (b) on
phasing won RICE decisively (0.85 vs 0.30) while resisting scope-creep bias.

## Next-stage handoff

- **The HLD document** (the deliverable IS the HLD text, not a plan-about-a-plan) is
  authored at **`/Users/jasonh/git/heimdall/plans/HLD.md`**, informed by this brief's
  Part A achievement audit and the converged scope above: harness-agnostic HLD across
  all 6 phases, with the pi.dev-hook portability interface and OpenCode/Gleipnir as the
  named Phase-1-3 reference implementation.
- **The Detailed Design** (Phases 1-3, per Q3) follows the HLD, authored under
  **`/Users/jasonh/git/heimdall/plans/`** (e.g. `DD/` per-component), targeting
  OpenCode/Gleipnir primitives per Q1.
- On completion and review, the HLD may be promoted to a top-level `HLD.md` in the
  Heimdall repo root (following its existing top-level-doc convention); until then it
  lives under `plans/`.

## Open Questions (now resolved by convergence — retained for trace)

- ~~Does the operator accept OpenCode-as-DD-target now, or hold Open Q4's deferral?~~
  → **Resolved (Q1): accepted as a legitimate re-scoping; HLD stays agnostic.**
- ~~Is D67-fix a DD input (pluggable) or a DD blocker?~~ → **Resolved (Q2): pluggable
  seam + tracked arming gate.**
- ~~Confirm the Phase 1-3 DD / Phase 4-6 HLD split?~~ → **Resolved (Q3): confirmed.**
