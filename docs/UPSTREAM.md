# Installation authorities and reviewed pins

Rust distribution interfaces, published uv/Juliaup crates and release layouts,
and the new dotfiles pin were independently reviewed 2026-10-03. Completion
interfaces retain their 2026-10-02 review; unrelated authorities retain their
2026-10-01 review. Policies and immutable artifact inputs are centralized
in [config/bootstrap.toml](../config/bootstrap.toml); this document records why
those methods were selected. Observed installation results and qualification
limits are separate in [VALIDATION.md](VALIDATION.md).

| Component | Official guidance | Implementation |
| --- | --- | --- |
| Rust | [Rustup binary/checksum interface](https://github.com/rust-lang/rustup/blob/main/doc/user-guide/src/installation/other.md) and verified rustup-init 1.29.1 help | Official target binary plus `.sha256`; no toolchain at init, self-update first, then stable/minimal/default; `--no-modify-path` |
| Cargo binaries | https://github.com/cargo-bins/cargo-binstall | Official release archive; manifest crates through binstall with explicit locked source fallback |
| uv | [uv Cargo installation](https://docs.astral.sh/uv/getting-started/installation/#cargo) and published crate/release manifests | Cargo-owned uv/uvx through binstall/locked fallback; no uv self-update |
| Python | https://docs.astral.sh/uv/concepts/python-versions/ | Stable managed CPython via uv, user-local default launchers |
| Node | https://github.com/Schniz/fnm/blob/master/docs/commands.md | fnm latest LTS and managed default |
| Julia | https://docs.julialang.org/en/v1/manual/installation/ | Cargo-owned Juliaup/julia; Juliaup owns `release`; no Juliaup binary self-update |
| Neovim | https://github.com/neovim/neovim/blob/master/INSTALL.md | Named official stable archive, GitHub release SHA-256, `/opt` installation |
| OpenModelica | https://openmodelica.org/download/download-linux/ | Official signed resolute/stable repository; `--no-install-recommends omc` |
| ngspice | https://ngspice.sourceforge.io/download.html and release `INSTALL` | Manual out-of-tree release build, normal-user staging, system publication |

Dotfiles commit `c44e4b8c8299f2b05ee225678daead77bf5bfbd1` was inspected against
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

The optional-provider follow-up is tracked in
[OPTIONAL_COMPLETIONS_PLAN.md](OPTIONAL_COMPLETIONS_PLAN.md), including the
confirmed Julia native destination. Optional package inspection uses full
installed inventories and actual Zsh registration, not executable-name guesses.

| Optional application/tool | Inspected authority and provider |
| --- | --- |
| Vim / Neovim | Zsh's official [`_vim`](https://github.com/zsh-users/zsh/blob/zsh-5.9/Completion/Unix/Command/_vim) declares both commands; Ubuntu `zsh-common` owns the installed provider |
| GCC aliases / Make / pkg-config | Ubuntu `zsh-common` owns Zsh's `_gcc`, `_make`, `_pkg-config`; registration and aliases are verified rather than assuming `_COMMAND` |
| Ninja | [Official Ninja Zsh completion](https://github.com/ninja-build/ninja/blob/master/misc/zsh-completion), packaged by Ubuntu `ninja-build` |
| Binutils / Debian build tools | [GNU Binutils manual](https://sourceware.org/binutils/docs/binutils/) and [Debian build-package interface](https://manpages.debian.org/unstable/dpkg-dev/dpkg-buildpackage.1.en.html); inspected `zsh-common` supplies nm/objdump/ranlib/readelf/strings/strip/gprof and dpkg-buildpackage/dpkg-source; `dpkg-dev` supplies dpkg-parsechangelog |
| Bison / Flex | Zsh's `_bison` and `_flex` from `zsh-common`, validated only when ngspice selects these source-build dependencies |
| CMake / CTest / CPack | [Official CMake CLI documentation](https://cmake.org/cmake/help/latest/manual/cmake.1.html); inspected Ubuntu `cmake`/`cmake-data` ship Bash completions, with no supported application-specific Zsh provider found |
| Emacs | [GNU command-line interface](https://www.gnu.org/software/emacs/manual/html_node/emacs/Emacs-Invocation.html) and Ubuntu `emacs-nox`, `emacs-common`, `emacs-bin-common` inventories; no supported application-specific Zsh provider found |
| ngspice | [Official ngspice documentation](https://ngspice.sourceforge.io/docs.html), CLI help and pinned installation tree; no supported application-specific Zsh provider found |
| OpenModelica | [Official compiler interface](https://openmodelica.org/doc/OpenModelicaUsersGuide/latest/omchelptext.html) and installed official `omc` package; no supported Zsh provider found |
| Juliaup | `juliaup completions zsh`; official [`global_paths.rs`](https://github.com/JuliaLang/juliaup/blob/main/src/global_paths.rs) distinguishes the native depot home from binary/self home, and [`operations.rs`](https://github.com/JuliaLang/juliaup/blob/main/src/operations.rs) writes a sourced native script registering both `juliaup` and `julia +channel` |

Missing providers are an explicit, nonfatal `unavailable` observation. A future
trusted package provider can be discovered and qualified through installed
inventories and `fpath`; no unofficial files or handwritten definitions are
substituted. Pin-specific shell integration remains the responsibility of the
reviewed [public dotfiles](https://github.com/Beren-Project/dotfiles-public/blob/c44e4b8c8299f2b05ee225678daead77bf5bfbd1/home/.zshrc).

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

## Reviewed Cargo packaging and dotfiles delta (2026-10-03)

Published [uv 0.12.22](https://crates.io/crates/uv/0.12.22) declares Linux `uv` and `uvx`; `uvw` is feature-gated for
Windows. Its official archive uses `uv-{target}/{bin}` under
`releases/download/{version}/uv-{target}.tar.gz`. Published Juliaup 1.22.7
([published crate](https://crates.io/crates/juliaup/1.22.7)) declares `juliaup`
and `julia`; installer and `julialauncher` names require
additional features. Its official portable archive uses root-level `{bin}`
under `releases/download/v{version}/juliaup-{version}-{target}-portable.tar.gz`.
The archive's extra GUI binary is not a declared Cargo install output. Both
layouts passed cargo-binstall dry runs against the actual published manifests
(x86_64 GNU uv, x86_64 musl Juliaup). These versions document inspected inputs;
bootstrap continues to resolve current stable crates, without ordinary pins.

### Cargo-binstall GitHub retry interfaces (2026-10-03)

The saved qualification receipt used **1.25.0**. An unauthenticated request to
the official GitHub latest-release API confirmed `v1.25.0`, published
2026-10-03T01:34:00Z, with neither draft nor prerelease set. Its tag and repository
HEAD were `a29e25869a42756b3be062dc4dae3e4b01bb4f38`. The local host binary was
1.24.0; its isolated public uv dry run took 4.730 seconds. Runtime qualification
records the actually installed manager version rather than relying on that host.

| Supported interface | Behavior relevant to bootstrap |
| --- | --- |
| `GITHUB_TOKEN`, then `GH_TOKEN`; `--github-token` | Explicit authentication; bootstrap only passes environment values, never token arguments. Authenticated requests may use GraphQL before REST. |
| `--no-discover-github-token`; `BINSTALL_NO_DISCOVER_GITHUB_TOKEN` | Disables default Git-credential/GitHub CLI credential discovery; bootstrap always passes the flag. |
| `--maximum-resolution-timeout`; `BINSTALL_MAXIMUM_RESOLUTION_TIMEOUT` | 15 seconds by default for each target/strategy/name candidate's discovery; excludes crate acquisition, archive download and installation. Bootstrap makes 15 explicit. |
| `--rate-limit`; `BINSTALL_RATE_LIMIT` | Local request pacing, default one request per 10 ms; does not configure remote retry/reset waits. |
| `--strategies`; `BINSTALL_STRATEGIES`; `--disable-strategies` | Select fetchers; bootstrap retains only `crate-meta-data`, with external controlled source fallback. |
| `--version`, `crate@version` | An exact bare version or explicit `=VERSION` is exact, not a caret range. Bootstrap uses `--version =VERSION`. |
| `--pkg-url`, `--pkg-fmt`, `--bin-dir` | Override published packaging metadata; existing validated overrides/layouts are retained. |
| `--json-output`, `--log-level info` | Structured diagnostics for the narrow retry guard; no verbose header/body logging. |

Reviewed [CLI definitions](https://github.com/cargo-bins/cargo-binstall/blob/v1.25.0/crates/bin/src/args.rs),
[version semantics](https://github.com/cargo-bins/cargo-binstall/blob/v1.25.0/crates/binstalk/src/ops/resolve/version_ext.rs),
and [credential selection](https://github.com/cargo-bins/cargo-binstall/blob/v1.25.0/crates/bin/src/entry.rs).
Cargo's [official install documentation](https://doc.rust-lang.org/cargo/commands/cargo-install.html#install-options)
also confirms bare `MAJOR.MINOR.PATCH` installs exactly that version, so the
existing source command and binstall's `=VERSION` select the same crate release.
There is no supported API-disable flag, whole-attempt timeout, or configurable HTTP
retry count/duration in this interface. Cargo HTTP timeout settings are not wired
to binstall's downloader; changing them would not fix its internal wait.

The [release resolver](https://github.com/cargo-bins/cargo-binstall/blob/v1.25.0/crates/binstalk-fetchers/src/gh_crate_meta.rs)
uses GitHub API existence checks even with exact versions and explicit direct
release URLs. Public asset downloads use the direct release URL afterward, without
the release-tag REST request, but no supported CLI setting skips the prior check.
Bootstrap does not alter URL fragments/query strings to exploit parser behavior.
Crates.io's existing `max_stable_version` metadata suffices to select one intended
version independently of GitHub; it does not remove binstall's API existence check.

The [downloader](https://github.com/cargo-bins/cargo-binstall/blob/v1.25.0/crates/binstalk-downloader/src/remote.rs)
allows three attempts and clamps `Retry-After`/quota-reset delays to 120 seconds.
It retries on these headers even with HTTP 200, and delays all requests to the
same host. Bare 403 is not automatically a rate limit; 429, 503, connection and
gateway timeouts also have distinct retry behavior. Bootstrap rejects recognized
long GitHub quota/retry-delay events while leaving ordinary latency/5xx/DNS paths
to upstream. SIGTERM is supported by [upstream cancellation](https://github.com/cargo-bins/cargo-binstall/blob/v1.25.0/crates/bin/src/signal.rs).
See [policy, fault injection and timings](CARGO_RETRY_2026-10-03.md).

The [new dotfiles HEAD](https://github.com/Beren-Project/dotfiles-public/commit/c44e4b8c8299f2b05ee225678daead77bf5bfbd1) directly follows the previous reviewed
`f7c3eb9ce433a1a8e285afdcda06c1da56c018fd`. The complete delta adds ANSI colors
to comparison/public-sync reports and their tests: 10 files, 515 insertions,
20 deletions. Selected configs, managed restore selection, restore implementation,
dependency checker, plugin installer/pins, Cargo environment sourcing and Julia
native sourcing are unchanged. The new renderer is not added to restore scope.
