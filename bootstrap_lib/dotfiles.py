"""Consume the upstream selective restore; never implement a second restore."""
import json
from pathlib import Path
import tempfile
import tomllib

from .config import restore_args
from .platform import BootstrapError


def git(ctx, root, *arguments):
    return ctx.output(["/usr/bin/git", "-C", root, *arguments])


def verify_checkout(ctx, root, url, revision):
    if root.is_symlink() or not (root / ".git").is_dir():
        raise BootstrapError(f"Refusing non-checkout: {root}")
    if git(ctx, root, "remote", "get-url", "origin") != url:
        raise BootstrapError(f"Unexpected checkout origin: {root}")
    if git(ctx, root, "rev-parse", "HEAD") != revision:
        raise BootstrapError(f"Checkout HEAD does not match pinned full SHA: {revision}")
    if git(ctx, root, "status", "--porcelain", "--untracked-files=all", "--ignored"):
        raise BootstrapError(f"Refusing dirty checkout: {root}; inspect it before rerunning")
    # Git index flags could otherwise hide altered code from status.
    entries = git(ctx, root, "ls-files", "-v").splitlines()
    if any(line[0].islower() or line.startswith("S ") for line in entries):
        raise BootstrapError("Checkout index flags hide working-tree contents")


def checkout(ctx):
    spec = ctx.config["dotfiles"]
    parent = ctx.data / "dotfiles"
    from .runtime import safe_directory
    safe_directory(parent)
    root = parent / spec["revision"]
    if not root.exists() and not root.is_symlink():
        ctx.status("INSTALL", "dotfiles", spec["revision"])
        with tempfile.TemporaryDirectory(prefix="fetch-", dir=parent) as directory:
            staged = Path(directory) / "checkout"
            ctx.run(["/usr/bin/git", "init", staged])
            ctx.run(["/usr/bin/git", "-C", staged, "remote", "add", "origin", spec["url"]])
            ctx.run(["/usr/bin/git", "-C", staged, "fetch", "--depth=1", "origin", spec["revision"]])
            ctx.run(["/usr/bin/git", "-C", staged, "checkout", "--detach", "FETCH_HEAD"])
            verify_checkout(ctx, staged, spec["url"], spec["revision"])
            staged.rename(root)
    verify_checkout(ctx, root, spec["url"], spec["revision"])
    ctx.status("VERIFY", "dotfiles", spec["revision"])
    return root


def validate(ctx, root):
    for name in ctx.config["dotfiles"]["files"]:
        destination = ctx.home / name
        if destination.is_symlink() or destination.read_bytes() != (root / "home" / name).read_bytes():
            raise BootstrapError(f"Selected restored config does not match pinned source: {name}")
    for name in (".zshrc", ".zshenv"):
        ctx.run(["/usr/bin/zsh", "-n", ctx.home / name])
    with (ctx.home / ".config/starship.toml").open("rb") as stream:
        tomllib.load(stream)
    if "starship" in ctx.receipts:
        ctx.run([ctx.home / ".cargo/bin/starship", "prompt"], cwd=ctx.cache)
    ctx.output(["/usr/bin/git", "config", "--global", "--list"])
    if ctx.output(["/usr/bin/git", "config", "--file", ctx.home / ".gitconfig", "--get", "core.pager"]) != "delta":
        raise BootstrapError("Shared Git pager is not delta")
    with tempfile.TemporaryDirectory(prefix="tmux-", dir=ctx.cache) as directory:
        socket = Path(directory) / "socket"
        try:
            ctx.run(["/usr/bin/tmux", "-S", socket, "-f", ctx.home / ".tmux.conf", "new-session", "-d"])
            if ctx.output(["/usr/bin/tmux", "-S", socket, "show-option", "-gv", "mode-keys"]) != "vi":
                raise BootstrapError("tmux did not load selected configuration")
        finally:
            ctx.run(["/usr/bin/tmux", "-S", socket, "kill-server"], check=False)
    ctx.run(["/usr/bin/zsh", "-lic", "exit 0"], cwd=ctx.cache)
    plugins = json.loads((root / "scripts/zsh-plugins.json").read_text())
    data = Path(ctx.env.get("XDG_DATA_HOME") or ctx.home / ".local/share") / "zsh/plugins"
    for name, spec in plugins.items():
        verify_checkout(ctx, data / name, spec["url"], spec["revision"])
    ctx.status("OK", "dotfiles", "five configs and pinned plugins validated")


def dotfiles(ctx):
    root = checkout(ctx)
    # Report output is informational: missing optional Zellij/Mermaid dependencies are expected.
    ctx.run(["/usr/bin/python3", "-B", "scripts/check_dependencies.py"], cwd=root)
    ctx.status("VERIFY", "dependencies", "informational upstream report in log; validate selected components only")
    ctx.run(["/usr/bin/python3", "-B", "scripts/install_zsh_plugins.py"], cwd=root)
    ctx.status("VERIFY", "dotfiles", "preview exact five-file selection")
    ctx.run(restore_args(ctx.config), cwd=root)
    ctx.run(restore_args(ctx.config, apply=True), cwd=root)
    validate(ctx, root)
    ctx.record("dotfiles", revision=ctx.config["dotfiles"]["revision"], files=ctx.config["dotfiles"]["files"])
