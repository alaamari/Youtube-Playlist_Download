import importlib.util
import json
from pathlib import Path
import signal
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import zipfile

spec = importlib.util.spec_from_file_location('engine', Path(__file__).resolve().parents[1] / 'engine/app.py')
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)

class EngineTests(unittest.TestCase):
    def test_validation_rejects_host_spoofing_and_injection(self):
        for url in ['https://spotify.com.evil.test/playlist/abc', 'http://youtube.com/watch?v=x',
                    'https://youtube.com@evil.test/', '--exec=bad', 'https://open.spotify.com/user/foo']:
            with self.assertRaises(ValueError): e.validate({'url': url})
        with self.assertRaises(ValueError): e.validate({'url':'https://youtu.be/abc','destination':'relative'})
        with self.assertRaises(ValueError): e.validate({'url':'https://youtu.be/abc','format':'exe'})

    def test_spotify_playlist_and_audio_formats(self):
        for fmt in ['mp3','flac','m4a']:
            values = e.validate({'url':'https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=abc','format':fmt,'destination':'/tmp'})
            cmd = e.command(*values[:3], values[3], values[4])
            self.assertIn('spotdl',cmd); self.assertIn(fmt,cmd)
            self.assertIn('{list-position}',cmd[cmd.index('--output')+1])
        with self.assertRaises(ValueError): e.validate({'url':'https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT','format':'mp4'})

    def test_youtube_playlist_flag_is_honored(self):
        for playlist in (True,False):
            cmd=e.command('https://youtu.be/abc','youtube','mp3',Path('/tmp/test'),playlist)
            self.assertIn('--yes-playlist' if playlist else '--no-playlist',cmd)
            self.assertEqual(cmd[-2],'--')

    def test_worker_packages_only_job_files(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)/'job'; folder.mkdir()
            (Path(d)/'unrelated.mp3').write_bytes(b'private')
            job=dict(id='a'*32,state='queued',message='',log=[],files=[],destination=str(folder),_folder=folder)
            cmd=[sys.executable,'-c',f'from pathlib import Path; Path({str(folder / "track.mp3")!r}).write_bytes(b"media")']
            e.execute(job,cmd)
            self.assertEqual(job['state'],'complete')
            self.assertTrue(job['archiveReady'])
            archive=e.DATA/(job['id']+'.zip')
            with zipfile.ZipFile(archive) as z:
                self.assertEqual(z.namelist(),['track.mp3']); self.assertEqual(z.read('track.mp3'),b'media')
            archive.unlink()

    def test_empty_output_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            job=dict(id='b'*32,state='queued',message='',log=[],files=[],destination=d,_folder=Path(d))
            e.execute(job,[sys.executable,'-c','pass'])
            self.assertEqual(job['state'],'error')

    def test_http_auth_origins_isolation_and_cancel(self):
        server=e.ThreadingHTTPServer(('127.0.0.1',0),e.Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        base='http://127.0.0.1:'+str(server.server_port)
        def request(path,data=None,auth=True,origin=None):
            headers={'Authorization':'Bearer '+e.TOKEN} if auth else {}
            if origin: headers['Origin']=origin
            return urlopen(Request(base+path,data=json.dumps(data).encode() if data is not None else None,headers=headers),timeout=5)
        try:
            with self.assertRaises(HTTPError) as err: request('/api/health',auth=False)
            self.assertEqual(err.exception.code,401)
            with self.assertRaises(HTTPError) as err: request('/api/health',origin='https://evil.test')
            self.assertEqual(err.exception.code,401)
            self.assertEqual(json.load(request('/api/health'))['status'],'ready')
            with tempfile.TemporaryDirectory() as d, patch.object(e,'command',return_value=[sys.executable,'-c','import time; time.sleep(30)']), patch.object(e,'dependencies',return_value={'youtube':True,'spotify':True,'ffmpeg':True}):
                payload={'url':'https://youtu.be/abc','destination':d}
                first=json.load(request('/api/jobs',payload)); second=json.load(request('/api/jobs',payload))
                self.assertNotEqual(first['destination'],second['destination'])
                for job in (first,second):
                    result=json.load(request('/api/jobs/'+job['id']+'/cancel',{}))
                    self.assertEqual(result['state'],'cancelled')
                with self.assertRaises(HTTPError): request('/api/jobs/'+'c'*32+'/archive')
        finally:
            server.shutdown(); server.server_close()

if __name__=='__main__': unittest.main()
