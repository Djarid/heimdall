# Heimdall: Adversarial Review Brief

**Author:** Jason Huxley
**Version:** 1.0
**Date:** August 2026
**Status:** a briefing for a hostile reviewer; written to be attacked, not to reassure
**Reads with:** `HEIMDALL.md` (architecture), `NEUROSYMBOLIC_FILTER_INVARIANTS.md` (the invariants and their proof status), `DECISIONS.md` (the 64 tracked decisions), `ONTOLOGY_CONSTRUCTION.md` (how the ontology is built and tested), `STATUS.md` (current state)

---

## 1. What this document is for

This is a brief for an adversarial reviewer, human or LLM, whose job is to break the design or find where its claims outrun its evidence. It is deliberately not a sales pitch. It states what Heimdall claims, points at the evidence, and then hands you the seams, assumptions and untested surface, because the project's worth is in stating limits plainly and a clearly-found hole is a good outcome.

Your task, if you are the reviewer: assume the claims are overstated somewhere, and find where. The most productive attacks are listed in section 5. If you can make one of the PROVEN invariants fail, or show that a DEMONSTRATED one does not generalise, or find a boundary the threat model misses, that is the result worth reporting.

A rule for the reviewer, because it is the load-bearing one: do not accept "we added a keyword rule to catch that attack" as a fix, and do not propose it as one. Detecting malicious content by pattern-matching is the mistake the whole architecture exists to avoid (invariant 3.5). If your critique reduces to "the classifier missed this phrasing", check first whether the content still fails closed (routes to review, or is gated by flow-to-sink); if it does, you have found a coverage observation, not a break.

---

## 2. The claim, in one paragraph

Heimdall lets an LLM agent work with untrusted external content (web, email, social, documents, tool output) without that content being able to cause action. Trust is assigned by origin at a single structural boundary, never by detecting malicious content. Untrusted content is quarantined as typed, inert data; the model only ever reads it as data; nothing acts on the model's output unless a wiring is proven safe by provenance and the value is not action-critical. "Action-critical" is not a per-sink label; it is computed by transitive flow-to-sink reachability over a world model, so a value inherits it the moment a path to a consequential sink exists, however many reversible hops intervene. The guarantee is only ever as strong as the ontology's coverage, and that bound is stated, not hidden.

---

## 3. What is claimed as PROVEN, and the evidence

These are the structural invariants the premise proof-of-concept established. "Proven" means demonstrated in running code on an adversarial corpus with a real local model, at two decoding temperatures. Evidence: `poc/`, `poc/OUTCOME.md`, invariants 3.1 to 3.10.

- **3.1 No language model in the symbolic layer.** The classifier, trust assignment and boundary are deterministic Python, verified by AST inspection each run. Attack surface: if any decision that authorises action consults a model, the guarantee is void.
- **3.2 Trust by origin at one boundary.** Provenance is stamped before content-sensitive parsing and is immutable. Everything derived from untrusted input is untrusted.
- **3.3 The data boundary is not forgeable by content.** Two real forgeries were found and closed in the PoC: an in-band string delimiter a payload could contain, and a tokenizer-level control-token forgery. The boundary is now out-of-band (token-id splicing, `split_special_tokens`).
- **3.4 The input assertion verifies the exact token ids the model received**, not a reconstruction.
- **3.5 Do not detect injection by inspecting content.** Output path proven by counter-example (an n-gram/imperative heuristic failed 11 cases including a clean control). Classification path demonstrated by a fail-closed property test (3.5 was extended to cover it).
- **3.6 (provenance gate half) Model output is inert until safely wired.** A safe wiring passes; an unsafe control wiring is caught before it fires, structurally, on every case.
- **3.9 (model-independence half) Safety holds regardless of model behaviour**, tested at temperature 0.0 and 0.7.
- **3.10 The harness is an audit artefact**, failures loud, clean and unsafe controls mandatory.

If you are reviewing, treat these as the strongest part. The PoC is small (31 cases, one model) but the properties are structural, not behavioural, which is why they held at temperature 0.7. The most credible attack on this tier is section 5.1 (the boundary is per model family).

---

## 4. What is claimed as DEMONSTRATED-on-the-seed, not proven

This is where the design has moved fastest and where the evidence is thinner. "Demonstrated on the seed" means it runs and passes on a small hand-authored ontology and corpus (four domains, 38 labelled cases, 94.7 percent coverage), with a real model at the marshalling seam, and over a live Memgraph store. It is not proven at production coverage or scale.

- **The ontology (invariant 3.11).** A deterministic classifier over a typed ontology (BFO spine plus communications, scheduling, finance, publication domains), the UNCLASSIFIED fail-safe, forward-chaining derivation, and agent-scoped cross-domain flow-to-sink. Evidence: `ontology/`, `ontology/OUTCOME.md`, `ontology/tests/harness.py`.
- **3.6 action-critical determination and gate (D58).** Gjoll authorises a consequential action only if no parameter it consumes as an action is an untrusted-derived, action-critical value. Caught with the mandatory safe-plus-unsafe control, including a value staged through a multi-hop cross-domain chain.
- **Cross-domain priority (D52), fail-closed classification (D54), and its enforcement (D55).** Inert types are earned by a positive signal; unmatched requests route to review; a property test asserts no unmatched request is ever typed inert, verified to fail against a simulated eager catch-all.
- **Reasoner soundness (D56)** with a negative control: a deliberately-unsound derivation is caught.
- **Substrate (D57) and live-store integration (D63, D64).** The flow-to-sink algorithm is proven on a live Memgraph store, matching an in-memory oracle across fuzzed sequences, and a persistent store catches state staging spread across separate batches.
- **Marshalling seam (D62).** Real model extraction is marshalled into a typed assertion and gated end to end; an injected directive extracted from real untrusted content is blocked before firing.

The honest summary of this tier: the mechanism is demonstrated; the coverage is not. See section 5.

---

## 5. Where to attack (the honest seam list)

This is the useful part for a reviewer. Ordered by how likely each is to yield a real finding.

### 5.1 Coverage is the guarantee's bound, and it is small
The whole live guarantee is exactly as strong as the ontology's coverage (invariant 3.11, design principle 10). Coverage is measured at 94.7 percent on a 38-case synthetic corpus across four domains. That is a demonstration, not a claim about the open web. Attacks to try: content whose real-world subject matter none of the four domains covers, and which is phrased to look positively like an inert type it is not. Note the defence before you claim a break: unrecognised content fails closed (routes to review), so to score you must get an action-critical value typed as a genuinely inert type, not merely get something into the review queue.

### 5.2 The classifier is keyword-based and cannot name pure euphemism (D34, open)
Classification rules are conservative keyword/shape matchers. They cannot distinguish an honest small-model extraction error from an injection-induced one, and they cannot name pure euphemism ("take care of the old records as we discussed"). This is an open research question. The design's answer is that euphemism still fails closed to review rather than to an inert type, so the euphemism buys no silent inert typing. Attack: find content that (a) should be action-critical, (b) is phrased to positively match an inert rule, and (c) therefore skips both review and the gate. If you can only get it to review, that is the fail-closed default working. Do not propose a keyword blacklist as the fix; that is invariant 3.5's mistake and it is explicitly rejected (D54, D55).

### 5.3 Sink-wiring honesty is assumed, not verified (invariant section 4)
The Gjoll gate proves a declared wiring safe or unsafe. It does not verify that a sink's declaration of how it consumes a field (inert vs action) is truthful. A sink that lies about consuming an action-critical value as inert would pass the gate. The design says consumption must be derived from real data flow, not a per-sink label, and that derivation is future work. Attack: this is a real trust assumption; probe whether anything forces a sink's declaration to match its behaviour. (It does not yet.)

### 5.4 Extraction accuracy is out of scope (invariant section 4)
A wrong sender, a poisoned entity list, a mis-summarised request all pass, because the extraction is inert. The premise is about action, not correctness. Attack: this is stated as out of scope, so it is not a break, but it is worth pressure-testing the boundary: is there any path where an inaccurate-but-inert value later parameterises an action without passing Gjoll? If yes, that is a real finding; if the value must pass Gjoll on the way to any action, the scope limit holds.

### 5.5 The boundary guarantees are per model family (invariant 3.7)
The control-token handling and boundary-forgery closures were verified for one tokenizer and chat template (Qwen2.5-7B-Instruct-4bit). A different model family has different control tokens. Attack: the mechanism is claimed general but the specific token ids are not; a model swap without re-deriving the control-token set is a live hole. Check whether model onboarding actually gates on boundary re-verification (it is specified, not yet built as a deployment gate).

### 5.6 Availability and the review queue (invariant section 4, D53)
Fail-closed routing sends a lot to human review: overlapping high-risk domains tie (about 15 percent of the seed corpus), and unrecognised requests route to review. This is safe but is a denial-of-service and alert-fatigue surface: flood the queue and a human rubber-stamps. Availability under load was not exercised. Attack: reason about whether the review queue is a soft target even though the action path is hard.

### 5.7 State staging, including across turns (D30, D64)
Action-critical status propagates transitively, and a persistent store now catches staging spread across separate batches. Attack: try to construct a staging chain the reachability graph does not see, for example a value that reaches a sink through a path that is not represented as a flow edge (the flow graph is only as complete as what feeds it, which loops back to sink-wiring honesty, 5.3). The per-batch default backend does NOT catch cross-batch staging; only the persistent mode does, and choosing it is a deployment decision.

### 5.8 The ontology substrate and dense cycles (D45)
Edge-deletion label retraction is sound but can degrade to near-full-graph work when reachability is one dense strongly-connected component. A realistic flow graph is sparse and mostly acyclic, so this is a monitoring caveat, but a reviewer might construct a workload that forces the degenerate case.

### 5.9 The gap between the PoC and the ontology build
The PoC (structural separation, proven) and the ontology build (classifier, reasoner, gate, demonstrated) are two bodies of code joined by the marshalling seam (D62). The seam is tested end to end with one real model on two messages. Attack: the seam is the newest joint and the least exercised; probe whether the PoC's provenance stamp and the ontology's TAINTED trust level can ever disagree, and whether a marshalled assertion can carry a field the classifier trusts more than it should.

---

## 6. What would count as a real break, versus a coverage observation

Because the design fails closed, most "the classifier missed X" findings are coverage observations, not breaks. Calibrate accordingly:

- **A real break:** an untrusted-derived, action-critical value reaches a consequential sink as an action without passing Gjoll; or an unrecognised/uncovered value is typed as a trusted or inert type by default rather than routed to review; or content forges the origin boundary so the model treats it as an instruction; or a model call sits on an action-authorisation path.
- **A coverage observation (useful, not a break):** content the ontology does not cover, which correctly routes to review; an over-classification to a higher-risk type; a benign message that ties and goes to review. These are the fail-safe working, and the honest response is demand-driven coverage growth, never a blacklist.

The distinction is deliberate and is itself a claim you may attack: if you can show the fail-closed default is not actually closed (something uncovered reaching an inert or trusted type, or the review route being bypassable), that collapses the distinction and is a headline finding.

---

## 7. Ground truth to check the claims against

Do not trust this summary; check it against the artifacts. The repository is designed so a cold reader can reconstruct and re-run everything.

- Run the ontology suite: `poc/.venv/bin/python -m ontology.tests.harness`. It reports coverage, classification correctness (downgrades are critical), the fail-closed property, reasoner soundness with its negative control, flow-to-sink reachability, and the Gjoll gate.
- Run the substrate spike: `poc/.venv/bin/python spike/substrate/harness.py`.
- Run the PoC: `cd poc && .venv/bin/python harness.py` (add `--temp 0.7`, and `--sinks unsafe` to see the gate catch the unsafe control).
- The optional real-model and live-store checks (`ontology/tests/e2e_harness.py`, `ontology/tests/memgraph_integration_harness.py`) skip cleanly if the model or Memgraph is absent, so their passing is not assumed by the core suite.
- Every claim above traces to a decision in `DECISIONS.md` with a realisation reference, and to an invariant in `NEUROSYMBOLIC_FILTER_INVARIANTS.md` with an explicit PROVEN / DEMONSTRATED / NOT YET TESTED mark. If a claim here is not backed there, that inconsistency is itself a finding.

The single most honest sentence about the whole project, and the one to test hardest: the premise is proven and the mechanism is demonstrated on a small seed; the guarantee's extent depends on ontology coverage, which is measured, not complete.
