"""Platform and original-user checks, before any privilege escalation."""
import os
from pathlib import Path
import platform
import pwd
import shlex


class BootstrapError(RuntimeError):
    pass


def detect(config, release_path=Path("/etc/os-release"), machine=None):
    values = {}
    for line in release_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            parsed = shlex.split(value)
            values[key] = parsed[0] if parsed else ""
    if (values.get("ID") != "ubuntu" or
            values.get("VERSION_ID") != config["ubuntu_release"] or
            values.get("VERSION_CODENAME") != config["ubuntu_codename"]):
        raise BootstrapError("Only Ubuntu 26.04 (resolute) is supported")
    architecture = {"x86_64": "amd64", "aarch64": "arm64"}.get(machine or platform.machine())
    if architecture is None:
        raise BootstrapError(f"Unsupported architecture: {machine or platform.machine()}")
    return architecture


def invoking_user():
    if os.geteuid() == 0 or os.getuid() == 0:
        raise BootstrapError("Launch as your normal user, without sudo; never run bootstrap as root")
    user = pwd.getpwuid(os.getuid())
    home = Path(os.environ.get("HOME", "")).absolute()
    if home.resolve() != Path(user.pw_dir).resolve() or home.stat().st_uid != user.pw_uid:
        raise BootstrapError("HOME must be the invoking user's passwd home, owned by that user")
    for variable, expected in [("CARGO_HOME", home / ".cargo"), ("RUSTUP_HOME", home / ".rustup"),
                               ("UV_PYTHON_BIN_DIR", home / ".local/bin"),
                               ("UV_PYTHON_INSTALL_DIR", home / ".local/share/uv/python")]:
        if variable in os.environ and Path(os.environ[variable]) != expected:
            raise BootstrapError(f"Custom {variable} is incompatible with the managed dotfiles layout")
    return user, home
