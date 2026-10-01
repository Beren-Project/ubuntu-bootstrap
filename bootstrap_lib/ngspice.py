"""Pinned source build following the official release INSTALL instructions."""
from pathlib import Path
import tempfile

from . import apt
from .platform import BootstrapError
from .runtime import extract
from .system_assets import link, publish


def ngspice(ctx):
    spec = ctx.config["ngspice"]
    prefix = Path("/opt/ubuntu-bootstrap") / f"ngspice-{spec['version']}"
    binary = prefix / "bin/ngspice"
    present = ctx.owned("ngspice", [binary], system=True)
    if present:
        version = ctx.output([binary, "--version"])
        if f"ngspice-{spec['version']}" not in version:
            raise BootstrapError("Installed ngspice does not match the requested source release")
        marker = prefix / "ubuntu-bootstrap-source.json"
        import json
        desired = {"version": spec["version"], "sha256": spec["sha256"], "configure": spec["configure"]}
        if not marker.is_file() or json.loads(marker.read_text()) != desired:
            raise BootstrapError("Installed ngspice source/configuration marker does not match manifest")
        link(ctx, "/usr/local/bin/ngspice", binary)
        ctx.status("FOUND", "ngspice", f"{spec['version']}; no download/rebuild")
        return
    if prefix.exists():
        raise BootstrapError(f"Incomplete/unmanaged ngspice installation at {prefix}; preserved")
    if Path("/usr/local/bin/ngspice").exists() or Path("/usr/local/bin/ngspice").is_symlink():
        raise BootstrapError("Unmanaged /usr/local/bin/ngspice exists; preserved")
    apt.ensure(ctx, ctx.config["apt"]["ngspice"])
    archive = ctx.download(spec["url"], spec["sha256"], f"ngspice-{spec['version']}.tar.gz")
    ctx.status("INSTALL", "ngspice", f"verified source {spec['version']}; build as {ctx.user.pw_name}")
    with tempfile.TemporaryDirectory(prefix="ngspice-build-", dir=ctx.cache) as directory:
        root = Path(directory)
        extract(archive, root)
        source = root / f"ngspice-{spec['version']}"
        build = source / "release"
        build.mkdir()
        ctx.run([source / "configure", f"--prefix={prefix}", *spec["configure"]], cwd=build)
        # Bound compilation memory rather than using every host core in WSL/containers.
        ctx.run(["/usr/bin/make", "-j2"], cwd=build)
        staging = root / "staging"
        ctx.run(["/usr/bin/make", "install", f"DESTDIR={staging}"], cwd=build)
        staged_prefix = staging / prefix.relative_to("/")
        ctx.run([staged_prefix / "bin/ngspice", "--version"])
        import json
        (staged_prefix / "ubuntu-bootstrap-source.json").write_text(json.dumps(
            {"version": spec["version"], "sha256": spec["sha256"], "configure": spec["configure"]}))
        publish(ctx, staged_prefix, prefix)
    link(ctx, "/usr/local/bin/ngspice", binary)
    ctx.run([binary, "--version"])
    ctx.record("ngspice", [binary], version=spec["version"], sha256=spec["sha256"], configure=spec["configure"])
