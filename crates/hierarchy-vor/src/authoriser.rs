//! The trusted authoriser set and the secret's provenance (section 2.2, section
//! 3.3, REQ-13 to REQ-19). This module is the only place in the crate that ever
//! touches a secret byte, and it enforces every one of REQ-14's seven fail-closed
//! refusal conditions before a [`TrustedAuthoriserSet`] can be built at all.
//!
//! **Why a path named by a variable, never the secret in the variable
//! (section 2.2).** A secret held directly in an environment variable is
//! inherited by every child process a later step shells out to (the git
//! actuator, `plans/synthesis-bootstrap.md` section 5), and would appear in
//! process listings and crash dumps on the way. [`SECRET_PATH_ENV_VAR`] therefore
//! names a **path**, never the secret itself, and there are exactly two public
//! entry points: [`load_trusted_set_from_env`], which reads that variable and
//! delegates, and [`load_trusted_set_from_path`], which takes a path directly so
//! an integration test needs no process-global mutation (REQ-37).
//!
//! **No secret literal anywhere under `crates/hierarchy-vor/src/` (REQ-13).**
//! [`TrustedAuthoriserSet`] has no public constructor taking secret bytes, no
//! public setter and no public accessor returning a secret. Its only
//! byte-taking constructor, [`TrustedAuthoriserSet::for_test`], is `pub(crate)`
//! and exists solely so `unit_tests/` can build a fixture set without going
//! through the filesystem; it is unreachable from any external crate.
//!
//! **REQ-15's in-tree rejection is a development-time guard, not a deployment
//! security control.** [`repo_root`] derives a repository root from
//! `CARGO_MANIFEST_DIR` at compile time. In a binary built on one machine and
//! run on another, the rejected prefix is a path that may not exist on the
//! running machine at all, and the check is then vacuous. It exists to catch
//! the source-tree-constant failure mode during development, not to defend a
//! deployed binary.
//!
//! **REQ-19, the named residual: no zeroisation.** Secret bytes read here are
//! never zeroised on drop. Zeroisation a compiler cannot elide needs either
//! `unsafe` or a crate dependency, and this crate forbids both (REQ-2, REQ-1,
//! section 2.3). A memory-scraping adversary is therefore out of scope for this
//! step; this is a named limit, not an oversight.
//!
//! **REQ-18: the secret never appears in output.** No refusal reason built
//! below ever includes a byte of the secret or the raw file content; every
//! reason names only the path, the condition and, where relevant, the
//! authoriser id. [`SecretRefusal`] does not derive `Debug`; its hand-written
//! [`std::fmt::Debug`] implementation below only ever prints the variant name
//! and its (secret-free) reason string.

use std::collections::HashMap;
use std::path::{Path, PathBuf};

/// Names the environment variable that carries the secret file's **path**,
/// never the secret itself (section 2.2, REQ-14 case 1).
pub const SECRET_PATH_ENV_VAR: &str = "HEIMDALL_COHORT_SECRET_FILE";

/// The minimum secret length in bytes, after the single trailing-line-ending
/// strip of REQ-17. Below this, or entirely whitespace, the secret is refused
/// (REQ-14 case 6).
pub const MIN_SECRET_BYTES: usize = 32;

/// The authorisers this crate trusts, each mapped to its own secret bytes
/// (REQ-13). Opaque: its field is private, it derives no `Debug`, and nothing
/// outside this crate can construct one from bytes or read a secret back out
/// of it. The only way to confirm which bytes a loaded set holds is to attest
/// a record under a candidate secret and check whether it verifies
/// (`crate::verify::verify_record`), which is exactly how `unit_tests/` does
/// it.
pub struct TrustedAuthoriserSet {
    authorisers: HashMap<String, Vec<u8>>,
}

impl TrustedAuthoriserSet {
    /// Test-only constructor building a set directly from in-memory bytes,
    /// bypassing the filesystem loader entirely. `pub(crate)`: reachable only
    /// from inside this crate, which includes the in-crate unit-test modules
    /// `lib.rs` wires in under `#[cfg(test)]` (REQ-13, REQ-38). No external
    /// crate can call this: it is not `pub`, and an integration test under
    /// `tests/` is compiled as a separate crate that cannot see `pub(crate)`
    /// items.
    #[cfg(test)]
    pub(crate) fn for_test(entries: &[(&str, &[u8])]) -> Self {
        let mut authorisers = HashMap::new();
        for (id, secret) in entries {
            authorisers.insert((*id).to_string(), secret.to_vec());
        }
        TrustedAuthoriserSet { authorisers }
    }

    /// The secret bytes trusted for `authoriser_id`, or `None` if it is not in
    /// this set. `pub(crate)` only (REQ-13): this is exactly the "public
    /// accessor returning a secret" the requirement forbids, so it must never
    /// be reachable from outside the crate. `crate::verify::verify_record` is
    /// the one caller.
    pub(crate) fn secret_for(&self, authoriser_id: &str) -> Option<&[u8]> {
        self.authorisers.get(authoriser_id).map(|v| v.as_slice())
    }
}

/// Hand-written, never derived (REQ-18): prints only the trusted authoriser ids
/// (not secret) and, for each, a fixed `"<redacted>"` placeholder in place of
/// its secret bytes and length, so a test asserting a refusal path (a `Result<
/// TrustedAuthoriserSet, SecretRefusal>` formatted with `{:?}` on its success
/// side included) can render without ever exposing a byte of any secret.
impl std::fmt::Debug for TrustedAuthoriserSet {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let mut set = f.debug_struct("TrustedAuthoriserSet");
        for id in self.authorisers.keys() {
            set.field(id, &"<redacted>");
        }
        set.finish()
    }
}

/// The loader's seven fail-closed refusal reasons (REQ-14), one variant per
/// condition. Closed: no eighth variant, no warning-only outcome. Each reason
/// string names the path and the condition, never the secret (REQ-18).
pub enum SecretRefusal {
    /// Case 1 (the env-var entry point only): the variable is absent or empty.
    EnvVarMissing(String),
    /// Case 2: the path does not exist, or exists and is not a regular file.
    NotARegularFile(String),
    /// Case 3 / REQ-15: the path resolves inside the repository working tree.
    InTreePath(String),
    /// Case 4 / REQ-16: the file is readable by group or other on Unix.
    InsecurePermissions(String),
    /// Case 5 / REQ-16: the target provides no Unix permission metadata, so
    /// the check is refused rather than silently skipped.
    NoPermissionMetadata(String),
    /// Case 6 / REQ-17: shorter than [`MIN_SECRET_BYTES`] after the trailing
    /// line-ending strip, or entirely whitespace.
    SecretTooShortOrBlank(String),
    /// Case 7: the file exists, is a regular file and has acceptable
    /// permissions, but could not actually be read.
    UnreadableFile(String),
}

/// Hand-written, never derived (REQ-18): this only ever prints the variant
/// name and the (already secret-free, by construction) reason string, never a
/// raw byte of the secret or the file's content.
impl std::fmt::Debug for SecretRefusal {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let (name, reason) = match self {
            SecretRefusal::EnvVarMissing(r) => ("EnvVarMissing", r),
            SecretRefusal::NotARegularFile(r) => ("NotARegularFile", r),
            SecretRefusal::InTreePath(r) => ("InTreePath", r),
            SecretRefusal::InsecurePermissions(r) => ("InsecurePermissions", r),
            SecretRefusal::NoPermissionMetadata(r) => ("NoPermissionMetadata", r),
            SecretRefusal::SecretTooShortOrBlank(r) => ("SecretTooShortOrBlank", r),
            SecretRefusal::UnreadableFile(r) => ("UnreadableFile", r),
        };
        f.debug_tuple(name).field(reason).finish()
    }
}

/// Reads [`SECRET_PATH_ENV_VAR`], then delegates to [`load_trusted_set_from_path`].
/// Refuses (REQ-14 case 1) rather than falling back to a default when the
/// variable is absent or empty.
pub fn load_trusted_set_from_env(authoriser_id: &str) -> Result<TrustedAuthoriserSet, SecretRefusal> {
    let path_value = std::env::var(SECRET_PATH_ENV_VAR).unwrap_or_default();
    if path_value.is_empty() {
        return Err(SecretRefusal::EnvVarMissing(format!(
            "{SECRET_PATH_ENV_VAR} is not set, or is set to an empty value; refusing \
             rather than falling back to a default secret path (REQ-14 case 1)"
        )));
    }
    load_trusted_set_from_path(authoriser_id, Path::new(&path_value))
}

/// Loads a trusted authoriser set from a secret file at `path`, enforcing
/// every one of REQ-14's seven refusal conditions (cases 2 to 7 directly;
/// case 1 belongs to [`load_trusted_set_from_env`] alone, since a bare path
/// has no "variable absent" case of its own). Exists so tests, and any other
/// caller that already has a path, need not go through an environment
/// variable at all (section 2.2).
pub fn load_trusted_set_from_path(
    authoriser_id: &str,
    path: &Path,
) -> Result<TrustedAuthoriserSet, SecretRefusal> {
    // Case 2: the path must exist and be a regular file.
    let metadata = std::fs::metadata(path).map_err(|_| {
        SecretRefusal::NotARegularFile(format!(
            "{} does not exist, or its metadata could not be read; refusing (REQ-14 case 2)",
            path.display()
        ))
    })?;
    if !metadata.is_file() {
        return Err(SecretRefusal::NotARegularFile(format!(
            "{} exists but is not a regular file; refusing (REQ-14 case 2)",
            path.display()
        )));
    }

    // Case 3 / REQ-15: refuse a path resolving inside the repository working
    // tree. Canonicalised on both sides so a symlinked temp directory or
    // repository checkout does not produce a false negative or a false
    // positive.
    let canonical = std::fs::canonicalize(path).map_err(|_| {
        SecretRefusal::NotARegularFile(format!(
            "{} could not be canonicalised; refusing (REQ-14 case 2)",
            path.display()
        ))
    })?;
    if canonical.starts_with(repo_root()) {
        return Err(SecretRefusal::InTreePath(format!(
            "{} resolves inside the repository working tree; this is a development-time \
             guard against the source-tree-constant failure mode, not a deployment \
             security control (REQ-15)",
            path.display()
        )));
    }

    // Case 4 and 5 / REQ-16: Unix permission bits, or their absence, refused
    // rather than silently skipped.
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mode = metadata.permissions().mode();
        if mode & 0o077 != 0 {
            return Err(SecretRefusal::InsecurePermissions(format!(
                "{} grants group or other access (mode {:o}); refusing (REQ-16)",
                path.display(),
                mode & 0o777
            )));
        }
    }
    #[cfg(not(unix))]
    {
        return Err(SecretRefusal::NoPermissionMetadata(format!(
            "this target provides no Unix permission metadata for {}; refusing rather \
             than silently skipping the permissions check, because a skipped check is \
             the fail-open shape (REQ-16)",
            path.display()
        )));
    }

    // Case 7: the file could not actually be read, distinct from case 4/5's
    // permission-bit inspection (a 0o000 file passes the group/other check
    // above but cannot be read by anyone, including its owner).
    let raw = std::fs::read(&canonical).map_err(|_| {
        SecretRefusal::UnreadableFile(format!(
            "{} could not be read; refusing (REQ-14 case 7)",
            path.display()
        ))
    })?;

    // Case 6 / REQ-17: strip exactly one trailing line ending and nothing
    // else, then refuse a secret shorter than MIN_SECRET_BYTES or entirely
    // whitespace.
    let stripped = strip_one_trailing_line_ending(&raw);
    if stripped.len() < MIN_SECRET_BYTES || stripped.iter().all(|b| b.is_ascii_whitespace()) {
        return Err(SecretRefusal::SecretTooShortOrBlank(format!(
            "the secret at {} is shorter than {MIN_SECRET_BYTES} bytes after stripping a \
             single trailing line ending, or is entirely whitespace; refusing (REQ-14 \
             case 6, REQ-17)",
            path.display()
        )));
    }

    let mut authorisers = HashMap::new();
    authorisers.insert(authoriser_id.to_string(), stripped);
    Ok(TrustedAuthoriserSet { authorisers })
}

/// Strips exactly one trailing line ending (`\n` or `\r\n`), and nothing else
/// (REQ-17). No trimming, decoding or other normalisation is applied.
fn strip_one_trailing_line_ending(bytes: &[u8]) -> Vec<u8> {
    if let Some(stripped) = bytes.strip_suffix(b"\r\n") {
        stripped.to_vec()
    } else if let Some(stripped) = bytes.strip_suffix(b"\n") {
        stripped.to_vec()
    } else {
        bytes.to_vec()
    }
}

/// The repository working tree's root, derived at compile time from this
/// crate's own manifest directory (REQ-15). `CARGO_MANIFEST_DIR` is
/// `crates/hierarchy-vor`; the repository root is two directories up. This is
/// a development-time guard only (see this module's own doc comment): on a
/// binary built on one machine and run on another, this path may not exist at
/// all on the running machine, and the in-tree check is then vacuous.
fn repo_root() -> PathBuf {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let root = manifest_dir
        .parent()
        .and_then(|p| p.parent())
        .map(|p| p.to_path_buf())
        .unwrap_or(manifest_dir);
    std::fs::canonicalize(&root).unwrap_or(root)
}
