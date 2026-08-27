//! Scaffold only (issue #47, phase 1 of
//! `.opencode/plans/git-actuator-step-four.md`'s execution workflow, section
//! 11 step 3.1). This module will own the hardcoded, non-empty permitted
//! remote-and-ref allowlist with its compile-time non-emptiness assertion,
//! the pair-membership function, and the defence-in-depth protected-ref arm
//! (REQ-14 to REQ-16, section 10 file 7). Not yet implemented: that is the
//! first load-bearing phase (section 11 step 3.3), a later issue's scope.
//! Declared here only so `crates/actuator-git/src/lib.rs` can name all five
//! modules per file 4's requirement, and so the crate compiles as an
//! empty-but-compiling member of the workspace.
