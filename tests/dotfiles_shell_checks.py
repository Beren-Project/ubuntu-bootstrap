"""Behavioral probes of the actual pinned dotfiles, in disposable environments.

Run directly with a verified checkout path, or through container_checks.base.
No copied shell implementation or live user configuration is used.
"""
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile


def check_shell_contract(root):
    root = Path(root)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from bootstrap_lib.config import load_manifest
    revision = load_manifest()["dotfiles"]["revision"]
    assert subprocess.check_output(["/usr/bin/git", "-C", str(root), "rev-parse", "HEAD"],
                                   text=True).strip() == revision
    assert not subprocess.check_output(["/usr/bin/git", "-C", str(root), "status", "--porcelain",
                                        "--untracked-files=all", "--ignored"], text=True).strip()
    with tempfile.TemporaryDirectory(prefix="bootstrap-shell-") as directory:
        home = Path(directory)
        for name in (".zshenv", ".zshrc"):
            shutil.copyfile(root / "home" / name, home / name)
        for name in (".cargo/bin", "bin", ".local/bin", ".juliaup/bin", "inherited tools",
                     ".julia/juliaup/completions", "runtime"):
            (home / name).mkdir(parents=True, exist_ok=True)
        cargo, personal, local, legacy, inherited = [str(home / name) for name in
            (".cargo/bin", "bin", ".local/bin", ".juliaup/bin", "inherited tools")]
        tools = ("uv", "uvx", "juliaup", "julia")
        for path in (cargo, local, legacy):
            for name in tools:
                binary = Path(path) / name
                binary.write_text("#!/bin/sh\nexit 0\n")
                binary.chmod(0o755)
        # Prevent machine-installed optional integrations from influencing probes.
        for name in ("starship", "direnv", "zoxide", "eza", "mmdc", "fnm"):
            binary = Path(inherited) / name
            binary.write_text("#!/bin/sh\nexit 1\n")
            binary.chmod(0o755)
        cargo_env = home / ".cargo/env"
        cargo_env.write_text('case ":$PATH:" in *:"$HOME/.cargo/bin":*) ;; '
                             '*) export PATH="$HOME/.cargo/bin${PATH:+:$PATH}" ;; esac\n')
        for name in ("env", "env.fish"):
            (home / ".local/bin" / name).write_text("BOOTSTRAP_LEGACY_HELPER_SOURCED=yes\n")
        (home / ".julia/juliaup/completions/zsh.zsh").write_text(
            "_juliaup() { return 0; }\n_julia_channel() { return 0; }\n"
            "compdef _juliaup juliaup\ncompdef _julia_channel julia\n")
        windows = "/mnt/c/Program Files/Bootstrap Fixture " + home.name
        lookalikes = [legacy + "-tools", legacy + "/nested", str(home / "other/.juliaup/bin")]
        inherited_entries = [inherited, "/usr/bin", "/bin", windows, *lookalikes]
        entries = [local, inherited, personal, cargo, *inherited_entries[1:], cargo, local, "/bin"]
        # A whitelist, not os.environ: inherited ZDOTDIR, functions, XDG paths,
        # Julia overrides, Node settings and live user PATH cannot enter probes.
        env = {"HOME": str(home), "ZDOTDIR": str(home), "PATH": ":".join(entries),
               "XDG_DATA_HOME": str(home / "data"), "XDG_CONFIG_HOME": str(home / "config"),
               "XDG_CACHE_HOME": str(home / "cache"), "XDG_STATE_HOME": str(home / "state"),
               "XDG_RUNTIME_DIR": str(home / "runtime"), "TERM": "dumb", "LC_ALL": "C"}

        def probe(code, interactive=True, overrides=None):
            result = subprocess.run(["/usr/bin/zsh", "-d", "-ic" if interactive else "-c", code],
                                    env={**env, **(overrides or {})}, cwd=home,
                                    stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                    start_new_session=True, timeout=15)
            assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
            assert not result.stderr, result.stderr
            return result.stdout.splitlines()

        emit = '''print -r -- "$PATH"
for tool in uv uvx juliaup julia; do whence -p -- "$tool" || exit 20; done
[[ -z ${BOOTSTRAP_LEGACY_HELPER_SOURCED:-} ]] || exit 21
[[ ${path[(Ie)$HOME/.juliaup/bin]} == 0 ]] || exit 22
[[ $_comps[juliaup] == _juliaup && $_comps[julia] == _julia_channel ]] || exit 23
'''
        # -d disables machine global startup; personal startup remains enabled.
        nvim = "/opt/nvim-linux-x86_64/bin"
        preference = [nvim] if Path(nvim).is_dir() else []
        expected_path = [*preference, cargo, *inherited_entries, personal, local]
        expected = [":".join(expected_path), *[str(Path(cargo) / name) for name in tools]]
        assert probe(emit) == expected
        repeated = "emit() { " + emit + " }; emit; source ~/.zshenv; source ~/.zshrc; emit; "
        nested = "/usr/bin/zsh -d -ic " + shlex.quote(emit)
        assert probe(repeated + nested) == expected * 3
        assert probe('print -r -- "$PATH"; whence -p uv; '
                     '[[ -z ${BOOTSTRAP_LEGACY_HELPER_SOURCED:-} ]]', interactive=False) == [
                         ":".join([cargo, *inherited_entries, personal, local]), str(Path(cargo) / "uv")]
        cargo_env.unlink()
        assert probe(emit) == expected, "Cargo directory fallback must not need .cargo/env"

        # fnm emits a fresh multishell per startup; only its stale entries retire.
        fnm_log = home / "fnm.jsonl"
        fnm = Path(inherited) / "fnm"
        fnm.write_text("#!/usr/bin/python3\nimport json, os, pathlib, shlex, sys\n"
            f"log = pathlib.Path({str(fnm_log)!r})\n"
            "with log.open('a') as stream:\n"
            "    stream.write(json.dumps({'args': sys.argv[1:], 'path': os.environ['PATH']}) + '\\n')\n"
            f"multishell = {str(home / 'runtime/fnm_multishells')!r} + '/' + str(os.getpid())\n"
            "print('export PATH=' + shlex.quote(multishell + '/bin') + ':$PATH')\n")
        stale = str(home / "runtime/fnm_multishells/old/bin")
        unrelated = str(home / "runtime/fnm_multishells-tools/keep/bin")
        output = probe(repeated + nested, overrides={"PATH": ":".join([stale, *entries, unrelated])})
        paths = [output[i].split(":") for i in (0, 5, 10)]
        fnm_tail = [*preference, cargo, *inherited_entries, unrelated, personal, local]
        for i, path in enumerate(paths):
            assert path[0].startswith(str(home / "runtime/fnm_multishells") + "/")
            assert path[0].endswith("/bin") and path[1:] == fnm_tail, path
            assert len(path) == len(set(path))
            assert output[i * 5 + 1:i * 5 + 5] == expected[1:]
        assert len({path[0] for path in paths}) == 3
        calls = [json.loads(line) for line in fnm_log.read_text().splitlines()]
        assert len(calls) == 3 and stale in calls[0]["path"].split(":")
        assert all(call["args"] == ["env", "--use-on-cd", "--shell", "zsh"] for call in calls)

        fnm.write_text('#!/bin/sh\nprintf \'export PATH="/invalid-fnm-output"\\n\'\nexit 7\n')
        failed_expected = [":".join([*preference, cargo, stale, *inherited_entries,
                                     unrelated, personal, local]), *expected[1:]]
        assert probe(repeated, overrides={"PATH": ":".join([stale, *entries, unrelated])}) == failed_expected * 2
    print("OK pinned Zsh: isolated fresh/repeated/nested startup, Cargo ownership, no legacy helpers/PATH, fnm success/failure")


if __name__ == "__main__":
    check_shell_contract(sys.argv[1])
