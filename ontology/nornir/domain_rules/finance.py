"""Finance-domain classification rules. The third sibling (D29), and the sharpest
test of the D52 priority principle.

Adding this module and its line in `register_all` is the whole of the finance domain
on the rules side. It edits no other domain's rules and no shared rule function.

The finance rules are authored to interact deliberately with the communications
payment rule, because that overlap is the point of the pressure test:

- `account_reference` (specificity 3): an explicit account identifier (IBAN, sort
  code, "account number 1234...") is a very specific, narrow signal. It should win
  the high-risk tier over a generic payment mention, because the presence of a
  concrete account is the strongest indicator that money is about to move to a named
  place, which is exactly the value an attacker substitutes.

- `financial_transaction` (specificity 1): a movement of money (transfer, settle,
  execute payment). Deliberately the SAME specificity as `comms:payment_request`
  (also 1). A message that is genuinely both "please pay this" (a communications ask)
  and "transfer X to Y" (a finance movement) matches both at equal risk tier and
  equal specificity, naming different high-risk types. Under D52 that is a genuine
  tie and routes to HIGH_RISK_UNRESOLVED for human review, gated, never a silent
  pick. This is the tie-to-review net proven at three domains.

- `financial_statement` (inert): a balance or receipt that asks nothing.

Reading the extracted fields to type them is describing untrusted content, not
obeying it. The predicates are fixed Python; the content cannot reclassify itself.
"""

from __future__ import annotations

import re

from ..assertions import MarshalledAssertion
from ..rules import (
    ClassificationRule,
    RiskTier,
    carries_imperative_or_consequence,
    register_classification_rule,
    register_high_risk_types,
    text_of,
)


# A concrete account identifier: the narrowest, strongest finance signal.
_ACCOUNT = re.compile(
    r"\b(iban|swift|bic|sort code|account (number|no|#)|acct|routing number|"
    r"[a-z]{2}\d{2}[a-z0-9]{10,}|new bank details|beneficiary account)\b"
)
# A movement or commitment of money. Deliberately MOVEMENT language, not the bare
# ask: "please pay" is a communications request (comms:payment_request), whereas
# "wire the transfer", "remit funds", "execute the payment" are the finance movement
# itself. Keeping "pay" OUT of this pattern is what stops every payment message from
# tying: only content that genuinely signals a money movement reaches finance, so a
# tie with comms:payment_request is reserved for content that is truly both.
_TRANSACTION = re.compile(
    r"\b(wire transfer|bank transfer|transfer the funds|transfer to|remit|"
    r"execute (the )?payment|disburse|send (the )?funds|move (the )?funds|"
    r"settle the (balance|invoice) (by|via) (wire|transfer|bank))\b"
)
# A balance, report or receipt: records money, asks nothing consequential.
_STATEMENT = re.compile(
    r"\b(balance|statement|receipt|report|summary of (charges|spend)|"
    r"year[- ]end|reconciliation|ledger)\b"
)


def _is_account_reference(a: MarshalledAssertion) -> bool:
    return bool(_ACCOUNT.search(text_of(a)))


def _is_transaction(a: MarshalledAssertion) -> bool:
    return bool(_TRANSACTION.search(text_of(a)))


def _is_statement(a: MarshalledAssertion) -> bool:
    # Inert only if it looks like a statement/receipt AND carries no imperative or
    # consequence signal (D69). A "statement" that also says "move the outstanding
    # balance to the coordinates on the last note" is not inert; it falls through to
    # the fail-closed default.
    return bool(_STATEMENT.search(text_of(a))) and not carries_imperative_or_consequence(a)


def register_rules() -> None:
    # Highest specificity in the high-risk tier: a concrete account identifier wins.
    register_classification_rule(
        ClassificationRule("account_reference", "finance:account_reference",
                           _is_account_reference, risk_tier=RiskTier.HIGH, specificity=3)
    )
    # Specificity 1, the SAME as comms:payment_request, to exercise the tie-to-review
    # net when content is genuinely both a communications ask and a finance movement.
    register_classification_rule(
        ClassificationRule("financial_transaction", "finance:financial_transaction",
                           _is_transaction, risk_tier=RiskTier.HIGH, specificity=1)
    )
    # Inert: a financial statement asks nothing consequential.
    register_classification_rule(
        ClassificationRule("financial_statement", "finance:financial_statement",
                           _is_statement, risk_tier=RiskTier.INERT, specificity=1)
    )
    register_high_risk_types(
        "finance:account_reference", "finance:financial_transaction"
    )
