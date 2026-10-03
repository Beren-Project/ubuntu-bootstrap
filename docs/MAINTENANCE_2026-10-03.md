# Cargo manager ownership and durable completion state

This pass starts at `0a19f529457a744e5d74df55622fbb1a5894b0c9`, with a clean
worktree. It keeps normal-user execution, scoped sudo, manifest authority,
first-install current stable software, preservation on ordinary reruns, and
selected owned-component updates. No whole-system upgrade or global Cargo update
is introduced. Validation results are recorded in [VALIDATION.md](VALIDATION.md).

## Trust and ownership

```text
APT
  └─ OS foundation
verified official rustup-init + official SHA-256
  └─ rustup (initially no toolchain; self-update before stable installation)
      └─ Cargo + cargo-binstall
          ├─ selected Cargo CLI applications
          ├─ uv + uvx → managed CPython
          └─ Juliaup + julia → Julia release channel
```

Rust's official architecture-specific HTTPS ELF executable is checked against
the strict official checksum record before execution. Rustup init uses
`--default-toolchain none --no-modify-path`; self-update precedes
`toolchain install stable --profile minimal --default --no-self-update`.
The final Rustup, Cargo and rustc commands, stable selection and `.cargo/env` are
verified. Custom Rust distribution/update roots are refused. There is no remote
shell installer helper or configuration for Rust, uv or Juliaup.
Existing Cargo/Rustup roots must be user-owned directories with secure,
non-symlinked paths before manager verification or updates. Incompatible Juliaup
depot overrides, including empty/relative values, are rejected before installing
the manager or running runtime operations.

One Cargo application implementation handles all three consumer profiles. It
ensures cargo-binstall once per invocation, tries official crate metadata/release
binaries first, and falls back to an explicitly resolved stable crate version
using `cargo install --locked` and scoped build prerequisites. Python and Julia
depend on Rust without selecting the unrelated Cargo CLI collection. Existing
default-profile selection is unchanged.

Cargo owns uv/uvx and Juliaup/julia in `.cargo/bin`. Manager crate versions must
agree with Cargo registration and version probes. `julia --version` is a runtime
probe, not a Juliaup crate-version probe. The `juliaup` receipt owns its launchers;
the `julia` receipt observes configured runtime state. Updates install the selected
crate first, then update managed CPython or Julia `release`. Neither application
uses its binary self-update command. Additional Julia channels and Python
environments are preserved. Native Julia completion still uses
`.julia/juliaup/completions/zsh.zsh`; no `.zfunc` duplicate is created.

## Exact legacy migration

Legacy uv receipts have manager `uv` and exactly `.local/bin/uv` and `uvx`.
Legacy Julia receipts have manager `juliaup` and exactly `.juliaup/bin/juliaup`
and `julia`. Existing artifacts must still match receipt hashes, user ownership,
executable types and secure parents. The upstream absolute `julia` symlink to
the exact user-owned `.juliaup/bin/julialauncher` is supported; that target is
preserved because it was not an exact receipt-owned path.

```text
STAGING → INSTALLING → REPLACEMENT_VERIFIED → LEGACY_RETIRED → COMMITTED
```

Cargo installs and validates the replacement before its final receipt is
published. The replacement's hashes, crates.io registration, runtime checks and
proposed receipts become durable at REPLACEMENT_VERIFIED. The replacement
binaries and Cargo registration have also been file-fsynced, with their
directory entries flushed. From that point,
recovery validates evidence and rolls forward: retire only still-matching old
launchers, flush their directories, publish new receipts, durably commit, clean.
Missing old launchers are allowed during retirement recovery; changed or newly
introduced old launchers are preserved and refused. Retired legacy launchers do
not shadow `.cargo/bin` through the unchanged dotfiles PATH order.

An interrupted third-party Cargo installer before replacement fingerprints are
durable can leave ambiguous outputs. Bootstrap preserves them and its INSTALLING
journal, stops, and reports the exact recovery directory. It does not infer
ownership from Cargo registration or a version string alone. An ordinary failed
install leaving no replacement output can discard its non-destructive intent.

## Shared diagnostic inventories

Receipts keep `_completion_inventories = {schema: 1, snapshots: {...}}` in the
same JSON document. Completion observations use `inventory_ref` values such as
`sha256:<digest>`. Canonical inventories sort package/artifact keys and unique
path lists; identity hashes UTF-8 JSON with sorted keys, compact separators and
unescaped Unicode. State publication retains existing indented JSON formatting.

Legacy inline inventories normalize automatically under the run lock. Ownership
paths/hashes and other observations are retained. Snapshot digests, reference
existence, conflicting inline/reference observations and schema are validated.
Only unreferenced inventory snapshots are discarded. The manifest continues to
select desired behavior; receipts/inventories cannot select packages or tools.

The saved preceding all-profile document was 4,329,372 bytes. The planning
projection was 1,145,612 bytes (73.54% lower), with 40 command references and nine
unique inventories. Final qualification measured the same installed inputs as 4,329,509 bytes
inline and 1,145,749 bytes shared (73.54% lower): 40 command references, nine
unique snapshots. Both representations use the same unrelated receipt fields.

## Completion publication and recovery

The fixed state `transaction/` directory contains a private journal and named
old/new artifact and receipt copies. Production receipt loading, recovery and
inventory normalization happen under the existing exclusive flock before
ownership checks. Generated base completions, transitions to system providers
and the native Julia completion use the same coupled-publication primitive.

```text
STAGING → PREPARED → ARTIFACT_PUBLISHED → STATE_PUBLISHED → COMMITTED
                  ↘ rollback → ROLLED_BACK
```

- STAGING has not published an artifact or receipt; known staging can be cleaned.
- Before PREPARED, new data and old recovery copies are file-fsynced and their
  directories fsynced. PREPARED intent is durably published before replacement.
  Newly created managed directories and their parent entries are also flushed;
  native/base completion directory permission changes are fsynced.
- Artifact replacement is atomic and followed by parent-directory fsync.
  Native restored-shell validation happens before receipt publication.
- Receipt publication writes a sibling stage, flushes/fsyncs it, atomically
  replaces the destination, and fsyncs the state directory.
- COMMITTED is durable only after both publications. Earlier phases recover the
  exact old artifact and receipt state, even when a phase record lagged a rename.
- Recovery uses copies of retained backups and sibling atomic replacements; it
  never consumes the only valid backup. Rollback restores original modes and
  timestamps, or verified prior absence, then durably records ROLLED_BACK.
- Terminal states verify the corresponding pair and complete restartable
  cleanup. New completion receipts must describe the actual committed artifact.
  Recovery material is deleted before the journal, with directory fsync at the
  cleanup boundaries. An empty transaction directory left after journal cleanup
  can be removed after validating its owner/type/mode.
- Known partial transaction publication stages can be cleaned once valid recovery
  copies/pairs are verified. Unknown files, symlinks, insecure ownership/modes,
  mismatched digests or missing required material cause a reported failure and
  are preserved. No normal handler continues through uncertain state publication.

The guarantee is crash-consistent recovery under the supported Linux/POSIX
filesystem semantics exercised by qualification. It is not a guarantee against
arbitrary storage/hardware failure, a whole-bootstrap transaction, or automatic
recovery of interrupted third-party installer internals. Unknown unjournaled
temporary files are preserved for inspection.

## Qualification boundary

The migration integration path constructs verified equivalent legacy state from
official checksummed artifacts and baseline receipt/layout contracts inside the
existing isolated test container. It does not execute the historical shell
installers. It verifies old PATH shadowing, Cargo replacement/retirement,
preserved managed Python and Julia channels/runtime, and an unchanged subsequent
bootstrap pass. Deterministic filesystem fixtures and an `os._exit` subprocess
exercise publication recovery independently of Python cleanup.

ARM64 mapping/consent tests remain separate from full x86_64 installation
qualification. Live WSL terminal/Wayland behavior and hosted Actions are not
claimed by these tests. Podman qualification uses only the fixed project
container and session-owned cleanup; unrelated OpenProject resources and cached
Ubuntu images are retained.

## Changed files

| Area | Files |
| --- | --- |
| Manifest | `config/bootstrap.toml` |
| Runtime | `bootstrap_lib/cli.py`, `completions.py`, `config.py`, `julia.py`, `optional_completions.py`, `python.py`, `runtime.py`, `rust.py`; new `durability.py`, `inventories.py`, `migration.py` in the same directory |
| Tests | `tests/container-scenario`, `container_checks.py`, `podman_runner.py`, `test_completions.py`, `test_logic.py`, `test_optional_completions.py`; new `test_maintenance.py` in the same directory |
| Documentation | `README.md`; `docs/ARCHITECTURE.md`, `DOCS_WORK_PLAN.md`, `OPTIONAL_COMPLETIONS_PLAN.md`, `UPSTREAM.md`, `USAGE.md`, `VALIDATION.md`; this new maintenance design/handoff |

Historical documentation plans are labeled as historical. The manifest remains
the single desired-state authority. No excluded tool or restore selection was
added. Source/runtime modules for Node/fnm, ngspice, OpenModelica, editors,
platform policy, dotfiles and shell consent were not changed.

## Final handoff status snapshot

Final local validation: 26 focused maintenance tests and 113 full-suite tests
passed. Fresh Ubuntu 26.04 x86_64 all-profile qualification passed after review
fixes, without retry, in 2,331.14 seconds. Final post-update receipts measure
4,329,509 bytes with inline inventories versus 1,145,749 bytes shared (73.54%
lower). The empty failure list, frozen-input match and unchanged Podman resource
audit are recorded in [VALIDATION.md](VALIDATION.md#final-qualification-and-resources-1).

No files were staged, committed or pushed. HEAD remains
`0a19f529457a744e5d74df55622fbb1a5894b0c9`. The following is the dated final
`git status --short` snapshot, before any later user Git action:

```text
 M README.md
 M bootstrap_lib/cli.py
 M bootstrap_lib/completions.py
 M bootstrap_lib/config.py
 M bootstrap_lib/julia.py
 M bootstrap_lib/optional_completions.py
 M bootstrap_lib/python.py
 M bootstrap_lib/runtime.py
 M bootstrap_lib/rust.py
 M config/bootstrap.toml
 M docs/ARCHITECTURE.md
 M docs/DOCS_WORK_PLAN.md
 M docs/OPTIONAL_COMPLETIONS_PLAN.md
 M docs/UPSTREAM.md
 M docs/USAGE.md
 M docs/VALIDATION.md
 M tests/container-scenario
 M tests/container_checks.py
 M tests/podman_runner.py
 M tests/test_completions.py
 M tests/test_logic.py
 M tests/test_optional_completions.py
?? bootstrap_lib/durability.py
?? bootstrap_lib/inventories.py
?? bootstrap_lib/migration.py
?? docs/MAINTENANCE_2026-10-03.md
?? tests/test_maintenance.py
```
