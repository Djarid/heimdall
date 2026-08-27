#![forbid(unsafe_code)]
// `process-engine` crate root -- TEST-INFRASTRUCTURE SCAFFOLD ONLY at this
// commit (build-order step five, `.opencode/plans/process-engine-step-five-spec.md`).
//
// This file is deliberately near-empty: no `mod sequence;`, no `mod task;`,
// no `mod cognition;`, no `mod proposal;`, no `mod outcome;`, no `mod
// startup;`, no crate-root re-exports and no types. Those are
// `@aetos-code`'s job (REQ-9 to REQ-37, REQ-25 to REQ-31 of the spec above).
// This crate exists at this commit purely so the failing test suite below
// has somewhere to physically live and attempt to compile (the judgement
// call the delegating prompt resolved explicitly: placeholder-crate scope is
// test infrastructure, not an implementation).
//
// Every `unit_tests/*.rs` file wired in below references crate items
// (`crate::EngineTask`, `crate::run_sequence`, `crate::EngineOutcome`, and
// so on) that do not exist yet. Compiling this crate is therefore EXPECTED
// TO FAIL with "cannot find type/value/function in this scope" or
// "unresolved import" diagnostics until `@aetos-code` adds the real
// modules. That failure is the correct RED state for this stage, not a
// defect in the test files themselves.

#[cfg(test)]
#[path = "../unit_tests/sequence_shape.rs"]
mod sequence_shape;

#[cfg(test)]
#[path = "../unit_tests/cognition_and_proposal.rs"]
mod cognition_and_proposal;

#[cfg(test)]
#[path = "../unit_tests/startup_failclosed.rs"]
mod startup_failclosed;
