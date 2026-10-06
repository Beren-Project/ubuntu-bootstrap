"""Assertions inside the normal Ubuntu integration user's isolated HOME."""
import hashlib
import json
import os
from pathlib import Path
import pty
import pwd
import re
import select
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap_lib.config import load_manifest, resolve
from bootstrap_lib.inventories import SECTION, resolve as resolve_inventory

HOME = Path.home()
CONFIG = load_manifest()
STATE = HOME / ".local/state/ubuntu-bootstrap"
RECEIPTS = STATE / "receipts.json"
BOOTSTRAP = "/workspace/bootstrap"


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, capture_output=True, **kwargs).stdout.strip()


def managed_directories():
    from bootstrap_lib.durability import parents, regular
    modes = {}
    for name in (".local", ".local/share", ".local/share/ubuntu-bootstrap", ".local/state",
                 ".local/state/ubuntu-bootstrap", ".cache", ".cache/ubuntu-bootstrap",
                 ".cargo", ".cargo/bin", ".rustup", ".zfunc"):
        path = HOME / name
        assert not path.is_symlink() and path.is_dir(), path
        assert path.stat().st_uid == os.getuid(), path
        assert path.stat().st_mode & 0o777 == 0o755, path
        parents(path / "ownership-check")
        modes[name] = f"{path.stat().st_mode & 0o777:04o}"
    for path in (RECEIPTS, HOME / ".cargo/env"):
        regular(path)
    assert RECEIPTS.stat().st_mode & 0o777 == 0o600
    print("OK managed directories under caller umask 0002: " + json.dumps(modes, sort_keys=True))


def fingerprint():
    receipts = json.loads(RECEIPTS.read_text())
    native_paths = {path for name, entry in receipts.items()
                    if name.startswith("completion:") and entry.get("provider") == "upstream-managed"
                    for path in entry["paths"]}
    return {"receipts": receipts,
            "files": {name: {"sha256": hashlib.sha256((HOME / name).read_bytes()).hexdigest(),
                              "mtime_ns": (HOME / name).stat().st_mtime_ns}
                      for name in CONFIG["dotfiles"]["files"]},
            "backups": sorted(str(p.relative_to(HOME)) for p in (HOME / ".dotfiles-backups").rglob("*")),
            "completions": {p.name: {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "mtime_ns": p.stat().st_mtime_ns}
                            for p in (HOME / ".zfunc").iterdir()},
            "upstream_completions": {path: {"sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                                            "mtime_ns": Path(path).stat().st_mtime_ns}
                                     for path in sorted(native_paths)}}


def unselected_completions():
    """Fresh base installation must not prepare any optional provider."""
    receipts = json.loads(RECEIPTS.read_text())
    for spec in CONFIG["optional_zsh_completions"]:
        for command in spec["commands"]:
            assert "completion:" + command not in receipts, command
            assert not (HOME / ".zfunc" / ("_" + command)).exists(), command
        if spec["provider"] == "upstream-managed":
            assert not (HOME / spec["destination"]).exists(), spec["destination"]
    print("OK unselected optional profiles: no receipts or generated completion artifacts")


def optional_completions():
    """Inspect real package/artifact contents and restored Zsh registration."""
    receipts = json.loads(RECEIPTS.read_text())
    system_arguments, unavailable = [], []
    for spec in CONFIG["optional_zsh_completions"]:
        inventory = {}
        for package in spec.get("packages", []):
            inventory[package] = run("/usr/bin/dpkg-query", "-L", package).splitlines()
            assert inventory[package], package
        if spec.get("artifact") == "ngspice":
            prefix = Path("/opt/ubuntu-bootstrap") / ("ngspice-" + str(CONFIG["ngspice"]["version"]))
            inventory["artifact:ngspice"] = [str(path) for path in prefix.rglob("*") if path.is_file()]
            assert inventory["artifact:ngspice"], prefix
        for command in spec["commands"]:
            entry = receipts["completion:" + command]
            assert entry["provider"] == spec["provider"], (command, entry)
            assert not (HOME / ".zfunc" / ("_" + command)).exists(), command
            if spec["provider"] == "system":
                assert entry["function"] == spec["function"], command
                assert len(entry["paths"]) == 1, entry
                path = Path(next(iter(entry["paths"])))
                assert path.is_file() and path.stat().st_uid == 0 and path.stat().st_size, path
                assert any(str(path) in files for files in inventory.values()), (path, inventory.keys())
                run("/usr/bin/zsh", "-n", str(path))
                system_arguments.extend([command, spec["function"], str(path)])
            elif spec["provider"] == "unavailable":
                assert entry["reason"] and not entry["paths"], entry
                observed = resolve_inventory(receipts, entry)
                assert set(inventory).issubset(observed), (command, observed.keys())
                for key, files in inventory.items():
                    assert set(files) == set(observed[key]), (command, key)
                unavailable.append(command)
            else:
                assert spec["provider"] == "upstream-managed", spec
                path = HOME / spec["destination"]
                assert list(entry["paths"]) == [str(path)], entry
                assert path.is_file() and path.stat().st_uid == os.getuid() and path.stat().st_size, path
                run("/usr/bin/zsh", "-n", str(path))
                binary = HOME / spec["executable"]
                result = subprocess.run([str(binary), *spec["arguments"]], check=True, capture_output=True)
                assert result.stdout == path.read_bytes(), command
    script = '''zmodload zsh/parameter || exit 20
typeset -A loaded
while (( $# )); do
  command=$1; function_name=$2; provider=$3; shift 3
  [[ $_comps[$command] == $function_name ]] || { print -u2 -- "wrong provider: $command"; exit 21; }
  if [[ -z ${loaded[$function_name]} ]]; then
    autoload +X -- $function_name || exit 22
    loaded[$function_name]=yes
  fi
  [[ ${functions_source[$function_name]} == $provider ]] || { print -u2 -- "shadowed provider: $command"; exit 23; }
done
print -- "OK selected system completion registration"
'''
    assert "OK selected system" in run("/usr/bin/zsh", "-lic", script, "test", *system_arguments)
    unavailable_script = '''for command in "$@"; do
  [[ -z $_comps[$command] || $_comps[$command] == _files || $_comps[$command] == _default ]] || {
    print -u2 -- "new provider needs qualification: $command -> $_comps[$command]"; exit 24
  }
done
print -- "OK unavailable completion status agrees with restored Zsh"
'''
    assert "OK unavailable" in run("/usr/bin/zsh", "-lic", unavailable_script, "test", *unavailable)
    # Exercise the official sourced integration in the actual restored shell.
    # Only compadd/_default are intercepted: Juliaup supplies the real channels.
    julia_script = '''[[ $_comps[juliaup] == _juliaup && $_comps[julia] == _julia_channel ]] || exit 25
(( $+functions[_juliaup] && $+functions[_julia_channel] )) || exit 26
typeset -a observed
compadd() { [[ $1 == -a && $2 == channels ]] || return 1; observed=("${channels[@]}"); }
PREFIX=+rel; IPREFIX=''
_julia_channel || exit 27
[[ $PREFIX == rel && $IPREFIX == + && ${observed[(Ie)release]} -gt 0 ]] || exit 28
typeset default_called=no
_default() { default_called=yes; }
PREFIX=ordinary_argument
_julia_channel || exit 29
[[ $default_called == yes ]] || exit 30
print -- "OK Juliaup registration and real julia +channel completion"
'''
    assert "OK Juliaup registration" in run("/usr/bin/zsh", "-lic", julia_script, "test")
    completions()
    print("OK selected optional providers: package-owned aliases, honest unavailable inventory, native Juliaup integration")


def optional_completion_update():
    """Use the real native generator to test atomic failure and stale refresh."""
    from bootstrap_lib import optional_completions as layer
    from bootstrap_lib.runtime import Context
    from bootstrap_lib.platform import BootstrapError
    from types import SimpleNamespace
    spec = next(s for s in CONFIG["optional_zsh_completions"] if s["provider"] == "upstream-managed")
    target = HOME / spec["destination"]
    before = target.read_bytes(), target.stat().st_mtime_ns
    receipts_before = json.loads(RECEIPTS.read_text())
    ctx = Context(CONFIG, SimpleNamespace(non_interactive=True, update=True, adopt=[]),
                  pwd.getpwuid(os.getuid()), HOME, "amd64")
    try:
        layer.provision_upstream(ctx, {**spec, "arguments": ["completions", "invalid-test-shell"]})
    except BootstrapError as error:
        assert "generation failed" in str(error).lower(), error
    else:
        raise AssertionError("Invalid real Juliaup completion generation unexpectedly succeeded")
    assert (target.read_bytes(), target.stat().st_mtime_ns) == before
    assert json.loads(RECEIPTS.read_text()) == receipts_before
    assert not list(target.parent.glob(".bootstrap-*"))
    for command in spec["commands"]:
        ctx.receipts["completion:" + command]["source"]["version"] = "older observed Juliaup version (test fixture)"
    ctx.write_state("receipts.json", ctx.receipts)
    layer.provision_upstream(ctx, spec)
    assert target.read_bytes() == before[0] and target.stat().st_mtime_ns != before[1]
    refreshed = target.stat().st_mtime_ns
    layer.provision_upstream(ctx, spec)
    assert target.stat().st_mtime_ns == refreshed
    optional_completions()
    print("OK real Juliaup failure preserves native script; stale --update refresh and current rerun are atomic/idempotent")


def completions():
    receipts = json.loads(RECEIPTS.read_text())
    directory = HOME / ".zfunc"
    assert directory.is_dir() and directory.stat().st_uid == os.getuid()
    generated = []
    for spec in CONFIG["zsh_completions"]:
        command = spec["command"]
        entry = receipts["completion:" + command]
        path = Path(next(iter(entry["paths"])))
        assert path.is_file() and path.stat().st_size, command
        run("/usr/bin/zsh", "-n", str(path))
        if entry["provider"] == "generated":
            generated.append(command)
            assert path == directory / ("_" + command)
            assert path.stat().st_uid == os.getuid()
            binary = Path(spec["executable"])
            if not binary.is_absolute():
                binary = HOME / binary
            result = subprocess.run([str(binary), *spec["arguments"]], check=True, capture_output=True)
            assert result.stdout == path.read_bytes(), command
        else:
            assert entry["provider"] == "system" and path.stat().st_uid == 0
            assert not (directory / ("_" + command)).exists()
    assert receipts["completion:gh"]["provider"] == "system"
    assert set(p.name for p in directory.iterdir()) == {"_" + name for name in generated}
    for name in ("eza", "zoxide", "nvim", "btm", "hyperfine", "dust"):
        assert not (directory / ("_" + name)).exists()
    script = '''[[ ${fpath[(Ie)$HOME/.zfunc]} -gt 0 ]] || exit 11
for command in "$@"; do
  [[ $_comps[$command] == _$command ]] || { print -u2 -- "missing compinit entry: $command"; exit 12; }
  autoload +X -- _$command || exit 13
done
print -- "OK restored Zsh fpath, compinit registration and completion autoload"
'''
    output = run("/usr/bin/zsh", "-lic", script, "test", *generated, "gh")
    assert "OK restored Zsh" in output
    print("OK completions: user-owned nonempty version-matched generators, system gh, restored fpath/compinit")


def completion_update():
    from bootstrap_lib import completions as layer
    from bootstrap_lib.runtime import Context
    from bootstrap_lib.platform import BootstrapError
    from types import SimpleNamespace
    spec = next(s for s in CONFIG["zsh_completions"] if s["command"] == "fnm")
    target = HOME / ".zfunc/_fnm"
    before = target.read_bytes(), target.stat().st_mtime_ns
    ctx = Context(CONFIG, SimpleNamespace(non_interactive=True, update=False, adopt=[]),
                  pwd.getpwuid(os.getuid()), HOME, "amd64")
    receipt = json.loads(RECEIPTS.read_text())["completion:fnm"]
    try:
        layer.provision_one(ctx, {**spec, "arguments": ["--intentionally-invalid-completion-option"]}, [])
    except BootstrapError as error:
        assert "generation failed" in str(error), error
    else:
        raise AssertionError("Invalid real fnm generation unexpectedly succeeded")
    assert (target.read_bytes(), target.stat().st_mtime_ns) == before
    assert json.loads(RECEIPTS.read_text())["completion:fnm"] == receipt
    assert not list((HOME / ".zfunc").glob(".bootstrap-*"))
    # A stale observation simulates a completion left over from a prior version.
    # The actual application-version change is exercised by the offline unit fixture.
    receipts = json.loads(RECEIPTS.read_text())
    receipts["completion:fnm"]["source"]["version"] = "older observed fnm version (test fixture)"
    RECEIPTS.write_text(json.dumps(receipts))
    others = {p.name: p.stat().st_mtime_ns for p in (HOME / ".zfunc").iterdir() if p != target}
    run(BOOTSTRAP, "--non-interactive", "--no-change-shell", "--update")
    assert target.stat().st_mtime_ns != before[1]
    after = json.loads(RECEIPTS.read_text())
    for filename, mtime in others.items():
        key = "completion:" + filename[1:]
        if receipts[key]["source"] == after[key].get("source"):
            assert (HOME / ".zfunc" / filename).stat().st_mtime_ns == mtime
    completions()
    print("OK real generator failure preserves working file; --update regenerates stale fnm and preserves current completions")


def base():
    assert os.geteuid() != 0
    assert pwd.getpwnam("engineer").pw_shell == "/bin/bash"
    for binary in ["gh", "zsh", "wl-copy", "wl-paste"]:
        assert Path("/usr/bin", binary).is_file()
    for tool in ["rustup", "cargo", "rustc", "cargo-binstall", *[b for t in CONFIG["cargo_tools"] for b in t["bins"]]]:
        path = HOME / ".cargo/bin" / tool
        assert path.stat().st_uid == os.getuid(), tool
        run(str(path), "-V" if tool == "cargo-binstall" else "--version")
    assert (HOME / ".cargo/bin/uv").stat().st_uid == os.getuid()
    assert (HOME / ".local/bin/python").stat().st_uid == os.getuid()
    run(str(HOME / ".local/bin/python"), "--version")
    run(str(HOME / ".cargo/bin/fnm"), "exec", "--using", "default", "node", "--version")
    run("sha256sum", "--check", str(HOME / "excluded.sha256"))
    root = HOME / ".local/share/ubuntu-bootstrap/dotfiles" / CONFIG["dotfiles"]["revision"]
    assert run("git", "-C", str(root), "rev-parse", "HEAD") == CONFIG["dotfiles"]["revision"]
    from dotfiles_shell_checks import check_shell_contract
    check_shell_contract(root)
    for name in CONFIG["dotfiles"]["files"]:
        assert (HOME / name).read_bytes() == (root / "home" / name).read_bytes(), name
    from bootstrap_lib.config import restore_args
    with tempfile.TemporaryDirectory() as directory:
        command = restore_args(CONFIG, apply=True)
        command[2] = str(root / "scripts/restore.py")
        run(*command, "--target", directory)
        for name in CONFIG["dotfiles"]["files"]:
            assert (Path(directory) / name).read_bytes() == (root / "home" / name).read_bytes()
        for name in (".bashrc", ".profile", ".config/zellij/config.kdl", ".config/mermaid/pptr.json"):
            assert not (Path(directory) / name).exists()
    assert list((HOME / ".dotfiles-backups").glob("*/.zshrc"))
    assert "build" in resolve(CONFIG, ["ngspice"])
    assert "build" not in resolve(CONFIG, ["openmodelica"])
    plugins = json.loads((root / "scripts/zsh-plugins.json").read_text())
    for name, spec in plugins.items():
        checkout = HOME / ".local/share/zsh/plugins" / name
        assert run("git", "-C", str(checkout), "rev-parse", "HEAD") == spec["revision"]
    report = run("/usr/bin/python3", "-B", str(root / "scripts/check_dependencies.py"))
    assert "MISSING: zellij" in report
    run("/usr/bin/zsh", "-lic", "command -v cargo; command -v uv; command -v node; command -v delta")
    cargo_ownership(False)
    log = (STATE / "bootstrap.log").read_text()
    assert "sh.rustup.rs" not in log and "astral.sh/uv/install.sh" not in log and "install.julialang.org" not in log
    init = log.index("--default-toolchain none")
    self_update = log.index("rustup self update", init)
    stable = log.index("rustup toolchain install stable", self_update)
    assert init < self_update < stable
    cargo_resolution_policy(log)
    completions()
    print("OK base: real installers, ownership, exact selective restore, pinned plugins, excluded files, No shell path")


def cargo_resolution_policy(log):
    import shlex
    versions = {}
    attempts = 0
    for line in log.splitlines():
        if not line.startswith((f"$ {HOME}/.cargo/bin/cargo-binstall ", f"$ {HOME}/.cargo/bin/cargo ")):
            continue
        args = shlex.split(line[2:])
        if args[0] == str(HOME / ".cargo/bin/cargo-binstall") and "--strategies" in args:
            assert args[args.index("--strategies") + 1] == "crate-meta-data"
            assert "--no-discover-github-token" in args
            assert "--json-output" in args and "--log-level" in args
            assert args[args.index("--maximum-resolution-timeout") + 1] == "15"
            version = args[args.index("--version") + 1]
            assert re.fullmatch(r"=\d+\.\d+\.\d+", version)
            versions[args[-1]] = version[1:]
            attempts += 1
        elif args[:2] == [str(HOME / ".cargo/bin/cargo"), "install"] and "--path" not in args:
            assert "--locked" in args
            assert args[args.index("--version") + 1] == versions[args[-1]]
    assert attempts
    assert "bootstrap: binary installed; binary attempt elapsed" in log
    print(f"OK {attempts} real binary attempts: no credential discovery, exact versions and controlled fallback policy")


def prompt(answer):
    master, slave = pty.openpty()
    process = subprocess.Popen([BOOTSTRAP, "--build"], stdin=slave, stdout=slave, stderr=slave,
                               env={**os.environ, "CI": "1"})
    os.close(slave)
    output = b""
    sent = False
    deadline = time.monotonic() + 600
    try:
        while process.poll() is None and time.monotonic() < deadline:
            if select.select([master], [], [], 1)[0]:
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    break
                output += chunk
                if not sent and b"Change your default shell to Zsh? [Y/n]" in output:
                    os.write(master, (answer + "\n").encode())
                    sent = True
        if process.poll() is None:
            process.terminate()
        code = process.wait(timeout=30)
        assert sent and code == 0, output.decode(errors="replace")
        return output.decode(errors="replace")
    finally:
        os.close(master)
        if process.poll() is None:
            process.kill()
            process.wait()


def prompts():
    root_shell = pwd.getpwnam("root").pw_shell
    no = prompt("n")
    assert pwd.getpwnam("engineer").pw_shell == "/bin/bash"
    assert "later: chsh" in no
    yes = prompt("")
    assert pwd.getpwnam("engineer").pw_shell == "/usr/bin/zsh"
    assert pwd.getpwnam("root").pw_shell == root_shell
    assert "FOUND   login shell" in prompt("y")
    print("OK interactive default-Yes and No prompts; no CI exec; root shell unchanged")


def failures():
    root = HOME / ".local/share/ubuntu-bootstrap/dotfiles" / CONFIG["dotfiles"]["revision"]
    dirty = root / "unexpected-file"
    dirty.write_text("integration dirty-checkout fixture")
    try:
        result = subprocess.run([BOOTSTRAP, "--non-interactive", "--no-change-shell"], capture_output=True, text=True)
        assert result.returncode != 0 and "dirty checkout" in result.stdout
    finally:
        dirty.unlink()
    # Actual symlink conflict must fail before restoration touches any selected file.
    config = HOME / ".config"
    preserved = HOME / ".config.integration-preserved"
    config.rename(preserved)
    config.symlink_to(preserved)
    before = {f: (HOME / f).read_bytes() for f in CONFIG["dotfiles"]["files"]}
    try:
        result = subprocess.run([BOOTSTRAP, "--non-interactive", "--no-change-shell"], capture_output=True, text=True)
        assert result.returncode != 0 and "symlink" in result.stdout
        assert before == {f: (HOME / f).read_bytes() for f in CONFIG["dotfiles"]["files"]}
    finally:
        config.unlink()
        preserved.rename(config)
    run(BOOTSTRAP, "--non-interactive", "--no-change-shell")
    # Unmanaged user tool is never adopted or overwritten; receipt deletion is recoverable explicitly.
    receipts = json.loads(RECEIPTS.read_text())
    entry = receipts.pop("eza")
    binary = HOME / ".cargo/bin/eza"
    before_hash = hashlib.sha256(binary.read_bytes()).hexdigest()
    RECEIPTS.write_text(json.dumps(receipts))
    result = subprocess.run([BOOTSTRAP, "--non-interactive", "--no-change-shell"], capture_output=True, text=True)
    assert result.returncode != 0 and "Unmanaged eza" in result.stdout
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == before_hash
    run(BOOTSTRAP, "--non-interactive", "--no-change-shell", "--adopt", "eza")
    # Requested optional failure must return failure while the installed base stays usable.
    source = Path("/etc/apt/sources.list.d/ubuntu-bootstrap-openmodelica.list")
    assert not source.exists()
    with tempfile.TemporaryDirectory() as directory:
        fixture = Path(directory) / "conflicting.list"
        fixture.write_text("integration conflict fixture\n")
        run("sudo", "install", "-m", "0644", str(fixture), str(source))
        try:
            result = subprocess.run([BOOTSTRAP, "--non-interactive", "--no-change-shell", "--openmodelica"], capture_output=True, text=True)
            assert result.returncode != 0 and "Conflicting managed OpenModelica" in result.stdout
            assert json.loads((STATE / "last-run.json").read_text())["failed"] == ["openmodelica"]
            run(str(HOME / ".cargo/bin/cargo"), "--version")
        finally:
            run("sudo", "rm", "--", str(source))
    print("OK dirty-checkout, symlink and unmanaged ownership failures; real rerun recovery")


def engineering():
    from dotfiles_shell_checks import check_shell_contract
    check_shell_contract(HOME / ".local/share/ubuntu-bootstrap/dotfiles" / CONFIG["dotfiles"]["revision"])
    for package in CONFIG["apt"]["build"]:
        assert run("dpkg-query", "-W", "-f=${Status}", package) == "install ok installed"
    assert "ngspice-47" in run("/usr/local/bin/ngspice", "--version")
    with tempfile.TemporaryDirectory() as directory:
        circuit = Path(directory) / "divider.cir"
        circuit.write_text("Voltage divider\nV1 in 0 10\nR1 in out 1k\nR2 out 0 1k\n.control\nop\nprint v(out)\nquit\n.endc\n.end\n")
        output = run("/usr/local/bin/ngspice", "-b", str(circuit))
        assert "5.000000" in output, output
        model = Path(directory) / "smoke.mos"
        model.write_text('loadString("model BootstrapSmoke Real x(start=1); equation der(x)=-x; end BootstrapSmoke;");\nsimulate(BootstrapSmoke, stopTime=0.1);\ngetErrorString();\n')
        output = run("/usr/bin/omc", str(model), cwd=directory)
        assert "Simulation execution failed" not in output and "resultFile = \"\"" not in output, output
    for package in ("omedit", "omplot", "openmodelica"):
        result = subprocess.run(["dpkg-query", "-W", "-f=${Status}", package], capture_output=True, text=True)
        assert result.stdout != "install ok installed", package
    run("/opt/nvim-linux-x86_64/bin/nvim", "--headless", "-u", "NONE", "+quit")
    run("/usr/bin/vim", "--version")
    run("/usr/bin/emacs", "--batch", "-Q", "--eval", "(princ (+ 1 1))")
    assert run(str(HOME / ".cargo/bin/julia"), "-e", "print(1+1)") == "2"
    cargo_ownership(True)
    inventory_size()
    optional_completions()
    optional_completion_update()
    print("OK build, ngspice numerical smoke, GUI-free OpenModelica simulation, all editors, Julia")


def unrelated():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "src").mkdir()
        (root / "Cargo.toml").write_text('[package]\nname="unrelated-user-tool"\nversion="0.1.0"\nedition="2021"\n')
        (root / "src/main.rs").write_text('fn main() { println!("unrelated-user-tool 0.1.0"); }\n')
        run(str(HOME / ".cargo/bin/cargo"), "install", "--path", str(root))
    binary = HOME / ".cargo/bin/unrelated-user-tool"
    (HOME / "unrelated.sha256").write_text(hashlib.sha256(binary.read_bytes()).hexdigest())
    print("OK installed unrelated Cargo fixture to test update ownership")


def update():
    binary = HOME / ".cargo/bin/unrelated-user-tool"
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == (HOME / "unrelated.sha256").read_text()
    assert run(str(binary)) == "unrelated-user-tool 0.1.0"
    assert "unrelated-user-tool" not in json.loads(RECEIPTS.read_text())
    run("sha256sum", "--check", str(HOME / "excluded.sha256"))
    cargo_ownership(True)
    optional_completions()
    print("OK --update left unrelated Cargo application and excluded/personal configs untouched")


def cargo_ownership(with_julia):
    from bootstrap_lib.rust import crate_state, executable_version
    from bootstrap_lib.runtime import Context
    from types import SimpleNamespace
    receipts = json.loads(RECEIPTS.read_text())
    ctx = Context(CONFIG, SimpleNamespace(non_interactive=True, update=False, adopt=[]),
                  pwd.getpwuid(os.getuid()), HOME, "amd64")
    for profile in (["python", "julia"] if with_julia else ["python"]):
        tool = CONFIG[profile]["cargo"]
        receipt = receipts[tool["crate"]]
        assert receipt["manager"] == "cargo" and receipt["crate"] == tool["crate"]
        assert receipt["version"] == crate_state(ctx, tool)
        for name in tool["bins"]:
            expected = HOME / ".cargo/bin" / name
            assert str(expected) in receipt["paths"], receipt
            assert run("/usr/bin/zsh", "-lic", 'whence -p -- "$1"', "test", name) == str(expected)
            assert expected.stat().st_uid == os.getuid()
        for name in tool.get("version_bins", tool["bins"]):
            assert executable_version(run(str(HOME / ".cargo/bin" / name), "--version")) == receipt["version"]
    print("OK Cargo ownership, registry versions and real login-shell command resolution")


def inventory_size():
    from bootstrap_lib.inventories import normalize
    from bootstrap_lib.durability import json_bytes
    receipts = json.loads(RECEIPTS.read_text())
    snapshots = receipts[SECTION]["snapshots"]
    inline = {k: dict(v) for k, v in receipts.items() if k != SECTION}
    count = 0
    for name, entry in inline.items():
        if "inventory_ref" in entry:
            entry["inventory"] = resolve_inventory(receipts, entry)
            del entry["inventory_ref"]
            count += 1
    before, after = len(json_bytes(inline)), len(json_bytes(receipts))
    assert after < before * 0.5, (before, after)
    assert normalize(receipts) == receipts
    evidence = {"inline_bytes": before, "deduplicated_bytes": after,
                "referencing_commands": count, "unique_snapshots": len(snapshots),
                "reduction_percent": round(100 * (1 - after / before), 2)}
    (HOME / "inventory-size.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print("OK measured completion inventories: " + json.dumps(evidence))


def legacy_migration():
    """Verified equivalent baseline layout, not historical shell installers.

    Use real official release artifacts and the baseline manager/receipt shapes,
    while retaining existing working Python and Julia installations. Only the
    two Cargo crates owned by this isolated test user are uninstalled first.
    """
    from bootstrap_lib.runtime import Context, release, extract
    from types import SimpleNamespace
    import shutil
    ctx = Context(CONFIG, SimpleNamespace(non_interactive=True, update=False, adopt=[]),
                  pwd.getpwuid(os.getuid()), HOME, "amd64")
    python_before = run(str(HOME / ".local/bin/python"), "--version")
    julia_before = run(str(HOME / ".cargo/bin/julia"), "-e", "print(VERSION)")
    julia_config = HOME / ".julia/juliaup/juliaup.json"
    channel_before = json.loads(julia_config.read_text())
    for profile, repo, asset, parent in (
        ("python", "astral-sh/uv", "uv-x86_64-unknown-linux-gnu.tar.gz", HOME / ".local/bin"),
        ("julia", "JuliaLang/juliaup", None, HOME / ".juliaup/bin")):
        version = ctx.receipts[CONFIG[profile]["cargo"]["crate"]]["version"]
        asset = asset or f"juliaup-{version}-x86_64-unknown-linux-musl-portable.tar.gz"
        # This qualification uses current stable matching official assets. The
        # release API supplies its official SHA-256; no artifact is executed
        # before the same production integrity/extraction checks have passed.
        tag, url, checksum = release(repo, asset)
        archive = ctx.download(url, checksum, "legacy-" + asset)
        with tempfile.TemporaryDirectory(dir=ctx.cache) as tmp:
            extract(archive, tmp)
            source = Path(tmp) / ("uv-x86_64-unknown-linux-gnu" if profile == "python" else "")
            run(str(HOME / ".cargo/bin/cargo"), "uninstall", CONFIG[profile]["cargo"]["crate"])
            parent.mkdir(parents=True, exist_ok=True)
            for name in CONFIG[profile]["cargo"]["bins"]:
                shutil.copy2(source / name, parent / name)
                (parent / name).chmod(0o755)
        if profile == "julia":
            (parent / "julia").rename(parent / "julialauncher")
            (parent / "julia").symlink_to(parent / "julialauncher")
            ctx.receipts.pop("juliaup")
            ctx.record("julia", [parent / "juliaup", parent / "julia"], manager="juliaup", channel="release")
        else:
            ctx.record("uv", [parent / "uv", parent / "uvx"], manager="uv")
    run(str(HOME / ".local/bin/uv"), "--version")
    assert run(str(HOME / ".juliaup/bin/julia"), "-e", "print(VERSION)") == julia_before
    # Legacy PATH is fixture input, not a responsibility of the new dotfiles.
    legacy_env = {**ctx.env, "HOME": str(HOME), "ZDOTDIR": str(HOME),
                  "PATH": f"{HOME}/.local/bin:{HOME}/.juliaup/bin:/usr/bin:/bin"}
    assert run("/usr/bin/zsh", "-lic", "whence -p uv", env=legacy_env) == str(HOME / ".local/bin/uv")
    assert run("/usr/bin/zsh", "-lic", "whence -p julia", env=legacy_env) == str(HOME / ".juliaup/bin/julia")
    run(BOOTSTRAP, "--non-interactive", "--no-change-shell", "--build", "--ngspice", "--openmodelica", "--vim", "--nvim", "--emacs", "--julia")
    cargo_ownership(True)
    for path in (".local/bin/uv", ".local/bin/uvx", ".juliaup/bin/juliaup", ".juliaup/bin/julia"):
        assert not (HOME / path).exists() and not (HOME / path).is_symlink(), path
    assert (HOME / ".juliaup/bin/julialauncher").exists(), "unreceipted launcher target must be preserved"
    assert run(str(HOME / ".local/bin/python"), "--version") == python_before
    assert run(str(HOME / ".cargo/bin/julia"), "-e", "print(VERSION)") == julia_before
    assert json.loads(julia_config.read_text()) == channel_before
    assert not (STATE / "transaction").exists()
    optional_completions()
    print("OK equivalent verified legacy migration, preserved runtimes/channels and retired PATH shadows")


def recovery_regressions():
    # Run real filesystem/subprocess recovery cases inside the qualified Linux
    # container too, without altering the integration user's active receipts.
    run("/usr/bin/python3", "-B", "-m", "unittest", "discover", "-s", "/workspace/tests", "-p", "test_maintenance.py", "-v")
    assert not (STATE / "transaction").exists()
    print("OK deterministic publication and migration recovery regressions in Ubuntu")


def cargo_retry_regressions():
    run("/usr/bin/python3", "-B", "-m", "unittest", "discover", "-s", "/workspace/tests", "-p", "test_cargo_binary.py", "-v")
    cargo_resolution_policy((STATE / "bootstrap.log").read_text())
    print("OK deterministic quota/network/integrity, process cleanup and exact-version fallback regressions in Ubuntu")


def main():
    action = sys.argv[1]
    if action == "snapshot":
        (HOME / "bootstrap-snapshot.json").write_text(json.dumps(fingerprint(), sort_keys=True))
    elif action == "repeat":
        assert json.loads((HOME / "bootstrap-snapshot.json").read_text()) == fingerprint(), "Idempotency changed files, receipts, or backups"
        print("OK second pass: unchanged versions, config mtimes, receipts and backup inventory")
    else:
        globals()[action]()


if __name__ == "__main__":
    main()
