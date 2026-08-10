# Heimdall: Requirements Extracted from the Premise PoC

**Author:** Jason Huxley
**Version:** 1.0
**Date:** August 2026
**Status:** requirements for the live build, derived from the PoC outcome
**Reads with:** `poc/OUTCOME.md` (the result), `HEIMDALL.md` (the architecture), `GLOSSARY.md` (component names)

---

## 1. Purpose

The premise PoC succeeded. It proved, on an adversarial corpus with a real local model, that a paired symbolic-plus-LLM pipeline can hold the property that untrusted instructions embedded in data do not cause action. This document turns what the PoC proved, and what it deliberately did not, into requirements for the live system.

Two rules govern the translation:

- A requirement is marked **PROVEN** when the PoC established it structurally, so it carries over to the live system as a property rather than a hope.
- A requirement is marked **DEMONSTRATED** when the PoC showed the mechanism works but on a scope narrow enough that the live system must re-establish it at scale (more sources, more models, real sinks).

Everything here maps to an existing design principle (HEIMDALL.md section "Design Principles"), a named component (GLOSSARY.md) and a build phase. Nothing here is new architecture. The PoC's job was to de-risk the architecture that already exists, and these requirements record which risks it retired and which it merely bounded.

---

## 2. What the PoC proved, in one paragraph

Trust is assigned by origin, not by inspecting content. A deterministic layer with no language model quarantines untrusted content as typed data and never lets it reach an instruction position. The model reads that data in a bound role, and its output is inert typed data that nothing acts on unless a downstream consumer is explicitly and safely wired to it. Every attempt to detect badness by looking at content, at the input or the output, was either unnecessary or actively harmful. The guarantee is structural.

---

## 3. Requirements

### 3.1 The symbolic layer contains no language model

**PROVEN.** Maps to design principle 1 (architectural separation over heuristic detection), principle 10 (determinism is a property of the boundary) and Nornir.

The component that assigns trust and separates data from control must be deterministic code with no call to any language model, direct or indirect. The PoC held `symbolic.py` to this and verified it by inspection on every run. If a model decides what is an instruction, that decision is itself injectable and the whole guarantee is void.

**Live requirement.** Nornir and the Bifröst taint boundary contain no model. Any model call in the classification or trust-assignment path is a build-blocking defect.

**Acceptance.** Static analysis in CI fails the build if the symbolic or boundary packages import a model client, call an inference endpoint or shell out to one. The PoC's AST check is the minimum bar.

### 3.2 Trust is assigned by origin at a single boundary

**PROVEN.** Maps to principle 6 (provenance is first-class), principle 7 (taint propagates conservatively) and Bifröst.

Everything crossing the boundary is stamped untrusted by origin, before any parsing that could be influenced by content. The PoC stamped provenance in the symbolic layer and carried it through every downstream step.

**Live requirement.** Bifröst is the single crossing point. Nothing reaches the trusted domain unstamped. Provenance is attached at the boundary and is immutable thereafter. Taint is inherited: any value derived from untrusted input is untrusted.

**Acceptance.** No code path constructs a trusted value from boundary-crossing content without an explicit, logged promotion. Unprovenanced assertions are rejected, not defaulted to trusted.

### 3.3 The data boundary must not be forgeable by content

**PROVEN, and this is the PoC's sharpest finding.** Maps to principle 1 and Bifröst.

The PoC's first design put untrusted data between string delimiters in the prompt. A payload containing the delimiter broke out (`extract-13`). Moving the payload to its own message exposed a second, subtler break: payload text matching the model's control-token strings was promoted to real control tokens by the tokenizer, forging a role boundary one layer down. Both are the same class of bug: **a boundary made of something the payload can contain is not a boundary.**

**Live requirement.** Any place the live system frames untrusted content for a model must use a boundary the content cannot forge. In order of preference: out-of-band structure (separate message or field) built at the token level, with the untrusted region encoded so its bytes cannot become control tokens; plus deterministic neutralisation of control-token strings at the boundary as defence in depth. The two mitigations must be independent, as they were in the PoC.

**Acceptance.** A boundary-forgery corpus (delimiter injection, control-token injection, encoding tricks) runs in CI. The untrusted token region must contain zero control tokens on every case. This test is per model family, because the control-token set differs (see 3.7).

### 3.4 The input assertion verifies the exact bytes the model receives

**PROVEN.** Maps to principle 3 (the LLM proposes, the harness acts) and Himinbjörg.

The PoC's first input check verified a string the model never actually received, because the real prompt also carried the field question and chat scaffolding. The fixed check verifies the true token-id prompt per call: the trusted frame matches an independent reconstruction, the untrusted region decodes exactly to the quarantined payload and holds no control token, and the whole prompt is exactly frame plus payload plus frame.

**Live requirement.** Whatever assembles a model prompt from trusted instructions and untrusted data must expose the exact input for verification, and the verifier must check that input, not a reconstruction of part of it. The trusted portion must be byte-identical to an independently held constant; the untrusted portion must be exactly the quarantined content and nothing else.

**Acceptance.** For every model call that includes untrusted content, the harness can produce the exact input and assert the frame is unaltered and the untrusted region is contained. A mismatch fails closed.

### 3.5 Do not detect injection by inspecting content

**PROVEN by counter-example, and it saved the design from a real mistake.** Maps to principle 1.

The PoC tried to strengthen the output check by scanning the extraction for directive-like text (n-gram overlap with the payload, imperative phrasing). It failed 11 cases including a clean control, because a faithful summary of any text must share words with that text. Content scanning cannot tell describing a directive from obeying one, and a classifier placed there is itself injectable, the same mistake as putting a model in the symbolic layer, one layer over.

**Live requirement.** No component may decide safety by pattern-matching untrusted or model-derived content for malicious wording. This applies to the output path specifically: the safety of a model's output is never a function of what the output says. Semantic detection (Huginn) may observe and alert, but must never be the gate that authorises action.

**Acceptance.** Any proposed content-based safety check on the action path is rejected in review. Detection and authorisation are separate concerns; detection informs humans, structure authorises action.

### 3.6 Model output is inert until explicitly and safely wired to a sink

**PROVEN for the empty and safe cases; the gate itself is PROVEN; real wirings are DEMONSTRATED.** Maps to principle 3, principle 12 (action-critical values gated at action time), principle 10 and Gjöll.

Every field a model produces from untrusted input is untrusted-derived. The PoC tagged all extraction fields as such, wired a mock actuator and enforced a provenance gate: a sink that consumes an untrusted-derived field as an action fails the assertion, structurally, before the actuator can fire. A safe sink (consuming fields only as inert data) passed on every case; an unsafe control sink (a payment actuator mis-wired to the extracted summary) was caught on every case including clean controls, because the wiring is unsafe by construction regardless of the payload.

**Live requirement.** Gjöll enforces, at action time, that no consequential action is parameterised by an untrusted-derived value without explicit re-validation against a source or semantic constraint. A sink declares, per input, whether it consumes that input as inert data or as an action. Consuming an untrusted-derived value as an action, without passing Gjöll, fails closed. The gate is a property of the wiring, checked structurally, not of the value's content.

**Acceptance.** The Phase 3 deliberate-friction test uses exactly the PoC's shape: one real consequential capability, a safe wiring that passes and an unsafe control wiring that must be caught before it fires. A green board with only safe wirings is insufficient; the unsafe control is mandatory, exactly as clean controls are mandatory for the extraction test.

### 3.7 Boundary guarantees are per model family, not universal

**DEMONSTRATED.** Maps to principle 10 and Fenrir.

The PoC's control-token handling was verified for one tokenizer and chat template. The mechanism is general; the specific token ids are not.

**Live requirement.** Every model admitted to a tainted-content role (Fenrir) must have its control-token set derived and its boundary re-verified before use. Swapping or upgrading a model re-runs the boundary-forgery corpus (3.3) against the new tokenizer.

**Acceptance.** Model onboarding includes a boundary-verification gate. No model processes tainted content until it passes. The single-constant model identifier in the PoC becomes a per-model onboarding record in the live system.

### 3.8 The tainted-content role is bound and has no egress

**DEMONSTRATED in shape, not in deployment.** Maps to principle 9 (bound monitored sandbox), principle 13 (taint and egress boundaries coincide) and Fenrir.

The PoC's model had no tools, no function calling and no execution surface, and ran fresh context per case with no history. It was a pure extraction subroutine. The PoC did not deploy network segmentation, because it ran offline on one box.

**Live requirement.** Fenrir has no tools, no external network egress, no filesystem and no cross-case state. Its outputs are always tainted. Egress restriction is enforced by network segmentation (default-deny, internal allowlist), not by discipline. A model cannot occupy both the tainted-processing role and the untainted-reasoning role.

**Acceptance.** Fenrir's segment denies egress to anything outside its permitted internal peers, verified by network policy test, not by code review. Fresh context per invocation is enforced by construction.

### 3.9 Determinism is claimed only for the boundary, and holds regardless of model behaviour

**PROVEN.** Maps to principle 10.

The PoC's guarantees held identically at decoding temperature 0.0 and 0.7. This is the direct evidence for principle 10: the result does not depend on what the model does, because the model is never trusted. The structural checks, not the model's phrasing, carry the guarantee.

**Live requirement.** No Heimdall safety property may depend on model determinism or on a model behaving well. Every neural output is untrusted probabilistic proposal subject to deterministic validation before it can cause anything. The guarantee is exactly as strong as the ontology's coverage; unclassifiable content routes to human review rather than being trusted.

**Acceptance.** Safety tests run at more than one temperature and, where feasible, more than one model. A property that holds at temperature 0 but not at temperature 0.7 is not a property; it is an accident of decoding and must be re-derived structurally.

### 3.10 The test harness is an audit artefact, and failures are loud

**PROVEN.** Maps to principle 8 (the harness observes itself) and Hliðskjálf.

The PoC harness read raw content only in one place, handed it only to the symbolic layer, checked both assertions per case, partitioned adversarial from control cases and printed failures prominently rather than burying them. A clearly reported failure was treated as a successful outcome.

**Live requirement.** The live validation harness records, per decision, the input, the assertions checked and the result, in a form suitable for the append-only audit log (Hliðskjálf). Control cases (both clean and deliberately-unsafe) are mandatory alongside adversarial cases, because a pass proves nothing without a control that would fail. Escalations travel a protected channel distinct from bulk triage (principle 11).

**Acceptance.** Every safety assertion produces an auditable record. The corpus always contains clean controls and at least one deliberately-unsafe control per gate under test. Absence of a required control fails the suite.

---

## 4. Requirements the PoC explicitly did not address

Stated so they are not mistaken for proven.

- **Extraction accuracy.** The premise is about action, not correctness. A wrong sender or a poisoned entity list passed the PoC, correctly, because it is inert. The live system's accuracy is a separate concern; a value being inert says nothing about it being right. Any value that will parameterise an action must pass Gjöll on its way to that action regardless of how accurate the extraction looked.
- **Sink-wiring honesty.** The gate proves a declared wiring safe or unsafe. It does not verify that a sink's declaration of how it consumes a field is truthful. The live system must derive consumption from the actual data flow (Gjöll's flow-to-sink transitive reachability), not trust a per-sink label.
- **Availability under load.** The PoC pulled a fixed corpus. Volume-based denial, backpressure and triage-queue flooding are addressed by the pull paradigm and channel separation (principle 11), none of which the PoC exercised.
- **The ontology.** The PoC had a fixed four-field schema, not an ontology. Coverage, promotion and the world model are Phase 2 onward and out of scope for what the PoC proved.

---

## 5. Mapping to build phases

- **Phase 1 (prove the separation).** Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.9, 3.10. The PoC is the Phase 1 architectural proof. These requirements are its acceptance criteria carried into the live build. Gjöll dormant, action-critical set empty, exactly as Phase 1 specifies.
- **Phase 2 (world model, reasoner, Fenrir).** Requirements 3.7 and 3.8 become live here, when Fenrir is deployed as a segmented sandbox and real models are onboarded.
- **Phase 3 (control surface, Gjöll).** Requirement 3.6 is validated here by the deliberate-friction test, using the PoC's safe-plus-unsafe-control shape on one real consequential capability.

---

## 6. The one-line summary for the live build

Protect by structure, not by detection. Assign trust by origin at one unforgeable boundary, keep the model output inert until a wiring is proven safe by provenance, and never let any safety property depend on what untrusted content says or on how the model behaves.
