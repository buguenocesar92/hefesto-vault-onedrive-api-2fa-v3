#!/usr/bin/env python3
"""Small private-storage REST gateway. No third-party Python dependencies."""
import ctypes, errno, hashlib, hmac, json, logging, os, secrets, socket, stat, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit, quote
ROOT='/data/respaldos'
LIMIT=int(os.getenv('API_MAX_UPLOAD_BYTES','2147483648'))
ORIGIN=os.getenv('PORTAL_ORIGIN','')
class APIError(Exception):
 def __init__(self,status,message): self.status,self.message=status,message

def mounted():
 with open('/proc/self/mountinfo') as f:
  return any(' /data/respaldos ' in l and ' - fuse.rclone ' in l for l in f)
def parts(path):
 if not isinstance(path,str) or len(path)>2048 or '\x00' in path or '\\' in path: raise APIError(400,'Ruta inválida')
 if path.startswith('/'): raise APIError(400,'Usar ruta relativa')
 if path=='': return []
 p=path.split('/')
 if any(x in ('','.','..') or x.startswith('.storage-upload-') for x in p): raise APIError(400,'Ruta inválida')
 return p
def directory(path):
 ps=parts(path)
 fd=os.open(ROOT,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:
  for name in ps:
   nxt=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
   os.close(fd);fd=nxt
  return fd
 except Exception:
  os.close(fd);raise
def parent(path):
 ps=parts(path)
 if not ps: raise APIError(400,'No se permite modificar la raíz')
 return directory('/'.join(ps[:-1])),ps[-1]
def rename_noreplace(srcfd,src,dstfd,dst):
 libc=ctypes.CDLL(None,use_errno=True)
 fn=getattr(libc,'renameat2',None)
 if fn is None: raise APIError(501,'Rename seguro no soportado')
 if fn(srcfd,src.encode(),dstfd,dst.encode(),1)!=0:
  e=ctypes.get_errno()
  if e in (errno.ENOSYS,errno.EINVAL,errno.EOPNOTSUPP): raise APIError(501,'El filesystem no soporta rename sin reemplazo')
  raise OSError(e,os.strerror(e))

class Handler(BaseHTTPRequestHandler):
 server_version='StorageAPI'
 sys_version=''
 def setup(self):
  super().setup();self.connection.settimeout(30)
 def log_message(self,fmt,*args):
  # Do not log headers, tokens, query strings or filenames.
  logging.info('%s %s',self.command,getattr(self,'result_status','-'))
 def json_response(self,status,obj):
  raw=json.dumps(obj,ensure_ascii=False).encode()
  self.result_status=status;self.send_response(status)
  self.send_header('Content-Type','application/json; charset=utf-8')
  self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
  self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 def authorize(self,write):
  auth=self.headers.get_all('Authorization',[])
  if len(auth)!=1 or not auth[0].startswith('Bearer '): raise APIError(401,'Bearer token requerido')
  token=auth[0][7:]
  if len(token)>512: raise APIError(401,'Token inválido')
  digest=hashlib.sha256(token.encode()).digest();scope=None
  for name,level in [('STORAGE_API_ADMIN_TOKEN','admin'),('STORAGE_API_READ_TOKEN','read')]:
   value=os.environ.get(name,'')
   if len(value)>=48 and hmac.compare_digest(digest,hashlib.sha256(value.encode()).digest()):scope=level
  if not scope: raise APIError(401,'Token inválido')
  if write and scope!='admin': raise APIError(403,'Token de solo lectura')
  origin=self.headers.get('Origin')
  if origin and origin!=ORIGIN: raise APIError(403,'Origen no permitido')
 def length(self,max_bytes):
  if self.headers.get('Transfer-Encoding'): raise APIError(400,'Transfer-Encoding no soportado; enviar Content-Length')
  values=self.headers.get_all('Content-Length',[])
  if len(values)!=1 or not values[0].isdigit(): raise APIError(411,'Content-Length requerido')
  n=int(values[0])
  if n>max_bytes: raise APIError(413,'Carga supera límite')
  return n
 def body(self):
  if self.headers.get_content_type()!='application/json': raise APIError(415,'Se requiere application/json')
  n=self.length(65536);raw=self.rfile.read(n)
  if len(raw)!=n: raise APIError(400,'Cuerpo incompleto')
  try: data=json.loads(raw)
  except (ValueError,UnicodeError):raise APIError(400,'JSON inválido')
  if not isinstance(data,dict):raise APIError(400,'Se requiere objeto JSON')
  return data
 def dispatch(self):
  self.close_connection=True
  try:
   self.authorize(self.command not in ('GET','HEAD'))
   if not mounted():raise APIError(503,'Montaje FUSE no disponible')
   parsed=urlsplit(self.path);query=parse_qs(parsed.query,keep_blank_values=True)
   path=query.get('path',[''])[0];parts(path)
   route=parsed.path
   if self.command=='GET' and route=='/v1/health':
    return self.json_response(200,{'status':'ok','storage':'mounted','max_upload_bytes':LIMIT})
   if self.command=='GET' and route=='/v1/files':
    fd=directory(path)
    try:
     try:offset=int(query.get('offset',['0'])[0]);limit=int(query.get('limit',['200'])[0])
     except ValueError: raise APIError(400,'Paginación inválida')
     if offset<0 or not 1<=limit<=1000:raise APIError(400,'Paginación inválida')
     entries=[]
     with os.scandir(fd) as it:
      for item in it:
       if item.name.startswith('.storage-upload-'):continue
       st=item.stat(follow_symlinks=False)
       if not stat.S_ISREG(st.st_mode) and not stat.S_ISDIR(st.st_mode):continue
       entries.append({'name':item.name,'type':'directory' if stat.S_ISDIR(st.st_mode) else 'file','size':st.st_size,'modified':st.st_mtime})
       if len(entries)>50000: raise APIError(413,'Directorio demasiado grande; dividir en subcarpetas')
     entries.sort(key=lambda x:(x['type']!='directory',x['name'].casefold()))
     return self.json_response(200,{'path':path,'items':entries[offset:offset+limit],'total':len(entries),'offset':offset,'limit':limit})
    finally:os.close(fd)
   if self.command=='GET' and route=='/v1/content':
    fd,name=parent(path)
    try:f=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
    finally:os.close(fd)
    with os.fdopen(f,'rb') as stream:
     st=os.fstat(stream.fileno())
     if not stat.S_ISREG(st.st_mode):raise APIError(400,'No es un archivo regular')
     self.result_status=200;self.send_response(200)
     self.send_header('Content-Type','application/octet-stream')
     self.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+quote(name,safe=''))
     self.send_header('Content-Length',str(st.st_size));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers()
     while chunk:=stream.read(1024*1024):self.wfile.write(chunk)
    return
   if self.command=='PUT' and route=='/v1/content':
    n=self.length(LIMIT);fd,name=parent(path);tmp='.storage-upload-'+secrets.token_hex(16)
    try:
     # Commit through atomic rename only after receiving the complete body.
     f=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
     with os.fdopen(f,'wb') as stream:
      remaining=n
      while remaining:
       chunk=self.rfile.read(min(1024*1024,remaining))
       if not chunk:raise APIError(400,'Carga incompleta')
       stream.write(chunk);remaining-=len(chunk)
      stream.flush();os.fsync(stream.fileno())
     os.rename(tmp,name,src_dir_fd=fd,dst_dir_fd=fd)
    finally:
     try:os.unlink(tmp,dir_fd=fd)
     except FileNotFoundError:pass
     os.close(fd)
    return self.json_response(200,{'path':path,'size':n,'status':'accepted_in_vfs','remote_durable':False})
   if self.command=='POST' and route=='/v1/directories':
    b=self.body();fd,name=parent(b.get('path'))
    try:os.mkdir(name,mode=0o770,dir_fd=fd)
    finally:os.close(fd)
    return self.json_response(201,{'path':b['path']})
   if self.command=='PATCH' and route=='/v1/entries':
    b=self.body();srcfd,src=parent(b.get('source'))
    try:
     dstfd,dst=parent(b.get('destination'))
     try:
      st=os.stat(src,dir_fd=srcfd,follow_symlinks=False)
      if not (stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode)):raise APIError(400,'Tipo no permitido')
      rename_noreplace(srcfd,src,dstfd,dst)
     finally:os.close(dstfd)
    finally:os.close(srcfd)
    return self.json_response(200,{'path':b['destination']})
   if self.command=='DELETE' and route=='/v1/entries':
    fd,name=parent(path)
    try:
     st=os.stat(name,dir_fd=fd,follow_symlinks=False)
     if stat.S_ISDIR(st.st_mode):os.rmdir(name,dir_fd=fd)
     elif stat.S_ISREG(st.st_mode):os.unlink(name,dir_fd=fd)
     else:raise APIError(400,'Tipo no permitido')
    finally:os.close(fd)
    return self.json_response(200,{'deleted':path})
   raise APIError(404,'Endpoint no encontrado')
  except APIError as e:self.json_response(e.status,{'error':e.message})
  except FileNotFoundError:self.json_response(404,{'error':'Ruta no encontrada'})
  except FileExistsError:self.json_response(409,{'error':'Destino ya existe'})
  except PermissionError:self.json_response(403,{'error':'Acceso denegado'})
  except (BrokenPipeError,ConnectionResetError,socket.timeout):pass
  except OSError as e:
   status=409 if e.errno in (errno.ENOTEMPTY,errno.EISDIR) else 400 if e.errno in (errno.ELOOP,errno.ENOTDIR) else 503
   self.json_response(status,{'error':'Operación de filesystem rechazada','code':e.errno})
  except Exception:
   logging.exception('Error interno');self.json_response(500,{'error':'Error interno'})
 do_GET=dispatch
 do_POST=dispatch
 do_PUT=dispatch
 do_PATCH=dispatch
 do_DELETE=dispatch

class Server(ThreadingHTTPServer):
 daemon_threads=True
 allow_reuse_address=True
 slots=threading.BoundedSemaphore(16)
 def process_request(self,request,address):
  if not self.slots.acquire(blocking=False):request.close();return
  try:super().process_request(request,address)
  except Exception:self.slots.release();raise
 def process_request_thread(self,request,address):
  try:super().process_request_thread(request,address)
  finally:self.slots.release()
if __name__=='__main__':
 if len(os.getenv('STORAGE_API_ADMIN_TOKEN',''))<48:raise SystemExit('Configurar token admin de al menos 48 caracteres')
 logging.basicConfig(level=logging.INFO)
 Server(('0.0.0.0',8081),Handler).serve_forever()
