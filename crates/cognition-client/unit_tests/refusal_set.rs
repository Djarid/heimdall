//! The fail-closed refusal set (REQ-31 to REQ-34 of
//! `.opencode/plans/build-order-step-seven-spec.md`; AC-34 to AC-37):
//! every one of REQ-31's eleven conditions returns `Err`, none returns
//! `Ok`; the wall-clock bound (REQ-32); the fixed argv with no shell
//! (REQ-33); and the closed environment-forwarding set (REQ-34).
//!
//! THIS FILE WILL FAIL TO COMPILE until `crates/cognition-client/src/`
//! carries an invocation module exposing the items assumed below. That is
//! the expected RED state for this build-order step.
//!
//! **Compiled as an IN-CRATE unit test module**, wired into
//! `crates/cognition-client/src/lib.rs` via
//! `#[cfg(test)] #[path = "../unit_tests/refusal_set.rs"] mod refusal_set_tests;`
//! (already present in the scaffolding `lib.rs`).
//!
//! **Signatures and shapes assumed here** (this file's own necessary
//! choices, flagged explicitly, following `crates/process-engine/src/startup.rs`'s
//! own pure/impure split precedent -- which REQ-11 itself cites -- so that
//! every environment-VALUE-shaped refusal condition is testable from an
//! in-crate module bound by `#![forbid(unsafe_code)]`, without mutating the
//! real process environment via the `unsafe fn`s `std::env::set_var`/
//! `remove_var` on this workspace's pinned toolchain):
//!
//!   - `crate::PYTHON_INTERPRETER_ENV_VAR: &str` and
//!     `crate::COGNITION_PACKAGE_ROOT_ENV_VAR: &str`: the two named,
//!     path-shaped environment-variable-name constants (REQ-11). This
//!     file's own necessary choice of concrete names; an implementer
//!     naming them differently satisfies the spec provided the two
//!     constants exist and are each read exactly once, inside the
//!     invocation module alone.
//!   - `crate::SIDECAR_TIMEOUT_SECS: u64`, fixed at 300 (REQ-32, ST7-10).
//!   - `crate::resolve_sidecar_invocation(interpreter_path_value:
//!     Option<&str>, package_root_value: Option<&str>, prompt: &str) ->
//!     Result<crate::CognitionMessage, crate::SidecarRefusal>`: the pure*
//!     half of the invocation module (*pure with respect to the process
//!     environment; it still performs the real spawn, wait and validate
//!     using the already-read values it is given, so its own tests below
//!     hold on every machine regardless of what is or is not provisioned
//!     in the real environment). `pub(crate)`, reachable from this
//!     in-crate module.
//!   - `crate::obtain_message(prompt: &str) -> Result<crate::CognitionMessage,
//!     crate::SidecarRefusal>`: the one public function (REQ-10), the thin
//!     wrapper that reads the two environment variables and forwards their
//!     values into `resolve_sidecar_invocation`. Not called by this file at
//!     all (mirroring `startup_failclosed.rs`'s own convention): every test
//!     below calls `resolve_sidecar_invocation` directly with fixture
//!     values, so this suite holds unconditionally regardless of what is or
//!     is not provisioned in the real environment.
//!
//! **The stand-in interpreter's own fixed output shape, this file's own
//! necessary choice** (REQ-22 fixes only that the shape is line-oriented,
//! fixed-key-order and not JSON; it does not fix the exact keys). This
//! file assumes the simplest instance satisfying REQ-16's
//! single-field-commit-message-schema reading: exactly one line, of the
//! form `MESSAGE=<content>`. A second line of any kind is therefore an
//! unexpected-key shape (there is only one key in a single-field schema),
//! and an absent or malformed first line is a missing-key shape. This
//! assumption is deliberately weaker than a multi-key schema would need
//! for an "out-of-order key" case to be meaningful; this file does not
//! claim to exercise that sub-case of REQ-31 item eight, and says so here
//! rather than silently claiming coverage it does not have.

use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

fn scratch_dir(label: &str) -> PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system clock before the Unix epoch")
        .as_nanos();
    let dir = std::env::temp_dir().join(format!("cognition-client-refusal-set-{label}-{nanos}"));
    fs::create_dir_all(&dir).expect("failed to create a scratch dir under the system temp directory");
    dir
}

/// Writes an executable shell-script "stand-in interpreter" at
/// `dir/name` whose body is `body` (the spec's own instruction, REQ-31's
/// header note and AC-34: "using a stand-in interpreter where a child is
/// needed"). The script ignores every argument, including the `-m` flag
/// and the module name REQ-33 fixes: this file's own stand-ins do not
/// need to inspect their argv at all, because each stand-in's own fixed
/// output is what a given test wants to exercise.
#[cfg(unix)]
fn write_stand_in_interpreter(dir: &std::path::Path, name: &str, body: &str) -> PathBuf {
    use std::os::unix::fs::PermissionsExt;
    let path = dir.join(name);
    fs::write(&path, format!("#!/bin/sh\n{body}\n")).expect("failed to write stand-in interpreter");
    fs::set_permissions(&path, fs::Permissions::from_mode(0o755))
        .expect("failed to make stand-in interpreter executable");
    path
}

#[cfg(unix)]
fn valid_looking_package_root(label: &str) -> PathBuf {
    scratch_dir(label)
}

// ---------------------------------------------------------------------------------
// REQ-31 conditions 1 and 2: the interpreter-path and package-root
// variables, unset/empty/whitespace-only/non-existent/wrong-type. Every
// scenario below isolates ONE failing precondition, pairing it with a
// genuinely resolving other one, on startup_failclosed.rs's own isolation
// discipline.
// ---------------------------------------------------------------------------------

#[cfg(unix)]
#[test]
fn interpreter_path_unset_refuses() {
    let package_root = valid_looking_package_root("interp-unset");
    let result = crate::resolve_sidecar_invocation(None, Some(package_root.to_str().unwrap()), "prompt");
    assert!(
        result.is_err(),
        "REQ-31 item 1/AC-34: an absent interpreter-path value must refuse"
    );
}

#[cfg(unix)]
#[test]
fn interpreter_path_empty_refuses() {
    let package_root = valid_looking_package_root("interp-empty");
    let result =
        crate::resolve_sidecar_invocation(Some(""), Some(package_root.to_str().unwrap()), "prompt");
    assert!(
        result.is_err(),
        "REQ-31 item 1/AC-34: an empty interpreter-path value must refuse"
    );
}

#[cfg(unix)]
#[test]
fn interpreter_path_whitespace_only_refuses() {
    let package_root = valid_looking_package_root("interp-whitespace");
    let result =
        crate::resolve_sidecar_invocation(Some("   "), Some(package_root.to_str().unwrap()), "prompt");
    assert!(
        result.is_err(),
        "REQ-31 item 1/AC-34: a whitespace-only interpreter-path value must refuse, not \
         merely a non-empty-length check"
    );
}

#[cfg(unix)]
#[test]
fn interpreter_path_nonexistent_refuses() {
    let package_root = valid_looking_package_root("interp-nonexistent");
    let bogus = scratch_dir("interp-nonexistent-target").join("this-was-never-created");
    let result = crate::resolve_sidecar_invocation(
        Some(bogus.to_str().unwrap()),
        Some(package_root.to_str().unwrap()),
        "prompt",
    );
    assert!(
        result.is_err(),
        "REQ-31 item 1/AC-34: an interpreter-path value naming a path that does not \
         exist must refuse"
    );
}

#[cfg(unix)]
#[test]
fn interpreter_path_naming_a_directory_refuses() {
    let package_root = valid_looking_package_root("interp-is-dir");
    let dir = scratch_dir("interp-is-dir-target");
    let result = crate::resolve_sidecar_invocation(
        Some(dir.to_str().unwrap()),
        Some(package_root.to_str().unwrap()),
        "prompt",
    );
    assert!(
        result.is_err(),
        "REQ-31 item 1/AC-34: an interpreter-path value naming a directory, not an \
         executable regular file, must refuse"
    );
}

#[cfg(unix)]
#[test]
fn interpreter_path_naming_a_non_executable_regular_file_refuses() {
    use std::os::unix::fs::PermissionsExt;
    let package_root = valid_looking_package_root("interp-not-exec");
    let dir = scratch_dir("interp-not-exec-target");
    let file_path = dir.join("not-executable");
    fs::write(&file_path, b"#!/bin/sh\necho not executable\n").unwrap();
    fs::set_permissions(&file_path, fs::Permissions::from_mode(0o644)).unwrap();
    let result = crate::resolve_sidecar_invocation(
        Some(file_path.to_str().unwrap()),
        Some(package_root.to_str().unwrap()),
        "prompt",
    );
    assert!(
        result.is_err(),
        "REQ-31 item 1/AC-34: an interpreter-path value naming a regular file with no \
         execute permission must refuse"
    );
}

#[cfg(unix)]
#[test]
fn package_root_unset_refuses() {
    let dir = scratch_dir("pkg-unset");
    let interpreter = write_stand_in_interpreter(
        &dir,
        "python-stand-in.sh",
        "echo 'MESSAGE=probe'",
    );
    let result = crate::resolve_sidecar_invocation(Some(interpreter.to_str().unwrap()), None, "prompt");
    assert!(
        result.is_err(),
        "REQ-31 item 2/AC-34: an absent package-root value must refuse"
    );
}

#[cfg(unix)]
#[test]
fn package_root_empty_refuses() {
    let dir = scratch_dir("pkg-empty");
    let interpreter = write_stand_in_interpreter(&dir, "python-stand-in.sh", "echo 'MESSAGE=probe'");
    let result =
        crate::resolve_sidecar_invocation(Some(interpreter.to_str().unwrap()), Some(""), "prompt");
    assert!(
        result.is_err(),
        "REQ-31 item 2/AC-34: an empty package-root value must refuse"
    );
}

#[cfg(unix)]
#[test]
fn package_root_whitespace_only_refuses() {
    let dir = scratch_dir("pkg-whitespace");
    let interpreter = write_stand_in_interpreter(&dir, "python-stand-in.sh", "echo 'MESSAGE=probe'");
    let result =
        crate::resolve_sidecar_invocation(Some(interpreter.to_str().unwrap()), Some("   "), "prompt");
    assert!(
        result.is_err(),
        "REQ-31 item 2/AC-34: a whitespace-only package-root value must refuse"
    );
}

#[cfg(unix)]
#[test]
fn package_root_nonexistent_refuses() {
    let dir = scratch_dir("pkg-nonexistent");
    let interpreter = write_stand_in_interpreter(&dir, "python-stand-in.sh", "echo 'MESSAGE=probe'");
    let bogus = scratch_dir("pkg-nonexistent-target").join("this-was-never-created");
    let result = crate::resolve_sidecar_invocation(
        Some(interpreter.to_str().unwrap()),
        Some(bogus.to_str().unwrap()),
        "prompt",
    );
    assert!(
        result.is_err(),
        "REQ-31 item 2/AC-34: a package-root value naming a path that does not exist \
         must refuse"
    );
}

#[cfg(unix)]
#[test]
fn package_root_naming_a_file_not_a_directory_refuses() {
    let dir = scratch_dir("pkg-is-file");
    let interpreter = write_stand_in_interpreter(&dir, "python-stand-in.sh", "echo 'MESSAGE=probe'");
    let file_path = dir.join("not-a-directory");
    fs::write(&file_path, b"probe").unwrap();
    let result = crate::resolve_sidecar_invocation(
        Some(interpreter.to_str().unwrap()),
        Some(file_path.to_str().unwrap()),
        "prompt",
    );
    assert!(
        result.is_err(),
        "REQ-31 item 2/AC-34: a package-root value naming a plain file, not a \
         directory, must refuse"
    );
}

// ---------------------------------------------------------------------------------
// REQ-31 conditions 6 to 10: the spawned child's own behaviour, exercised
// with stand-in interpreters (AC-34's own instruction).
// ---------------------------------------------------------------------------------

#[cfg(unix)]
#[test]
fn nonzero_exit_status_refuses() {
    let dir = scratch_dir("nonzero-exit");
    let interpreter =
        write_stand_in_interpreter(&dir, "python-stand-in.sh", "echo 'MESSAGE=probe'\nexit 1");
    let package_root = valid_looking_package_root("nonzero-exit-pkg");
    let result = crate::resolve_sidecar_invocation(
        Some(interpreter.to_str().unwrap()),
        Some(package_root.to_str().unwrap()),
        "prompt",
    );
    assert!(
        result.is_err(),
        "REQ-31 item 6/AC-34: a non-zero exit status from the child must refuse"
    );
}

#[cfg(unix)]
#[test]
fn empty_output_refuses() {
    let dir = scratch_dir("empty-output");
    let interpreter = write_stand_in_interpreter(&dir, "python-stand-in.sh", "true");
    let package_root = valid_looking_package_root("empty-output-pkg");
    let result = crate::resolve_sidecar_invocation(
        Some(interpreter.to_str().unwrap()),
        Some(package_root.to_str().unwrap()),
        "prompt",
    );
    assert!(
        result.is_err(),
        "REQ-31 item 7/AC-34: output that is empty must refuse"
    );
}

#[cfg(unix)]
#[test]
fn whitespace_only_output_refuses() {
    let dir = scratch_dir("whitespace-output");
    let interpreter = write_stand_in_interpreter(&dir, "python-stand-in.sh", "printf '   \\n  '");
    let package_root = valid_looking_package_root("whitespace-output-pkg");
    let result = crate::resolve_sidecar_invocation(
        Some(interpreter.to_str().unwrap()),
        Some(package_root.to_str().unwrap()),
        "prompt",
    );
    assert!(
        result.is_err(),
        "REQ-31 item 7/AC-34: output that is whitespace only must refuse"
    );
}

#[cfg(unix)]
#[test]
fn output_with_no_recognised_key_refuses_missing_key_shape() {
    let dir = scratch_dir("missing-key");
    let interpreter = write_stand_in_interpreter(&dir, "python-stand-in.sh", "echo 'not the right shape'");
    let package_root = valid_looking_package_root("missing-key-pkg");
    let result = crate::resolve_sidecar_invocation(
        Some(interpreter.to_str().unwrap()),
        Some(package_root.to_str().unwrap()),
        "prompt",
    );
    assert!(
        result.is_err(),
        "REQ-31 item 8/AC-34: output whose fixed line-oriented shape does not parse \
         (here, a missing MESSAGE= key) must refuse"
    );
}

#[cfg(unix)]
#[test]
fn output_with_an_unexpected_extra_line_refuses_unexpected_key_shape() {
    let dir = scratch_dir("unexpected-key");
    let interpreter = write_stand_in_interpreter(
        &dir,
        "python-stand-in.sh",
        "echo 'MESSAGE=probe'\necho 'EXTRA=unexpected'",
    );
    let package_root = valid_looking_package_root("unexpected-key-pkg");
    let result = crate::resolve_sidecar_invocation(
        Some(interpreter.to_str().unwrap()),
        Some(package_root.to_str().unwrap()),
        "prompt",
    );
    assert!(
        result.is_err(),
        "REQ-31 item 8/AC-34: output carrying an unexpected extra key/line beyond the \
         fixed single-field schema must refuse"
    );
}

#[cfg(unix)]
#[test]
fn output_failing_the_positive_match_validator_refuses() {
    let dir = scratch_dir("validator-fail");
    // A leading hyphen in the message content fails REQ-24's own validator
    // (see unit_tests/validator.rs), so this exercises REQ-31 item 9's own
    // condition end to end through a real spawn.
    let interpreter =
        write_stand_in_interpreter(&dir, "python-stand-in.sh", "echo 'MESSAGE=-leading-hyphen'");
    let package_root = valid_looking_package_root("validator-fail-pkg");
    let result = crate::resolve_sidecar_invocation(
        Some(interpreter.to_str().unwrap()),
        Some(package_root.to_str().unwrap()),
        "prompt",
    );
    assert!(
        result.is_err(),
        "REQ-31 item 9/AC-34: output whose message content fails the positive-match \
         validator must refuse"
    );
}

#[cfg(unix)]
#[test]
fn output_exceeding_the_declared_maximum_length_refuses() {
    let dir = scratch_dir("over-length");
    // MAX_RECEIVED_VALUE_LEN plus one 'a' characters, echoed by the
    // stand-in via a Rust-generated shell command embedding the literal
    // content (small enough to fit comfortably in a shell command line on
    // every supported platform, since this crate's own maximum length is
    // expected to be well under argv/line-length limits, REQ-24).
    let too_long = "a".repeat(4_097);
    let script_body = format!("echo 'MESSAGE={too_long}'");
    let interpreter = write_stand_in_interpreter(&dir, "python-stand-in.sh", &script_body);
    let package_root = valid_looking_package_root("over-length-pkg");
    let result = crate::resolve_sidecar_invocation(
        Some(interpreter.to_str().unwrap()),
        Some(package_root.to_str().unwrap()),
        "prompt",
    );
    assert!(
        result.is_err(),
        "REQ-31 item 10/AC-34: output exceeding the declared maximum length must refuse"
    );
}

// ---------------------------------------------------------------------------------
// Contrapositive: a well-behaved stand-in interpreter, satisfying every
// condition, resolves successfully. Without this, every refusal test above
// would pass trivially if resolve_sidecar_invocation always refused.
// ---------------------------------------------------------------------------------

#[cfg(unix)]
#[test]
fn a_well_behaved_stand_in_interpreter_resolves_to_a_validated_message() {
    let dir = scratch_dir("well-behaved");
    let interpreter =
        write_stand_in_interpreter(&dir, "python-stand-in.sh", "echo 'MESSAGE=heimdall: probe commit'");
    let package_root = valid_looking_package_root("well-behaved-pkg");
    let result = crate::resolve_sidecar_invocation(
        Some(interpreter.to_str().unwrap()),
        Some(package_root.to_str().unwrap()),
        "prompt",
    );
    assert!(
        result.is_ok(),
        "contrapositive of REQ-31: a stand-in interpreter satisfying every one of \
         REQ-31's conditions must resolve to Ok, not Err; got {:?}",
        result.err().map(|r| r.diagnostic)
    );
}

// ---------------------------------------------------------------------------------
// REQ-32: a named 300-second constant, no unbounded wait, no retry, no
// unsafe.
// ---------------------------------------------------------------------------------

#[test]
fn sidecar_timeout_is_named_and_fixed_at_300_seconds() {
    assert_eq!(
        crate::SIDECAR_TIMEOUT_SECS,
        300,
        "AC-35/REQ-32: the sidecar's wall-clock bound must be a named constant fixed at \
         300 seconds"
    );
}

fn crate_src_dir() -> std::path::PathBuf {
    std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("src")
}

fn cleaned_whole_crate_src() -> String {
    let mut all = String::new();
    let src_dir = crate_src_dir();
    let entries = std::fs::read_dir(&src_dir).unwrap_or_else(|e| {
        panic!("expected crates/cognition-client/src/ to exist once this step lands: {e}")
    });
    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) == Some("rs") {
            if let Ok(src) = std::fs::read_to_string(&path) {
                let cleaned: String = src
                    .lines()
                    .map(|line| match line.find("//") {
                        Some(idx) => format!("{}{}", &line[..idx], " ".repeat(line.len() - idx)),
                        None => line.to_string(),
                    })
                    .collect::<Vec<_>>()
                    .join("\n");
                all.push_str(&cleaned);
                all.push('\n');
            }
        }
    }
    all
}

/// Word-boundary-safe check for the bare `unsafe` keyword, mirroring the
/// `\bunsafe\b` regex used by
/// `ontology/tests/rust_cognition_client_harness.py`'s
/// `check_forbid_unsafe_and_no_bin`. A plain substring check on `"unsafe"`
/// would also match inside `unsafe_code`, which is mandated by REQ-8's own
/// `#![forbid(unsafe_code)]` attribute, so it can never pass alongside a
/// correct implementation; this scans for `"unsafe"` and rejects a match
/// only when it is not immediately flanked by an identifier character
/// (alphanumeric or `_`) on either side.
fn contains_unsafe_keyword(src: &str) -> bool {
    let bytes = src.as_bytes();
    let is_ident_byte = |b: u8| b.is_ascii_alphanumeric() || b == b'_';
    let mut start = 0;
    while let Some(rel) = src[start..].find("unsafe") {
        let idx = start + rel;
        let before_ok = idx == 0 || !is_ident_byte(bytes[idx - 1]);
        let after_idx = idx + "unsafe".len();
        let after_ok = after_idx >= bytes.len() || !is_ident_byte(bytes[after_idx]);
        if before_ok && after_ok {
            return true;
        }
        start = idx + "unsafe".len();
        if start >= src.len() {
            break;
        }
    }
    false
}

#[test]
fn no_retry_and_no_unsafe_appear_anywhere_in_the_crate() {
    let cleaned = cleaned_whole_crate_src();
    assert!(
        !contains_unsafe_keyword(&cleaned),
        "REQ-32/REQ-8: the `unsafe` keyword must appear nowhere in this crate's src/"
    );
    for retry_marker in ["retry", "for _attempt", "loop {"] {
        assert!(
            !cleaned.to_lowercase().contains(&retry_marker.to_lowercase()),
            "REQ-32: no retry of the sidecar invocation must exist on any path; found a \
             pattern resembling {retry_marker:?}"
        );
    }
}

// ---------------------------------------------------------------------------------
// REQ-33: the spawn's argv is a fixed shape with no shell on any path.
// ---------------------------------------------------------------------------------

#[test]
fn no_shell_is_ever_invoked_to_spawn_the_sidecar() {
    let cleaned = cleaned_whole_crate_src();
    for forbidden in ["Command::new(\"sh\")", "Command::new(\"/bin/sh\")", "sh -c", "\"-c\""] {
        assert!(
            !cleaned.contains(forbidden),
            "AC-36/REQ-33: crates/cognition-client/src/ must contain no {forbidden:?}: the \
             child is spawned with a fixed argv and no shell on any path"
        );
    }
}

// ---------------------------------------------------------------------------------
// REQ-34: the child's environment is cleared and populated only from a
// named, closed forwarding set.
// ---------------------------------------------------------------------------------

#[test]
fn env_clear_is_called_before_spawning_the_child() {
    let cleaned = cleaned_whole_crate_src();
    assert!(
        cleaned.contains("env_clear"),
        "AC-36/REQ-34: the invocation module must call env_clear() before spawning the \
         child, on execute.rs's own precedent, so no variable crosses to the child by a \
         wildcard, a prefix match or an inherited default"
    );
}
