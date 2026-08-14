# Heimdall: High-Level Design

**Author:** Jason Huxley
**Date:** August 2026
**Version:** 0.1 (draft, pre-implementation)
**Target audience:** engineers building Heimdall, and reviewers assessing whether the build plan is sound

---

## 1. Front matter

### 1.1 Purpose of this document

This is the High-Level Design for building Heimdall. It translates the ratified architecture specification (`HEIMDALL.md`, v0.11) into a build-oriented engineering view: component boundaries, interface contracts at signature level, data ownership, dependencies between components, deployment topology, non-functional requirements, a phase roadmap and a risk register.

`HEIMDALL.md` remains the authoritative architecture source. This HLD does not restate it in full; it reorganises it for build-readiness and adds the engineering structure a spec does not carry. Where this HLD and `HEIMDALL.md` could drift, `HEIMDALL.md` wins, unless the Decisions index in section 1.4 explicitly supersedes a named point.

### 1.2 Relationship to the achievement baseline

This HLD is grounded in what has actually been built and tested, not only in what `HEIMDALL.md` specifies. Section 3 records the evidence-based status of every component. A reader should treat the architecture (sections 4 to 10) as the target and section 3 as the honest starting line, and should read the phase roadmap (section 11) as the path between them.

The baseline is drawn from the converged scoping brief (`plans/hld_scoping_brainstorm.md`), which audited the real code in `poc/`, `spike/substrate/` and `ontology/` against the claims in `STATUS.md` and `HEIMDALL.md`.

### 1.3 Scope boundary

This HLD covers all six Build Phases at architecture (HLD) depth. It is the full system view.

A separate, later Detailed Design artifact will reach implementation fidelity (data schemas, per-field interface contracts, algorithms, deployment manifests, test plans) for Phases 1 to 3 only, where the core security properties become real: the taint boundary (Phase 1), the world model plus Fenrir plus canary (Phase 2), and the full control surface plus Gjöll (Phase 3). Phases 4 to 6 (ingestion expansion, introspection framework, promotion mechanisms) remain at this HLD's depth, with a named follow-on Detailed Design pass once Phases 1 to 3 are real.

The Detailed Design targets OpenCode/Gleipnir primitives as its Phase 1 to 3 reference harness (see decision D-1). This HLD does not: it stays harness-agnostic, so the architecture is not bound to any single runtime.

### 1.4 Decisions (index)

| # | Decision | Chosen | Rejected | Rationale |
|---|---|---|---|---|
| D-1 | Target harness for the design work | HLD harness-agnostic (pi.dev hooks abstracted into a portability interface); Detailed Design targets OpenCode/Gleipnir primitives for Phases 1 to 3 | pi.dev as specified throughout; OpenCode throughout including the HLD | Operator-converged at the precept-10 gate. The control surface is where an existing OpenCode framework (Gleipnir) most de-risks the build, and it is a Phase-3 concern, so binding the DD to OpenCode buys the most where it does not distract from Phase 1's taint-boundary point. The HLD stays agnostic so the architecture survives a harness change. See `plans/hld_scoping_brainstorm.md` Q1. |
| D-2 | Nornir classifier stance on the open false-inert break | Pluggable classifier behind a stable fail-closed interface; D67-fix tracked as a Phase-2 arming gate | Adopt the candidate D67-fix now; block all Nornir design until D67-fix closes | Operator-converged. Honours the project discipline (a red suite that names a real break beats a false green; no keyword treadmill). The structural design proceeds; the classifier mechanism is swappable; no consequential capability arms against Nornir until D67-fix is closed and re-measured on an independent corpus. See Q2. |
| D-3 | Detailed Design fidelity and phasing | Full HLD across six phases; implementation-ready DD scoped to Phases 1 to 3; Phases 4 to 6 HLD-level with a named follow-on DD | Full-fidelity DD for all six phases now; DD Phase 1 only | Operator-converged. Phases 1 to 3 are where the security properties become real and are already 5 to 7 months of roadmap. Designing Phases 4 to 6 in detail now is designing on unbuilt foundations. See Q3. |
| D-4 | Harness Integration Interface naming | A named contract, the Harness Boundary Interface (HBI), with five capability groups mapped to the five pi.dev hooks | Reproduce pi.dev hook names directly in the architecture | An abstract named contract lets pi.dev or OpenCode bind to the same architecture. HLD-level structural decision made while authoring; not material. See section 4.3. |
| D-5 | Ørlög inconsistency | Recorded as an open documentation defect, not resolved here | Silently drop it; silently add it to the architecture | `GLOSSARY.md` lists Ørlög (configuration substrate) as a named component, but `HEIMDALL.md`'s architecture and the achievement audit contain no such component. Resolving it either way would be a silent architecture change. Flagged in the risk register (R-11) for the operator. |

---

## 2. System context

### 2.1 What Heimdall is

Heimdall is a neurosymbolic harness for autonomous LLM agents. Its purpose is to let agents work with untrusted external content (email, web, documents, images, audio, tool output) without that content being able to cause action.

The mechanism is a structural separation of the data channel from the control channel. A deterministic symbolic layer owns the control channel and makes every action decision. LLMs are demoted to untrusted subroutines that propose; the symbolic layer acts. External content is read only inside a bound, monitored, egress-restricted sandbox that has no route to the control channel.

Trust is assigned by origin at a structural boundary, not by detecting malicious content. This is the load-bearing distinction: detection is heuristic and loses to a determined adversary, whereas an origin label attached at a boundary the content cannot cross is a structural property.

### 2.2 The problem it solves

Every current autonomous agent framework carries the same flaw: the data channel and the control channel are the same channel. An LLM token stream cannot distinguish a system instruction from an attacker-controlled string in a tool response. Prompt injection follows structurally, across every medium, and no amount of in-stream guardrailing fixes it because the fight is on the attacker's ground.

Heimdall moves the decision out of the token stream and into a deterministic layer the content cannot reach. The full argument is in `HEIMDALL.md` sections "Problem Statement" and "Design Principles".

### 2.3 In scope

- Ingestion of untrusted content across multiple media, with a uniform taint boundary
- Deterministic classification of that content against an ontology
- A persistent typed world model with per-node taint and provenance
- A gateway process that constructs agent context and authorises or blocks every action
- A sandboxed reading path (Fenrir) for language tasks over tainted content
- Action-time re-validation of values that can reach a consequential action (Gjöll)
- Self-observation and human-gated self-improvement (Huginn, Muninn, Odin)
- A tamper-evident audit trail (Hliðskjálf)

### 2.4 Out of scope

Carried from `HEIMDALL.md` Non-Goals:

- Network-level and host security. Heimdall operates at the agent cognition layer and assumes host, key management and canonical-channel integrity as trust roots it does not itself provide.
- Constraining what a model can reason about (only what an agent can do).
- Full formal verification. Constraint enforcement is sound only for the covered ontology; coverage gaps are enforcement gaps that fail closed to human review.
- Sub-100ms interactive latency. The symbolic layer adds cost at every decision point; Heimdall targets batch and ingestion workloads.

### 2.5 Relationship to a hosting harness

Heimdall is not a standalone runtime. It integrates with an existing agent harness through a defined interface (section 4.3). `HEIMDALL.md` specifies this against pi.dev's extension API. This HLD abstracts that into the Harness Boundary Interface so the architecture holds against either pi.dev or OpenCode. The Detailed Design's reference implementation targets OpenCode/Gleipnir (D-1).

### 2.6 Relationship to external content sources

Heimdall pulls content from sources at a cadence it sets (Design Principle 11, the pull paradigm). An external source can offer content but cannot force proportional processing and cannot exert backpressure. This is the basis of the availability guarantee: a source that floods is deprioritised or quarantined, and the compute pipeline is never forced to keep pace with attacker volume.

---

## 3. Achievement baseline

Status key: **PROVEN** (running code and passing tests demonstrate it), **DEMONSTRATED** (partial, spike-level or seed-level, not production-integrated), **SPECIFIED-ONLY** (design exists in `HEIMDALL.md`, little or no code), **OPEN** (explicitly unresolved per `DECISIONS.md`).

The taint-boundary premise is genuinely proven at proof-of-concept scale. The classifier, ontology, world-model algorithm and value-integrity gate are demonstrated at seed or spike depth, with one deliberately-failing test that names a real break. The entire control surface (Himinbjörg), the introspection triad (Huginn, Muninn, Odin), the alerting layer (Gjallarhorn), the audit log service (Hliðskjálf) and a deployed Fenrir sandbox are specified but unbuilt.

| Component | Status | Evidence | Delta to a deployable Phase 1 to 3 system |
|---|---|---|---|
| Bifröst (taint boundary) | DEMONSTRATED (PoC shape) | `poc/symbolic.py` (148 lines): deterministic email parse, `UNTRUSTED` provenance stamp, control-marker neutralisation; out-of-band token-id boundary in `poc/neural.py`. Invariants 3.2 and 3.3 proven. | No live multi-medium parser layer (web, document, OCR, STT are Phase 4). Single medium (email), PoC scale. Mixed-trust-source re-stamping unaddressed (`ADVERSARIAL_REVIEW.md` 5.9). |
| Nornir (classifier and reasoner) | DEMONSTRATED, one RED obligation | `ontology/nornir/` real: `rules.py` (370 lines, four rule kinds, risk-tier priority, shared `carries_imperative_or_consequence` guard D69), `engine.py`, fail-closed `unclassified.py`; harness `ontology/tests/harness.py` (706 lines) runs obligations 8.1 to 8.4. Obligation 8.2 is failing: false-inert 1/16 (D67). | Close or scope D67-fix (D-2). Coverage 36/38 on a self-authored four-domain seed; breadth untested; no independent-labelled corpus. |
| Mímisbrunnr (world model) | DEMONSTRATED (spike plus live binding) | `spike/substrate/reachability.py` (322 lines): support-counted incremental flow-to-sink, sound conservative and exact retraction; live Memgraph binding (D57, 1800 fuzzed operations, zero unsound). D25, D32, D38 ratified. | The live store is an optional skip-if-absent verification harness, not a production world-model service. No persistent typed-node schema for real ingestion; no causal graph; per-batch is the default (cross-batch only under `persist=True`). |
| Himinbjörg (gateway and control surface) | SPECIFIED-ONLY (rich), plus a dormant slice | `HEIMDALL.md` 294 to 401: full agent-definition schema (trust levels 0 to 5; 10 control groups), six-step proposal validation, global-default-plus-override. Built: `ontology/yggdrasil/control_surface.py` (73 lines), a dormant `AgentContext` with 4 fields. | The gateway process does not exist. About 4 of roughly 20 control fields are modelled. No proposal-validation pipeline, no credential broker, no tool-call interception, no context construction from the world model. The single largest Phase-3 build and the critical path. |
| Gjallarhorn (alert and escalation) | SPECIFIED-ONLY | `HEIMDALL.md` 405 to 423; `rules.py` names a constraint violation as a Gjallarhorn event (naming only). | No alert routing, aggregation, containment-decoupled-from-alerting or protected escalation channel. Phase 3. |
| Huginn (behavioural observation) | SPECIFIED-ONLY | `HEIMDALL.md` canary signal tables and attempt-introspection (513 to 592); D34 (honest-versus-injection features) open. | Zero code. Episode capture, canary monitoring and baselining all unbuilt. Phase 2 (canary) and Phase 5 (patterns). |
| Muninn (episode memory) | SPECIFIED-ONLY | `HEIMDALL.md` Phase 5; glossary. | Zero code. Phase 5. |
| Odin (self-modification proposer) | OPEN / SPECIFIED-ONLY | `HEIMDALL.md` 1005 to 1007, Open Question 3; D35 open (self-modification of own definition excluded). | Zero code. The only human-approval-gated loop. Phase 5 to 6. |
| Hliðskjálf (audit log) | DEMONSTRATED in spirit only | Harnesses treat failures as loud audit artefacts (invariant 3.10 proven as a harness property). The signed append-only chain is a trust-root assumption. | No signed append-only log service exists. Phase 2. |
| Fenrir (sandbox agent) | DEMONSTRATED in shape, not deployment | PoC `neural.py` is tool-less, egress-free, fresh-context extraction (invariant 3.8 demonstrated in shape). Canary mechanism and attempt-introspection fully specified (`HEIMDALL.md` 519 to 592) but unbuilt. | No segmented sandbox deployment, no egress-policy test, no canary wrapping, no Huginn monitoring, no attempt-introspection tripwire. Phase 2. |
| Gjöll (value integrity and action-time gate) | DEMONSTRATED (gate shape and action-critical label) | `ontology/nornir/gjoll.py` (151 lines): a real four-term-conjunction gate, fails closed, blocks before the actuator fires, wired to the flow-to-sink action-critical determination (D58); provenance gate proven in PoC `sinks.py`. | Sink and flow declarations are unattested trusted input (`ADVERSARIAL_REVIEW.md` 5.1, "the root"): no schema, no signing, `consumes` is an unchecked dict. Re-validation modes (re-derivation, semantic constraint, corroboration) specified, not built. Phase 3. |
| Yggdrasil (ontology) | DEMONSTRATED (four-domain seed) | `ontology/yggdrasil/` real: BFO-anchored `core.py`, `spine/`, four `domain/` modules, `media.py`, `unclassified.py`; BFO 2020 loaded, SUMO reference-only. Attach test D29 demonstrated three times. 45 to 58 nodes. | Seed only. Coverage breadth untested; growth is hand-authored (the Odin path is Phase 5). |

**Baseline summary.** The core value proposition (external content cannot reach the control channel) holds in running code. The distance to a deployable Phase 1 to 3 system is dominated by Himinbjörg, which is essentially unbuilt and is the Phase-3 critical path, and by a deployed Fenrir sandbox. The Detailed Design should lead with both.

---

## 4. Architecture overview

### 4.1 Component diagram

The pipeline is a one-way flow from the world, across the taint boundary, through classification into the world model, and out through the gateway that owns all action. The reading path (Fenrir) hangs off the agent runtime and returns only to the world model, never to the control channel.

```
┌───────────────────────────────────────────────────────────────┐
│                            WORLD                                │
│   email · web · files · audio · images · tools · APIs           │
└───────────────────────────┬───────────────────────────────────┘
                            │ raw external content (all media)
                            ▼
┌───────────────────────────────────────────────────────────────┐
│                          BIFRÖST                                │
│                       taint boundary                            │
│   parsers per medium · all output tainted · patterns logged     │
└───────────────────────────┬───────────────────────────────────┘
                            │ typed tainted assertions
                            ▼
┌───────────────────────────────────────────────────────────────┐
│                           NORNIR                                │
│           symbolic classifier and reasoner (pluggable)          │
│   maps assertions to ontology types · fail-closed to review     │
└───────────────────────────┬───────────────────────────────────┘
                            │ classified, provenanced assertions
                            ▼
┌───────────────────────────────────────────────────────────────┐
│                        MÍMISBRUNNR                              │
│             world model (typed property graph)                  │
│   taint per node · provenance chain · causal graph              │
│   flow-to-sink action-critical label (backward propagated)      │
└───────────────────────────┬───────────────────────────────────┘
                            │ structured world state
                            ▼
┌───────────────────────────────────────────────────────────────┐
│                        HIMINBJÖRG                               │
│                       gateway process                           │
│   builds agent context · owns control channel · validates       │
│   proposals · brokers credentials · applies Gjöll at action time │
└───────┬───────────────────────────────────────┬───────────────┘
        │                                        │
        ▼                                        ▼
┌────────────────────────┐          ┌───────────────────────────┐
│     AGENT RUNTIME       │          │    HUGINN & MUNINN         │
│  (via Harness Boundary  │          │   introspection framework  │
│   Interface)            │          │   observe · remember       │
│  agents propose;        │          │   detect drift and anomaly │
│  harness never acts     │          │   → ODIN proposes fixes    │
└──────────┬─────────────┘          └───────────────────────────┘
           │ tainted content tasks only
           ▼
┌───────────────────────────────────────────────────────────────┐
│                           FENRIR                                │
│                sandbox agent (egress-restricted)                │
│   canary-wrapped · zero tools · fresh context · monitored       │
│   outputs always tainted → Mímisbrunnr only                     │
└───────────────────────────────────────────────────────────────┘

  All decisions, denials, promotions and escalations are written to
  HLIÐSKJÁLF (signed, append-only). GJALLARHORN routes alerts and
  triggers containment. GJÖLL gates action-critical values at action
  time inside Himinbjörg.
```

### 4.2 Data and control flow

The controlling invariant is that content flows one way and never gains authority by doing so. Raw content enters only at Bifröst and is stamped tainted at the crossing. Nornir classifies it deterministically; anything it cannot classify becomes an `UNCLASSIFIED_DATA_ASSERTION` bound for human review, never trusted. Classified assertions land in Mímisbrunnr carrying taint and provenance. Himinbjörg constructs agent context from Mímisbrunnr, so a normal agent never sees a raw content window. Agents propose; Himinbjörg validates every proposal against the world model, the agent's control surface and the constraint axioms, then executes, queues or blocks. Any language task that needs to read tainted content directly is routed to Fenrir, which returns typed tainted assertions to Mímisbrunnr and nothing to the control channel.

The control channel is a set the attacker cannot write to. Only Himinbjörg and the canonical instruction source populate it. Every other input is data.

### 4.3 The Harness Boundary Interface (HBI)

`HEIMDALL.md` specifies integration against five pi.dev extension hooks. This HLD abstracts them into a named contract, the Harness Boundary Interface, so any harness can host Heimdall by implementing five capability groups. A harness binding is an adapter that satisfies the HBI; the architecture depends on the interface, not on any harness's hook names (D-4).

| HBI capability group | Contract | pi.dev hook | OpenCode/Gleipnir analogue (DD reference) |
|---|---|---|---|
| Provider-request interception | Heimdall reconstructs the model payload from Mímisbrunnr; raw external content is never present in what reaches the provider | `before_provider_request` | Plugin on the model-request path; the agent context is assembled from the world model, not the raw thread |
| Agent-start enforcement | The agent's symbolic definition (tools, permissions, scope, skills) is applied before the first token | `before_agent_start` | Deny-by-default permission map applied at agent load; capabilities absent, not merely denied |
| Trust ownership | Heimdall owns trust decisions; the harness's own trust prompts are suppressed | `project_trust` | Framework owns the permission surface; the harness defers |
| Tool-call interception | Every tool call is validated against the agent definition, the world state and the constraint axioms, then executed, queued or blocked | tool-call interception | `tool.execute.before` gate that inspects typed arguments and refuses out of policy |
| Episode capture | Every turn is captured to Huginn as a structured episode, before and after execution | episode capture | `tool.execute.after` and turn hooks emitting typed events |

The DD will specify the OpenCode binding of the HBI concretely. This HLD requires only that a harness satisfy all five groups; a harness that cannot is unsuitable.

The reference-implementation choice is grounded, not incidental. Gleipnir (a sibling OpenCode framework) already runs a deny-by-default permission map, a Tier-0/1/2/3 authority ladder analogous to Heimdall's trust levels 0 to 5, a deterministic sequencing engine that decides while the LLM only proposes (the same principle as Design Principle 2 and 3), and a broker that holds credentials so agents never see them (analogous to Himinbjörg's credential brokering). It has also already paid for the permission-grammar failure a from-scratch binding would otherwise rediscover: an allowlist of exact capabilities beats a denylist of string patterns, because a pattern deny is evadable by a compound command. Targeting OpenCode for the DD reuses that proven pattern exactly where Heimdall needs it most, in Himinbjörg's control surface (Phase 3). It does not help Phase 1's taint boundary, which has no harness analogue in either direction, so the choice does not distract from proving the architecture's central point.

---

## 5. Component design

Each subsection states the component's responsibilities, its key interfaces at signature level (not full field schemas, which are Detailed Design), the data it owns, its upstream and downstream dependencies and its current build status from section 3. The order leads with the two components the pre-mortem flagged as highest-risk to under-specify: Himinbjörg (the largest unbuilt piece) and Gjöll (whose declarations are the unattested root). The remaining components follow in pipeline order.

### 5.1 Himinbjörg: gateway process

**Status:** specified-only, plus a dormant `AgentContext` stub. This is the Phase-3 critical path and the largest single build.

**Responsibilities.** Himinbjörg owns the control channel exclusively. Nothing executes without passing through it. It has four jobs: construct agent context from the world model, enforce each agent's control surface, validate every proposal before execution and broker credentialled actions so agents never see plaintext secrets. It also applies Gjöll at action time (section 5.2) and routes Gjallarhorn alerts (section 5.5).

**Context construction.** Himinbjörg builds a normal agent's context from Mímisbrunnr, never from raw external content. A normal agent receives its identity summary, a typed relevant subgraph of the world model, its standing constraints, the task context and the canonical control channel. It deliberately has no content window. Reintroducing one would reopen the injection surface Fenrir exists to close, so the absence is a hard rule, not a default.

**The control surface.** Every agent is a first-class object with two inseparable halves, a symbolic definition (deterministic, enforced here) and a neural persona (probabilistic, shapes reasoning). The symbolic definition is the full schema in `HEIMDALL.md` 331 to 384: trust level, world-model read and write scope, and 10 control groups (tools, filesystem, network, resources, credentials, subagents, inter-agent, exfiltration, temporal, escalation). Global defaults apply to every agent; an agent definition may override within its trust-level ceiling and never above it. This HLD does not restate the schema field by field; the DD will. The HLD requires that Himinbjörg enforce it as written, that overrides never exceed the ceiling and that an agent cannot grant itself a capability its definition does not carry.

**Proposal validation.** Every agent proposal returns to Himinbjörg before any execution. The six checks (from `HEIMDALL.md` 314 to 323): the action type is in the agent's permitted action space; the target is in scope per the world model; no constraint axiom is violated; the blast radius is within authorised bounds; the taint level of the inputs is compatible with the action; the resource budget is not exceeded. A proposal failing any check is blocked, logged to Hliðskjálf and optionally escalated through Gjallarhorn.

**Key interfaces (signature level).**

- `build_context(agent_id, task) -> AgentContext` reads Mímisbrunnr and returns a typed context with no raw-content window.
- `validate_proposal(agent_id, proposal) -> Decision{ALLOW | BLOCK | QUEUE | ESCALATE}` runs the six checks plus Gjöll for any action-critical value.
- `broker_action(agent_id, action, credential_scope) -> Result` performs a credentialled action without exposing the credential to the agent.
- `enforce_definition(agent_id) -> ControlSurface` resolves global defaults with agent overrides under the trust ceiling, applied at agent start via the HBI.

**Data owned.** The agent definitions (symbolic halves), the global default control surface and the live authorisation state. It reads Mímisbrunnr; it does not own it.

**Dependencies.** Upstream: Mímisbrunnr (context source), the agent runtime via the HBI (proposals arrive). Downstream: Gjöll (action-time value gating), Gjallarhorn (alerts), Hliðskjálf (audit), the credential store (brokering).

**Build delta.** The gateway process itself must be built. The dormant `control_surface.py` models about 4 of roughly 20 fields. Proposal validation, context construction, credential brokering and tool-call interception through the HBI are all unbuilt. Targeting OpenCode/Gleipnir for the DD (D-1) reuses a proven permission-map and deny-by-default pattern here.

### 5.2 Gjöll: value integrity and action-time re-validation

**Status:** demonstrated (the gate shape and the action-critical determination are real in `ontology/nornir/gjoll.py`); the re-validation gates and the declaration schema are unbuilt.

**Responsibilities.** Gjöll answers a question provenance does not: is this value safe to act on right now. A value can be correctly typed, correctly provenanced and still be a poisoned value. Gjöll gates the action, not the assertion. It exists because writing an action-critical value to the world model is an execution capability, and the taint boundary alone does not close value poisoning (see section 8).

**Action-critical classification (the flow-to-sink rule).** A value is action-critical if it can ever flow into a consequential, not-trivially-reversible action, directly or transitively through any chain of intermediate writes. Reversibility of the immediate step is irrelevant; what matters is whether the value can reach a consequential sink downstream. This is transitive taint analysis over Mímisbrunnr's write and read dependency graph. Action-critical status propagates backward from declared consequential sinks to every value that can reach them, so the gate fires at a staging write, not only at the final action. This is the rule that closes multi-step state staging, which the earlier per-step consequence rule did not. The backward-propagated label is maintained incrementally at write time, giving constant-time authorisation-time reads (the algorithm is proven in `spike/substrate/reachability.py`, including sound edge-deletion retraction).

**The four gates.** Before Himinbjörg authorises a consequential action, every action-critical value it depends on must pass at least one gate. Each gate's honest strength (from `HEIMDALL.md` 745 to 762):

- Re-derivation: re-extract the value from source at action time via a fresh Fenrir instance and require a match. Weak; catches unstable poisoning and instance-state corruption, not a deterministic source-structured poison. A floor against accidents, not adversaries.
- Semantic constraint: the value must satisfy ontology axioms beyond its type (an address in scope, an amount in range). Bounds targeting freedom to what was already authorised; does not verify benignity.
- Promotion requirement: an action-critical value must be TRUSTED, not merely present; a tainted action-critical value cannot drive a consequential action without human or cryptographic promotion. The strongest gate and the fallback for the others; sound but shifts cost onto the human.
- Corroboration from independent provenance: a second, genuinely independent origin attests the value. Sound where it exists, frequently unavailable.

A value passing no gate does not fail silently: the action is blocked, the dependency flagged, and the value routed to human authorisation on the protected channel, not the bulk review queue.

**Key interfaces (signature level).**

- `is_action_critical(value_node) -> bool` reads the backward-propagated flow-to-sink label from Mímisbrunnr.
- `gate(value_node, action, gate_policy) -> GateResult{PASS(gate) | BLOCK(reason)}` applies the action's chosen gate or gates.
- `declare_sink(sink_spec)` registers a consequential sink; sink and flow declarations are the trust root and must be attested (see build delta).

**What Gjöll achieves and does not.** It does not make value poisoning impossible. Its real contribution is narrow and worth having: it converts a silent integrity failure into an explicit authorisation decision. The containment is achieved by moving the decision to a human or a key, not by the automated gates defeating the attack. This is containment, not elimination.

**Build delta.** The four-term gate and the action-critical wiring are real. The three non-promotion re-validation modes are unbuilt. Critically, sink and flow declarations are currently unattested trusted input (`consumes` is an unchecked dict), which `ADVERSARIAL_REVIEW.md` 5.1 names as the root: the DD must specify a signed sink-declaration schema with gate-boundary validation, or the whole flow-to-sink guarantee rests on an unchecked input.

### 5.3 Bifröst: taint boundary

**Status:** demonstrated at PoC shape for one medium (email).

**Responsibilities.** Bifröst is the single crossing point for all external content. Nothing crosses raw. Every parser, per medium, emits tainted assertions only, stamped with a provenance class (`EXTERNAL_COMMS`, `EXTERNAL_WEB`, `EXTERNAL_DOCUMENT`, `EXTERNAL_VISUAL`, `EXTERNAL_AUDIO`, `TOOL_OUTPUT`, `EXTERNAL_FILE`). A structural classifier flags instruction patterns (imperative forms, capability references, known injection phrasings, encoded variants); flagged patterns are stripped from the content crossing to Nornir, logged to Hliðskjálf with the full original and routed to Gjallarhorn.

Instruction-pattern detection is belt-and-braces only. The architectural guarantee is provenance: an email body is `EXTERNAL_COMMS` and tainted regardless of content and regardless of detection confidence. A detection miss does not compromise the structural guarantee, because the guarantee is the origin label, not the detector.

**Key interfaces (signature level).**

- `parse(raw_content, medium) -> [TaintedAssertion]` emits typed tainted assertions.
- `scan_patterns(assertion) -> [Flag]` runs the belt-and-braces structural classifier.

**Data owned.** The parser registry and the taint-class bindings (present as data in `ontology/media/`).

**Dependencies.** Upstream: the pull-ingestion loop. Downstream: Nornir.

**Build delta.** Only email is demonstrated. Web, document, OCR and STT parsers are Phase 4. Mixed-trust-source re-stamping (a document that quotes an untrusted source inside a trusted one) is an unaddressed seam (`ADVERSARIAL_REVIEW.md` 5.9).

### 5.4 Nornir: symbolic classifier and reasoner

**Status:** demonstrated on a four-domain seed, with one deliberately-failing obligation (D67).

**Responsibilities.** Nornir maps tainted assertions to typed ontology nodes and derives new facts via a forward-chaining reasoner. It is not an LLM; it is a deterministic rule engine over the composed ontology (upper, domain, action space, constraint space, trust). Unknown content does not block ingestion: it becomes an `UNCLASSIFIED_DATA_ASSERTION`, actionable false, review-queued, and enters Mímisbrunnr without ever reaching the control channel. Constraint violations trigger Gjallarhorn immediately.

**The pluggable, fail-closed classifier (D-2).** The classifier is a swappable component behind a stable interface. Its binding contract is fail-closed: unclassifiable or unconfidently-classified content routes to human review and is never trusted; the inert type is earned only by a positive informational signal, so a passively-phrased consequential message does not silently go inert. The open false-inert break (D67, measured 1/16 on an independent corpus, suite deliberately red) is a tracked Phase-2 arming gate (risk R-1): no autonomous consequential capability may arm against Nornir's classification until D67-fix is closed and re-measured on a genuinely independent corpus. The candidate fix (a narrow grammar-constrained model question, inert requires a documented no) is not committed to here; the interface is built to accept it or a better mechanism later without redesigning Nornir.

**Key interfaces (signature level).**

- `classify(assertion) -> Classification{typed | UNCLASSIFIED}` via the pluggable classifier, fail-closed by contract.
- `reason(assertion_batch) -> [DerivedFact]` forward-chains; derived facts carry `inferred: true` and their assertion chain.
- `check_constraints(fact) -> [Violation]` raises a Gjallarhorn event on any breach.

**Data owned.** The classifier rule registry (per domain) and the reasoner rules. The ontology it operates over is owned by Yggdrasil (section 5.12).

**Dependencies.** Upstream: Bifröst. Downstream: Mímisbrunnr, Gjallarhorn.

**Build delta.** Real classifier and reasoner on a four-domain seed. Coverage is 36/38 self-authored; breadth is untested and an independent-labelled corpus does not exist (risk R-2). D67-fix is open.

### 5.5 Gjallarhorn: alert and escalation

**Status:** specified-only.

**Responsibilities.** Fires on: an instruction pattern at Bifröst, a constraint violation, a taint-boundary breach attempt, a Huginn anomaly, a resource-limit approach, a promotion request above threshold, an audit-integrity failure. Two properties are load-bearing. First, containment is decoupled from alerting: when attempt introspection or a canary check fires, the Fenrir instance is halted and its output discarded automatically, per instance, without waiting for a human, so burying an alert in volume does not help an attacker (the poisoned run is already contained). Second, human-facing alerts are aggregated: correlated events collapse into one incident, and a spike in attempt-introspection or canary events is itself a single high-priority signal that triggers source quarantine.

**Key interfaces (signature level).**

- `raise(event) -> void` accepts a typed event; routing is per event type (log, notify, halt-agent, halt-system).
- `contain(fenrir_instance) -> void` halts and discards, independent of alert delivery.
- `aggregate(events) -> Incident` collapses correlated events.

**Dependencies.** Upstream: every component that can raise. Downstream: the protected escalation channel, source quarantine, Hliðskjálf.

**Build delta.** Only the naming exists (a constraint violation is called a Gjallarhorn event in `rules.py`). Routing, aggregation, containment decoupling and the protected channel are Phase 3.

### 5.6 Fenrir: sandbox agent

**Status:** demonstrated in shape (tool-less, egress-free, fresh-context extraction in the PoC); the sandbox deployment and canary mechanism are unbuilt.

**Responsibilities.** Fenrir is the only agent permitted to read tainted content, and it makes reading structurally safe rather than preventing it. Its safety rests on four structural properties: fresh context per invocation (no cross-invocation conditioning), a local egress-restricted model (no exfiltration path), zero execution surface (no tools, MCP, shell or filesystem, so injection can only influence text, never cause action) and full mandatory introspection (every emission observed).

**The canary mechanism.** Himinbjörg wraps every Fenrir context with a signed top and tail canary carrying the task, the output schema, a per-invocation canary token (a UUID from a secure source, never reused, never logged to any ingestion-reachable surface) and a honeypot phrase (a secret unknown to the tainted content). Injection must defeat both tokens independently. Huginn checks the output for token presence, honeypot absence and schema compliance.

**Attempt introspection (the null-surface tripwire).** Because Fenrir has no tools, it has no legitimate reason to emit an action-shaped token sequence. Any action-shaped emission therefore has one explanation: the tainted content instructed it to act. This fires at the attempt, before any manipulated output is produced, is less evadable than the output canary (it checks the reasoning trace) and has zero false positives by construction. It is a hard signal: immediate Gjallarhorn, halt, discard, quarantine.

**Grammar-constrained decoding.** Because Fenrir is a local model, its output is constrained to emit directly into the typed assertion schema, removing the free-text intermediate and with it the second-parse injection surface. An interpretive task that cannot be constrained becomes a single `INTERPRETIVE_SUMMARY` tainted assertion, never decomposed by a second LLM pass and never actionable without human promotion.

**Key interfaces (signature level).**

- `extract(canary_wrapped_content) -> [TaintedAssertion]` under grammar-constrained decoding.
- The canary wrap and the monitoring are Himinbjörg's and Huginn's; Fenrir's own surface is deliberately just extraction.

**Data owned.** None persistent. Fresh context per run, no carryover.

**Dependencies.** Upstream: Himinbjörg (canary wrap), Bifröst-parsed content. Downstream: Mímisbrunnr only. Monitored by Huginn throughout.

**Build delta.** No segmented deployment, no egress-policy test, no canary wrapping, no attempt-introspection tripwire. Phase 2. The reference deployment (a local dense model on an egress-restricted segment) is in section 9.

### 5.7 Mímisbrunnr: world model

**Status:** demonstrated (the flow-to-sink algorithm via spike and a live Memgraph binding); the production world-model service is unbuilt.

**Responsibilities.** The persistent typed graph that is the authoritative state of everything Heimdall knows. Agents have a view of it constructed by Himinbjörg, not a traditional context window. Every node carries a type, a taint level, a provenance chain, timestamps, a confidence, an actionable flag and an inferred flag. Every action writes a causal edge (agent performed action produced state-change, with pre- and post-conditions), enabling rollback via causal unwind, counterfactual queries and blast-radius analysis before execution. It maintains the backward-propagated flow-to-sink action-critical label for Gjöll.

**Key interfaces (signature level).**

- `assert(typed_assertion) -> NodeId` writes a node with taint and provenance and updates the flow-to-sink label incrementally.
- `subgraph(scope) -> Subgraph` for Himinbjörg context construction.
- `causal_unwind(action_id) -> void` rolls back via the causal graph.
- `reachable_to_sink(node) -> bool` reads the maintained label (constant-time).

**Data owned.** All world state, the causal graph and the action-critical labels.

**Dependencies.** Upstream: Nornir (classified assertions), Fenrir via Nornir. Downstream: Himinbjörg (reads), Gjöll (reads the label), Hliðskjálf (causal anchoring).

**Build delta.** The algorithm and a live store binding are proven. The production service, the persistent typed-node schema for real ingestion, the causal graph and the default cross-batch maintenance are unbuilt. Choice of store is Open Question 1 in `HEIMDALL.md`; the flow-to-sink maintenance favours a property graph (Memgraph).

### 5.8 Hliðskjálf: audit framework

**Status:** demonstrated in spirit only (the harnesses treat failures as loud audit artefacts); the signed append-only service does not exist.

**Responsibilities.** A tamper-evident append-only log of every decision, promotion, denial, escalation and proposal. Each entry is signed; the signature chain detects tampering. Rollback uses the causal graph in Mímisbrunnr anchored by Hliðskjálf entries. The signature chain's integrity is a trust root (section 8), a prerequisite the architecture assumes rather than provides.

**Key interfaces (signature level).**

- `append(entry) -> EntryId` signs and chains.
- `verify_chain() -> bool` detects tampering.

**Dependencies.** Upstream: Himinbjörg and every decision-making component. Downstream: causal-unwind, forensic reconstruction.

**Build delta.** The service must be built. Phase 2.

### 5.9 Huginn: behavioural observation

**Status:** specified-only.

**Responsibilities.** Captures all agent behaviour as structured episodes (context hash, proposal, decision, result, world-model delta, token and time usage, taint exposures) and runs pattern detection over the episode stream: drift, constraint pressure, taint-handling, capability gaps, ontology gaps, anomalies. It also performs the Fenrir canary monitoring and the attempt-introspection checks (hard and soft signals from `HEIMDALL.md` 558 to 577).

**Key interfaces (signature level).**

- `capture(episode) -> void` before and after each turn.
- `check_canary(fenrir_output) -> [Signal]` hard and soft signals.
- `detect(episode_stream) -> [Anomaly]` pattern detection.

**Dependencies.** Upstream: the agent runtime, Fenrir. Downstream: Muninn (storage), Gjallarhorn (hard signals), Odin (evidence).

**Build delta.** Zero code. Canary monitoring is Phase 2; pattern detection is Phase 5. The discriminating features that separate an honest weak-model extraction error from an injection-induced one are open (D34); until then, the fail-closed default makes the gap safe.

### 5.10 Muninn: episode memory

**Status:** specified-only.

**Responsibilities.** The persistent queryable store of all episodes: per-agent baselines, cross-agent comparison, longitudinal analysis and training-signal generation. Queryable by Odin and by Himinbjörg for context construction.

**Key interfaces (signature level).**

- `store(episode) -> void`.
- `query(spec) -> [Episode]`.

**Dependencies.** Upstream: Huginn. Downstream: Odin, Himinbjörg.

**Build delta.** Zero code. Phase 5.

### 5.11 Odin: roster agent

**Status:** open / specified-only. The only human-approval-gated loop.

**Responsibilities.** A roster-type agent that consumes Huginn and Muninn evidence and proposes improvements (agent-definition updates, constraint refinements, ontology extensions, taint-policy updates, new agents, escalation-policy updates). Odin never executes changes; it surfaces proposals to the human operator with supporting episode evidence, versioned and logged to Hliðskjálf. Odin may never propose changes to its own definition (Open Question 3; circular self-modification is out of scope, D35).

This is the KFA distinction that separates Heimdall's operational autonomy from its self-modification. Ordinary operation runs without a human in the loop; only self-modification is human-gated, and Odin is that gate's proposer.

**Key interfaces (signature level).**

- `propose(evidence) -> Proposal` never auto-applied.
- Proposals are human-approved, then applied by the operator, never by Odin.

**Dependencies.** Upstream: Huginn, Muninn. Downstream: the human operator, Hliðskjálf.

**Build delta.** Zero code. Phase 5 to 6. The feedback loop is a target for a patient adversary (risk R-3); hardening (independent evidence sampling, requiring CANONICAL or human-VOUCHED evidence for any control relaxation) is deferred.

### 5.12 Yggdrasil: ontology

**Status:** demonstrated (a four-domain seed).

**Responsibilities.** The composed ontology Nornir operates over: an upper layer (BFO, with SUMO as unloaded reference), domain layers (communications, scheduling, finance, publication in the seed), an action space, a constraint space and a trust layer. It declares which sinks are consequential, which is what makes the flow-to-sink rule computable. Coverage grows demand-driven from captured gaps; the guarantee is exactly as strong as coverage, so growth methodology matters as much as the boundary (see `ONTOLOGY_CONSTRUCTION.md`).

**Key interfaces (signature level).**

- The ontology is data, loaded by Nornir. A domain attaches without editing existing domains or the spine (the attach test, D29, demonstrated three times).

**Dependencies.** Downstream: Nornir (classification and reasoning), Gjöll (sink declarations).

**Build delta.** Seed only, four domains, 45 to 58 nodes. Breadth untested; growth is hand-authored until the Odin path lands. BFO 2020 is loaded; the upper-ontology load-and-extend against a live store is a low-risk residual.

---

## 6. Data architecture

Mímisbrunnr is a typed property graph. This section states the shape at HLD depth; the per-field schema is Detailed Design.

**Node model.** Every node carries: `id` (uuid), `type` (an ontology type), `taint` (one of TAINTED, VOUCHED, TRUSTED, CANONICAL), `provenance` (a source chain), `created_at` and `updated_at`, `confidence` (float), `actionable` (bool) and `inferred` (bool). The taint level and the provenance chain are on every node without exception; an unprovenanced assertion is structurally untrusted and cannot exist as a trusted node.

**Edge model and the causal graph.** Ordinary edges carry typed relations between nodes. Action edges form the causal graph: an agent performed an action, the action produced a state change, the action had preconditions (world state before) and postconditions (world state after). This structure is what enables causal unwind (rollback), counterfactual queries (if we had not done X, is Y still reachable) and pre-execution blast-radius analysis.

**The flow-to-sink label.** Separate from taint, every node carries a maintained `reachable_to_sink` label: true if the node's value can reach a declared consequential sink by any path, however many reversible hops intervene. The label is propagated backward from declared sinks and maintained incrementally at write time, so an authorisation-time read is constant-time. Edge deletion is the known hard case for label retraction and is handled by support-counting (proven in the substrate spike, including exact retraction).

**Provenance chain.** Every node records where it came from and through what transformations. A value extracted by Fenrir from an email body carries the `EXTERNAL_COMMS` origin, the Fenrir invocation and the classification step. Provenance answers where a value came from; it does not by itself make a value safe to act on, which is why Gjöll exists (section 5.2).

---

## 7. Trust and promotion model

### 7.1 Agent trust levels

Trust level is a ceiling on what an agent's symbolic definition may grant, not a grant in itself. An agent cannot override any control above its ceiling.

| Level | Class | Ceiling |
|---|---|---|
| 0 | Observer | Read-only world-model access. No tools, no writes, no actions. |
| 1 | Sandbox | Tainted-content processing only (Fenrir). No execution surface. Outputs always tainted. |
| 2 | Restricted | Bounded tool access, no destructive actions, no credential use. Recoverable actions only. |
| 3 | Standard | Full tool access within scope, credential-brokered actions, recoverable and bounded-irrecoverable actions with logging. |
| 4 | Privileged | Broad action authority, cross-scope operations, subagent spawning under escalation policy. |
| 5 | Roster | Meta-level (Odin). May propose changes to definitions, controls and ontology; cannot execute them (proposals need human approval); no operational tool access. |

Elevating an agent's trust level is a human-authorised action logged to Hliðskjálf.

### 7.2 Taint levels

| Level | Meaning | Can drive autonomous action |
|---|---|---|
| TAINTED | External origin, no trust | No |
| VOUCHED | Human-reviewed, limited scope | Scoped only |
| TRUSTED | Explicitly authorised | Within authorisation scope |
| CANONICAL | Control-channel origin | Yes |

### 7.3 Promotion mechanisms

Five mechanisms move an assertion up the taint ladder, all logged to Hliðskjálf:

- Human explicit promotion: the operator promotes specific assertions to VOUCHED or TRUSTED with a scope and TTL. The only mechanism that applies to arbitrary content.
- Cryptographic provenance: content signed by a registered key arrives pre-trusted at the key's registered level. Revocable.
- Corroboration: multiple independent TAINTED sources asserting the same typed fact promote that specific fact (not the source) to VOUCHED at a configurable threshold.
- Temporal accumulation: a source with no anomalies over an observation window accrues trust passively toward a ceiling. Slow, for recurring known sources.
- Sandbox promotion: an action is executed in a constrained recoverable scope; a clean outcome promotes the authorising assertion for similar future actions.

A sixth, the Fenrir corroboration track, accumulates clean Fenrir runs from a single source as Muninn evidence; Odin may propose source promotion once a clean-run threshold is met, still human-approved.

---

## 8. Security architecture

### 8.1 Posture

Heimdall assumes breach. Against a sufficiently resourced targeted adversary there is no absolute defence, and the architecture does not claim one. Its guarantees are stated in two registers: against the opportunistic threat (the bulk of real attack volume) it prevents outright; against the targeted adversary it imposes cost, forces the attack onto instrumented ground, detects and reconstructs, and contains blast radius. Every prevention claim below should be read as prevented against opportunistic attackers, taxed and instrumented against targeted ones.

### 8.2 Adversary model

The attacker is assumed able to control the full content of any external input across any medium, craft content targeting known Heimdall internals, inject repeatedly and adaptively, and know the architecture in full (no security through obscurity). The targeted adversary additionally invests substantial resources and tolerates cost and exposure.

The attacker is assumed unable to: write to the canonical control channel; access the honeypot phrase or per-invocation canary token; execute code on the host outside the agent sandbox; tamper with Hliðskjálf's signature chain. These are the trust roots. Heimdall protects everything downstream of them and nothing about the roots themselves. Host security, key management and canonical-channel integrity are prerequisites, not products, of the architecture.

### 8.3 What the architecture does, by threat class

| Attack | Opportunistic | Targeted resourced |
|---|---|---|
| Prompt injection causing action (any medium) | Prevented: content never reaches the control channel | Forced onto the instrumented boundary; the action attempt is observable at emission |
| Injection via Fenrir causing action | Prevented: zero execution surface | Same; attempt introspection makes the try itself dispositive |
| Exfiltration of tainted content by an injected Fenrir | Prevented: local model on an egress-restricted segment | Prevented for this path; the adversary must defeat network segmentation or find another egress, at cost |
| Cross-invocation conditioning of Fenrir | Prevented: fresh context | Prevented: no state to condition |
| Overt output manipulation of Fenrir | Detected: output canary | Detected: canary and attempt introspection |
| Value poisoning (schema-valid, corrupted field value) | Contained: Gjöll gates action-critical values | Serious residual (section 8.5); action-critical values gated, non-critical values remain corruptible |
| Corrupted assertion driving autonomous action | Prevented: tainted assertions cannot drive action | Prevented: the promotion pipeline is the hard gate |
| Agent exceeding permissions | Prevented: control surface and trust ceiling | Prevented structurally; blast radius bounded even if the runtime is subverted |
| Tampering with the audit record | Prevented: signed append-only chain | Taxed: tampering is detectable |

### 8.4 Action-critical set sizing: the central operational discipline

The size of the action-critical set determines whether Heimdall is secure, usable or neither. Too large a set makes Gjöll fire constantly, the system fails closed on routine tasks, operators reclassify values to keep working, and the control deletes itself. Too small a set lets poisoned values flow into consequential actions ungated, and the integrity guarantee is hollow.

The discipline: the action-critical set starts empty for autonomous action and grows one capability at a time. Each time a specific autonomous consequential capability is granted, its Gjöll gate is chosen to fit that action's provenance reality. If an action has no independent-provenance channel, its gate is the promotion requirement (human or cryptographic authorisation), accepted as the cost of that autonomy. The rule: never grant an autonomous consequential capability whose integrity you cannot gate. The flow-to-sink classification keeps the set small in the common case because most flows terminate at read-only or human-gated terminals that are not sinks.

### 8.5 The value-poisoning limitation

The one attack the taint boundary does not close is value poisoning: a payload that makes Fenrir produce a schema-compliant, canary-valid, honeypot-clean output whose field values are corrupted. Grammar-constrained decoding guarantees output shape, not value truth. Taint labels answer origin, not safety. If a poisoned action-critical value is written to the world model, a fully legitimate, fully authorised, non-compromised agent will act on it, because the attack does not cross the control channel; it corrupts the premises the control channel reasons from. Writing an action-critical value is, in effect, an execution capability.

Gjöll contains this by moving the decision to a human or a key for action-critical values (section 5.2), and the poisoned-draft limit (a human reviewing an AI-drafted output can be a proxy for a poisoned value) is mitigated by provenance highlighting, by running Gjöll's checks on action-critical values in drafts and by explicit acknowledgement, without being eliminated. This is the primary open limitation of the reading path, named and partially closed, not solved.

### 8.6 The shape of adversarial findings

The strongest findings against Heimdall (value poisoning within valid grammar, multi-step state staging, alert-attention exhaustion) are all attacks on the second and third layers of defence. They presuppose the taint boundary holds, grammar-constrained decoding is in place, and attempt introspection and signed forensics exist. A direct-dispatch agent framework has none of those, so its review never reaches these findings, because the injection simply executes. That a determined review must climb three layers in to find real issues, and that what it finds is the assumed-breach residual the spec already commits to naming, is evidence the architecture is categorically ahead of the direct-dispatch baseline. Both things hold: the value-poisoning limitation is real and serious, and it is the frontier of the attack surface rather than the front door.

---

## 9. Non-functional requirements

**Latency.** The symbolic layer, Fenrir extraction and the reasoner each add per-action cost. Graph query cost (including flow-to-sink reachability) is dominated by LLM inference cost by orders of magnitude, milliseconds against seconds, so the reachability check is not on the latency-critical path. Heimdall targets batch and ingestion workloads; it is unsuitable for interactive use below 100ms (a stated non-goal).

**Availability.** The pull paradigm (Design Principle 11) makes the compute layer structurally resilient to volume-based denial: Heimdall sets its own consumption rate, unconsumed content costs nothing, and a noisy source is deprioritised or quarantined. The human layer is defended separately: genuine security escalations travel on a protected channel distinct from the bulk unclassified-triage queue, so flooding the triage queue cannot bury a real escalation; the triage queue is sampled and prioritised rather than FIFO; and a queue flood is itself a quarantine trigger. Residual: a determined adversary still imposes triage cost (risk R-4).

**Scalability.** Multiple Fenrir instances run in parallel over different content streams, independently monitored, sharing no state and coordinating only through Mímisbrunnr via Himinbjörg. The world model is the shared scaling bottleneck and the reason the store choice (Open Question 1) matters.

**Reference hardware and model (reference, not requirement).** Fenrir's guarantees derive from its structural properties (local, egress-restricted, zero-execution, fresh context, monitored), not from any specific model. A reference deployment: a DGX-Spark-class local machine (unified memory around 128GB) running a dense 30B to 80B model on an egress-restricted segment, paired with a same-family small draft model (for example an 80B target with a 7B draft) for speculative decoding. Dense is preferred over sparse MoE as a security property: MoE routing is an input-dependent variance surface, undesirable in a component whose job is resisting adversarial input. Grammar-constrained decoding and low-entropy extraction workloads both raise speculative-draft acceptance, and every token is target-verified, so the draft cannot introduce a poisoned value the target would not have produced.

---

## 10. Deployment and network architecture

The taint boundary and the network-egress boundary coincide (Design Principle 13). Tainted content is processed only by components with no egress path out of the trust boundary. This is egress control, not air-gapping: Fenrir has the internal connectivity it needs (receiving from Bifröst, writing to Mímisbrunnr) but sits on a segment under default-deny egress with an allowlist of internal peers only and no route to any external endpoint.

This makes exfiltration a network-policy guarantee rather than a discipline: a compromised Fenrir cannot phone home because its segment denies egress to anything outside its permitted peers. The rule "never send tainted content to an external API" is enforced by segmentation, because the component holding tainted content has no route to an external API in the first place. This partitions the model inventory into two non-overlapping roles: local egress-restricted models process tainted content (Fenrir), and networked API models reason only over untainted typed state (normal agents), reachable only from the untainted side. A model cannot occupy both roles.

Component placement: Bifröst, Nornir, Mímisbrunnr, Himinbjörg, Gjallarhorn, Huginn, Muninn and Hliðskjálf sit on the trusted side. Fenrir sits on the egress-restricted tainted segment. The canonical control channel and the key store (canary token, honeypot phrase, signing keys) are trust roots outside Heimdall's own guarantees and must be isolated from the ingestion surface by construction (section 8.2).

---

## 11. Build phase roadmap

All six phases at HLD depth. Phases 1 to 3 receive a full Detailed Design next; Phases 4 to 6 stay at this depth (D-3).

**Phase 1: prove the separation (target 4 to 6 weeks).** Single ingestion source (email). Hard taint boundary at Bifröst. Himinbjörg constructs agent context from the world model only. Demonstrate that a crafted injection in an email body never reaches the control channel. The action-critical set is empty for autonomous action, so Gjöll is present but dormant and nothing can fail closed. Deliverable: architectural proof of data/control separation plus read-only and human-gated email autonomy. (Largely proven already at PoC scale; Phase 1 hardens the PoC into the reference implementation on the chosen harness.)

**Phase 2: world model, reasoner and Fenrir (target +2 to 3 months).** Mímisbrunnr as a typed property graph. Nornir classifier and reasoner over the initial ontology. Causal graph operational. Hliðskjálf logging all decisions. Fenrir sandbox operational with the canary mechanism and Huginn canary monitoring. The D67-fix arming gate (R-1) is a Phase-2 obligation: it must close and be re-measured on an independent corpus before any Phase-3 consequential capability arms. Deliverable: a symbolic layer with demonstrable inference and constraint enforcement, and tainted-content processing demonstrated safe via Fenrir plus canary.

**Phase 3: full control surface (target +2 to 3 months).** The complete agent-definition schema, global defaults and overrides, the full control surface (tools, filesystem, network, credentials, inter-agent, resources, exfiltration, temporal). Gjallarhorn routing with aggregation and containment decoupled from alerting. Gjöll: flow-to-sink action-critical classification and the action-time gates. A deliberate friction test introduces exactly one autonomous consequential capability, reversible if possible, to encounter Gjöll's usability friction on purpose under controlled conditions, and to validate the flow-to-sink classifier against a real state-staging attempt. Deliverable: a complete deterministic control layer with transitive action-critical value integrity, validated against one live consequential action. This is the critical-path phase; Himinbjörg is its largest build.

**Phase 4: ingestion surface expansion (target +1 to 2 months).** Additional Bifröst parsers: web, documents, images (OCR), audio (STT). Medium blindness, so the world model receives typed assertions regardless of source medium. HLD-level only in this document.

**Phase 5: introspection framework (target +2 to 3 months).** Huginn episode capture and pattern detection, Muninn episode store, Odin operational with its first proposal types, the self-improvement loop closed. HLD-level only.

**Phase 6: promotion mechanisms (target +1 to 2 months).** Human explicit promotion, cryptographic provenance, corroboration, temporal accumulation, sandbox promotion. Full trust-lifecycle management. HLD-level only.

Inter-phase dependencies: Phase 2 depends on Phase 1's boundary; Phase 3's Gjöll depends on Phase 2's world model and flow-to-sink label; Phase 3 must not arm a consequential capability until R-1 (D67-fix) closes; Phases 4 to 6 all depend on a real Phase 1 to 3 core.

---

## 12. Risk register

Every open item, with status, the phase that owns it and the mitigation or tracked gate.

| # | Risk | Status | Owner phase | Mitigation or gate |
|---|---|---|---|---|
| R-1 | False-inert classification break (D67); a consequential message earns an inert signal and skips the gate | OPEN, measured 1/16 on an independent corpus, suite deliberately red | Phase 2 | Tracked arming gate: no autonomous consequential capability arms until D67-fix closes and is re-measured on a genuinely independent corpus (D-2). Fix must be a design change, not more keywords. |
| R-2 | Ontology coverage is a self-authored four-domain seed; breadth untested, no independent-labelled corpus | OPEN | Phase 2 onward | Coverage grows demand-driven from captured gaps; unclassifiable content fails closed to review; build a genuinely independent adversarial corpus (the highest-information next artefact). |
| R-3 | Odin feedback-loop poisoning; a patient adversary shapes the episode stream Odin learns from | OPEN (partial) | Phase 5 | Human approval backstop; deferred hardening: independent evidence sampling, anomaly-aware weighting, requiring CANONICAL or human-VOUCHED evidence for any control relaxation. Odin may never propose changes to its own definition. |
| R-4 | Review-queue flooding, human layer; a flood of edge-case-unclassifiable content blinds operators | OPEN (partial) | Phase 3 to 5 | Protected escalation channel separate from bulk triage; sampled prioritised queue; queue flood is itself a quarantine trigger. Residual: triage cost still imposed. |
| R-5 | Forced-misclassification suppression; obscuring a legitimate high-priority signal so it dumps to UNCLASSIFIED and suppresses response | OPEN (partial, named) | Phase 2 to 4 | Recognise critical inbound types by source and channel provenance not only content; route UNCLASSIFIED from high-trust sources to the protected channel; age critical-source unclassifiables upward. Residual: a fully attacker-controlled non-protected source can still delay response. |
| R-6 | Value poisoning; a schema-valid corrupted action-critical value drives an authorised action | SERIOUS, named, partially closed | Phase 3 | Gjöll gates action-critical values at action time; the load-bearing gate is the promotion requirement (human or key). Non-action-critical values remain corruptible. Containment, not elimination. |
| R-7 | Sink and flow declarations are unattested trusted input (`consumes` is an unchecked dict); the root of the Gjöll guarantee | OPEN | Phase 3 | DD must specify a signed sink-declaration schema with gate-boundary validation. Named "the root" in `ADVERSARIAL_REVIEW.md` 5.1. Lead the DD with it. |
| R-8 | Himinbjörg is the single largest unbuilt piece and the Phase-3 critical path | SPECIFIED-ONLY | Phase 3 | DD leads with Himinbjörg; reuse Gleipnir's proven permission-map and deny-by-default pattern (D-1). |
| R-9 | Small-model extraction quality; a weak Fenrir's honest error is hard to separate from injection | OPEN (D34) | Phase 2 / 5 | Huginn baselining is the proposed mechanism; discriminating features unspecified. Fail-closed default makes the gap safe meanwhile. |
| R-10 | Mixed-trust-source re-stamping; a trusted document quoting an untrusted source | OPEN | Phase 4 | Named seam (`ADVERSARIAL_REVIEW.md` 5.9); unaddressed. Owner phase is the ingestion expansion that introduces multi-part documents. |
| R-11 | Ørlög documentation inconsistency; `GLOSSARY.md` names a configuration-substrate component absent from the architecture and the audit | OPEN (documentation defect) | Pre-Phase-1 housekeeping | Recorded, not silently resolved (D-5). The operator decides whether Ørlög is a real intended component to add to `HEIMDALL.md` or a stale glossary entry to remove. |
| R-12 | Control-channel or trust-root compromise | OUT OF SCOPE by design | n/a | If breached, Heimdall offers nothing, by design. Carried by non-Heimdall controls (host security, HSM-backed keys, canonical-channel isolation). |

---

## 13. Traceability appendix

Mapping from HLD section to the authoritative sources, so a reader can verify this HLD did not silently diverge.

| HLD section | HEIMDALL.md source | DECISIONS.md / other |
|---|---|---|
| 2 System context | Problem Statement; Design Principles 1 to 3 | |
| 3 Achievement baseline | (evidence audit) | `plans/hld_scoping_brainstorm.md` Part A; `STATUS.md`; `poc/`, `spike/substrate/`, `ontology/` code |
| 4.1 to 4.2 Architecture | Architecture diagram; component flow | |
| 4.3 Harness Boundary Interface | Harness Integration (pi.dev hooks); Open Question 4 | D-1, D-4 |
| 5.1 Himinbjörg | Himinbjörg; Agent Definitions | D-1; R-8 |
| 5.2 Gjöll | Gjöll; Action-Critical Set Sizing | D58; R-6, R-7 |
| 5.3 Bifröst | Bifröst | Invariants 3.2, 3.3; R-10 |
| 5.4 Nornir | Nornir | D-2; D31, D52, D54, D55, D69, D67; R-1, R-2 |
| 5.5 Gjallarhorn | Gjallarhorn; Alert aggregation | |
| 5.6 Fenrir | Fenrir; canary mechanism; attempt introspection | Invariant 3.8; R-9 |
| 5.7 Mímisbrunnr | Mímisbrunnr; latency note | D25, D32, D38, D57; Open Question 1 |
| 5.8 Hliðskjálf | Hliðskjálf | Invariant 3.10 |
| 5.9 Huginn | Huginn and Muninn | D34; R-9 |
| 5.10 Muninn | Huginn and Muninn | |
| 5.11 Odin | Odin; Odin hardening note | Open Question 3; D35; R-3 |
| 5.12 Yggdrasil | Nornir ontology composition | D29, D39, D40; `ONTOLOGY_CONSTRUCTION.md`; R-2 |
| 6 Data architecture | Mímisbrunnr node properties; causal graph | |
| 7 Trust and promotion | Trust and Promotion Model | |
| 8 Security architecture | Threat Model; value poisoning; action-critical sizing | R-6, R-12 |
| 9 Non-functional | latency note; pull paradigm; Fenrir implementation notes | Open Question 1 |
| 10 Deployment | Design Principle 13; taint/egress coincidence | |
| 11 Build roadmap | Build Phases | D-3 |
| 12 Risk register | Residual risks; Open Questions | R-1 to R-12 |

---

## Licence

This design document is part of the Heimdall specification and is licensed under CC-BY-SA-4.0, consistent with the repository. See `LICENSE.md`.
