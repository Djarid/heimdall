//! The secret loader's seven fail-closed refusal conditions (REQ-14 to REQ-18) and
//! the test-isolation discipline of REQ-37 (section 3.6). Wired into the crate by
//! `lib.rs`'s `#[path = "../unit_tests/loader_failclosed.rs"] mod loader_failclosed;`
//! declaration (REQ-38): compiled as an IN-CRATE module so it can reach
//! `crate::authoriser`, `crate::record`, `crate::types` and `crate::verify`'s
//! `pub(crate)` items to build fixture `TrustedAuthoriserSet`s and to verify a
//! record against a loaded secret indirectly (REQ-13 forbids any PUBLIC accessor
//! returning the secret, so the ONLY way this file can confirm exactly which bytes
//! a loader produced is to attest a record with a candidate byte string and check
//! whether it verifies against what was loaded -- see `attest_and_verify` below).
//!
//! THIS FILE WILL FAIL TO COMPILE until `crate::authoriser`, `crate::record`,
//! `crate::types` and `crate::verify` exist and are declared as modules from
//! `lib.rs`. That is expected and correct at this stage, exactly as
//! `substrate_parity.rs`'s header states for the same reason.
//!
//! Signatures assumed here (this test suite's own committed contract, in addition
//! to `substrate_parity.rs`'s header):
//!
//!   - `authoriser::{SECRET_PATH_ENV_VAR, MIN_SECRET_BYTES}`, `authoriser::
//!     TrustedAuthoriserSet`, `authoriser::load_trusted_set_from_path(authoriser_id:
//!     &str, path: &Path) -> Result<TrustedAuthoriserSet, SecretRefusal>` and
//!     `authoriser::load_trusted_set_from_env(authoriser_id: &str) ->
//!     Result<TrustedAuthoriserSet, SecretRefusal>` (REQ-13, REQ-14 to REQ-17).
//!   - `authoriser::SecretRefusal`, a closed seven-variant enum, one variant per
//!     REQ-14 condition, each a single-field tuple variant carrying a `String`
//!     reason that never contains the secret (REQ-18):
//!     `EnvVarMissing(String)` (case 1), `NotARegularFile(String)` (case 2, covers
//!     both a nonexistent path and a path that is not a regular file, EC-6),
//!     `InTreePath(String)` (case 3, REQ-15), `InsecurePermissions(String)` (case 4,
//!     REQ-16), `NoPermissionMetadata(String)` (case 5, REQ-16's non-Unix branch),
//!     `SecretTooShortOrBlank(String)` (case 6, REQ-17) and `UnreadableFile(String)`
//!     (case 7).
//!
//! **Case 1 (the env-var entry point only) is deliberately NOT tested in this
//! file.** This repository's pinned toolchain (`cargo 1.98.0`, confirmed directly:
//! `std::env::set_var` and `std::env::remove_var` are `unsafe fn` on this
//! toolchain) cannot be exercised inside `hierarchy-vor` at all, because the crate
//! root carries `#![forbid(unsafe_code)]` (REQ-2), which is a crate-wide attribute
//! that this unit-test module inherits (it is compiled INTO the crate via `lib.rs`'s
//! `#[path]` declaration, unlike an external integration test). REQ-37 permits
//! exactly one environment-mutating test in the whole suite; it lives in
//! `tests/public_surface.rs` instead, specifically because an integration test is
//! compiled as its own external crate and is not bound by `hierarchy_vor`'s
//! `forbid(unsafe_code)`. Every other REQ-14 case here uses
//! `load_trusted_set_from_path` exclusively and touches no environment variable at
//! all, matching section 2.2's own reason for having two loader entry points
//! ("testable without mutating process-global state").

use std::fs;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use crate::authoriser::TrustedAuthoriserSet;
use crate::record::compute_record_attestation;
use crate::types::CohortDefinition;
use crate::verify::{RecordRefusal, verify_record};

// ---------------------------------------------------------------------------------
// Fixture helpers. Every secret file this suite writes lives under the system
// temporary directory (REQ-37), with exactly one deliberate exception (REQ-15's own
// in-tree fixture, which is removed again in the same test that creates it).
// ---------------------------------------------------------------------------------

fn temp_scratch_dir(label: &str) -> PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system clock before the Unix epoch")
        .as_nanos();
    let dir = std::env::temp_dir().join(format!("hierarchy-vor-loader-failclosed-{label}-{nanos}"));
    fs::create_dir_all(&dir)
        .expect("failed to create a scratch dir under the system temp directory");
    dir
}

#[cfg(unix)]
fn write_secret_file(path: &Path, content: &[u8], mode: u32) {
    use std::os::unix::fs::PermissionsExt;
    fs::write(path, content).expect("failed to write a fixture secret file");
    fs::set_permissions(path, fs::Permissions::from_mode(mode))
        .expect("failed to set a fixture secret file's permissions");
}

/// Builds a minimal, otherwise-valid `CohortDefinition`, attests it under `secret`
/// naming `authoriser_id`, and verifies it against `trusted`. This is the ONLY way
/// this file can confirm which exact bytes a loaded `TrustedAuthoriserSet` holds,
/// because REQ-13 forbids any public accessor that returns the secret directly: an
/// `Ok(())` here means `trusted`'s secret for `authoriser_id` is BYTE-IDENTICAL to
/// `secret`; an `Err` means it differs by at least one byte.
fn attest_and_verify(
    authoriser_id: &str,
    secret: &[u8],
    trusted: &TrustedAuthoriserSet,
) -> Result<(), RecordRefusal> {
    let mut record = CohortDefinition {
        cohort_id: "loader-failclosed-fixture".to_string(),
        permitted_actions: vec!["action:git.commit".to_string()],
        trust_ceiling: "TAINTED".to_string(),
        consequential_sinks: vec!["sink:git.commit".to_string()],
        authoriser: Some(authoriser_id.to_string()),
        attestation: None,
    };
    let attestation = compute_record_attestation(&record, secret);
    record.attestation = Some(attestation);
    verify_record(
        &record,
        record.authoriser.as_deref(),
        record.attestation.as_deref(),
        trusted,
    )
}

// ---------------------------------------------------------------------------------
// REQ-14 case 2 (EC-6 folded in): the path does not exist, or exists and is not a
// regular file.
// ---------------------------------------------------------------------------------

#[test]
fn req14_case_2a_nonexistent_path_refused() {
    let dir = temp_scratch_dir("case2a");
    let missing = dir.join("does-not-exist");
    let outcome = crate::authoriser::load_trusted_set_from_path("req14-2a", &missing);
    assert!(
        outcome.is_err(),
        "a nonexistent secret path must be refused, never fall back"
    );
}

#[test]
fn req14_case_2b_directory_instead_of_regular_file_refused() {
    let dir = temp_scratch_dir("case2b");
    // `dir` is itself a directory, never a regular file (EC-6: must not hang on a
    // FIFO either, but a directory is the deterministic case to exercise here).
    let outcome = crate::authoriser::load_trusted_set_from_path("req14-2b", &dir);
    assert!(
        outcome.is_err(),
        "a directory must be refused as not a regular file"
    );
}

// ---------------------------------------------------------------------------------
// REQ-14 case 3 / REQ-15: the in-tree rejection, paired with the same content
// succeeding outside the tree (AC-15).
// ---------------------------------------------------------------------------------

#[cfg(unix)]
#[test]
fn req15_in_tree_secret_refused_same_content_outside_tree_succeeds() {
    let content = b"01234567890123456789012345678901"; // 32 bytes, non-whitespace

    let in_tree_path = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(".tmp-req15-in-tree-secret");
    write_secret_file(&in_tree_path, content, 0o600);
    let in_tree_outcome = crate::authoriser::load_trusted_set_from_path("req15", &in_tree_path);
    let _ = fs::remove_file(&in_tree_path); // clean up regardless of outcome
    assert!(
        matches!(in_tree_outcome, Err(_)),
        "REQ-15: a secret path inside the repository working tree must be refused \
         even with correct permissions and a long-enough secret"
    );

    let dir = temp_scratch_dir("req15-outside");
    let outside_path = dir.join("secret");
    write_secret_file(&outside_path, content, 0o600);
    let outside_outcome = crate::authoriser::load_trusted_set_from_path("req15", &outside_path);
    assert!(
        outside_outcome.is_ok(),
        "the SAME content outside the repository working tree must load: {outside_outcome:?}"
    );
}

// ---------------------------------------------------------------------------------
// REQ-14 case 4 and REQ-16: group- or other-readable permissions refused; 0o600
// loads.
// ---------------------------------------------------------------------------------

#[cfg(unix)]
#[test]
fn req14_case_4_group_or_other_readable_secret_refused() {
    let dir = temp_scratch_dir("case4");
    let path = dir.join("secret-0644");
    write_secret_file(&path, b"01234567890123456789012345678901", 0o644);
    let outcome = crate::authoriser::load_trusted_set_from_path("req14-4", &path);
    assert!(
        outcome.is_err(),
        "0o644 grants group and other read access and must be refused (REQ-16)"
    );
}

#[cfg(unix)]
#[test]
fn req16_0600_secret_outside_repo_loads_successfully() {
    let dir = temp_scratch_dir("req16-0600");
    let path = dir.join("secret-0600");
    write_secret_file(&path, b"01234567890123456789012345678901", 0o600);
    let outcome = crate::authoriser::load_trusted_set_from_path("req16", &path);
    assert!(
        outcome.is_ok(),
        "a 0o600 secret file outside the repository must load: {outcome:?}"
    );
}

// ---------------------------------------------------------------------------------
// REQ-14 case 5 / REQ-16's non-Unix branch: refuses rather than silently skipping.
// Only compiled and run on a non-Unix target; on this repository's Unix
// development and CI platform the Unix branch above is what is exercised.
// ---------------------------------------------------------------------------------

#[cfg(not(unix))]
#[test]
fn req14_case_5_no_unix_permission_metadata_refuses_rather_than_skips() {
    let dir = temp_scratch_dir("case5-non-unix");
    let path = dir.join("secret");
    fs::write(&path, b"01234567890123456789012345678901")
        .expect("failed to write fixture secret file");
    let outcome = crate::authoriser::load_trusted_set_from_path("req14-5", &path);
    assert!(
        outcome.is_err(),
        "a target providing no Unix permission metadata must refuse, never silently skip \
         the permissions check (a skipped check is the fail-open shape)"
    );
}

// ---------------------------------------------------------------------------------
// REQ-14 case 6 / REQ-17: length and whitespace-only refusals, and the exact
// trailing-newline-stripping semantics (including EC-7's CRLF case), verified
// indirectly via `attest_and_verify` because REQ-13 forbids a public secret
// accessor.
// ---------------------------------------------------------------------------------

#[cfg(unix)]
#[test]
fn req14_case_6a_31_byte_secret_refused_as_too_short() {
    let dir = temp_scratch_dir("case6a");
    let path = dir.join("secret");
    write_secret_file(&path, b"0123456789012345678901234567890", 0o600); // 31 bytes
    let outcome = crate::authoriser::load_trusted_set_from_path("req14-6a", &path);
    assert!(
        outcome.is_err(),
        "a bare 31-byte secret must be refused as too short"
    );
}

#[cfg(unix)]
#[test]
fn req14_case_6b_31_bytes_plus_newline_is_still_31_after_strip_refused() {
    let dir = temp_scratch_dir("case6b");
    let path = dir.join("secret");
    let mut content = b"0123456789012345678901234567890".to_vec(); // 31 bytes
    content.push(b'\n');
    write_secret_file(&path, &content, 0o600);
    let outcome = crate::authoriser::load_trusted_set_from_path("req14-6b", &path);
    assert!(
        outcome.is_err(),
        "stripping exactly one trailing newline must still leave only 31 bytes, \
         refused as too short"
    );
}

#[cfg(unix)]
#[test]
fn req14_case_6c_whitespace_only_secret_refused_even_though_long_enough() {
    let dir = temp_scratch_dir("case6c");
    let path = dir.join("secret");
    let content = vec![b' '; 40]; // well over MIN_SECRET_BYTES, but entirely whitespace
    write_secret_file(&path, &content, 0o600);
    let outcome = crate::authoriser::load_trusted_set_from_path("req14-6c", &path);
    assert!(
        outcome.is_err(),
        "an entirely-whitespace secret must be refused even though its length is \
         sufficient (REQ-14 case 6)"
    );
}

#[cfg(unix)]
#[test]
fn req17_single_trailing_newline_stripped_leaves_exactly_32_bytes() {
    let dir = temp_scratch_dir("req17-single-newline");
    let path = dir.join("secret");
    let thirty_two = b"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"; // 32 bytes
    let mut on_disk = thirty_two.to_vec();
    on_disk.push(b'\n');
    write_secret_file(&path, &on_disk, 0o600);

    let trusted = crate::authoriser::load_trusted_set_from_path("req17-a", &path)
        .expect("a 32-byte secret with one trailing newline must load");
    assert!(
        attest_and_verify("req17-a", thirty_two, &trusted).is_ok(),
        "AC-17: the loaded secret must equal exactly the 32 bytes, with the trailing \
         newline stripped and nothing else transformed"
    );
}

#[cfg(unix)]
#[test]
fn req17_two_trailing_newlines_only_one_is_stripped() {
    let dir = temp_scratch_dir("req17-two-newlines");
    let path = dir.join("secret");
    let thirty_two = b"BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB";
    let mut on_disk = thirty_two.to_vec();
    on_disk.extend_from_slice(b"\n\n");
    write_secret_file(&path, &on_disk, 0o600);

    let trusted = crate::authoriser::load_trusted_set_from_path("req17-b", &path).expect(
        "two trailing newlines still leaves >= 32 bytes after stripping one, and must load",
    );

    // The bare 32 bytes (as if BOTH newlines were stripped) must NOT match: AC-17
    // requires exactly one line ending stripped, never a second transformation.
    assert!(
        attest_and_verify("req17-b", thirty_two, &trusted).is_err(),
        "AC-17: stripping both trailing newlines is a forbidden second transformation; \
         the loaded secret must not equal the bare 32 bytes"
    );

    // Exactly 32 bytes plus ONE trailing newline must match.
    let mut expected = thirty_two.to_vec();
    expected.push(b'\n');
    assert!(
        attest_and_verify("req17-b", &expected, &trusted).is_ok(),
        "AC-17: exactly one trailing newline must be stripped, leaving the other as \
         part of the 33-byte secret"
    );
}

#[cfg(unix)]
#[test]
fn ec7_crlf_trailing_line_ending_stripped_as_a_single_unit() {
    let dir = temp_scratch_dir("ec7-crlf");
    let path = dir.join("secret");
    let thirty_two = b"CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC";
    let mut on_disk = thirty_two.to_vec();
    on_disk.extend_from_slice(b"\r\n");
    write_secret_file(&path, &on_disk, 0o600);

    let trusted = crate::authoriser::load_trusted_set_from_path("req17-crlf", &path)
        .expect("a CRLF-terminated 32-byte secret must load (EC-7)");
    assert!(
        attest_and_verify("req17-crlf", thirty_two, &trusted).is_ok(),
        "EC-7: a \\r\\n line ending must be stripped as a single unit, leaving exactly \
         the same 32 bytes as the bare-\\n case, not 33 (a stray \\r kept) or 31 \
         (over-stripped)"
    );
}

// ---------------------------------------------------------------------------------
// REQ-14 case 7: the file cannot be read.
// ---------------------------------------------------------------------------------

#[cfg(unix)]
#[test]
fn req14_case_7_unreadable_file_refused() {
    // A file with NO read permission for owner, group or other passes REQ-16's
    // group/other-permission check (there is no group or other access to grant)
    // but fails at the actual read, which is what distinguishes this case from
    // case 4 above.
    //
    // Caveat, stated rather than hidden: a test runner executing as root would
    // still be able to read a 0o000 file, in which case this assertion would not
    // hold. That is a limitation of running this specific test as root, not of
    // the loader; this repository's own CI and local development both run
    // unprivileged.
    let dir = temp_scratch_dir("case7");
    let path = dir.join("secret");
    write_secret_file(&path, b"01234567890123456789012345678901", 0o000);
    let outcome = crate::authoriser::load_trusted_set_from_path("req14-7", &path);
    assert!(
        outcome.is_err(),
        "a file with no read permission for anyone, including its owner, must be \
         refused (REQ-14 case 7)"
    );
}

// ---------------------------------------------------------------------------------
// REQ-18: no refusal reason, from the loader or from the verifier, may contain any
// byte of the secret.
// ---------------------------------------------------------------------------------

#[cfg(unix)]
#[test]
fn req18_loader_refusal_reasons_never_contain_the_secret() {
    const CANARY: &str = "REQ18-CANARY-NEVER-PRINTED-PADDING-TO-32-BYTES";

    let mut refusals: Vec<crate::authoriser::SecretRefusal> = Vec::new();

    // In-tree (REQ-15): content carries the canary.
    let in_tree_path = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(".tmp-req18-in-tree-secret");
    write_secret_file(&in_tree_path, CANARY.as_bytes(), 0o600);
    if let Err(r) = crate::authoriser::load_trusted_set_from_path("req18-a", &in_tree_path) {
        refusals.push(r);
    }
    let _ = fs::remove_file(&in_tree_path);

    // Insecure permissions (REQ-16): content carries the canary.
    let dir = temp_scratch_dir("req18-perms");
    let perm_path = dir.join("secret");
    write_secret_file(&perm_path, CANARY.as_bytes(), 0o644);
    if let Err(r) = crate::authoriser::load_trusted_set_from_path("req18-b", &perm_path) {
        refusals.push(r);
    }

    assert!(
        refusals.len() >= 2,
        "both fixtures above must be refused for this redaction test to be meaningful; \
         got {} refusal(s)",
        refusals.len()
    );
    for refusal in &refusals {
        let rendered = format!("{refusal:?}");
        assert!(
            !rendered.contains(CANARY),
            "REQ-18: a SecretRefusal's Debug output contained the secret: {rendered}"
        );
    }
}

#[test]
fn req18_record_refusal_reason_never_contains_the_secret() {
    const CANARY: &str = "REQ18-CANARY-FOR-RECORD-REFUSAL-TEST-PADDED!!!!";
    let secret = CANARY.as_bytes();
    let trusted = TrustedAuthoriserSet::for_test(&[("req18-record-authoriser", secret)]);

    let mut record = CohortDefinition {
        cohort_id: "req18-fixture".to_string(),
        permitted_actions: vec!["action:git.commit".to_string()],
        trust_ceiling: "TAINTED".to_string(),
        consequential_sinks: vec!["sink:git.commit".to_string()],
        authoriser: Some("req18-record-authoriser".to_string()),
        attestation: None,
    };
    let attestation = compute_record_attestation(&record, secret);
    record.attestation = Some(attestation);
    record.trust_ceiling = "TRUSTED".to_string(); // force a digest-mismatch refusal

    let refusal = verify_record(
        &record,
        record.authoriser.as_deref(),
        record.attestation.as_deref(),
        &trusted,
    )
    .expect_err("a mutated record must be refused for this redaction test to be meaningful");

    let rendered = format!("{refusal:?}");
    assert!(
        !rendered.contains(CANARY),
        "REQ-18: a RecordRefusal's Debug output contained the secret: {rendered}"
    );
}
