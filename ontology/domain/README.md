# Domain layers

One layer per subject-matter domain, each extending the BFO spine
(`../upper/bfo`) and never redefining a spine type (decision D23). Domains are
subject-matter, not medium (D22): a domain type must be medium-neutral, so a
fact expressed by email, web page or social-media post types identically.

- `communications/` the Phase 1 seed domain: a message from a person or
  organisation, whatever medium carried it. Seeded from the PoC's four-field
  schema (sender, subject, requested-action summary, entities), promoted from a
  flat schema into a typed hierarchy under BFO.

Future domains (scheduling, finance) attach here as sibling directories. The
attach test (`ONTOLOGY_CONSTRUCTION.md` 4.2): a new domain must attach without
editing the existing domains or the spine.

When authoring a new domain, SUMO's matching domain ontology in
`../reference/sumo` may be read as a starting point, but types are re-expressed
in Heimdall's own vocabulary, never copied (GPL; see the reference licence
notice).

Authored (Phase 2): the communications seed's runnable form is
`yggdrasil/domain/communications.py`, promoting the four PoC fields into a typed
hierarchy anchored to BFO. See `ontology/OUTCOME.md`.
