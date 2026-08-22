# Heimdall synthesis: capability-mapping matrix

**Author:** Jason Huxley (recorded by AETOS orchestrator session)
**Date:** August 2026
**Version:** 1.0
**Status:** Input artefact for a future synthesis architecture. Not a build plan.

---

## 1. Purpose

Heimdall's proven neurosymbolic core is one of three inputs to the eventual production autonomous agent. The other two, AETOS and Gleipnir, are under active development and will keep inventing capabilities Heimdall does not yet have. This document is the capability-mapping matrix that resulted from a working session reconciling the three: what each contributes, which of Gleipnir's and AETOS's capabilities Heimdall absorbs, in what form, and the structural rulings that resolve the tensions between them. It is deliberately the input to a later synthesis architecture document, not the architecture itself.

## 2. The governing constraint: Rust, not Python, at runtime

Heimdall's production runtime will be compiled Rust, not Python. The reasoning is architectural, not a language preference: an interpreted deterministic core is reachable by the population it is meant to guard, because its source is mutable in place and its running state can be rewritten (monkey-patching, module swaps) without recompilation. This is Gleipnir's Axiom Two (a guard must not be reachable, forgeable or blindable by the population it guards) applied to the implementation substrate itself, not just to configuration and evidence.

Gleipnir's own enforcement core is stdlib-only Python, dependency-free by policy, but still mutable at the interpreter level. Its own defence against this is filesystem-level (read-only mounts, OS access-control lists), an external cage bolted around a mutable core. A compiled Rust binary makes the determinism boundary intrinsic to the artefact rather than mounted around it. This directly strengthens Heimdall's own design principle that determinism is a property of the boundary, and closes the reachable-guard seam at the substrate level rather than relying on deployment-phase container hardening.

The consequence for absorbing Gleipnir's capabilities: Gleipnir's Python is treated as a reference specification, in the same way Heimdall already treats the GPL-licensed SUMO ontology as reference-only and never loads it directly. Gleipnir's enforcement semantics are re-expressed natively in Rust; its code is read to understand behaviour, not imported or wrapped.

The one component that cannot be compiled away is the large language model itself, which remains the sole probabilistic, non-deterministic element. It is held outside the boundary by construction: the compiled Rust core calls the model over a defined interface (a local server or a remote API), and everything that adjudicates the model's output is compiled and immutable. The Rust and non-Rust line is, by design, the same line as the data and control channel separation that is Heimdall's founding thesis.

## 3. What each input contributes

| Input | Contributes | Nature | Substrate rule |
|---|---|---|---|
| Heimdall (proven core) | The boundary: data and control channel separation, the Nornir symbolic classifier, Fenrir, Gjöll, the neurosymbolic filter invariants | Runtime core | Rust-compiled |
| Gleipnir | Mechanism: enforcement semantics (the process plane) | Runtime core | Re-expressed in Rust; Python is reference-only |
| AETOS | Shape: cohort structure, GOTCHA and ATLAS discipline, deterministic-control patterns (the output plane) | Development-time and shape-informing | Language-agnostic patterns, not shipped code |
| Large language model | Cognition | External service | Non-Rust by nature; behind a Rust client, outside the boundary |

Gleipnir is not an independent third input in the same sense as AETOS. Gleipnir exists because AETOS's guards were found sound against an honest agent tripping them by accident and unsound against an agent working their seams deliberately: AETOS's guards assume their own subjects will not attack them. Gleipnir is a hardening programme on top of AETOS's shape, not a second, competing shape. Heimdall inherits AETOS's cohort and output-control catalogue, and Gleipnir's hardened enforcement mechanism, rather than choosing between two competing enforcement philosophies.

## 4. The four control planes

Two axes of constraint turned out to be orthogonal rather than competing, once distinguished precisely: AETOS constrains what a language model produces in a single step (its output); Gleipnir constrains the order in which steps are allowed to happen (the process). An autonomous production agent needs both, and they do not compete because they adjudicate different things. Together with the structural question of which predefined agents compose and how, and the external cognition call itself, this gives four control planes.

| Plane | Constrains | Shape inherited from | Realised in Heimdall by | Substrate |
|---|---|---|---|---|
| Output | The model's per-step output: a value, an action, a claim | AETOS output controls | Nornir, the Fenrir canary, and Gjöll (the existing boundary) | Rust |
| Process | The workflow sequence across steps within a goal | Gleipnir's G-5 engine | A state-machine engine, resident in Himinbjörg | Rust |
| Hierarchy | Which predefined actors compose, and how instances spin up per goal, at every altitude from a single agent to a fleet of Heimdall instances | The AETOS, HADES, ARGUS and RECALL roster model, extended with new tiers | The agent registry, the cohort catalogue, the privileged resident coordinator, and inter-instance delegation | Rust |
| Cognition | The reasoning itself | Not inherited; irreducibly probabilistic | The external large language model, called through a Rust client | External |

The output plane and the process plane are both kept and both compiled; neither supersedes the other. The output plane says a given value or action is not safe. The process plane says a given step is not permitted here, or not yet.

## 5. What Heimdall is

Heimdall is the compiled, deterministic autonomous-agent substrate: the runtime that safely runs cohorts, not itself a cohort. Sibling projects each define their own cohort: AETOS is a development cohort, HADES an open-source-intelligence cohort, ARGUS a reconnaissance cohort, and RECALL a data-extraction-and-presentation cohort. Each of these is a tenant expressed on the Heimdall substrate, not a peer architecture Heimdall must choose between.

The determinism invariant that makes this safe: every agent definition is predefined and attested. There are no ephemeral agents. What can be ephemeral is a cohort instance, meaning a running orchestrator bound to a specific goal, composed from predefined agents drawn from a predefined cohort definition in a catalogue. Structure is never decided at runtime; only which predefined structure to instantiate for a given goal is decided at runtime. This is a deliberate departure from ephemeral-agent styles of agentic design, made in service of determinism rather than in ignorance of the alternative.

Within a single Heimdall instance there is also a privileged resident structure: a coordinator, with its own supporting cohort, that is always present rather than instantiated per goal. Its job is overarching coordination of long-running work that spans multiple goals: decomposing a durable objective, selecting which cohorts to instantiate from the catalogue and in what order, and holding continuity across them. This tier is privileged rather than uniform with the goal cohorts it manages, and Axiom Two therefore applies to it hardest of all: its configuration, code and evidence must sit at a strictly lower, agent-unreachable enforcement surface than anything it coordinates.

The structural hierarchy, in full, with the master-control tier explicitly named as a later phase rather than dropped:

```
[Later phase] Master control entity
    delegates to independent, predefined Heimdall instances

Heimdall instance (the Rust substrate)
    Resident coordinator and supporting cohort   (privileged; multi-goal continuity)
    Cohort catalogue                              (predefined cohorts, instantiated from)
        ephemeral cohort instance, per goal
            = predefined orchestrator plus predefined sub-agents
    Predefined agent registry                     (immutable, attested atoms)
    The boundary: Nornir, Fenrir, Gjöll, the process engine
        wraps every tier above it
```

## 6. Caging default

Gleipnir's own current posture is uncaged by default: it treats the single human at the terminal as a trusted owning principal, and caging is an opt-in mode reached through a runbook. That default is correct for Gleipnir's attended, single-principal case. It is the wrong default for Heimdall. An autonomous production substrate cannot assume a trusted human is present at every terminal every time it runs, so Heimdall inverts Gleipnir's default: caged by default, with guard configuration, guard code and the agent registry unreachable from the agent surface as the standing state. Uncaging, where it is ever needed, becomes the reviewed, deliberate exception, not the default.

## 7. The absorption seam

Both AETOS and Gleipnir are under active development, so Heimdall must stay open to capabilities neither project has invented yet, without a rewrite each time one lands. The four-plane structure gives this an explicit home rather than leaving it implicit: a new capability lands as one of exactly three kinds of extension, never as a fork of the substrate.

- A new predefined agent or cohort added to the catalogue (the hierarchy plane).
- A new output-plane check, realised through Nornir, Fenrir or Gjöll (the output plane).
- A new process-plane transition, realised in the state-machine engine (the process plane).

## 8. Capability matrices

Four judgment columns recur throughout: disposition (keep, adapt, defer, drop or reference), plane, substrate and any open tension. Substrate values are Rust (compiled into the artefact), external (called over an interface), development-time (used to build Heimdall but not shipped in it), or not applicable.

### 8.1 Matrix A: Gleipnir, mapped to the process plane and substrate hardening

| Item | Capability | Disposition | Plane | Notes |
|---|---|---|---|---|
| G1 | Axiom Two: a guard must not be reachable, forgeable or blindable by the population it guards | Keep | All | The meta-principle; applies hardest to the privileged resident coordinator |
| G2 | The G-5 engine: a data-driven transition table, code-enforced loop caps, a human-question gate with no outgoing edge until answered | Adapt, re-express in Rust | Process | The core of Himinbjörg's process plane |
| G3 | The G-3.1 keyed verification marker: an HMAC over a tree or source hash, fail-closed, mintable only by the verifier key | Adapt, re-express in Rust | Process, hierarchy | Attests agents and cohorts at load |
| G4 | G-3.2, binding a completion claim to a live attestation | Defer; named seam even inside Gleipnir | Process | Specified but not wired even in the source project |
| G5 | The G-4 typed, append-only event bus | Adapt, re-express in Rust | All | Reconcile with Heimdall's own signed Hliðskjálf chain and Huginn capture rather than duplicating it |
| G6 | The G-4d honest metrics ledger, distinguishing measured from estimated values, with a digest-protected rate table | Adapt, re-express in Rust | All | A strong fit with Heimdall's existing honesty-over-reassurance discipline |
| G7 | The S-2 fail-closed execution sandbox: container-runtime detection, no network, a read-only mount, no host fallback | Adapt, re-express in Rust and an external runtime | Output | Overlaps Fenrir's own sandbox; the two must be unified or explicitly scoped apart, not built twice |
| G8 | S-3 boundary preflight, described in Gleipnir as a guard on the guards, fail-closed, no session starts without it | Keep, re-express in Rust | All | Becomes Heimdall's own launch-time boundary verification |
| G9 | The single-holder credential broker: exactly one role holds push and application programming interface credentials, running outside the boundary | Adapt, re-express in Rust and an external runtime | Output, hierarchy | Maps to Heimdall's own credential-brokering and actuator layer |
| G10 | G-1 caging: guard paths unwritable, and the verification key unreadable, from the agent surface | Keep, re-express in Rust; default inverted | All | Gleipnir defaults uncaged for its attended case; Heimdall defaults caged, per section six above |
| G11 | G-2: forbidden actions are removed as a capability rather than detected by inspecting use | Keep, re-express in Rust | Output | Echoes Heimdall's own anti-blacklist invariant |
| G12 | G-6: review-gated persistent memory, built so memory cannot be poisoned | Adapt, re-express in Rust | Output, hierarchy | Reconcile with Mímisbrunnr and Heimdall's existing promotion policy |
| G13 | Configuration and agent-content scanning, wired into a pre-commit hook and continuous integration | Defer | Development-time | Largely a build-time concern; may not apply to a sealed, compiled binary |
| G14 | The cognition layer: a two-gate mechanism distinct from G-5 sequencing | Defer, re-express in Rust | Process | The newest and still-evolving Gleipnir work; a strong first candidate for the absorption seam |
| G15 | The spec section spine (parts G, S, T, L, K, C and D) | Reference | Development-time | A documentation convention, not a shipped mechanism |
| G16 | The stdlib-only, zero-dependency discipline on the enforcement core | Keep as a principle | All | Rust analogue: a minimal, audited set of crates on the enforcement path |

### 8.2 Matrix B: AETOS, mapped to the output plane and hierarchy shape

| Item | Capability | Disposition | Plane | Notes |
|---|---|---|---|---|
| A1 | The GOTCHA six-layer separation: goals, orchestration, tools, context, hard prompts and args | Reference | Development-time | Informs Heimdall's own internal separation of concerns; the product is not itself built on GOTCHA directories |
| A2 | The ATLAS five-step build discipline: architect, trace, link, assemble, stress-test | Reference | Development-time | The methodology used to build Heimdall, not a shipped component |
| A3 | A fixed, permission-scoped sub-agent cohort, coordinated by an orchestrator through delegation | Keep, generalised, re-express in Rust | Hierarchy | Generalised beyond a single roster: many cohorts exist across sibling projects, and Heimdall is the substrate that runs them |
| A4 | The one-verb-per-delegation discipline | Adapt, re-express in Rust | Hierarchy | Becomes a compiled delegation constraint rather than a written convention |
| A5 | A model matrix assigning cheaper or more capable models by task type | Adapt | Cognition | Per-task model choice, configured behind the Rust client |
| A6 | Deterministic controls and fail-closed hooks on agent behaviour, with fail-safe defaults and an audit log of every block | Keep, re-express in Rust | Output | Treated as the catalogue of what must be controlled on output; the mechanism that controls it is Gleipnir's, not duplicated from AETOS |
| A7 | Compaction survival: re-injecting critical guardrails after context loss | Adapt, re-express in Rust | Process | In a compiled orchestrator this becomes state the coordinator owns directly, not a re-injected plugin |
| A8 | Verification before completion: no claim of done without evidence produced in the same turn | Keep, re-express in Rust | Output | A compiled gate, not a written instruction the model might ignore |
| A9 | Replacing a language-model-driven polling loop with a deterministic one that returns a fixed set of terminal verdicts | Keep, re-express in Rust | Process | The template for every place the product would otherwise let the model drive a loop itself |
| A10 | Read-only reviewer roles kept as distinct agents from the roles that edit | Adapt, re-express in Rust | Hierarchy | Applies wherever the hierarchy plane defines review-type predefined agents |
| A11 | Secrets scanning, branch protection and a merge-request gate | Adapt or drop, depending on scope | Development-time | Largely a software-development workflow concern; a running autonomous agent may never touch a source-control system at all |
| A12 | The seven Model Context Protocol packages providing memory, git, project management, notification and code-graph services | Reference, mostly drop | Development-time | Model Context Protocol is runtime plumbing specific to the development environment; the underlying capabilities, such as memory and notification, may reappear as native Rust modules, never as Model Context Protocol servers, in the shipped product |
| A13 | The Go command-line installer | Drop | Not applicable | Tooling for installing AETOS itself, with no analogue needed in Heimdall |
| A14 | Choosing, per control, whether it should fail open or fail closed | Keep as a principle | Output, process | Each control in Heimdall must make this choice explicitly rather than by accident |
| A15 | The thesis that autonomy is set by the scaffolding built around a model, not by the model's own capability | Keep as a principle | All | The idea that justifies building Heimdall as a substrate at all |

### 8.3 Matrix C: Heimdall's existing core, mapped to the boundary

| Item | Capability | Disposition | Plane | Notes |
|---|---|---|---|---|
| H1 | Data and control channel separation | Keep | All | The founding thesis |
| H2 | The Nornir symbolic classifier and the Yggdrasil ontology | Keep, re-express in Rust | Output | Reimplemented from the Python proof of concept; the ontology becomes compiled data |
| H3 | The Fenrir tainted-content sandbox | Keep, re-express in Rust and an external runtime | Output | Unify with Gleipnir's G7 rather than building two sandboxes |
| H4 | The Gjöll action-time gate and flow-to-sink reachability | Keep, re-express in Rust | Output | Invoked from within the process-plane engine |
| H5 | The neurosymbolic filter invariants, including no model on the classification path and the anti-blacklist discipline | Keep, re-express in Rust | All | Rust compilation makes the no-model-on-the-path invariant structurally trivial to hold, rather than merely policed by review |
| H6 | The Himinbjörg control surface | Build, in Rust | Process, hierarchy | Currently unbuilt; the critical path to a live system, and the natural home for Gleipnir's engine, the resident coordinator, and the credential broker |
| H7 | The large language model as an untrusted subroutine that only proposes | Keep | Cognition | Called externally, behind the Rust client |

### 8.4 Matrix D: new synthesis capabilities with no single parent project

| Item | Capability | Disposition | Plane | Notes |
|---|---|---|---|---|
| N1 | A predefined agent registry of attested atoms | Build, in Rust | Hierarchy | The determinism floor: nothing runs that was not predefined and attested |
| N2 | A cohort catalogue that is instantiated from, never invented at runtime | Build, in Rust | Hierarchy | The mechanism behind "predefined agents, ephemeral cohort instances" |
| N3 | A privileged resident coordinator and its supporting cohort | Build, in Rust | Hierarchy | The highest-protected tier; multi-goal continuity across a Heimdall instance's lifetime |
| N4 | Ephemeral instantiation of a cohort, bound to a single goal | Build, in Rust | Hierarchy | Only the instance is ephemeral; the structure it instantiates is not |
| N5 | A master-control entity delegating to multiple independent Heimdall instances | Defer; designed for, not built | Hierarchy | A later phase; a single instance with its resident coordinator is the first buildable target |
| N6 | An explicit absorption seam for capabilities neither AETOS nor Gleipnir has invented yet | Build, in Rust | All | Every new capability lands as a catalogue entry, an output-plane check, or a process-plane transition, never as a fork |
| N7 | A Rust client interface to external large language model inference | Build, in Rust | Cognition | The Rust and non-Rust line is the data and control channel line |

## 9. Open items carried forward, not resolved here

- Whether Gleipnir's execution sandbox (G7) and Fenrir's content sandbox (H3) become one mechanism serving two purposes, or two mechanisms with an explicitly stated boundary between them.
- Whether the memory and notification capabilities named in A12 reappear as native Rust modules inside Heimdall, or are dropped entirely in favour of capabilities the sibling cohort projects bring themselves.
- The exact contract for the absorption seam named in section seven: what a new catalogue entry, output check or process transition must supply to be accepted, and who or what reviews it before it is compiled in.
- The master-control and multi-instance tier named in section five and item N5: designed for, explicitly deferred, not scoped further here.

## 10. Rulings recorded in this session

- The production runtime is compiled Rust. No Python, and no other interpreted language, sits on the determinism boundary.
- The large language model is called as an external service behind a Rust client, never embedded in the compiled artefact.
- Gleipnir's Python enforcement core is treated as a reference specification, re-expressed natively in Rust, on the same footing as Heimdall's existing treatment of the SUMO ontology.
- AETOS's output controls and Gleipnir's process controls are orthogonal and both kept; neither supersedes the other.
- The sub-agent cohort pattern is generalised: Heimdall is the substrate that runs many predefined cohorts, including but not limited to AETOS's own development cohort, HADES, ARGUS and RECALL.
- Every agent definition is predefined and attested; only cohort instances are ephemeral.
- The resident multi-goal coordinator is a privileged, always-present structure, not one predefined cohort among equals in the catalogue.
- A master-control tier delegating across multiple independent Heimdall instances is in scope for a later phase, not the first buildable target.
- Heimdall defaults to caged, inverting Gleipnir's own uncaged-by-default posture, because an autonomous substrate cannot assume a trusted human is present at every terminal.
