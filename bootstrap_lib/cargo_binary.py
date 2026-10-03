"""Observe cargo-binstall resolution; bound announced GitHub retry sleeps only.

This is subprocess supervision, not another installer. Upstream performs all
discovery, downloads, validation and Cargo publication. See docs/UPSTREAM.md.
"""
from dataclasses import dataclass
import hashlib
import json
import os
import re
import selectors
import shlex
import signal
import subprocess
import time
from urllib.parse import urlsplit

from .durability import parents, regular
from .platform import BootstrapError

RETRY_BUDGET = 5.0
CANCEL_GRACE = 2.0
RESOLUTION_TIMEOUT = 15
MAX_LINE = 1024 * 1024


@dataclass(frozen=True)
class Result:
    returncode: int
    reason: str
    elapsed: float


def _fingerprint(path):
    for parent in path.parents:
        if parent.is_symlink():
            raise BootstrapError(f"Unsafe Cargo publication parent: {parent}")
    if path.parent.exists():
        parents(path)
    if not regular(path, missing=True):
        return None
    info = path.stat()
    return (hashlib.sha256(path.read_bytes()).hexdigest(), info.st_mode, info.st_uid)


class Diagnostics:
    def __init__(self):
        self.delay = 0.0
        self.stop = None
        self.reason = "binary unavailable"
        self.fatal = None
        self.publishing = False

    def observe(self, event):
        message = event.get("fields", {}).get("message", "")
        target = event.get("target", "")
        if not isinstance(message, str) or not isinstance(target, str):
            return "", None
        if target == "binstalk::ops::resolve::resolution" and message == "Installing binaries...":
            self.publishing = True
            self.stop = None
        history = event.get("spans", [])
        spans = [event.get("span", {}), *(history if isinstance(history, list) else [])]
        endpoint = next((span.get("url") for span in spans
                         if isinstance(span, dict) and span.get("name") == "do_send_request"
                         and isinstance(span.get("url"), str)), None)
        try:
            url = urlsplit(endpoint or "")
            github = (url.scheme == "https" and url.hostname == "api.github.com"
                      and (url.path.startswith("/repos/") or url.path == "/graphql"))
        except ValueError:
            github = False
            endpoint = None
        retry = re.fullmatch(r"Received status code (\d{3}) .+, will wait for "
                             r"(\d+(?:\.\d+)?)(ns|µs|ms|s) and retry", message)
        if target == "binstalk_downloader::remote" and retry and github:
            status = int(retry[1])
            if status in (200, 403, 429):
                # A bare 403 doesn't enter this branch: upstream emits this
                # event only with Retry-After/exhausted quota (or status 429).
                self.delay += float(retry[2]) * {"ns": 1e-9, "µs": 1e-6, "ms": 1e-3, "s": 1}[retry[3]]
                self.reason = ("binary resolution rate-limited/retry-delayed" if status in (403, 429)
                               else "binary resolution server-requested retry delay")
                if self.delay > RETRY_BUDGET and not self.publishing:
                    self.stop = self.reason
            else:
                self.reason = "binary resolution network/server failure"
        elif (target == "binstalk_fetchers::common"
              and message.startswith("Your GitHub API token (if any) has reached its rate limit")):
            self.reason = "binary resolution rate-limited"
            if not self.publishing:
                self.stop = self.reason
        elif message.startswith("Timeout reached while checking fetcher"):
            if "retry" not in self.reason and "rate-limited" not in self.reason:
                self.reason = ("binary resolution timed out after network/server failure"
                               if "network" in self.reason else "binary resolution timed out")
        elif message.startswith(("Error while checking fetcher", "Error while downloading and extracting")):
            # Upstream aggregates these into exit 94, including invalid archives
            # and signatures. Only known transport errors may use our fallback.
            transport = ("Reqwest error:" in message or "could not GET https://" in message
                         or "could not HEAD https://" in message)
            invalid = any(marker in message for marker in (
                "builder error", "error decoding response body", "error following redirect",
                "Failed to parse http response body", "Failed to parse url",
                "Failed to verify signature", "Failed to extract zipfile"))
            if transport and not invalid:
                self.reason = "binary resolution network failure"
            else:
                self.fatal = message
        elif message.startswith("Failed to render url for"):
            self.fatal = message
        return message, endpoint


def _terminate(process):
    # Cargo-binstall supports SIGTERM cancellation and ordinarily drops its
    # staging directory and Cargo lock. Reap before invoking cargo install.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=CANCEL_GRACE)
    except subprocess.TimeoutExpired:
        pass
    finally:
        # Also finish cleanup if a second user interruption arrives while waiting.
        # A descendant may hold the output pipe after its parent exits.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def attempt(ctx, arguments, paths):
    root = ctx.home / ".cargo"
    metadata = [root / ".crates.toml", root / ".crates2.json", root / "binstall/crates-v1.json"]
    before = {path: _fingerprint(path) for path in [*paths, *metadata]}
    stages = set(root.glob("cargo-binstall*"))
    # Longest first: overlapping explicitly supplied values must not leak suffixes.
    tokens = sorted((ctx.env[key] for key in ("GITHUB_TOKEN", "GH_TOKEN") if ctx.env.get(key)),
                    key=len, reverse=True)

    def redact(value):
        for token in tokens:
            value = value.replace(token, "[REDACTED]").replace(json.dumps(token)[1:-1], "[REDACTED]")
        return value

    diagnostics = Diagnostics()
    started = time.monotonic()
    command = list(map(str, arguments))
    with ctx.log_path.open("a") as log:
        log.write("\n$ " + redact(shlex.join(command)) + "\n")
        log.flush()
        process = subprocess.Popen(command, env=ctx.env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                pending = b""
                while selector.get_map():
                    ready = selector.select(timeout=0.1)
                    if not ready and process.poll() is not None:
                        _terminate(process)
                    for key, _ in ready:
                        chunk = os.read(key.fd, 65536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                        pending += chunk
                        if len(pending) > MAX_LINE:
                            raise BootstrapError("Oversized cargo-binstall diagnostic; installation stopped")
                        lines = pending.split(b"\n")
                        pending = lines.pop()
                        if not chunk and pending:
                            lines.append(pending)
                            pending = b""
                        for raw in lines:
                            line = raw.decode("utf-8", errors="replace")
                            try:
                                event = json.loads(line)
                            except ValueError:
                                event = None
                            if isinstance(event, dict) and isinstance(event.get("fields"), dict):
                                message, endpoint = diagnostics.observe(event)
                                # Do not dump request headers or unrelated HTTP contents.
                                rendered = f"cargo-binstall: {event.get('level', '')} {message}"
                                if endpoint:
                                    url = urlsplit(endpoint)
                                    rendered += f" [{url.scheme}://{url.hostname}{url.path}]"
                            else:
                                rendered = line
                            log.write(redact(rendered) + "\n")
                        log.flush()
                        if diagnostics.stop:
                            log.write(f"bootstrap: {diagnostics.stop}; announced GitHub retry budget "
                                      f"{RETRY_BUDGET:g}s exceeded/rejected; cancelling binary attempt\n")
                            log.flush()
                            _terminate(process)
                            if selector.get_map():
                                selector.unregister(process.stdout)
                            break
                process.wait()
        except BaseException:
            _terminate(process)
            raise
        finally:
            process.stdout.close()
        code = process.returncode
        elapsed = time.monotonic() - started
        leftovers = set(root.glob("cargo-binstall*")) - stages
        if leftovers:
            log.write("bootstrap: preserved unproven Cargo staging paths: "
                      + redact(", ".join(map(str, sorted(leftovers)))) + "\n")
        if code or diagnostics.stop:
            for path, fingerprint in before.items():
                after = _fingerprint(path)
                # Upstream can create an empty Cargo v1 manifest on first use.
                initialized = (path == root / ".crates.toml" and fingerprint is None
                               and after is not None and path.read_bytes() == b"")
                if after != fingerprint and not initialized:
                    raise BootstrapError(f"Failed binary attempt changed Cargo publication evidence at {path}; preserved")
            if diagnostics.fatal:
                raise BootstrapError("Cargo binary metadata/archive/integrity failure; preserved: "
                                     + redact(diagnostics.fatal))
            # Exit 94 means no candidate succeeded, NOT an installer failure.
            # Other exits (including user cancellation) retain error semantics.
            if not diagnostics.stop and code != 94:
                raise BootstrapError(f"Cargo binary installation failed ({code}); see {ctx.log_path}")
        reason = diagnostics.stop or (diagnostics.reason if code else "binary installed")
        log.write(f"bootstrap: {reason}; binary attempt elapsed {elapsed:.3f}s\n")
    return Result(code, reason, elapsed)
