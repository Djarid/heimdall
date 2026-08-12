# Heimdall: Project Status

**Author:** Jason Huxley
**Version:** 1.0
**Date:** August 2026
**Status:** living status page; update at the end of each working session

This is the "you are here" page. It orients a reader (or a fresh agent session
with no prior context) on where the project stands, what is proven, what is
open, and what to do next. For the full detail, follow the links; this page is
the map, not the territory.

---

## 1. What Heimdall is

A neurosymbolic architecture that lets LLM agents work with untrusted external
content (web, social media, email, documents, tool output) without that content
being able to cause action. Trust is assigned by origin at a structural
boundary, not by detecting malicious content. Read `HEIMDALL.md` for the full
architecture and `README.md` for the orientation paths.

---

## 2. Where we are now

**The premise is proven; the coverage is untested.** That one sentence is the
state of the project.

- **Proven (the PoC).** The neurosymbolic filter's structural half holds: a
  deterministic layer with no LLM quarantines untrusted content as typed data,
  the model only ever receives it as inert data, and nothing acts on the output
  unless a wiring is proven safe by provenance. Demonstrated on an adversarial
  corpus with a real local model, at decoding temperatures 0.0 and 0.7. See
  `poc/OUTCOME.md`.
- **Not yet tested (the ontology).** The live guarantee is exactly as strong as
  the ontology's coverage, and the ontology does not meaningfully exist yet. The
  PoC used a flat four-field schema, not an ontology. This is the largest open
  dependency. See `NEUROSYMBOLIC_FILTER_INVARIANTS.md` invariant 3.11.

---

## 3. The document map

| Document | What it is |
|----------|-----------|
| `HEIMDALL.md` | The full architecture specification |
| `README.md` | Orientation, with audience-specific reading paths |
| `GLOSSARY.md` | Norse component names mapped to their architectural roles |
| `NEUROSYMBOLIC_FILTER_INVARIANTS.md` | The invariants the live build must hold, each marked PROVEN, DEMONSTRATED or NOT YET TESTED |
| `ONTOLOGY_CONSTRUCTION.md` | How the ontology (Yggdrasil) is built, grown and tested |
| `DECISIONS.md` | The decision log: 40 tracked decisions with consistency checks |
| `STATUS.md` | This page |
| `poc/` | The proof-of-concept: code, corpus, spec and outcome |
| `ontology/` | The nascent Yggdrasil tree: BFO loaded, SUMO reference, layers stubbed |
| `reference/style_guide.md` | The writing style guide all prose is written to |

Read order for a cold start: this page, then `poc/OUTCOME.md`,
then `NEUROSYMBOLIC_FILTER_INVARIANTS.md`, then `ONTOLOGY_CONSTRUCTION.md`, with
`DECISIONS.md` as the running record of why each choice was made.

---

## 4. What is built

- **PoC** (`poc/`): `symbolic.py`, `neural.py`, `harness.py`, `sinks.py`, a
  31-case corpus, an external-jailbreak adapter. Runs in a venv via `mlx-lm` on
  Apple silicon. All cases pass both assertions at temp 0.0 and 0.7.
- **Ontology scaffold** (`ontology/`): BFO 2020 fetched and loaded
  (`upper/bfo`, CC BY 4.0); SUMO fetched as unloaded GPL reference
  (`reference/sumo`); the authored layers (`spine`, `domain`, `media`, `rules`)
  and the test suite (`tests`) are stubbed with intent-stating READMEs.
- **The documentation spine**: invariants, ontology methodology, decision log,
  status page, style guide, all committed.

---

## 5. What is open, and who forces it

From `DECISIONS.md` section 5. Nothing here is a surprise; each has a trigger.

| Item | Kind | Trigger / phase |
|------|------|-----------------|
| D25 substrate (Memgraph) | SPIKE-GATED | Phase 2 spike, criteria in `ONTOLOGY_CONSTRUCTION.md` 3.3 |
| D38 upper ontology (BFO) | SPIKE-GATED | Phase 2 spike confirms load-and-extend |
| D31 domain governance (curated vs federated) | DEFERRED | Forced by a second domain (Phase 4) |
| D32 edge-deletion label retraction | OPEN (research) | Substrate spike pass criterion |
| D33 constrained decomposition grammar | OPEN (research) | If opaque summaries prove too coarse |
| D34 Huginn discriminating features | OPEN (research) | Needed for classification-correctness testing |
| D35 Odin self-modification | OPEN (research) | Currently excluded |
| D36 cross-harness portability | DEFERRED | Post-Phase 1 |

---

## 6. Recommended next step

**Run the D25 / D38 substrate spike** (Phase 2). It is the highest-leverage next
action because the substrate decision gates the entire ontology layer, and it
carries the real technical risk: edge-deletion label retraction in the
flow-to-sink reachability graph (D32). The spike is throwaway and time-boxed,
with pass criteria already written in `ONTOLOGY_CONSTRUCTION.md` section 3.3:
write-time label maintenance, authorisation-time read, edge-deletion retraction,
and scale. The outcome ratifies or overturns D25, and the code is then binned.

Other viable directions, lower leverage: author the Phase-1 communications seed
domain on BFO; build the ontology test harness so coverage becomes measurable;
or feed the external jailbreak corpus through `poc/corpus/adapter.py` (a PoC
loose end).

---

## 7. How to update this page

At the end of a working session, update sections 2, 4, 5 and 6 to reflect what
changed, and add any new decisions to `DECISIONS.md`. A decision that is only in
a chat and not in `DECISIONS.md` is a decision that will be lost.
