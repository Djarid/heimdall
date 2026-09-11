// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! The sixth crate's own structural posture (REQ-7 to REQ-13 of
//! `.opencode/plans/build-order-step-seven-spec.md`; AC-9, AC-10, AC-11,
//! AC-13, AC-14, AC-15): the empty dependency tables, `#![forbid(unsafe_code)]`
//! with no `unsafe` keyword and no `[[bin]]` target, the module split, the
//! `std::env`/`std::net` absence outside the invocation module, and no
//! filesystem write entry point anywhere in the crate.
//!
//! THIS FILE WILL FAIL TO COMPILE until `crates/cognition-client/src/`
//! carries real content: this file's own scans read `src/` at runtime via
//! `std::fs`, so most of its assertions do not depend on any particular
//! `crate::`-scoped symbol existing, but the crate as a whole (via
//! `src/lib.rs`) must still compile as a library for `cargo test -p
//! cognition-client` to run any of these at all, and this file is wired in
//! from `lib.rs`, so a compile failure anywhere in the crate blocks every
//! test in this file too.
//!
//! **Compiled as an IN-CRATE unit test module**, wired into
//! `crates/cognition-client/src/lib.rs` via
//! `#[cfg(test)] #[path = "../unit_tests/structural_posture.rs"] mod structural_posture_tests;`
//! (already present in the scaffolding `lib.rs`).

use std::path::PathBuf;

fn crate_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

fn src_dir() -> PathBuf {
    crate_dir().join("src")
}

fn cleaned_whole_crate_src() -> String {
    let mut all = String::new();
    let src_dir = src_dir();
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

fn cleaned_files() -> Vec<(String, String)> {
    let src_dir = src_dir();
    let mut out = Vec::new();
    if let Ok(entries) = std::fs::read_dir(&src_dir) {
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
                    out.push((
                        path.file_name().unwrap().to_string_lossy().to_string(),
                        cleaned,
                    ));
                }
            }
        }
    }
    out
}

// ---------------------------------------------------------------------------------
// AC-9 (REQ-7): both dependency tables are empty.
// ---------------------------------------------------------------------------------

/// Deliberately not a TOML parser: this crate's own `[dev-dependencies]`
/// stays empty (REQ-7), which forbids this test file from depending on an
/// external `toml` crate to check its neighbour's manifest correctly. A
/// plain line scan, on this repository's own established
/// mechanical-proxy-not-a-full-parser discipline (see the Python
/// harnesses' own header notes for the same convention), is sufficient
/// here: for each named table header, every non-blank, non-comment line
/// until the next `[` header (or end of file) must be empty of content.
fn table_is_empty(manifest: &str, table_header: &str) -> bool {
    let mut found = false;
    for line in manifest.lines() {
        let trimmed = line.trim();
        if trimmed == table_header {
            found = true;
            continue;
        }
        if found {
            if trimmed.starts_with('[') {
                break;
            }
            if !trimmed.is_empty() && !trimmed.starts_with('#') {
                return false;
            }
        }
    }
    // A table header that never appears at all is vacuously empty (Cargo
    // treats an absent table the same as an empty one).
    true
}

#[test]
fn dependency_tables_are_both_empty() {
    let manifest_path = crate_dir().join("Cargo.toml");
    let manifest = std::fs::read_to_string(&manifest_path)
        .expect("expected crates/cognition-client/Cargo.toml to exist");
    for table_header in ["[dependencies]", "[dev-dependencies]"] {
        assert!(
            table_is_empty(&manifest, table_header),
            "AC-9/REQ-7: {table_header} must be empty in crates/cognition-client/Cargo.toml"
        );
    }
}

// ---------------------------------------------------------------------------------
// AC-10 (REQ-8): forbid(unsafe_code) at file scope, no unsafe keyword
// anywhere, no [[bin]] target.
// ---------------------------------------------------------------------------------

#[test]
fn crate_root_begins_with_forbid_unsafe_code() {
    let lib_rs = std::fs::read_to_string(src_dir().join("lib.rs"))
        .expect("expected crates/cognition-client/src/lib.rs to exist");
    assert!(
        lib_rs.trim_start().starts_with("#![forbid(unsafe_code)]"),
        "AC-10/REQ-8: src/lib.rs must begin with #![forbid(unsafe_code)] at file scope"
    );
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
fn unsafe_keyword_appears_nowhere_in_the_crate() {
    let cleaned = cleaned_whole_crate_src();
    assert!(
        !contains_unsafe_keyword(&cleaned),
        "AC-10/REQ-8: the `unsafe` keyword must appear nowhere in this crate's src/"
    );
}

#[test]
fn no_bin_target_is_declared() {
    let manifest_path = crate_dir().join("Cargo.toml");
    let manifest = std::fs::read_to_string(&manifest_path)
        .expect("expected crates/cognition-client/Cargo.toml to exist");
    assert!(
        !manifest.contains("[[bin]]"),
        "AC-10/REQ-8: crates/cognition-client/Cargo.toml must declare no [[bin]] target; \
         the workspace's one binary stays crates/process-engine/src/main.rs"
    );
}

// ---------------------------------------------------------------------------------
// AC-11 (REQ-9): the module split -- a types module with no logic, a
// validation module holding the one validator, an invocation module
// holding every std::process reference, and the crate root holding the
// forbid attribute and the public surface.
// ---------------------------------------------------------------------------------

#[test]
fn crate_carries_more_than_one_source_module_beyond_the_crate_root() {
    let files = cleaned_files();
    let non_root_modules: Vec<&str> = files
        .iter()
        .map(|(name, _)| name.as_str())
        .filter(|name| *name != "lib.rs")
        .collect();
    assert!(
        non_root_modules.len() >= 2,
        "AC-11/REQ-9: expected at least a types module, a validation module and an \
         invocation module beyond src/lib.rs itself (REQ-9's four-way split); found only \
         {non_root_modules:?}"
    );
}

// ---------------------------------------------------------------------------------
// AC-13 (REQ-11, REQ-12): std::env appears only in the invocation module;
// std::net appears nowhere.
// ---------------------------------------------------------------------------------

#[test]
fn std_env_appears_in_exactly_one_module() {
    let files = cleaned_files();
    let modules_naming_std_env: Vec<&str> = files
        .iter()
        .filter(|(_, src)| src.contains("std::env"))
        .map(|(name, _)| name.as_str())
        .collect();
    assert_eq!(
        modules_naming_std_env.len(),
        1,
        "AC-13/REQ-11: std::env must appear in exactly one module (the invocation \
         module) across crates/cognition-client/src/; found it in {modules_naming_std_env:?}"
    );
}

#[test]
fn std_net_appears_nowhere_in_the_crate() {
    let cleaned = cleaned_whole_crate_src();
    assert!(
        !cleaned.contains("std::net"),
        "AC-14/REQ-12: std::net must appear nowhere in crates/cognition-client/src/: \
         the sidecar is a child process, not a socket"
    );
}

// ---------------------------------------------------------------------------------
// AC-15 (REQ-13): no filesystem write entry point anywhere in the crate.
// ---------------------------------------------------------------------------------

#[test]
fn no_filesystem_write_entry_point_exists_anywhere_in_the_crate() {
    let cleaned = cleaned_whole_crate_src();
    for forbidden in [
        "File::create(",
        "OpenOptions::new(",
        "fs::write(",
        "fs::create_dir(",
        "fs::create_dir_all(",
        "tempfile::",
    ] {
        assert!(
            !cleaned.contains(forbidden),
            "AC-15/REQ-13: crates/cognition-client/src/ must contain no {forbidden:?}: \
             this crate performs no filesystem write on any path"
        );
    }
}

// ---------------------------------------------------------------------------------
// std::process confined to one named module (REQ-9, REQ-12, REQ-53): the
// only module besides the crate root permitted to touch std::process.
// ---------------------------------------------------------------------------------

#[test]
fn std_process_appears_in_at_most_one_module_under_src() {
    let files = cleaned_files();
    let modules_naming_std_process: Vec<&str> = files
        .iter()
        .filter(|(name, src)| *name != "lib.rs" && src.contains("std::process"))
        .map(|(name, _)| name.as_str())
        .collect();
    assert!(
        modules_naming_std_process.len() <= 1,
        "REQ-9/REQ-12/REQ-53: std::process must be confined to at most one module \
         under src/ (the invocation module); found it in {modules_naming_std_process:?}"
    );
}
