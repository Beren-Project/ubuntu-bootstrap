"""Provision version-matched Zsh completions without executing generators as root."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

from .platform import BootstrapError
from .runtime import digest, safe_directory


def normal_user(ctx):
    if os.geteuid() == 0 or os.getuid() != ctx.user.pw_uid or os.geteuid() != ctx.user.pw_uid:
        raise BootstrapError("Completion provisioning must run as the original normal user, never root")


def executable(ctx, value):
    path = Path(value)
    return path if path.is_absolute() else ctx.home / path


def validate(ctx, path, command):
    lines = path.read_text().splitlines()
    if not lines or command not in lines[0].removeprefix("#compdef ").split() or not lines[0].startswith("#compdef "):
        raise BootstrapError(f"Invalid/empty Zsh completion for {command}: expected #compdef {command}")
    if not any(line.strip() and not line.lstrip().startswith("#") for line in lines[1:]):
        raise BootstrapError(f"Incomplete Zsh completion for {command}: no autoload code")
    ctx.run(["/usr/bin/zsh", "-n", path])


def system_completion(ctx, command, fpath):
    for directory in fpath:
        directory = Path(directory)
        if not directory.is_absolute() or not directory.resolve().is_relative_to("/usr"):
            continue
        path = directory / ("_" + command)
        if (path.is_file() and path.stat().st_uid == 0 and directory.stat().st_uid == 0
                and not (path.stat().st_mode | directory.stat().st_mode) & 0o022):
            validate(ctx, path, command)
            return path
    return None


def completion_directory(ctx):
    path = ctx.home / ".zfunc"
    existing = path.exists() or path.is_symlink()
    directory = safe_directory(path)
    if not existing:
        directory.chmod(0o755)  # newly generated state must be safe even with a permissive umask
    if directory.stat().st_mode & 0o022:
        raise BootstrapError(f"Completion directory is writable by group/others; Zsh would ignore it: {directory}")
    return directory


def provision_one(ctx, spec, fpath):
    normal_user(ctx)
    command = spec["command"]
    name = "completion:" + command
    destination = ctx.home / ".zfunc" / ("_" + command)
    if destination.parent.exists() or destination.parent.is_symlink():
        completion_directory(ctx)
    receipt = ctx.receipts.get(name)
    exists = destination.exists() or destination.is_symlink()
    if exists:
        if destination.is_symlink() or not destination.is_file() or destination.stat().st_uid != ctx.user.pw_uid:
            raise BootstrapError(f"Refusing non-user-owned regular completion: {destination}")
        if not receipt or receipt.get("provider") != "generated" or receipt.get("paths", {}).get(str(destination)) != digest(destination):
            raise BootstrapError(f"Unmanaged or externally changed completion preserved: {destination}; inspect it before retrying")
    system = system_completion(ctx, command, fpath)
    if system:
        if exists:
            destination.unlink()  # only an unchanged, receipt-verified generated artifact
        ctx.record(name, [system], provider="system")
        ctx.status("FOUND", "completion " + command, f"system: {system}")
        return
    binary = executable(ctx, spec["executable"])
    version_binary = executable(ctx, spec.get("version_executable", spec["executable"]))
    if spec["owner"] != "apt":
        if spec["owner"] not in ctx.receipts:
            ctx.status("SKIP", "completion " + command, "tool not managed/selected on this architecture")
            return
        if not ctx.owned(spec["owner"], list(dict.fromkeys([binary, version_binary]))):
            raise BootstrapError(f"Managed completion generator is missing: {binary}")
    source = {"executable": str(binary), "sha256": digest(binary),
              "version": ctx.output([version_binary, "--version"]), "arguments": spec["arguments"]}
    if exists and receipt.get("source") == source:
        validate(ctx, destination, command)
        ctx.status("FOUND", "completion " + command)
        return
    directory = completion_directory(ctx)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".bootstrap-", dir=directory, delete=False) as stream:
            temporary = Path(stream.name)
            argv = list(map(str, [binary, *spec["arguments"]]))
            normal_user(ctx)
            with ctx.log_path.open("a") as log:
                log.write("\n$ " + shlex.join(argv) + "\n")
                log.flush()
                result = subprocess.run(argv, env=ctx.env, cwd=ctx.cache, stdin=subprocess.DEVNULL,
                                        stdout=stream, stderr=log, timeout=60)
            if result.returncode:
                raise BootstrapError(f"Completion generation failed for {command} (exit {result.returncode}); existing file preserved. See {ctx.log_path}")
        validate(ctx, temporary, command)
        temporary.chmod(0o644)
        temporary.replace(destination)
    except subprocess.TimeoutExpired as error:
        raise BootstrapError(f"Completion generation timed out for {command}; existing file preserved") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    ctx.record(name, [destination], provider="generated", source=source)
    ctx.status("UPDATE" if exists else "INSTALL", "completion " + command)


def provision(ctx, profile):
    normal_user(ctx)
    from . import optional_completions
    optional_completions.provision(ctx, profile)
    specs = [spec for spec in ctx.config["zsh_completions"] if spec["profile"] == profile]
    if not specs:
        return
    fpath = ctx.output(["/usr/bin/zsh", "-fc", "print -rl -- $fpath"]).splitlines()
    errors = []
    for spec in specs:
        try:
            provision_one(ctx, spec, fpath)
        except (BootstrapError, OSError, ValueError) as error:
            errors.append(f"{spec['command']}: {error}")
    if errors:
        raise BootstrapError("; ".join(errors))
