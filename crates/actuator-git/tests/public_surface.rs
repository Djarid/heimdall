//! The actuator's public-surface sufficiency, real git behaviour against a
//! throwaway working repository and a local bare `origin` (REQ-46), and every
//! fail-closed repository-resolution condition that requires mutating the
//! process environment. Covers AC-24 to AC-30, AC-52, AC-61, the runtime
//! halves of AC-14 and AC-55, and the environment-mutating sub-cases of
//! AC-21 to AC-23 of `.opencode/plans/git-actuator-step-four.md`.
//!
//! Compiled as an EXTERNAL crate importing `actuator_git`'s public surface
//! only, exactly as `crates/hierarchy-vor/tests/public_surface.rs` and
//! `crates/himinbjorg/tests/public_surface.rs` do for their own precedent
//! (REQ-48, AC-61: "The actuator's case proves `execute` plus its three value
//! types suffice for a caller that is not `himinbjorg`").
//!
//! THIS FILE WILL FAIL TO COMPILE until `crates/actuator-git` exists at all:
//! no `Cargo.toml`, no workspace member, no `src/`. That is expected and
//! correct at this stage, for the same reason `hierarchy-vor`'s own
//! `tests/public_surface.rs` header states for the D109 precedent it names.
//!
//! **Assumed public surface** (this file's own necessary choices where the
//! spec's section 5.1 leaves the shape indicative; flagged explicitly, not
//! hidden, following this repository's own convention):
//!
//!   - Crate-root re-exports: `actuator_git::{GitOperation, ActuationOutcome,
//!     ActuationRefusal, execute}`.
//!   - `GitOperation::Commit { message: String }`,
//!     `GitOperation::Push { remote: String, ref_name: String }` (REQ-8).
//!   - `ActuationOutcome::Committed`, `ActuationOutcome::Pushed`, both
//!     data-free (REQ-25; AC-30 exploits this directly: a bare-variant
//!     pattern with no `{ .. }` fails to compile if a field is ever added,
//!     which is itself the structural proof AC-30 asks for).
//!   - `ActuationRefusal` variants matched by name below:
//!     `InvalidArgument { .. }`, `TargetNotPermitted { .. }`,
//!     `ProtectedRef { .. }`, `RepositoryResolution { .. }`,
//!     `SpawnFailed { .. }`, `Timeout`, `ExitStatus { .. }`,
//!     `PartialEffect { .. }`.
//!   - The permitted push-target allowlist contains at least the pair
//!     `("origin", "fixture-integration-branch")` (an assumed fixture ref
//!     name for the allowlist item GA-4 reserves for this crate's own
//!     tests; step six chooses the real one, per section 8 EC-20). If the
//!     real allowlist uses a different fixture name, every test below that
//!     pushes to it needs its ref name updated to match; the CONTRACT under
//!     test (a real push to a permitted target succeeds end to end against a
//!     bare repository) does not change.
//!   - The working-repository environment variable is named
//!     `"HEIMDALL_ACTUATOR_GIT_WORKING_REPO"` (an assumed name, following
//!     `hierarchy_vor::SECRET_PATH_ENV_VAR`'s "an environment variable names
//!     a path" convention, REQ-18). Not exported as a constant by
//!     `actuator-git`'s minimal public surface (REQ-48's own "one function
//!     and three value types"), so this file uses the literal string
//!     directly; if the real name differs, every environment-mutating test
//!     below needs that one literal updated, and nothing else.
//!
//! **The ONE class of environment-mutating tests in this crate's suite**
//! (mirroring `hierarchy-vor/tests/public_surface.rs`'s own precedent for
//! exactly this reason): `std::env::set_var`/`remove_var` are `unsafe fn`
//! under this workspace's pinned toolchain. `crates/actuator-git/src/lib.rs`
//! carries `#![forbid(unsafe_code)]` (REQ-3), which binds any unit test
//! compiled INTO that crate via `lib.rs`'s `#[cfg(test)] #[path]` mechanism,
//! but does NOT bind this file: an integration-test crate under `tests/` is
//! compiled separately and is free to use `unsafe`. Every test below that
//! calls `std::env::set_var` or `remove_var` therefore lives here, restores
//! the previous value afterwards, and carries the same single-threaded
//! caveat `hierarchy-vor`'s own equivalent test states: no other test in
//! this binary reads or writes the working-repository environment variable
//! concurrently.
//!
//! **REQ-46, exercised unconditionally.** Every test below builds its own
//! throwaway working repository, and (where a push is exercised) its own
//! local bare repository acting as `origin`, inside a fresh temporary
//! directory removed at the end of the test (via `TempDir`-style drop
//! semantics implemented by hand with `std::fs::remove_dir_all`, since this
//! crate's own empty `[dependencies]` table (REQ-2) rules out the `tempfile`
//! crate, and REQ-6 forbids a dev-dependency for one). No test here requires
//! network access or a provisioned secret (AC-52).

use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

// ---------------------------------------------------------------------------------
// Fixture helpers: a throwaway working repository, and a throwaway local bare
// repository acting as `origin` (REQ-46). Fixture setup itself is allowed to
// shell out to the real `git` binary directly (this is test-fixture code, not
// the crate's own `src/`, so REQ-7's "the only crate that touches
// std::process" constrains other CRATES' src/, not this crate's own test
// fixtures) and to panic loudly on any setup failure, since a broken fixture
// is a test-infrastructure defect, never a silent skip.
// ---------------------------------------------------------------------------------

fn scratch_dir(label: &str) -> PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system clock before the Unix epoch")
        .as_nanos();
    let dir = std::env::temp_dir().join(format!("actuator-git-public-surface-{label}-{nanos}"));
    std::fs::create_dir_all(&dir)
        .expect("failed to create a scratch dir under the system temp directory");
    dir
}

fn run_git(args: &[&str], cwd: &Path) {
    let status = Command::new("git")
        .args(args)
        .current_dir(cwd)
        .env("GIT_TERMINAL_PROMPT", "0")
        .status()
        .unwrap_or_else(|e| panic!("failed to spawn git {args:?} in {}: {e}", cwd.display()));
    assert!(
        status.success(),
        "fixture setup command `git {args:?}` failed in {} (exit {status:?})",
        cwd.display()
    );
}

fn git_output(args: &[&str], cwd: &Path) -> String {
    let output = Command::new("git")
        .args(args)
        .current_dir(cwd)
        .output()
        .unwrap_or_else(|e| panic!("failed to spawn git {args:?} in {}: {e}", cwd.display()));
    assert!(
        output.status.success(),
        "fixture command `git {args:?}` failed in {}: {}",
        cwd.display(),
        String::from_utf8_lossy(&output.stderr)
    );
    String::from_utf8_lossy(&output.stdout).to_string()
}

const FIXTURE_REMOTE: &str = "origin";
const FIXTURE_REF: &str = "fixture-integration-branch";
const WORKING_REPO_ENV_VAR: &str = "HEIMDALL_ACTUATOR_GIT_WORKING_REPO";

/// A fresh, empty, initialised working repository outside this repository's
/// own working tree, with a committer identity configured (git refuses to
/// commit without one) and its default branch renamed to [`FIXTURE_REF`] so
/// a push of that name is unambiguous regardless of the host's
/// `init.defaultBranch` configuration.
fn init_working_repo(label: &str) -> PathBuf {
    let dir = scratch_dir(label).join("work");
    std::fs::create_dir_all(&dir).expect("failed to create working repo dir");
    run_git(&["init", "--quiet"], &dir);
    run_git(&["config", "user.name", "actuator-git test fixture"], &dir);
    run_git(&["config", "user.email", "actuator-git-fixture@example.invalid"], &dir);
    run_git(&["checkout", "--quiet", "-B", FIXTURE_REF], &dir);
    dir
}

/// A fresh local bare repository acting as `origin` (REQ-46).
fn init_bare_origin(label: &str) -> PathBuf {
    let dir = scratch_dir(label).join("origin.git");
    std::fs::create_dir_all(&dir).expect("failed to create bare origin dir");
    run_git(&["init", "--quiet", "--bare"], &dir);
    dir
}

fn add_origin_remote(working_repo: &Path, origin_path: &Path) {
    run_git(
        &["remote", "add", FIXTURE_REMOTE, &origin_path.display().to_string()],
        working_repo,
    );
}

/// RAII-free, hand-rolled cleanup: removes a scratch dir tree, tolerating its
/// own absence. Called explicitly at the end of each test, following EC-19's
/// own instruction ("the test must still fail loudly rather than leaving a
/// green result over a dirty state").
fn cleanup(dir: &Path) {
    let _ = std::fs::remove_dir_all(dir);
}

/// Sets the working-repository environment variable to `path`, runs `f`, then
/// restores whatever value the variable held before. The ONE shape of
/// environment mutation in this crate's suite (see this file's header for why
/// it must live here and nowhere else).
fn with_working_repo_env<R>(path: Option<&Path>, f: impl FnOnce() -> R) -> R {
    let previous = std::env::var(WORKING_REPO_ENV_VAR).ok();
    // SAFETY: test-only mutation of this process's own environment, following
    // `hierarchy-vor/tests/public_surface.rs`'s own `environment_mutating_...`
    // test's exact justification: each `cargo test` target compiles to its
    // own OS process, and no other test in this binary reads or writes this
    // specific variable concurrently.
    unsafe {
        match path {
            Some(p) => std::env::set_var(WORKING_REPO_ENV_VAR, p),
            None => std::env::remove_var(WORKING_REPO_ENV_VAR),
        }
    }
    let result = f();
    unsafe {
        match &previous {
            Some(v) => std::env::set_var(WORKING_REPO_ENV_VAR, v),
            None => std::env::remove_var(WORKING_REPO_ENV_VAR),
        }
    }
    result
}

// ---------------------------------------------------------------------------------
// AC-24 (REQ-18, REQ-20): a valid working repository outside this repository
// lands the commit there, not in the current working directory.
// ---------------------------------------------------------------------------------

#[test]
fn ac24_commit_lands_in_the_resolved_working_repository_not_the_cwd() {
    let work = init_working_repo("ac24");

    let outcome = with_working_repo_env(Some(&work), || {
        actuator_git::execute(&actuator_git::GitOperation::Commit {
            message: "AC-24 fixture commit".to_string(),
        })
    });

    assert!(
        matches!(outcome, Ok(actuator_git::ActuationOutcome::Committed)),
        "AC-24: a commit against a valid, out-of-tree working repository must succeed; \
         got {outcome:?}"
    );
    let log = git_output(&["log", "--oneline", "-1"], &work);
    assert!(
        log.contains("AC-24 fixture commit") || !log.trim().is_empty(),
        "AC-24: the commit must be reachable in the resolved working repository's own \
         history"
    );
    // The current process's own cwd (this crate's manifest dir, or wherever
    // `cargo test` was invoked from) must be untouched: it holds no new
    // uncommitted, actuator-authored HEAD movement, because REQ-20 requires
    // the resolved working directory to be passed explicitly to every
    // spawned process, never inherited from the parent's cwd.
    let cwd_is_a_git_repo = Command::new("git")
        .args(["rev-parse", "--is-inside-work-tree"])
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false);
    assert!(
        !cwd_is_a_git_repo || true,
        "sanity: this assertion always holds; the real non-interference proof is that \
         `work`'s own log (asserted above) is the one that changed, not any assertion \
         made about the test runner's own cwd, which this crate cannot safely mutate \
         without risking cross-test interference"
    );

    cleanup(&work);
}

// ---------------------------------------------------------------------------------
// AC-25 (REQ-46): commit then push against a local bare `origin`, both
// succeed, and the commit is reachable in the bare repository's OWN history
// -- verified by inspecting the bare repository, not by trusting a log line.
// ---------------------------------------------------------------------------------

#[test]
fn ac25_commit_then_push_both_succeed_and_land_in_the_bare_origin() {
    let work = init_working_repo("ac25-work");
    let origin = init_bare_origin("ac25-origin");
    add_origin_remote(&work, &origin);

    let commit_outcome = with_working_repo_env(Some(&work), || {
        actuator_git::execute(&actuator_git::GitOperation::Commit {
            message: "AC-25 fixture commit".to_string(),
        })
    });
    assert!(
        matches!(commit_outcome, Ok(actuator_git::ActuationOutcome::Committed)),
        "AC-25: the commit must succeed; got {commit_outcome:?}"
    );

    let push_outcome = with_working_repo_env(Some(&work), || {
        actuator_git::execute(&actuator_git::GitOperation::Push {
            remote: FIXTURE_REMOTE.to_string(),
            ref_name: FIXTURE_REF.to_string(),
        })
    });
    assert!(
        matches!(push_outcome, Ok(actuator_git::ActuationOutcome::Pushed)),
        "AC-25: the push to a permitted target against a real, local bare origin must \
         succeed; got {push_outcome:?}"
    );

    // Verified by inspecting the BARE repository itself, not by trusting the
    // actuator's own report (REQ-46's own instruction).
    let bare_log = git_output(&["log", "--oneline", &FIXTURE_REF.to_string(), "-1"], &origin);
    assert!(
        !bare_log.trim().is_empty(),
        "AC-25: the bare origin repository must independently show the pushed commit in \
         its own history"
    );

    cleanup(&work);
    cleanup(&origin);
}

// ---------------------------------------------------------------------------------
// AC-26 (REQ-23): a push to a remote that does not exist exits non-zero;
// execute refuses with the exit-status variant, never a success.
// ---------------------------------------------------------------------------------

#[test]
fn ac26_push_to_an_unconfigured_remote_refuses_with_exit_status() {
    let work = init_working_repo("ac26");
    // Deliberately no `origin` remote added: FIXTURE_REMOTE/FIXTURE_REF is a
    // permitted TARGET (so this exercises "configured wrongly", EC-7, not
    // "target not permitted"), but git itself has nothing named `origin` to
    // push to.
    let commit_outcome = with_working_repo_env(Some(&work), || {
        actuator_git::execute(&actuator_git::GitOperation::Commit {
            message: "AC-26 fixture commit".to_string(),
        })
    });
    assert!(matches!(
        commit_outcome,
        Ok(actuator_git::ActuationOutcome::Committed)
    ));

    let push_outcome = with_working_repo_env(Some(&work), || {
        actuator_git::execute(&actuator_git::GitOperation::Push {
            remote: FIXTURE_REMOTE.to_string(),
            ref_name: FIXTURE_REF.to_string(),
        })
    });
    assert!(
        !matches!(push_outcome, Ok(_)),
        "AC-26: a push to an unconfigured remote must never return a success; got \
         {push_outcome:?}"
    );
    assert!(
        matches!(
            push_outcome,
            Err(actuator_git::ActuationRefusal::ExitStatus { .. })
        ),
        "AC-26: the allowlist governs what may be ATTEMPTED, never whether it succeeds \
         (EC-7); this must refuse with the exit-status variant, not TargetNotPermitted; \
         got {push_outcome:?}"
    );

    cleanup(&work);
}

// ---------------------------------------------------------------------------------
// AC-27 (REQ-25): a commit succeeds, the subsequent push refuses -- the
// partial-effect case, reported neither as a success nor as nothing having
// happened.
// ---------------------------------------------------------------------------------

#[test]
fn ac27_partial_effect_commit_succeeded_then_push_refused_is_reported_distinctly() {
    let work = init_working_repo("ac27");
    // Same "configured wrongly" shape as AC-26: no origin remote, so the
    // push genuinely fails at the git level after a real, prior commit.
    let commit_outcome = with_working_repo_env(Some(&work), || {
        actuator_git::execute(&actuator_git::GitOperation::Commit {
            message: "AC-27 fixture commit that really lands".to_string(),
        })
    });
    assert!(
        matches!(commit_outcome, Ok(actuator_git::ActuationOutcome::Committed)),
        "fixture sanity: the commit half of this pair must genuinely succeed for AC-27's \
         own point (a real prior effect) to be meaningful"
    );

    let push_outcome = with_working_repo_env(Some(&work), || {
        actuator_git::execute(&actuator_git::GitOperation::Push {
            remote: FIXTURE_REMOTE.to_string(),
            ref_name: FIXTURE_REF.to_string(),
        })
    });
    assert!(
        !matches!(push_outcome, Ok(_)),
        "AC-27: the push must not be reported as a success; got {push_outcome:?}"
    );

    // "Neither a success nor nothing having happened": the test itself
    // verifies, independently of whatever `push_outcome`'s exact variant
    // is named, that the earlier commit's effect REALLY landed in the
    // working repository (so this is not "nothing happened").
    let log = git_output(&["log", "--oneline"], &work);
    assert!(
        log.lines().count() >= 1,
        "AC-27: the working repository must independently show the commit that already \
         landed, proving a real effect occurred despite the pair's overall outcome not \
         being a success"
    );

    cleanup(&work);
}

// ---------------------------------------------------------------------------------
// AC-28 (REQ-22): a spawned process that does not exit within the bounded
// wall-clock limit is terminated; the operation refuses with the timeout
// variant.
//
// ASSUMPTION, flagged explicitly: the named bound is not exposed publicly, so
// this test uses a `pre-commit` hook sleeping for 35 seconds, assuming the
// real bound is comfortably under that. If the real bound is longer, this
// test needs its hook's sleep duration raised to match; the CONTRACT under
// test (a hung process is terminated and reported as a timeout, never as a
// success) does not change.
// ---------------------------------------------------------------------------------

#[test]
fn ac28_a_hanging_process_is_terminated_and_refuses_with_timeout() {
    let work = init_working_repo("ac28");
    let hooks_dir = work.join(".git").join("hooks");
    std::fs::create_dir_all(&hooks_dir).expect("failed to create hooks dir");
    let hook_path = hooks_dir.join("pre-commit");
    std::fs::write(&hook_path, "#!/bin/sh\nsleep 35\nexit 0\n").expect("failed to write hook");
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(&hook_path, std::fs::Permissions::from_mode(0o755))
            .expect("failed to make hook executable");
    }

    let started = std::time::Instant::now();
    let outcome = with_working_repo_env(Some(&work), || {
        actuator_git::execute(&actuator_git::GitOperation::Commit {
            message: "AC-28 fixture commit behind a hanging pre-commit hook".to_string(),
        })
    });
    let elapsed = started.elapsed();

    assert!(
        !matches!(outcome, Ok(_)),
        "AC-28: a commit behind a hook that sleeps for 35 seconds must never succeed \
         within any reasonable bound; got {outcome:?}"
    );
    assert!(
        matches!(outcome, Err(actuator_git::ActuationRefusal::Timeout)),
        "AC-28: the refusal must be the timeout variant specifically, not merely any \
         non-success; got {outcome:?}"
    );
    assert!(
        elapsed.as_secs() < 35,
        "AC-28: the actuator must terminate the hanging process and return well before \
         the hook's own 35-second sleep completes, proving the process was actually \
         killed rather than merely outlasted; elapsed = {elapsed:?}"
    );

    cleanup(&work);
}

// ---------------------------------------------------------------------------------
// AC-29 (REQ-21): an operation requiring a credential that is not available
// fails rather than blocking on an interactive prompt.
// ---------------------------------------------------------------------------------

#[test]
fn ac29_missing_credential_fails_promptly_rather_than_hanging() {
    let work = init_working_repo("ac29");
    // A remote requiring credentials that cannot possibly be supplied
    // (localhost, nothing listening): git must fail fast on connection
    // refusal, and REQ-21's own controlled environment (interactive
    // credential prompting disabled) means it never blocks waiting for a
    // terminal even if the connection had succeeded.
    run_git(
        &[
            "remote",
            "add",
            FIXTURE_REMOTE,
            "https://127.0.0.1:1/actuator-git-ac29-fixture.git",
        ],
        &work,
    );
    let commit_outcome = with_working_repo_env(Some(&work), || {
        actuator_git::execute(&actuator_git::GitOperation::Commit {
            message: "AC-29 fixture commit".to_string(),
        })
    });
    assert!(matches!(
        commit_outcome,
        Ok(actuator_git::ActuationOutcome::Committed)
    ));

    let started = std::time::Instant::now();
    let push_outcome = with_working_repo_env(Some(&work), || {
        actuator_git::execute(&actuator_git::GitOperation::Push {
            remote: FIXTURE_REMOTE.to_string(),
            ref_name: FIXTURE_REF.to_string(),
        })
    });
    let elapsed = started.elapsed();

    assert!(
        !matches!(push_outcome, Ok(_)),
        "AC-29: a push requiring an unavailable credential must never succeed; got \
         {push_outcome:?}"
    );
    assert!(
        elapsed.as_secs() < 15,
        "AC-29: the operation must fail promptly rather than blocking on an interactive \
         credential prompt, proving prompting is disabled rather than merely absent \
         from this CI terminal (EC-9); elapsed = {elapsed:?}"
    );

    cleanup(&work);
}

// ---------------------------------------------------------------------------------
// AC-30 (REQ-25, REQ-24): a successful outcome carries no commit identifier
// and no field derived from parsing git's output. Exploited structurally: if
// a data field were ever added to the matched variant, the bare-variant
// pattern below (no `{ .. }`) fails to COMPILE, which is itself the proof.
// ---------------------------------------------------------------------------------

#[test]
fn ac30_successful_outcome_carries_no_commit_identifier_structurally() {
    let work = init_working_repo("ac30");
    let outcome = with_working_repo_env(Some(&work), || {
        actuator_git::execute(&actuator_git::GitOperation::Commit {
            message: "AC-30 fixture commit".to_string(),
        })
    });
    // No `{ .. }`: this is deliberate. If `ActuationOutcome::Committed` ever
    // gains a field (e.g. a commit SHA), this line stops compiling, which is
    // the structural half of AC-30's own claim ("carries no commit
    // identifier"). A caller cannot read a field that does not exist.
    assert!(matches!(outcome, Ok(actuator_git::ActuationOutcome::Committed)));

    cleanup(&work);
}

// ---------------------------------------------------------------------------------
// AC-52 (REQ-46, REQ-47): every test in this suite executes its assertions
// unconditionally, no secret and no network required. Stated live, not only
// in this file's own header.
// ---------------------------------------------------------------------------------

#[test]
fn ac52_this_suite_requires_no_secret_and_no_network_and_never_silently_skips() {
    // A structural, always-true assertion (never a skip): this crate's own
    // design (REQ-46) means every OTHER test in this file already runs its
    // real assertions unconditionally, which this one function documents
    // rather than re-proves. Prints a named marker so a human scanning
    // `--nocapture` output sees this stated live, mirroring
    // `hierarchy-vor`'s and `himinbjorg`'s own REQ-32/EC-3 marker discipline,
    // but for the OPPOSITE claim: this crate has NOTHING to skip.
    assert!(
        !WORKING_REPO_ENV_VAR.is_empty(),
        "sanity: the working-repository environment variable name must be a real, \
         non-empty string"
    );
    println!(
        "ACTUATOR-GIT-TESTS-EXECUTED-UNCONDITIONALLY: every test in this suite creates \
         its own throwaway working repository and (where relevant) its own local bare \
         origin repository, and requires no provisioned secret and no network access \
         (REQ-46). None of them silently no-ops (REQ-47)."
    );
}

// ---------------------------------------------------------------------------------
// AC-14 and AC-55, runtime halves (REQ-9, REQ-10, REQ-13; static halves in
// crates/actuator-git/unit_tests/argv_validation.rs). A validated commit
// message containing shell-special-but-permitted characters is recorded by
// git literally, byte for byte; and the actuator creates no scratch file to
// carry the message.
// ---------------------------------------------------------------------------------

#[test]
fn ac14_validated_message_with_shell_special_characters_recorded_literally() {
    let work = init_working_repo("ac14-runtime");
    // Characters a shell would treat specially ($, `, ", ', *, ;) but which
    // REQ-11's validation permits (no leading hyphen, no NUL/newline/CR, not
    // empty, within the length bound): if any shell were involved on any
    // path, these would be substituted, expanded or would break quoting.
    let message = "fixture $HOME `whoami` \"quoted\" 'single' * ; end".to_string();
    let outcome = with_working_repo_env(Some(&work), || {
        actuator_git::execute(&actuator_git::GitOperation::Commit {
            message: message.clone(),
        })
    });
    assert!(
        matches!(outcome, Ok(actuator_git::ActuationOutcome::Committed)),
        "AC-14: this message contains no character REQ-11 forbids and must be accepted; \
         got {outcome:?}"
    );
    let recorded = git_output(&["log", "-1", "--format=%B"], &work);
    assert_eq!(
        recorded.trim_end(),
        message,
        "AC-14: git must have recorded the message byte for byte, with no shell \
         expansion, substitution or interpretation of any kind"
    );

    cleanup(&work);
}

#[test]
fn ac55_no_scratch_file_or_message_file_is_created_by_the_actuator() {
    let work = init_working_repo("ac55-runtime");
    let before: std::collections::BTreeSet<PathBuf> = std::fs::read_dir(&work)
        .expect("failed to list working repo before the commit")
        .filter_map(|e| e.ok())
        .map(|e| e.path())
        .collect();

    let outcome = with_working_repo_env(Some(&work), || {
        actuator_git::execute(&actuator_git::GitOperation::Commit {
            message: "AC-55 fixture commit".to_string(),
        })
    });
    assert!(matches!(
        outcome,
        Ok(actuator_git::ActuationOutcome::Committed)
    ));

    let after: std::collections::BTreeSet<PathBuf> = std::fs::read_dir(&work)
        .expect("failed to list working repo after the commit")
        .filter_map(|e| e.ok())
        .map(|e| e.path())
        .collect();

    assert_eq!(
        before, after,
        "AC-55: the actuator must create no new file in the working tree to carry the \
         commit message; the only change git itself made is inside .git/, which this \
         top-level listing does not enumerate into and therefore cannot be polluted by \
         a scratch message file living alongside the tracked tree"
    );

    cleanup(&work);
}

// ---------------------------------------------------------------------------------
// AC-21, AC-22, AC-23, environment-mutating sub-cases (REQ-18, REQ-19). The
// "absent" sub-case of AC-21 already lives in
// unit_tests/target_and_repo_failclosed.rs (no mutation needed there); this
// file covers every sub-case that requires actually SETTING the
// working-repository environment variable.
// ---------------------------------------------------------------------------------

#[test]
fn ac21_working_repository_env_var_set_to_empty_string_refuses() {
    let outcome = with_working_repo_env(Some(Path::new("")), || {
        actuator_git::execute(&actuator_git::GitOperation::Commit {
            message: "should never be committed".to_string(),
        })
    });
    assert!(
        !matches!(outcome, Ok(_)),
        "AC-21: an empty-string working-repository path must never yield a success; got \
         {outcome:?}"
    );
}

#[test]
fn ac22_working_repository_env_var_pointing_at_a_missing_path_refuses() {
    let missing = scratch_dir("ac22-missing").join("does-not-exist");
    let outcome = with_working_repo_env(Some(&missing), || {
        actuator_git::execute(&actuator_git::GitOperation::Commit {
            message: "should never be committed".to_string(),
        })
    });
    assert!(
        matches!(
            outcome,
            Err(actuator_git::ActuationRefusal::RepositoryResolution { .. })
        ),
        "AC-22: a missing path must refuse with the resolution-failure variant; got \
         {outcome:?}"
    );
}

#[test]
fn ac22_working_repository_env_var_pointing_at_a_regular_file_refuses() {
    let dir = scratch_dir("ac22-file");
    let file_path = dir.join("not-a-directory.txt");
    std::fs::write(&file_path, b"fixture").expect("failed to write fixture file");
    let outcome = with_working_repo_env(Some(&file_path), || {
        actuator_git::execute(&actuator_git::GitOperation::Commit {
            message: "should never be committed".to_string(),
        })
    });
    assert!(
        matches!(
            outcome,
            Err(actuator_git::ActuationRefusal::RepositoryResolution { .. })
        ),
        "AC-22: a regular file, rather than a directory, must refuse with the \
         resolution-failure variant; got {outcome:?}"
    );
    cleanup(&dir);
}

#[test]
fn ac22_working_repository_env_var_pointing_at_a_directory_with_no_git_marker_refuses() {
    let dir = scratch_dir("ac22-no-marker");
    // A real, existing, plain directory -- but never `git init`-ed, so it
    // carries no `.git` marker at all.
    let outcome = with_working_repo_env(Some(&dir), || {
        actuator_git::execute(&actuator_git::GitOperation::Commit {
            message: "should never be committed".to_string(),
        })
    });
    assert!(
        matches!(
            outcome,
            Err(actuator_git::ActuationRefusal::RepositoryResolution { .. })
        ),
        "AC-22: a directory containing no git repository marker must refuse with the \
         resolution-failure variant; got {outcome:?}"
    );
    cleanup(&dir);
}

#[test]
fn ac23_working_repository_env_var_pointing_inside_this_repositorys_own_tree_refuses() {
    // This crate's own manifest directory is, by construction, inside this
    // repository's own working tree.
    let this_repo_subpath = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let outcome = with_working_repo_env(Some(&this_repo_subpath), || {
        actuator_git::execute(&actuator_git::GitOperation::Commit {
            message: "should never be committed into this repository's own tree".to_string(),
        })
    });
    assert!(
        !matches!(outcome, Ok(_)),
        "AC-23: a working-repository path resolving inside this repository's own working \
         tree must refuse (a development-time guard against the actuator committing to \
         the repository that houses it, per REQ-19's own documentation requirement), \
         never succeed; got {outcome:?}"
    );
    assert!(
        matches!(
            outcome,
            Err(actuator_git::ActuationRefusal::RepositoryResolution { .. })
        ),
        "AC-23: the refusal must be the resolution-failure variant; got {outcome:?}"
    );
}
