"""Assertions inside the normal Ubuntu integration user's isolated HOME."""
import hashlib
import json
import os
from pathlib import Path
import pty
import pwd
import select
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap_lib.config import load_manifest, resolve

HOME = Path.home()
CONFIG = load_manifest()
STATE = HOME / ".local/state/ubuntu-bootstrap"
RECEIPTS = STATE / "receipts.json"
BOOTSTRAP = "/workspace/bootstrap"


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, capture_output=True, **kwargs).stdout.strip()


def fingerprint():
    return {"receipts": json.loads(RECEIPTS.read_text()),
            "files": {name: {"sha256": hashlib.sha256((HOME / name).read_bytes()).hexdigest(),
                              "mtime_ns": (HOME / name).stat().st_mtime_ns}
                      for name in CONFIG["dotfiles"]["files"]},
            "backups": sorted(str(p.relative_to(HOME)) for p in (HOME / ".dotfiles-backups").rglob("*")),
            "completions": {p.name: {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "mtime_ns": p.stat().st_mtime_ns}
                            for p in (HOME / ".zfunc").iterdir()}}


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
    assert (HOME / ".local/bin/uv").stat().st_uid == os.getuid()
    assert (HOME / ".local/bin/python").stat().st_uid == os.getuid()
    run(str(HOME / ".local/bin/python"), "--version")
    run(str(HOME / ".cargo/bin/fnm"), "exec", "--using", "default", "node", "--version")
    run("sha256sum", "--check", str(HOME / "excluded.sha256"))
    root = HOME / ".local/share/ubuntu-bootstrap/dotfiles" / CONFIG["dotfiles"]["revision"]
    assert run("git", "-C", str(root), "rev-parse", "HEAD") == CONFIG["dotfiles"]["revision"]
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
    completions()
    print("OK base: real installers, ownership, exact selective restore, pinned plugins, excluded files, No shell path")


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
    assert run(str(HOME / ".juliaup/bin/julia"), "-e", "print(1+1)") == "2"
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
    print("OK --update left unrelated Cargo application and excluded/personal configs untouched")


action = sys.argv[1]
if action == "snapshot":
    (HOME / "bootstrap-snapshot.json").write_text(json.dumps(fingerprint(), sort_keys=True))
elif action == "repeat":
    assert json.loads((HOME / "bootstrap-snapshot.json").read_text()) == fingerprint(), "Idempotency changed files, receipts, or backups"
    print("OK second pass: unchanged versions, config mtimes, receipts and backup inventory")
else:
    globals()[action]()
