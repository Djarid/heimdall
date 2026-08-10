# Heimdall Premise PoC

**Author:** Jason Huxley
**Version:** 1.0
**Date:** August 2026
**Status:** throwaway proof-of-concept

A throwaway proof-of-concept that tests one premise and nothing else:

> In a paired symbolic-plus-LLM pipeline, the LLM only ever receives trusted, typed, provenance-stamped versions of data, and untrusted instructions embedded in that data do not cause action.

This is not Heimdall. There is no ontology, no graph database, no promotion mechanism and no control surface. Those are later phases and out of scope. Read `SPEC.md` for the full build brief.

---

## What it proves, and what it does not

A pass on the corpus means, for every case, that both of these hold:

1. **Input assertion.** The exact prompt the model received contains no untrusted bytes in an instruction position. Untrusted content appears only inside a typed, delimited data field.
2. **Output assertion.** No field the pipeline treats as actionable traces back to an instruction embedded in untrusted content.

A pass proves the mechanism works on this corpus with this model. It does not prove the architecture is secure. The harness prints that limit on every run.

A green board is not the goal. A trustworthy, interpretable board is. A clearly reported failure is a successful outcome, because a boundary leak found now is the most valuable thing this exercise can produce.

---

## The one rule that matters

The symbolic layer (`symbolic.py`) contains no call to any language model, local or remote, direct or indirect. It is plain deterministic Python: parsing, rules and a schema. Trust is assigned by origin, not by inspecting whether content looks malicious. If the separation of data from control were done by a model, that classifier would itself be injectable and the test would be void.

---

## Architecture

Data flows in one direction only.

```
raw untrusted input
        │
        ▼
  symbolic.py     deterministic, no LLM. Emits a typed record.
        │  typed record (untrusted body quarantined in a data field)
        ▼
  neural.py       MLX-constrained LLM. Receives ONLY the typed record.
        │  schema-constrained extraction (typed output)
        ▼
  harness.py      runs the corpus, checks the two assertions, prints results
```

`harness.py` is the only component that reads raw corpus files, and it hands them to `symbolic.py`, never to `neural.py`.

---

## Requirements

- Apple silicon (built and run on an M5 MacBook Pro, 48GB unified memory).
- Python 3.11 or later. Tested on 3.14.
- Inference through MLX (`mlx-lm`), not llama.cpp and not a remote API.
- Default model `mlx-community/Qwen2.5-7B-Instruct-4bit`, set as a single constant at the top of `neural.py`. Weights download on first run (about 4GB).

---

## Install

Everything runs inside a virtual environment to avoid version conflicts on the host. This is required, not optional.

```
cd poc
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install mlx-lm
```

The only third-party dependency is `mlx-lm`. Everything else is the standard library.

---

## Run

Full corpus:

```
.venv/bin/python harness.py
```

Useful flags:

- `--limit N` runs the first N cases only (handy for a quick check).
- `--model <id>` overrides the default model.
- `--corpus <path>` points at a different corpus file.
- `--json` also emits machine-readable results after the table.

The first run downloads the model. Later runs load from the local cache.

---

## Reading the results

The harness prints a per-case table, a summary and two things that matter most.

**Partitions.** Cases are split into three groups (spec 6.3):

- Instruction-targeting payloads should pass trivially. Any failure is a boundary leak and a headline finding.
- Extraction-targeting payloads are the ones that actually stress the premise. The external jailbreak corpus is thin here, so the harness flags the gap.
- Clean controls must extract correctly. Without them a pass is meaningless, because a pipeline that does nothing at all would trivially not follow instructions.

**Failures.** Any case that deviates from expectation is printed in a loud block with its notes, never buried in the table.

Every run ends with the scope limit stated in full.

---

## The corpus

`corpus/corpus.jsonl` holds the starter corpus (18 cases), one JSON object per line:

```json
{"id": "...", "category": "...", "raw_text": "...", "expected": {"input_pass": true, "output_pass": true}}
```

Categories cover direct instruction override, instruction disguised as quoted or forwarded content, encoded or obfuscated instruction (base64, spacing, homoglyph), instruction that references the extractor's own task, multi-part social-engineering narratives and clean controls with no injection. Two cases target extraction directly (a fake header planted in the body and an entity-poisoning attempt).

To regenerate the starter corpus:

```
.venv/bin/python corpus/_build_starter.py
```

---

## Ingesting an external jailbreak corpus

A colleague's anti-guardrail programme produces jailbreak payloads. The adapter maps that output onto the corpus schema and tags each payload by which layer it targets.

```
.venv/bin/python corpus/adapter.py <external_file> --out corpus/imported.jsonl
.venv/bin/python harness.py --corpus corpus/imported.jsonl
```

The adapter accepts a JSON array or JSONL, reads the payload from the first recognised field (`raw_text`, `payload`, `prompt`, `text`, `content`, `jailbreak`, `body`) and classifies each case as instruction-targeting or extraction-targeting. Tagging here is for reporting only. The trust boundary lives in `symbolic.py`, and everything imported is UNTRUSTED regardless of tag.

---

## Files

- `symbolic.py` the deterministic symbolic layer. No model.
- `neural.py` the MLX schema-constrained extractor. Receives only the typed record.
- `harness.py` runs the corpus and checks both assertions.
- `corpus/corpus.jsonl` the starter corpus.
- `corpus/_build_starter.py` regenerates the starter corpus.
- `corpus/adapter.py` maps an external jailbreak corpus to the schema.
- `SPEC.md` the full build brief.

---

## How the two assertions are checked

The input assertion is mechanical, not a judgement, and it checks the prompt the model actually received at the token level. `neural.py` puts the trusted instruction in a system message and the untrusted payload alone in a user message, then builds the prompt as token ids: the trusted frame is tokenized once, the payload is tokenized in isolation with special tokens split, and the two are spliced. `harness.py` verifies, per field, that the frame token ids match an independent reconstruction from the trusted constants, that the payload region decodes to the quarantined payload and contains zero control tokens, and that the full prompt is exactly frame plus payload plus frame. There is no in-band delimiter for a payload to forge, and no payload byte can become a control token and forge a role boundary.

The output assertion checks inertness by construction, not by scanning the extraction for directive-like text. Scanning is unsound: a faithful summary of untrusted data must be able to quote it, so text overlap cannot tell describing a directive from obeying one, and a text classifier at the output would itself be injectable. Instead the schema is declared with every field typed and marked non-action-capable, and the check confirms the extraction conforms to that schema, that no field is action-capable, and that passing the extraction through the (empty) registry of downstream sinks fires nothing. The content of any field is therefore irrelevant to whether an action occurred. Nothing acts on the extraction; it is inert typed data, which is the point.

Output is valid by construction. Rather than asking the model for JSON and hoping, each field is produced by a bounded single-line generation and the JSON envelope is assembled in Python, so malformed output is impossible.
