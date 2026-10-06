# Contributing

Start with [usage and recovery](docs/USAGE.md), the
[runtime architecture](docs/ARCHITECTURE.md) and
[dated validation evidence](docs/VALIDATION.md). The supported installation
target is Ubuntu 26.04 (`resolute`), primarily x86_64 WSL2; Windows/WSL host
provisioning is outside this repository. ARM64 and live terminal qualification
limits are recorded in the evidence document.

## Development prerequisites

For local checks, use system `/usr/bin/python3` and Zsh. The suite was verified
with Python 3.12 on Ubuntu 24.04 and Python 3.14 on Ubuntu 26.04; the test host
need not be the production installation target. The Python modules use the
standard library; there is no pip dependency installation.
`./scripts/test` requires Zsh because completion tests execute real syntax and
autoload checks. ShellCheck runs when it is available; record if it was absent.
The local suite needs neither sudo nor network access and uses temporary fixture
homes rather than applying bootstrap to your HOME. Python commands use `-B` so
checks do not leave bytecode in inspected checkouts.

Podman and network access are additional prerequisites for real installation
tests. Run the local suite first. Choose integration deliberately: it downloads
tools, compiles source fallbacks and installs packages inside its container.
Do not test a change by running installers against your working account.

## Change boundaries

Keep desired profiles, package lists, channels, completion generators and
immutable inputs in [the manifest](config/bootstrap.toml). A receipt describes
an observed installation and cannot select additional tools. Review official
authorities and trust inputs in [UPSTREAM.md](docs/UPSTREAM.md) before changing
a source pin, archive mapping or repository key.

Preserve normal-user entry, explicit ownership/adoption, scoped sudo, consent
for the original user's login shell and the pinned upstream restore interface.
Dotfiles restore is exactly five repeated `--file` selections; bootstrap must
not implement its own restore or replace them with `--profile shell`.
Add regression coverage for changed behavior at the appropriate boundary, such
as dependency resolution, external ownership, failed publication or generator
output. Keep unrelated tools, configs and test resources intact.

The documentation follow-up is recorded in the
[approved work plan and handoff](docs/DOCS_WORK_PLAN.md). It records contracts,
file ownership, writer handoffs, independent review, checks and the stop boundary
in one durable file. The coordinator integrates the writers' scoped changes;
the reviewer reads the combined result after both writers finish. This is a
bounded collaboration record. It requires no new agent framework or runtime
configuration. For future work, agree scope and record the same information
before implementation when a coordinated change needs a handoff.

## Local verification

Run from the repository root as a normal user:

```sh
./scripts/test
git diff --check
```

The test script discovers `tests/test_*.py`, checks shell syntax, runs optional
ShellCheck, loads the manifest and parses every Python source in `bootstrap_lib`
and `tests`. [test_logic.py](tests/test_logic.py) covers profiles, ownership,
downloads, dotfiles verification, system publication and shell consent.
[test_completions.py](tests/test_completions.py) covers real fixture generators,
Zsh loading, version changes, permissions, conflicts and failure preservation.
[test_optional_completions.py](tests/test_optional_completions.py) covers explicit
provider classification, selected-only work, shared system functions, native
Juliaup generation/channel registration, secure permissions and rollback after
validation, receipt-write or publication-interrupt failures. The restored-shell
probe observes startup registration without running a second `compinit`.
For a focused iteration, select a file with unittest discovery, then run
the full script before handoff:

```sh
/usr/bin/python3 -B -m unittest discover -s tests -p 'test_completions.py' -v
/usr/bin/python3 -B -m unittest discover -s tests -p 'test_optional_completions.py' -v
```

Passing these checks does not establish fresh Ubuntu installation or live WSL
terminal qualification. Record exactly which checks ran and any limitations.
The hosted [GitHub Actions workflow](.github/workflows/tests.yml) separates the
local suite from real installation qualification as described below;
configuration alone is not evidence that a hosted job passed.

## CI meanings and triggers

| Result | Exact meaning |
| --- | --- |
| **Unit CI passed** | Host-independent regression coverage passed: logic, ownership, migration, recovery, state machines and completion behavior. This requires Python/Zsh, but does not qualify the host distribution for production installation. |
| **Platform-gate tests passed** | Platform decision logic passed against explicit release/architecture fixtures, including Ubuntu 26.04 acceptance and unsupported-release rejection. These tests are part of the unit job, not installation evidence. |
| **Ubuntu 26.04 qualification passed** | The real bootstrap ran successfully as a normal user in a fresh Ubuntu 26.04 environment, with real platform detection and the full `all` scenario. This is the platform-support qualification gate. |

The `unit` job, displayed as **Host-independent units and platform-gate logic**,
runs `./scripts/test` on GitHub-hosted `ubuntu-24.04`. Unrelated logic tests
isolate platform detection, including the CLI completion-failure regression in
[test_completions.py](tests/test_completions.py). Explicit `PlatformTests` in
[test_logic.py](tests/test_logic.py) exercise the real detector with fixture
files. A passing Ubuntu 24.04 unit job must never be described as Ubuntu 26.04
qualification; production still rejects Ubuntu 24.04.

The `integration` job, displayed as **Ubuntu 26.04 qualification (all profiles,
Podman)**, also uses a GitHub-hosted `ubuntu-24.04` orchestration host. It runs
`./scripts/test-podman --scenario all` against the real
`docker.io/library/ubuntu:26.04` userspace, without mocking platform detection.
The orchestration host is not the installation target.

| Event | Unit job | Ubuntu 26.04 qualification |
| --- | --- | --- |
| Other branch/tag push, or pull request (including into `main`) | Runs | Skipped |
| Push to `main` | Runs | Runs after units pass |
| `workflow_dispatch`, `integration=false` (default) | Runs | Skipped |
| `workflow_dispatch`, `integration=true` | Runs | Full run after units pass on the selected ref |

This is post-push qualification of `main`, not a pre-merge installation check.
A failed unit job prevents qualification. No reused container or interactive
debug retry is requested by CI; qualification failure remains a failure.

### Qualification environment choice and cost

Retain the Ubuntu 24.04 host plus Ubuntu 26.04 Podman path. It reproduces the
already-qualified local command and preserves the existing resource discipline.
The full run covers base installation, all optional profiles, second-pass
preservation, migration/recovery, real tool smoke checks and scoped updates.

| Consideration | Ubuntu 24.04 host + Podman 26.04 | Direct native GitHub-hosted Ubuntu 26.04 |
| --- | --- | --- |
| Meaning | Fresh minimal 26.04 userspace installation with real detection | Real 26.04 host/kernel, but preinstalled tools can mask fresh-install behavior |
| Reproducibility | Same image/setup/harness locally and in CI | Hosted inventory changes; direct fixtures would need adaptation |
| Isolation | Container-local HOME, normal user, read-only repository mount | Disposable VM, with installation into runner account/system |
| Runtime | Image/setup overhead; downloads and builds dominate | Could avoid container setup; no measured speed advantage |
| Maintenance | Existing harness unchanged | Separate direct-run setup and checks required |
| Runner maturity | Established explicit 24.04 orchestration label | Newer 26.04 image; maturity alone does not improve installation coverage |
| Cleanup | Per-run container ownership, signal/finally cleanup, before/after audits | VM disposal isolates jobs but does not retain the existing resource audit |
| Local similarity | Exact existing qualification command | Separate reproduction path |

As checked on 2026-10-05, GitHub reports that native Ubuntu 26.04 runners
[left public preview on 2026-09-17](https://github.blog/changelog/2026-09-17-ubuntu-26-generally-available-and-latest-migration/).
While in preview, image stability would be an additional concern; the current
choice rests on fresh-install isolation and reuse, not an outdated preview claim.
Changing only the orchestration host to 26.04 while retaining Podman offers no
demonstrated additional qualification signal.

The [2026-10-05 dotfiles qualification](docs/VALIDATION.md#dotfiles-cargo-ownership-alignment--2026-10-05)
took 592.42 seconds (9.9 minutes); earlier full runs took up to 2331.14 seconds
(38.9 minutes). That longest run preceded the
[Cargo retry guard](docs/CARGO_RETRY_2026-10-03.md#validation-evidence), whose
fresh qualification took 722.45 seconds (12 minutes). The later
[permissive-umask qualification](docs/VALIDATION.md#permissive-umask-directory-safety--2026-10-05)
took 577.68 seconds (9.6 minutes). These are dated local observations, not hosted
timing promises.
Units take tens of seconds locally. Each successful unit run on a push to `main`
now adds one full installation job, bounded by its existing 45-minute timeout;
branch/PR cost is unchanged. Cold downloads, source fallbacks, upstream service
failures and hosted CPU/memory/disk limits can slow or fail qualification. The
45-minute hosted budget still needs confirmation from actual Actions runs.

A base-only automatic run would still execute real 26.04 installation, but lose
optional-profile installation and smoke tests, all-profile second-pass checks,
legacy migration/recovery regressions and scoped all-profile update coverage.
Keep `all` on `main` rather than silently reducing that assurance. No additional
caching, retry policy or installer path is introduced.

The Ubuntu image tag and latest-stable tool channels are mutable, so this is a
repeatable environment/setup rather than a bit-for-bit pinned installation.
Containers share the orchestration host's kernel: this gate qualifies x86_64
Ubuntu 26.04 userspace bootstrap behavior, not a native 26.04 kernel, ARM64,
desktop, or live WSL/Wayland/terminal session.

## Pinned-dotfiles shell probes

The integration suite also runs [pinned-dotfiles shell probes](tests/dotfiles_shell_checks.py)
against the verified checkout. To run them separately with a clean checkout at
the manifest's exact revision:

```sh
/usr/bin/python3 -B tests/dotfiles_shell_checks.py /path/to/pinned-dotfiles-checkout
```

These probes use temporary HOME, ZDOTDIR and XDG directories, a whitelisted
environment, and controlled executable/PATH fixtures. They check Cargo launcher
precedence, absence of legacy uv helper sourcing and Julia PATH injection,
inherited ordering, repeated/nested startup, native completion registration,
and fnm success/failure. They never restore files into the host user's HOME.

## Real installation verification

[test-podman](scripts/test-podman) runs the single-container integration harness.
The default covers all scenarios:

```sh
./scripts/test-podman
```

| Scenario | Scope and prerequisites |
| --- | --- |
| `--scenario base` | Base installation, second-pass preservation, shell Yes/No, ownership/recovery and generated completions |
| `--scenario engineering` | All optional profiles, system/native completion registration, unavailable reporting, native failure/update preservation and second-pass checks; bootstrap also installs their default base |
| `--scenario update` | Updates selected profiles while preserving an unrelated Cargo fixture; requires an already initialized managed base for fixture creation |
| Default `all` | Runs base, engineering and update in order in one fresh container |

The runner audits both `podman ps` and `podman ps -a` before creating or starting
anything and after cleanup. It uses `docker.io/library/ubuntu:26.04`, fixed name
`ubuntu-bootstrap-integration` and label
`org.beren-project.ubuntu-bootstrap=integration`; its repository mount is read
only. A fresh container is limited to 6 GB memory and four CPUs. Fixture setup
creates a normal `engineer` user with container-local sudo; bootstrap itself
runs as that user with an isolated HOME. No bootstrap installation targets the
host's HOME.

If the fixed name already exists, the runner inspects it and refuses unrelated
ownership. A matching container needs explicit `--reuse`; a borrowed container
is never deleted by the runner. With no matching container, `--reuse` still
creates a fresh one. Reuse and retries after a failure establish debugging
evidence, not a new fresh-install qualification. `--debug-retry` permits an
interactive retry in the same container; it does not create numbered replacements.
When an `all` run resumes at `base` or `engineering`, a successful retry also
finishes the remaining stages in that container, including update checks.
Only container IDs created by that invocation are cleaned up. Interrupted-create
discovery requires a unique per-run label in addition to the fixed name, and
uses full IDs. Borrowed containers never enter this cleanup list. Do not substitute
global prune, broad cleanup or removal of unrelated images/volumes.

Ignored `test-results/` contains the latest session audit, exit code, timing,
receipts, last-run status and installation log. It is overwritten by later
sessions, so preserve relevant evidence separately before another run. Inspect
the before/after inventories and report unrelated resource states as well as
project cleanup; the runner's automated unrelated-container check only proves
that those IDs remain present.

## Human inspection

Follow [the human inspection guide](docs/HUMAN_TESTING.md) for a fresh interactive
Podman session with all optional profiles. It separates host, container-root and
normal-user commands, preserves terminal settings through login, and provides
color samples plus prompt, completion, tmux, editor and engineering-tool checks.
Export observations and bootstrap diagnostics before the `--rm` container exits.
This complements the automated harness; a manual pass does not establish its
ownership, recovery or update coverage or live WSL/Wayland qualification.

## Review and support evidence

For a documentation change, verify the following before handoff:

- Inventories and dependencies agree with the manifest and CLI, including
  crate versus executable names and automatic source-build prerequisites.
- Commands distinguish planning, installation, update and recovery. State the
  Stage-0 missing-Python exception to `--plan`, shell consent and automation rules.
- The full dotfiles SHA and five-file selection match the current manifest;
  ownership, receipts, optional failures and completion integration are accurate.
- Local links/anchors resolve, duplicated claims agree, and historical test
  results stay dated and separate from new documentation checks.
- `git diff --check` passes; inspect `git diff --stat`, `git diff` and
  `git status --short` for the intended scope and staged changes.

For support, supply the repository revision, exact command and exit status,
Ubuntu release/architecture, interactive versus CI mode, selected profiles and
the failing summary entry. Include the relevant log excerpt and receipt/last-run
observations from `~/.local/state/ubuntu-bootstrap/` (or the configured
`XDG_STATE_HOME`). For integration issues, include `podman-session.json` and
whether the container was fresh, reused or retried. Remove personal information
and credentials from shared evidence. Inspect conflicts before recovery and
keep original files and retained installation trees available for review.

Report the final diff, validation performed, unperformed qualification and Git
status for review. Stage, commit and push only when explicitly requested.
