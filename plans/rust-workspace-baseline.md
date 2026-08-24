# Rust workspace baseline

**Author:** Jason Huxley
**Date:** August 2026
**Version:** 0.1 (draft)
**Status:** the standing baseline the repository's first Rust crate established

---

## 1. Purpose

`crates/boundary-gjoll/` (D109) is the repository's first Rust crate, built as build-order
step one of `plans/synthesis-bootstrap.md` (D108). This document records the workspace
layout, the toolchain pin, the minimum supported Rust version (MSRV), the dependency
posture, the module-layering pattern, the test-isolation pattern and the vector-parity
mechanism it established, so steps two to seven of D108's build order inherit one set of
conventions rather than each re-deciding them. It is a cross-cutting document, not a
per-component one: see `plans/dd/index.md` section 1's cross-reference note.

## 2. Workspace layout

A single Cargo workspace at the repository root:

- `Cargo.toml`: the workspace manifest. `resolver = "3"`, one member
  (`crates/boundary-gjoll`), and a `[workspace.package]` table setting
  `edition = "2024"` and `rust-version = "1.85"`. A future crate joins this workspace as a
  new member rather than starting its own.
- `rust-toolchain.toml`: pins the toolchain (section 3). Applies repository-wide.
- `Cargo.lock`: committed, covering the dev-dependency graph of every workspace member.
- `crates/<name>/`: one directory per crate, each with its own `Cargo.toml` inheriting
  `edition` and `rust-version` from the workspace.

Rust build output is ignored by `.gitignore`; nothing under `target/` is tracked.

## 3. Toolchain pin and MSRV

`rust-toolchain.toml` pins `channel = "1.98.0"`, with `rustfmt` and `clippy` as components
and `profile = "minimal"`. This is the toolchain verified present on the build machine
(`cargo 1.98.0`, `rustc 1.98.0`), observed rather than assumed.

The workspace's `rust-version` is `1.85`, the edition-2024 floor, and is distinct from the
pinned channel: `rust-version` states the minimum a crate is written to compile against,
while the pinned channel is the version this repository's own builds and tests actually
run on. A future crate may rely on a language feature newer than 1.85 only if the workspace
`rust-version` is raised deliberately, which is a decision worth its own `DECISIONS.md` row
if it narrows what can build this repository.

## 4. Dependency posture

`boundary-gjoll`'s `[dependencies]` table is empty, and carries no `license` field (the
licence question is OPEN; see section 7). Dev-dependencies are permitted for test-only
concerns (in this crate, JSON vector parsing) and must be version-pinned exactly, not
range-pinned, so a dependency upgrade is a deliberate, reviewed edit rather than a silent
drift on the next build.

This is the Rust analogue of `ontology/nornir/symbolic_guard.py`'s structural enforcement
of invariant 3.1, and of D105 row H5: with no runtime dependency present, there is no crate
through which a model call or a network call could be reached. A mechanical check
(`ontology/tests/rust_gate_harness.py::check_dependency_posture`) asserts the
`[dependencies]` table stays empty, failing loudly if a runtime dependency is added, and
stating the dev-dependency exemption in its own output. Adding a runtime dependency to a
future crate's gate-adjacent path is a deliberate trust-boundary decision requiring its own
`DECISIONS.md` row, exactly as `ALLOWED_IMPORT_ROOTS` treats a new Python import root (D71).

Every crate root carries `#![forbid(unsafe_code)]`.

## 5. The two-layer module pattern

`boundary-gjoll` splits into four modules, following a Single Responsibility discipline
worth reusing:

- **`types`**: shared value shapes, no logic.
- **`rule`**: a pure, total core carrying the load-bearing decision logic. It receives the
  narrowest input that can express the decision, denied anything that would let it be
  fooled (in this crate, the registry, the agent sink set, a self-asserted safety flag and
  effect observations are all structurally unreachable from the rule).
- **`declaration`**: contracts and validation, separated out so the module that validates
  input has one reason to change (a new validation condition) distinct from the module that
  derives a verdict (a new derivation source).
- **`consequentiality`** (or the equivalent shell for a future crate): the mandatory,
  registry-backed entry point that validates, derives and then delegates to the rule.

The rule core exposes a verdict or decision type constructible only from inside the crate
(`pub(crate)`, no public constructor, no public `From` conversion, no `cfg` escape hatch a
downstream caller could enable). This turns a "the rule does not trust a self-asserted
input" claim into a property of the type system rather than of review, and it is why the
crate's public surface can stay narrow: a caller reaches the decision logic only through
the mandatory shell, never around it.

## 6. Test-isolation pattern

Test code and implementation code live in separate files in separate directories, so the
implementing agent and the test-writing agent never edit the same file:

- **Unit tests** (needing access to `pub(crate)` items) live in `unit_tests/`, a sibling of
  `src/` and of `tests/`. They are attached to the crate by exactly one declaration in
  `lib.rs`, of the form
  `#[cfg(test)] #[path = "../unit_tests/<name>.rs"] mod <name>;`. That declaration is the
  only test-related construct permitted anywhere under `src/`: no `#[test]`, no
  `mod tests`, no fixture and no double may appear in an implementation file. Because
  `cfg(test)` is set only when Cargo compiles the crate's own test harness, this does not
  widen the visibility a downstream consumer of the crate sees.
- **Integration tests** (proving the public API alone is sufficient) live under `tests/`,
  compiled as an external crate, importing only public items.

The ownership boundary this creates is directory-level and mechanically checkable: a grep
for `#[test]`, `mod tests` or `#[cfg(test)]` over `src/` should return exactly the `lib.rs`
declaration lines and nothing else, and no file should appear under both `src/` and either
test directory.

## 7. The vector-parity mechanism

Where a Rust crate re-expresses existing Python behaviour, correctness is checked from day
one by replaying golden vectors captured from the Python reference, not by writing Rust
tests against an assumed specification:

- A Python exporter (`ontology/tools/export_gate_vectors.py` for this crate) wraps the
  Python reference's own public entry point, captures every real call the existing test
  harnesses make, and derives each vector's expected result by calling the Python's own
  functions rather than reimplementing them.
- The emitted vector file is committed (small, textual and diffable, inspectable without a
  working Rust toolchain), carries a schema version and SHA-256 digests of every Python
  source file the re-expression's correctness depends on.
- A standalone sub-harness (`ontology/tests/rust_gate_harness.py` for this crate) checks
  digest drift first, dependency posture second and the Rust test run third, skipping
  loudly only when no Rust toolchain is present, following
  `ontology/tests/memgraph_integration_harness.py`'s skip-if-absent precedent. A present
  toolchain whose test run fails is always fatal, never laundered into a skip.
- The sub-harness folds into the main Python suite (`ontology/tests/harness.py`) as an
  additive obligation, following the exact shape of an existing fatal-gated obligation
  (`run_effect_probe`), so a Rust re-expression's drift or failure is visible in the same
  report as every other obligation.

A digest mismatch is fatal regardless of whether a Rust toolchain is present, because drift
is a fact about repository state, not about the toolchain: a reviewer without Rust installed
must still be able to tell that the vectors are stale.

## 8. What this baseline does not decide

This document records conventions a crate should follow; it does not itself authorise or
build anything. In particular it does not:

- Decide which future step of D108's build order builds next, or what that crate does.
- Settle the code licence (section 4), which stays OPEN.
- Extend the vector-parity mechanism to a component with no existing Python reference to
  replay against; a genuinely new Rust component needs its own test strategy.

---

## Licence

Part of the Heimdall specification, licensed under CC-BY-SA-4.0. See `LICENSE.md`.
