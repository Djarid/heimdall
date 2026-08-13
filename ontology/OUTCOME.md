# Phase 2 Seed Ontology and Nornir: Outcome

**Author:** Jason Huxley
**Version:** 2.0
**Date:** August 2026
**Status:** result of authoring the Phase 1 seed on BFO (communications, then scheduling), a minimal Nornir, and the ontology test runs
**Reads with:** `ONTOLOGY_CONSTRUCTION.md` (sections 4, 5, 6, 8), `NEUROSYMBOLIC_FILTER_INVARIANTS.md` (invariants 3.9, 3.11), `spike/substrate/OUTCOME.md`, `DECISIONS.md`

---

## 1. Result

The Phase 1 seed ontology exists, spans three domains (communications, scheduling and finance), runs through a deterministic Nornir, and passes the four test obligations of invariant 3.11 on a hand-labelled corpus. The coverage bound of invariant 3.9 is now a measured number: **93.9 percent** across three domains (it was 88.2 percent on the communications seed alone), with the rest failing safe to review. Cross-domain classification priority is governed by a principle (D31, D52), and the inert classification fails closed (D54), both without a blacklist.

| Obligation (section 8) | Result |
|------------------------|--------|
| 8.1 Coverage | 93.9% classified to a known type (31/33); the rest fail safe. Reported, not pass/fail. |
| 8.2 Classification correctness | 30/33 exact; 0 downgrades, 0 fail-safe breaches. The three mismatches are high-risk to high-risk (both gated), tolerated. |
| 8.3 Reasoner soundness | 13 derived facts, 0 unsound; every chain traces to its premises. |
| 8.4 Flow-to-sink | Four fixtures pass, including genuine communications-to-scheduling-to-sink and communications-to-finance-to-payment-sink chains; agent-scoping honoured. |

No critical finding: no action-critical value was downgraded to an inert label, no uncovered content reached a trusted or actionable type, no unsound derivation, and the cross-domain state-staging cases (D30) were caught agent-scoped. This is the seed proven on this corpus across three domains, not a claim of complete coverage. The guarantee is reported with its coverage figure, never unqualified (invariant 3.9).

---

## 2. What was built

Runnable, substrate-neutral, in the existing `poc/.venv` with no third-party dependency. The substrate spike ratified a property graph (D25), so the loaded layers are authored as graph nodes and relations, not OWL, and map onto Memgraph later without a triple-store conversion.

- **`ontology/yggdrasil/`**: the loaded ontology as a Python package. `core.py` holds the node and relation model and the verified BFO anchor IRIs; `spine/` holds the trust lattice, action vocabulary and constraint vocabulary; `domain/communications.py` holds the medium-neutral seed domain; `unclassified.py` the fail-safe; `media.py` the taint-class bindings; `control_surface.py` the per-agent binding that deliberately does NOT live in the ontology (D20). `load()` composes them into one graph and validates it (45 nodes, 35 relations).
- **`ontology/nornir/`**: the deterministic classifier and reasoner. No model (invariant 3.1). Four rule kinds (classification, derivation, constraint, flow-to-sink). The flow-to-sink reachability reproduces the algorithm the substrate spike proved (D43), as the reference the live Memgraph binding must match.
- **`ontology/tests/`**: the harness and the ground-truth corpus (33 labelled cases across three domains, 4 flow fixtures). An audit artefact: failures are loud, the critical distinctions are called out rather than buried in a percentage. The harness derives its high-risk and inert type sets from the rule registry and ontology, so adding a domain does not require editing it.

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

### 3.6 The domain attach test is demonstrated twice, not just asserted

Two further domains were attached to test D29 for real: scheduling, then finance. Each is a sibling type module (`yggdrasil/domain/{scheduling,finance}.py`) and a sibling rule module (`nornir/domain_rules/{scheduling,finance}.py`), both extending the shared spine and registering their own rules. `git diff` confirms that adding finance left communications, scheduling (types AND rules), the spine, `core.py` and `unclassified.py` unchanged: the only edits were the loader's compose line and the new sibling modules. All three domains root at `generically dependent continuant`, the same BFO ancestor, so they relate through it rather than drifting into separate dialects (D23). Coverage rose 88.2 to 90.9 to 92.6 to 93.9 percent across the additions (the last step being the fail-closed catch-all of 3.9) with no regression.

### 3.7 Cross-domain priority is principled (D31, D52), not accidental

With two domains sharing action vocabulary, a scheduled task phrased with generic action verbs ("run", "deploy") originally typed as `comms:instruction_to_act` because the communications instruction rule registered first. That was safe (both types gate) but accidental. The domain-governance decision (D31) settled it with a cross-domain priority principle (D52): highest risk tier wins so nothing is masked down to inert; within a tier, higher specificity wins, so a scheduling signal (`cron`, `scheduled to`, `run at 2am`) beats a bare action verb and a genuine scheduled task types as `sched:scheduled_task`; and a genuine tie (two top-tier rules of equal specificity naming different types) routes to `HIGH_RISK_UNRESOLVED` for human review, gated, never silently picked. Registration order is no longer load-bearing. The corpus proves both the resolved masking case (`sched-04-task-with-action-verb`, now an exact match) and a genuine tie (`tie-01-payment-and-credential`, routed to review).

### 3.8 The finance domain measured the price of the principle (D53)

Finance was attached specifically to pressure-test D52, because finance and communications share the sharpest overlap: both cover payment. The account-reference rule (a concrete IBAN or sort code) is the narrowest signal and wins its tier cleanly. But money-movement content ("execute the payment", "wire transfer the funds") matches both `comms:payment_request` and `finance:financial_transaction` at equal specificity, so it ties to review, and some existing communications payment cases re-typed to finance once finance could claim them. The result across the corpus: 15 percent of cases now route to review as ties, all safe (high-risk, gated, zero downgrades, zero fail-safe breaches). This is the honest cost of overlapping high-risk domains, recorded as D53. Separating "a payment ask" from "a money movement" precisely is regex-tuning best done demand-driven (D26) once real traffic shows which overlaps occur; the tie-to-review net is the safety backstop until then. The point of the pressure test is proven: the principle stays safe as domains multiply, and its cost is review-queue volume, which is measurable rather than hidden.

### 3.9 Classification fails closed, without a blacklist (D54), and the discipline is enforced (D55)

Probing the classifier with realistic BEC evasions (an obfuscated payment with no payment keyword, gift-card fraud, "our banking has changed", a pure-euphemism instruction) exposed a fail-open gap: the earlier catch-all typed any unrecognised communication as inert `informational_statement`, so an evasively-phrased request silently went inert and would skip Gjoll. Five of six probes downgraded that way.

The fix is fail-closed and whitelist-shaped, not a blacklist. Inert is now earned: `informational_statement` requires a positive informational signal (it reports, announces, describes) and no imperative. Any communication that does not earn it falls to `comms:unrecognised_request`, a FALLBACK tier below inert that routes to human review. So an unclassified request is treated as "not confirmed safe, so a human looks", not "assumed harmless". All five evasions now route to review; genuine informational controls (a status notification, a "please find attached" newsletter) still earn inert.

The rejected alternative is worth recording, because it is the tempting one: extend the high-risk rules with keywords for gift cards, bank-detail changes and verification codes. That was declined on principle. Enumerating malicious phrasings is a blacklist that fails open on the next phrasing, and it is the injectable-classifier mistake one layer over, the same error as the PoC's rejected n-gram output heuristic (invariant 3.5). The classifier's safety must not rest on a keyword list being complete. It rests on the fail-closed default and flow-to-sink gating. Pure euphemism that no keyword can name (D34 stays open) still routes to review, so the euphemism buys no silent inert typing. The cost is more review volume for ambiguous benign content, which fails safe.

That this happened at all is a warning: the blacklist trap was caught by human vigilance, which does not scale to the next session. So the discipline is now enforced structurally (D55). The harness carries a classification fail-closed property (obligation 8.2b): it generates novel, non-corpus request-shaped inputs that match no positive rule and asserts none classify inert. It passes now and, verified by simulating the pre-D54 eager catch-all, fails with 48 findings against a fail-open classifier, so it catches a regression that reopens the silent-downgrade path without a human needing to notice. Alongside it, `AGENTS.md` carries the rule (auto-loaded every session), `ONTOLOGY_CONSTRUCTION.md` 6.1 adds a rule-authoring checklist, and invariant 3.5 is extended to name the classification path. The guardrail is itself structural, not content-scanning: it checks where an unmatched request lands, never what it says.

---

## 4. Provenance discipline on the test corpus

The adversarial realism in the corpus (BEC with thread hijacking and VIP impersonation, fake invoice and wire requests, indirect prompt injection via email, web and screenshot) is informed by patterns in the maintainer's security-research corpus. Per D27 that material informed the TEST cases only; it never became classifier logic. Every expected label was set by a human, and no case is copied from a source; all are synthesised to exercise a labelled distinction. This keeps the classifier hand-authored while grounding the adversarial cases in real attack shapes.

---

## 5. The honest limits

- **Coverage is 93.9 percent on 33 cases across three domains.** That is a real number, not a large one, and it is a small corpus. It says the seed classifies these cases; it says nothing about the long tail. Coverage grows demand-driven (D26), and the fail-safe carries the rest.
- **Review volume is the accepted cost of failing safe.** Overlapping high-risk domains tie (D53), and the fail-closed inert gate (D54) sends unconfirmed requests to review. Both are safe (gated, no downgrade) but both add review-queue volume, and it will grow as domains multiply. That is the deliberate trade: the system errs toward a human looking rather than a silent inert typing. Tuning the boundaries to reduce volume without losing safety is demand-driven work.
- **This Nornir is substrate-neutral and per-batch.** It computes flow-to-sink reachability over one batch's flow graph, which is exact. The live system maintains the label incrementally in the store; the spike proved that is sound and cheap, but binding this to Memgraph and re-checking is still to do.
- **Extraction accuracy is out of scope** (invariant section 4), unchanged. The corpus tests typing and action-criticality, not whether the extracted values are correct.
- **The rules are keyword-based, and deliberately not a blacklist.** They are conservative and err safe. They cannot name pure euphemism, and they are not meant to: the fail-closed default (D54) catches what the keywords miss by routing it to review, not by growing the keyword list. Distinguishing an honest extraction error from an injection-induced one (D34) is still open and is where a richer classification-correctness corpus will bite.

---

## 6. What this advances

Invariant 3.11 moves from wholly untested toward demonstrated-on-a-seed: the deterministic classifier, the fail-safe path, reasoner soundness and agent-scoped cross-domain flow-to-sink all run and pass on a labelled corpus. Invariant 3.9's coverage bound is measurable, and grew from 88.2 to 93.9 percent as two more domains, a principled priority rule and a fail-closed inert gate were added, without regression. The attach test (D29) is demonstrated twice, at scheduling and finance, without editing the existing domains or the spine. The domain-governance decision (D31) and its cross-domain priority principle (D52) are settled and realised, and finance measured the principle's cost (D53). Most importantly, probing with realistic BEC evasions exposed a fail-open catch-all and it was closed the right way (D54): inert is earned, unconfirmed requests route to review, and the fix is whitelist-shaped, not a blacklist of malicious phrasings, keeping the classifier off the injectable path (invariant 3.5). That the trap was caught by human vigilance rather than a test was itself a gap, so the discipline is now enforced structurally (D55): a fail-closed property test that fails against an eager catch-all, a standing rule in the auto-loaded `AGENTS.md`, an authoring checklist, and a sharpened invariant 3.5. The residuals are the Memgraph binding (low-risk after the spike) and growing coverage beyond the seed.
