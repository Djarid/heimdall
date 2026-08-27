#![forbid(unsafe_code)]
//! `actuator-git` crate root: the repository's fourth Rust crate and, once
//! wired behind `himinbjorg`'s witness-carrying entry point (a later phase of
//! `.opencode/plans/git-actuator-step-four.md`), the first crate in this
//! project's history able to perform a real, gated, executed action: a
//! commit and a push, run by the system `git` binary, and nothing else.
//!
//! STATUS AT THIS COMMIT (issue #47, section 11 step 3.1 of the spec named
//! above): this is the empty-but-compiling scaffold phase only. `types`
//! (REQ-8, REQ-25) is real: [`GitOperation`], [`ActuationOutcome`] and
//! [`ActuationRefusal`] are the closed vocabularies this crate's whole public
//! surface is built from. `argv`, `targets`, `repo` and `execute` are
//! declared, per this file's own requirement (REQ-5, section 10 file 4), but
//! are placeholders: none of REQ-9 to REQ-25's fail-closed behaviour is
//! implemented yet. [`execute`] exists as a real, callable symbol at this
//! crate's public surface, so downstream code (including the unit tests
//! wired in below) compiles against it, but it currently does nothing but
//! refuse. The first and second load-bearing phases (argument-vector safety
//! and the target allowlist; working-repository resolution and the process
//! spawn itself) are later issues' scope, per the spec's section 11 steps 3.3
//! and 3.4.
//!
//! **What this crate, once complete, is built to do.** Exactly two
//! operations (REQ-8): a local commit and a push, each constructed from one
//! fixed, validated argument shape (REQ-9), positive-match validated before
//! any process is spawned (REQ-11), with no shell invoked on any path
//! (REQ-10). A hardcoded, non-empty, positive-match push-target allowlist
//! (REQ-14) from which `main` and `master` are absent by omission, not by an
//! enumerated denylist (REQ-15). A working repository resolved from an
//! environment-named path, fail closed on every resolution failure including
//! a development-time guard against operating on this repository's own
//! working tree (REQ-18, REQ-19). A controlled process environment, a
//! bounded wait, and exit-status mapping that never reports a non-zero or
//! signalled exit as a success (REQ-21 to REQ-23).
//!
//! **What this crate does not claim, now or once the later phases land**
//! (drawn from the spec's section 13, restated here for the parts that bear
//! on this crate specifically rather than on `himinbjorg`'s side of the
//! wiring):
//!
//!   - It does not verify the identity of the resolved `git` binary. The
//!     actuator trusts whatever `git` resolves to on `PATH`; that trust root
//!     is named, not closed (EC-2).
//!   - It does not add flow-to-sink transitive reachability or a world
//!     model. `execute` is a fixed, two-operation entry point, not a general
//!     command-execution sandbox (deferred item 2).
//!   - It does not settle the code licence, which stays OPEN (REQ-4).
//!   - Even once its own logic lands, an actuator that can execute, inside a
//!     crate nothing calls, is not the gate invoked live against a real
//!     action: this step does not advance invariant 3.6, and does not by
//!     itself complete D108's definition of done.
//!
//! **Module layout (section 9.3, one responsibility per module).** `types`:
//! the operation, outcome and refusal vocabularies, no logic. `argv`: turns
//! one operation into one fixed, validated argument vector. `targets`:
//! answers whether a remote-and-ref pair is permitted. `repo`: resolves and
//! validates the working repository path. `execute`: spawns the process and
//! maps its exit status; the only module in the workspace that touches
//! `std::process`. None of `argv`, `targets`, `repo` or `execute` is `pub`:
//! every internal seam is reachable only through the one function this crate
//! exposes, [`execute`].

mod argv;
mod execute;
mod repo;
mod targets;
mod types;

pub use execute::execute;
pub use types::{ActuationOutcome, ActuationRefusal, GitOperation};

// The only test-related construct permitted anywhere under src/ (REQ-5). One
// `#[cfg(test)] #[path = ...] mod ...;` declaration per unit-test file, no
// test logic here. The test bodies live in ../unit_tests/, which src/ never
// touches.
#[cfg(test)]
#[path = "../unit_tests/argv_validation.rs"]
mod argv_validation;

#[cfg(test)]
#[path = "../unit_tests/target_and_repo_failclosed.rs"]
mod target_and_repo_failclosed;
