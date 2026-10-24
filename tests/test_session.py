import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        with patch.dict(os.environ,{'MEDIAFLOW_JOB_DIR':self.temp.name,'JOB_KEY':'fixture','APP_ORIGIN':'https://example.test'}):
            spec=importlib.util.spec_from_file_location('session_worker',Path(__file__).resolve().parents[1]/'cloud/worker.py')
            self.worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.worker)
        self.worker.COOKIE_FILE.write_text('# Netscape HTTP Cookie File\n')
    def tearDown(self):self.temp.cleanup()
    def test_youtube_session_is_passed_to_downloader_and_deleted_on_failure(self):
        w=self.worker;calls=[]
        with patch.object(w,'run',side_effect=lambda cmd: calls.append(cmd) or False):
            w.download({'provider':'youtube','url':'https://youtu.be/fixture','format':'mp3','playlist':False})
        self.assertIn('--cookies',calls[0]);self.assertIn(str(w.COOKIE_FILE),calls[0])
        self.assertFalse(w.COOKIE_FILE.exists())
    def test_spotify_session_used_only_for_audio_and_deleted_on_completion(self):
        w=self.worker;calls=[]
        def run(cmd):
            calls.append(cmd)
            if 'save' in cmd:(w.BASE/'tracks.spotdl').write_text(json.dumps([{'url':'https://open.spotify.com/track/fixture'}]))
            else:(w.BASE/'files'/'first.mp3').write_bytes(b'fixture')
            return True
        with patch.object(w,'run',side_effect=run):w.download({'provider':'spotify','url':'https://open.spotify.com/playlist/fixture','format':'mp3'})
        self.assertNotIn('--cookie-file',calls[0]);self.assertIn('--cookie-file',calls[1])
        self.assertFalse(w.COOKIE_FILE.exists());self.assertEqual(w.STATE['state'],'complete')
        import zipfile
        with zipfile.ZipFile(w.BASE/'playlist.zip') as archive:self.assertEqual(archive.namelist(),['first.mp3'])
    def test_bot_error_produces_actionable_auth_state(self):
        w=self.worker
        process=type('Process',(),{'stdout':io.StringIO('ERROR: Sign in to confirm you’re not a bot.\n'),'wait':lambda self:1})()
        with patch.object(w.subprocess,'Popen',return_value=process):
            w.download({'provider':'youtube','url':'https://youtu.be/fixture','format':'mp3','playlist':False})
        self.assertEqual(w.STATE['errorCode'],'YOUTUBE_AUTH_REQUIRED')
        self.assertIn('cookies.txt',w.STATE['message'])
        self.assertFalse(w.COOKIE_FILE.exists())

if __name__=='__main__':unittest.main()
