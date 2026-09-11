// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! The invocation module (REQ-9, REQ-11 to REQ-13, REQ-31 to REQ-34): the
//! only module in this crate -- and the second module in the whole
//! workspace, alongside `crates/actuator-git/src/execute.rs` and `main.rs`'s
//! one disclosed `std::process::exit` (D112, reopened by REQ-53) -- that
//! touches `std::process`, and the only module in this crate that reads the
//! process environment (REQ-11).
//!
//! **The spawn is a fixed argv with no shell on any path (REQ-15, REQ-33).**
//! The sidecar is invoked as a module (`-m`), never as a path: the module
//! name is [`SIDECAR_MODULE_NAME`], a compile-time constant. Nothing
//! derived from any input, any environment value's contents beyond the two
//! resolved paths, or any prior output contributes any other part of the
//! argv.
//!
//! **The child's environment is cleared and then populated from a named,
//! closed forwarding set (REQ-34), on `execute.rs`'s own `env_clear`
//! precedent:** `PATH` (so the interpreter can resolve its own shared
//! libraries and helper binaries) and `HOME` (so it finds whatever
//! per-user configuration -- a virtual environment marker, a package
//! cache -- the host already carries; neither is a secret), each
//! forwarded explicitly from this process's own environment, plus
//! `PYTHONPATH`, set explicitly by this module itself from the
//! already-validated package-root path rather than forwarded from any
//! pre-existing `PYTHONPATH` this process might have inherited. No other
//! variable crosses.
//!
//! **A bounded, named wall-clock limit, implemented with the standard
//! library only (REQ-32).** [`SIDECAR_TIMEOUT_SECS`] is the one named
//! constant checked against, on `execute.rs`'s own `EXECUTION_TIMEOUT`
//! precedent: a bounded poll on [`std::process::Child::try_wait`], never an
//! unbounded [`std::process::Child::wait`]. On expiry the child is killed
//! and reaped, no partial output is read or used, and the call refuses. No
//! retry exists on any path.
//!
//! **The child is placed in its own process group before it is spawned
//! (`#[cfg(unix)] .process_group(0)`), on `execute.rs`'s exact precedent.**
//! A named residual, not a full fix: it exists purely so an orphaned
//! descendant is not left in this crate's own process group. It does not,
//! by itself, guarantee that every further descendant a timed-out Python
//! interpreter may have spawned (for example, anything `mlx_lm` itself
//! forks while loading the model) is reaped on timeout; see `execute.rs`'s
//! own doc comment for the same residual stated against `git`'s hooks.
//!
//! **The child's own output is drained continuously while the parent
//! waits (EC-46).** Both standard output and standard error are piped and
//! read to completion on their own threads for the whole lifetime of the
//! wait, on `execute.rs`'s own precedent, so a verbose sidecar cannot
//! deadlock the bounded wait against a full, unread pipe buffer.
//!
//! **Every one of REQ-31's eleven refusal conditions is fail closed
//! here.** No branch below produces a default value, caches or reuses a
//! previous value, retries, accepts a partial output or substitutes any
//! other value on any failure.

use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

use crate::types::{CognitionMessage, SidecarRefusal};

/// The environment variable naming the Python interpreter to spawn
/// (REQ-11). Read exactly once, inside [`obtain_message`], and nowhere
/// else in this crate.
pub(crate) const PYTHON_INTERPRETER_ENV_VAR: &str = "HEIMDALL_COGNITION_PYTHON_INTERPRETER";

/// The environment variable naming the directory placed on the child's
/// `PYTHONPATH` so the `cognition` package can import (REQ-11). Read
/// exactly once, inside [`obtain_message`], and nowhere else in this
/// crate.
pub(crate) const COGNITION_PACKAGE_ROOT_ENV_VAR: &str = "HEIMDALL_COGNITION_PACKAGE_ROOT";

/// The sidecar's wall-clock bound (REQ-32, ST7-10): fixed at 300 seconds,
/// chosen so a cold model load on Apple silicon (tens of seconds for a
/// 4-bit 7B model) cannot false-fire while the bound stays a real one.
pub(crate) const SIDECAR_TIMEOUT_SECS: u64 = 300;

/// How often the bounded wait polls [`std::process::Child::try_wait`].
/// Small enough that a fast sidecar's exit is observed promptly, large
/// enough not to spin the polling thread.
const POLL_INTERVAL: Duration = Duration::from_millis(20);

/// The sidecar's module name (REQ-15): a compile-time constant, never a
/// path. Spawned as `<interpreter> -m cognition.sidecar`.
const SIDECAR_MODULE_NAME: &str = "cognition.sidecar";

/// The fixed line-oriented output's one key, followed by its separator
/// (REQ-22): the sidecar's own single line of output is
/// `MESSAGE=<content>`, deliberately not JSON, so this module needs no
/// parser beyond a prefix check and a byte-index slice.
const MESSAGE_KEY_PREFIX: &str = "MESSAGE=";

/// Resolves the interpreter-path value into a validated, existing,
/// executable regular file (REQ-31 item 1). Refuses on every one of: an
/// absent value, an empty or whitespace-only value, a value naming a path
/// that does not exist, a value naming a directory, or a value naming a
/// regular file with no execute permission.
fn resolve_interpreter_path(value: Option<&str>) -> Result<PathBuf, SidecarRefusal> {
    let Some(raw) = value else {
        return Err(SidecarRefusal::new(
            "the interpreter-path environment value is not set",
        ));
    };
    if raw.trim().is_empty() {
        return Err(SidecarRefusal::new(
            "the interpreter-path environment value is empty or whitespace only",
        ));
    }
    let path = Path::new(raw);
    let metadata = match std::fs::metadata(path) {
        Ok(m) => m,
        Err(_) => {
            return Err(SidecarRefusal::new(
                "the interpreter-path environment value names a path that does not exist",
            ));
        }
    };
    if metadata.is_dir() {
        return Err(SidecarRefusal::new(
            "the interpreter-path environment value names a directory, not an \
             executable regular file",
        ));
    }
    if !metadata.is_file() {
        return Err(SidecarRefusal::new(
            "the interpreter-path environment value does not name a regular file",
        ));
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mode = metadata.permissions().mode();
        if mode & 0o111 == 0 {
            return Err(SidecarRefusal::new(
                "the interpreter-path environment value names a regular file with no \
                 execute permission",
            ));
        }
    }
    #[cfg(not(unix))]
    {
        return Err(SidecarRefusal::new(
            "this target provides no Unix permission metadata to confirm the \
             interpreter path is executable; refusing rather than silently skipping \
             the check",
        ));
    }
    Ok(path.to_path_buf())
}

/// Resolves the package-root value into a validated, existing directory
/// (REQ-31 item 2). Refuses on every one of: an absent value, an empty or
/// whitespace-only value, a value naming a path that does not exist, or a
/// value naming a plain file rather than a directory.
fn resolve_package_root(value: Option<&str>) -> Result<PathBuf, SidecarRefusal> {
    let Some(raw) = value else {
        return Err(SidecarRefusal::new(
            "the package-root environment value is not set",
        ));
    };
    if raw.trim().is_empty() {
        return Err(SidecarRefusal::new(
            "the package-root environment value is empty or whitespace only",
        ));
    }
    let path = Path::new(raw);
    let metadata = match std::fs::metadata(path) {
        Ok(m) => m,
        Err(_) => {
            return Err(SidecarRefusal::new(
                "the package-root environment value names a path that does not exist",
            ));
        }
    };
    if !metadata.is_dir() {
        return Err(SidecarRefusal::new(
            "the package-root environment value names a plain file, not a directory",
        ));
    }
    Ok(path.to_path_buf())
}

/// Spawns the sidecar with a fixed argv and no shell (REQ-33), under a
/// cleared and explicitly repopulated environment (REQ-34), writes `prompt`
/// to its standard input, drains its standard output and standard error
/// continuously (EC-46), waits under the bounded, named wall-clock limit
/// (REQ-32), and returns the captured standard output on a clean, non-zero
/// exit; refuses on a spawn failure, a non-zero exit, or the timeout
/// expiring (REQ-31 items 3, 6, 11).
fn spawn_and_collect(
    interpreter: &Path,
    package_root: &Path,
    prompt: &str,
) -> Result<Vec<u8>, SidecarRefusal> {
    let mut command = Command::new(interpreter);
    command.arg("-m").arg(SIDECAR_MODULE_NAME);
    command.env_clear();
    if let Ok(path_var) = std::env::var("PATH") {
        // Permitted so the interpreter can resolve its own shared
        // libraries and helper binaries.
        command.env("PATH", path_var);
    }
    if let Ok(home_var) = std::env::var("HOME") {
        // Permitted so the interpreter finds whatever per-user
        // configuration the host already carries; neither variable is a
        // secret.
        command.env("HOME", home_var);
    }
    // Set explicitly by this module itself from the already-validated
    // package-root path, never forwarded from any pre-existing PYTHONPATH
    // this process might have inherited, so the cognition package's
    // import location is always exactly what REQ-11 resolved.
    command.env("PYTHONPATH", package_root);
    command.stdin(Stdio::piped());
    command.stdout(Stdio::piped());
    command.stderr(Stdio::piped());
    #[cfg(unix)]
    {
        use std::os::unix::process::CommandExt;
        // A named residual, not a full fix: places the child in its own
        // process group purely so an orphaned descendant is not left in
        // this crate's own process group. See execute.rs's own doc comment
        // (this module's own doc comment mirrors it) for why this does
        // not, by itself, guarantee a timed-out interpreter's further
        // descendants (for example, anything mlx_lm itself spawns) are
        // reaped on timeout.
        command.process_group(0);
    }

    let mut child = command
        .spawn()
        .map_err(|_| SidecarRefusal::new("failed to spawn the sidecar interpreter process"))?;

    if let Some(mut stdin) = child.stdin.take() {
        // Best effort: a child that exits before reading its prompt (for
        // example, a stand-in interpreter under test) closes its own end
        // of the pipe, which makes this write fail; that failure is never
        // treated as its own refusal reason, because the real outcome (if
        // any) is the child's own exit status or output shape, checked
        // below. Dropping `stdin` at the end of this block closes this
        // process's end too, giving the child a clean end of file.
        let _ = stdin.write_all(prompt.as_bytes());
    }

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

    // REQ-32: a bounded, named wall-clock limit, implemented with the
    // standard library only. A `while` bound rather than an unconditional
    // repeat, so the wait is bounded by construction rather than by
    // review.
    let deadline = Instant::now() + Duration::from_secs(SIDECAR_TIMEOUT_SECS);
    let mut exited = None;
    while Instant::now() < deadline {
        match child.try_wait() {
            Ok(Some(status)) => {
                exited = Some(status);
                break;
            }
            Ok(None) => {
                std::thread::sleep(POLL_INTERVAL);
            }
            Err(_) => {
                return Err(SidecarRefusal::new(
                    "failed to wait on the spawned sidecar process",
                ));
            }
        }
    }

    match exited {
        Some(status) => {
            let stdout = stdout_reader.join().unwrap_or_default();
            let _stderr = stderr_reader.join().unwrap_or_default();
            if !status.success() {
                return Err(SidecarRefusal::new(
                    "the sidecar process exited with a non-zero status",
                ));
            }
            Ok(stdout)
        }
        None => {
            // REQ-32: on expiry, the child is killed and reaped; no
            // partial output is read or used. The two reader threads are
            // abandoned rather than joined, on `execute.rs`'s own
            // precedent, so an orphaned descendant holding a pipe open
            // cannot block this call past its own bounded wait.
            let _ = child.kill();
            let _ = child.wait();
            drop(stdout_reader);
            drop(stderr_reader);
            Err(SidecarRefusal::new(
                "the sidecar did not respond within the timeout and was killed",
            ))
        }
    }
}

/// Parses the fixed, minimal, line-oriented output shape (REQ-22, REQ-31
/// items 7 and 8): refuses on output that is empty or whitespace only,
/// refuses on output that is not exactly one line, and refuses on a line
/// that does not begin with the fixed `MESSAGE=` key. Returns the raw
/// content after the key, unvalidated: validating it is
/// `crate::validation`'s job alone.
fn parse_line_oriented_output(raw_bytes: &[u8]) -> Result<String, SidecarRefusal> {
    let raw = String::from_utf8_lossy(raw_bytes);
    if raw.trim().is_empty() {
        return Err(SidecarRefusal::new(
            "the sidecar produced empty or whitespace-only output",
        ));
    }
    let lines: Vec<&str> = raw.lines().collect();
    if lines.len() != 1 {
        return Err(SidecarRefusal::new(
            "the sidecar's output did not consist of exactly one line in the fixed \
             line-oriented shape",
        ));
    }
    let line = lines[0];
    if !line.starts_with(MESSAGE_KEY_PREFIX) {
        return Err(SidecarRefusal::new(
            "the sidecar's output line did not begin with the expected MESSAGE= key",
        ));
    }
    Ok(line[MESSAGE_KEY_PREFIX.len()..].to_string())
}

/// The pure* half of this module (REQ-11's own doc comment names the
/// property; *pure with respect to the process environment only: it still
/// performs the real spawn, wait and validate using the already-resolved
/// values it is given). Resolves both path-shaped values, spawns the
/// sidecar, waits under the bounded timeout, parses its fixed output
/// shape, and validates the extracted message through
/// [`crate::validation::validate_received_message`], the single
/// positive-match validator. Refuses on every one of REQ-31's eleven
/// conditions; substitutes, caches, retries or defaults on none of them.
pub(crate) fn resolve_sidecar_invocation(
    interpreter_path_value: Option<&str>,
    package_root_value: Option<&str>,
    prompt: &str,
) -> Result<CognitionMessage, SidecarRefusal> {
    let interpreter = resolve_interpreter_path(interpreter_path_value)?;
    let package_root = resolve_package_root(package_root_value)?;
    let stdout_bytes = spawn_and_collect(&interpreter, &package_root, prompt)?;
    let content = parse_line_oriented_output(&stdout_bytes)?;
    crate::validation::validate_received_message(&content)
}

/// The crate's one public function (REQ-10). Reads the two path-shaped
/// environment variables exactly once, here, and forwards their values
/// into [`resolve_sidecar_invocation`]. No other environment variable, no
/// configuration file and no command-line argument is read anywhere in
/// this crate (REQ-11).
pub fn obtain_message(prompt: &str) -> Result<CognitionMessage, SidecarRefusal> {
    let interpreter_path_value = std::env::var(PYTHON_INTERPRETER_ENV_VAR).ok();
    let package_root_value = std::env::var(COGNITION_PACKAGE_ROOT_ENV_VAR).ok();
    resolve_sidecar_invocation(
        interpreter_path_value.as_deref(),
        package_root_value.as_deref(),
        prompt,
    )
}
