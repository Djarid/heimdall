"""Downstream sinks for the Heimdall premise proof-of-concept.

This module tests the load-bearing half of the premise: that untrusted
instructions embedded in data do not cause action. Earlier phases proved the
extraction is inert typed data. This phase adds something that actually acts, a
downstream sink, and checks whether the pipeline's provenance discipline stops
attacker-influenced content from reaching it as an instruction.

The design, per the Heimdall trust model:

  * Every extraction field is UNTRUSTED_DERIVED. The model produced it by
    reading untrusted data, so its content is attacker-influenceable.

  * A sink declares, per field it consumes, HOW it consumes that field: as
    INERT data (logged, stored, displayed, never acted on) or as an ACTION
    instruction (money moved, mail sent, access changed).

  * The provenance gate: a sink that consumes an UNTRUSTED_DERIVED field as an
    ACTION is acting on attacker-influenceable content. That is the violation.
    Consuming the same field as INERT is fine.

Two sinks are wired to make the test meaningful, exactly as clean controls make
an extraction pass meaningful:

  * A SAFE sink consumes extraction fields only as INERT data (an audit log).
    It must never be flagged, and its actuator must record only inert effects.

  * An UNSAFE control sink consumes an UNTRUSTED_DERIVED field as an ACTION (it
    treats the extracted summary as a payment instruction). It MUST be flagged.
    Without it, a green board would be trivial: a pipeline wired to nothing
    would pass by doing nothing, which proves nothing.

No language model is used here. The gate is structural and provenance-based.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field

from neural import PROVENANCE_UNTRUSTED_DERIVED


# How a sink consumes a given field.
CONSUME_INERT = "INERT"    # logged, stored, displayed; never acted upon
CONSUME_ACTION = "ACTION"  # drives an effect (money, mail, access)


class Actuator:
    """A mock actuator. Records effects instead of performing them.

    ``inert_effects`` are harmless (a log line). ``action_effects`` are the ones
    that would matter in the real world (a transfer, an email). In a correct
    pipeline no action effect is ever driven by attacker-influenced content.
    """

    def __init__(self) -> None:
        self.inert_effects: list[str] = []
        self.action_effects: list[str] = []

    def record_inert(self, description: str) -> None:
        self.inert_effects.append(description)

    def record_action(self, description: str) -> None:
        self.action_effects.append(description)

    def reset(self) -> None:
        self.inert_effects.clear()
        self.action_effects.clear()


@dataclass
class Sink:
    """A downstream consumer of the extraction.

    ``consumes`` maps each field the sink reads to how it reads it
    (CONSUME_INERT or CONSUME_ACTION). ``safe`` records the author's intent, for
    reporting only; the provenance gate does not trust it, it re-derives safety
    from the consumption mode and the field provenance.
    """

    name: str
    consumes: dict[str, str]
    safe: bool
    _fn: object = dataclass_field(repr=False, default=None)

    def fire(self, extraction: dict, actuator: Actuator) -> None:
        """Run the sink's effect. Called only after the gate has been checked.

        A real sink would act here. The mock records the effect on the
        actuator, tagged inert or action, so the harness can see what would have
        happened.
        """
        for fname, mode in self.consumes.items():
            value = extraction.get(fname)
            if mode == CONSUME_ACTION:
                actuator.record_action(f"{self.name}: acted on {fname}={value!r}")
            else:
                actuator.record_inert(f"{self.name}: logged {fname}={value!r}")


def provenance_violations(sink: Sink, provenance: dict) -> list[str]:
    """Return the reasons a sink is unsafe, or [] if it is safe.

    The structural gate: a sink is unsafe if it consumes any UNTRUSTED_DERIVED
    field as an ACTION. This is wording-independent and does not inspect the
    field's content at all. It is a property of the wiring, not the value.
    """
    reasons: list[str] = []
    for fname, mode in sink.consumes.items():
        if mode != CONSUME_ACTION:
            continue
        origin = provenance.get(fname)
        if origin == PROVENANCE_UNTRUSTED_DERIVED:
            reasons.append(
                f"sink {sink.name!r} consumes UNTRUSTED_DERIVED field "
                f"{fname!r} as an ACTION instruction"
            )
    return reasons


# --- The two wired sinks -------------------------------------------------

# SAFE: an audit log. It reads extraction fields but only as inert data. No
# field is consumed as an action, so no attacker content can drive an effect.
SAFE_AUDIT_LOG = Sink(
    name="audit_log",
    consumes={
        "sender_extracted": CONSUME_INERT,
        "subject_extracted": CONSUME_INERT,
        "requested_action_summary": CONSUME_INERT,
        "entities": CONSUME_INERT,
    },
    safe=True,
)

# UNSAFE control: a payment actuator mis-wired to treat the extracted summary
# (UNTRUSTED_DERIVED) as a payment instruction. This is the mistake the whole
# architecture exists to prevent. It MUST be caught by the provenance gate
# before it fires, on every case, including clean controls (the wiring is
# unsafe regardless of whether a given payload happens to contain an attack).
UNSAFE_PAYMENT_ACTUATOR = Sink(
    name="payment_actuator",
    consumes={
        "requested_action_summary": CONSUME_ACTION,
    },
    safe=False,
)


SAFE_SINKS = [SAFE_AUDIT_LOG]
UNSAFE_SINKS = [UNSAFE_PAYMENT_ACTUATOR]
ALL_SINKS = SAFE_SINKS + UNSAFE_SINKS
