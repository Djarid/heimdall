// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! Public-surface sufficiency for `cognition-client` (REQ-10 of
//! `.opencode/plans/build-order-step-seven-spec.md`; section 7 row 9), on
//! `crates/process-engine/tests/public_surface.rs`'s precedent: the one
//! function, the one value type and the one refusal type are reachable and
//! sufficient; the value type cannot be minted without going through the
//! function.
//!
//! Compiled as an EXTERNAL crate importing `cognition_client`'s public
//! surface only, exactly as every sibling crate's own `tests/public_surface.rs`
//! does. THIS FILE WILL FAIL TO COMPILE until `cognition-client` declares
//! its real modules and re-exports its public surface from the crate root.
//! That is the expected RED state for this build-order step.
//!
//! **Signatures assumed here** (this file's own necessary choices, flagged
//! explicitly, in addition to `unit_tests/validator.rs`'s and
//! `unit_tests/refusal_set.rs`'s own headers, which this file inherits
//! without repeating):
//!
//!   - Crate-root re-exports: `cognition_client::{CognitionMessage,
//!     SidecarRefusal, obtain_message}`.
//!   - `cognition_client::obtain_message(prompt: &str) ->
//!     Result<CognitionMessage, SidecarRefusal>` (REQ-10): the crate's one
//!     public function, reading the two path-shaped environment variables
//!     internally and forwarding their values into the invocation module
//!     (REQ-11).
//!   - `CognitionMessage::as_str(&self) -> &str`: the one public reader
//!     REQ-10 names.
//!   - `SidecarRefusal { pub diagnostic: String }`: the refusal type's own
//!     bounded diagnostic field (REQ-25).

// ---------------------------------------------------------------------------------
// REQ-10: exactly one function, one value type and one refusal type are
// reachable from outside the crate.
// ---------------------------------------------------------------------------------

#[test]
fn the_one_public_function_is_reachable_and_has_the_expected_signature() {
    let _entry_point_exists: fn(&str) -> Result<cognition_client::CognitionMessage, cognition_client::SidecarRefusal> =
        cognition_client::obtain_message;
}

// ---------------------------------------------------------------------------------
// REQ-10/AC-12: the value type cannot be minted without going through the
// function -- exercised for real, without provisioning the sidecar, so
// this holds on every machine. The two path-shaped environment variables
// are deliberately left unset for this test, so `obtain_message` is
// expected to refuse (an absent interpreter path is REQ-31 item 1); the
// exact refusal reason is not the point here, only that calling the public
// function is the ONLY route this external test has to attempt to obtain a
// `CognitionMessage` at all -- there is no second, direct-construction
// route for an external caller to try instead, which this file's own
// compilation (naming no constructor, no `From` impl and no field
// literal for `CognitionMessage` anywhere above) already demonstrates.
// ---------------------------------------------------------------------------------

#[test]
fn calling_the_public_function_is_the_only_route_this_external_crate_has_to_a_message() {
    // This call is expected to refuse on a machine with no sidecar path
    // variables provisioned (REQ-31 item 1); what matters for THIS test is
    // only that it compiles and runs without this external crate naming
    // any private constructor, `From` impl or field literal for
    // `CognitionMessage` -- there is no other syntax available to it.
    let _ = cognition_client::obtain_message("a fixture prompt, never sent anywhere real here");
}

// ---------------------------------------------------------------------------------
// AC-12's own compile-fail companion, following
// crates/process-engine/unit_tests/sequence_shape.rs's own AC-13/AC-40
// convention: the "does not compile" half is a hand-confirmed diagnostic,
// never an automated test in this file (a snippet that must NOT compile
// cannot be asserted by a passing test in this same crate without a
// trybuild-style dev-dependency, which REQ-7 forbids adding to this crate
// at all). To confirm by hand once the crate exists: uncomment ONE line
// below, run `cargo build -p cognition-client --tests`, capture the
// diagnostic (expected E0423/E0599: no associated function or tuple
// constructor to build a CognitionMessage directly, and E0433 for any
// private module path), and record it in the pull request. Leave every
// line commented in the committed file, otherwise this crate never builds
// at all.
//
// ```rust,ignore
// fn _ac12_confirm_cognition_message_has_no_public_constructor() {
//     let _bad = cognition_client::CognitionMessage("direct construction attempt".to_string());
// }
// ```

// ---------------------------------------------------------------------------------
// REQ-25: the refusal type's own bounded diagnostic field is reachable and
// readable from outside the crate.
// ---------------------------------------------------------------------------------

#[test]
fn the_refusal_types_diagnostic_field_is_reachable_from_outside_the_crate() {
    match cognition_client::obtain_message("a fixture prompt") {
        Ok(_) => {
            // Also acceptable: if the two sidecar path variables happen to
            // be provisioned in this test's environment and the call
            // genuinely succeeds, that is a stronger, not weaker,
            // demonstration that the public function is sufficient.
        }
        Err(refusal) => {
            let _diagnostic: &str = refusal.diagnostic.as_str();
        }
    }
}
