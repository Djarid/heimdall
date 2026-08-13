# Heimdall: Adversarial Review Brief

**Author:** Jason Huxley
**Version:** 2.0
**Date:** August 2026
**Status:** a briefing for a hostile reviewer; revised after a first hostile review found real faults in v1.0 (see the changelog at the end)
**Reads with:** `HEIMDALL.md` (architecture), `NEUROSYMBOLIC_FILTER_INVARIANTS.md` (the invariants and their proof status), `DECISIONS.md` (the tracked decisions), `ONTOLOGY_CONSTRUCTION.md` (how the ontology is built and tested), `STATUS.md` (current state)

---

## 1. What this document is for, and how v1.0 was wrong

This is a brief for an adversarial reviewer, human or LLM, whose job is to break the design or find where its claims outrun its evidence. It is not a sales pitch. It states what Heimdall claims, points at the evidence, and hands you the seams and untested surface.

Version 1.0 of this brief was itself reviewed adversarially and had two structural faults, both of which flattered the design. They are fixed here and named so you can check the fix rather than trust it:

- **v1.0 defined "a real break" in terms of the system's own computed labels.** Since `action-critical` is a label the classifier assigns, a value the classifier wrongly types as inert satisfied no clause of the break definition, so every classifier miss was definitionally a non-break. That is an unfalsifiability construction sitting on top of the one weakness the brief admits is open. Section 6 now states break conditions in terms of real-world consequence and ground-truth labels, not the system's own output.
- **v1.0's headline said trust is assigned "never by detecting malicious content", full stop.** True of provenance; false of the authorisation decision, which is a conjunction whose second term (criticality) is computed by content-inspecting keyword rules over model-produced text. Section 2 now separates the two.

A rule for the reviewer that survives from v1.0, because it is correct and load-bearing: a keyword rule that enumerates malicious phrasings is not a fix and must not be proposed as one (invariant 3.5). But note the corollary v1.0 abused: the fact that unrecognised content fails closed does not make a misclassification harmless. If a genuinely consequential value is positively typed as inert, it does not fail closed, it fails silently. That is the attack worth mounting, and section 6 now scores it as a break.

---

## 2. The claim, stated so it does not overclaim

Heimdall lets an LLM agent work with untrusted external content without that content being able to cause action. The guarantee has two parts, and they are different in kind. State them separately, because conflating them is how the design flatters itself:

- **Trust by origin (structural, proven).** Untrusted content is quarantined as typed data at a single boundary, stamped by origin, immutable thereafter. The model only ever reads it as data. This half inspects no content and is independent of what the model says.
- **Criticality by classification (content-inspecting, measured not proven).** Whether a value is action-critical is decided by classifying it (keyword and shape rules over model-produced text), then propagating that over a flow-to-sink graph. This half does inspect content. The improvement over a naive design is one of polarity, not of removing content inspection: inertness must be positively earned (an allowlist), and unmatched content fails closed to review rather than passing. But the security-critical surface is now the precision of the inert-typing rules, and an inert rule is a capability grant written in keywords.

The gate that authorises a consequential action is the **conjunction**: block if a consumed parameter is both untrusted-derived (structural) and action-critical (classified). So the guarantee is a proven structural property AND a measured classification property, and it is only as strong as the weaker of the two. The flow-to-sink computation does not escape this: it is transitive closure over a graph whose edges and sink semantics are **declarations** (see 5.1), so "computed, not a per-sink label" is one level of indirection over declarations, not a change in kind.

---

## 3. What is PROVEN, on what, and what the D62 seam did to those proofs

The structural invariants (3.1 to 3.10) were established in the premise proof-of-concept: running code, an adversarial corpus of 31 cases, one local model (`Qwen2.5-7B-Instruct-4bit`), two decoding temperatures. Evidence: `poc/`, `poc/OUTCOME.md`.

The strongest details, which you should try hardest to break precisely because they look solid:
- **3.3 forgery closures.** Two real forgeries found and closed: an in-band delimiter a payload could contain, and a tokenizer-level control-token forgery. The boundary is now out-of-band token-id splicing.
- **3.5 method.** Content-detection was disproven by building the heuristic and showing it fails 11 cases including a clean control, not by assertion.
- **Negative controls throughout:** the unsound derivation (D56), the simulated eager catch-all (D54/D55), the unsafe sink wiring (3.6). Passes mean something only because a mandated control would fail.

**The scope caveat v1.0 hid (accept this as a live weakness).** Those proofs were established *before* the marshalling seam (D62) connected the real model pipeline to the ontology. After D62, the classifier's keyword rules run over model-produced text, and the resulting type decides criticality, which decides whether the gate blocks. So **model behaviour now influences the gate outcome through criticality**, even though it does not influence provenance. The honest per-invariant status after the seam:

- 3.1, 3.2, 3.3, 3.4: structural, provenance-path, **not** touched by the seam. Still proven in scope.
- 3.5 output path: proven; classification path: demonstrated, and now the seam feeds it real model text, so its adversarial precision is the open question (5.2).
- 3.6 provenance-gate half: proven. Action-critical half: demonstrated, and it inherits the classification dependency.
- 3.9: the invariant doc states it precisely (no safety property depends on model *determinism or good behaviour*; the extent is bounded by ontology coverage, which it marks NOT YET TESTED). That holds post-seam: a mistyped value is caught or not by the *deterministic* classifier and gate, not by the model behaving. But the honest reading the seam sharpens is that the classifier's *input* is now model-produced text, so the coverage bound (already the marked-untested half of 3.9) is where the risk sits, and it is measured only on a self-authored corpus. v1.0's own summary of 3.9 as flatly "safety holds regardless of model behaviour, tested at 0.0 and 0.7" was an oversimplification of what the invariant doc actually claims; the doc is more careful than v1.0 was.

A reviewer should still ask for, and the project does not publish, a per-invariant "re-verified after D62" column. Its absence is a real gap.

---

## 4. What is DEMONSTRATED on a small, self-authored seed

"Demonstrated" means it runs and passes on a hand-authored ontology and corpus, with a real model at the seam and over a live store. Not proven at production coverage or scale, and the corpus was written by the same author who wrote the classification rules, so it measures internal consistency, not adversarial robustness.

- **The ontology (invariant 3.11):** a deterministic classifier over a BFO spine plus four domains (communications, scheduling, finance, publication), the UNCLASSIFIED fail-safe, forward-chaining derivation, agent-scoped cross-domain flow-to-sink. **The ontology and all rules are hand-authored Python, no model output on the authoring path** (verifiable: there is no model call anywhere under `ontology/`). Evidence: `ontology/`, `ontology/OUTCOME.md`.
- **The gate (D58), fail-closed classification (D54) and its property test (D55), reasoner soundness with a control (D56), the substrate binding (D57), live-store integration and cross-batch staging (D63/D64), the marshalling seam (D62).** Each has a passing check; the cross-batch-staging catch (D64) is real and was absent before.
- **Coverage: 36 of 38 corpus cases classify to a known type; the other 2 fail safe.** (The harness reports this as "94.7%"; on n=38 that is false precision, the 95 percent Wilson interval is 83 to 99 percent.) Coverage is **not** the bound of the guarantee (see 6); it is a demonstration figure.

---

## 5. Where to attack (re-ranked; the root joint is first)

Ordered by where a real finding is most likely, corrected from v1.0 which under-ranked its own root.

### 5.1 Sink and flow declarations are trusted input, and nothing attests them (the root)
The flow-to-sink graph's edges and each sink's declaration of how it consumes a field (inert vs action) are declarations, not derived facts. The gate proves a *declared* wiring safe or unsafe; it does not verify the declaration against behaviour. A sink that declares it consumes an action-critical value as inert, but actually acts on it, passes the gate. A missing flow edge is a silent hole. Inert-rule precision (5.2), extraction accuracy (5.6) and cross-batch staging (5.5) all reduce to this: labels only mean something if the graph they propagate over is honest. This is the single most load-bearing unverified assumption in the design, and there is currently no integrity control, signing, or behaviour-derivation for it. Attack here first.

### 5.2 Inert-rule precision under adversarial phrasing (the unmeasured bound)
Classification is conservative keyword/shape matching over model-produced text. The security-critical number is the **false-inert rate**: the probability that genuinely consequential content positively matches an inert rule and is therefore never marked action-critical, never gated, and never sent to review. This is the actual bound of the guarantee, and it is unmeasured on any independent adversarial corpus (the seed corpus is self-authored, and reports 0 downgrades on cases the author wrote). The obligation to measure it exists (invariant 3.11 obligation 8.2, the "downgrade a critical value" class), but only a self-authored instance has been run. Attack: construct content that is in fact consequential and positively matches an inert type. Do not propose a keyword blacklist as the remedy (3.5); the remedy is fail-closed types and a measured false-inert rate.

### 5.3 The review queue is an integrity path, not just availability
Fail-closed routing sends a lot to human review: on the 38-case seed corpus, 10 of 38 (26 percent) route to review, of which 4 (11 percent) are genuine cross-domain ties and the rest are unrecognised requests and unclassified content. That is a benign corpus; the adversarial rate is unmeasured and there is no reason to think it is lower. A flooded queue that gets rubber-stamped is not a denial of availability, it is an **integrity failure**: the effective classifier for the hardest cases becomes a fatigued human with an approve button, and approval is the sanctioned override that bypasses the whole symbolic layer. The human is the one component with no measured reliability figure. "Fail closed" is only a safety property if the thing it closes onto is a reliable oracle at the offered rate. This is the softest target in the design because attacking it needs no cleverness about ontologies or tokenizers.

### 5.4 The D62 seam migrated proofs without restating their scope
The marshalling seam joins the proven PoC and the demonstrated ontology build. It is the newest joint and the least exercised (one model, two messages). Beyond "can the provenance stamp and the trust level disagree", the structural question is which PoC-tier proofs had their scope assumptions invalidated when model text started feeding the classifier (see 3, 3.9). Attack the seam as the place where PROVEN quietly became conditional.

### 5.5 The default deployment does not hold the cross-batch guarantee
Cross-batch state staging (write A to B now, complete B to sink in a later turn) is caught only in the persistent store mode. The **default per-batch mode does not catch it**. Multi-turn staging is the natural attack once single-shot injection is closed, so a per-batch deployment is vulnerable to one of the most likely real attacks. Framing the mitigation as "a deployment decision" understates it: the guarantee against cross-batch staging is a precondition (persistent mode), not a default.

### 5.6 Extraction accuracy is out of scope, conditional on 5.1
A wrong or poisoned extracted value passes because the extraction is inert; the premise is about action, not correctness. This scope limit holds only if every value that parameterises an action must pass the gate, which in turn depends on 5.1 (an honest flow graph). Attack: find a path where an inaccurate-but-inert value later parameterises an action without a gate check. If it must pass the gate, the scope limit holds; if 5.1 is broken, this is too.

### 5.7 Boundary closures are per pinned tokenizer/template, not per "model family"
The control-token handling was verified for one tokenizer and chat template. "Model family" is the wrong unit: special-token inventories and chat templates change across point releases, and a quantised conversion is a distinct artefact with its own `tokenizer.json`. The correct unit is a pinned tokenizer/template hash, and onboarding should refuse any artefact whose hash is not in a verified set. Relatedly, 3.4 verifies the tokens *submitted* at the call boundary; off-device (hosted endpoint, server-side templating, prefix caching, batching) that is a claim about the request, not about reception. On-device execution (or an attested equivalent) is a precondition of 3.4; the word to use is "submitted", not "received".

### 5.8 There is no adversary model for the authoring and configuration path
The stated threat model is untrusted external content. But an inert-typing rule, a sink consumption declaration, a flow edge, the backend mode, the verified-tokenizer set and the ontology content are all trusted inputs that decide outcomes, and none is content. The design offers no integrity control, review requirement or signing for any of them. A design whose guarantee is bounded by an ontology needs the ontology and its sibling configuration in the threat model. This is the obvious next invariant to write.

### 5.9 Substrate dense-cycle cost (a performance caveat, lowest)
Edge-deletion retraction is sound but degrades toward full-graph work when reachability is one dense strongly-connected component. A realistic flow graph is sparse; this is a monitoring caveat, not a security seam, unless a workload can force the degenerate case.

---

## 6. What counts as a real break (stated in consequence, not in the system's own labels)

v1.0 stated break conditions using `action-critical`, a computed label, which made every classifier miss a non-break by construction. Corrected: a break is defined against real-world consequence and ground-truth labels, not the system's output.

**A real break** is any of:
- Untrusted-derived content parameterises an action with real-world consequence, without a human decision, when that content was **in fact** consequential. "In fact consequential" is adjudicated against ground-truth labels (the obligation 8.2 corpus), not against what the classifier decided. A consequential value the classifier typed as inert, so it skipped the gate, is a break, not a coverage observation.
- Uncovered or unrecognised content is typed as a trusted or actionable type by default rather than routed to review (a genuine fail-open of the default).
- Content forges the origin boundary so the model treats it as an instruction.
- A model call, or model-generated content (rules, ontology, config), sits on an action-authorisation path.
- A sink's declaration diverges from its behaviour so the gate authorises an action it should have blocked (5.1).

**A severity gradient, not a separate category.** Classifier misses are breaks, graded by consequence: a mistyped payment request is a high-severity break; a mistyped newsletter that would have been inert anyway is low. This is the correction to v1.0, which parked all misses as non-breaks.

**Genuinely not a break (the fail-safe working):** content that is uncovered and routes to review; content the classifier types to a *higher*-risk type than needed (an over-classification, which is a cost, not a safety property, and should be counted as a cost not pooled with the fail-safe). If you can only get content to the review queue, you have not broken the action path, but see 5.3: the review queue is itself an attackable integrity path.

The distinction is itself a claim you may attack: if you can show the fail-closed default is not closed (uncovered content reaching an inert or trusted type, or the review route being bypassable), that collapses the distinction and is a headline finding.

---

## 7. Numbers a hostile reviewer will ask for and cannot find

These are the evidential gaps, and the first is the one the design should not be signed off without.

| Wanted | Present? |
|--------|----------|
| False-inert rate under adversarial phrasing, on an independent corpus (**the** bound) | No |
| Held-out or third-party / red-team corpus results (the seed is self-authored) | No |
| Count and breadth of inert rules (the actual capability-grant surface) | No |
| Review-queue throughput and assumed human error rate at that rate | No |
| Which of 3.1 to 3.10 were re-verified after the D62 seam | No |
| Build-time provenance of the ontology (answer: hand-authored; now stated, previously implicit) | Now yes (section 4) |
| Coverage as a raw fraction with an interval (36/38), not 94.7% | Now yes (section 4) |
| An adversary model for configuration and rule authoring | No |
| Verified tokenizer/template hash set (not "family") | No |

---

## 8. Findings the author would least like to receive

Naming these costs credibility, which is why they belong here. In descending order of how much each would force a redesign rather than an increment:

1. **A verified-in-the-wild false-inert case:** consequential content that positively matches an inert rule, adjudicated consequential by ground truth, that skips both the gate and review. This attacks the measured half of the guarantee (section 2) at its weakest and unmeasured point.
2. **A demonstrated divergence between a sink's declaration and its behaviour** in a real integration, so the gate authorises what it should block (5.1). This attacks the assumption the whole flow-to-sink guarantee rests on.
3. **Any path that puts model-generated content on an authorisation path**, for example if a future coverage-growth step drafts ontology rules with a model and they are loaded without human ratification. This would breach invariant 3.1 in substance while passing its runtime AST check.
4. **A working multi-turn staging chain against a default (per-batch) deployment** (5.5), since that is the shipped configuration.
5. **A review-queue flooding argument with numbers** showing the human oracle's effective error rate at the induced rate makes fail-closed routing a fail-open path in practice (5.3).

If you are the reviewer, these are the targets. A finding here changes the design; a finding elsewhere increments it.

---

## 9. Ground truth to check the claims against

Do not trust this summary; check it against the artifacts.

- `poc/.venv/bin/python -m ontology.tests.harness` reports coverage, classification correctness (downgrades are critical), the fail-closed property, reasoner soundness with its negative control, flow-to-sink reachability, and the Gjoll gate.
- `poc/.venv/bin/python spike/substrate/harness.py` runs the substrate spike.
- `cd poc && .venv/bin/python harness.py` (add `--temp 0.7`, `--sinks unsafe`) runs the PoC.
- `ontology/tests/e2e_harness.py` and `ontology/tests/memgraph_integration_harness.py` are the optional real-model and live-store checks; they skip cleanly when the model or Memgraph is absent, so a green core suite does not assume them.
- Every claim traces to a decision in `DECISIONS.md` and an invariant in `NEUROSYMBOLIC_FILTER_INVARIANTS.md` with an explicit PROVEN / DEMONSTRATED / NOT YET TESTED mark. A claim here not backed there is a finding.

The single most honest sentence about the project, corrected from v1.0 which attributed the whole bound to the one input that has a number: **the premise is proven for a pre-seam system and only partially re-verified since; the mechanism is demonstrated on a small self-authored seed; and the guarantee is bounded by three things, ontology coverage (measured), inert-rule precision under adversarial phrasing (unmeasured), and the honesty of sink and flow declarations (unattested).** Test that sentence hardest.

---

## Changelog: what the first hostile review changed

A hostile review of v1.0 was accepted almost in full; the substantive corrections it forced, recorded so the change is auditable (decision D66):

- **Break definition** rewritten in consequence and ground-truth terms; classifier misses are breaks with a severity gradient, not a separate non-break category (was the review's F1, the headline finding).
- **The headline claim** split into a proven structural half (trust by origin) and a measured classification half (criticality), because the authorisation decision does inspect content (F2).
- **Invariant 3.9** re-described accurately: v1.0's flat "safety holds regardless of model behaviour" oversimplified the invariant doc, which already scopes the guarantee to the coverage bound it marks NOT YET TESTED. The correction is that v1.0's summary was looser than the doc, and the seam puts model-produced text into the classifier's input, so the already-untested coverage bound is where the risk sits (F3).
- **The seam list reordered** so sink and flow declaration honesty is first, as the root the other seams reduce to (F4).
- **Coverage reported as 36/38** with an interval, self-authorship of the corpus flagged, and the false-inert rate named as the true unmeasured bound (F5).
- **Invariant 3.1 generalised** to no model output on any authorisation path (config, rules, ontology), not just the runtime call graph; the ontology confirmed hand-authored (F6).
- **Cross-batch staging** stated plainly as absent from the default deployment (F7).
- **The review queue** recategorised from availability to an integrity / confused-deputy path (F8).
- **The temperature sweep** reframed as "no behavioural dependence detected", not corroboration of structure (F9).
- **Boundary scope** pinned to a tokenizer/template hash, not "model family"; 3.4 restated as "submitted" tokens with on-device as a precondition (F10).
- **A configuration/authoring adversary** added as a named gap and the obvious next invariant (F11).
- **This "least welcome findings" section** added, on the review's document-level finding that v1.0 spent all its care telling the reviewer which findings did not count and none naming the ones the author would least like.

Two points where the review was only partly accepted, recorded for honesty: its proposed break definition invoked a hypothetical "competent human reviewer" as the oracle; section 6 instead ties "in fact consequential" to the ground-truth labels of the obligation-8.2 corpus, which is measurable rather than hypothetical. And its F9 "null experiment" charge is accepted as a reframing (present the sweep as a dependence check) but not as "worthless": a sweep that could have surfaced an accidental behavioural dependence and did not is a modest real result, which is how it is now stated.
