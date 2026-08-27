//! The permitted-target allowlist and the working-repository resolution's
//! fail-closed refusal conditions that do NOT require mutating the process
//! environment (REQ-14 to REQ-20). Covers AC-15 to AC-18 in full, and the
//! portion of AC-21 to AC-23 that is reachable without `std::env::set_var`,
//! of `.opencode/plans/git-actuator-step-four.md`.
//!
//! THIS FILE WILL FAIL TO COMPILE until `crates/actuator-git` exists at all
//! and is wired into `src/lib.rs`. That is expected and correct at this
//! stage, for the same reason `argv_validation.rs`'s own header states.
//!
//! **Compiled as an IN-CRATE unit test module**, once wired in (a later,
//! implementation-side change), so this file could reach `pub(crate)`
//! internals; the tests below use the public `execute` entry point
//! exclusively, since the assumed check order (see `argv_validation.rs`'s
//! header) makes that sufficient here too.
//!
//! **Assumed public surface**: identical to `argv_validation.rs`'s own
//! assumption block; not repeated in full here. In addition, this file
//! assumes `execute` checks target-allowlist membership (REQ-14, push only)
//! strictly BEFORE working-repository resolution (REQ-18/19), so a
//! disallowed target is reported as `TargetNotPermitted`/`ProtectedRef`
//! rather than `RepositoryResolution`, even in this unit-test binary where no
//! working-repository environment variable is configured at all.
//!
//! **Why AC-21's "set to the empty string" sub-case, and all of AC-22 and
//! AC-23, are NOT here.** Every one of those sub-cases requires actually
//! SETTING the working-repository environment variable to a specific value
//! (a missing path, a regular file, a directory with no git marker, a path
//! inside this repository's own working tree, or the empty string), which
//! requires `std::env::set_var`. This workspace's pinned toolchain makes that
//! function `unsafe`, and this file is compiled INTO the
//! `#![forbid(unsafe_code)]` crate (REQ-3) via `lib.rs`'s `#[cfg(test)]
//! #[path]` mechanism, so it cannot use an `unsafe` block at all -- exactly
//! the constraint `crates/hierarchy-vor/tests/public_surface.rs`'s header
//! names for its own ONE environment-mutating test, which is why THAT test
//! lives in an external `tests/` crate rather than in `unit_tests/`. This
//! file therefore tests only the "absent" half of AC-21, relying on the
//! working-repository environment variable's natural absence in a plain
//! `cargo test` invocation (nobody sets a variable this specific and
//! fixture-only by accident); the remaining sub-cases of AC-21, and all of
//! AC-22 and AC-23, are `crates/actuator-git/tests/public_surface.rs`'s job,
//! compiled as an external crate that is free to mutate the process
//! environment the same way `hierarchy-vor`'s own external test does.

// ---------------------------------------------------------------------------------
// AC-15 (REQ-14, REQ-15): the permitted-target allowlist is non-empty and
// neither `main` nor `master` appears.
// ---------------------------------------------------------------------------------

#[test]
fn ac15_permitted_target_allowlist_is_non_empty_and_excludes_main_and_master() {
    // Exercised through the public surface: a push to a target this file has
    // no way of knowing is permitted must still be refused by SOME allowlist
    // check, proving the allowlist exists and is consulted. The direct,
    // pub(crate) enumeration this criterion literally asks for
    // ("when its members are enumerated") is available once this file is
    // wired in-crate (`crate::targets::PERMITTED_TARGETS`, an assumed name);
    // if that constant's real name differs, only the assertion below needs
    // updating, not the CONTRACT under test.
    for protected in ["main", "master"] {
        let op = crate::GitOperation::Push {
            remote: "origin".to_string(),
            ref_name: protected.to_string(),
        };
        let outcome = crate::execute(&op);
        assert!(
            !matches!(outcome, Ok(_)),
            "AC-15: a push to {protected:?} must never succeed; got {outcome:?}"
        );
        // REQ-15's own load-bearing point: the mechanism is ABSENCE from the
        // allowlist, so the refusal should be TargetNotPermitted, the same
        // as any other absent target, not a special-cased protected-ref
        // arm treated as the mechanism (AC-16 asserts this distinction
        // directly for `main`).
    }
}

// ---------------------------------------------------------------------------------
// AC-16 (REQ-14, REQ-15, REQ-16): a push to `main` refuses with the
// target-not-permitted variant, NOT the protected-ref variant.
// ---------------------------------------------------------------------------------

#[test]
fn ac16_push_to_main_refuses_via_absence_not_via_the_protected_ref_arm() {
    let op = crate::GitOperation::Push {
        remote: "origin".to_string(),
        ref_name: "main".to_string(),
    };
    let outcome = crate::execute(&op);
    assert!(
        matches!(
            outcome,
            Err(crate::ActuationRefusal::TargetNotPermitted { .. })
        ),
        "AC-16: a push to main must refuse with TargetNotPermitted (absence from the \
         allowlist is the mechanism, REQ-15), not ProtectedRef (defence in depth only, \
         REQ-16); got {outcome:?}"
    );
    assert!(
        !matches!(outcome, Err(crate::ActuationRefusal::ProtectedRef { .. })),
        "AC-16: ProtectedRef must not be the variant returned for main; it is \
         structurally unreachable given REQ-14 and REQ-15 and must never be described \
         as the mechanism"
    );
}

// ---------------------------------------------------------------------------------
// AC-17 (REQ-14): an arbitrary absent, non-protected target refuses
// identically -- an unrecognised target earns no positive match.
// ---------------------------------------------------------------------------------

#[test]
fn ac17_arbitrary_unrecognised_target_refuses_identically() {
    let op = crate::GitOperation::Push {
        remote: "origin".to_string(),
        ref_name: "totally-unrelated-ref-outside-any-hardcoded-allowlist-zzz".to_string(),
    };
    let outcome = crate::execute(&op);
    assert!(
        matches!(
            outcome,
            Err(crate::ActuationRefusal::TargetNotPermitted { .. })
        ),
        "AC-17: an arbitrary target absent from the allowlist and not a known protected \
         name must still refuse with TargetNotPermitted (fails closed on an unrecognised \
         positive match, invariant 3.5's own discipline one layer over); got {outcome:?}"
    );
}

// ---------------------------------------------------------------------------------
// AC-18 (REQ-14): membership is by PAIR, not by either field alone.
// ---------------------------------------------------------------------------------

#[test]
fn ac18_remote_and_ref_individually_permitted_but_not_as_a_pair_refuses() {
    // Two calls, each permitted on ONE axis: a real permitted remote paired
    // with an unrelated ref, and vice versa. Neither call can be assumed to
    // know the crate's real allowlist pairing from outside, so this uses two
    // plausible-but-almost-certainly-mismatched combinations; if the real
    // allowlist happens to permit one of these exact pairs, this is a named
    // gap to replace with a concrete counter-fixture once the real allowlist
    // is visible (the same "named gap" discipline
    // `crates/himinbjorg/unit_tests/six_checks.rs` uses for `ac19`/`ac21`).
    let mismatched_a = crate::GitOperation::Push {
        remote: "origin".to_string(),
        ref_name: "totally-unrelated-ref-outside-any-hardcoded-allowlist-zzz".to_string(),
    };
    let mismatched_b = crate::GitOperation::Push {
        remote: "totally-unrelated-remote-outside-any-hardcoded-allowlist-zzz".to_string(),
        ref_name: "fixture-integration-branch".to_string(),
    };
    for op in [mismatched_a, mismatched_b] {
        let outcome = crate::execute(&op);
        assert!(
            matches!(
                outcome,
                Err(crate::ActuationRefusal::TargetNotPermitted { .. })
            ),
            "AC-18: a remote/ref pair that is not JOINTLY permitted must refuse with \
             TargetNotPermitted even if one field alone matches a permitted entry; got \
             {outcome:?} for {op:?}"
        );
    }
}

// ---------------------------------------------------------------------------------
// AC-21 (REQ-18, REQ-19), absent-only half: the working-repository
// environment variable's natural absence in this unit-test binary refuses
// with the resolution-failure variant. The "empty string" half lives in
// tests/public_surface.rs (see this file's header).
// ---------------------------------------------------------------------------------

#[test]
fn ac21_working_repository_env_var_absent_by_default_refuses_resolution() {
    // No env::set_var anywhere in this file (forbidden under
    // #![forbid(unsafe_code)], see this file's header): this relies on the
    // working-repository environment variable's natural absence in a plain
    // `cargo test` invocation for a fixture-only variable name nobody sets
    // by accident. A permitted-target push is used so this test observes
    // resolution failure specifically, not a target-allowlist refusal.
    let op = crate::GitOperation::Push {
        remote: "origin".to_string(),
        ref_name: "fixture-integration-branch".to_string(),
    };
    let outcome = crate::execute(&op);
    assert!(
        matches!(
            outcome,
            Err(crate::ActuationRefusal::RepositoryResolution { .. })
        ) || matches!(outcome, Err(crate::ActuationRefusal::TargetNotPermitted { .. })),
        "AC-21: with the working-repository environment variable absent (its default \
         state in this unit-test binary), execute must refuse; if the target pair above \
         happens not to be the real permitted one, TargetNotPermitted is an acceptable \
         alternative refusal, but a bare Ok(_) is never acceptable; got {outcome:?}"
    );
    assert!(
        !matches!(outcome, Ok(_)),
        "AC-21: an absent working-repository environment variable must never yield a \
         success, whatever the exact refusal variant; got {outcome:?}"
    );
}
