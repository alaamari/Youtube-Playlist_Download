import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import urlopen

class IncrementalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        with patch.dict(os.environ,{'MEDIAFLOW_JOB_DIR':self.temp.name,'JOB_KEY':'test-token','APP_ORIGIN':'https://example.test'}):
            spec=importlib.util.spec_from_file_location('worker',Path(__file__).resolve().parents[1]/'cloud/worker.py')
            self.worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.worker)
    def tearDown(self):self.temp.cleanup()
    def test_first_spotify_song_published_before_second_download(self):
        w=self.worker;calls=[]
        def run(cmd,on_line=None):
            calls.append(cmd)
            if 'save' in cmd:
                (w.BASE/'tracks.spotdl').write_text(json.dumps([{'url':'https://open.spotify.com/track/first'},{'url':'https://open.spotify.com/track/second'}]))
            else:
                index=sum('download' in call for call in calls)
                if index==2:
                    self.assertEqual([f['name'] for f in w.STATE['files']],['001.mp3'])
                    self.assertEqual(w.STATE['state'],'running')
                    self.assertFalse(w.STATE['archiveReady'])
                (w.BASE/'files'/f'{index:03}.mp3').write_bytes(b'complete-audio')
            return True
        with patch.object(w,'run',side_effect=run):w.download({'provider':'spotify','url':'https://open.spotify.com/playlist/test','format':'mp3'})
        self.assertEqual(len(w.STATE['files']),2)
        self.assertTrue(w.STATE['archiveReady'])
        self.assertTrue(all(cmd[cmd.index('--threads')+1]=='1' for cmd in calls if 'download' in cmd))
    def test_finished_song_is_downloadable_while_job_running(self):
        w=self.worker;folder=w.BASE/'files';folder.mkdir();file=folder/'first.mp3';file.write_bytes(b'finished-song');w.publish(file)
        # Partial files and unrelated paths cannot be published.
        partial=folder/'second.mp3.part';partial.write_bytes(b'partial');w.publish(partial)
        server=w.ThreadingHTTPServer(('127.0.0.1',0),w.Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with urlopen(f'http://127.0.0.1:{server.server_port}/file?name=first.mp3&key=test-token') as response:
                self.assertEqual(response.read(),b'finished-song')
            self.assertEqual(w.STATE['state'],'running')
            self.assertFalse(w.STATE['archiveReady'])
            self.assertEqual(len(w.STATE['files']),1)
        finally:server.shutdown();server.server_close()

if __name__=='__main__':unittest.main()
