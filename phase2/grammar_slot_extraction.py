"""True token-level grammar-constrained structural slot extraction (D90).

D86 built the structural slot extraction and D87 demonstrated it with a real model, but by
the Phase-2 STAND-IN that `plans/dd/fenrir.md` 3.1 sanctions: one bounded per-field
sub-generation with a newline hard-stop, the JSON envelope assembled in Python. fenrir.md
3.1 names the eventual design explicitly: TRUE grammar-constrained decoding, where the model
emits DIRECTLY into the typed schema and can only produce tokens valid within the grammar, so
there is no natural-language output to re-parse and no second parsing pass to reintroduce an
injection surface. This module builds that.

What "true grammar-constrained" buys over the D87 stand-in, and why it is a real advance and
not a rename:

  - D87 ran N separate generations (one per field) and assembled the JSON object in Python.
    The model never saw or emitted the envelope; Python did. That proves the VALUES can be
    extracted, but the structure is still Python's, so the marshalling problem is dissolved by
    fiat rather than by the decode.
  - This runs ONE generation that emits the whole object, with a logits mask at every step
    that permits ONLY tokens keeping the output a valid prefix of the schema grammar. The
    envelope (braces, the fixed field keys, quoting, commas) is emitted BY THE MODEL but is
    not the model's to CHOOSE: the mask forces the structure token by token. A malformed
    object is unreachable by construction, and the field keys are fixed by the grammar, so the
    model cannot invent a key the schema did not declare. This is the fenrir.md 3.1 property.

The invariant 3.1 boundary is unchanged and load-bearing. The grammar and the schema are
fixed, authored Python; the model fills bounded VALUE spans only; the binding to typed
`ProposedFact`s stays the deterministic `bind_slots` from `slot_extraction.py` (no second
model pass). phase2 is not on the authorisation path, so nornir/yggdrasil have no dependency
on this and the 3.1 AST guard stays clean and scoped.

The constraint is implemented natively with mlx_lm's `logits_processors` hook, the SAME
mechanism the PoC's proven `_StopOnNewline` uses, rather than adding a grammar library
(outlines/xgrammar). That keeps the dependency surface at the PoC's single `mlx-lm`, and the
constraint is small, self-contained and directly testable: `GrammarState` is pure Python and
is exercised deterministically in the harness WITHOUT a model, so the grammar's correctness is
proven independently of any model run.

Honest scope:

  - Real-model runs are non-deterministic and slow, so the model demonstration is OPTIONAL and
    skip-if-absent, like `real_slot_demo.py` and the e2e harness. The GRAMMAR ITSELF is tested
    deterministically and always runs.
  - Value poisoning stays open (fenrir.md 9, FR-6): the grammar constrains the STRUCTURE and
    that a value is a well-formed string, not that the value is the TRUE one. A model can still
    emit a schema-valid wrong value; that is contained by Gjoll at action time, not here. Note
    the distinction from D89's gate work: this hardens extraction structure, not sink honesty.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .slot_extraction import SEED_SLOT_SCHEMA, SlotExtractionSchema


# The JSON grammar this module constrains to is deliberately narrow: a single object whose
# keys are EXACTLY the schema field names in order, each mapped to a JSON string. The value
# strings are the only free spans; everything else (braces, keys, quotes, colons, commas) is
# forced. A string value may be the sentinel "none" to mean the field is not stated, which
# `bind_slots` already treats as unbound. This is the smallest grammar that makes the envelope
# unforgeable while leaving the extraction values free.


class GrammarState:
    """A deterministic state machine over the target JSON grammar for a fixed field list.

    It answers one question at each decode step: given the characters emitted so far, which
    NEXT characters keep the output a valid prefix of the grammar? The logits processor turns
    that character-level answer into a token-level mask. The machine is pure Python and has no
    model dependency, so its correctness is proven in the harness by driving it with strings.

    The grammar, as a sequence of segments:

        { "<key0>": "<value0>" , "<key1>": "<value1>" , ... , "<keyN>": "<valueN>" }

    with insignificant whitespace permitted between structural tokens. Inside a value string,
    any character is allowed except an unescaped quote (which closes the string) and a control
    character; a backslash starts a two-character escape. Keys are FIXED literals: the machine
    emits them itself and the model has no choice over them.
    """

    def __init__(self, field_names: tuple[str, ...]):
        if not field_names:
            raise ValueError("the grammar needs at least one field")
        self._fields = field_names
        # The fixed literal skeleton the machine walks, as a list of ("literal", text) and
        # ("value", field_name) segments. Whitespace is allowed but never required.
        self._segments: list[tuple[str, str]] = [("literal", "{")]
        for i, name in enumerate(field_names):
            if i:
                self._segments.append(("literal", ","))
            self._segments.append(("literal", f'"{name}":'))
            self._segments.append(("value", name))
        self._segments.append(("literal", "}"))
        self.reset()

    def reset(self) -> None:
        self._seg = 0          # index into self._segments
        self._pos = 0          # position within the current literal segment
        self._in_value = False  # currently inside a value string's body
        self._value_open = False  # emitted the opening quote of the current value
        self._escape = False   # last char inside a value was a backslash
        self._done = False
        self._values: dict[str, list[str]] = {n: [] for n in self._fields}
        self._cur_field: str | None = None

    @property
    def done(self) -> bool:
        return self._done

    def clone(self) -> "GrammarState":
        """A cheap copy of the current position, for testing a candidate continuation without
        disturbing the live machine. Used by the logits mask to check each candidate token in
        O(token length) from the CURRENT state, instead of replaying all accepted text."""
        c = GrammarState.__new__(GrammarState)
        c._fields = self._fields
        c._segments = self._segments
        c._seg = self._seg
        c._pos = self._pos
        c._in_value = self._in_value
        c._value_open = self._value_open
        c._escape = self._escape
        c._done = self._done
        c._cur_field = self._cur_field
        # Values are not needed for a legality probe, so share empty lists (never mutated on a
        # probe that only calls allowed()/advance() for the accept/reject decision).
        c._values = {n: [] for n in self._fields}
        return c

    def accepts(self, addition: str) -> bool:
        """Would `addition`, applied from the CURRENT state, stay a valid grammar prefix?"""
        probe = self.clone()
        for ch in addition:
            if not probe.allowed().permits(ch):
                return False
            probe.advance(ch)
        return True

    def values(self) -> dict[str, str]:
        """The extracted value strings so far, decoded from the sentinel."""
        out: dict[str, str] = {}
        for name in self._fields:
            v = "".join(self._values[name])
            out[name] = v
        return out

    def allowed(self) -> "AllowedChars":
        """Which characters may legally come next. Returns an AllowedChars describing the
        permitted set: a fixed required char (for a literal position), the option to open or
        continue a value, whether whitespace is allowed, and whether the object may end."""
        if self._done:
            return AllowedChars(finished=True)

        seg_kind, seg_text = self._segments[self._seg]

        if seg_kind == "literal":
            # Inside a fixed literal: exactly one char is required next. JSON permits
            # insignificant whitespace between structural tokens, so whitespace is allowed at
            # the START of any literal segment (before its first char), never mid-token.
            required = seg_text[self._pos]
            allow_ws = (self._pos == 0)
            return AllowedChars(required_char=required, allow_whitespace=allow_ws)

        # seg_kind == "value": a JSON string.
        if not self._value_open:
            # Must open with a quote (whitespace allowed before it).
            return AllowedChars(required_char='"', allow_whitespace=True)
        if self._escape:
            # After a backslash, a single escape char (we accept the JSON set).
            return AllowedChars(escape_char=True)
        # Inside the value body: any non-control char; a quote closes it, a backslash escapes.
        return AllowedChars(value_body=True)

    def advance(self, ch: str) -> None:
        """Feed one accepted character, moving the machine. The caller must only pass a char
        the current `allowed()` permits; the harness asserts that discipline."""
        if self._done:
            return
        seg_kind, seg_text = self._segments[self._seg]

        if seg_kind == "literal":
            if ch.isspace():
                return  # insignificant whitespace, no state move
            # Consume the required literal char.
            self._pos += 1
            if self._pos >= len(seg_text):
                self._advance_segment()
            return

        # value segment
        if not self._value_open:
            if ch.isspace():
                return
            if ch == '"':
                self._value_open = True
                self._cur_field = seg_text  # seg_text is the field name for a value segment
            return
        if self._escape:
            self._values[self._cur_field].append(ch)
            self._escape = False
            return
        if ch == "\\":
            self._escape = True
            self._values[self._cur_field].append(ch)
            return
        if ch == '"':
            # Close the value.
            self._value_open = False
            self._cur_field = None
            self._advance_segment()
            return
        self._values[self._cur_field].append(ch)

    def _advance_segment(self) -> None:
        self._seg += 1
        self._pos = 0
        if self._seg >= len(self._segments):
            self._done = True


@dataclass(frozen=True)
class AllowedChars:
    """The character-level permission at one grammar position. Exactly one shape is set:

      - `required_char`: the next non-whitespace char must be this literal (structure).
      - `value_body`: inside a value string; any non-control char, plus quote (close) and
        backslash (escape).
      - `escape_char`: immediately after a backslash inside a value.
      - `finished`: the object is complete; only EOS/whitespace may follow.
    """
    required_char: "str | None" = None
    allow_whitespace: bool = False
    value_body: bool = False
    escape_char: bool = False
    finished: bool = False

    def permits(self, ch: str) -> bool:
        if self.finished:
            return ch.isspace()
        if self.value_body:
            if ch == "\n" or (ord(ch) < 0x20):
                return False  # no raw control chars in a JSON string
            return True       # includes '"' (close) and '\\' (escape)
        if self.escape_char:
            return ch in '"\\/bfnrtu'
        if self.required_char is not None:
            if self.allow_whitespace and ch.isspace():
                return True
            return ch == self.required_char
        return False


def parse_constrained(text: str, field_names: tuple[str, ...]) -> "dict[str, str] | None":
    """Drive a GrammarState over a full string, character by character, rejecting any char the
    grammar forbids. Returns the extracted value map if the string is a complete valid object,
    else None. This is the pure-Python heart the harness proves without a model: if the mask
    is correct, a model constrained by it can only ever produce strings this accepts."""
    state = GrammarState(field_names)
    for ch in text:
        allowed = state.allowed()
        if not allowed.permits(ch):
            return None
        state.advance(ch)
    if not state.done:
        return None
    return state.values()


# The value sentinel meaning "the data does not state this field", mirroring the D87 unbound
# rule so `bind_slots` drops it (no ProposedFact, no fabricated delta).
UNBOUND_SENTINEL = "none"


def constrained_values_to_emitted(values: dict[str, str]) -> dict[str, str]:
    """Turn the grammar's raw value map into the `emitted` dict `bind_slots` consumes, applying
    the unbound-sentinel rule. A value equal to the sentinel (case-insensitive) or empty is
    omitted, so it produces no binding: the same fail-closed behaviour as the D87 producer, now
    enforced by the grammar rather than by per-field prompting."""
    emitted: dict[str, str] = {}
    for name, raw in values.items():
        v = (raw or "").strip()
        if not v or v.lower() == UNBOUND_SENTINEL:
            continue
        emitted[name] = v
    return emitted
