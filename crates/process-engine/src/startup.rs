//! The binary's fail-closed startup contract (PE-5, REQ-26 to REQ-29):
//! resolving the two environment-named preconditions before any step of
//! the sequence runs, refusing fail closed and naming every failing
//! condition, never defaulting, and never printing a byte of secret
//! material. This is the one module in the crate that reads the
//! environment (REQ-26); `src/main.rs` delegates to it rather than
//! reading the environment itself.
//!
//! [`resolve_startup_preconditions`] is the pure half: it takes
//! already-read environment VALUES as parameters, rather than reading
//! `std::env` itself, so it is exercisable from an in-crate unit-test
//! module on every machine regardless of what is or is not provisioned.
//! [`run`] is the thin wrapper that actually reads the two environment
//! variables and forwards their values into it; it is the one place in
//! this crate the two variable NAMES below are read from the real
//! process environment.

use std::path::{Path, PathBuf};

/// Names the environment variable carrying the trusted secret file's
/// path (`hierarchy_vor::SECRET_PATH_ENV_VAR`'s own value, restated here
/// as this crate's own named constant on `context::TARGET_SCOPE`'s own
/// agreement-not-derivation precedent for a value two independently
/// owned constants happen to share).
pub const SECRET_PATH_ENV_VAR: &str = "HEIMDALL_COHORT_SECRET_FILE";

/// Names the environment variable carrying the actuator's own working
/// repository path. This crate cannot name `actuator_git::repo::WORKING_REPO_ENV_VAR`
/// at all (it is `pub(crate)` to that crate, and this crate does not
/// depend on `actuator-git` in any case, REQ-4): this constant restates
/// the same variable name as this crate's own agreement, never a
/// derivation.
pub const WORKING_REPO_ENV_VAR: &str = "HEIMDALL_ACTUATOR_GIT_WORKING_REPO";

/// One startup's own refusal (REQ-27, REQ-28): one field per
/// environment-named precondition. `None` means that precondition
/// resolved; `Some(description)` names the failing environment variable
/// and its refusal class, never a secret byte (REQ-29). Both fields are
/// always populated independently, so a caller can read whichever
/// failed, or both, rather than only the first (EC-5).
#[derive(Debug)]
pub struct StartupRefusal {
    /// `None` if the cohort precondition resolved; otherwise names
    /// [`SECRET_PATH_ENV_VAR`] and the reason it failed.
    pub cohort: Option<String>,
    /// `None` if the working-repository precondition resolved;
    /// otherwise names [`WORKING_REPO_ENV_VAR`] and the reason it
    /// failed.
    pub working_repo: Option<String>,
}

/// Resolves the cohort precondition from an already-read environment
/// VALUE (never reading `std::env` itself): loads a
/// `hierarchy_vor::TrustedAuthoriserSet` from `secret_path_value` and
/// verifies it into a real `hierarchy_vor::VerifiedCohort`. Refuses fail
/// closed, naming [`SECRET_PATH_ENV_VAR`], on an absent or empty value
/// and never falls back to any default or candidate path.
fn resolve_cohort(secret_path_value: Option<&str>) -> Result<hierarchy_vor::VerifiedCohort, String> {
    let path = match secret_path_value {
        Some(path) if !path.trim().is_empty() => path,
        _ => {
            return Err(format!(
                "{SECRET_PATH_ENV_VAR} is not set, or is set to an empty value; refusing \
                 rather than defaulting or searching the filesystem for a candidate secret"
            ));
        }
    };

    let trusted =
        hierarchy_vor::load_trusted_set_from_path(hierarchy_vor::cohort::AUTHORISER_ID, Path::new(path))
            .map_err(|refusal| {
                format!("{SECRET_PATH_ENV_VAR} names a path, but loading it was refused: {refusal:?}")
            })?;

    hierarchy_vor::load_verified_cohort(&trusted).map_err(|refusal| {
        format!(
            "{SECRET_PATH_ENV_VAR} named a path, and a secret loaded from it, but the \
             cohort's committed attestation did not verify against it: {refusal:?}"
        )
    })
}

/// Resolves the working-repository precondition from an already-read
/// environment VALUE. Checks only that the named path exists and is a
/// directory (EC-4's own instruction: this crate must not duplicate the
/// actuator's deeper policy, only establish that the precondition is
/// resolvable at all); the actuator's own five refusal conditions still
/// own the deeper validation. Refuses fail closed, naming
/// [`WORKING_REPO_ENV_VAR`], and never falls back to the inherited
/// current working directory.
fn resolve_working_repo(working_repo_path_value: Option<&str>) -> Result<PathBuf, String> {
    let path = match working_repo_path_value {
        Some(path) if !path.trim().is_empty() => path,
        _ => {
            return Err(format!(
                "{WORKING_REPO_ENV_VAR} is not set, or is set to an empty value; refusing \
                 rather than defaulting to the inherited current working directory"
            ));
        }
    };

    let candidate = PathBuf::from(path);
    if !candidate.is_dir() {
        return Err(format!(
            "{WORKING_REPO_ENV_VAR} names {path:?}, which does not exist or is not a \
             directory; refusing rather than defaulting"
        ));
    }

    Ok(candidate)
}

/// The pure precondition-resolving logic (REQ-27): both preconditions
/// are resolved independently, and both are always attempted, so a
/// caller sees which one failed, or both, never merely the first
/// (EC-5). Never defaults on either failing condition (EC-3, EC-4).
pub fn resolve_startup_preconditions(
    secret_path_value: Option<&str>,
    working_repo_path_value: Option<&str>,
) -> Result<(hierarchy_vor::VerifiedCohort, PathBuf), StartupRefusal> {
    let cohort_result = resolve_cohort(secret_path_value);
    let working_repo_result = resolve_working_repo(working_repo_path_value);

    match (cohort_result, working_repo_result) {
        (Ok(cohort), Ok(working_repo)) => Ok((cohort, working_repo)),
        (cohort_result, working_repo_result) => Err(StartupRefusal {
            cohort: cohort_result.err(),
            working_repo: working_repo_result.err(),
        }),
    }
}

/// The one place in this crate the two environment variable NAMES above
/// are read from the real process environment (REQ-26): reads both, then
/// delegates to [`resolve_startup_preconditions`]. `src/main.rs` calls
/// this function alone; it never reads the environment itself.
pub fn run() -> Result<(hierarchy_vor::VerifiedCohort, PathBuf), StartupRefusal> {
    let secret_path_value = std::env::var(SECRET_PATH_ENV_VAR).ok();
    let working_repo_path_value = std::env::var(WORKING_REPO_ENV_VAR).ok();
    resolve_startup_preconditions(secret_path_value.as_deref(), working_repo_path_value.as_deref())
}
