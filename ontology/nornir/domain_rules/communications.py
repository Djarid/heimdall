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
    RiskTier,
    register_classification_rule,
    register_high_risk_types,
    text_of,
)


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


# A POSITIVE informational signal: the message reports, announces or describes,
# rather than asking the reader to do something. This is a whitelist, not a
# blacklist: inertness must be earned by looking informational, not granted by
# default. The distinction we need is narrow and stable (does this TELL or ASK?),
# unlike enumerating which bad action is being requested, which is fragile.
_INFORMATIONAL = re.compile(
    r"\b(fyi|for your information|newsletter|digest|announce|announcing|update on|"
    r"read more|no action (is )?(needed|required)|here (is|are)|please find|"
    r"attached (is|are|you)|notes? from|minutes of|summary of|recap|programme|"
    r"published|now live|is available to (view|read)|report for|"
    r"notification|status (update|notification)|this is to (inform|notify|let you know)|"
    r"a heads[- ]up|just so you know)\b"
)
# An IMPERATIVE / request signal: the message asks the reader to DO something. Kept
# deliberately generic (does it ask?), NOT a list of specific bad actions. A message
# that asks but matches no known high-risk type is an unrecognised request and fails
# closed to review, so this detector being imperfect only ever means "more review",
# never "silent inert". Note bare "please" is deliberately NOT here: on its own it is
# politeness ("please find attached") not a request. We require please/kindly to be
# followed by an action, or an action/request phrase to stand alone.
_IMPERATIVE = re.compile(
    r"\b((please|kindly) (?!find|see|note|be advised|disregard|ignore)\w+|"
    r"can you|could you|would you|need you to|"
    r"make sure|ensure you|"
    r"send|buy|purchase|confirm|provide|share|reply with|respond with|"
    r"go to|visit|use the new|use the (new )?details|as (we )?discussed|as agreed|"
    r"(?<!no )action (needed|required)|get back to me|move the|take care of)\b"
)


def _is_communication(a: MarshalledAssertion) -> bool:
    return bool(a.fields.get("sender_extracted") or a.fields.get("subject_extracted"))


def _is_informational(a: MarshalledAssertion) -> bool:
    """POSITIVELY informational: a communication that shows an informational signal
    and NO imperative. Earning the inert label requires both. A message that both
    informs and asks is treated as asking (it falls through to the FALLBACK
    unrecognised_request), because the ask is the part that could be consequential."""
    if not _is_communication(a):
        return False
    text = text_of(a)
    return bool(_INFORMATIONAL.search(text)) and not _IMPERATIVE.search(text)


def register_rules() -> None:
    # High-risk requested-action subtypes. Risk tier HIGH so they beat any inert
    # catch-all (D31). Specificity 1: these match a specific high-risk vocabulary. A
    # broad instruction verb is deliberately LESS specific (specificity 0) so a
    # domain rule matching a narrower, stronger signal can outrank it within the tier.
    register_classification_rule(
        ClassificationRule("payment_request", "comms:payment_request", _is_payment,
                           risk_tier=RiskTier.HIGH, specificity=1)
    )
    register_classification_rule(
        ClassificationRule("credential_request", "comms:credential_request", _is_credential,
                           risk_tier=RiskTier.HIGH, specificity=1)
    )
    # The instruction rule matches broad action verbs (run, deploy, configure...).
    # It is high-risk but LOW specificity, because those verbs also appear in other
    # domains' content (a scheduled task "runs"). Low specificity lets a domain with a
    # stronger, narrower signal win the tier; where none does, this still gates.
    register_classification_rule(
        ClassificationRule("instruction_to_act", "comms:instruction_to_act", _is_instruction,
                           risk_tier=RiskTier.HIGH, specificity=0)
    )
    # Inert ONLY if positively informational (informational signal and no imperative).
    # Inert tier: earned, not default.
    register_classification_rule(
        ClassificationRule("informational_statement", "comms:informational_statement",
                           _is_informational, risk_tier=RiskTier.INERT, specificity=1)
    )
    # The fail-closed default: a communication that matched NO positive rule of any
    # domain. FALLBACK tier, below inert, so any positive classification (a calendar
    # entry, a financial statement, a genuine informational statement) wins over it;
    # it only fires as a last resort, and then routes to review. This is what stops an
    # evasively-phrased request from silently going inert, without a blacklist of bad
    # phrasings (invariant 3.5): we do not name the bad thing, we decline to assume
    # safety when nothing positively classified the content.
    register_classification_rule(
        ClassificationRule("unrecognised_request", "comms:unrecognised_request",
                           _is_communication, risk_tier=RiskTier.FALLBACK, specificity=0)
    )
    # Declare which communications types are high-risk (drives the shared derivation
    # rule and the harness's downgrade check). unrecognised_request is REVIEW, not
    # high-risk: it is gated by routing to a human, not by being a known consequential
    # type.
    register_high_risk_types(
        "comms:payment_request", "comms:credential_request", "comms:instruction_to_act"
    )
