# Heimdall: Decision Log

**Author:** Jason Huxley
**Version:** 1.0
**Date:** August 2026
**Status:** living log of design and build decisions
**Reads with:** `HEIMDALL.md`, `NEUROSYMBOLIC_FILTER_INVARIANTS.md`, `ONTOLOGY_CONSTRUCTION.md`, `poc/OUTCOME.md`

---

## 1. Purpose

This log records every material decision taken across the premise PoC and the design work that followed, so the design can be checked for internal consistency and so no acceptance obligation is left without an owner. Each decision has a stable identifier, a status, the rationale, where it is realised, and its dependencies. A decision that contradicts another, or a test obligation with no owning phase, is meant to be visible here rather than discovered late.

**Status values:**

- **SETTLED** decided and realised (in code, in a document, or as a fixed design choice).
- **SPIKE-GATED** decided in principle, ratification pending a defined spike with pass criteria.
- **DEFERRED** deliberately not decided yet, with a recorded trigger that will force it.
- **OPEN** a named question that bears on the design and is not yet resolved.

**How to verify the design from this log:** every SETTLED decision should have a realisation reference; every SPIKE-GATED and DEFERRED decision should have a trigger and an owning phase; no two SETTLED decisions should conflict; every acceptance obligation in the invariants doc should trace to a decision here. Section 6 records the consistency checks.

---

## 2. PoC decisions (settled and realised in code)

| ID | Decision | Status | Rationale | Realised in |
|----|----------|--------|-----------|-------------|
| D01 | Python runs in a venv, never the host interpreter | SETTLED | Avoid version conflicts on the M5; reproducibility | `poc/.venv`, `poc/README.md` |
| D02 | Symbolic layer contains no language model, verified by AST inspection each run | SETTLED | A model in the classifier is itself injectable; the whole guarantee is void otherwise | `poc/symbolic.py`; invariant 3.1 |
| D03 | Trust assigned by origin at a single boundary, stamped before content-sensitive parsing | SETTLED | Provenance not content is the trust signal | `poc/symbolic.py`; invariant 3.2 |
| D04 | Data boundary must not be forgeable by content; out-of-band token-level framing | SETTLED | String delimiters were forged (`extract-13`); a boundary a payload can contain is not a boundary | `poc/neural.py`; invariant 3.3 |
| D05 | Payload encoded with `split_special_tokens=True`, plus deterministic `<\|...\|>` neutralisation in the symbolic layer | SETTLED | Payload control-token strings were promoted to real control tokens, forging a role boundary; two independent mitigations | `poc/neural.py`, `poc/symbolic.py`; invariant 3.3 |
| D06 | Input assertion verifies the exact token-id prompt per field, not a partial reconstruction | SETTLED | The first check verified a string the model never received | `poc/harness.py`; invariant 3.4 |
| D07 | Never detect injection by scanning output content; the n-gram/imperative heuristic was tried and rejected | SETTLED | It failed 11 cases including a clean control; a summary must be able to quote its source; a content classifier is injectable | `poc/harness.py` history; invariant 3.5 |
| D08 | Output assertion is structural inertness: schema conformance, no action-capable field, provenance-gated sinks | SETTLED | Content of a field is irrelevant if nothing acts on it | `poc/harness.py`; invariant 3.6 |
| D09 | Every extraction field is `UNTRUSTED_DERIVED`; a sink consuming one as an action fails the assertion | SETTLED | The model only ever read untrusted data | `poc/neural.py`, `poc/sinks.py`; invariant 3.6 |
| D10 | Sink experiment wires both a safe sink and an unsafe control; the unsafe control must be caught | SETTLED | A green board with only safe wirings is trivial; the control makes the pass meaningful | `poc/sinks.py`, `poc/harness.py`; `poc/OUTCOME.md` section 5 |
| D11 | Safety properties tested at more than one decoding temperature (0.0 and 0.7) | SETTLED | A property that holds only at temperature 0 is an accident of decoding | `poc/harness.py --temp`; invariant 3.9 |
| D12 | The harness is an audit artefact; failures are loud; clean and unsafe controls mandatory | SETTLED | A pass proves nothing without a control that would fail | `poc/harness.py`; invariant 3.10 |
| D13 | Model identifier is a single swappable constant | SETTLED | Boundary guarantees are per model family and must be re-verified on swap | `poc/neural.py` `MODEL_ID`; invariant 3.7 |

---

## 3. Documentation and framing decisions (settled)

| ID | Decision | Status | Rationale | Realised in |
|----|----------|--------|-----------|-------------|
| D14 | Extract PoC findings and limits into a live-build document | SETTLED | The PoC's value is the requirements it retires and bounds | `NEUROSYMBOLIC_FILTER_INVARIANTS.md` |
| D15 | Name that document for the mechanism, at repo root, not `REQUIREMENTS.md` | SETTLED | It is the invariant set for one mechanism (the neurosymbolic filter), not the whole project's requirements | `NEUROSYMBOLIC_FILTER_INVARIANTS.md` |
| D16 | Three status marks for invariants: PROVEN, DEMONSTRATED, NOT YET TESTED | SETTLED | Distinguish structurally proven from bounded from wholly untested | invariants doc section 1 |
| D17 | Ontology framework named Yggdrasil, framed as Phase-1 seed only | SETTLED | The glossary reserves Yggdrasil for exactly this; the myth mirrors the role; marked future so no overclaim | `ONTOLOGY_CONSTRUCTION.md` |
| D18 | Ontology construction methodology is its own root doc, referenced by invariant 3.11 | SETTLED | Invariants are the what; construction is the how; keep them separate | `ONTOLOGY_CONSTRUCTION.md`, invariant 3.11 |
| D19 | This decision log exists and is maintained | SETTLED | Track choices for consistency and ownership | this file |

---

## 4. Ontology construction decisions

| ID | Decision | Status | Rationale | Realised in / trigger |
|----|----------|--------|-----------|-----------------------|
| D20 | Ontology holds action/constraint **vocabulary** only; per-agent **binding** lives in Himinbjörg's control surface | SETTLED | Correction to an earlier error: action and constraint spaces are agent-specific in binding, shared in vocabulary (HEIMDALL.md principle 5) | `ONTOLOGY_CONSTRUCTION.md` section 2.3 |
| D21 | Two orthogonal axes of variation: by-domain (in Yggdrasil), by-agent (in the control surface) | SETTLED | An agent spans domains; a domain is touched by many agents; coupling them fragments the design | section 2.1 |
| D22 | Domains are subject-matter, not medium; parser sets taint class, domain layer sets type | SETTLED | Medium-blindness requires the same fact to type identically regardless of source medium | section 2.4 |
| D22a | Threat surface is any external content an LLM agent reads (web, social media, documents, tool output), not email; email is only the Phase 1 staging medium | SETTLED | Correction: the PoC used email but web and social content are the larger, less-structured attack surface; framing the ontology around email biases the design | section 2.4, section 4 |
| D23 | Domain layers extend the shared upper ontology; never redefine general types | SETTLED | Cross-domain facts relate through common ancestors; prevents dialect drift | section 2.2 |
| D24 | Action-critical status is agent-scoped, computed against a given agent's reachable sink set | SETTLED | Follows from D20; a value can be action-critical for one agent and inert for another | section 2.5, section 8.4 |
| D25 | Substrate: property graph (Memgraph) for store and reasoning | SPIKE-GATED | Flow-to-sink reachability favours write-time incremental labels over authorisation-time SPARQL path queries | section 3; spike criteria in 3.3; Phase 2 |
| D26 | Coverage growth: hand-authored now, Odin-proposed later | SETTLED | Sound and auditable early; automated scaling later, gated | section 7 |
| D27 | Odin's proposal path is provenance-gated: proposals are untrusted until human ratification, never auto-apply | SETTLED | Odin's proposals derive from tainted content; the ontology is the classifier; ungated this reintroduces the injectable-classifier problem one level up | section 7.2 |
| D28 | Marshalling: grammar derived from ontology types; interpretive tasks become single opaque `INTERPRETIVE_SUMMARY`; no second LLM pass | SETTLED | A second model reading the first's output reopens the injection surface | section 5 |
| D29 | Phase-1 ontology built to pass two attach tests: a second medium feeds existing types, and a second subject-matter domain attaches without editing the first or the spine | SETTLED | If either extension forces a change to what exists, the layering is wrong; the medium attach test is the one most easily forgotten because email arrives first | section 4.2 |
| D30 | Flow-to-sink tests are agent-scoped and cross-domain; state-staging across a domain boundary is mandatory | SETTLED | Reachability is global across domains and parameterised by agent permission | section 8.4 |
| D38 | Upper ontology: load BFO as the spine (confirmed by a Phase 2 spike); keep SUMO as an unloaded reference library to prune domain types from | SPIKE-GATED | SUMO's breadth is not wanted loaded: under invariant 3.11 loaded coverage is trust-boundary surface that must be tested, so 25,000 untested terms is a liability; the filter needs typed inertness not SUMO's semantic richness; and coverage should grow demand-driven (D26) not be front-loaded. SUMO's domain ontologies remain valuable as a source to import-and-prune when extending coverage, capturing the head-start without the untested-surface cost | `ONTOLOGY_CONSTRUCTION.md` section 3.4; Phase 2 |

---

## 5. Deferred and open items

| ID | Item | Status | Trigger / owning phase | Recorded in |
|----|------|--------|------------------------|-------------|
| D31 | Domain ontology governance: single curated modules vs federated with a conformance harness | DEFERRED | Forced when a second domain arrives (Phase 4) or a second owning team appears | `ONTOLOGY_CONSTRUCTION.md` 10.1 |
| D32 | Edge-deletion label retraction in the flow-to-sink graph | OPEN | Substrate spike pass criterion (D25); Phase 2 | 10.2; HEIMDALL.md open question 1 |
| D33 | Constrained decomposition grammar for interpretive tasks | OPEN | If opaque `INTERPRETIVE_SUMMARY` proves too coarse; Phase 2+ | 10.2; HEIMDALL.md open question 6 |
| D34 | Huginn's discriminating features: honest extraction error vs injection-induced error | OPEN | Needed for the classification-correctness corpus (8.2); Phase 2/5 | 10.2; HEIMDALL.md open question 7 |
| D35 | Odin self-modification (propose changes to its own definition) | OPEN | Currently excluded; circular self-modification is an open research problem | HEIMDALL.md open question 3 |
| D36 | Cross-harness portability (pi.dev primary, OpenCode secondary) | DEFERRED | Post-Phase 1 abstraction-layer design | HEIMDALL.md open question 4 |

---

## 6. Consistency checks

Recorded so the design can be audited against itself. Re-run these when a decision changes.

1. **No SETTLED conflict.** D20 (vocabulary in ontology, binding in control surface) and D24 (agent-scoped action-critical) are mutually consistent: agent scoping is the reason binding is not in the ontology. D22 (subject-matter not medium) and D22a (threat surface is all external content, not email) reinforce each other: both say the medium is not the type. No conflict found.
2. **Every acceptance obligation has an owner.** The four obligations in invariant 3.11 map to D25/D32 (substrate and retraction), D26/D27 (growth), D28 (marshalling) and D30 (flow-to-sink testing), all with owning phases in `ONTOLOGY_CONSTRUCTION.md` section 9. No orphan obligation.
3. **Every NOT YET TESTED invariant has a construction path.** Invariants 3.6 (action-critical half), 3.9 (coverage bound) and 3.11 trace to D20 to D30, D38 and the phase mapping. No untested invariant lacks a build route.
4. **Every DEFERRED and OPEN item has a trigger.** D31 to D36 each record a trigger or owning phase, and the SPIKE-GATED items D25 and D38 have Phase 2 spikes. None is deferred without a condition that forces it.
5. **The PoC decisions carry into invariants.** D02 to D13 each map to an invariant (3.1 to 3.10). No proven PoC property is dropped.
6. **Threat surface is not narrowed by the staging choice.** D22a records that starting with email (a staging decision) does not narrow the threat model to email; D29's medium attach test enforces that web and social media attach as media feeding existing types, so the ontology cannot silently become email-shaped. Checked against `ONTOLOGY_CONSTRUCTION.md` sections 2.4 and 4.

**Known residual risk this log makes explicit:** the strongest live guarantee (structural separation, D02 to D09) is fully proven, but the guarantee's *extent* depends on ontology coverage (D25 to D30), which is NOT YET TESTED and gated on Phase 2/3 work. The design is sound in mechanism and unproven in coverage. That is the honest state.
