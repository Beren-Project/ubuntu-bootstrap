# Installation authorities and reviewed pins

Core installation authorities and pins were reviewed 2026-10-01; completion
interfaces were inspected 2026-10-02. These are historical review dates, not a
new live upstream audit. Policies and immutable artifact inputs are centralized
in [config/bootstrap.toml](../config/bootstrap.toml); this document records why
those methods were selected. Observed installation results and qualification
limits are separate in [VALIDATION.md](VALIDATION.md).

| Component | Official guidance | Implementation |
| --- | --- | --- |
| Rust | https://rust-lang.org/tools/install/ and official rustup installer help | rustup stable/minimal, `--no-modify-path` |
| Cargo binaries | https://github.com/cargo-bins/cargo-binstall | Official release archive; manifest crates through binstall with explicit locked source fallback |
| uv | https://docs.astral.sh/uv/reference/installer/ | Official installer; `UV_NO_MODIFY_PATH=1` |
| Python | https://docs.astral.sh/uv/concepts/python-versions/ | Stable managed CPython via uv, user-local default launchers |
| Node | https://github.com/Schniz/fnm/blob/master/docs/commands.md | fnm latest LTS and managed default |
| Julia | https://docs.julialang.org/en/v1/manual/installation/ | Juliaup release, `--add-to-path=no`, no scheduled self-updates |
| Neovim | https://github.com/neovim/neovim/blob/master/INSTALL.md | Named official stable archive, GitHub release SHA-256, `/opt` installation |
| OpenModelica | https://openmodelica.org/download/download-linux/ | Official signed resolute/stable repository; `--no-install-recommends omc` |
| ngspice | https://ngspice.sourceforge.io/download.html and release `INSTALL` | Manual out-of-tree release build, normal-user staging, system publication |

Dotfiles commit `f7c3eb9ce433a1a8e285afdcda06c1da56c018fd` was inspected against
its selective restore implementation and bootstrap contract. The selected paths
are exactly `.zshrc`, `.zshenv`, `.gitconfig`, `.tmux.conf` and
`.config/starship.toml`, using repeated upstream `--file` flags for preview/apply.
The three-file upstream `--profile shell` preset is a separate interface.
Git identity remains personal state even
though upstream setup notes suggest creating it before restore; a missing
`.gitconfig.local` is supported and bootstrap reports that account action.

The ngspice 47 artifact was fetched from the official release distribution and
its SHA-256 matched SourceForge's published
`894e649651f1838a14095e5a5439e7d3aa63e87ede14d283173fda4fcdef675f`.
The release INSTALL recommends `../configure --with-x`, make and install;
bootstrap adds CIDER, preserves default XSPICE/OpenMP/OSDI, supplies FFTW and
sound-file dependencies, and never runs the build as root. It uses DESTDIR
staging instead of executing upstream make/install with sudo.

The official OpenModelica key contains reviewed primary fingerprints
`D229AF1CE5AED74E5F59DF303A59B53664970947` and
`5DE86CC050F6623BBA7995B864CE41328E03B30A`. Signed Release metadata and APT
package verification are both checked. A future upstream key change requires
reviewing this trust input, rather than accepting a newly downloaded key blindly.
The official resolute `omc` package inspected during the core review declared
compiler/build dependencies;
these are APT dependencies, not a bootstrap build-profile edge. GUI recommendations
and the `openmodelica` metapackage are not selected.

## Zsh completion interfaces

Inspected 2026-10-02 against official guidance/source and installed CLI help.
Only application-provided stable generators are declared in `zsh_completions`
in the manifest; no generated completion payload is stored here.

| Command | Verified interface / authority |
| --- | --- |
| gh | [`gh completion --shell zsh`](https://cli.github.com/manual/gh_completion); prefer Ubuntu's discoverable `/usr/share/zsh/vendor-completions/_gh` |
| rustup | [`rustup completions zsh`](https://rust-lang.github.io/rustup/installation/index.html#enable-tab-completion-for-bash-fish-zsh-or-powershell) |
| cargo | `rustup completions zsh cargo`, verified by `rustup help completions`; upstream-generated loader uses the active toolchain's own `_cargo` |
| uv / uvx | [`uv generate-shell-completion zsh` / `uvx --generate-shell-completion zsh`](https://docs.astral.sh/uv/getting-started/installation/#shell-autocompletion) |
| fnm | [`fnm completions --shell zsh`](https://github.com/Schniz/fnm#completions) |
| starship | `starship completions zsh`, verified by installed help and [official CLI source](https://github.com/starship/starship/blob/master/src/main.rs) |
| rg | [`rg --generate complete-zsh`](https://github.com/BurntSushi/ripgrep/blob/master/FAQ.md#does-ripgrep-have-support-for-shell-auto-completion) |
| fd | [`fd --gen-completions zsh`](https://github.com/sharkdp/fd#completions) |
| bat | [`bat --completion zsh`](https://github.com/sharkdp/bat#from-source) |
| delta | `delta --generate-completion zsh`, verified by installed help and [official completion definitions](https://github.com/dandavison/delta/blob/main/etc/completion/completion.zsh) |
| mcat | `mcat --generate zsh`, verified by installed CLI help from the [official application](https://github.com/Skardyy/mcat) |

Each generated file is named `_<command>` and must begin with an appropriate
`#compdef`. This is the upstream autoload format, including Cargo's short loader;
the installed Cargo version participates in regeneration even though rustup
emits that loader. File receipts only record observed generator/version/hash and
artifact ownership; the manifest selects desired generators.

[Eza's official installation guidance](https://github.com/eza-community/eza/blob/main/INSTALL.md#completions)
uses distributed static completion files, not an application runtime generator.
[Zoxide's command definitions](https://github.com/ajeetdsouza/zoxide/blob/main/src/cmd/cmd.rs)
expose shell initialization rather than a standalone completion command; its
existing `zoxide init zsh` integration remains in dotfiles. Inspected cargo-binstall,
cargo-update and Macchina help exposes no suitable generator. Juliaup keeps its
official generated integration location. Zsh's system `_vim` declares `nvim`
alongside Vim, so Neovim requires no fabricated or duplicate completion file.
Bottom, hyperfine and dust are absent from the bootstrap tool manifest and are
outside this completion change.
