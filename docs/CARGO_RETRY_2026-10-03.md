# Cargo binary-resolution retry follow-up

Starting commit: `384260cda6ae5e6de581c9913cdade592b692e17`; worktree clean.
No staging, committing or pushing is part of this pass. Rust, uv/Juliaup
ownership, receipts/journal schemas, completions, dotfiles and engineering
profiles retain the completed maintenance design.

## Root cause and policy

The saved 2,331.14-second qualification used cargo-binstall 1.25.0. Requests to
`https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}` scheduled
111.606–120-second retries after GitHub quota/reset or Retry-After headers.
Exact versions and existing package URL overrides do not skip these existence
checks. Healthy binary installs already took approximately 2–4 seconds.
See the [verified upstream interfaces and sources](UPSTREAM.md#cargo-binstall-github-retry-interfaces-2026-10-03).

The scheduled delay is not evidence that every request actually slept 120
seconds: upstream's separate 15-second candidate timeout interrupts discovery.
The old log contains four candidate timeouts for ripgrep and two each for zoxide,
macchina, mcat and uv, corresponding to 60/30/30/30/30 seconds of sequential
candidate budgets, excluding metadata acquisition. Source compilation and its
own network failures added substantial time. These are derived budgets, not
measured historical per-application wall times.

Supported per-candidate timeouts do not give a selective quota budget and exclude
archive download. There is no supported API-disable or HTTP retry-budget flag.
The selected small supervisor leaves all installation work with cargo-binstall:

1. Resolve/validate stable crates.io metadata once when install/update is needed.
2. Attempt `crate-meta-data` binary installation for that exact version, retaining
   validated URL/layout overrides and upstream target selection.
3. Observe JSON events at info level. Recognized GitHub REST/GraphQL 403/429
   retry events carry upstream evidence of a requested delay, not merely a status.
   HTTP-200 delay events are labelled server-requested retry delays, without
   claiming their header was definitely quota exhaustion.
4. Allow at most five seconds of cumulative announced GitHub retry sleeps.
   Reject a proposed sleep exceeding the budget, cancelling as soon as its
   diagnostic is observed instead of waiting through that delay.
   An explicit upstream GraphQL rate-limit diagnostic cancels immediately too.
   Ordinary latency, bare 403, DNS errors and 5xx are not labelled quota events.
5. SIGTERM the isolated process group; allow two seconds for upstream cancellation
   and staging/lock cleanup, then SIGKILL/reap if necessary. Publication-start
   diagnostics revoke automatic cancellation. User cancellation never falls back.
6. After a failed/cancelled attempt, verify executable hashes/types/modes/owners and
   Cargo registration files are unchanged; only harmless empty first-use Cargo
   v1 metadata is allowed. Changed evidence is preserved and fails closed.
7. For known transport failures or no available candidate (upstream exit 94), use
   the existing scoped prerequisites and `cargo install --locked --version VERSION`.
   Candidate metadata/archive/signature errors aggregated into exit 94 are
   detected separately and stop; installation and other unknown exits stop too.
8. Validate installed registry and executable versions before publishing receipts.

Binary and source versions cannot drift between metadata resolutions. Missing
previously owned binaries also use `--force` in source repair, so an existing
same-version Cargo registration cannot prevent restoring their executables.
No broad Cargo application update is introduced.

`--no-discover-github-token` prevents default private credential discovery. Only
explicit environment `GITHUB_TOKEN`/`GH_TOKEN` values pass naturally to binstall;
they are never command arguments or receipt fields, and captured output is
redacted before logging. Source-build environments omit these two variables,
matching upstream's own fallback behavior. No authentication is required.

## Validation evidence

Focused subprocess fixtures cover healthy success/latency, small retries,
403/429/HTTP-200 long waits, GraphQL rate-limit reporting, ordinary 403/DNS/5xx,
unavailable binaries, metadata/archive/signature failures, partial writes,
publication boundaries, TERM/KILL and descendant cleanup, user interruption,
token secrecy, exact-version fallback, repair, rerun/update and unrelated Cargo
preservation. Each long-wait fixture announces and would sleep 120 seconds; the
test checks cancellation well below that duration without exhausting a live quota.

Final focused tests: 40 tests passed in 2.054 seconds. `./scripts/test` passed
133 tests in 21.223 seconds, plus manifest validation, Python AST, shell syntax
and ShellCheck. `git diff --check` passed. Modified documentation file links
were checked locally too.

| Deterministic fixture | Measured elapsed | Result |
| --- | ---: | --- |
| Fast success | 0.0282 s | Binary installed |
| Ordinary 200 ms latency | 0.2291 s | Binary installed |
| Short 429 retry (200 ms) | 0.2292 s | Binary installed |
| 403 proposing a 120-second wait | 0.0321 s | Cancelled; controlled fallback permitted |
| 429 proposing a 120-second wait | 0.0317 s | Cancelled; controlled fallback permitted |
| HTTP 200 proposing a 120-second wait | 0.0315 s | Cancelled; labelled server-requested delay |
| Explicit GraphQL rate-limit diagnostic | 0.0322 s | Cancelled |

These timings include shim process startup. The before case is a fixture's
announced/implemented 120-second sleep, derived without actually waiting for it;
the after values are measured. The exact-version source-command shim takes
approximately 0.028 seconds and performs no compilation. Real source timings
are recorded separately below.

Independent review tightened generic Reqwest classification: request-builder,
response-decoding and redirect errors stop as metadata/body errors, rather than
being treated as ordinary network failure. Added regressions passed before the
final fresh qualification. Earlier review also covered publication-marker
cancellation races, partial writes, descendants holding output pipes, repeated
user interruptions, registry repair and symlinked registration parents.

An initial fresh qualification passed in 813.70 seconds after a test-only
log-parser correction and same-container engineering/update retry. The parser
had tried to split an unrelated multiline shell command. Its regression now
limits parsing to Cargo command lines. That container was removed before a
second fresh qualification of the final runtime; final results follow below.

`./scripts/test-podman --scenario all --debug-retry` then passed **all, fresh**,
without a retry, in **722.45 seconds** on Ubuntu 26.04 x86_64. Cargo-binstall was
again 1.25.0. Runtime and test hashes were frozen throughout this qualification.
It exercised real Cargo ownership/command resolution, Python/Julia, legacy
migration, completion and receipt idempotency, publication recovery, engineering
and editor smoke tests, scoped updates and an untouched unrelated Cargo fixture.
The deterministic retry regressions also passed inside Ubuntu.

| Previously affected crate | Old candidate budgets (derived) | Old Cargo-reported source release-profile time | Final fresh binary attempt |
| --- | ---: | ---: | ---: |
| ripgrep | 60 s | 29.96 s | 2.308 s |
| zoxide | 30 s | 32.25 s | 2.659 s |
| macchina | 30 s | 106 s | 2.527 s |
| mcat | 30 s | 459 s | 3.106 s |
| uv | 30 s | 892 s | 3.644 s |

Other fresh successes: starship 2.824 s, bat 2.814 s, eza 3.021 s, fd-find
2.706 s, fnm 2.988 s, git-delta 2.771 s and Juliaup 3.397 s. Cargo-update's
binary attempt reported unavailable in 1.379 s; the real locked source fallback
for the same 22.1.1 version took **58.256 s**, excluding APT prerequisites.
Binary-attempt timings exclude bootstrap's preceding stable-version metadata
lookup. Already-current `--update` successes are excluded from the fresh table.

The total decreased by 1,608.69 seconds (about 69%). **No live quota rejection
occurred** in the final run. Most improvement came from healthy GitHub paths
avoiding the previously expensive source builds; this comparison does not prove
the retry guard saved that entire difference. The deterministic 120-second-wait
fixtures prove the guarded path independently.

Final post-qualification logging review hardened overlapping explicitly supplied
token redaction by processing the longest values first. This only changes log
rendering: commands, environment, diagnostics classification and installation
behavior remain unchanged. Prefix/suffix secrecy and ordinary latency exceeding
a reduced test retry budget have new regressions. The final focused/full results
above include those post-review reruns. Authenticated live HTTP was not exercised;
supported token selection was verified from upstream source and subprocess fixtures.

## Resource accounting and handoff

Both qualification invocations inspected `podman ps` and `podman ps -a` before
and after. The same fixed name `ubuntu-bootstrap-integration` and project labels
were used, with one container at a time. Exactly these session-created containers
were removed:

- Initial qualification: `a17a4d9b730c4bb9d8855f953f6ebb90f022a3fb930bff5a57b46782d324f7ac`.
- Final fresh qualification: `cbcbbc1221d08a94d08b6e62f7a0d73da5bd325841a90ad145a3350ad04391a4`.

Before and after each run: zero running containers, zero project test containers,
and the same seven stopped OpenProject containers (`c769d61c0153`, `e6ae4f641c7f`,
`055b44fdfa2b`, `7af40bbce2b9`, `f0c52be42500`, `6ed5d35aaeeb`, `6c9aa0d02932`).
No unrelated container, volume or image was removed; no global prune ran.
Cached Ubuntu images were retained. Final raw evidence is in ignored
`test-results/`; prior run evidence was retained under `/tmp` during analysis.

Changed files: `bootstrap_lib/rust.py`, new `bootstrap_lib/cargo_binary.py`;
`tests/container-scenario`, `tests/container_checks.py`, `tests/test_logic.py`,
`tests/test_maintenance.py`, new `tests/test_cargo_binary.py`; `docs/ARCHITECTURE.md`,
`docs/UPSTREAM.md`, `docs/USAGE.md` and this report. The final independent review
checked retry classification, version consistency, publication boundaries,
process-group termination/reaping, partial writes, token secrecy, update/migration
behavior and scope. No ownership/recovery redesign was made.

`git diff --check` passes. Nothing is staged, committed or pushed. Expected final
`git status --short`:

```text
 M bootstrap_lib/rust.py
 M docs/ARCHITECTURE.md
 M docs/UPSTREAM.md
 M docs/USAGE.md
 M tests/container-scenario
 M tests/container_checks.py
 M tests/test_logic.py
 M tests/test_maintenance.py
?? bootstrap_lib/cargo_binary.py
?? docs/CARGO_RETRY_2026-10-03.md
?? tests/test_cargo_binary.py
```

## Limits

The guard bounds recognized announced GitHub retry sleeps, not all network or
installation time. Source compilation retains its own Cargo network behavior.
Diagnostics are checked against current upstream JSON events; changes to that
interface need regression review. A hard-killed installer may leave internal
Cargo staging directories: their exact unproven paths are logged and preserved,
not deleted by a broad sweep. Unexpected publication evidence stops fallback.
Cargo-binstall bootstrap's existing verified release/checksum acquisition is
unchanged and still requires its official GitHub metadata to be reachable.

Live qualification without throttling proves the normal path; deterministic
fixtures prove quota handling. Faster live runs cannot by themselves distinguish
healthier GitHub availability from savings caused by this guard.
