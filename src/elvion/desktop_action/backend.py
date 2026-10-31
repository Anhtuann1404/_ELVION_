"""One-shot private-pipe handshake with the pinned Calculator AX helper."""
from hashlib import sha256
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

from elvion.models.structured import strict_json
from .contracts import PressOutcome, supports

SOURCE = Path(__file__).resolve().parents[3] / 'native/macos/CalculatorPress.swift'
REASONS = frozenset(('PREPARED', 'AXPRESS_RETURNED', 'AXPRESS_ERROR', 'INVALID_REQUEST',
    'AUTHORIZATION_EXPIRED', 'TARGET_CHANGED', 'AX_PERMISSION_UNAVAILABLE',
    'DISPLAY_LAYOUT_CHANGED', 'SAMPLED_VISIBILITY_UNCERTAIN', 'COMMIT_REJECTED',
    'PROBE_TOO_LONG', 'AXPRESS_UNSUPPORTED'))


class HelperTransport:
    def __init__(self, binary):
        self.process = subprocess.Popen([str(binary)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=False, bufsize=0)

    def send(self, payload):
        raw = json.dumps(payload, allow_nan=False, separators=(',', ':')).encode() + b'\n'
        if len(raw) > 16384:
            raise ValueError('PROTOCOL_ERROR')
        self.process.stdin.write(raw)
        self.process.stdin.flush()

    def read(self, timeout):
        deadline = time.monotonic() + timeout
        raw = bytearray()
        while len(raw) <= 4096:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.process.stdout], [], [], remaining)[0]:
                raise TimeoutError('HELPER_TIMEOUT')
            byte = os.read(self.process.stdout.fileno(), 1)
            if not byte:
                raise ValueError('HELPER_EOF')
            if byte == b'\n':
                return strict_json(raw.decode('utf-8'))
            raw.extend(byte)
        raise ValueError('PROTOCOL_ERROR')

    def close(self):
        for stream in (self.process.stdin, self.process.stdout):
            if stream:
                stream.close()
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(timeout=2)


class CalculatorPressBackend:
    def __init__(self, *, transport_factory=HelperTransport, runner=subprocess.run):
        self.transport_factory, self.runner = transport_factory, runner
        self.binary = SOURCE.parents[2] / 'artifacts/native' / (
            'calculator-press-' + sha256(SOURCE.read_bytes()).hexdigest()[:16])

    def prepare(self):
        if sys.platform != 'darwin':
            raise ValueError('MACOS_REQUIRED')
        if self.binary.is_file() and os.access(self.binary, os.X_OK):
            return
        self.binary.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self.binary.parent, prefix='.press-build-') as folder:
            path = Path(folder)
            source, binary = path/'main.swift', path/'helper'
            source.write_bytes(SOURCE.read_bytes())
            built = self.runner(['/usr/bin/swiftc', '-swift-version', '5', '-module-cache-path',
                str(path/'cache'), str(source), '-o', str(binary)], shell=False,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60, check=False)
            if built.returncode != 0 or not binary.is_file():
                raise ValueError('CALCULATOR_PRESS_BUILD_FAILED')
            binary.chmod(0o700)
            os.replace(binary, self.binary)

    def press(self, intent, token, *, authorized, reserve):
        if not supports(intent) or not token.permits(intent) or not authorized():
            return PressOutcome('blocked', 'AUTHORIZATION_DENIED')
        nonce = str(uuid4())
        digest = intent.digest()
        target = json.loads(json.dumps(intent.target, allow_nan=False))
        request = {'version': 1, 'nonce': nonce, 'digest': digest,
                   'expires_at': token.expires_at.timestamp(), **{k:v for k,v in target.items() if k!='app'}}
        transport = None
        commit_possible = False
        try:
            transport = self.transport_factory(self.binary)
            transport.send(request)
            prepared = self._reply(transport.read(3), nonce, final=False)
            if prepared['status'] != 'prepared':
                return PressOutcome('blocked', prepared['reason'])
            if not token.permits(intent) or intent.digest()!=digest or not authorized():
                return PressOutcome('blocked', 'AUTHORIZATION_DENIED')
            if not reserve():
                return PressOutcome('blocked', 'ATTEMPT_ALREADY_RESERVED')
            if not token.permits(intent) or intent.digest()!=digest or not authorized():
                return PressOutcome('blocked', 'AUTHORIZATION_DENIED')
            # Reserve BEFORE any commit bytes: a partial write/timeout may have acted.
            commit_possible = True
            transport.send({'version':1, 'command':'commit', 'nonce':nonce, 'digest':digest})
            reply = self._reply(transport.read(4), nonce, final=True)
            if reply['status']=='blocked':
                return PressOutcome('blocked', reply['reason'])
            if reply['status']=='dispatched' and reply['native_error']==0:
                return PressOutcome('dispatched', reply['reason'], True, 0)
            return PressOutcome('uncertain', reply['reason'], True, reply['native_error'])
        except (Exception, KeyboardInterrupt):
            return PressOutcome('uncertain' if commit_possible else 'blocked',
                                'AXPRESS_IPC_UNCERTAIN' if commit_possible else 'AXPRESS_PRECOMMIT_FAILED',
                                commit_possible)
        finally:
            if transport is not None:
                try:
                    transport.close()
                except Exception:
                    pass

    @staticmethod
    def _reply(data, nonce, *, final):
        keys={'version','nonce','status','reason'} | ({'native_error'} if final else set())
        if (type(data) is not dict or set(data)!=keys or
                type(data['version']) is not int or data['version']!=1 or data['nonce']!=nonce or
                data['reason'] not in REASONS or data['status'] not in
                (('blocked','dispatched','uncertain') if final else ('prepared','blocked'))):
            raise ValueError('PROTOCOL_ERROR')
        if final and (type(data['native_error']) is not int or not -(2**31)<=data['native_error']<2**31):
            raise ValueError('PROTOCOL_ERROR')
        if data['status']=='prepared' and data['reason']!='PREPARED':
            raise ValueError('PROTOCOL_ERROR')
        if data['status']=='dispatched' and (data['reason']!='AXPRESS_RETURNED' or data['native_error']!=0):
            raise ValueError('PROTOCOL_ERROR')
        if data['status']=='blocked' and data['reason'] in ('AXPRESS_RETURNED','AXPRESS_ERROR','PREPARED'):
            raise ValueError('PROTOCOL_ERROR')
        if final and data['status']=='blocked' and data['native_error']!=0:
            raise ValueError('PROTOCOL_ERROR')
        if final and data['status']=='uncertain' and (data['reason']!='AXPRESS_ERROR' or data['native_error']==0):
            raise ValueError('PROTOCOL_ERROR')
        return data
