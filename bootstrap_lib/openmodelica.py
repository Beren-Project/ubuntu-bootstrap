"""Official signed resolute repository; omc CLI only, no build-profile dependency."""
from pathlib import Path
import tempfile

from . import apt
from .platform import BootstrapError
from .runtime import digest, get_bytes


def openmodelica(ctx):
    spec = ctx.config["openmodelica"]
    codename = ctx.config["ubuntu_codename"]
    source = Path("/etc/apt/sources.list.d/ubuntu-bootstrap-openmodelica.list")
    keyring = Path("/usr/share/keyrings/ubuntu-bootstrap-openmodelica.gpg")
    expected = (f"# Managed by ubuntu-bootstrap\ndeb [arch={ctx.arch} signed-by={keyring}] "
                f"{spec['url']} {codename} {spec['channel']}\n")
    candidates = [Path("/etc/apt/sources.list"), *Path("/etc/apt/sources.list.d").glob("*")]
    for candidate in candidates:
        if candidate.is_file() and spec["url"] in candidate.read_text(errors="replace"):
            if candidate != source or candidate.is_symlink() or candidate.read_text() != expected:
                raise BootstrapError(f"Existing OpenModelica APT source is not bootstrap-managed: {candidate}; preserved")
    if source.exists() and source.read_text() != expected:
        raise BootstrapError("Conflicting managed OpenModelica source; preserved")
    apt.ensure(ctx, ctx.config["apt"]["openmodelica"])
    with tempfile.TemporaryDirectory(prefix="openmodelica-", dir=ctx.cache) as directory:
        root = Path(directory)
        asc = root / "key.asc"
        asc.write_bytes(get_bytes(spec["key_url"]))
        keys = ctx.output(["/usr/bin/gpg", "--homedir", root, "--batch", "--with-colons", "--show-keys", asc])
        fingerprints, primary = set(), False
        for line in keys.splitlines():
            if line.startswith("pub:"):
                primary = True
            elif line.startswith("fpr:") and primary:
                fingerprints.add(line.split(":")[9])
                primary = False
        if fingerprints != set(spec["key_fingerprints"]):
            raise BootstrapError("Official OpenModelica key fingerprint changed; review manifest before trusting it")
        staged_key = root / "key.gpg"
        ctx.run(["/usr/bin/gpg", "--homedir", root, "--batch", "--dearmor", "--output", staged_key, asc])
        release = root / "Release"
        signature = root / "Release.gpg"
        release.write_bytes(get_bytes(f"{spec['url']}/dists/{codename}/Release"))
        signature.write_bytes(get_bytes(f"{spec['url']}/dists/{codename}/Release.gpg"))
        ctx.run(["/usr/bin/gpgv", "--homedir", root, "--keyring", staged_key, signature, release])
        fields = dict(line.split(": ", 1) for line in release.read_text().splitlines() if ": " in line)
        if fields.get("Codename") != codename or ctx.arch not in fields.get("Architectures", "").split():
            raise BootstrapError(f"Official OpenModelica repository does not support {codename}/{ctx.arch}")
        if spec["channel"] not in fields.get("Components", "").split():
            raise BootstrapError("Official OpenModelica channel unavailable")
        if keyring.is_symlink():
            raise BootstrapError("Refusing symlinked OpenModelica keyring")
        if not keyring.exists() or digest(keyring) != digest(staged_key):
            ctx.run(["/usr/bin/install", "-m", "0644", staged_key, keyring], sudo=True)
        if not source.exists():
            staged_source = root / "source.list"
            staged_source.write_text(expected)
            ctx.run(["/usr/bin/install", "-m", "0644", staged_source, source], sudo=True)
            ctx.apt_refreshed = False
    apt.refresh(ctx)
    policy = ctx.output(["/usr/bin/apt-cache", "policy", spec["package"]])
    if "Candidate: (none)" in policy or f"{spec['url']} {codename}/{spec['channel']}" not in policy:
        raise BootstrapError(f"No official OpenModelica CLI package for {codename}/{ctx.arch}")
    apt.ensure(ctx, [spec["package"]])
    ctx.run(["/usr/bin/omc", "--version"])
    ctx.record("openmodelica", manager="apt", repository=spec["url"], codename=codename, package=spec["package"])
