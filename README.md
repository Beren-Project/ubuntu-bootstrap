# ubuntu-bootstrap

Set up an already installed **Ubuntu 26.04 (resolute)** engineering/development
workstation. **x86_64 WSL2** is the primary target; native Ubuntu uses the same
installation paths. ARM64 is best effort and is not qualified by the current
integration evidence. Other releases/distributions fail early.

## Quick start

**First runs and reruns apply the five shared configs.** Existing differing
selected files can be backed up and replaced. Review your customizations first;
keep personal Git settings in `~/.gitconfig.local`. See
[shared configuration and backup behavior](docs/USAGE.md#shared-configuration-and-reruns).

If Git is missing, run `sudo apt-get update && sudo apt-get install -y git`,
or download and extract the repository archive.

```sh
git clone https://github.com/Beren-Project/ubuntu-bootstrap.git
cd ubuntu-bootstrap
./bootstrap
```

Run as your **normal user**, with sudo access. `sudo ./bootstrap` is refused.
Sudo is limited to system operations and a consented login-shell change;
user tools and generated completions remain user-owned.
Choose optional components from the menu, then answer
`Change your default shell to Zsh? [Y/n]`. Yes is the default; after successful
interactive completion with consent, bootstrap enters a Zsh login session.
No preserves your login shell and prints a command for later.

An optional flag bypasses the menu; defaults still apply:

```sh
./bootstrap --ngspice --openmodelica --nvim
```

For automation, choose the shell explicitly and provide working `sudo -n`:

```sh
./bootstrap --non-interactive --no-change-shell
./bootstrap --non-interactive --change-shell --build
```

`--yes` omits the optional menu and accepts Zsh consent unless overridden by
`--no-change-shell`. It needs a terminal unless paired with `--non-interactive`,
which still requires an explicit shell choice. `./bootstrap --plan` prints the
configuration, but **Stage 0 may first install missing system Python**.
See [all flags and interactions](docs/USAGE.md#choose-a-run).

## Installation inventory

The [manifest](config/bootstrap.toml) defines these requested packages/tools;
APT can additionally install their declared dependencies. The
[detailed inventory](docs/USAGE.md#installation-inventory) gives each item's
purpose, command and owner.

| Default group | Installed components | Installer |
| --- | --- | --- |
| System base | ca-certificates, curl, git, gh, python3, zsh, tmux, fzf, wl-clipboard (`wl-copy`, `wl-paste`) | Ubuntu APT |
| Rust | rustup; stable/minimal toolchain (`rustc`, `cargo`) | Verified official rustup-init binary |
| Cargo support | cargo-binstall; cargo-update (`cargo-install-update`, `cargo-install-update-config`) | Official binstall archive; Cargo via binstall/source fallback |
| CLI applications | starship, bat, eza, fd-find (`fd`), fnm, git-delta (`delta`), ripgrep (`rg`), zoxide, macchina, mcat | Cargo via binstall/source fallback |
| Python | uv/uvx; stable managed CPython with user-local `python`/`python3` launchers | Cargo via binstall/source fallback, then uv |
| Node | Current Node LTS, selected as the managed default | fnm |
| Shared configuration | `.zshrc`, `.zshenv`, `.gitconfig`, `.tmux.conf`, `.config/starship.toml`; pinned standalone Zsh plugins | Pinned dotfiles-public restore/plugin scripts |

| Optional flag | Installed components | Installer |
| --- | --- | --- |
| `--build` | build-essential, pkg-config, cmake, ninja-build | Ubuntu APT |
| `--julia` | Juliaup and Julia `release` channel | Cargo via binstall/source fallback, then Juliaup |
| `--ngspice` | ngspice 47; enables `build` and [simulator prerequisites](docs/USAGE.md#build-and-installer-dependencies) | Verified pinned source; dependencies through APT |
| `--openmodelica` | gnupg and `omc` CLI from signed official `resolute`/stable repository | Ubuntu and official OpenModelica APT repositories |
| `--vim` | vim | Ubuntu APT |
| `--nvim` | Neovim (`nvim`) official stable archive | Verified official release archive |
| `--emacs` | emacs-nox (`emacs`) | Ubuntu APT |

Cargo prefers upstream binaries. Locked source fallback automatically adds
**build-essential, pkg-config and libssl-dev**, even without `--build`.
OpenModelica does **not** enable `build`; APT may resolve compilers declared by
`omc` itself. System Python runs bootstrap; development Python, Rust, Node and
Julia use their dedicated managers.

Unqualified ARM64 `dotfiles`, `ngspice`, `nvim` and `cargo-update` require opt-in;
`--yes` and automation skip them unless named with repeatable
`--attempt-unqualified COMPONENT`.

## Reruns and personal setup

Reruns preserve working owned tools. **First runs and reruns can back up and
replace existing differing files among the five shared configs**; identical
files create no backup. Dotfiles revision
`b0fecc41f00fa2423aaf22478f2cec98cdf15229` is consumed through upstream preview/apply
with the same five explicit `--file` arguments and all upstream protections.
The pinned Zsh configuration prioritizes Cargo-managed uv/uvx and Juliaup/Julia,
without sourcing the legacy uv helper or adding the legacy Julia binary directory.
Bash's `.bashrc` and `.profile` remain outside bootstrap's restore selection.

`--update` updates selected owned channel-managed components; repeat optional
flags for optional tools. It does not advance immutable source pins or update
unrelated Cargo applications. Unmanaged tools and external replacements are
preserved and reported; use `--adopt COMPONENT` only after inspection. Receipts
record observations, not desired configuration.

Configure your Git identity in `~/.gitconfig.local`. Run `gh auth login` when you
need GitHub authentication. Bootstrap creates no identity, credentials, tokens
or SSH keys. Follow the [personal setup steps](docs/USAGE.md#finish-personal-setup).

Supported completions are generated as the normal user, validated and atomically
published to `~/.zfunc`. Correct system completions and upstream Juliaup
integration retain their owners. Completion errors preserve the application and
previous completion while returning nonzero. See the
[completion lifecycle](docs/USAGE.md#zsh-completions) and
[task-based recovery](docs/USAGE.md#troubleshooting-by-task).

Selected optional profiles validate their declared system providers or prepare
Juliaup's native integration. Tools without a supported provider report
`unavailable` without failing installation; no completion definitions are invented.

## Documentation and validation

- [Usage](docs/USAGE.md): detailed inventory, flags, paths, updates and recovery.
- [Contributing](CONTRIBUTING.md): contributor workflow and relevant checks.
- [Architecture](docs/ARCHITECTURE.md): ownership and failure boundaries.
- [Upstream interfaces](docs/UPSTREAM.md): sources, pins and completion interfaces.
- [Validation evidence](docs/VALIDATION.md): dated results and qualification limits.

Run `./scripts/test` for the normal suite (system Python and Zsh required).
**Unit CI passed** means host-independent regression coverage passed;
**platform-gate tests passed** means release/architecture decision logic passed.
The Ubuntu 24.04 hosted unit job does not qualify Ubuntu 26.04 support.

`./scripts/test-podman` installs inside an isolated Ubuntu 26.04 container and
needs Podman, network access and several GB of resources; read
[Contributing](CONTRIBUTING.md) before using it. Historical all-profile and
focused completion qualifications are separate records; documentation checks
are not fresh-install qualification.

**Ubuntu 26.04 qualification passed** means the real bootstrap succeeded in a
fresh Ubuntu 26.04 environment with real platform detection. CI runs the full
Podman qualification after units on pushes to `main`; other branch pushes and PRs run
units only. Manual dispatch can also request the full run. See
[CI meanings, triggers and environment choice](CONTRIBUTING.md#ci-meanings-and-triggers).

This project starts **inside Ubuntu**. Windows/WSL provisioning, Windows
packages, fonts, host/network configuration and personal project environments
remain outside its scope. Containers do not qualify every WSL behavior; live
Wayland clipboard use and terminal/font appearance need session-specific checks.

Manager ownership is explicit: APT supplies the OS foundation; verified
`rustup-init` bootstraps Rustup before stable Rust; Cargo plus cargo-binstall owns
CLI applications, uv and Juliaup. uv owns managed CPython and Juliaup owns Julia
release channels. Cargo remains binary-first with controlled `cargo install
--locked` fallback. See [migration and crash recovery](docs/MAINTENANCE_2026-10-03.md).
