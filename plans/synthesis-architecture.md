# Heimdall synthesis: architecture

**Author:** Jason Huxley (recorded by AETOS orchestrator session)
**Date:** August 2026
**Version:** 1.0
**Status:** Draft architecture. Builds on `plans/synthesis-capability-matrix.md` (D105). Not yet a Detailed Design document in the sense `plans/dd/index.md` defines that term.

**Precedence.** Per `plans/dd/index.md`'s own rule, `HEIMDALL.md` wins on architecture and `plans/hld.md` wins on structure where this document could drift from either. Where this document assigns new responsibility to an existing specified component (Himinbjörg, Gjöll, Hliðskjálf, Mímisbrunnr), it cites that component's own Detailed Design interface rather than re-specifying it. Every genuinely new component this document introduces is named and scoped only at architecture depth; each earns its own Detailed Design document once its Phase 3 build begins, following the one-document-per-component convention `plans/dd/index.md` already establishes.

## 1. Recap of the four planes

`plans/synthesis-capability-matrix.md` (D105) established four control planes for the synthesised product: output (constrains the model's per-step output, shaped by AETOS, realised by Nornir, Fenrir and Gjöll), process (constrains workflow sequence, shaped by Gleipnir's G-5 engine, realised by a new state-machine engine), hierarchy (which predefined actors compose and how instances spin up per goal, shaped by the AETOS, HADES, ARGUS and RECALL roster model, realised by a new agent registry, cohort catalogue and resident coordinator), and cognition (the model itself, called externally behind a Rust client). This document gives each plane concrete module boundaries.

## 2. Grounding in what already exists

Four Heimdall components are already specified at Detailed Design depth, and this architecture places the new planes around them rather than through them.

**Himinbjörg** (`plans/dd/himinbjorg.md`) already claims the entire control channel: "it owns the control channel exclusively, and nothing executes without passing through it." Its four interfaces, `build_context`, `enforce_definition`, `validate_proposal` and `broker_action`, already cover context construction, control-surface enforcement, six-step proposal validation with a Gjöll call at check five, and credential brokering. This document does not introduce a second control-channel owner. Instead, the new process-plane engine, the resident coordinator and the credential broker are placed inside Himinbjörg's boundary, as internal structure Himinbjörg gates through its own existing interfaces, never as peers that bypass `validate_proposal`.

**Gjöll** (`plans/dd/gjoll.md`) already has a real, demonstrated gate (`evaluate`, `enforce`) and a specified but unbuilt re-validation mechanism (`GatePolicy`, `GateResult`), left open deliberately because it is not yet settled whether that mechanism reuses the promotion-policy's corroboration logic or is a separate one. This document does not resolve that question. The new process-plane engine calls Gjöll exactly where Himinbjörg already calls it, at proposal-validation check five, and treats `GatePolicy` as Himinbjörg's open design question to settle on its own timeline.

**Hliðskjálf** (`plans/dd/hlidskjalf.md`) is a signed, append-only, write-once log of decisions, not a general event bus: "it does not parse, classify or store world state; it records the decisions the other components make." Gleipnir's G-4 typed event bus is a broader mechanism for general inter-component signalling. This document keeps them distinct rather than merging them: Hliðskjálf stays the tamper-evident sink specifically for decision records, and any new event-bus mechanism the process or hierarchy plane needs is a separate live-signalling layer whose decision-relevant events feed Hliðskjálf as one of its writers, alongside Himinbjörg, the promotion pipeline, Bifröst, Nornir and Odin, which are already named as Hliðskjálf writers.

**Mímisbrunnr** (`plans/dd/mimisbrunnr.md`) already carries a taint lattice for world-model data (`TAINTED`, `VOUCHED`, `TRUSTED`, `CANONICAL`) with an explicit rule that promotion is mediated elsewhere, never raised by Mímisbrunnr itself, and an explicit review queue for anything unclassified. This lattice protects data. It has no bearing on the integrity of the hierarchy plane's own configuration, which is a new surface this document must address on its own terms, in section four below.

## 3. New components this architecture introduces

None of the following exist yet as Detailed Design documents. Each is named and scoped here at architecture depth only.

**The process engine.** A Rust re-expression of Gleipnir's G-5 mechanism: a data-driven transition table, code-enforced loop caps, and a human-question state with no outgoing edge until answered. Resident inside Himinbjörg. Sequences a cohort instance's steps; calls into the output plane (Nornir, Fenrir, Gjöll) for each step's adjudication rather than adjudicating output itself. Does not decide whether an action is safe; decides only whether this step is permitted to happen now.

**The resident coordinator and its supporting cohort.** The privileged, always-present tier named in D105 section five. Not one entry in the cohort catalogue among equals; a structure Axiom Two applies to hardest of all, because its configuration, code and evidence must sit at a strictly lower, agent-unreachable enforcement surface than anything it coordinates. Its job is decomposing a durable objective into goals, selecting which predefined cohorts to instantiate from the catalogue and in what order, and holding continuity across them. Resident inside Himinbjörg's boundary, gated by the same `validate_proposal` pipeline as any other proposal it originates.

**The predefined agent registry.** The determinism floor named in D105 as N1: every agent definition is predefined and attested before it can be referenced by any cohort. An agent is never constructed at runtime; it is looked up.

**The cohort catalogue.** Named in D105 as N2: a registry of predefined cohort definitions, each an orchestrator role plus a bounded set of sub-agent roles drawn from the agent registry. A cohort is instantiated from the catalogue, never invented at runtime, and only the instance is ephemeral.

**The credential broker.** A Rust re-expression of Gleipnir's G-9 single-holder pattern: exactly one role holds push and application programming interface credentials, and it runs outside the boundary proper, alongside Himinbjörg's existing `broker_action` interface, which already names this responsibility without yet building it.

## 4. A trust-tier lattice for the hierarchy plane

Mímisbrunnr's taint lattice protects world-model data. It was never meant to, and does not, protect the hierarchy plane's own configuration: the agent registry's contents, the cohort catalogue's contents, and the resident coordinator's own configuration. This is a genuinely new protected object introduced by absorbing the cohort and coordinator model from the sibling projects, and it needs its own lattice, not a repurposing of Mímisbrunnr's.

Gleipnir's G-6 requirement, "memory is not poisonable," is the correct template, carried over as a principle rather than as code, per D105's ruling that Gleipnir's Python is reference-only. G-6's four trust tiers, policy, user-reviewed, retrieved and temporary, with authority decreasing as writability increases, and with named writers so a model may propose but never itself promote into a higher tier, map directly onto the objects this architecture protects:

| Tier | Protects | May be altered by |
|---|---|---|
| Policy | Agent registry, cohort catalogue, resident coordinator configuration | Nothing in the running system; changed only by a rebuild of the compiled artefact or an explicitly attested, out-of-band load, mirroring Gleipnir's own rule that policy is agent-unwritable |
| User-reviewed | Newly proposed agent or cohort definitions awaiting acceptance into the registry or catalogue | A deterministic review gate only, never a model directly |
| Retrieved | Observed behaviour of a running cohort instance, fed back for review | The process engine and the coordinator, as provenance-stamped observation, carrying no authority of its own |
| Temporary | A single cohort instance's own working state | The instance itself, disposable, authority-free |

This lattice is a hierarchy-plane concern, kept explicitly separate from Mímisbrunnr's data-taint lattice, which is left exactly as `plans/dd/mimisbrunnr.md` already specifies it.

## 5. A candidate output-plane technique: context shielding

AETOS's `aetos-sandbox` container auto-indexes large command or fetch output into a local search store and returns compact summaries or snippets instead of the raw text, shielding the model's context window from both bloat and, incidentally, a share of injection surface area. This is named here as a candidate technique for the output plane, not yet ruled on: before any large external output reaches a cognition call, it could be indexed and summarised by a deterministic component, with the summary, not the raw content, offered to the model, and the raw content still available to Fenrir and Nornir for classification. This composes with, rather than replaces, Fenrir's existing canary-wrapped reading of tainted content. Left as an open item for the synthesis architecture's next revision rather than settled here.

## 6. Proposed Rust workspace layout

A first sketch, not a final module boundary. Each crate names the plane it primarily serves.

```
heimdall/
  crates/
    boundary-nornir/        output plane: the symbolic classifier and Yggdrasil ontology
    boundary-fenrir/        output plane: the tainted-content sandbox, external runtime for execution
    boundary-gjoll/         output plane: the action-time gate and flow-to-sink reachability
    process-engine/         process plane: the Gleipnir-derived state machine, resident in himinbjorg
    hierarchy-registry/     hierarchy plane: the predefined agent registry
    hierarchy-catalogue/    hierarchy plane: the predefined cohort catalogue
    hierarchy-coordinator/  hierarchy plane: the privileged resident coordinator, resident in himinbjorg
    hierarchy-trust/        hierarchy plane: the policy/user-reviewed/retrieved/temporary lattice from section four
    himinbjorg/             the gateway process itself: context construction, control-surface enforcement,
                             proposal validation, credential brokering; hosts process-engine and
                             hierarchy-coordinator; the only crate every proposal must pass through
    mimisbrunnr/             the world-model store and its existing taint lattice, unchanged in scope
    hlidskjalf/              the signed, append-only decision log, unchanged in scope
    cognition-client/        cognition plane: the Rust client to an external large language model
```

## 7. Open items carried forward

From D105 section nine, still unresolved:

- Whether Gleipnir's execution sandbox and Fenrir's content sandbox become one mechanism or stay two with a stated boundary between them. (resolved, see D107 in `plans/synthesis-resolutions.md`)
- Whether AETOS's memory and notify capabilities reappear as native Rust modules or are dropped. (resolved, see D107 in `plans/synthesis-resolutions.md`)
- The exact contract for the absorption seam: what a new catalogue entry, output check or process transition must supply to be accepted, and who reviews it. (resolved, see D107 in `plans/synthesis-resolutions.md`)
- The master-control tier's scope, named but not designed further. (resolved, see D107 in `plans/synthesis-resolutions.md`)

Newly surfaced while grounding this architecture in the existing Detailed Design set and the Tolaria vault's documentation of AETOS and Gleipnir:

- Gjöll's own open question, whether `GatePolicy` reuses the promotion policy's corroboration logic or is a separate mechanism, is inherited unresolved by the process-plane engine and must be settled by whoever builds Himinbjörg, not by this document. (resolved, see D107 in `plans/synthesis-resolutions.md`)
- The hierarchy-plane trust-tier lattice in section four is named and mapped but not yet built; it needs its own Detailed Design document once Phase 3 work on the hierarchy plane begins. (resolved, see D107 in `plans/synthesis-resolutions.md`)
- The context-shielding technique in section five is a candidate, not a ruling; it needs a decision before it is designed further. (resolved, see D107 in `plans/synthesis-resolutions.md`)
- Gleipnir's own open engineering seams, E-1 through E-5 in its specification, name gaps in the broker's argument policy, the platform-webhook receiver's home, the event bus's correction-provenance signal quality, a build-order disagreement between two of its verification sub-requirements, and unbuilt GOTCHA and ATLAS methodology bindings. None of these seams are inherited as Heimdall obligations by this document; they are named here only so a future session re-grounding this architecture in Gleipnir's evolving specification does not have to rediscover that they exist.

## 8. Documents this architecture does not replace

`plans/hld.md` remains the authoritative build-oriented view and `plans/dd/*` remain the authoritative per-component implementation-fidelity documents for Phases one to three. This document does not restate their status claims; where a status is quoted here, it is quoted from `plans/hld.md` section three's achievement-baseline table, per that table's own stated role as the single source for those claims.
