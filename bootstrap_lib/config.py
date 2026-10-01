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
    return config


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
