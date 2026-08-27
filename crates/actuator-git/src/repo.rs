//! Resolution and validation of the working repository the actuator is to
//! operate on (REQ-18 to REQ-20, section 10 file 8 of
//! `.opencode/plans/git-actuator-step-four.md`). This module's one
//! responsibility (section 9.3) is answering exactly one question, "does a
//! valid, out-of-tree working repository exist at the path named by
//! [`WORKING_REPO_ENV_VAR`]", and nothing else: it knows nothing about
//! operations, argument vectors or the permitted-target allowlist.
//!
//! **Why a path named by a variable, never a path baked into the binary
//! (REQ-18).** Following D110's out-of-tree convention (restated by
//! `hierarchy_vor::authoriser`'s own doc comment for
//! `SECRET_PATH_ENV_VAR`): an environment variable names a location, and the
//! actuator resolves it fresh on every call rather than trusting the
//! inherited current working directory or a compiled-in default. A caller
//! that wants the actuator to operate on a particular repository sets the
//! variable; a caller that does not is refused, never defaulted.
//!
//! **The five fail-closed refusal conditions (REQ-19), in the order this
//! module checks them.** The variable is absent or empty; the named path
//! does not exist; the path exists but is not a directory; the path is a
//! directory but carries no git repository marker; and the path resolves,
//! after canonicalisation, inside this repository's own working tree. Every
//! one of the five refuses; none of them ever falls back to a default.
//!
//! **The fifth condition is a development-time guard, not a deployment
//! control (REQ-19's own documentation requirement, restated here rather than
//! left to a comment elsewhere).** It exists to stop the actuator from ever
//! being pointed at the repository that houses it while this crate is under
//! active development. [`this_repository_root`] derives its answer from
//! `CARGO_MANIFEST_DIR`, a path baked in at compile time on the machine that
//! built the binary. On a binary built here and run elsewhere, that path may
//! not exist on the running machine at all, at which point the check is
//! vacuous by construction. This mirrors `hierarchy_vor::authoriser`'s
//! identical `repo_root` precedent and its identical honesty about the same
//! limit for the secret-path case (REQ-15 there, REQ-19 here).
//!
//! **What this module does not decide.** Whether an operation's caller-
//! supplied strings are individually valid (`crate::argv`'s job, REQ-11) and
//! whether a push target is a member of the permitted allowlist
//! (`crate::targets`'s job, REQ-14) are both decided elsewhere and, per the
//! assumed check order documented in `unit_tests/argv_validation.rs` and
//! `unit_tests/target_and_repo_failclosed.rs`, both run strictly before this
//! module is ever consulted.

use std::path::{Path, PathBuf};

/// Names the environment variable that carries the working repository's
/// **path**, never a secret and never the repository's content (REQ-18).
/// Read fresh on every call to [`resolve_working_repository`]; never cached
/// and never defaulted.
pub(crate) const WORKING_REPO_ENV_VAR: &str = "HEIMDALL_ACTUATOR_GIT_WORKING_REPO";

/// Resolves and validates the working repository the actuator is to operate
/// on, enforcing every one of REQ-19's five fail-closed refusal conditions in
/// turn. Returns the canonicalised path on success, so every later caller
/// (`crate::execute`) passes an unambiguous, symlink-resolved working
/// directory to the spawned process explicitly (REQ-20): no operation relies
/// on the parent process's own current directory.
///
/// On failure, returns a bounded, human-readable diagnostic naming which
/// condition failed. The caller (`crate::execute::execute`) wraps this in
/// [`crate::types::ActuationRefusal::RepositoryResolution`]; this module
/// knows nothing about that type; the two-layer split is deliberate (the
/// operation, outcome and refusal vocabularies live in `crate::types` alone,
/// per section 9.3).
pub(crate) fn resolve_working_repository() -> Result<PathBuf, String> {
    // Condition 1: the variable is absent, or set to the empty string.
    // `std::env::var` (read only) needs no `unsafe` block: only the
    // process-mutating `set_var`/`remove_var` are `unsafe fn` under this
    // workspace's pinned toolchain, and this module never calls either.
    let path_value = std::env::var(WORKING_REPO_ENV_VAR).unwrap_or_default();
    if path_value.is_empty() {
        return Err(format!(
            "{WORKING_REPO_ENV_VAR} is not set, or is set to an empty value; refusing \
             rather than falling back to the inherited current working directory or a \
             path baked into the binary (REQ-18, REQ-19)"
        ));
    }
    let path = Path::new(&path_value);

    // Condition 2: the named path does not exist, or its metadata cannot be
    // read at all.
    let metadata = std::fs::metadata(path).map_err(|_| {
        format!(
            "{} does not exist, or its metadata could not be read; refusing (REQ-19)",
            path.display()
        )
    })?;

    // Condition 3: the path exists but is not a directory (for example, a
    // regular file).
    if !metadata.is_dir() {
        return Err(format!(
            "{} exists but is not a directory; refusing (REQ-19)",
            path.display()
        ));
    }

    // Condition 4: the directory carries no git repository marker. A `.git`
    // entry (a directory for a normal repository, or a file for a linked
    // worktree) is the marker this module looks for; this crate operates on
    // a non-bare working repository only, so a bare repository's own
    // `HEAD`/`refs`/`objects` living directly under `path`, with no `.git`
    // entry at all, does not satisfy this condition.
    if std::fs::metadata(path.join(".git")).is_err() {
        return Err(format!(
            "{} contains no git repository marker (no .git entry); refusing (REQ-19)",
            path.display()
        ));
    }

    // Condition 5, the development-time guard: refuse a path that resolves,
    // after canonicalisation on both sides, inside this repository's own
    // working tree. Canonicalising both sides means a symlinked temporary
    // directory (common on macOS, where `/tmp` itself is a symlink) produces
    // neither a false negative nor a false positive.
    let canonical = std::fs::canonicalize(path).map_err(|_| {
        format!(
            "{} could not be canonicalised; refusing (REQ-19)",
            path.display()
        )
    })?;
    if canonical.starts_with(this_repository_root()) {
        return Err(format!(
            "{} resolves inside this repository's own working tree; this is a \
             development-time guard against the actuator committing to the repository \
             that houses it, not a deployment control (REQ-19)",
            path.display()
        ));
    }

    Ok(canonical)
}

/// This repository's own working-tree root, derived at compile time from
/// this crate's own manifest directory (`crates/actuator-git`, two
/// directories below the repository root), mirroring
/// `hierarchy_vor::authoriser::repo_root`'s identical precedent and identical
/// honesty about its own limit: this is a development-time guard, not a
/// deployment control, and is documented as such on [`resolve_working_repository`]
/// rather than only here.
fn this_repository_root() -> PathBuf {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let root = manifest_dir
        .parent() // crates/
        .and_then(|p| p.parent()) // the repository root
        .map(|p| p.to_path_buf())
        .unwrap_or(manifest_dir);
    std::fs::canonicalize(&root).unwrap_or(root)
}
