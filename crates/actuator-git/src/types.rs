//! The operation, outcome and refusal vocabularies (REQ-8, REQ-25). No logic
//! and no decision anywhere in this module: every item below is a plain,
//! closed data shape. `crate::argv` decides how an operation's argument
//! vector is built and validated; `crate::targets` decides whether a push
//! target is permitted; `crate::repo` decides whether a working repository
//! resolves; `crate::execute` decides what actually happens when the process
//! runs. This module decides none of that, exactly as
//! `plans/git-actuator-step-four.md` section 9.3 names its one
//! responsibility.

/// The actuator's closed, two-variant operation set (REQ-8). No third
/// operation exists and no variant is reserved for a future one: a real
/// third operation (a merge, per D108's own dogfooding text) is added as a
/// new variant when a real workflow needs it, per the spec's Open/Closed
/// analysis (section 9.1), never by widening one of these two.
///
/// Every exhaustive `match` over this type, in this crate and in
/// `himinbjorg`, has no wildcard arm: a future third variant forces every
/// match site to be revisited rather than silently folding into a catch-all
/// (mirroring EC-18's instruction for [`ActuationRefusal`]).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum GitOperation {
    /// A local commit. `message` is the commit message, validated (REQ-11)
    /// and placed in exactly one value position of the fixed argument shape
    /// `crate::argv` owns (REQ-9, REQ-13); it is never templated into a
    /// larger string, never written to a file this crate creates, and never
    /// passed through a shell.
    Commit {
        /// The commit message, in caller-supplied, unvalidated form. Validated
        /// before it reaches an argument vector.
        message: String,
    },
    /// A push. `remote` and `ref_name` are both validated individually
    /// (REQ-11) and then checked together, as a pair, against the permitted
    /// allowlist `crate::targets` owns (REQ-14).
    Push {
        /// The remote name, in caller-supplied, unvalidated form.
        remote: String,
        /// The ref name, in caller-supplied, unvalidated form.
        ref_name: String,
    },
}

/// A success outcome (REQ-25). Names the operation that ran and nothing it
/// did not observe: deliberately no commit identifier, because obtaining one
/// would require a third git operation REQ-8 forbids, and deliberately no
/// field derived from parsing git's own output (REQ-24). Both variants are
/// data free by construction, not merely by convention: a caller matching
/// either variant with no `{ .. }` pattern fails to compile the day a field
/// is ever added, which is itself the structural proof that no such field
/// exists today.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ActuationOutcome {
    /// The commit operation ran and the process exited zero.
    Committed,
    /// The push operation ran and the process exited zero.
    Pushed,
}

/// The actuator's closed refusal vocabulary (section 5.1, section 6). Every
/// variant that carries a `diagnostic` bounds its length before assignment
/// (REQ-24): the text may include captured, untrusted git output, and is
/// treated as diagnostic content only, never as a value any control-flow
/// decision is derived from, and never as a value any later reader should
/// treat as trusted.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ActuationRefusal {
    /// A caller-supplied string failed REQ-11's positive-match validation
    /// before any process was spawned: empty, beginning with a hyphen,
    /// containing a NUL byte, a newline, a carriage return, or exceeding the
    /// named length bound.
    InvalidArgument {
        /// A bounded, human-readable description of which value failed and why.
        diagnostic: String,
    },
    /// The push target (remote and ref, as a pair) is absent from the
    /// hardcoded permitted allowlist (REQ-14). This, not
    /// [`ActuationRefusal::ProtectedRef`], is the mechanism that blocks a
    /// push to `main` or `master`: their absence from the allowlist, not an
    /// enumeration of forbidden names (REQ-15).
    TargetNotPermitted {
        /// A bounded, human-readable description of the rejected remote/ref pair.
        diagnostic: String,
    },
    /// A named protected ref was matched. Defence in depth only (REQ-16):
    /// structurally unreachable given REQ-14 and REQ-15, and never the
    /// mechanism that protects `main` or `master`, following
    /// `DefinitionRefusal::EmptyIntersection`'s precedent of naming a
    /// defence-in-depth arm honestly rather than presenting it as load
    /// bearing. Must never be described anywhere as the protection.
    ProtectedRef {
        /// A bounded, human-readable description of the matched protected ref.
        diagnostic: String,
    },
    /// The working repository failed to resolve: the naming environment
    /// variable is absent or empty, the named path is missing, is not a
    /// directory, contains no git repository marker, or resolves inside this
    /// repository's own working tree (a development-time guard, not a
    /// deployment control; REQ-18, REQ-19).
    RepositoryResolution {
        /// A bounded, human-readable description of which resolution condition failed.
        diagnostic: String,
    },
    /// The `git` process failed to spawn (for example, the binary is absent
    /// from `PATH`). Never a fallback to a second candidate path (EC-1).
    SpawnFailed {
        /// A bounded, human-readable description of the spawn failure.
        diagnostic: String,
    },
    /// The spawned process did not exit within the bounded wall-clock limit
    /// (REQ-22) and was terminated. Carries no diagnostic text: the timeout
    /// itself is the whole of the information.
    Timeout,
    /// The process exited with a non-zero status, or with a status the
    /// platform reports as absent (a signalled process). Never a success and
    /// never a partial success (REQ-23).
    ExitStatus {
        /// A bounded, human-readable description of the exit status and any captured, untrusted output.
        diagnostic: String,
    },
    /// The partial-effect case (REQ-25, AC-27): a commit succeeded and the
    /// subsequent push refused. Reported neither as a success nor as nothing
    /// having happened: a local commit is a real effect that happened and
    /// must not be reported away.
    PartialEffect {
        /// A bounded, human-readable description of the partial effect: what succeeded and what then refused.
        diagnostic: String,
    },
}
