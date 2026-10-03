"""Official rustup and scoped binary-first Cargo installations."""
import json
from pathlib import Path
import re
import tempfile
import tomllib

from . import apt
from .platform import BootstrapError
from .runtime import digest, extract, get_bytes, release, safe_directory
from .durability import parents, regular


def applications(config):
    return [*config["cargo_tools"], config["python"]["cargo"], config["julia"]["cargo"]]


def manager_directories(ctx):
    # Never follow a changed root into another installation before verification
    # or updates. Missing roots remain the official installer's responsibility.
    for directory in (ctx.home / ".cargo", ctx.home / ".cargo/bin", ctx.home / ".rustup"):
        if directory.exists() or directory.is_symlink():
            safe_directory(directory)
            parents(directory / "ownership-check")


def rust_environment(ctx):
    official = {"RUSTUP_UPDATE_ROOT": "https://static.rust-lang.org/rustup",
                "RUSTUP_DIST_SERVER": "https://static.rust-lang.org"}
    for key, value in official.items():
        if ctx.env.get(key, value) != value:
            raise BootstrapError(f"Custom {key} conflicts with the official Rust trust chain")
    return {**ctx.env, **official}


def rustup_init(ctx):
    target = {"amd64": "x86_64", "arm64": "aarch64"}[ctx.arch] + "-unknown-linux-gnu"
    url = ctx.config["rust"]["binaries"] + "/" + target + "/rustup-init"
    if ctx.config["rust"]["binaries"] != "https://static.rust-lang.org/rustup/dist":
        raise BootstrapError("Rust bootstrap must use the official binary distribution")
    try:
        metadata = get_bytes(url + ".sha256").decode("ascii")
    except UnicodeError as error:
        raise BootstrapError("Malformed official rustup-init checksum") from error
    match = re.fullmatch(r"([0-9a-f]{64})[ \t]+\*?(?:\./)?rustup-init\n?", metadata)
    if not match:
        raise BootstrapError("Missing/malformed official rustup-init checksum")
    executable = ctx.download(url, match[1], f"rustup-init-{target}-{match[1]}")
    regular(executable)
    if executable.read_bytes()[:4] != b"\x7fELF":
        raise BootstrapError("Verified rustup-init is not an ELF executable")
    executable.chmod(0o700)
    return executable


def rust(ctx):
    manager_directories(ctx)
    root = ctx.home / ".cargo"
    paths = [root / "bin" / name for name in ("rustup", "cargo", "rustc")]
    present = ctx.owned("rust", paths)
    env = rust_environment(ctx)
    channel = ctx.config["rust"]["channel"]
    if present:
        active = ctx.output([paths[0], "show", "active-toolchain"], env=env, cwd=ctx.cache)
        default = ctx.output([paths[0], "default"], env=env, cwd=ctx.cache)
        if not active.startswith(channel + "-") or not default.startswith(channel + "-"):
            raise BootstrapError("Rust's default toolchain is not stable; preserved existing selection. Select stable explicitly and rerun.")
    if not present:
        if ((ctx.home / ".rustup").exists() or (ctx.home / ".rustup").is_symlink()) and "rust" not in ctx.receipts and "rust" not in ctx.args.adopt:
            raise BootstrapError("Unmanaged .rustup state exists; review the Rust installation first")
        if (root / "env").exists() and "rust" not in ctx.receipts:
            raise BootstrapError("Unmanaged .cargo/env exists; review the Rust installation first")
        ctx.status("INSTALL", "rust", "official rustup, stable/minimal")
        executable = rustup_init(ctx)
        ctx.run([executable, "-y", "--no-modify-path", "--default-toolchain", "none"], env=env, cwd=ctx.cache)
    elif ctx.args.update:
        ctx.status("UPDATE", "rust")
    else:
        ctx.status("FOUND", "rust")
    if not present or ctx.args.update:
        ctx.run([paths[0], "self", "update"], env=env, cwd=ctx.cache)
        ctx.run([paths[0], "toolchain", "install", channel, "--profile", "minimal", "--default",
                 "--no-self-update"], env=env, cwd=ctx.cache)
    active = ctx.output([paths[0], "show", "active-toolchain"], env=env, cwd=ctx.cache)
    default = ctx.output([paths[0], "default"], env=env, cwd=ctx.cache)
    if not active.startswith(channel + "-") or not default.startswith(channel + "-"):
        raise BootstrapError("Rust's default toolchain is not stable; preserved existing selection. Select stable explicitly and rerun.")
    for path in paths:
        ctx.run([path, "--version"], env=env, cwd=ctx.cache)
    regular(root / "env", missing=True)
    if not (root / "env").is_file():
        raise BootstrapError("rustup did not create .cargo/env required by dotfiles")
    ctx.record("rust", paths, manager="rustup", channel=ctx.config["rust"]["channel"])


def binstall(ctx):
    manager_directories(ctx)
    if getattr(ctx, "cargo_manager_ready", False):
        return
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
    ctx.cargo_manager_ready = True


def cargo_registry(ctx):
    manager_directories(ctx)
    # Binstall updates Cargo's v1 registry but may leave .crates2.json unchanged.
    # Prefer the shared v1 registry instead of treating source-only v2 as complete.
    legacy = ctx.home / ".cargo/.crates.toml"
    modern = ctx.home / ".cargo/.crates2.json"
    for path in (legacy, modern):
        regular(path, missing=True)
    if legacy.exists():
        with legacy.open("rb") as stream:
            return {key: {"bins": bins} for key, bins in tomllib.load(stream).get("v1", {}).items()}
    return json.loads(modern.read_text()).get("installs", {}) if modern.exists() else {}


def crate_state(ctx, tool):
    entries = cargo_registry(ctx)
    matches = [key for key in entries if key.split(" ", 1)[0] == tool["crate"]]
    if len(matches) > 1:
        raise BootstrapError(f"Ambiguous Cargo registration for {tool['crate']}; preserved")
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
    tool = next(t for t in applications(ctx.config) if t["crate"] == crate)
    if "binstall_urls" in tool:
        args.extend(["--pkg-url", tool["binstall_urls"][ctx.arch],
                     "--pkg-fmt", tool["binstall_format"], "--bin-dir", tool["binstall_bin_dir"]])
    return [*args, crate]


def executable_version(output):
    # eza prints a descriptive heading before its version; several tools prefix v.
    match = re.search(r"(?<![0-9])\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", output)
    return match.group() if match else None


def install_tool(ctx, tool, *, publish=True, migrating=False):
    name = tool["crate"]
    if not ctx.arm_allowed(name, tool["arm64"]):
        return
    binstall(ctx)
    paths = [ctx.home / ".cargo/bin" / binary for binary in tool["bins"]]
    for path in paths:
        regular(path, missing=True)
    present = False if migrating else ctx.owned(name, paths)
    if migrating and any(p.exists() or p.is_symlink() for p in paths):
        raise BootstrapError(f"Unmanaged replacement {name} installation preserved")
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
            metadata = json.loads(get_bytes(f"https://crates.io/api/v1/crates/{name}"))
            version = metadata["crate"]["max_stable_version"]
            if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
                raise BootstrapError(f"Invalid stable crate version for {name}")
            ctx.status("INSTALL", name, "binary unavailable; locked source fallback with required build dependencies")
            apt.ensure(ctx, ctx.config["apt"]["cargo_source"], update=False)
            ctx.run([ctx.home / ".cargo/bin/cargo", "install", "--locked", "--version", version,
                     *( ["--force"] if present else []), name])
    else:
        ctx.status("FOUND", name)
    version = crate_state(ctx, tool)
    for path in paths:
        regular(path)
        if not path.stat().st_mode & 0o111:
            raise BootstrapError(f"Cargo application is not executable: {path}")
    for binary in tool.get("version_bins", tool["bins"]):
        path = ctx.home / ".cargo/bin" / binary
        reported = ctx.output([path, "--version"])
        if executable_version(reported) != version:
            raise BootstrapError(f"{name} executable/manager version mismatch at {path}: {reported.splitlines()[0]} != {version}")
    receipt = {"paths": {str(p): digest(p) for p in paths}, "manager": "cargo", "crate": name, "version": version}
    if publish:
        ctx.record(name, paths, manager="cargo", crate=name, version=version)
    return receipt


def cargo(ctx):
    binstall(ctx)
    for tool in ctx.config["cargo_tools"]:
        install_tool(ctx, tool)
