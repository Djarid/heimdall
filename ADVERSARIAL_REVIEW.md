# Heimdall: Adversarial Review Brief

**Author:** Jason Huxley
**Version:** 2.1
**Date:** August 2026
**Status:** a briefing for a hostile reviewer; revised after two hostile reviews. v2.1 acts on the second review's structural findings, and, more importantly, on its central point: it stopped polishing prose and built the false-inert measurement, which found a real break (see the changelog at the end)
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

The gate that authorises a consequential action is a **four-term conjunction** (verify against `ontology/nornir/gjoll.py`): block if the sink is consequential for this agent (declared) AND the parameter is consumed as an action rather than inert (declared) AND the value is untrusted-derived (structural) AND the value is action-critical (classified). Only one of the four terms is the proven structural property; two are per-sink declarations and one is classified from model text. So the guarantee is the weakest of a structural property, two unattested declarations and a measured classifier, and v2.0's statement of it as a two-term (structural-and-classified) conjunction understated the declaration surface. The flow-to-sink computation does not escape this either: it is transitive closure over a graph whose edges and sink semantics are also declarations (see 5.1), so "computed, not a per-sink label" is one level of indirection over declarations, not a change in kind.

---

## 3. What is PROVEN, on what, and what the D62 seam did to those proofs

The structural invariants (3.1 to 3.10) were established in the premise proof-of-concept: running code, an adversarial corpus of 31 cases, one local model (`Qwen2.5-7B-Instruct-4bit`), two decoding temperatures. Evidence: `poc/`, `poc/OUTCOME.md`.

The strongest details, which you should try hardest to break precisely because they look solid:
- **3.3 forgery closures.** Two real forgeries found and closed: an in-band delimiter a payload could contain, and a tokenizer-level control-token forgery. The boundary is now out-of-band token-id splicing.
- **3.5 method.** Content-detection was disproven by building the heuristic and showing it fails 11 cases including a clean control, not by assertion.
- **Negative controls throughout:** the unsound derivation (D56), the simulated eager catch-all (D54/D55), the unsafe sink wiring (3.6). Passes mean something only because a mandated control would fail.

**The scope caveat v1.0 hid (accept this as a live weakness).** Those proofs were established *before* the marshalling seam (D62) connected the real model pipeline to the ontology. After D62, the classifier's keyword rules run over model-produced text, and the resulting type decides criticality, which decides whether the gate blocks. So **model behaviour now influences the gate outcome through criticality**, even though it does not influence provenance. The honest per-invariant status after the seam:

Marked with three honest states, not two: **[argued-unaffected]** the seam is reasoned not to touch it; **[re-verified]** actually re-run after the seam; **[exposed]** the seam changed its input and its adversarial behaviour is now open. This distinction is the review's G9: careful scoping is not completed verification.

- 3.1, 3.2, 3.3, 3.4 **[argued-unaffected]**: structural, provenance-path. The seam feeds model text to the *classifier*, not to these; they are reasoned unaffected, not re-run against a post-seam corpus.
- 3.5 output path: proven. Classification path **[re-verified, and now failing]**: the fail-closed property test runs post-seam and passes, but the false-inert measurement (5.2) runs post-seam and *fails at 3/12*. So the classification path is re-verified and the verification is red.
- 3.6 provenance-gate half: proven **[re-verified]** end to end with the real model (D62, `e2e_harness.py`). Action-critical half **[exposed]**: inherits the classification dependency, hence the false-inert break.
- 3.9 **[argued-unaffected, with the risk relocated]**: the invariant doc states it precisely (no safety property depends on model determinism or good behaviour; extent bounded by ontology coverage, marked NOT YET TESTED). That still holds post-seam, a mistyped value is caught or not by the *deterministic* classifier and gate, not by the model behaving. But the seam puts model-produced text into the classifier's input, so the already-untested coverage bound is where the risk sits, and it is now measured non-zero (5.2). v1.0's flat "safety holds regardless of model behaviour" oversimplified the doc, which is more careful.

The project still does not publish a formal per-invariant re-verification table; the three states above are this brief's partial stand-in, and a reviewer should ask for the real one.

---

## 4. What is DEMONSTRATED on a small, self-authored seed

"Demonstrated" means it runs and passes on a hand-authored ontology and corpus, with a real model at the seam and over a live store. Not proven at production coverage or scale, and the corpus was written by the same author who wrote the classification rules, so it measures internal consistency, not adversarial robustness.

- **The ontology (invariant 3.11):** a deterministic classifier over a BFO spine plus four domains (communications, scheduling, finance, publication), the UNCLASSIFIED fail-safe, forward-chaining derivation, agent-scoped cross-domain flow-to-sink. **The ontology and all rules are asserted hand-authored, no model output on the authoring path.** Take care with the evidence: the runtime fact "no model call under `ontology/`" does NOT establish this, because a rule drafted by a model and pasted in by hand leaves no call (this is the same category error as the runtime AST check, one level up, and section 8 lists model-drafted rules as a redesign-forcing finding). The claim currently rests on the author's assertion plus git authorship, not on an independent attestation; treat it as asserted, not verified. Evidence: `ontology/`, `git log`, `ontology/OUTCOME.md`.
- **The gate (D58), fail-closed classification (D54) and its property test (D55), reasoner soundness with a control (D56), the substrate binding (D57), live-store integration and cross-batch staging (D63/D64), the marshalling seam (D62).** Each has a passing check; the cross-batch-staging catch (D64) is real and was absent before.
- **Coverage: 36 of 38 corpus cases classify to a known type; the other 2 fail safe.** (The harness reports this as "94.7%"; on n=38 that is false precision, the 95 percent Wilson interval is 83 to 99 percent.) Coverage is **not** the bound of the guarantee (see 6); it is a demonstration figure.

---

## 5. Where to attack (re-ranked; the root joint is first)

Ordered by where a real finding is most likely, corrected from v1.0 which under-ranked its own root.

### 5.1 Sink and flow declarations are trusted input, and nothing attests them (the root)
The flow-to-sink graph's edges and each sink's declaration of how it consumes a field (inert vs action) are declarations, not derived facts. The gate proves a *declared* wiring safe or unsafe; it does not verify the declaration against behaviour. A sink that declares it consumes an action-critical value as inert, but actually acts on it, passes the gate. A missing flow edge is a silent hole. Inert-rule precision (5.2), extraction accuracy (5.6) and cross-batch staging (5.5) all reduce to this: labels only mean something if the graph they propagate over is honest. This is the single most load-bearing unverified assumption in the design, and there is currently no integrity control, signing, or behaviour-derivation for it. Attack here first.

### 5.2 Inert-rule precision under adversarial phrasing (now measured, and non-zero)
Classification is conservative keyword/shape matching over model-produced text. The security-critical number is the **false-inert rate**: the fraction of genuinely consequential content that the classifier types to an inert type, so it is never marked action-critical, never gated, and never sent to review. This is the actual bound of the guarantee. v2.0 called it unmeasured; it is now measured, and this is the substantive result of the second review. An independent adversarial corpus (`ontology/tests/corpora/false_inert_adversarial.json`) labels consequentiality by an external test (does doing what it asks move money, grant access, run code, exfiltrate data or change security state?) and constructs cases to evade the rule vocabulary. **The measured rate is 3/12, and the test suite is red because of it (D67).** The mechanism: euphemistic cases that merely evade the high-risk keywords still fail closed to review (the D54 catch-all catches them), but consequential content that *positively earns an inert signal* (an informational, calendar or publication signal wrapping a consequential request) is typed inert and skips both gate and review. That is invariant 3.5 in its deeper form: the inert-earning signal is itself a content pattern an attacker can satisfy. Attack: extend the corpus with more such cases and push the rate up; the fix is an OPEN design change to how inertness is earned (D67-fix), not a keyword blacklist (3.5). Honest limit on the number: one author wrote both the rules and this corpus, so the consequence labels come from the external test rather than from third-party judgement; a genuinely independent corpus (labelled by someone who has not seen the rules) would likely push the rate higher, so 3/12 is a lower bound, not an estimate.

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

### 5.9 Origin trust is per-source, but real sources are mixed-trust containers (attacks the proven half)
The structural half of the guarantee (trust by origin) is the genuinely proven half, and it rests on origin trust being a well-founded property of a source. Real sources are not uniform: an internal wiki any employee (or a compromised account) can edit; a Slack workspace with external guests; an internal mail domain with one compromised mailbox; **tool output that itself fetched the web** (a trusted tool returning untrusted content); and a trusted document that quotes or forwards untrusted content (the forwarded-email case, the commonest shape in a real inbox). Invariant 3.2 propagates taint correctly *once* something is stamped untrusted, but the stamp is applied at source granularity, so a trusted source carrying attacker-influenced content inside it is a laundering path into the trusted side that requires no boundary forgery. Verified in the current build: the PoC stamps all boundary-crossing content uniformly `UNTRUSTED` and has no trusted-source path, so this does not bite yet; but the moment any source is trusted at source granularity, there is no rule re-stamping its embedded untrusted regions. Attack / construction obligation: state at what granularity provenance is assigned, and either restrict the trusted set to sources with no untrusted write path (which likely excludes tool output entirely) or add embedded-region re-stamping. This is distinct from 5.8 (who may edit the trusted-origin list); this is whether a legitimately-trusted origin can carry untrusted content.

### 5.10 Substrate dense-cycle cost (a performance caveat, lowest)
Edge-deletion retraction is sound but degrades toward full-graph work when reachability is one dense strongly-connected component. A realistic flow graph is sparse; this is a monitoring caveat, not a security seam, unless a workload can force the degenerate case.

---

## 6. What counts as a real break (stated in consequence, not in the system's own labels)

v1.0 stated break conditions using `action-critical`, a computed label, which made every classifier miss a non-break by construction. Corrected: a break is defined against real-world consequence and ground-truth labels, not the system's output.

**A real break** is any of:
- Untrusted-derived content parameterises an action with real-world consequence, without a human decision, when that content was **in fact** consequential. "In fact consequential" is adjudicated against ground-truth labels, not against what the classifier decided. A consequential value the classifier typed as inert, so it skipped the gate, is a break, not a coverage observation. **This is no longer hypothetical: it is measured at 3/12 on the independent adversarial corpus (5.2, D67), and the test suite is red because of it.**
- Uncovered or unrecognised content is typed as a **trusted or inert** type by default rather than routed to review (a genuine fail-open of the default). Inert is the dangerous default, because inert skips the gate; an actionable/trusted type would at least reach the gate.
- Content forges the origin boundary so the model treats it as an instruction.
- A model call, or model-generated content (rules, ontology, config), sits on an action-authorisation path.
- A sink's declaration diverges from its behaviour so the gate authorises an action it should have blocked (5.1).

**A severity gradient, not a separate category.** Classifier misses are breaks, graded by the **ground-truth consequence class of the content, never by the outcome that happened to occur** (grading by outcome would launder a break as low-severity whenever the sink happened not to act, which is the very sink-behaviour thing 5.1 says is unattested). So: a consequential-and-irreversible value (a payment, an access grant) typed inert is a high-severity break; a consequential-but-reversible value typed inert is a lower-severity break; content whose ground-truth label is non-consequential and is typed inert is not a break at all, it is correct. This corrects v1.0 (which parked all misses as non-breaks) and v2.0 (which graded by outcome and offered a "mistyped newsletter" example that, being non-consequential, was never a break).

**Genuinely not a break (the fail-safe working):** content that is uncovered and routes to review; content the classifier types to a *higher*-risk type than needed (an over-classification, which is a cost, not a safety property, and should be counted as a cost not pooled with the fail-safe). If you can only get content to the review queue, you have not broken the action path, but see 5.3: the review queue is itself an attackable integrity path.

The distinction is itself a claim you may attack: if you can show the fail-closed default is not closed (uncovered content reaching an inert or trusted type, or the review route being bypassable), that collapses the distinction and is a headline finding.

---

## 7. Numbers a hostile reviewer will ask for and cannot find

These are the evidential gaps, and the first is the one the design should not be signed off without.

The status column distinguishes **measured** (a number from a run), **stated** (an asserted fact, not independently verified), and **no**.

| Wanted | Status |
|--------|--------|
| False-inert rate under adversarial phrasing (**the** bound) | Measured, 3/12, on a self-authored-but-externally-labelled corpus (5.2, D67); an independent third-party corpus is still No |
| Held-out or third-party / red-team corpus results (the seed is self-authored) | No |
| Count and breadth of inert rules (the actual capability-grant surface) | No |
| Review-queue throughput and assumed human error rate at that rate (the fourth bound) | No |
| Which of 3.1 to 3.10 were re-verified after the D62 seam | Partial: the three-state marking in section 3, not a formal table |
| Build-time provenance of the ontology | Stated (hand-authored, asserted not attested; section 4, G5) |
| Coverage as a raw fraction with an interval (36/38) | Measured (section 4) |
| An adversary model for configuration and rule authoring | No (5.8) |
| Origin-trust granularity and mixed-trust-source handling | No (5.9) |
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

The single most honest sentence about the project, corrected again (v1.0 attributed the whole bound to coverage, the one input with a number; v2.0 named three bounds but omitted the human, the one bound with no artefact to point at): **the premise is proven for a pre-seam system and only partially re-verified since; the mechanism is demonstrated on a small self-authored seed; and the guarantee is bounded by four things, ontology coverage (measured), inert-rule precision under adversarial phrasing (now measured non-zero, 3/12, and red), the honesty of sink and flow declarations (unattested), and the reliability of the human reviewer at the induced review rate of roughly a quarter of traffic (unmeasured).** Test that sentence hardest; the fourth bound is the one the design has nothing to point at, which is exactly why it kept being left out.

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

Two points where the review was only partly accepted, recorded for honesty: its proposed break definition invoked a hypothetical "competent human reviewer" as the oracle; section 6 instead ties "in fact consequential" to ground-truth labels derived from an external consequence test, which is measurable rather than hypothetical. And its F9 "null experiment" charge is accepted as a reframing (present the sweep as a dependence check) but not as "worthless": a sweep that could have surfaced an accidental behavioural dependence and did not is a modest real result, which is how it is now stated.

**The v1.0 review changed no artefact.** All eleven corrections above were changes to how the system was described, not to what it does. That is the second review's finding G1, and it is stated plainly here rather than left implicit: a code-blind reviewer moved the claims layer eleven times and the implementation zero times, which is a fact about how loosely v1.0's claims were bound to the artefact, not a sign of diligence.

## Changelog: what the second hostile review changed (v2.1)

The second review's load-bearing instruction was to stop polishing prose and produce a real number. This round did, and unlike the first round it **changed the artefact, not only the description**:

- **Built the false-inert measurement** (G2, the residual of the headline finding): an independent adversarial corpus (`ontology/tests/corpora/false_inert_adversarial.json`) with externally-derived consequence labels and cases constructed to evade the rule vocabulary, plus a harness obligation. It found a real, reproducible break at **3/12**, and the test suite is now red because of it (D67). This is the first finding in three rounds that changed code and test outcomes rather than wording.
- **Left the suite red and named the break** rather than patching it; the fix (how inertness is earned so an inert signal cannot override a co-present consequence signal) is an OPEN design item (D67-fix), not a keyword blacklist.

The prose corrections the second review also forced: the gate restated as the true four-term conjunction (G6); the break severity gradient bound to ground-truth consequence class, not outcome, and the non-break "newsletter" example deleted (G3); the nominated most-honest sentence given its fourth bound, the human reviewer (G4); the hand-authorship claim demoted from "verifiable" to "asserted" because absence of runtime calls cannot establish authoring provenance (G5); a new seam added for origin trust being per-source while real sources are mixed-trust containers, which attacks the proven half (G7); the per-invariant status given three states (re-verified / argued-unaffected / exposed) instead of two (G9); the numbers table marking measured versus stated; and G1 stated plainly above.

Not accepted as an artefact change this round, deliberately: the review's own closing verdict is that a third *documentation* round would be diminishing returns and the only work with real information in it is a number, a schema, or a reviewer with repository access. This round produced the number. The next units of real information are an independently-labelled corpus (to turn 3/12 from a lower bound into an estimate) and the sink-declaration schema published so seam 5.1 becomes attackable by someone other than its author. Those are build tasks, not brief revisions.
