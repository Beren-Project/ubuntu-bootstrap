"""Fast public-network failure fixtures: no live quota exhaustion or compilation."""
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import container_checks
from test_maintenance import Environment
from bootstrap_lib import cargo_binary, rust
from bootstrap_lib.platform import BootstrapError


SHIM = r'''
import json, os, shutil, signal, subprocess, sys, tempfile, time, tomllib
from pathlib import Path
root = Path(os.environ['SHIM_ROOT'])
mode = os.environ.get('SHIM_MODE', 'success')
args = sys.argv[1:]
record = Path(os.environ['SHIM_RECORD'])
with record.open('a') as stream:
    stream.write(json.dumps({'command':Path(sys.argv[0]).name, 'argv':args,
                            'token_present':'GITHUB_TOKEN' in os.environ or 'GH_TOKEN' in os.environ}) + '\n')
def event(message, target='binstalk_downloader::remote', url='https://api.github.com/repos/fixture/tool/releases/tags/v1.2.3'):
    value = {'level':'INFO', 'target':target, 'fields':{'message':message},
             'spans':[{'name':'do_send_request','url':url}]}
    line = json.dumps(value) + '\n'
    if mode == 'token':
        for part in (line[:23], line[23:]):
            sys.stdout.write(part); sys.stdout.flush()
    else:
        print(line, end='', flush=True)
def publish():
    name = args[-1]
    bins = json.loads(os.environ['SHIM_BINS'])
    manifest = root / '.crates.toml'
    entries = tomllib.loads(manifest.read_text()).get('v1', {}) if manifest.exists() else {}
    entries = {k:v for k,v in entries.items() if not k.startswith(name+' ')}
    entries[name+' 1.2.3 (registry+https://github.com/rust-lang/crates.io-index)'] = bins
    manifest.write_text('[v1]\n' + '\n'.join(json.dumps(k)+' = '+json.dumps(v) for k,v in entries.items())+'\n')
    for binary in bins:
        path = root / 'bin' / binary
        path.write_text('verified new binary'); path.chmod(0o755)
if Path(sys.argv[0]).name == 'cargo':
    publish(); print('source installed', flush=True); sys.exit(0)
stage = Path(tempfile.mkdtemp(prefix='cargo-binstall', dir=root))
child = None
def cancel(signum, frame):
    if child:
        child.terminate(); child.wait()
    shutil.rmtree(stage)
    sys.exit(32)
signal.signal(signal.SIGTERM, cancel)
manifest = root / '.crates.toml'
if not manifest.exists():
    manifest.touch()
if mode == 'forced':
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
if mode == 'child':
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])
    (root / 'child.pid').write_text(str(child.pid))
if mode in ('rate403', 'rate429', 'retry200', 'forced', 'partial', 'child'):
    if mode == 'partial':
        publish()
    status = '429 Too Many Requests' if mode == 'rate429' else '200 OK' if mode == 'retry200' else '403 Forbidden'
    event('Received status code '+status+', will wait for 120s and retry')
    time.sleep(120)
elif mode == 'graphql':
    event('Your GitHub API token (if any) has reached its rate limit and cannot be used again until None, so we will fallback to HEAD/GET on the url.', 'binstalk_fetchers::common')
    time.sleep(120)
elif mode == 'small_retry':
    event('Received status code 429 Too Many Requests, will wait for 200ms and retry')
    time.sleep(.2)
elif mode == 'latency':
    time.sleep(.2)
elif mode == 'token':
    event('diagnostic '+' '.join(os.environ.get(key, '') for key in ('GITHUB_TOKEN', 'GH_TOKEN')))
elif mode == 'unavailable':
    shutil.rmtree(stage); sys.exit(94)
elif mode == 'network':
    event('Error while checking fetcher invalid url: Reqwest error: DNS lookup failed', 'binstalk::ops::resolve')
    shutil.rmtree(stage); sys.exit(94)
elif mode == 'forbidden':
    event('Error while checking fetcher invalid url: Reqwest error: HTTP status client error (403 Forbidden)', 'binstalk::ops::resolve')
    shutil.rmtree(stage); sys.exit(94)
elif mode == 'outage':
    event('Received status code 503 Service Unavailable, will wait for 120s and retry')
    event('Timeout reached while checking fetcher invalid url: deadline has elapsed', 'binstalk::ops::resolve')
    shutil.rmtree(stage); sys.exit(94)
elif mode in ('archive', 'signature', 'template', 'builder', 'decode', 'redirect'):
    errors = {'archive':'Failed to extract zipfile: malformed archive', 'signature':'Failed to verify signature', 'template':'Failed to parse template: invalid metadata',
              'builder':'Failed to download from remote: Reqwest error: builder error',
              'decode':'Failed to download from remote: Reqwest error: error decoding response body',
              'redirect':'Failed to download from remote: Reqwest error: error following redirect'}
    event('Error while downloading and extracting from fetcher fixture: '+errors[mode], 'binstalk::ops::resolve')
    shutil.rmtree(stage); sys.exit(94)
elif mode == 'install_error':
    event('Installing binaries...', 'binstalk::ops::resolve::resolution')
    publish(); shutil.rmtree(stage); sys.exit(74)
elif mode == 'publication':
    event('Installing binaries...', 'binstalk::ops::resolve::resolution')
    event('Received status code 429 Too Many Requests, will wait for 120s and retry')
elif mode == 'publication_race':
    event('Received status code 429 Too Many Requests, will wait for 120s and retry')
    event('Installing binaries...', 'binstalk::ops::resolve::resolution')
elif mode == 'held_pipe':
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])
    (root / 'child.pid').write_text(str(child.pid))
elif mode == 'cancelled':
    shutil.rmtree(stage); sys.exit(32)
elif mode == 'unsupported':
    shutil.rmtree(stage); sys.exit(2)
elif mode == 'wrong_version':
    args[-1] = 'wrong-crate'
publish()
shutil.rmtree(stage)
event('Done', 'cargo_binstall::bin_util')
'''


class BinaryTests(Environment):
    def setUp(self):
        super().setUp()
        self.tool = self.ctx.config['python']['cargo']
        self.root = self.home / '.cargo'
        self.binary = self.file(self.root / 'bin/cargo-binstall', ('#!'+sys.executable+'\n'+SHIM).encode())
        self.file(self.root / 'bin/cargo', ('#!'+sys.executable+'\n'+SHIM).encode())
        self.record = self.home / 'commands.jsonl'
        self.ctx.env.update(SHIM_ROOT=str(self.root), SHIM_RECORD=str(self.record), SHIM_BINS=json.dumps(self.tool['bins']))
        self.paths = [self.root / 'bin' / name for name in self.tool['bins']]

    def attempt(self, mode):
        self.ctx.env['SHIM_MODE'] = mode
        return cargo_binary.attempt(self.ctx, rust.update_argv(self.ctx, 'uv', '1.2.3'), self.paths)

    def calls(self):
        return [json.loads(line) for line in self.record.read_text().splitlines()]

    def test_fast_success_latency_and_small_retry(self):
        for mode in ('success', 'latency', 'small_retry', 'publication'):
            with self.subTest(mode=mode):
                result = self.attempt(mode)
                self.assertEqual(result.reason, 'binary installed')
                self.assertEqual(result.returncode, 0)
                self.assertLess(result.elapsed, 2)
                self.assertFalse(list(self.root.glob('cargo-binstall*')))

    def test_ordinary_latency_does_not_consume_retry_budget(self):
        with patch.object(cargo_binary, 'RETRY_BUDGET', .01):
            result = self.attempt('latency')
        self.assertEqual(result.reason, 'binary installed')
        self.assertGreater(result.elapsed, .2)

    def test_long_wait_is_cancelled_fast_before_publication(self):
        for mode in ('rate403', 'rate429', 'retry200', 'graphql', 'child'):
            with self.subTest(mode=mode):
                result = self.attempt(mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertLess(result.elapsed, 2)
                self.assertFalse(any(path.exists() for path in self.paths))
                self.assertFalse(list(self.root.glob('cargo-binstall*')))
                self.assertIn('retry budget 5s', self.ctx.log_path.read_text())
                if mode == 'child':
                    with self.assertRaises(ProcessLookupError):
                        os.kill(int((self.root / 'child.pid').read_text()), 0)

    def test_forced_termination_is_bounded_and_preserves_unproven_stage(self):
        with patch.object(cargo_binary, 'CANCEL_GRACE', .15):
            result = self.attempt('forced')
        self.assertLess(result.elapsed, 1)
        self.assertEqual(result.returncode, -9)
        self.assertTrue(list(self.root.glob('cargo-binstall*')))
        self.assertIn('preserved unproven Cargo staging paths', self.ctx.log_path.read_text())

    def test_parent_exit_with_held_pipe_does_not_hang(self):
        result = self.attempt('held_pipe')
        self.assertEqual(result.reason, 'binary installed')
        self.assertLess(result.elapsed, 1)

    def test_publication_marker_revokes_pending_cancellation(self):
        state = cargo_binary.Diagnostics()
        state.observe({'target':'binstalk_downloader::remote', 'fields':{'message':'Received status code 429 Too Many Requests, will wait for 120s and retry'},
                       'span':{'name':'do_send_request', 'url':'https://api.github.com/repos/fixture/tool/releases/tags/v1'}})
        self.assertIsNotNone(state.stop)
        state.observe({'target':'binstalk::ops::resolve::resolution', 'fields':{'message':'Installing binaries...'}})
        self.assertIsNone(state.stop)

    def test_user_interruption_terminates_and_reaps_without_fallback(self):
        select = cargo_binary.selectors.DefaultSelector.select
        def interrupted(selector, *args, **kwargs):
            select(selector, *args, **kwargs)
            raise KeyboardInterrupt()
        with patch.object(cargo_binary.selectors.DefaultSelector, 'select', interrupted), \
                patch.object(cargo_binary, '_terminate', wraps=cargo_binary._terminate) as terminate:
            with self.assertRaises(KeyboardInterrupt):
                self.attempt('rate403')
        self.assertIsNotNone(terminate.call_args.args[0].poll())
        self.assertEqual(len(self.calls()), 1)
        self.assertFalse(any(p.exists() for p in self.paths))

    def test_second_interruption_during_cancel_still_reaps(self):
        self.ctx.env['SHIM_MODE'] = 'rate403'
        process = cargo_binary.subprocess.Popen([str(self.binary), 'uv'], env=self.ctx.env,
                                               stdout=cargo_binary.subprocess.PIPE, start_new_session=True)
        try:
            process.stdout.readline()  # Fixture is initialized and waiting.
            wait = process.wait
            calls = []
            def interrupted(*args, **kwargs):
                calls.append(None)
                if len(calls) == 1:
                    raise KeyboardInterrupt()
                return wait(*args, **kwargs)
            with patch.object(process, 'wait', side_effect=interrupted):
                with self.assertRaises(KeyboardInterrupt):
                    cargo_binary._terminate(process)
            self.assertIsNotNone(process.poll())
        finally:
            cargo_binary._terminate(process)
            process.stdout.close()

    def test_non_quota_failures_are_distinguished(self):
        for mode, reason in (('unavailable', 'binary unavailable'), ('network', 'network failure'),
                             ('forbidden', 'network failure'), ('outage', 'timed out')):
            with self.subTest(mode=mode):
                result = self.attempt(mode)
                self.assertEqual(result.returncode, 94)
                self.assertIn(reason, result.reason)
                self.assertNotIn('rate-limited', result.reason)

    def test_integrity_metadata_install_and_user_errors_do_not_fallback(self):
        for mode in ('archive', 'signature', 'template', 'builder', 'decode', 'redirect', 'cancelled', 'unsupported', 'install_error'):
            with self.subTest(mode=mode):
                with self.assertRaises(BootstrapError):
                    self.attempt(mode)

    def test_partial_writes_on_cancel_fail_closed(self):
        with self.assertRaisesRegex(BootstrapError, 'changed Cargo publication evidence'):
            self.attempt('partial')
        self.assertTrue(self.paths[0].exists())
        self.assertNotIn('uv', self.ctx.receipts)

    def test_tokens_pass_through_but_are_redacted(self):
        for key in ('GITHUB_TOKEN', 'GH_TOKEN'):
            with self.subTest(key=key):
                self.ctx.env.pop('GITHUB_TOKEN', None)
                self.ctx.env.pop('GH_TOKEN', None)
                token = 'explicit-test-secret-'+key
                self.ctx.env[key] = token
                self.attempt('token')
                self.assertTrue(self.calls()[-1]['token_present'])
                self.assertNotIn(token, self.ctx.log_path.read_text())
                self.assertNotIn(token, self.ctx.receipts_path.read_text() if self.ctx.receipts_path.exists() else '')
                self.assertIn('[REDACTED]', self.ctx.log_path.read_text())

    def test_overlapping_explicit_tokens_do_not_leak_suffixes(self):
        self.ctx.env.update(GITHUB_TOKEN='explicit-prefix-secret', GH_TOKEN='explicit-prefix-secret-private-suffix')
        self.attempt('token')
        log = self.ctx.log_path.read_text()
        self.assertNotIn('explicit-prefix-secret', log)
        self.assertNotIn('private-suffix', log)

    def test_one_version_for_binary_and_locked_source_and_unrelated_preserved(self):
        unrelated = self.file(self.root / 'bin/unrelated', b'personal application')
        manifest = self.root / '.crates.toml'
        manifest.write_text('[v1]\n"unrelated 9.8.7 (registry+https://github.com/rust-lang/crates.io-index)" = ["unrelated"]\n')
        self.ctx.env.update(SHIM_MODE='rate403', GITHUB_TOKEN='explicit-secret-token')
        with patch.object(rust, 'binstall'), patch.object(rust.apt, 'ensure') as apt, \
                patch.object(rust, 'get_bytes', return_value=b'{"crate":{"max_stable_version":"1.2.3"}}') as metadata, \
                patch.object(self.ctx, 'output', return_value='uv 1.2.3'):
            receipt = rust.install_tool(self.ctx, self.tool)
        metadata.assert_called_once()
        apt.assert_called_once()
        binary, source = self.calls()
        self.assertIn('--no-discover-github-token', binary['argv'])
        self.assertEqual(binary['argv'][binary['argv'].index('--version')+1], '=1.2.3')
        self.assertEqual(source['argv'], ['install', '--locked', '--version', '1.2.3', 'uv'])
        self.assertTrue(binary['token_present'])
        self.assertFalse(source['token_present'])
        self.assertEqual(receipt['version'], '1.2.3')
        self.assertEqual(unrelated.read_bytes(), b'personal application')
        self.assertIn('unrelated 9.8.7', manifest.read_text())
        self.assertNotIn('explicit-secret-token', self.ctx.log_path.read_text())
        with patch.object(rust, 'get_bytes') as metadata, patch.object(cargo_binary, 'attempt') as attempt, \
                patch.object(rust, 'binstall'), patch.object(self.ctx, 'output', return_value='uv 1.2.3'):
            rust.install_tool(self.ctx, self.tool)
        metadata.assert_not_called()
        attempt.assert_not_called()
        self.ctx.args.update = True
        self.ctx.env['SHIM_MODE'] = 'unavailable'
        with patch.object(rust, 'binstall'), patch.object(rust.apt, 'ensure'), \
                patch.object(rust, 'get_bytes', return_value=b'{"crate":{"max_stable_version":"1.2.3"}}'), \
                patch.object(self.ctx, 'output', return_value='uv 1.2.3'):
            rust.install_tool(self.ctx, self.tool)
        self.assertIn('--force', self.calls()[-1]['argv'])
        self.assertIn('unrelated 9.8.7', manifest.read_text())

    def test_malformed_stable_metadata_prevents_binary_attempt(self):
        for raw in (b'{}', b'{"crate":null}', b'{"crate":{"max_stable_version":null}}',
                    b'{"crate":{"max_stable_version":"1.2.3-beta"}}', b'bad json'):
            with patch.object(rust, 'get_bytes', return_value=raw), patch.object(rust, 'binstall'):
                with self.assertRaisesRegex(BootstrapError, 'Invalid stable crate'):
                    rust.install_tool(self.ctx, self.tool)
        self.assertFalse(self.record.exists())

    def test_unexpected_installed_version_is_not_receipted(self):
        with patch.object(rust, 'binstall'), \
                patch.object(rust, 'get_bytes', return_value=b'{"crate":{"max_stable_version":"1.2.4"}}'):
            with self.assertRaisesRegex(BootstrapError, 'Cargo version mismatch'):
                rust.install_tool(self.ctx, self.tool)
        self.assertNotIn('uv', self.ctx.receipts)

    def test_missing_owned_binaries_source_fallback_repairs_registration(self):
        for path in self.paths:
            self.file(path)
        self.cargo_metadata(self.tool)
        self.ctx.record('uv', self.paths, manager='cargo', crate='uv', version='1.2.3')
        for path in self.paths:
            path.unlink()
        self.ctx.env['SHIM_MODE'] = 'unavailable'
        with patch.object(rust, 'binstall'), patch.object(rust.apt, 'ensure'), \
                patch.object(rust, 'get_bytes', return_value=b'{"crate":{"max_stable_version":"1.2.3"}}'), \
                patch.object(self.ctx, 'output', return_value='uv 1.2.3'):
            rust.install_tool(self.ctx, self.tool)
        self.assertIn('--force', self.calls()[-1]['argv'])

    def test_symlinked_registration_parent_is_preserved(self):
        target = self.home / 'personal'
        target.mkdir()
        (self.root / 'binstall').symlink_to(target)
        with self.assertRaisesRegex(BootstrapError, 'Unsafe Cargo publication parent'):
            self.attempt('success')
        self.assertFalse(self.record.exists())

    def test_cumulative_budget_and_unrelated_endpoints(self):
        state = cargo_binary.Diagnostics()
        event = {'target':'binstalk_downloader::remote', 'fields':{'message':'Received status code 429 Too Many Requests, will wait for 3s and retry'},
                 'span':{'name':'do_send_request', 'url':'https://api.github.com/repos/fixture/tool/releases/tags/v1'}}
        state.observe(event)
        self.assertIsNone(state.stop)
        state.observe(event)
        self.assertIsNotNone(state.stop)
        for endpoint in ('https://crates.io/api/v1/crates/uv', 'https://api.github.com.evil/repos/f/r', 'https://github.com/fixture/tool/releases/download/v1/tool.tgz'):
            event['span']['url'] = endpoint
            state = cargo_binary.Diagnostics()
            state.observe(event)
            self.assertIsNone(state.stop)

    def test_container_audit_ignores_unrelated_multiline_commands(self):
        args = rust.update_argv(self.ctx, 'uv', '1.2.3')
        import shlex
        log = ("$ /usr/bin/zsh -lc 'a multiline\ncommand'\n"
               + '$ ' + shlex.join(list(map(str, args))) + '\n'
               + 'bootstrap: binary installed; binary attempt elapsed 0.100s\n'
               + '$ '+str(self.root/'bin/cargo')+' install --locked --version 1.2.3 uv\n')
        with patch.object(container_checks, 'HOME', self.home):
            container_checks.cargo_resolution_policy(log)


if __name__ == '__main__':
    unittest.main()
