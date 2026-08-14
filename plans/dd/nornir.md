# Detailed Design: Nornir (symbolic classifier and reasoner)

**Author:** Jason Huxley
**Date:** August 2026
**Version:** 0.1 (draft)
**Phase:** 2
**Status of the component today:** demonstrated on a four-domain seed with one deliberately-failing obligation (D67), per `plans/hld.md` section 3. The classifier, forward-chaining reasoner and constraint checker are real in `ontology/nornir/`; the false-inert obligation (8.2) is red at 1/17 by design (reduced from 3/12 by the D69 and D72 structural guards, re-opened each time by a fresh probe, now understood to be bounded by invariant 3.1, D72).

---

## 1. Purpose

Nornir is the deterministic layer that decides what a tainted assertion is. It takes the typed TAINTED assertions Bifröst produces, classifies each against the composed ontology, forward-chains the facts that follow, propagates action-critical status by flow-to-sink reachability and checks the constraint axioms. Nothing it emits is trusted or actionable by virtue of its own decision: classification types a value, it never promotes it. The load-bearing property is that it contains no language model on the authorisation path (invariant 3.1), so it cannot be told to reclassify by the content it reads.

This document takes Nornir to implementation fidelity for Phase 2. It specifies the pluggable classifier contract and its fail-closed binding invariant (D-2), the classify, reason and check-constraints interfaces at signature level, and the per-domain rule registry. It carries the open false-inert break (D67) as a first-class Phase-2 arming gate and does not commit to any candidate fix.

## 2. Responsibilities and boundaries

In scope for Nornir:

- Classify each marshalled assertion to an ontology type, or to a fail-safe when no positive rule matches, applying the cross-domain priority principle (highest risk tier, then specificity, then a genuine tie routes to review).
- Forward-chain derivation rules after classification and flow-to-sink, each derived fact carrying `inferred: true` and the assertion chain that produced it.
- Propagate action-critical status transitively by flow-to-sink reachability over the batch flow graph against the agent's consequential sink set (agent-scoped, cross-domain).
- Check the constraint axioms and raise a Gjallarhorn event on any violation.
- Route unclassifiable or unconfidently-classified content to `UNCLASSIFIED_DATA_ASSERTION`, `actionable: false`, human review and into Mímisbrunnr without any path to the control channel.

Out of scope for Nornir:

- Any language-model call. A model in the classification or trust-assignment path is a build-blocking defect (invariant 3.1), enforced by the AST symbolic-layer guard in the test harness, not by inspection alone.
- Trust promotion. Nornir types a value; moving it up the taint ladder is the promotion pipeline (HLD section 7.3), never a classification side effect.
- Owning the ontology. Nornir reasons over the composed ontology, which is owned by Yggdrasil (HLD section 5.12). Nornir owns only its rules.
- Storing world state. Classified assertions land in Mímisbrunnr (document 3); Nornir is a transform, not a store.

The describe-versus-obey distinction from the proof of concept holds throughout: a classification rule reads `requested_action_summary` to decide a type is `comms:payment_request`, which is describing untrusted content, not making a payment. The rules match on the shape and keywords of the extracted values as fixed Python, so no crafted payload can instruct a reclassification (`ontology/nornir/assertions.py`).

## 3. The core contracts

### 3.1 The pluggable classifier interface (D-2)

The classifier is a swappable component behind a stable interface. This is the locked D-2 stance: the structural design proceeds now, the classification mechanism is replaceable, and the interface is built to accept the current rule-based classifier, the candidate fix or a better mechanism later without redesigning Nornir.

**The binding invariant is fail-closed.** The interface's contract, not any one implementation, guarantees the direction of failure: unclassifiable or unconfidently-classified content routes to human review and is never typed to a trusted or actionable type. An implementation is a valid classifier only if it holds this contract. The contract has three parts:

- **No match is the fail-safe, never a guess.** Content matching no positive rule becomes `UNCLASSIFIED_DATA_ASSERTION`, `actionable: false`, routed to review (`ontology/nornir/engine.py:152`, `ontology/yggdrasil/unclassified.py:26`).
- **The inert type is earned, not defaulted.** A value receives a low-risk inert type only by a positive informational signal that also passes the shared inert-earning discipline (section 3.3). A passively-phrased consequential message does not silently go inert; when in doubt the inert label is denied and the value falls through to the fail-closed default of review.
- **A genuine high-risk tie routes to review.** Two top-tier rules of equal specificity naming different high-risk types resolve to `HIGH_RISK_UNRESOLVED`, which stays gated (action-critical if it can reach a sink), never a silent pick (`ontology/nornir/rules.py:262`).

**The D67 arming gate (risk R-1), and the scoped exception for the detection layer (D74).** The open false-inert break is a tracked Phase-2 arming gate, not a blocker on the design. The break: consequential content that positively earns an inert signal defeats the fail-closed default, because inertness is a content pattern an attacker can also satisfy. It is measured at 1/17 on an independent adversarial corpus and the suite is deliberately red (D67, reduced from 3/12 by the D69 shared inert-earning guard and the D72 referential-completeness guard, and re-opened at 1/17 by a fresh metaphor probe). The gate is a first-class rule: no autonomous consequential capability may arm against Nornir's classification until D67-fix is closed and re-measured on a genuinely independent corpus (one labelled by someone who has not seen the rules). Two guards have already reduced the rate (D69, D72) and each was re-opened by a fresh probe, which is the point rather than a failure of the fix: the rate is a lower bound, and no keyword widening escapes it (the treadmill invariant 3.5 forbids). One scoped exception to R-1 (D74): the Fenrir + Huginn DETECTION layer was built before D67-fix closed, because a fail-closed detector arms no consequential capability. It was proposed as D67-fix direction (d), an attempt-introspection catch: route inert-uncertain content through Fenrir under the tripwire, and treat any action request the model emits (which Fenrir's empty capability set refuses) as dispositive proof of consequence. Built and measured (D75, `phase2/`): the deterministic logic passes, but the real-model demonstration DEMOTED direction (d). A robust model is not steered by the false-inert payloads (fi-19, fi-20, and an overt injection were all read as tainted data and not acted on), so it emits no action attempt and the tripwire has nothing to catch. Direction (d) is therefore an injection-SUCCESS detector, not a false-inert fix for a resisting model, which is the case that matters here. The layer stands as a real component for safe reading and successful-injection detection; the live false-inert-fix directions are a deterministic referential-completeness discipline, a fail-closed advisory model, or accepting the bound. R-1 stays open and the suite stays red until D67-fix is closed and re-measured (D74, D75, `phase2/OUTCOME.md`).

**No commitment to the candidate fix.** The candidate mechanism (a narrow grammar-constrained model question where the inert label requires a documented no) is named in the HLD but is not committed here. The interface is what this document fixes; the mechanism behind it is deliberately left open so the fix, when it lands, is a swap behind the contract rather than a Nornir redesign. Understanding recorded in D72 and invariant 3.5: separating a passively-phrased or metaphorical consequence from a genuine informational statement requires world knowledge, so a purely deterministic content classifier has an inherent residual. A model that DECIDES trust (grants inertness) is barred by 3.1 because that decision is injectable; a model that only ADVISES in a fail-closed direction (routes to review, never grants inertness) is permitted (3.5), which is the correction recorded in the D72 row after an earlier draft over-stated the bar. Any accepted fix is therefore a deterministic referential-completeness discipline stronger than a regex; a fail-closed advisory model (Huginn-style, direction b); or accepting the residual as the stated bound and reporting the guarantee alongside it. (Direction d, the attempt-introspection catch through Fenrir, was built and demoted, D75: a robust model is not steered, so it is an injection-success detector, not a false-inert fix.)

### 3.2 The classify, reason and check-constraints interfaces (signature level)

Nornir runs as one ordered pass over a batch. The public entry point is `Nornir.run`, and the order is fixed: classify, then flow-to-sink, then derivations (so a derivation can key on the action-critical label), then constraints (`ontology/nornir/engine.py:164`).

```
Nornir.run(assertions: list[MarshalledAssertion],
           agent: AgentContext | None = None) -> NornirResult
```

The three contract surfaces the HLD names map to concrete functions:

- **classify.** `classify_assertion(a: MarshalledAssertion) -> ClassificationOutcome` collects every matching rule and applies the priority principle, returning a chosen type, a genuine tie or no match (`ontology/nornir/rules.py:229`). The engine wraps it in `_classify_one`, which turns no match into the `UNCLASSIFIED` fail-safe and a tie into `HIGH_RISK_UNRESOLVED`, and honours a type's declared `route` read from the ontology node rather than hardcoded, so a domain that adds a review-routed type needs no engine change (`ontology/nornir/engine.py:112`).
- **reason.** Forward-chaining runs each `DerivationRule` over every classified assertion, appending `{"fact", "chain", "rule"}` entries to `ClassifiedAssertion.inferred`. Each `DerivationRule` carries its own `entails(assertion, fact) -> bool` soundness oracle, so a derived fact is verifiable against the rule that produced it rather than against harness-hardcoded knowledge (`ontology/nornir/rules.py:276`). The two seed rules are `high_risk_needs_review` and the chained `action_critical_needs_second_approval`, which fires only when a value is both high-risk by type and action-critical by flow-to-sink. Derivations confer scrutiny, never trust or actionable status.
- **check_constraints.** `check_constraints(classified: list[ClassifiedAssertion]) -> list[Violation]` evaluates the constraint axioms over the batch (`ontology/nornir/rules.py:373`). The seed axiom `no_tainted_actionable` catches a TAINTED assertion marked actionable. The engine adds `_check_gating`, the `action_critical_must_gate` axiom, which asserts every value that can reach a consequential sink is marked action-critical; a divergence between the flag and the reachable set is the critical misclassification of obligation 8.2 (`ontology/nornir/engine.py:206`). A violation is a Gjallarhorn event.

Flow-to-sink is the fourth rule kind and feeds the reason and constraint steps. `action_critical_set(flow_edges, sinks) -> set[str]` is a backward breadth-first search from the agent's sink set over reversed edges, reproducing the substrate spike's proven algorithm exactly on a per-batch graph (`ontology/nornir/rules.py:400`). It runs through an injectable backend (`in_memory` by default, an optional `MemgraphFlowBackend` for a live store, D63); both return the same set for the same input, and nothing about the store leaks into the default path.

`NornirResult` carries the classified assertions, the violations and the action-critical set, and exposes `coverage()` (the reported fraction classified to a known type versus the fail-safe) and `coverage_gaps()` (review-routed assertions grouped by reason, so coverage growth is demand-driven off real signal; it reports, it does not act, D60) (`ontology/nornir/engine.py:35`).

### 3.3 The per-domain rule registry (the attach pattern)

Rules are contributed per domain through a registry, not a central list, so a new domain is a sibling module that registers its own rules and never edits another domain's rules or the spine (the D29 attach test extended to rules, D50). A domain module calls `register_classification_rule(rule)` at import time, and `Nornir.__init__` loads every domain's rules through `domain_rules.register_all()`, idempotently (`ontology/nornir/rules.py:203`, `ontology/nornir/engine.py:110`). The four seed domains are communications, scheduling, finance and publication (`ontology/nornir/domain_rules/`).

Registration order is no longer load-bearing (D31, resolving D51). The winner among matching rules is decided by the priority principle in `classify_assertion`: highest `risk_tier` wins so nothing is masked down to inert, then highest `specificity` within the top tier, then a genuine tie between different high-risk types routes to review. The tiers are `FALLBACK` (below inert, the last-resort `comms:unrecognised_request`), `INERT` and `HIGH` (`ontology/nornir/rules.py:53`). A tie between two purely inert types resolves deterministically by name rather than routing to review, since no gating decision hinges on it (D61).

Two shared structures are authored once over the whole rule set rather than per domain, the same discipline as the flow-to-sink rule:

- **The high-risk type registry.** Each domain declares its high-risk types by `register_high_risk_types(...)`; the shared derivation rule reads the set, so a domain contributes high-risk types without editing the rule (`ontology/nornir/rules.py:307`).
- **The shared inert-earning guard (D69, extended by D72).** A value earns an inert type only if `earns_inert(a)` holds, which requires it carry no imperative or consequence signal (`carries_imperative_or_consequence`, D69) and not defer a consequence to out-of-message context (`defers_consequence_to_context`, D72) (`ontology/nornir/rules.py:185`). The guard exists because a repository-access review found only the communications inert rule required no imperative, so consequential content that earned another domain's bare keyword signal went inert and skipped both the gate and review. It is not a blacklist of attacks (invariant 3.5): it is a conservative "does this ask for, or describe, something with an effect?" test that denies inert and falls through to review when in doubt, so an imperfect detector here only ever means more review, never a silent inert.

## 4. Composition over the ontology

Nornir does not carry the type structure; it loads it. The composed ontology (upper BFO spine, domain layers, action space, constraint space, trust layer) is Yggdrasil's, and Nornir reads it as data (`ontology/nornir/engine.py:22`). A classified assertion's `route` and `risk` come from the ontology node, not from engine code, so a domain that adds a review-routed or low-risk type does not force a Nornir change. The `UNCLASSIFIED_DATA_ASSERTION` and `HIGH_RISK_UNRESOLVED` fail-safes anchor to the same BFO root as a communication (`generically dependent continuant`), so an unclassified assertion is still information content inside the tree, not a value floating outside it (`ontology/yggdrasil/unclassified.py`).

## 5. Fail-closed behaviour

- Content matching no positive rule is `UNCLASSIFIED_DATA_ASSERTION`, `actionable: false`, routed to review. There is no default to a trusted or actionable type (`ontology/nornir/engine.py:152`).
- A value earns an inert type only through a positive informational signal that passes the shared inert-earning guard. An unmatched request never lands inert, and the fail-closed property test asserts this on generated novel inputs (obligation 8.2b).
- A genuine high-risk tie routes to `HIGH_RISK_UNRESOLVED`, which stays gated; Nornir never silently picks one of the tied types.
- A TAINTED assertion is never marked actionable, and Phase 2 marks nothing actionable regardless; the `no_tainted_actionable` axiom catches a regression.
- Any value that can reach a consequential sink is marked action-critical; the `action_critical_must_gate` axiom catches a flag-versus-reachable-set divergence, which would be a value skipping Gjöll.
- The known residual is the D67 false-inert break: consequential content that positively earns an inert signal is neither gated nor reviewed. It is measured, named and left red, and it is the arming gate of section 3.1, not a silent gap.

## 6. Data owned

- The classification-rule registry (per domain, populated at import through `register_classification_rule`).
- The derivation rules and their entailment oracles (`DERIVATION_RULES`).
- The constraint axioms (`check_constraints` and the engine's gating axiom).
- The high-risk type set and the shared inert-earning guard, authored once over the rule set.
- No persistent world state. Classified assertions are handed to Mímisbrunnr, which owns them. The ontology is owned by Yggdrasil; Nornir loads it.

## 7. Dependencies

- Upstream: Bifröst (document 2), which hands Nornir typed TAINTED assertions and nothing else. The marshalling seam turns a Fenrir or proof-of-concept extraction envelope into a `MarshalledAssertion`, deterministic and model-free, failing closed if any field claims non-untrusted provenance (D28, D62).
- Downstream: Mímisbrunnr (document 3), which stores the classified assertions with taint and provenance; Gjallarhorn (document 9), which receives a constraint violation as an event.
- Lateral: Yggdrasil supplies the composed ontology; the flow-to-sink backend may be the in-memory reference or a Memgraph binding, both proven equivalent (D63).

## 8. Build delta from today

- The classifier, forward-chaining reasoner, flow-to-sink propagation and constraint checker are real in `ontology/nornir/` on a four-domain seed. Phase 2 hardens them over Mímisbrunnr as a persistent typed store rather than the per-batch in-memory pass, using the incremental flow-to-sink maintenance the substrate spike proved (document 3).
- Coverage is 36/38 on a self-authored four-domain corpus, reported as a fraction with a Wilson interval rather than a false-precision percent. Breadth beyond the seed is untested, and a genuinely independent labelled corpus does not exist (risk R-2). Building that corpus is the highest-information next artefact and is named as a required Phase-2 deliverable in the test plan.
- D67-fix is open. The classifier interface (section 3.1) is built to accept the fix behind its fail-closed contract; no consequential capability arms against Nornir until the fix closes and is re-measured on an independent corpus (risk R-1).
- Coverage growth stays hand-authored and human-curated, driven by the coverage-gap capture (D60); the automated Odin proposal path is Phase 5 and provenance-gated (D27).

## 9. Test plan

Nornir inherits the ontology test harness (`ontology/tests/harness.py`), which runs the four obligations of invariant 3.11 plus the fail-closed property, the false-inert measurement, the Gjöll gate and the symbolic-layer guard. The inherited obligations:

- **8.1 Coverage measurement.** The reported fraction classified to a known type versus `UNCLASSIFIED`, with a Wilson interval. The hard invariant behind the number is that uncovered content fails safe, never to a trusted or actionable type; a fail-safe breach is a critical finding.
- **8.2 Classification correctness.** Each case to its expected type, with the failure direction distinguished: a downgrade of an action-critical value to an inert label is a critical finding that fails the suite, while an over-classification costs only a review and is tolerated. This obligation is deliberately red, at false-inert 1/17 on the independent adversarial corpus, and it is left red because a suite that names a real break is worth more than a green one that never tested it. A future session must not mistake this red bar for a regression, and must not silence it with more keywords.
- **8.3 Reasoner soundness.** Every derived fact is checked against its producing rule's entailment oracle and must carry its assertion chain; a chained derivation is exercised; and a deliberately-unsound rule is registered as a negative control and must be caught, so the check is proven to bite (D56).
- **8.4 Flow-to-sink reachability.** Agent-scoped and cross-domain, including the mandatory state-staging case where a value reaches a sink only through a multi-hop cross-domain chain (D30). A missing action-critical value is fatal; an extra one fails safe.

Nornir adds, before implementation:

- **Fail-closed property tests (obligation 8.2b).** Generate request-shaped inputs from neutral scaffolding and novel nonsense tokens that match no positive keyword, and assert none receives an inert type: every one must route to review or to a high-risk type. The test scans no content for malicious wording (that would be the invariant 3.5 mistake); it checks only where an unmatched request lands. It fails loudly against a simulated eager catch-all, so it catches a regression that reopens the silent-downgrade path.
- **The pluggable-interface swap test.** Substitute a second classifier implementation behind the interface of section 3.1 and assert the fail-closed contract holds identically: no match routes to the fail-safe, an inert type is earned not defaulted, and a high-risk tie routes to review. This proves the D-2 swappability is real, so a later D67-fix mechanism can bind without a Nornir redesign, and that the contract, not any one implementation, carries the fail-closed guarantee.
- **The independent-corpus construction.** A genuinely independent adversarial corpus, labelled for consequentiality by someone who has not seen the rules, is a required Phase-2 artefact. It turns the 1/17 lower bound into an estimate and is the re-measurement gate that D67-fix must clear before any consequential capability arms (risk R-1). The existing `false_inert_adversarial.json` is self-authored and externally-labelled, so its rate is a lower bound, not the independent measurement the arming gate requires.

Coverage is reported line and branch, and a green count over low branch coverage is not evidence on a fail-closed component, because the failure paths (fail-safe routing, tie-to-review, the gating axiom) are the point. The symbolic-layer guard runs first and is fatal: an AST scan of the authorisation-path packages asserts no model import, no inference call and no model subprocess, enforced by a known-good allowlist so an unlisted egress route is a violation by construction (D68, D70, D71).

## 10. Decisions (index)

| # | Decision | Chosen | Rejected | Rationale |
|---|---|---|---|---|
| NR-1 | Classifier stance on the open false-inert break | Pluggable classifier behind a stable fail-closed interface; D67-fix tracked as a Phase-2 arming gate | Adopt the candidate D67-fix now; block all Nornir design until D67-fix closes | HLD D-2. The structural design proceeds, the mechanism is swappable, and no consequential capability arms until D67-fix closes and is re-measured on an independent corpus. Honours the discipline that a red suite naming a real break beats a false green. |
| NR-2 | What carries the fail-closed guarantee | The interface contract, verified by a swap test | The current rule-based implementation | If the guarantee lived in one implementation it would not survive the swap D-2 requires. The contract (no match to fail-safe, inert earned, tie to review) is the invariant; any implementation must hold it. |
| NR-3 | Cross-domain classification winner | Risk tier, then specificity, then a genuine high-risk tie to review | First registered rule wins | Registration order was an accident of import order (D51). Risk-first guarantees nothing is masked down to inert (D31, D52); a true tie fails safe to review while staying gated. |
| NR-4 | Inert-earning discipline | A shared guard authored once over the rule set, denying inert on any imperative, consequence or deferred-context signal | A per-domain bare keyword match; enumerating attack phrasings as high-risk keywords | A per-domain asymmetry was the concrete false-inert break (D69). Enumerating malicious phrasings is the injectable-classifier mistake one layer over and fails open on the next phrasing (invariant 3.5). The guard denies inert when in doubt, so an imperfect detector means more review, never a silent inert. |
| NR-5 | Rule contribution | Per-domain modules registering into shared registries; shared structures (flow-to-sink, high-risk set, inert guard) authored once | A central rule list edited per domain | Makes the D29 attach test hold for rules (D50): a new domain is a sibling module that never edits another domain's rules or the spine. |
| NR-6 | Flow-to-sink backend | An injectable backend, in-memory by default, Memgraph optional | Hardcode the store, or hardcode the in-memory path | The per-batch in-memory reachability is exact and dependency-free (D01, D47); the Memgraph backend runs the same determination over a live store, verified equivalent (D63). The default carries no store dependency. |

---

## Licence

Part of the Heimdall specification, licensed under CC-BY-SA-4.0. See `LICENSE.md`.
