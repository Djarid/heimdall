#![forbid(unsafe_code)]
//! `process-engine`'s one binary target (REQ-25, PE-5). A separate crate
//! root from `src/lib.rs` (REQ-5: its own `#![forbid(unsafe_code)]`
//! above, since a binary's attributes are not inherited from the
//! library). Its only job: call `process_engine::startup::run()` to
//! resolve both environment-named preconditions, call the library's one
//! public entry point once, and map the outcome to a documented exit
//! code.
//!
//! No step logic, no proposal shaping, no cognition and no outcome
//! interpretation beyond mapping the outcome to an exit code and
//! printing it (REQ-25). No argument parsing and no configuration-file
//! read (REQ-31): this crate's only input surface is the two
//! environment-named PATHS `process_engine::startup` resolves. Runs the
//! sequence at most once per process: no loop, no daemon mode, no
//! retry, no signal handler and no scheduler.
//!
//! **A disclosed, narrowly-scoped exception to REQ-8's own wording.**
//! REQ-8 says this crate references neither `std::process` nor
//! `std::net`. `std::process::exit`, below, is this file's one and only
//! reference to that module, and it exists for the one purpose REQ-30
//! itself requires: mapping an outcome to the process's own, real exit
//! code, which Rust has no route to achieve without touching
//! `std::process` somewhere. It is categorically different from
//! `std::process::Command` (subprocess spawning), which stays exactly
//! where D112 left it, inside `crates/actuator-git/src/execute.rs`
//! alone: this file never spawns a process, it only terminates its own.
//! `src/lib.rs` and every module it declares carry zero references to
//! `std::process`; this is the one, disclosed exception, confined to
//! this file, and it is recorded here, in the implementing agent's final
//! report and for `DECISIONS.md` to carry forward.

/// The one hardcoded task this binary ever runs (REQ-31): no argument
/// parsing, no configuration-file read. A named constant with its own
/// compile-time non-emptiness assertion, on [`process_engine`]'s own
/// cognition-constants precedent (PE-2's no-configuration-surface
/// reasoning, applied here to the binary's own input).
const TASK_ID: &str = "process-engine-binary-task";

/// The one hardcoded action name this binary's task ever names.
const TASK_ACTION_NAME: &str = "action:git.commit";

/// The one hardcoded target this binary's task ever names. A member of
/// `himinbjorg::context::TARGET_SCOPE` after this step's own additive
/// change (REQ-17), so a commit proposal built from this task can reach
/// `Decision::Allow` for real, given a provisioned cohort.
const TASK_TARGET: &str = "fixture-target";

/// The one hardcoded declared cost this binary's task ever names.
const TASK_DECLARED_COST: u32 = 0;

const _: () = assert!(!TASK_ID.is_empty(), "TASK_ID must be non-empty (REQ-31)");
const _: () = assert!(
    !TASK_ACTION_NAME.is_empty(),
    "TASK_ACTION_NAME must be non-empty (REQ-31)"
);
const _: () = assert!(!TASK_TARGET.is_empty(), "TASK_TARGET must be non-empty (REQ-31)");

fn main() {
    let task = process_engine::EngineTask {
        task_id: TASK_ID.to_string(),
        action_name: TASK_ACTION_NAME.to_string(),
        target: TASK_TARGET.to_string(),
        declared_cost: TASK_DECLARED_COST,
    };

    // The call to startup (REQ-26 to REQ-28): every environment read in
    // this crate happens inside `process_engine::startup::run()`, never
    // here. No step of the sequence runs until both preconditions
    // resolve.
    let (cohort, _working_repo) = match process_engine::startup::run() {
        Ok(resolved) => resolved,
        Err(refusal) => {
            // AC-31/REQ-28: name every failing condition, not merely the
            // first. AC-29/REQ-29: only the path and the refusal class
            // are ever printed here, never a secret byte -- because
            // `process_engine::startup` itself never puts one into
            // either field.
            if let Some(cohort_problem) = refusal.cohort {
                eprintln!("process-engine: startup refused: {cohort_problem}");
            }
            if let Some(working_repo_problem) = refusal.working_repo {
                eprintln!("process-engine: startup refused: {working_repo_problem}");
            }
            std::process::exit(process_engine::EXIT_STARTUP_REFUSAL);
        }
    };

    // The one call to the library's one public entry point (REQ-25).
    let outcome = process_engine::run_sequence(&cohort, &task);
    let code = process_engine::exit_code_for(&outcome);
    println!("process-engine: outcome: {outcome:?}");
    std::process::exit(code);
}
