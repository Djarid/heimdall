# Writing Style Guide

**Author:** Jason Huxley
**Version:** 2.0
**Date:** August 2026

This guide applies to all documents (specifications, policy submissions,
academic briefs, public explainers, campaign materials) and to AI-generated
drafts including daemon email responses. Every agent session should enforce
these rules.

Version 2.0 generalises the guide beyond any single project: project-specific
terminology and figures have been removed, the essence of the figure-usage
rules kept, the em dash rule clarified against markdown horizontal rules, and
the mandatory licence footer dropped (licence notices are set per project).

---

## 1. Language and Spelling

- **British English throughout:** labour, defence, realise, colour, programme,
  analyse, centre, metre (but meter for measuring devices), licence (noun),
  license (verb)
- **No Americanisms:** "gotten", "math", "oftentimes", "utilize" are all wrong.
  Use "got", "maths", "often", "use".
- **Oxford comma:** do not use. Write "energy, bandwidth and data" not
  "energy, bandwidth, and data".
- **Numbers:** spell out one to nine in prose. Use figures for 10 and above,
  all monetary amounts, all percentages, and all technical quantities.
  **Consistency rule:** if any number in a group or range requires figures,
  all numbers in that group use figures. Write "7 to 10 days" not
  "seven to 10 days". Write "three components" but "£31 billion" and
  "12 TWh".

---

## 2. Punctuation

- **No em dashes in prose.** Do not use `—` or ` - ` (spaced hyphen) as
  parenthetical separators. Ever.
- **A markdown horizontal rule (`---` on its own line) is not an em dash.**
  It is a section break and is required between major sections (see 5.1).
  The ban in this section is on inline `—` and spaced-hyphen separators
  within sentences, not on horizontal rules.
- **Use parentheses** (like this) or **commas** for asides and interjections.
- **Hyphens** only for:
  - Compound modifiers before a noun: "post-employment economy",
    "age-banded supplements", "self-scaling mechanism"
  - List markers in markdown (`- item`)
  - Ranges in tables or technical contexts: "£200-800/TB"
- **Colons** to introduce lists, explanations, or elaborations. Lowercase
  after a colon unless the next word is a proper noun.
- **Semicolons** sparingly, to join closely related independent clauses.
  If in doubt, use a full stop instead.

---

## 3. Tone and Register

### 3.1 General Principles

- **Direct and precise.** Say what you mean. Do not hedge with "perhaps",
  "it could be argued that", or "some might say".
- **Technically confident.** A worked proposal or specification carries
  sourced figures and stated reasoning, not speculation. Write accordingly.
- **No sycophancy.** Do not praise the reader, flatter institutions, or
  express gratitude for being allowed to submit. State the case.
- **No waffle.** Every sentence must carry information. If you can delete a
  sentence without losing meaning, delete it.

### 3.2 Register by Audience

Match register to reader without changing the substance:

- **Formal submission or specification:** precise, structured, sourced.
  Assume a technical or expert reader.
- **Academic brief:** academic but accessible, every claim sourced. Assume a
  researcher.
- **Public explainer:** plain English, short sentences, no jargon. Assume no
  prior knowledge.
- **Email:** professional but not stiff, concise. Match length to purpose.

### 3.3 Words and Phrases to Avoid

| Avoid | Use Instead | Reason |
|---|---|---|
| comprehensive | thorough, detailed, full | AI writing tell |
| robust | strong, solid, resilient | AI writing tell |
| utilize | use | Americanism and pompous |
| leverage (as verb) | use, exploit, apply | Corporate jargon |
| stakeholders | people affected, parties involved | Vague corporate-speak |
| going forward | from now, henceforth, (or delete) | Filler |
| in terms of | (rephrase the sentence) | Filler |
| it should be noted that | (delete; just state the thing) | Throat-clearing |
| it is important to | (delete; just state the thing) | Throat-clearing |
| comprehensive analysis | analysis (it's either analysis or it isn't) | Redundant modifier |
| holistic | (delete or rephrase) | Meaningless buzzword |
| ecosystem | system, network, sector | Unless referring to actual ecology |
| synergy | (rephrase) | Corporate jargon |
| paradigm shift | change, transformation | Overused to the point of emptiness |

---

## 4. AI Writing Tells

AI-generated text has recognisable patterns. All drafts must be checked for
these before publication.

### 4.1 Structural Tells

- **Tricolon habit:** AI loves groups of three ("efficient, effective, and
  equitable"). Break up or reduce to two where three is gratuitous.
- **Antithesis habit:** AI loves the "X, not Y" construction ("containment,
  not elimination", "a property of the boundary, not the pipeline"). Used once
  it is fine; used every other sentence it is a tell. Cut most of them.
- **Mirrored sentence openings:** AI tends to start consecutive paragraphs
  with the same structure. Vary your openings.
- **Excessive hedging:** "This could potentially help to address some of
  the challenges" instead of "This addresses the problem". Be direct.
- **Summary-then-detail pattern:** AI always gives a summary sentence then
  elaborates. Real writers sometimes lead with the detail.
- **Self-referential flourishes:** "named as such", "stated honestly",
  "that is the point", "which is exactly why". Delete them; let the content
  carry the weight.

### 4.2 Lexical Tells

- Overuse of "comprehensive", "robust", "holistic", "leverage", "ecosystem"
- "Importantly" or "crucially" at sentence start (just state the importance)
- "It is worth noting that" (delete it; note it by saying it)
- "This is particularly relevant because" (just explain why)
- "In this context" (usually deletable)
- Bold used mid-sentence for emphasis on ordinary phrases (reserve bold for
  key terms on first use, amounts, and conclusions, per 5.1)

### 4.3 The Test

Read the text aloud. If it sounds like a management consultant's slide
deck, rewrite it. If it sounds like a human being explaining something
they understand and care about, it's probably fine.

---

## 5. Formatting

### 5.1 Markdown Conventions

- **Headers:** ATX-style (`#`, `##`, `###`) with clear hierarchy. Never
  skip levels (no `##` followed immediately by `####`).
- **Section numbering:** decimal system (1.1, 1.2, 2.1) in formal documents.
  No numbering in public explainers.
- **Bold** for key terms on first use, amounts, and conclusions. Not for
  ordinary mid-sentence emphasis.
- **Italic** for emphasis (sparingly) and publication titles.
- **Lists:** bullet (`-`) for unordered lists, numbered (`1.`) for
  sequences or ranked items.
- **Tables:** pipe-delimited, with header row. Use for structured
  comparisons and data.
- **Separators:** `---` (horizontal rule, on its own line) between major
  sections.
- **Line length:** no hard wrap in markdown source. Let the renderer
  handle line breaks.

### 5.2 Document Metadata

Every formal document should include at the top:

- Title
- Author
- Date
- Version number
- Target audience (where useful)

Licence notices are set per project (for example CC-BY 4.0 or CC-BY-SA-4.0),
not mandated by this guide. Place the notice at the end of the document in the
form the project requires.

### 5.3 File Naming

- `snake_case.md` for all files
- No spaces in filenames
- Group by purpose in sensible directories (for example `docs/`, `technical/`)

---

## 6. Figures and Sources

The project-specific figure tables that earlier versions carried have been
removed. The principles that govern figure usage remain:

- **Never invent statistics.** If a figure is not sourced, flag it as
  "[source needed]" rather than fabricating a citation.
- **Cite sources inline:** "(ONS ASHE 2025)" or "(OBR Nov 2023 EFO)".
- **Reference the authoritative source** for any project's own figures (a
  named model or data file), with section numbers where they exist. Do not
  reproduce a figure from memory when an authoritative source exists; quote
  the source.
- **Note stale data:** "stale after [date] when [new release] publishes".
- **Apply the numbers formatting rule** from Section 1 to every figure.

---

## 7. Checklist Before Publication

Before any document is submitted, emailed, or published:

1. [ ] British English throughout (no Americanisms)
2. [ ] No em dashes in prose (horizontal rules on their own line are fine)
3. [ ] No Oxford commas
4. [ ] Numbers formatted per Section 1 (including the group consistency rule)
5. [ ] No AI writing tells (Section 4)
6. [ ] Bold reserved for key terms, amounts and conclusions (not mid-sentence emphasis)
7. [ ] Sources cited for all statistics; none invented
8. [ ] Metadata block present on formal documents
9. [ ] Licence notice in the form the project requires
10. [ ] Version number incremented if the document was previously published
