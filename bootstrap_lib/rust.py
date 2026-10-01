"""Official rustup and scoped binary-first Cargo installations."""
import json
from pathlib import Path
import re
import tempfile
import tomllib

from . import apt
from .platform import BootstrapError
from .runtime import extract, release


def rust(ctx):
    root = ctx.home / ".cargo"
    paths = [root / "bin" / name for name in ("rustup", "cargo", "rustc")]
    present = ctx.owned("rust", paths)
    if not present:
        if (root / "env").exists() and "rust" not in ctx.receipts:
            raise BootstrapError("Unmanaged .cargo/env exists; review the Rust installation first")
        ctx.status("INSTALL", "rust", "official rustup, stable/minimal")
        ctx.installer(ctx.config["rust"]["installer"], ["-y", "--no-modify-path", "--profile", "minimal",
                                                       "--default-toolchain", ctx.config["rust"]["channel"]])
    elif ctx.args.update:
        ctx.status("UPDATE", "rust")
        ctx.run([paths[0], "self", "update"])
        ctx.run([paths[0], "update", ctx.config["rust"]["channel"]])
    else:
        ctx.status("FOUND", "rust")
    active = ctx.output([paths[0], "show", "active-toolchain"])
    if not active.startswith(ctx.config["rust"]["channel"] + "-"):
        raise BootstrapError("Rust's default toolchain is not stable; preserved existing selection. Select stable explicitly and rerun.")
    ctx.run([paths[1], "--version"])
    ctx.run([paths[2], "--version"])
    if not (root / "env").is_file():
        raise BootstrapError("rustup did not create .cargo/env required by dotfiles")
    ctx.record("rust", paths, manager="rustup", channel=ctx.config["rust"]["channel"])


def binstall(ctx):
    binary = ctx.home / ".cargo/bin/cargo-binstall"
    present = ctx.owned("cargo-binstall", [binary])
    if not present or ctx.args.update:
        target = {"amd64": "x86_64", "arm64": "aarch64"}[ctx.arch] + "-unknown-linux-musl"
        tag, url, checksum = release(ctx.config["rust"]["binstall_repository"], f"cargo-binstall-{target}.tgz")
        archive = ctx.download(url, checksum, f"cargo-binstall-{tag}-{target}.tgz")
        with tempfile.TemporaryDirectory(dir=ctx.cache) as directory:
            extract(archive, directory)
            executable = Path(directory) / "cargo-binstall"
            ctx.status("UPDATE" if present else "INSTALL", "cargo-binstall", tag)
            ctx.run([executable, "--self-install"])
        ctx.record("cargo-binstall", [binary], release=tag, sha256=checksum)
    else:
        ctx.status("FOUND", "cargo-binstall")
    ctx.run([binary, "-V"])


def cargo_registry(ctx):
    # Binstall updates Cargo's v1 registry but may leave .crates2.json unchanged.
    # Prefer the shared v1 registry instead of treating source-only v2 as complete.
    legacy = ctx.home / ".cargo/.crates.toml"
    modern = ctx.home / ".cargo/.crates2.json"
    for path in (legacy, modern):
        if path.is_symlink() or (path.exists() and path.stat().st_uid != ctx.user.pw_uid):
            raise BootstrapError("Cargo registry metadata has unexpected ownership/type")
    if legacy.exists():
        with legacy.open("rb") as stream:
            return {key: {"bins": bins} for key, bins in tomllib.load(stream).get("v1", {}).items()}
    return json.loads(modern.read_text()).get("installs", {}) if modern.exists() else {}


def crate_state(ctx, tool):
    entries = cargo_registry(ctx)
    for key, info in entries.items():
        if key.split(" ", 1)[0] == tool["crate"]:
            if not key.endswith("(registry+https://github.com/rust-lang/crates.io-index)"):
                raise BootstrapError(f"{tool['crate']} comes from an unrelated Cargo source; preserved")
            if not set(tool["bins"]).issubset(info["bins"]):
                raise BootstrapError(f"Cargo metadata lacks expected binaries for {tool['crate']}")
            return key.split(" ")[1]
    raise BootstrapError(f"No crates.io installation metadata for {tool['crate']}")


def update_argv(ctx, crate):
    # One explicit manifest crate per operation. Never pass all-installed flags.
    args = [ctx.home / ".cargo/bin/cargo-binstall", "--no-confirm", "--disable-telemetry",
            "--strategies", "crate-meta-data"]
    tool = next(t for t in ctx.config["cargo_tools"] if t["crate"] == crate)
    if "binstall_urls" in tool:
        args.extend(["--pkg-url", tool["binstall_urls"][ctx.arch],
                     "--pkg-fmt", tool["binstall_format"], "--bin-dir", tool["binstall_bin_dir"]])
    return [*args, crate]


def executable_version(output):
    # eza prints a descriptive heading before its version; several tools prefix v.
    match = re.search(r"(?<![0-9])\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", output)
    return match.group() if match else None


def install_tool(ctx, tool):
    name = tool["crate"]
    if not ctx.arm_allowed(name, tool["arm64"]):
        return
    paths = [ctx.home / ".cargo/bin" / binary for binary in tool["bins"]]
    present = ctx.owned(name, paths)
    if present:
        crate_state(ctx, tool)
    if not present or ctx.args.update:
        ctx.status("UPDATE" if present else "INSTALL", name)
        arguments = update_argv(ctx, name)
        if not present:
            arguments.insert(1, "--force")  # repair missing owned binaries despite old Cargo metadata
        result = ctx.run(arguments, check=False)
        if result:
            # A network/server failure must not be disguised as a source fallback.
            # Resolve the stable crate version explicitly, then try a locked build.
            from .runtime import get_bytes
            metadata = json.loads(get_bytes(f"https://crates.io/api/v1/crates/{name}"))
            version = metadata["crate"]["max_stable_version"]
            ctx.status("INSTALL", name, "binary unavailable; locked source fallback with required build dependencies")
            apt.ensure(ctx, ctx.config["apt"]["cargo_source"], update=False)
            ctx.run([ctx.home / ".cargo/bin/cargo", "install", "--locked", "--version", version,
                     *( ["--force"] if present else []), name])
    else:
        ctx.status("FOUND", name)
    version = crate_state(ctx, tool)
    for path in paths:
        reported = ctx.output([path, "--version"])
        if executable_version(reported) != version:
            raise BootstrapError(f"{name} executable/manager version mismatch at {path}: {reported.splitlines()[0]} != {version}")
    ctx.record(name, paths, manager="cargo", crate=name, version=version)


def cargo(ctx):
    binstall(ctx)
    for tool in ctx.config["cargo_tools"]:
        install_tool(ctx, tool)
