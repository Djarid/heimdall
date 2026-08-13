"""Yggdrasil: the loaded ontology, authored as a property graph.

This package is the runnable, substrate-neutral form of Heimdall's ontology
(`ONTOLOGY_CONSTRUCTION.md`). The substrate spike ratified a property graph
(decision D25), so the loaded layers are authored as graph nodes and relations,
not as OWL. Every type here is a node; every subtype and every anchor to BFO is a
relation. Nothing depends on Memgraph: the same node and relation records map onto
a property graph later (the deferred, low-risk binding), and run now as plain
Python over an in-memory graph.

Layer composition (`ONTOLOGY_CONSTRUCTION.md` section 2.2), one module per layer:

- `core`        the node/relation vocabulary this package is written in, plus the
                loaded BFO anchor IRIs the spine and domains extend (D23, D40).
- `spine.trust` the trust lattice (TAINTED, VOUCHED, TRUSTED, CANONICAL).
- `spine.action` the action vocabulary (types that can exist; not per-agent, D20).
- `spine.constraint` the constraint vocabulary (axioms that can be expressed).
- `domain.communications` the Phase 1 seed domain, medium-neutral (D22, D22a).
- `media`       taint-class-to-type bindings; medium sets taint, domain sets type.
- `unclassified` the coverage fail-safe (UNCLASSIFIED_DATA_ASSERTION).

The one rule that shapes the tree: subject-matter TYPE lives here; per-agent
PERMISSION does not (that is control-surface state, `control_surface.py`, D20).

`load()` assembles the whole loaded ontology into one `Ontology` graph, which
Nornir classifies against. Read `ONTOLOGY_CONSTRUCTION.md` and `ontology/README.md`
before changing anything here: a change to a loaded type is a change to the trust
boundary (invariant 3.11).
"""

from __future__ import annotations

from .core import Ontology


def load() -> Ontology:
    """Assemble and return the whole loaded ontology as one graph.

    Import order follows layer dependency: BFO anchors first, then the spine, then
    the domain and media layers that extend it, then the fail-safe. Each layer's
    `register` adds its nodes and relations to the shared graph.
    """
    from . import core
    from .spine import trust, action, constraint
    from .domain import communications
    from . import media, unclassified

    onto = Ontology()
    core.register(onto)
    trust.register(onto)
    action.register(onto)
    constraint.register(onto)
    communications.register(onto)
    media.register(onto)
    unclassified.register(onto)
    onto.validate()
    return onto


__all__ = ["Ontology", "load"]
