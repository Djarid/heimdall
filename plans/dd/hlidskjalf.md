# Detailed Design: Hliðskjálf (tamper-evident audit log)

**Author:** Jason Huxley
**Date:** August 2026
**Version:** 0.1 (draft)
**Phase:** 2
**Status of the component today:** demonstrated in spirit only, per `plans/hld.md` section 3. The existing harnesses treat failures as loud audit artefacts (invariant 3.10 is proven as a harness property), but no signed append-only log service exists.

---

## 1. Purpose

Hliðskjálf is the tamper-evident append-only log of every decision Heimdall makes: every proposal, promotion, denial, escalation and system event. Named for Odin's high seat, from which everything is seen, it is the record that lets a breach be reconstructed after the fact and the anchor that lets a bad state be unwound. It makes the architecture's third register of defence real: when prevention and detection have both been assumed to fail against a targeted adversary, Hliðskjálf is what makes the breach loud, attributable and reconstructable (`HEIMDALL.md` Design Principle 3, the detection-and-reconstruction stance).

Its two jobs are narrow. First, record each decision as a signed entry chained to the one before it, so any later tampering with the record is detectable. Second, anchor the causal graph in Mímisbrunnr (document 3), so a rollback follows signed entries and unwinds only what a given action actually touched.

This document takes Hliðskjálf to implementation fidelity for Phase 2: the entry schema at signature level, the `append` and `verify_chain` interfaces, the chaining mechanism, the binding of an entry to a Mímisbrunnr state and the causal-unwind anchoring. It is honest throughout about the one thing Hliðskjálf assumes rather than provides: the integrity of the signing key. That key is a **trust root** (`HEIMDALL.md` threat model, HLD section 8.2), not a product of this component, and this document does not pretend otherwise.

## 2. Responsibilities and boundaries

In scope for Hliðskjálf:

- Append a signed entry for every decision, promotion, denial, escalation and proposal handed to it, and for system events.
- Chain each entry to its predecessor so that altering any earlier entry breaks verification of every entry after it.
- Bind each entry to a Mímisbrunnr state through the `world_model_state_hash` field, so an entry names the world the decision was made against.
- Verify the chain on demand and report an integrity failure as a Gjallarhorn event (an audit-integrity failure), never as a silent boolean a caller may ignore.
- Serve as the anchor set for causal unwind and for forensic reconstruction: the signed entries are the fixed points the causal graph is replayed against.

Out of scope for Hliðskjálf:

- **It is not the world model.** Hliðskjálf records that a decision was made and against which world state; Mímisbrunnr (document 3) holds the world state itself. The `world_model_state_hash` is a reference into Mímisbrunnr, not a copy of it. An entry is a decision record, not a state store.
- **It does not secure the signing key.** The signature chain is only as sound as the key that signs it. Key generation, storage, rotation and access control are trust roots carried by non-Heimdall controls (an HSM, host isolation, the key store on a segment isolated from the ingestion surface, per HLD section 10). Heimdall protects everything downstream of the key. It offers nothing about the key itself, and this boundary is stated plainly so the audit trail's guarantee is not overclaimed. If an attacker holds the signing key they can forge a consistent chain, and no property of this component detects that. The threat model (HLD section 8.2) assumes the attacker cannot, and that assumption, not any Hliðskjálf mechanism, is what the guarantee rests on.
- It does not make trust or promotion decisions. Those are made in Himinbjörg and the promotion pipeline; Hliðskjálf only records them.
- It does not route alerts. It raises a Gjallarhorn event on a verification failure; Gjallarhorn (document 9) owns the routing.

## 3. The core contracts

### 3.1 The entry schema (signature level)

Every entry has the shape fixed by `HEIMDALL.md` (the Hliðskjálf section). Reproduced here because it is the contract this document builds on, not restated in prose:

```
entry_id: uuid
timestamp: timestamp
type: DECISION | PROMOTION | DENIAL | ESCALATION | PROPOSAL | SYSTEM
agent_id: string | system
action: typed_action
himinbjörg_decision: typed_decision
constraint_checks: [check_result_list]
world_model_state_hash: string
signature: string
```

Field notes at the level this document owns:

- `entry_id` is a UUID assigned at append time. It is the identity a causal-graph anchor and a forensic query refer to.
- `type` is the closed enumeration above. A caller cannot invent a type. `SYSTEM` covers events not tied to a single agent decision (startup, key rotation acknowledgement, a verification run's own record).
- `agent_id` is the acting agent, or the literal `system` for a `SYSTEM` entry. It is never absent.
- `action` and `himinbjörg_decision` are the typed proposal and the typed decision, carried verbatim from Himinbjörg (document 7). Hliðskjálf does not reinterpret them.
- `constraint_checks` is the list of check results Himinbjörg's six-step validation produced, so the record shows not only the verdict but the checks that reached it.
- `world_model_state_hash` binds the entry to a Mímisbrunnr state (section 3.4).
- `signature` is the chained signature (section 3.3). It is the last field computed and the field the whole tamper-evidence property rests on.

The schema is fixed by `HEIMDALL.md`; this document adds only the interface and mechanism around it, and does not alter a field.

### 3.2 The append and verify interfaces (signature level)

The two interfaces from HLD section 5.8, at signature level:

```
append(entry: AuditEntry) -> EntryId
verify_chain() -> bool
```

- `append` takes a populated entry (all fields except `signature`, which it computes), signs it over its own content plus the previous entry's signature (section 3.3), persists it and returns the assigned `EntryId`. Append is the only write path. There is no update and no delete interface, by construction: the log is append-only, and the absence of any mutating interface is the structural form of that property, not a policy applied on top of a mutable store.
- `verify_chain` walks the log from the genesis entry forward, recomputing each entry's signature over its content and its predecessor's signature and comparing against the stored signature. It returns `true` only if every entry verifies in order. A `false` result is never returned silently to a caller who might ignore it: `verify_chain` raises a Gjallarhorn audit-integrity event on any mismatch before it returns (section 5), so a broken chain cannot pass unnoticed.

`verify_chain` may be called over the full log or a bounded suffix (for a periodic check that does not re-walk history every time); the suffix form still chains back to a known-good checkpoint, so it verifies a segment against an anchor rather than in isolation.

### 3.3 The chaining mechanism

Each entry's signature is computed over the entry's own content **and the previous entry's signature**:

```
signature[n] = sign(key, content(entry[n]) || signature[n-1])
```

where `content(entry[n])` is the deterministic serialisation of every entry field except `signature` itself, and `||` is a domain-separated concatenation. The genesis entry (the first in the log) chains over a fixed, published genesis constant in place of a predecessor signature, so even the first entry has a defined chaining input and the walk has a fixed starting point.

This is what makes tampering detectable. Altering the content of any entry `k` changes `content(entry[k])`, so `signature[k]` recomputed at verification no longer matches the stored value, and because `signature[k]` feeds `signature[k+1]`, every entry after `k` also fails to verify. An attacker who edits one historical entry must re-sign that entry and every entry after it, which requires the signing key. Without the key the edit is detected at the next `verify_chain`; the tamper-evidence property is exactly this and no more. It detects alteration of the stored record; it does not prevent it, and it does not detect forgery by a holder of the key (section 2).

The serialisation is deterministic (fixed field order, canonical encoding), so a verifier recomputes byte-identical content to what was signed. A non-deterministic serialisation would make an honest chain fail to verify, which on a fail-closed component is an availability failure and is treated as a defect.

### 3.4 Binding an entry to a Mímisbrunnr state

The `world_model_state_hash` binds an entry to the world model state the decision was made against. It is a hash of the relevant Mímisbrunnr state at decision time, computed by Mímisbrunnr and carried into the entry, so the record answers not only what was decided but what the world looked like when it was decided. This binding is what lets forensic reconstruction line a decision up against the state that produced it, and it is what lets a rollback know which state an entry corresponds to.

The hash is a reference, not a copy: the entry names a state, Mímisbrunnr holds it. If the referenced state is later mutated, the hash no longer matches, which is itself evidence that the world moved on from what the decision saw. Hliðskjálf does not police Mímisbrunnr's mutation; it records the reference and leaves state ownership where it belongs (section 2, the not-the-world-model boundary).

### 3.5 Causal-unwind anchoring

Rollback in Heimdall is a structural operation over the causal graph in Mímisbrunnr (document 3, `causal_unwind`), and Hliðskjálf entries are its anchors. The causal graph records that an agent performed an action that produced a state change, with preconditions and postconditions; the signed Hliðskjálf entry for that decision is the fixed, tamper-evident point the unwind is keyed to. A rollback follows the causal edges from a named anchor entry and reverses the state changes that entry's action produced, and only those.

The anchoring matters because it makes rollback trustworthy exactly as far as the chain is trustworthy. An unwind driven from a tampered or forged anchor would reverse the wrong state, so the same trust-root caveat applies: causal unwind is sound downstream of the signing key and assumes the key's integrity, it does not establish it. Hliðskjálf provides the anchors and the ordering; Mímisbrunnr owns the graph and performs the reversal (the split is stated from Mímisbrunnr's side in document 3 section 3.6).

## 4. Where Hliðskjálf sits in the pipeline

Hliðskjálf is lateral to the one-way ingestion flow, not on it. It does not parse, classify or store world state; it records the decisions the other components make and reads back the causal anchors for rollback and forensics. Every decision-making component writes to it, and two downstream consumers read from it: causal unwind (through Mímisbrunnr) and forensic reconstruction. A verification failure turns Hliðskjálf from a passive recorder into an active alarm, routed through Gjallarhorn (section 5). This position, off the ingestion path but binding every decision, is why the tainted-content boundary never reaches it: Hliðskjálf receives typed decision records from trusted-side components, never raw external content, and there is no path by which a payload from Bifröst becomes an audit entry the attacker controls (the cross-cutting canonical-channel contract, `index.md` section 4.4).

## 5. Fail-closed behaviour

- **A verification failure is a Gjallarhorn event.** A `verify_chain` mismatch is an audit-integrity failure, the most consequential kind, because it means the record itself can no longer be trusted. `verify_chain` raises a Gjallarhorn event before returning, so an integrity failure is loud, aggregated and routed, never a boolean a caller may quietly discard. The event type is distinct from an operational alert: an audit-integrity failure names a compromise of the record, and Gjallarhorn treats it as high priority (document 9).
- **A decision that cannot be logged blocks.** If `append` fails (the store is unreachable, signing fails, serialisation raises), the decision it was recording does not proceed. The action blocks rather than executing unlogged, so there is no path by which a consequential action happens without a durable signed record of it. This is the load-bearing fail-closed property of the component: the audit trail cannot be silently bypassed by making logging fail, because a failed log is a blocked action, not an unrecorded one. An unlogged decision is treated as no decision.
- **Append is the only write path.** There is no update or delete interface (section 3.2), so there is no in-band operation that can rewrite history. Rewriting the stored bytes out of band is exactly what the chain detects.
- **A missing or malformed field fails the append.** An entry with an absent `agent_id`, an out-of-enumeration `type` or an absent `world_model_state_hash` is rejected at `append`, not stored partial. A partial record is a record that cannot be reconstructed against, so it fails closed to a block.

The one failure this component cannot fail closed against is signing-key compromise: a holder of the key can produce a chain that verifies. That is the trust-root boundary (section 2), stated here so the fail-closed claim is not read as covering it. Heimdall's fail-closed guarantees hold downstream of the key; the key's integrity is a prerequisite.

## 6. Data owned

- **The append-only signed log.** The ordered sequence of signed entries, the genesis entry and the chaining state (the last signature, so the next append chains correctly). This is the whole of what Hliðskjálf owns.
- **Not world state.** Mímisbrunnr owns the world model and the causal graph; the log holds references (`world_model_state_hash`, the causal anchors), not the state itself (section 2).
- **Not the signing key.** The key lives in the key store, a trust root on a segment isolated from the ingestion surface (HLD section 10), outside Hliðskjálf's ownership. Hliðskjálf uses the key to sign; it does not store, rotate or guard it.

## 7. Dependencies

- Upstream (writers): Himinbjörg (every proposal, decision, denial and escalation) and every other decision-making component that produces a loggable event, including the promotion pipeline (every promotion, HLD section 7.3), Bifröst (original content on a pattern flag, document 2), Nornir (constraint violations) and Odin (proposals with rationale). Every component that decides writes an entry.
- Downstream (readers): causal unwind through Mímisbrunnr (document 3, which reads the signed anchors), forensic reconstruction (which reads entries against the `world_model_state_hash` bindings) and Gjallarhorn (document 9), which receives the audit-integrity event on a verification failure.
- Trust-root dependency: the key store and the signing key, carried by non-Heimdall controls (an HSM or equivalent). This is a dependency Hliðskjálf assumes sound and does not verify (section 2, section 8).

## 8. Build delta from today

- **Demonstrated in spirit only.** The existing harnesses already treat failures as loud audit artefacts, and invariant 3.10 is proven as a harness property (`plans/hld.md` section 3, `NEUROSYMBOLIC_FILTER_INVARIANTS.md` invariant 3.10): the live validation harness records, per decision, the input, the assertions checked and the result, in a form suited to an append-only log. That is the shape of an audit record, not the service.
- **No signed append-only log service exists.** The signed, chained, tamper-evident store with the `append` and `verify_chain` interfaces is the Phase-2 build. The entry schema is specified (`HEIMDALL.md`); the chaining mechanism, the deterministic serialisation, the persistence and the Gjallarhorn wiring on a verification failure are all new.
- **The causal-graph anchoring depends on Mímisbrunnr's causal graph (document 3), which is itself a Phase-2 build.** Hliðskjálf's anchoring interface is built against Mímisbrunnr's `causal_unwind`; the two are Phase-2 siblings and are built together.
- **Signing-key management is out of scope, by design.** It is a trust root (HLD section 8.2, section 10), carried by non-Heimdall controls such as an HSM, host isolation and a key store on a segment isolated from ingestion. Phase 2 builds the log service that uses the key; it does not build the key custody, and this document does not claim it. The honest boundary is that Heimdall's audit guarantee is real downstream of a sound key and vacuous without one.

## 9. Test plan

Inherits the harness-as-audit-artefact baseline (invariant 3.10): the existing per-decision recording shape is the starting point for the entry contents.

Adds, before implementation:

- **Append and verify (happy path):** append a sequence of well-formed entries of each `type`, assert each returns an `EntryId`, and assert `verify_chain` returns `true` over the full log and over a bounded suffix chained to a checkpoint.
- **Tamper detection (the security property, tested by its failure mode):** mutate the content of one historical entry in the stored log directly, then assert `verify_chain` returns `false` and raises a Gjallarhorn audit-integrity event, and assert that the mismatch is reported at the mutated entry and at every entry after it (the chaining property). Repeat for a mutated `signature` field and for a reordered pair of entries.
- **A decision that fails to log blocks:** simulate an `append` failure (store unreachable, signing raises) and assert the decision does not proceed, that the action blocks rather than executing unlogged, and that no partial entry is persisted. This is the load-bearing fail-closed test.
- **Chain verification across a rebuild:** persist a log, tear down and rebuild the service from the stored log and assert `verify_chain` still returns `true`, so verification is a property of the stored chain and the genesis constant, not of live process state. Then mutate an entry in the persisted store, rebuild, and assert verification fails, so a rebuild does not launder a tampered log clean.
- **Malformed-entry rejection:** append an entry with an absent `agent_id`, an out-of-enumeration `type` and an absent `world_model_state_hash` in turn, and assert each is rejected at `append` and nothing partial is stored.
- **State binding:** append an entry with a `world_model_state_hash` for a known Mímisbrunnr state, then mutate that state and assert the recorded hash no longer matches the current state, so the binding surfaces that the world moved on (a reconstruction signal, not a Hliðskjálf failure).
- **Determinism of serialisation:** serialise the same entry twice and assert byte-identical output, so an honest chain verifies and a non-deterministic serialisation (which would make an honest chain fail) is caught as a defect.

The signing-key trust root is explicitly not tested as a Heimdall property: no test asserts detection of a key-holder forgery, because the architecture does not claim it (section 2). A test suite that appeared to prove key-forgery detection would be asserting a guarantee Heimdall does not make, and is itself a defect.

Coverage is reported line and branch; the fail-closed branches (append-fails-to-block, verify-fails-to-Gjallarhorn, malformed-rejection) are covered explicitly, since on an audit component the failure paths are the point (`index.md` section 5).

## 10. Decisions (index)

| # | Decision | Chosen | Rejected | Rationale |
|---|---|---|---|---|
| HK-1 | Tamper-evidence mechanism | A signature chain: each entry signs over its content plus the previous entry's signature | Per-entry signature with no chaining; a Merkle tree | Chaining makes altering any one entry break every entry after it, so a tamper is detectable with a forward walk and no external witness. It is the mechanism `HEIMDALL.md` specifies; a Merkle tree adds proof-of-inclusion the architecture does not need at Phase 2. |
| HK-2 | Mutability surface | Append-only: `append` is the sole write path, no update or delete interface exists | A mutable store with an append-only policy enforced in code | Absence of a mutating interface is the structural form of append-only. A policy on top of a mutable store is a rule that can be bypassed; a missing interface cannot be called. |
| HK-3 | Verification-failure handling | `verify_chain` raises a Gjallarhorn audit-integrity event before returning | Return a bare boolean the caller may ignore | An audit-integrity failure means the record cannot be trusted, the highest-consequence failure this component has. A silent boolean lets a broken chain pass unnoticed, which is the exact bypass the component exists to prevent. |
| HK-4 | Failed-log behaviour | A decision that cannot be logged blocks; the action does not proceed unlogged | Log best-effort and proceed on a logging failure | Proceeding unlogged is a silent audit bypass: an attacker who makes logging fail would get an unrecorded consequential action. Blocking makes the audit trail impossible to bypass by breaking the logger. |
| HK-5 | Signing-key custody | Out of scope; a trust root carried by non-Heimdall controls (HSM, isolated key store) | Manage key generation, storage and rotation inside Hliðskjálf | The threat model (HLD section 8.2) names key integrity as a prerequisite the architecture assumes, not a product. Heimdall protects downstream of the key; building key custody inside the component would overclaim a guarantee it cannot make and would put the key on the ingestion-adjacent surface it must be isolated from. |

---

## Licence

Part of the Heimdall specification, licensed under CC-BY-SA-4.0. See `LICENSE.md`.
