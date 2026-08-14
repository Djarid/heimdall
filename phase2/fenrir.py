"""Fenrir: the sandbox reading agent.

Fenrir is the only agent permitted to read tainted content directly. It reads a
canary-wrapped window and emits typed TAINTED assertions. It has no tools, no network
egress, no filesystem and no cross-invocation state, so a payload that reaches it can
influence text but cannot cause an action (fenrir.md sections 1 and 2, invariant 3.8).

This module is model-agnostic. The model is injected as an `EmissionProducer`: a
callable that, given the canary-wrapped prompt, returns a `FenrirEmission` (the
reasoning trace plus the output). That lets the same code run against a deterministic
MOCK (the always-run suite) and the real mlx model (the optional demonstration). The
security properties live in the structure around the producer, not in the model:

- Empty capability set. Fenrir exposes no tool, shell, filesystem or network handle. A
  request to act can be EMITTED by the model (that is the attempt-introspection signal)
  but there is nothing for it to act with, so it cannot be fulfilled. The zero-false-
  positive property of the tripwire (huginn.py) holds only while this set stays empty.
- Fresh context per invocation. `extract` carries no state between calls.
- Tainted output only. Every assertion Fenrir returns is TAINTED and non-actionable; it
  requires downstream promotion before any action, which Fenrir never performs.
- No egress role. Fenrir returns its emission to the caller (Huginn, then Nornir); it
  never reaches the control channel and has no path off the trust boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .canary import CanaryWrap, build_wrap


# Fenrir's capability set. Empty by construction, and this is the load-bearing fact:
# the tripwire's zero-false-positive property is a property of this emptiness
# (fenrir.md line 93). A non-empty set here is a change to the security contract, not a
# configuration tweak, so it is defined as a frozen empty set and asserted at use.
FENRIR_CAPABILITIES: frozenset[str] = frozenset()

TAINTED = "TAINTED"


@dataclass(frozen=True)
class FenrirEmission:
    """What a model produces in one Fenrir invocation, as the monitor sees it.

    `reasoning_trace` is the intermediate token stream (where an intent-to-act reveals
    itself before any final output). `output` is the final text. `tool_calls` is any
    structured action request the harness intercepted (in the live system, a native
    tool-call the empty capability set refuses; here, whatever the producer reports).
    Separating the trace from the output is what makes attempt introspection earlier
    and less evadable than the output canary (fenrir.md 3.3)."""

    reasoning_trace: str
    output: str
    tool_calls: tuple[str, ...] = ()


# An EmissionProducer takes the wrapped prompt and returns an emission. The real model
# and the mock both satisfy this signature.
EmissionProducer = Callable[[str], FenrirEmission]


@dataclass
class FenrirAssertion:
    """A typed tainted assertion Fenrir emits. Always TAINTED, never action-capable."""

    field_name: str
    value: str
    taint: str = TAINTED
    action_capable: bool = False


@dataclass
class FenrirRun:
    """The full record of one Fenrir invocation, handed to Huginn for monitoring.
    Carries the wrap (so Huginn can check the output against the token and honeypot),
    the raw emission, and the parsed assertions."""

    wrap: CanaryWrap
    emission: FenrirEmission
    assertions: list[FenrirAssertion] = field(default_factory=list)


def extract(
    tainted_content: str,
    producer: EmissionProducer,
    task: str = "Extract the requested fields from the external content.",
    output_schema: str = "requested_action_summary: one neutral sentence",
) -> FenrirRun:
    """Read a tainted-content window and return a FenrirRun for monitoring.

    Fresh context per call (no module or closure state persists between invocations).
    The content is placed only in the canary window, never in the instruction frame.
    The producer (mock or real model) generates the emission; Fenrir itself performs no
    action and holds no capability. Every parsed assertion is TAINTED and inert."""
    # Structural assertion: Fenrir must hold no capability. If this ever fails, the
    # tripwire's zero-false-positive property is void, so fail loudly rather than
    # silently degrade (fenrir.md FR-1).
    assert FENRIR_CAPABILITIES == frozenset(), (
        "Fenrir capability set is non-empty; the attempt-introspection guarantee is void"
    )

    wrap = build_wrap(task=task, output_schema=output_schema, tainted_content=tainted_content)
    emission = producer(wrap.full_prompt)

    # Parse the (single, for this build) field as a tainted assertion. The output is
    # never trusted or acted on here; parsing only gives downstream a typed slot.
    assertions = [
        FenrirAssertion(field_name="requested_action_summary", value=emission.output.strip())
    ]
    return FenrirRun(wrap=wrap, emission=emission, assertions=assertions)
