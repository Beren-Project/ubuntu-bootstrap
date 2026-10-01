"""Optional Ubuntu editors and verified official Neovim archives."""
from pathlib import Path
import tempfile

from . import apt
from .platform import BootstrapError
from .runtime import extract, release, safe_directory
from .system_assets import link, publish


def vim(ctx):
    apt.ensure(ctx, ctx.config["apt"]["vim"])
    ctx.run(["/usr/bin/vim", "--version"])


def emacs(ctx):
    apt.ensure(ctx, ctx.config["apt"]["emacs"])
    ctx.run(["/usr/bin/emacs", "--version"])


def nvim(ctx):
    spec = ctx.config["nvim"]
    artifact = spec["archives"][ctx.arch]
    folder = artifact.removesuffix(".tar.gz")
    destination = Path("/opt") / folder
    binary = destination / "bin/nvim"
    present = ctx.owned("nvim", [binary], system=True)
    if destination.exists() and not present:
        raise BootstrapError(f"Unmanaged or incomplete Neovim directory: {destination}; preserved")
    tag = ctx.receipts.get("nvim", {}).get("release")
    checksum = ctx.receipts.get("nvim", {}).get("sha256")
    if not present or ctx.args.update:
        tag, url, checksum = release(spec["repository"], artifact)
        if present and ctx.output([binary, "--version"]).splitlines()[0] == f"NVIM {tag}":
            ctx.status("FOUND", "nvim", tag)
        else:
            archive = ctx.download(url, checksum, f"{tag}-{artifact}")
            with tempfile.TemporaryDirectory(dir=ctx.cache) as directory:
                extract(archive, directory)
                staged = Path(directory) / folder
                ctx.run([staged / "bin/nvim", "--version"])
                ctx.status("UPDATE" if present else "INSTALL", "nvim", tag)
                publish(ctx, staged, destination)
    else:
        ctx.status("FOUND", "nvim", tag or "explicitly adopted")
    ctx.run([binary, "--headless", "-u", "NONE", "+quit"])
    if ctx.arch == "arm64":
        safe_directory(ctx.home / ".local/bin")
        link(ctx, ctx.home / ".local/bin/nvim", binary, sudo=False)
    ctx.record("nvim", [binary], release=tag, sha256=checksum, architecture=ctx.arch)
