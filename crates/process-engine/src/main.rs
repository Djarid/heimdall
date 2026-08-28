#![forbid(unsafe_code)]
//! `process-engine`'s one binary target (REQ-25, PE-5). A separate crate
//! root from `src/lib.rs` (REQ-5: its own `#![forbid(unsafe_code)]`
//! above, since a binary's attributes are not inherited from the
//! library). Its only job: call `process_engine::startup::run()` to
//! resolve every environment-named precondition, call the library's one
//! public entry point once, and map the outcome to a documented exit
//! code.
//!
//! No step logic, no proposal shaping, no cognition and no outcome
//! interpretation beyond mapping the outcome to an exit code and
//! printing it (REQ-25). No argument parsing and no configuration-file
//! read (REQ-31): this crate's only input surface is the
//! environment-named values `process_engine::startup` resolves. Runs the
//! sequence at most once per process: no loop, no daemon mode, no
//! retry, no signal handler and no scheduler.
//!
//! **The five task constant-sets (build-order step six, ST6-2, REQ-6 to
//! REQ-13).** This file carries exactly five task constant-sets,
//! matching `.opencode/plans/build-order-step-six-spec.md` REQ-6's table
//! verbatim, in one fixed, compile-time length-asserted array,
//! [`TASK_MEMBERS`]. Every one of the five sink values, five action
//! names and four target values is an **agreement** with an
//! independently owned list (Himinbjörg's, Vör's or the actuator's own),
//! never a derivation (REQ-4): nothing in this file reads any of those
//! crates' own constants, and no test anywhere asserts that two
//! independently owned lists agree. Exactly one member is selected per
//! process, by the index `process_engine::startup::run()` resolves from
//! `HEIMDALL_ENGINE_TASK`, the fail-closed startup selector REQ-14 to
//! REQ-22 add to `startup.rs`; this file never reads the environment
//! itself (REQ-15) and never names the selector's own environment
//! variable or accepted-name set (REQ-39's own containment property).
//! No branch anywhere in this file is keyed on which member is selected,
//! and no expected-outcome value, table, enum or string literal exists
//! anywhere in this crate (REQ-10): this file knows only what is
//! proposed, never what is expected to happen to it.
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

/// One task constant-set's own fixed shape (REQ-6, REQ-9): plain data
/// only, no logic and no method. Every field of every member is a
/// `&'static str` (or, for `declared_cost`, a `u32`) copied verbatim from
/// REQ-6's table; nothing here computes, rewrites or derives a field from
/// any other field, member or crate.
struct EngineTaskMember {
    /// REQ-11's own positive derivation rule (never a blacklist of
    /// forbidden words): the action name's leaf, the substring after
    /// `action:git.`, joined to the target by a single hyphen. Distinct
    /// from every other member's own selector name, asserted at compile
    /// time below. Not read anywhere in this file: matching a resolved
    /// `HEIMDALL_ENGINE_TASK` value against a selector name happens
    /// inside `startup.rs` alone, against that module's own independent
    /// copy of the five names (REQ-39's own containment property, and
    /// the reason `startup.rs` cannot import this file's own constants
    /// across the crate-root boundary in either direction). The
    /// selector's only product this file ever sees is the resulting
    /// array index (REQ-18). Kept on this struct for REQ-11's own record
    /// of the derivation rule, so the two independent arrays can be kept
    /// in step by inspection rather than silently drifting apart.
    #[allow(dead_code)]
    selector_name: &'static str,
    /// This member's own task identifier. Distinct from every other
    /// member's and non-empty, on the removed single-task `TASK_ID`
    /// constant's own precedent.
    task_id: &'static str,
    /// The action this member's task names. An agreement with
    /// `hierarchy_vor::cohort::PERMITTED_ACTIONS` and
    /// `himinbjorg::definition::GLOBAL_DEFAULT_ACTIONS`, never a
    /// derivation from either (REQ-4): this crate reads neither
    /// constant, and N1's own `action:git.merge` is a deliberate
    /// agreement that the action is ABSENT from both.
    action_name: &'static str,
    /// The target this member's task names. An agreement with
    /// `himinbjorg::context::TARGET_SCOPE` and, separately and
    /// independently, with the actuator's own target allowlist (a
    /// constant this crate cannot even name, REQ-4, so it is deliberately
    /// not named by its own identifier here either, on AC-21's own
    /// never-reconcile rule), never a derivation from either: N3's own
    /// `fixture-target` is a deliberate agreement that the target is
    /// present in the first list and absent from the second.
    target: &'static str,
    /// The sink this member's task declares. An agreement with
    /// `himinbjorg::sinks::registry()`, never a derivation from it
    /// (REQ-4): N1's own `sink:git.commit` is a deliberate agreement that
    /// the sink IS present in that registry, so N1's block is
    /// attributable to exactly one named check (REQ-12).
    sink: &'static str,
    /// This member's own declared cost. Zero for every member (REQ-8).
    declared_cost: u32,
}

// ---------------------------------------------------------------------------
// P1: commit-fixture-target (REQ-6's table, row P1).
// ---------------------------------------------------------------------------

const P1_SELECTOR_NAME: &str = "commit-fixture-target";
const P1_TASK_ID: &str = "target-loop-commit-fixture-target";
const P1_ACTION_NAME: &str = "action:git.commit";
const P1_TARGET: &str = "fixture-target";
const P1_SINK: &str = "sink:git.commit";
const P1_DECLARED_COST: u32 = 0;

const _: () = assert!(!P1_SELECTOR_NAME.is_empty(), "P1_SELECTOR_NAME must be non-empty (REQ-8)");
const _: () = assert!(!P1_TASK_ID.is_empty(), "P1_TASK_ID must be non-empty (REQ-8)");
const _: () = assert!(!P1_ACTION_NAME.is_empty(), "P1_ACTION_NAME must be non-empty (REQ-8)");
const _: () = assert!(!P1_TARGET.is_empty(), "P1_TARGET must be non-empty (REQ-8)");
const _: () = assert!(!P1_SINK.is_empty(), "P1_SINK must be non-empty (REQ-8)");

// ---------------------------------------------------------------------------
// P2: push-fixture-integration-branch (REQ-6's table, row P2).
// ---------------------------------------------------------------------------

const P2_SELECTOR_NAME: &str = "push-fixture-integration-branch";
const P2_TASK_ID: &str = "target-loop-push-fixture-integration-branch";
const P2_ACTION_NAME: &str = "action:git.push";
const P2_TARGET: &str = "fixture-integration-branch";
const P2_SINK: &str = "sink:git.push";
const P2_DECLARED_COST: u32 = 0;

const _: () = assert!(!P2_SELECTOR_NAME.is_empty(), "P2_SELECTOR_NAME must be non-empty (REQ-8)");
const _: () = assert!(!P2_TASK_ID.is_empty(), "P2_TASK_ID must be non-empty (REQ-8)");
const _: () = assert!(!P2_ACTION_NAME.is_empty(), "P2_ACTION_NAME must be non-empty (REQ-8)");
const _: () = assert!(!P2_TARGET.is_empty(), "P2_TARGET must be non-empty (REQ-8)");
const _: () = assert!(!P2_SINK.is_empty(), "P2_SINK must be non-empty (REQ-8)");

// ---------------------------------------------------------------------------
// N1: merge-fixture-target (REQ-6's table, row N1). Names
// `action:git.merge`, an action absent from both
// `hierarchy_vor::cohort::PERMITTED_ACTIONS` and
// `himinbjorg::definition::GLOBAL_DEFAULT_ACTIONS` today (REQ-12). This is
// a statement about the cohort's attested control surface today alone,
// and prejudges nothing about merge's eventual permission
// (`plans/dd/actuator-git.md` section 13 item 8 and
// `crates/actuator-git/src/types.rs` both name merge as the anticipated
// third operation).
// ---------------------------------------------------------------------------

const N1_SELECTOR_NAME: &str = "merge-fixture-target";
const N1_TASK_ID: &str = "target-loop-merge-fixture-target";
const N1_ACTION_NAME: &str = "action:git.merge";
const N1_TARGET: &str = "fixture-target";
const N1_SINK: &str = "sink:git.commit";
const N1_DECLARED_COST: u32 = 0;

const _: () = assert!(!N1_SELECTOR_NAME.is_empty(), "N1_SELECTOR_NAME must be non-empty (REQ-8)");
const _: () = assert!(!N1_TASK_ID.is_empty(), "N1_TASK_ID must be non-empty (REQ-8)");
const _: () = assert!(!N1_ACTION_NAME.is_empty(), "N1_ACTION_NAME must be non-empty (REQ-8)");
const _: () = assert!(!N1_TARGET.is_empty(), "N1_TARGET must be non-empty (REQ-8)");
const _: () = assert!(!N1_SINK.is_empty(), "N1_SINK must be non-empty (REQ-8)");

// ---------------------------------------------------------------------------
// N2: push-main (REQ-6's table, row N2).
// ---------------------------------------------------------------------------

const N2_SELECTOR_NAME: &str = "push-main";
const N2_TASK_ID: &str = "target-loop-push-main";
const N2_ACTION_NAME: &str = "action:git.push";
const N2_TARGET: &str = "main";
const N2_SINK: &str = "sink:git.push";
const N2_DECLARED_COST: u32 = 0;

const _: () = assert!(!N2_SELECTOR_NAME.is_empty(), "N2_SELECTOR_NAME must be non-empty (REQ-8)");
const _: () = assert!(!N2_TASK_ID.is_empty(), "N2_TASK_ID must be non-empty (REQ-8)");
const _: () = assert!(!N2_ACTION_NAME.is_empty(), "N2_ACTION_NAME must be non-empty (REQ-8)");
const _: () = assert!(!N2_TARGET.is_empty(), "N2_TARGET must be non-empty (REQ-8)");
const _: () = assert!(!N2_SINK.is_empty(), "N2_SINK must be non-empty (REQ-8)");

// ---------------------------------------------------------------------------
// N3: push-fixture-target (REQ-6's table, row N3).
// ---------------------------------------------------------------------------

const N3_SELECTOR_NAME: &str = "push-fixture-target";
const N3_TASK_ID: &str = "target-loop-push-fixture-target";
const N3_ACTION_NAME: &str = "action:git.push";
const N3_TARGET: &str = "fixture-target";
const N3_SINK: &str = "sink:git.push";
const N3_DECLARED_COST: u32 = 0;

const _: () = assert!(!N3_SELECTOR_NAME.is_empty(), "N3_SELECTOR_NAME must be non-empty (REQ-8)");
const _: () = assert!(!N3_TASK_ID.is_empty(), "N3_TASK_ID must be non-empty (REQ-8)");
const _: () = assert!(!N3_ACTION_NAME.is_empty(), "N3_ACTION_NAME must be non-empty (REQ-8)");
const _: () = assert!(!N3_TARGET.is_empty(), "N3_TARGET must be non-empty (REQ-8)");
const _: () = assert!(!N3_SINK.is_empty(), "N3_SINK must be non-empty (REQ-8)");

/// The fixed, closed array itself (REQ-6, REQ-9): exactly REQ-6's table's
/// five members, in that order, and no other. The `const _: () =
/// assert!(...)` immediately below fails the BUILD, not a later test run,
/// the moment an edit adds or removes a member -- on
/// `sequence::STEP_SEQUENCE`'s own precedent for the identical construct.
const TASK_MEMBERS: [EngineTaskMember; 5] = [
    EngineTaskMember {
        selector_name: P1_SELECTOR_NAME,
        task_id: P1_TASK_ID,
        action_name: P1_ACTION_NAME,
        target: P1_TARGET,
        sink: P1_SINK,
        declared_cost: P1_DECLARED_COST,
    },
    EngineTaskMember {
        selector_name: P2_SELECTOR_NAME,
        task_id: P2_TASK_ID,
        action_name: P2_ACTION_NAME,
        target: P2_TARGET,
        sink: P2_SINK,
        declared_cost: P2_DECLARED_COST,
    },
    EngineTaskMember {
        selector_name: N1_SELECTOR_NAME,
        task_id: N1_TASK_ID,
        action_name: N1_ACTION_NAME,
        target: N1_TARGET,
        sink: N1_SINK,
        declared_cost: N1_DECLARED_COST,
    },
    EngineTaskMember {
        selector_name: N2_SELECTOR_NAME,
        task_id: N2_TASK_ID,
        action_name: N2_ACTION_NAME,
        target: N2_TARGET,
        sink: N2_SINK,
        declared_cost: N2_DECLARED_COST,
    },
    EngineTaskMember {
        selector_name: N3_SELECTOR_NAME,
        task_id: N3_TASK_ID,
        action_name: N3_ACTION_NAME,
        target: N3_TARGET,
        sink: N3_SINK,
        declared_cost: N3_DECLARED_COST,
    },
];

const _: () = assert!(
    TASK_MEMBERS.len() == 5,
    "TASK_MEMBERS must carry exactly five task constant-sets (REQ-9, REQ-6's table): an \
     edit that adds or removes a member must fail the build, not a later test run"
);

/// Byte-for-byte FNV-1a, `const fn` so it can run inside the compile-time
/// pairwise-distinctness assertion below, on `himinbjorg::definition::str_eq`'s
/// own const-fn precedent for the same underlying problem (stable Rust has
/// no const `PartialEq` for `&str` or `&[u8]`, so `!=` cannot be written
/// directly on two `&str` values inside a `const` context; comparing their
/// hashes with a plain integer `!=` is the const-compatible equivalent).
/// A non-cryptographic, well-known hash, used here for one purpose only:
/// a compile-time, necessary-but-not-sufficient distinctness signal over
/// five short, hardcoded, human-reviewed literals (REQ-11).
const fn fnv1a64(bytes: &[u8]) -> u64 {
    const FNV_OFFSET_BASIS: u64 = 0xcbf2_9ce4_8422_2325;
    const FNV_PRIME: u64 = 0x0000_0100_0000_01b3;
    let mut hash = FNV_OFFSET_BASIS;
    let mut i = 0;
    while i < bytes.len() {
        hash ^= bytes[i] as u64;
        hash = hash.wrapping_mul(FNV_PRIME);
        i += 1;
    }
    // Folded together with the byte length so that two inputs of equal
    // hash but different length (a possibility for any non-cryptographic
    // hash) remain distinguishable in the common case.
    hash ^ (bytes.len() as u64)
}

const P1_SELECTOR_HASH: u64 = fnv1a64(P1_SELECTOR_NAME.as_bytes());
const P2_SELECTOR_HASH: u64 = fnv1a64(P2_SELECTOR_NAME.as_bytes());
const N1_SELECTOR_HASH: u64 = fnv1a64(N1_SELECTOR_NAME.as_bytes());
const N2_SELECTOR_HASH: u64 = fnv1a64(N2_SELECTOR_NAME.as_bytes());
const N3_SELECTOR_HASH: u64 = fnv1a64(N3_SELECTOR_NAME.as_bytes());

// The five selector names are pairwise distinct, asserted at compile time
// (REQ-11): every one of the ten pairs among the five members compared,
// never merely a chain covering some but not all pairs.
const _: () = assert!(
    P1_SELECTOR_HASH != P2_SELECTOR_HASH
        && P1_SELECTOR_HASH != N1_SELECTOR_HASH
        && P1_SELECTOR_HASH != N2_SELECTOR_HASH
        && P1_SELECTOR_HASH != N3_SELECTOR_HASH
        && P2_SELECTOR_HASH != N1_SELECTOR_HASH
        && P2_SELECTOR_HASH != N2_SELECTOR_HASH
        && P2_SELECTOR_HASH != N3_SELECTOR_HASH
        && N1_SELECTOR_HASH != N2_SELECTOR_HASH
        && N1_SELECTOR_HASH != N3_SELECTOR_HASH
        && N2_SELECTOR_HASH != N3_SELECTOR_HASH,
    "the five selector names of TASK_MEMBERS must be pairwise distinct (REQ-11): every \
     pair of P1_SELECTOR_NAME, P2_SELECTOR_NAME, N1_SELECTOR_NAME, N2_SELECTOR_NAME and \
     N3_SELECTOR_NAME must differ"
);

fn main() {
    // The call to startup (REQ-26 to REQ-28; build-order step six,
    // REQ-14 to REQ-19): every environment read in this crate happens
    // inside `process_engine::startup::run()`, never here. No step of
    // the sequence runs, and no member of TASK_MEMBERS is even looked
    // at, until every precondition -- including the third, selector,
    // precondition -- resolves.
    let (cohort, _working_repo, selected_index) = match process_engine::startup::run() {
        Ok(resolved) => resolved,
        Err(refusal) => {
            // AC-31/REQ-16: name every failing condition, not merely the
            // first. AC-29/REQ-19: only the path and the refusal class
            // are ever printed here, never a secret byte -- because
            // `process_engine::startup` itself never puts one into any
            // of the three fields.
            if let Some(cohort_problem) = refusal.cohort {
                eprintln!("process-engine: startup refused: {cohort_problem}");
            }
            if let Some(working_repo_problem) = refusal.working_repo {
                eprintln!("process-engine: startup refused: {working_repo_problem}");
            }
            if let Some(selector_problem) = refusal.selector {
                eprintln!("process-engine: startup refused: {selector_problem}");
            }
            std::process::exit(process_engine::EXIT_STARTUP_REFUSAL);
        }
    };

    // REQ-18: the selector's only product was an index into
    // TASK_MEMBERS; it supplied nothing else, and this is the one and
    // only place that index is used.
    let member = &TASK_MEMBERS[selected_index];
    let task = process_engine::EngineTask {
        task_id: member.task_id.to_string(),
        action_name: member.action_name.to_string(),
        target: member.target.to_string(),
        sink: member.sink.to_string(),
        declared_cost: member.declared_cost,
    };

    // The one call to the library's one public entry point (REQ-25).
    let outcome = process_engine::run_sequence(&cohort, &task);
    let code = process_engine::exit_code_for(&outcome);
    println!("process-engine: outcome: {outcome:?}");
    std::process::exit(code);
}
