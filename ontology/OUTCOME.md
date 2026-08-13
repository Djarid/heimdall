# Phase 2 Seed Ontology and Nornir: Outcome

**Author:** Jason Huxley
**Version:** 2.0
**Date:** August 2026
**Status:** result of authoring the Phase 1 seed on BFO (communications, then scheduling), a minimal Nornir, and the ontology test runs
**Reads with:** `ONTOLOGY_CONSTRUCTION.md` (sections 4, 5, 6, 8), `NEUROSYMBOLIC_FILTER_INVARIANTS.md` (invariants 3.9, 3.11), `spike/substrate/OUTCOME.md`, `DECISIONS.md`

---

## 1. Result

The Phase 1 seed ontology exists, spans two domains (communications and scheduling), runs through a deterministic Nornir, and passes the four test obligations of invariant 3.11 on a hand-labelled corpus. The coverage bound of invariant 3.9 is now a measured number: **90.5 percent** across two domains (it was 88.2 percent on the communications seed alone), with the rest failing safe to review.

| Obligation (section 8) | Result |
|------------------------|--------|
| 8.1 Coverage | 90.5% classified to a known type (19/21); the rest fail safe. Reported, not pass/fail. |
| 8.2 Classification correctness | 19/21 exact; 0 downgrades, 0 fail-safe breaches. The two mismatches are high-risk to high-risk (both gated), tolerated. |
| 8.3 Reasoner soundness | 13 derived facts, 0 unsound; every chain traces to its premises. |
| 8.4 Flow-to-sink | Three fixtures pass, including a genuine communications-to-scheduling-to-sink chain; agent-scoping honoured. |

No critical finding: no action-critical value was downgraded to an inert label, no uncovered content reached a trusted or actionable type, no unsound derivation, and the cross-domain state-staging cases (D30) were caught agent-scoped. This is the seed proven on this corpus across two domains, not a claim of complete coverage. The guarantee is reported with its coverage figure, never unqualified (invariant 3.9).

---

## 2. What was built

Runnable, substrate-neutral, in the existing `poc/.venv` with no third-party dependency. The substrate spike ratified a property graph (D25), so the loaded layers are authored as graph nodes and relations, not OWL, and map onto Memgraph later without a triple-store conversion.

- **`ontology/yggdrasil/`**: the loaded ontology as a Python package. `core.py` holds the node and relation model and the verified BFO anchor IRIs; `spine/` holds the trust lattice, action vocabulary and constraint vocabulary; `domain/communications.py` holds the medium-neutral seed domain; `unclassified.py` the fail-safe; `media.py` the taint-class bindings; `control_surface.py` the per-agent binding that deliberately does NOT live in the ontology (D20). `load()` composes them into one graph and validates it (45 nodes, 35 relations).
- **`ontology/nornir/`**: the deterministic classifier and reasoner. No model (invariant 3.1). Four rule kinds (classification, derivation, constraint, flow-to-sink). The flow-to-sink reachability reproduces the algorithm the substrate spike proved (D43), as the reference the live Memgraph binding must match.
- **`ontology/tests/`**: the harness and the ground-truth corpus (21 labelled cases across two domains, 3 flow fixtures). An audit artefact: failures are loud, the critical distinctions are called out rather than buried in a percentage. The harness derives its high-risk and inert type sets from the rule registry and ontology, so adding a domain does not require editing it.

---

## 3. Design decisions worth recording

### 3.1 The seed anchors to real BFO classes, checked

Every spine and domain type anchors to a BFO class by its verified IRI (from `ontology/upper/bfo/bfo-core.ttl`), and `load()` fails if a type anchors to an IRI not in the checked anchor set. A communication is a `generically dependent continuant` (medium-neutral information content); a requested action is a `realizable entity` (a disposition never realised by Heimdall); a trust level is a `role`; an action type is a `process`. No type redefines a BFO class (D23).

### 3.2 Medium-neutral by construction

The four PoC fields became a type hierarchy under `comms:communication`, with no medium in the type names. A payment request types to `comms:payment_request` whether it arrived by email, web, document or tool output. The corpus exercises this directly: the same fact via different media types identically (cases `benign-01` vs `benign-02`, `cred-01` vs `cred-02`). Media are taint classes in `media.py`, not types (D22, D22a).

### 3.3 Conservative classification errs toward the higher-risk type

The keyword rules are deliberately broad and ordered high-risk first. The reason is asymmetric cost: an over-classification (a benign article about "payment rails" typed as a payment request) costs a human review, while a downgrade (a real payment request typed as informational) lets an action-critical value skip Gjoll. The corpus includes `edge-02`, a benign article that over-classifies, recorded to show the rule errs in the safe direction. The harness treats a downgrade as fatal and an over-classification as tolerated.

### 3.4 High-risk to high-risk mismatch is not a downgrade

Case `instr-03` (a web page saying "approve a transfer") types as `payment_request` rather than the expected `instruction_to_act`. Both are high-risk and both are gated, so the value is not laundered to inert. The harness reports this as tolerated, not as a critical finding. Keyword rules cannot always separate one consequential intent from another, and for gating that distinction does not matter: what matters is that a consequential value is not typed as inert.

### 3.5 The action-critical machinery is present and dormant

The Phase 1 action-critical set is empty (no action sets `consequential=True`, asserted in `spine/action.py`). But the machinery is exercised: the control surface carries per-agent consequential sinks, and the flow-to-sink test fixtures supply an agent with a real sink to prove the propagation works, agent-scoped (D24). The same staged chain is inert for an agent with no sinks. This proves the mechanism without arming Gjoll in Phase 1.

### 3.6 The domain attach test is demonstrated, not just asserted

A second domain (scheduling) was attached to test D29 for real. Scheduling is a sibling type module (`yggdrasil/domain/scheduling.py`) and a sibling rule module (`nornir/domain_rules/scheduling.py`), both extending the shared spine and registering their own rules. `git diff` confirms the communications domain, the spine, `core.py` and `unclassified.py` were unchanged by the addition: the only edits were the loader's compose line and a one-time refactor of Nornir's rules into a per-domain registry (D50). A scheduling item is a `generically dependent continuant`, the same BFO root as a communication, so the two domains relate through their shared ancestor rather than drifting into separate dialects (D23). Coverage rose from 88.2 to 90.5 percent with no regression.

### 3.7 Cross-domain masking is safe and recorded, not fixed

With two domains sharing action vocabulary, a scheduled task phrased with generic action verbs ("run", "deploy") types as `comms:instruction_to_act` because the communications instruction rule shares the high-risk priority band and registers first. Both types are high-risk and gated, so the value is not laundered to inert: this is a sideways high-risk-to-high-risk mismatch, not a downgrade. It is recorded honestly (corpus case `sched-04`) rather than fixed with ad hoc priority, because arbitrating classification priority between domains that share vocabulary is exactly the cross-domain question the domain-governance decision (D31) settles. Fixing it in the seed would pre-empt that decision. This is decision D51, and it is a worked example that helps force D31.

---

## 4. Provenance discipline on the test corpus

The adversarial realism in the corpus (BEC with thread hijacking and VIP impersonation, fake invoice and wire requests, indirect prompt injection via email, web and screenshot) is informed by patterns in the maintainer's security-research corpus. Per D27 that material informed the TEST cases only; it never became classifier logic. Every expected label was set by a human, and no case is copied from a source; all are synthesised to exercise a labelled distinction. This keeps the classifier hand-authored while grounding the adversarial cases in real attack shapes.

---

## 5. The honest limits

- **Coverage is 90.5 percent on 21 cases across two domains.** That is a real number, not a large one, and it is a small corpus. It says the seed classifies these cases; it says nothing about the long tail. Coverage grows demand-driven (D26), and the fail-safe carries the rest.
- **Cross-domain classification priority is not yet governed.** The masking in 3.7 is safe but is a symptom: with more domains sharing vocabulary, deciding which domain's rule wins needs the D31 governance decision. The seed defers it deliberately.
- **This Nornir is substrate-neutral and per-batch.** It computes flow-to-sink reachability over one batch's flow graph, which is exact. The live system maintains the label incrementally in the store; the spike proved that is sound and cheap, but binding this to Memgraph and re-checking is still to do.
- **Extraction accuracy is out of scope** (invariant section 4), unchanged. The corpus tests typing and action-criticality, not whether the extracted values are correct.
- **The rules are keyword-based.** They are conservative and err safe, but they are not a claim of semantic understanding. Distinguishing an honest extraction error from an injection-induced one (D34) is still open and is where a richer classification-correctness corpus will bite.

---

## 6. What this advances

Invariant 3.11 moves from wholly untested toward demonstrated-on-a-seed: the deterministic classifier, the fail-safe path, reasoner soundness and agent-scoped cross-domain flow-to-sink all run and pass on a labelled corpus. Invariant 3.9's coverage bound is measurable, and grew from 88.2 to 90.5 percent when a second domain was added without regression. The attach tests (D29) are now demonstrated, not just structural: media beyond email feed the same types, and the scheduling domain attached under the spine without editing the communications domain or the spine. The residuals are the Memgraph binding (low-risk after the spike), the cross-domain priority governance (D31, now with a worked case), and growing coverage beyond the seed.
