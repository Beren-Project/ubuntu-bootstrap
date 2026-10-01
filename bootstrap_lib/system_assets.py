"""Publish staged system assets without deleting a working installation first."""
from pathlib import Path
import time

from .platform import BootstrapError


def link(ctx, destination, target, *, sudo=True):
    destination, target = Path(destination), Path(target)
    if destination.is_symlink() and destination.resolve() == target.resolve():
        return
    if destination.exists() or destination.is_symlink():
        raise BootstrapError(f"Refusing unrelated existing command link/file: {destination}")
    ctx.run(["/usr/bin/ln", "-s", target, destination], sudo=sudo)


def publish(ctx, staged, destination):
    destination = Path(destination)
    if any(p.is_symlink() for p in (destination, *destination.parents)):
        raise BootstrapError(f"Refusing symlinked system installation: {destination}")
    temporary = destination.with_name(destination.name + ".ubuntu-bootstrap-new")
    previous = destination.with_name(destination.name + f".ubuntu-bootstrap-previous-{time.time_ns()}")
    if any(p.exists() or p.is_symlink() for p in (temporary, previous)):
        raise BootstrapError(f"Interrupted publication at {temporary} or {previous}; inspect before retrying")
    ctx.run(["/usr/bin/mkdir", "-p", destination.parent], sudo=True)
    ctx.run(["/usr/bin/cp", "-r", "--no-preserve=ownership", staged, temporary], sudo=True)
    moved = False
    try:
        if destination.exists():
            ctx.run(["/usr/bin/mv", destination, previous], sudo=True)
            moved = True
        ctx.run(["/usr/bin/mv", temporary, destination], sudo=True)
    except BootstrapError:
        if moved and not destination.exists():
            ctx.run(["/usr/bin/mv", previous, destination], sudo=True)
        raise
    # Retain each working predecessor without blocking subsequent replacements.
    if moved:
        ctx.status("OK", destination.name, f"previous installation retained at {previous}")
