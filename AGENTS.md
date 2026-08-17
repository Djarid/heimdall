# Heimdall: instructions for agents working on this repository

This file is loaded automatically into every agent session working in this
repository. It tells you how to work here and, above all, how to leave the
repository in a state the next session can pick up cold.

Note: this file is about maintaining **this repository**. It is not about
Heimdall's own runtime agent definitions (the symbolic-definition plus
neural-persona entities described in `HEIMDALL.md`), which are part of the
system being designed, not the tooling that builds it.

---

## Read this first

Before doing anything else, read `STATUS.md`, starting at its **section 0
(Resume here)**, which carries the handoff state, the commands to run to see it for
yourself, the next task in priority order, and the traps that have already caught
someone in this repo. Then read section 6 and follow the cold-start read order
(`poc/OUTCOME.md`, then `NEUROSYMBOLIC_FILTER_INVARIANTS.md`, then
`ONTOLOGY_CONSTRUCTION.md`, with `DECISIONS.md` as the running record of why).

---

## The currency rule (most important)

The value of this repository is that a fresh session can reconstruct the whole
project from committed artifacts. That only stays true if you maintain currency.
At the end of any session that changes the design or the build:

1. **Record every decision in `DECISIONS.md`.** A decision that lives only in a
   chat is a decision that will be lost. Give it the next `D` identifier, a
   status (SETTLED, SPIKE-GATED, DEFERRED or OPEN), a rationale, and a
   realisation reference or trigger. Re-run the consistency checks in
   `DECISIONS.md` section 6 and update them if a new decision touches them.
2. **Update `STATUS.md`.** Refresh sections 2, 4, 5 and 6 to reflect what
   changed and what the next step now is.
3. **Keep cross-references live.** If you add a root document, add it to the
   `STATUS.md` document map and, if a reader would look for it, to `README.md`.

If you are unsure whether something is a decision, record it. Over-recording is
cheap; a lost decision is expensive.

---

## How the documents relate

- `HEIMDALL.md` the architecture specification (the system being built).
- `NEUROSYMBOLIC_FILTER_INVARIANTS.md` the invariants the live build must hold,
  each marked PROVEN, DEMONSTRATED or NOT YET TESTED. Do not weaken an invariant
  without recording why in `DECISIONS.md`.
- `ONTOLOGY_CONSTRUCTION.md` how the ontology (Yggdrasil) is built, grown and
  tested.
- `DECISIONS.md` the decision log. The source of truth for why things are as
  they are.
- `STATUS.md` the living status page.
- `poc/` the proof-of-concept.
- `ontology/` the nascent Yggdrasil tree.

---

## Working conventions

- **Writing style.** All prose in this repository follows
  `reference/style_guide.md`: British English, no Oxford comma, no em dashes or
  spaced-hyphen separators, spell out one to nine, and avoid the AI-writing
  tells the guide lists. Check your prose against it before committing.
- **Honesty over reassurance.** This project's worth is in stating limits
  plainly. Mark what is proven as proven and what is untested as untested. A
  clearly reported failure or gap is a good outcome, not something to smooth
  over. The running theme is "the premise is proven; the coverage is untested".
- **The symbolic layer never contains a language model.** This is invariant 3.1
  and the load-bearing rule of the whole architecture. Never introduce a model
  call into a classification, trust-assignment or boundary path.
- **Classification fails closed and is never a blacklist.** Inert or low-risk
  types must be earned by a positive signal (this content looks informational),
  never granted by default. Content that matches no positive rule routes to
  review, so an unrecognised request cannot silently become inert. Never grow
  coverage by adding keyword rules that enumerate malicious phrasings (gift
  cards, "banking has changed" and the like) to catch an attack: that is a
  blacklist, it fails open on the next phrasing, and it is invariant 3.5's
  mistake one layer over (the same error as putting a model in the symbolic
  layer). Grow coverage with fail-closed types, not blacklists. The rule is
  enforced by the classification fail-closed property in
  `ontology/tests/harness.py`; run it after any classification-rule change. See
  invariant 3.5, decisions D54 and D55, and the authoring checklist in
  `ONTOLOGY_CONSTRUCTION.md` section 6.
- **Python runs in a venv.** The PoC uses `poc/.venv` with `mlx-lm` on Apple
  silicon. Do not install into the system interpreter.
- **Licence boundary.** `ontology/reference/sumo` is GPL and reference-only:
  never copy it into the loaded ontology layers. See its `LICENCE_NOTICE.md`.

---

## Commits

- Commit only when the work is coherent and the docs are current. Do not leave
  `DECISIONS.md` or `STATUS.md` stale in a commit that changed the design.
- Do not commit `reference/style_guide.md` changes, the venv, model weights or
  caches; the root `.gitignore` covers the artifacts.
- Write concise commit messages that match the existing style in the log.
