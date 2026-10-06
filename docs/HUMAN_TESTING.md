# Human inspection in Podman

Use this procedure to inspect a fresh installation in your actual terminal:
colors, prompt appearance, completions, tmux and terminal editors. It installs
all optional profiles in an isolated Ubuntu 26.04 container as `engineer`.
The repository is mounted read only; the container has its own HOME.

This supplements [automated installation verification](../CONTRIBUTING.md#real-installation-verification).
A manual pass records the behavior you observed in that terminal. It does not
establish the automated suite's ownership, recovery or update coverage, ARM64
qualification, or live WSL/Wayland clipboard behavior.

## 1. Host: inspect and launch

Use an interactive terminal on the Podman host, from the repository root.
You need Podman, network access and capacity for the 6 GiB/four-CPU container,
downloads and source builds. The procedure targets x86_64; ARM64 retains the
[decline/opt-in policy and qualification limits](USAGE.md#choose-a-run).

Inspect running and stopped containers before launching:

```sh
test -x ./bootstrap
podman ps
podman ps -a
printf 'TERM=%s\nCOLORTERM=%s\nNO_COLOR=%s\n' \
  "${TERM:-}" "${COLORTERM:-}" "${NO_COLOR-<unset>}"
if command -v tput >/dev/null 2>&1; then tput colors; fi
```

If `ubuntu-bootstrap-human` already exists, inspect it and finish that session
before starting a fresh test. Preserve it rather than deleting an unknown
container or choosing replacement names. Keep the initial inventory for the
final comparison. If host `tput` is absent, record that fact; continue with the
visual samples below. An empty `TERM` needs investigation before launch.

```sh
podman run --rm -it \
  --name ubuntu-bootstrap-human \
  --memory 6g \
  --cpus 4 \
  -e TERM="$TERM" \
  -e COLORTERM="${COLORTERM:-}" \
  -v "$PWD:/workspace:ro" \
  docker.io/library/ubuntu:26.04 \
  bash
```

Run this directly in the terminal. Podman's `-it` provides interactive input
and a pseudo-terminal; see the [official run reference](https://docs.podman.io/en/latest/markdown/podman-run.1.html#tty-t).
`--rm` removes this container when its initial Bash exits, so export evidence
before finishing. Only the repository directory is mounted; HOME belongs to
the container.

## 2. Container root: prepare the normal user

The first prompt is root **inside the container**. Run only this preparation
there; installation itself belongs to `engineer`. `ncurses-bin` supplies `tput`
and `infocmp` for the inspection and is a test prerequisite, not a new bootstrap
package requirement.

```sh
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  --no-install-recommends sudo git ca-certificates ncurses-bin

useradd -m -s /bin/bash engineer
printf 'engineer ALL=(ALL) NOPASSWD: ALL\n' \
  > /etc/sudoers.d/engineer
chmod 0440 /etc/sudoers.d/engineer

printf 'TERM=%s\nCOLORTERM=%s\n' "${TERM:-}" "${COLORTERM:-}"
tput colors
su --login --whitelist-environment=TERM,COLORTERM engineer
```

The passwordless sudo rule is confined to this disposable container.
The explicit whitelist preserves terminal variables while login sets
`engineer`'s HOME and PATH. `su` versions differ in which color-related variables
they preserve by default; PAM can also affect the final environment. See the
[official su manual](https://man7.org/linux/man-pages/man1/su.1.html).

## 3. Engineer: compare the terminal and install

Confirm that the prompt now belongs to `engineer`, HOME is `/home/engineer`,
UID is nonzero, and terminal settings agree with the container-root baseline.
`su --login` starts in the user's HOME, so use the absolute mount path
`/workspace`, not `cd workspace`.

```sh
id
printf 'HOME=%s\nTERM=%s\nCOLORTERM=%s\n' \
  "$HOME" "${TERM:-}" "${COLORTERM:-}"
tput colors
sudo -n true
cd /workspace
```

Run the [color diagnostics](#color-diagnostics-and-eight-color-results) now,
before bootstrap, and record the baseline. Then install all optional profiles:

```sh
./bootstrap \
  --build \
  --julia \
  --ngspice \
  --openmodelica \
  --vim \
  --nvim \
  --emacs
```

Optional flags bypass the selection menu. The shell-consent prompt still
appears: Enter accepts the default Yes, changes only `engineer`'s login shell,
and enters Zsh after successful installation. Answer `n` to preserve Bash;
after a successful run, enter `zsh -l` manually for the inspection.
Keep the run attached to the terminal rather than piping it through `tee`,
which changes the final-shell entry conditions. Bootstrap saves its own log.

Expect `OK bootstrap ready` and an empty `failed` list in
`~/.local/state/ubuntu-bootstrap/last-run.json`. Inspect errors before marking
the installation passed; early failures can leave that record absent or stale.
An `unavailable` completion status is expected for some tools and is distinct
from an installation failure. See [usage and recovery](USAGE.md#troubleshooting-by-task).

## Color diagnostics and eight-color results

Run these commands on the host, as `engineer` before installation, in the
installed Zsh session, and inside tmux. Record each location separately.
On the host, skip `tput`/`infocmp` if absent and note the missing diagnostic.

```sh
printf 'TERM=%s\nCOLORTERM=%s\nNO_COLOR=%s\n' \
  "${TERM:-}" "${COLORTERM:-}" "${NO_COLOR-<unset>}"
test -t 0 && test -t 1 && printf 'stdin and stdout are terminals\n'
tput colors
infocmp "$TERM"
```

`tput colors` reads the selected terminfo entry, not the display's actual color
rendering. For example, `xterm` commonly reports 8 and `xterm-256color` reports
256. A missing entry is an error, not an eight-color result. A reported 256
does not prove or exclude RGB truecolor support. Consult the
[official tput reference](https://invisible-island.net/ncurses/man/tput.1.html).

These samples bypass application color detection and work in Bash or Zsh:

```sh
# Sixteen ANSI background colors (normal and bright).
for human_color in $(seq 40 47) $(seq 100 107); do
    printf '\033[%sm   \033[0m %s ' "$human_color" "$human_color"
done
printf '\n'

# Indexed 256-color palette, sixteen entries per row.
for human_color in $(seq 0 255); do
    printf '\033[48;5;%sm %3s \033[0m' "$human_color" "$human_color"
    if [ $(((human_color + 1) % 16)) -eq 0 ]; then printf '\n'; fi
done

# RGB gradient, eighty samples from green to red.
for human_color in $(seq 0 79); do
    human_red=$((255 * human_color / 79))
    printf '\033[48;2;%s;%s;128m \033[0m' \
      "$human_red" "$((255 - human_red))"
done
printf '\n'
```

Expect the indexed palette to contain many distinct colors on a supporting
terminal. For RGB-capable terminals, compare the gradient with the host sample;
an unsupported or visibly quantized host gradient is not a bootstrap failure.
ANSI colors depend on your terminal theme, and appearance is a human judgment.
Record unexpected reductions and the first location where they occur.

| Observation | Inspect and next step |
| --- | --- |
| Host and container both report 8 | Check the host terminal's documented capabilities and actual `TERM`. Correct a mismatched host setting only after verifying support, then launch a new test. |
| Host reports 256, container reports 8 | Compare `TERM` at container-root, engineer and Zsh boundaries; inspect the selected terminfo entry and shell startup for changes. |
| `infocmp` or `tput` reports a missing terminal entry | Inside the container, try `sudo apt-get install -y --no-install-recommends ncurses-term`, then recheck the same `TERM`. Record this additional test prerequisite; do not relabel the terminal to hide the missing entry. |
| Palette works but an application has few/no colors | Inspect that application's configuration, color mode, `COLORTERM`, `NO_COLOR`, and whether output is attached to a terminal. Basic ANSI colors may be its intended theme. |
| Colors degrade only inside tmux | Compare outer and pane settings, tmux configuration and its reported terminal features. The pane's `TERM` is expected to describe tmux rather than match the outer terminal literally. |
| Colors work but prompt symbols appear as boxes | Inspect the host terminal's font and glyph coverage; installing fonts inside this container does not configure the host terminal. |

Preserve the failing observations before any experiment. Do not automatically
force `TERM=xterm-256color` or `COLORTERM=truecolor`: neither adds capabilities
to the host terminal. The cause of the earlier eight-color result remains
unconfirmed until the failing boundary is reproduced.

## 4. Installed Zsh: inspect the interactive environment

Run these checks outside tmux first. Mark each row passed, failed or skipped;
record the reason for skips and any differences from the baseline.

| Check | Expected observation |
| --- | --- |
| Prompt and startup | Zsh opens without startup errors; Starship prompt text is readable and expected glyphs render. Repeat the color samples. |
| Command paths and runtimes | Cargo applications resolve from `~/.cargo/bin`; managed Python resolves from `~/.local/bin`; Node is available through fnm and matches its default. |
| Tab completion | Type `uv --` and press Tab for option candidates, `vim /tmp/` for file candidates, and `julia +` for installed channel candidates. Clear each line with Ctrl+C rather than executing it. |
| fzf selection | Verify the bindings below, then try Ctrl+R for history, Ctrl+T for files, Alt+C for directories, and type `ls **` followed by Tab for fuzzy completion. Cancel with Esc or Ctrl+C; record disabled bindings and unexpected behavior. |
| Terminal editors | Vim, Neovim and Emacs open, accept navigation/input, redraw correctly and exit cleanly. Inspect their appearance; no editor theme is prescribed. |
| Build and engineering tools | Version commands succeed; Julia arithmetic prints `2`. These basic probes supplement the automated numerical simulations. |

Check fzf in this interactive terminal, where stdin is a terminal and ZLE is
enabled. A captured `zsh -lic 'true'` deliberately skips fzf integration.

```zsh
fzf --version
bindkey '^R'
bindkey '^T'
bindkey '^[c'
bindkey '^I'
print -- ${+widgets[fzf-history-widget]} ${+widgets[fzf-file-widget]} ${+widgets[fzf-cd-widget]} ${+widgets[fzf-completion]}
```

With fzf 0.48.0+ supporting `--zsh` and default settings, expect
`fzf-history-widget`, `fzf-file-widget`, `fzf-cd-widget`, and `fzf-completion`,
respectively, and `1 1 1 1`. An intentionally empty `FZF_CTRL_R_COMMAND`,
`FZF_CTRL_T_COMMAND`, or `FZF_ALT_C_COMMAND` disables its corresponding binding.
The config loads embedded integration rather than examples under
`/usr/share/doc/fzf/`; absent documentation files do not prevent setup.

Check paths and versions in the installed Zsh session:

```sh
for human_tool in rustup cargo uv uvx python fnm node juliaup julia; do
    command -v "$human_tool"
done
zsh --version
gh --version
rustup show active-toolchain
cargo --version
uv --version
python --version
fnm default
node --version
juliaup status
julia -e 'println(1 + 1)'

gcc --version
cmake --version
ninja --version
ngspice --version
omc --version
vim --version
nvim --version
emacs --version
```

Rust should select stable, Juliaup should list the `release` channel, and Julia
should print `2`. Ordinary software versions follow managed stable/LTS channels;
ngspice remains the manifest-pinned release. Inspect each command's result
individually; a final successful command does not erase an earlier failure.

Open each editor separately using a container-local scratch path:

```sh
vim /tmp/ubuntu-bootstrap-human.txt
nvim /tmp/ubuntu-bootstrap-human.txt
emacs -nw /tmp/ubuntu-bootstrap-human.txt
```

For Vim/Neovim, press Escape and enter `:q!` to discard changes and exit.
For Emacs, press Ctrl+x followed by Ctrl+c; decline saving if prompted.
Scratch files belong inside the container, since `/workspace` is read only.

## 5. Engineer: inspect tmux

Start a separate test server inside the container, loading the installed
`~/.tmux.conf`:

```sh
tmux -L ubuntu-bootstrap-human new-session -s inspection
```

In the pane, repeat the color diagnostics and prompt/completion checks. Use
`zsh -l` first if the pane opens Bash because shell change was declined.
Also inspect:

```sh
tmux display-message -p 'outer=#{client_termname} features=#{client_termfeatures}'
tmux show-options -s default-terminal
```

The pane normally uses a tmux/screen terminal description. Compare rendering
with the outer session and record any reduction. Exit the pane shell, and any
nested Zsh, to return to the outer engineer session. Finishing the last pane
ends this test server; it does not affect a host tmux server.

## 6. Host: save evidence before closing the container

Leave the container running. In a **second host terminal**, change to the same
repository root and export into a new ignored directory:

```sh
mkdir -p test-results
human_evidence_dir=$(mktemp -d "$PWD/test-results/human-XXXXXXXX")
git rev-parse HEAD > "$human_evidence_dir/revision.txt"
git status --short > "$human_evidence_dir/worktree-status.txt"
podman --version > "$human_evidence_dir/podman-version.txt"
podman inspect --format '{{.Image}}' ubuntu-bootstrap-human \
  > "$human_evidence_dir/image-id.txt"
podman cp \
  ubuntu-bootstrap-human:/home/engineer/.local/state/ubuntu-bootstrap \
  "$human_evidence_dir/"
printf 'Evidence directory: %s\n' "$human_evidence_dir"
```

If installation failed before creating state, record the missing state and
save the visible error instead. Inspect `bootstrap.log` and `last-run.json`
before sharing; keep early-failure/stale-record limits explicit.
Add a short inspection note using this template, with copied diagnostic output
and optional screenshots for appearance failures:

| Item | Record |
| --- | --- |
| Session | Date, revision/worktree changes, host OS/architecture, terminal name/version and font |
| Installation | Exact bootstrap command, shell-consent answer, final summary and failed/skipped lists |
| Terminal boundaries | Host/root/engineer/Zsh/tmux `TERM`, `COLORTERM`, `NO_COLOR`, `tput colors` and visual sample results |
| Interactive checks | Prompt, paths/runtimes, Tab completion, each editor, build/engineering probes and tmux: passed/failed/skipped with details |
| Experiments | Original failing observation, any session-only corrections or extra diagnostic packages, and retest result |
| Resources | Initial/final container inventories and whether the human container was removed |

This manual export does not produce the automated runner's
`podman-session.json`, nor does it replace its audit. Human evidence lives in
its own subdirectory so later automated runs do not overwrite it.

## 7. Container, then host: finish

After saving evidence, return to the container terminal. Exit nested sessions
until the initial container-root Bash exits. With the default successful shell
transition, the usual sequence is Zsh → engineer Bash → root Bash → host;
additional manual Zsh/tmux sessions add nesting. Use `id -un` to identify your
current user if unsure, and stop exiting once you reach the host terminal.

On the host, compare with the initial inventory:

```sh
podman ps
podman ps -a
```

Expect `ubuntu-bootstrap-human` to be absent after its initial Bash exits and
unrelated containers to retain their original states. Detaching leaves the
container running; it is not completion. No image/volume cleanup or global
prune is part of this procedure. Record remaining resources for inspection.
