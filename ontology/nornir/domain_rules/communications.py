"""Communications-domain classification rules.

The classification predicates for the communications seed domain, moved here from the
shared `rules.py` so the domain owns its rules (the D29 attach test for rules). The
predicates are deliberately broad and register high-risk first: an over-match costs a
human review, an under-match risks a downgrade (a critical finding), so the rules err
toward the higher-risk type (D48).

Reading the extracted fields to decide a type is describing untrusted content, not
obeying it. The predicates are fixed Python matched over the extracted text; they
cannot be told to reclassify by the content.
"""

from __future__ import annotations

import re

from ..assertions import MarshalledAssertion
from ..rules import (
    ClassificationRule,
    register_classification_rule,
    register_high_risk_types,
    text_of,
)
from . import priorities


_PAYMENT = re.compile(
    r"\b(payment|invoice|wire|transfer|remit|pay|bank details|account number|"
    r"iban|swift|sort code|settle|outstanding balance|purchase order)\b"
)
_INSTRUCTION = re.compile(
    r"\b(run|execute|install|configure|change the|update the|forward|delete|"
    r"disable|grant|approve|click|download|open the attachment|reset|deploy)\b"
)
_CREDENTIAL = re.compile(
    r"\b(password|passphrase|credential|mfa|2fa|one-time code|otp|verification code|"
    r"token|api key|access code|log ?in to|sign in to|authenticate)\b"
)


def _is_payment(a: MarshalledAssertion) -> bool:
    return bool(_PAYMENT.search(text_of(a)))


def _is_instruction(a: MarshalledAssertion) -> bool:
    return bool(_INSTRUCTION.search(text_of(a)))


def _is_credential(a: MarshalledAssertion) -> bool:
    return bool(_CREDENTIAL.search(text_of(a)))


def _is_communication(a: MarshalledAssertion) -> bool:
    """Anything with a sender or subject is at least a communication. The broad catch
    that keeps genuine messages inside the domain; the fail-safe is for content that
    is not recognisably a communication at all."""
    return bool(a.fields.get("sender_extracted") or a.fields.get("subject_extracted"))


def register_rules() -> None:
    # High-risk requested-action subtypes, in the HIGH_RISK band so they beat any
    # domain's catch-all. Registration order sets the tie-break within the band.
    register_classification_rule(
        ClassificationRule("payment_request", "comms:payment_request", _is_payment),
        priorities.HIGH_RISK,
    )
    register_classification_rule(
        ClassificationRule("credential_request", "comms:credential_request", _is_credential),
        priorities.HIGH_RISK,
    )
    register_classification_rule(
        ClassificationRule("instruction_to_act", "comms:instruction_to_act", _is_instruction),
        priorities.HIGH_RISK,
    )
    # The catch-all: a bare communication is informational.
    register_classification_rule(
        ClassificationRule("informational_statement", "comms:informational_statement", _is_communication),
        priorities.CATCH_ALL,
    )
    # Declare which communications types are high-risk (drives the shared derivation
    # rule and the harness's downgrade check).
    register_high_risk_types(
        "comms:payment_request", "comms:credential_request", "comms:instruction_to_act"
    )
