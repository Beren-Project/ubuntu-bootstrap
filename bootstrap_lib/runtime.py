"""Commands, disposable receipts, ownership verification and downloads."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import tarfile
import tempfile
import time
import urllib.request

from .platform import BootstrapError


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe_directory(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise BootstrapError(f"Refusing managed directory with symlinked path: {path}")
    path.mkdir(parents=True, exist_ok=True)
    if path.stat().st_uid != os.getuid():
        raise BootstrapError(f"Managed directory belongs to another user: {path}")
    return path


def get_bytes(url):
    if not url.startswith("https://"):
        raise BootstrapError(f"Only HTTPS downloads are permitted: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "ubuntu-bootstrap"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                if not response.url.startswith("https://"):
                    raise BootstrapError("Refusing a download redirected away from HTTPS")
                return response.read()
        except OSError as error:
            if attempt == 2:
                raise BootstrapError(f"Download failed: {url}: {error}") from error
            time.sleep(1 + attempt)


def release(repository, asset_name):
    metadata = json.loads(get_bytes(f"https://api.github.com/repos/{repository}/releases/latest"))
    if metadata.get("prerelease") or metadata.get("draft"):
        raise BootstrapError("Upstream latest release is not a stable published release")
    for asset in metadata["assets"]:
        if asset["name"] == asset_name:
            checksum = asset.get("digest") or ""
            if not checksum.startswith("sha256:") or len(checksum) != 71:
                raise BootstrapError(f"Official release has no SHA-256 for {asset_name}")
            return metadata["tag_name"], asset["browser_download_url"], checksum[7:]
    raise BootstrapError(f"Official release has no artifact for this architecture: {asset_name}")


def extract(archive, target):
    # Refuse links/special files/traversal before touching a staging tree.
    with tarfile.open(archive) as tree:
        for member in tree.getmembers():
            if (Path(member.name).is_absolute() or ".." in Path(member.name).parts or
                    not (member.isfile() or member.isdir())):
                raise BootstrapError(f"Unsafe archive member: {member.name}")
        tree.extractall(target, filter="data")


class Context:
    def __init__(self, config, args, user, home, architecture):
        self.config, self.args, self.user, self.home, self.arch = config, args, user, home, architecture
        self.data = safe_directory(Path(os.environ.get("XDG_DATA_HOME") or home / ".local/share") / "ubuntu-bootstrap")
        self.cache = safe_directory(Path(os.environ.get("XDG_CACHE_HOME") or home / ".cache") / "ubuntu-bootstrap")
        self.state = safe_directory(Path(os.environ.get("XDG_STATE_HOME") or home / ".local/state") / "ubuntu-bootstrap")
        self.receipts_path = self.state / "receipts.json"
        if self.receipts_path.is_symlink():
            raise BootstrapError("Refusing symlinked receipts")
        self.receipts = json.loads(self.receipts_path.read_text()) if self.receipts_path.exists() else {}
        self.log_path = self.state / "bootstrap.log"
        if self.log_path.is_symlink():
            raise BootstrapError("Refusing symlinked log")
        self.results = []
        self.apt_refreshed = False
        self.env = {**os.environ, "PATH": f"{home}/.cargo/bin:{home}/.local/bin:{home}/.juliaup/bin:/usr/local/bin:/usr/bin:/bin",
                    "GIT_TERMINAL_PROMPT": "0", "UV_NO_MODIFY_PATH": "1"}

    def status(self, state, component, detail=""):
        print(f"{state:7} {component}" + (f" — {detail}" if detail else ""), flush=True)
        self.results.append({"state": state, "component": component, "detail": detail})

    def run(self, argv, *, sudo=False, cwd=None, env=None, check=True, input=None):
        command = list(map(str, argv))
        if sudo:
            command = ["/usr/bin/sudo"] + (["-n"] if self.args.non_interactive else []) + command
        with self.log_path.open("a") as log:
            log.write("\n$ " + shlex.join(command) + "\n")
            log.flush()
            # Keep stdin on the terminal for sudo/chsh credential prompts unless explicit input is supplied.
            completed = subprocess.run(command, cwd=cwd, env=env or self.env,
                                       input=input, text=True, stdout=log, stderr=log)
        if check and completed.returncode:
            tail = "\n".join(self.log_path.read_text(errors="replace").splitlines()[-18:])
            raise BootstrapError(f"Command failed ({completed.returncode}): {shlex.join(command)}\n{tail}")
        return completed.returncode

    def output(self, argv, *, cwd=None, env=None):
        completed = subprocess.run(list(map(str, argv)), cwd=cwd, env=env or self.env,
                                   text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if completed.returncode:
            raise BootstrapError(f"Command failed: {shlex.join(list(map(str, argv)))}: {completed.stderr.strip()}")
        return completed.stdout.strip()

    def record(self, name, paths=(), **details):
        self.receipts[name] = {"paths": {str(p): digest(p) for p in paths}, **details}
        self.write_state("receipts.json", self.receipts)

    def write_state(self, name, value):
        destination = self.state / name
        if destination.parent != self.state or destination.is_symlink():
            raise BootstrapError(f"Refusing unsafe diagnostic state path: {destination}")
        staged = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", dir=self.state, delete=False) as stream:
                staged = Path(stream.name)
                json.dump(value, stream, indent=2, sort_keys=True)
                stream.write("\n")
            staged.replace(destination)
        finally:
            if staged:
                staged.unlink(missing_ok=True)

    def owned(self, name, paths, *, system=False):
        paths = list(map(Path, paths))
        receipt = self.receipts.get(name)
        # Existing user managers/tools cannot be adopted based on PATH alone.
        existing = [p for p in paths if p.exists() or p.is_symlink()]
        if receipt:
            for p in existing:
                if not p.is_file() or (not system and p.stat().st_uid != self.user.pw_uid):
                    raise BootstrapError(f"Invalid ownership/type for {name}: {p}")
                if receipt.get("paths", {}).get(str(p)) != digest(p):
                    if name not in self.args.adopt:
                        raise BootstrapError(f"{name} changed outside bootstrap: {p}. Review and explicitly --adopt {name} to reconcile.")
            return len(existing) == len(paths)
        if existing and name not in self.args.adopt:
            raise BootstrapError(f"Unmanaged {name} installation at {existing[0]}. Preserved. Review it and use --adopt {name} explicitly if desired.")
        for p in existing:
            if not p.is_file() or (not system and p.stat().st_uid != self.user.pw_uid):
                raise BootstrapError(f"Cannot adopt {name}: invalid owner/type at {p}")
        if existing and len(existing) != len(paths):
            raise BootstrapError(f"Partial unmanaged {name} installation; inspect it before retrying")
        return bool(existing)

    def arm_allowed(self, name, support):
        if self.arch != "arm64" or support == "supported":
            return True
        print(f"WARNING {name} is not qualified on ARM64", flush=True)
        allowed = name in self.args.attempt_unqualified
        if not allowed and not self.args.non_interactive and not self.args.yes:
            allowed = input(f"{name} is not qualified on ARM64. Attempt installation anyway? [y/N] ").strip().lower() in ("y", "yes")
        if not allowed:
            self.status("SKIP", name, "ARM64 unqualified; attempt declined")
        return allowed

    def download(self, url, checksum, filename):
        destination = self.cache / filename
        if destination.is_symlink():
            raise BootstrapError(f"Refusing symlinked artifact: {destination}")
        if destination.exists() and digest(destination) == checksum:
            return destination
        data = get_bytes(url)
        if hashlib.sha256(data).hexdigest() != checksum:
            raise BootstrapError(f"SHA-256 mismatch for {url}")
        with tempfile.NamedTemporaryFile(dir=self.cache, delete=False) as stream:
            stream.write(data)
            staged = Path(stream.name)
        staged.replace(destination)
        return destination

    def installer(self, url, arguments, *, env=None):
        with tempfile.TemporaryDirectory(prefix="installer-", dir=self.cache) as directory:
            script = Path(directory) / "install.sh"
            script.write_bytes(get_bytes(url))
            self.run(["/bin/sh", script, *arguments], cwd=directory, env=env)
