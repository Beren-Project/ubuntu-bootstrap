# Usage and recovery

Run from the repository as your normal user with sudo access, on Ubuntu 26.04
(`resolute`). x86_64 WSL2 is the primary target; native Ubuntu uses the same paths.
ARM64 is best effort. Sudo is scoped to APT, system publication and a consented
change of the original user's shell. User installers, source builds and
completion generators run without sudo; installer shell/PATH edits are disabled.

## Choose a run

Default profiles are always selected: `apt`, `rust`, `cargo`, `python`, `node`,
`dotfiles`. Optional profiles add to them; there is no single-tool-only mode.

```sh
./bootstrap                                  # Interactive menu and shell consent
./bootstrap --ngspice --openmodelica --nvim    # Direct optional selection
./bootstrap --non-interactive --no-change-shell
./bootstrap --plan --openmodelica             # See Stage-0 exception below
```

| Flag | Behavior and interaction |
| --- | --- |
| `-h`, `--help` | Show CLI help. A first-argument help request works without system Python and does not install it. |
| `--build` | Add the general build package set. |
| `--julia` | Add Juliaup and Julia's `release` channel. |
| `--ngspice` | Add pinned ngspice; automatically select `build`. |
| `--openmodelica` | Add signed official `omc` CLI; depends on `apt`, not `build`. |
| `--vim`, `--nvim`, `--emacs` | Independently add editors; multiple selections may coexist. |
| `--yes` | Omit the optional menu and accept Zsh consent unless an explicit shell flag overrides it. ARM64 unqualified components default to No. Does not suppress sudo credentials or permit a terminal-free run by itself. |
| `--non-interactive` | Disable prompts and use `sudo -n`; requires an explicit shell choice except with `--plan`. `--yes` does not satisfy that requirement. |
| `--change-shell` | Consent to setting the original user's login shell to installed, allowed Zsh; skip the consent prompt. |
| `--no-change-shell` | Preserve the login shell and print a later `chsh` command. Mutually exclusive with `--change-shell`. |
| `--update` | Update selected owned channel-managed components and selected APT packages; repeat optional flags for optional tools. |
| `--adopt COMPONENT` | Reconcile a reviewed existing installation with ownership checks; repeat for multiple names. Does not select an optional profile or waive validation. |
| `--attempt-unqualified COMPONENT` | Explicit ARM64 opt-in; repeat per component. Does not select an optional profile. |
| `--plan` | Print JSON architecture, resolved profiles, dotfiles selection and update choice; no menu or module installation handlers. Stage 0 may first install missing system Python. |

With no optional flags, the interactive menu accepts shown names separated by
spaces (for example, `ngspice nvim`); Enter means base only. Any optional flag, `--yes`, `--non-interactive` or
`--plan` suppresses it. Unknown options/components fail.

**Stage-0 exception:** the shell entry point checks normal-user entry, release
and architecture, then obtains missing `/usr/bin/python3` with sudo/APT, even
for `--plan`. First-argument help bypasses this. With Python present, planning
validates platform/user/HOME/layout and prints configuration without a normal
run context. It is not an ownership, network or APT-candidate preflight, and
does not apply ARM64 decline decisions.

Shell consent defaults to Yes. Bootstrap checks `/etc/shells`, changes only the
original user's passwd entry and verifies it. After a successful consented run,
it enters a Zsh login session only with interactive input/output and outside CI.
Non-interactive runs never enter Zsh. `--no-change-shell` still installs Zsh,
shared configs and completions; use `zsh -l` yourself when ready.

On ARM64, `dotfiles`, `ngspice`, `nvim` and Cargo crate `cargo-update` are
unqualified. Interactive `Attempt installation anyway? [y/N]` defaults to No;
`--yes`/automation skip them unless explicitly named. For Neovim, use both
`--nvim` and `--attempt-unqualified nvim`. Supported components select ARM64
artifacts; opting in does not establish qualification.

## Installation inventory

These are manifest-requested packages/tools, not every transitive dependency.
APT resolves declared dependencies with `--no-install-recommends`.

### Default system packages

Every row belongs to default profile `apt`, with Ubuntu APT as installer/owner.

| Package | Command when relevant | Purpose |
| --- | --- | --- |
| ca-certificates | — | Trusted certificates for HTTPS. |
| curl | `curl` | HTTP transfers and installer prerequisite. |
| git | `git` | Version control and pinned checkout verification. |
| gh | `gh` | GitHub CLI and shared Git credential helper. |
| python3 | `/usr/bin/python3` | Bootstrap/upstream-script runtime, separate from user Python. |
| zsh | `zsh` | Shared shell and completion validation. |
| tmux | `tmux` | Terminal session multiplexer. |
| fzf | `fzf` | Interactive fuzzy selection. |
| wl-clipboard | `wl-copy`, `wl-paste` | Wayland clipboard commands; live use needs a compositor/session. |

### Default user tools and runtimes

Cargo binaries live in `~/.cargo/bin`. “Cargo” below means binary-first
cargo-binstall, with one stable crates.io version used for both the binary attempt
and controlled `cargo install --locked --version VERSION` fallback. Known network
failures or unavailable binaries can use the fallback with automatic prerequisites;
metadata, archive, integrity and installation errors stop with diagnostics.
Announced GitHub API retry sleeps have a five-second cumulative budget; a longer
proposed wait is cancelled before sleeping through it. Ordinary request latency
retains upstream's 15-second timeout per resolution candidate. No GitHub token is
required. Explicit `GITHUB_TOKEN`/`GH_TOKEN` values are passed to cargo-binstall;
credential discovery is disabled and values are redacted from its log. See
[the retry policy and validation evidence](CARGO_RETRY_2026-10-03.md).

| Tool/package | Command(s) | Purpose | Installer/owner |
| --- | --- | --- | --- |
| rustup | `rustup` | Rust toolchain management. | Verified official rustup-init binary; `rust` profile. |
| Rust stable/minimal | `rustc`, `cargo` | Compiler and package/build manager. | rustup; `rust` profile. |
| cargo-binstall | `cargo-binstall` (`cargo binstall`) | Binary-first Cargo application installer. | Verified official archive; `cargo` profile. |
| cargo-update | `cargo-install-update`, `cargo-install-update-config` | Cargo update utilities; bootstrap updates through explicit binstall operations. | Cargo; `cargo` profile; ARM64 unqualified. |
| starship | `starship` | Shared shell prompt. | Cargo; `cargo` profile. |
| bat | `bat` | Syntax-highlighted file viewing. | Cargo; `cargo` profile. |
| eza | `eza` | Directory listings. | Cargo; `cargo` profile. |
| fd-find | `fd` | File-name search. | Cargo; `cargo` profile. |
| fnm | `fnm` | Node version/default management. | Cargo; `cargo` profile. |
| git-delta | `delta` | Diff viewer and shared Git pager. | Cargo; `cargo` profile. |
| ripgrep | `rg` | Recursive text search. | Cargo; `cargo` profile. |
| zoxide | `zoxide` | Shell directory navigation. | Cargo; `cargo` profile. |
| macchina | `macchina` | System information display. | Cargo; `cargo` profile. |
| mcat | `mcat` | Terminal content viewer. | Cargo; `cargo` profile. |
| uv | `~/.cargo/bin/uv`, `~/.cargo/bin/uvx` | Python environment/package tools and interpreter installation. | Cargo via binstall/source fallback; `python` profile; receipt owner `uv`. |
| Managed CPython | `~/.local/bin/python`, `~/.local/bin/python3` | Stable user development interpreter launchers. | uv; `python` profile; receipt owner `python`. |
| Node LTS | `node` in the fnm-selected environment | JavaScript runtime and managed LTS default. | fnm; `node` profile. |
| Shared dotfiles | Configuration files | Configure Zsh, Git, tmux and Starship. | Pinned upstream `restore.py`; `dotfiles` profile. |
| Standalone Zsh plugins | Shell integrations | Shared shell plugin integrations. | Pinned upstream `install_zsh_plugins.py`; [exact revision's plugin inventory](https://github.com/Beren-Project/dotfiles-public/blob/b0fecc41f00fa2423aaf22478f2cec98cdf15229/scripts/zsh-plugins.json). |

System Python is never the pip development environment. Project dependencies
and environments remain user actions. Versions are channels, not new pins:
Rust `stable`/minimal, Python `cpython` (stable managed CPython), Node `lts`, and
optional Julia `release`. Ordinary Cargo versions are unpinned. Receipts record
observed versions/hashes; immutable dotfiles/ngspice choices live in the
[manifest](../config/bootstrap.toml). See [upstream interfaces](UPSTREAM.md).

### Optional applications

| Selection | Package/tool | Command | Purpose | Installer/owner |
| --- | --- | --- | --- | --- |
| `--julia` | Juliaup | `~/.cargo/bin/juliaup` | Manage Julia release channel. | Cargo via binstall/source fallback. |
| `--julia` | Julia | `~/.cargo/bin/julia` | Technical/numerical computing. | Cargo-owned launcher; Juliaup owns runtime/`release` channel. |
| `--ngspice` | ngspice 47 | `ngspice` | SPICE circuit simulation. | Verified pinned source; user build/staging, system publication. |
| `--openmodelica` | omc | `/usr/bin/omc` | OpenModelica modeling/simulation CLI. | Signed official `resolute`/stable APT repository, no GUI recommendations. |
| `--vim` | vim | `vim` | Terminal editor. | Ubuntu APT. |
| `--nvim` | Neovim | `nvim` | Terminal editor. | Verified official stable archive; system publication. |
| `--emacs` | emacs-nox | `emacs` | Terminal Emacs editor. | Ubuntu APT. |

OpenModelica depends on `apt`, **not** `build`; APT may install compilers required
by `omc` itself. Official signatures, key fingerprints, resolute/architecture,
channel and candidate are checked. Missing official support fails clearly;
another Ubuntu suite is never substituted.

### Build and installer dependencies

All rows below are explicit additional Ubuntu APT packages. “Build” means
`--build`, also implied by `--ngspice`; “source fallback” means Cargo's locked
source build, even without a build profile.

| Package | Command when relevant | Purpose | Selection |
| --- | --- | --- | --- |
| build-essential | Compiler/Make toolchain via dependencies | Native builds. | Build or source fallback. |
| pkg-config | `pkg-config` | Native library build flags. | Build or source fallback. |
| cmake | `cmake` | CMake build configuration. | Build. |
| ninja-build | `ninja` | Ninja build executor. | Build. |
| libssl-dev | — | OpenSSL development files. | Source fallback. |
| gnupg | `gpg`, `gpgv` | Key processing and release signature verification. | `--openmodelica`. |
| bison | `bison` | Parser generation. | `--ngspice`. |
| flex | `flex` | Scanner generation. | `--ngspice`. |
| libx11-dev | — | X11 development files. | `--ngspice`. |
| libxaw7-dev | — | X Athena widget development files. | `--ngspice`. |
| libxmu-dev | — | X utility development files. | `--ngspice`. |
| libxext-dev | — | X extension development files. | `--ngspice`. |
| libxft-dev | — | X font rendering development files. | `--ngspice`. |
| libfontconfig-dev | — | Font configuration development files. | `--ngspice`. |
| libxrender-dev | — | X rendering development files. | `--ngspice`. |
| libfreetype-dev | — | Font rendering development files. | `--ngspice`. |
| libreadline-dev | — | Line-editing development files. | `--ngspice`. |
| libfftw3-dev | — | FFT development files. | `--ngspice`. |
| libsndfile1-dev | — | Audio file I/O development files. | `--ngspice`. |
| libsamplerate0-dev | — | Sample-rate conversion development files. | `--ngspice`. |

Ngspice uses checksum-verified source with `--with-x --enable-cider
--disable-debug` and `make -j2`. Its source/configuration is pinned, not a latest
channel.

## Shared configuration and reruns

Dotfiles revision **`b0fecc41f00fa2423aaf22478f2cec98cdf15229`** supplies only:

```text
.zshrc
.zshenv
.gitconfig
.tmux.conf
.config/starship.toml
```

Bootstrap verifies the machine checkout's origin, exact HEAD, clean
tracked/untracked/ignored state and index flags. It runs the upstream dependency
report/plugin installer, then preview and apply through `scripts/restore.py`
using the same five repeatable `--file` arguments, never a broader `--profile`.
Upstream backup, symlink, overlap and conflict protections apply. Bash, `.profile`,
Zellij and Mermaid configs are excluded; missing optional tools in the upstream
dependency report are informational.

The current Zsh configuration resolves uv/uvx and Juliaup/Julia from
`~/.cargo/bin`. It does not source `~/.local/bin/env` or add `~/.juliaup/bin`.
Julia state and native completions remain under `~/.julia/juliaup/`.
Inherited Linux/Windows PATH ordering is retained after Cargo, with conditional
`~/bin` and `~/.local/bin` last; interactive fnm and Neovim preferences precede
the base PATH. Existing Bash/login files are not overwritten by this update.

**First runs and reruns apply the five selected shared configs.** Existing
differing selected files can be backed up under `~/.dotfiles-backups/` and
replaced with pinned contents, subject to upstream symlink and conflict
protections. Identical files create no backup or replacement. Reruns preserve
verified working tools. Review local customizations before either run; keep
personal Git settings in
`~/.gitconfig.local`. Keep human development clones separate from the managed
checkout. Pinned plugin checkouts retain their upstream installer owner.

## Finish personal setup

After successful installation, use the Zsh session bootstrap opened, or run
`zsh -l` if you declined the shell change. Check the base environment without
installing or updating anything:

```sh
zsh --version
gh --version
rustup show active-toolchain
uv --version
python --version
fnm default
node --version
```

Rust should report the stable toolchain, and Node should match the fnm default.
If a command is missing, inspect its expected path and shell startup using the
[recovery guide](#troubleshooting-by-task). These checks do not qualify live
clipboard behavior or every WSL terminal integration.

Supply your own identity, replacing these examples with your details:

```sh
git config --file ~/.gitconfig.local user.name "Your Name"
git config --file ~/.gitconfig.local user.email "you@example.com"
git config --global --get user.name
git config --global --get user.email
```

The shared Git configuration uses gh as GitHub credential helper. When needed,
run `gh auth status` and deliberately authenticate with `gh auth login`.
Bootstrap creates no identity, credentials, tokens or SSH keys and does not
authenticate accounts. Existing personal files and credentials are preserved.
Project environments, terminal/Nerd Font setup and live Wayland clipboard use
are user/session tasks, separate from installed commands.

## Updates and ownership

```sh
./bootstrap --non-interactive --no-change-shell --update --nvim --julia
```

The manifest defines desired ownership/channels/pins; receipts are observed
paths, versions and hashes. Normal reruns verify manager state and expected
paths/hashes, install missing managed components and preserve working tools.
`--update` follows selected managers' channels and requests selected APT
packages/dependencies without a distribution upgrade. Cargo operations name
manifest crates individually; unrelated applications are excluded. Optional
tools are not selected because an old receipt exists. Dotfiles/ngspice pins
do not advance with updates.

Unmanaged tools and external replacements are preserved and reported. Inspect
origin, path, owner and manager metadata before adopting. Accepted names are
`rust`, `cargo-binstall`, `uv`, `python`, `node`, `juliaup`, `julia`, `nvim`, `ngspice`, plus
the eleven manifest crates: `cargo-update`, `starship`, `bat`, `eza`, `fd-find`,
`fnm`, `git-delta`, `ripgrep`, `zoxide`, `macchina`, `mcat`. Use crate names,
not aliases such as `fd`. Optional adoption still needs selection, for example
`--nvim --adopt nvim`.

Adoption enforces expected owner/type, versions and manager state; Cargo needs
matching crates.io metadata/binaries. Partial unmanaged installations need
inspection. Incompatible custom `CARGO_HOME`, `RUSTUP_HOME`, `UV_PYTHON_BIN_DIR`
and `UV_PYTHON_INSTALL_DIR` are refused. Receipt loss does not authorize deleting
tool trees or adopting everything. Completion conflicts have a separate policy.

## Zsh completions

Supported commands are `gh`, `rustup`, `cargo`, `uv`, `uvx`, `fnm`, `starship`,
`rg`, `fd`, `bat`, `delta`, `mcat`. The shared Zsh config adds `~/.zfunc` to
`fpath` before `compinit`.

- Correct discoverable system providers take precedence. Ubuntu's `_gh` remains
  system-owned; a system provider supersedes only an unchanged receipt-verified
  generated copy, which bootstrap can remove.
- Generators run as the normal user into a temporary file, checked for matching
  `#compdef`, autoload code and Zsh syntax before atomic publication to `_COMMAND`.
- Generator hash, reported version and arguments determine freshness. Matching
  files are preserved; changed sources regenerate them, including after updates.
- Completion errors return nonzero but preserve the application and previous
  completion; independent work can continue.
- Unmanaged/edited/symlinked/wrong-owner files are preserved and refused; receipt
  loss does not authorize replacement. Unrelated `.zfunc` files stay untouched.
- The directory must be user-owned, without symlinked paths or group/other write
  bits; insecure directories are refused because `compinit -i` ignores them.

Eza has no selected standalone runtime generator; zoxide retains its shell
integration. Optional completion provisioning is conditional on profile
selection. No extra apps are installed for completions.

| Selected profile | Completion result |
| --- | --- |
| `--vim`, `--nvim` | Validate shared Ubuntu `_vim` and actual Zsh registration; no user duplicate |
| `--julia` | Generate the official sourced integration at `~/.julia/juliaup/completions/zsh.zsh`; validate `juliaup` and `julia +channel` |
| `--build` | Validate package-owned compiler/Make/pkg-config/Ninja, Binutils and Debian build providers; explicitly report inspected tools without a supported provider |
| `--ngspice` | Validate selected build dependencies plus Bison/Flex; report application completion unavailable when none is qualified |
| `--openmodelica`, `--emacs` | Inspect installed CLI packages and report application completion unavailable when none is qualified |

Unavailable completion is a nonfatal `SKIP`; it does not mean the application
failed installation. Unselected profiles prepare no artifacts; adding a profile
on a later run prepares its declared integration then. System completion files
remain package-owned. See the exact [provider mapping](OPTIONAL_COMPLETIONS_PLAN.md#inspected-provider-mapping) and
[verified interfaces](UPSTREAM.md#zsh-completion-interfaces).

Juliaup's native script is sourced by the pinned dotfiles after `compinit`; it
does not use the `.zfunc/_COMMAND` autoload format. Unchanged valid output keeps
its timestamp; an updated generator refreshes it atomically. Generation or final
registration failure preserves a previous working file. Personal/unmanaged
native scripts are preserved and refused; after reviewing the manager and script,
explicit `--julia --adopt julia` also permits reconciliation of this integration.
This exception does not adopt other `.zfunc` files. Custom `JULIAUP_DEPOT_PATH`
values incompatible with the pinned native location are refused.

Native scripts and existing parents writable by group/others are preserved and
refused, including on ordinary reruns. Newly created native directories are 0755
and generated scripts are 0644 even with a permissive umask. Publication and
the paired native receipts roll back on caught failures/interruption before
commit. After commit, later interruption or recovery-copy cleanup failure keeps
the matching new script and receipts intact. If rollback
itself fails, bootstrap reports the exact retained script/receipt backup path;
inspect that recovery copy before making any manual repair.

## Paths and diagnostics

| Path | Role/owner |
| --- | --- |
| `${XDG_DATA_HOME:-$HOME/.local/share}/ubuntu-bootstrap/dotfiles/<SHA>` | Verified machine checkout; normal user. |
| `${XDG_DATA_HOME:-$HOME/.local/share}/zsh/plugins` | Upstream pinned plugin checkouts; normal user. |
| `${XDG_CACHE_HOME:-$HOME/.cache}/ubuntu-bootstrap` | Downloads and temporary installer/build staging; normal user. |
| `${XDG_STATE_HOME:-$HOME/.local/state}/ubuntu-bootstrap/bootstrap.log` | Appended command/output log across runs. |
| Same state directory: `last-run.json` | Last summary-completed run's profiles, results, failures/skips; can be absent/stale after early failure. |
| Same state directory: `receipts.json` | Ownership/version/hash observations. |
| Same state directory: `lock` | Process-held nonblocking run lock. |
| `~/.cargo`, `~/.rustup` | User Rust/Cargo tools and toolchains. |
| `~/.local/bin` | User Python launchers; optional ARM64 Neovim link. |
| `~/.cargo/bin` | Cargo applications, including uv/uvx and optional Juliaup/julia. |
| `~/.juliaup` | Legacy remaining files are preserved after exact launcher migration. |
| `~/.julia/juliaup/completions/zsh.zsh` | Optional Juliaup native sourced completion, generated as the user. |
| `~/.zfunc` | Generated user completions. |
| `~/.dotfiles-backups` | Upstream restore backups. |
| `~/.gitconfig.local` | Personal Git settings, outside restore selection. |
| `/opt/ubuntu-bootstrap/ngspice-47`, `/usr/local/bin/ngspice` | Pinned simulator tree and system command link. |
| `/opt/nvim-linux-x86_64/bin` or `/opt/nvim-linux-arm64/bin` | Optional official editor tree; shared x86_64 PATH or ARM64 user-bin link. |
| `/etc/apt/sources.list.d/ubuntu-bootstrap-openmodelica.list` | Managed official resolute/stable source. |
| `/usr/share/keyrings/ubuntu-bootstrap-openmodelica.gpg` | Verified official key. |
| Beside system trees: `*.ubuntu-bootstrap-previous-<timestamp>` | Retained working predecessors. |
| Beside system trees: `*.ubuntu-bootstrap-new` | Publication staging, preserved if interrupted. |

Console statuses and the summary distinguish installation, discovery, update,
skip and errors, and print the log path. Failures return nonzero; interruption
returns 130. Base-handler failure stops further handlers; optional failures can
allow independent work and skip dependents. Completion errors are separate.
Successful earlier changes remain; a failed run is not a complete rollback.

## Troubleshooting by task

Start with the latest error, printed log path and last run record:

```sh
bootstrap_state="${XDG_STATE_HOME:-$HOME/.local/state}/ubuntu-bootstrap"
tail -n 80 "$bootstrap_state/bootstrap.log"
/usr/bin/python3 -m json.tool "$bootstrap_state/last-run.json"
```

The log includes earlier runs. `last-run.json` can be absent/stale after early
failure. Correct the specific cause and rerun with the same optional selection
and shell choice; `--update` is not a generic repair switch.

| Task/error | Inspect first | Next action |
| --- | --- | --- |
| Entry/platform/sudo/terminal failure | `/etc/os-release`, `uname -m`, `id`, HOME owner; `sudo -n true` for automation. | Use supported Ubuntu and normal-user entry; supply explicit automation shell choice or an interactive terminal. |
| Another bootstrap is running | Existing process/session holding the lock. | Finish/investigate that run; do not delete the lock to bypass it. |
| Unmanaged or externally changed tool | Exact path, command version, owner, receipt and manager listing; Cargo registry metadata for crates. | Explicitly adopt only a reviewed compatible component, or preserve it while investigating. |
| Replaced shared config | Corresponding `~/.dotfiles-backups/` file and installed/pinned contents. | Compare before deliberate recovery; another rerun reapplies the pinned selection. |
| Dirty/wrong-origin/pinned checkout | Exact managed checkout's status (including ignored/untracked files), origin and HEAD. | [Preserve the entire reviewed checkout, then refetch the pin](#recover-the-managed-dotfiles-checkout). |
| Missing command/PATH integration | Expected inventory path, `command -v TOOL`, version, `.zshenv`/`.zshrc`; whether ARM64 dotfiles was declined. | Review startup and open a new Zsh login session; installers do not edit PATH. |
| Shell-change failure | Original user's passwd entry, `/etc/shells`, sudo/PAM error. | Fix the specific problem; use the printed later `chsh` command if consent was deferred. |
| Completion generation/conflict | Named artifact, owner/type/mode, receipt and installed generator. | Correct generator failure, or preserve the exact reviewed conflicting file elsewhere before rerunning. Base `.zfunc` files have no adoption flag; reviewed native Julia integration permits explicit `--julia --adopt julia`. |
| Insecure completion directory | `.zfunc` ownership, symlinks and group/other write bits. | Make only the reviewed specific correction; avoid recursive permission changes or deleting the directory. |
| Download/checksum/signature/APT candidate | Latest command/error and official source availability. | Correct connectivity/prerequisites, or ask maintainers to review changed upstream trust/interfaces. Keep verification enabled. |
| Conflicting OpenModelica source | Exact managed and existing APT sources named in the error. | Review reconciliation; do not substitute an older Ubuntu suite. |
| Interrupted system publication | Destination, `.ubuntu-bootstrap-new`, retained predecessors and command links. | Preserve artifacts for deliberate recovery. A failed final rename attempts to restore the predecessor. |
| Clipboard or font issue | Installed binaries and current Wayland/terminal session. | Review session/font setup; container binary checks do not establish live WSL behavior. |

For example, inspect a completion with `ls -ld ~/.zfunc`,
`ls -l ~/.zfunc/_fnm` and `/usr/bin/zsh -n ~/.zfunc/_fnm`. After successful
repair, start a new Zsh session. Avoid broad clean/reset/delete, recursive
ownership changes or blanket adoption as recovery steps.

### Recover the managed dotfiles checkout

With no bootstrap run active, inspect the exact machine-managed checkout named
in the error as your normal user. This applies only to
`${XDG_DATA_HOME:-$HOME/.local/share}/ubuntu-bootstrap/dotfiles/b0fecc41f00fa2423aaf22478f2cec98cdf15229`,
not a development clone or a checkout under `zsh/plugins`. Review that path
before using the example:

```sh
bootstrap_checkout="${XDG_DATA_HOME:-$HOME/.local/share}/ubuntu-bootstrap/dotfiles/b0fecc41f00fa2423aaf22478f2cec98cdf15229"
ls -ld "$bootstrap_checkout"
git -C "$bootstrap_checkout" remote get-url origin
git -C "$bootstrap_checkout" rev-parse HEAD
git -C "$bootstrap_checkout" status --short --untracked-files=all --ignored
git -C "$bootstrap_checkout" ls-files -v
```

Expected origin is `https://github.com/Beren-Project/dotfiles-public.git` and
expected HEAD is `b0fecc41f00fa2423aaf22478f2cec98cdf15229`. Status must include
ignored files; lowercase tags or `S` in `ls-files -v` indicate index flags that
can hide changes. Preserve these findings for review. If the path is a symlink
or is not an ordinary checkout, investigate that specific error before moving it.

To preserve a reviewed checkout intact, choose an **unused backup destination
outside the active checkout path**, with an existing parent directory. Adjust
this example destination first; it refuses an existing file, directory or
symlink and never merges into another directory:

```sh
bootstrap_checkout_backup="$HOME/dotfiles-checkout-backup-2026-10-02"
if [ -e "$bootstrap_checkout_backup" ] || [ -L "$bootstrap_checkout_backup" ]; then
    printf '%s\n' "Backup destination already exists; choose another unused path."
else
    mv -T --no-clobber -- "$bootstrap_checkout" "$bootstrap_checkout_backup"
fi
```

Only after confirming the move succeeded and the original checkout path is
absent, rerun your original bootstrap command with the same optional selections
and shell choice. Bootstrap fetches the missing checkout at the same pin and
verifies origin, HEAD, cleanliness and index flags before using it; the restore
still selects only the five configs above with upstream protections. Keep the
backup for deliberate comparison or recovery. Do not move unrelated development
or plugin checkouts, or delete, reset or clean them; no system configuration
change is needed for this checkout recovery.

Bootstrap does not provision Windows/WSL, fonts, host networks or project
environments. Check [dated qualification limits](VALIDATION.md) before treating
container evidence as live WSL qualification. For contributor checks and source
changes, see [CONTRIBUTING.md](../CONTRIBUTING.md),
[architecture](ARCHITECTURE.md) and [upstream notes](UPSTREAM.md).

## Cargo-owned Python and Julia managers

Cargo owns uv/uvx and Juliaup/julia in `~/.cargo/bin`; uv owns managed CPython,
and Juliaup owns the Julia `release` channel in the existing depot. `--update`
updates the selected manager crate through cargo-binstall/locked source fallback
first, then the managed runtime. Bootstrap does not call either manager's binary
self-update command. Python/Julia prerequisites do not select the Cargo CLI
collection, although the normal default selection still includes that collection.

Verified baseline receipts migrate automatically after replacement validation.
Only unchanged, proven `.local/bin/uv`, `.local/bin/uvx`, `.juliaup/bin/juliaup`
and `.juliaup/bin/julia` launchers are retired. The supported legacy Julia symlink
is removed as a link; its unreceipted `julialauncher` target is preserved. Changed,
unmanaged or unsafe launchers are retained and cause a clear failure, including
when adoption flags are supplied. Python environments and Julia data/channels
remain intact. `--adopt juliaup` separately covers reviewed Cargo manager adoption;
`--adopt julia` retains its runtime/native-completion meaning.

The state directory's `transaction/` contains a journal and required recovery
material during coupled publication. Startup reconciles it before ownership
checks. Before completion commit it restores prior artifacts/receipts; verified
launcher retirement rolls forward. If recovery fails, preserve the reported
material for inspection. An interrupted Cargo install before durable replacement
evidence is not automatically adopted. See [the state machines and limits](MAINTENANCE_2026-10-03.md).
