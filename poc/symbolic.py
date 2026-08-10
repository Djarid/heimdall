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

from email import message_from_string
from email.message import Message
from email.utils import parseaddr


PROVENANCE_UNTRUSTED = "UNTRUSTED"


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
      3. Place the untrusted body verbatim in ``data_payload``. It is never
         concatenated into an instruction, system prompt or task string.

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

    return {
        "provenance": PROVENANCE_UNTRUSTED,
        "source": source,
        "parsed_fields": {
            "sender": sender,
            "subject": subject,
        },
        # The full body, verbatim, quarantined here as data. Never an
        # instruction. If headers failed to parse (a plain-text case with no
        # email structure), the whole raw text is still available as data.
        "data_payload": body if body else raw_text,
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
