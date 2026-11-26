import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from live import install_bundled_bridge


class BundledBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.base=Path(self.temporary.name)/'bundle';self.base.mkdir()
        self.destination=Path(self.temporary.name)/'state';self.destination.mkdir()
        self.payload=b'MZ-test-bridge';self.fingerprint='source-fingerprint'

    def bundle(self):
        (self.base/'HornoWcfBridge.exe').write_bytes(self.payload)
        (self.base/'HornoWcfBridge.build.json').write_text(json.dumps(dict(
            source_sha256=self.fingerprint,binary_sha256=hashlib.sha256(self.payload).hexdigest())),encoding='utf-8')

    def test_source_checkout_keeps_compilation_fallback(self):
        self.assertFalse(install_bundled_bridge(self.base,self.destination,self.fingerprint))
        self.assertFalse((self.destination/'HornoWcfBridge.exe').exists())

    def test_matching_bundle_replaces_old_copy_and_leaves_no_temporary_file(self):
        self.bundle();(self.destination/'HornoWcfBridge.exe').write_bytes(b'older')
        self.assertTrue(install_bundled_bridge(self.base,self.destination,self.fingerprint))
        self.assertEqual((self.destination/'HornoWcfBridge.exe').read_bytes(),self.payload)
        self.assertEqual([p.name for p in self.destination.iterdir()],['HornoWcfBridge.exe'])

    def test_changed_csharp_source_does_not_run_stale_binary(self):
        self.bundle()
        self.assertFalse(install_bundled_bridge(self.base,self.destination,'different-source'))
        self.assertFalse((self.destination/'HornoWcfBridge.exe').exists())

    def test_corrupted_binary_preserves_previous_working_copy(self):
        self.bundle();(self.base/'HornoWcfBridge.exe').write_bytes(b'corrupted')
        destination=self.destination/'HornoWcfBridge.exe';destination.write_bytes(b'previous')
        with self.assertRaisesRegex(RuntimeError,'dañado'):
            install_bundled_bridge(self.base,self.destination,self.fingerprint)
        self.assertEqual(destination.read_bytes(),b'previous')


if __name__=='__main__':unittest.main()
