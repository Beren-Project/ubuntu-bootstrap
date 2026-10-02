# Documentation improvement work plan

Approved 2026-10-02. Starting revision: `f5e841a` (completion follow-up), with a
clean worktree. This document records this bounded documentation change, rather
than creating a new runtime configuration or ongoing agent framework.

## Goal and acceptance

Serve both fresh Ubuntu 26.04 team members and maintainers. Keep the README
concise and make installation inventories explicit: default versus optional,
purpose, executable names, responsible installer, and automatic dependencies.
Add detailed usage/recovery and contributor/architecture references. Explain the
existing behavior; do not redesign or change it.

A new user must be able to identify exactly what is installed, choose profiles,
understand shell consent and find safe recovery guidance. A contributor must be
able to trace ownership and failure boundaries and choose the correct tests.

## Contracts to preserve

- Documentation changes only: no runtime, manifest, workflow, test, or dotfiles
  edits; no host installation, bootstrap application, or new Podman test run.
- Normal-user entry; scoped sudo for system work and consented original-user
  shell change. Never install user tools/completions as root.
- Ubuntu 26.04/resolute; primary x86_64 WSL2 target. Preserve ARM64 and live WSL
  qualification limits. Windows/WSL host provisioning remains out of scope.
- Dotfiles revision `f7c3eb9ce433a1a8e285afdcda06c1da56c018fd`; restore only
  `.zshrc`, `.zshenv`, `.gitconfig`, `.tmux.conf`, `.config/starship.toml` through
  upstream repeatable `--file` preview/apply and all upstream protections.
- OpenModelica is signed resolute CLI `omc`, with no build-profile dependency;
  APT may resolve package-declared compiler dependencies.
- Manifest defines desired ownership/configuration. Receipts are observations;
  adoption remains explicit and updates affect only selected managed tools.
- Completions stay normal-user generated, validated and atomically published;
  system and Juliaup integrations retain their owners.
- No staging, commit, push, unrelated repository edits, or automatic credentials.

## Delegation and file ownership

| Role | Owned files | Status |
| --- | --- | --- |
| Coordinator | This work plan; final integration edits after writers finish | Complete; handed off for user review |
| User-documentation writer | `README.md`, `docs/USAGE.md` | Complete; integrated |
| Maintainer-documentation writer | `CONTRIBUTING.md`, `docs/ARCHITECTURE.md`, `docs/UPSTREAM.md`, `docs/VALIDATION.md` | Complete; integrated |
| Independent reviewer | Read-only review of combined documentation and source | Complete; no findings requiring correction |

Each writer reads this handoff and relevant live source, edits only its files,
and returns changed files, checked claims, unresolved questions and evidence.
Only the coordinator updates this shared artifact. The reviewer starts after
both writers finish. No nested delegation is needed.

## Required clarifications

- `--yes` omits the optional menu and accepts Zsh shell consent unless overridden.
- Reruns preserve working owned tools but can back up/replace local edits to the
  selected shared configs; unchanged configs do not create backups.
- `--plan` enters Stage-0 first, which may install missing system Python.
- Account setup and identity are deliberate user actions, not bootstrap actions.
- Historical all-profile core qualification and focused completion qualification
  remain separate dated records. Documentation validation is not fresh Ubuntu
  installation qualification.

## Checks and evidence

Maintainer writer checked claims against the live manifest, CLI, handlers,
tests and container runner. Its draft passed `git diff --check`; it performed
no test execution, installation or Git staging/commit/push.

User writer checked inventories, flags, installation and recovery guidance
against the live manifest, Stage-0, CLI, handlers, runtime and source tests.
Upstream plugin names remain linked to their exact-revision manifest rather
than guessed. It performed no test execution, installation or Git operations.

Coordinator reconciled installation tables and all public flags with live
manifest/CLI; checked the pinned SHA and exact five-file selection; reviewed
command examples and recovery safety; and verified local Markdown links and
heading anchors. The source-driven check covered 59 package/tool identifiers
and 16 public long flags, including help. It is a documentation review check,
not a new source of desired configuration.

`./scripts/test` passed all 51 tests in 1.226 seconds, plus manifest, Python
AST, shell syntax and ShellCheck checks. The suite ran once; no installation
qualification was repeated. `git diff --check` passed. Final inspection is
restricted to the seven documentation files assigned above, with no staged
changes and the original implementation commit unchanged.

The independent reviewer checked all seven documents against the manifest,
entry point, CLI, handlers, tests and saved historical integration evidence,
and reported no findings requiring correction. Coordinator integration added
explicit README privilege wording and a short post-install command checklist,
both included in that review. The new dated documentation record in
[VALIDATION.md](VALIDATION.md#documentation-follow-up--2026-10-02) distinguishes
these checks from prior full/core and focused/completion installation evidence.

No host bootstrap application, Podman command, staging, commit or push ran.
No new upstream availability audit or browser-rendered documentation check was
performed. Existing Ubuntu/WSL qualification limits remain unchanged.

## Open decisions and stop boundary

The original documentation pass and approved fresh-reader follow-up are
complete. English documentation; concise README and linked detailed guides;
inspect before recovery and avoid broad cleanup/adoption. At the documentation
handoff, the agent left the uncommitted diff for user review without staging,
committing or pushing. The user subsequently committed that documentation as
`0883eed`; the dated evidence below describes the earlier implementation phase.

## Approved fresh-reader follow-up — 2026-10-02

A new agent reviewed public documentation without the writers' explanations.
It found no general onboarding blocker, but identified two medium-priority
usability gaps. The user approved a new implementation agent to correct both:

1. Explain before quick start that first runs, as well as reruns, apply the
   five shared configs. Link backup behavior and personal Git settings guidance;
   keep the warning consistent with the detailed usage guide.
2. Complete managed dotfiles checkout recovery: inspect the exact path and
   preserve it intact at a separate backup location, then rerun the original
   selection so the verified pinned checkout is fetched again. Preserve user
   changes and verification; never prescribe broad cleanup/reset/deletion.

The correction writer owns only `README.md` and `docs/USAGE.md`; coordinator
owns this handoff and final verification. No runtime or manifest edits,
installation, test reruns, Podman work, staging, commit or push are needed.
The normal suite already passed; these prose/example corrections do not change
the behavior it tests. Coordinator will check the focused diff, local
links/anchors, shell example syntax, whitespace and unchanged implementation.

Status at handoff: complete and submitted for user review. The correction writer changed only
`README.md` and `docs/USAGE.md`. Coordinator reviewed the focused changes against
the original snapshot and the absent-checkout fetch/verification implementation;
the other four public documents remain unchanged. The README warning now
precedes quick-start commands and agrees with detailed restore protections.
Recovery preserves the exact reviewed checkout and refuses backup collisions
(including dangling symlinks), using quoted paths and `mv -T --no-clobber`;
the user reruns their original selection only after confirming the move.

Final documentation checks passed: all seven Markdown files, 62 local
links/anchors, 16 shell example blocks checked with `sh -n`, exact pinned paths,
warning placement, whitespace (including new files), documentation-only scope,
unchanged `f5e841a` implementation and no staged changes. No example was
executed, normal tests were not repeated, and no bootstrap, installer or Podman
command, staging, commit or push ran. The earlier 51-test result and installation
qualification records remain historical evidence with their original scope.
