// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! The single positive-match validator (REQ-9, REQ-23 to REQ-26): the only
//! place in this crate a value received from the child is checked, on
//! `crates/actuator-git/src/argv.rs`'s own single-validator precedent.
//! Every check below is a permitted-shape check, never a forbidden-shape
//! check: this is invariant 3.5's discipline applied at a new boundary.
//! A value that does not affirmatively match every one of them is
//! refused, never sanitised, truncated, escaped, quote-wrapped, re-encoded
//! or repaired (REQ-26). Operates on an already line-parsed value: the
//! fixed line-oriented shape's own parsing (REQ-22) is `crate::invocation`'s
//! job, not this module's.

use crate::types::{CognitionMessage, SidecarRefusal};

/// This crate's own named maximum-length constant (REQ-24). Never read
/// from `actuator_git::argv::MAX_VALUE_LEN`, which this crate cannot see
/// (REQ-7 forbids depending on `actuator-git` at all): the two are an
/// agreement between independently owned constants, never a derivation, on
/// `context::TARGET_SCOPE`'s PE-4 precedent. No test in this crate asserts
/// that the two values agree.
pub(crate) const MAX_RECEIVED_VALUE_LEN: usize = 4_096;

/// True if `value` is empty once leading and trailing whitespace is
/// disregarded for the purpose of this one check only -- `.trim()` never
/// changes what is returned to a caller; it is used here purely to decide
/// whether the ENTIRE value is whitespace, never to strip, shorten or
/// otherwise alter the value itself.
fn is_whitespace_only(value: &str) -> bool {
    value.trim().is_empty()
}

/// The one positive-match validator (REQ-23). A received value is
/// returned unchanged, byte for byte, inside [`CognitionMessage`] if it
/// affirmatively satisfies every check below; otherwise the call refuses
/// with a diagnostic naming which check failed, built only from this
/// module's own fixed strings (REQ-25), never from any portion of `raw`
/// itself.
///
/// The policy is at least as strict as `argv.rs`'s `ValueKind::Message`
/// policy (REQ-24): non-empty, not whitespace only, at most
/// [`MAX_RECEIVED_VALUE_LEN`] bytes, no leading hyphen, no NUL byte, no
/// newline, no carriage return, and every character matching the positive
/// allowlist `is_ascii_graphic() || c == ' '`.
pub(crate) fn validate_received_message(raw: &str) -> Result<CognitionMessage, SidecarRefusal> {
    if raw.is_empty() {
        return Err(SidecarRefusal::new(
            "the received value is empty; refusing rather than accepting a value with no content",
        ));
    }
    if is_whitespace_only(raw) {
        return Err(SidecarRefusal::new(
            "the received value is whitespace only; refusing rather than accepting a value \
             with no visible content",
        ));
    }
    if raw.len() > MAX_RECEIVED_VALUE_LEN {
        return Err(SidecarRefusal::new(
            "the received value exceeds this crate's own maximum permitted length",
        ));
    }
    if raw.starts_with('-') {
        return Err(SidecarRefusal::new(
            "the received value begins with a hyphen; refusing, never escaped",
        ));
    }
    if raw.bytes().any(|b| b == 0) {
        return Err(SidecarRefusal::new(
            "the received value contains a NUL byte",
        ));
    }
    if raw.contains('\n') {
        return Err(SidecarRefusal::new(
            "the received value contains a newline",
        ));
    }
    if raw.contains('\r') {
        return Err(SidecarRefusal::new(
            "the received value contains a carriage return",
        ));
    }
    if !raw.chars().all(|c| c.is_ascii_graphic() || c == ' ') {
        return Err(SidecarRefusal::new(
            "the received value contains a character outside the permitted allowlist \
             (is_ascii_graphic() or the literal space)",
        ));
    }
    Ok(CognitionMessage::new(raw.to_string()))
}
