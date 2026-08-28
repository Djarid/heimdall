//! The binary's fail-closed startup contract (PE-5, REQ-26 to REQ-29;
//! build-order step six ST6-3, REQ-14 to REQ-22): resolving the three
//! environment-named preconditions before any step of the sequence runs,
//! refusing fail closed and naming every failing condition, never
//! defaulting, and never printing a byte of secret material. This is the
//! one module in the crate that reads the environment (REQ-26, REQ-15);
//! `src/main.rs` delegates to it rather than reading the environment
//! itself.
//!
//! [`resolve_startup_preconditions`] is the pure half: it takes
//! already-read environment VALUES as parameters, rather than reading
//! `std::env` itself, so it is exercisable from an in-crate unit-test
//! module on every machine regardless of what is or is not provisioned.
//! [`run`] is the thin wrapper that actually reads the three environment
//! variables and forwards their values into it; it is the one place in
//! this crate the three variable NAMES below are read from the real
//! process environment.
//!
//! **The third precondition, `HEIMDALL_ENGINE_TASK` (ST6-3, REQ-14 to
//! REQ-22).** Unlike the first two, which each name a path, this one
//! names a selection: an index into `src/main.rs`'s own closed,
//! compile-time `TASK_MEMBERS` array. It resolves fail closed exactly
//! like the other two (absent, empty or whitespace-only refuses, never
//! defaulting), and its membership test against the closed set of
//! accepted selector names is exact byte equality only: no case folding,
//! no trimming before comparison, no prefix or substring match, no
//! numeric-index acceptance and no fuzzy match anywhere on the path
//! (REQ-17). Its only product is an index; it supplies no action name,
//! no target, no sink, no declared cost and no task identifier (REQ-18).
//! The five accepted names are kept here, in [`ACCEPTED_SELECTOR_NAMES`],
//! as this module's own private, closed constant array, rather than
//! imported from `main.rs`: `main.rs` is a separate crate root (a
//! distinct compilation unit from this library, REQ-5 of the step-five
//! spec) whose own selector-name constants are private to it, so there
//! is no import path across that boundary regardless of visibility, and
//! this containment is also exactly what REQ-39's structural check
//! requires -- `HEIMDALL_ENGINE_TASK` and `TASK_SELECTOR_ENV_VAR` appear
//! in this file and nowhere else under `crates/process-engine/src/`. The
//! two arrays are independent, hand-maintained agreements, in the same
//! never-a-derivation sense [`SECRET_PATH_ENV_VAR`] and
//! [`WORKING_REPO_ENV_VAR`] already are for the two path-shaped
//! preconditions: an edit to either array without the matching edit to
//! the other is a silent divergence neither compiler nor this module can
//! detect by itself, so any change to one is always paired with the same
//! change to the other by inspection, in the same commit.

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

/// Names the environment variable carrying the selector value that
/// chooses which member of `main.rs`'s own closed `TASK_MEMBERS` array
/// is submitted for adjudication (build-order step six, ST6-3, REQ-14).
/// It names a **selection**, never a path and never a secret. This is a
/// third, independent precondition on the existing two's own shape, not
/// a widening of either: the existing two name paths and this one names
/// a selection, so collapsing them into one would give this module a
/// second reason to change (REQ-22).
pub const TASK_SELECTOR_ENV_VAR: &str = "HEIMDALL_ENGINE_TASK";

/// The closed, compile-time set of accepted selector names (REQ-17,
/// REQ-39): the five values `main.rs`'s own `TASK_MEMBERS` array selects
/// among, in the same P1, P2, N1, N2, N3 order that array uses, restated
/// here as this module's own independent, hand-maintained agreement --
/// never a derivation -- for the reason this module's own doc comment
/// above explains (`main.rs` is a separate compilation unit this module
/// cannot import from at all). A value's membership in this set is
/// tested by exact byte equality alone (REQ-17): no case folding, no
/// trimming before comparison, no prefix or substring match and no
/// numeric-index acceptance.
const ACCEPTED_SELECTOR_NAMES: [&str; 5] = [
    "commit-fixture-target",
    "push-fixture-integration-branch",
    "merge-fixture-target",
    "push-main",
    "push-fixture-target",
];

/// One startup's own refusal (REQ-27, REQ-28; REQ-16): one field per
/// environment-named precondition. `None` means that precondition
/// resolved; `Some(description)` names the failing environment variable
/// and its refusal class, never a secret byte (REQ-29, REQ-19). All
/// three fields are always populated independently, so a caller can read
/// whichever failed, or which two, or all three, rather than only the
/// first (EC-5, extended to the third condition by REQ-16 and weakened
/// nowhere).
#[derive(Debug)]
pub struct StartupRefusal {
    /// `None` if the cohort precondition resolved; otherwise names
    /// [`SECRET_PATH_ENV_VAR`] and the reason it failed.
    pub cohort: Option<String>,
    /// `None` if the working-repository precondition resolved;
    /// otherwise names [`WORKING_REPO_ENV_VAR`] and the reason it
    /// failed.
    pub working_repo: Option<String>,
    /// `None` if the selector precondition resolved to a member of
    /// [`ACCEPTED_SELECTOR_NAMES`]; otherwise names
    /// [`TASK_SELECTOR_ENV_VAR`] and the reason it failed.
    pub selector: Option<String>,
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

/// Resolves the selector precondition from an already-read environment
/// VALUE (REQ-14 to REQ-18; build-order step six, ST6-3). Refuses fail
/// closed, naming [`TASK_SELECTOR_ENV_VAR`], on an absent, empty or
/// whitespace-only value, and never defaults to any member of
/// [`ACCEPTED_SELECTOR_NAMES`]. A present, non-blank value is then
/// checked for EXACT byte equality against the closed set: no case
/// folding, no trimming before that comparison, no prefix or substring
/// match, no numeric-index acceptance and no fuzzy match (REQ-17). On a
/// match, the only thing returned is the matching member's own index
/// into the array; nothing else is derived from the value (REQ-18).
fn resolve_selector(task_selector_value: Option<&str>) -> Result<usize, String> {
    let value = match task_selector_value {
        Some(value) if !value.trim().is_empty() => value,
        _ => {
            return Err(format!(
                "{TASK_SELECTOR_ENV_VAR} is not set, or is set to an empty or \
                 whitespace-only value; refusing rather than defaulting to any member of \
                 the closed array of accepted selector names"
            ));
        }
    };

    match ACCEPTED_SELECTOR_NAMES
        .iter()
        .position(|accepted| *accepted == value)
    {
        Some(index) => Ok(index),
        None => Err(format!(
            "{TASK_SELECTOR_ENV_VAR} is set to {value:?}, which is not an exact byte-equal \
             match against the closed set of accepted selector names; refusing rather than \
             falling back to a first, nearest or best-matching member"
        )),
    }
}

/// The pure precondition-resolving logic (REQ-27, REQ-15): all three
/// preconditions are resolved independently, and all three are always
/// attempted, so a caller sees which one failed, or which two, or all
/// three, never merely the first (EC-5, extended by REQ-16). Never
/// defaults on any failing condition (EC-3, EC-4, REQ-17). The selected
/// index (REQ-18) is the third element of the success tuple.
pub fn resolve_startup_preconditions(
    secret_path_value: Option<&str>,
    working_repo_path_value: Option<&str>,
    task_selector_value: Option<&str>,
) -> Result<(hierarchy_vor::VerifiedCohort, PathBuf, usize), StartupRefusal> {
    let cohort_result = resolve_cohort(secret_path_value);
    let working_repo_result = resolve_working_repo(working_repo_path_value);
    let selector_result = resolve_selector(task_selector_value);

    match (cohort_result, working_repo_result, selector_result) {
        (Ok(cohort), Ok(working_repo), Ok(selected_index)) => {
            Ok((cohort, working_repo, selected_index))
        }
        (cohort_result, working_repo_result, selector_result) => Err(StartupRefusal {
            cohort: cohort_result.err(),
            working_repo: working_repo_result.err(),
            selector: selector_result.err(),
        }),
    }
}

/// The one place in this crate the three environment variable NAMES
/// above are read from the real process environment (REQ-26, REQ-15):
/// reads all three, then delegates to [`resolve_startup_preconditions`].
/// `src/main.rs` calls this function alone; it never reads the
/// environment itself.
pub fn run() -> Result<(hierarchy_vor::VerifiedCohort, PathBuf, usize), StartupRefusal> {
    let secret_path_value = std::env::var(SECRET_PATH_ENV_VAR).ok();
    let working_repo_path_value = std::env::var(WORKING_REPO_ENV_VAR).ok();
    let task_selector_value = std::env::var(TASK_SELECTOR_ENV_VAR).ok();
    resolve_startup_preconditions(
        secret_path_value.as_deref(),
        working_repo_path_value.as_deref(),
        task_selector_value.as_deref(),
    )
}
