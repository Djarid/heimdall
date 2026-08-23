# Heimdall synthesis: resolutions

**Author:** Jason Huxley (recorded by AETOS orchestrator session)
**Date:** August 2026
**Version:** 1.0
**Status:** Resolves all open items carried forward by `plans/synthesis-architecture.md` (D106) section seven, and the items D105 first named. Not yet a Detailed Design document.

## 1. Purpose

`plans/synthesis-capability-matrix.md` (D105) and `plans/synthesis-architecture.md` (D106) each carried forward a set of open items rather than settling them, deliberately. This document works through every one of them in turn, grounding each in the relevant Heimdall Detailed Design document, Gleipnir specification, or AETOS component before ruling, and records the ruling and its rationale. Seven items are resolved. One further item, Gleipnir's own named engineering seams, is confirmed to need no ruling at all, because it was never a Heimdall obligation in the first place.

## 2. Resolution one: Fenrir and Gleipnir's execution sandbox stay separate mechanisms

Fenrir isolates the reading of untrusted content by a model with a deliberately empty capability set: no tools, no shell, no filesystem, no Model Context Protocol access. Its own design point, quoted from `plans/dd/fenrir.md`, is that reading is not acting, and its isolation rests on a network segment with a two-peer allowlist plus that empty capability set, never on a container runtime. Gleipnir's S-2 sandbox exists for the opposite case: letting a build, test or lint command execute safely, using container-runtime detection, a network-none policy, a read-only mount and a digest-pinned image. `plans/dd/fenrir.md` never mentions Gleipnir, containers or code execution at all, and gives no basis for merging the two.

**Ruling.** The two mechanisms stay separate. Fenrir remains exactly as specified. Gleipnir's S-2 pattern is generalised and re-expressed in Rust as part of Himinbjörg's existing `broker_action` interface, for the case where a cohort instance's already-authorised action legitimately requires executing an external tool or command, such as a reconnaissance tool run by an ARGUS-shaped cohort. Both mechanisms ship in the production runtime, solving different problems, and the generalised sandbox sits inside Himinbjörg's boundary, gated by the same `validate_proposal` pipeline as any other proposal.

## 3. Resolution two: Gjöll's re-validation gates, per gate, not as a block

`plans/dd/gjoll.md` specifies four re-validation gates, re-derivation, semantic constraint, the promotion requirement and corroboration from independent provenance, under an unbuilt `gate(value_node, action, gate_policy) -> GateResult` interface. `ontology/nornir/promotion_policy.py` already exists and already decides, once and upstream, whether a fact is corroborated by enough distinct provenance sources to be promoted into trusted world-model state. The two operate on different objects at different points in the pipeline: promotion decides once whether a slot value ever becomes trusted; Gjöll's gate decides, per action, whether a specific already-marshalled value may drive that action right now. `promotion_policy.py` cannot be called directly from within Gjöll's gate, because its inputs, a set of `SourcedValue` candidates for one world-model slot, do not match what the gate has available, a `value_node` and an `Action`.

One gate is the exception. The promotion requirement, named in `gjoll.md` as the load-bearing gate, is naturally the question of whether a value has already crossed the promotion boundary `promotion_policy.py` guards. That gate can check the value's existing trust level, the recorded output of a prior `evaluate_promotion` call, rather than re-deriving anything. `gjoll.md`'s own separately named corroboration gate uses the same word but answers a different question, whether an action-time value is attested by an independent-provenance source right now, and cannot be built by calling `evaluate_promotion`, whose inputs are gathered at promotion time, not action time.

**Ruling.** The promotion-requirement gate is implemented as a trust-level check against `promotion_policy.py`'s existing decision, consuming its output rather than duplicating its logic. Re-derivation, semantic constraint and the corroboration gate each get new, purpose-built mechanisms under the `GatePolicy` and `GateResult` scaffold, which does not exist today and must be built regardless. This is a decision for whoever builds Himinbjörg to implement; it is not itself a Himinbjörg design choice this document pre-empts, because it concerns Gjöll's own internal gate mechanism, which `gjoll.md` already states is inside Gjöll's boundary.

## 4. Resolution three: the hierarchy plane's policy tier is load-time-attested, not compiled in

`plans/synthesis-architecture.md` section four named a new trust-tier lattice, policy, user-reviewed, retrieved and temporary, modelled on Gleipnir's G-6 requirement, to protect the agent registry, the cohort catalogue and the resident coordinator's own configuration. Left open was how the policy tier is actually enforced. Compiling the registry and catalogue directly into the binary would be the strictest possible reading of agent-unwritable, but it would mean every new predefined agent or cohort, including every one contributed by a sibling project such as HADES, ARGUS or RECALL, requires a full rebuild and redeployment of the Heimdall artefact.

D103, built earlier in this repository's own history, already established a working alternative: `AgentContext` attestation, a keyed digest verified before use, with an altered, unattested or unknown-authoriser context refused outright rather than degraded. This pattern already carries the two properties the policy tier needs, unforgeable and reviewed, without requiring a rebuild for every change.

**Ruling.** The policy tier is enforced as an external, keyed-digest-attested manifest, holding the agent registry and the cohort catalogue, verified at Heimdall instance startup, extending D103's existing pattern rather than inventing a new one. An altered, unattested or unknown-authoriser manifest is refused, exactly as D103 already refuses an altered `AgentContext`. A new predefined cohort ships as an attested manifest update, not a rebuild.

## 5. Resolution four: context shielding is adopted, narrowly, as a deterministic pre-filter for Fenrir

AETOS's `aetos-sandbox` container auto-indexes large command or fetch output into a local search store using SQLite FTS5 and BM25 ranking, and returns a compact summary or snippet instead of the raw text. This is a deterministic, non-neural mechanism, not a model call, which matters here specifically: adopting it introduces no new path that a model adjudicates, and so does not weaken the neurosymbolic filter's own invariant that no model sits on the classification path.

**Ruling.** The technique is adopted narrowly. A deterministic pre-filter, built on the same shape, sits between Bifröst and Himinbjörg's construction of Fenrir's canary wrap, reducing the size of the content window Fenrir must read per invocation without replacing or weakening any of Fenrir's own protections, the canary, the empty capability set or the egress restriction. It is not adopted as a general context-management utility elsewhere in the system; that broader use is a distinct, unruled-on question, kept separate so this narrower, clearly justified use is not entangled with a separate cost or performance argument.

## 6. Resolution five: notify closes a real, previously unspecified gap

`plans/dd/gjallarhorn.md` was read in full to check whether Heimdall's own alert and escalation layer already covers what AETOS's notify capability would provide. It does not. Gjallarhorn's own specification stops at admitting an escalation onto an internal protected-channel data structure, and names delivery to the operator as a downstream dependency without ever defining it. No document in `plans/dd/` or `HEIMDALL.md` names a concrete transport, Slack, electronic mail, or otherwise, by which a human operator actually receives an escalation. This is an unaddressed gap in Heimdall's own existing design, not a deferred item with a name already attached to it.

**Ruling.** AETOS's notify pattern, dynamic contact resolution and multi-channel dispatch, is adopted and re-expressed natively in Rust as the concrete delivery-to-the-operator mechanism that Gjallarhorn's protected channel feeds into. This closes a real gap named by Gjallarhorn's own specification, and does not compete with or duplicate anything Gjallarhorn already does, since Gjallarhorn continues to own routing, aggregation and prioritisation, and this component owns only the final, outward transport.

## 7. Resolution six: coordinator memory is shaped like Gleipnir's concept graph, not AETOS's SQLite store

Neither of Heimdall's existing memory-shaped components serves the resident coordinator's need for continuity across goals. Mímisbrunnr holds world knowledge, taint-classified, and Hliðskjálf is a write-once, append-only decision log, not built to answer a question like which goals are currently open. AETOS's own memory capability, persistent facts, tasks and session logs in a searchable store, is the closest existing analogue, but Gleipnir, deriving from and amending AETOS, has already moved past that model for the same underlying need: Gleipnir's T-1 requirement specifies an OKF-style concept graph, one markdown file per concept with markdown-link relationships and an index file as the traversal entry point, governed by the same G-6 trust-tier requirement this document already adopted in resolution three, and states plainly that absorbing the SQLite-backed read and search surface it inherited from AETOS is a migration to be completed, not a model to keep.

**Ruling.** The resident coordinator's own durable memory is built on Gleipnir's newer concept-graph shape rather than a port of AETOS's SQLite model, and its writes are governed by the same hierarchy-plane trust-tier lattice adopted in resolution three, rather than by a fourth, separately invented protection mechanism.

## 8. Resolution seven: the absorption seam needs no new mechanism

`plans/synthesis-architecture.md` named an absorption seam, a way for a future AETOS or Gleipnir capability to enter Heimdall as a new catalogue entry, a new output-plane check, or a new process-plane transition, without a rewrite of the substrate. Reviewing the six resolutions above together shows a pattern that was not planned in advance but held in every one of them: every accepted capability was re-expressed natively in Rust rather than ported or wrapped, was placed inside an existing gate rather than beside it, Himinbjörg's proposal validation, Gjöll's gate, the hierarchy-plane trust lattice, and carried an explicit, narrow statement of the specific gap it closed rather than being adopted because it was available.

**Ruling.** The absorption seam is not a new mechanism. A new capability enters through the same load-time-attested, human-reviewed policy-tier pipeline that resolution three already established for any other change to the agent registry or the cohort catalogue. No dedicated review process is built to sit above or alongside it.

## 9. Resolution eight: the master-control tier stays deferred, without a preparatory hook

No sibling project offers a pattern to borrow here: both AETOS and Gleipnir are single-orchestrator designs, with nothing resembling multiple independent instances under one delegating authority. Nothing has emerged since D105 first named this tier as a later phase that would change that assessment.

**Ruling.** The master-control tier remains deferred exactly as D105 and D106 already left it. No preparatory hook, such as giving every Heimdall instance a stable attested identity ahead of any component that would consume it, is built now. A single instance with its resident coordinator remains the first buildable target, and this question is revisited only when multi-instance work actually begins.

## 10. Not a resolution: Gleipnir's own open engineering seams

Gleipnir's specification names five open engineering seams of its own, a gap in the credential broker's argument policy, no persistent home for a platform-webhook receiver, a signal-quality gap in the event bus's correction provenance, a build-order disagreement between two of its own verification sub-requirements, and unbuilt bindings from its adopted GOTCHA and ATLAS methodology amendments. None of these were ever inherited as a Heimdall obligation, and this document confirms that status rather than ruling on any of them. They are named here only so that a future session re-grounding this synthesis in Gleipnir's own evolving specification does not have to rediscover that they exist, and does not mistake their presence in Gleipnir's own register for an open question this repository owes an answer to.

## 11. Summary table

| Item | Ruling |
|---|---|
| Sandbox unification | Stay separate; Gleipnir's S-2 pattern generalised into Himinbjörg's `broker_action` |
| Gjöll's gate policy | Promotion-requirement gate reuses trust level; the other three gates are new |
| Hierarchy policy tier | Load-time-attested manifest, extending D103's pattern |
| Context shielding | Adopted narrowly, as a deterministic pre-filter feeding Fenrir only |
| Notify | Adopted, as Gjallarhorn's own named but unbuilt delivery-to-operator mechanism |
| Coordinator memory | Built on Gleipnir's concept-graph shape, governed by the hierarchy trust lattice |
| Absorption seam | Not a new mechanism; the policy-tier attestation pipeline already serves this purpose |
| Master-control tier | Stays deferred, no preparatory hook |
| Gleipnir's own open seams | Not a Heimdall obligation; named for the record only |
