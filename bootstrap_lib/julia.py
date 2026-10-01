"""Official Juliaup, user ownership and explicit update lifecycle."""
import re

from .platform import BootstrapError


def julia(ctx):
    paths = [ctx.home / ".juliaup/bin" / name for name in ("juliaup", "julia")]
    present = ctx.owned("julia", paths)
    if not present:
        ctx.status("INSTALL", "julia")
        ctx.installer(ctx.config["julia"]["installer"], ["-y", "--add-to-path=no",
                      f"--default-channel={ctx.config['julia']['channel']}",
                      "--background-selfupdate=0", "--startup-selfupdate=0"])
    elif ctx.args.update:
        ctx.status("UPDATE", "julia")
        ctx.run([paths[0], "self", "update"])
        ctx.run([paths[0], "update", ctx.config["julia"]["channel"]])
    else:
        ctx.status("FOUND", "julia")
    status = ctx.output([paths[0], "status"])
    if not re.search(r"(?m)^\s*\*\s+" + re.escape(ctx.config["julia"]["channel"]) + r"\s", status):
        raise BootstrapError("Juliaup release default is missing; existing configuration preserved")
    ctx.run([paths[1], "-e", "print(VERSION)"])
    ctx.record("julia", paths, manager="juliaup", channel=ctx.config["julia"]["channel"])
