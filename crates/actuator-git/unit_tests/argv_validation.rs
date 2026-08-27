//! Argument-vector safety: the operation set, value validation and no-shell
//! guarantee (REQ-8 to REQ-13). Covers AC-7 to AC-14, AC-31, AC-55 of
//! `.opencode/plans/git-actuator-step-four.md`.
//!
//! THIS FILE WILL FAIL TO COMPILE until `crates/actuator-git` exists at all: no
//! `Cargo.toml`, no workspace member, no `src/`, and it is not even wired into
//! any `lib.rs` yet (that wiring is file 4 of section 10, an implementation
//! change, not a test-writing one). That is expected and correct at this
//! stage, for the same reason `crates/hierarchy-vor/unit_tests/loader_failclosed.rs`'s
//! own header states for its own precedent, and `crates/himinbjorg/unit_tests/
//! six_checks.rs`'s header states for issue #37.
//!
//! **Compiled as an IN-CRATE unit test module**, once wired via
//! `#[cfg(test)] #[path = "../unit_tests/argv_validation.rs"] mod argv_validation;`
//! in `crates/actuator-git/src/lib.rs` (a later, implementation-side change).
//! This lets this file reach `pub(crate)` internals if ever needed, though the
//! tests below deliberately exercise the public `execute` entry point alone
//! wherever that is sufficient, following the crate's own Interface
//! Segregation stance (section 9.1 of the spec: "actuator-git exposes one
//! function and three value types").
//!
//! **Assumed public surface** (this file's own necessary choices where the
//! spec's section 5.1 leaves the shape indicative rather than fixed; flagged
//! explicitly, not hidden, following `six_checks.rs`'s own precedent for its
//! blast-radius assumption):
//!
//!   - `crate::{GitOperation, ActuationOutcome, ActuationRefusal, execute}`.
//!   - `GitOperation::Commit { message: String }` and
//!     `GitOperation::Push { remote: String, ref_name: String }` -- the two,
//!     and only two, variants (REQ-8).
//!   - `ActuationOutcome::Committed` and `ActuationOutcome::Pushed` (REQ-25).
//!   - `ActuationRefusal` is a closed enum whose variants this file matches by
//!     name: `InvalidArgument { diagnostic: String }`,
//!     `TargetNotPermitted { diagnostic: String }`,
//!     `ProtectedRef { diagnostic: String }` (defence in depth, REQ-16),
//!     `RepositoryResolution { diagnostic: String }`,
//!     `SpawnFailed { diagnostic: String }`, `Timeout`,
//!     `ExitStatus { diagnostic: String }`, `PartialEffect { diagnostic: String }`.
//!     If the implementation's variant names differ, the CONTRACT under test
//!     (which validation stage produced the refusal) does not change; only
//!     the `matches!` arms below would need adjusting.
//!   - `execute(operation: &GitOperation) -> Result<ActuationOutcome, ActuationRefusal>`
//!     (REQ-8, section 5.1).
//!   - **Assumed check ORDER inside `execute`**, stated explicitly because it
//!     is load bearing for which tests below need a real working repository
//!     and which do not: value validation (REQ-11) runs strictly before
//!     target-allowlist membership (REQ-14, push only), which runs strictly
//!     before working-repository resolution (REQ-18/19), which runs strictly
//!     before the process is ever spawned (REQ-21/22/23). This lets every
//!     test in THIS file assert a refusal that must have happened at the
//!     validation stage, without needing any working repository to exist at
//!     all: if validation did not run first, a validation-refusing input
//!     would instead surface as `RepositoryResolution` (no env var configured
//!     in this unit-test binary) or a spawn/exit-status refusal, never
//!     `InvalidArgument`, so asserting the EXACT refusal VARIANT is itself the
//!     proof that no process was spawned for these inputs (REQ-11's own
//!     "no process is spawned" clause), without any process-inspection
//!     instrumentation.
//!   - **The named length bound (REQ-11).** Not exposed as a public constant;
//!     this file uses a value far longer than any plausible bound (1,000,000
//!     bytes) for the over-length case (AC-12) so the assertion holds
//!     regardless of the bound's exact value.
//!
//! **Why AC-14's and AC-55's REST is NOT here.** Both criteria have a runtime
//! half that requires a commit to actually execute successfully and be
//! inspected afterwards (byte-for-byte literal recording; no scratch file
//! left behind). Executing successfully requires the working-repository
//! environment variable to be set to a real, valid repository -- and setting
//! an environment variable requires `std::env::set_var`, which this
//! workspace's pinned toolchain makes an `unsafe fn`
//! (`crates/hierarchy-vor/tests/public_surface.rs`'s own header confirms this
//! directly against `cargo 1.98.0`). Because `crates/actuator-git/src/lib.rs`
//! carries `#![forbid(unsafe_code)]` (REQ-3) and THIS file is compiled INTO
//! that same crate via `lib.rs`'s `#[cfg(test)] #[path]` mechanism, it cannot
//! use an `unsafe` block at all -- exactly the same constraint
//! `hierarchy-vor/tests/public_surface.rs`'s header names for its own ONE
//! environment-mutating test, which is why THAT test lives in an external
//! `tests/` crate rather than in `unit_tests/`. Accordingly:
//!   - This file tests AC-14's and AC-55's STATIC half only (the message's
//!     route from caller to argument vector, traced by reading `argv.rs`'s
//!     own source: no larger string, no template, no message-from-file
//!     argument form).
//!   - The RUNTIME half of both (the commit actually executing and being
//!     inspected) is `crates/actuator-git/tests/public_surface.rs`'s job,
//!     which is compiled as an external crate and is free to mutate the
//!     process environment the same way `hierarchy-vor`'s own external test
//!     does.
//!
//! **AC-8, AC-9 and AC-31 are source scans (section 12 of the spec lists
//! AC-9, AC-31, AC-4 and AC-8 as MANUAL checks, "record the grep commands and
//! their empty results").** This file automates the SAME scans anyway, as a
//! standing regression guard, using nothing but `std::fs` (REQ-2 forbids a
//! `regex` dependency, and REQ-6 forbids a dev-dependency for one), so a
//! future edit that reintroduces a forbidden subcommand name or a shell
//! invocation fails a normal `cargo test` run, not only a one-off manual grep
//! that nobody re-runs. This is a mechanical, comment-stripped substring scan
//! -- a proxy, not a full parser, exactly the discipline
//! `ontology/tests/rust_gateway_harness.py`'s own text scans use and document
//! for the same reason.

use std::path::{Path, PathBuf};

// ---------------------------------------------------------------------------------
// Shared scanning helpers (std-only, no dependency of any kind, REQ-2/REQ-6).
// ---------------------------------------------------------------------------------

fn crate_src_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("src")
}

/// Truncates every line at its first `//`, replacing the removed tail with
/// spaces so byte offsets are preserved. A mechanical proxy only (no
/// string-literal awareness), following
/// `ontology/tests/rust_gateway_harness.py::_strip_line_comments`'s own
/// reasoning, re-implemented here in Rust because this crate may add no
/// dependency of any kind.
fn strip_line_comments(src: &str) -> String {
    src.lines()
        .map(|line| match line.find("//") {
            Some(idx) => {
                let mut s = line[..idx].to_string();
                s.push_str(&" ".repeat(line.len() - idx));
                s
            }
            None => line.to_string(),
        })
        .collect::<Vec<_>>()
        .join("\n")
}

fn load_all_rs_under(dir: &Path) -> Vec<(PathBuf, String)> {
    let mut out = Vec::new();
    let Ok(read_dir) = std::fs::read_dir(dir) else {
        return out;
    };
    for entry in read_dir.flatten() {
        let path = entry.path();
        if path.is_dir() {
            out.extend(load_all_rs_under(&path));
        } else if path.extension().is_some_and(|e| e == "rs") {
            if let Ok(contents) = std::fs::read_to_string(&path) {
                out.push((path, contents));
            }
        }
    }
    out
}

// ---------------------------------------------------------------------------------
// AC-7 (REQ-8): exactly two operations, neither naming anything other than
// commit or push.
// ---------------------------------------------------------------------------------

#[test]
fn ac7_exactly_two_operations_commit_and_push() {
    // Exhaustive match: if a third variant is ever added, this match stops
    // compiling (no wildcard arm), which is the point -- a reviewer must
    // revisit this test, not have it silently keep passing.
    fn describe(op: &crate::GitOperation) -> &'static str {
        match op {
            crate::GitOperation::Commit { .. } => "commit",
            crate::GitOperation::Push { .. } => "push",
        }
    }

    let commit = crate::GitOperation::Commit {
        message: "a valid fixture commit message".to_string(),
    };
    let push = crate::GitOperation::Push {
        remote: "origin".to_string(),
        ref_name: "fixture-integration-branch".to_string(),
    };
    assert_eq!(describe(&commit), "commit");
    assert_eq!(describe(&push), "push");
}

// ---------------------------------------------------------------------------------
// AC-8 (REQ-8): no other git subcommand name reaches an argument vector.
// ---------------------------------------------------------------------------------

#[test]
fn ac8_no_forbidden_git_subcommand_name_reaches_an_argument_vector() {
    const FORBIDDEN_SUBCOMMANDS: &[&str] = &[
        "\"add\"",
        "\"checkout\"",
        "\"fetch\"",
        "\"rev-parse\"",
        "\"config\"",
        "\"remote\"",
        "\"status\"",
        "\"reset\"",
    ];
    let files = load_all_rs_under(&crate_src_dir());
    assert!(
        !files.is_empty(),
        "expected at least one .rs file under crates/actuator-git/src/ once the crate exists"
    );
    let mut violations = Vec::new();
    for (path, raw) in &files {
        let cleaned = strip_line_comments(raw);
        for needle in FORBIDDEN_SUBCOMMANDS {
            if cleaned.contains(needle) {
                violations.push(format!("{}: contains {needle}", path.display()));
            }
        }
    }
    assert!(
        violations.is_empty(),
        "AC-8: a forbidden git subcommand name reached the source in argument-vector \
         position (REQ-8): {violations:?}"
    );
}

// ---------------------------------------------------------------------------------
// AC-9 (REQ-10): no shell is invoked on any path.
// ---------------------------------------------------------------------------------

#[test]
fn ac9_no_shell_invocation_on_any_path() {
    const SHELL_MARKERS: &[&str] = &["\"sh\"", "\"bash\"", "\"cmd\"", "\"-c\""];
    let files = load_all_rs_under(&crate_src_dir());
    assert!(
        !files.is_empty(),
        "expected at least one .rs file under crates/actuator-git/src/ once the crate exists"
    );
    let mut violations = Vec::new();
    for (path, raw) in &files {
        let cleaned = strip_line_comments(raw);
        for marker in SHELL_MARKERS {
            if cleaned.contains(marker) {
                violations.push(format!("{}: contains {marker}", path.display()));
            }
        }
        if cleaned.contains(".split_whitespace()") && cleaned.contains("message") {
            violations.push(format!(
                "{}: appears to split a caller-supplied value into arguments \
                 (string-splitting a value is exactly the shape REQ-10 forbids)",
                path.display()
            ));
        }
    }
    assert!(
        violations.is_empty(),
        "AC-9: a shell-invocation shape was found (REQ-10): {violations:?}"
    );
}

// ---------------------------------------------------------------------------------
// AC-10 (REQ-11, REQ-12): a commit message beginning with a hyphen refuses
// with the invalid-argument variant, and (by the assumed check order) no
// process could have been spawned.
// ---------------------------------------------------------------------------------

#[test]
fn ac10_commit_message_leading_hyphen_refused_invalid_argument() {
    let op = crate::GitOperation::Commit {
        message: "--upload-pack=touch /tmp/pwned".to_string(),
    };
    let outcome = crate::execute(&op);
    assert!(
        matches!(
            outcome,
            Err(crate::ActuationRefusal::InvalidArgument { .. })
        ),
        "AC-10: a commit message beginning with a hyphen must refuse with \
         InvalidArgument, proving (by the assumed check order) that no process was \
         spawned; got {outcome:?}"
    );
}

#[test]
fn ac10_push_ref_beginning_with_hyphen_refused_invalid_argument() {
    let op = crate::GitOperation::Push {
        remote: "origin".to_string(),
        ref_name: "--upload-pack=touch /tmp/pwned".to_string(),
    };
    let outcome = crate::execute(&op);
    assert!(
        matches!(
            outcome,
            Err(crate::ActuationRefusal::InvalidArgument { .. })
        ),
        "AC-10/REQ-12: a push ref beginning with a hyphen must refuse with \
         InvalidArgument, never be escaped; got {outcome:?}"
    );
}

// ---------------------------------------------------------------------------------
// AC-11 (REQ-11): a NUL byte, a newline, and a carriage return, each in turn,
// refuse.
// ---------------------------------------------------------------------------------

#[test]
fn ac11_commit_message_with_nul_byte_refused() {
    let op = crate::GitOperation::Commit {
        message: "fixture message with a\u{0}NUL byte".to_string(),
    };
    assert!(
        matches!(
            crate::execute(&op),
            Err(crate::ActuationRefusal::InvalidArgument { .. })
        ),
        "AC-11: a commit message containing a NUL byte must refuse"
    );
}

#[test]
fn ac11_commit_message_with_newline_refused() {
    let op = crate::GitOperation::Commit {
        message: "fixture message\nwith an embedded newline".to_string(),
    };
    assert!(
        matches!(
            crate::execute(&op),
            Err(crate::ActuationRefusal::InvalidArgument { .. })
        ),
        "AC-11: a commit message containing a newline must refuse"
    );
}

#[test]
fn ac11_commit_message_with_carriage_return_refused() {
    let op = crate::GitOperation::Commit {
        message: "fixture message\rwith an embedded carriage return".to_string(),
    };
    assert!(
        matches!(
            crate::execute(&op),
            Err(crate::ActuationRefusal::InvalidArgument { .. })
        ),
        "AC-11: a commit message containing a carriage return must refuse"
    );
}

// ---------------------------------------------------------------------------------
// AC-12 (REQ-11): an empty message, and a message exceeding the named length
// bound, each refuse.
// ---------------------------------------------------------------------------------

#[test]
fn ac12_empty_commit_message_refused() {
    let op = crate::GitOperation::Commit {
        message: String::new(),
    };
    assert!(
        matches!(
            crate::execute(&op),
            Err(crate::ActuationRefusal::InvalidArgument { .. })
        ),
        "AC-12: an empty commit message must refuse"
    );
}

#[test]
fn ac12_overlong_commit_message_refused() {
    // Far longer than any plausible named bound, so this holds regardless of
    // the exact value chosen by the implementation (see this file's header).
    let op = crate::GitOperation::Commit {
        message: "a".repeat(1_000_000),
    };
    assert!(
        matches!(
            crate::execute(&op),
            Err(crate::ActuationRefusal::InvalidArgument { .. })
        ),
        "AC-12: a commit message exceeding the named length bound must refuse"
    );
}

// ---------------------------------------------------------------------------------
// AC-13 (REQ-11, REQ-10): real shell-injection payload shapes, drawn from
// section 13's corpus sources, refuse at validation with no interpretation.
// ---------------------------------------------------------------------------------

#[test]
fn ac13_ref_name_with_home_assistant_style_payload_refused() {
    // github.blog's "Securing our home labs" corpus source: a git-legal
    // branch-name character set is still sufficient for command execution.
    let op = crate::GitOperation::Push {
        remote: "origin".to_string(),
        ref_name: "foo\";echo${IFS}\"hello\";#".to_string(),
    };
    assert!(
        matches!(
            crate::execute(&op),
            Err(crate::ActuationRefusal::InvalidArgument { .. })
        ),
        "AC-13: the Home Assistant-style payload must refuse at validation, never reach \
         an argument vector or a shell"
    );
}

#[test]
fn ac13_ref_name_with_tj_actions_style_payload_refused() {
    // adnanthekhan.com's tj-actions/branch-names CVE-2023-49291 payload shape.
    let op = crate::GitOperation::Push {
        remote: "origin".to_string(),
        ref_name: "Test\")${IFS}&&${IFS}{curl,-sSfL,example}".to_string(),
    };
    assert!(
        matches!(
            crate::execute(&op),
            Err(crate::ActuationRefusal::InvalidArgument { .. })
        ),
        "AC-13: the tj-actions-style payload must refuse at validation, never reach an \
         argument vector or a shell"
    );
}

#[test]
fn ac13_remote_name_with_injection_payload_refused() {
    let op = crate::GitOperation::Push {
        remote: "\";echo${IFS}hello;#".to_string(),
        ref_name: "fixture-integration-branch".to_string(),
    };
    assert!(
        matches!(
            crate::execute(&op),
            Err(crate::ActuationRefusal::InvalidArgument { .. })
        ),
        "AC-13: an injection-shaped remote name must refuse at validation too, not only \
         a ref name"
    );
}

// ---------------------------------------------------------------------------------
// AC-14 (static half only, REQ-9, REQ-10; runtime half in tests/public_surface.rs):
// the message's route to the argument vector is traced statically.
// ---------------------------------------------------------------------------------

#[test]
fn ac14_static_no_string_concatenation_or_templating_of_the_message() {
    let files = load_all_rs_under(&crate_src_dir());
    assert!(!files.is_empty());
    let mut violations = Vec::new();
    for (path, raw) in &files {
        let cleaned = strip_line_comments(raw);
        // A commit message templated into a larger string (format! building
        // an argument string, rather than a fixed argv position) would show
        // up as the message identifier appearing inside a `format!(...)`
        // call whose literal also contains other argv-shaped text. This is a
        // heuristic, not a parser (see this file's header): it looks for the
        // suspicious co-occurrence and nothing more subtle.
        if cleaned.contains("format!(") && cleaned.contains("-m {") {
            violations.push(format!(
                "{}: a commit message appears templated into a larger '-m {{...}}' \
                 string rather than occupying a single fixed value position",
                path.display()
            ));
        }
    }
    assert!(
        violations.is_empty(),
        "AC-14 (static half): {violations:?}"
    );
}

// ---------------------------------------------------------------------------------
// AC-31 (REQ-24): no branch, comparison or match over captured process output
// outside a length-bounded diagnostic assignment.
// ---------------------------------------------------------------------------------

#[test]
fn ac31_no_control_flow_derived_from_captured_process_output() {
    let files = load_all_rs_under(&crate_src_dir());
    assert!(!files.is_empty());
    let mut violations = Vec::new();
    for (path, raw) in &files {
        let cleaned = strip_line_comments(raw);
        for (lineno, line) in cleaned.lines().enumerate() {
            let touches_output = line.contains("stdout") || line.contains("stderr");
            if !touches_output {
                continue;
            }
            let looks_like_decision = (line.contains("if ") || line.contains("match "))
                && (line.contains(".contains(")
                    || line.contains(".starts_with(")
                    || line.contains(".ends_with("));
            if looks_like_decision {
                violations.push(format!(
                    "{}:{}: appears to branch on captured process output content, \
                     outside a bounded diagnostic-string assignment (REQ-24)",
                    path.display(),
                    lineno + 1
                ));
            }
        }
    }
    assert!(
        violations.is_empty(),
        "AC-31: {violations:?}"
    );
}

// ---------------------------------------------------------------------------------
// AC-55 (static half only, REQ-13, REQ-9; runtime half in tests/public_surface.rs):
// the message occupies exactly one value position; no message-from-file form.
// ---------------------------------------------------------------------------------

#[test]
fn ac55_static_message_never_written_to_a_file_the_actuator_creates() {
    let files = load_all_rs_under(&crate_src_dir());
    assert!(!files.is_empty());
    let mut violations = Vec::new();
    for (path, raw) in &files {
        let cleaned = strip_line_comments(raw);
        for needle in ["NamedTempFile", "tempfile::", "\"-F\"", "\"--file\""] {
            if cleaned.contains(needle) {
                violations.push(format!(
                    "{}: contains {needle:?}, suggesting a message-from-file argument \
                     form (REQ-13 forbids this: the message is never written to a file \
                     the actuator creates)",
                    path.display()
                ));
            }
        }
    }
    assert!(
        violations.is_empty(),
        "AC-55 (static half): {violations:?}"
    );
}
