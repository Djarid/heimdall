#![forbid(unsafe_code)]
//! `cognition-client` crate root: the workspace's sixth Rust crate
//! (build-order step seven, `.opencode/plans/build-order-step-seven-spec.md`,
//! REQ-6 to REQ-13). Spawns the Python MLX sidecar (`cognition.sidecar`,
//! REQ-15) with a fixed argv and no shell, and returns either a validated
//! commit message or a refusal (REQ-10). It knows nothing of proposals,
//! parameters, trust levels or consume modes (ST7-7): those declarations
//! live in `crates/process-engine/src/cognition.rs`, which depends on this
//! crate rather than the other way round.
//!
//! **The module split (REQ-9):** [`types`] carries the value shapes with no
//! logic; [`validation`] carries the single positive-match validator;
//! [`invocation`] is the only module in this crate -- and the second module
//! in the whole workspace -- permitted to touch `std::process`, and the
//! only module that reads the process environment; this crate root carries
//! the `forbid` attribute above and the public surface below.
//!
//! **The public surface is exactly one function, one value type and one
//! refusal type (REQ-10):** [`obtain_message`], [`CognitionMessage`] and
//! [`SidecarRefusal`]. `CognitionMessage` has no public constructor and no
//! public `From` conversion anywhere in this crate, so a caller cannot mint
//! one without going through [`obtain_message`] and therefore through
//! [`validation::validate_received_message`], on
//! `boundary_gjoll::rule::ConsequentialityVerdict`'s own containment
//! precedent.

mod invocation;
mod types;
mod validation;

pub use invocation::obtain_message;
pub use types::{CognitionMessage, SidecarRefusal};

#[allow(unused_imports)]
use invocation::{
    COGNITION_PACKAGE_ROOT_ENV_VAR, PYTHON_INTERPRETER_ENV_VAR, SIDECAR_TIMEOUT_SECS,
    resolve_sidecar_invocation,
};
#[allow(unused_imports)]
use validation::{MAX_RECEIVED_VALUE_LEN, validate_received_message};

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
