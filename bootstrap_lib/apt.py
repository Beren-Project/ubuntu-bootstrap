"""Ubuntu package operations; explicit selected packages only."""
from .platform import BootstrapError


def installed(ctx, package):
    try:
        return ctx.output(["/usr/bin/dpkg-query", "-W", "-f=${Status}", package]) == "install ok installed"
    except BootstrapError:
        return False


def refresh(ctx):
    if not ctx.apt_refreshed:
        ctx.run(["/usr/bin/apt-get", "-o", "APT::Update::Error-Mode=any", "update"], sudo=True)
        ctx.apt_refreshed = True


def ensure(ctx, packages, *, update=None):
    update = ctx.args.update if update is None else update
    wanted = list(dict.fromkeys(packages))
    missing = [p for p in wanted if not installed(ctx, p)]
    if missing or update:
        ctx.status("UPDATE" if update else "INSTALL", "apt", ", ".join(wanted if update else missing))
        refresh(ctx)
        ctx.run(["/usr/bin/env", "DEBIAN_FRONTEND=noninteractive", "/usr/bin/apt-get", "install", "-y",
                 "--no-install-recommends", *(wanted if update else missing)], sudo=True)
    else:
        ctx.status("FOUND", "apt", ", ".join(wanted))
    for package in wanted:
        if not installed(ctx, package):
            raise BootstrapError(f"APT did not install {package}")


def base(ctx):
    ensure(ctx, ctx.config["apt"]["base"])
    for binary in ("zsh", "wl-copy", "wl-paste", "gh"):
        ctx.run(["/usr/bin/test", "-x", f"/usr/bin/{binary}"])
