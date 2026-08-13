"""The communications seed domain, medium-neutral (D22, D22a).

The Phase 1 subject-matter domain: a message from a person or organisation,
whatever medium carried it. It promotes the PoC's flat four-field schema
(`sender_extracted`, `subject_extracted`, `requested_action_summary`, `entities`)
into a typed hierarchy under BFO, as `ONTOLOGY_CONSTRUCTION.md` 4.1 requires.

The anchoring to BFO (D23, never redefining a BFO class):

- A `communication` is the information content of a message: a BFO
  `generically dependent continuant`. It is content that can be carried by many
  media and copied without loss, which is exactly what a generically dependent
  continuant is. This is what makes the type medium-neutral: the content type is
  the same whether the bearer is an email, a web page or a social post. The medium
  is recorded as a taint class (see `../media.py`), not as a subtype here.
- A `requested_action` is what the message asks a reader to do: a BFO
  `realizable entity`. It is a disposition to act that may or may not be realised;
  crucially it is NEVER realised by Heimdall reading it. This is the type that most
  needs care, because an attacker's whole aim is to get a requested action realised
  (a payment made, a command run). In the ontology it is inert content to be
  described; whether any value derived from it can reach a consequential sink is
  decided by flow-to-sink reachability, not by this type.
- A `mentioned_entity` is a person, organisation or place named in the content: a
  BFO `independent continuant` (an object), referenced by the message.
- The `sender` and `subject` are qualities/roles of the communication.

The subtype hierarchy under `requested_action` is where classification correctness
bites (obligation 8.2). A `payment_request` and an `instruction_to_act` are the
high-risk subtypes: the adversarial test class is content that tries to get one of
these typed as an inert `informational_statement` so it skips Gjoll. The types
exist so the classifier CAN name them; whether a given assertion is one is Nornir's
classification rules' job, tested against ground truth.

Nothing here is per-agent, and nothing here is per-medium. A payment request types
to `comms:payment_request` whether it arrived by email, web or social (D22a).
"""

from __future__ import annotations

from ..core import NodeKind, Ontology, Relation, RelationKind, TypeNode


def _domain_type(name: str, label: str, anchor: str | None, parent: str | None,
                 onto: Ontology, **attrs: object) -> None:
    onto.add_node(
        TypeNode(
            name=name,
            kind=NodeKind.DOMAIN_TYPE,
            label=label,
            attrs=dict(domain="communications", medium_neutral=True, **attrs),
        )
    )
    if parent is not None:
        onto.add_relation(Relation(name, RelationKind.IS_A, parent))
    if anchor is not None:
        onto.add_relation(Relation(name, RelationKind.ANCHORS_TO, anchor))


def register(onto: Ontology) -> None:
    # The domain root: a communication is information content (a GDC).
    _domain_type(
        "comms:communication",
        "communication",
        anchor="bfo:generically_dependent_continuant",
        parent=None,
        onto=onto,
        description="the information content of a message from a person or organisation, "
        "medium-neutral",
    )

    # The four PoC fields become typed structure under the communication.
    # sender and subject are qualities of the communication.
    _domain_type(
        "comms:sender",
        "sender",
        anchor="bfo:role",
        parent="comms:communication",
        onto=onto,
        seed_field="sender_extracted",
        description="the party the message is from (a role borne in the sending)",
    )
    _domain_type(
        "comms:subject",
        "subject",
        anchor="bfo:quality",
        parent="comms:communication",
        onto=onto,
        seed_field="subject_extracted",
        description="the stated subject of the message",
    )
    onto.add_relation(Relation("comms:communication", RelationKind.HAS_FIELD, "comms:sender"))
    onto.add_relation(Relation("comms:communication", RelationKind.HAS_FIELD, "comms:subject"))

    # mentioned_entity: the entities field. A named object referenced by the content.
    _domain_type(
        "comms:mentioned_entity",
        "mentioned entity",
        anchor="bfo:object",
        parent="comms:communication",
        onto=onto,
        seed_field="entities",
        description="a person, organisation or place named in the content",
    )
    onto.add_relation(
        Relation("comms:communication", RelationKind.HAS_FIELD, "comms:mentioned_entity")
    )

    # requested_action: the requested_action_summary field, the high-risk branch.
    # A realizable entity: a disposition to act, never realised by Heimdall.
    _domain_type(
        "comms:requested_action",
        "requested action",
        anchor="bfo:realizable_entity",
        parent="comms:communication",
        onto=onto,
        seed_field="requested_action_summary",
        description="what the message asks a reader to do; inert content, never realised here",
    )
    onto.add_relation(
        Relation("comms:communication", RelationKind.HAS_FIELD, "comms:requested_action")
    )

    # Subtypes of requested_action. The classification-correctness distinctions.
    # informational_statement: the message is POSITIVELY informational (it reports,
    # announces or describes) AND carries no imperative. Inertness must be EARNED by a
    # positive informational signal, not granted by default: an eager catch-all that
    # types any unrecognised message as informational fails open, silently sending an
    # evasively-phrased request (gift-card fraud, "our banking has changed") to an
    # inert type so it skips Gjoll. See comms:unrecognised_request for the fail-closed
    # default. This split closes that gap without a blacklist: we do not enumerate bad
    # phrasings, we require a good (informational) one to earn the inert label.
    _domain_type(
        "comms:informational_statement",
        "informational statement",
        anchor=None,  # inherits requested_action's anchor
        parent="comms:requested_action",
        onto=onto,
        risk="low",
        description="the content is positively informational (reports, announces, "
        "describes) and carries no imperative; the only inert communications type",
    )
    # unrecognised_request: a communication that is NOT positively informational and
    # matched no known high-risk type. This is the fail-closed default: rather than
    # assume an unclassified message is harmless, route it to human review. It is not
    # inert and not a known high-risk type; it is "we could not confirm this is safe,
    # so a human looks". This is what makes the classifier fail closed against novel
    # phrasings without chasing them with keywords (invariant 3.5: you cannot secure a
    # boundary by enumerating malicious content).
    _domain_type(
        "comms:unrecognised_request",
        "unrecognised request",
        anchor=None,
        parent="comms:requested_action",
        onto=onto,
        risk="review",
        route="human_review",
        description="a communication carrying an unclassified imperative or request; "
        "not confirmed informational, so routed to review rather than assumed inert",
    )
    # payment_request: the content asks for money to move. High-risk: the value it
    # carries (an amount, an account) is exactly what must be action-critical if it
    # can reach a payment sink.
    _domain_type(
        "comms:payment_request",
        "payment request",
        anchor=None,
        parent="comms:requested_action",
        onto=onto,
        risk="high",
        description="the content asks for a payment, transfer or invoice settlement",
    )
    # instruction_to_act: the content tries to direct an action (run this, change
    # that, forward here). High-risk for the same reason.
    _domain_type(
        "comms:instruction_to_act",
        "instruction to act",
        anchor=None,
        parent="comms:requested_action",
        onto=onto,
        risk="high",
        description="the content directs the reader to perform an action "
        "(execute, configure, forward, grant access)",
    )
    # credential_request: the content asks for a secret or access. High-risk.
    _domain_type(
        "comms:credential_request",
        "credential request",
        anchor=None,
        parent="comms:requested_action",
        onto=onto,
        risk="high",
        description="the content asks for a password, token, code or access grant",
    )
