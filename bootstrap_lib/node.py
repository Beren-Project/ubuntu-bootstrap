"""Node LTS through the manifest-owned fnm installation."""
import re
from pathlib import Path

from .platform import BootstrapError


def node(ctx):
    fnm = ctx.home / ".cargo/bin/fnm"
    if "fnm" not in ctx.receipts:
        raise BootstrapError("Node requires the manifest-owned fnm installation")
    ctx.owned("fnm", [fnm])
    try:
        default = ctx.output([fnm, "default"])
    except BootstrapError:
        default = ""
    receipt = ctx.receipts.get("node")
    if default and receipt is None and "node" not in ctx.args.adopt:
        raise BootstrapError("Unmanaged fnm default exists. Preserved; review and explicitly --adopt node")
    if receipt and default != receipt.get("version"):
        if "node" not in ctx.args.adopt:
            raise BootstrapError("fnm default changed outside bootstrap; review and explicitly --adopt node")
    if default:
        old_executable = Path(ctx.output([fnm, "exec", "--using", default, "node", "-p", "process.execPath"]))
        ctx.owned("node", [old_executable])
    if not default or ctx.args.update:
        remote = ctx.output([fnm, "ls-remote", "--lts", "--latest"])
        versions = re.findall(r"(?m)^\s*(v\d+\.\d+\.\d+)", remote)
        if len(versions) != 1:
            raise BootstrapError(f"Could not resolve a unique official Node LTS: {remote}")
        default = versions[0]
        ctx.status("UPDATE" if receipt else "INSTALL", "node", default)
        ctx.run([fnm, "install", "--arch", {"amd64": "x64", "arm64": "arm64"}[ctx.arch], default])
        ctx.run([fnm, "default", default])
    else:
        ctx.status("FOUND", "node", default)
    observed = ctx.output([fnm, "exec", "--using", default, "node", "--version"])
    if observed != default:
        raise BootstrapError(f"Node version mismatch: {observed} != {default}")
    observed_arch = ctx.output([fnm, "exec", "--using", default, "node", "-p", "process.arch"])
    if observed_arch != {"amd64": "x64", "arm64": "arm64"}[ctx.arch]:
        raise BootstrapError(f"Node architecture mismatch: {observed_arch}")
    executable = Path(ctx.output([fnm, "exec", "--using", default, "node", "-p", "process.execPath"]))
    if executable.stat().st_uid != ctx.user.pw_uid:
        raise BootstrapError("Managed Node executable belongs to another user")
    ctx.record("node", [executable], manager="fnm", version=default)
