# Contributing

Start with [usage and recovery](docs/USAGE.md), the
[runtime architecture](docs/ARCHITECTURE.md) and
[dated validation evidence](docs/VALIDATION.md). The supported installation
target is Ubuntu 26.04 (`resolute`), primarily x86_64 WSL2; Windows/WSL host
provisioning is outside this repository. ARM64 and live terminal qualification
limits are recorded in the evidence document.

## Development prerequisites

For local checks, use the target's system `/usr/bin/python3` and Zsh. The Python
modules use the standard library; there is no pip dependency installation.
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

The current documentation change uses the
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
For a focused iteration, select either file with unittest discovery, then run
the full script before handoff:

```sh
/usr/bin/python3 -B -m unittest discover -s tests -p 'test_completions.py' -v
```

Passing these checks does not establish fresh Ubuntu installation or live WSL
terminal qualification. Record exactly which checks ran and any limitations.
The hosted [GitHub Actions workflow](.github/workflows/tests.yml) runs the local
suite; configuration alone is not evidence that a hosted job passed.

## Real installation verification

[test-podman](scripts/test-podman) runs the single-container integration harness.
The default covers all scenarios:

```sh
./scripts/test-podman
```

| Scenario | Scope and prerequisites |
| --- | --- |
| `--scenario base` | Base installation, second-pass preservation, shell Yes/No, ownership/recovery and generated completions |
| `--scenario engineering` | All optional profiles and second-pass preservation; bootstrap also installs their default base |
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
Only container IDs created by that invocation are cleaned up. Do not substitute
global prune, broad cleanup or removal of unrelated images/volumes.

Ignored `test-results/` contains the latest session audit, exit code, timing,
receipts, last-run status and installation log. It is overwritten by later
sessions, so preserve relevant evidence separately before another run. Inspect
the before/after inventories and report unrelated resource states as well as
project cleanup; the runner's automated unrelated-container check only proves
that those IDs remain present.

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
