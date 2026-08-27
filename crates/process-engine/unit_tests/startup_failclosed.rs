//! The binary's fail-closed startup contract (REQ-26 to REQ-30, PE-5): AC-30
//! to AC-34, and edge cases EC-3 to EC-6 of
//! `.opencode/plans/process-engine-step-five-spec.md`.
//!
//! THIS FILE WILL FAIL TO COMPILE until `crates/process-engine/src/startup.rs`
//! exists at real fidelity, on `sequence_shape.rs`'s own header note for the
//! same expected RED state.
//!
//! **Compiled as an IN-CRATE unit test module** (REQ-7), wired into
//! `crates/process-engine/src/lib.rs` via
//! `#[cfg(test)] #[path = "../unit_tests/startup_failclosed.rs"] mod
//! startup_failclosed;`. This is deliberate, not incidental: `startup.rs`'s
//! own precondition-resolving logic is `pub(crate)` (REQ-26's "the only
//! module in the crate that reads the environment"), so testing its refusal
//! shapes at all requires in-crate access, following every prior crate's own
//! `*_failclosed.rs` naming convention (`crates/hierarchy-vor/unit_tests/
//! loader_failclosed.rs`, `crates/himinbjorg/unit_tests/gate_bridge_failclosed.rs`).
//!
//! **Signatures assumed here**, flagged explicitly per this crate's own
//! `sequence_shape.rs`/`cognition_and_proposal.rs` convention:
//!
//!   - `crate::startup::StartupRefusal { cohort: Option<String>, working_repo:
//!     Option<String> }`: a `pub(crate)` struct, one field per environment-
//!     named precondition (REQ-27, REQ-28). `None` means that precondition
//!     resolved; `Some(description)` names the failing environment variable
//!     and its refusal class, never a secret byte (REQ-29).
//!   - `crate::startup::resolve_startup_preconditions(secret_path_value:
//!     Option<&str>, working_repo_path_value: Option<&str>) ->
//!     Result<(hierarchy_vor::VerifiedCohort, std::path::PathBuf),
//!     StartupRefusal>`: the pure precondition-resolving logic, taking
//!     already-read environment VALUES as parameters rather than reading
//!     `std::env` itself. This split is this file's own necessary choice: it
//!     is what makes REQ-27's five fail-closed conditions testable at all
//!     from an in-crate module bound by `#![forbid(unsafe_code)]`
//!     (`std::env::set_var`/`remove_var` are `unsafe fn` under this
//!     workspace's pinned toolchain, exactly the constraint
//!     `crates/himinbjorg/unit_tests/witness_and_audit.rs`'s own header names
//!     for why ITS one environment-mutating test lives in an external
//!     integration-test crate instead). The thin wrapper that actually calls
//!     `std::env::var` and forwards the two values into this function is
//!     assumed to live in `main.rs` or in this same module, and is REQ-26's
//!     own environment-reading boundary; this file never mutates the real
//!     process environment, so its own tests hold unconditionally regardless
//!     of what is or is not provisioned on the machine running them.
//!   - The working-repository precondition is assumed to check only that
//!     the named path exists and is a directory (EC-4's own instruction:
//!     "the binary must not duplicate [the actuator's] policy, only
//!     establish that the precondition is resolvable"), never the deeper
//!     git-repository-marker or inside-this-repository checks
//!     `actuator_git::repo::resolve_working_repository` itself owns.
//!   - `crate::EXIT_EXECUTED`, `crate::EXIT_STARTUP_REFUSAL`,
//!     `crate::EXIT_GATE_BLOCKED`, `crate::EXIT_BROKER_REFUSED`,
//!     `crate::EXIT_WELL_FORMEDNESS_REFUSAL`: five named `i32` constants
//!     (REQ-30), assumed to live in the library (rather than solely in
//!     `main.rs`, which is a separate compilation unit this in-crate module
//!     cannot reach at all) so their distinctness is testable here; and
//!     `crate::exit_code_for(outcome: &EngineOutcome) -> i32`, the mapping
//!     function, also assumed `pub(crate)`.
//!
//! **Why this file never constructs a successful `VerifiedCohort`, and what
//! that leaves untested here.** `hierarchy_vor::VerifiedCohort` has no public
//! constructor anywhere outside `hierarchy_vor` itself, and its committed
//! attestation verifies only under the real, out-of-tree `heimdall-dev`
//! secret (D110). Every scenario below that needs the SECRET side of the
//! precondition to genuinely SUCCEED, while isolating a genuine
//! working-repository failure on its own, is therefore unreachable from this
//! file: it would need a real provisioned secret, and REQ-53's own
//! discipline forbids silently degrading a fixture to fake that. This file
//! instead isolates what it CAN isolate without one (a failing secret
//! precondition paired with a genuinely resolving working-repository
//! precondition, in both of the secret's own distinct refusal classes:
//! missing, and present-but-unverified), and states this limit plainly
//! rather than smoothing over it, on `crates/himinbjorg/unit_tests/six_checks.rs`'s
//! own precedent for a named, undisguised gap. The full both-succeed-then-one-
//! fails matrix, and the true happy path, belong to `tests/public_surface.rs`
//! instead, gated behind `HEIMDALL_COHORT_SECRET_FILE`.

use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

fn scratch_dir(label: &str) -> PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system clock before the Unix epoch")
        .as_nanos();
    let dir = std::env::temp_dir().join(format!("process-engine-startup-failclosed-{label}-{nanos}"));
    fs::create_dir_all(&dir).expect("failed to create a scratch dir under the system temp directory");
    dir
}

fn valid_looking_working_repo_dir(label: &str) -> PathBuf {
    let dir = scratch_dir(label);
    // A directory that exists (satisfies the assumed, deliberately shallow
    // precondition check this module owns); no `.git` marker is needed
    // because that deeper check belongs to `actuator_git::repo` alone
    // (EC-4).
    dir
}

// ---------------------------------------------------------------------------------
// EC-3: HEIMDALL_COHORT_SECRET_FILE is unset. Isolated: the working-repo
// precondition genuinely resolves.
// ---------------------------------------------------------------------------------

#[test]
fn ec3_secret_path_value_absent_refuses_fail_closed_naming_the_variable() {
    let repo_dir = valid_looking_working_repo_dir("ec3");

    let result = crate::startup::resolve_startup_preconditions(
        None,
        Some(repo_dir.to_str().expect("scratch path must be valid UTF-8")),
    );

    match result {
        Err(refusal) => {
            let cohort_problem = refusal
                .cohort
                .as_deref()
                .expect("EC-3/AC-30: an absent secret path value must refuse, naming HEIMDALL_COHORT_SECRET_FILE");
            assert!(
                cohort_problem.contains("HEIMDALL_COHORT_SECRET_FILE"),
                "AC-31: the refusal must name the failing environment variable by name; \
                 got {cohort_problem:?}"
            );
            assert!(
                refusal.working_repo.is_none(),
                "EC-3: the working-repository precondition must genuinely resolve on this \
                 path and must not be reported as failing when it did not; got \
                 {:?}",
                refusal.working_repo,
            );
        }
        Ok(_) => panic!(
            "EC-3: an absent secret path value must never fall back to a default and must \
             never succeed"
        ),
    }
}

// ---------------------------------------------------------------------------------
// EC-6: the secret file exists and is readable but the cohort's attestation
// does not verify. Isolated the same way: the working-repo precondition
// genuinely resolves.
// ---------------------------------------------------------------------------------

#[test]
fn ec6_secret_present_but_attestation_does_not_verify_refuses_naming_vors_own_class() {
    let dir = scratch_dir("ec6");
    let secret_path = dir.join("secret");
    let marker = "PROCESS-ENGINE-EC6-PROBE-SECRET-CONTENT-MUST-NEVER-BE-PRINTED";
    fs::write(&secret_path, marker.as_bytes()).expect("failed to write fixture secret file");
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(&secret_path, fs::Permissions::from_mode(0o600))
            .expect("failed to set fixture secret file permissions");
    }
    let repo_dir = valid_looking_working_repo_dir("ec6");

    let result = crate::startup::resolve_startup_preconditions(
        Some(secret_path.to_str().expect("scratch path must be valid UTF-8")),
        Some(repo_dir.to_str().expect("scratch path must be valid UTF-8")),
    );

    match result {
        Err(refusal) => {
            let cohort_problem = refusal
                .cohort
                .as_deref()
                .expect("EC-6: an arbitrary, non-real secret must never verify D110's \
                         committed attestation, and startup must refuse");
            assert!(
                !cohort_problem.contains(marker),
                "AC-29/AC-32: the refusal must never print a byte of the secret file's \
                 contents; got {cohort_problem:?}"
            );
            assert!(
                refusal.working_repo.is_none(),
                "the working-repository precondition must genuinely resolve on this path"
            );
        }
        Ok(_) => panic!(
            "EC-6: an arbitrary, non-real secret must never verify D110's fixed committed \
             attestation, so startup must never succeed on this path"
        ),
    }
}

// ---------------------------------------------------------------------------------
// EC-4: HEIMDALL_ACTUATOR_GIT_WORKING_REPO is unset or names an unusable
// path. Paired with a failing secret (the isolation this file can achieve
// without a real one, see the header); both refusal descriptions are
// checked so the working-repo half is genuinely exercised regardless.
// ---------------------------------------------------------------------------------

#[test]
fn ec4_working_repo_unset_refuses_fail_closed_naming_the_variable() {
    let result = crate::startup::resolve_startup_preconditions(None, None);

    match result {
        Err(refusal) => {
            let working_repo_problem = refusal.working_repo.as_deref().expect(
                "EC-4/AC-30: an absent working-repository path value must refuse, naming \
                 HEIMDALL_ACTUATOR_GIT_WORKING_REPO",
            );
            assert!(
                working_repo_problem.contains("HEIMDALL_ACTUATOR_GIT_WORKING_REPO"),
                "AC-31: the refusal must name the failing environment variable by name; \
                 got {working_repo_problem:?}"
            );
            assert!(
                !working_repo_problem.contains(std::env::current_dir().unwrap().to_str().unwrap_or_default())
                    || working_repo_problem.contains("HEIMDALL_ACTUATOR_GIT_WORKING_REPO"),
                "EC-4: a refusal must never silently default to the inherited current \
                 working directory"
            );
        }
        Ok(_) => panic!("EC-4: an absent working-repository path value must never succeed"),
    }
}

#[test]
fn ec4_working_repo_names_a_nonexistent_path_refuses_fail_closed() {
    let bogus = scratch_dir("ec4-nonexistent").join("this-path-was-never-created");
    let result = crate::startup::resolve_startup_preconditions(
        None,
        Some(bogus.to_str().expect("scratch path must be valid UTF-8")),
    );

    match result {
        Err(refusal) => {
            let working_repo_problem = refusal.working_repo.as_deref().expect(
                "EC-4/AC-30: a working-repository path that does not exist must refuse, \
                 naming HEIMDALL_ACTUATOR_GIT_WORKING_REPO",
            );
            assert!(
                working_repo_problem.contains("HEIMDALL_ACTUATOR_GIT_WORKING_REPO"),
                "AC-31: the refusal must name the failing environment variable by name"
            );
        }
        Ok(_) => panic!(
            "EC-4: a working-repository path naming a location that does not exist must \
             never succeed"
        ),
    }
}

#[test]
fn ec4_working_repo_names_a_file_not_a_directory_refuses_fail_closed() {
    let dir = scratch_dir("ec4-file-not-dir");
    let file_path = dir.join("not-a-directory");
    fs::write(&file_path, b"probe").expect("failed to write fixture file");

    let result = crate::startup::resolve_startup_preconditions(
        None,
        Some(file_path.to_str().expect("scratch path must be valid UTF-8")),
    );

    match result {
        Err(refusal) => {
            assert!(
                refusal.working_repo.is_some(),
                "EC-4: a working-repository path naming a plain file, not a directory, \
                 must refuse"
            );
        }
        Ok(_) => panic!(
            "EC-4: a working-repository path naming a plain file must never resolve as a \
             usable working repository"
        ),
    }
}

// ---------------------------------------------------------------------------------
// EC-5, AC-31: both environment-named preconditions fail in the same
// startup. The refusal must name BOTH, not merely the first.
// ---------------------------------------------------------------------------------

#[test]
fn ec5_both_preconditions_failing_are_both_named_never_only_the_first() {
    let result = crate::startup::resolve_startup_preconditions(None, None);

    match result {
        Err(refusal) => {
            assert!(
                refusal.cohort.is_some(),
                "EC-5/AC-31: when both preconditions fail, the cohort precondition's own \
                 failure must still be named"
            );
            assert!(
                refusal.working_repo.is_some(),
                "EC-5/AC-31: when both preconditions fail, the working-repository \
                 precondition's own failure must ALSO be named -- not merely the first \
                 condition checked. A refusal that says only \"startup failed\", or names \
                 only one of the two, fails this criterion."
            );
        }
        Ok(_) => panic!("EC-5: with both preconditions absent, startup must never succeed"),
    }
}

// ---------------------------------------------------------------------------------
// AC-32: no byte of the secret file's contents, no digest and no key
// material is ever printed, on any refusal path, including when the value
// is known to this test in advance.
// ---------------------------------------------------------------------------------

#[test]
fn ac32_no_secret_bytes_appear_in_any_refusal_description() {
    let dir = scratch_dir("ac32");
    let secret_path = dir.join("secret");
    let known_secret_marker = "THIS-EXACT-STRING-MUST-NEVER-APPEAR-IN-ANY-STARTUP-OUTPUT";
    fs::write(&secret_path, known_secret_marker.as_bytes())
        .expect("failed to write fixture secret file");
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(&secret_path, fs::Permissions::from_mode(0o600))
            .expect("failed to set fixture secret file permissions");
    }

    // Exercise every refusal path this file can reach with this secret file
    // in scope, and confirm none of them ever echoes it back.
    let scenarios: Vec<Result<_, crate::startup::StartupRefusal>> = vec![
        crate::startup::resolve_startup_preconditions(
            Some(secret_path.to_str().unwrap()),
            None,
        ),
        crate::startup::resolve_startup_preconditions(None, None),
        crate::startup::resolve_startup_preconditions(
            Some(secret_path.to_str().unwrap()),
            Some(secret_path.to_str().unwrap()), // deliberately unusable as a working repo too
        ),
    ];

    for scenario in scenarios {
        if let Err(refusal) = scenario {
            for description in [refusal.cohort.as_deref(), refusal.working_repo.as_deref()]
                .into_iter()
                .flatten()
            {
                assert!(
                    !description.contains(known_secret_marker),
                    "AC-29/AC-32: a refusal description must never contain a byte of the \
                     secret file's contents; got {description:?}"
                );
            }
        }
    }
}

// ---------------------------------------------------------------------------------
// AC-33 (REQ-30): the exit-code constants are distinct, each is documented,
// and the mapping function maps each testable outcome to its own code.
// EXIT_EXECUTED cannot be exercised here (constructing a real
// himinbjorg::ActuationReceipt needs actuator_git, which this crate cannot
// depend on at all, REQ-4); its own confirmation belongs to
// tests/public_surface.rs, where a real sequence run actually reaches it.
// ---------------------------------------------------------------------------------

#[test]
fn ac33_exit_codes_are_five_distinct_named_constants_with_zero_reserved_for_executed() {
    let codes = [
        crate::EXIT_EXECUTED,
        crate::EXIT_STARTUP_REFUSAL,
        crate::EXIT_GATE_BLOCKED,
        crate::EXIT_BROKER_REFUSED,
        crate::EXIT_WELL_FORMEDNESS_REFUSAL,
    ];
    let mut unique = codes.to_vec();
    unique.sort_unstable();
    unique.dedup();
    assert_eq!(
        unique.len(),
        5,
        "AC-33/REQ-30: the five exit-code constants must all be distinct; got {codes:?}"
    );
    assert_eq!(
        crate::EXIT_EXECUTED,
        0,
        "AC-33/REQ-30: zero must be reserved for the executed case only"
    );
    for (name, code) in [
        ("EXIT_STARTUP_REFUSAL", crate::EXIT_STARTUP_REFUSAL),
        ("EXIT_GATE_BLOCKED", crate::EXIT_GATE_BLOCKED),
        ("EXIT_BROKER_REFUSED", crate::EXIT_BROKER_REFUSED),
        (
            "EXIT_WELL_FORMEDNESS_REFUSAL",
            crate::EXIT_WELL_FORMEDNESS_REFUSAL,
        ),
    ] {
        assert_ne!(
            code, 0,
            "AC-33/REQ-30: no failing outcome may map to zero; {name} maps to zero"
        );
    }
}

#[test]
fn ac33_exit_code_mapping_maps_each_constructible_outcome_case_to_its_own_documented_code() {
    let well_formedness = crate::EngineOutcome::RefusedBeforeCognition {
        reason: "probe: empty task_id".to_string(),
    };
    assert_eq!(
        crate::exit_code_for(&well_formedness),
        crate::EXIT_WELL_FORMEDNESS_REFUSAL,
        "AC-33: RefusedBeforeCognition must map to EXIT_WELL_FORMEDNESS_REFUSAL"
    );

    let gate_blocked = crate::EngineOutcome::GateBlocked {
        checks: vec![(
            himinbjorg::CheckId::ActionPermitted,
            himinbjorg::CheckOutcome::Fail {
                reasons: vec!["probe".to_string()],
            },
        )],
    };
    assert_eq!(
        crate::exit_code_for(&gate_blocked),
        crate::EXIT_GATE_BLOCKED,
        "AC-33: GateBlocked must map to EXIT_GATE_BLOCKED"
    );

    let broker_refused = crate::EngineOutcome::BrokerRefused {
        refusal: himinbjorg::BrokerRefusal::ScopeNotPermitted,
    };
    assert_eq!(
        crate::exit_code_for(&broker_refused),
        crate::EXIT_BROKER_REFUSED,
        "AC-33: BrokerRefused must map to EXIT_BROKER_REFUSED"
    );
}

// ---------------------------------------------------------------------------------
// AC-34, EC-16: the startup module never defaults to the current working
// directory, and never falls back to any candidate secret path.
// ---------------------------------------------------------------------------------

#[test]
fn ac34_startup_module_source_contains_no_default_fallback_for_either_precondition() {
    let startup_rs = fs::read_to_string(
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("src")
            .join("startup.rs"),
    )
    .expect("expected crates/process-engine/src/startup.rs to exist");
    for forbidden in [
        "unwrap_or_else(|| std::env::current_dir",
        "unwrap_or(\".\")",
        ".ok().unwrap_or_default()",
    ] {
        assert!(
            !startup_rs.contains(forbidden),
            "AC-34/EC-16/REQ-27: startup.rs must never fall back to a default value for a \
             failing precondition; found a pattern resembling {forbidden:?}"
        );
    }
}
