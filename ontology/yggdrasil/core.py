"""The graph vocabulary Yggdrasil is authored in, and the loaded BFO anchors.

Two things live here:

1. The node and relation types the whole ontology is written as. A property graph
   (D25) has typed nodes and typed edges; this is the minimal Python analogue. A
   `TypeNode` is an ontology type (a class of assertion, an action, a trust level,
   a constraint). A `Relation` connects two types. The kinds of relation mirror the
   ontology's structure: `IS_A` (subtype), `ANCHORS_TO` (a spine or domain type
   extends a BFO class), `CAN_REACH` (a flow edge used by flow-to-sink), and a few
   others named below. Nothing here is Memgraph-specific; these records map onto
   graph nodes and edges when the store is bound.

2. The loaded BFO anchor IRIs (D40). BFO is the loaded upper layer under
   `ontology/upper/bfo`; the domain and spine layers extend it and never redefine a
   BFO class (D23). We do not re-parse the OWL here: we record the specific BFO
   class IRIs the seed anchors to, verified against `bfo-core.ttl`, so an anchor is
   a checked reference to a real BFO class rather than a free-floating string. If a
   layer anchors to an IRI not in `BFO_ANCHORS`, `Ontology.validate` fails loudly.

The licence boundary (D40) is respected: BFO (CC BY 4.0) is referenced by IRI, and
nothing from GPL SUMO appears in any loaded module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RelationKind(Enum):
    """The kinds of edge the loaded ontology uses.

    IS_A          type-to-type subtype (a payment request IS_A requested action).
    ANCHORS_TO    a Heimdall type extends a BFO class (D23): the anchor never
                  redefines the BFO class, it specialises beneath it.
    HAS_FIELD     a domain type declares a named field (the marshalled slots).
    CAN_REACH     a flow edge: a value of the tail type can flow into the head.
                  This is the edge flow-to-sink reachability runs over (D24, D30).
    PROMOTES_TO   a trust-lattice promotion edge (TAINTED -> VOUCHED -> ...).
    BINDS_TAINT   a medium binds a taint class (email BINDS_TAINT EXTERNAL_COMMS).
    """

    IS_A = "is_a"
    ANCHORS_TO = "anchors_to"
    HAS_FIELD = "has_field"
    CAN_REACH = "can_reach"
    PROMOTES_TO = "promotes_to"
    BINDS_TAINT = "binds_taint"


class NodeKind(Enum):
    """What a node is, so a classifier or a test can reason about it by kind."""

    BFO_ANCHOR = "bfo_anchor"          # a loaded BFO class, referenced by IRI
    DOMAIN_TYPE = "domain_type"        # a subject-matter assertion type
    ACTION_TYPE = "action_type"        # an action vocabulary entry
    TRUST_LEVEL = "trust_level"        # a trust-lattice level
    CONSTRAINT = "constraint"          # a constraint axiom
    TAINT_CLASS = "taint_class"        # a medium taint class
    MEDIUM = "medium"                  # an ingestion medium (parser binding)
    SINK = "sink"                      # a consequential-sink type (action-critical)
    FAILSAFE = "failsafe"              # the UNCLASSIFIED fail-safe type


@dataclass(frozen=True)
class TypeNode:
    """One node in the loaded ontology graph.

    `name` is the stable identifier (unique across the whole ontology). `kind` is
    its NodeKind. `label` is human-readable. `attrs` carries type-level properties,
    for example a domain type's `medium_neutral` flag or an action type's
    `consequential` flag. `action_critical` on an action or sink type marks it as
    something Gjoll must gate; the Phase 1 action-critical SET is empty even though
    the machinery to declare it is present (section 4.1).
    """

    name: str
    kind: NodeKind
    label: str
    attrs: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Relation:
    src: str
    kind: RelationKind
    dst: str
    attrs: dict = field(default_factory=dict)


# The loaded BFO anchor IRIs, verified against ontology/upper/bfo/bfo-core.ttl.
# A Heimdall type may only ANCHORS_TO one of these. Adding an anchor means checking
# the IRI exists in the loaded BFO and adding it here deliberately (D23, D40).
BFO_ANCHORS: dict[str, str] = {
    "bfo:entity": "http://purl.obolibrary.org/obo/BFO_0000001",
    "bfo:continuant": "http://purl.obolibrary.org/obo/BFO_0000002",
    "bfo:occurrent": "http://purl.obolibrary.org/obo/BFO_0000003",
    "bfo:independent_continuant": "http://purl.obolibrary.org/obo/BFO_0000004",
    "bfo:process": "http://purl.obolibrary.org/obo/BFO_0000015",
    "bfo:disposition": "http://purl.obolibrary.org/obo/BFO_0000016",
    "bfo:realizable_entity": "http://purl.obolibrary.org/obo/BFO_0000017",
    "bfo:quality": "http://purl.obolibrary.org/obo/BFO_0000019",
    "bfo:specifically_dependent_continuant": "http://purl.obolibrary.org/obo/BFO_0000020",
    "bfo:role": "http://purl.obolibrary.org/obo/BFO_0000023",
    "bfo:object": "http://purl.obolibrary.org/obo/BFO_0000030",
    "bfo:generically_dependent_continuant": "http://purl.obolibrary.org/obo/BFO_0000031",
    "bfo:material_entity": "http://purl.obolibrary.org/obo/BFO_0000040",
}


class Ontology:
    """The composed loaded ontology as an in-memory graph.

    Layers add nodes and relations through `add_node` / `add_relation` in their
    `register` functions. `validate` enforces the structural rules that keep the
    trust boundary sound: unique names, no dangling relations, every ANCHORS_TO
    target a known BFO anchor, and no domain type redefining a BFO class (D23).
    """

    def __init__(self) -> None:
        self.nodes: dict[str, TypeNode] = {}
        self.relations: list[Relation] = []

    def add_node(self, node: TypeNode) -> None:
        if node.name in self.nodes:
            raise ValueError(f"duplicate ontology node: {node.name!r}")
        self.nodes[node.name] = node

    def add_relation(self, rel: Relation) -> None:
        self.relations.append(rel)

    # --- queries used by Nornir and the tests ---

    def parents(self, name: str, kind: RelationKind = RelationKind.IS_A) -> list[str]:
        return [r.dst for r in self.relations if r.src == name and r.kind == kind]

    def ancestors(self, name: str) -> set[str]:
        """Transitive IS_A ancestors, so a subtype relates to its supertypes and,
        through ANCHORS_TO on those, to BFO. Used to check cross-domain relatedness
        and to test that a type sits under the intended spine root."""
        seen: set[str] = set()
        stack = list(self.parents(name))
        while stack:
            p = stack.pop()
            if p in seen:
                continue
            seen.add(p)
            stack.extend(self.parents(p))
        return seen

    def anchor_of(self, name: str) -> str | None:
        for r in self.relations:
            if r.src == name and r.kind == RelationKind.ANCHORS_TO:
                return r.dst
        # A type with no direct anchor inherits its parent's anchor.
        for p in self.parents(name):
            a = self.anchor_of(p)
            if a is not None:
                return a
        return None

    def nodes_of_kind(self, kind: NodeKind) -> list[TypeNode]:
        return [n for n in self.nodes.values() if n.kind == kind]

    def validate(self) -> None:
        """Fail loudly on any structural break. Called at the end of `load`."""
        names = set(self.nodes)
        for r in self.relations:
            if r.src not in names:
                raise ValueError(f"relation from unknown node: {r.src!r}")
            # ANCHORS_TO targets are BFO IRIs (keys of BFO_ANCHORS), not nodes.
            if r.kind == RelationKind.ANCHORS_TO:
                if r.dst not in BFO_ANCHORS:
                    raise ValueError(
                        f"{r.src!r} anchors to unknown BFO class {r.dst!r}; "
                        f"add it to BFO_ANCHORS only after verifying it in bfo-core.ttl"
                    )
                if self.nodes[r.src].kind == NodeKind.BFO_ANCHOR:
                    raise ValueError(f"a BFO anchor cannot itself anchor: {r.src!r}")
            elif r.dst not in names:
                raise ValueError(f"relation to unknown node: {r.dst!r}")
        # D23: no domain type may redefine a BFO class. We register BFO anchors as
        # nodes of kind BFO_ANCHOR; a domain type sharing a BFO name would collide
        # on add_node already, but assert the invariant explicitly.
        for n in self.nodes.values():
            if n.kind == NodeKind.DOMAIN_TYPE and n.name in BFO_ANCHORS:
                raise ValueError(f"domain type redefines a BFO class: {n.name!r}")


def register(onto: Ontology) -> None:
    """Register the loaded BFO anchors as nodes, so relations can reference them and
    `validate` can confirm every anchor target is real. We record the IRIs, not the
    OWL axioms: BFO is loaded under `ontology/upper/bfo` and is the authority; this
    is a checked reference to it (D40)."""
    for name, iri in BFO_ANCHORS.items():
        onto.add_node(
            TypeNode(
                name=name,
                kind=NodeKind.BFO_ANCHOR,
                label=name.split(":", 1)[1].replace("_", " "),
                attrs={"iri": iri},
            )
        )
