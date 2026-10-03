"""User-owned uv and managed CPython; never mutate system Python."""
from pathlib import Path
import tempfile

from .platform import BootstrapError
from .migration import install_application


def managed_python(ctx):
    install_application(ctx, "python")
    uv = ctx.home / ".cargo/bin/uv"
    python_paths = [ctx.home / ".local/bin/python", ctx.home / ".local/bin/python3"]
    python_present = ctx.owned("python", python_paths)
    with tempfile.TemporaryDirectory(dir=ctx.cache) as directory:
        if not python_present or ctx.args.update:
            ctx.status("UPDATE" if python_present else "INSTALL", "python", "latest stable managed CPython")
            # Version-file discovery is deliberately outside the user's projects.
            ctx.run([uv, "python", "install", ctx.config["python"]["channel"], "--default"], cwd=directory)
        else:
            ctx.status("FOUND", "python")
        actual = Path(ctx.output([uv, "python", "find", "--managed-python", "--no-python-downloads"], cwd=directory))
        if actual.resolve() != python_paths[0].resolve():
            raise BootstrapError("uv managed Python differs from the expected user default; preserved")
        ctx.run([python_paths[0], "--version"])
        ctx.record("python", python_paths, manager="uv", executable=str(actual))
