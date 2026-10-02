# Validation

This is a dated evidence index, not a promise that every scenario ran at the
current revision. The implementation documented here is `f5e841a`; its core baseline and
completion follow-up were subsequently committed by the user after the original
implementation agents finished without committing or pushing.

| Record | Code/evidence scope | Local suite | Real installation evidence |
| --- | --- | --- | --- |
| [Core qualification — 2026-10-01](#core-qualification--2026-10-01) | Original core implementation, subsequently committed as `ec3df7f` | 35 tests plus static checks | Fresh x86_64 Ubuntu 26.04, all profiles, 1000.62 s |
| [Completion follow-up — 2026-10-02](#completion-follow-up--2026-10-02) | Completion implementation, subsequently committed as `f5e841a` | 51 tests plus static checks | Fresh x86_64 Ubuntu 26.04, focused base scenario, 233.28 s |
| [Documentation follow-up — 2026-10-02](#documentation-follow-up--2026-10-02) | Documentation-only changes on `f5e841a`; implementation unchanged | 51 tests plus static and documentation checks | No installation run; earlier qualification unchanged |

The focused completion run did not reinstall the all-profile engineering
baseline. New documentation verification belongs in a separate dated record;
it does not extend installation qualification. Contributor commands and
resource discipline are described in [CONTRIBUTING.md](../CONTRIBUTING.md).

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
