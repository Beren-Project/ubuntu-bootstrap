# Optional completion follow-up

Historical implementation plan for the optional-provider baseline. Current
Cargo ownership, shared inventories and durable publication are described in
[the 2026-10-03 maintenance design](MAINTENANCE_2026-10-03.md).

Baseline: `0883eed`. Scope is explicit optional-provider metadata, conditional
post-install checks, official Juliaup integration, tests and related docs.
The existing package/profile graph, managers, updates and pinned five-file
dotfiles restore remain the baseline. The implementation phase excluded Git
staging, commits and pushes; Git publication remains a separate user action.

## Inspected provider mapping

| Profile | Commands | Provider | Registration/owner |
| --- | --- | --- | --- |
| Vim | `vim` | system | `_vim`, Ubuntu `zsh-common` |
| Neovim | `nvim` | system | Shared `_vim`, Ubuntu `zsh-common` |
| Build | `gcc`, `g++`, `cc`, `c++` | system | `_gcc`, Ubuntu `zsh-common` |
| Build | `make` | system | `_make`, Ubuntu `zsh-common` |
| Build | `pkg-config` | system | `_pkg-config`, Ubuntu `zsh-common` |
| Build | `ninja` | system | `_ninja`, Ubuntu `ninja-build` |
| Build | `nm`, `objdump`, `ranlib`, `readelf`, `strings`, `strip`, `gprof` | system | Corresponding Zsh functions, Ubuntu `zsh-common` |
| Build | `dpkg-buildpackage`, `dpkg-source` | system | `_dpkg-buildpackage`, `_dpkg_source`, Ubuntu `zsh-common` |
| Build | `dpkg-parsechangelog` | system | Ubuntu `dpkg-dev` vendor completion |
| Build | `ar`, `as`, `ld`, `objcopy`, `size`, `addr2line`, `c++filt`, `elfedit`, `ld.bfd` | unavailable | No application-specific provider in inspected Binutils/Zsh inventory |
| Build | `cpp`, `gcov`, `gcov-tool`, `gcov-dump` | unavailable | No application-specific provider in inspected GCC/Zsh inventory |
| Build | `cmake`, `ctest`, `cpack` | unavailable | Inspected Ubuntu CMake packages provide Bash, not Zsh, completions |
| Emacs | `emacs` | unavailable | No application-specific provider in inspected Ubuntu packages/official CLI |
| ngspice | `ngspice` | unavailable | Inspect pinned `/opt` source-install tree and official CLI |
| ngspice dependencies | `bison`, `flex` | system | `_bison`, `_flex`, Ubuntu `zsh-common` |
| OpenModelica | `omc` | unavailable | Inspect signed official CLI package and official CLI |
| Julia | `juliaup`, `julia +channel` | upstream-managed | `juliaup completions zsh`, sourced native script |

Unavailable is an explicit observed status, not an installation failure.
Installed package/artifact inventories are recorded; an appropriate trusted
system registration appearing in a later package release can be validated
instead. No handwritten completion definitions or extra applications are added.
System candidates must be root-owned, not writable by group/others, package-owned
and first in the actual restored Zsh `fpath`. Personal shadows are preserved and
required-provider conflicts fail clearly. System providers are never copied to
`.zfunc`. Unselected profiles do no optional completion work.

## Confirmed Julia path decision

The request names `~/.juliaup/completions/zsh.zsh`. Live inspection of the exact
reviewed dotfiles revision shows `.zshrc` line 93 instead sources
`~/.julia/juliaup/completions/zsh.zsh`. Juliaup's implementation also uses the
second location as its native depot completion home, distinct from the binary
self-install home `~/.juliaup`. The dotfiles pin remains
`f7c3eb9ce433a1a8e285afdcda06c1da56c018fd`.

The user confirmed the verified `~/.julia/juliaup/completions/zsh.zsh` path.
The manifest records it explicitly; no compatibility link or dotfiles change is
needed. An incompatible `JULIAUP_DEPOT_PATH` fails clearly before preparation.

## Implementation and validation handoff

- Root refuses all completion preparation. Every generator runs as the original
  user, staging output beside the target and replacing only after success.
- Base autoload validation is unchanged. Native Julia scripts get separate
  syntax, `juliaup` registration and real `+channel` candidate checks.
- Normal native reruns compare the owned generator's hash/version/arguments,
  validate and preserve current files. Changed sources regenerate atomically.
  Existing unmanaged/personal native scripts are preserved and refused unless
  explicitly reviewed with `--adopt julia`; an observed upstream refresh must
  match the installed official generator exactly to be accepted automatically.
- Receipts record observations, provider/function, package/artifact inventory
  and generator state. The manifest remains desired-state authority.
- Focused local tests exercise real Zsh and normal-user fixture generators.
- Ubuntu 26.04 integration extends the existing fixed-name runner: fresh base
  has no optional receipts/artifacts, later selected profiles register their
  providers, second pass preserves files/receipts/backups, native generator
  failure preserves old output, and update/revalidation follows ownership.
- Audits used separate read-only system-provider and Julia-path agents; a
  separate test agent edited only container checks/scenario. The coordinator
  owns runtime/manifest/unit tests/docs and final integration/resource review.

Commands for final qualification:

```sh
./scripts/test
./scripts/test-podman --scenario all --debug-retry
git diff --check
git status --short
```

Before testing: no running containers, seven unrelated stopped OpenProject
containers, no project test container. Never remove unrelated resources; audit
both `podman ps` and `podman ps -a` afterward. Record actual results and any
remaining limitation in `VALIDATION.md`; this plan is not qualification evidence.

Initial implementation handoff (2026-10-02): 72 normal tests
and the fresh full Ubuntu 26.04 Podman scenario passed. System/native providers,
honest absence, conditional work, second-pass preservation, update ownership and
resource cleanup were verified. The dated [validation record](VALIDATION.md#optional-completion-follow-up--2026-10-02)
records exact evidence and limits. The implementation agent performed no Git
staging, commits or pushes during that phase. Later review results are recorded
separately in the validation document.
