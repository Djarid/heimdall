"""Media: taint-class-to-type bindings. Medium sets taint, domain sets type.

Media are how content arrived, not what it is about (D22, D22a). This module holds
per-medium taint classes and the binding that says which taint class a medium sets.
It holds no subject-matter types: those are in `domain/`. This separation is what
makes the system medium-blind, a payment request typing to `comms:payment_request`
whether it came by email, web or social.

The Bifrost parser build is out of scope here (that is runtime component work); this
records the taint-class discipline the parsers must honour. A medium node BINDS_TAINT
a taint-class node. The parser, when built, stamps the taint class on the assertion;
the domain layer, via Nornir's classification rules, sets the type. Neither can set
the other.

The medium attach test (D29, `ONTOLOGY_CONSTRUCTION.md` 4.2): a new medium attaches
by adding a MEDIUM node and a BINDS_TAINT edge to an existing taint class that feeds
the existing domain types, with no new subject-matter type. Phase 1's staging medium
is email; web and social are present here precisely to prove the seed is not
email-shaped (the medium attach test is the one most easily forgotten because email
arrives first).
"""

from __future__ import annotations

from .core import NodeKind, Ontology, Relation, RelationKind, TypeNode


# taint class -> description
_TAINT_CLASSES = {
    "taint:EXTERNAL_COMMS": "content from a direct message channel (email and the like)",
    "taint:EXTERNAL_WEB": "content from the open web or social media",
    "taint:EXTERNAL_DOCUMENT": "content from an attached or fetched document",
    "taint:EXTERNAL_AUDIO": "content from speech-to-text transcription",
    "taint:TOOL_OUTPUT": "content returned by a tool the agent called",
}

# medium -> (label, taint class it binds)
_MEDIA = {
    "medium:email": ("email", "taint:EXTERNAL_COMMS"),
    "medium:web": ("web page", "taint:EXTERNAL_WEB"),
    "medium:social": ("social media", "taint:EXTERNAL_WEB"),
    "medium:document": ("document", "taint:EXTERNAL_DOCUMENT"),
    "medium:audio": ("transcribed audio", "taint:EXTERNAL_AUDIO"),
    "medium:tool": ("tool output", "taint:TOOL_OUTPUT"),
}


def register(onto: Ontology) -> None:
    for name, desc in _TAINT_CLASSES.items():
        onto.add_node(
            TypeNode(
                name=name,
                kind=NodeKind.TAINT_CLASS,
                label=name.split(":", 1)[1],
                attrs={"description": desc},
            )
        )
    for name, (label, taint) in _MEDIA.items():
        onto.add_node(
            TypeNode(
                name=name,
                kind=NodeKind.MEDIUM,
                label=label,
                attrs={"binds_taint": taint},
            )
        )
        onto.add_relation(Relation(name, RelationKind.BINDS_TAINT, taint))
