import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request,urlopen
from urllib.error import HTTPError

class IncrementalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        with patch.dict(os.environ,{'MEDIAFLOW_JOB_DIR':self.temp.name,'JOB_KEY':'test-token','APP_ORIGIN':'https://example.test'}):
            spec=importlib.util.spec_from_file_location('worker',Path(__file__).resolve().parents[1]/'cloud/worker.py')
            self.worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.worker)
    def tearDown(self):self.temp.cleanup()
    def test_first_song_is_published_before_second_engine_event(self):
        w=self.worker
        class Output:
            def __iter__(stream):
                (w.BASE/'files'/'first.mp3').write_bytes(b'finished-first')
                yield json.dumps({'type':'saved','name':'first.mp3','count':1})+'\n'
                self.assertEqual([f['name'] for f in w.STATE['files']],['first.mp3'])
                self.assertEqual(w.STATE['state'],'running');self.assertFalse(w.STATE['archiveReady'])
                (w.BASE/'files'/'second.mp3').write_bytes(b'finished-second')
                yield json.dumps({'type':'saved','name':'second.mp3','count':2})+'\n'
                yield json.dumps({'type':'done','state':'complete','count':2})+'\n'
            def close(stream):pass
        process=type('Process',(),{'stdin':io.StringIO(),'stdout':Output(),'wait':lambda self:0})()
        with patch.object(w.subprocess,'Popen',return_value=process):w.download({'url':'https://youtu.be/fixture','format':'mp3','playlist':False})
        self.assertEqual(len(w.STATE['files']),2);self.assertEqual(w.STATE['state'],'complete');self.assertTrue(w.STATE['archiveReady'])
    def test_finished_song_is_downloadable_while_job_running_and_after_cancel(self):
        w=self.worker;folder=w.BASE/'files';folder.mkdir();file=folder/'first.mp3';file.write_bytes(b'finished-song');w.publish(file)
        partial=folder/'second.mp3.part';partial.write_bytes(b'partial');w.publish(partial)
        server=w.ThreadingHTTPServer(('127.0.0.1',0),w.Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with self.assertRaises(HTTPError):urlopen(base+'/status?key=wrong')
            with urlopen(base+'/file?name=first.mp3&key=test-token') as response:self.assertEqual(response.read(),b'finished-song')
            req=Request(base+'/control?key=test-token',data=b'{"action":"cancel"}',headers={'Content-Type':'application/json'})
            with urlopen(req) as response:self.assertEqual(json.load(response)['state'],'cancelled')
            with urlopen(base+'/file?name=first.mp3&key=test-token') as response:self.assertEqual(response.read(),b'finished-song')
            self.assertFalse(w.STATE['archiveReady']);self.assertEqual(len(w.STATE['files']),1)
        finally:server.shutdown();server.server_close()
    def test_pause_and_resume_only_signal_the_engine_group(self):
        w=self.worker;process=type('Process',(),{'pid':12345,'poll':lambda self:None})()
        with patch.object(w,'PROC',process),patch.object(w.os,'killpg') as kill:
            self.assertEqual(w.control('pause')['state'],'paused')
            kill.assert_called_with(12345,signal.SIGSTOP)
            self.assertEqual(w.control('resume')['state'],'running')
            kill.assert_called_with(12345,signal.SIGCONT)
            self.assertEqual(w.control('cancel')['state'],'cancelled')
            kill.assert_called_with(12345,signal.SIGTERM)

if __name__=='__main__':unittest.main()
