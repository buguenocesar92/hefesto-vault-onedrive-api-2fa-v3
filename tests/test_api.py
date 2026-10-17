import importlib.util, json, os, tempfile, threading, unittest, urllib.request, urllib.error
from pathlib import Path
s=importlib.util.spec_from_file_location('storage_api',Path(__file__).resolve().parent.parent/'api/server.py');api=importlib.util.module_from_spec(s);s.loader.exec_module(api)
class APITests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();api.ROOT=cls.temp.name;api.mounted=lambda:True
  os.environ['STORAGE_API_ADMIN_TOKEN']='a'*64;os.environ['STORAGE_API_READ_TOKEN']='r'*64
  cls.server=api.Server(('127.0.0.1',0),api.Handler);cls.base='http://127.0.0.1:'+str(cls.server.server_port)
  cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.temp.cleanup()
 def call(self,path,method='GET',body=None,token='a'*64,headers=None):
  h={'Authorization':'Bearer '+token,**(headers or {})}
  if isinstance(body,dict):body=json.dumps(body).encode();h['Content-Type']='application/json'
  req=urllib.request.Request(self.base+path,data=body,headers=h,method=method)
  try:
   with urllib.request.urlopen(req) as r:return r.status,r.read()
  except urllib.error.HTTPError as e:return e.code,e.read()
 def test_auth(self):self.assertEqual(self.call('/v1/files',token='bad')[0],401)
 def test_read_only(self):self.assertEqual(self.call('/v1/content?path=deny','PUT',b'a',token='r'*64)[0],403)
 def test_traversal(self):self.assertEqual(self.call('/v1/content?path=../outside')[0],400)
 def test_symlink(self):
  link=Path(api.ROOT)/'link';link.symlink_to('/etc')
  self.assertEqual(self.call('/v1/content?path=link/passwd')[0],400)
 def test_crud(self):
  self.assertEqual(self.call('/v1/directories','POST',{'path':'sample'})[0],201)
  self.assertEqual(self.call('/v1/content?path=sample/test.txt','PUT',b'hello')[0],200)
  self.assertEqual(self.call('/v1/content?path=sample/test.txt')[1],b'hello')
  self.assertEqual(self.call('/v1/entries','PATCH',{'source':'sample/test.txt','destination':'sample/new.txt'})[0],200)
  self.assertEqual(self.call('/v1/entries?path=sample','DELETE')[0],409)
  self.assertEqual(self.call('/v1/entries?path=sample/new.txt','DELETE')[0],200)
  self.assertEqual(self.call('/v1/entries?path=sample','DELETE')[0],200)
 def test_no_overwrite_rename(self):
  self.call('/v1/content?path=first','PUT',b'a');self.call('/v1/content?path=second','PUT',b'b')
  self.assertEqual(self.call('/v1/entries','PATCH',{'source':'first','destination':'second'})[0],409)
  self.assertEqual(self.call('/v1/content?path=second')[1],b'b')
 def test_origin(self):self.assertEqual(self.call('/v1/files',headers={'Origin':'https://evil.example'})[0],403)
 def test_upload_limit(self):
  old=api.LIMIT;api.LIMIT=1
  try:self.assertEqual(self.call('/v1/content?path=huge','PUT',b'ab')[0],413)
  finally:api.LIMIT=old
 def test_mount_missing(self):
  api.mounted=lambda:False
  try:self.assertEqual(self.call('/v1/files')[0],503)
  finally:api.mounted=lambda:True
if __name__=='__main__':unittest.main()
