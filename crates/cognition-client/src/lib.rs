#![forbid(unsafe_code)]
//! `cognition-client` crate root: the workspace's sixth Rust crate
//! (build-order step seven, `.opencode/plans/build-order-step-seven-spec.md`,
//! REQ-6 to REQ-13). **NOT YET IMPLEMENTED.** This file is scaffolding only,
//! added by the test-writing agent so the crate can exist as a workspace
//! member (REQ-6) and so `unit_tests/` and `tests/public_surface.rs` have a
//! crate root to wire into (REQ-9's own module-split convention: a types
//! module, a validation module, an invocation module and this crate root).
//!
//! The public surface this crate must eventually carry (REQ-10, fixed for
//! the tests below to compile against once implemented): exactly one
//! function, one value type and one refusal type. None of the three exists
//! yet. Every test in `unit_tests/` and `tests/public_surface.rs` that
//! names `crate::` or `cognition_client::` items beyond this doc comment is
//! therefore expected to fail to compile until `@aetos-code` adds:
//!
//!   - a types module carrying the validated-message value type (no public
//!     constructor, no public `From`) and the refusal type (REQ-10, REQ-25);
//!   - a validation module carrying the one positive-match validator and
//!     this crate's own maximum-length constant (REQ-23, REQ-24);
//!   - an invocation module, the only module besides this crate root
//!     permitted to touch `std::process`, carrying the two path-shaped
//!     environment-variable constants, the fixed-argv spawn, the bounded
//!     wait and the fail-closed refusal set (REQ-11 to REQ-13, REQ-31 to
//!     REQ-34);
//!   - this crate root's own public re-exports of the one function, the one
//!     value type and the one refusal type.
//!
//! This is the correct RED state for this build-order step: the tests
//! below are written against the specification alone, not against an
//! implementation, and they are expected to fail to compile (missing
//! modules, missing types, missing functions) until that implementation
//! exists.

// The only test-related construct permitted anywhere under src/, on
// crates/process-engine/src/lib.rs's own precedent (REQ-9's module-split
// discipline applied to this crate's own test wiring): one
// `#[cfg(test)] #[path = ...] mod ...;` declaration per unit-test file, no
// test logic here.

#[cfg(test)]
#[path = "../unit_tests/validator.rs"]
mod validator_tests;

#[cfg(test)]
#[path = "../unit_tests/refusal_set.rs"]
mod refusal_set_tests;

#[cfg(test)]
#[path = "../unit_tests/no_sanitising.rs"]
mod no_sanitising_tests;

#[cfg(test)]
#[path = "../unit_tests/structural_posture.rs"]
mod structural_posture_tests;
