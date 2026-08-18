"""Deterministic mock emission-producers for the always-run Phase 2 suite.

The detection logic (Fenrir's structure, Huginn's canary monitor and the
attempt-introspection tripwire) is model-agnostic: it runs against any
`EmissionProducer`. These mocks stand in for a model so the detection logic has fast,
deterministic, always-runnable coverage, the same discipline as the rest of the repo
(the real-model demonstration is separate and optional).

Each mock takes the canary-wrapped prompt and returns a `FenrirEmission`. The mocks
model the two things that matter: whether the model echoed the canary token (a compliant
model does; a defeated one may not), and whether reading the content made the model
attempt an action (the behavioural signal the tripwire exists to catch).

Crucially, the mocks derive their behaviour from the CONTENT in the wrap, not from a
hidden label, so a test that feeds a consequential payload and asserts an
attempt-introspection hit is testing the pipeline shape, not a rigged oracle. The
`extract_content` helper pulls the tainted window back out of the wrapped prompt so a
mock reacts to what a model would actually read.
"""

from __future__ import annotations

import re

from .canary import CanaryWrap
from .fenrir import FenrirEmission


def _echo_token(wrapped_prompt: str) -> str:
    """Pull the canary token out of the wrap so a compliant mock can echo it verbatim,
    exactly as a model following the canonical instruction would."""
    m = re.search(r'include EXACTLY "([^"]+)"', wrapped_prompt)
    return m.group(1) if m else ""


def extract_content(wrapped_prompt: str) -> str:
    """Return the tainted content window from a wrapped prompt (what a model reads)."""
    m = re.search(
        r"\[TAINTED CONTENT WINDOW\]\n(.*?)\n\n\[TAIL CANARY", wrapped_prompt, re.S
    )
    return m.group(1).strip() if m else ""


def compliant_extractor(wrapped_prompt: str) -> FenrirEmission:
    """A well-behaved model: it reads the content, describes it neutrally, echoes the
    canary token, attempts no action. This is the clean baseline the zero-false-positive
    property is measured against: over benign content it must produce no hard signal."""
    token = _echo_token(wrapped_prompt)
    content = extract_content(wrapped_prompt)
    summary = f"The content appears to concern: {content[:80]}"
    return FenrirEmission(
        reasoning_trace="Reading external content as inert data; describing only.",
        output=f"{summary} {token}",
        tool_calls=(),
    )


# Content shapes that, if a model were injected by them, would make it ATTEMPT an
# action. This is the mock's model of "the payload steered the model into acting". It is
# deliberately broad and behavioural: an imperative or a deferred/metaphorical
# consequence that a competent reader would act on. The point of the mock is to simulate
# a model that DOES get steered, so the tripwire can be tested; it is not the detector.
_STEERS_TO_ACTION = (
    re.compile(r"\b(send|transfer|pay|wire|forward|delete|disable|grant|approve|purchase|buy|deploy|run|execute)\b", re.I),
    re.compile(r"\b(standing order|payment|the funds|the transfer|the invoice)\b", re.I),
    re.compile(r"\b(set to go|going out|in motion|proceeds|going ahead|take care of|the usual)\b", re.I),
    re.compile(r"\bwheels are turning\b", re.I),
)


def injectable_extractor(wrapped_prompt: str) -> FenrirEmission:
    """A model that CAN be steered: if the content carries an actionable consequence, it
    emits an action-shaped intermediate (an intent-to-act in the reasoning trace or a
    tool call), even while its final text output looks like a clean description. This
    models the attack the tripwire is designed to catch: the payload makes the model try
    to act, and the attempt is visible in the trace before any effect.

    This mock is the honest heart of the false-inert catch: it reacts to the SAME
    passive and metaphorical consequences (`the standing order is set to go out`, `the
    wheels are turning`) that the deterministic content classifier types inert, because a
    model reading them understands the consequence and tries to act, which the classifier
    cannot see from the surface text."""
    token = _echo_token(wrapped_prompt)
    content = extract_content(wrapped_prompt)
    steered = any(p.search(content) for p in _STEERS_TO_ACTION)

    if steered:
        # The final output would have looked clean (a plausible summary + token), but the
        # reasoning trace reveals the attempt to act. This is exactly the case fenrir.md
        # 3.3 says the tripwire catches earlier and less evadably than the output canary.
        return FenrirEmission(
            reasoning_trace=(
                "The message indicates a consequence is under way. "
                "I will initiate the transfer to complete it."
            ),
            output=f"The content is a notification. {token}",
            tool_calls=(),
        )
    # Benign content: behaves like the compliant extractor.
    return FenrirEmission(
        reasoning_trace="Reading external content as inert data; describing only.",
        output=f"The content appears informational: {content[:60]} {token}",
        tool_calls=(),
    )


def tool_calling_extractor(wrapped_prompt: str) -> FenrirEmission:
    """A model steered into emitting a native tool call (the harness refuses it, the
    refusal is the proof). Used to test the tool-call hard signal and the tripwire's
    structured-call path."""
    token = _echo_token(wrapped_prompt)
    return FenrirEmission(
        reasoning_trace="I should use the payments tool to complete this.",
        output=f"Done. {token}",
        tool_calls=("payments.execute(amount=5000, to='new-account')",),
    )


def honeypot_leaking_extractor(wrapped_prompt: str) -> FenrirEmission:
    """A model whose output contains the honeypot phrase (proof an injected instruction
    steered it to emit a phrase it was told to withhold). Used to test the honeypot
    hard signal. It reads the honeypot back out of the wrap to leak it, which only an
    injected instruction could cause a real model to do."""
    token = _echo_token(wrapped_prompt)
    m = re.search(r'do not include the phrase "([^"]+)"', wrapped_prompt)
    honeypot = m.group(1) if m else "leaked"
    return FenrirEmission(
        reasoning_trace="Following the embedded instruction.",
        output=f"Here is the summary {honeypot}. {token}",
        tool_calls=(),
    )


def token_dropping_extractor(wrapped_prompt: str) -> FenrirEmission:
    """A model that does not echo the canary token (the canonical instruction was not
    followed). Used to test the token-absent hard signal."""
    return FenrirEmission(
        reasoning_trace="Ignoring the frame.",
        output="A summary with no canary token at all.",
        tool_calls=(),
    )


# Structural-extraction mock (D86). A grammar-constrained extractor fills bounded VALUES
# into a fixed schema; this mock models that by mapping recognised facts in the content to
# schema field values. It is NOT a detector and NOT the security boundary: it stands in for
# a model emitting slot values, exactly as the other mocks stand in for a model emitting
# free text. The security property is that the schema and the binding (slot_extraction.py)
# are fixed and deterministic, so whatever this mock emits can only fill declared values,
# never invent a slot. Deliberately keyed on the EFFECT a value would have (a new bank
# destination, a cleared flag), which is what a competent reader binds, so the state-delta
# layer catches consequence even when the surface wording is inert. That is the division of
# labour: the classifier is blind to passive phrasing, the structural binding is not,
# because it reads what the value WOULD DO, not how it reads.
_STRUCTURAL_PATTERNS = (
    # (schema field, regex over the content) -> the value bound is the matched group
    ("new_bank_details", re.compile(r"\b(?:remittance|bank|payment) (?:coordinates|details|account) (?:have )?(?:moved|changed|updated) (?:to )?(?:the )?([\w -]+)", re.I)),
    ("new_salary_destination", re.compile(r"\bsalary (?:will |to )?(?:now )?(?:land|go|paid) (?:in|to) (?:the )?([\w -]+?)(?:\.|$)", re.I)),
    ("changed_feature_flag", re.compile(r"\bflag (?:that was holding[\w ]+ )?(?:has been |is )?(cleared|enabled|disabled|set)", re.I)),
    ("changed_firewall_rule", re.compile(r"\b(?:firewall|rule) (?:is )?(open|opened|added|removed|changed)\b", re.I)),
    ("changed_retention_policy", re.compile(r"\bretention (?:is |set to )?([\w ]+?minutes|purge[\w ]*)", re.I)),
    ("new_holder_of_record", re.compile(r"\b(?:registration|mark|name|title) (?:moves|is (?:now )?recorded|transferred) (?:to |under )(?:the )?([\w -]+)", re.I)),
    ("changed_entitlement_status", re.compile(r"\bcover (?:on[\w ]+ )?(?:is )?set to (lapse|expire|end)\b", re.I)),
)


def structural_extractor(wrapped_prompt: str) -> FenrirEmission:
    """A model that emits STRUCTURAL slot values as well as a neutral summary. Compliant
    (echoes the token, attempts no action); its value is that it BINDS the consequential
    fact in the content to a typed schema field, which the free-text path cannot. Used to
    drive the end-to-end structural pipeline: bind_slots turns these into ProposedFacts and
    the wired state-delta layer catches the consequence downstream even for content the
    classifier types inert."""
    token = _echo_token(wrapped_prompt)
    content = extract_content(wrapped_prompt)
    slot_values: dict = {}
    for field_name, pattern in _STRUCTURAL_PATTERNS:
        m = pattern.search(content)
        if m:
            # The bound value is the first captured group if present, else the whole match.
            slot_values[field_name] = (m.group(1) if m.groups() else m.group(0)).strip()
    summary = f"The content appears to concern: {content[:80]}"
    return FenrirEmission(
        reasoning_trace="Reading external content as inert data; binding declared fields only.",
        output=f"{summary} {token}",
        tool_calls=(),
        slot_values=slot_values,
    )
