//! The no-sanitising-path property (REQ-26 of
//! `.opencode/plans/build-order-step-seven-spec.md`; AC-29): no function in
//! this crate removes, replaces, strips, filters or maps characters of a
//! received value; none truncates it to a permitted length; and none wraps,
//! escapes or quote-wraps it. Exercised both structurally (a source scan,
//! duplicated here deliberately from `unit_tests/validator.rs`'s own check
//! of the same property, because REQ-26 is independently named as its own
//! requirement and this repository's own convention is that two detectors
//! proving overlapping but distinctly-numbered properties are two
//! detectors, not one shared helper, `rust_target_loop_harness.py`'s own
//! precedent for restating rather than importing) and behaviourally (a
//! value that WOULD be sanitisable under a lenient policy -- for example
//! one a truncating implementation might shorten rather than refuse -- is
//! refused whole, never partially accepted).
//!
//! THIS FILE WILL FAIL TO COMPILE until `crates/cognition-client/src/`
//! exposes `crate::validate_received_message` and `crate::MAX_RECEIVED_VALUE_LEN`
//! (see `unit_tests/validator.rs`'s own header for the full assumed
//! signature list, which this file inherits without repeating).

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

// ---------------------------------------------------------------------------------
// Structural half: no sanitising-shaped function exists anywhere.
// ---------------------------------------------------------------------------------

#[test]
fn no_function_removing_replacing_stripping_filtering_or_mapping_characters_exists() {
    let cleaned = cleaned_whole_crate_src();
    for forbidden in [
        ".retain(",
        ".filter_map(",
        ".chars().filter(",
        ".replacen(",
        "strip_prefix(",
        "strip_suffix(",
    ] {
        assert!(
            !cleaned.contains(forbidden),
            "AC-29/REQ-26: crates/cognition-client/src/ must contain no {forbidden:?}: no \
             function may remove, replace, strip, filter or map characters of a value \
             received from the child"
        );
    }
}

#[test]
fn no_function_truncating_a_value_to_a_permitted_length_exists() {
    let cleaned = cleaned_whole_crate_src();
    for forbidden in [".truncate(", "[..MAX_RECEIVED_VALUE_LEN]", "chars().take("] {
        assert!(
            !cleaned.contains(forbidden),
            "AC-29/REQ-26: crates/cognition-client/src/ must contain no {forbidden:?}: an \
             over-length value must be refused, never shortened to fit"
        );
    }
}

// ---------------------------------------------------------------------------------
// Behavioural half: a value that a lenient, truncating or stripping
// implementation might silently repair is instead refused whole. Each
// scenario below constructs a value that a sanitiser could plausibly
// "fix" cheaply; the correct behaviour is a flat refusal, never a
// modified acceptance.
// ---------------------------------------------------------------------------------

#[test]
fn a_value_one_byte_over_the_maximum_length_is_refused_whole_never_shortened() {
    let base = "a".repeat(crate::MAX_RECEIVED_VALUE_LEN);
    let one_over = format!("{base}x");
    let result = crate::validate_received_message(&one_over);
    assert!(
        result.is_err(),
        "AC-29/REQ-26: a value one byte over the maximum length must be refused whole; \
         a truncating implementation might instead accept the first \
         MAX_RECEIVED_VALUE_LEN bytes, which this crate must never do"
    );
}

#[test]
fn a_value_with_one_disallowed_character_among_many_allowed_ones_is_refused_whole() {
    // A single disallowed character (a NUL byte) embedded in an otherwise
    // fully permitted message. A stripping implementation might remove
    // just the one bad byte and accept the rest; this crate must refuse
    // the whole value instead.
    let poisoned = format!("heimdall: a perfectly good message{}with one bad byte", '\u{0}');
    let result = crate::validate_received_message(&poisoned);
    assert!(
        result.is_err(),
        "AC-29/REQ-26: a value containing one disallowed character among many allowed \
         ones must be refused whole, never repaired by stripping just the bad byte"
    );
}

#[test]
fn a_value_with_a_trailing_disallowed_character_is_refused_whole_never_stripped() {
    let poisoned = "heimdall: a good message\r";
    let result = crate::validate_received_message(poisoned);
    assert!(
        result.is_err(),
        "AC-29/REQ-26: a value with one disallowed trailing character (here, a bare \
         carriage return) must be refused whole, never stripped of just that character"
    );
}
