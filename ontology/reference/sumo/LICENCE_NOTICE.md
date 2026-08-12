# SUMO reference files: licence and usage notice

**Read this before using anything in this directory.**

## What these files are

These are unmodified files from the Suggested Upper Merged Ontology (SUMO),
fetched from `https://github.com/ontologyportal/sumo`. They are kept here as a
**reference library only**, per decision D38 in `DECISIONS.md`: SUMO is not
loaded into Heimdall's ontology. It is a source to import and prune domain types
from when coverage is extended.

Files present:

- `Merge.kif` SUMO upper ontology (SUO-KIF)
- `Mid-level-ontology.kif` MILO, the mid-level ontology
- `Communications.kif` communications domain
- `FinancialOntology.kif` finance domain

## Licence: GPL, and why that matters here

SUMO is released under the **GNU General Public License** by Articulate Software.
Heimdall itself is licensed CC-BY-SA-4.0. These are different licences with
different obligations, so SUMO content is quarantined in this directory and is
subject to three rules:

1. **Do not compile SUMO files into the loaded ontology.** Nothing under
   `ontology/upper`, `ontology/spine`, `ontology/domain`, `ontology/media` or
   `ontology/rules` may be a copy or derivative of a SUMO file. Those layers are
   the loaded ontology and must stay clear of GPL content.
2. **Reference, do not vendor into the build.** When a SUMO type is useful as a
   starting point for a hand-authored domain type, the type is re-expressed from
   scratch in Heimdall's own vocabulary, not copied. Treat these files as
   documentation to read, not source to include.
3. **Preserve attribution.** SUMO's own copyright and GPL notice sits at the top
   of each `.kif` file. Do not strip it. Any writing that builds on SUMO must
   credit it, per SUMO's own request.

If in doubt about whether a use crosses from reference into derivative, treat it
as derivative and keep it out of the loaded layers.

## Why SUMO is reference-only, not loaded

Recorded in full in `ONTOLOGY_CONSTRUCTION.md` section 3.4. In short: under the
neurosymbolic filter's invariants, every loaded classification type is
trust-boundary surface that must be tested, so SUMO's roughly 25,000 terms would
be a large untested liability. The filter needs typed inertness, not SUMO's
semantic richness, and coverage is grown demand-driven rather than front-loaded.
SUMO's value here is as a head start for authoring domain types, which is a
build-time convenience, not a runtime dependency.
