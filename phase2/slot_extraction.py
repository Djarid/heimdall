"""Structural slot extraction: Fenrir binds values to typed slots, not just free text.

Why this exists. The false-inert mitigations D79 to D82 are wired into the live engine
and gate (D84), and the state-delta layer (D79) is the one that catches consequence by
EFFECT rather than by wording. But it can only bite where extraction binds a value to a
typed slot (`salary_destination = X`), and today Fenrir's `extract` emits a single
free-text `requested_action_summary`, the interpretive fallback. So the pipeline score
(D83) supplies the slot bindings from the corpus's `structural` blocks rather than from a
live extraction, which is the honest caveat on the 33-of-33 figure. This module produces
those bindings from tainted content, closing the caveat structurally.

The contract, and the one distinction that keeps it safe (invariant 3.1). Fenrir runs a
model, but the model's only job here is to FILL BOUNDED VALUES into a fixed schema. It
never chooses which slot a value targets and never emits the envelope structure: the
`SlotExtractionSchema` is authored, reviewed and fixed, exactly like the consequential-
sink set. The binding from an emitted value to a `ProposedFact` is plain deterministic
Python, the same discipline as `ontology/nornir/marshalling.py`: no second model pass, no
re-interpretation, so nothing on the authorisation path becomes a model. `fenrir.md`
section 3.1 (FR-2) prefers exactly this: grammar-constrained decoding into the typed
schema, so the structure is not the model's to emit.

Fail-closed in both directions:

  - A field the model does not fill, or fills with an empty or low-confidence value,
    produces NO `ProposedFact`. Absence never fabricates a delta, so the state-delta
    layer's "only ever adds caution" property (D79) is preserved: an unbound field is
    invisible to it, and an unbound field is also not an actionable premise, so harm
    potential and detectability stay tied together.
  - A value the model DOES bind to a declared consequential slot flows straight into the
    D79 detector as a `ProposedFact`, where a state comparison (not a text match) decides
    whether it is a consequential delta. The model cannot phrase around this: to redirect
    a payroll it must actually bind a new value to `salary_destination`, and that binding
    IS the delta.

This module is model-agnostic, like the rest of Fenrir: it takes the emitted field-value
map from any `EmissionProducer` and binds it deterministically. The mock producer in the
suite emits values from content; the real model would emit them under grammar constraint.
Neither the schema nor the binding is the model's to alter.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The state-delta primitives are the contract this module binds to. They live on the
# authorisation path (ontology/nornir); importing them here in phase2 is fine because
# phase2 is NOT on the authorisation path (the 3.1 guard scopes to yggdrasil, nornir and
# poc/symbolic.py). The binding produced here is handed to Nornir as inert typed data.
from ontology.nornir.state_delta import CONSEQUENTIAL_SLOTS, ProposedFact, SlotRef
from ontology.nornir.marshalling import marshal

from .fenrir import FenrirRun


@dataclass(frozen=True)
class SlotField:
    """One field a grammar-constrained extraction may bind.

    `field_name` is the schema field the model fills (a bounded value). `slot` is the
    typed slot that value targets, and `entity_ref` is how the target entity is named. In
    a full build the entity would itself be resolved structurally; here it is a fixed
    reference per field (a supplier, an employee, a policy), which is enough to give the
    state-delta layer a concrete `SlotRef` to compare against stored state. `slot` MUST be
    a declared consequential slot: a schema field pointing at a non-consequential slot is
    a schema error, caught at construction, so the schema cannot silently bind values to
    slots the state-delta layer ignores."""

    field_name: str
    entity_ref: str
    slot: str

    def __post_init__(self) -> None:
        if self.slot not in CONSEQUENTIAL_SLOTS:
            raise ValueError(
                f"SlotField {self.field_name!r} targets slot {self.slot!r}, which is not a "
                f"declared consequential slot; a schema may only bind values to consequential "
                f"slots the state-delta layer recognises (invariant 3.5: authored declaration, "
                f"not a content pattern)"
            )


@dataclass(frozen=True)
class SlotExtractionSchema:
    """The fixed, authored set of fields a structural extraction may bind. This is the
    envelope the model fills but does not emit (invariant 3.1). It is reviewed like the
    consequential-sink set, and adding a field is a deliberate trust-boundary decision.

    A seed schema covers the Phase 1 domains' consequential slots; a real deployment
    contributes fields per domain on the same attach pattern the ontology uses."""

    fields: tuple[SlotField, ...]

    def field_names(self) -> tuple[str, ...]:
        return tuple(f.field_name for f in self.fields)


# The seed structural-extraction schema for the four Phase 1 domains. Each field names a
# bounded value the model may fill and the consequential slot it targets. The entity refs
# are fixed per field for this build (the full build resolves the entity structurally);
# that is enough for the state-delta layer to compare a proposed value against stored
# state. This is authored data, not a content pattern: it enumerates SLOTS to read, never
# malicious phrasings to match (invariant 3.5).
SEED_SLOT_SCHEMA = SlotExtractionSchema(fields=(
    SlotField("new_bank_details", "supplier:of-record", "bank_details"),
    SlotField("new_salary_destination", "employee:of-record", "salary_destination"),
    SlotField("new_payment_destination", "payee:of-record", "payment_destination"),
    SlotField("changed_feature_flag", "service:of-record", "feature_flag"),
    SlotField("changed_firewall_rule", "network:of-record", "firewall_rule"),
    SlotField("changed_retention_policy", "data:of-record", "retention_policy"),
    SlotField("changed_mfa_required", "identity:of-record", "mfa_required"),
    SlotField("new_group_member", "group:of-record", "group_members"),
    SlotField("new_role_grant", "identity:of-record", "role_grants"),
    SlotField("changed_contract_term", "contract:of-record", "contract_term"),
    SlotField("new_holder_of_record", "asset:of-record", "holder_of_record"),
    SlotField("changed_entitlement_status", "policy:of-record", "entitlement_status"),
))


@dataclass(frozen=True)
class SlotBinding:
    """One value the model bound to a schema field, with the confidence it reported.

    `confidence` is the model's own reported confidence in the extraction; a binding below
    the schema's floor is dropped (treated as unbound), consistent with fenrir.md's
    fail-closed rule that a low-confidence extraction is not trusted. It never RAISES
    caution on its own: a dropped binding simply produces no ProposedFact."""

    field_name: str
    value: str
    confidence: float = 1.0


# The confidence floor below which a binding is treated as unbound (dropped). Fail-closed:
# an uncertain extraction does not become a confident consequential fact. It is a floor on
# TRUSTING the binding enough to compare it against stored state, not a trust grant.
CONFIDENCE_FLOOR = 0.5


@dataclass
class ExtractionResult:
    """The outcome of binding a producer's emitted values against the schema.

    `proposed_facts` is the deterministic result the state-delta layer (D79) consumes.
    `dropped` records fields that were emitted but not bound (empty value or below the
    confidence floor), for the audit trail, so a reviewer can see what the extraction saw
    but declined to trust. `bound_fields` is the accepted subset."""

    proposed_facts: tuple[ProposedFact, ...] = ()
    bound_fields: tuple[str, ...] = ()
    dropped: tuple[str, ...] = ()


def bind_slots(
    emitted: dict[str, "str | SlotBinding"],
    schema: SlotExtractionSchema = SEED_SLOT_SCHEMA,
    confidence_floor: float = CONFIDENCE_FLOOR,
) -> ExtractionResult:
    """Bind a producer's emitted field values to typed ProposedFacts, deterministically.

    `emitted` maps schema field names to values (a bare string, or a SlotBinding carrying
    confidence). This is the ONLY place a value becomes a slot binding, and it is plain
    Python: no model, no re-parse (invariant 3.1). A field absent from `emitted`, empty,
    or below the confidence floor produces no ProposedFact (fail-closed). A field not in
    the schema is ignored: the model cannot invent a new binding the schema did not
    declare, because the schema, not the emission, decides which slots exist."""
    by_field = {f.field_name: f for f in schema.fields}
    facts: list[ProposedFact] = []
    bound: list[str] = []
    dropped: list[str] = []

    for field_name, raw in emitted.items():
        slot_field = by_field.get(field_name)
        if slot_field is None:
            # Not a declared schema field: the model does not get to name new slots.
            continue
        if isinstance(raw, SlotBinding):
            value = raw.value
            confidence = raw.confidence
        else:
            value = raw
            confidence = 1.0
        value = (value or "").strip()
        if not value or confidence < confidence_floor:
            # Unbound or low-confidence: fail closed, no ProposedFact, only recorded.
            dropped.append(field_name)
            continue
        facts.append(ProposedFact(
            slot=SlotRef(entity=slot_field.entity_ref, slot=slot_field.slot),
            value=value,
        ))
        bound.append(field_name)

    return ExtractionResult(
        proposed_facts=tuple(facts),
        bound_fields=tuple(bound),
        dropped=tuple(dropped),
    )


def marshal_fenrir_run(
    run: FenrirRun,
    assertion_id: str,
    taint_class: str = "taint:EXTERNAL_COMMS",
    flows: tuple = (),
    source: str = "",
    schema: SlotExtractionSchema = SEED_SLOT_SCHEMA,
    confidence_floor: float = CONFIDENCE_FLOOR,
) -> "tuple":
    """Bridge a Fenrir run into a MarshalledAssertion the live engine consumes (D86).

    This is the seam that turns structural extraction into the input the wired D79 state-
    delta layer reads. It is deterministic and model-free (invariant 3.1): it binds the
    run's emitted slot values against the fixed schema (`bind_slots`), copies the free-
    text field for classification, and hands both to `marshal`. No second model pass and
    no re-interpretation; the model already emitted its values, and everything from here
    is plain Python.

    Returns (MarshalledAssertion, ExtractionResult) so the caller can both run the
    assertion through Nornir and audit which fields were bound versus dropped. The
    free-text `requested_action_summary` is still carried (the classifier reads it), so
    the layer-one classification is unchanged: this only ADDS the structural bindings the
    later layers need, it does not alter what the classifier sees."""
    extraction_result = bind_slots(run.emission.slot_values, schema, confidence_floor)
    # The free-text extraction envelope the classifier reads, from the run's assertions.
    extraction = {a.field_name: a.value for a in run.assertions}
    provenance = {a.field_name: "UNTRUSTED_DERIVED" for a in run.assertions}
    marshalled = marshal(
        assertion_id=assertion_id,
        extraction=extraction,
        provenance=provenance,
        taint_class=taint_class,
        flows=tuple(flows),
        proposed_facts=extraction_result.proposed_facts,
        source=source,
    )
    return marshalled, extraction_result
