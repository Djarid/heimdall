# Yggdrasil: the ontology tree

**Status:** nascent, Phase 1 seed. Most of this tree is scaffolding with the
sources fetched and the layers stubbed. It is laid out now so growth is
deliberate.

This directory holds Heimdall's ontology, named Yggdrasil (see
`GLOSSARY.md`). The methodology that governs it is `ONTOLOGY_CONSTRUCTION.md` at
the repo root; the decisions behind the structure are in `DECISIONS.md`. Read
those two first. This README is the map.

## The one rule that shapes the whole tree

There are two independent axes, and only one lives here. Subject-matter **type**
lives in this ontology. Per-agent **permission** does not: it is control-surface
state in Himinbjörg (decision D20). So this tree holds types and vocabulary, not
who-may-do-what.

A second rule shapes the split between `domain` and `media`: a domain is
subject-matter, a medium is how content arrived (decision D22, D22a). Email, web
and social media are media, not domains. The same fact must type identically
whichever medium carried it.

## Layout

```
ontology/
  upper/            the loaded upper ontology (the shared spine root)
    bfo/            BFO 2020, CC BY 4.0, LOADED. See bfo/SOURCE.md
  spine/            the rest of the shared spine (Heimdall-authored)
    action/         action vocabulary: the action types that can exist
    constraint/     constraint vocabulary: the axioms that can be expressed
    trust/          the trust lattice: TAINTED, VOUCHED, TRUSTED, CANONICAL
  domain/           per subject-matter domain, each extending the spine
    communications/ the Phase 1 seed domain (medium-neutral)
  media/            per-medium taint classes and parser bindings (NOT types)
  rules/            Nornir's deterministic rules: classification, derivation,
                    constraint axioms, flow-to-sink propagation
  reference/        NOT loaded. Read-only source material to prune from
    sumo/           SUMO, GPL, reference only. See sumo/LICENCE_NOTICE.md
  tests/            the ontology test suite (the four obligations of 3.11)
    corpora/        labelled and adversarial corpora with ground truth
```

## Loaded versus reference (the licence and trust boundary)

Two directories are fundamentally different from the rest:

- `reference/sumo` is **not loaded** and is **GPL**. It is documentation to read
  and prune from, never compiled into the ontology. See its `LICENCE_NOTICE.md`.
  Nothing in the loaded layers may be a copy or derivative of it.
- Everything else is **loaded**: it is the ontology Nornir classifies against,
  and every type in it is trust-boundary surface that must be tested
  (`ONTOLOGY_CONSTRUCTION.md` section 8). Loaded coverage is a cost, not just a
  benefit, which is why the loaded tree stays minimal and grows demand-driven.

BFO (loaded) is CC BY 4.0 and compatible with the repo's CC-BY-SA-4.0. SUMO
(reference) is GPL and quarantined. Keeping these physically separate is what
keeps the licences and the trust boundary clean at once.

## What exists now, and what does not

Fetched and present:

- BFO 2020, loaded upper layer (`upper/bfo`)
- SUMO core, MILO, communications and finance, reference only (`reference/sumo`)

Authored (Phase 2), as a runnable property-graph-native package in `yggdrasil/`
with the reasoner in `nornir/`:

- The Heimdall-authored spine (`yggdrasil/spine/{trust,action,constraint}.py`)
- The communications seed domain (`yggdrasil/domain/communications.py`)
- The UNCLASSIFIED fail-safe (`yggdrasil/unclassified.py`)
- Media taint-class bindings (`yggdrasil/media.py`)
- The dormant per-agent control surface (`yggdrasil/control_surface.py`, D20)
- Nornir's four rule kinds and engine (`nornir/`)
- The test suite and ground-truth corpus (`tests/`), passing obligations 8.1-8.4

The layer directories (`spine`, `domain`, `media`, `rules`, `tests`) hold each
layer's intent and map; the `yggdrasil` and `nornir` packages hold the loaded
nodes, relations and rules. The substrate they map onto is a property graph
(D25, ratified by the spike); binding to a live Memgraph store is the residual.
See `ontology/OUTCOME.md`.

## Format note

BFO ships as OWL (RDF/XML and Turtle). SUMO ships as SUO-KIF. The
Heimdall-authored layers are authored as graph nodes and relations, not OWL,
because the substrate spike (D25) ratified a property graph. The `yggdrasil`
package records each type as a node and each subtype or BFO anchor as a relation,
substrate-neutral now and mapping onto Memgraph at binding time.
