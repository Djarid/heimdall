"""The finance seed domain, medium-neutral. The third domain (D29 attach test again).

Finance is the domain where the sharpest cross-domain overlap lives, and that is why
it is the right pressure test for the D52 priority principle. Communications already
has `comms:payment_request` (a MESSAGE asking someone to pay). Finance is about the
financial fact itself: a transaction, an account, a balance, an invoice as a record
of money owed. The two domains describe the same real-world money from different
angles, and their vocabulary overlaps heavily on words like payment, invoice and
transfer. The principle (D52) must arbitrate that overlap deliberately rather than by
accident, and where it genuinely cannot, the tie must route to review.

Attaching finance edits nothing that exists: not communications, not scheduling, not
the spine, not `core.py`, not `unclassified.py`. It is a sibling type module plus a
sibling rule module, exactly as scheduling was (D50). This re-proves the domain attach
test (D29) at three domains, not two.

BFO anchoring (D23, never redefining a BFO class):

- A `financial_item` is information content about money: a BFO
  `generically dependent continuant`, the same root as a communication and a
  scheduling item, so all three domains relate through their shared ancestor.
- A `financial_transaction` is a movement or commitment of money: the high-risk
  branch. Anchored to `realizable entity` because a transaction is a disposition to
  move money that is realised when settled, and is never realised by Heimdall reading
  it. This is the type that can stage a consequential effect (a transfer that reaches
  a payment sink), so its value must be action-critical if it can reach one.
- An `account_reference` is a named financial account: a BFO `object`, referenced by
  the content. It is high-risk because an account number is exactly the value an
  attacker wants substituted (the BEC new-bank-details trick).

The distinction from communications: `comms:payment_request` is the ASK in a message;
`finance:financial_transaction` is the MONEY MOVEMENT itself. Content that is clearly
a message asking for payment is communications; content that is a financial record or
an instruction to move money is finance. Where the extracted text is genuinely both
(a message that is also a transfer instruction with account details), the two
high-risk types tie at equal specificity and the assertion routes to review (D52).
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
            attrs=dict(domain="finance", medium_neutral=True, **attrs),
        )
    )
    if parent is not None:
        onto.add_relation(Relation(name, RelationKind.IS_A, parent))
    if anchor is not None:
        onto.add_relation(Relation(name, RelationKind.ANCHORS_TO, anchor))


def register(onto: Ontology) -> None:
    # The domain root: a financial item is information content about money.
    _domain_type(
        "finance:financial_item",
        "financial item",
        anchor="bfo:generically_dependent_continuant",
        parent=None,
        onto=onto,
        description="information content about money: a transaction, account, balance or "
        "invoice record; medium-neutral",
    )

    # A financial_transaction: a movement or commitment of money. Realizable entity.
    _domain_type(
        "finance:financial_transaction",
        "financial transaction",
        anchor="bfo:realizable_entity",
        parent="finance:financial_item",
        onto=onto,
        description="a movement or commitment of money (transfer, settlement, payment "
        "execution); inert content here, never realised by Heimdall",
    )
    onto.add_relation(
        Relation("finance:financial_item", RelationKind.HAS_FIELD, "finance:financial_transaction")
    )

    # An account_reference: a named financial account. Object. High-risk because it is
    # the value an attacker substitutes.
    _domain_type(
        "finance:account_reference",
        "account reference",
        anchor="bfo:object",
        parent="finance:financial_item",
        onto=onto,
        risk="high",
        description="a named financial account (IBAN, sort code, account number) referenced "
        "by the content; the value most often substituted in payment fraud",
    )
    onto.add_relation(
        Relation("finance:financial_item", RelationKind.HAS_FIELD, "finance:account_reference")
    )

    # A low-risk financial statement: a balance or report that asks nothing.
    _domain_type(
        "finance:financial_statement",
        "financial statement",
        anchor=None,  # inherits financial_item's anchor
        parent="finance:financial_item",
        onto=onto,
        risk="low",
        description="a balance, report or receipt that records money but asks nothing "
        "consequential of the reader",
    )
