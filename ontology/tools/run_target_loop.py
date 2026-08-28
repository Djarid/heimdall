"""The out-of-band target-loop driver (build-order step six, ST6-4 and ST6-5,
`.opencode/plans/build-order-step-six-spec.md` section 4.4, REQ-23 to
REQ-30; section 5.4, AC-25 to AC-35; section 6.2, EC-25 to EC-33; section
9.1's Single Responsibility argument).

Run from the repository root, once the binary is already built:

    cargo build -p process-engine --release
    HEIMDALL_COHORT_SECRET_FILE=/path/outside/the/repo/secret \\
        python3 -m ontology.tools.run_target_loop

This is a standalone, operator-invoked tool (REQ-23). It is not a test and
not a library: nothing under `ontology/tests/` imports or invokes it
(REQ-29), and it is never invoked by `ontology/tests/harness.py`,
`ontology/tests/rust_target_loop_harness.py` or any Rust test (REQ-29,
REQ-37). It creates real repositories and causes a real commit and a real
push against a real (throwaway) remote, so running it is a deliberate,
separate act from running the Python test suite, exactly as
`ontology/tools/export_cohort_vectors.py`'s own authoring mode is a
deliberate, separate act from running `ontology/tests/rust_cohort_harness.py`.

Why this file owns exactly fixture provisioning and nothing else (section
9.1's Single Responsibility argument, restated here because this is the
file it governs). This file changes when the FIXTURE changes: a different
branch name, a different file to stage, a different remote layout, a
different way of provisioning identity. None of that is a change to what
Heimdall is permitted to do. `crates/process-engine/` changes when the
sequence, the proposal shape or the startup contract changes; none of
that is a change to how a fixture is provisioned. Putting fixture setup
inside the binary would give it a second reason to change, would breach
the engine's own no-filesystem-write property, and would put a second
`std::process` site in the workspace. Putting execution inside this
driver would be worse: it would make Python part of the governed
pipeline, and it would move the one thing that must be compiled and
unmodifiable (the gate, the witness, the actuator) into the one layer
that is neither. This file therefore does exactly eight things, in this
fixed order (REQ-24), and nothing beyond them (REQ-25):

  1. Resolve a fixture root outside heimdall's own working tree, and
     refuse before creating anything if it is not (REQ-24 item 1). Both
     sides are canonicalised (`Path.resolve()`, which resolves symbolic
     links) before the containment comparison, because the conventional
     macOS temporary-directory prefix is itself a symbolic link into
     another prefix (EC-25): a naive string comparison would produce a
     false result in either direction. If the resolved fixture root
     already exists, this driver refuses, naming the path; it never
     reuses and never deletes an existing directory (REQ-30, AC-35), and
     it holds no lock, so it does not make two concurrent runs against
     the same fixture safe (EC-26).
  2. Create a bare repository acting as `origin` inside the fixture root
     (`git init --bare`).
  3. Clone it into a working repository alongside (`git clone`).
  4. Set `user.name`, `user.email` and `commit.gpgsign=false` in the
     clone's OWN, repository-local configuration -- never with `--global`
     -- so the run depends on the host's global git configuration for
     neither identity nor signing (REQ-24 item 4, EC-27):
     `actuator-git`'s own `execute.rs` calls `env_clear()` and then
     forwards `HOME`, so the spawned git process CAN read the host's
     global configuration, and repository-local configuration overrides
     it.
  5. Check out `fixture-integration-branch` in the clone
     (`git checkout -b`), so the branch the push names is the branch the
     commit lands on (REQ-24 item 5, EC-28): a clone of a freshly
     initialised bare repository has an unborn branch and no remote
     branch to track, and the actuator's fixed push shape
     (`["push", "--", <remote>, <ref_name>]`) creates the remote branch
     of that name on first push, needing no upstream configuration.
  6. Write one small fixture file into the clone and stage it with
     `git add`. This is the WHOLE of the staging mechanism (REQ-24 item
     6), and it completes before the engine binary is invoked even once.
     Governed staging is deferred to build-order step seven as a named
     obligation (`plans/dd/process-engine.md` section 12's new row); this
     driver's own `git add` is deliberately out of band and never
     pretends otherwise.
  7. Invoke the already-built Rust binary five times, once per accepted
     selector value, in the fixed order P1 (`commit-fixture-target`), P2
     (`push-fixture-integration-branch`), N1 (`merge-fixture-target`), N2
     (`push-main`), N3 (`push-fixture-target`) -- REQ-24 item 7. Each
     invocation is a SEPARATE subprocess with `HEIMDALL_ENGINE_TASK`,
     `HEIMDALL_COHORT_SECRET_FILE` and `HEIMDALL_ACTUATOR_GIT_WORKING_REPO`
     (pointing at the clone) exported in its environment. This driver
     does NOT inspect one invocation's outcome to decide whether to run
     the next (REQ-25, EC-33): all five run regardless, because
     inspecting an outcome to decide what to do next is adjudication, and
     this driver adjudicates nothing. In particular, P2's push has
     nothing new to push unless P1's commit succeeded (EC-33); this
     driver does not encode that dependency, it only lets the transcript
     show both outcomes so a reader can see it.
  8. Capture each invocation's exit code, standard output and standard
     error. After all five, read `git log` and `git ls-remote` from the
     BARE origin (read-only), and emit the evidence transcript to
     standard output always, and additionally to a file only when an
     explicit `--output` path is supplied on the command line (REQ-27):
     this driver never writes inside heimdall's own working tree by
     default.

Explicit non-responsibilities (REQ-25), each checkable by reading this
file alone:

  - This driver never runs a commit, a push or a merge operation itself.
    The only steps it takes against git are `init --bare`, `clone`,
    `config`, `checkout -b`, `add`, and the read-only `log`/`ls-remote`
    against the bare origin. The only commit and the only push in the
    whole proof are the actuator's own, reached through the binary this
    driver merely invokes.
  - It adjudicates nothing: no read of any cohort, sink registry, scope
    or allowlist anywhere in this file; no branch on whether an action is
    permitted; no inspection of an outcome to decide what to do next.
  - It holds no expectation: no expected exit code, no expected outcome
    string, no pass/fail verdict, no comparison of an observed outcome
    against an expected one, anywhere in this file. Its own exit code
    (see `main` below) reflects only whether its own provisioning and its
    five invocations completed AS OPERATIONS -- it is 0 once all five
    have run, regardless of what their five outcomes were, and non-zero
    only when a provisioning step or an invocation's own subprocess spawn
    failed operationally (REQ-25, AC-30). It never reflects whether an
    outcome matched anything, because it holds nothing to match against.
  - It creates, generates, derives and embeds no secret material of any
    kind, and it prints no byte of any secret. `HEIMDALL_COHORT_SECRET_FILE`
    is read from this driver's OWN environment as a path VALUE ONLY --
    checked for presence and non-emptiness, never opened, never read as
    file content -- and that same unread path string is forwarded
    verbatim into each of the five invocations' own environments (REQ-26).
    If it is absent or empty in this driver's own environment, this
    driver refuses fail closed, naming the variable, before creating any
    fixture (REQ-26, AC-31): it never invents a path and never searches
    the filesystem for a candidate.
  - It writes nothing inside heimdall's own working tree by default
    (REQ-27, AC-32): the fixture root is asserted to be outside that tree
    before anything is created, and the transcript goes to standard
    output always, and to a file only when `--output` is supplied.

The engine binary's own path (an open design choice REQ-24 leaves to the
implementer, documented here per the delegation's own instruction). This
driver assumes the binary has ALREADY been built -- it does not invoke
`cargo` itself, because building is not fixture provisioning and giving
this file a second reason to change (a build-system change) would
undermine the very single-responsibility argument section 9.1 makes for
why this split exists at all. By default it looks for the binary at
`<repo root>/target/release/process-engine` (the workspace's own default
`cargo build --release` output location); `--engine-binary` overrides
this with an explicit path. If neither locates an existing file, this
driver refuses, naming the path and suggesting the `cargo build`
invocation, before creating any fixture.

What this file's own exit code does and does not mean (REQ-25, AC-30),
restated once more because it is easy to misread: 0 means every
provisioning step succeeded and all five subprocess invocations of the
engine binary were spawned and ran to completion -- it says NOTHING about
what those five invocations' own exit codes were. Reading the five
observed exit codes and outcomes against
`.opencode/plans/build-order-step-six-spec.md` REQ-7's expectation table
is the reviewer's job, done by hand against the printed transcript, for
`TARGET_LOOP_EVIDENCE.md` (REQ-55) -- never this driver's own job, and
never a comparison this file performs.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Mirrored, byte for byte, from `crates/hierarchy-vor/src/authoriser.rs`'s
# `SECRET_PATH_ENV_VAR` and `crates/process-engine/src/startup.rs`'s own
# constant of the same name and value (section 2, baseline table). This
# driver never reads this file's CONTENTS (REQ-25, REQ-26): it only checks
# that the variable naming it is present and non-empty in its own
# environment, then forwards that same path value, unread, into each of
# the five invocations below.
SECRET_PATH_ENV_VAR = "HEIMDALL_COHORT_SECRET_FILE"

# Mirrored from `crates/actuator-git/src/repo.rs`'s `WORKING_REPO_ENV_VAR`.
# This driver sets this one itself, pointed at the clone it just
# provisioned; it never reads it from its own environment.
WORKING_REPO_ENV_VAR = "HEIMDALL_ACTUATOR_GIT_WORKING_REPO"

# Mirrored from `crates/process-engine/src/startup.rs`'s
# `TASK_SELECTOR_ENV_VAR`. This driver sets this one itself, once per
# invocation, to the selector value currently being run.
TASK_SELECTOR_ENV_VAR = "HEIMDALL_ENGINE_TASK"

# REQ-6's table / REQ-11's derivation rule, in the fixed order REQ-24 item
# 7 requires: P1, P2, N1, N2, N3. This driver names selector VALUES only
# (an index-selecting string the binary's own closed compile-time set
# accepts); it supplies nothing else to any of the five proposals, on
# `crates/process-engine/src/startup.rs`'s own REQ-18 property.
SELECTOR_ORDER: "tuple[str, ...]" = (
    "commit-fixture-target",
    "push-fixture-integration-branch",
    "merge-fixture-target",
    "push-main",
    "push-fixture-target",
)

# REQ-24 item 5: the branch the push names must be the branch the commit
# lands on.
INTEGRATION_BRANCH = "fixture-integration-branch"

# This driver's default assumption about where the already-built binary
# lives (documented above in the module docstring): the workspace's own
# default `cargo build -p process-engine --release` output location.
# `--engine-binary` overrides this.
DEFAULT_ENGINE_BINARY = REPO_ROOT / "target" / "release" / "process-engine"

# REQ-24 item 6: the whole of the staging mechanism is one small fixture
# file, written once, staged once, before the binary is ever invoked.
FIXTURE_FILE_NAME = "fixture-content.txt"

# A placeholder identity, deliberately using the `.invalid` top-level
# domain (RFC 2606) so it can never resolve to, or be mistaken for, a real
# address. Set repository-locally in the clone (REQ-24 item 4), never
# with `--global`.
FIXTURE_USER_NAME = "Heimdall Target Loop Fixture"
FIXTURE_USER_EMAIL = "target-loop-fixture@heimdall.invalid"


class DriverError(RuntimeError):
    """Raised on an OPERATIONAL failure of this driver's own provisioning
    or invocation steps (a git command failing, a required environment
    variable absent, the engine binary missing, a subprocess failing to
    spawn). Never raised because an invocation's own outcome was
    unexpected: this driver holds no expectation to be violated (REQ-25).
    """


# ---------------------------------------------------------------------------------
# REQ-26: the secret path, read as a path value only, never opened.
# ---------------------------------------------------------------------------------


def require_fixture_secret_path() -> str:
    """Reads `HEIMDALL_COHORT_SECRET_FILE` from this driver's own
    environment as a path VALUE. Refuses fail closed, naming the
    variable, if it is absent or empty, before this driver creates any
    fixture (REQ-26, AC-31). Never opens the file this path names; never
    invents a path; never searches the filesystem for a candidate."""
    value = os.environ.get(SECRET_PATH_ENV_VAR, "")
    if not value:
        raise DriverError(
            f"{SECRET_PATH_ENV_VAR} is not set, or is set to an empty value, in this "
            f"driver's own environment; refusing before creating any fixture (REQ-26). "
            f"This driver never invents a path and never searches the filesystem for a "
            f"candidate secret; it only forwards the value of this variable, unread, to "
            f"each of the five invocations below."
        )
    return value


# ---------------------------------------------------------------------------------
# The engine binary's own path (an open design choice, documented in the
# module docstring above).
# ---------------------------------------------------------------------------------


def resolve_engine_binary(cli_value: "str | None") -> Path:
    """Resolves the already-built engine binary's path: `cli_value` if
    supplied, else `DEFAULT_ENGINE_BINARY`. Refuses, naming the path and
    suggesting the build command, if the result does not exist. This
    driver never invokes `cargo` itself (module docstring)."""
    candidate = Path(cli_value).resolve() if cli_value else DEFAULT_ENGINE_BINARY
    if not candidate.is_file():
        raise DriverError(
            f"the engine binary at {candidate} does not exist. This driver invokes an "
            f"already-built binary; it does not build one itself. Build it first, for "
            f"example with `cargo build -p process-engine --release` from the "
            f"repository root, or pass --engine-binary pointing at an existing build."
        )
    return candidate


# ---------------------------------------------------------------------------------
# REQ-24 item 1, EC-25: the fixture root's own resolution and
# non-containment assertion.
# ---------------------------------------------------------------------------------


def default_fixture_root() -> Path:
    """A fresh, timestamped default under the platform's own temporary
    directory, so a run with no `--fixture-root` supplied does not
    collide with a prior run's own fixture (REQ-30's own refusal is about
    a genuinely REUSED path, never about this driver silently generating
    one that collides)."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    return Path(tempfile.gettempdir()) / f"heimdall-target-loop-fixture-{stamp}-{os.getpid()}"


def assert_fixture_root_outside_repository(
    fixture_root: Path, repo_root: Path = REPO_ROOT
) -> Path:
    """Canonicalises both `fixture_root` and `repo_root` (`Path.resolve()`,
    which resolves symbolic links on both sides) and refuses if the
    fixture root's canonical form is inside heimdall's canonical root
    (REQ-24 item 1, EC-25). Returns the fixture root's own canonical
    form, which every later step operates on, so a symlinked temporary
    prefix (the macOS convention) is resolved exactly once and
    consistently thereafter."""
    canonical_fixture = fixture_root.resolve()
    canonical_repo = repo_root.resolve()
    if canonical_fixture == canonical_repo or canonical_repo in canonical_fixture.parents:
        raise DriverError(
            f"the fixture root {fixture_root} resolves, after canonicalising both sides "
            f"and resolving symbolic links on each, to {canonical_fixture}, which is "
            f"inside heimdall's own canonical working tree ({canonical_repo}). Refusing "
            f"before creating anything (REQ-24 item 1, EC-25): the actuator's own "
            f"working-repository guard refuses a path inside this tree, and this driver "
            f"must not put the fixture somewhere that guard would trip."
        )
    return canonical_fixture


def assert_fixture_root_absent(canonical_fixture_root: Path) -> None:
    """Refuses, naming the path, if the resolved fixture root already
    exists. Never reuses it and never deletes it (REQ-30, AC-35)."""
    if canonical_fixture_root.exists():
        raise DriverError(
            f"the fixture root {canonical_fixture_root} already exists. Refusing "
            f"rather than reusing or deleting it (REQ-30): this driver holds no lock "
            f"and does not make two concurrent runs against the same fixture safe "
            f"(EC-26); choose a fresh --fixture-root."
        )


# ---------------------------------------------------------------------------------
# Small process-spawning helpers. No commit, no push and no merge
# operation is ever named in an argument list anywhere in this module
# (REQ-25): only init --bare, clone, config, checkout -b, add, and the
# read-only log/ls-remote pair against the bare origin.
# ---------------------------------------------------------------------------------


def _run(args: "list[str]", cwd: "Path | None" = None) -> "subprocess.CompletedProcess[str]":
    """Spawns `args`, capturing standard output and standard error as
    text, never raising on a non-zero exit (a non-zero exit from a
    READ-ONLY step, such as the git log / ls-remote pair, is recorded in
    the transcript, never treated as this driver's own operational
    failure). Raises `DriverError` only if the subprocess could not be
    spawned at all (for example, `git` absent from `PATH`), which IS an
    operational failure of this driver's own invocation step."""
    try:
        return subprocess.run(
            args, cwd=str(cwd) if cwd is not None else None, capture_output=True, text=True
        )
    except OSError as exc:
        raise DriverError(
            f"failed to spawn {args!r} ({exc}); this is an operational failure of this "
            f"driver's own invocation step, never an adjudication over any outcome "
            f"(REQ-25)"
        ) from exc


def _run_checked(args: "list[str]", cwd: "Path | None" = None, *, step: str = "") -> None:
    """As `_run`, but raises `DriverError` on a non-zero exit too. Used
    only for this driver's own PROVISIONING steps (REQ-24 items 2 to 6),
    each of which must succeed for the fixture to be usable at all; never
    used for reading the bare origin's own history afterwards (REQ-24
    item 8), which records whatever it finds."""
    result = _run(args, cwd=cwd)
    if result.returncode != 0:
        raise DriverError(
            f"provisioning step {step!r} failed: {args!r} exited {result.returncode} "
            f"in {cwd}; stdout={result.stdout!r} stderr={result.stderr!r}"
        )


# ---------------------------------------------------------------------------------
# REQ-24 items 2 to 6: fixture provisioning.
# ---------------------------------------------------------------------------------


def init_bare_origin(bare_dir: Path) -> None:
    """REQ-24 item 2. `git init --bare` creates `bare_dir` itself if it
    does not already exist."""
    _run_checked(["git", "init", "--bare", str(bare_dir)], step="init --bare")


def clone_origin(bare_dir: Path, clone_dir: Path) -> None:
    """REQ-24 item 3. `git clone` creates `clone_dir` itself."""
    _run_checked(["git", "clone", str(bare_dir), str(clone_dir)], step="clone")


def configure_repository_local_identity(clone_dir: Path) -> None:
    """REQ-24 item 4, EC-27: repository-local `user.name`, `user.email`
    and `commit.gpgsign=false`, never `--global`, so the run depends on
    the host's global git configuration for neither identity nor
    signing."""
    _run_checked(
        ["git", "config", "user.name", FIXTURE_USER_NAME], cwd=clone_dir, step="config user.name"
    )
    _run_checked(
        ["git", "config", "user.email", FIXTURE_USER_EMAIL],
        cwd=clone_dir,
        step="config user.email",
    )
    _run_checked(
        ["git", "config", "commit.gpgsign", "false"],
        cwd=clone_dir,
        step="config commit.gpgsign",
    )


def checkout_integration_branch(clone_dir: Path) -> None:
    """REQ-24 item 5, EC-28: check out the branch the push will name, so
    the branch the push names is the branch the commit lands on."""
    _run_checked(
        ["git", "checkout", "-b", INTEGRATION_BRANCH], cwd=clone_dir, step="checkout -b"
    )


def stage_fixture_file(clone_dir: Path) -> Path:
    """REQ-24 item 6: the whole of the staging mechanism. Writes one
    small fixture file naming this driver and the moment it ran (so
    repeated runs against different fixture roots are each
    distinguishable in `git log`), and stages it with `git add`. This
    completes before the engine binary is invoked even once."""
    fixture_file = clone_dir / FIXTURE_FILE_NAME
    stamp = datetime.now(timezone.utc).isoformat()
    fixture_file.write_text(
        "heimdall build-order step six target-loop fixture content.\n"
        f"Written by ontology/tools/run_target_loop.py at {stamp}.\n"
        "This file, and the decision to stage it, are the whole of the out-of-band\n"
        "fixture step (ST6-4): the content and the staging choice are the operator's,\n"
        "made outside the governed pipeline, never Heimdall's own. Governed staging\n"
        "is deferred to build-order step seven as a named obligation.\n",
        encoding="utf-8",
    )
    _run_checked(["git", "add", FIXTURE_FILE_NAME], cwd=clone_dir, step="add")
    return fixture_file


# ---------------------------------------------------------------------------------
# REQ-24 item 7: the five invocations.
# ---------------------------------------------------------------------------------


@dataclass
class InvocationRecord:
    """One invocation's own recorded evidence (REQ-28): the selector
    value, the three environment variable names with the two path values
    (never a secret byte -- these are paths, not the secret file's own
    content), the process exit code, and the printed standard output and
    standard error verbatim."""

    selector: str
    secret_path: str
    working_repo: str
    exit_code: int
    stdout: str
    stderr: str


def invoke_engine(
    selector: str, engine_binary: Path, secret_path: str, working_repo: Path
) -> InvocationRecord:
    """Runs `engine_binary` once, as a SEPARATE subprocess, with
    `HEIMDALL_ENGINE_TASK`, `HEIMDALL_COHORT_SECRET_FILE` and
    `HEIMDALL_ACTUATOR_GIT_WORKING_REPO` exported in its environment
    (REQ-24 item 7). Records the exit code and both output streams
    without inspecting them to decide anything (REQ-25, EC-33): this
    driver never branches on `selector`, on the exit code, or on either
    stream's content. Raises `DriverError` only if the binary could not
    be spawned at all, which is an operational failure of this driver's
    own invocation step, never an adjudication over the selector's own
    outcome."""
    env = os.environ.copy()
    env[TASK_SELECTOR_ENV_VAR] = selector
    env[SECRET_PATH_ENV_VAR] = secret_path
    env[WORKING_REPO_ENV_VAR] = str(working_repo)
    try:
        result = subprocess.run([str(engine_binary)], env=env, capture_output=True, text=True)
    except OSError as exc:
        raise DriverError(
            f"failed to spawn the engine binary at {engine_binary} for selector "
            f"{selector!r} ({exc}); this is an operational failure of this driver's "
            f"own invocation step, never an adjudication over the selector's own "
            f"outcome (REQ-25)"
        ) from exc
    return InvocationRecord(
        selector=selector,
        secret_path=secret_path,
        working_repo=str(working_repo),
        exit_code=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


# ---------------------------------------------------------------------------------
# REQ-24 item 8: reading the bare origin, read-only, and the transcript.
# ---------------------------------------------------------------------------------


@dataclass
class RunEvidence:
    """Everything the transcript reports, recorded once for the whole
    run (REQ-28): the fixture root, the bare origin path, the clone path,
    the engine binary path, all five invocations' own records, and the
    two read-only readings from the bare origin afterwards."""

    fixture_root: Path
    bare_origin: Path
    clone: Path
    engine_binary: Path
    invocations: "list[InvocationRecord]" = field(default_factory=list)
    git_log: "subprocess.CompletedProcess[str] | None" = None
    git_ls_remote: "subprocess.CompletedProcess[str] | None" = None


def read_bare_origin_evidence(
    bare_dir: Path,
) -> "tuple[subprocess.CompletedProcess[str], subprocess.CompletedProcess[str]]":
    """Read-only. `git log` run with `bare_dir` as the current directory
    (git recognises a bare repository's own top-level layout without
    needing `--git-dir`); `git ls-remote` run against `bare_dir` as a
    remote specification. Neither call is checked for a zero exit: this
    is a READING, and whatever it finds -- including an empty history,
    before any invocation has succeeded -- belongs in the transcript
    verbatim, never suppressed."""
    log_result = _run(["git", "log", "--all", "--decorate", "--source"], cwd=bare_dir)
    ls_remote_result = _run(["git", "ls-remote", str(bare_dir)])
    return log_result, ls_remote_result


def _render_stream(label: str, text: str, indent: str = "    ") -> "list[str]":
    lines = [f"{indent[:-2]}{label}:"] if label else []
    body = text or ""
    rendered = body.splitlines() or [""]
    for line in rendered:
        lines.append(f"{indent}{line}")
    return lines


def render_transcript(evidence: RunEvidence) -> str:
    """Builds the evidence transcript (REQ-28): per invocation, the
    selector value, the three environment variable names with the two
    path values, the exit code and the printed standard output verbatim;
    once for the run, the fixture root, the bare origin path, the clone
    path, the git log reading and the git ls-remote reading. States
    plainly that the fixed order used is SEQUENCING, never adjudication
    (REQ-25, EC-33)."""
    lines: "list[str]" = []
    lines.append("HEIMDALL TARGET-LOOP DRIVER TRANSCRIPT")
    lines.append("=" * len(lines[0]))
    lines.append("")
    lines.append(
        "Ordering note (REQ-28, EC-33). The five invocations below ran in the fixed "
        "order build-order-step-six-spec.md's own REQ-6 table fixes: P1, P2, N1, N2, "
        "N3. This driver did not inspect any invocation's own outcome to decide "
        "whether to run the next one; all five ran regardless of what the earlier "
        "ones produced. Running this fixed order is SEQUENCING, never ADJUDICATION: "
        "this transcript records what happened and holds no expectation about what "
        "was supposed to happen. Reading the five exit codes and outcomes below "
        "against the spec's own REQ-7 expectation table is the reviewer's job, done "
        "by hand for TARGET_LOOP_EVIDENCE.md, never something this driver computed."
    )
    lines.append("")
    lines.append(f"Fixture root:  {evidence.fixture_root}")
    lines.append(f"Bare origin:   {evidence.bare_origin}")
    lines.append(f"Clone:         {evidence.clone}")
    lines.append(f"Engine binary: {evidence.engine_binary}")
    lines.append("")

    for index, record in enumerate(evidence.invocations, start=1):
        lines.append(f"--- invocation {index}: selector {record.selector!r} ---")
        lines.append(f"  {TASK_SELECTOR_ENV_VAR} = {record.selector}")
        lines.append(f"  {SECRET_PATH_ENV_VAR} = {record.secret_path}  (a path; contents never read or printed by this driver)")
        lines.append(f"  {WORKING_REPO_ENV_VAR} = {record.working_repo}")
        lines.append(f"  exit code: {record.exit_code}")
        for line in _render_stream("stdout", record.stdout):
            lines.append(f"  {line}")
        if record.stderr:
            for line in _render_stream("stderr", record.stderr):
                lines.append(f"  {line}")
        lines.append("")

    if evidence.git_log is not None:
        lines.append("--- bare origin reading: git log ---")
        lines.append(f"  exit code: {evidence.git_log.returncode}")
        for line in _render_stream("", evidence.git_log.stdout, indent="  "):
            lines.append(line)
        if evidence.git_log.stderr:
            for line in _render_stream("stderr", evidence.git_log.stderr):
                lines.append(f"  {line}")
        lines.append("")

    if evidence.git_ls_remote is not None:
        lines.append("--- bare origin reading: git ls-remote ---")
        lines.append(f"  exit code: {evidence.git_ls_remote.returncode}")
        for line in _render_stream("", evidence.git_ls_remote.stdout, indent="  "):
            lines.append(line)
        if evidence.git_ls_remote.stderr:
            for line in _render_stream("stderr", evidence.git_ls_remote.stderr):
                lines.append(f"  {line}")
        lines.append("")

    lines.append(
        "This transcript holds no expectation and no verdict (REQ-25): it records "
        "what happened, never what was supposed to happen. It is emitted to standard "
        "output on every run, and additionally to a file only when --output was "
        "supplied on the command line (REQ-27)."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------------
# Orchestration.
# ---------------------------------------------------------------------------------


def run_driver(fixture_root_arg: "str | None", engine_binary_arg: "str | None") -> RunEvidence:
    """Runs REQ-24's eight responsibilities in order, on an already
    validated environment, and returns the recorded evidence. Raises
    `DriverError` on any operational failure; never raises because an
    invocation's own outcome was merely unexpected."""
    secret_path = require_fixture_secret_path()
    engine_binary = resolve_engine_binary(engine_binary_arg)

    fixture_root = Path(fixture_root_arg) if fixture_root_arg else default_fixture_root()
    canonical_fixture_root = assert_fixture_root_outside_repository(fixture_root)
    assert_fixture_root_absent(canonical_fixture_root)

    try:
        canonical_fixture_root.mkdir(parents=True)
    except OSError as exc:
        raise DriverError(
            f"could not create the fixture root {canonical_fixture_root} ({exc})"
        ) from exc

    bare_dir = canonical_fixture_root / "origin.git"
    clone_dir = canonical_fixture_root / "clone"

    init_bare_origin(bare_dir)
    clone_origin(bare_dir, clone_dir)
    configure_repository_local_identity(clone_dir)
    checkout_integration_branch(clone_dir)
    stage_fixture_file(clone_dir)

    evidence = RunEvidence(
        fixture_root=canonical_fixture_root,
        bare_origin=bare_dir,
        clone=clone_dir,
        engine_binary=engine_binary,
    )

    for selector in SELECTOR_ORDER:
        evidence.invocations.append(
            invoke_engine(selector, engine_binary, secret_path, clone_dir)
        )

    evidence.git_log, evidence.git_ls_remote = read_bare_origin_evidence(bare_dir)

    return evidence


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Provision a throwaway fixture outside heimdall's own working tree and "
            "run the process-engine binary five times, once per accepted "
            "HEIMDALL_ENGINE_TASK selector, in the fixed order the spec fixes "
            "(build-order step six). Adjudicates nothing and holds no expectation: "
            "see the module docstring for the full statement of what this tool does "
            "and does not do."
        )
    )
    parser.add_argument(
        "--fixture-root",
        default=None,
        help=(
            "Where to provision the fixture. Must resolve outside heimdall's own "
            "working tree (checked before anything is created) and must not "
            "already exist (REQ-24 item 1, REQ-30). Defaults to a freshly "
            "timestamped directory under the platform's temporary-directory prefix."
        ),
    )
    parser.add_argument(
        "--engine-binary",
        default=None,
        help=(
            f"Path to the already-built process-engine binary. Defaults to "
            f"{DEFAULT_ENGINE_BINARY}. This driver never builds the binary itself."
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Also write the evidence transcript to this path. The transcript is "
            "always printed to standard output regardless; this driver writes "
            "nothing else, and writes nothing inside heimdall's own working tree "
            "unless this option names a path there explicitly (REQ-27)."
        ),
    )
    return parser


def main(argv: "list[str] | None" = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        evidence = run_driver(args.fixture_root, args.engine_binary)
    except DriverError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1

    transcript = render_transcript(evidence)
    print(transcript)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(transcript, encoding="utf-8")

    # REQ-25, AC-30: this driver's own exit code reflects only that
    # provisioning succeeded and all five invocations were spawned and
    # ran to completion. It is 0 here regardless of what the five
    # invocations' own exit codes were: none of them is inspected above
    # to decide this return value.
    return 0


if __name__ == "__main__":
    sys.exit(main())
