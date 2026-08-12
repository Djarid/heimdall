# BFO: source and licence

## What these files are

The Basic Formal Ontology (BFO) 2020, the loaded upper layer of Heimdall's
ontology (Yggdrasil), per decision D38 in `DECISIONS.md`. Unlike SUMO (which is
reference-only), BFO **is loaded**: it is the minimal, rigorous spine that all
domain layers extend.

Files, fetched unmodified from `https://github.com/BFO-ontology/BFO-2020`
(`21838-2/owl/`):

- `bfo-core.owl` RDF/XML, the canonical release form
- `bfo-core.ttl` Turtle, the same ontology in a more readable syntax

BFO is about 35 classes rooted at `entity`, splitting into `continuant` (things
that persist through time) and `occurrent` (things that unfold in time). It is
standardised as ISO/IEC 21838-2.

## Licence

BFO is released under **Creative Commons Attribution 4.0 International
(CC BY 4.0)**, which is compatible with Heimdall's CC-BY-SA-4.0. BFO may
therefore be loaded and extended. Preserve the attribution and contributor
metadata carried inside the files.

## How it is used

Domain layers under `ontology/domain` extend BFO classes; they never redefine a
BFO class (decision D23). A communications message, for example, is typed as a
specialisation of a BFO `continuant` or `occurrent` as appropriate, so that
facts from different domains relate through their shared BFO ancestors. This is
what gives the composed ontology one coherent spine rather than a set of
disconnected domain vocabularies.

## Version

Pin the fetched version here when the ontology build is set up, so a BFO upstream
change is a deliberate update rather than a silent drift. Current fetch: BFO 2020
`bfo-core` from the `master` branch, August 2026.
