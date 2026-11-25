"""Windows-only tests of the installer's exact data preservation helper.

All paths are isolated fixtures; never enumerates/deletes the machine's actual data.
"""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'nt', 'Requires Windows PowerShell')
class InstallerUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='exam-upgrade-')
        self.root = Path(self.temp.name)
        self.backup = self.root / 'backup'
        self.dirs = [self.root / user / '微机教室考试系统' for user in ('user', 'other', 'common')]
        for index, folder in enumerate(self.dirs):
            folder.mkdir(parents=True)
            with closing(sqlite3.connect(folder / 'exam_system.db')) as db:
                db.execute('CREATE TABLE preserved (id INTEGER PRIMARY KEY, content BLOB)')
                db.execute('INSERT INTO preserved(content) VALUES (?)', (f'账号、题目、成绩-{index}'.encode(),))
                db.commit()
            (folder / 'exam_system.db-wal').write_bytes(b'wal-sidecar-fixture')
            (folder / 'exam_system.db-shm').write_bytes(b'shm-sidecar-fixture')
            (folder / 'images').mkdir()
            (folder / 'images' / '图片.png').write_bytes(bytes(range(256)))
        self.before = self.hashes()

    def tearDown(self):
        self.temp.cleanup()

    def hashes(self):
        return {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for folder in self.dirs for p in folder.rglob('*') if p.is_file()}

    def run_tool(self, mode, ok=True):
        result = subprocess.run([
            'powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
            '-File', str(ROOT / 'packaging' / 'upgrade_data.ps1'), '-Mode', mode,
            '-TestRoot', str(self.root), '-BackupRoot', str(self.backup),
            '-ResultFile', str(self.root / 'result.txt'),
        ], capture_output=True, timeout=60)
        if ok:
            self.assertEqual(result.returncode, 0, repr(result.stderr))
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def test_detect_data_left_after_uninstall(self):
        self.run_tool('detect')
        self.assertEqual((self.root / 'result.txt').read_text(encoding='utf-8-sig'), '3')
        self.assertEqual(self.hashes(), self.before)

    def test_legacy_uninstaller_deletes_every_profile_then_restore_all_bytes(self):
        self.run_tool('snapshot')
        for directory in self.dirs:
            shutil.rmtree(directory)  # exact legacy silent-uninstall behavior
        self.run_tool('restore')
        self.assertEqual(self.hashes(), self.before)
        for index, directory in enumerate(self.dirs):
            # The test sidecars aren't real SQLite WAL files; remove before opening.
            (directory / 'exam_system.db-wal').unlink()
            (directory / 'exam_system.db-shm').unlink()
            with closing(sqlite3.connect(directory / 'exam_system.db')) as db:
                self.assertEqual(db.execute('SELECT content FROM preserved').fetchone()[0], f'账号、题目、成绩-{index}'.encode())

    def test_modern_uninstaller_keeps_files_untouched(self):
        self.run_tool('snapshot')
        times = {p: p.stat().st_mtime_ns for folder in self.dirs for p in folder.rglob('*') if p.is_file()}
        self.run_tool('restore')
        self.assertEqual(self.hashes(), self.before)
        self.assertEqual(times, {p: p.stat().st_mtime_ns for p in times})

    def test_reset_clears_all_active_data_but_not_unrelated_files(self):
        unrelated = self.root / 'user' / '其他软件.txt'
        unrelated.write_text('keep')
        self.run_tool('clear')
        self.assertTrue(all(not folder.exists() for folder in self.dirs))
        self.assertEqual(unrelated.read_text(), 'keep')

    def test_corrupt_snapshot_aborts_restore_without_touching_active_data(self):
        self.run_tool('snapshot')
        manifest = json.loads((self.backup / 'manifest.json').read_text(encoding='utf-8-sig'))
        entry = manifest['directories'][-1]
        (self.backup / entry['slot'] / entry['files'][0]['path']).write_bytes(b'corrupt')
        self.run_tool('restore', ok=False)
        self.assertEqual(self.hashes(), self.before)

    def test_existing_backup_cannot_be_overwritten(self):
        self.run_tool('snapshot')
        manifest = (self.backup / 'manifest.json').read_bytes()
        self.run_tool('snapshot', ok=False)
        self.assertEqual((self.backup / 'manifest.json').read_bytes(), manifest)
        self.assertEqual(self.hashes(), self.before)

    def test_empty_machine(self):
        for directory in self.dirs:
            shutil.rmtree(directory)
        self.run_tool('snapshot')
        self.run_tool('restore')
        self.run_tool('clear')


if __name__ == '__main__':
    unittest.main()
