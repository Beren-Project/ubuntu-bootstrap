"""Official Juliaup, user ownership and explicit update lifecycle."""
import re
from pathlib import Path

from .platform import BootstrapError
from .migration import install_application


def validate_depot(ctx):
    depot = ctx.env.get("JULIAUP_DEPOT_PATH")
    if depot is not None and (not Path(depot).is_absolute() or Path(depot) != ctx.home / ".julia"):
        raise BootstrapError("Custom JULIAUP_DEPOT_PATH conflicts with the pinned dotfiles' native integration; existing state preserved")


def verify_release(ctx):
    binary = ctx.home / ".cargo/bin/juliaup"
    status = ctx.output([binary, "status"])
    if not re.search(r"(?m)^\s*\*\s+" + re.escape(ctx.config["julia"]["channel"]) + r"\s", status):
        raise BootstrapError("Juliaup release default is missing; existing configuration preserved")
    ctx.run([ctx.home / ".cargo/bin/julia", "-e", "print(VERSION)"])


def julia(ctx):
    validate_depot(ctx)
    depot = ctx.home / ".julia/juliaup/juliaup.json"
    present = "julia" in ctx.receipts
    if (depot.exists() or depot.is_symlink()) and not present and "julia" not in ctx.args.adopt:
        raise BootstrapError("Unmanaged Julia channels preserved; review before --adopt julia")
    install_application(ctx, "julia")
    paths = [ctx.home / ".cargo/bin" / name for name in ("juliaup", "julia")]
    if not present and not depot.exists():
        ctx.status("INSTALL", "julia")
        ctx.run([paths[0], "add", ctx.config["julia"]["channel"]])
        ctx.run([paths[0], "default", ctx.config["julia"]["channel"]])
    elif ctx.args.update:
        ctx.status("UPDATE", "julia")
        ctx.run([paths[0], "update", ctx.config["julia"]["channel"]])
    else:
        ctx.status("FOUND", "julia")
    verify_release(ctx)
    ctx.record("julia", manager="juliaup", channel=ctx.config["julia"]["channel"])
