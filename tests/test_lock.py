"""Behavior tests use a fast KDF; the default KDF gets a separate smoke test."""
import csv
import json
import tempfile
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from locksystem import DigitalLock, SequenceLock, gate_next, table_next
from locksystem.logic import decode
from server import start_background, stop_background

ROOT = Path(__file__).resolve().parents[1]

class Clock:
    def __init__(self): self.value = 1000.0
    def __call__(self): return self.value
    def advance(self, seconds): self.value += seconds

class LogicTests(unittest.TestCase):
    def test_all_transitions(self):
        for state in range(4):
            for key in range(16):
                self.assertEqual(gate_next(state,key),table_next(state,key))

    def test_decoder(self):
        for key in range(16):
            self.assertEqual(decode(key),(int(key==10),int(key==6),int(key==9)))

    def test_sequence_and_reset(self):
        lock=SequenceLock()
        self.assertEqual([lock.press(k) for k in [10,6,9,9,10,10,6,9]],[1,2,3,0,1,0,0,0])
        lock.press(10);lock.reset();self.assertEqual(lock.state,0)

    def test_bad_inputs(self):
        for state,key in [(4,10),(-1,10),(0,16),(0,-1),(True,10),(0,'10')]:
            with self.assertRaises(ValueError): gate_next(state,key)

    def test_exported_truth_table(self):
        with (ROOT/'docs/truth-table.csv').open() as f:
            rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),64)
        for row in rows:
            q=(int(row['q1'])<<1)|int(row['q0'])
            expected=(int(row['d1'])<<1)|int(row['d0'])
            self.assertEqual(gate_next(q,int(row['key'])),expected)

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.patch=patch('locksystem.core.ITERATIONS',1000);self.patch.start()
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'lock.db'
        self.wall,self.mono=Clock(),Clock()
        self.lock=DigitalLock(self.path,wall_clock=self.wall,clock=self.mono)
    def tearDown(self):
        self.lock.close();self.temp.cleanup();self.patch.stop()
    def setup_pin(self): self.lock.setup('483729')

    def test_first_run(self):
        self.assertEqual(self.lock.status()['state'],'UNCONFIGURED')
        with self.assertRaises(ValueError): self.lock.unlock('483729')
        self.setup_pin()
        with self.assertRaises(ValueError): self.setup_pin()

    def test_pin_validation(self):
        for pin in ['12345','1'*13,'１２３４５６',123456,None,'abc123','123 45']:
            with self.assertRaises(ValueError): self.lock.setup(pin)
        self.lock.setup('000001');self.assertTrue(self.lock.unlock('000001')['ok'])

    def test_unlock_and_exact_expiry(self):
        self.setup_pin();self.lock.unlock('483729')
        self.assertIn('message',self.lock.protected_content())
        self.mono.advance(14.99);self.assertEqual(self.lock.status()['state'],'UNLOCKED')
        self.mono.advance(.01)
        with self.assertRaises(PermissionError): self.lock.protected_content()

    def test_clock_rollback_does_not_extend_open(self):
        self.setup_pin();self.lock.unlock('483729');self.wall.advance(-100)
        self.mono.advance(15);self.assertEqual(self.lock.status()['state'],'LOCKED')

    def test_manual_lock(self):
        self.setup_pin();self.lock.unlock('483729');self.lock.lock()
        with self.assertRaises(PermissionError): self.lock.protected_content()

    def test_lockout_boundary_and_correct_pin_blocked(self):
        self.setup_pin()
        for i in range(5): self.assertFalse(self.lock.unlock('999999')['ok'])
        self.assertEqual(self.lock.status()['state'],'LOCKOUT')
        self.assertFalse(self.lock.unlock('483729')['ok'])
        self.wall.advance(29.99);self.mono.advance(29.99);self.assertEqual(self.lock.status()['state'],'LOCKOUT')
        self.wall.advance(.01);self.mono.advance(.01);self.assertTrue(self.lock.unlock('483729')['ok'])

    def test_lock_does_not_clear_lockout(self):
        self.setup_pin()
        for _ in range(5):self.lock.unlock('999999')
        self.lock.lock();self.assertEqual(self.lock.status()['state'],'LOCKOUT')

    def test_restart_preserves_cooldown(self):
        self.setup_pin()
        for _ in range(5):self.lock.unlock('999999')
        self.lock.close();self.lock=DigitalLock(self.path,wall_clock=self.wall,clock=self.mono)
        self.assertEqual(self.lock.status()['state'],'LOCKOUT')

    def test_restart_relocks_and_preserves_credential(self):
        self.setup_pin();self.lock.unlock('483729');self.lock.close()
        self.lock=DigitalLock(self.path,wall_clock=self.wall,clock=self.mono)
        self.assertEqual(self.lock.status()['state'],'LOCKED');self.assertTrue(self.lock.unlock('483729')['ok'])

    def test_change_pin_requires_current_and_relocks(self):
        self.setup_pin()
        self.assertFalse(self.lock.change_pin('999999','123456')['ok'])
        self.assertTrue(self.lock.change_pin('483729','123456')['ok'])
        self.assertEqual(self.lock.status()['state'],'LOCKED')
        self.assertFalse(self.lock.unlock('483729')['ok']);self.assertTrue(self.lock.unlock('123456')['ok'])

    def test_change_pin_cannot_bypass_lockout(self):
        self.setup_pin()
        for _ in range(5): self.lock.change_pin('999999','123456')
        self.assertFalse(self.lock.change_pin('483729','123456')['ok'])

    def test_success_clears_failures(self):
        self.setup_pin();self.lock.unlock('999999');self.lock.unlock('483729')
        self.assertEqual(self.lock.status()['attempts_left'],5)

    def test_concurrent_wrong_attempts_are_serialized(self):
        self.setup_pin()
        with ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(self.lock.unlock,['999999']*12))
        self.assertTrue(all(not row['ok'] for row in results))
        self.assertEqual(self.lock.status()['attempts_left'],0)

    def test_no_plaintext_credential_or_event(self):
        self.setup_pin();self.lock.unlock('483729')
        row=self.lock.db.execute('SELECT salt,digest FROM credential').fetchone()
        self.assertEqual(len(row[0]),16);self.assertEqual(len(row[1]),32)
        self.assertNotIn('483729',json.dumps(self.lock.status()))
        self.assertNotIn(b'483729',self.path.read_bytes())

    def test_event_retention(self):
        self.setup_pin()
        for _ in range(250):self.lock.lock()
        self.assertEqual(self.lock.db.execute('SELECT count(*) FROM events').fetchone()[0],200)
        self.assertEqual(len(self.lock.status()['events']),20)

    def test_unique_salts(self):
        self.setup_pin(); other=DigitalLock(':memory:')
        try:
            other.setup('483729');self.assertNotEqual(self.lock._row()[0],other._row()[0])
        finally: other.close()

class DefaultKDFTests(unittest.TestCase):
    def test_production_parameters(self):
        lock=DigitalLock(':memory:')
        try:
            lock.setup('483729');self.assertEqual(lock._row()[2],600000)
            self.assertTrue(lock.unlock('483729')['ok'])
        finally: lock.close()

class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.server=start_background(0,Path(cls.temp.name)/'lock.db')
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'
        with urllib.request.urlopen(cls.base+'/api/session') as response:
            cls.token=json.load(response)['token']
    @classmethod
    def tearDownClass(cls):stop_background(cls.server);cls.temp.cleanup()
    def req(self,path,body=None,headers=None):
        defaults={'Origin':self.base,'X-Lock-Token':self.token,'Content-Type':'application/json'}
        defaults.update(headers or {})
        request=urllib.request.Request(self.base+path,data=body,headers=defaults)
        try:
            with urllib.request.urlopen(request) as r:return r.status,r.read(),r.headers
        except urllib.error.HTTPError as r:return r.code,r.read(),r.headers
    def test_static_and_headers(self):
        status,body,headers=self.req('/')
        self.assertEqual(status,200);self.assertIn(b'VONDOOM',body)
        self.assertEqual(headers['Cache-Control'],'no-store')
        self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])
    def test_private_files_not_served(self):
        for path in ['/server.py','/data/lock.sqlite3','/../server.py','/VonDoom.ipynb']:
            self.assertEqual(self.req(path)[0],404)
    def test_bad_host(self):self.assertEqual(self.req('/',headers={'Host':'evil.example'})[0],403)
    def test_origin_and_token(self):
        for headers in [{'Origin':'https://evil.example'},{'X-Lock-Token':'wrong'}]:
            self.assertEqual(self.req('/api/lock',b'{}',headers)[0],403)
    def test_invalid_bodies(self):
        for body in [b'{broken',b'[]',b'null',b'\xff']:
            self.assertEqual(self.req('/api/unlock',body)[0],400)
        self.assertEqual(self.req('/api/lock',b'x'*1025)[0],413)
        self.assertEqual(self.req('/api/lock',b'{}',{'Content-Type':'text/plain'})[0],415)
    def test_full_flow(self):
        self.assertEqual(self.req('/api/protected',b'{}')[0],403)
        self.assertEqual(self.req('/api/setup',b'{"pin":"483729"}')[0],200)
        status,body,_=self.req('/api/unlock',b'{"pin":"483729"}')
        self.assertEqual(status,200);self.assertTrue(json.loads(body)['ok'])
        self.assertEqual(self.req('/api/protected',b'{}')[0],200)
        self.req('/api/lock',b'{}')
        self.assertEqual(self.req('/api/protected',b'{}')[0],403)

if __name__=='__main__':unittest.main()
