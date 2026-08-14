# Heimdall: Neurosymbolic Filter Invariants

**Author:** Jason Huxley
**Version:** 1.1
**Date:** August 2026
**Status:** invariants for the neurosymbolic filter, derived from the premise PoC
**Reads with:** `poc/OUTCOME.md` (the result), `HEIMDALL.md` (the architecture), `GLOSSARY.md` (component names)

---

## 1. Purpose

This document defines the invariants that Heimdall's neurosymbolic filter must hold: the data/control separation mechanism that takes untrusted content, quarantines it as typed provenance-stamped data, lets a bound model read it, and keeps the result inert until a wiring is provably safe. In the architecture's terms the filter spans Bifröst (the taint boundary), Nornir (the deterministic classifier and reasoner), Fenrir (the bound neural extraction) and Gjöll (the action-time gate).

This is not the whole project's requirements. It is the invariant set for one mechanism, the filter, stated as properties the live build must hold rather than as features to add. The premise PoC is the evidence, not the subject: it proved the mechanism on an adversarial corpus with a real local model, and this document records which invariants that proof established and which it left for the live build.

Three marks govern each invariant:

- **PROVEN** when the PoC established it structurally, so it carries over to the live system as a property rather than a hope.
- **DEMONSTRATED** when the PoC showed the mechanism works but on a scope narrow enough that the live system must re-establish it at scale (more sources, more models, real sinks).
- **NOT YET TESTED** when the invariant is load-bearing but the PoC did not exercise it at all, because the component did not exist in the PoC. The live build must establish it from scratch, and the acceptance criteria say how.

Everything here maps to an existing design principle (HEIMDALL.md section "Design Principles"), a named component (GLOSSARY.md) and a build phase. Nothing here is new architecture. The PoC's job was to de-risk the architecture that already exists, and these invariants record which risks it retired, which it merely bounded, and which remain wholly untested.

---

## 2. What the PoC proved, in one paragraph

Trust is assigned by origin, not by inspecting content. A deterministic layer with no language model quarantines untrusted content as typed data and never lets it reach an instruction position. The model reads that data in a bound role, and its output is inert typed data that nothing acts on unless a downstream consumer is explicitly and safely wired to it. Every attempt to detect badness by looking at content, at the input or the output, was either unnecessary or actively harmful. The guarantee is structural.

---

## 3. Invariants

### 3.1 The symbolic layer contains no language model

**PROVEN.** Maps to design principle 1 (architectural separation over heuristic detection), principle 10 (determinism is a property of the boundary) and Nornir.

The component that assigns trust and separates data from control must be deterministic code with no call to any language model, direct or indirect. The PoC held `symbolic.py` to this and verified it by human inspection (`poc/SPEC.md`: "verified by inspection"). If a model decides what is an instruction, that decision is itself injectable and the whole guarantee is void.

**Invariant.** Nornir and the Bifröst taint boundary contain no model. Any model call in the classification or trust-assignment path is a build-blocking defect.

**Acceptance.** An AST scan of the authorisation-path packages (`ontology/yggdrasil`, `ontology/nornir`, `poc/symbolic.py`) asserts no model call by any route: no model-client import (direct), no dynamic import (`importlib.import_module`, `__import__`, the indirect import), no outbound network call (any import of `requests`/`httpx`/`urllib`/`http`/`socket` and the like, since a hosted inference endpoint is the likeliest indirect model call and the symbolic layer has no reason to reach the network, aligning with 3.8), and no subprocess to a model runner. Graph-database drivers (the substrate, not a model) are permitted. This covers the invariant's "direct or indirect" wording; the guard was extended to the indirect paths after a repository-access review found the first version caught only direct imports and model subprocesses (decision D70). It runs as a harness obligation (`ontology/nornir/symbolic_guard.py`, obligation 3.1 in `ontology/tests/harness.py`) and carries a mandatory negative control that plants each violation class and confirms the guard catches it (and that benign controls are not flagged), so the check is not theatre (invariant 3.10, D10). Honest status of the automation: the AST check exists and runs in the harness; there is NO continuous-integration wiring yet, so nothing runs it automatically on commit or push. An earlier version of this clause described "static analysis in CI" and "the PoC's AST check" when neither existed (the PoC verified 3.1 by human inspection only); the check now exists, CI does not, and this clause states that plainly (decisions D68, D70). It does not detect a model that DREW a rule which a human then pasted in (authoring provenance), which remains an open, separately-named hole.

### 3.2 Trust is assigned by origin at a single boundary

**PROVEN.** Maps to principle 6 (provenance is first-class), principle 7 (taint propagates conservatively) and Bifröst.

Everything crossing the boundary is stamped untrusted by origin, before any parsing that could be influenced by content. The PoC stamped provenance in the symbolic layer and carried it through every downstream step.

**Invariant.** Bifröst is the single crossing point. Nothing reaches the trusted domain unstamped. Provenance is attached at the boundary and is immutable thereafter. Taint is inherited: any value derived from untrusted input is untrusted.

**Acceptance.** No code path constructs a trusted value from boundary-crossing content without an explicit, logged promotion. Unprovenanced assertions are rejected, not defaulted to trusted.

### 3.3 The data boundary must not be forgeable by content

**PROVEN, and this is the PoC's sharpest finding.** Maps to principle 1 and Bifröst.

The PoC's first design put untrusted data between string delimiters in the prompt. A payload containing the delimiter broke out (`extract-13`). Moving the payload to its own message exposed a second, subtler break: payload text matching the model's control-token strings was promoted to real control tokens by the tokenizer, forging a role boundary one layer down. Both are the same class of bug: **a boundary made of something the payload can contain is not a boundary.**

**Invariant.** Any place the live system frames untrusted content for a model must use a boundary the content cannot forge. In order of preference: out-of-band structure (separate message or field) built at the token level, with the untrusted region encoded so its bytes cannot become control tokens; plus deterministic neutralisation of control-token strings at the boundary as defence in depth. The two mitigations must be independent, as they were in the PoC.

**Acceptance.** A boundary-forgery corpus (delimiter injection, control-token injection, encoding tricks) runs in CI. The untrusted token region must contain zero control tokens on every case. This test is per model family, because the control-token set differs (see 3.7).

### 3.4 The input assertion verifies the exact bytes the model receives

**PROVEN.** Maps to principle 3 (the LLM proposes, the harness acts) and Himinbjörg.

The PoC's first input check verified a string the model never actually received, because the real prompt also carried the field question and chat scaffolding. The fixed check verifies the true token-id prompt per call: the trusted frame matches an independent reconstruction, the untrusted region decodes exactly to the quarantined payload and holds no control token, and the whole prompt is exactly frame plus payload plus frame.

**Invariant.** Whatever assembles a model prompt from trusted instructions and untrusted data must expose the exact input for verification, and the verifier must check that input, not a reconstruction of part of it. The trusted portion must be byte-identical to an independently held constant; the untrusted portion must be exactly the quarantined content and nothing else.

**Acceptance.** For every model call that includes untrusted content, the harness can produce the exact input and assert the frame is unaltered and the untrusted region is contained. A mismatch fails closed.

### 3.5 Do not detect injection by inspecting content

**Output path PROVEN by counter-example; classification path DEMONSTRATED by a fail-closed property test.** It has now saved the design from the same mistake twice, once on each path. Maps to principle 1.

The PoC tried to strengthen the output check by scanning the extraction for directive-like text (n-gram overlap with the payload, imperative phrasing). It failed 11 cases including a clean control, because a faithful summary of any text must share words with that text. Content scanning cannot tell describing a directive from obeying one, and a classifier placed there is itself injectable, the same mistake as putting a model in the symbolic layer, one layer over.

**Invariant.** No component may decide safety by pattern-matching untrusted or model-derived content for malicious wording. This applies on two paths. On the **output path**: the safety of a model's output is never a function of what the output says. On the **classification path**: the classifier must not decide a value's risk (inert versus consequential) by matching untrusted content against enumerated malicious wording. A blacklist of bad phrasings is the same mistake one layer over, and it fails open on the next phrasing. Instead, inertness is earned by a positive signal and the classifier fails closed: content that matches no positive rule routes to review, never to an inert type by default (see 3.11, decision D54). Semantic detection (Huginn) may observe and alert, but must never be the gate that authorises action.

**The deeper form of the same mistake, found by measurement (decision D67).** "Inertness is earned by a positive signal" is not automatically safe, because the positive signal is itself a content pattern an attacker can satisfy. An adversarial corpus that wraps a consequential request in a positive informational, calendar or publication signal ("for your information... no action needed" around a recurring payment) earns the inert type and so defeats the fail-closed default: it is neither gated nor routed to review. Measured false-inert rate on that corpus is 3 of 12, and the test suite is red because of it. The allowlist polarity (earn inert by a positive signal) is a real improvement over a blacklist, but it does not escape 3.5: whenever the inert-earning signal can co-occur with consequential intent, an allowlist has a false-inert hole. The fix is an open design problem (how inertness is earned so a positive inert signal cannot override a co-present consequence signal), and it must not be more keywords.

**Acceptance.** Any proposed content-based safety check on the action path, and any classification rule that enumerates malicious phrasings to catch an attack, is rejected in review. The classification-path half is enforced automatically on two axes: the fail-closed property (`ontology/tests/harness.py`) asserts that a request matching no positive rule never receives an inert type, and fails loudly against an eager catch-all (D55); the false-inert measurement (same harness, D67) asserts that consequential content, adjudicated by an external consequence test, is never typed inert, and it currently fails at 3 of 12 (a measured bound, honestly red). Detection and authorisation are separate concerns; detection informs humans, structure authorises action.

### 3.6 Model output is inert until explicitly and safely wired to a sink

**The provenance gate is PROVEN; the action-critical determination and its wiring to the gate are DEMONSTRATED on the seed.** Maps to principle 3, principle 12 (action-critical values gated at action time), principle 10 and Gjöll.

Every field a model produces from untrusted input is untrusted-derived. The PoC tagged all extraction fields as such, wired a mock actuator and enforced a provenance gate: a sink that consumes an untrusted-derived field as an action fails the assertion, structurally, before the actuator can fire. A safe sink (consuming fields only as inert data) passed on every case; an unsafe control sink (a payment actuator mis-wired to the extracted summary) was caught on every case including clean controls, because the wiring is unsafe by construction regardless of the payload.

The PoC's gate decided action-critical status from a per-sink label: the sink declared, per input, whether it consumed that input as inert or as an action. That is the degenerate stand-in. In the live system a per-sink label is not trustworthy (see 4, sink-wiring honesty) and is unsound against multi-step state staging. Action-critical status must instead be declared in the ontology (which sinks are consequential) and propagated by flow-to-sink transitive reachability over Mímisbrunnr, so a value inherits action-critical status the moment a path to a consequential sink exists, however many reversible hops intervene (HEIMDALL.md action-critical set sizing). The PoC did not build this; it is the same untested dependency as 3.11.

**Invariant.** Gjöll enforces, at action time, that no consequential action is parameterised by an untrusted-derived value without passing a gate. Consuming an untrusted-derived value as an action without passing Gjöll fails closed. Whether a value is action-critical is a property of its transitive flow to a consequential sink, declared in the ontology and computed by reachability, not a self-asserted per-sink label. The provenance gate is a property of the wiring, checked structurally, never of the value's content.

**Acceptance.** Two layers. The provenance gate (PROVEN): the Phase 3 deliberate-friction test uses exactly the PoC's shape, one real consequential capability, a safe wiring that passes and an unsafe control wiring that must be caught before it fires; a green board with only safe wirings is insufficient, the unsafe control is mandatory, exactly as clean controls are mandatory for the extraction test. The action-critical determination (DEMONSTRATED on the seed, decision D58): the Gjoll gate (`ontology/nornir/gjoll.py`) authorises a consequential action only if no parameter it consumes as an action is an untrusted-derived, action-critical value, where action-critical is computed by flow-to-sink reachability, not a per-sink label. The harness obligation runs the PoC's safe-plus-unsafe-control shape over the ontology build, catches the unsafe control before it fires including when the value is staged through a multi-hop cross-domain chain, and confirms a non-action-critical value is not gated. It remains bounded by ontology coverage (the reachability graph must be correct) and by sink-wiring honesty (see 4).

### 3.7 Boundary guarantees are per model family, not universal

**DEMONSTRATED.** Maps to principle 10 and Fenrir.

The PoC's control-token handling was verified for one tokenizer and chat template. The mechanism is general; the specific token ids are not.

**Invariant.** Every model admitted to a tainted-content role (Fenrir) must have its control-token set derived and its boundary re-verified before use. Swapping or upgrading a model re-runs the boundary-forgery corpus (3.3) against the new tokenizer.

**Acceptance.** Model onboarding includes a boundary-verification gate. No model processes tainted content until it passes. The single-constant model identifier in the PoC becomes a per-model onboarding record in the live system.

### 3.8 The tainted-content role is bound and has no egress

**DEMONSTRATED in shape, not in deployment.** Maps to principle 9 (bound monitored sandbox), principle 13 (taint and egress boundaries coincide) and Fenrir.

The PoC's model had no tools, no function calling and no execution surface, and ran fresh context per case with no history. It was a pure extraction subroutine. The PoC did not deploy network segmentation, because it ran offline on one box.

**Invariant.** Fenrir has no tools, no external network egress, no filesystem and no cross-case state. Its outputs are always tainted. Egress restriction is enforced by network segmentation (default-deny, internal allowlist), not by discipline. A model cannot occupy both the tainted-processing role and the untainted-reasoning role.

**Acceptance.** Fenrir's segment denies egress to anything outside its permitted internal peers, verified by network policy test, not by code review. Fresh context per invocation is enforced by construction.

### 3.9 Determinism is claimed only for the boundary, holds regardless of model behaviour, and is bounded by ontology coverage

**Independence from model behaviour is PROVEN; the coverage bound is NOT YET TESTED.** Maps to principle 10.

The PoC's guarantees held identically at decoding temperature 0.0 and 0.7. This is the direct evidence for the first half of principle 10: the result does not depend on what the model does, because the model is never trusted. The structural checks, not the model's phrasing, carry the guarantee.

But principle 10 has a second half the PoC could not test, because it had no ontology: the guarantee is exactly as strong as the ontology's coverage, and gaps in the ontology are gaps in the boundary. Independence from model behaviour does not make the guarantee unbounded. It relocates the bound from the model to the ontology. A perfectly deterministic boundary over an incomplete ontology is a boundary with holes, and those holes are silent (see 3.11).

**Invariant.** No Heimdall safety property may depend on model determinism or on a model behaving well; every neural output is untrusted probabilistic proposal subject to deterministic validation before it can cause anything. The extent of that guarantee is bounded by ontology coverage, and the bound must be measured and stated, not assumed. Content outside coverage fails safe: to human review, never to a trusted or actionable type.

**Acceptance.** Two layers. Model independence (PROVEN): safety tests run at more than one temperature and, where feasible, more than one model; a property that holds at temperature 0 but not at 0.7 is an accident of decoding, not a property, and must be re-derived structurally. Coverage bound (NOT YET TESTED): the coverage-measurement and fail-safe obligations in 3.11 apply; the guarantee is reported alongside its coverage figure, never stated unqualified.

### 3.10 The test harness is an audit artefact, and failures are loud

**PROVEN.** Maps to principle 8 (the harness observes itself) and Hliðskjálf.

The PoC harness read raw content only in one place, handed it only to the symbolic layer, checked both assertions per case, partitioned adversarial from control cases and printed failures prominently rather than burying them. A clearly reported failure was treated as a successful outcome.

**Invariant.** The live validation harness records, per decision, the input, the assertions checked and the result, in a form suitable for the append-only audit log (Hliðskjálf). Control cases (both clean and deliberately-unsafe) are mandatory alongside adversarial cases, because a pass proves nothing without a control that would fail. Escalations travel a protected channel distinct from bulk triage (principle 11).

**Acceptance.** Every safety assertion produces an auditable record. The corpus always contains clean controls and at least one deliberately-unsafe control per gate under test. Absence of a required control fails the suite.

### 3.11 Untrusted content is classified against a typed ontology, and the guarantee extends only as far as coverage

**DEMONSTRATED on a four-domain seed, with one obligation now measured FAILING.** The mechanism the PoC wholly lacked now exists (decisions D46 to D64): a deterministic classifier over a typed ontology, the UNCLASSIFIED fail-safe, forward-chaining derivation with a soundness control, agent-scoped cross-domain flow-to-sink feeding the Gjoll gate, and the marshalling seam to the real model proven end to end (D62). But the classification-correctness obligation (8.2) is no longer uniformly green: an independent adversarial corpus measures a false-inert rate of 1 of 16 (D67, reduced from 3 of 12 by the D69 shared inert-earning guard, then re-opened at 1/16 by a fresh probe), consequential content that positively earns an inert signal and so skips both the gate and review, and the test suite is red because of it. This is the honest state and it is left red. Two things remain, of different kinds. The false-inert hole is a KNOWN BREAK, reduced but not closed, with an OPEN fix (how inertness is earned, D67-fix), not a coverage gap. Separately, coverage BREADTH is still untested: the guarantee is only as strong as the ontology's coverage, measured 36 of 38 on the seed corpus (not "94.7 percent", which is false precision on n=38). Sits logically alongside 3.2 (trust by origin): once content is stamped untrusted, the deterministic layer decides what it is, and that decision now has a measured error with a real-world-consequence cost. Maps to principle 6, principle 10, and Nornir plus Mímisbrunnr.

This is the load-bearing invariant the PoC did not exercise at all. The PoC used a flat four-field schema with a single trust rule and no reasoner. That is not a small ontology; it is the absence of one. The structural invariants above (3.1 to 3.10) prove untrusted content cannot become an instruction. They say nothing about whether it is classified correctly, and classification is where the live guarantee actually lives. The architecture states the limit plainly: the determinism guarantee is exactly as strong as the ontology's coverage, and gaps in the ontology are gaps in the boundary (HEIMDALL.md principle 10).

Its failure mode is not injection reaching the control channel. It is misclassification: a value that should be action-critical typed as an inert label, so it skips Gjöll; a derived fact the reasoner should not have entailed; a consequential sink the ontology fails to declare, so flow-to-sink analysis never marks a staged value action-critical. None of these are caught by the structural checks, because the bytes reached the model legitimately and the output was inert. The flaw is in the typing, not the boundary.

**Invariant.** Nornir classifies untrusted assertions against a composed, typed ontology using deterministic rules and a formal reasoner, no model. Unknown content is classified `UNCLASSIFIED_DATA_ASSERTION`, `actionable: false`, and routed to human review; it never defaults to a trusted or actionable type. Derived facts carry their assertion chain. Action-critical status is declared in the ontology and propagated by flow-to-sink reachability, not assigned per step (see 3.6). The guarantee the whole filter offers is bounded by this ontology's coverage, and that bound must be stated, not hidden.

**Acceptance.** Four distinct test obligations, all Phase 2 or 3, because the ontology does not exist before then:

1. **Coverage measurement.** Against a representative corpus, the fraction of assertions classified to a known type versus `UNCLASSIFIED` is measured and tracked over time. Coverage is a reported number, not a pass or fail. The only hard invariant is that uncovered content fails safe: to review, never to a trusted or actionable type.
2. **Classification correctness.** A labelled corpus maps each assertion to its expected type, including adversarial cases engineered to force misclassification, above all cases that try to get an action-critical value typed as an inert label. Ground-truth labels are required, which the injection corpus does not have, so this is a new corpus. A misclassification that downgrades an action-critical value is a critical finding.
3. **Reasoner soundness.** For a set of asserted facts, every derived fact must be entailed by the ontology's rules. A derived fact that does not follow, especially one that confers trust or in-scope status, fails the suite.
4. **Flow-to-sink reachability.** Any value that can reach a consequential sink by any path, however many reversible hops intervene, must inherit action-critical status at the point it is written. The state-staging attack (HEIMDALL.md action-critical set sizing) is the mandatory adversarial case: a chain of individually-reversible writes that composes into a consequential action must be caught at the staging write, not missed.

The methodology for building, growing and testing this ontology, including the substrate choice, the layer composition, the marshalling contract and these test obligations in full, is `ONTOLOGY_CONSTRUCTION.md`.

---

## 4. Out of scope for this filter

Stated so they are not mistaken for proven.

- **Extraction accuracy.** The premise is about action, not correctness. A wrong sender or a poisoned entity list passed the PoC, correctly, because it is inert. The live system's accuracy is a separate concern; a value being inert says nothing about it being right. Any value that will parameterise an action must pass Gjöll on its way to that action regardless of how accurate the extraction looked.
- **Sink-wiring honesty.** The gate proves a declared wiring safe or unsafe. It does not verify that a sink's declaration of how it consumes a field is truthful. The live system must derive consumption from the actual data flow (Gjöll's flow-to-sink transitive reachability), not trust a per-sink label.
- **Availability under load.** The PoC pulled a fixed corpus. Volume-based denial, backpressure and triage-queue flooding are addressed by the pull paradigm and channel separation (principle 11), none of which the PoC exercised.
- **The ontology.** The single largest thing the PoC did not exercise, and where residual risk now concentrates: coverage, the deterministic classifier and reasoner (Nornir), the world model (Mímisbrunnr), promotion, and action-critical classification by flow-to-sink reachability. This is not a caveat but an invariant with its own test obligations; it is stated in full at 3.11 and referenced by 3.6 and 3.9. The open question of the minimum viable Phase 1 ontology (HEIMDALL.md open questions) is where that work starts.

---

## 5. Mapping to build phases

- **Phase 1 (prove the separation).** Invariants 3.1, 3.2, 3.3, 3.4, 3.5, 3.10, and the model-independence half of 3.9. The PoC is the Phase 1 architectural proof, and these are its acceptance criteria carried into the live build. Gjöll dormant, action-critical set empty, exactly as Phase 1 specifies.
- **Phase 2 (world model, reasoner, Fenrir).** Invariants 3.7 and 3.8 become live here, when Fenrir is deployed as a segmented sandbox and real models are onboarded. The bulk of 3.11 lands here too: coverage measurement, the classification-correctness corpus and reasoner soundness, against the initial Nornir ontology over Mímisbrunnr. The coverage bound in 3.9 becomes measurable for the first time.
- **Phase 3 (control surface, Gjöll).** The provenance-gate half of 3.6 is validated by the deliberate-friction test, using the PoC's safe-plus-unsafe-control shape on one real consequential capability. The action-critical half of 3.6, and the flow-to-sink reachability obligation of 3.11, are validated here against a real state-staging attempt.

---

## 6. The one-line summary for the live build

Protect by structure, not by detection. Assign trust by origin at one unforgeable boundary, keep the model output inert until a wiring is proven safe by provenance, and never let any safety property depend on what untrusted content says or on how the model behaves.
