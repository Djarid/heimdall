//! The fixed argument shapes for the two [`crate::GitOperation`] variants,
//! the single value validator, the end-of-options separator placement and
//! the named length bound (REQ-9, REQ-11 to REQ-13, section 10 file 6 of
//! `.opencode/plans/git-actuator-step-four.md`).
//!
//! **This module decides one thing only** (section 9.3): given caller-supplied
//! strings, turn one operation into one fixed, validated argument vector.
//! Nothing here decides whether an operation is permitted (that is
//! `crate::targets`), nothing here resolves a working repository (that is
//! `crate::repo`), and nothing here spawns a process (that is `crate::execute`,
//! the only module in the workspace that touches `std::process`, REQ-7).
//!
//! **The validator is a positive-match allowlist, never a denylist** (REQ-11).
//! A caller-supplied string is refused unless it is explicitly permitted; no
//! character or shape is refused by name. This is deliberate: the corpus
//! sources named in section 15 of the spec (the `ultralytics/actions`
//! compromise, `tj-actions/branch-names` CVE-2023-49291, and the Home
//! Assistant branch-name review) each show a real incident in which a git ref
//! or branch name, itself restricted to git's own legal character set,
//! nonetheless achieved command execution once concatenated into a shell
//! command. Enumerating the metacharacter shapes those incidents used (`"`,
//! `;`, `$`, `{`, `}`, `(`, `)`, `&`, `,` and so on) as a denylist would be
//! exactly the blacklist trap invariant 3.5 names, one layer over: the next
//! unseen shape would pass silently. Instead, every character not explicitly
//! named in [`char_permitted`]'s allowlist is refused, so no enumeration of
//! forbidden shapes is needed or present anywhere in this module.
//!
//! **Two positions, one shared mechanism, two different policies** (section
//! 9.2 point 3). A commit message and a ref or remote name share the same
//! structural rule -- non-empty, no leading hyphen, no NUL byte, no newline,
//! no carriage return, at most [`MAX_VALUE_LEN`] bytes -- enforced by the one
//! function [`validate_value`]. What differs is the per-character allowlist
//! each position additionally requires, via [`ValueKind`]: a ref or remote
//! name is restricted to git's own conventional character set, while a commit
//! message is permitted the whole printable ASCII range plus the space,
//! still a positive-match allowlist (`is_ascii_graphic` in [`char_permitted`]),
//! because a message never reaches a shell and never occupies the REQ-14
//! target allowlist's position, so the structural checks alone (no leading
//! hyphen, no NUL byte, no newline, no carriage return, non-empty, bounded
//! length) remain its load-bearing defence. The mechanism (the structural
//! checks) is shared; the policy (which characters are permitted) is not,
//! following the spec's own instruction not to apply one position's rule to
//! the other.
//!
//! **The end-of-options separator (REQ-12).** `git push` documents its own
//! synopsis as `git push [<options>] [--] [<repository> [<refspec>...]]`: the
//! `--` separator is git's own supported way of guaranteeing that whatever
//! follows is never read as an option, whatever it contains. [`build_push_argv`]
//! places one before `remote`, the first value position, so neither `remote`
//! nor `ref_name` can occupy an option position even in principle. `git
//! commit`'s message value has no comparable separate value position to
//! guard this way: `-m` always consumes the very next argument vector entry
//! as its value, unconditionally, so the load-bearing defence for the commit
//! message is REQ-11's leading-hyphen refusal itself, exactly as REQ-12 names
//! it ("refused by REQ-11 rather than escaped").

use crate::types::ActuationRefusal;

/// The named length bound (REQ-11): the maximum permitted byte length of any
/// caller-supplied value before it reaches an argument vector. Referenced
/// everywhere a length check is needed; never repeated as a literal
/// elsewhere in this crate (section 9.2, "constants, never repeated
/// literals").
pub(crate) const MAX_VALUE_LEN: usize = 4_096;

/// Which per-position character rule a value must additionally satisfy,
/// beyond the shared structural checks every value position shares (REQ-11).
/// The mechanism is shared ([`validate_value`] itself); the policy (which
/// characters are permitted) is not, one variant per position kind.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum ValueKind {
    /// A commit message (REQ-13).
    Message,
    /// A remote name or a ref name (REQ-14's allowlist reads both, as a
    /// pair, once this module's validation has already passed).
    RefOrRemote,
}

/// The positive-match character allowlist for `kind` (REQ-11). Never a
/// denylist: a character not explicitly named here is refused, including
/// every shell-metacharacter shape named in this module's own header, none
/// of which needs enumerating because none of them is ever granted.
fn char_permitted(kind: ValueKind, c: char) -> bool {
    match kind {
        // A commit message never reaches a shell (`crate::execute` spawns
        // the binary directly, REQ-10) and never occupies the REQ-14 target
        // allowlist's position, so its policy can permit the whole printable
        // ASCII range (`is_ascii_graphic`, 0x21 to 0x7E, plus the space
        // 0x20) without weakening any invariant: the structural checks in
        // [`validate_value`] (no leading hyphen, no NUL byte, no newline, no
        // carriage return, non-empty, bounded length) remain the load-bearing
        // defence for this position, exactly as this module's header
        // describes (REQ-11, REQ-12).
        ValueKind::Message => c.is_ascii_graphic() || c == ' ',
        // A ref or remote name's policy stays exactly as narrow as before:
        // it is additionally checked against the REQ-14 target allowlist
        // once this module's validation passes, but this module's own
        // character policy is still the first line of defence against the
        // AC-13 injection-payload shapes, so it is never widened.
        ValueKind::RefOrRemote => c.is_ascii_alphanumeric() || matches!(c, '-' | '_' | '.' | '/'),
    }
}

/// Builds an [`ActuationRefusal::InvalidArgument`] with a bounded,
/// human-readable diagnostic naming which value failed and why. The inputs
/// to `label` are this module's own fixed strings and `reason` is always one
/// of this module's own fixed strings too, so the resulting diagnostic is
/// bounded by construction; it never carries untrusted, unbounded content
/// (that concern is REQ-24's, for captured process output, a different
/// module's problem).
fn invalid(label: &str, reason: &str) -> ActuationRefusal {
    ActuationRefusal::InvalidArgument {
        diagnostic: format!("{label} {reason}"),
    }
}

/// The single value validator (REQ-11). The only place in this crate a
/// caller-supplied string is checked before it can reach an argument vector.
/// Positive match only: every check below is a permitted-shape check, not a
/// forbidden-shape check, and a value that does not affirmatively pass every
/// one of them is refused.
fn validate_value(kind: ValueKind, label: &str, value: &str) -> Result<(), ActuationRefusal> {
    if value.is_empty() {
        return Err(invalid(label, "must not be empty"));
    }
    if value.len() > MAX_VALUE_LEN {
        return Err(invalid(label, "exceeds the maximum permitted length"));
    }
    if value.starts_with('-') {
        return Err(invalid(
            label,
            "must not begin with a hyphen (refused, never escaped, REQ-12)",
        ));
    }
    if value.bytes().any(|b| b == 0) {
        return Err(invalid(label, "must not contain a NUL byte"));
    }
    if value.contains('\n') {
        return Err(invalid(label, "must not contain a newline"));
    }
    if value.contains('\r') {
        return Err(invalid(label, "must not contain a carriage return"));
    }
    if !value.chars().all(|c| char_permitted(kind, c)) {
        return Err(invalid(
            label,
            "contains a character outside the permitted allowlist",
        ));
    }
    Ok(())
}

/// The commit operation's fixed argument shape (REQ-9): exactly `["commit",
/// "-m", <message>]`. `message` occupies exactly one value position of this
/// one fixed shape (REQ-13): it is validated by [`validate_value`] before
/// this function ever returns it in the vector, it is never templated into a
/// larger string, never written to a file this crate creates, and never
/// passed through a shell (`crate::execute` spawns the binary directly, per
/// REQ-10).
pub(crate) fn build_commit_argv(message: &str) -> Result<Vec<String>, ActuationRefusal> {
    validate_value(ValueKind::Message, "commit message", message)?;
    Ok(vec![
        "commit".to_string(),
        "-m".to_string(),
        message.to_string(),
    ])
}

/// The push operation's fixed argument shape (REQ-9): exactly `["push", "--",
/// <remote>, <ref_name>]`. `remote` and `ref_name` are each validated
/// individually by [`validate_value`] before this function returns (REQ-11);
/// whether the pair is a *permitted* target is `crate::targets`'s question,
/// not this module's (checked strictly afterwards, by the assumed check order
/// this crate's own tests document). The `--` end-of-options separator
/// (REQ-12) is placed before `remote`, the first value position, per this
/// module's own header.
pub(crate) fn build_push_argv(
    remote: &str,
    ref_name: &str,
) -> Result<Vec<String>, ActuationRefusal> {
    validate_value(ValueKind::RefOrRemote, "remote name", remote)?;
    validate_value(ValueKind::RefOrRemote, "ref name", ref_name)?;
    Ok(vec![
        "push".to_string(),
        "--".to_string(),
        remote.to_string(),
        ref_name.to_string(),
    ])
}
