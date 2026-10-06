# Validation

This is a dated evidence index, not a promise that every scenario ran at the
current revision. Earlier records retain their historical pins, ownership
layouts and limitations. The core and completion implementations were
subsequently committed by the user after their implementation agents finished
without committing or pushing. Commit/worktree descriptions are snapshots at
each dated handoff, not claims
about the current checkout's Git state.

The [2026-10-03 maintenance design](MAINTENANCE_2026-10-03.md) supersedes the
inline-inventory and exception-only publication debts described in older
records. It describes the current schema, ownership and recovery state machines.

| Record | Code/evidence scope | Local suite | Real installation evidence |
| --- | --- | --- | --- |
| [Core qualification — 2026-10-01](#core-qualification--2026-10-01) | Original core implementation, subsequently committed as `ec3df7f` | 35 tests plus static checks | Fresh x86_64 Ubuntu 26.04, all profiles, 1000.62 s |
| [Completion follow-up — 2026-10-02](#completion-follow-up--2026-10-02) | Completion implementation, subsequently committed as `f5e841a` | 51 tests plus static checks | Fresh x86_64 Ubuntu 26.04, focused base scenario, 233.28 s |
| [Documentation follow-up — 2026-10-02](#documentation-follow-up--2026-10-02) | Documentation-only changes on `f5e841a`; implementation unchanged | 51 tests plus static and documentation checks | No installation run; earlier qualification unchanged |
| [Optional completion follow-up — 2026-10-02](#optional-completion-follow-up--2026-10-02) | Optional-provider implementation on `0883eed` | 72 tests plus static/documentation checks | Fresh x86_64 Ubuntu 26.04, all profiles, 593.25 s; no retry |
| [Optional-completion precommit review — 2026-10-02](#optional-completion-precommit-review--2026-10-02) | Provider registration and publication corrections | 87 tests plus static/documentation checks | Final fresh x86_64 Ubuntu 26.04, all profiles, 637.13 s; no retry |
| [Cargo ownership and durable recovery — 2026-10-03](#cargo-ownership-and-durable-recovery--2026-10-03) | Coordinated maintenance on clean `0a19f52`; uncommitted | 113 tests plus static/documentation checks | Final fresh x86_64 Ubuntu 26.04, all profiles, 2331.14 s |
| [Cargo retry follow-up — 2026-10-03](CARGO_RETRY_2026-10-03.md#validation-evidence) | Retry supervision on clean `384260c`; includes later log-only hardening | 133 tests plus static checks | Final fresh x86_64 Ubuntu 26.04, all profiles, 722.45 s; later log-only changes covered by units |
| [Dotfiles Cargo ownership alignment — 2026-10-05](#dotfiles-cargo-ownership-alignment--2026-10-05) | Update on clean `f5a20fc`; uncommitted | 136 tests plus isolated pinned-shell probes and static checks | Fresh x86_64 Ubuntu 26.04, all profiles, 592.42 s; no retry |
| [CI semantics — 2026-10-05](#ci-semantics--2026-10-05) | Workflow/documentation update on clean `c7dca58`; uncommitted; runtime/tests unchanged | 136 tests on local 26.04 and container 24.04; workflow/static/documentation checks | Fresh x86_64 Ubuntu 26.04, all profiles, 580.10 s; no retry; real 24.04 production rejection |
| [Documentation precommit review — 2026-10-05](#documentation-precommit-review--2026-10-05) | All ten Markdown files reviewed with the pending CI patch | Manifest/CLI/implementation cross-checks, local links and example syntax | No new installation run; preceding CI qualification inputs unchanged |
| [Permissive-umask directory safety — 2026-10-05](#permissive-umask-directory-safety--2026-10-05) | Safe managed ancestry creation, installation-scoped umask and completion checks | 149 tests plus focused, static and documentation checks | Fresh x86_64 Ubuntu 26.04, all profiles, 577.68 s; verified caller umask 0002 |

The focused completion run did not reinstall the all-profile engineering
baseline. New documentation verification belongs in a separate dated record;
it does not extend installation qualification. Contributor commands and
resource discipline are described in [CONTRIBUTING.md](../CONTRIBUTING.md).

## CI evidence terminology

**Unit CI passed** means host-independent regression coverage passed.
**Platform-gate tests passed** means release/architecture decision logic passed
against explicit fixtures, including supported acceptance and unsupported
rejection. Both run in the Ubuntu 24.04 hosted unit job; neither result qualifies
Ubuntu 26.04 installation support.

**Ubuntu 26.04 qualification passed** means the real bootstrap successfully ran
in a fresh Ubuntu 26.04 environment with real platform detection. The full
Podman `all` scenario is the platform-support qualification gate, automatically
requested after passing units on pushes to `main`, or manually with the
dispatch integration input. See [CI meanings and triggers](../CONTRIBUTING.md#ci-meanings-and-triggers)
for environment choice, runtime tradeoffs and container qualification limits.
Historical local records below are not evidence of hosted Actions execution.

## Core qualification — 2026-10-01

Validated locally on 2026-10-01. Installation qualification used a fresh official
`docker.io/library/ubuntu:26.04` x86_64 container and a normal `engineer` user with
an isolated HOME. No bootstrap installation was applied to the host's HOME.

Commands:

```sh
./scripts/test
./scripts/test-podman
```

The normal suite passed **35 tests**, Python AST/manifest validation, shell syntax
checks and ShellCheck. Ownership tests use real temporary files. System asset
tests execute real copy/rename commands to check successive replacements,
retained predecessors, rollback and interrupted-publication refusal. These tests
do not require network access or administrator privileges.

### Real Ubuntu integration

The final `./scripts/test-podman` fresh-container scenario passed with exit code
0 in 1000.62 seconds (approximately 17 minutes, including network fetches). It
exercises:

| Area | Evidence |
| --- | --- |
| Platform and privilege | Ubuntu 26.04/resolute, normal UID; whole-bootstrap root invocation rejected |
| APT base | All manifest base packages installed; Zsh, gh, wl-copy and wl-paste executable |
| Rust and Cargo | Official stable rustup, user-owned Cargo paths; every manifest CLI runs and matches crates.io manager metadata |
| Binary-first installation | Upstream binaries used where available; cargo-update and Macchina exercised the locked source fallback with automatic prerequisites |
| Python and Node | Official user-owned uv, managed CPython and fnm-managed default Node LTS; no system pip changes |
| Dotfiles | Exact origin, clean checkout and full pinned HEAD verified before scripts execute |
| Selective restore | All five selected files match pinned sources; existing changed .zshrc backed up by upstream restore |
| Excluded configs | Bash, .profile, Zellij, Mermaid and personal Git config sentinels preserved; isolated selective restore creates none of the four excluded managed paths |
| Plugins/config validation | Real pinned plugin installation, Zsh startup, Starship prompt, Git config and isolated tmux server |
| Shell consent | Real PTY default-Yes and explicit No; original user's passwd entry checked, root shell unchanged; CI does not exec Zsh |
| Idempotency | Base and all-profile second passes preserve selected file mtimes/hashes, backup inventory and receipts; ngspice is not rebuilt |
| Optional profiles | Build packages, Julia arithmetic, Vim, headless Neovim, batch Emacs |
| ngspice | Verified release 47 built as normal user; batch voltage-divider result is 5 V |
| OpenModelica | Signed resolute/stable repository and CLI package; actual differential-equation simulation; no omedit/omplot/openmodelica metapackage |
| Failure/recovery | Dirty checkout, symlink conflict and unmanaged Cargo tool fail without overwrite; explicit ownership recovery; optional failure is nonzero while base stays usable |
| Update ownership | --update checks selected manifest crates; an unrelated user-installed Cargo fixture retains its executable hash/version and is absent from receipts |

Tested dotfiles revision:

```text
f7c3eb9ce433a1a8e285afdcda06c1da56c018fd
```

The restore selection is `.zshrc`, `.zshenv`, `.gitconfig`, `.tmux.conf` and
`.config/starship.toml`, using upstream repeated `--file` flags for preview and
apply. Optional missing Zellij dependencies in the real upstream report do not
fail bootstrap.

Observed versions include Rust 1.99.0, cargo-binstall 1.24.0, uv 0.12.21,
managed CPython 3.14.7, Node 24.21.0 LTS, ngspice 47, OpenModelica
1.27.1~2-g6db4671 and Neovim 0.12.5. These are test observations, not new pins.
Immutable source/artifact checksums and desired channels remain in the manifest.

### Podman resource audit

Every session runs both `podman ps` and `podman ps -a` before creation and after
cleanup. The fixed project name is `ubuntu-bootstrap-integration` with label
`org.beren-project.ubuntu-bootstrap=integration`. Debugging installer issues
reused the same failed container before cleanup; no numbered replacements were
created. The final qualification uses the normal documented command above.

Before testing there were **zero running containers**, **seven unrelated stopped
containers**, and **zero project test containers**. After completed sessions the
same seven unrelated containers remain stopped, with zero project test leaks:

```text
c769d61c0153 openproject-demo_db_1
e6ae4f641c7f openproject-demo_cache_1
055b44fdfa2b openproject-demo_hocuspocus_1
7af40bbce2b9 openproject-demo_web_1
f0c52be42500 openproject-demo_worker_1
6ed5d35aaeeb openproject-demo_cron_1
6c9aa0d02932 openproject-demo_proxy_1
```

Only session-created project containers are removed. The fixed Ubuntu 26.04
image remains cached (approximately 112 MB); no custom images were built, no
unrelated containers/images/volumes were removed, and no global prune ran.
Ignored `test-results/` contains the final before/after JSON inventory,
exit status, timing, receipts and installation log.

The final session created container
`2f9c616e860c0e3d940d6f4a4bbe91837fa57814f9a55204e9c5954c41b562bb`
under the fixed project name, then removed it. Before/after unrelated container
IDs, names, states and exit codes were equal. Both final inventory commands were
also repeated independently after runner cleanup.

### Qualification limits

- Official OpenModelica **resolute** support was available and verified during
  the core run. Its CLI package then declared compiler dependencies itself; the
  bootstrap profile
  does not enable the generic build profile. GUI recommendations are excluded.
- ARM64 mappings and decline/opt-in logic are unit tested; ARM64 installation is
  best effort and has not received real-machine qualification.
- Container tests verify clipboard binaries, not a live Wayland socket. The host
  WSL2 platform detection and read-only plan were checked; a real WSL interactive
  login transition, terminal font rendering and host clipboard behavior remain
  unqualified. Native Ubuntu interactive desktop behavior was not tested.
- Channels were current during --update tests. The ownership boundary is proven;
  future upstream release changes and service availability cannot be guaranteed.
- Previous system installation trees are deliberately retained for recovery.
  Interrupted publication requires inspection; bootstrap never deletes arbitrary
  existing installation trees to recover automatically.
- GitHub Actions configuration is provided; its hosted execution has not run.
- During initial implementation this workspace had an empty read-only `.git`
  placeholder, so Git status reported `fatal: not a git repository`. That initial
  review used direct inspection and `git diff --no-index --check`, without Git
  initialization, staging, commit or push by the implementation agent. The user
  subsequently committed the core implementation as `ec3df7f`.

## Completion follow-up — 2026-10-02

Baseline: committed `ec3df7f` (`feat: add Ubuntu 26.04 development environment
bootstrap`). The user subsequently committed this follow-up as `f5e841a`
(`feat: provision Zsh completions for bootstrap-managed tools`). The follow-up
retains the existing modules/profile graph, package
set, update policy and exact dotfiles SHA. It adds a completion module, manifest
generator definitions and a small post-install hook; no dotfiles payloads or
upstream restore behavior change.

```sh
./scripts/test
./scripts/test-podman --scenario base --debug-retry
git diff --check
```

The normal suite passes **51 tests**, including 16 new completion regressions,
plus the existing static checks. Completion tests use real normal-user fixture
applications, temporary files and Zsh syntax/autoload validation. They cover
initial creation, ownership, secure permissions with permissive umask, unchanged
reruns/updates, changed application versions, a Cargo-style unchanged proxy with
a changed toolchain version, root refusal, unmanaged/symlink/insecure directory
protection, empty/invalid/failed output, atomic preservation and optional
integration failure reporting.

Final review added a reproduced regression for exit-0 output containing only
comments: this now fails validation before replacing a working file. The final
strict format validator was also checked against all twelve actual supported
generator outputs using normal-user temporary files on the host; it accepts
the legitimate formats. Newly created `.zfunc` directories are explicitly 0755
even with umask 002; preexisting insecure directories are preserved and refused.

The focused **fresh Ubuntu 26.04 x86_64** Podman scenario passed with exit code 0
in **233.28 seconds**. The debug-retry option was armed for safe debugging but no
failure or retry occurred. The normal documented command without that option
runs the identical scenario on success. It verified:

- Eleven real generated files: `_rustup`, `_cargo`, `_uv`, `_uvx`, `_fnm`,
  `_starship`, `_rg`, `_fd`, `_bat`, `_delta`, `_mcat`, all nonempty and user-owned.
- Each generated file matches its installed application's current output and
  passes `zsh -n`; the restored Zsh configuration includes `$HOME/.zfunc` in
  `fpath`, registers generated commands through `compinit`, and autoloads them.
- Ubuntu's `_gh` stays system-owned and is recognized without a `.zfunc` copy.
  Eza/zoxide/Neovim/bottom/hyperfine/dust artifacts are not invented.
- Base second pass preserves generated contents, modification times, receipt
  observations, config files and backup inventory, with no duplicate/temp files.
- A deliberately invalid invocation of the **real managed fnm** returns failure
  without changing its working completion or receipt. A stale recorded version
  then triggers regeneration through real `bootstrap --update`; current
  completions retain their timestamps. Actual application version advancement
  is covered separately by the controlled unit fixture, not falsely attributed
  to a new upstream release during integration.
- Existing root rejection, shell Yes/No and failure/recovery checks still pass.

The session created just
`c3c33ae97da3f375d70eb56171cd5da980b9fa04e8a0b6c2c9a50e60ff80daee`
under the existing fixed project name, then removed it. Both inventory commands
ran before creation and after cleanup and were repeated independently afterward.
Before and after: **zero running**, **the same seven unrelated stopped**,
**zero project test containers**. Unrelated IDs/names/states/exit codes were
equal. No replacement containers or images were created and no global prune ran.
Ignored `test-results/` now records this completion session's receipts/log/audit.

This follow-up qualifies the completion layer and base path. The already-passed
all-engineering baseline above was not reinstalled; optional application's
completion failure behavior is covered by the focused unit orchestration test.
ARM64 and live WSL terminal behavior retain the baseline's qualification limits.
GitHub Actions now installs Zsh to run the real syntax/autoload unit checks; the
hosted workflow had not been executed during this qualification. No commit or
push was performed by the follow-up implementation agent; the user subsequently
committed it as recorded above.

## Documentation follow-up — 2026-10-02

The approved documentation change adds detailed installation/usage/recovery,
contributor and architecture guidance, shortens the README, and indexes the
historical evidence. Two writers owned disjoint files and an independent
read-only reviewer checked the combined result against the implementation.
The [work plan and handoff](DOCS_WORK_PLAN.md) records assignments and outcomes.

```sh
./scripts/test
git diff --check
```

The normal suite passed **51 tests** in 1.226 seconds, followed by manifest,
Python AST, shell syntax and ShellCheck checks. A one-off standard-library
documentation check verified local file links and heading anchors, manifest
package/tool coverage, all public CLI flags, exact dotfiles SHA/selection and
documentation-only changed paths. Command examples and ownership/failure claims
were also reviewed against source rather than executed as installations.

No runtime, manifest, workflow, test or dotfiles behavior changed. No bootstrap
installation or Podman command ran for this change; no container was created,
started, removed or otherwise managed. Historical inventories above are dated
test evidence, not a new live Podman audit. No staging, commit or push was
performed by this documentation implementation. External links and rendered
GitHub pages were not browser-tested, and no new upstream availability audit,
Ubuntu installation qualification or WSL runtime qualification is claimed.

## Optional completion follow-up — 2026-10-02

Baseline: `0883eed`. The focused follow-up adds explicit optional-provider
metadata, a separate optional completion module and conditional post-handler
integration. Existing package sets, profile dependencies, manager/channel
policy, base autoload contract and pinned five-file restore remain unchanged.
The approved native Julia script destination is
`~/.julia/juliaup/completions/zsh.zsh`, matching the pinned dotfiles; no
compatibility link, dotfiles payload change or duplicate Julia `.zfunc` file
was needed. See the [provider mapping and handoff](OPTIONAL_COMPLETIONS_PLAN.md).

```sh
./scripts/test
./scripts/test-podman --scenario all --debug-retry
git diff --check
```

The normal suite passed **72 tests** in **14.946 seconds**, followed by manifest,
Python AST, shell syntax and ShellCheck validation. Twenty-one optional-provider
tests exercise classification, selected-only execution, shared functions,
already-loaded valid system functions, personal shadows, generic fallback,
native Julia registration/channel behavior, changed versions, root refusal,
custom-depot refusal, ownership, atomic generation and rollback after final
restored-shell validation failure. Local documentation links/anchors and four
standalone embedded Zsh scripts were also checked. Independent read-only review
found no remaining blocker after its concrete findings were corrected.

The final **fresh Ubuntu 26.04 x86_64** full Podman scenario passed with exit 0
in **593.25 seconds**, without a retry. It verified:

- Fresh base installation prepares no optional receipts/completion artifacts,
  even when compiler packages exist because a Cargo fallback required them.
- Later-selected profiles validate **21 system registrations**, including
  Vim/Neovim's shared `_vim`, compiler aliases, Make, pkg-config, Ninja,
  traditional Binutils, primary Debian build commands and Bison/Flex.
  Actual restored Zsh `compinit` registration, autoload source and root package
  ownership are checked; no duplicate `.zfunc` files are created.
- **19 commands** record explicit `unavailable` status after inspecting full
  package/artifact inventories. These include CMake/CTest/CPack, selected
  Binutils/GCC helpers, Emacs, ngspice and OpenModelica. Generic file completion
  is not claimed as application-specific support; absence is nonfatal.
- Juliaup **1.22.7** generates the real official native script as the normal
  user. Its installed output matches the published file exactly. Restored Zsh
  recognizes both `juliaup` and the real `julia +channel` handler, including
  channel candidates and ordinary-argument fallback.
- A deliberately invalid invocation of the real Juliaup generator fails
  without changing the existing file, timestamp or receipts, and leaves no
  staging files. A stale observed version triggers atomic refresh; the next
  unchanged run preserves its timestamp. Actual version advancement is covered
  by the offline fixture, rather than claiming a new upstream release occurred.
- Base/all-profile second passes preserve completion hashes/timestamps,
  receipts, selected config files and backup inventory. Ngspice is not rebuilt.
  Full `--update` revalidates providers and preserves the unrelated Cargo fixture
  and excluded/personal configs. Existing root, shell Yes/No, exact checkout,
  plugin, numerical engineering/editor and failure/recovery checks also pass.

Dotfiles revision tested remains:

```text
f7c3eb9ce433a1a8e285afdcda06c1da56c018fd
```

### Resource evidence

An earlier development session reused its same fixed-name container after a
test failure while the manifest/path decision was being completed; it passed
base and engineering checks and cleaned up. It created/removed only
`8ff0c6d9b0e6040d63c8cecc76898f7a0eb088ce25ca455ea6d46ebda1d5f4e2`.
Its audit was preserved at `/tmp/ubuntu-bootstrap-optional-development-audit.json`.
The final fresh qualification then created/removed only
`994ceb94682f5139220d58b39b54c43071b34b5d5c6d3438643d55d4c6e2e5ba`.
Both used `ubuntu-bootstrap-integration`, the existing label, normal test user,
cached fixed Ubuntu image and finally-style cleanup; no numbered debugging
replacement or uniquely tagged image was created.

Both inventory commands ran before creation and after cleanup in each session,
and were independently repeated afterward. Final before/after unrelated IDs,
names, states and exit codes match: **zero running**, **the same seven unrelated
stopped**, **zero project test containers**. Only session-created resources were
removed; no global prune or unrelated container/image/volume deletion occurred.
The approximately 112 MB Ubuntu image remains cached. Ignored `test-results/`
contains the final receipts, last-run status, bootstrap log and full session audit.

### Limits and final handoff

This is Ubuntu integration evidence; ARM64 and live WSL terminal/Wayland behavior
retain the earlier qualification limits. OpenModelica's signed **resolute** CLI
repository/package worked; no GUI packages or generic build-profile implication
were added. Internal dpkg-dev plumbing, architecture-prefixed aliases and unrelated
transitive utilities are outside this completion inventory. Missing supported
providers are reported honestly; no custom definitions or extra apps are added.
The hosted Actions workflow was not executed. During this initial optional-layer
implementation phase, the agent did not stage, commit or push; the implementation
and documentation were handed off for user review.

## Optional-completion precommit review — 2026-10-02

The independent source review covered the tracked diff and all three untracked
implementation/handoff/test files. Previous passing results were treated as
historical evidence, not proof that the new transaction and registration paths
were correct. Concrete reproductions required these corrections:

- The login-shell probe ran another `compinit`, masking missing registration
  in actual startup. It now observes existing `_comps` without repairing it.
- Provider discovery and loading used separate shells without binding the
  second shell to the previously verified paths. A changing `fpath` could load
  a personal provider while receipts described the trusted first selection.
  Loading now checks the saved command/function/path selection before autoload
  and verifies the actual function source afterward. Native Julia functions
  must also come from the exact sourced script rather than a personal override.
- An existing writable native script was accepted on rerun; newly created
  parents could also inherit unsafe permissions from umask 002. Existing
  insecure files/parents are preserved and refused before child creation;
  only new directories receive 0755 and generated files receive 0644.
- Native recovery ended before the paired receipt writes. Receipt failure or
  an interrupt immediately after rename could leave changed files and old
  observations. Both native observations now publish together within recovery;
  precommit failures restore the file and in-memory/on-disk receipts. Once
  receipts commit, an interrupt or recovery-copy cleanup error keeps the
  matching new script and receipts instead of rolling back the file alone.
  If restoration itself fails, the named recovery copy is retained.
- Diagnostic state publication leaked its staging file on serialization/rename
  failure. The shared helper now cleans its exact staging path in `finally`.
- Duplicate protection did not span base and optional command tables, permitting
  an optional entry to overwrite a base receipt. Both tables share that check.
- Handoff wording permanently describing pending review/no commits was scoped
  to the dated implementation phases. The old counts and qualification records
  remain historical evidence; they were not replaced with the new results.

The package/artifact inventory representation is deliberately unchanged.
Duplicating inventory across command receipts makes direct diagnostic inspection
simple; the all-profile snapshot is about 4.1 MiB, with no demonstrated
correctness or performance problem that justifies a refactor. System providers
still validate in place, unavailable providers remain nonfatal, and no extra
applications, handwritten completions, dotfiles changes or Julia compatibility
links were introduced.

```sh
./scripts/test
./scripts/test-podman --scenario all --debug-retry
git diff --check
```

The final local suite passed **87 tests** in **28.714 seconds**, plus manifest,
Python AST, shell syntax and available ShellCheck checks. The 36 optional-provider
tests include 15 new regressions/checks for the review findings, explicit Julia
adoption, publication/receipt interruption boundaries, retained recovery copies
and normal-user filesystem permissions. These execute real Zsh and fixture
applications; controlled faults exercise failure paths that a successful network
installation would not demonstrate. A separate real-Zsh probe confirmed that
autoloading a symlink reports the selected logical provider path.

The first review integration run passed all fresh-container scenarios in
791.42 seconds and cleaned its only container,
`a339c2486c944f5776d5efa5e2c23ef99c197db59083d01d31bd663084743f7e`.
The final transaction-edge fix was completed while that session ran, so a
separate final qualification was started with runtime, manifest and test hashes
frozen. Its results and resource audit follow.

### Final qualification and resources

The final **fresh Ubuntu 26.04 x86_64** full scenario passed with exit 0 in
**637.13 seconds**, without a retry. Runtime, manifest and test hashes still
matched their pre-run snapshot afterward. The run verified fresh base isolation,
later-selected optional profiles, the actual restored Zsh environment,
generation/failure preservation, stale-source refresh, unchanged reruns and
full `--update` ownership. All engineering numerical/editor smoke checks,
shell consent paths and existing conflict recovery checks passed. The final
last-run failure list is empty.

There are **21 optional system registrations**, **19 optional unavailable
observations** and **two native Julia observations**. Including base providers,
the receipts contain 11 generated, 22 system, 19 unavailable and two native
entries. Juliaup 1.22.7 generated the installed native script; both native
commands refer to that same version/hash/arguments and validated file. The
receipt snapshot is 4.129 MiB. Dotfiles remain at the exact tested revision
`f7c3eb9ce433a1a8e285afdcda06c1da56c018fd` and the unchanged five-file selection.

Final qualification created and removed only
`19feaf72e5faa7be9aef273311048ab74c358755449e049f6eaf57b01a32a663`.
Both review sessions used the same predictable name and labels sequentially;
the first container was already removed before final qualification began.
There was no appropriate existing project container to reuse and no numbered
debugging replacement. Both `podman ps` and `podman ps -a` ran before creation
and after cleanup, and were independently repeated after each session.
Before and after: **zero running**, **the same seven unrelated stopped**,
**zero project test containers**. Unrelated IDs/names/states/exit codes match.
No unrelated container, image or volume was deleted and no global prune ran.

The fixed official `ubuntu:26.04` tag advanced between pulls; the older
preexisting approximately 112 MB cached image is now untagged and was preserved.
No custom or uniquely tagged image was built. Image inventories were inspected
after both sessions. Ignored `test-results/` contains final logs/receipts/audit;
the first review audit was preserved separately at
`/tmp/ubuntu-bootstrap-review-first-podman-session.json`.

Final `git diff --check` and local Markdown links/anchors/whitespace checks
passed, including inspection of the untracked files. The initial no-Git handoff
wording now describes implementation history and remains correct after a future
user commit. This review performed no staging, commit, push or host bootstrap
application.

Qualification remains Ubuntu-container evidence: ARM64, live WSL terminal/
Wayland behavior and hosted Actions were not tested. Rollback covers caught
exceptions/interrupts; abrupt process termination or power loss is not a durable
transaction guarantee and can leave staging/recovery files for inspection.
If the filesystem prevents restoration or cleanup, bootstrap reports the named
recovery path instead of deleting the only recovery copy. No redesign into a
persistent transaction journal was introduced.

## Cargo ownership and durable recovery — 2026-10-03

Started at clean `0a19f529457a744e5d74df55622fbb1a5894b0c9`. This coordinated
maintenance pass changes the reviewed dotfiles pin, replaces shell installers,
moves uv/Juliaup into the shared Cargo pipeline, and closes both receipt debts.
The [maintenance design](MAINTENANCE_2026-10-03.md) records trust, migration,
inventory schema, transaction state machines and limits. No host bootstrap was
applied; no files were staged, committed or pushed.

### Independent upstream review

The full new dotfiles commit is
`c44e4b8c8299f2b05ee225678daead77bf5bfbd1`, whose sole parent is the previous
reviewed `f7c3eb9ce433a1a8e285afdcda06c1da56c018fd`. Exact objects, origin and
remote HEAD were checked in an isolated inspection clone. The entire ten-file
diff (515 insertions, 20 deletions) adds colored comparison/public-sync output,
a terminal renderer and related docs/tests. Selected config files, restore,
plugin/dependency interfaces, Cargo environment sourcing and native Julia
completion sourcing are unchanged. The five-file restore set is unchanged.

Official Rustup binary/checksum endpoints and executable/CLI help were inspected,
including GNU x86_64 and aarch64 artifacts. The current reviewed init is 1.29.1;
bootstrap does not pin that ordinary version. Published uv 0.12.22 and Juliaup
1.22.7 crates, bin feature gates, actual release archives and cargo-binstall
compatibility were checked before selecting the manifest URL/layout metadata.
Real dry runs used official published manifests and successful GNU uv/musl
Juliaup paths. [UPSTREAM.md](UPSTREAM.md) contains the authorities and layouts.

### Local regressions and separate review

Final focused maintenance tests pass **26 tests**. The full `./scripts/test`
passes **113 tests**, plus manifest validation, Python AST parsing, shell syntax
and ShellCheck. `git diff --check` passes. Tests exercise strict checksum gates,
Rust order/preservation/update, lazy shared Cargo capability, binary-first and
locked fallback, migration refusal/retirement/restart, receipt migration and
inventory identity/reference integrity. Existing completion, consent, ownership,
engineering and profile regressions remain included.

Recovery tests construct persisted phases and mixed artifact/state combinations
at every publication boundary, including phase records lagging replacements,
terminal cleanup interruptions, unsafe/mismatched recovery material and failed
restoration. An `os._exit` subprocess leaves publication for startup recovery.
File/directory fsync ordering, durable new ancestry and replacement persistence
before retirement have regression coverage. Recovery failure retains named
material and suspends state-dependent work.

A separate review after the first successful full qualification checked trust,
Cargo ownership and scoped updates, legacy receipt/path/hash/type evidence, PATH
shadows, canonical inventory references, journal phases, fsync order, symlinks,
interruption boundaries, staging cleanup and accidental scope expansion. It
found and fixed three concrete defects, each reproduced by a failing regression:

- Existing symlinked Cargo/Rustup roots could redirect owned manager operations;
  secure user-owned directories are checked before verification/updates.
- Custom Juliaup depots were refused during completion preparation after runtime
  operations; the shared refusal now precedes manager/runtime operations and
  handles empty/relative overrides too.
- Failed migration retirement recovery could surface as an ordinary optional
  failure; it now stops the run and reports the exact retained transaction path.

Earlier durability review also added fsync for newly created managed directory
ancestry and for verified Cargo binaries/registration before legacy retirement.
The affected and full suites passed after the fixes. The remaining separate
review found no further defects. Runtime/manifest/test hashes were saved before
the final fresh qualification; no runtime edits are made while it runs.

### Installation evidence and measurement

The first complete fresh all-profile qualification passed in **811.50 seconds**,
exit 0, without retry, using unchanged frozen inputs. It exercised verified Rust
order, Cargo-owned uv/uvx and Juliaup/julia, the real binary-first paths and
cargo-update/Macchina locked source fallback, managed CPython, Julia release,
actual restored login-shell command resolution and native completion sourcing.
All engineering/editor smoke tests, shell consent/conflicts, ordinary second
passes, and scoped update checks passed; the unrelated Cargo fixture was untouched.
The final failure list was empty. Runtime review fixes were followed by the separate final
fresh qualification below.

Migration uses an equivalent verified legacy layout and baseline receipt formats,
constructed from official checksummed release archives, retaining working Python
and Julia data. It does not execute historical shell installers. It proves old
PATH shadowing first, migrates both managers, verifies exact launcher retirement
and Cargo command resolution, preserves runtime versions and Julia channel JSON,
keeps the unreceipted legacy `julialauncher` target, and checks a subsequent
unchanged pass. Recovery regressions also run in the Ubuntu container's isolated
temporary homes.

The measured same-input all-profile representation is **4,329,521 bytes inline →
1,145,761 bytes shared**, **73.54% smaller**: 40 command references, nine unique
inventories. The saved preceding baseline was 4,329,372 bytes; its projected
normalization was 1,145,612 bytes, also 73.54% lower. Ownership hashes and
unrelated receipt fields were not optimized. Shared snapshots/references survive
ordinary reruns and scoped updates.

### Final qualification and resources

After the final-review runtime fixes, the exact required command
`./scripts/test-podman --scenario all --debug-retry` passed a **fresh Ubuntu
26.04 x86_64** all-profile scenario, exit 0, in **2,331.14 seconds**, without any
scenario/debug retry. Runtime, manifest and test hashes all still matched the
pre-run snapshot. The last-run failure list is empty. No runtime or test edits
followed this qualification.

Compared with the first successful run, more binary paths were unavailable,
so this run additionally exercised actual locked-source installs of ripgrep,
zoxide, mcat and uv. Cargo recovered transient dependency-download errors;
uv's large release build accounts for much of the longer time. Both successful
runs used cargo-binstall first, retaining the same source fallback. Juliaup's
binary path succeeded; its locked fallback command/bin/version validation is
also covered by the focused regressions.

The final run passed actual Cargo ownership/registry/version checks and restored
login-shell resolution for uv, uvx, Juliaup and Julia; managed Python and Julia
release arithmetic; all engineering/editor checks; native/generic completion
validation and failure preservation; equivalent verified legacy migration with
unchanged runtimes/channel JSON and retired PATH shadows; deterministic startup
recovery tests inside Ubuntu; all-profile unchanged reruns; and selected owned
updates preserving the unrelated Cargo fixture and excluded/personal configs.

Final measured inventory representation: **4,329,509 → 1,145,749 bytes**, a
**73.54% reduction**, with 40 command references and nine unique snapshots. The
small difference from the first measurement comes from actual installed
completion source observations, including source-built uv. The same-input
comparison changes only inventory representation. Final receipts retain valid
shared references after reruns and updates.

Every invocation inspected both `podman ps` and `podman ps -a` before creation
and after cleanup. Independent final inspections repeated both lists. Before
and after all sessions: **zero running containers, the same seven unrelated
stopped OpenProject containers, zero project test containers**. Final audit
compares IDs, names, states and exit codes exactly; they are unchanged.

Only the following session-created containers were removed, each sequentially
under `ubuntu-bootstrap-integration` and the existing project labels:

```text
16957c7f106d6254d0a1efa691405d283aeb196ba6972270b3813e1e527a4023  interrupted early for directory durability fix
30c6eb76d6007bd320ad70d4fafee9c526e39161446ff42bdcc963c0587f45d5  first successful qualification
3e07c462b46e5d686f44c40b9ecf570248907fb71679c96f799ea9eb361c6f7b  final successful qualification after review fixes
```

The fixed 6 GiB/four-CPU limits and session-owned `--rm`/finally cleanup remain.
No borrowed or unrelated container, volume or image was deleted. No numbered
containers, custom images or global prune were used. Cached Ubuntu images were
retained. Ignored `test-results/` holds final receipts, last-run summary, log,
inventory measurement and before/after resource audit. The first successful
run's evidence is separately preserved under
`/tmp/ubuntu-bootstrap-maintenance-first-*`.

Final Markdown file/anchor and whitespace checks pass, including new files.
The final `git diff --check` passes. Handoff worktree changes comprise 22 modified
tracked files and five new files, listed in the maintenance handoff; Git HEAD
remains the actual starting commit. No staging, commit, push or host bootstrap
application occurred.

### Limits

Qualification covers the supported Ubuntu/Linux filesystem semantics exercised
by the container and deterministic crash-state/subprocess tests. It does not
claim arbitrary storage/hardware-failure protection, a whole-bootstrap
transaction, or automatic recovery of third-party Cargo installer internals.
Ambiguous INSTALLING output and unproven/unjournaled recovery material are
preserved for operator inspection. Changed/unmanaged legacy launchers are
preserved and refused. The migration test constructs verified equivalent legacy
state rather than running the historical shell installers. ARM64 installation,
live WSL/Wayland/terminal behavior and hosted Actions were not qualified here.


## Dotfiles Cargo ownership alignment — 2026-10-05

This approved update began on clean `f5a20fc`. The dotfiles pin advances from
`c44e4b8c8299f2b05ee225678daead77bf5bfbd1` to
`b0fecc41f00fa2423aaf22478f2cec98cdf15229`. Only the five existing Zsh/Git/tmux/
Starship selections are restored; `.bashrc` and `.profile` remain excluded.
The verified upstream delta and unchanged restore/plugin interfaces are recorded
in [UPSTREAM.md](UPSTREAM.md#reviewed-dotfiles-ownership-and-path-delta-2026-10-05).

Bootstrap removes the exact legacy Julia directory from its constructed
subprocess PATH, with no substring/prefix filtering. Existing Cargo installers,
receipt schemas and migration safeguards are retained. The legacy-migration test
now supplies its old launcher PATH explicitly instead of requiring the new
shell to inject it. Podman interrupted-create discovery requires the current
invocation's unique label and full container IDs; existing containers, images,
volumes and networks are not cleanup targets.

### Local checks

```sh
./scripts/test
/usr/bin/python3 -B tests/dotfiles_shell_checks.py /tmp/ubuntu-bootstrap-dotfiles-review-20261005
git diff --check
```

The full local suite passed **136 tests in 19.369 seconds**, with no failures or
skips, plus manifest loading, Python AST parsing, shell syntax and ShellCheck.
All **87 local documentation links and anchors** also passed. The actual pinned
shell probes passed with temporary HOME/ZDOTDIR/XDG roots, an explicit
environment whitelist, controlled PATH/executable
fixtures, and disabled global Zsh startup files. They cover all four Cargo
launchers against conflicting local/legacy copies, obsolete helper sentinels,
absence of Julia directory injection, similarly named inherited paths, Linux/
Windows ordering, fresh/repeated/nested startup, Cargo environment absence,
native Julia completion registration, and fnm success/failure.

Three deliberate regressions were introduced only into disposable fixture
copies: legacy uv helper sourcing, Julia directory injection, and local
launchers preceding Cargo. The probes rejected all three. The reviewed source
checkout and live user configuration remained unchanged.

### Fresh qualification and resource preservation

```sh
./scripts/test-podman --scenario all
```

The fresh Ubuntu 26.04 x86_64 all-profile run passed with **exit 0 in 592.42
seconds**, without a retry. The final run reports empty failed/skipped profile
lists. All **36 frozen runtime, manifest, script and test inputs** still match.
The full installation output, receipt snapshots and resource inventories are
retained under ignored `test-results/qualification-20261005/`, including
`final-audit.json` and the unique run identifier.

The run exercised initial installation, base/all-profile second-pass
preservation, exact selective restoration and untouched Bash/login files,
real Cargo registry/version/launcher checks, default Node availability,
isolated pinned-shell probes before and after Neovim installation, native
Julia completions and generator failure/refresh, ngspice/OpenModelica/editor
smoke tests, receipt-proven legacy migration with preserved Python/Julia runtime
and channel state, recovery regressions, and scoped updates preserving an
unrelated Cargo executable. No ownership/update policy changes were needed.

Final resource identities match the baseline: **seven unrelated stopped
containers, twelve images, two volumes and three networks** remain. Container
states, timestamps, exit codes, attachments and ports are preserved, comparing
unordered attachment lists as sets. Original image tags and digest observations
remain; the normal Ubuntu image pull added one digest observation to the same
existing image ID. Only the uniquely identified test container was removed;
there are no running or project containers. No image, volume, network or global
prune cleanup ran.

Volume metadata and network configuration also match. The built-in `podman`
network's diagnostic `created` field varies between consecutive read-only
inventory calls, so that field is excluded from the configuration comparison.

No host-user bootstrap or live configuration restore was performed. ARM64
installation, live WSL terminal/browser behavior and hosted Actions were not
qualified. Final review found no further changes needed. Nothing was staged,
committed or pushed; HEAD remains `f5a20fc`.

## CI semantics — 2026-10-05

Baseline: clean `c7dca58`, including the unit-test platform-isolation fix.
Only the Actions workflow and documentation change. Production Ubuntu 26.04
gates, manifest, unit fixtures and Podman qualification/cleanup machinery are
unchanged. The workflow retains its `unit` and `integration` job IDs and Ubuntu
24.04 orchestration hosts, with explicit display names and the full
`./scripts/test-podman --scenario all` command. Qualification is now requested
after units on pushes to `main`, while manual opt-in remains available.
See [the trigger and environment comparison](../CONTRIBUTING.md#ci-meanings-and-triggers).

### Validation performed

- Local `./scripts/test`: **136 tests in 19.451 seconds**, no failures or skips,
  plus manifest, Python AST, shell syntax and ShellCheck checks.
- The same command in a disposable real Ubuntu 24.04 container: **136 tests in
  22.864 seconds**, no failures or skips, plus the same static checks. This is
  host-independent regression evidence, not Ubuntu 26.04 qualification.
- In that Ubuntu 24.04 container, the unmodified `./bootstrap --non-interactive
  --no-change-shell` exited 1 with `Only Ubuntu 26.04 (resolute) is supported`,
  before creating bootstrap state. The real Python detector independently
  rejected the actual `/etc/os-release`. Explicit unit fixtures still exercise
  supported 26.04/architectures and unsupported-release/codename/architecture
  decisions.
- `actionlint` **1.7.11** accepted the workflow. Parsed workflow checks covered
  main/branch/tag pushes, PRs, manual opt-in/default, commands, timeout and unit
  dependency; qualification is skipped unless the triggering condition and
  successful unit dependency both hold.
- `./scripts/test-podman --scenario all`: **exit 0 in 580.10 seconds**, fresh
  x86_64 Ubuntu 26.04 container, real bootstrap/platform detection, all profiles,
  no reuse or retry. Final failed/skipped profile lists are empty. The run
  includes base/all-profile preservation, pinned-shell probes, optional-tool
  smoke checks, migration/recovery regressions and scoped update ownership.
- Local Markdown file/anchor checks and `git diff --check` passed.

### Resource audit and limits

Both disposable probes ran sequentially under the fixed project container name,
with unique per-run labels, a read-only repository mount and container-local
normal-user homes. Only their session-created full container IDs were removed.
The unchanged integration runner performed its normal before/after audits;
independent comparison also confirms **seven unrelated stopped containers,
twelve images, two volumes and three networks** are preserved. Container
states, exit codes, timestamps, ports and attachments match. Original image
identities/tags/digests remain; volume metadata and network configuration match
(excluding the built-in Podman network's read-varying diagnostic `created`
field). There are no running or project containers and no global prune ran.
All **36 frozen runtime, manifest, script and test inputs** remain unchanged.

Ignored `test-results/ci-semantics-20261005/` preserves both probe outputs,
session inventories, qualification receipts/log/status, input hashes and the
final resource audit. No host-user bootstrap was applied. These commands were
exercised locally; neither the GitHub-hosted Ubuntu 24.04 unit job nor the new
automatic hosted qualification was executed in this session. Hosted runtime,
45-minute budget, and runner-kernel behavior still require actual Actions
evidence. ARM64 and live WSL/desktop qualification remain outside this run.
Nothing was staged, committed or pushed.

## Documentation precommit review — 2026-10-05

Reviewed all ten Markdown files against the current manifest, CLI, runtime,
test architecture, workflow and preserved qualification evidence. Corrected
README branch-trigger wording, replaced the unqualified Python 3.11 minimum
claim with the verified test environments, completed the dated evidence index,
and identified the longest historical run as preceding the Cargo retry guard.
Historical pins, measurements, implementation contracts and Git snapshots remain
dated; they were not rewritten as current results.

Checks passed for **100 local file/anchor links**, **22 shell example blocks**
(syntax only), **54 package/tool identifiers**, **16 public CLI flags**,
the exact dotfiles pin/five-file selection and **14 profile dependency edges**.
`git diff --check` passed, and all **36 qualified runtime, manifest, script and
test inputs** remain unchanged. The approved workflow is also unchanged by
this documentation review. No unit or installation tests were repeated;
the preceding 136-test results, actual Ubuntu 24.04
rejection and 580.10-second fresh Ubuntu 26.04 qualification remain the relevant
evidence. External link availability and browser-rendered documentation were
not rechecked. Nothing was staged, committed or pushed.

## Permissive-umask directory safety — 2026-10-05

Implementation began on clean `de6e129`. Nothing was staged, committed or pushed.

The new regression sets umask 0002 before constructing Context, using both the
default XDG layout and missing nested custom roots. Before the production fix,
the real receipt publication failed with `Writable publication parent` because
bootstrap's recursive mkdir created 0775 ancestry. Existing completion tests
changed the mask only after Context setup and did not cover this boundary.
The failing output is retained in
`test-results/umask-20261005/before-fix-tests.log`.

Managed paths now validate existing ancestry first, create each missing component
explicitly with requested mode 0755, and fsync the new directory and its naming
parent before descendants. Pre-existing unsafe paths are preserved and refused;
there is no permission repair. The publication ancestry policy in `durability.py`
is unchanged, including its sticky-directory exception. Managed-leaf ownership,
symlink refusal and transaction/recovery rules remain enforced.

The installation-only effective mask is the caller's mask OR 0022, applied before
Context construction and inherited by child installers. Tests verify restoration
after success, handler failure, Context failure and failed shell exec, and verify
the original mask at final login-shell entry. Help and planning do not change
the mask. Directory creation itself is also tested directly under the caller's
mask, independently of the CLI policy:

| Caller mask | Installation mask | New managed directories | Receipt files |
| --- | --- | --- | --- |
| 0002 | 0022 | 0755 | 0600 |
| 0022 | 0022 | 0755 | 0600 |
| 0077 | 0077 | 0700 | 0600 |

Completion creation no longer uses post-creation chmod. Its stricter checks are
retained around creation: concurrently appearing sticky writable base/native
parents remain rejected even though generic publication permits sticky ancestry.
Two additional regressions failed before this review correction and now pass;
the failing output is retained in `before-review-fix-tests.log` in the same
evidence directory. An initial qualification was stopped for this correction;
its runner's signal/finally cleanup removed only its session-created container
and preserved all seven original container identities, states and attachments.
It is not counted as successful qualification.

### Local checks

```sh
PYTHONPATH=tests /usr/bin/python3 -B -m unittest -v \
  test_logic test_maintenance test_completions test_optional_completions
./scripts/test
git diff --check
```

The corrected focused suite passes **127 tests in 44.393 seconds**. The full
suite passes **149 tests in 47.545 seconds**, without failures or skips, plus
manifest loading, Python AST parsing, shell syntax and ShellCheck. The 13 new
tests cover the root-cause seam, nested XDG creation, unsafe-path preservation,
direct publication rejection, symlinks, concurrent directory appearance, child
mask inheritance/restoration and restrictive base/native completion creation.
The existing ancestry durability regression additionally checks safe permissions
under 0002 at its fsync boundary. Existing ownership, migration, recovery,
completion and Podman cleanup regressions remain included.

The documentation review follows the existing CONTRIBUTING checklist: local
links/anchors, shell example syntax, public CLI flags, exact dotfiles pin/five-file
selection, defaults and manifest dependency edges. Historical evidence remains
dated. No host-user bootstrap or live configuration restore was performed.

### Fresh qualification and resources

```sh
./scripts/test-podman --scenario all
```

The final fresh Ubuntu 26.04 x86_64 run passed with **exit 0 in 577.68 seconds**,
without reuse or retry. It used the normal `engineer` user, real platform
detection and scoped sudo. Freshness assertions required absent `.local` and
`.cache` ancestry before installation; fixtures did not pre-create or chmod
managed paths. All five scenario bootstrap invocations set and verified **0002
after Bash login startup**, before Stage 0. Unrelated integration fixtures use
0022 independently.

After base and engineering installation, all eleven checked managed directories
were user-owned 0755: `.local`, `.local/share`, `.local/state`, `.cache`, their
three `ubuntu-bootstrap` leaves, `.cargo`, `.cargo/bin`, `.rustup` and `.zfunc`.
Receipts were 0600, and `.cargo/env` passed the regular-file safety check.
Base/all-profile second passes, pinned-shell/Cargo resolution, optional-tool
smoke checks, native Julia completions, equivalent verified legacy migration,
deterministic recovery/retry regressions and scoped updates all passed. The final
failed/skipped profile lists are empty. All **36 frozen runtime, manifest,
script and test inputs** still match; no runtime or test edits followed the
successful qualification.

The independent resource comparison confirms **seven original stopped
containers, twelve images, two volumes and three networks** are preserved.
Container identities, states, exit codes, timestamps, ports, mounts and network
attachments match; unordered attachment lists are compared as sets. Original
image metadata/tags/digests and volume metadata match, with no new image IDs or
digest observations. Network configuration matches; the built-in `podman`
network's read-varying diagnostic `created` field is excluded. There are no
running or project containers. No image, volume, network or global prune cleanup
ran. The runner itself is unchanged and removed only the uniquely identified
container created by each invocation:

- Interrupted review run: `7e1026784c2c320362101ceb4a2373069dad54bb03c240f551c11e1ccf16a4a9`.
- Successful final run: `5e174c6756b1d629d72b94c162a531b49d5282ad5bb27d56b159d09a8e1f4814`.

Ignored `test-results/umask-20261005/` retains failing/passing unit outputs,
observed modes, interrupted and successful qualification outputs, receipts,
state/log snapshots, frozen input hashes, documentation checks and before/after
resource inventories. `final-audit.json` records the successful run ID
`cf4c908a00be408a9b36ef6280e2189f`, complete resource comparisons and input checks.
The temporary documentation/resource check scripts are also retained there.
Final documentation checks pass **101 local links/anchors**, **24 shell example
blocks**, all **16 public CLI flags** and the manifest/restore/dependency
contracts. `git diff --check` passes. Nothing was staged, committed or pushed;
HEAD remains `de6e129`.

### Limits

Qualification uses controlled login Bash startup with non-interactive bootstrap
and the existing separate PTY consent checks; it does not qualify a live WSL
terminal or desktop/Wayland session. ARM64 and hosted GitHub Actions were not
run. The original mask's restoration at final login-shell exec is regression
tested with a controlled exec boundary. Existing path checks remain path-based;
this change does not claim complete resistance to concurrent same-user/root
path replacement or arbitrary storage/hardware failure, nor transactional
recovery of third-party installer internals. Pre-existing unsafe paths remain
an operator-review boundary.
