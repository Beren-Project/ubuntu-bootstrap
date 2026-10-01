"""Consent-controlled change of only the original user's login shell."""
import os
from pathlib import Path
import pwd
import shutil
import sys

from .platform import BootstrapError


def choose(ctx):
    path = shutil.which("zsh", path="/usr/bin:/bin")
    if path is None:
        raise BootstrapError("Installed Zsh executable not found")
    allowed = [line.strip() for line in Path("/etc/shells").read_text().splitlines()
               if line.strip() and not line.startswith("#")]
    if path not in allowed:
        raise BootstrapError(f"Installed Zsh is not an allowed login shell: {path}")
    consent = ctx.args.change_shell
    if consent is None:
        consent = ctx.args.yes or input("Change your default shell to Zsh? [Y/n] ").strip().lower() not in ("n", "no")
    if not consent:
        ctx.status("SKIP", "login shell", f"later: chsh -s {path} {ctx.user.pw_name}")
        return None
    current = pwd.getpwnam(ctx.user.pw_name)
    if current.pw_uid != ctx.user.pw_uid or current.pw_uid == 0:
        raise BootstrapError("Original invoking user changed; refusing login-shell modification")
    if current.pw_shell != path:
        ctx.status("INSTALL", "login shell", f"{ctx.user.pw_name} → {path}")
        # Consent has been obtained; Ubuntu PAM may require elevation here.
        ctx.run(["/usr/bin/chsh", "-s", path, ctx.user.pw_name], sudo=True)
    else:
        ctx.status("FOUND", "login shell", path)
    verified = pwd.getpwnam(ctx.user.pw_name)
    if verified.pw_shell != path or verified.pw_uid != ctx.user.pw_uid:
        raise BootstrapError("Login shell change did not match the original user's passwd entry")
    ctx.record("shell", user=ctx.user.pw_name, shell=path)
    return path


def should_enter(args):
    return not args.non_interactive and not os.environ.get("CI") and sys.stdin.isatty() and sys.stdout.isatty()
