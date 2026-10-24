import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

CLOUD=Path(__file__).resolve().parents[1]/'cloud'

def load(name,file):
    spec=importlib.util.spec_from_file_location(name,file);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        with patch.dict(os.environ,{'MEDIAFLOW_JOB_DIR':self.temp.name,'JOB_KEY':'fixture','APP_ORIGIN':'https://example.test'}):self.worker=load('session_worker',CLOUD/'worker.py')
        self.worker.COOKIE_FILE.write_text('# Netscape HTTP Cookie File\n')
        self.entry=load('entry',CLOUD/'runner_entry.py')
    def tearDown(self):self.temp.cleanup()
    def test_engine_is_an_unchanged_copy_of_the_verified_mac_version(self):
        manifest=json.loads((CLOUD/'engine-version.json').read_text())
        self.assertEqual(hashlib.sha256((CLOUD/'mac_runner.py').read_bytes()).hexdigest(),manifest['sourceSha256'])
        self.assertEqual(manifest['desktopVersion'],'1.1.1')
    def test_commands_match_mac_exactly_without_optional_session(self):
        baseline=load('baseline',CLOUD/'mac_runner.py');engine=self.entry.prepare_engine()
        for fmt in ('mp3','m4a','flac'):
            args=('https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M',fmt,Path('/tmp/files'),Path('/tmp/data'))
            self.assertEqual(engine.spotify_command(*args),baseline.spotify_command(*args))
        for fmt in ('mp3','m4a','flac','mp4'):
            args=('https://youtu.be/fixture',fmt,Path('/tmp/files'),True)
            self.assertEqual(engine.youtube_command(*args),baseline.youtube_command(*args))
    def test_optional_session_is_injected_without_changing_engine_source(self):
        engine=self.entry.prepare_engine(self.worker.COOKIE_FILE)
        youtube=engine.youtube_command('https://youtu.be/fixture','mp3',Path('/tmp/files'),False)
        spotify=engine.spotify_command('https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT','mp3',Path('/tmp/files'),Path('/tmp/data'))
        self.assertIn('--cookies',youtube);self.assertIn('--cookie-file',spotify)
        self.assertLess(youtube.index('--cookies'),youtube.index('--'))
    def test_session_deleted_on_failure_and_bot_error_is_actionable(self):
        w=self.worker;events=[{'type':'progress','message':'ERROR: Sign in to confirm you’re not a bot.'},{'type':'done','state':'error','message':'YouTube requested sign-in for this media.'}]
        process=type('Process',(),{'stdin':io.StringIO(),'stdout':io.StringIO(''.join(json.dumps(e)+'\n' for e in events)),'wait':lambda self:1})()
        with patch.object(w.subprocess,'Popen',return_value=process):w.download({'url':'https://youtu.be/fixture','format':'mp3','playlist':False})
        self.assertFalse(w.COOKIE_FILE.exists());self.assertEqual(w.STATE['errorCode'],'YOUTUBE_AUTH_REQUIRED');self.assertEqual(w.STATE['state'],'error')

if __name__=='__main__':unittest.main()
