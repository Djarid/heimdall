# Media: taint classes and parser bindings

Media are how content arrived, not what it is about. This directory holds the
per-medium taint classes and their Bifröst parser bindings. It holds **no
subject-matter types**: those live in `../domain`. This separation is what makes
the system medium-blind (decisions D22, D22a).

Each medium binds a parser to a taint class:

- email to `EXTERNAL_COMMS`
- web content to `EXTERNAL_WEB`
- social media to `EXTERNAL_WEB` (or a dedicated social taint class if the
  distinction earns its keep)
- documents to `EXTERNAL_DOCUMENT`
- audio (STT) to `EXTERNAL_AUDIO`
- tool output to `TOOL_OUTPUT`

The medium sets the taint class on the assertion; the domain layer sets the
type. A payment request types to the same domain type whether it arrived by
email, web or social media (D22a). The threat surface is all external content an
agent reads, not email; email is only the Phase 1 staging medium.

The medium attach test (`ONTOLOGY_CONSTRUCTION.md` 4.2): a new medium attaches by
adding a parser and taint class here that feed the existing domain types,
without adding medium-specific types. If a new medium forces new types, the
domain layer has leaked medium assumptions and must be corrected.

Authored (Phase 2): the taint-class-to-type bindings' runnable form is
`yggdrasil/media.py` (media nodes, taint-class nodes, BINDS_TAINT edges). Parser
bindings themselves remain Bifröst build work; this layer records the
taint-class-to-type discipline the parsers must honour. See `ontology/OUTCOME.md`.
