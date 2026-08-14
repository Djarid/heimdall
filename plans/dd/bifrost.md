# Detailed Design: Bifröst (taint boundary)

**Author:** Jason Huxley
**Date:** August 2026
**Version:** 0.1 (draft)
**Phase:** 1
**Status of the component today:** demonstrated at proof-of-concept shape for one medium (email), per `plans/hld.md` section 3. See `poc/symbolic.py`.

---

## 1. Purpose

Bifröst is the single point at which external content enters Heimdall. Its job is to turn raw external content of any medium into typed, provenance-stamped, tainted assertions, and to guarantee that nothing crosses raw. It is the component that makes Phase 1's point: a crafted injection in an email body never reaches the control channel, because the body is quarantined as data at the crossing and is never an instruction.

This document takes Bifröst to implementation fidelity for Phase 1 (email), and specifies the parser interface so Phase 4 media (web, document, OCR, STT) attach without changing the boundary.

## 2. Responsibilities and boundaries

In scope for Bifröst:

- Parse raw content into structural parts with deterministic, model-free code.
- Stamp every derived field with an origin-based provenance class and TAINTED taint.
- Quarantine the body as `data_payload`, never merged into an instruction or control field.
- Neutralise chat-template control-token strings in untrusted content (defence in depth).
- Run a belt-and-braces structural classifier for instruction patterns, strip flagged patterns from the content crossing to Nornir, and log the original to Hliðskjálf with a Gjallarhorn event.

Out of scope for Bifröst:

- Classification against the ontology (that is Nornir, document 4).
- Any language-model call. A model in this layer would itself be injectable and would void the boundary. This is a hard rule, stated in `poc/symbolic.py` and carried here.
- Trust decisions. Bifröst assigns provenance and taint by origin; it never promotes.

## 3. The parsing contract

### 3.1 Signature

The parse entry point is a pure function of its inputs, so the same raw content and source always produce the same assertion:

```
parse(raw_content: bytes | str, medium: Medium, source: str) -> TaintedAssertion
```

`Medium` is an enumeration (`EMAIL`, `WEB`, `DOCUMENT`, `IMAGE`, `AUDIO`, `TOOL_OUTPUT`, `FILE`). Phase 1 implements `EMAIL` only; the others raise a not-implemented-in-this-phase error rather than silently degrading, so an unsupported medium fails closed rather than crossing unparsed.

### 3.2 The TaintedAssertion (the Phase-1 concrete form)

The assertion is the cross-cutting type defined in `index.md` section 4.1. Bifröst produces it with these fields populated:

- `provenance`: the origin class for the medium. Email is `EXTERNAL_COMMS`. Fixed by the medium and the source, never by content.
- `taint`: always `TAINTED` for Bifröst output. There is no path by which Bifröst emits anything else.
- `source`: the concrete source identifier (for email, the ingesting mailbox or feed id).
- `parsed_fields`: deterministic structural extractions. For email: `sender` (via `email.utils.parseaddr`), `subject`. These are typed slots for downstream extraction, still TAINTED by origin.
- `data_payload`: the full body, verbatim except for control-marker neutralisation, quarantined as data. If structural parsing recovers no body (a plain-text case with no email structure), the whole raw text is the payload, so nothing is silently dropped.
- `control_markers_neutralised`: a boolean recording whether the payload was altered from verbatim by neutralisation, so the harness and a reviewer can see the change and why.

This is the exact shape `poc/symbolic.py::to_typed_record` already produces. The Phase-1 build hardens that proof-of-concept function into the production parser for email; it does not redesign it.

### 3.3 Control-marker neutralisation

Chat-template control-token strings (the `<|...|>` shape) in untrusted text are broken by inserting spaces (`<|im_start|>` becomes `<| im_start |>`), so the payload cannot forge a role boundary at the tokeniser level no matter how it is later encoded. The regex fires only on the `<|...|>` shape, so ordinary prose is untouched; the change is visible, reversible by eye and cannot be steered by the payload. The neural layer also neutralises this at encode time (`split_special_tokens=True`), so this is defence in depth, not the only line. Proven in `poc/symbolic.py::neutralise_control_markers`.

### 3.4 The parser registry

Each medium binds to a parser through a registry, so Phase 4 media attach without touching the boundary logic. The registry maps a `Medium` to a parser callable with the signature above. The taint-class bindings already exist as data in `ontology/media/`. The registry is the extension point; the guarantee (everything out is TAINTED, the body is quarantined, no model in the layer) is a property of the boundary, held identically for every parser.

## 4. The belt-and-braces instruction-pattern classifier

Bifröst runs a structural classifier over parsed content before it enters Nornir. It targets imperative verb forms directed at a second-person agent, references to agent capabilities or action vocabulary, explicit instruction patterns (for example "ignore", "instead", "new instructions") and encoded or obfuscated variants (base64, leetspeak, Unicode substitution).

This is belt-and-braces only. The architectural guarantee is provenance, not detection: an email body is `EXTERNAL_COMMS` and TAINTED regardless of content and regardless of detection confidence. A detection miss does not compromise the structural guarantee, because the guarantee is the origin label attached at a boundary the content cannot cross, not the detector's accuracy. This ordering matters: the classifier is a signal for Gjallarhorn and a convenience for review, never the thing the boundary relies on.

Flagged patterns are stripped from the content crossing to Nornir, the full original is logged to Hliðskjálf, and a Gjallarhorn event is raised. Stripping is applied to the crossing copy only; the original is preserved in the audit log, so nothing is destroyed and a reviewer sees exactly what arrived.

### 4.1 Interface

```
scan_patterns(assertion: TaintedAssertion) -> list[PatternFlag]
```

Each `PatternFlag` records the pattern class, the matched span and the decoded form if the match was obfuscated. The scan is deterministic and model-free.

## 5. Fail-closed behaviour

- An unsupported medium fails closed (not-implemented error), never crosses unparsed.
- A parse that recovers no structured body still emits the raw text as `data_payload`, so content is never silently dropped.
- If neutralisation or scanning raises, the assertion is quarantined to review rather than crossing unscanned. Bifröst never emits an un-neutralised, un-scanned assertion into Nornir.
- Bifröst never emits anything other than TAINTED. There is no code path to a higher taint level in this component.

## 6. Data owned

- The parser registry (medium to parser bindings).
- The taint-class bindings (`ontology/media/`, present as data).
- No persistent state. Bifröst is a pure transform from raw content to assertion.

## 7. Dependencies

- Upstream: the pull-ingestion loop, which sets the consumption cadence (HLD Design Principle 11). Bifröst does not pull; it parses what the loop hands it.
- Downstream: Nornir (classification). Bifröst hands typed TAINTED assertions to Nornir and nothing else.
- Lateral: Hliðskjálf (original content logging on a pattern flag), Gjallarhorn (the flag event).

## 8. Build delta from today

- `poc/symbolic.py` proves the email path at PoC shape. Phase 1 hardens it into the production email parser behind the registry interface.
- The instruction-pattern classifier exists in the PoC's spirit (the boundary is proven) but the structural pattern set (encoded-variant detection in particular) needs building out as the belt-and-braces layer.
- The registry and the `Medium` enumeration are new, small and exist so Phase 4 attaches cleanly.
- Web, document, OCR and STT parsers are Phase 4 and out of scope here; the registry reserves their slots.
- Mixed-trust-source re-stamping (a trusted document quoting an untrusted source inside it) is an unaddressed seam (`ADVERSARIAL_REVIEW.md` 5.9, HLD risk R-10). It is owned by the Phase-4 ingestion expansion that introduces multi-part documents, not by this Phase-1 email design. Named here so it is not forgotten.

## 9. Test plan

Inherits the PoC separation suite (`poc/`): an adversarial corpus of emails with embedded injections, asserting for each case that the injection lands in `data_payload` and never in an instruction or control field, at decoding temperatures 0.0 and 0.7. This is the proven baseline (invariants 3.2 and 3.3).

Adds, before implementation:

- Provenance invariance: for a corpus of email bodies with and without injection content, assert `provenance == EXTERNAL_COMMS` and `taint == TAINTED` for every case regardless of content. This tests that the guarantee is the origin label, not the detector.
- Neutralisation: assert every `<|...|>` control-marker shape in a payload is broken and the flag is set; assert ordinary prose containing no such shape is untouched and the flag is unset.
- No-body fallback: a plain-text non-email input yields the raw text as `data_payload`, nothing dropped.
- Unsupported medium: a `WEB` input in Phase 1 fails closed with a not-implemented error, does not cross.
- Pattern scan and strip: a planted `<instruction>ignore previous</instruction>`-style pattern is flagged, stripped from the crossing copy, and the original is present in the Hliðskjálf log; a Gjallarhorn event is raised. A benign body raises no flag.
- Determinism: the same raw content and source produce a byte-identical assertion across repeated calls.

Coverage is reported line and branch; the fail-closed branches (unsupported medium, scan-raises-to-review) are covered explicitly, since they are the point of a boundary component.

## 10. Decisions (index)

| # | Decision | Chosen | Rejected | Rationale |
|---|---|---|---|---|
| BF-1 | Parser structure | A registry keyed by `Medium`, one parser per medium, sharing the boundary guarantee | A single parser with per-medium branches | The registry is the clean Phase-4 attach point and keeps the boundary guarantee identical across media. |
| BF-2 | Unsupported medium in Phase 1 | Fail closed (not-implemented error) | Best-effort generic parse | A generic parse of an unmodelled medium is exactly the silent-degrade that lets content cross under-handled. Fail closed. |
| BF-3 | Instruction-pattern detection role | Belt-and-braces signal for Gjallarhorn and review; strip-and-log, never the guarantee | Rely on detection to block injection | The guarantee is provenance, attached at a boundary the content cannot cross. Detection is heuristic and loses to a determined adversary; making it load-bearing would reintroduce the flaw Heimdall exists to remove. |
| BF-4 | Neutralisation placement | In Bifröst as defence in depth, in addition to the neural layer's encode-time neutralisation | Only at the neural layer | Two independent neutralisation points mean the payload cannot forge a boundary even if one layer's encoding changes. Proven in the PoC. |

---

## Licence

Part of the Heimdall specification, licensed under CC-BY-SA-4.0. See `LICENSE.md`.
