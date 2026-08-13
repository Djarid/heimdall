"""The marshalling seam: Fenrir's extraction envelope becomes a typed assertion.

This is the contract of `ONTOLOGY_CONSTRUCTION.md` section 5 and decision D28, made
concrete against the PoC's real extraction output. The PoC's `neural.py` produces an
extraction envelope: a fixed set of fields the model filled by reading untrusted data,
plus a provenance map marking every field UNTRUSTED_DERIVED. This module turns that
envelope into a `MarshalledAssertion` that Nornir classifies.

The discipline the contract holds, and this module enforces:

- The grammar/structure is fixed, not the model's to emit. The four fields are the
  seed schema; the model fills values, the envelope shape is assembled in Python
  (the PoC's rule, invariant 3.3-3.4). This adapter copies values into a typed
  assertion; it does not re-parse or re-interpret the model's output.
- No second interpretation pass. A second model reading the first model's output
  would reopen the injection surface one layer over (D28). This adapter is plain
  deterministic Python, no model: it maps fields to fields.
- Everything is TAINTED by origin. Fenrir read untrusted content, so every field it
  emitted is untrusted-derived regardless of how cleanly it typed. The assertion's
  taint class is set from the medium (the PoC's email corpus is EXTERNAL_COMMS), and
  Nornir stamps the trust level TAINTED at classification. Provenance is set here and
  is immutable thereafter.

`marshal` is pure (a dict in, a MarshalledAssertion out) and has no dependency on the
model or on mlx, so it can be unit-tested and imported freely. The end-to-end harness
(`ontology/tests/e2e_harness.py`) is what actually runs the model, marshals its real
output through here, and classifies and gates it, proving the contract with a real
model rather than hand-authored fixtures.
"""

from __future__ import annotations

from .assertions import MarshalledAssertion


# The PoC provenance stamp for a model-derived field, mirrored so this module does not
# import the PoC package. If the PoC's constant ever changes, the end-to-end harness
# asserts they still agree, so drift is caught rather than silent.
POC_PROVENANCE_UNTRUSTED_DERIVED = "UNTRUSTED_DERIVED"

# The seed schema fields the communications domain expects (the four PoC fields).
_SEED_FIELDS = ("sender_extracted", "subject_extracted", "requested_action_summary", "entities")


def marshal(
    assertion_id: str,
    extraction: dict,
    provenance: dict,
    taint_class: str = "taint:EXTERNAL_COMMS",
    flows: tuple = (),
) -> MarshalledAssertion:
    """Marshal a PoC extraction envelope into a typed MarshalledAssertion (D28).

    `extraction` is the PoC's field dict; `provenance` maps each field to its origin
    stamp. This function is deterministic and model-free: it copies field values into
    the assertion, it does not interpret them. It fails closed on a provenance
    violation: if any field claims to be anything other than untrusted-derived, that
    is a contract breach (the model only ever read untrusted data), and we raise
    rather than silently trust it.
    """
    for field_name, origin in provenance.items():
        if origin != POC_PROVENANCE_UNTRUSTED_DERIVED:
            raise ValueError(
                f"marshalling contract breach: field {field_name!r} has provenance "
                f"{origin!r}, expected {POC_PROVENANCE_UNTRUSTED_DERIVED!r}. Every field "
                f"a model produced from untrusted content is untrusted-derived (D28); a "
                f"field claiming otherwise must not be marshalled as trusted."
            )
    # Copy only the recognised seed fields; the structure is fixed, not the model's to
    # extend. `entities` is a list in the PoC; the classifier reads text fields, so we
    # carry it through unchanged for the record but do not let it drive classification
    # any differently from the PoC.
    fields = {}
    for key in _SEED_FIELDS:
        if key in extraction:
            fields[key] = extraction[key]
    return MarshalledAssertion(
        assertion_id=assertion_id,
        taint_class=taint_class,
        fields=fields,
        flows=tuple(flows),
    )
