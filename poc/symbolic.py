"""Symbolic layer for the Heimdall premise proof-of-concept.

This is the symbolic half of the paired symbolic-plus-LLM pipeline. It is plain
deterministic Python: parsing, rules and a schema. It contains NO language model
of any kind, direct or indirect. Origin determines trust, not content.

If you are reading this file to add a model call to "help classify", stop. The
separation of data from control here is structural and provenance-based. A model
in this layer would itself be injectable and the whole test would be void.

Input: a raw message as text (the content of one corpus case).
Output: a typed record (a dict) in which untrusted body content is quarantined
        in a named data field, never merged into any instruction or control
        field.
"""

from __future__ import annotations

import re

from email import message_from_string
from email.message import Message
from email.utils import parseaddr


PROVENANCE_UNTRUSTED = "UNTRUSTED"


# Chat-template control-token strings. If an untrusted payload contains these
# verbatim, the tokenizer promotes them to real control tokens, which would let
# the payload forge a role boundary (a break of the data/instruction boundary
# one layer below the string delimiter). The neural layer already neutralises
# this at encode time (split_special_tokens=True), but we also neutralise here
# as defence in depth, so the quarantined payload cannot forge a boundary no
# matter how it is later encoded. This is deterministic string handling, not an
# interpretation of intent: origin still determines trust.
_CONTROL_MARKER_RE = re.compile(r"<\|[^>]*?\|>")


def neutralise_control_markers(text: str) -> str:
    """Break any chat-template control-token strings in untrusted text.

    ``<|im_start|>`` becomes ``<| im_start |>`` and so on. The change is
    visible, reversible by eye and cannot itself be steered by the payload. It
    only ever fires on the ``<|...|>`` shape, so ordinary prose is untouched.
    """
    return _CONTROL_MARKER_RE.sub(lambda m: m.group(0).replace("<|", "<| ").replace("|>", " |>"), text)


def _extract_body(msg: Message) -> str:
    """Extract the full body text from a parsed email message, verbatim.

    Multipart messages are flattened by concatenating the text payloads in
    order. Non-text parts are described structurally rather than decoded, so
    that nothing is silently dropped. This is deterministic string handling
    only, no interpretation of intent.
    """
    if not msg.is_multipart():
        payload = msg.get_payload(decode=False)
        if isinstance(payload, str):
            return payload
        return str(payload)

    parts: list[str] = []
    for part in msg.walk():
        if part.is_multipart():
            continue
        content_type = part.get_content_type()
        payload = part.get_payload(decode=False)
        if isinstance(payload, list):
            payload = "".join(str(p) for p in payload)
        if not isinstance(payload, str):
            payload = str(payload)
        if content_type.startswith("text/"):
            parts.append(payload)
        else:
            parts.append(f"[non-text part: {content_type}]\n{payload}")
    return "\n".join(parts)


def to_typed_record(raw_text: str, source: str) -> dict:
    """Parse one raw message into a typed, provenance-stamped record.

    Behaviour:
      1. Parse the raw message into structural parts with the standard-library
         ``email`` module only.
      2. Stamp everything derived from the raw message as UNTRUSTED.
      3. Neutralise any chat-template control-token strings in the untrusted
         content (defence in depth against tokenizer-level boundary forgery).
      4. Place the untrusted body in ``data_payload``. It is never concatenated
         into an instruction, system prompt or task string.

    The function is a pure function of its inputs: the same ``raw_text`` and
    ``source`` always produce the same record.
    """
    if not isinstance(raw_text, str):
        raise TypeError("raw_text must be str; the symbolic layer parses text only")

    msg = message_from_string(raw_text)

    # Deterministic header extraction. These are parsed structural fields, not
    # trusted content: they are still UNTRUSTED by origin. They exist so the
    # neural layer has typed slots to extract into, and so the harness can see
    # what deterministic parsing recovered independently of the model.
    raw_from = msg.get("From", "")
    _display, sender_addr = parseaddr(raw_from)
    sender = sender_addr or raw_from.strip()
    subject = (msg.get("Subject", "") or "").strip()

    body = _extract_body(msg)
    body = body if body else raw_text

    # Neutralise control-token strings everywhere the untrusted content flows.
    sender = neutralise_control_markers(sender)
    subject = neutralise_control_markers(subject)
    payload = neutralise_control_markers(body)
    neutralised = payload != body

    return {
        "provenance": PROVENANCE_UNTRUSTED,
        "source": source,
        # Record that neutralisation happened, so the harness and a reviewer can
        # see the payload was altered from verbatim and why.
        "control_markers_neutralised": neutralised,
        "parsed_fields": {
            "sender": sender,
            "subject": subject,
        },
        # The full body, quarantined here as data with control markers broken.
        # Never an instruction. If headers failed to parse (a plain-text case
        # with no email structure), the whole raw text is still available here.
        "data_payload": payload,
    }


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) != 2:
        print("usage: python symbolic.py <path-to-raw-message>", file=sys.stderr)
        raise SystemExit(2)

    path = sys.argv[1]
    with open(path, "r", encoding="utf-8") as handle:
        raw = handle.read()
    record = to_typed_record(raw, source=path)
    print(json.dumps(record, indent=2, ensure_ascii=False))
