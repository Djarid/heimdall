//! Value shapes only (REQ-9): the crate's one validated-message type and
//! its one refusal type. No logic beyond construction and reading lives
//! here; every check that decides whether a value is accepted at all is
//! `crate::validation`'s job, and every spawn, wait or environment read is
//! `crate::invocation`'s job.

/// The validated commit-message value (REQ-10). Carries exactly the bytes
/// a call to [`crate::obtain_message`] received from the sidecar and passed
/// every one of `crate::validation::validate_received_message`'s checks,
/// unchanged, byte for byte (REQ-26): this type never holds a sanitised,
/// truncated or otherwise repaired copy of anything.
///
/// **No public constructor and no public `From` conversion (REQ-10).** The
/// only way to mint one is [`new`](CognitionMessage::new), `pub(crate)` so
/// only this crate's own validator can call it, on
/// `boundary_gjoll::rule::ConsequentialityVerdict`'s own containment
/// precedent for the identical property: a downstream caller depending on
/// this crate as a library has no path to a value of this type except
/// through [`crate::obtain_message`], and therefore through
/// [`crate::validation::validate_received_message`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CognitionMessage(String);

impl CognitionMessage {
    /// `pub(crate)`: only `crate::validation`'s own validator calls this.
    /// Not exported, not `pub`, and no `From<String>` implementation
    /// exists anywhere in this crate (REQ-10).
    pub(crate) fn new(validated_message: String) -> Self {
        Self(validated_message)
    }

    /// The one public reader REQ-10 names.
    pub fn as_str(&self) -> &str {
        &self.0
    }
}

/// The one refusal type (REQ-10). Every one of REQ-31's eleven refusal
/// conditions, and every one of `crate::validation`'s checks, produces one
/// of these rather than any other shape.
///
/// `diagnostic` is bounded and built only from this crate's own fixed
/// strings (REQ-25): no portion of a value received from the sidecar, and
/// no portion of any environment value's contents beyond the path itself,
/// ever appears in it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SidecarRefusal {
    pub diagnostic: String,
}

impl SidecarRefusal {
    /// Builds a refusal from one of this crate's own fixed diagnostic
    /// strings (REQ-25). `pub(crate)`: an external caller cannot construct
    /// one directly, only receive one from [`crate::obtain_message`].
    pub(crate) fn new(diagnostic: &'static str) -> Self {
        Self {
            diagnostic: diagnostic.to_string(),
        }
    }
}
