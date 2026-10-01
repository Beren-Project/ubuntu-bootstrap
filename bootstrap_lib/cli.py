"""Human and automated entry point."""
if __package__ in (None, ""):
    import sys
    from pathlib import Path
    # Replace the script directory so platform.py/python.py cannot shadow stdlib modules.
    sys.path[0] = str(Path(__file__).resolve().parents[1])
    __package__ = "bootstrap_lib"

import argparse
import fcntl
import json
import os
import shutil
import sys

from . import apt, dotfiles, editors, julia, ngspice, node, openmodelica, python, rust, shell
from .config import OPTIONAL, load_manifest, resolve
from .platform import BootstrapError, detect, invoking_user
from .runtime import Context


def arguments(argv=None):
    parser = argparse.ArgumentParser(description="Bootstrap Ubuntu 26.04 as your normal user. See README.md.")
    for name in OPTIONAL:
        parser.add_argument("--" + name, action="store_true", help=f"Install optional {name} profile")
    parser.add_argument("--yes", action="store_true", help="Accept interactive defaults and omit optional menu")
    parser.add_argument("--non-interactive", action="store_true", help="No prompts; requires explicit shell choice and available sudo -n")
    parser.add_argument("--update", action="store_true", help="Update only selected bootstrap-owned channel-managed components")
    parser.add_argument("--adopt", action="append", default=[], metavar="COMPONENT", help="Explicitly accept a reviewed existing manager/tool; never inferred from PATH")
    parser.add_argument("--attempt-unqualified", action="append", default=[], metavar="COMPONENT", help="Opt into an unqualified ARM64 component")
    parser.add_argument("--plan", action="store_true", help="Print resolved manifest/profile plan without installing")
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--change-shell", dest="change_shell", action="store_true")
    choice.add_argument("--no-change-shell", dest="change_shell", action="store_false")
    parser.set_defaults(change_shell=None)
    args = parser.parse_args(argv)
    if args.non_interactive and args.change_shell is None and not args.plan:
        parser.error("--non-interactive requires --change-shell or --no-change-shell")
    if not args.non_interactive and not sys.stdin.isatty() and not args.plan:
        parser.error("No interactive terminal: use --non-interactive with an explicit shell choice")
    return args


def main(argv=None):
    ctx = None
    try:
        args = arguments(argv)
        config = load_manifest()
        user, home = invoking_user()
        arch = detect(config)
        requested = [name for name in OPTIONAL if getattr(args, name)]
        if not requested and not args.yes and not args.non_interactive and not args.plan:
            print("Optional components (Enter for base only): " + " ".join(OPTIONAL))
            entered = input("Select names separated by spaces: ").strip().split()
            if any(name not in OPTIONAL for name in entered):
                raise BootstrapError("Unknown optional component; choose names shown in the menu")
            requested = entered
        profiles = resolve(config, [*config["defaults"], *requested])
        names = set(config["profiles"]) | {t["crate"] for t in config["cargo_tools"]} | {"uv", "cargo-binstall"}
        adopt_names = {t["crate"] for t in config["cargo_tools"]} | {"rust", "cargo-binstall", "uv", "python", "node", "julia", "nvim", "ngspice"}
        if any(name not in adopt_names for name in args.adopt) or any(name not in names for name in args.attempt_unqualified):
            raise BootstrapError("Unknown ownership/architecture component identifier")
        if args.plan:
            print(json.dumps({"architecture": arch, "profiles": profiles, "dotfiles": config["dotfiles"], "update": args.update}, indent=2))
            return 0
        if not shutil.which("sudo", path="/usr/bin:/bin"):
            raise BootstrapError("Install sudo and give your normal user sudo access first")
        ctx = Context(config, args, user, home, arch)
        lock_path = ctx.state / "lock"
        if lock_path.is_symlink():
            raise BootstrapError("Refusing symlinked bootstrap lock")
        with lock_path.open("w") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise BootstrapError("Another bootstrap is running") from error
            ctx.status("VERIFY", "platform", f"Ubuntu 26.04/{arch}; original user {user.pw_name}")
            # Obtain ARM64 decisions before installing a declined profile's prerequisites.
            declined = {name for name in [*config["defaults"], *requested]
                        if not ctx.arm_allowed(name, config["profiles"][name]["arm64"])}
            profiles = resolve(config, [name for name in [*config["defaults"], *requested] if name not in declined])
            ctx.run(["/usr/bin/true"], sudo=True)
            handlers = {"apt": apt.base, "rust": rust.rust, "cargo": rust.cargo,
                        "python": python.managed_python, "node": node.node, "dotfiles": dotfiles.dotfiles,
                        "build": lambda c: apt.ensure(c, c.config["apt"]["build"]),
                        "julia": julia.julia, "ngspice": ngspice.ngspice, "openmodelica": openmodelica.openmodelica,
                        "vim": editors.vim, "nvim": editors.nvim, "emacs": editors.emacs}
            failed, skipped = set(), set(declined)
            fatal = False
            for name in profiles:
                dependencies = config["profiles"][name]["depends"]
                if any(dep in failed or dep in skipped for dep in dependencies):
                    skipped.add(name)
                    ctx.status("SKIP", name, "dependency unavailable")
                    if name in requested:
                        failed.add(name)
                    continue
                try:
                    handlers[name](ctx)
                except (BootstrapError, OSError, ValueError) as error:
                    ctx.status("ERROR", name, str(error))
                    failed.add(name)
                    if name in config["defaults"]:
                        fatal = True
                        break
            login = None
            if not fatal:
                try:
                    login = shell.choose(ctx)
                except (BootstrapError, OSError) as error:
                    ctx.status("ERROR", "login shell", str(error))
                    failed.add("shell")
            for name in OPTIONAL:
                if name not in profiles and name not in skipped:
                    ctx.status("SKIP", name, "not selected")
            print("\nSummary: " + "; ".join(f"{state.lower()} {', '.join(dict.fromkeys(r['component'] for r in ctx.results if r['state'] == state))}"
                    for state in ("INSTALL", "FOUND", "UPDATE", "SKIP", "ERROR") if any(r["state"] == state for r in ctx.results)))
            if "dotfiles" in ctx.receipts:
                print("Personal setup: review ~/.gitconfig.local for your Git identity; run gh auth login when you need GitHub authentication.")
            print(f"Log: {ctx.log_path}")
            ctx.write_state("last-run.json", {"profiles": profiles, "architecture": arch,
                "failed": sorted(failed), "skipped": sorted(skipped), "results": ctx.results})
            if failed:
                return 1
            ctx.status("OK", "bootstrap", "ready")
        if login and shell.should_enter(args):
            os.execve(login, ["-zsh"], ctx.env)
        return 0
    except (BootstrapError, OSError, ValueError, KeyboardInterrupt) as error:
        print(f"ERROR {error}", file=sys.stderr)
        if ctx:
            print(f"Log: {ctx.log_path}", file=sys.stderr)
        return 130 if isinstance(error, KeyboardInterrupt) else 1


if __name__ == "__main__":
    sys.exit(main())
