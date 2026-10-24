import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
class WorkerHTTP(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        values={'MEDIAFLOW_JOB_DIR':self.temp.name,'JOB_KEY':'fixture-control-key-32-bytes-long-only','FILE_KEY':'fixture-file-signing-key-32-bytes-long','APP_ORIGIN':'https://youtube-playlist-download.vercel.app'}
        with patch.dict(os.environ,values):
            spec=importlib.util.spec_from_file_location('worker_fixture',ROOT/'cloud/worker.py');self.worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.worker)
        w=self.worker;w.STATE['state']='complete';(w.FILES/'first.mp3').write_bytes(b'fixture audio');w.publish(w.FILES/'first.mp3')
        self.server=w.BoundedServer(('127.0.0.1',0),w.Handler);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.base='http://127.0.0.1:'+str(self.server.server_port)
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
    def request(self,path,headers=None,body=None):
        request=urllib.request.Request(self.base+path,headers=headers or {},data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(request,timeout=3) as r:return r.status,r.headers,r.read()
        except urllib.error.HTTPError as e:return e.code,e.headers,e.read()
    def test_control_credentials_are_not_accepted_in_query_strings(self):
        w=self.worker
        self.assertEqual(self.request('/status?key='+w.KEY)[0],401)
        code,headers,data=self.request('/status',{'Authorization':'Bearer '+w.KEY});self.assertEqual(code,200)
        state=json.loads(data);self.assertIn('token',state['files'][0]);self.assertNotIn(w.KEY,data.decode());self.assertEqual(headers['Cache-Control'],'no-store')
    def test_file_links_are_scoped_and_cannot_control_a_job(self):
        w=self.worker;token=w.file_token('first.mp3');query=urllib.parse.urlencode({'name':'first.mp3','token':token})
        self.assertEqual(self.request('/file?'+query)[2],b'fixture audio')
        bad=urllib.parse.urlencode({'name':'second.mp3','token':token});self.assertEqual(self.request('/file?'+bad)[0],401)
        self.assertEqual(self.request('/control',{'Authorization':'Bearer '+token,'Origin':w.ORIGIN},body={'action':'cancel'})[0],401)
        self.assertEqual(self.request('/control',{'Authorization':'Bearer '+w.KEY,'Origin':'https://evil.test'},body={'action':'cancel'})[0],403)
    def test_unlisted_paths_symlinks_and_oversized_files_stay_private(self):
        w=self.worker
        outside=Path(self.temp.name)/'private.txt';outside.write_text('private');(w.FILES/'escape.mp3').symlink_to(outside);w.publish(w.FILES/'escape.mp3')
        with (w.FILES/'oversized.mp3').open('wb') as f:f.truncate(w.MAX_FILE+1)
        w.publish(w.FILES/'oversized.mp3');self.assertEqual(len(w.STATE['files']),1)
        name='../private.txt';query=urllib.parse.urlencode({'name':name,'token':w.file_token(name)});self.assertEqual(self.request('/file?'+query)[0],404)
    def test_transfer_budget_and_expiry_are_enforced(self):
        w=self.worker;w.TRANSFER=w.MAX_TRANSFER
        query=urllib.parse.urlencode({'name':'first.mp3','token':w.file_token('first.mp3')});self.assertEqual(self.request('/file?'+query)[0],429)
        w.EXPIRES=0;self.assertEqual(self.request('/status',{'Authorization':'Bearer '+w.KEY})[0],410)

if __name__=='__main__':unittest.main()
