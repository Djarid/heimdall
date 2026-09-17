# Detailed Design: Gjöll (value integrity and action-time re-validation)

**Author:** Jason Huxley
**Date:** August 2026
**Version:** 0.1 (draft)
**Phase:** 3
**Status of the component today:** demonstrated. The gate shape and the action-critical determination are real in `ontology/nornir/gjoll.py` (151 lines); the promotion-requirement gate is now also built in Rust (D120 to D123, DEMONSTRATED under harness and test invocation only, never PROVEN, section 5.1); the sink-declaration schema and the other three re-validation gates (corroboration, re-derivation, semantic constraint) are unbuilt. Per `plans/hld.md` section 3.

---

## 1. Purpose

Gjöll answers a question provenance does not: is this value safe to act on right now. A value can be correctly typed, correctly provenanced and still be a poisoned value. Gjöll gates the action, not the assertion.

It exists because the taint boundary alone does not close value poisoning. Writing an action-critical value to the world model is, in effect, an execution capability: a legitimate, fully authorised, non-compromised agent will act on a poisoned value if that value reaches a consequential action. Gjöll is the layer that treats an action-critical write as the execution capability it is, and re-validates it at action time.

Gjöll's honest contribution is narrow and worth having: it converts a silent integrity failure into an explicit authorisation decision. It does not make value poisoning impossible. This is containment, not elimination, and this document preserves that framing throughout.

## 2. Responsibilities and boundaries

In scope for Gjöll:

- Determine whether a value is action-critical, by reading Mímisbrunnr's maintained flow-to-sink label.
- Gate a consequential action at authorisation time: block it if it consumes, as an action instruction, an untrusted-derived action-critical value that has not passed a gate.
- Provide the four re-validation gates (re-derivation, semantic constraint, promotion requirement, corroboration) an action-critical value may pass.
- Own the sink-declaration schema: which sinks are consequential and how each parameter is consumed.

Out of scope for Gjöll:

- Computing the flow-to-sink label. That is Mímisbrunnr's incremental maintenance (`mimisbrunnr.md` section 3); Gjöll reads it.
- Choosing the action wiring. Gjöll proves a given wiring safe or unsafe; it does not decide what an agent proposes. This is the boundary the proof-of-concept gate already held (`poc/sinks.py`).
- Inspecting the value's content. The gate inspects the wiring and the computed labels (consumption mode, provenance, action-critical status), never the parameter's content. A content inspection would be a heuristic detector, the thing the architecture avoids.

## 3. The action-critical gate

This is the proven core, real in `ontology/nornir/gjoll.py`. The rule, in one line: a consequential action is authorised only if no parameter it consumes as an action instruction is an untrusted-derived, action-critical value that has not passed the gate.

### 3.1 The three conditions

A parameter blocks the action only when all three hold (from `gjoll.py::evaluate`):

- consumed as an action (`CONSUME_ACTION`), not as inert data. Consuming the same value as inert data (logged, stored, displayed) is always fine; this is the proof-of-concept's describe-versus-obey distinction. A parameter consumed as `CONSUME_INERT` never blocks.
- untrusted-derived: the value's trust level is TAINTED (every marshalled assertion is TAINTED by origin). This is the proof-of-concept's provenance test.
- action-critical: the value can actually reach a consequential sink by some path, as read from Mímisbrunnr's flow-to-sink label. A value that is untrusted-derived but cannot reach any consequential sink for this agent is inert in effect, and gating it would be friction without safety.

The action-critical condition is what makes the gate sound against multi-step state staging: the value is caught at the staging write, because reachability already marked it action-critical the moment a path to a consequential sink existed, not only at the final consequential step. The per-step consequence rule the architecture replaced could not express this.

### 3.2 Interfaces

From the real code:

```
evaluate(proposal: ActionProposal, classified_by_id: dict, agent_consequential_sinks: frozenset) -> GateDecision
enforce(proposal, classified_by_id, agent_consequential_sinks, actuator) -> GateDecision
```

`evaluate` authorises or blocks and fails closed: a parameter consumed as an action with no known provenance is unknown-origin and blocks, because the gate cannot confirm it is safe to act on. `enforce` evaluates and, only if authorised, lets the effect run: a blocked action never reaches the actuator, exactly as the proof-of-concept gate blocked the payment actuator before any mock money moved. The `fired` flag stays false on a block.

`ActionProposal` carries the sink id, a `consumes` map (parameter id to `CONSUME_INERT` or `CONSUME_ACTION`) and a `declared_safe` flag recorded for reporting only. The gate does not trust `declared_safe`; it re-derives authorisation from the consumption mode, the provenance and the action-critical status.

## 4. The sink-declaration schema (the root)

This is the load-bearing gap and the reason this document leads two components in the pre-mortem. The gate's soundness rests on the sink and consumption declarations: which sinks are consequential (`agent_consequential_sinks`) and how each parameter is consumed (`consumes`). In the current code these are trusted input. `gjoll.py` states this limit in its own docstring: the per-sink consumption declaration is trusted input, and deriving it from real data flow is future work. `ADVERSARIAL_REVIEW.md` 5.1 names it the root: `ActionProposal.consumes` is an unchecked dict.

An attacker or an authoring error that mislabels a `CONSUME_ACTION` parameter as `CONSUME_INERT`, or omits a consequential sink from the declaration, defeats the gate without the gate detecting it. The gate is only as sound as the declaration it is handed.

### 4.1 What Phase 3 must build

- A signed sink-declaration schema. A sink declaration states the sink id, whether it is consequential and for each parameter how it is consumed. The declaration is an enforcement-bearing artifact and must be attested, not an unchecked dict handed in at call time. It is authored under policy (a trust root, like the canonical channel and the signing key) and validated at the gate boundary before the gate trusts it.
- Gate-boundary validation. Before `evaluate` trusts a `consumes` map, the boundary checks it against the signed declaration for that sink: an undeclared sink, or a consumption mode that disagrees with the declaration, fails closed. `ActionProposal.consumes` stops being an unchecked dict and becomes a claim checked against the attested declaration.
- The longer-term direction, named not built: deriving the consumption wiring from real data flow rather than declaration, so the trusted input shrinks. This is future work and is not a Phase-3 deliverable; Phase 3 closes the gap by attesting the declaration rather than by eliminating it.

This is HLD risk R-7. Until it is built, the flow-to-sink guarantee rests on an unchecked input, and the DD says so plainly rather than presenting the gate as sound end to end.

## 5. The four re-validation gates

Before Himinbjörg authorises a consequential action (proposal-validation check 5, `himinbjorg.md` section 5), every action-critical value it depends on must pass at least one gate. Each gate's honest strength, from `HEIMDALL.md` 745 to 762:

- Re-derivation. Re-extract the value from source at action time via a fresh Fenrir instance and require a match. Weak: it catches sampling noise and instance-state corruption, not a deterministic source-structured poison that a fresh instance reads the same way. A floor against accidents, not adversaries, and must not be relied on as the primary gate.
- Semantic constraint. The value must satisfy ontology axioms beyond its type (an address in an authorised scope set, an amount in a bounded range). It bounds the attacker's reachable set to what was already authorised, which bounds blast radius, but it verifies boundaries, not benignity: a valid, in-scope value pointing at a vulnerable in-scope target passes.
- Promotion requirement. An action-critical value must be TRUSTED, not merely present; a tainted action-critical value cannot drive a consequential action without human or cryptographic promotion. This is the strongest gate and the fallback for the others' failures. It is sound but shifts cost onto the human, which is why the action-critical set must stay small (section 7).
- Corroboration from independent provenance. The value must be attested by a source of a different provenance class, a genuinely independent origin, not a second reading of the same content. Sound where it exists, frequently unavailable, so it cannot be mandatory without paralysing the system.

The load-bearing gate is the promotion requirement. Re-derivation is near-worthless against a competent attacker, semantic constraint only bounds targeting, and independent provenance is often unavailable. Gjöll's containment is achieved by moving the decision to a human or a key for action-critical values, not by the automated gates defeating the attack.

### 5.1 Interface

```
gate(value_node: NodeId, action: Action, gate_policy: GatePolicy) -> GateResult
```

`GateResult` is `PASS(gate_name)` or `BLOCK(reason)`. `gate_policy` names which gate or gates apply to this action, chosen per capability (section 7). A value passing no gate does not fail silently: the action is blocked, the dependency is flagged, and the value is routed to human authorisation on the protected channel, not the bulk review queue (`gjallarhorn.md`).

`plans/synthesis-resolutions.md` (D107) records a ruling on how the promotion-requirement gate above relates to `promotion_policy.py`: it is implemented as a check against that module's existing trust-level output rather than a duplicate of its logic, while the other three gates above still need their own new mechanisms under this `GatePolicy`/`GateResult` interface, unchanged here.

**D107's ruling is AMENDED, not complied with (D121).** `ontology/nornir/promotion_policy.py`'s `evaluate_promotion` returns `promoted=True` on a single source whenever the slot is not consequential, so a value carrying no promotion evidence at all would pass on that function's exact semantics: a fail-open path, found independently by the 22 August Python spec's own REQ-39 and by the Rust build's own brainstorm. What is built instead, in Rust (`.opencode/plans/rust-promotion-gate-spec.md`), honours D107's underlying concern (no duplicate of `promotion_policy.py`'s corroboration-counting logic; the trust-level input D107 points at, `boundary_gjoll::types::TrustLevel`, genuinely exists) while replacing its delegated semantics: `crates/hierarchy-vor/src/promotion.rs` defines `PromotionRecord`, a second `AttestedRecord` type on the substrate the crate already owns, attesting the exact assertion id, a digest of that assertion's content, the trust level being promoted to (an opaque string, never ranked inside `hierarchy-vor`) and a validity window, verified through the crate's existing four-case fail-closed `verify_record` procedure into an opaque `VerifiedPromotion` witness (`load_verified_promotion`, its one public entry point, taking a caller-supplied instant, never reading a clock). `crates/boundary-gjoll/src/gate_policy.rs` supplies `GatePolicy` (a required-gate set read as a conjunction, an empty set BLOCKing) and `GateResult` as a closed enum naming the four `gjoll.md` section 5 gates by variant, never by string, so an unrecognised gate name is structurally unrepresentable rather than merely refused; its promotion-requirement evaluator PASSes only when all of: it is handed a `VerifiedPromotion`; that witness binds the exact assertion id under evaluation; that witness binds a digest matching the parameter's own content; and the witness's promoted-to level is at or above a named threshold by rank. The other three gates named in section 5 (corroboration, re-derivation, semantic constraint) stay specified and unimplemented: a `GatePolicy` naming any of them BLOCKs with a reason naming that gate unimplemented, visibly rather than silently. **The status word is DEMONSTRATED under harness and test invocation only, never PROVEN**: nothing can mint a `VerifiedPromotion` at runtime, because a promotion is per-value and per-instant and the live authoring path needs **two** things, not one. **Corrected, after the Gjallarhorn build (`crates/gjallarhorn/`, `.opencode/plans/gjallarhorn-build-spec.md`):** the first half, a human decision on Gjallarhorn's protected channel, is now BUILT; the second half, a promotion-authoring entry point inside `crates/hierarchy-vor/` that computes an attestation over a human-approved record rather than merely checking one, is NOT built, because `compute_record_attestation` and `TrustedAuthoriserSet::secret_for` are both `pub(crate)` under that crate's own REQ-13, and no `src/` module calls the former to issue rather than to check. The second half is the genuine remaining blocker, and it reopens REQ-13's secret boundary, a trust-boundary decision of a different kind from building an alerting layer. `ontology/tests/promotion_invocation_harness.py` reporting zero non-test call sites of the promotion-verification entry point or the gate-policy evaluator, live, after the Gjallarhorn build, is now evidence of the second half being open, not the first being unbuilt. `crates/boundary-gjoll/`'s `[dependencies]` table gains its first entry, a path dependency on `hierarchy-vor` (`plans/rust-workspace-baseline.md` section 4's fourth path-dependency ruling); the reverse direction is refused, and `hierarchy-vor`'s own manifest stays untouched. See `DECISIONS.md` D120 to D123 and D126 to D130.

## 6. Fail-closed behaviour

- A parameter consumed as an action with no known provenance blocks (unknown-origin, cannot confirm safe). Real in `gjoll.py::evaluate`.
- An action-critical untrusted-derived value consumed as an action, that passes no gate, blocks and routes to human authorisation.
- A `consumes` map that disagrees with the signed sink declaration, or names an undeclared sink, fails closed at the gate boundary (section 4.1).
- A blocked action never reaches the actuator; `enforce` lets the effect run only after authorisation. Proven in `gjoll.py`.
- The gate never inspects value content, so a content-level evasion has no gate surface to attack; it can only attack the declaration (section 4) or the action-critical set sizing (section 7).

## 7. The action-critical set sizing discipline

The size of the action-critical set determines whether Gjöll is secure, usable or neither (HLD section 8.4). Too large a set makes the gate fire constantly, the system fails closed on routine tasks, operators reclassify values to keep working and the control deletes itself. Too small a set lets poisoned values flow into consequential actions ungated.

The discipline, carried from `HEIMDALL.md` 812 to 814: the action-critical set starts empty for autonomous action and grows one capability at a time. Each time a specific autonomous consequential capability is granted, its `gate_policy` (section 5.1) is chosen to fit that action's provenance reality. If an action has no independent-provenance channel, its gate is the promotion requirement, accepted as the cost of that autonomy. The binding rule: never grant an autonomous consequential capability whose integrity you cannot gate. The flow-to-sink classification keeps the set small in the common case, because most flows terminate at read-only or human-gated terminals that are not sinks.

Phase 3's deliberate friction test (HLD section 11) introduces exactly one autonomous consequential capability, to encounter the gate's usability friction on purpose under controlled conditions and to validate the flow-to-sink classifier against a real state-staging attempt.

## 8. Data owned

- The signed sink-declaration schema (section 4), a policy-tier artifact.
- The gate policies (which gate or gates apply per capability).
- No world state and no flow-to-sink label; those are Mímisbrunnr's.

## 9. Dependencies

- Upstream: Himinbjörg (invokes the gate in proposal-validation check 5), Mímisbrunnr (the flow-to-sink label and the classified assertions), Fenrir (a re-derivation gate spins a fresh Fenrir instance).
- Downstream: the actuator (only on authorisation), Gjallarhorn (a block that routes to human authorisation), Hliðskjálf (every gate decision logged).

## 10. Build delta from today

- The action-critical gate (`evaluate`/`enforce`), the three-condition rule and the block-before-actuator behaviour are real and proven in `ontology/nornir/gjoll.py`, wired to the flow-to-sink action-critical determination (D58).
- The signed sink-declaration schema and gate-boundary validation are unbuilt. This is the root (section 4, HLD R-7) and Phase 3 must build it first, because every other Gjöll guarantee rests on it.
- Of the four re-validation gates, the promotion requirement is the load-bearing one and is now **built**, in Rust (D120 to D123, below); re-derivation, semantic constraint and corroboration stay specified and unimplemented, each chosen per capability rather than applied as a blanket policy when the capability set eventually grows to need them.
- The action-critical set sizing is a discipline, not code, but the per-capability `gate_policy` mechanism that enforces it is a Phase-3 build.
- The gate is now also re-expressed in Rust, at `crates/boundary-gjoll/` (D109, build-order step one of `plans/synthesis-bootstrap.md`, D108). A two-layer crate carries a pure, total rule core (the three-condition rule plus the D89-A inert-contradiction check) behind a registry-mandatory consequentiality shell (D81 validation, D89-B derivation). Correctness is checked against 22 golden vectors captured from the existing Python harnesses, with a source-digest drift detector folded into `ontology/tests/harness.py`'s fatal-gated suite. It designs out the Python no-registry branch, D97's named residual and D100's stamp-rewrite limit, since the shell requires a registry on every call; it defers D93's behavioural effect-probe cross-check, D103's `AgentContext` attestation, D94's sink-declaration attestation, the four re-validation gates and their `GatePolicy`/`GateResult` scaffold and a public actuator. It proves translation fidelity against the Python reference; it does not advance invariant 3.6's proof status, change the 22 RED findings or close the sink-declaration root seam (section 4). See `plans/rust-workspace-baseline.md` for the workspace conventions it establishes.
- **The promotion-requirement gate is built, in Rust, and the other three re-validation gates named in section 5 stay specified and unimplemented, deliberately (D120 to D123, `.opencode/plans/rust-promotion-gate-spec.md`).** `crates/boundary-gjoll/src/gate_policy.rs` supplies `GatePolicy`/`GateResult`; `crates/hierarchy-vor/src/promotion.rs` supplies `PromotionRecord`, verified into an opaque `VerifiedPromotion` witness through the crate's existing substrate; a precondition fix (`types.rs`'s `rank()` and `TRUSTED_THRESHOLD`, both arms of `rule.rs`) replaces equality-against-`Tainted` with a rank comparison, so `Vouched` is correctly untrusted-derived. Section 5.1 above carries the full account of what is built, what D107's ruling is amended to (D121), and the status word: **DEMONSTRATED under harness and test invocation only, never PROVEN**, because nothing can mint a `VerifiedPromotion` at runtime while Gjallarhorn, the intended live authoring path, is unbuilt. Corroboration, re-derivation and semantic constraint each BLOCK visibly if named in a `GatePolicy`, rather than being silently absent: the narrowing is a design choice (OR-3, the brainstorm's own open item seven), not an oversight, since building the corroboration gate would need a Rust re-expression of `promotion_policy.py`'s counting kernel, a genuinely separate build. This does not advance invariant 3.6 beyond the narrow sense the existing Rust build-order steps already established (checks 33 to 39 of `DECISIONS.md` section 6, and check 41): a pass path now exists, reachable from a test only, and Gjöll's own Python gate functions in `ontology/nornir/gjoll.py` still have zero non-test callers, unaffected. It does not close the sink-declaration root seam of section 4, does not compute flow-to-sink transitive reachability, and arms nothing: R-1 (D73) is not engaged. See `plans/rust-workspace-baseline.md` section 4 for this build's own fourth path-dependency ruling.

## 11. Test plan

Inherits the proven gate suite (`ontology/nornir/gjoll.py` tests): a safe wiring passes, an unsafe control wiring is blocked before the actuator fires, the describe-versus-obey distinction holds (inert consumption of the same value passes), and multi-step state staging is caught at the staging write because the value is already action-critical. This is the demonstrated baseline (invariant 3.6, D58).

Adds, before implementation:

- Sink-declaration attestation: a `consumes` map that disagrees with the signed declaration for its sink fails closed; an undeclared sink fails closed; a `declared_safe: true` flag does not authorise anything the re-derived checks would block (the gate does not trust `declared_safe`).
- The promotion-requirement gate: an action-critical TAINTED value blocks; the same value after human or cryptographic promotion to TRUSTED passes within its scope.
- Semantic-constraint gate: an in-range value passes, an out-of-range value blocks, and the honest limit is tested (an in-scope value pointing at an in-scope target passes, demonstrating the gate bounds targeting not benignity).
- Re-derivation gate: a value that re-extracts identically passes; a value that does not match blocks; the honest limit is documented in the test (a deterministic source-structured poison re-derives identically and passes, so re-derivation is not relied on alone).
- Fail-closed: an action-critical value passing no gate blocks and routes to human authorisation on the protected channel.
- The value-poisoning residual is named in the test plan as not closed: a source-level corruption that survives re-derivation and satisfies semantic bounds, on a value gated only by those two, remains possible. The containment is the promotion requirement, and the discipline is to gate high-blast capabilities with it.

Coverage is reported line and branch, with the fail-closed and unknown-provenance branches covered explicitly.

## 12. Decisions (index)

| # | Decision | Chosen | Rejected | Rationale |
|---|---|---|---|---|
| GJ-1 | What the gate inspects | The wiring and the computed labels (consumption mode, provenance, action-critical status), never the value content | A content-level poison detector | A content detector is the heuristic the architecture avoids. The gate proves a wiring safe or unsafe, as the proof-of-concept gate did. |
| GJ-2 | Sink and consumption declaration | A signed, attested schema validated at the gate boundary | The current unchecked `consumes` dict | It is the root (`ADVERSARIAL_REVIEW.md` 5.1, HLD R-7): the gate is only as sound as the declaration. Phase 3 must attest it before the gate can be trusted end to end. |
| GJ-3 | The load-bearing gate | The promotion requirement (human or cryptographic) | Re-derivation or semantic constraint as primary | Re-derivation is near-worthless against a competent attacker and semantic constraint only bounds targeting. The containment is moving the decision to a human or a key. |
| GJ-4 | Gate selection | Per-capability `gate_policy`, chosen to fit each action's provenance reality | A blanket gate policy for all consequential actions | The action-critical set sizing discipline (section 7): a blanket policy either paralyses the system or under-gates. Each capability's gate fits its provenance. |
| GJ-5 | Honesty framing | State plainly that this is containment not elimination, and that the automated gates do not defeat the attack | Present the gate as sound end to end | Overselling a gate is worse than a weak gate honestly labelled. The value-poisoning limitation is the frontier of the reading path (HLD section 8.5), named not concealed. |
| GJ-6 | The Rust re-expression's public gate API | Registry-mandatory: the registry parameter is not optional, and no code path reaches a verdict without one | A registry-optional dual-mode gate, mirroring the Python no-registry branch | D105's argument for Rust is that a compiled boundary makes the guard unreachable and its holes structurally absent. Carrying a registry-optional path into it would make D97's named residual a property of that artefact, for backward compatibility with Python callers that do not exist in Rust: D97 itself declined to require a registry only because this repository already had callers, and Rust has none. |

---

## Licence

Part of the Heimdall specification, licensed under CC-BY-SA-4.0. See `LICENSE.md`.
