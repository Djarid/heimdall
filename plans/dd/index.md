# Heimdall Detailed Design: index and conventions

**Author:** Jason Huxley
**Date:** August 2026
**Version:** 0.1 (draft)
**Target audience:** engineers implementing Heimdall Phases 1 to 3

---

## 1. Purpose and scope

This is the index for the Heimdall Detailed Design. The Detailed Design takes the High-Level Design (`plans/hld.md`) to implementation fidelity: concrete data schemas, interface contracts at the level of function signatures and message formats, algorithms, deployment manifests and test plans.

Scope is Phases 1 to 3 only, per HLD decision D-3:

- Phase 1: the taint boundary (Bifröst) and the read-only, human-gated separation proof.
- Phase 2: the world model (Mímisbrunnr), the classifier and reasoner (Nornir), the sandbox reading path (Fenrir) with the canary mechanism, and the audit log (Hliðskjálf).
- Phase 3: the full control surface (Himinbjörg), alerting (Gjallarhorn) and value integrity (Gjöll).

Phases 4 to 6 (ingestion expansion, introspection, promotion mechanisms) stay at HLD depth. They get a follow-on Detailed Design pass once Phases 1 to 3 are real.

`HEIMDALL.md` remains the authoritative architecture source, and `plans/hld.md` is the authoritative build-oriented view. Where this Detailed Design could drift from either, the HLD wins on structure and `HEIMDALL.md` wins on architecture, unless a Detailed Design document's own decisions table explicitly supersedes a named point.

Cross-reference: `plans/synthesis-architecture.md` (D106) is a cross-cutting integration document, not a per-component one, so it earns no row in the table below. It places new process-plane and hierarchy-plane structure around the components indexed here, citing Himinbjörg, Gjöll, Hliðskjálf and Mímisbrunnr's interfaces rather than altering them; none of this document's own interfaces or status claims change as a result. `plans/rust-workspace-baseline.md` (D109) is the same kind of document: it records the workspace layout, toolchain pin and module conventions the repository's first Rust crate established, cutting across whichever component a future crate re-expresses rather than belonging to one, so it likewise earns no row below.

## 2. Document set

The Detailed Design is split by component, one document each, so a document stays a readable size and a reviewer can attack one component at a time. Documents are authored and reviewed in build order.

| Order | Document | Component | Phase | Lead risk it addresses |
|---|---|---|---|---|
| 1 | `index.md` | this document (conventions, harness binding, cross-cutting contracts) | all | Sets the shared vocabulary so per-component docs do not each reinvent it |
| 2 | `bifrost.md` | Bifröst taint boundary | 1 | The Phase-1 point: content cannot cross raw |
| 3 | `mimisbrunnr.md` | Mímisbrunnr world model | 2 | The typed store, causal graph and flow-to-sink label |
| 4 | `nornir.md` | Nornir classifier and reasoner | 2 | The pluggable fail-closed classifier and the D67 arming gate |
| 5 | `fenrir.md` | Fenrir sandbox and canary | 2 | The reading path, egress restriction, attempt introspection |
| 6 | `hlidskjalf.md` | Hliðskjálf audit log | 2 | The signed append-only chain |
| 7 | `himinbjorg.md` | Himinbjörg gateway and control surface | 3 | The critical path and largest build; the OpenCode binding |
| 8 | `gjoll.md` | Gjöll value integrity | 3 | The sink-declaration schema (the unattested root) and the gates |
| 9 | `gjallarhorn.md` | Gjallarhorn alerting | 3 | Containment decoupled from alerting; the protected channel |

Two components carry the pre-mortem's top risks and get the deepest treatment: Himinbjörg (`himinbjorg.md`, the largest unbuilt piece) and the Gjöll sink-declaration schema (`gjoll.md`, named "the root" in `ADVERSARIAL_REVIEW.md` 5.1).

## 3. The harness binding: OpenCode/Gleipnir as the reference implementation

Per HLD decision D-1, the Detailed Design targets OpenCode/Gleipnir primitives as the Phase 1 to 3 reference implementation. The HLD's Harness Boundary Interface (HBI, HLD section 4.3) is the abstract contract; this section fixes how the reference implementation satisfies it, so each component document can refer to a concrete substrate.

Gleipnir is a sibling OpenCode framework in the same workspace (`/Users/jasonh/git/gleipnir/`). It provides four proven patterns the Detailed Design reuses:

- **Deny-by-default permission maps.** An agent's capabilities are an explicit allowlist; anything not granted is absent, not merely denied. The lesson Gleipnir already paid for: an allowlist of exact capabilities beats a denylist of string patterns, because a pattern deny is evadable by a compound command (a `bash: "*": deny` plus an exact-match allowlist, not a `git*` string deny that `sh -c "git push"` evades). Himinbjörg's control surface (document 7) uses this pattern directly.
- **A trust-tier authority ladder.** Gleipnir's Tier-0/1/2/3 model (disposable, retrieved, user-reviewed, policy) is the same shape as Heimdall's agent trust levels 0 to 5 and its taint levels: authority decreases as writability increases, and nothing lower may alter anything higher. Himinbjörg's trust-ceiling enforcement and Mímisbrunnr's taint model both map onto it.
- **Deterministic sequencing with the LLM as a per-step proposer.** Gleipnir's engine sequences pipeline transitions in code and calls the LLM only for bounded per-step judgment; the LLM's output feeds a router, it does not decide order. This is Heimdall's Design Principle 2 and 3 (the harness is the agent; the LLM proposes, the harness acts) in running form. Himinbjörg's proposal-validation loop is the Heimdall instance of it.
- **A single-holder credential broker.** In Gleipnir only one role holds the git and platform credentials; every other role is structurally denied them. Himinbjörg's credential brokering (agents never see plaintext secrets) is the same single-holder pattern.

The HBI's five capability groups bind to OpenCode as follows (the concrete form each component document builds on):

| HBI group | OpenCode/Gleipnir binding |
|---|---|
| Provider-request interception | A plugin on the model-request path assembles the agent payload from Mímisbrunnr; the raw thread is never forwarded. |
| Agent-start enforcement | The agent's permission map is applied at load; capabilities are absent unless granted. |
| Trust ownership | The framework owns the permission surface; the harness's own trust prompts are suppressed. |
| Tool-call interception | A `tool.execute.before` gate inspects typed arguments against the control surface and the world state and refuses out of policy. |
| Episode capture | `tool.execute.after` and turn hooks emit typed events to Huginn. |

The Detailed Design does not require OpenCode. A pi.dev binding (or any harness satisfying the five HBI groups) is a valid alternative; the reference implementation is OpenCode because a proven pattern exists there for the control surface, which is the Phase-3 critical path.

## 4. Cross-cutting contracts

These contracts are shared across component documents and are defined once here.

### 4.1 The typed assertion

Every piece of content crossing Bifröst becomes a typed assertion. The assertion is the unit that flows through Nornir into Mímisbrunnr. Its shape at the interface level:

- `provenance`: an origin class (for example `EXTERNAL_COMMS`, `EXTERNAL_WEB`, `TOOL_OUTPUT`), never absent.
- `taint`: one of TAINTED, VOUCHED, TRUSTED, CANONICAL. Content from Bifröst is always TAINTED.
- `source`: the concrete source identifier within the provenance class.
- `payload`: the quarantined data. Never merged into any instruction or control field. This is the `data_payload` discipline proven in `poc/symbolic.py`.
- `parsed_fields`: deterministic structural extractions (for example sender, subject), still TAINTED by origin, present so downstream typed slots exist.
- `control_markers_neutralised`: a flag recording whether chat-template control-token strings were broken in the payload (defence in depth, per `poc/symbolic.py`).

The binding rule, carried from the PoC: the payload is data, always, and never concatenated into an instruction, system prompt or task string. A model in the parsing layer would void this, so the parsing layer contains no model.

### 4.2 The fail-closed default

Every classification, validation and gate decision fails closed. Unclassifiable content becomes an `UNCLASSIFIED_DATA_ASSERTION` routed to human review, never trusted. An action-critical value that passes no Gjöll gate is blocked and routed to human authorisation. A proposal that fails any Himinbjörg check is blocked. The fail-closed direction is a binding contract, not an implementation preference, and every component document states its own fail-closed behaviour explicitly.

### 4.3 Provenance is mandatory

No node exists in Mímisbrunnr without a provenance chain. An unprovenanced assertion is structurally untrusted and cannot be stored as trusted. This is enforced at the Mímisbrunnr write interface (document 3), not by convention.

### 4.4 The canonical control channel

The control channel is a set only Himinbjörg and the canonical instruction source populate. It is a trust root: the architecture assumes the attacker cannot write to it (HLD section 8.2). Every component treats any input not on the canonical channel as data. No component document may specify a path by which tainted content reaches the control channel; a document that appears to is a defect.

## 5. Test-plan conventions

Each component document carries a test plan. The conventions:

- Tests are written before implementation where the component has executable behaviour (the test is the correctness arbiter).
- A security property is tested by its failure mode, not only its happy path: a taint-boundary test plants an injection and asserts it does not reach the control channel; a gate test plants a poisoned value and asserts a block; a fail-closed test feeds unclassifiable input and asserts routing to review.
- The existing proof-of-concept and spike suites are the baseline: `poc/` (the separation proof), `spike/substrate/` (the flow-to-sink algorithm), `ontology/tests/` (the classifier and gate, currently deliberately red at false-inert 1/17). A component document states which existing tests it inherits and which it adds.
- Coverage is reported as line and branch, and a green count over low branch coverage on a fail-closed component is not evidence, because the failure paths are the point.

## 6. Decisions (index)

Detailed-Design-level decisions shared across documents. Per-component decisions live in each document's own table.

| # | Decision | Chosen | Rejected | Rationale |
|---|---|---|---|---|
| DD-0 | Document structure | One document per component, authored and reviewed in build order | One monolithic Detailed Design | A per-component split keeps each document a reviewable size and lets a reviewer attack one component at a time; matches the pre-mortem's instruction to lead with the highest-risk components. |
| DD-1 | Reference harness binding | OpenCode/Gleipnir, via the four proven patterns in section 3 | pi.dev; harness-neutral pseudo-code only | HLD D-1. A proven control-surface pattern exists in Gleipnir; the DD reuses it where Heimdall needs it most (Phase 3). The HBI keeps the architecture portable. |
| DD-2 | Shared vocabulary | The cross-cutting contracts in section 4 are defined once here and referenced, not restated | Each document defines its own assertion shape | Prevents drift in the assertion, fail-closed and provenance contracts across nine documents. |

---

## Licence

Part of the Heimdall specification, licensed under CC-BY-SA-4.0. See `LICENSE.md`.
