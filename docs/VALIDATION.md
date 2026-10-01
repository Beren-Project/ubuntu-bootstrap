# Validation

Validated locally on 2026-10-01. Installation qualification uses a fresh official
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

## Real Ubuntu integration

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

## Podman resource audit

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

## Limits

- Official OpenModelica **resolute** support was available and verified. Its CLI
  package currently declares compiler dependencies itself; the bootstrap profile
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
- This supplied workspace has an empty read-only `.git` placeholder, so
  `git status --short` reports `fatal: not a git repository`. Files were reviewed
  directly and with `git diff --no-index --check`; no Git initialization, staging,
  commit or push was performed.
