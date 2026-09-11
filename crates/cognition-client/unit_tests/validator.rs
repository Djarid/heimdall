// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! The single positive-match validator (REQ-23, REQ-24, REQ-25, REQ-26 of
//! `.opencode/plans/build-order-step-seven-spec.md`; AC-25 to AC-29): the
//! only place in this crate a value received from the child is checked, on
//! `crates/actuator-git/src/argv.rs`'s own single-validator precedent.
//!
//! THIS FILE WILL FAIL TO COMPILE until `crates/cognition-client/src/`
//! carries a validation module exposing the items assumed below. That is
//! the expected RED state for this build-order step: the crate does not
//! exist at real fidelity yet (only `src/lib.rs`'s own scaffolding comment
//! names the module split this file assumes).
//!
//! **Compiled as an IN-CRATE unit test module**, wired into
//! `crates/cognition-client/src/lib.rs` via
//! `#[cfg(test)] #[path = "../unit_tests/validator.rs"] mod validator_tests;`
//! (already present in the scaffolding `lib.rs`), so this file can reach
//! `crate::`-scoped `pub(crate)` items rather than only the crate's public
//! surface.
//!
//! **Signatures assumed here** (this file's own necessary choices, flagged
//! explicitly rather than hidden, on this repository's own established
//! convention for a spec that leaves an exact module boundary indicative
//! rather than fixed, REQ-9's own "an implementer reaching the same
//! properties with a different boundary satisfies this spec" clause):
//!
//!   - `crate::validate_received_message(raw: &str) ->
//!     Result<crate::CognitionMessage, crate::SidecarRefusal>`: the one
//!     positive-match validator (REQ-23), `pub(crate)` so this in-crate
//!     module can reach it directly without going through the one public
//!     function's own spawn-and-wait machinery. Operates on an already
//!     line-parsed value (the fixed line-oriented shape's own parsing,
//!     REQ-22, is a separate concern this file does not test; see
//!     `unit_tests/refusal_set.rs` for that).
//!   - `crate::CognitionMessage`: the validated-message value type (REQ-10),
//!     with a public reader `as_str(&self) -> &str` and no public
//!     constructor and no public `From` conversion anywhere (REQ-10; the
//!     compile-fail confirmation of that half lives in
//!     `tests/public_surface.rs`, never here).
//!   - `crate::SidecarRefusal`: the one refusal type (REQ-10), carrying a
//!     bounded diagnostic naming which check failed, `pub diagnostic:
//!     String`, built only from this crate's own fixed strings (REQ-25).
//!   - `crate::MAX_RECEIVED_VALUE_LEN: usize`: this crate's own named
//!     maximum-length constant (REQ-24), never read from
//!     `actuator_git::argv::MAX_VALUE_LEN` (this crate cannot depend on
//!     `actuator-git` at all, REQ-7), and not asserted anywhere in this
//!     file to agree with that constant's value (REQ-24's own
//!     never-a-derivation rule; `context::TARGET_SCOPE`'s PE-4 precedent).

fn valid_message() -> &'static str {
    "heimdall: automated commit via the model sidecar"
}

// ---------------------------------------------------------------------------------
// AC-26: eight distinct refusal shapes, each refused with a diagnostic
// naming the failing check; one accepting case, returned unchanged.
// ---------------------------------------------------------------------------------

#[test]
fn empty_value_is_refused() {
    let result = crate::validate_received_message("");
    assert!(
        result.is_err(),
        "AC-26/REQ-24: an empty received value must be refused"
    );
}

#[test]
fn whitespace_only_value_is_refused() {
    let result = crate::validate_received_message("   \t  ");
    assert!(
        result.is_err(),
        "AC-26/REQ-24: a whitespace-only received value must be refused, not merely a \
         non-empty-length check"
    );
}

#[test]
fn leading_hyphen_value_is_refused() {
    let result = crate::validate_received_message("-rm-rf-looking-message");
    assert!(
        result.is_err(),
        "AC-26/REQ-24: a value beginning with a hyphen must be refused"
    );
}

#[test]
fn nul_byte_value_is_refused() {
    let with_nul = format!("hello{}world", '\u{0}');
    let result = crate::validate_received_message(&with_nul);
    assert!(
        result.is_err(),
        "AC-26/REQ-24: a value containing a NUL byte must be refused"
    );
}

#[test]
fn newline_value_is_refused() {
    let result = crate::validate_received_message("hello\nworld");
    assert!(
        result.is_err(),
        "AC-26/REQ-24: a value containing a newline must be refused (the fixed \
         line-oriented shape's own trailing-line-ending handling is a separate, \
         upstream concern from this per-character validator; see refusal_set.rs)"
    );
}

#[test]
fn carriage_return_value_is_refused() {
    let result = crate::validate_received_message("hello\rworld");
    assert!(
        result.is_err(),
        "AC-26/REQ-24: a value containing a carriage return must be refused"
    );
}

#[test]
fn character_outside_ascii_graphic_or_space_is_refused() {
    // A tab is not ascii_graphic and is not the literal space character, so
    // it must be refused under the `is_ascii_graphic() || c == ' '` policy
    // (REQ-24), independently of the whitespace-only case above.
    let result = crate::validate_received_message("hello\tworld");
    assert!(
        result.is_err(),
        "AC-26/REQ-24: a value containing a character outside \
         is_ascii_graphic()||' ' must be refused"
    );
}

#[test]
fn character_outside_ascii_range_entirely_is_refused() {
    let result = crate::validate_received_message("héllo world");
    assert!(
        result.is_err(),
        "AC-26/REQ-24: a value containing a non-ASCII character must be refused under \
         the is_ascii_graphic()||' ' allowlist"
    );
}

#[test]
fn over_length_value_is_refused() {
    let too_long = "a".repeat(crate::MAX_RECEIVED_VALUE_LEN + 1);
    let result = crate::validate_received_message(&too_long);
    assert!(
        result.is_err(),
        "AC-26/REQ-24: a value exceeding MAX_RECEIVED_VALUE_LEN must be refused"
    );
}

#[test]
fn value_at_exactly_the_maximum_length_is_accepted() {
    let exactly_max = "a".repeat(crate::MAX_RECEIVED_VALUE_LEN);
    let result = crate::validate_received_message(&exactly_max);
    assert!(
        result.is_ok(),
        "AC-26/REQ-24: a value at exactly MAX_RECEIVED_VALUE_LEN bytes, satisfying every \
         other check, must be accepted -- the bound is inclusive, not exclusive"
    );
}

#[test]
fn a_value_satisfying_every_check_is_returned_unchanged_byte_for_byte() {
    let input = valid_message();
    let result = crate::validate_received_message(input);
    match result {
        Ok(message) => assert_eq!(
            message.as_str(),
            input,
            "AC-26: a value satisfying every check must be returned unchanged, byte for \
             byte, inside the validated type -- never sanitised, never truncated"
        ),
        Err(refusal) => panic!(
            "AC-26: a well-formed value satisfying every one of REQ-24's checks must be \
             accepted; got a refusal: {:?}",
            refusal.diagnostic
        ),
    }
}

// ---------------------------------------------------------------------------------
// AC-28 (REQ-25): every refusal's diagnostic is built only from this crate's
// own fixed strings; it never carries a portion of the failing value's own
// content.
// ---------------------------------------------------------------------------------

#[test]
fn refusal_diagnostics_never_carry_a_portion_of_the_failing_values_own_content() {
    let marker = "THIS-EXACT-MARKER-MUST-NEVER-APPEAR-IN-ANY-DIAGNOSTIC";
    let scenarios: Vec<String> = vec![
        String::new(),
        format!("-{marker}"),
        format!("{marker}\n"),
        format!("{marker}\r"),
        format!("{marker}{}", '\u{0}'),
        format!("{marker}\t"),
        "a".repeat(crate::MAX_RECEIVED_VALUE_LEN) + marker,
    ];
    for scenario in scenarios {
        if let Err(refusal) = crate::validate_received_message(&scenario) {
            assert!(
                !refusal.diagnostic.contains(marker),
                "AC-28/REQ-25: a refusal diagnostic must never contain a portion of the \
                 failing value's own content; got {:?} for input starting {:?}",
                refusal.diagnostic,
                &scenario.chars().take(20).collect::<String>(),
            );
        }
    }
}

// ---------------------------------------------------------------------------------
// AC-25, structural half: every check the validator makes is a
// permitted-shape check, never a forbidden-shape check enumerating a
// blacklist of characters. Checked by reading the validation module's own
// source, on the sibling crates' own established source-scan discipline
// (never a full parser).
// ---------------------------------------------------------------------------------

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

#[test]
fn no_sanitising_truncating_escaping_or_quote_wrapping_function_exists_anywhere_in_the_crate() {
    let cleaned = cleaned_whole_crate_src();
    for forbidden in [
        ".replace(",
        ".trim_matches(",
        ".truncate(",
        "chars().take(",
        ".escape_default(",
        "format!(\"'{",
        "format!(\"\\\"{",
    ] {
        assert!(
            !cleaned.contains(forbidden),
            "AC-25/AC-29/REQ-26: crates/cognition-client/src/ must contain no {forbidden:?}: \
             a received value is either returned unchanged inside the validated type or the \
             call refuses -- there is no sanitising, truncating, escaping or quote-wrapping \
             path anywhere in this crate"
        );
    }
}
