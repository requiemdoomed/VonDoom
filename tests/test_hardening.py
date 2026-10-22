"""Regression tests for process ownership, clock changes and malformed requests."""
import json
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from locksystem import DigitalLock
from server import make_server, start_background, stop_background

ROOT = Path(__file__).resolve().parents[1]

class OwnershipTests(unittest.TestCase):
    def test_second_controller_rejected_then_released(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'lock.sqlite3'
            with DigitalLock(path) as first:
                with self.assertRaises(OSError): DigitalLock(path)
            with DigitalLock(path) as second:
                self.assertEqual(second.status()['state'],'UNCONFIGURED')
            second.close()  # Closing twice must be harmless.

    def test_other_process_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'lock.sqlite3'
            with DigitalLock(path):
                result=subprocess.run([sys.executable,'-c',
                    'from locksystem import DigitalLock; import sys; DigitalLock(sys.argv[1])',str(path)],
                    cwd=ROOT,capture_output=True,text=True,timeout=10)
                self.assertNotEqual(result.returncode,0)
                self.assertIn('already in use',result.stderr)

    def test_invalid_database_releases_ownership(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'lock.sqlite3'
            path.write_bytes(b'not a sqlite database')
            with self.assertRaises(sqlite3.DatabaseError): DigitalLock(path)
            path.unlink()
            with DigitalLock(path) as lock:
                self.assertEqual(lock.status()['state'],'UNCONFIGURED')

    def test_invalid_credential_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'lock.sqlite3'
            with patch('locksystem.core.ITERATIONS',1000):
                with DigitalLock(path) as lock:
                    lock.setup('483729')
                    with lock.db:
                        lock.db.execute("UPDATE credential SET digest=x'00'")
            with self.assertRaisesRegex(ValueError,'credential record is invalid'):
                DigitalLock(path)

    def test_port_validation(self):
        for port in [-1,65536,True,'8765']:
            with self.assertRaises(ValueError):make_server(port,':memory:')

    def test_bind_failure_releases_database(self):
        with tempfile.TemporaryDirectory() as folder:
            first=make_server(0,Path(folder)/'first.db')
            second_path=Path(folder)/'second.db'
            try:
                with self.assertRaises(OSError):make_server(first.server_port,second_path)
                with DigitalLock(second_path) as lock:
                    self.assertEqual(lock.status()['state'],'UNCONFIGURED')
            finally:
                first.server_close();first.lock.close()

class ClockTests(unittest.TestCase):
    def setUp(self):
        self.patch=patch('locksystem.core.ITERATIONS',1000);self.patch.start()
        self.wall=1000.;self.mono=1000.
        self.lock=DigitalLock(':memory:',wall_clock=lambda:self.wall,clock=lambda:self.mono)
        self.lock.setup('483729')
    def tearDown(self):self.lock.close();self.patch.stop()
    def block(self):
        for _ in range(5):self.lock.unlock('999999')
    def test_wall_jump_cannot_skip_live_cooldown(self):
        self.block();self.wall+=3600
        self.assertFalse(self.lock.unlock('483729')['ok'])
        self.assertEqual(self.lock.status()['cooldown'],30)
        self.mono+=30;self.assertTrue(self.lock.unlock('483729')['ok'])
    def test_wall_rollback_cannot_extend_live_cooldown(self):
        self.block();self.wall-=900;self.mono+=30
        self.assertTrue(self.lock.unlock('483729')['ok'])
    def test_wrong_pin_revokes_existing_access(self):
        self.lock.unlock('483729');self.lock.unlock('999999')
        with self.assertRaises(PermissionError):self.lock.protected_content()
    def test_repeated_blocked_requests_do_not_extend_deadline(self):
        self.block();self.mono+=10
        for _ in range(10):self.lock.unlock('999999')
        self.assertEqual(self.lock.status()['cooldown'],20)
    def test_partial_cooldown_restored(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'lock.db'
            with DigitalLock(path,wall_clock=lambda:self.wall,clock=lambda:self.mono) as lock:
                lock.setup('483729')
                for _ in range(5):lock.unlock('999999')
            self.wall+=12;self.mono+=12
            with DigitalLock(path,wall_clock=lambda:self.wall,clock=lambda:self.mono) as lock:
                self.assertEqual(lock.status()['cooldown'],18)
    def test_restart_after_expiry(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'lock.db'
            with DigitalLock(path,wall_clock=lambda:self.wall,clock=lambda:self.mono) as lock:
                lock.setup('483729')
                for _ in range(5):lock.unlock('999999')
            self.wall+=31;self.mono+=31
            with DigitalLock(path,wall_clock=lambda:self.wall,clock=lambda:self.mono) as lock:
                self.assertEqual(lock.status()['attempts_left'],5)
                self.assertTrue(lock.unlock('483729')['ok'])

class ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=start_background(0,':memory:')
        cls.port=cls.server.server_port
        response=cls.send('GET','/api/session')
        cls.token=json.loads(response.split(b'\r\n\r\n',1)[1])['token']
    @classmethod
    def tearDownClass(cls):stop_background(cls.server)
    @classmethod
    def send(cls,method,path,body=b'',extras=None,omit=()):
        headers=[('Host',f'127.0.0.1:{cls.port}')]
        if method=='POST':headers += [('Origin',f'http://127.0.0.1:{cls.port}'),
            ('X-Lock-Token',cls.token),('Content-Type','application/json'),('Content-Length',str(len(body)))]
        headers=[(k,v) for k,v in headers if k not in omit]+(extras or [])
        wire=f'{method} {path} HTTP/1.0\r\n'+''.join(f'{k}: {v}\r\n' for k,v in headers)+'\r\n'
        with socket.create_connection(('127.0.0.1',cls.port),timeout=3) as sock:
            sock.sendall(wire.encode('latin1')+body);sock.shutdown(socket.SHUT_WR)
            chunks=[]
            while True:
                chunk=sock.recv(65536)
                if not chunk:break
                chunks.append(chunk)
        return b''.join(chunks)
    def check_status(self,expected,*args,**kwargs):
        self.assertEqual(int(self.send(*args,**kwargs).split(b' ')[1]),expected)
    def test_duplicate_host(self):self.check_status(403,'GET','/',extras=[('Host','evil.example')])
    def test_duplicate_headers(self):
        for name,value in [('Origin','http://evil.example'),('Content-Length','2'),('X-Lock-Token','x'),('Content-Type','text/plain')]:
            self.check_status(400,'POST','/api/lock',b'{}',extras=[(name,value)])
    def test_missing_origin(self):self.check_status(400,'POST','/api/lock',b'{}',omit=('Origin',))
    def test_transfer_encoding(self):self.check_status(400,'POST','/api/lock',b'{}',extras=[('Transfer-Encoding','chunked')])
    def test_duplicate_json_fields(self):self.check_status(400,'POST','/api/unlock',b'{"pin":"483729","pin":"999999"}')
    def test_unknown_and_missing_fields(self):
        for body in [b'{}',b'{"pin":"483729","extra":1}']:
            self.check_status(400,'POST','/api/unlock',body)
    def test_non_ascii_token(self):self.check_status(403,'POST','/api/lock',b'{}',extras=[('X-Lock-Token','\xe9')],omit=('X-Lock-Token',))
    def test_truncated_body(self):self.check_status(400,'POST','/api/lock',b'{',extras=[('Content-Length','10')],omit=('Content-Length',))
    def test_unknown_api(self):self.check_status(404,'POST','/api/unknown',b'{}')
    def test_request_after_invalid_input(self):
        self.send('POST','/api/unlock',b'null')
        self.check_status(200,'GET','/api/status')
    def test_worker_limit_rejects_excess_connections(self):
        clients=[]
        try:
            for _ in range(8):
                sock=socket.create_connection(('127.0.0.1',self.port),timeout=3)
                clients.append(sock)
                sock.sendall(b'GET / HTTP/1.0\r\n')
            self.check_status(503,'GET','/api/status')
        finally:
            for sock in clients:sock.close()

if __name__=='__main__':unittest.main()
