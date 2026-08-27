//! `execute`, the crate's single public entry point, and the only module in
//! the whole workspace that touches `std::process` (REQ-7, section 10 file
//! nine of `.opencode/plans/git-actuator-step-four.md`). This module's one
//! responsibility (section 9.3) is spawning the process under a controlled
//! environment and a bounded wait, and mapping its exit status; it decides
//! nothing about whether an operation is permitted, which is
//! `crate::argv`'s and `crate::targets`'s job, called here in the fixed
//! order the crate's own unit tests assume (see this module's "ASSUMED
//! CONTRACT" section below).
//!
//! **No shell is invoked on any path (REQ-10).** The `git` binary is spawned
//! directly with a constructed argument vector (`std::process::Command::new("git").args(argv)`).
//! There is no `sh -c`, no `bash -c`, no `cmd /c`, and no string built up and
//! handed to a shell to reinterpret.
//!
//! **The spawned process's environment is controlled, never inherited
//! wholesale (REQ-21).** `Command::env_clear` empties the child's
//! environment before anything is added back; only `PATH` and `HOME`, each
//! read once from this process's own environment and forwarded explicitly,
//! are permitted through, because git needs `PATH` to resolve its own helper
//! binaries and benefits from `HOME` to find whatever global configuration
//! the host already carries. `GIT_TERMINAL_PROMPT` is never inherited; it is
//! always set to `"0"` by this module itself, so a credential git cannot
//! obtain non-interactively fails the operation rather than blocking on a
//! terminal prompt (REQ-21, EC-9). No other variable, named or not, crosses
//! from this process into the spawned one. This is the direct analogue of
//! the corpus source cited in section 15 of the spec (synacktiv.com):
//! inheriting a parent environment wholesale hands every secret it carries
//! to the child process, which this module never does.
//!
//! **A bounded, named wall-clock limit, implemented with the standard
//! library only (REQ-22).** [`EXECUTION_TIMEOUT`] is the one named constant
//! this module checks against, read exactly once here (REQ-2 forbids an
//! external dependency of any kind, so there is no timer crate to reach
//! for). The spawned process's standard output and standard error are
//! drained continuously by two dedicated threads for the whole lifetime of
//! the wait (never left to fill an unread pipe buffer, which could otherwise
//! deadlock a verbose process against a main thread that is merely polling),
//! while the main thread polls [`std::process::Child::try_wait`] until
//! either the process exits or the deadline passes. On expiry the process is
//! terminated (REQ-22) and the operation refuses with
//! [`crate::types::ActuationRefusal::Timeout`].
//!
//! **A named residual on termination, stated rather than smoothed.**
//! [`std::process::Child::kill`] targets the direct child process only (the
//! `git` binary itself). A git hook that has itself spawned a further
//! descendant (for example, a shell script invoking `sleep`) is not
//! guaranteed to be reaped when the direct child is killed: on most
//! platforms, killing a parent does not automatically kill its own
//! orphaned children. Closing this fully needs a dedicated process group
//! and a group-wide signal, which needs either `unsafe` (forbidden, REQ-3)
//! or a dependency (forbidden, REQ-2) to send outside the direct-child
//! surface `std::process::Child` itself exposes safely; this module instead
//! places the child in its own process group (`#[cfg(unix)]`, via the safe,
//! std-only `CommandExt::process_group`) purely so an orphaned descendant is
//! not left in the actuator's own process group, and states the remaining
//! limit here rather than claiming full termination.
//!
//! **Exit-status checking never reports a non-zero or signalled process as a
//! success (REQ-23).** `std::process::ExitStatus::success` is `true` if and
//! only if the process exited with code zero; a signalled process (whose
//! `code()` the platform reports as absent) makes `success()` `false` too,
//! so both cases route to the same refusal path, never a success and never a
//! partial success.
//!
//! **Captured, never inherited, and treated as untrusted (REQ-24).** Both
//! `stdout` and `stderr` are piped, never `Stdio::inherit`, and no
//! comparison, branch or classification anywhere in this module (or
//! elsewhere in the crate, per `unit_tests/argv_validation.rs`'s AC-31 scan)
//! derives a control-flow decision from their content. The only use captured
//! output is ever put to is [`bounded_diagnostic`], on a refusal path only,
//! which truncates it to [`MAX_DIAGNOSTIC_BYTES`] before it reaches any
//! `ActuationRefusal` variant's `diagnostic` field, so a verbose or
//! adversarial process cannot use its own output to inflate a refusal's
//! memory footprint (EC-8).
//!
//! **Integration with `crate::argv` and `crate::targets` (issue #48,
//! landed).** This module calls three functions it does not own, per
//! section 9.3's split of responsibility:
//!
//!   - `crate::argv::build_commit_argv(message: &str) -> Result<Vec<String>, ActuationRefusal>`
//!     and `crate::argv::build_push_argv(remote: &str, ref_name: &str) -> Result<Vec<String>, ActuationRefusal>`.
//!     Each owns its operation's fixed argument shape (REQ-9) and the
//!     positive-match value validation of every caller-supplied string that
//!     shape carries (REQ-11 to REQ-13), returning
//!     `Err(ActuationRefusal::InvalidArgument { .. })` before any process is
//!     spawned when a value fails validation. This module never constructs
//!     a git argument vector itself and never revalidates a value `argv`
//!     already validated.
//!   - `crate::targets::check_target(remote: &str, ref_name: &str) -> Result<(), ActuationRefusal>`.
//!     Answers, for a push only, both REQ-14's allowlist-membership question
//!     and REQ-16's defence-in-depth protected-ref arm, returning the
//!     already-constructed `TargetNotPermitted` or `ProtectedRef` refusal
//!     directly. This module never reads the permitted-target allowlist
//!     itself and is never called for a commit, which has no target at all.

use crate::types::{ActuationOutcome, ActuationRefusal, GitOperation};
use std::io::Read;
use std::path::Path;
use std::process::{Command, ExitStatus, Stdio};
use std::time::{Duration, Instant};

/// The bounded, named wall-clock limit REQ-22 requires. Appears exactly
/// once, as this named constant, and is referenced nowhere else as a
/// literal (section 9.2's "constants, never repeated literals" rule).
const EXECUTION_TIMEOUT: Duration = Duration::from_secs(10);

/// How long the polling loop in [`spawn_and_wait`] sleeps between successive
/// [`std::process::Child::try_wait`] checks. Small enough that a fast git
/// invocation is not perceptibly delayed by polling granularity, large
/// enough that polling does not spin the CPU.
const POLL_INTERVAL: Duration = Duration::from_millis(20);

/// The named length bound REQ-24 requires on any diagnostic text that may
/// carry captured, untrusted process output. Appears exactly once, as this
/// named constant.
const MAX_DIAGNOSTIC_BYTES: usize = 4096;

/// The crate's single public entry point (section 5.1). Performs exactly one
/// of the two operations REQ-8 permits: a local commit, or a push. Every
/// fail-closed check REQ-9 to REQ-25 describe is enforced in this fixed
/// order, matching the order `unit_tests/argv_validation.rs` and
/// `unit_tests/target_and_repo_failclosed.rs` both assume:
///
///   1. Value validation and fixed argument-vector construction
///      (`crate::argv::build_argv`, REQ-9, REQ-11 to REQ-13). A failing
///      caller-supplied string refuses here, before anything else runs and
///      before any process is spawned.
///   2. For a push only, permitted-target membership, then the REQ-16
///      defence-in-depth protected-ref arm (`crate::targets`, REQ-14 to
///      REQ-16).
///   3. Working-repository resolution (`crate::repo::resolve_working_repository`,
///      REQ-18 to REQ-20).
///   4. The process spawn itself, under a controlled environment and a
///      bounded wait, with exit-status checking (REQ-7, REQ-10, REQ-21 to
///      REQ-24, this module's own doc comment above).
pub fn execute(operation: &GitOperation) -> Result<ActuationOutcome, ActuationRefusal> {
    match operation {
        GitOperation::Commit { message } => {
            // Step one: value validation and argument-vector construction.
            // This function never builds a git argument vector itself
            // (section 9.3); a commit has no target, so step two (below)
            // never runs for it.
            let argv = crate::argv::build_commit_argv(message)?;

            // Step three: working-repository resolution. Never the
            // inherited current working directory, never a compiled-in
            // default (REQ-18).
            let repo = crate::repo::resolve_working_repository()
                .map_err(|diagnostic| ActuationRefusal::RepositoryResolution { diagnostic })?;

            // Step four: the process spawn itself.
            run_git(&argv, &repo, ActuationOutcome::Committed)
        }
        GitOperation::Push { remote, ref_name } => {
            // Step one: value validation and argument-vector construction.
            let argv = crate::argv::build_push_argv(remote, ref_name)?;

            // Step two: target-allowlist membership (REQ-14), then the
            // REQ-16 defence-in-depth protected-ref arm, both answered by
            // `crate::targets`, the allowlist's only reader. This module
            // never reads `crate::targets::PERMITTED_TARGETS` itself.
            crate::targets::check_target(remote, ref_name)?;

            // Step three: working-repository resolution.
            let repo = crate::repo::resolve_working_repository()
                .map_err(|diagnostic| ActuationRefusal::RepositoryResolution { diagnostic })?;

            // Step four: the process spawn itself.
            run_git(&argv, &repo, ActuationOutcome::Pushed)
        }
    }
}

/// Spawns `git` with `argv` inside `repo` (REQ-20: the resolved working
/// directory is always given explicitly, never inherited), waits under
/// [`EXECUTION_TIMEOUT`], checks the exit status (REQ-23), and maps a clean
/// zero exit to `success`. Every other outcome is a refusal, never a success
/// and never a partial success.
fn run_git(
    argv: &[String],
    repo: &Path,
    success: ActuationOutcome,
) -> Result<ActuationOutcome, ActuationRefusal> {
    let (status, stdout, stderr) = spawn_and_wait(argv, repo)?;
    if status.success() {
        Ok(success)
    } else {
        Err(ActuationRefusal::ExitStatus {
            diagnostic: bounded_diagnostic(format!(
                "git {argv:?} exited with status {status:?} in {}; captured output \
                 follows and is untrusted (REQ-24): stdout={:?} stderr={:?}",
                repo.display(),
                bounded_diagnostic(String::from_utf8_lossy(&stdout).into_owned()),
                bounded_diagnostic(String::from_utf8_lossy(&stderr).into_owned()),
            )),
        })
    }
}

/// Spawns the `git` binary directly (REQ-10: no shell on any path), under a
/// controlled environment (REQ-21) and the resolved working directory
/// (REQ-20), waits under a bounded, named wall-clock limit implemented with
/// the standard library only (REQ-22), and returns the exit status together
/// with the process's fully captured, never-inherited standard output and
/// standard error (REQ-24). On a spawn failure or a timeout, returns the
/// corresponding refusal directly; the caller never sees a bare `Ok` for
/// either case.
fn spawn_and_wait(
    argv: &[String],
    repo: &Path,
) -> Result<(ExitStatus, Vec<u8>, Vec<u8>), ActuationRefusal> {
    let mut command = Command::new("git");
    command.args(argv);
    command.current_dir(repo); // REQ-20: explicit, never the inherited cwd.
    command.env_clear(); // REQ-21: controlled, never inherited wholesale.
    if let Ok(path) = std::env::var("PATH") {
        // Permitted so git can resolve its own helper binaries.
        command.env("PATH", path);
    }
    if let Ok(home) = std::env::var("HOME") {
        // Permitted so git can find whatever global configuration the host
        // already carries; neither variable is a secret.
        command.env("HOME", home);
    }
    // Always set by this module itself, never inherited: disables
    // interactive credential prompting, so a credential git cannot obtain
    // non-interactively fails the operation rather than blocking on a
    // terminal prompt (REQ-21, EC-9).
    command.env("GIT_TERMINAL_PROMPT", "0");
    command.stdin(Stdio::null());
    command.stdout(Stdio::piped());
    command.stderr(Stdio::piped());
    #[cfg(unix)]
    {
        use std::os::unix::process::CommandExt;
        // A named residual, not a full fix: places the child in its own
        // process group purely so an orphaned descendant is not left in the
        // actuator's own process group. See this module's own doc comment
        // for why this does not, by itself, guarantee a hook's further
        // descendants are reaped on timeout.
        command.process_group(0);
    }

    let mut child = command.spawn().map_err(|e| ActuationRefusal::SpawnFailed {
        diagnostic: bounded_diagnostic(format!(
            "failed to spawn the git binary (never a fallback to a second candidate \
             path, EC-1): {e}"
        )),
    })?;

    // REQ-24: captured, never inherited, drained continuously so a verbose
    // process cannot deadlock the wait against a full, unread pipe buffer.
    let mut stdout_pipe = child
        .stdout
        .take()
        .expect("stdout was requested as piped above");
    let mut stderr_pipe = child
        .stderr
        .take()
        .expect("stderr was requested as piped above");
    let stdout_reader = std::thread::spawn(move || {
        let mut buffer = Vec::new();
        let _ = stdout_pipe.read_to_end(&mut buffer);
        buffer
    });
    let stderr_reader = std::thread::spawn(move || {
        let mut buffer = Vec::new();
        let _ = stderr_pipe.read_to_end(&mut buffer);
        buffer
    });

    // REQ-22: bounded, named wall-clock limit, implemented with the
    // standard library only (no external timer of any kind, REQ-2).
    let deadline = Instant::now() + EXECUTION_TIMEOUT;
    let exited = loop {
        match child.try_wait() {
            Ok(Some(status)) => break Some(status),
            Ok(None) => {
                if Instant::now() >= deadline {
                    break None;
                }
                std::thread::sleep(POLL_INTERVAL);
            }
            Err(e) => {
                return Err(ActuationRefusal::SpawnFailed {
                    diagnostic: bounded_diagnostic(format!(
                        "failed to wait on the spawned git process: {e}"
                    )),
                });
            }
        }
    };

    match exited {
        Some(status) => {
            let stdout = stdout_reader.join().unwrap_or_default();
            let stderr = stderr_reader.join().unwrap_or_default();
            Ok((status, stdout, stderr))
        }
        None => {
            // REQ-22: on expiry, the process is terminated and the
            // operation refuses fail closed. `child.kill` and `child.wait`
            // target the direct child (`git` itself) only, and both return
            // promptly: SIGKILL cannot be caught, blocked or ignored, so
            // `git` dies immediately even mid-syscall, and `wait` then
            // reaps it. Deliberately NOT joined here: `stdout_reader` and
            // `stderr_reader` (spawned above) call `read_to_end` on the
            // piped descriptors, which only returns once every process
            // holding the write end closes it. A hook that has itself
            // spawned a further descendant (this module's own doc comment's
            // named residual) inherits those same descriptors; if that
            // descendant is still running when `git` is killed, it keeps
            // the pipe open, and joining here would block this call for as
            // long as that orphaned descendant keeps running, defeating the
            // whole point of a bounded, named wall-clock limit (REQ-22).
            // `ActuationRefusal::Timeout` carries no diagnostic text at all
            // (its own doc comment: "the timeout itself is the whole of the
            // information"), so there is nothing captured output could add
            // here even if it were available. The two reader threads are
            // simply abandoned: dropping their `JoinHandle`s does not stop
            // them, so each keeps running independently and exits on its
            // own once its pipe eventually reaches end of file, with its
            // result discarded, never blocking this function's return.
            let _ = child.kill();
            let _ = child.wait();
            drop(stdout_reader);
            drop(stderr_reader);
            Err(ActuationRefusal::Timeout)
        }
    }
}

/// Truncates `text` to at most [`MAX_DIAGNOSTIC_BYTES`], so a refusal's
/// diagnostic text, which may carry captured, untrusted process output
/// (REQ-24), cannot be used by that same process to inflate the memory
/// footprint of a refusal value (EC-8). Truncation is on a UTF-8 boundary by
/// construction: [`String::from_utf8_lossy`] never panics on an ill-formed
/// byte sequence, replacing it with the standard replacement character
/// instead.
fn bounded_diagnostic(text: String) -> String {
    if text.len() <= MAX_DIAGNOSTIC_BYTES {
        text
    } else {
        let mut truncated =
            String::from_utf8_lossy(&text.as_bytes()[..MAX_DIAGNOSTIC_BYTES]).into_owned();
        truncated.push_str(" ...[diagnostic truncated at the named length bound]");
        truncated
    }
}
