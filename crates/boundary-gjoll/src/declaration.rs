//! Sink contracts and D81 declaration validation (D109, spec section 5.1, REQ-14,
//! REQ-15). Re-expresses `ontology/nornir/sink_declaration.py`'s effect-primitive
//! taxonomy (lines 70 to 93), `SinkRegistry`, `validate_proposal` (its five
//! conditions, lines 185 to 240) and `sink_is_intrinsically_consequential` (lines
//! 243 to 268).
//!
//! This file contains **no test bytes at all** (REQ-24): no `#[test]`, no `mod
//! tests`, no fixture and no double. Its Rust-native coverage lives in
//! `crates/boundary-gjoll/tests/native_failclosed.rs`.

use std::collections::{HashMap, HashSet};

use crate::types::{Reason, ReasonKind};

/// The attested effect-primitive taxonomy (D89, direction B), mirroring
/// `sink_declaration.py` lines 70 to 93 one for one: the seven effect-producing
/// primitives, the two inert primitives, plus an `Unrecognised` catch-all. The
/// catch-all exists so an unknown declared primitive string PARSES and then fails
/// closed at the derivation step (`intrinsically_consequential`, REQ-15), rather
/// than being rejected at parse time, which would lose the fail-closed
/// demonstration (D89-B silence case 3).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum EffectPrimitive {
    // The seven effect-producing primitives (`EFFECT_PRODUCING_PRIMITIVES`). A
    // sink declaring any of these is consequential by derivation, whatever its
    // `consequential_by_default` flag says.
    MoveMoney,
    GrantOrUseAccess,
    RunOrChangeCode,
    ExfiltrateData,
    DestroyData,
    BindingCommitment,
    ChangeSecurityState,
    // The two inert primitives (`INERT_PRIMITIVES`). The only honest way a
    // declaration earns non-consequential.
    DisplayOnly,
    StoreOnly,
    /// An unrecognised primitive string (e.g. a typo, or `"totally_harmless"`).
    /// Fails closed to consequential exactly as an undeclared sink does; never
    /// read as inert.
    Unrecognised,
}

impl EffectPrimitive {
    /// Membership test over `EFFECT_PRODUCING_PRIMITIVES`.
    fn is_effect_producing(self) -> bool {
        matches!(
            self,
            EffectPrimitive::MoveMoney
                | EffectPrimitive::GrantOrUseAccess
                | EffectPrimitive::RunOrChangeCode
                | EffectPrimitive::ExfiltrateData
                | EffectPrimitive::DestroyData
                | EffectPrimitive::BindingCommitment
                | EffectPrimitive::ChangeSecurityState
        )
    }

    /// Membership test over `INERT_PRIMITIVES`.
    fn is_inert(self) -> bool {
        matches!(
            self,
            EffectPrimitive::DisplayOnly | EffectPrimitive::StoreOnly
        )
    }
}

/// The declared contract of one sink (mirrors
/// `sink_declaration.py::SinkDeclaration`). `name` is the sink node id;
/// `parameters` is the full set of parameter names the sink consumes, which is
/// what closes the silent-omission path (D81 condition four).
///
/// `consequential_by_default` is carried here only for schema parity with the
/// Python dataclass and the golden-vector fixtures (`gate_vectors.json`'s
/// `layer_two.registry.declarations[].consequential_by_default`); it is never
/// read by `intrinsically_consequential`. The derivation is by `effect_primitive`
/// alone (D89-B), so a dishonest flag cannot disarm the gate: this struct keeping
/// the field around to be ignored, rather than acted on, is what makes "never
/// derive from a per-sink boolean" (REQ-15) an observable fact about this module
/// rather than an unenforced convention.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SinkDeclaration {
    pub name: String,
    pub parameters: HashSet<String>,
    pub consequential_by_default: bool,
    pub effect_primitive: Option<EffectPrimitive>,
}

/// The declared sinks (mirrors `sink_declaration.py::SinkRegistry`). A sink
/// absent from the registry is an ERROR, not a non-consequential sink: that
/// inversion is the point of this module (D81).
#[derive(Debug, Clone, Default)]
pub struct SinkRegistry {
    declarations: HashMap<String, SinkDeclaration>,
}

impl SinkRegistry {
    pub fn new() -> Self {
        Self {
            declarations: HashMap::new(),
        }
    }

    pub fn declare(&mut self, declaration: SinkDeclaration) {
        self.declarations
            .insert(declaration.name.clone(), declaration);
    }

    pub fn get(&self, name: &str) -> Option<&SinkDeclaration> {
        self.declarations.get(name)
    }

    pub fn is_declared(&self, name: &str) -> bool {
        self.declarations.contains_key(name)
    }
}

/// The outcome of validating one proposal against the registry (mirrors
/// `sink_declaration.py::ValidationResult`). `reasons` being non-empty means the
/// proposal must be BLOCKED before the rule runs; `treat_as_consequential` is the
/// fail-closed instruction for the shell when the sink itself is undeclared.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct ValidationOutcome {
    pub reasons: Vec<Reason>,
    pub treat_as_consequential: bool,
}

/// Validate a proposal's declarations before the rule runs (REQ-14). Fails
/// closed, mirroring `sink_declaration.py::validate_proposal`'s five conditions
/// exactly, in the same order:
///
///   1. The sink must be declared. Undeclared is a declaration error AND is
///      treated as consequential (fail closed), so a typo or a rename can no
///      longer silently disable the gate.
///   2. Every consume mode string must be one of `"ACTION"` or `"INERT"`. A typo
///      must never be read as inert consumption.
///   3. No phantom parameters: every parameter named in `consumes` must be a
///      known classified assertion.
///   4. No silent omissions: every parameter the sink declares must be
///      accounted for in `consumes`.
///   5. No extra parameters: `consumes` must not name a parameter the sink does
///      not accept.
///
/// `consumes` is deliberately a raw `str -> str` map, never a parsed
/// `ConsumeMode` map: condition two is precisely that an invalid mode string
/// exists, which by REQ-9 is unrepresentable as an already-parsed `ConsumeMode`.
/// This mirrors `sink_declaration.py`'s own signature, which keeps `consumes` a
/// raw dict everywhere, one for one.
pub fn validate_proposal(
    sink: &str,
    consumes: &HashMap<String, String>,
    registry: &SinkRegistry,
    known_assertion_ids: &HashSet<String>,
) -> ValidationOutcome {
    let mut outcome = ValidationOutcome::default();

    // 1. The sink must be declared.
    let declaration = registry.get(sink);
    if declaration.is_none() {
        outcome.reasons.push(Reason {
            kind: ReasonKind::DeclarationInvalid,
            parameter_id: String::new(),
            sink: sink.to_string(),
            detail: format!(
                "sink {sink:?} is not declared in the sink registry; a proposal cannot be \
                 authorised against an undeclared sink (fail closed: treated as consequential)"
            ),
        });
        outcome.treat_as_consequential = true;
        // Without a declaration there is no parameter contract to check against,
        // so the remaining structural checks that do not need one still run below.
    }

    // 2. Every consume mode must be valid.
    let mut invalid_mode_params: Vec<&String> = consumes
        .iter()
        .filter(|(_, mode)| mode.as_str() != "ACTION" && mode.as_str() != "INERT")
        .map(|(param_id, _)| param_id)
        .collect();
    invalid_mode_params.sort();
    for param_id in invalid_mode_params {
        let mode = &consumes[param_id];
        outcome.reasons.push(Reason {
            kind: ReasonKind::DeclarationInvalid,
            parameter_id: param_id.clone(),
            sink: sink.to_string(),
            detail: format!(
                "parameter {param_id:?} declares consume mode {mode:?}, which is not \
                 \"ACTION\" or \"INERT\"; an unrecognised mode is not treated as inert"
            ),
        });
    }

    // 3. No phantom parameters: every declared parameter must be a known assertion.
    let mut phantom_params: Vec<&String> = consumes
        .keys()
        .filter(|param_id| !known_assertion_ids.contains(*param_id))
        .collect();
    phantom_params.sort();
    for param_id in phantom_params {
        outcome.reasons.push(Reason {
            kind: ReasonKind::DeclarationInvalid,
            parameter_id: param_id.clone(),
            sink: sink.to_string(),
            detail: format!(
                "parameter {param_id:?} is declared in consumes but is not a known \
                 classified assertion; the declaration has drifted from the batch"
            ),
        });
    }

    // 4. No silent omissions, and 5. no extra parameters.
    if let Some(decl) = declaration {
        let mut missing: Vec<&String> = decl
            .parameters
            .iter()
            .filter(|p| !consumes.contains_key(*p))
            .collect();
        missing.sort();
        for param_id in missing {
            outcome.reasons.push(Reason {
                kind: ReasonKind::DeclarationInvalid,
                parameter_id: param_id.clone(),
                sink: sink.to_string(),
                detail: format!(
                    "sink {sink:?} declares parameter {param_id:?} that the proposal does \
                     not account for; an unaccounted parameter would never be gated"
                ),
            });
        }

        let mut extra: Vec<&String> = consumes
            .keys()
            .filter(|p| !decl.parameters.contains(*p))
            .collect();
        extra.sort();
        for param_id in extra {
            outcome.reasons.push(Reason {
                kind: ReasonKind::DeclarationInvalid,
                parameter_id: param_id.clone(),
                sink: sink.to_string(),
                detail: format!(
                    "proposal declares parameter {param_id:?} that sink {sink:?} does not \
                     accept; the declaration does not match the sink contract"
                ),
            });
        }
    }

    outcome
}

/// Derive a sink's INTRINSIC consequentiality from its declared effect primitive
/// (D89, direction B, REQ-15). Never reads `consequential_by_default`. A set-
/// membership test over the attested taxonomy, no model, no allocation. Fails
/// closed in all three silence cases:
///
///   - no declaration at all: `true` (an undeclared sink is an error, treated
///     consequential).
///   - a declared effect primitive in the effect-producing set: `true`, by
///     derivation. A dishonest `consequential_by_default = false` cannot change
///     this.
///   - a declared inert primitive (display/store only): `false`. The only
///     honest way to earn non-consequential.
///   - no primitive declared (`effect_primitive` is `None`): `true`. Silence
///     fails closed to consequential, exactly like an undeclared sink; it never
///     earns inert by omission.
///   - an unrecognised primitive string: `true`. Never read as inert, the same
///     fail-closed rule the consume-mode validation uses.
pub fn intrinsically_consequential(declaration: Option<&SinkDeclaration>) -> bool {
    let decl = match declaration {
        None => return true,
        Some(d) => d,
    };
    let prim = match decl.effect_primitive {
        None => return true,
        Some(p) => p,
    };
    if prim.is_effect_producing() {
        return true;
    }
    if prim.is_inert() {
        return false;
    }
    // Unrecognised primitive: fail closed.
    true
}
