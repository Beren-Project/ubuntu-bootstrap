# ubuntu-bootstrap

Turn an already installed **Ubuntu 26.04 (resolute)** environment into a team
engineering/development workstation. Ubuntu 26.04 on WSL2, x86_64 is the primary
target. Native Ubuntu uses the same installation paths; ARM64 is best effort and
is not qualified by v1 integration tests. Other releases/distributions fail early.

## Quick start

If Git is missing, first run `sudo apt-get update && sudo apt-get install -y git`,
or download and extract the repository archive.

```sh
git clone https://github.com/Beren-Project/ubuntu-bootstrap.git
cd ubuntu-bootstrap
./bootstrap
```

Run as your **normal user**, with sudo access. Do **not** run `sudo ./bootstrap`.
Choose optional components from the menu, then answer:

```text
Change your default shell to Zsh? [Y/n]
```

Yes is the default. Bootstrap verifies the login-shell change and, on successful
interactive completion, enters a Zsh login session. No leaves your login shell
alone and prints the command you can run later.

Select components directly if preferred:

```sh
./bootstrap --ngspice --openmodelica --nvim
```

For automation, explicitly decide whether to change the login shell:

```sh
./bootstrap --non-interactive --no-change-shell
./bootstrap --non-interactive --change-shell --build
```

Automation requires working `sudo -n`. `--yes` accepts interactive defaults and
omits the optional menu; use `--non-interactive` for runs without a terminal.
`./bootstrap --plan` prints the resolved configuration without installation.

## What is installed

| Owner | Default components |
| --- | --- |
| Ubuntu APT | ca-certificates, curl, git, gh, python3, **zsh**, tmux, fzf, **wl-clipboard** |
| rustup | Stable Rust, minimal toolchain |
| Cargo | cargo-binstall, cargo-update, starship, bat, eza, fd-find (`fd`), fnm, git-delta (`delta`), ripgrep (`rg`), zoxide, macchina, mcat |
| uv | uv/uvx and a managed stable CPython with user-local Python launchers |
| fnm | Current Node LTS, made the managed default |
| dotfiles-public | Five selected shared configs and pinned standalone Zsh plugins |

Ubuntu Python runs bootstrap; it is never a pip development environment. Rust,
Python, Node and Julia are not installed through APT. Compiler tooling is added
only for a requested build profile or an actual dependency/source fallback.
Cargo installations prefer upstream release binaries and fall back to locked
source builds with automatically installed build prerequisites.

Bootstrap also provisions Zsh completions from supported installed applications
into user-owned `~/.zfunc`: rustup, Cargo (through rustup), uv, uvx, fnm, Starship,
ripgrep, fd, bat, delta and mcat. Correct discoverable system completions take
precedence; Ubuntu's gh completion and Zsh's Neovim completion stay system-owned.
The existing dotfiles add `.zfunc` to `fpath` before `compinit`; no shell config
or generated payload is copied into this project.

| Optional flag | Installation |
| --- | --- |
| `--build` | build-essential, pkg-config, cmake, ninja-build |
| `--ngspice` | Verified source release; automatically enables build profile and simulator dependencies |
| `--openmodelica` | Official signed `resolute` repository, `omc` CLI, no GUI recommendations; **does not enable `--build`** |
| `--julia` | Official Juliaup installer and release channel |
| `--vim` | Ubuntu Vim |
| `--nvim` | Verified official Neovim archive; x86_64 layout `/opt/nvim-linux-x86_64/bin` |
| `--emacs` | Ubuntu `emacs-nox` |

APT resolves OpenModelica's actual package dependencies, which may themselves
include compilers. Its profile never adds the generic build profile. Missing
official release/architecture support fails clearly; an older Ubuntu repository
is never substituted.

ARM64-supported components select ARM64 packages/artifacts normally. Unqualified
components ask `Attempt installation anyway? [y/N]`; declining skips them.
Automation defaults to skipping them; use repeatable
`--attempt-unqualified COMPONENT` to opt in (for example `dotfiles`, `ngspice`,
`nvim`, `cargo-update`). ARM64 Neovim uses its own `/opt`
directory and a user-bin command link.

## Reruns, updates and ownership

Important channels, package sets, dependencies, dotfiles selection, and source
pins live in [config/bootstrap.toml](config/bootstrap.toml).

- First installation: current stable/latest from the responsible manager.
- Normal rerun: verify working expected paths, manager state, ownership and
  recorded binary hashes; install missing components and preserve working ones.
- `--update`: upgrade the selected bootstrap-owned channel-managed components.
  Repeat optional flags for optional components you want checked/updated.

Cargo updates operate on explicit manifest crate names. They never update all
Cargo-installed applications. APT operations name only selected packages and
their dependencies, without a distribution upgrade. Immutable dotfiles and
ngspice source pins require a manifest review; `--update` does not advance them.
Downloaded binary releases use a named upstream stable release and SHA-256;
the observed release/hash is recorded after successful installation.

An executable with the right name is not evidence that bootstrap owns it.
Existing unmanaged managers/tools and external replacements are preserved and
reported. After reviewing an installation, explicitly opt in with
`--adopt COMPONENT`, such as `--adopt rust`, `--adopt uv`, `--adopt python`,
`--adopt node`, or `--adopt eza`. Cargo adoption still requires the expected
crates.io metadata and binaries. Custom manager paths incompatible with the
dotfiles layout are rejected.

Receipts are disposable observations, **not desired configuration**. Losing
receipts cannot add components to the manifest or authorize overwriting user
tools; reconstruct them through explicit reviewed adoption. Failed installs
retain diagnostic state and can be rerun. Interrupted/partial unmanaged paths
require inspection rather than destructive cleanup. Previous system-asset trees
are retained for recovery when replacing a working installation.

Completions are regenerated when the installed generator's binary, reported
version or generation command changes. Thus `--update` refreshes completions for
changed tools and preserves current ones. Files are generated as the normal user
into a temporary file, checked for a matching `#compdef` and valid Zsh syntax,
then replaced atomically. A failed integration reports an error and returns
nonzero while keeping the installed application and previous completion intact.
Unmanaged, externally edited or symlinked completion files are preserved and
reported for inspection; receipt loss does not authorize replacing them. Insecure
directories writable by group/others are refused because `compinit -i` ignores
them. After reviewing a conflicting generated artifact, move it aside before
rerunning bootstrap; unrelated files in `.zfunc` are never removed.

Eza and zoxide currently have no standalone runtime generator. Zoxide's existing
shell integration and Juliaup's own completion location remain upstream-owned.
Neovim uses Zsh's `_vim`; bottom, hyperfine and dust are not bootstrap-managed
applications. No extra tools are installed to obtain completions. See the
[verified completion interfaces](docs/UPSTREAM.md#zsh-completion-interfaces).

## Shared dotfiles

Bootstrap consumes [Beren-Project/dotfiles-public](https://github.com/Beren-Project/dotfiles-public),
at the reviewed full commit SHA in the manifest. The machine-managed checkout is
under `${XDG_DATA_HOME:-$HOME/.local/share}/ubuntu-bootstrap/dotfiles/<SHA>`;
human development clones are separate. Origin, clean checkout, and exact HEAD
are checked before upstream scripts run.

Bootstrap runs the upstream dependency report, pinned plugin installer, and
`restore.py` preview/apply with the **same explicit five-file selection**:

```text
.zshrc
.zshenv
.gitconfig
.tmux.conf
.config/starship.toml
```

It does not copy editable dotfiles into this repository or recreate restore
logic. Upstream backup, symlink, overlap and conflict protections apply. Existing
changed selected files are backed up under `~/.dotfiles-backups/`; identical
files receive no replacement or backup. Bash, `.profile`, Zellij and Mermaid
configs are not restored. Optional missing items in the upstream dependency
report are informational; bootstrap validates only its selected components.

Personal identity belongs in `~/.gitconfig.local`. Existing personal files and
credentials are preserved. Bootstrap does not invent Git identity, create
credentials/tokens/SSH keys, or authenticate accounts. The shared Git config
uses gh as its GitHub credential helper; authenticate with `gh auth login` when
needed. Supply your own `user.name` and `user.email` before making commits.

## Testing

No extra Python packages are required for the normal suite. Zsh must be installed
for real completion syntax and autoload checks:

```sh
./scripts/test
```

The real installation test requires Podman, network access and several GB of
disk/memory; it installs tools inside a normal container user's isolated HOME:

```sh
./scripts/test-podman
```

The runner audits running/all containers before creation, uses one predictable
`ubuntu-bootstrap-integration` name and project labels, and removes only its
created container in finally/signal cleanup. It never prunes globally or touches
unrelated containers/images. A matching existing container is inspected first;
`--reuse` permits deliberate debugging without deleting a borrowed container.
Reused runs are not fresh-install qualification. Reports go to ignored
`test-results/`.

The full scenario covers base installation, selective restore, ownership,
Yes/No/non-interactive shell behavior, failures/recovery, optional profiles,
repeat passes, generated completion ownership/compinit discovery, explicit updates
and an unrelated Cargo application. `--scenario base` includes the focused
completion failure/regeneration test. For a bounded
debugging run use `--scenario base`, `engineering`, or `update`; the latter two
expect an already prepared container via `--reuse`.

GitHub Actions runs the normal suite on pushes/pull requests. Its manual workflow
can additionally run Podman integration. The CI host is Ubuntu 24.04; the tested
bootstrap installation is exclusively inside its Ubuntu 26.04 container.

Clipboard testing verifies `wl-copy`/`wl-paste` binaries, not a host compositor.
See [validation evidence](docs/VALIDATION.md) for actual results and limitations.
Ubuntu container results do not qualify every WSL runtime behavior. Nerd Font
appearance and live Wayland clipboard operation require the user's terminal/session.

## Boundaries

Sudo is restricted to APT, publishing under system paths and a consented change
to the original user's login shell. Installer shell edits are disabled; all
user-level installations run without sudo. HTTPS, artifact checksums, pinned
checkout verification and APT signature verification remain enabled.

This project starts **inside Ubuntu**. It does not install/enable WSL, install
the distribution, configure Windows/Windows Terminal, install Windows packages
or fonts, or manage WSL host/network configuration. It does not manage personal
credentials, project environments, Windows PATH policy, or the excluded legacy
tools. Installation failure returns an error rather than claiming success.
