//! Scaffold only (issue #47, phase 1 of
//! `.opencode/plans/git-actuator-step-four.md`'s execution workflow, section
//! 11 step 3.1). This module will own `execute`, the crate's single public
//! entry point and the only `std::process` site in the workspace: a
//! controlled environment, no shell, a bounded wait with termination on
//! expiry, exit-status mapping and bounded output capture (REQ-7, REQ-10,
//! REQ-21 to REQ-25, section 10 file 9).
//!
//! The function below is a placeholder only, not yet load-bearing: it never
//! spawns a process, never reads `crate::argv`, `crate::targets` or
//! `crate::repo` (none of which are implemented yet either), and always
//! refuses. It exists solely so this crate presents a real `execute` symbol
//! at its public surface and compiles as an empty-but-compiling workspace
//! member (section 11 step 3.1). The real behaviour, including every
//! fail-closed check REQ-9 to REQ-25 describe, is a later issue's scope (the
//! first and second load-bearing phases, section 11 steps 3.3 and 3.4).

use crate::types::{ActuationOutcome, ActuationRefusal, GitOperation};

/// Placeholder body: unconditionally refuses, naming itself as not yet
/// implemented, and never spawns a process. See this module's own doc
/// comment for why.
pub fn execute(_operation: &GitOperation) -> Result<ActuationOutcome, ActuationRefusal> {
    Err(ActuationRefusal::SpawnFailed {
        diagnostic: "actuator-git::execute is scaffolding only at this commit (issue #47); \
                     its real behaviour is a later issue's scope"
            .to_string(),
    })
}
