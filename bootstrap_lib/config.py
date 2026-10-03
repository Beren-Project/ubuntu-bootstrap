"""Declarative configuration and dependency resolution."""
from pathlib import Path
import re
import tomllib

ROOT = Path(__file__).resolve().parents[1]
OPTIONAL = ("build", "julia", "ngspice", "openmodelica", "vim", "nvim", "emacs")


def load_manifest():
    with (ROOT / "config/bootstrap.toml").open("rb") as stream:
        config = tomllib.load(stream)
    if config["schema"] != 1:
        raise ValueError("Unsupported manifest schema")
    if not re.fullmatch(r"[0-9a-f]{40}", config["dotfiles"]["revision"]):
        raise ValueError("Dotfiles revision must be a full commit SHA")
    if not re.fullmatch(r"[0-9a-f]{64}", config["ngspice"]["sha256"]):
        raise ValueError("Invalid ngspice checksum")
    files = config["dotfiles"]["files"]
    if len(files) != len(set(files)) or any(
        Path(f).is_absolute() or ".." in Path(f).parts for f in files
    ):
        raise ValueError("Invalid dotfiles selection")
    resolve(config, config["profiles"])
    names = set()
    tools = [*config["cargo_tools"], config["python"]["cargo"], config["julia"]["cargo"]]
    crates = [tool["crate"] for tool in tools]
    bins = [binary for tool in tools for binary in tool["bins"]]
    if len(crates) != len(set(crates)) or len(bins) != len(set(bins)):
        raise ValueError("Duplicate Cargo application/binary ownership")
    for tool in tools:
        if not tool["bins"] or not set(tool.get("version_bins", tool["bins"])).issubset(tool["bins"]):
            raise ValueError("Invalid Cargo application version probes")
        if any(not re.fullmatch(r"[a-zA-Z0-9_-]+", value) for value in [tool["crate"], *tool["bins"]]):
            raise ValueError("Unsafe Cargo application name")
    owners = set(crates) | {"apt", "rust"}
    for spec in config["zsh_completions"]:
        name = spec["command"]
        if not re.fullmatch(r"[a-z][a-z0-9-]*", name) or name in names:
            raise ValueError("Invalid/duplicate completion command")
        names.add(name)
        if spec["profile"] not in config["profiles"] or spec["owner"] not in owners:
            raise ValueError("Unknown completion profile/owner")
        for value in (spec["executable"], spec.get("version_executable", spec["executable"])):
            if ".." in Path(value).parts:
                raise ValueError("Unsafe completion executable path")
    validate_optional_completions(config)
    return config


def validate_optional_completions(config):
    if {spec["profile"] for spec in config["optional_zsh_completions"]} != set(OPTIONAL):
        raise ValueError("Every optional profile must declare its completion provider")
    names = {spec["command"] for spec in config["zsh_completions"]}
    for spec in config["optional_zsh_completions"]:
        if spec["profile"] not in OPTIONAL or not spec["commands"]:
            raise ValueError("Invalid optional completion profile/commands")
        for command in spec["commands"]:
            if not re.fullmatch(r"[a-z][a-z0-9+.-]*", command) or command in names:
                raise ValueError("Invalid/duplicate optional completion command")
            names.add(command)
        provider = spec["provider"]
        if provider not in ("system", "upstream-managed", "unavailable"):
            raise ValueError("Unknown optional completion provider")
        if provider == "system" and not re.fullmatch(r"_[a-z][a-z0-9_-]*", spec.get("function", "")):
            raise ValueError("Invalid optional system completion function")
        if provider in ("system", "unavailable") and not spec.get("packages"):
            raise ValueError("Optional provider needs package inventory")
        if provider == "unavailable" and not spec.get("reason"):
            raise ValueError("Unavailable completion needs an explicit reason")
        if provider == "upstream-managed":
            if spec["profile"] != "julia" or spec.get("owner") != "juliaup":
                raise ValueError("Unknown upstream-managed completion owner")
            for key in ("destination", "executable"):
                value = Path(spec[key])
                if value.is_absolute() or ".." in value.parts or not value.parts:
                    raise ValueError("Unsafe upstream completion path")
            if spec["commands"] != ["juliaup", "julia"] or spec["functions"] != ["_juliaup", "_julia_channel"]:
                raise ValueError("Invalid Juliaup native registration contract")


def resolve(config, requested):
    ordered, visiting = [], set()

    def visit(name):
        if name in visiting:
            raise ValueError(f"Profile dependency cycle at {name}")
        if name in ordered:
            return
        if name not in config["profiles"]:
            raise ValueError(f"Unknown profile: {name}")
        visiting.add(name)
        for dependency in config["profiles"][name]["depends"]:
            visit(dependency)
        visiting.remove(name)
        ordered.append(name)

    for name in requested:
        visit(name)
    return ordered


def restore_args(config, apply=False):
    args = ["/usr/bin/python3", "-B", "scripts/restore.py"]
    for name in config["dotfiles"]["files"]:
        args.extend(["--file", name])
    return args + (["--apply"] if apply else [])
