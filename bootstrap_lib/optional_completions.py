"""Selected optional providers: package-owned autoloads and native integrations.

Keep native sourced scripts separate from the base #compdef autoload contract.
The manifest defines providers; receipts only record verified observations.
"""
from pathlib import Path
import shlex
import subprocess
import tempfile

from .completions import normal_user, validate
from .platform import BootstrapError
from .runtime import digest, safe_directory
from .durability import RecoveryError, Transaction
from .inventories import normalize


def zsh_probe(ctx, commands, *, load=False, expected=None, sourced=None):
    """Observe restored startup, without repairing its completion registration."""
    normal_user(ctx)
    arguments = list(commands)
    script = 'selected_commands=("$@")\n'
    if load:
        if expected is None or set(expected) != set(commands):
            raise BootstrapError("Provider loading requires the previously verified command/path selection")
        arguments = [str(value) for command in commands for value in (command, *expected[command])]
        script = r'''
typeset -a selected_commands
typeset -A wanted_functions wanted_sources
while (( $# )); do
  selected_commands+=("$1")
  wanted_functions[$1]=$2
  wanted_sources[$2]=$3
  shift 3
done
'''
    script += r'''
(( ${+_comps} )) || { print -u2 -- 'Restored Zsh did not initialize compinit'; exit 1; }
print -rl -- ${fpath/#/BOOTSTRAP-FPATH\t}
for command in "${selected_commands[@]}"; do
  print -r -- "BOOTSTRAP-COMP\t${command}\t${_comps[$command]}"
done
'''.replace("\\t", "\t")
    if load:
        script += r'''
zmodload zsh/parameter || exit 4
typeset -A loaded
for command in "${selected_commands[@]}"; do
  function_name=${_comps[$command]}
  [[ $function_name == ${wanted_functions[$command]} ]] || exit 2
  if [[ -z ${loaded[$function_name]} ]]; then
    first_provider=''
    for directory in "${fpath[@]}"; do
      if [[ -e "$directory/$function_name" || -L "$directory/$function_name" ]]; then
        first_provider="$directory/$function_name"
        break
      fi
    done
    [[ $first_provider == ${wanted_sources[$function_name]} ]] || {
      print -u2 -- "Completion provider changed before load: $function_name -> $first_provider"
      exit 5
    }
    autoload +X "$function_name" || (( $+functions[$function_name] )) || exit 3
    print -r -- "BOOTSTRAP-SOURCE\t${function_name}\t${functions_source[$function_name]}"
    loaded[$function_name]=yes
  fi
done
'''.replace("\\t", "\t")
    elif sourced:
        script += r'''
zmodload zsh/parameter || exit 4
for command in "${selected_commands[@]}"; do
  function_name=${_comps[$command]}
  print -r -- "BOOTSTRAP-SOURCE\t${function_name}\t${functions_source[$function_name]}"
done
'''.replace("\\t", "\t")
    output = ctx.output(["/usr/bin/zsh", "-lic", script, "bootstrap-completions", *arguments], cwd=ctx.cache)
    fpath, registrations, sources = [], {}, {}
    for line in output.splitlines():
        if line.startswith("BOOTSTRAP-FPATH\t"):
            fpath.append(Path(line.split("\t", 1)[1]))
        elif line.startswith("BOOTSTRAP-COMP\t"):
            _, command, function = (line + "\t").split("\t", 2)
            function = function.rstrip("\t")
            registrations[command] = function
        elif line.startswith("BOOTSTRAP-SOURCE\t"):
            _, function, source = (line + "\t").split("\t", 2)
            sources[function] = source.rstrip("\t")
    if set(registrations) != set(commands) or not fpath:
        raise BootstrapError("Zsh completion probe did not return its registration/fpath contract")
    if load or sourced:
        for function in set(registrations.values()):
            wanted = sourced if sourced else next(path for name, path in expected.values() if name == function)
            if sources.get(function) != str(wanted):
                raise BootstrapError(f"Zsh loaded a personal/shadowed {function}: {sources.get(function)}; expected {wanted}; existing configuration preserved")
    return fpath, registrations


def trusted_system(path):
    """No user shadowing, writable parents or non-root package providers."""
    if not path.is_absolute() or not path.resolve().is_relative_to("/usr") or not path.is_file():
        return False
    resolved = path.resolve()
    for part in (path, *path.parents, resolved, *resolved.parents):
        if part.stat().st_uid != 0 or part.stat().st_mode & 0o022:
            return False
    return True


def inventory(ctx, spec):
    contents = {package: ctx.output(["/usr/bin/dpkg-query", "-L", package]).splitlines()
                for package in spec["packages"]}
    if spec.get("artifact") == "ngspice":
        root = Path("/opt/ubuntu-bootstrap") / ("ngspice-" + ctx.config["ngspice"]["version"])
        if not root.is_dir():
            raise BootstrapError(f"Installed ngspice artifact is missing: {root}")
        contents["artifact:ngspice"] = sorted(str(path) for path in root.rglob("*") if path.is_file())
    return contents


def system_path(function, fpath):
    # First match controls autoload: never silently bypass a personal shadow.
    for directory in fpath:
        path = directory / function
        if path.exists() or path.is_symlink():
            return path
    return None


def provision_system(ctx, spec):
    normal_user(ctx)
    contents = inventory(ctx, spec)
    fpath, registrations = zsh_probe(ctx, spec["commands"])
    package_files = {path for paths in contents.values() for path in paths}
    providers = {}
    for command in spec["commands"]:
        function = registrations[command]
        generic = function in ("_files", "_default", "_gnu_generic")
        path = system_path(function, fpath) if function.startswith("_") and not generic else None
        if spec["provider"] == "system" and function != spec["function"]:
            raise BootstrapError(f"Expected {spec['function']} registration for {command}, found {function or 'none'}; personal providers preserved")
        if path and str(path) in package_files and trusted_system(path):
            validate(ctx, path, command)
            providers[command] = (function, path)
        elif spec["provider"] == "system":
            raise BootstrapError(f"Expected trusted package-owned {function} provider for {command}; found {path}; no user copy created")
    if providers:
        # Only load after ownership, package contents and syntax were checked.
        zsh_probe(ctx, list(providers), load=True, expected=providers)
    for command in spec["commands"]:
        if command in providers:
            function, path = providers[command]
            ctx.record("completion:" + command, [path], provider="system", function=function, inventory=contents)
            ctx.status("VERIFY", "completion " + command, f"system {function}: {path}")
        else:
            reason = spec["reason"]
            ctx.record("completion:" + command, provider="unavailable", reason=reason, inventory=contents)
            ctx.status("SKIP", "completion " + command, "unavailable: " + reason)


def validate_native(ctx, path):
    """Juliaup emits a sourced script, including its native +channel handler."""
    if not path.stat().st_size:
        raise BootstrapError("Empty Juliaup native completion script; existing file preserved")
    ctx.run(["/usr/bin/zsh", "-n", path])
    ctx.run(["/usr/bin/zsh", "-fc", r'''
autoload -Uz compinit
compinit -i -d /dev/null -D || exit 1
source "$1" || exit 2
[[ $_comps[juliaup] == _juliaup && $_comps[julia] == _julia_channel ]] || exit 3
[[ $+functions[_juliaup] == 1 && $+functions[_julia_channel] == 1 ]] || exit 4
expected_channel=$2
# Exercise the official handler outside a terminal's completion widget. Only
# compadd is captured: the candidate list still comes from installed Juliaup.
compadd() { [[ "$1" == -a && "$2" == channels && ${channels[(Ie)$expected_channel]} -gt 0 ]]; }
PREFIX="+$expected_channel" IPREFIX=''
_julia_channel || exit 5
[[ $PREFIX == $expected_channel && $IPREFIX == + ]] || exit 6
''', "bootstrap-native-completion", path, ctx.config["julia"]["channel"]], cwd=ctx.cache)


def native_directory(ctx, path):
    """Validate existing parents; secure only directories this call creates."""
    def validate_parents():
        for parent in (path, *path.parents):
            if parent == ctx.home.parent:
                break
            if parent.is_symlink():
                raise BootstrapError(f"Refusing symlinked Juliaup completion parent: {parent}")
            if parent.exists() and (not parent.is_dir() or parent.stat().st_uid != ctx.user.pw_uid
                                    or parent.stat().st_mode & 0o022):
                raise BootstrapError(f"Insecure Juliaup completion parent: {parent}")
    validate_parents()
    directory = safe_directory(path)
    # Keep the native provider's stricter rules for concurrent creators too.
    validate_parents()
    return directory


def native_receipts(ctx, spec, destination, source, checksum):
    proposed = dict(ctx.receipts)
    for command, function in zip(spec["commands"], spec["functions"]):
        proposed["completion:" + command] = {"paths": {str(destination): checksum},
            "provider": "upstream-managed", "function": function, "source": source}
    return normalize(proposed)


def record_native(ctx, spec, destination, source):
    proposed = native_receipts(ctx, spec, destination, source, digest(destination))
    if proposed != ctx.receipts:
        ctx.write_state("receipts.json", proposed)
        ctx.receipts = proposed


def provision_upstream(ctx, spec):
    normal_user(ctx)
    from .julia import validate_depot
    validate_depot(ctx)
    binary = ctx.home / spec["executable"]
    if spec["owner"] not in ctx.receipts:
        raise BootstrapError("Juliaup completion requires the selected, bootstrap-managed Julia installation")
    if not ctx.owned(spec["owner"], [binary]):
        raise BootstrapError(f"Juliaup completion generator is missing: {binary}")
    destination = ctx.home / spec["destination"]
    exists = destination.exists() or destination.is_symlink()
    receipt = ctx.receipts.get("completion:juliaup")
    if exists:
        if destination.is_symlink() or not destination.is_file() or destination.stat().st_uid != ctx.user.pw_uid:
            raise BootstrapError(f"Refusing non-user-owned regular Juliaup completion: {destination}")
        if destination.stat().st_mode & 0o022:
            raise BootstrapError(f"Insecure Juliaup completion file preserved: {destination}; remove group/other write permissions after review")
        if not receipt and spec["profile"] not in ctx.args.adopt:
            raise BootstrapError(f"Unmanaged Juliaup completion preserved: {destination}; review before explicitly --adopt julia")
    directory = native_directory(ctx, destination.parent)
    source = {"executable": str(binary), "sha256": digest(binary),
              "version": ctx.output([binary, "--version"]), "arguments": spec["arguments"]}
    unchanged = exists and receipt and receipt.get("paths", {}).get(str(destination)) == digest(destination)
    if unchanged and receipt.get("source") == source:
        validate_native(ctx, destination)
        verify_native_registration(ctx, spec)
        record_native(ctx, spec, destination, source)
        ctx.status("FOUND", "completion juliaup/julia", str(destination))
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".bootstrap-", dir=directory, delete=False) as stream:
            temporary = Path(stream.name)
            argv = [str(binary), *spec["arguments"]]
            normal_user(ctx)
            with ctx.log_path.open("a") as log:
                log.write("\n$ " + shlex.join(argv) + "\n")
                log.flush()
                result = subprocess.run(argv, env=ctx.env, cwd=ctx.cache, stdin=subprocess.DEVNULL,
                                        stdout=stream, stderr=log, timeout=60)
            if result.returncode:
                raise BootstrapError(f"Juliaup completion generation failed (exit {result.returncode}); existing file preserved")
        validate_native(ctx, temporary)
        if exists and not unchanged and spec["profile"] not in ctx.args.adopt:
            if destination.read_bytes() != temporary.read_bytes():
                raise BootstrapError(f"Externally changed Juliaup completion preserved: {destination}")
        temporary.chmod(0o644)
        proposed = native_receipts(ctx, spec, destination, source, digest(temporary))
        Transaction(ctx).publish_completion(destination, temporary, proposed,
                                            lambda: verify_native_registration(ctx, spec))
    except subprocess.TimeoutExpired as error:
        raise BootstrapError("Juliaup completion generation timed out; existing file preserved") from error
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    ctx.status("UPDATE" if exists else "INSTALL", "completion juliaup/julia", str(destination))


def verify_native_registration(ctx, spec):
    _, registrations = zsh_probe(ctx, spec["commands"], sourced=ctx.home / spec["destination"])
    expected = dict(zip(spec["commands"], spec["functions"]))
    if registrations != expected:
        raise BootstrapError(f"Restored Zsh did not source Juliaup's native integration: {registrations}; expected {expected}")


def provision(ctx, profile):
    normal_user(ctx)
    errors = []
    for spec in ctx.config["optional_zsh_completions"]:
        if spec["profile"] != profile:
            continue
        try:
            if spec["provider"] == "upstream-managed":
                provision_upstream(ctx, spec)
            else:
                provision_system(ctx, spec)
        except (BootstrapError, OSError, ValueError) as error:
            if isinstance(error, RecoveryError) or ctx.state_failed:
                raise
            errors.append(f"{', '.join(spec['commands'])}: {error}")
    if errors:
        raise BootstrapError("; ".join(errors))
